"""Reconcile executed receipts and preserved data; never convert unavailable gates into passes."""
import hashlib,json,re,shutil,sqlite3,sys,time
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'application'),str(ROOT/'.build-deps-postgresql')]
from living.contracts import atomic_json,now,file_hash
from living.storage import Store
from living.postgres_control import PostgresControl
from living.postgres_migration import reconcile
OUT=ROOT/'evidence/mission-006/postgresql';stamp=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())
def read(p):return json.loads(Path(p).read_text())
def save(name,value):
    target=OUT/name
    if target.exists():
        history=OUT/'report-history'/stamp;history.mkdir(parents=True,exist_ok=True);shutil.copy2(target,history/name)
    if isinstance(value,str):target.write_text(value,encoding='utf-8')
    else:atomic_json(target,{'at':now(),**value})
    return str(target)
def receipt(path,expected=None):
    p=Path(path);d=read(p);checks=d.get('checks',[])
    assert checks and all(c['status'] in ('PASS','LIVE_PASS','MOCK_PASS') for c in checks),str(p)
    if expected is not None:assert len(checks)==expected,(p,len(checks))
    return {'path':str(p),'sha256':file_hash(p),'status':d.get('status') or 'LIVE_PASS','checks':len(checks)}
manifest=read(OUT/'PACKAGE-MANIFEST.json');review=read(OUT/'OWNER-REVIEW-APPLICATION.json');football=read(OUT/'POSTGRESQL-FOOTBALL-IMPORTS.json');migration=read(OUT/'REVIEW-DATA.json')
assert review['exe']==manifest['exe'] and review['version']==manifest['version']
build=read(OUT.parent/'latest-build.json');final=receipt(Path(read(OUT/'latest-final-package.json')['directory'])/'results.json')
assert read(final['path'])['build']['portable_sha256']==build['portable_sha256']
windows=next(p/'results.json' for p in sorted(OUT.parent.glob('windows-*'),reverse=True) if (p/'results.json').exists() and read(p/'results.json').get('installer_sha256')==build['installer_sha256'] and read(p/'results.json').get('status')=='PASS')
native=OUT.parent/'native-acceptance-20261119T094838Z/results.json'
native_current=next(p/'results.json' for p in sorted(OUT.parent.glob('native-acceptance-*'),reverse=True) if (p/'results.json').exists())
native_attempt=read(native_current);native_method='Final physical pointer and Windows control-message attempts did not complete Start/handoff; no pass claimed. Earlier unchanged launcher functions passed eight checks on the previous beta.4 package.';native_pointer='BLOCKED_UNRESOLVED_INPUT_DELIVERY'
tests={
 'live_migration':receipt(OUT/'live-20261119T092725Z/acceptance.json',14),
 'recovery':receipt(OUT/'recovery-20261119T093751Z/results.json',5),
 'source_gui':receipt(OUT/'browser-20261119T093452Z/results.json',29),
 'portable_gui':receipt(OUT/'browser-20261119T094403Z/results.json',29),
 'installed_gui':receipt(Path(read(OUT/'latest-browser.json')['directory'])/'results.json',29),
 'windows':receipt(windows,37),'native_previous':receipt(native,8),
 'cockpit':receipt(OUT.parent/'cockpit-browser-20261119T095051Z/results.json',64),
 'football':receipt(OUT/'football-live-20261119T094516Z/results.json',10),'final_package':final}
unit=OUT/'unit-regression.log';text=unit.read_text();match=re.search(r'Ran (\d+) tests in ([\d.]+)s\s+OK\s*$',text);assert match and int(match[1])==49
tests['unit']={'status':'PASS','checks':49,'seconds':float(match[2]),'path':str(unit),'sha256':file_hash(unit),'scope':'Application and cockpit regression, including mocked provider protocols; not 49 live-provider tests'}
# Independent immutable baseline comparison. Never write into the baseline or original SQLite databases.
pointer=read(OUT/'BASELINE-POINTER.json');base=Path(pointer['directory']);assert file_hash(base/'BASELINE.json')==pointer['sha256']
protected=read(base/'protected-hashes.json');mismatches=[p for p,h in protected.items() if not Path(p).is_file() or file_hash(Path(p))!=h]
assert not mismatches
dbs=[]
for item in read(base/'databases.json'):
    snapshot=Path(item['snapshot']);source=Path(item['source']);assert file_hash(snapshot)==item['sha256']
    with closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro&immutable=1',uri=True)) as c:
        original=dict(c.execute('SELECT id,payload FROM observations'));snapshot_integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True,timeout=15)) as c:
        current=dict(c.execute('SELECT id,payload FROM observations'));integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
    changed=[id for id,payload in original.items() if current.get(id)!=payload];assert not changed and snapshot_integrity==integrity=='ok'
    dbs.append({'source':str(source),'snapshot':str(snapshot),'snapshot_sha256':item['sha256'],'snapshot_hash_matches':True,'original_records':len(original),'current_records':len(current),'additional_records':len(current)-len(original),'missing_or_changed':0,'integrity':integrity})
save('POSTGRESQL-DATA-PRESERVATION.json',{'status':'PASS','baseline_manifest_unchanged':True,'protected_files':len(protected),'matching_protected_files':len(protected),'mismatches':mismatches,'databases':dbs,'sql_server_changes':False,'sidecar_note':'SQLite backup API captured committed WAL. Preserved complete snapshot bytes remain identical; transient empty WAL/SHM files are not a replacement baseline.'})
local=Store(Path(review['data'])/'intelligence.sqlite3');pg=PostgresControl(local,Path(review['data']))
try:
    connection=pg.test();save('POSTGRESQL-CONNECTION-TEST.json',connection);save('POSTGRESQL-DATABASE-INVENTORY.json',{'status':'LIVE_PASS',**pg.databases()})
    checks=[]
    for i in (2,3):
        with closing(sqlite3.connect((base/('database-'+str(i)+'.sqlite3')).as_uri()+'?mode=ro&immutable=1',uri=True)) as c:rows=c.execute('SELECT id,payload FROM observations ORDER BY id').fetchall()
        checks.append(reconcile(pg,rows));assert checks[-1]['status']=='PASS'
    counts=pg.fetch('SELECT kind,origin,count(*) AS rows FROM '+pg.relation('observations')+' GROUP BY kind,origin ORDER BY kind,origin');total=sum(x['rows'] for x in counts);assert total==5840
    save('SQLITE-POSTGRESQL-RECONCILIATION.json',{'status':'PASS','preserved_source_observations':5830,'new_live_acquired_historical_results':10,'destination_observations':total,'comparisons':checks,'counts':counts,'unique_match_caution':'Two separately imported 217-row Champions League datasets retain different source identities. They are not 434 unique matches. No forced cross-provider merge.','historical_checkpoint':{'epl_matches':760,'bookmaker_quotes':2280,'synthetic_observations':84,'champions_league_rows_per_source':217}})
    validation=read(OUT/'POSTGRESQL-SCHEMA-VALIDATION.json');validation.update(counts=counts,tables=pg.tables());save('POSTGRESQL-SCHEMA-VALIDATION.json',validation)
finally:local.close()
save('POSTGRESQL-MIGRATION-RECEIPTS.json',{'status':'PASS','database':'codex_engineering','schema':'dragonhydra_intelligence','receipts':migration['migration_receipts'],'isolated_migration_acceptance':tests['live_migration'],'reconciliation':'SQLITE-POSTGRESQL-RECONCILIATION.json'})
save('POSTGRESQL-MIGRATION-PLAN.md',"""PostgreSQL is the selected relational backend. SQLite remains the explicit offline datastore and local control plane for settings, sessions, protected-credential references and task coordination.

The existing non-superuser owner can create schemas but cannot create databases or roles. The authorized fallback uses codex_engineering.dragonhydra_intelligence, with an ownership marker and independent read-only codex_mcp_ro identity. Runtime, migration and backup purposes have separate protected bindings to the existing owner account; dedicated runtime-role isolation remains BLOCKED.

1. Preserve five coherent SQLite backup snapshots, baseline manifest and protected-file hashes.
2. Provision a fresh DRAGONHYDRA-only test schema. Migrate snapshots 2 and 3 atomically, retaining original payload text, identifiers, SHA-256, metadata and ancillary source tables.
3. Independently compare every source ID and original UTF-8 payload hash; test repeated migration, NUMERIC odds, DATE-only results and rollback. These operations passed before primary selection.
4. Migrate the canonical owned schema, reconcile 5,830 observations, then deliberately select PostgreSQL in the separate review workspace.
5. Carry forward ten verified API-Football historical results with original receipts and response fingerprints. Do not classify them as current live odds.
6. Use pg_dump with an exported repeatable-read snapshot. Restore into a fresh owned schema and compare all recorded table counts and original-payload fingerprints. Separate-database restoration remains BLOCKED by CREATEDB privileges.
7. Preserve the original installed application and SQLite files. Roll back through the older launcher, or deliberately select SQLite for offline access. PostgreSQL failure never silently changes the selected datastore.

No SQL Server services, databases, accounts or maintenance guards were modified. No PostgreSQL server was installed. Credentials are Windows-user/data-directory-bound DPAPI records and excluded from portable archives and backup packages; another Windows account must configure its own authorized credentials.
""")
save('POSTGRESQL-MCP-ACCEPTANCE.json',{'status':'LIVE_PASS','canonical_result':football['mcp'],'restart_acceptance':tests['recovery'],'connection_id_repair':'Use connect response connectionId, not profile UUID. Parse documented CSV results; compare with independent driver.','existing_registration_reused':True,'initial_parser_failure_retained':str(OUT/'live-20261119T092725Z/mcp.json'),'retest':str(OUT/'live-20261119T092725Z/mcp-retest.json')})
save('POSTGRESQL-GUI-ACCEPTANCE.json',{'status':'LIVE_PASS','source':tests['source_gui'],'portable':tests['portable_gui'],'installed':tests['installed_gui'],'final_package':tests['final_package'],'owner_review':read(OUT/'OWNER-REVIEW-GUI.json'),'changed_scope':'Final package recompiled to use the actual native version; web footer and PostgreSQL card wrapping corrected. No database, connector, security or cockpit implementation changed after their retained receipts.','actions_verified':'Discovery, connection, databases, selection, schemas, tables, columns, bounded SELECT, sports, migration, activation, receipts, MCP, backup, isolated restore, diagnostics, CSV import, duplicates, analysis, restart and explicit offline selection.'})
save('POSTGRESQL-AI-TOOLS.json',{'status':'LIVE_PASS','registry_tools':23,'read_role':'codex_mcp_ro','installed_browser_dispatch':tests['installed_gui'],'real_football_tool':tests['football'],'security':'Strict simple SELECT grammar, owned-schema identifiers, parameterized values, maximum 100 returned rows, 10-second statement timeout; database role has no write privileges.','cloud_inference':'BLOCKED for previously configured OpenAI account: insufficient credits; no paid retries. Other unconfigured providers are not live-tested. Actual local tool dispatch is distinct from model inference.','cockpit_regression':tests['cockpit']})
save('POSTGRESQL-BACKUP-RESTORE.json',{'status':'PARTIAL','owned_schema_backup_restore':'PASS','backup':football['review_backup'],'restore':football['restore'],'separate_database_restore':'BLOCKED_NO_CREATEDB','pgadmin':read(OUT/'PGADMIN-ACCEPTANCE.json'),'credentials_included':False,'failed_transaction_and_interruption':tests['recovery'],'original_schema_overwritten':False})
save('POSTGRESQL-WINDOWS-ACCEPTANCE.json',{'status':'PARTIAL','candidate':manifest,'windows':tests['windows'],'native_previous':tests['native_previous'],'native_final_attempt':{'status':'FAIL','path':str(native_current),'checks':native_attempt['checks']},'native_method':native_method,'physical_pointer':native_pointer,'installed_postgresql':tests['installed_gui'],'final_asset_acceptance':tests['final_package'],'cockpit_protocol_regression':tests['cockpit'],'historical_live_football':tests['football'],'previous_installation_replaced':False,'isolated_registration':True,'test_inheritance':'Unchanged acquisition, storage, authentication and cockpit sources retain their source/hash-linked receipts. Full installer lifecycle and PostgreSQL GUI passed on the final recompiled package; final native Start automation remains unresolved.'})
limits=[{'gate':'Dedicated application database','status':'BLOCKED','reason':'Existing authorized account lacks CREATEDB; approved isolated schema fallback is live.'},{'gate':'Dedicated runtime role','status':'BLOCKED','reason':'Existing account lacks CREATEROLE; existing non-superuser owner used for runtime/migration with separate protected purpose bindings; AI uses a distinct read-only role.'},{'gate':'Separate-database restore','status':'BLOCKED','reason':'No CREATEDB. Fresh-schema restore passed without overwriting original data.'},{'gate':'Current pgAdmin GUI query','status':'NOT_RUN','reason':'Existing desktop has no available previous CDP session; preserved without restart. Registration inspected and earlier Mission001 evidence retained.'},{'gate':'Cloud model inference','status':'BLOCKED','reason':'Previously tested OpenAI inference lacks account credits. Other company credentials/access unavailable; mocks explicitly identified.'},{'gate':'Public release','status':'NOT_RUN','reason':'Prepared a local verified candidate. No existing release tags or assets changed; remaining administration limits disclosed.'}]
if native_pointer!='PASS':limits.append({'gate':'Final native Start/handoff automation','status':'FAIL','reason':'Requested pointer position did not remain on the owned control and foreground activation was unstable. Targeted Windows message attempts also did not trigger Start. Three discovery/version/control-layout checks passed; the Start acceptance failed. Earlier eight-check native receipt belongs to the previous package. Final browser and CLI startup pass; native interaction is unresolved.'})
matrix=[{'gate':name,**value} for name,value in tests.items()]+limits
save('ACCEPTANCE-MATRIX.json',{'status':'PARTIAL','rows':matrix,'counts_are_receipt_scoped_not_unique_test_total':True})
save('FINAL-RELEASE-READINESS.json',{'status':'PARTIAL','core_postgresql_candidate':'PASS','local_windows_distribution':'PASS','published':False,'version':manifest['version'],'limitations':limits,'acceptance_matrix':'ACCEPTANCE-MATRIX.json','package_manifest':'PACKAGE-MANIFEST.json','no_sql_server_runtime_requirement':True})
report=f"""DRAGONHYDRA {manifest['version']} is a usable local Windows candidate with real PostgreSQL 18.6 connectivity at 127.0.0.1:5432. It is not published. The original installed applications and published beta.1/beta.2 packages remain available.

Open the desktop shortcut `DRAGONHYDRA PostgreSQL beta.4`. It selects the separate review data directory and opens the existing authenticated application. PostgreSQL is the selected relational datastore in that workspace. The native launcher retains offline mode for external APIs; local PostgreSQL queries remain available. The original application installation was not replaced.

Database: `codex_engineering`; owned schema: `dragonhydra_intelligence`; read identity: `codex_mcp_ro`. A genuine version/identity query and bounded SELECT succeeded. The control center and 23-tool application registry expose actual metadata and records; SQL Server controls and active ODBC dependencies are retired. Existing SQL Server software, guard and evidence were preserved.

Data: 5,830 original immutable observations reconciled by ID and exact payload bytes, plus 10 genuinely acquired API-Football historical results = 5,840 observations. The 760 EPL match results, 2,280 imported historical bookmaker quotations, 84 synthetic observations and both separately attributed 217-row Champions League imports remain identifiable. Duplicate source evidence is preserved, not counted as extra unique football matches. The live acquisition used four bounded provider requests; no live odds or paid feature is claimed.

Validation: 49 application/cockpit regression tests; 14 live migration checks; 5 interruption/recovery checks; 29 PostgreSQL browser checks in each source/portable/installed context; 10 live football-pipeline checks; 37 installer lifecycle checks; 64 cockpit checks using explicitly labeled mock provider protocols; {tests['final_package']['checks']} final package/layout checks. Native method: {native_method}. Final physical-pointer result: {native_pointer}; three initial checks passed and Start/handoff failed. Failed attempts remain recorded and are not converted to passes. Counts overlap by scenario and must not be added as distinct tests. See ACCEPTANCE-MATRIX.json for exact receipts and source/build associations.

Preservation: all {len(protected):,} protected file hashes match; all five original SQLite observation sets and coherent snapshot hashes remain unchanged. PostgreSQL backup and fresh-schema restoration match 5,840 identities and recorded table counts. Credentials are excluded from release archives. Existing unrelated engineering-schema rows also matched their earlier before/after fingerprints.

Limitations: dedicated database and runtime-role creation and separate-database restore are BLOCKED by existing privileges. The explicitly authorized schema fallback is used without privilege escalation. Current pgAdmin GUI querying is NOT_RUN; earlier Mission001 GUI evidence is retained. Cloud inference remains subject to actual credentials and account credits; 64 mock cockpit checks do not establish live company replies. No public release was created.

Portable folder: `{Path(manifest['exe']).parent}`

Installer and ZIP: `{manifest['directory']}`. PACKAGE-MANIFEST.json records exact filenames, sizes and SHA-256 values. Tested source commit: `{manifest['source_commit']}`. The source archive contains exact build inputs; source, installer and portable archive hashes were independently checked.

Rollback: continue using the untouched beta.2 or previous beta.3 launcher/data directory. In this candidate, select SQLite explicitly for preserved offline observations; new PostgreSQL records stay in PostgreSQL. Never overwrite the original data to roll back. Review data: `{review['data']}`.

Overall transition status: PARTIAL because the administration and external-access gates above remain unresolved. Core PostgreSQL migration, authentication, persistence, read-only tools, schema-isolated recovery and the Windows package passed their recorded acceptance.
"""
save('POSTGRESQL-FINAL-REPORT.md',report)
save('MISSION-006-STATE.json',{'mission':'006','workstream':'PostgreSQL transition','status':'PARTIAL','candidate':manifest['version'],'checkpoint':'Verified PostgreSQL Windows candidate delivered locally; preserved baseline independently rechecked','core_candidate':'PASS','server':connection,'observations':total,'review_application':review,'limitations':limits,'published':False,'no_competing_codex_workers':True})
required=['POSTGRESQL-DISCOVERY.json','POSTGRESQL-CONNECTION-TEST.json','POSTGRESQL-DATABASE-INVENTORY.json','POSTGRESQL-SCHEMA-VALIDATION.json','POSTGRESQL-MIGRATION-PLAN.md','POSTGRESQL-MIGRATION-RECEIPTS.json','SQLITE-POSTGRESQL-RECONCILIATION.json','POSTGRESQL-MCP-ACCEPTANCE.json','POSTGRESQL-GUI-ACCEPTANCE.json','POSTGRESQL-AI-TOOLS.json','POSTGRESQL-FOOTBALL-IMPORTS.json','POSTGRESQL-BACKUP-RESTORE.json','POSTGRESQL-WINDOWS-ACCEPTANCE.json','POSTGRESQL-DATA-PRESERVATION.json','POSTGRESQL-FINAL-REPORT.md']
for name in required:
    target=OUT.parent/name
    if target.exists():
        archive=OUT/'report-history'/stamp;archive.mkdir(parents=True,exist_ok=True);shutil.copy2(target,archive/('mission-root-'+name))
    shutil.copy2(OUT/name,target)
atomic_json(OUT/'EVIDENCE-INDEX.json',{'at':now(),'status':'PASS','reports':{name:file_hash(OUT/name) for name in required}})
print(json.dumps({'status':'PARTIAL','core_candidate':'PASS','reports':len(required),'protected_files':len(protected),'observations':total,'report':str(OUT/'POSTGRESQL-FINAL-REPORT.md')}))
