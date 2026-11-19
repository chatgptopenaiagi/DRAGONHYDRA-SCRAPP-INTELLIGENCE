"""Fault injection only in an owned acceptance schema; no service interruption."""
import copy,json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'application'),str(ROOT/'.build-deps-postgresql')]
from living.postgres_control import PostgresControl
from living.storage import Store
from living.contracts import atomic_json,fingerprint,now,Cancelled
root=ROOT/'evidence/mission-006/postgresql';last=json.loads((root/'latest-live.json').read_text());run=Path(last['directory']);local=Store(run/'data/intelligence.sqlite3');pg=PostgresControl(local,run/'data');out=root/('recovery-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));out.mkdir();checks=[]
def check(name,fn):
    try:detail=fn();checks.append({'name':name,'status':'LIVE_PASS','detail':detail})
    except Exception as e:checks.append({'name':name,'status':'FAIL','error':str(e)});raise
    finally:atomic_json(out/'results.json',{'checks':checks,'schema':pg.config()['schema']})
    print(name+': LIVE_PASS',flush=True)
def original():return pg.fetch('SELECT id,payload_sha256 FROM '+pg.relation('observations')+' ORDER BY id')
baseline=fingerprint(original())
def cancelled():
    rows=pg.store.query({'kind':'NUMBER'},5)['rows'];rows=copy.deepcopy(rows)
    for r in rows:r['id']=uuid.uuid4().hex;r['source_id']='recovery-synthetic';r['origin']='SYNTHETIC'
    tick=0
    def stop():
        nonlocal tick;tick+=1;return tick==3
    try:pg.store.ingest(rows,{'id':uuid.uuid4().hex,'source_id':'recovery-synthetic'},stop)
    except Cancelled:pass
    else:raise AssertionError('Cancellation did not roll back')
    assert fingerprint(original())==baseline;return {'cancelled_after_rows':2,'original_identities_unchanged':True}
def invalid():
    rows=copy.deepcopy(pg.store.query({'kind':'NUMBER'},2)['rows'])
    for r in rows:r['id']=uuid.uuid4().hex;r['source_id']='recovery-synthetic';r['origin']='SYNTHETIC'
    rows[-1]['value']='not-a-number'
    try:pg.store.ingest(rows,{'id':uuid.uuid4().hex,'source_id':'recovery-synthetic'})
    except Exception:pass
    else:raise AssertionError('Invalid NUMERIC was committed')
    assert fingerprint(original())==baseline;return {'rejected_batch_atomic':True}
def crash():
    ready=out/'transaction-ready.json';script=out/'owned-crash-child.py';script.write_text('''import sys,time,json
from pathlib import Path
sys.path[:0]=PATHS
from living.storage import Store
from living.postgres_control import PostgresControl
s=Store(Path(DATA)/'intelligence.sqlite3');pg=PostgresControl(s,DATA)
with pg.connect('runtime',False) as c:
 c.execute('INSERT INTO '+pg.relation('providers')+' VALUES(%s,%s)',('crash-uncommitted','{}'))
 Path(READY).write_text(json.dumps({'transaction':'uncommitted'}))
 time.sleep(120)
'''.replace('PATHS',repr(sys.path[:2])).replace('DATA',repr(str(run/'data'))).replace('READY',repr(str(ready))))
    log=(out/'child.log').open('w');p=subprocess.Popen([sys.executable,str(script)],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        end=time.monotonic()+15
        while not ready.exists() and p.poll() is None and time.monotonic()<end:time.sleep(.1)
        assert ready.exists(),'Owned crash worker did not enter its disposable transaction';p.terminate();p.wait(10)
        assert not pg.fetch('SELECT id FROM '+pg.relation('providers')+' WHERE id=%s',('crash-uncommitted',));assert fingerprint(original())==baseline
        return {'owned_pid':p.pid,'uncommitted_write_rolled_back':True,'postgresql_service_interrupted':False}
    finally:
        if p.poll() is None:p.terminate();p.wait(10)
        log.close()
def immutable():
    try:
        with pg.connect('runtime',False) as c:c.execute('UPDATE '+pg.relation('observations')+" SET origin='INFERRED' WHERE id=(SELECT id FROM "+pg.relation('observations')+' LIMIT 1)')
    except ValueError:pass
    else:raise AssertionError('Immutable observation trigger did not reject mutation')
    assert fingerprint(original())==baseline;return {'original_update_denied':True}
try:
    check('Cancelled acquisition is atomic',cancelled);check('Invalid batch is atomic',invalid);check('Abrupt owned process termination rolls back PostgreSQL transaction',crash);check('Original observations reject mutation',immutable);check('MCP restart after independent process failure',pg.check_mcp)
    atomic_json(out/'results.json',{'status':'LIVE_PASS','checks':checks,'schema':pg.config()['schema'],'observations_sha256':baseline});atomic_json(root/'latest-recovery.json',{'directory':str(out),'checks':len(checks),'status':'LIVE_PASS'})
finally:local.close()
