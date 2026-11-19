"""DH-STORAGE: versioned, owned SQLite; immutable observations and atomic receipts."""
import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path
from .contracts import encode,now,fingerprint,file_hash,Cancelled

OWNER='dragonhydra.living-intelligence'
class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock();self.c=sqlite3.connect(self.path,timeout=10,check_same_thread=False)
        self.c.row_factory=sqlite3.Row
        tables={r[0] for r in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables:
            try: meta=dict(self.c.execute('SELECT key,value FROM metadata'))
            except sqlite3.Error: self.c.close();raise ValueError('Unowned database; original database will not be migrated') from None
            if meta.get('owner')!=OWNER or self.c.execute('PRAGMA user_version').fetchone()[0] not in (1,2,3):
                self.c.close();raise ValueError('Unowned or unsupported database version')
        t=time.perf_counter();self.integrity=self.c.execute('PRAGMA integrity_check').fetchone()[0];self.integrity_ms=(time.perf_counter()-t)*1000
        if self.integrity!='ok':self.c.close();raise ValueError('Database integrity failed; restore a verified backup')
        if tables and self.c.execute('PRAGMA user_version').fetchone()[0]<3:
            backup=self.path.with_name(self.path.name+'.before-schema3-'+str(time.time_ns()))
            with closing(sqlite3.connect(backup)) as out:self.c.backup(out)
        self.c.execute('PRAGMA foreign_keys=ON');self.c.execute('PRAGMA journal_mode=WAL');self.c.execute('PRAGMA synchronous=FULL')
        self.c.executescript('''BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,source TEXT NOT NULL,series TEXT NOT NULL,kind TEXT NOT NULL,origin TEXT NOT NULL,unit TEXT NOT NULL,observed_at TEXT,collected_at TEXT NOT NULL,identity_key TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS receipts(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,state TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,payload TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,result TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,at TEXT NOT NULL,level TEXT NOT NULL,code TEXT NOT NULL,detail TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS aliases(scope TEXT NOT NULL,original TEXT NOT NULL,canonical TEXT NOT NULL,PRIMARY KEY(scope,original));
CREATE TABLE IF NOT EXISTS component_state(scope TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(scope,id));
CREATE TRIGGER IF NOT EXISTS immutable_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'Original observations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'Original observations are immutable'); END;
CREATE INDEX IF NOT EXISTS observation_time ON observations(observed_at,collected_at);
CREATE INDEX IF NOT EXISTS observation_scope ON observations(source,series,unit,origin);
CREATE INDEX IF NOT EXISTS observation_identity ON observations(source,identity_key,series,origin);
INSERT OR IGNORE INTO metadata VALUES('owner','dragonhydra.living-intelligence');
PRAGMA user_version=3;
COMMIT;''')
        with self.c:self.c.execute('INSERT OR IGNORE INTO metadata VALUES(?,?)',('owner',OWNER))
        with self.c:
            self.c.execute("UPDATE tasks SET state='INTERRUPTED',updated_at=? WHERE state='RUNNING'",(now(),))
        self.event('INFO','STARTUP_INTEGRITY','SQLite integrity checked; schema 3; interrupted tasks retained')
    def state(self,scope,id,value=None):
        with self.lock,self.c:
            if value is not None:self.c.execute('INSERT INTO component_state VALUES(?,?,?) ON CONFLICT(scope,id) DO UPDATE SET payload=excluded.payload',(scope,str(id),encode(value)))
            r=self.c.execute('SELECT payload FROM component_state WHERE scope=? AND id=?',(scope,str(id))).fetchone()
            return json.loads(r[0]) if r else None
    def states(self,scope):
        with self.lock:return [json.loads(r[0]) for r in self.c.execute('SELECT payload FROM component_state WHERE scope=? ORDER BY id',(scope,))]
    def event(self,level,code,detail):
        with self.lock,self.c:self.c.execute('INSERT INTO events(at,level,code,detail) VALUES(?,?,?,?)',(now(),level,code,str(detail)[:500]))
    def source(self,item):
        with self.lock,self.c:self.c.execute('INSERT INTO sources VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(item['id'],encode(item)))
    def sources(self):
        with self.lock:return [json.loads(r[0]) for r in self.c.execute('SELECT payload FROM sources ORDER BY id')]
    def task(self,payload):
        with self.lock,self.c:
            for r in self.c.execute("SELECT id,payload FROM tasks WHERE state IN ('QUEUED','RUNNING')"):
                if json.loads(r['payload']).get('source_id')==payload.get('source_id'):raise ValueError('This source already has an active task')
            id=uuid.uuid4().hex;self.c.execute('INSERT INTO tasks VALUES(?,?,?,?,?,0,NULL)',(id,'QUEUED',now(),now(),encode(payload)));return id
    def task_update(self,id,state,progress=0,result=None):
        with self.lock,self.c:self.c.execute('UPDATE tasks SET state=?,updated_at=?,progress=?,result=? WHERE id=?',(state,now(),progress,encode(result) if result is not None else None,id))
    def tasks(self):
        with self.lock:return [dict(r)|{'payload':json.loads(r['payload']),'result':json.loads(r['result']) if r['result'] else None} for r in self.c.execute('SELECT * FROM tasks ORDER BY created_at DESC LIMIT 200')]
    def receipt(self,id):
        with self.lock:
            r=self.c.execute('SELECT payload FROM receipts WHERE id=?',(id,)).fetchone();return json.loads(r[0]) if r else None
    def ingest(self,rows,receipt,cancel=lambda:False):
        with self.lock:
            if self.receipt(receipt['id']):return self.receipt(receipt['id'])
            inserted=duplicates=conflicts=0
            try:
                self.c.execute('BEGIN IMMEDIATE')
                for r in rows:
                    if cancel():raise Cancelled('Cancelled before atomic commit; no observations from this task committed')
                    if self.c.execute('SELECT 1 FROM observations WHERE id=?',(r['id'],)).fetchone():duplicates+=1;continue
                    conflict=self.c.execute('SELECT 1 FROM observations WHERE source=? AND identity_key=? AND series=? AND origin=?',(r['source_id'],r['identity'],r['key'],r['origin'])).fetchone()
                    if conflict:
                        r['quality']['warnings'].append('Conflicting record identity: both original observations retained');r['quality']['state']='UNCERTAIN';conflicts+=1
                    self.c.execute('INSERT INTO observations VALUES(?,?,?,?,?,?,?,?,?,?)',(r['id'],r['source_id'],r['key'],r['kind'],r['origin'],r['unit'],r['observed_at'],r['collected_at'],r['identity'],encode(r)));inserted+=1
                receipt=receipt|dict(inserted=inserted,duplicates=duplicates,conflicts=conflicts,committed_at=now())
                self.c.execute('INSERT INTO receipts VALUES(?,?)',(receipt['id'],encode(receipt)));self.c.commit();return receipt
            except BaseException:self.c.rollback();raise
    def query(self,filters=None,limit=100,offset=0):
        filters=filters or {};limit=int(limit);offset=int(offset)
        if not 1<=limit<=10000 or not 0<=offset<=1000000:raise ValueError('Invalid query bounds')
        clauses=[];params=[]
        for arg,col in [('source','source'),('kind','kind'),('origin','origin'),('series','series'),('unit','unit')]:
            if filters.get(arg):clauses.append(col+'=?');params.append(filters[arg])
        if filters.get('search'):
            clauses.append("payload LIKE ? ESCAPE '~'");params.append('%'+str(filters['search'])[:120].replace('~','~~').replace('%','~%').replace('_','~_')+'%')
        for arg,op in [('start','>='),('end','<=')]:
            if filters.get(arg):clauses.append('collected_at'+op+'?');params.append(filters[arg])
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        with self.lock:
            total=self.c.execute('SELECT COUNT(*) FROM observations'+where,params).fetchone()[0]
            rows=[json.loads(r[0]) for r in self.c.execute("SELECT payload FROM observations"+where+" ORDER BY COALESCE(observed_at,json_extract(payload,'$.metadata.date'),collected_at),id LIMIT ? OFFSET ?",params+[limit,offset])]
        return dict(total=total,rows=rows,limit=limit,offset=offset)
    def summary(self):
        with self.lock:
            return {'observations':self.c.execute('SELECT COUNT(*) FROM observations').fetchone()[0],
                    'provenance':dict(self.c.execute('SELECT origin,COUNT(*) FROM observations GROUP BY origin')),
                    'series':[dict(r) for r in self.c.execute("SELECT source,series,unit,origin,COUNT(*) n,SUM(CASE WHEN json_extract(payload,'$.value') IS NOT NULL THEN 1 ELSE 0 END) numeric_n FROM observations GROUP BY source,series,unit,origin")],
                    'receipts':[json.loads(r[0]) for r in self.c.execute('SELECT payload FROM receipts ORDER BY rowid DESC LIMIT 30')],
                    'events':[dict(r) for r in self.c.execute('SELECT * FROM events ORDER BY id DESC LIMIT 40')],
                    'integrity':self.integrity,'integrity_ms':self.integrity_ms,'schema':3}
    def save_analysis(self,result):
        with self.lock,self.c:self.c.execute('INSERT OR IGNORE INTO analyses VALUES(?,?)',(result['id'],encode(result)))
    def analyses(self):
        with self.lock:return [json.loads(r[0]) for r in self.c.execute('SELECT payload FROM analyses ORDER BY rowid DESC LIMIT 50')]
    def backup(self,destination):
        destination=Path(destination)
        if destination.exists():raise ValueError('Backup already exists')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with self.lock,closing(sqlite3.connect(destination)) as target:
            self.c.backup(target)
            if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup integrity failed')
        return {'name':destination.name,'sha256':file_hash(destination),'bytes':destination.stat().st_size,'at':now()}
    def close(self):
        with self.lock:self.c.close()
