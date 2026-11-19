"""Read-only comparison with immutable prior baselines and the pre-edit database backup."""
import json,sqlite3,sys
from pathlib import Path
from contextlib import closing
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'application'),str(ROOT/'.build-deps-postgresql')]
from living.contracts import file_hash,atomic_json,now
from living.storage import Store
from living.postgres_control import PostgresControl
from living.postgres_backup import signature
out=Path(json.loads((ROOT/'evidence/mission-006/BEGINNER-LATEST.json').read_text())['directory'])
read=lambda p:json.loads(Path(p).read_text())
pointer=read(ROOT/'evidence/mission-006/postgresql/BASELINE-POINTER.json');base=Path(pointer['directory'])
assert file_hash(base/'BASELINE.json')==pointer['sha256'],'Original baseline changed'
protected=read(base/'protected-hashes.json');mismatches=[p for p,h in protected.items() if not Path(p).is_file() or file_hash(Path(p))!=h]
assert not mismatches,'Protected asset mismatch; original baseline retained'
dbs=[]
for item in read(base/'databases.json'):
    snapshot=Path(item['snapshot']);source=Path(item['source']);assert file_hash(snapshot)==item['sha256']
    with closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro&immutable=1',uri=True)) as c:original=dict(c.execute('SELECT id,payload FROM observations'))
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=15)) as c:
        current=dict(c.execute('SELECT id,payload FROM observations'));integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    changed=[id for id,payload in original.items() if current.get(id)!=payload];assert not changed and integrity=='ok'
    dbs.append({'source':str(source),'snapshot':str(snapshot),'snapshot_sha256':item['sha256'],'original_records':len(original),'current_records':len(current),'missing_or_changed':0,'integrity':integrity})
old=read(out/'baseline/beta4-package.json');folder=Path(old['directory']);files=read(folder/'DragonhydraIntelligence/FILES-SHA256.json')
assert all(file_hash(folder/'DragonhydraIntelligence'/p)==h for p,h in files.items())
assert all(file_hash(folder/name)==asset['sha256'] for name,asset in old['assets'].items())
data=Path(read(out/'REPRODUCTION-INSTANCE.json')['data']);local=Store(data/'intelligence.sqlite3');pg=PostgresControl(local,data)
try:
    with pg.connect() as c:actual=signature(c,pg.config()['schema'])
    prior=read(out/'baseline/postgresql-backup.json');assert actual==prior['signature'],'Original PostgreSQL identity or table counts changed'
    for name,key in ((prior['name'],'sha256'),):assert file_hash(data/'postgresql-backups'/name)==prior[key]
    assert file_hash(data/'postgresql-backups'/prior['local_control_backup']['name'])==prior['local_control_backup']['sha256']
    counts=pg.fetch('SELECT origin,count(*) AS count FROM '+pg.relation('observations')+' GROUP BY origin ORDER BY origin')
finally:local.close()
result={'at':now(),'status':'PASS','original_baseline_hash_matches':True,'protected_files':len(protected),'matching_protected_files':len(protected),'previous_beta4_bundle_files':len(files),'previous_beta4_assets':len(old['assets']),'mismatches':mismatches,'sqlite_databases':dbs,'postgresql_signature_unchanged':actual,'counts':counts,'previous_backup_hash_matches':True,'sql_server_or_guard_modified':False,'credentials_exported':False}
atomic_json(out/'PRESERVATION-VERIFICATION.json',result);print(json.dumps({'status':'PASS','protected_files':len(protected),'beta4_bundle_files':len(files),'postgresql_observations':actual['rows'],'original_payloads_sha256':actual['original_payloads_sha256']}))
