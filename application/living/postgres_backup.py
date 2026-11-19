"""Consistent pg_dump archives and non-overwriting isolated-schema restore verification."""
import json,os,re,subprocess,uuid
from pathlib import Path
from .contracts import now,file_hash,atomic_json,fingerprint,Blocked
from .postgres_control import ident,TABLES
BIN=Path(r'C:\Program Files\PostgreSQL\18\bin')

def run(control,program,args):
    cfg=control.config();env=os.environ.copy();env.update(PGPASSWORD=control.vault.get('administration',control.binding('administration')),PGCONNECT_TIMEOUT='5',PGCLIENTENCODING='UTF8')
    command=[str(BIN/(program+'.exe'))]+args
    try:r=subprocess.run(command,capture_output=True,env=env,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired:raise ValueError(program+' exceeded its bounded runtime; originals were not replaced') from None
    if r.returncode:
        # Utility diagnostics can include SQL values; retain only a bounded, redacted structural error.
        error=r.stderr.decode('utf-8',errors='replace');error=re.sub(r'(?m)^.*(?:COPY|CONTEXT|DETAIL|STATEMENT).*$','[SQL data detail withheld]',error)
        for secret in control.secrets():error=error.replace(secret,'[REDACTED]')
        raise ValueError(program+' failed: '+error[:600])
    return r.stdout
def connection_args(control):
    c=control.config();return ['--host',c['host'],'--port',str(c['port']),'--username',c['administration_user'],'--dbname',c['database'],'--no-password']
def signature(c,schema):
    rows=c.execute('SELECT id,payload_text FROM '+ident(schema)+'.observations ORDER BY id').fetchall()
    return {'rows':len(rows),'original_payloads_sha256':fingerprint(rows),'odds':c.execute('SELECT count(*) FROM '+ident(schema)+'.odds_quotes').fetchone()[0],'tables':{t:c.execute('SELECT count(*) FROM '+ident(schema)+'.'+ident(t)).fetchone()[0] for t in TABLES}}
def backup(control):
    folder=control.data/'postgresql-backups';folder.mkdir(exist_ok=True);id=uuid.uuid4().hex;path=folder/(id+'.dump');cfg=control.config()
    with control.connect('administration',True) as c:
        control.owned(c);c.rollback();c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY');snapshot=c.execute('SELECT pg_export_snapshot()').fetchone()[0]
        baseline=signature(c,cfg['schema']);run(control,'pg_dump',connection_args(control)+['--format=custom','--no-owner','--no-acl','--schema',cfg['schema'],'--snapshot',snapshot,'--file',str(path)])
    local=control.local.backup(folder/(id+'.control.sqlite3'))
    result={'id':id,'name':path.name,'status':'PASS','at':now(),'sha256':file_hash(path),'bytes':path.stat().st_size,'schema':cfg['schema'],'database':cfg['database'],'signature':baseline,'local_control_backup':local,'credentials_included':False,'restore_verified':False,'method':'pg_dump custom archive with exported repeatable-read snapshot'}
    atomic_json(folder/(id+'.json'),result);control.local.state('postgres-backup',id,result);return result

def remap_script(text,source,target):
    """Only our pg_dump schema identifier tokens change; COPY payload bytes remain identical."""
    out=[];copy=False
    # SQL lexer protects literals/comments/quoted strings. Our fixed trigger body contains no schema references.
    token=re.compile(r"(--[^\n]*|/\*[\s\S]*?\*/|'(?:''|[^'])*'|\$\$[\s\S]*?\$\$|\"(?:\"\"|[^\"])*\"|[A-Za-z_][A-Za-z0-9_]*)")
    def replace(m):
        v=m.group();return target if v==source else ident(target) if v==ident(source) else v
    chunk=[]
    def flush():
        if chunk:out.append(token.sub(replace,''.join(chunk)));chunk.clear()
    for line in text.splitlines(keepends=True):
        if copy:
            out.append(line)
            if line.rstrip('\r\n')=='\\.':copy=False
        elif line.startswith('COPY '):
            flush()
            if not re.match(r'COPY (?:'+re.escape(source)+'|'+re.escape(ident(source))+r')\.',line):raise ValueError('Backup contains a COPY target outside its owned schema')
            out.append(token.sub(replace,line));copy=True
        else:chunk.append(line)
    flush()
    if copy:raise ValueError('Incomplete PostgreSQL COPY data in backup')
    return ''.join(out)
def restore(control,id):
    if not isinstance(id,str) or not re.fullmatch('[0-9a-f]{32}',id):raise ValueError('Choose a backup created by this application')
    folder=control.data/'postgresql-backups';manifest=control.local.state('postgres-backup',id);path=folder/(id+'.dump')
    if not manifest or file_hash(path)!=manifest['sha256']:raise ValueError('Backup identity or checksum failed; nothing was restored')
    if manifest['database']!=control.config()['database']:raise Blocked('Select the original engineering database before isolated restore')
    target='dragonhydra_restore_'+uuid.uuid4().hex[:12]
    with control.connect('administration',True) as c:
        if c.execute('SELECT 1 FROM pg_namespace WHERE nspname=%s',(target,)).fetchone():raise ValueError('Restore namespace already exists; overwrite is prohibited')
    sql=run(control,'pg_restore',['--no-owner','--no-acl','--file','-',str(path)]).decode('utf-8');script=folder/(id+'.'+target+'.sql');script.write_text(remap_script(sql,manifest['schema'],target),encoding='utf-8',newline='')
    run(control,'psql',connection_args(control)+['--no-psqlrc','--set','ON_ERROR_STOP=1','--single-transaction','--file',str(script)])
    with control.connect('administration',True) as c:actual=signature(c,target)
    result={'status':'PASS' if actual==manifest['signature'] else 'FAIL','at':now(),'backup_id':id,'restored_schema':target,'signature':actual,'matches_original':actual==manifest['signature'],'isolation':'SEPARATE_SCHEMA','separate_database_restore':'BLOCKED: existing account lacks CREATEDB; original schema was not overwritten'}
    manifest['restore_verified']=result['status']=='PASS';manifest['restore']=result;control.local.state('postgres-backup',id,manifest);atomic_json(folder/(id+'.restore.json'),result);return result
