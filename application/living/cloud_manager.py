"""Protected AI configuration, single-use sharing approval, budgets and durable receipts."""
import json,re,threading,time,uuid
from .contracts import now,fingerprint,Blocked
from .credentials import Vault
from .cloud_adapters import CATALOG,Adapter,validate_endpoint
from .evidence_tools import safe_record
from .provider_transport import redact
from .net import NetworkError

def scrub(value,secrets=()):
    if isinstance(value,dict):return {k:('[REDACTED]' if re.search(r'(?i)(password|secret|authorization|api.?key|access.?token)',k) else scrub(v,secrets)) for k,v in value.items()}
    if isinstance(value,list):return [scrub(x,secrets) for x in value]
    if isinstance(value,str):return re.sub(r'sk-(?:proj-)?[A-Za-z0-9_-]{20,}','[REDACTED]',redact(value,secrets))
    return value

class Cloud:
    def __init__(self,store,data,mode,knowledge,tools,mocks=()):
        self.store=store;self.mode=mode;self.knowledge=knowledge;self.tools=tools;self.mocks=mocks;self.vault=Vault(data,'cloud');self.lock=threading.RLock();self.previews={}
        for id,(_,endpoint,_,_) in CATALOG.items():
            if not store.state('cloud',id):store.state('cloud',id,dict(id=id,endpoint=endpoint,enabled=False,model='',max_output_tokens=512,max_daily_requests=10,timeout=20,state='UNCONFIGURED'))
        for r in store.states('cloud-receipt'):
            if r['state']=='RUNNING':r.update(state='INTERRUPTED',error='Request outcome is unknown after interruption. Inspect the provider before deliberately retrying; no automatic paid replay.');store.state('cloud-receipt',r['id'],r)
    def config(self,id):
        if id not in CATALOG:raise ValueError('Unknown cloud provider')
        return self.store.state('cloud',id)
    def binding(self,c):return fingerprint(['dh.cloud/1',c['id'],c['endpoint']])
    def public(self,c):
        id=c['id'];name,_,docs,kind=CATALOG[id];return {**c,'name':name,'docs':docs,'protocol':kind,'credential_status':self.vault.status(id,self.binding(c)),'effective_state':'OFFLINE' if id!='local' and self.mode()=='offline' else 'DISABLED' if not c['enabled'] else c['state'],'usage':self.store.state('cloud-budget',id) or {},'cost_estimate':None,'cost_note':'Actual cost is not inferred from token counts. Review your provider pricing/account. No subscription is created.'}
    def list(self):return [self.public(self.config(id)) for id in CATALOG]
    def configure(self,b):
        if set(b)-{'id','endpoint','enabled','model','max_output_tokens','max_daily_requests','timeout'}:raise ValueError('Unknown AI configuration field; use the protected credential operation for keys')
        c={**self.config(b.get('id')),**b};c['endpoint']=c['endpoint'].rstrip('/');validate_endpoint(c['id'],c['endpoint'],self.mocks)
        if type(c['enabled']) is not bool or not isinstance(c['model'],str) or len(c['model'])>160 or c['model'] and (not re.fullmatch(r'[A-Za-z0-9_./:@-]{1,160}',c['model']) or c['model'].startswith('sk-')):raise ValueError('Invalid AI configuration')
        for k,lo,hi in [('max_output_tokens',16,4096),('max_daily_requests',1,100),('timeout',1,45)]:
            if type(c[k]) is not int or not lo<=c[k]<=hi:raise ValueError('Invalid '+k.replace('_',' '))
        c.update(state='CONFIGURED',last_result=None);self.store.state('cloud',c['id'],c);return self.public(c)
    def credential(self,b,remove=False):
        c=self.config(b['id'])
        if remove:result=self.vault.remove(c['id']);c.update(state='UNCONFIGURED',enabled=False);self.store.state('cloud',c['id'],c);return result
        validate_endpoint(c['id'],c['endpoint'],self.mocks);result=self.vault.save(c['id'],self.binding(c),b.get('key'));c.update(credential_changed_at=now(),state='CONFIGURED');self.store.state('cloud',c['id'],c);return result
    def ready(self,id):
        c=self.config(id)
        if id!='local' and self.mode()!='connected':raise Blocked('Offline mode: switch to Configured connections before contacting a cloud provider')
        if not c['enabled']:raise Blocked('Enable this explicitly configured AI provider first')
        validate_endpoint(id,c['endpoint'],self.mocks)
        key='' if id=='local' and self.vault.status(id,self.binding(c))=='MISSING' else self.vault.get(id,self.binding(c))
        return c,Adapter(c,key,self.mocks)
    def reserve(self,c):
        with self.lock:
            b=self.store.state('cloud-budget',c['id']) or {};day=now()[:10]
            if b.get('day')!=day:b={'day':day,'requests':0,'reported_tokens':0,'scope':'Only requests made by this DRAGONHYDRA workspace; not account-wide usage'}
            if time.time()<b.get('retry_at',0):raise Blocked('Provider retry delay is still active')
            if b['requests']>=c['max_daily_requests']:raise Blocked('The configured daily application request limit has been reached')
            b['requests']+=1;b['last_request']=now();self.store.state('cloud-budget',c['id'],b)
    def failure(self,c,e):
        state='AUTHENTICATION_FAILED' if isinstance(e,NetworkError) and e.status in (401,403) else 'RATE_LIMITED' if isinstance(e,NetworkError) and e.status==429 else 'FAILED'
        if getattr(e,'code',None)=='ACCOUNT_ALLOWANCE_EXHAUSTED':state='ACCOUNT_ALLOWANCE_EXHAUSTED'
        message=str(e) if isinstance(e,(ValueError,Blocked)) else 'Request failed; no automatic retry was attempted'
        c.update(state=state,last_checked=now(),last_result={'error':message,'http_status':getattr(e,'status',None)});self.store.state('cloud',c['id'],c)
        if state=='RATE_LIMITED':
            b=self.store.state('cloud-budget',c['id']) or {};delay=getattr(e,'headers',{}).get('retry-after','60');b['retry_at']=time.time()+max(60,min(int(delay) if str(delay).isdigit() else 60,86400));self.store.state('cloud-budget',c['id'],b)
    def test(self,id):
        c,a=self.ready(id);self.reserve(c)
        try:r=scrub(a.test(),[a.key]+self.secrets());c.update(state='CONNECTED',models=r['models'],last_checked=now(),last_success=now(),last_result=r);self.store.state('cloud',id,c);return self.public(c)
        except Exception as e:self.failure(c,e);raise
    def secrets(self):
        values=[]
        for id in CATALOG:
            c=self.config(id)
            if self.vault.status(id,self.binding(c))=='SAVED':values.append(self.vault.get(id,self.binding(c)))
        # Football credentials are also scrubbed if they occur in selected text.
        from .football_providers import ADAPTERS
        vault=Vault(self.vault.data)
        for c in self.store.states('provider'):
            try:
                a=ADAPTERS[c['slot']];binding=fingerprint([c['slot'],a.name,c.get('mock_origin') or a.base,a.auth,a.key_name]);values.append(vault.get(c['slot'],binding))
            except (ValueError,KeyError):pass
        return values
    def preview(self,b):
        c=self.config(b['id']);prompt=b.get('prompt','');ids=b.get('observation_ids',[]);knowledge=b.get('knowledge_ids',[])
        if not isinstance(prompt,str) or not 1<=len(prompt)<=2000:raise ValueError('Enter a question of 1–2000 characters')
        if not isinstance(ids,list) or len(ids)>20 or not isinstance(knowledge,list) or len(knowledge)>5:raise ValueError('Select at most 20 observations and 5 knowledge sources')
        if any(not isinstance(i,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',i) for i in ids+knowledge):raise ValueError('Invalid evidence identity')
        with self.store.lock:
            records=[safe_record(json.loads(r[0])) for i in dict.fromkeys(ids) for r in self.store.c.execute('SELECT payload FROM observations WHERE id=?',(i,))]
        if len(records)!=len(set(ids)):raise ValueError('Selected observation no longer exists; refresh the preview')
        payload={'question':prompt,'observations':records,'knowledge':self.knowledge.query(ids=knowledge),'classification':'AI_INTERPRETATION_REQUEST'}
        if b.get('tool'):
            if b['tool']['name'] not in ('list_competitions','list_football_matches','search_historical_results','query_match_statistics','query_available_odds','describe_table_schema','compare_provider_records'):raise ValueError('This tool output is local-only; select observation records for cloud sharing')
            payload['tool_evidence']=self.tools.run(b['tool']['name'],b['tool'].get('arguments',{}))
        payload=scrub(payload,self.secrets());size=len(json.dumps(payload).encode())
        if size>32000:raise ValueError('Selected evidence exceeds 32 KB. Narrow the selection; nothing was sent')
        id=uuid.uuid4().hex;preview={'id':id,'provider':c['id'],'endpoint':c['endpoint'],'model':c['model'],'payload':payload,'bytes':size,'fingerprint':fingerprint(payload),'expires_at':time.time()+300,'configuration_fingerprint':fingerprint(c),'cost_estimate':None,'request_limit':c['max_daily_requests'],'max_output_tokens':c['max_output_tokens']}
        with self.lock:
            self.previews={k:v for k,v in self.previews.items() if v['expires_at']>time.time()}
            if len(self.previews)>=50:raise ValueError('Too many pending previews; wait for expiration')
            self.previews[id]=preview
        return preview
    def run(self,b):
        if b.get('confirm_share') is not True:raise ValueError('Inspect and explicitly approve the selected evidence before sending')
        with self.lock:p=self.previews.pop(b.get('preview_id'),None)
        if not p or p['expires_at']<time.time() or p['fingerprint']!=b.get('fingerprint'):raise ValueError('Sharing preview expired or already used. Preview again')
        c,a=self.ready(p['provider'])
        if fingerprint(c)!=p['configuration_fingerprint']:raise ValueError('Provider configuration changed; preview the request again')
        self.reserve(c);receipt={'id':uuid.uuid4().hex,'provider':c['id'],'model':c['model'],'at':now(),'state':'RUNNING','classification':'AI_INTERPRETATION','input':p['payload'],'input_fingerprint':p['fingerprint'],'endpoint':c['endpoint'],'cost_estimate':None};self.store.state('cloud-receipt',receipt['id'],receipt)
        try:
            r=a.run(json.dumps(p['payload'],ensure_ascii=False));receipt.update(scrub(r,[a.key]+self.secrets()),completed_at=now());c=self.config(c['id']);c.update(state='CONNECTED',last_success=now());self.store.state('cloud',c['id'],c)
            usage=r.get('usage',{});budget=self.store.state('cloud-budget',c['id']);budget['last_usage']=usage;budget['reported_tokens']+=sum(int(usage.get(k,0)) for k in ('input_tokens','output_tokens','prompt_tokens','completion_tokens'));self.store.state('cloud-budget',c['id'],budget)
        except Exception as e:receipt.update(state='FAILED',error=str(e) if isinstance(e,(ValueError,Blocked)) else 'Inference failed',http_status=getattr(e,'status',None));self.failure(c,e)
        self.store.state('cloud-receipt',receipt['id'],receipt);return receipt
    def inspect(self,id,stop=False):
        r=self.store.state('cloud-receipt',id)
        if not r or not r.get('task_id'):raise ValueError('No remote task associated with this receipt')
        c,a=self.ready(r['provider'])
        if c['endpoint']!=r['endpoint']:raise ValueError('Task endpoint changed; restore its original configuration')
        self.reserve(c)
        try:r.update(scrub(a.inspect(r['task_id'],stop),self.secrets()),checked_at=now());self.store.state('cloud-receipt',id,r);return r
        except Exception as e:self.failure(c,e);raise
