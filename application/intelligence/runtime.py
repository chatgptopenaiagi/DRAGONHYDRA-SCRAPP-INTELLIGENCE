import hashlib,json,os,threading,time
from pathlib import Path
from dragonhydra.kernel.contracts import ModuleDefinition
from dragonhydra.kernel.registry import ModuleRegistry
from dragonhydra.market_signals import convert_odds,implied_probability
from .model import normalize,stamp,now,freshness
from .storage import Store,StorageUnavailable
from .cognition import interpret,trend
from .demo import fixtures,TIMES
from .providers import parse_open_meteo,weather_url,read_mirror
from .acquisition import SourceClient,extract_table,SchemaMismatch,AcquisitionError,resolve_public
from . import VERSION

class Service:
    contract_version='core-next.engine/1'
    def stop(self):pass
    def observe(self):return {'state':'READY','reason':'IMPLEMENTED_LOCAL_ENGINE','metrics':{'configured':True}}

class StorageService(Service):
    def __init__(self,store,error):self.store=store;self.error=error
    def ingest(self,rows):
        if not self.store:raise StorageUnavailable(self.error)
        interpretations=[interpret(r) for r in rows if r['kind']=='SHORT_TEXT']
        return self.store.ingest(rows,interpretations)
    def observe(self):
        if not self.store:return {'state':'UNAVAILABLE','reason':'SQL_DATABASE_UNAVAILABLE','metrics':{'configured':True}}
        return {'state':'READY','reason':'OFFLINE_STORAGE_VERIFIED' if self.store.offline else 'SQL_SCHEMA_CONNECTED','metrics':{'retained_observation_count':self.store.query(limit=1)['total'],'schema_complete':True}}

class CognitiveService(Service):
    def analyze(self,row):return interpret(row)
    def classify(self,value,context=None):
        from .classification import classify
        return classify(value,context=context)
class ProbabilityService(Service):
    def calculate(self,value,fmt='decimal'):
        price=convert_odds(value,fmt);return {'decimal':str(price),'implied_probability':str(implied_probability(price)),'interpretation':'Price transform, not a calibrated outcome prediction','engine':'DRAGONHYDRA market_signals'}

class AcquisitionService(Service):
    def __init__(self,runtime):self.runtime=runtime
    def collect(self,source_id):return self.runtime.collect(source_id)
    def observe(self):
        health=self.runtime.store.health() if self.runtime.store else []
        failed=sum(r['state']!='READY' for r in health)
        return {'state':'DEGRADED' if failed else 'READY','reason':'SOURCE_FAILURES' if failed else 'OFFLINE_CAPABLE_ADAPTERS','metrics':{'observations_failed':failed,'enabled_schedules':sum(bool(s.get('enabled')) for s in self.runtime.sources)}}

class Runtime:
    def __init__(self,data_dir,*,offline=False):
        self.data_dir=Path(data_dir);self.data_dir.mkdir(parents=True,exist_ok=True);self.offline=offline
        self.done=threading.Event();self.lock=threading.RLock();self.clients={};self.thread=None;self.demo_index=5
        self.source_file=self.data_dir/'sources.json'
        self.sources=json.loads(self.source_file.read_text()) if self.source_file.exists() else [{'id':'open-meteo','method':'open_meteo','latitude':'52.52','longitude':'13.405','enabled':False,'interval':900,'location_status':'configured coordinates; not linked to any sports venue'}]
        self.store_error=None
        try:self.store=Store(self.data_dir/'offline-demo.sqlite3',offline=offline)
        except Exception as e:self.store=None;self.store_error='SQL database/schema unavailable ('+type(e).__name__+'); no automatic fallback'
        self.services={'storage':StorageService(self.store,self.store_error),'cognition':CognitiveService(),'probability':ProbabilityService(),'acquisition':AcquisitionService(self)}
        definitions=[]
        for name,op,deps in [('storage','ingest',()),('cognition','analyze',()),('probability','calculate',()),('acquisition','collect',('storage',))]:
            operations=(op,'classify') if name=='cognition' else (op,)
            definitions.append(ModuleDefinition(name,name.title(),'SCRAPP '+name,'intelligence',dependencies=deps,capabilities=operations,supported_operations=operations,capability_operations=tuple((method,(method,)) for method in operations),implementation_reference='intelligence.runtime.'+self.services[name].__class__.__name__,origin='scrapp.integration'))
        self.registry=ModuleRegistry(definitions,self.services,installation_id='scrapp-lab',build_identity=VERSION,ttl_seconds=45)
        self.registry.start()
    def operation(self,module,op,*args):
        if module not in self.services or op not in self.registry.definitions[module].supported_operations:raise ValueError('Unsupported operation')
        try:result=getattr(self.services[module],op)(*args)
        except Exception:
            self.registry.record_operation(module,op,'DEGRADED','OPERATION_FAILED');raise
        self.registry.record_operation(module,op,'READY','OPERATION_COMPLETED',evidence=('scrapp:'+module+':'+op,));return result
    def seed(self):
        result=self.operation('storage','ingest',fixtures())
        for source in sorted({r['source_id'] for r in fixtures()}):self.store.health(source,'READY','Fictional deterministic fixture')
        return result
    def import_rows(self,rows):
        if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Import a bounded records array')
        received=now();normalized=[normalize(r,origin='imported',received_at=received) for r in rows]
        return self.operation('storage','ingest',normalized)
    def query(self,**params):
        if self.store is None:raise StorageUnavailable(self.store_error)
        if params.get('origin')=='synthetic' and not params.get('at'):params['at']=TIMES[self.demo_index]
        elif not params.get('at'):params['at']=now()
        result=self.store.query(**params)
        for row in result['rows']:
            source=next((s for s in self.sources if s['id']==row['source_id']),{})
            row['freshness']=freshness(row,params['at'],source.get('freshness_seconds',600))
            row['interpretations']=[item for item in self.store.interpretations(row['id']) if item['interpreted_at']<=stamp(params['at'])]
            # Raw evidence is intentionally inspectable, but HTML is never rendered.
        result.update(cutoff=params['at'],mode='offline_synthetic_lab' if self.offline else 'sqlserver',synthetic_notice='Synthetic observations are fictional. Imported data is unverified. Interpretations are not raw facts.')
        return result
    def collect(self,source_id):
        if self.offline:raise AcquisitionError('External network collection is disabled in offline mode')
        if self.store is None:raise StorageUnavailable(self.store_error)
        source=next((s for s in self.sources if s['id']==source_id),None)
        if not source:raise ValueError('Unknown configured source')
        client=self.clients.get(source_id)
        if not client:
            def wait(delay):
                if self.done.wait(delay):raise AcquisitionError('Collection cancelled')
            client=SourceClient(sleep=wait,interval=source.get('interval',900));self.clients[source_id]=client
            previous=next((s for s in self.store.health() if s['source_id']==source_id),None)
            if previous and previous['last_attempt']:
                elapsed=(datetime_now()-datetime_from(previous['last_attempt'])).total_seconds()
                client.next_due=time.monotonic()+max(0,client.interval-elapsed)
        try:
            url=weather_url(source['latitude'],source['longitude']) if source['method']=='open_meteo' else source['url']
            auth={}
            if source.get('auth_env'):
                credential=os.environ.get(source['auth_env'])
                if not credential:raise AcquisitionError('Configured provider credential is unavailable')
                name=source.get('auth_header','Authorization');auth[name]=('Bearer ' if name=='Authorization' else '')+credential
            body,headers,final_url=client.get(url,html=source['method']=='html_table',allowed_hosts=('api.open-meteo.com',) if source['method']=='open_meteo' else (),headers=auth)
            received=now();digest=hashlib.sha256(body).hexdigest();rawdir=self.data_dir/'raw';rawdir.mkdir(exist_ok=True)
            evidence=rawdir/(digest+'.bin')
            if not evidence.exists():
                if sum(p.stat().st_size for p in rawdir.glob('*.bin'))+len(body)>64*1024*1024:raise AcquisitionError('Raw evidence retention limit reached; archive before more collection')
                evidence.write_bytes(body)
            if source['method']=='open_meteo':rows=parse_open_meteo(body,received,final_url)
            elif source['method']=='rss':
                from .rss import parse_feed
                rows=parse_feed(body,source,received)
            elif source['method']=='json':
                payload=json.loads(body,parse_float=str,parse_constant=lambda _:(_ for _ in ()).throw(SchemaMismatch('Nonfinite JSON number')))
                if not isinstance(payload,dict) or not isinstance(payload.get('records'),list):raise SchemaMismatch('Expected records array')
                rows=[normalize(dict(r,source_id=source_id,source_url=final_url),origin='observed',received_at=received) for r in payload['records']]
            elif source['method']=='html_table':
                extracted=extract_table(body.decode('utf-8'),expected_units=source['expected_units'])
                rows=[normalize(dict(r,source_id=source_id,source_url=final_url,kind='NUMBER',metadata={'source_time_status':'unavailable'}),origin='observed',received_at=received) for r in extracted]
            else:raise ValueError('Unsupported acquisition method')
            for row in rows:row['raw_evidence_sha256']=digest
            result=self.operation('storage','ingest',rows);self.store.health(source_id,'READY','Validated provider response');return result
        except Exception as e:
            self.store.health(source_id,'DEGRADED',type(e).__name__+': '+str(e)[:300]);raise
    def configure_source(self,source):
        from .model import label
        source=dict(source);source['id']=label(source.get('id'),100)
        allowed={'id','method','url','latitude','longitude','enabled','interval','location_status','freshness_seconds','expected_units','language','auth_env','auth_header'}
        if set(source)-allowed:raise ValueError('Unsupported source setting; credentials belong in environment variables')
        if source.get('auth_env'):
            import re
            if not re.fullmatch(r'[A-Z_][A-Z0-9_]{0,99}',source['auth_env']) or source.get('auth_header','Authorization') not in ('Authorization','X-API-Key'):raise ValueError('Invalid credential reference')
        if source.get('method') not in ('json','html_table','open_meteo','rss'):raise ValueError('Unsupported method')
        if source['method']!='open_meteo':resolve_public(source['url'])
        else:weather_url(source['latitude'],source['longitude'])
        if type(source.get('enabled',False)) is not bool or not 60<=int(source.get('interval',900))<=86400:raise ValueError('Invalid enabled/interval setting')
        if type(source.get('freshness_seconds',600)) is not int or not 10<=source.get('freshness_seconds',600)<=604800:raise ValueError('Freshness must be 10..604800 seconds')
        if self.offline and source.get('enabled'):raise ValueError('Offline mode cannot enable external collection')
        with self.lock:
            current=[s for s in self.sources if s['id']!=source['id']]+[source]
            if len(current)>20:raise ValueError('Source limit is 20')
            temp=self.source_file.with_suffix('.tmp');temp.write_text(json.dumps(current,indent=2),encoding='utf-8');os.replace(temp,self.source_file);self.sources=current
        return source
    def mirror_import(self,port,market,cutoff=None):
        # Trusted loopback application bridge is separate from the public scraper transport.
        return self.operation('storage','ingest',read_mirror(port,market,cutoff))
    def status(self):
        for name in self.services:self.registry.refresh(name)
        healthy=bool(self.store);error=self.store_error
        try:health=self.store.health() if self.store else []
        except Exception as exc:healthy=False;error='Storage unavailable ('+type(exc).__name__+')';health=[]
        return {'product':'DRAGONHYDRA SCRAPP INTELLIGENCE','version':VERSION,'mode':'OFFLINE SYNTHETIC LAB' if self.offline else 'SQL SERVER','storage':'READY' if healthy else 'UNAVAILABLE','storage_error':error,'sql_verified':bool(healthy and not self.offline),'core':self.registry.items(),'sources':self.sources,'health':health,'now':now(),'demo_times':TIMES,'demo_index':self.demo_index,'external_scheduling_enabled':not self.offline and any(s.get('enabled') for s in self.sources),'ai':'Optional local service; deterministic baseline remains available','release_status':'CANDIDATE; full SQL/Joomla acceptance pending'}
    def start(self):
        def loop():
            due={}
            while not self.done.wait(1):
                for source in list(self.sources):
                    if self.done.is_set():break
                    if self.offline or not source.get('enabled'):continue
                    sid=source['id']
                    if time.monotonic()<due.get(sid,0):continue
                    due[sid]=time.monotonic()+int(source.get('interval',900))
                    try:self.operation('acquisition','collect',sid)
                    except Exception:pass # Error is persisted in source health and CORE operation record.
        self.thread=threading.Thread(target=loop,name='scrapp-observer',daemon=True);self.thread.start()
    def stop(self):
        self.done.set()
        if self.thread:self.thread.join(timeout=25)
        if self.thread and self.thread.is_alive():raise RuntimeError('Observer has not stopped within deadline')
        self.registry.stop()

def datetime_now():
    from datetime import datetime,timezone
    return datetime.now(timezone.utc)
def datetime_from(value):
    from datetime import datetime,timezone
    if isinstance(value,datetime):return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return datetime.fromisoformat(stamp(value).replace('Z','+00:00'))
