"""Bounded stdio client for the existing postgres_engineering server; no new registration."""
import csv,io,json,os,queue,subprocess,threading,time
from pathlib import Path
from .contracts import now,Blocked

EXE=Path(r'C:\xampp\POSTGRESQL-CODEX-LAB\mcp\node_modules\@microsoft\postgres-mcp-win32-x64\bin\postgres-mcp.exe')
class Client:
    def __enter__(self):
        if not EXE.is_file():raise Blocked('The existing postgres_engineering executable was not found')
        env=os.environ.copy();env.update(POSTGRES_MCP_DISABLE_CWD_ACCESS='1',POSTGRES_MCP_QUERY_TIMEOUT_MS='10000')
        self.p=subprocess.Popen([str(EXE),'run','--no-telemetry'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8',env=env,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.q=queue.Queue();self.next=0
        def reader():
            for line in self.p.stdout:
                try:self.q.put(json.loads(line))
                except ValueError:pass
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
        try:
            self.call('initialize',{'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'DRAGONHYDRA','version':'0.2'}});self.p.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');self.p.stdin.flush();return self
        except BaseException:self.__exit__();raise
    def call(self,method,params):
        self.next+=1;id=self.next;self.p.stdin.write(json.dumps({'jsonrpc':'2.0','id':id,'method':method,'params':params})+'\n');self.p.stdin.flush();end=time.monotonic()+20
        while time.monotonic()<end:
            try:r=self.q.get(timeout=max(.1,end-time.monotonic()))
            except queue.Empty:break
            if r.get('id')==id:
                if 'error' in r:raise ValueError('PostgreSQL MCP rejected the operation; inspect the configured read-only profile')
                return r['result']
        raise ValueError('PostgreSQL MCP timed out; its owned subprocess will be closed')
    def tool(self,name,args):
        r=self.call('tools/call',{'name':'postgres_mcp_'+name,'arguments':args})
        if r.get('isError'):raise ValueError('PostgreSQL MCP tool '+name+' failed; credentials and data were not exposed')
        if r.get('structuredContent') is not None:return r['structuredContent']
        for part in r.get('content',[]):
            if part.get('type')=='text':
                try:return json.loads(part['text'])
                except ValueError:pass
        return r
    def __exit__(self,*args):
        self.p.stdin.close()
        try:self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:self.p.terminate();self.p.wait(timeout=5)
        self.p.stdout.close();self.reader.join(timeout=1)

def check(control):
    if control.config()['database']!='codex_engineering':raise Blocked('The existing MCP profile is registered for codex_engineering; no duplicate profile was created')
    query='SELECT current_database() AS database, current_user AS identity, count(*) AS observations FROM '+control.relation('observations')
    independent=control.fetch(query)
    with Client() as m:
        profiles=m.tool('list_connection_profiles',{});connected=m.tool('connect',{'profileId':'codex-engineering-ro'});cid=connected.get('connectionId')
        if not cid:raise ValueError('MCP connect did not return a connectionId; the profile ID must not be substituted')
        result=m.tool('query',{'connectionId':cid,'query':query,'validationQueries':[],'maxResultRows':5})
        m.tool('disconnect',{'connectionId':cid})
    # Require genuine row equality. Do not mark a registration or successful process launch as acceptance.
    def find_rows(v):
        if isinstance(v,list):
            if v and isinstance(v[0],dict) and 'observations' in v[0]:return v
            for item in v:
                found=find_rows(item)
                if found is not None:return found
        if isinstance(v,dict):
            for item in v.values():
                found=find_rows(item)
                if found is not None:return found
        return None
    rows=find_rows(result)
    if rows is None and isinstance(result,dict) and not result.get('errorMessage') and isinstance(result.get('results'),str):
        rows=list(csv.DictReader(io.StringIO(result['results'])))
        for row in rows:
            if str(row.get('observations','')).isdecimal():row['observations']=int(row['observations'])
    if rows!=independent:return {'status':'FAIL','at':now(),'reason':'MCP row structure or values differ from the independent driver query','mcp_result':result,'driver_rows':independent}
    return {'status':'LIVE_PASS','at':now(),'connection_id':cid,'rows':rows,'driver_rows':independent,'identity':'codex_mcp_ro','comparison':'Independent driver query equals actual MCP rows','server':str(EXE),'shutdown':'Owned MCP subprocess closed'}
