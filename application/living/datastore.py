"""SQLite control plane and explicit analytical datastore selection; never silently falls back."""
import json
from .contracts import now
from .storage import Store
from .postgres_control import PostgresControl

class DataStore:
    def __init__(self,path):
        self.local=Store(path);self.postgres=PostgresControl(self.local,self.local.path.parent)
    def __getattr__(self,name):return getattr(self.local,name)
    @property
    def is_postgres(self):return self.postgres.config()['primary']
    @property
    def backend(self):return self.postgres.store if self.is_postgres else self.local
    def query(self,*a,**kw):return self.backend.query(*a,**kw)
    def ingest(self,*a,**kw):return self.backend.ingest(*a,**kw)
    def receipt(self,*a,**kw):return self.backend.receipt(*a,**kw)
    def save_analysis(self,*a,**kw):return self.backend.save_analysis(*a,**kw)
    def analyses(self,*a,**kw):return self.backend.analyses(*a,**kw)
    def sources(self):
        local=self.local.sources()
        if not self.is_postgres:return local
        ids={s['id'] for s in local}
        try:
            with self.postgres.connect() as c:
                for id,payload in c.execute('SELECT id,payload FROM '+self.postgres.relation('providers')+' ORDER BY id'):
                    if id not in ids:local.append({'id':id,'name':payload.get('name',id),'enabled':False,'adapter':'archived','origin':payload.get('origin','IMPORTED'),'status':'HISTORICAL_CONFIGURATION','note':'Retained provenance. Configure a current source before collection.'})
        except Exception:pass
        return local
    def summary(self):
        if not self.is_postgres:return self.local.summary()|{'datastore':'SQLITE_OFFLINE','read_at':now(),'database':str(self.local.path),'cached':False,'integrity_basis':'SQLite startup integrity check plus current read'}
        with self.local.lock:events=[dict(r) for r in self.local.c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 40')]
        try:return self.postgres.store.summary()|{'events':events}
        except Exception:return {'observations':None,'provenance':{},'series':[],'receipts':[],'events':events,'integrity':'unavailable','datastore':'POSTGRESQL','error':'PostgreSQL is unavailable. Test the connection in PostgreSQL Control Center. SQLite offline mode must be selected explicitly.'}
    def backup(self,destination):return self.postgres.backup() if self.is_postgres else self.local.backup(destination)
    def observations_by_ids(self,ids):
        if self.is_postgres:return self.postgres.store.observations_by_ids(ids)
        with self.local.lock:return [json.loads(r[0]) for id in dict.fromkeys(ids) for r in self.local.c.execute('SELECT payload FROM observations WHERE id=?',(id,))]
    def competitions(self,a):
        if self.is_postgres:return self.postgres.store.competitions(a)
        with self.local.lock:return [dict(r) for r in self.local.c.execute("SELECT DISTINCT source,json_extract(payload,'$.metadata.competition') competition,json_extract(payload,'$.metadata.season') season FROM observations WHERE json_extract(payload,'$.metadata.competition') IS NOT NULL AND (?='' OR source=?) AND (?='' OR payload LIKE ? ESCAPE '~') ORDER BY source,competition,season LIMIT ?",(a.get('source',''),a.get('source',''),a.get('search',''),'%'+a.get('search','').replace('~','~~').replace('%','~%').replace('_','~_')+'%',a.get('limit',20)))]
    def table_info(self,table):
        if self.is_postgres:return self.postgres.describe({'sources':'providers','receipts':'import_receipts','tasks':'acquisition_tasks','analyses':'analysis_results'}.get(table,table))
        if table not in ('sources','observations','receipts','tasks','analyses'):raise ValueError('Unknown table')
        with self.local.lock:return [dict(x) for x in self.local.c.execute('PRAGMA table_info('+table+')')]
