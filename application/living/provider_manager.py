"""Provider lifecycle, budgets and receipts, using the existing single acquisition worker."""
import hashlib,json,re,threading,time
from datetime import datetime,timezone,date
from email.utils import parsedate_to_datetime
from pathlib import Path
from .contracts import now,fingerprint,Cancelled,Blocked,atomic_json
from .credentials import Vault
from .normalization import normalize
from .football_providers import ADAPTERS
from .football_providers.base import ProviderError
from . import provider_transport

class ProviderManager:
    def __init__(self,store,data,acquisition,mock_origins=()):
        self.store=store;self.data=Path(data);self.worker=acquisition;self.vault=Vault(data);self.lock=threading.RLock();self.mock_origins=tuple(mock_origins)
        for origin in mock_origins:
            from urllib.parse import urlsplit
            p=urlsplit(origin)
            if p.scheme!='http' or p.hostname!='127.0.0.1' or not p.port or p.path or p.query or p.fragment:raise ValueError('Only exact loopback origins are permitted for mock acceptance')
        for slot,a in ADAPTERS.items():
            if not store.state('provider',slot):store.state('provider',slot,dict(slot=slot,configured=False,enabled=False,approved=False,schedule=False,category='teams' if slot=='3' else 'competitions',competition='',season=str(date.today().year),team='Arsenal' if slot=='3' else '',date_from='',date_to='',matchday='',interval=max(3600,a.minimum_interval),state='UNCONFIGURED',last_checked=None,last_success=None,last_import=None,http_status=None,error=None,competitions=[],revision=0,budget={'requests':[],'consumed_total':0,'retry_at':0,'headers':{}}))
    def adapter(self,slot):
        if str(slot) not in ADAPTERS:raise ValueError('Unknown provider slot')
        return ADAPTERS[str(slot)]
    def binding(self,slot,c):
        a=self.adapter(slot);return fingerprint([str(slot),a.name,c.get('mock_origin') or a.base,a.auth,a.key_name])
    def public(self,slot):
        a=self.adapter(slot);c=self.store.state('provider',slot);v={**a.metadata(),**c};v.pop('mock_origin',None);v['test_mode']='MOCK' if c.get('mock_origin') else 'LIVE_ENDPOINT';v['credential_status']='NOT_REQUIRED' if a.auth in ('none','public-demo') else self.vault.status(slot,self.binding(slot,c));v['monthly_subscription_cost']='0 mandatory';v['budget']=self.budget_view(a,c)
        if not c['configured']:v['state']='UNCONFIGURED'
        elif not c['enabled']:v['state']='DISABLED'
        elif self.worker.mode!='connected':v['state']='OFFLINE'
        return v
    def list(self):return [self.public(s) for s in ADAPTERS]
    def budget_view(self,a,c):
        b=c['budget'];t=time.time();today=sum(t-x<86400 for x in b['requests']);window=sum(t-x<a.window_seconds for x in b['requests'])
        return {'local_consumed_total':b['consumed_total'],'local_last_24h':today,'local_24h_cap':a.daily_cap,'estimated_local_remaining':max(0,a.daily_cap-today),'verified_window_limit':a.window_limit,'window_seconds':a.window_seconds,'local_window_requests':window,'last_request':b.get('last_request'),'retry_at':datetime.fromtimestamp(b['retry_at'],timezone.utc).isoformat() if b['retry_at']>t else None,'provider_headers':b.get('headers',{}),'account_usage':'Unknown beyond provider response headers; local counters are not account usage'}
    def cancel_slot(self,slot):
        for task in self.store.tasks():
            if task['payload'].get('provider_slot')==str(slot) and task['state'] in ('QUEUED','RUNNING'):
                self.worker.cancelled.add(task['id'])
                if task['state']=='QUEUED':self.store.task_update(task['id'],'CANCELLED',0,{'error':'Provider disabled or configuration changed'})
    def configure(self,body):
        slot=str(body['slot']);a=self.adapter(slot)
        allowed={'slot','enabled','approved','schedule','category','competition','season','team','date_from','date_to','matchday','interval','mock_origin'}
        if set(body)-allowed:raise ValueError('Unexpected provider field. Save API keys using the protected credential form')
        with self.lock:
            c=self.store.state('provider',slot);v={**c,**body,'slot':slot}
            for k in ('enabled','approved','schedule'):
                if type(v[k]) is not bool:raise ValueError('Invalid provider flag')
            if v['category'] not in a.categories:raise ValueError('This data type is not enabled for the provider free tier')
            if not a.minimum_interval<=int(v['interval'])<=604800:raise ValueError(f'Polling interval must be {a.minimum_interval}–604800 seconds for this provider')
            if v.get('mock_origin') and v['mock_origin'] not in self.mock_origins:raise ValueError('Mock endpoints require an explicitly isolated acceptance launch')
            for k in ('competition','season','matchday'):
                if not re.fullmatch(r'[A-Za-z0-9_-]{0,40}',str(v.get(k,''))):raise ValueError('Invalid '+k)
            for k in ('date_from','date_to'):
                if v.get(k):date.fromisoformat(v[k])
            if v.get('date_from') and v.get('date_to') and (date.fromisoformat(v['date_to'])-date.fromisoformat(v['date_from'])).days not in range(32):raise ValueError('Choose a chronological date range of at most 31 days')
            if len(str(v.get('team','')))>100:raise ValueError('Team search is too long')
            if v['enabled'] and not v['approved']:raise ValueError('Confirm permitted free-tier access before enabling this provider')
            self.cancel_slot(slot);v.update(configured=True,state='CONFIGURED',revision=c['revision']+1,error=None);self.store.state('provider',slot,v)
            self.store.source({'id':'football-api-'+slot,'name':a.name,'adapter':'provider','enabled':False,'interval':v['interval'],'mapping':{},'kind':'FOOTBALL_RECORD','unit':'record','origin':'COLLECTED','location':a.base,'options':{'provider_slot':slot}})
        return self.public(slot)
    def credential(self,body,remove=False):
        slot=str(body['slot']);a=self.adapter(slot);c=self.store.state('provider',slot)
        if a.auth in ('none','public-demo'):raise ValueError('This free connector does not require a private API key')
        with self.lock:
            self.cancel_slot(slot)
            result=self.vault.remove(slot) if remove else self.vault.save(slot,self.binding(slot,c),body.get('credential'))
            c.update(revision=c['revision']+1,state='CONFIGURED',error=None);self.store.state('provider',slot,c)
        return result
    def remove(self,slot):
        slot=str(slot);self.adapter(slot)
        with self.lock:
            self.cancel_slot(slot);self.vault.remove(slot);c=self.store.state('provider',slot);c.update(configured=False,enabled=False,schedule=False,approved=False,state='UNCONFIGURED',revision=c['revision']+1,error=None);self.store.state('provider',slot,c)
        return {'state':'UNCONFIGURED','historical_observations':'PRESERVED'}
    def guard(self,slot,c):
        a=self.adapter(slot)
        if self.worker.mode!='connected':raise Blocked('Online collection is disabled. Switch to Configured connections to test this API.')
        if not c['configured'] or not c['enabled'] or not c['approved']:raise Blocked('Save and enable this provider with permission for free-tier requests first.')
        if a.auth not in ('none','public-demo') and self.vault.status(slot,self.binding(slot,c))!='SAVED':raise Blocked('Enter an API key for this provider before testing the connection.')
        if c['budget']['retry_at']>time.time():raise Blocked('Provider requests are paused until the displayed retry time.')
    def submit(self,slot,operation='collect'):
        slot=str(slot);a=self.adapter(slot)
        if operation not in ('test','collect','status') or operation=='status' and slot!='2':raise ValueError('Unknown provider operation')
        with self.lock:
            c=self.store.state('provider',slot);self.guard(slot,c)
            if operation=='collect' and c['category'] not in ('competitions','teams'):
                if not any(str(x['id'])==str(c['competition']) for x in c['competitions']):raise Blocked('Test connection to discover competitions, then select a returned competition.')
            a.request(c,operation)
            source=next(s for s in self.store.sources() if s['id']=='football-api-'+slot)
            id=self.store.task({'operation':'provider','provider_operation':operation,'provider_slot':slot,'source_id':source['id'],'source':source,'revision':c['revision'],'attempt':0});return {'task_id':id}
    def reserve(self,slot,c,endpoint):
        a=self.adapter(slot);t=time.time();b=c['budget'];b['requests']=[x for x in b['requests'] if t-x<86400]
        waits=[]
        if len(b['requests'])>=a.daily_cap:waits.append(b['requests'][0]+86400)
        recent=[x for x in b['requests'] if t-x<a.window_seconds]
        if len(recent)>=a.window_limit:waits.append(recent[0]+a.window_seconds)
        if b['retry_at']>t:waits.append(b['retry_at'])
        if waits:
            b['retry_at']=max(waits);self.store.state('provider',slot,c);raise ProviderError('The local free-tier request budget is exhausted. Wait until the displayed retry time.','RATE_LIMITED')
        b['requests'].append(t);b['consumed_total']+=1;b['last_request']=now();self.store.state('provider',slot,c)
    def schedule(self):
        if self.worker.mode!='connected':return
        t=time.time()
        for slot in ADAPTERS:
            with self.lock:
                c=self.store.state('provider',slot)
                if not(c['enabled'] and c['schedule'] and c['configured']) or t<c.get('next_due',0):continue
                c['next_due']=t+int(c['interval'])+int(slot)*7;self.store.state('provider',slot,c)
                try:self.submit(slot)
                except (ValueError,Blocked):pass
    def execute(self,task,cancel):
        slot=task['payload']['provider_slot'];a=self.adapter(slot);c=self.store.state('provider',slot);revision=task['payload']['revision'];operation=task['payload']['provider_operation'];secrets=[]
        def cancelled():return cancel() or self.worker.mode!='connected' or self.store.state('provider',slot)['revision']!=revision
        try:
            self.guard(slot,c)
            if cancelled():raise Cancelled('Provider operation cancelled by mode or configuration change')
            key=self.vault.get(slot,self.binding(slot,c)) if a.auth not in ('none','public-demo') else None
            if key:secrets=[key]
            pages=[];records=[];headers={};page=1;http_status=None;received_at=None
            for page_number in range(10):
                path,params,category=a.request(c,operation,page);auth_headers={};safe_query=dict(params)
                if key:
                    if a.auth=='header':auth_headers[a.key_name]=key
                    elif a.auth=='query':params[a.key_name]=key
                base=c.get('mock_origin') or a.base;cache_id=fingerprint([slot,base,path,safe_query,c['revision']]);cache=self.store.state('http-cache',cache_id)
                if cache:
                    if cache.get('etag'):auth_headers['If-None-Match']=cache['etag']
                    elif cache.get('last_modified'):auth_headers['If-Modified-Since']=cache['last_modified']
                response=None
                # Bounded retries for transport failures/5xx only. 429 is deferred, never polled repeatedly.
                for attempt in range(3):
                    if cancelled():raise Cancelled('Provider operation cancelled')
                    with self.lock:
                        latest=self.store.state('provider',slot)
                        if latest['revision']!=revision:raise Cancelled('Provider configuration changed before request')
                        c['budget']=latest['budget'];self.reserve(slot,c,path)
                    try:
                        response,headers,http_status=provider_transport.get(base,path,params,auth_headers,cancelled,self.mock_origins);break
                    except ProviderError as e:
                        if e.state!='UNAVAILABLE' or e.status not in (None,500,502,503,504) or attempt==2:raise
                        until=time.monotonic()+2**attempt
                        while time.monotonic()<until:
                            if cancelled():raise Cancelled('Provider retry cancelled')
                            time.sleep(.1)
                if cancelled():raise Cancelled('Provider operation cancelled before parsing')
                received_at=now();headers=provider_transport.redact(headers,secrets)
                if http_status==304:
                    if not cache:raise ProviderError('Provider returned not-modified without a cached response')
                    data=cache['data'];raw_sha=cache['raw_sha256'];retrieved=cache['retrieved_at']
                else:
                    raw_sha=hashlib.sha256(response).hexdigest()
                    try:data=json.loads(response,parse_float=str,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
                    except (ValueError,UnicodeError):raise ProviderError('Provider returned malformed JSON; no observations imported') from None
                    data=provider_transport.redact(data,secrets);retrieved=received_at
                parsed=a.parse(data,category,c)
                if category=='account_status':
                    account=data['response'];c['reported_account']={'checked_at':received_at,'requests_used':account['requests']['current'],'daily_allowance':account['requests']['limit_day'],'remaining':max(0,account['requests']['limit_day']-account['requests']['current']),'plan':account.get('subscription',{}).get('plan'),'active':True}
                    # Preserve quota and response fingerprint, never account names or email addresses.
                    data={'get':'status','errors':[],'response':{'requests':account['requests'],'subscription':{k:account.get('subscription',{}).get(k) for k in ('plan','active','end')}}}
                if len(records)+len(parsed)>100000:raise ProviderError('Collection exceeds 100000 observations; narrow the selection')
                records.extend(parsed);pages.append({'sha256':raw_sha,'response_status':http_status,'retrieved_at':retrieved,'checked_at':received_at,'safe_parameters':safe_query,'path':path,'records':len(parsed)})
                folder=self.data/'provider-responses';folder.mkdir(exist_ok=True);evidence_path=folder/(fingerprint(data)+'.json')
                if not evidence_path.exists():atomic_json(evidence_path,data)
                self.store.state('http-cache',cache_id,{'data':data,'raw_sha256':raw_sha,'retrieved_at':retrieved,'etag':headers.get('etag'),'last_modified':headers.get('last-modified')})
                c['budget']['headers']=headers
                remaining=headers.get('x-ratelimit-requests-remaining')
                if remaining is not None and str(remaining).isdigit() and int(remaining)==0:c['budget']['retry_at']=time.time()+86400
                self.store.task_update(task['id'],'RUNNING',min(70,10+page_number*6))
                next_page=a.next_page(data,page)
                if not next_page:break
                if next_page<=page:raise ProviderError('Pagination did not advance')
                page=next_page
            else:raise ProviderError('Collection requires more than 10 pages. Narrow the selection; no partial batch was imported.')
            if cancelled():raise Cancelled('Provider operation cancelled before commit')
            evidence='MOCK_PASS' if c.get('mock_origin') else 'LIVE_PASS';origin='SYNTHETIC' if c.get('mock_origin') else 'COLLECTED';at=now();source=task['payload']['source'];normalized=[]
            for r in records:
                r['metadata'].update(provider=a.name,provider_slot=slot,adapter_version='1',evidence_class=evidence)
                normalized.append(normalize(r,source,origin,at))
            receipt={'id':task['id'],'source_id':source['id'],'method':'football-provider','provider':a.name,'operation':operation,'category':category,'content_hash':fingerprint([p['sha256'] for p in pages]),'pages':pages,'acquired_at':at,'rows_validated':len(normalized),'validation_errors':0,'origin':origin,'evidence_class':evidence,'limitations':a.limitations,'raw_response_storage':'Sanitized JSON plus original response SHA-256; credential echoes removed'}
            # Connection tests validate records and discover competitions without pretending they were imported.
            with self.lock:
                current=self.store.state('provider',slot)
                if current['revision']!=revision:raise Cancelled('Provider configuration changed before receipt commit')
                result=self.store.ingest(normalized if operation=='collect' else [],receipt,cancelled)
                current.update(state='CONNECTED',last_checked=at,last_success=at,http_status=http_status,error=None,budget=c['budget'],last_receipt=result)
                if c.get('reported_account'):current['reported_account']=c['reported_account']
                if operation=='collect':current['last_import']=at
                if category=='competitions':current['competitions']=[{'id':r['metadata']['competition'],'name':r['metadata']['name'],'seasons':r['metadata'].get('seasons',[])} for r in records]
                self.store.state('provider',slot,current)
            return result
        except Exception as e:
            with self.lock:
                current=self.store.state('provider',slot)
                if current['revision']==revision:
                    state=e.state if isinstance(e,ProviderError) else 'CANCELLED' if isinstance(e,Cancelled) else 'OFFLINE' if isinstance(e,Blocked) else 'UNAVAILABLE'
                    # Never echo exception text from transport, JSON parsing, OS or cryptography.
                    message=str(e) if isinstance(e,(ProviderError,Cancelled,Blocked)) else 'Provider schema validation failed; no batch committed. Review endpoint coverage.'
                    message=provider_transport.redact(message,secrets)
                    current.update(state=state,error=message,last_checked=now(),http_status=getattr(e,'status',None))
                    if state=='RATE_LIMITED':
                        delay=60;retry=getattr(e,'retry_after',None)
                        if retry:
                            try:delay=max(60,float(retry))
                            except ValueError:
                                try:delay=max(60,parsedate_to_datetime(retry).timestamp()-time.time())
                                except (ValueError,TypeError):pass
                        current['budget']['retry_at']=max(current['budget']['retry_at'],time.time()+min(delay,604800))
                    self.store.state('provider',slot,current)
            if isinstance(e,Cancelled):raise
            if isinstance(e,Blocked):raise
            raise ValueError(message if current['revision']==revision else 'Provider configuration changed; retry the current configuration') from None
