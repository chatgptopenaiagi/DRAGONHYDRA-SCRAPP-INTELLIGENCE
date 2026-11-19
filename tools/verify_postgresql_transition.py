"""Bounded live acceptance against a fresh DRAGONHYDRA-owned schema. No service changes."""
import json,sys,time,traceback,uuid,sqlite3,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'application'),str(ROOT/'.build-deps-postgresql')]
from living.storage import Store
from living.postgres_control import PostgresControl
from living.contracts import atomic_json,now,fingerprint

def main():
    run=ROOT/'evidence/mission-006/postgresql'/('live-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));run.mkdir(parents=True)
    local=Store(run/'data/intelligence.sqlite3');pg=PostgresControl(local,run/'data');checks=[]
    def check(name,fn):
        try:
            value=fn();checks.append({'name':name,'status':'LIVE_PASS','detail':value});print(name+': LIVE_PASS',flush=True)
        except Exception as e:
            checks.append({'name':name,'status':'FAIL','error':str(e) if isinstance(e,(ValueError,AssertionError)) else type(e).__name__});print(name+': FAIL '+checks[-1]['error'],flush=True)
            atomic_json(run/'acceptance.json',{'at':now(),'checks':checks});raise
        atomic_json(run/'acceptance.json',{'at':now(),'checks':checks});return value
    try:
        pg.configure({'enabled':True,'schema':'dragonhydra_test_'+uuid.uuid4().hex[:12]});check('Protected existing credential reuse',pg.import_existing_credentials);check('Real PostgreSQL SELECT',pg.test)
        before=pg.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='ai_workspace' ORDER BY table_name")
        def unrelated():
            with pg.connect() as c:return {r['table_name']:fingerprint(c.execute('SELECT row_to_json(t)::text FROM ai_workspace."'+r['table_name']+'" t ORDER BY 1').fetchall()) for r in before}
        baseline=unrelated();atomic_json(run/'unrelated-before.json',baseline)
        check('Create only isolated owned schema',pg.provision)
        base=Path(json.loads((ROOT/'evidence/mission-006/postgresql/BASELINE-POINTER.json').read_text())['directory'])
        for i in (2,3):check('Migrate preserved snapshot '+str(i),lambda i=i:pg.migrate(base/('database-'+str(i)+'.sqlite3')))
        def counts():
            rows=pg.fetch('SELECT kind,origin,count(*) AS rows FROM '+pg.relation('observations')+' GROUP BY kind,origin ORDER BY kind,origin');assert sum(x['rows'] for x in rows)==5830,rows;return rows
        check('5830 original observation identities',counts)
        check('Repeat migration safely',lambda:pg.migrate(base/'database-2.sqlite3'))
        check('Counts unchanged after repeat',counts)
        def exact():
            r=pg.fetch('SELECT count(*) AS n FROM '+pg.relation('observations')+" WHERE origin='IMPORTED' AND kind='SPORTS_ODDS' AND value::numeric=(payload->>'value')::numeric");assert r[0]['n']==2280,r
            d=pg.fetch('SELECT count(*) AS n FROM '+pg.relation('observations')+" WHERE origin='IMPORTED' AND kind='SPORTS_RESULT' AND observed_at IS NULL AND event_date IS NOT NULL");assert d[0]['n']==1194,d
            return {'decimal_odds_exact':r,'date_only_results':d}
        check('NUMERIC odds and DATE precision',exact)
        def rollback():
            try:
                with pg.connect('runtime',False) as c:c.execute('INSERT INTO '+pg.relation('providers')+' VALUES(%s,%s)',('rollback-probe','{}'));raise RuntimeError('Injected transaction failure')
            except RuntimeError:pass
            assert not pg.fetch('SELECT id FROM '+pg.relation('providers')+' WHERE id=%s',('rollback-probe',));return {'rolled_back':True}
        check('Failed transaction rollback',rollback)
        def readonly():
            denied=False
            try:
                with pg.connect() as c:c.execute('INSERT INTO '+pg.relation('providers')+' VALUES(%s,%s)',('readonly-probe','{}'))
            except ValueError:denied=True
            assert denied
            with pg.connect() as c:
                c.rollback();c.execute('SET TRANSACTION READ WRITE')
                row=c.execute("SELECT has_table_privilege(current_user,%s,'INSERT'),has_table_privilege(current_user,%s,'UPDATE'),has_table_privilege(current_user,%s,'DELETE')",(pg.config()['schema']+'.observations',)*3).fetchone();assert row==(False,False,False),row
            return {'transaction_write_denied':True,'database_role_write_privileges':row}
        check('Read-only transaction and role enforcement',readonly)
        def attack():
            for query in ('SELECT pg_sleep(10)','SELECT * FROM observations; DROP TABLE providers','WITH x AS (DELETE FROM observations RETURNING *) SELECT * FROM x','SELECT * FROM ai_workspace.projects','SELECT * INTO observations FROM providers'):
                try:pg.query({'sql':query})
                except (ValueError,RuntimeError):continue
                raise AssertionError('Unsafe SQL accepted')
            return {'unsafe_queries_rejected':5}
        check('SQL grammar rejects writes and functions',attack)
        check('Real bounded query',lambda:pg.query({'sql':'SELECT id,kind,origin FROM observations LIMIT 5'}))
        def preserve():assert unrelated()==baseline;return {'other_schema_rows_unchanged':True}
        check('Unrelated engineering tables unchanged',preserve)
        atomic_json(run/'configuration.json',pg.config());atomic_json(ROOT/'evidence/mission-006/postgresql/latest-live.json',{'directory':str(run),'schema':pg.config()['schema'],'checks':len(checks),'status':'LIVE_PASS'})
    finally:local.close()
if __name__=='__main__':main()
