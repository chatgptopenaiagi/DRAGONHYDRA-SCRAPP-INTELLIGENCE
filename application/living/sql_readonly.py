"""Bounded local SQL reads. No user/model SQL text is accepted or executed."""
import json,re,uuid
from contextlib import closing
from .contracts import now,Blocked,fingerprint

SPORTS=re.compile(r'football|sport|fixture|match|odds|team|competition|standing|bookmaker',re.I)
SENSITIVE=re.compile(r'password|secret|credential|token|email|address|phone',re.I)
def quote(name):
    if not isinstance(name,str) or not 1<=len(name)<=128 or any(ord(c)<32 for c in name):raise ValueError('Invalid SQL object identifier')
    return '['+name.replace(']',']]')+']'
def row_limit(value):
    if type(value) is not int or not 1<=value<=100:raise ValueError('SQL reads return 1–100 rows per request')
    return value

class ReadOnlyQueries:
    def read(self,query_id,database,sql,parameters=(),limit=100):
        row_limit(limit);receipt={'id':uuid.uuid4().hex,'query_id':query_id,'at':now(),'database':database,'permission':'READ_ONLY','row_limit':limit,'timeout_seconds':10}
        try:
            with closing(self.connect(database)) as c:
                cur=c.cursor().execute(sql,*parameters);names=[d[0] for d in cur.description];records=cur.fetchmany(limit+1)
                rows=[{k:v if v is None or isinstance(v,(str,int,float,bool)) else str(v) for k,v in zip(names,r)} for r in records[:limit]]
            if len(json.dumps(rows).encode())>40000:raise ValueError('Result exceeds 40 KB. Select fewer rows or narrower metadata.')
            receipt.update(state='PASS',returned=len(rows),truncated=len(records)>limit,rows=rows,fingerprint=fingerprint(rows),completed_at=now())
        except Exception as e:
            receipt.update(state='BLOCKED' if isinstance(e,Blocked) else 'FAILED',error=self.sql_error(e),completed_at=now());self.store.state('sql','last_query',receipt)
            raise (Blocked if isinstance(e,Blocked) else ValueError)(receipt['error']) from None
        self.store.state('sql','last_query',receipt);return receipt
    @staticmethod
    def sql_error(e):
        if isinstance(e,(Blocked,ValueError)):return str(e)
        # Windows-authenticated fixed queries never contain API keys or SQL passwords.
        state=str(getattr(e,'args',[''])[0])[:5]
        return 'SQL read failed (SQLSTATE '+state+'). The Windows login may lack access, or the query timed out. No permission or database was changed.'
    def databases(self):
        return self.read('database_catalog','master','SELECT TOP (101) name,state_desc,HAS_DBACCESS(name) AS accessible FROM sys.databases ORDER BY name')
    def schemas(self,database=None):
        db=database or self.store.state('sql','configuration')['database'];quote(db)
        return self.read('schemas',db,'SELECT TOP (101) name,schema_id FROM sys.schemas ORDER BY name')
    def tables(self,database=None,schema='',include_system=False):
        db=database or self.store.state('sql','configuration')['database'];quote(db)
        if schema:quote(schema)
        if type(include_system) is not bool:raise ValueError('Invalid system object option')
        r=self.read('tables',db,"SELECT TOP (101) s.name AS schema_name,o.name AS table_name,o.object_id,o.type_desc,o.is_ms_shipped AS system_object,HAS_PERMS_BY_NAME(QUOTENAME(s.name)+'.'+QUOTENAME(o.name),'OBJECT','SELECT') AS select_allowed FROM sys.all_objects o JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE o.type IN ('U','V') AND (?=1 OR o.is_ms_shipped=0) AND (?='' OR s.name=?) ORDER BY s.name,o.name",(int(include_system),schema,schema))
        for row in r['rows']:row['sports_candidate']=bool(SPORTS.search(row['table_name'])) or row['schema_name']=='dh006'
        r['limitation']='Only metadata visible to this Windows login. No visible sports tables does not prove none exist in inaccessible databases.';return r
    def describe(self,database=None,schema='dbo',table=''):
        db=database or self.store.state('sql','configuration')['database'];quote(db);quote(schema);quote(table)
        obj=self.read('object_identity',db,"SELECT o.object_id,o.type_desc,o.is_ms_shipped AS system_object,HAS_PERMS_BY_NAME(QUOTENAME(s.name)+'.'+QUOTENAME(o.name),'OBJECT','SELECT') AS select_allowed FROM sys.all_objects o JOIN sys.schemas s ON s.schema_id=o.schema_id WHERE s.name=? AND o.name=? AND o.type IN ('U','V')",(schema,table))
        if not obj['rows']:raise ValueError('This table or view is absent or not visible to the authenticated Windows login')
        oid=obj['rows'][0]['object_id']
        columns=self.read('table_columns',db,"SELECT TOP (101) c.name,c.column_id,t.name AS data_type,c.max_length,c.is_nullable FROM sys.all_columns c JOIN sys.types t ON t.user_type_id=c.user_type_id WHERE c.object_id=? ORDER BY c.column_id",(oid,))
        indexes=self.read('table_indexes',db,'SELECT TOP (101) name,is_primary_key,is_unique,type_desc FROM sys.indexes WHERE object_id=? AND name IS NOT NULL ORDER BY index_id',(oid,))
        return {'database':db,'schema':schema,'table':table,'object':obj['rows'][0],'columns':columns['rows'],'indexes':indexes['rows'],'column_list_truncated':columns['truncated'],'sports_candidate':bool(SPORTS.search(table)) or schema=='dh006','checked_at':now()}
    def readonly_query(self,b):
        if not isinstance(b,dict) or set(b)-{'query_id','database','schema','table','limit'}:raise ValueError('Select a read-only query template; arbitrary SQL and extra arguments are not accepted')
        db=b.get('database') or self.store.state('sql','configuration')['database'];quote(db);limit=row_limit(b.get('limit',20));q=b.get('query_id')
        if q=='server_identity':return self.read(q,db,'SELECT @@VERSION AS SQLServerVersion,CONVERT(nvarchar(128),SERVERPROPERTY(\'ServerName\')) AS ServerName,DB_NAME() AS CurrentDatabase,SUSER_SNAME() AS LoginName,ORIGINAL_LOGIN() AS OriginalLogin',limit=limit)
        if q=='database_catalog':return self.read(q,'master','SELECT TOP (101) name,state_desc,HAS_DBACCESS(name) AS accessible FROM sys.databases ORDER BY name',limit=limit)
        if q=='schemas':return self.read(q,db,'SELECT TOP (101) name,schema_id FROM sys.schemas ORDER BY name',limit=limit)
        if q=='sports_records':
            d=self.describe(db,b.get('schema','dbo'),b.get('table',''))
            if not d['sports_candidate'] or d['object']['system_object'] or not d['object']['select_allowed']:raise Blocked('Select a visible sports table with SELECT permission; unrelated or system records are not shared')
            if d['column_list_truncated']:raise ValueError('This table has too many columns for the supported bounded reader')
            allowed=[c for c in d['columns'] if not SENSITIVE.search(c['name']) and c['data_type'] in ('int','bigint','smallint','tinyint','bit','decimal','numeric','money','smallmoney','float','real','varchar','nvarchar','char','nchar','date','datetime','datetime2','smalldatetime','datetimeoffset','time','uniqueidentifier')]
            if not allowed or len(allowed)>64:raise ValueError('No supported bounded sports projection, or more than 64 selected columns')
            # Every identifier came from exact parameterized metadata lookup; quote even those.
            columns=','.join('CONVERT(nvarchar(2000),'+quote(c['name'])+') AS '+quote(c['name']) for c in allowed)
            r=self.read(q,db,'SELECT TOP (?) '+columns+' FROM '+quote(d['schema'])+'.'+quote(d['table']),(limit+1,),limit)
            r['projection']={'schema':d['schema'],'table':d['table'],'columns':[c['name'] for c in allowed],'limitation':'Bounded preview; values represented as text up to 2,000 characters. No inferred timestamps, total count or stable row ordering.'};return r
        raise ValueError('Unknown read-only query template. SQL text, batches, EXEC and writes are never accepted.')
