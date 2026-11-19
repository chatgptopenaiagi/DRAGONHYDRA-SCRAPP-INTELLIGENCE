"""Versioned AI tools: bounded reads and owner-review requests, with durable receipts."""
import json,uuid
from contextlib import closing
from .contracts import now,fingerprint,Blocked
from .cloud_manager import scrub
from .evidence_tools import safe_record

S={'type':'string','maxLength':200};LIMIT={'type':'integer','minimum':1,'maximum':100}
DEFINITIONS={
 'get_system_status':('Application counts, health and mode',{}),
 'get_hardware_metrics':('Measured CPU, RAM, NVIDIA GPU and application process metrics',{}),
 'list_dragonhydra_sources':('Configured data sources; credentials and file paths excluded',{'limit':LIMIT}),
 'list_football_competitions':('Competitions present in a bounded retained observation sample',{'source':S,'search':S,'limit':LIMIT}),
 'query_football_results':('Retained football fixtures and results with provenance',{'source':S,'search':S,'limit':LIMIT}),
 'query_historical_odds':('Retained bookmaker quotations, not predictions',{'source':S,'search':S,'limit':LIMIT}),
 'get_api_provider_status':('Actual saved football provider status without keys',{}),
 'get_postgresql_status':('Actual PostgreSQL connection and selected datastore',{}),
 'list_postgresql_databases':('Actual accessible PostgreSQL database catalog',{}),
 'list_postgresql_schemas':('Actual PostgreSQL schema catalog',{}),
 'list_postgresql_tables':('Tables in the owned DRAGONHYDRA schema',{}),
 'describe_postgresql_table':('Real PostgreSQL columns and types',{'table':S}),
 'run_bounded_postgresql_select':('Simple SELECT columns FROM owned_table LIMIT n; functions and compound SQL prohibited',{'sql':{'type':'string','maxLength':1000},'table':S,'limit':LIMIT}),
 'query_sports_data':('Bounded PostgreSQL sports records',{'table':S,'limit':LIMIT}),
 'inspect_postgresql_migrations':('Verified migration receipts in PostgreSQL',{'limit':LIMIT}),
 'get_database_integrity':('Actual observation and provenance counts in the selected datastore',{}),
 'get_postgresql_mcp_status':('Last genuine MCP query comparison; never infer connection from registration',{}),
 'inspect_import_receipts':('Actual import receipts and identities',{'receipt_id':S,'limit':LIMIT}),
 'compare_football_providers':('Compare original football records without merging uncertain identities',{'source':S,'search':S,'limit':LIMIT}),
 'read_application_diagnostics':('Recent redacted application errors and task states',{'limit':LIMIT}),
 'request_csv_import':('Stage an owner action to open the CSV wizard; never select or import files automatically',{'reason':S}),
 'request_database_sync':('Stage a verified local SQLite snapshot migration for owner execution',{'source':S,'reason':S}),
 'request_engineering_diagnostic':('Stage an instruction for owner approval to the existing Codex thread; no cloud shell access',{'instruction':{'type':'string','maxLength':2000}}),
}
MAPPING={'list_football_competitions':'list_competitions','query_football_results':'search_historical_results','query_historical_odds':'query_available_odds','compare_football_providers':'compare_provider_records'}

class Registry:
    def __init__(self,rt):self.rt=rt;self.store=rt.store
    def contracts(self):
        return [{'name':n,'description':d,'input_schema':{'type':'object','properties':p,'additionalProperties':False},'enabled':self.store.state('tool-enabled',n)!=False,'permission':'OWNER_ACTION_REQUEST' if n.startswith('request_') else 'BOUNDED_READ','provider':'DRAGONHYDRA local','last_result':self.store.state('tool-last',n)} for n,(d,p) in DEFINITIONS.items()]
    def enable(self,name,enabled):
        if name not in DEFINITIONS or type(enabled) is not bool:raise ValueError('Unknown tool or invalid switch')
        self.store.state('tool-enabled',name,enabled);return {'name':name,'enabled':enabled}
    def validate(self,name,args):
        if name not in DEFINITIONS or not isinstance(args,dict) or set(args)-set(DEFINITIONS[name][1]):raise ValueError('Unknown tool or argument')
        if self.store.state('tool-enabled',name)==False:raise Blocked('This tool is disabled by the owner')
        for key,v in args.items():
            rule=DEFINITIONS[name][1][key]
            if rule['type']=='integer':
                if type(v) is not int or not rule['minimum']<=v<=rule['maximum']:raise ValueError('Tool row limit must be 1–100')
            elif not isinstance(v,str) or len(v)>rule.get('maxLength',200) or ('enum' in rule and v not in rule['enum']):raise ValueError('Invalid tool argument: '+key)
    def run(self,name,args,session_id=None):
        receipt={'id':uuid.uuid4().hex,'tool':name,'at':now(),'session_id':session_id,'state':'RUNNING'}
        self.store.state('tool-receipt',receipt['id'],receipt)
        try:
            self.validate(name,args);args=scrub(args,self.rt.cloud.secrets());out=self.execute(name,args);out=scrub(out,self.rt.cloud.secrets())
            if len(json.dumps(out).encode())>40000:raise ValueError('Tool evidence exceeds 40 KB. Narrow the query; no oversized result was shared.')
            receipt.update(state='PASS',arguments=scrub(args,self.rt.cloud.secrets()),output=out,fingerprint=fingerprint(out))
        except Exception as e:receipt.update(state='BLOCKED' if isinstance(e,Blocked) else 'FAIL',error=scrub(str(e) if isinstance(e,(ValueError,Blocked)) else 'Tool operation failed ('+type(e).__name__+')',self.rt.cloud.secrets()))
        receipt['completed_at']=now();self.store.state('tool-receipt',receipt['id'],receipt);self.store.state('tool-last',name,{k:receipt[k] for k in ('id','state','at')});return receipt
    def execute(self,n,a):
        rt=self.rt;limit=a.get('limit',20)
        if n in ('query_football_results','query_historical_odds'):
            selected=self.store.query({k:a[k] for k in ('source','search') if a.get(k)}|{'kind':'SPORTS_RESULT' if n=='query_football_results' else 'SPORTS_ODDS'},limit)
            return {'total_matching':selected['total'],'returned':len(selected['rows']),'records':[safe_record(r) for r in selected['rows']],'limitation':'Retained observations only; bookmaker prices are not predictions or a claim of live availability.'}
        if n=='list_football_competitions':return {'competitions':self.store.competitions(a),'limit':limit,'limitation':'Provider identities remain distinct.'}
        if n in MAPPING:return rt.evidence_tools.run(MAPPING[n],a)
        if n=='get_hardware_metrics':return rt.hardware.sample()
        if n=='get_system_status':
            s=rt.status();return {k:s[k] for k in ('product','version','mode','storage','uptime_seconds','pid','disk_free','database_bytes','recovery')}|{'observations':s['summary']['observations'],'provenance':s['summary']['provenance']}
        if n=='list_dragonhydra_sources':return [{k:s.get(k) for k in ('id','name','adapter','kind','origin','enabled','last_success')} for s in self.store.sources()[:limit]]
        if n=='get_api_provider_status':return [{k:p.get(k) for k in ('slot','name','state','effective_state','credential_status','last_success','last_checked','last_result','quota')} for p in rt.providers.list()]
        if n=='get_postgresql_status':return rt.postgres.status()
        if n=='list_postgresql_databases':return rt.postgres.databases()
        if n=='list_postgresql_schemas':return rt.postgres.schemas()
        if n=='list_postgresql_tables':return rt.postgres.tables()
        if n=='describe_postgresql_table':return rt.postgres.describe(a.get('table','observations'))
        if n in ('query_sports_data','run_bounded_postgresql_select'):return rt.postgres.query(a)
        if n=='inspect_postgresql_migrations':return rt.postgres.query({'table':'migration_history','limit':limit})
        if n=='get_database_integrity':return {k:v for k,v in self.store.summary().items() if k not in ('events','receipts','series')}
        if n=='get_postgresql_mcp_status':return rt.postgres.status()['mcp']
        if n=='inspect_import_receipts':return self.store.receipt(a['receipt_id']) if a.get('receipt_id') else self.store.summary()['receipts'][:limit]
        if n=='read_application_diagnostics':return {'events':self.store.summary()['events'][:limit],'tasks':[{k:t.get(k) for k in ('id','state','error','updated_at')} for t in self.store.tasks()[:limit]],'integrity':self.store.integrity}
        if n.startswith('request_'):
            action={'id':uuid.uuid4().hex,'kind':n,'arguments':a,'at':now(),'state':'AWAITING_OWNER','message':'No data or code was changed. The owner must execute this action from the application.'};self.store.state('owner-action',action['id'],action);return action
        raise ValueError('Tool implementation unavailable')
    def action(self,id,approve=False):
        a=self.store.state('owner-action',id)
        if not a or a['state']!='AWAITING_OWNER':raise ValueError('Owner action is missing or already handled')
        a['state']='EXECUTING' if approve else 'DECLINED';self.store.state('owner-action',id,a)
        if approve:
            try:
                n=a['kind'];b=a['arguments']
                result={'open_view':'import-wizard'} if n=='request_csv_import' else self.rt.postgres.migrate(self.store.path) if n=='request_database_sync' else self.rt.engineering.submit(b.get('instruction',''))
                a.update(state='COMPLETE',result=result)
            except Exception as e:a.update(state='BLOCKED',error=str(e) if isinstance(e,(ValueError,Blocked)) else 'Owner action failed')
        a['completed_at']=now();self.store.state('owner-action',id,a);return a
