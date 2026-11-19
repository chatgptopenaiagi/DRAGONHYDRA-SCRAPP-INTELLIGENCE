"""SQL is authoritative; SQLite is available only through an explicit offline selection."""
import json,os,sqlite3,threading
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from .model import stamp,now

DB='DRAGONHYDRA_SCRAPP_INTELLIGENCE'
MARKER='scrapp-intelligence/mission-002'
class StorageUnavailable(RuntimeError):pass

class Store:
    def __init__(self,path=None,*,offline=False):
        self.offline=offline;self.path=Path(path) if path else None;self.lock=threading.RLock();self.observation_limit=100000
        if offline:
            if not self.path:raise ValueError('Explicit offline database path required')
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with self.connect() as c:
                c.executescript('''PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS sources(source_id TEXT PRIMARY KEY,source_url TEXT NOT NULL,category TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES sources(source_id),series_key TEXT NOT NULL,kind TEXT NOT NULL,origin TEXT NOT NULL,received_at TEXT NOT NULL,observed_at TEXT,published_at TEXT,issue_at TEXT,valid_at TEXT,payload TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS series_time ON observations(source_id,series_key,received_at DESC);
                CREATE INDEX IF NOT EXISTS origin_time ON observations(origin,received_at DESC);
                CREATE TABLE IF NOT EXISTS interpretations(id TEXT PRIMARY KEY,observation_id TEXT NOT NULL REFERENCES observations(id),payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS health(source_id TEXT PRIMARY KEY,state TEXT NOT NULL,last_success TEXT,last_attempt TEXT,failures INTEGER NOT NULL,reason TEXT);
                ''')
        else:
            with self.connect() as c:
                if not c.execute("SELECT OBJECT_ID(N'scrapp.RawObservations',N'U')").fetchone()[0]:raise StorageUnavailable('SQL schema is not provisioned')
    @contextmanager
    def connect(self,*,schema=False):
        c=None
        try:
            if self.offline:
                c=sqlite3.connect(str(self.path),timeout=8);c.execute('PRAGMA foreign_keys=ON')
            else:
                import pyodbc
                c=pyodbc.connect('DRIVER={ODBC Driver 18 for SQL Server};SERVER=lpc:'+os.environ['COMPUTERNAME']+';DATABASE='+DB+';Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=yes;APP=DRAGONHYDRA-SCRAPP;Connection Timeout=5',autocommit=False)
                c.timeout=15
                marker=c.execute("SELECT CONVERT(nvarchar(128),value) FROM sys.extended_properties WHERE class=0 AND name=N'DragonhydraOwner'").fetchone()
                if not marker or marker[0]!=MARKER:raise StorageUnavailable('SQL ownership marker missing')
                if not schema:c.execute("EXECUTE AS USER=N'scrapp_runtime_user'")
            yield c
            c.commit()
        except Exception:
            if c is not None:c.rollback()
            raise
        finally:
            if c is not None:c.close()
    def sqltime(self,value):
        if value is None:return None
        value=stamp(value)
        return value if self.offline else datetime.fromisoformat(value.replace('Z','+00:00')).replace(tzinfo=None)
    def ingest(self,rows,interpretations=()):
        if len(rows)>1000:raise ValueError('Batch limited to 1000 records')
        count=0
        with self.lock,self.connect() as c:
            if not self.offline:c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')
            else:c.execute('BEGIN IMMEDIATE')
            table='observations' if self.offline else 'scrapp.RawObservations'
            identifier='id' if self.offline else 'observation_id'
            retained=c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]
            for r in rows:
                if c.execute('SELECT '+identifier+' FROM '+table+' WHERE '+identifier+'=?',[r['id']]).fetchone():continue
                if retained>=self.observation_limit:raise StorageUnavailable('Observation retention limit reached; verified archival required before more ingestion')
                retained+=1
                payload=json.dumps(r,ensure_ascii=False,sort_keys=True,allow_nan=False)
                if self.offline:
                    c.execute('INSERT OR IGNORE INTO sources VALUES(?,?,?)',(r['source_id'],r['source_url'],r['kind']))
                    cur=c.execute('INSERT OR IGNORE INTO observations VALUES(?,?,?,?,?,?,?,?,?,?,?)',(r['id'],r['source_id'],r['key'],r['kind'],r['origin'],r['received_at'],r['observed_at'],r['published_at'],r['issue_at'],r['valid_at'],payload));count+=cur.rowcount
                else:
                    if not c.execute('SELECT source_id FROM scrapp.DataSources WITH(UPDLOCK,HOLDLOCK) WHERE source_id=?',r['source_id']).fetchone():c.execute('INSERT INTO scrapp.DataSources(source_id,source_url,category) VALUES(?,?,?)',r['source_id'],r['source_url'],r['kind'])
                    if c.execute('SELECT observation_id FROM scrapp.RawObservations WITH(UPDLOCK,HOLDLOCK) WHERE observation_id=?',r['id']).fetchone():continue
                    c.execute('INSERT INTO scrapp.RawObservations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',r['id'],r['source_id'],r['key'],r['kind'],r['origin'],r['verification'],*[self.sqltime(r[k]) for k in ('received_at','observed_at','published_at','issue_at','valid_at')],r['raw_hash'],r['raw_json'],payload,r['engine_version'])
                    if r['value'] is not None:c.execute('INSERT INTO scrapp.NumericalObservations VALUES(?,?,?,?)',r['id'],Decimal(r['value']),r['original_value'],r['unit'])
                    if r['text'] is not None:c.execute('INSERT INTO scrapp.PublicTextObservations VALUES(?,?,?)',r['id'],r['text'],r['metadata'].get('language','unknown'))
                    if r['kind']=='WEATHER_OBSERVATION':c.execute('INSERT INTO scrapp.WeatherObservations VALUES(?,?,?,?)',r['id'],self.sqltime(r['observed_at']),r['metadata'].get('latitude'),r['metadata'].get('longitude'))
                    if r['kind']=='WEATHER_FORECAST':c.execute('INSERT INTO scrapp.WeatherForecasts VALUES(?,?,?,?,?)',r['id'],self.sqltime(r['issue_at']),self.sqltime(r['valid_at']),r['metadata'].get('model'), 'supplied' if r['issue_at'] else 'unavailable')
                    if r['kind']=='SPORTS_ODDS':
                        meta=r['metadata'];event=meta['event'];eid=event['id']
                        if not c.execute('SELECT event_id FROM scrapp.SportsEvents WITH(UPDLOCK,HOLDLOCK) WHERE event_id=?',eid).fetchone():c.execute('INSERT INTO scrapp.SportsEvents VALUES(?,?)',eid,json.dumps(event,ensure_ascii=False))
                        c.execute('INSERT INTO scrapp.SportsOdds VALUES(?,?,?,?,?,?)',r['id'],eid,meta['market_id'],meta['bookmaker'],meta['outcome'],json.dumps(meta['market'],ensure_ascii=False))
                    count+=1
            for item in interpretations:
                encoded=json.dumps(item,ensure_ascii=False)
                if self.offline:c.execute('INSERT OR IGNORE INTO interpretations VALUES(?,?,?)',(item['id'],item['observation_id'],encoded))
                elif not c.execute('SELECT result_id FROM scrapp.SentimentResults WHERE result_id=?',item['id']).fetchone():c.execute('INSERT INTO scrapp.SentimentResults VALUES(?,?,?,?,?,?,?)',item['id'],item['observation_id'],item['label'],Decimal(str(item['strength'])),encoded,item['engine_version'],self.sqltime(item['interpreted_at']))
        return {'inserted':count,'duplicates':len(rows)-count,'backend':'sqlite_offline' if self.offline else 'sqlserver'}
    def query(self,*,source='',kind='',origin='',start=None,at=None,search='',limit=100,offset=0,order='desc'):
        limit=int(limit);offset=int(offset)
        if not 1<=limit<=500 or not 0<=offset<=100000 or order not in ('asc','desc'):raise ValueError('Invalid query bounds/order')
        clauses=[];args=[]
        for col,v in [('source_id',source),('kind',kind),('origin',origin)]:
            if v:clauses.append(col+'=?');args.append(v)
        received='received_at' if self.offline else 'received_at_utc'
        if start:clauses.append(received+'>=?');args.append(self.sqltime(start))
        if at:
            cutoff=self.sqltime(at);clauses.append(received+'<=?');args.append(cutoff)
            for col in ('published_at','issue_at'):
                field=col if self.offline else col+'_utc';clauses.append(f'({field} IS NULL OR {field}<=?)');args.append(cutoff)
        payload='payload' if self.offline else 'normalized_json';table='observations' if self.offline else 'scrapp.RawObservations'
        if search:
            if len(search)>120:raise ValueError('Search too long')
            clauses.append("series_key LIKE ? ESCAPE '~'");args.append('%'+search.replace('~','~~').replace('%','~%').replace('_','~_').replace('[','~[')+'%')
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        order_id='id' if self.offline else 'observation_id'
        sql=f'SELECT {payload} FROM {table}{where} ORDER BY {received} {order},{order_id} {order}'
        sql+= ' LIMIT ? OFFSET ?' if self.offline else ' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY'
        bounds=[limit,offset] if self.offline else [offset,limit]
        with self.connect() as c:
            count=c.execute('SELECT COUNT(*) FROM '+table+where,args).fetchone()[0]
            rows=[json.loads(r[0]) for r in c.execute(sql,args+bounds).fetchall()]
        return {'total':count,'rows':rows,'limit':limit,'offset':offset}
    def interpretations(self,observation_id):
        with self.connect() as c:
            sql='SELECT payload FROM interpretations WHERE observation_id=?' if self.offline else 'SELECT interpretation_json FROM scrapp.SentimentResults WHERE observation_id=?'
            return [json.loads(r[0]) for r in c.execute(sql,[observation_id]).fetchall()]
    def health(self,source_id=None,state=None,reason=None):
        table='health' if self.offline else 'scrapp.SourceHealth'
        with self.lock,self.connect() as c:
            if source_id is not None:
                old=c.execute('SELECT * FROM '+table+' WHERE source_id=?',[source_id]).fetchone()
                at=self.sqltime(now());previous_success=old[2] if old else None
                values=[state,at if state=='READY' else previous_success,at,0 if state=='READY' else (old[4] if old else 0)+1,str(reason or '')[:500],source_id]
                # SQL source registry must already exist before health writes.
                if not self.offline and not c.execute('SELECT source_id FROM scrapp.DataSources WHERE source_id=?',source_id).fetchone():c.execute('INSERT INTO scrapp.DataSources(source_id,source_url,category) VALUES(?,?,?)',source_id,'unavailable://'+source_id,'UNKNOWN')
                if old:
                    names='state,last_success,last_attempt,failures,reason' if self.offline else 'state,last_success_utc,last_attempt_utc,failures,reason'
                    c.execute('UPDATE '+table+' SET '+','.join(n+'=?' for n in names.split(','))+' WHERE source_id=?',values)
                else:c.execute('INSERT INTO '+table+' VALUES(?,?,?,?,?,?)',[source_id]+values[:-1])
            return [dict(zip(('source_id','state','last_success','last_attempt','failures','reason'),r)) for r in c.execute('SELECT * FROM '+table).fetchall()]
    def close(self):pass

def migrate():
    obj=object.__new__(Store);obj.offline=False
    with obj.connect(schema=True) as c:c.execute(Path(__file__).with_name('schema.sql').read_text())
