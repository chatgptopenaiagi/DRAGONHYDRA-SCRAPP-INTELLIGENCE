"""Bounded, read-only tool contracts. No arbitrary SQL or model-directed writes."""
import json,re
from .contracts import fingerprint,now
TOOL_NAMES=('list_data_sources','list_competitions','list_football_matches','search_historical_results','query_match_statistics','query_available_odds','inspect_import_receipt','inspect_sql_health','compare_provider_records','describe_table_schema','run_bounded_readonly_query')
SCHEMA={'type':'object','properties':{'source':{'type':'string','maxLength':80},'search':{'type':'string','maxLength':200},'limit':{'type':'integer','minimum':1,'maximum':100},'receipt_id':{'type':'string','maxLength':80},'table':{'type':'string','enum':['observations','sources','receipts','tasks','analyses']},'query_id':{'type':'string','enum':['observations_recent','football_results','odds_quotes','sources','receipts_recent']}},'additionalProperties':False}
SAFE_META=('contract','provider','provider_slot','competition','season','home','away','home_team','away_team','home_goals','away_goals','hg','ag','date','scheduled_at','reported_at','classification','bookmaker','market','outcome','match_id','fixture_id','score_period','name','team','rank','points')
def safe_record(r):
    return {**{k:r.get(k) for k in ('id','source_id','kind','key','origin','value','unit','observed_at','collected_at','issue_at','valid_at','raw_hash')},'text':str(r.get('text') or '')[:1000],'metadata':{k:v for k,v in r.get('metadata',{}).items() if k in SAFE_META}}
class EvidenceTools:
    def __init__(self,store,sql):self.store=store;self.sql=sql
    def contracts(self):return [{'name':n,'description':n.replace('_',' ')+'; read only, bounded output','input_schema':SCHEMA,'maximum_rows':100,'writes':False} for n in TOOL_NAMES]
    def run(self,name,args):
        if name not in TOOL_NAMES or not isinstance(args,dict) or set(args)-set(SCHEMA['properties']):raise ValueError('Unknown read-only tool or argument')
        limit=args.get('limit',20)
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('Choose 1–100 rows')
        if any(not isinstance(v,str) or len(v)>200 for k,v in args.items() if k!='limit'):raise ValueError('Invalid bounded tool argument')
        if name=='run_bounded_readonly_query':
            name={'observations_recent':'observations','football_results':'search_historical_results','odds_quotes':'query_available_odds','sources':'list_data_sources','receipts_recent':'receipts'}.get(args.get('query_id'))
            if name is None:raise ValueError('Select a documented query template; arbitrary SQL is not accepted')
        if name=='list_data_sources':out=self.store.sources()[:limit]
        elif name=='inspect_sql_health':out=self.sql.status()
        elif name=='inspect_import_receipt':
            out=self.store.receipt(args.get('receipt_id',''))
            if out is None:raise ValueError('Import receipt not found')
        elif name=='receipts':out=self.store.summary()['receipts'][:limit]
        elif name=='describe_table_schema':
            table=args.get('table','observations')
            if table not in SCHEMA['properties']['table']['enum']:raise ValueError('Table is outside the read-only tool allowlist')
            with self.store.lock:out=[dict(x) for x in self.store.c.execute('PRAGMA table_info('+table+')')]
        elif name=='compare_provider_records':
            from .football_comparison import compare
            out=compare(self.store,{k:args[k] for k in ('source','search') if k in args});out['groups']=out['groups'][:limit];out['unmatched']=out['unmatched'][:limit]
        else:
            filters={k:args[k] for k in ('source','search') if args.get(k)};allrows=self.store.query(filters,1000);rows=allrows['rows']
            if name in ('list_football_matches','search_historical_results','query_match_statistics'):rows=[r for r in rows if r['kind']=='SPORTS_RESULT' or r.get('metadata',{}).get('contract') in ('football.fixture/1','football.result/1')]
            if name=='query_available_odds':rows=[r for r in rows if r['kind']=='SPORTS_ODDS']
            if name=='list_competitions':
                out=[{'competition':c,'source_id':s} for s,c in sorted({(r['source_id'],str(r.get('metadata',{}).get('competition'))) for r in rows if r.get('metadata',{}).get('competition') is not None})][:limit]
            elif name=='query_match_statistics':
                values=[float(r['value']) for r in rows if r.get('value') is not None and r['kind']=='SPORTS_RESULT'];out={'sampled_results':len(values),'mean_recorded_total_goals':sum(values)/len(values) if values else None,'inputs':[r['id'] for r in rows[:limit]],'limitation':'Bounded sample; no future probability or observed odds inferred'}
            else:out=[safe_record(r) for r in rows[:limit]]
        return {'tool':name,'at':now(),'output':out,'fingerprint':fingerprint(out),'read_only':True,'limit':limit,'limitations':'Results are bounded; original records and AI interpretations remain separate'}
