"""Repeatable SQLite snapshot migration with byte-for-byte original payload reconciliation."""
import hashlib,json,sqlite3,uuid
from contextlib import closing
from pathlib import Path
from .contracts import now,encode,file_hash,fingerprint,Blocked
from .storage import OWNER as SQLITE_OWNER
from .postgres_store import digest

def reconcile(control,rows):
    expected={id:digest(payload) for id,payload in rows}
    with control.connect() as c:
        control.owned(c);actual=dict(c.execute('SELECT id,payload_sha256 FROM '+control.relation('observations')+' WHERE id=ANY(%s)',(list(expected),)))
        # Recompute from independently retrieved original text instead of trusting the recorded hash alone.
        recomputed={id:digest(payload) for id,payload in c.execute('SELECT id,payload_text FROM '+control.relation('observations')+' WHERE id=ANY(%s)',(list(expected),))}
    mismatches=[id for id,h in expected.items() if actual.get(id)!=h or recomputed.get(id)!=h]
    return {'status':'PASS' if not mismatches else 'FAIL','source_rows':len(expected),'matched':len(expected)-len(mismatches),'mismatched_ids':mismatches[:25],'identities_sha256':fingerprint(sorted(expected.items())),'comparison':'Original observation ID and exact UTF-8 payload bytes, recomputed at destination','at':now()}

def migrate(control,path):
    from psycopg.types.json import Jsonb
    path=path.resolve()
    if not path.is_file():raise ValueError('Select an existing verified SQLite snapshot')
    # Always acquire a coherent backup first, including committed WAL; never mutate the input.
    snapshots=control.data/'postgresql-snapshots';snapshots.mkdir(exist_ok=True);snapshot=snapshots/(uuid.uuid4().hex+'.sqlite3')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=10)) as source,closing(sqlite3.connect(snapshot)) as out:
        if dict(source.execute('SELECT key,value FROM metadata')).get('owner')!=SQLITE_OWNER:raise ValueError('Only owned DRAGONHYDRA SQLite data is supported')
        if source.execute('PRAGMA user_version').fetchone()[0]!=3:raise ValueError('Select a preserved schema-3 snapshot; legacy releases remain unchanged')
        source.backup(out)
        if out.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite snapshot integrity failed')
    sha=file_hash(snapshot);job={'id':str(uuid.uuid4()),'state':'RUNNING','at':now(),'snapshot_sha256':sha,'snapshot':str(snapshot)};control.local.state('postgres','migration',job)
    try:
        with closing(sqlite3.connect(snapshot)) as source:
            source.row_factory=sqlite3.Row;raw=[(r[0],r[1]) for r in source.execute('SELECT id,payload FROM observations ORDER BY id')];rows=[json.loads(r[1]) for r in raw];sources=[json.loads(r[0]) for r in source.execute('SELECT payload FROM sources')]
            with control.connect('migration',False) as c:
                control.owned(c);c.execute('SELECT pg_advisory_xact_lock(%s)',(control.lock_id(),))
                old=c.execute('SELECT payload FROM '+control.relation('migration_history')+' WHERE snapshot_sha256=%s',(sha,)).fetchone()
                if old:result=old[0]|{'already_committed':True}
                else:
                    result=control.store.insert(c,rows,{'id':job['id'],'source_id':'sqlite-migration','at':now()},sources,originals=dict(raw),snapshot=sha)
                    tables=[r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name<>'observations'")]
                    for table in tables:
                        if not table.replace('_','').isalnum():raise ValueError('Unexpected SQLite table identifier')
                        for n,r in enumerate(source.execute('SELECT * FROM "'+table+'"')):
                            c.execute('INSERT INTO '+control.relation('workspace_evidence')+' VALUES(%s,%s,%s,%s)',(sha,table,n,Jsonb(dict(r))))
                            if table=='receipts':c.execute('INSERT INTO '+control.relation('import_receipts')+' VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(r['id'],Jsonb(json.loads(r['payload'])),r['payload']))
                            if table=='analyses':c.execute('INSERT INTO '+control.relation('analysis_results')+' VALUES(%s,%s) ON CONFLICT DO NOTHING',(r['id'],Jsonb(json.loads(r['payload']))))
                    result.update(status='PASS',snapshot_sha256=sha,rows_read=len(rows),identities_sha256=fingerprint(sorted((id,digest(p)) for id,p in raw)))
                    c.execute('INSERT INTO '+control.relation('migration_history')+' VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(job['id'],now(),sha,len(rows),result['inserted'],result['duplicates'],result['identities_sha256'],'COMMITTED',Jsonb(result)))
            check=reconcile(control,raw)
            if check['status']!='PASS':raise ValueError('PostgreSQL reconciliation failed; primary datastore unchanged')
        job.update(state='COMPLETE',result=result,reconciliation=check,completed_at=now());control.local.state('postgres','migration',job);return job
    except Exception as e:
        job.update(state='FAILED',error=str(e) if isinstance(e,(ValueError,Blocked)) else type(e).__name__);control.local.state('postgres','migration',job);raise
