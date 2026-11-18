"""DH-ACQUISITION: bounded inert parsers; one durable worker owns each import."""
import base64,csv,io,json,re,sqlite3,threading,time,zipfile
from contextlib import closing
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from .contracts import now,fingerprint,file_hash,atomic_json,Cancelled,Blocked
from .normalization import normalize

MAX_BYTES=20*1024*1024; MAX_ROWS=100000
def xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('DTD and entities are forbidden')
    return ET.fromstring(raw)
class Table(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None;self.tables=0
    def handle_starttag(self,tag,attrs):
        if tag=='table':self.tables+=1
        if tag=='tr':self.row=[]
        if tag in ('td','th'):self.cell=''
    def handle_data(self,data):
        if self.cell is not None:self.cell+=data
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            if self.row is not None:self.row.append(self.cell.strip())
            self.cell=None
        if tag=='tr' and self.row:self.rows.append(self.row);self.row=None
def parse(raw,filename,options=None):
    options=options or {}
    if len(raw)>MAX_BYTES:raise ValueError('File exceeds 20 MiB')
    ext=Path(filename).suffix.lower()
    if ext in ('.csv','.tsv'):rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='\t' if ext=='.tsv' else ','))
    elif ext=='.jsonl':rows=[json.loads(line,parse_float=str) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    elif ext=='.json':
        rows=json.loads(raw.decode('utf-8-sig'),parse_float=str)
        if isinstance(rows,dict):rows=rows.get('rows',rows.get('records',rows.get('observations')))
    elif ext=='.xml':rows=[{e.tag.split('}')[-1]:e.text for e in record} for record in xml(raw)]
    elif ext in ('.html','.htm'):
        table=Table();table.feed(raw.decode('utf-8-sig'))
        if table.tables!=1 or len(table.rows)<2:raise ValueError('Supply exactly one table with a header and data rows')
        if any(len(r)!=len(table.rows[0]) for r in table.rows):raise ValueError('Inconsistent HTML table columns')
        rows=[dict(zip(table.rows[0],r)) for r in table.rows[1:]]
    elif ext=='.xlsx':
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if sum(i.file_size for i in z.infolist())>64*1024*1024:raise ValueError('XLSX expansion exceeds 64 MiB')
            ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            strings=[''.join(t.text or '' for t in n.findall('.//m:t',ns)) for n in xml(z.read('xl/sharedStrings.xml')).findall('m:si',ns)] if 'xl/sharedStrings.xml' in z.namelist() else []
            sheet=options.get('sheet','sheet1')
            if not re.fullmatch(r'sheet\d+',sheet):raise ValueError('Sheet must be sheet1, sheet2, ...')
            values=[]
            for row in xml(z.read('xl/worksheets/'+sheet+'.xml')).findall('.//m:row',ns):
                cells={}
                for c in row.findall('m:c',ns):
                    letters=re.match('[A-Z]+',c.get('r','A1'))[0];index=0
                    for char in letters:index=index*26+ord(char)-64
                    if index>500:raise ValueError('Worksheet exceeds 500 columns')
                    v=c.find('m:v',ns);val=v.text if v is not None else ''.join(t.text or '' for t in c.findall('.//m:t',ns))
                    cells[index-1]=strings[int(val)] if c.get('t')=='s' else val
                values.append([cells.get(i,'') for i in range(max(cells,default=-1)+1)])
            rows=[dict(zip(values[0],r)) for r in values[1:]] if values else []
    elif ext=='.pdf':
        from pypdf import PdfReader
        reader=PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages)>200:raise ValueError('Encrypted or over-200-page PDF unsupported')
        rows=[{'key':'pdf-page','kind':'SHORT_TEXT','text':p.extract_text(),'metadata':{'page':i+1,'extraction':'pypdf text only; no OCR'}} for i,p in enumerate(reader.pages) if p.extract_text().strip()]
        if not rows:raise ValueError('No extractable text; image-only PDF requires unsupported OCR')
    else:raise ValueError('Unsupported file format')
    if not isinstance(rows,list) or not rows or len(rows)>MAX_ROWS or not all(isinstance(r,dict) for r in rows):raise ValueError('Expected 1..100000 structured rows')
    return rows
def validate_source(value):
    allowed={'id','name','adapter','location','enabled','interval','mapping','kind','unit','origin','options','approved'}
    if set(value)-allowed:raise ValueError('Unknown source field; secrets are not accepted in source configuration')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}',str(value.get('id',''))):raise ValueError('Source ID must contain letters, digits, _ or -')
    if value.get('adapter') not in ('upload','file','http','sqlite','football','legacy'):raise ValueError('Unknown source adapter')
    v=dict(value);v.setdefault('name',v['id']);v.setdefault('enabled',False);v.setdefault('interval',900);v.setdefault('mapping',{});v.setdefault('origin','IMPORTED')
    if type(v['enabled']) is not bool or not 60<=int(v['interval'])<=86400:raise ValueError('Invalid enabled flag or interval 60..86400 seconds')
    if v['origin'] not in ('IMPORTED','SYNTHETIC'):raise ValueError('Configured imports cannot assert verified or measured provenance')
    if not isinstance(v['mapping'],dict) or not all(isinstance(k,str) and isinstance(x,str) for k,x in v['mapping'].items()):raise ValueError('Invalid field mapping')
    if v['adapter']=='http':
        p=urlsplit(v.get('location',''))
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment:raise ValueError('Explicit HTTP(S) source required')
        if re.search(r'(?i)(token|key|password|secret|signature)=',p.query):raise ValueError('Credentials must not appear in recorded source URLs')
        if not v.get('approved'):raise ValueError('Confirm permission to collect from this endpoint')
    return v
def sqlite_rows(path,table):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}',table):raise ValueError('Invalid table name')
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():raise ValueError('Selected base table is missing')
        rows=[dict(r) for r in c.execute('SELECT * FROM "'+table+'" LIMIT 100001')]
    if len(rows)>MAX_ROWS:raise ValueError('Table exceeds 100000 rows')
    return rows
class Acquisition:
    def __init__(self,store,data_dir,mode='offline'):
        self.store=store;self.data=Path(data_dir);self.mode=mode;self.stop=threading.Event();self.cancelled=set();self.thread=None;self.due={}
    def submit(self,source_id,upload=None,filename=None):
        source=next((s for s in self.store.sources() if s['id']==source_id),None)
        if source is None:raise ValueError('Configure a source before collection')
        payload={'source_id':source_id,'source':source,'attempt':0}
        if upload is not None:
            raw=base64.b64decode(upload,validate=True)
            if len(raw)>MAX_BYTES:raise ValueError('Upload exceeds 20 MiB')
            import hashlib
            sha=hashlib.sha256(raw).hexdigest();suffix=Path(filename or '').suffix.lower()
            folder=self.data/'originals';folder.mkdir(exist_ok=True);path=folder/(sha+suffix)
            if not path.exists():
                with path.open('xb') as f:f.write(raw);f.flush();__import__('os').fsync(f.fileno())
            payload.update(staged_file=str(path),filename=Path(filename).name,content_hash=sha)
        return self.store.task(payload)
    def resume(self,id):
        task=next((t for t in self.store.tasks() if t['id']==id),None)
        if not task or task['state'] not in ('INTERRUPTED','FAILED','CANCELLED','BLOCKED'):raise ValueError('Task is not resumable')
        if any(t['id']!=id and t['state'] in ('QUEUED','RUNNING') and t['payload']['source_id']==task['payload']['source_id'] for t in self.store.tasks()):raise ValueError('Source already active')
        self.cancelled.discard(id);self.store.task_update(id,'QUEUED')
    def execute(self,task):
        id=task['id'];p=task['payload'];source=p['source'];adapter=source['adapter'];origin=source.get('origin','IMPORTED')
        prior=self.store.receipt(id)
        if prior:self.store.task_update(id,'COMPLETE',100,prior);return
        self.store.task_update(id,'RUNNING',1)
        cancelled=lambda:id in self.cancelled or self.stop.is_set()
        try:
            if cancelled():raise Cancelled('Task cancelled')
            method=adapter;version=None
            if adapter in ('football','legacy'):
                from .connectors import football_rows,legacy_rows
                rows,extra=(football_rows if adapter=='football' else legacy_rows)(source['location']);sha=extra['dataset_fingerprint'];version=extra.get('schema')
            elif adapter=='sqlite':
                rows=sqlite_rows(source['location'],source.get('options',{}).get('table','observations'));sha=fingerprint(rows)
            else:
                if adapter=='http':
                    if self.mode!='connected':raise Blocked('Connected mode required; offline mode forbids external collection')
                    from intelligence.acquisition import fetch_public,HTTPFailure
                    for attempt in range(3):
                        try:raw,headers,url=fetch_public(source['location'],max_bytes=MAX_BYTES,allowed_hosts=(urlsplit(source['location']).hostname,));version=headers.get('etag') or headers.get('last-modified');break
                        except (OSError,HTTPFailure) as error:
                            if isinstance(error,HTTPFailure) and error.status not in (429,500,502,503,504):raise
                            if attempt==2 or self.stop.wait(2**attempt):raise
                    origin='COLLECTED';filename=source.get('options',{}).get('filename','response.json')
                else:
                    path=Path(p.get('staged_file') or source.get('location',''))
                    if path.stat().st_size>MAX_BYTES:raise ValueError('File exceeds 20 MiB')
                    raw=path.read_bytes();filename=p.get('filename',path.name)
                import hashlib
                sha=hashlib.sha256(raw).hexdigest()
                if p.get('content_hash') and p['content_hash']!=sha:raise ValueError('Staged source content changed')
                folder=self.data/'originals';folder.mkdir(exist_ok=True);original=folder/(sha+Path(filename).suffix.lower())
                if not original.exists():original.write_bytes(raw)
                rows=parse(raw,filename,source.get('options'))
            self.store.task_update(id,'RUNNING',30)
            at=now();normalized=[];errors=[]
            for i,row in enumerate(rows):
                if cancelled():raise Cancelled('Task cancelled during validation')
                actual_origin='SYNTHETIC' if adapter=='legacy' and row.pop('_legacy_synthetic',False) else origin
                try:normalized.append(normalize(row,source,actual_origin,at))
                except (ValueError,TypeError) as e:errors.append({'row':i+1,'error':str(e)[:200]})
            if errors:raise ValueError(f'Import rejected atomically: {len(errors)} invalid rows; first: {errors[:3]}')
            self.store.task_update(id,'RUNNING',70)
            from collections import Counter
            origins=dict(Counter(row['origin'] for row in normalized))
            receipt={'id':id,'source_id':source['id'],'method':method,'content_hash':sha,'dataset_version':version,'field_mapping':source.get('mapping',{}),'acquired_at':at,'rows_validated':len(rows),'validation_errors':0,'origin':next(iter(origins)) if len(origins)==1 else 'MIXED' if origins else origin,'observation_origins':origins}
            result=self.store.ingest(normalized,receipt,cancelled);self.store.task_update(id,'COMPLETE',100,result);self.store.event('INFO','IMPORT_COMPLETE',f'{source["id"]}: {result["inserted"]} inserted; {result["duplicates"]} duplicates')
        except Exception as e:
            state='CANCELLED' if isinstance(e,Cancelled) else 'BLOCKED' if isinstance(e,Blocked) else 'FAILED'
            message=str(e)[:500] if isinstance(e,(ValueError,Cancelled,Blocked)) else type(e).__name__+'; inspect local source availability'
            self.store.task_update(id,state,0,{'error':message,'error_type':type(e).__name__});self.store.event('ERROR','ACQUISITION_'+state,source['id']+': '+message)
    def start(self):
        def run():
            while not self.stop.wait(.2):
                for s in self.store.sources():
                    if s.get('enabled') and s['adapter']!='upload' and time.monotonic()>=self.due.get(s['id'],0):
                        self.due[s['id']]=time.monotonic()+int(s['interval'])
                        try:self.submit(s['id'])
                        except ValueError:pass
                task=next((t for t in reversed(self.store.tasks()) if t['state']=='QUEUED'),None)
                if task:self.execute(task)
        self.thread=threading.Thread(target=run,name='DH-Acquisition',daemon=True);self.thread.start()
    def close(self):
        self.stop.set()
        if self.thread:self.thread.join(30)
        if self.thread and self.thread.is_alive():raise RuntimeError('Acquisition did not stop within deadline')
