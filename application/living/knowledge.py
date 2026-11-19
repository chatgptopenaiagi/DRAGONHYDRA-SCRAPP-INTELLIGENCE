"""Explicit URL knowledge registry; bounded refresh, local search and source evidence."""
import hashlib,re,time,uuid
from html.parser import HTMLParser
from urllib.parse import urlsplit,urljoin
from .contracts import now,Blocked,fingerprint
from . import net
SEEDS=[
 ('api-sports','API-Football v3','https://api-sports.io/documentation/football/v3','football API fixtures leagues odds'),
 ('api-football-quota','API-Football quota','https://www.api-football.com/news/post/how-to-optimize-api-sports-calls-and-quota-usage','football quota status rate limits'),
 ('openai','OpenAI Responses','https://developers.openai.com/api/reference/responses/overview','AI models responses tools'),
 ('anthropic','Claude Messages','https://platform.claude.com/docs/en/build-with-claude/working-with-messages','AI Claude messages models'),
 ('xai','Grok API','https://docs.x.ai/developers/quickstart','AI Grok Responses models'),
 ('foundry','Microsoft Foundry inference','https://learn.microsoft.com/en-us/rest/api/microsoft-foundry/modelinference/','Microsoft Azure model inference'),
 ('azure-openai','Azure OpenAI Responses','https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses','Microsoft Azure OpenAI deployments'),
 ('copilot-studio','Copilot Studio channels','https://learn.microsoft.com/en-us/microsoft-copilot-studio/guidance/channels','Microsoft Copilot Studio Direct Line agents'),
 ('manus','Manus task API','https://open.manus.im/docs/v2/introduction','AI Manus asynchronous task agent'),
 ('sql-server','SQL Server metadata','https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/catalog-views-transact-sql?view=sql-server-ver16','SQL Server tables schemas columns indexes'),
 ('football-csv','Historical football CSV','https://www.football-data.co.uk/notes.txt','football CSV historical odds provenance schema'),
 ('openligadb','OpenLigaDB documentation','https://api.openligadb.de/swagger/v1/swagger.json','football Bundesliga JSON schema'),
 ('thesportsdb','TheSportsDB documentation','https://www.thesportsdb.com/documentation','football teams API public data')]
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','noscript'):self.skip+=1
    def handle_endtag(self,tag):
        if tag in ('script','style','noscript'):self.skip=max(0,self.skip-1)
    def handle_data(self,text):
        if not self.skip and text.strip():self.parts.append(text.strip())
class Knowledge:
    def __init__(self,store,mode,mock_origins=()):
        self.store=store;self.mode=mode;self.mock_origins=mock_origins
        for id,title,url,tags in SEEDS:
            if not store.state('knowledge',id):store.state('knowledge',id,dict(id=id,title=title,url=url,tags=tags,status='NOT_FETCHED',enabled=False,schedule=False,interval=86400,last_checked=None,content_hash=None,text='',official_seed=True))
    def list(self,search=''):
        tokens=search.lower().split();return [{k:v for k,v in d.items() if k!='text'} for d in self.store.states('knowledge') if all(t in (d['title']+' '+d['tags']+' '+d.get('text','')).lower() for t in tokens)]
    def configure(self,b):
        if set(b)-{'id','title','url','tags','enabled','schedule','interval'}:raise ValueError('Unknown knowledge-source field')
        id=b.get('id') or uuid.uuid4().hex
        if not re.fullmatch('[A-Za-z0-9_-]{1,80}',id):raise ValueError('Invalid source identity')
        d=self.store.state('knowledge',id) or dict(id=id,status='NOT_FETCHED',last_checked=None,content_hash=None,text='',official_seed=False,enabled=False,schedule=False,interval=86400)
        url=b.get('url',d.get('url',''));p=urlsplit(url)
        if p.scheme!='https' or not p.hostname or p.username or p.password or p.fragment or p.port not in (None,443) or re.search(r'(?i)(key|token|secret|password)=',p.query):raise ValueError('Use a public HTTPS documentation URL without credentials')
        d.update(b,id=id,url=url)
        if not isinstance(d.get('title'),str) or not 1<=len(d['title'])<=200:raise ValueError('Source title required')
        if type(d['enabled']) is not bool or type(d['schedule']) is not bool or not 3600<=int(d['interval'])<=604800:raise ValueError('Invalid source schedule')
        d.setdefault('tags','');self.store.state('knowledge',id,d);return {k:v for k,v in d.items() if k!='text'}
    def refresh(self,id):
        d=self.store.state('knowledge',id)
        if not d:raise ValueError('Unknown knowledge source')
        if self.mode()!='connected':raise Blocked('Offline mode: saved knowledge remains searchable; refreshing public URLs is disabled')
        if not d['enabled']:raise Blocked('Enable this explicitly selected knowledge source before refreshing')
        try:
            url=d['url'];p=urlsplit(url);base=p.scheme+'://'+p.netloc;path=p.path or '/'
            from urllib.parse import parse_qsl
            status,h,raw=net.request(base,path,query=dict(parse_qsl(p.query)),limit=1024*1024,timeout=20)
            # Never follow arbitrary redirects. Report their destination for deliberate review.
            if 300<=status<400:raise ValueError('Source redirected. Review and configure its current official URL before retrying')
            if status!=200:raise ValueError('Documentation source returned HTTP '+str(status))
            text=raw.decode('utf-8-sig',errors='replace');mime=h.get('content-type','')
            if 'html' in mime:
                parser=Text();parser.feed(text);text='\n'.join(parser.parts)
            if len(text)>100000:text=text[:100000];truncated=True
            else:truncated=False
            d.update(status='VERIFIED_RETRIEVAL' if text.strip() else 'EMPTY_DYNAMIC_CONTENT',last_checked=now(),content_hash=hashlib.sha256(raw).hexdigest(),text=text,bytes=len(raw),text_truncated=truncated,http_status=status,error=None)
        except Exception as e:d.update(status='FAILED',last_checked=now(),error=str(e) if isinstance(e,(ValueError,net.NetworkError)) else 'Documentation refresh failed');self.store.state('knowledge',id,d);raise
        self.store.state('knowledge',id,d);return {k:v for k,v in d.items() if k!='text'}
    def query(self,search='',ids=None,limit=5):
        limit=max(1,min(int(limit),5));matches=self.list(search);allowed=set(ids) if ids is not None else None;result=[]
        for m in matches:
            if allowed is not None and m['id'] not in allowed:continue
            d=self.store.state('knowledge',m['id'])
            if not d.get('content_hash'):continue
            result.append({**m,'excerpt':d['text'][:3000],'classification':'DOCUMENTATION_EVIDENCE_NOT_FOOTBALL_OBSERVATION','excerpt_truncated':len(d['text'])>3000})
            if len(result)==limit:break
        return result
    def schedule(self):
        if self.mode()!='connected':return
        for d in self.store.states('knowledge'):
            if d['enabled'] and d['schedule'] and time.time()>=d.get('next_due',0):
                d['next_due']=time.time()+int(d['interval']);self.store.state('knowledge',d['id'],d)
                try:self.refresh(d['id'])
                except Exception:pass
                break
