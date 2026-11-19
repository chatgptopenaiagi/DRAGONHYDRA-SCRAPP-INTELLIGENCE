"""Local PostgreSQL integration. Explicit schema ownership and separate read credentials."""
import contextlib,hashlib,json,re,socket,subprocess,uuid
from pathlib import Path
from .contracts import now,encode,fingerprint,Blocked,atomic_json
from .credentials import Vault,protect
from .postgres_schema import OWNER,DDL

PURPOSES=('runtime','migration','readonly','administration')
TABLES=('providers','competitions','seasons','teams','fixtures','match_results','match_events','player_statistics','team_statistics','bookmakers','odds_markets','odds_quotes','observations','raw_evidence','import_receipts','acquisition_tasks','provider_connections','analysis_results','data_lineage','migration_history','workspace_evidence')
def ident(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z_][a-z0-9_]{0,62}',value):raise ValueError('Use a PostgreSQL identifier containing lowercase letters, digits and underscores')
    return '"'+value+'"'
def jsonable(value):return json.loads(json.dumps(value,default=str))

class PostgresControl:
    def __init__(self,local,data):
        self.local=local;self.data=Path(data);self.vault=Vault(data,'postgres')
        if not self.local.state('postgres','configuration'):
            self.local.state('postgres','configuration',{'enabled':False,'primary':False,'host':'127.0.0.1','port':5432,'database':'codex_engineering','schema':'dragonhydra_intelligence','runtime_user':'codex_lab_owner','migration_user':'codex_lab_owner','readonly_user':'codex_mcp_ro','administration_user':'codex_lab_owner'})
        # A historical test is not a live failure. Do not reset shared state when a
        # diagnostic client is constructed; successful reads establish this session.
        self._query_health=None
        from .postgres_store import PostgresStore
        self.store=PostgresStore(self)
    def config(self):return self.local.state('postgres','configuration')
    def relation(self,name):return ident(self.config()['schema'])+'.'+ident(name)
    def lock_id(self):return int.from_bytes(hashlib.sha256((self.config()['database']+'/'+self.config()['schema']).encode()).digest()[:8],signed=True)
    def binding(self,purpose):
        c=self.config();return fingerprint(['dh.postgresql/1',c['host'],c['port'],c['database'],c['schema'],c[purpose+'_user']])
    def configure(self,body):
        c=self.config()
        if set(body)-set(c) or 'primary' in body:raise ValueError('Unknown configuration field; use verified activation to change the primary datastore')
        if c['primary'] and any(body.get(k,c[k])!=c[k] for k in c if k not in ('primary',)):raise Blocked('Switch explicitly to SQLite before changing a primary PostgreSQL connection')
        c.update(body)
        if c['host'] not in ('127.0.0.1','localhost','::1'):raise ValueError('Only the verified local PostgreSQL service is supported')
        if type(c['port']) is not int or not 1<=c['port']<=65535:raise ValueError('Invalid PostgreSQL port')
        if type(c['enabled']) is not bool:raise ValueError('Enable must be a boolean')
        for k in ('database','schema',*(p+'_user' for p in PURPOSES)):ident(c[k])
        if not c['schema'].startswith('dragonhydra_'):raise ValueError('Select an isolated dragonhydra_ schema')
        if c['readonly_user']==c['runtime_user']:raise ValueError('AI queries require a separate read-only database identity')
        self._query_health=None
        self.local.state('postgres','configuration',c);self.local.state('postgres','connection',{'state':'NOT_CHECKED'});return self.status()
    def credentials(self,body,remove=False):
        purpose=body.get('purpose','runtime')
        if purpose not in PURPOSES:raise ValueError('Unknown PostgreSQL credential purpose')
        return self.vault.remove(purpose) if remove else self.vault.save(purpose,self.binding(purpose),body.get('credential'))
    def import_existing_credentials(self):
        c=self.config()
        if c['database']!='codex_engineering' or any(c[p+'_user']!=('codex_mcp_ro' if p=='readonly' else 'codex_lab_owner') for p in PURPOSES):raise Blocked('Existing profiles belong only to the verified Mission 001 identities and database')
        root=Path(r'C:\xampp\POSTGRESQL-CODEX-LAB\.secrets')
        for p in PURPOSES:
            raw=protect((root/('readonly.dpapi' if p=='readonly' else 'dev.dpapi')).read_bytes(),b'',True).decode()
            self.vault.save(p,self.binding(p),raw);del raw
        return {'status':'PASS','credentials':'Four purpose bindings protected with Windows user-scoped DPAPI','limitation':'Runtime, migration and administration share the existing non-superuser account. No privilege escalation or role creation.'}
    def secrets(self):
        values=[]
        for p in PURPOSES:
            try:values.append(self.vault.get(p,self.binding(p)))
            except (ValueError,OSError):pass
        return values
    @contextlib.contextmanager
    def connect(self,purpose='readonly',read_only=True):
        if purpose not in PURPOSES:raise ValueError('Unknown PostgreSQL access purpose')
        c=self.config()
        if not c['enabled']:raise Blocked('PostgreSQL is disabled. Configure and enable the local connection first.')
        if purpose=='readonly' and not read_only:raise Blocked('The AI read-only credential cannot execute write operations')
        try:import psycopg
        except ImportError:raise Blocked('The PostgreSQL client is unavailable in this build; select the explicit SQLite offline datastore') from None
        try:
            with psycopg.connect(host=c['host'],port=c['port'],dbname=c['database'],user=c[purpose+'_user'],password=self.vault.get(purpose,self.binding(purpose)),connect_timeout=5,application_name='DRAGONHYDRA/'+purpose,options='-c statement_timeout=10000 -c lock_timeout=5000 -c search_path=pg_catalog') as conn:
                conn.execute('SET TRANSACTION READ ONLY' if read_only else 'SET TRANSACTION READ WRITE')
                role=conn.execute('SELECT rolsuper,rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user').fetchone()
                if role[0] or role[1]:raise Blocked('Use a non-superuser account without role-administration privileges')
                yield conn
                identity={'database':conn.info.dbname,'user':conn.info.user,'host':conn.info.host,'port':conn.info.port}
            if purpose=='readonly':self._query_health={'state':'CONNECTED','at':now(),'last_successful_query':now(),'verified_by':'Successful read-only PostgreSQL transaction in this application session',**identity}
        except psycopg.Error as e:
            code=e.sqlstate or 'CONNECTION'
            explanation=('The saved database login was rejected. Check the selected read-only identity and re-enter its authorized password.' if code.startswith('28') else 'The database login cannot read this object. Check the selected DRAGONHYDRA schema and existing permissions; no permission changes were made.' if code=='42501' else 'The query exceeded its time limit. Narrow the selected data and try again.' if code=='57014' else 'Could not complete the database query. Check the local PostgreSQL service, host, port and selected database.')
            if purpose=='readonly':self._query_health={'state':'AUTHENTICATION_FAILED' if code.startswith('28') else 'BLOCKED' if code=='42501' else 'FAILED','at':now(),'error':explanation,'sqlstate':code}
            raise ValueError(explanation+' (SQLSTATE '+code+'). Original observations were not replaced.') from None
        except (ValueError,Blocked) as e:
            if purpose=='readonly':self._query_health={'state':'BLOCKED','at':now(),'error':str(e)}
            raise
    def owned(self,c):
        s=self.config()['schema'];row=c.execute('SELECT to_regclass(%s)',(s+'.ownership',)).fetchone()
        if not row[0]:raise Blocked('The selected schema has not been initialized as DRAGONHYDRA-owned')
        if c.execute('SELECT owner,version FROM '+self.relation('ownership')).fetchall()!=[(OWNER,1)]:raise Blocked('Schema ownership or version does not match DRAGONHYDRA')
    def provision(self):
        from psycopg import sql
        cfg=self.config();s=ident(cfg['schema'])
        with self.connect('migration',False) as c:
            c.execute('SELECT pg_advisory_xact_lock(%s)',(self.lock_id(),))
            if c.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s',(cfg['schema'],)).fetchone():self.owned(c)
            else:
                c.execute(DDL.replace('__S__',s));c.execute('INSERT INTO '+self.relation('ownership')+' VALUES(%s,1)',(OWNER,))
            c.execute('REVOKE ALL ON SCHEMA '+s+' FROM PUBLIC')
            c.execute('GRANT USAGE ON SCHEMA '+s+' TO '+ident(cfg['readonly_user']))
            c.execute('GRANT SELECT ON ALL TABLES IN SCHEMA '+s+' TO '+ident(cfg['readonly_user']))
        return {'status':'PASS','database':cfg['database'],'schema':cfg['schema'],'owner':OWNER,'version':1,'isolation':'OWNED_SCHEMA','dedicated_database':'BLOCKED_NO_CREATEDB','dedicated_runtime_role':'BLOCKED_NO_CREATEROLE'}
    def test(self):
        try:
            with self.connect('readonly',True) as c:
                version=c.execute('SELECT version()').fetchone()[0];r=c.execute('SELECT current_database(),current_user,inet_server_addr(),inet_server_port()').fetchone()
                readonly=c.execute('SHOW transaction_read_only').fetchone()[0]
            result={'state':'CONNECTED','status':'LIVE_PASS','version':version,'database':r[0],'user':r[1],'host':str(r[2]),'port':r[3],'transaction_read_only':readonly,'at':now(),'last_successful_query':now(),'verified_by':'SELECT version(); SELECT current_database(),current_user,inet_server_addr(),inet_server_port()'}
            self.local.state('postgres','connection',result);return result
        except (ValueError,Blocked) as e:self.local.state('postgres','connection',{'state':'BLOCKED' if isinstance(e,Blocked) else 'FAILED','at':now(),'error':str(e)});raise
    def status(self):
        c=self.config();last=self.local.state('postgres','connection') or {'state':'DISCONNECTED'}
        current={**last,**(self._query_health or {'state':'NOT_CHECKED','note':'No query has run in this session yet. A previous test is historical, not evidence of a current failure.'})}
        if current['state']=='CONNECTED':current.pop('error',None);current.pop('note',None);current.pop('sqlstate',None)
        return {'state':current['state'] if c['enabled'] else 'DISABLED','configuration':c,'connection':current,'last_explicit_test':last,'configuration_only':self._query_health is None,'credentials':{p:self.vault.status(p,self.binding(p)) for p in PURPOSES},'primary':'POSTGRESQL' if c['primary'] else 'SQLITE_OFFLINE','query_permissions':'READ_ONLY','writes':'APPLICATION_OWNED_SCHEMA_ONLY','mcp':self.local.state('postgres','mcp') or {'status':'NOT_RUN'},'backups':self.local.states('postgres-backup'),'migration':self.local.state('postgres','migration'),'role_limitation':'Existing non-superuser owner is shared for runtime/migration/admin; AI has a distinct SELECT-only credential. Separate runtime role creation requires an authorized database administrator.'}
    def discover(self):
        binaries=Path(r'C:\Program Files\PostgreSQL\18\bin');result={'at':now(),'client_bin':str(binaries),'tools':{name:(binaries/(name+'.exe')).is_file() for name in ('psql','pg_dump','pg_restore')},'connection_verified':False}
        try:
            import psutil
            result['services']=[]
            for service in psutil.win_service_iter():
                if service.name().lower().startswith('postgres'):
                    d=service.as_dict();result['services'].append({'Name':d['name'],'State':d['status'],'StartName':d['username'],'PathName':d['binpath'],'ProcessId':d['pid']})
        except (ImportError,OSError,RuntimeError):result['services']='UNAVAILABLE'
        self.local.state('postgres','discovery',result);return result
    def fetch(self,query,params=()):
        with self.connect() as c:
            cur=c.execute(query,params or None);return jsonable([dict(zip([d.name for d in cur.description],r)) for r in cur.fetchall()])
    def databases(self):return {'rows':self.fetch("SELECT datname AS database,pg_get_userbyid(datdba) AS owner,has_database_privilege(datname,'CONNECT') AS accessible FROM pg_database WHERE NOT datistemplate ORDER BY datname"),'at':now()}
    def schemas(self):return {'rows':self.fetch("SELECT nspname AS schema,has_schema_privilege(nspname,'USAGE') AS accessible FROM pg_namespace WHERE nspname NOT LIKE 'pg_%' AND nspname<>'information_schema' ORDER BY nspname"),'at':now()}
    def tables(self):return {'rows':self.fetch('SELECT table_schema,table_name,table_type FROM information_schema.tables WHERE table_schema=%s ORDER BY table_name',(self.config()['schema'],)),'at':now()}
    def describe(self,table):
        self.allowed_table(table)
        return {'rows':self.fetch('SELECT column_name,data_type,is_nullable,numeric_precision,numeric_scale FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',(self.config()['schema'],table)),'at':now()}
    def allowed_table(self,table):
        if table not in TABLES:raise ValueError('Select a DRAGONHYDRA table or view from the discovered list')
        return table
    def query(self,body):
        table=body.get('table','observations');cols=body.get('columns',['*']);limit=body.get('limit',25);filters=body.get('filters',{})
        if body.get('sql'):
            # Intentionally small SELECT grammar. No functions, expressions, joins, comments or multiple statements.
            m=re.fullmatch(r'\s*SELECT\s+(\*|[a-z_][a-z0-9_]*(?:\s*,\s*[a-z_][a-z0-9_]*)*)\s+FROM\s+(?:([a-z_][a-z0-9_]*)\.)?([a-z_][a-z0-9_]*)(?:\s+LIMIT\s+(\d+))?\s*;?\s*',body['sql'],re.I)
            if not m or (m[2] and m[2]!=self.config()['schema']):raise ValueError('Supported query: SELECT column1,column2 FROM selected_table LIMIT 25. Use table filters for parameterized equality conditions. Functions, writes and compound SQL are prohibited.')
            table=m[3];cols=[x.strip() for x in m[1].split(',')];limit=int(m[4] or limit)
        self.allowed_table(table)
        if table in ('workspace_evidence','provider_connections','raw_evidence'):raise Blocked('Original evidence is retained privately. Use observations, receipts or lineage for bounded research queries.')
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('Read-only query limit must be 1–100 rows')
        names={r['column_name'] for r in self.describe(table)['rows']}
        if not isinstance(cols,list) or not cols or (cols!=['*'] and any(x not in names for x in cols)):raise ValueError('Select actual discovered column names')
        if not isinstance(filters,dict) or len(filters)>8 or any(k not in names or not isinstance(v,(str,int,bool,type(None))) for k,v in filters.items()):raise ValueError('Filters must contain at most eight valid column/value pairs')
        query='SELECT '+('*' if cols==['*'] else ','.join(ident(x) for x in cols))+' FROM '+self.relation(table);params=[]
        if filters:query+=' WHERE '+' AND '.join(ident(k)+' IS NOT DISTINCT FROM %s' for k in filters);params=list(filters.values())
        query+=' LIMIT %s';params.append(limit)
        rows=self.fetch(query,params);result={'id':uuid.uuid4().hex,'at':now(),'status':'LIVE_PASS','database':self.config()['database'],'schema':self.config()['schema'],'table':table,'rows':rows,'returned':len(rows),'limit':limit,'read_only':True,'credential_purpose':'readonly'}
        # Avoid returning binary raw content or private state to an AI/UI query.
        if table in ('workspace_evidence','provider_connections','raw_evidence'):raise Blocked('Original evidence is retained privately. Use observations, receipts or lineage for bounded research queries.')
        self.local.state('postgres','last_query',{k:v for k,v in result.items() if k!='rows'});return result
    def migrate(self,path):
        from .postgres_migration import migrate
        return migrate(self,Path(path))
    def activate(self,backend):
        c=self.config()
        if backend=='POSTGRESQL':
            from .postgres_migration import reconcile
            with self.local.lock:rows=self.local.c.execute('SELECT id,payload FROM observations ORDER BY id').fetchall()
            result=reconcile(self,[(r[0],r[1]) for r in rows])
            if result['status']!='PASS':raise Blocked('Local observations are not fully reconciled in PostgreSQL. Run verified migration first.')
            self.test();c['primary']=True
        elif backend=='SQLITE_OFFLINE':c['primary']=False
        else:raise ValueError('Select POSTGRESQL or SQLITE_OFFLINE explicitly')
        self.local.state('postgres','configuration',c);return self.status()
    def backup(self):
        from .postgres_backup import backup
        return backup(self)
    def restore(self,backup_id):
        from .postgres_backup import restore
        return restore(self,backup_id)
    def check_mcp(self):
        from .postgres_mcp import check
        result=check(self);self.local.state('postgres','mcp',result);return result
