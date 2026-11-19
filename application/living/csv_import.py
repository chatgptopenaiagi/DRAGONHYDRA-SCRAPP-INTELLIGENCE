"""Inspectable CSV drafts, explicit mappings and atomic, resumable imports."""
import base64,csv,hashlib,io,os,re,time,uuid
from datetime import datetime,date
from pathlib import Path
from .contracts import now,fingerprint,file_hash,Cancelled
from .normalization import normalize,number,timestamp

MAX_BYTES=20*1024*1024;MAX_ROWS=100000
FIELDS=['value','key','text','date','observed_at','competition','season','home_team','away_team','home_goals','away_goals','score','result','bookmaker','home_odds','draw_odds','away_odds']
ALIASES={'value':['value','measurement','amount'],'key':['key','series'],'text':['text','description'],'date':['Date','date'],'observed_at':['observed_at','Observation timestamp'],'competition':['Div','Competition'],'season':['Season','season'],'home_team':['HomeTeam','Team 1','Home team'],'away_team':['AwayTeam','Team 2','Away team'],'home_goals':['FTHG','Home goals'],'away_goals':['FTAG','Away goals'],'score':['FT','Score'],'result':['FTR','Full-time result'],'bookmaker':['Bookmaker'],'home_odds':['B365H','Home odds'],'draw_odds':['B365D','Draw odds'],'away_odds':['B365A','Away odds']}

def read_csv(raw,options=None):
    options=options or {}
    if not raw:raise ValueError('The file is empty')
    if len(raw)>MAX_BYTES:raise ValueError('File exceeds the supported 20 MiB limit; split it into complete CSV files before importing')
    encoding=options.get('encoding','auto');warnings=[]
    if encoding=='auto':
        encoding='utf-8-sig'
        try:text=raw.decode(encoding)
        except UnicodeDecodeError:
            encoding='cp1252'
            try:text=raw.decode(encoding)
            except UnicodeDecodeError:raise ValueError('Encoding could not be detected safely. Select the file encoding explicitly') from None
            warnings.append('Windows-1252 is a candidate encoding, not a certainty. Inspect accented characters or select the original encoding.')
    else:
        if encoding not in ('utf-8-sig','cp1252','cp1250','latin-1','utf-16'):raise ValueError('Unsupported encoding')
        try:text=raw.decode(encoding)
        except UnicodeDecodeError:raise ValueError('The selected encoding cannot decode this file') from None
    if '\x00' in text:raise ValueError('NUL characters detected. Select UTF-16 if appropriate; binary files are not CSV')
    delimiter=options.get('delimiter','auto')
    if delimiter=='auto':
        try:delimiter=csv.Sniffer().sniff(text[:65536],delimiters=',;\t').delimiter
        except csv.Error:delimiter=',';warnings.append('Delimiter could not be detected confidently; inspect the preview.')
    if delimiter not in (',',';','\t'):raise ValueError('Select comma, semicolon or tab delimiter')
    reader=csv.reader(io.StringIO(text,newline=''),delimiter=delimiter,strict=True);rows=[];errors=[]
    try:
        headers=next(reader)
        if not headers or any(not h.strip() for h in headers) or len(set(headers))!=len(headers) or len(headers)>500:raise ValueError('Headers must be nonempty, unique, and at most 500 columns')
        while True:
            line=reader.line_num+1
            try:values=next(reader)
            except StopIteration:break
            if not values:continue
            if len(rows)>=MAX_ROWS:raise ValueError('File exceeds 100000 records; no records have been truncated or imported')
            if len(values)!=len(headers):errors.append({'row':line,'field':'columns','reason':f'Expected {len(headers)} cells, received {len(values)}'})
            rows.append((line,dict(zip(headers,values))))
    except csv.Error:raise ValueError(f'Malformed CSV near physical line {reader.line_num}; check quotes and delimiter') from None
    if not rows:raise ValueError('The CSV has a header but no records')
    return dict(headers=headers,rows=rows,encoding=encoding,delimiter=delimiter,warnings=warnings,errors=errors)

def suggestions(headers):
    mapping={k:next((a for a in aliases if a in headers),'') for k,aliases in ALIASES.items()}
    profile='sports' if mapping['home_team'] and mapping['away_team'] else 'text' if mapping['text'] and not mapping['value'] else 'measurement'
    return dict(profile=profile,mapping=mapping,date_format='champs' if 'Team 1' in headers else 'dmy' if 'FTHG' in headers else 'iso',decimal='.',thousands='',bookmaker='Bet365' if 'B365H' in headers else '',competition='',season='',series='measurement',unit='unknown')

def calendar(value,style):
    if not value:return None
    try:
        if style=='champs':
            m=re.fullmatch(r'\([A-Za-z]{3}\) (\d{1,2}) ([A-Za-z]{3}) (\d{4}) \(W\d{1,2}\)',value)
            if not m:raise ValueError()
            months='Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split();return date(int(m[3]),months.index(m[2])+1,int(m[1])).isoformat()
        if style=='iso':return date.fromisoformat(value).isoformat()
        return datetime.strptime(value,{'dmy':'%d/%m/%Y','dmy2':'%d/%m/%y','mdy':'%m/%d/%Y'}[style]).date().isoformat()
    except (ValueError,KeyError):raise ValueError('Date does not match the selected date convention') from None

def decimal(value,options):
    if value in ('',None):return None
    value=str(value).strip();point=options.get('decimal','.');group=options.get('thousands','')
    if point not in ('.',',') or group not in ('',',','.',' ') or point==group:raise ValueError('Select distinct decimal and grouping separators')
    sign='[-+]?';sep=re.escape(point)
    integer=r'\d+' if not group else r'(?:\d+|\d{1,3}(?:'+re.escape(group)+r'\d{3})+)'
    if not re.fullmatch(sign+integer+'(?:'+sep+r'\d+)?(?:[eE][-+]?\d+)?',value):raise ValueError('Number does not match the selected decimal/grouping convention')
    return number(value.replace(group,'') .replace(point,'.') if group else value.replace(point,'.'))

def mapped_rows(parsed,options,source,cancel=lambda:False,progress=lambda n:None):
    mapping=options.get('mapping',{});profile=options.get('profile');errors=list(parsed['errors']);normalized=[];at=now()
    if profile not in ('sports','measurement','text'):raise ValueError('Select a supported schema profile')
    if set(mapping)-set(FIELDS) or any(v and v not in parsed['headers'] for v in mapping.values()):raise ValueError('Mapping references an unknown field or CSV column')
    required=['home_team','away_team'] if profile=='sports' else ['text'] if profile=='text' else ['value']
    if any(not mapping.get(k) for k in required):raise ValueError('Choose the columns containing '+', '.join(required))
    for index,(line,raw) in enumerate(parsed['rows']):
        if cancel():raise Cancelled('Import cancelled during validation; no rows committed')
        field='mapping'
        def get(k):return (raw.get(mapping.get(k,'')) or '').strip()
        try:
            field='date';day=calendar(get('date'),options.get('date_format','iso'))
            field='observed_at';observed=timestamp(get('observed_at'))
            meta={'date':day,'date_precision':'day' if day else 'unknown','original_csv_row':raw,'physical_line':line,'mapping_version':'dh.csv/1'}
            items=[]
            if profile=='sports':
                field='teams';home,away=get('home_team'),get('away_team')
                if not home or not away:raise ValueError('Home and away teams are required')
                competition=get('competition') or options.get('competition','');season=get('season') or options.get('season','')
                meta.update(home_team=home,away_team=away,competition=competition,season=season,provider_match_id=None,identity_status='UNRECONCILED')
                identity=fingerprint([competition,season,home,away,day,raw.get('Round'),raw.get('Group')]);hg=ag=None
                field='score'
                if get('score'):
                    score=get('score')
                    if options.get('date_format')=='champs' and score.endswith(' (*)'):
                        score=score[:-4];meta['score_note']='FT is regulation-time score; extra time and penalties remain in original_csv_row'
                    match=re.fullmatch(r'(\d+)\s*[-–:]\s*(\d+)',score)
                    if not match:raise ValueError('Score must contain two nonnegative integers separated by - or :')
                    hg,ag=int(match[1]),int(match[2])
                elif get('home_goals') or get('away_goals'):
                    if not re.fullmatch(r'\d+',get('home_goals')) or not re.fullmatch(r'\d+',get('away_goals')):raise ValueError('Both goal counts must be nonnegative integers')
                    hg,ag=int(get('home_goals')),int(get('away_goals'))
                if hg is not None and (hg>100 or ag>100):raise ValueError('Goal count exceeds supported validation bounds')
                result=('H' if hg>ag else 'A' if hg<ag else 'D') if hg is not None else None
                if get('result') and result and get('result').upper()!=result:raise ValueError('Full-time result conflicts with the supplied score')
                meta.update(home_goals=hg,away_goals=ag,score_period='REGULATION',status='FINAL' if hg is not None else 'UNKNOWN',contract='football.result/1' if hg is not None else 'football.fixture/1')
                items.append(dict(key='football.total_goals' if hg is not None else 'football.fixture',kind='SPORTS_RESULT' if hg is not None else 'FOOTBALL_RECORD',value=hg+ag if hg is not None else None,unit='goals' if hg is not None else 'record',identity=identity,metadata=dict(meta)))
                for outcome,label in [('home','H'),('draw','D'),('away','A')]:
                    field=outcome+'_odds';price=decimal(get(field),options)
                    if price is not None:
                        bookmaker=get('bookmaker') or options.get('bookmaker','')
                        if not bookmaker:raise ValueError('Select or supply the bookmaker identity for price columns')
                        items.append(dict(key='football.odds.'+label,kind='SPORTS_ODDS',value=price,unit='decimal_odds',identity=identity+'|'+bookmaker+'|'+label,metadata=meta|{'contract':'football.odds.quote/1','bookmaker':bookmaker,'outcome':label,'market':'1X2','quote_status':'IMPORTED_HISTORICAL','quote_time':observed}))
            else:
                field='value' if profile=='measurement' else 'text'
                items=[dict(key=get('key') or options.get('series','measurement'),kind='SHORT_TEXT' if profile=='text' else 'NUMBER',value=decimal(get('value'),options) if profile=='measurement' else None,text=get('text') if profile=='text' else None,unit=options.get('unit','unknown'),identity=fingerprint(raw),metadata=meta)]
            for item in items:
                item['observed_at']=observed
                normalized.append(normalize(item,source,source.get('origin','IMPORTED'),at))
            if len(normalized)>MAX_ROWS:raise ValueError('Expanded observations exceed 100000; split the input file')
        except ValueError as e:errors.append({'row':line,'field':field,'reason':str(e)})
        if index%500==0:progress(int((index+1)/len(parsed['rows'])*60)+10)
    return normalized,errors

class CsvWizard:
    def __init__(self,store,data):self.store=store;self.data=Path(data)
    def preview(self,body):
        if body.get('draft_id'):
            draft=self.get(body['draft_id']);raw=Path(draft['path']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=draft['sha256']:raise ValueError('Staged file changed; choose the original file again')
        else:
            raw=base64.b64decode(body.get('content',''),validate=True)
            if len(raw)>MAX_BYTES:raise ValueError('File exceeds 20 MiB; no bytes imported')
            name=Path(body.get('filename','')).name
            if Path(name).suffix.lower() not in ('.csv','.tsv'):raise ValueError('This wizard accepts CSV and TSV; use Local sources for other readers')
            sha=hashlib.sha256(raw).hexdigest();folder=self.data/'originals';folder.mkdir(exist_ok=True);path=folder/(sha+'.csv')
            if not path.exists():
                stage=folder/(uuid.uuid4().hex+'.partial')
                with stage.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
                os.replace(stage,path)
            draft={'id':uuid.uuid4().hex,'path':str(path),'filename':name,'bytes':len(raw),'sha256':sha,'created_at':now()}
        options=body.get('reader',{});parsed=read_csv(raw,options)
        draft.update(state='PREVIEW',reader={'encoding':parsed['encoding'],'delimiter':parsed['delimiter']},headers=parsed['headers'],records=len(parsed['rows']),warnings=parsed['warnings'],errors=parsed['errors'][:200],error_count=len(parsed['errors']),preview=[{'row':i,'cells':r} for i,r in parsed['rows'][:12]],suggested=suggestions(parsed['headers']))
        self.store.state('csv',draft['id'],draft);return {k:v for k,v in draft.items() if k!='path'}
    def get(self,id):
        draft=self.store.state('csv',id)
        if not draft:raise ValueError('Import draft is unavailable; select the file again')
        return draft
    def validate(self,body):
        draft=self.get(body['draft_id']);source=next((s for s in self.store.sources() if s['id']==body.get('source_id')),None)
        if not source or source['adapter']!='upload':raise ValueError('Create a source for this file or select a local upload source')
        if file_hash(Path(draft['path']))!=draft['sha256']:raise ValueError('Staged source content changed')
        # Wizard mappings are canonical, independent of the advanced reader mapping.
        source=dict(source,mapping={});options=body.get('options',{});parsed=read_csv(Path(draft['path']).read_bytes(),draft['reader'])
        rows,errors=mapped_rows(parsed,options,source)
        draft.update(state='INVALID' if errors else 'VALIDATED',options=options,source=source,errors=errors[:200],error_count=len(errors),accepted_observations=0 if errors else len(rows),warnings=parsed['warnings']+(['Unknown observation times remain unknown. Match dates are preserved as dates.'] if any(not r['observed_at'] for r in rows) else []),validation_id=uuid.uuid4().hex)
        self.store.state('csv',draft['id'],draft);return {k:v for k,v in draft.items() if k not in ('path','source')}
    def confirm(self,body):
        with self.store.lock:
            draft=self.get(body['draft_id'])
            if draft['state']!='VALIDATED' or draft['validation_id']!=body.get('validation_id'):raise ValueError('Validate the current file and mapping before confirming import')
            if file_hash(Path(draft['path']))!=draft['sha256']:raise ValueError('Staged source content changed')
            id=self.store.task({'source_id':draft['source']['id'],'source':draft['source'],'operation':'csv','draft':draft,'attempt':0})
            draft.update(state='QUEUED',task_id=id);self.store.state('csv',draft['id'],draft);return {'task_id':id}
    def execute(self,task,cancel):
        d=task['payload']['draft'];id=task['id']
        if file_hash(Path(d['path']))!=d['sha256']:raise ValueError('Staged source content changed; original import was not committed')
        parsed=read_csv(Path(d['path']).read_bytes(),d['reader']);rows,errors=mapped_rows(parsed,d['options'],d['source'],cancel,lambda p:self.store.task_update(id,'RUNNING',p))
        if errors:raise ValueError(f'Atomic import rejected: {len(errors)} invalid rows; first: {errors[:3]}')
        self.store.task_update(id,'RUNNING',80)
        receipt={'id':id,'source_id':d['source']['id'],'method':'csv-wizard','content_hash':d['sha256'],'filename':d['filename'],'reader':d['reader'],'field_mapping':d['options'],'acquired_at':now(),'rows_validated':len(parsed['rows']),'observations_validated':len(rows),'rejected':0,'validation_errors':0,'origin':d['source'].get('origin','IMPORTED')}
        return self.store.ingest(rows,receipt,cancel)
