"""Local SQL Server discovery and explicitly guarded, owned SQL synchronization."""
import json,os,re,socket,time,uuid
from pathlib import Path
from contextlib import closing
from .contracts import now,fingerprint,Blocked
from .sql_readonly import ReadOnlyQueries
OWNER='dragonhydra.living-intelligence.mission006';PREFIX='DRAGONHYDRA_M006_'
def ident(name):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}',name):raise ValueError('Invalid owned SQL identifier')
    return '['+name+']'
def guard_state(path,write=False):
    try:s=json.loads(Path(path).read_text(encoding='utf-8-sig')) if path else {}
    except (OSError,ValueError):s={}
    released=s.get('status')=='RELEASED' and s.get('sql_tests_allowed') is True
    allowed=released and s.get('maintenance_window_confirmed') is True if write else released or s.get('sql_read_only_allowed') is True
    return {'allowed':bool(allowed),'status':s.get('status','UNVERIFIED'),'owner':s.get('owner'),'writes_allowed':bool(released and s.get('maintenance_window_confirmed') is True),'reason':s.get('reason','A verified maintenance authority is required')}
def discovery():
    result={'at':now(),'machine':socket.gethostname(),'instances':[],'odbc_drivers':[],'connection_verified':False,'version_source':'Windows registry, not a SQL query'}
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Microsoft SQL Server\Instance Names\SQL') as key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                name,instance,_=winreg.EnumValue(key,i);item={'instance_name':name,'registry_id':instance,'server':socket.gethostname() if name=='MSSQLSERVER' else socket.gethostname()+'\\'+name,'protocols':{}}
                for suffix,fields in [('Setup',('Version','Edition')),('MSSQLServer\\SuperSocketNetLib\\Tcp',('Enabled',)),('MSSQLServer\\SuperSocketNetLib\\Tcp\\IPAll',('TcpPort','TcpDynamicPorts')),('MSSQLServer\\SuperSocketNetLib\\Np',('Enabled',)),('MSSQLServer\\SuperSocketNetLib\\Sm',('Enabled',))]:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,'SOFTWARE\\Microsoft\\Microsoft SQL Server\\'+instance+'\\'+suffix) as k:
                            item['protocols'][suffix]={f:winreg.QueryValueEx(k,f)[0] for f in fields}
                    except OSError:pass
                result['instances'].append(item)
    except (ImportError,OSError):result['registry_status']='UNAVAILABLE'
    try:import pyodbc;result['odbc_drivers']=[d for d in pyodbc.drivers() if 'SQL Server' in d]
    except ImportError:result['driver_status']='NOT_INSTALLED'
    return result
MIGRATIONS=[
 "IF SCHEMA_ID('dh006') IS NULL EXEC('CREATE SCHEMA dh006')",
 "IF OBJECT_ID('dh006.Ownership') IS NULL CREATE TABLE dh006.Ownership(owner nvarchar(100) PRIMARY KEY, schema_version int NOT NULL)",
 "IF OBJECT_ID('dh006.Providers') IS NULL CREATE TABLE dh006.Providers(id nvarchar(80) PRIMARY KEY,name nvarchar(200) NOT NULL)",
 "IF OBJECT_ID('dh006.Observations') IS NULL CREATE TABLE dh006.Observations(id char(64) PRIMARY KEY,provider_id nvarchar(80) NOT NULL REFERENCES dh006.Providers(id),kind nvarchar(40) NOT NULL,origin nvarchar(30) NOT NULL,payload_hash char(64) NOT NULL,payload nvarchar(max) NOT NULL CHECK(ISJSON(payload)=1))",
 "IF OBJECT_ID('dh006.RawEvidence') IS NULL CREATE TABLE dh006.RawEvidence(observation_id char(64) PRIMARY KEY REFERENCES dh006.Observations(id),content_hash char(64) NOT NULL)",
 "IF OBJECT_ID('dh006.SourceIdentities') IS NULL CREATE TABLE dh006.SourceIdentities(observation_id char(64) PRIMARY KEY REFERENCES dh006.Observations(id),external_identity nvarchar(400) NOT NULL)",
 "IF OBJECT_ID('dh006.Lineage') IS NULL CREATE TABLE dh006.Lineage(observation_id char(64) PRIMARY KEY REFERENCES dh006.Observations(id),source_id nvarchar(80) NOT NULL,collected_at nvarchar(40) NOT NULL,observed_at nvarchar(40) NULL)",
 "IF OBJECT_ID('dh006.CollectionReceipts') IS NULL CREATE TABLE dh006.CollectionReceipts(id nvarchar(80) PRIMARY KEY,payload nvarchar(max) NOT NULL CHECK(ISJSON(payload)=1))",
 "IF OBJECT_ID('dh006.ImportTasks') IS NULL CREATE TABLE dh006.ImportTasks(id nvarchar(80) PRIMARY KEY,state nvarchar(30) NOT NULL,payload nvarchar(max) NOT NULL CHECK(ISJSON(payload)=1))",
 "IF OBJECT_ID('dh006.SyncCheckpoints') IS NULL CREATE TABLE dh006.SyncCheckpoints(id nvarchar(80) PRIMARY KEY,completed_at nvarchar(40) NOT NULL,source_fingerprint char(64) NOT NULL,inserted int NOT NULL,duplicates int NOT NULL)"]
for table in ('Competitions','Teams','Fixtures','MatchResults','Statistics','OddsQuotations'):
    MIGRATIONS.append(f"IF OBJECT_ID('dh006.{table}') IS NULL CREATE TABLE dh006.{table}(observation_id char(64) PRIMARY KEY REFERENCES dh006.Observations(id),external_id nvarchar(400) NULL,competition nvarchar(200) NULL,season nvarchar(80) NULL,home_team nvarchar(200) NULL,away_team nvarchar(200) NULL,measurement nvarchar(100) NULL,unit nvarchar(80) NULL,metadata nvarchar(max) NOT NULL CHECK(ISJSON(metadata)=1))")
class SqlControl(ReadOnlyQueries):
    def __init__(self,store,data,guard=None,connector=None):
        self.store=store;self.data=Path(data);self.guard=guard;self.connector=connector
        prior=store.state('sql','connection')
        if prior and prior.get('state')=='CONNECTED':store.state('sql','connection',dict(prior,state='DISCONNECTED',note='Previous query retained. Test the connection after restart to verify current availability.'))
        if not store.state('sql','configuration'):store.state('sql','configuration',{'enabled':False,'server':'lpc:'+socket.gethostname(),'database':'master','driver':'ODBC Driver 18 for SQL Server','trust_local_certificate':False,'guard_path':str(guard) if guard else '', 'sync_enabled':False})
        sync=store.state('sql','sync')
        if sync and sync.get('state')=='RUNNING':sync.update(state='INTERRUPTED',error='SQL transaction outcome must be reconciled using original identities; repeat this bounded page safely');store.state('sql','sync',sync)
    def status(self):
        c=self.store.state('sql','configuration');g=guard_state(self.guard or c.get('guard_path'));last=self.store.state('sql','connection') or {};state='BLOCKED' if not g['allowed'] else 'DISCONNECTED' if not c['enabled'] else last.get('state','DISCONNECTED');return {'state':state,'status':state,'guard':g,'configuration':c,'discovery':self.store.state('sql','discovery'),'connection':last,'query_permissions':'READ_ONLY' if g['allowed'] else 'BLOCKED','write_operations':'ALLOWED_OWNED_ONLY' if g['writes_allowed'] else 'BLOCKED','last_query':self.store.state('sql','last_query'),'sync':self.store.state('sql','sync') or {'state':'DISABLED'},'authentication':'Windows integrated authentication','backups':self.store.state('sql','backups') or {'status':'NOT_RUN'}}
    def discover(self):
        d=discovery();self.store.state('sql','discovery',d);return d
    def configure(self,b):
        if set(b)-{'enabled','server','database','driver','trust_local_certificate','guard_path','sync_enabled'}:raise ValueError('Unknown SQL configuration field; credentials are not accepted')
        c={**self.store.state('sql','configuration'),**b};server=c['server'];host=server.removeprefix('lpc:').removeprefix('tcp:').split('\\')[0].split(',')[0].lower()
        if host not in ('.','localhost','127.0.0.1',socket.gethostname().lower()) or not re.fullmatch(r'[A-Za-z0-9_.\\,:-]{1,160}',server):raise ValueError('Only this local Windows SQL instance is permitted')
        ident(c['database'])
        if c['driver'] not in ('ODBC Driver 18 for SQL Server','ODBC Driver 17 for SQL Server','SQL Server'):raise ValueError('Select an installed SQL Server ODBC driver')
        for k in ('enabled','trust_local_certificate','sync_enabled'):
            if type(c[k]) is not bool:raise ValueError('Invalid SQL option')
        if c.get('guard_path') and not Path(c['guard_path']).is_file():raise ValueError('Select the existing maintenance guard file; this application cannot release it')
        self.store.state('sql','configuration',c);self.store.state('sql','connection',{'state':'DISCONNECTED'});return self.status()
    def connect(self,database=None,write=False):
        c=self.store.state('sql','configuration');g=guard_state(self.guard or c.get('guard_path'),write)
        if not g['allowed']:raise Blocked('SQL maintenance guard '+g['status']+' owned by '+str(g['owner'])+' blocks this operation. Service status does not grant database permission.')
        if not c['enabled']:raise Blocked('Enable the explicitly configured SQL integration first')
        if write and not c['database'].startswith(PREFIX):raise Blocked('Writes require an isolated DRAGONHYDRA_M006_ database')
        if self.connector:return self.connector(database or c['database'],write)
        try:import pyodbc
        except ImportError:raise Blocked('SQL driver module is unavailable; SQLite remains operational') from None
        if c['driver'] not in pyodbc.drivers():raise Blocked('The selected Windows ODBC driver is not installed')
        db=database or c['database'];ident(db)
        try:
            conn=pyodbc.connect('DRIVER={'+c['driver']+'};SERVER='+c['server']+';DATABASE='+db+';Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate='+('yes' if c['trust_local_certificate'] else 'no')+';',timeout=5,autocommit=False);conn.timeout=10;return conn
        except pyodbc.Error as e:
            code=str(e.args[0])[:5];detail=str(e).lower()
            reason='The local SQL certificate is not trusted. For a verified local instance, explicitly select Trust this local instance certificate.' if 'certificate' in detail else 'Windows authentication or database access was denied.' if code in ('28000','42000') else 'Verify the local instance, installed driver and connection timeout.'
            raise ValueError('SQL connection failed (SQLSTATE '+code+'). '+reason+' Server settings were not changed.') from None
    def test(self):
        try:
            with closing(self.connect('master')) as c:
                row=c.cursor().execute("SELECT CONVERT(nvarchar(128),SERVERPROPERTY('ServerName')),CONVERT(nvarchar(80),SERVERPROPERTY('ProductVersion')),CONVERT(nvarchar(128),SERVERPROPERTY('Edition'))").fetchone()
                version=c.cursor().execute('SELECT @@VERSION AS SQLServerVersion').fetchone()[0]
                identity=c.cursor().execute('SELECT DB_NAME() AS CurrentDatabase,SUSER_SNAME() AS LoginName,ORIGINAL_LOGIN() AS OriginalLogin').fetchone()
                dbs=[r[0] for r in c.cursor().execute('SELECT name FROM sys.databases WHERE HAS_DBACCESS(name)=1 ORDER BY name')]
                result={'state':'CONNECTED','checked_at':now(),'last_successful_query':now(),'server':row[0],'product_version':row[1],'edition':row[2],'version':version,'current_database':identity[0],'login_name':identity[1],'original_login':identity[2],'databases':dbs,'verified_by':'REAL_SQL_QUERY','query_permissions':'READ_ONLY'};self.store.state('sql','connection',result);return result
        except Exception as e:self.store.state('sql','connection',{'state':'BLOCKED' if isinstance(e,Blocked) else 'FAILED','checked_at':now(),'error':self.sql_error(e)});raise
    def inventory(self):
        with closing(self.connect()) as c:
            tables=[{'schema':r[0],'table':r[1],'sports_candidate':bool(re.search('football|sport|fixture|match|odds|team|competition',r[1],re.I)) or r[0]=='dh006'} for r in c.cursor().execute('SELECT s.name,t.name FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id ORDER BY s.name,t.name')]
            columns=[{'schema':r[0],'table':r[1],'column':r[2],'type':r[3],'nullable':bool(r[4])} for r in c.cursor().execute('SELECT s.name,t.name,c.name,ty.name,c.is_nullable FROM sys.columns c JOIN sys.tables t ON t.object_id=c.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id JOIN sys.types ty ON ty.user_type_id=c.user_type_id')]
            indexes=[{'schema':r[0],'table':r[1],'index':r[2],'primary_key':bool(r[3])} for r in c.cursor().execute('SELECT s.name,t.name,i.name,i.is_primary_key FROM sys.indexes i JOIN sys.tables t ON t.object_id=i.object_id JOIN sys.schemas s ON s.schema_id=t.schema_id WHERE i.name IS NOT NULL')]
        result={'checked_at':now(),'tables':tables,'columns':columns,'indexes':indexes,'row_data_read':False};self.store.state('sql','inventory',result);return result
    def owned(self,c):
        row=c.cursor().execute("SELECT CAST(value AS nvarchar(100)) FROM sys.extended_properties WHERE class=0 AND name='DRAGONHYDRA_OWNER'").fetchone()
        if not row or row[0]!=OWNER:raise Blocked('Database ownership is not DRAGONHYDRA Mission 006; unrelated tables will not be altered')
    def provision(self,confirmation):
        config=self.store.state('sql','configuration');db=config['database']
        if confirmation!=db or not db.startswith(PREFIX):raise ValueError('Type the exact isolated DRAGONHYDRA_M006_ database name to confirm')
        with closing(self.connect('master',True)) as c:
            exists=c.cursor().execute('SELECT name FROM sys.databases WHERE name=?',db).fetchone()
            if not exists:c.commit();c.autocommit=True;c.cursor().execute('CREATE DATABASE '+ident(db));c.autocommit=False
        with closing(self.connect(write=True)) as c:
            if not exists:c.cursor().execute("EXEC sys.sp_addextendedproperty @name=N'DRAGONHYDRA_OWNER',@value=?",OWNER);c.commit()
            self.owned(c)
            for statement in MIGRATIONS:c.cursor().execute(statement)
            row=c.cursor().execute('SELECT owner,schema_version FROM dh006.Ownership').fetchone()
            if row and (row[0]!=OWNER or row[1]!=1):raise Blocked('Unsupported SQL schema ownership/version')
            if not row:c.cursor().execute('INSERT INTO dh006.Ownership VALUES(?,1)',OWNER)
            c.commit()
        return {'status':'PASS','database':db,'schema':'dh006','version':1,'unrelated_tables_modified':False}
    def sync(self,source,limit=1000,offset=0):
        if not self.store.state('sql','configuration')['sync_enabled']:raise Blocked('SQL synchronization is disabled')
        if type(limit) is not int or not 1<=limit<=1000:raise ValueError('Sync limit is 1–1000 observations')
        if not isinstance(source,str) or not any(s['id']==source for s in self.store.sources()):raise ValueError('Select a configured source for bounded synchronization')
        if type(offset) is not int or offset<0:raise ValueError('Invalid synchronization page offset')
        selected=self.store.query({'source':source},limit,offset);rows=selected['rows'];run=uuid.uuid4().hex;progress={'id':run,'state':'RUNNING','source_id':source,'started_at':now(),'records':len(rows),'offset':offset,'next_offset':offset+len(rows),'total':selected['total'],'paging_note':'Dataset changes can shift pages. Repeating from offset zero checks immutable identities and safely skips committed records.'};self.store.state('sql','sync',progress)
        try:
            with closing(self.connect(write=True)) as c:
                self.owned(c);cur=c.cursor();inserted=duplicates=0
                try:
                    for r in rows:
                        digest=fingerprint(r);prior=cur.execute('SELECT payload_hash FROM dh006.Observations WHERE id=?',r['id']).fetchone()
                        if prior:
                            if prior[0]!=digest:raise ValueError('SQL identity conflict; original evidence differs. Batch rolled back.')
                            duplicates+=1;continue
                        cur.execute('IF NOT EXISTS(SELECT 1 FROM dh006.Providers WHERE id=?) INSERT INTO dh006.Providers VALUES(?,?)',r['source_id'],r['source_id'],r['source_id']);cur.execute('INSERT INTO dh006.Observations VALUES(?,?,?,?,?,?)',r['id'],r['source_id'],r['kind'],r['origin'],digest,json.dumps(r,ensure_ascii=False));cur.execute('INSERT INTO dh006.RawEvidence VALUES(?,?)',r['id'],r['raw_hash']);cur.execute('INSERT INTO dh006.SourceIdentities VALUES(?,?)',r['id'],str(r.get('identity',''))[:400]);cur.execute('INSERT INTO dh006.Lineage VALUES(?,?,?,?)',r['id'],r['source_id'],r['collected_at'],r.get('observed_at'));m=r.get('metadata',{});contract=m.get('contract','');tables=['MatchResults','Fixtures'] if r['kind']=='SPORTS_RESULT' else ['OddsQuotations'] if r['kind']=='SPORTS_ODDS' else {'football.competition/1':['Competitions'],'football.team/1':['Teams'],'football.fixture/1':['Fixtures'],'football.result/1':['Fixtures','MatchResults'],'football.player.statistic/1':['Statistics']}.get(contract,[])
                        for table in tables:cur.execute('INSERT INTO dh006.'+ident(table)+' VALUES(?,?,?,?,?,?,?,?,?)',r['id'],str(r.get('identity',''))[:400],str(m.get('competition',''))[:200],str(m.get('season',''))[:80],str(m.get('home',m.get('home_team','')))[:200],str(m.get('away',m.get('away_team','')))[:200],r.get('value'),r.get('unit'),json.dumps(m,ensure_ascii=False))
                        inserted+=1
                    for receipt in self.store.summary()['receipts']:
                        if receipt['source_id']==source:cur.execute('IF NOT EXISTS(SELECT 1 FROM dh006.CollectionReceipts WHERE id=?) INSERT INTO dh006.CollectionReceipts VALUES(?,?)',receipt['id'],receipt['id'],json.dumps(receipt))
                    for task in self.store.tasks():
                        if task['payload'].get('source_id')==source:cur.execute('IF NOT EXISTS(SELECT 1 FROM dh006.ImportTasks WHERE id=?) INSERT INTO dh006.ImportTasks VALUES(?,?,?)',task['id'],task['id'],task['state'],json.dumps(task))
                    cur.execute('INSERT INTO dh006.SyncCheckpoints VALUES(?,?,?,?,?)',run,now(),fingerprint(rows),inserted,duplicates);c.commit()
                except BaseException:c.rollback();raise
                count=cur.execute('SELECT COUNT_BIG(*) FROM dh006.Observations WHERE provider_id=?',source).fetchone()[0]
            progress.update(state='COMPLETE',inserted=inserted,duplicates=duplicates,sql_source_row_count=count,completed_at=now(),source_fingerprint=fingerprint(rows));self.store.state('sql','sync',progress);return progress
        except Exception as e:progress.update(state='BLOCKED' if isinstance(e,Blocked) else 'FAILED',error=str(e));self.store.state('sql','sync',progress);raise
    def backup_info(self):
        config=self.store.state('sql','configuration')
        with closing(self.connect('msdb')) as c:rows=[{'finished_at':str(r[0]),'type':r[1],'bytes':int(r[2])} for r in c.cursor().execute('SELECT TOP(20) backup_finish_date,type,backup_size FROM dbo.backupset WHERE database_name=? ORDER BY backup_finish_date DESC',config['database'])]
        result={'status':'CATALOG_VERIFIED','backups':rows,'restoration_verified':False,'limitation':'Catalog records do not prove that media remains accessible or restorable'};self.store.state('sql','backups',result);return result
