"""Public-only HTTP transport, bounded retries and field-aware extraction."""
import http.client,ipaddress,json,socket,ssl,time,threading,re
from urllib.parse import urlsplit,urljoin,parse_qs
from urllib.robotparser import RobotFileParser
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from .model import decimal_value

class AcquisitionError(ValueError):pass
class SchemaMismatch(AcquisitionError):pass
class HTTPFailure(AcquisitionError):
    def __init__(self,status,retry_after=None):self.status=status;self.retry_after=retry_after;super().__init__('Provider HTTP '+str(status))

def resolve_public(url,resolver=socket.getaddrinfo):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.fragment:raise AcquisitionError('URL scheme/authority is not permitted')
    if any(k.casefold() in {'api_key','apikey','password','token','access_token','secret'} for k in parse_qs(p.query)):raise AcquisitionError('Credentials must not be placed in recorded URLs')
    try:port=p.port or (443 if p.scheme=='https' else 80)
    except ValueError:raise AcquisitionError('Invalid port') from None
    if port not in (80,443):raise AcquisitionError('External acquisition ports are restricted to HTTP/HTTPS')
    host=p.hostname.encode('idna').decode('ascii')
    addresses=resolver(host,port,type=socket.SOCK_STREAM)
    if not addresses:raise AcquisitionError('No provider address')
    for item in addresses:
        ip=ipaddress.ip_address(item[4][0].split('%')[0])
        if not ip.is_global or (getattr(ip,'ipv4_mapped',None) and not ip.ipv4_mapped.is_global):raise AcquisitionError('Local/private/reserved provider address rejected')
    return p,host,port,addresses[0]

def fetch_public(url,*,max_bytes=2_000_000,timeout=8,allowed_hosts=(),resolver=socket.getaddrinfo,headers=None):
    deadline=time.monotonic()+20
    request_headers={'User-Agent':'DRAGONHYDRA-Research/0.1','Accept-Encoding':'identity','Connection':'close'}
    for key,value in (headers or {}).items():
        if key not in ('Authorization','X-API-Key') or not isinstance(value,str) or len(value)>2048 or any(ord(c)<32 or ord(c)>126 for c in value):raise AcquisitionError('Invalid provider authentication header')
        request_headers[key]=value
    credential_host=urlsplit(url).hostname
    for redirect in range(4):
        p,host,port,address=resolve_public(url,resolver)
        if headers and p.hostname!=credential_host:raise AcquisitionError('Authenticated cross-host redirect refused')
        if allowed_hosts and host not in allowed_hosts:raise AcquisitionError('Provider host outside configured allowlist')
        family,socktype,proto,_,endpoint=address
        raw=socket.socket(family,socktype,proto);raw.settimeout(timeout)
        conn=http.client.HTTPConnection(host,port,timeout=timeout)
        try:
            # Pin the already validated address; no second DNS lookup/rebinding window.
            raw.connect(endpoint)
            conn.sock=ssl.create_default_context().wrap_socket(raw,server_hostname=host) if p.scheme=='https' else raw
            transport_socket=conn.sock
            conn.request('GET',(p.path or '/')+('?' +p.query if p.query else ''),headers=request_headers)
            resp=conn.getresponse();headers=dict((k.lower(),v) for k,v in resp.getheaders())
            if resp.status in (301,302,303,307,308):
                location=headers.get('location')
                if not location:raise AcquisitionError('Redirect has no location')
                url=urljoin(url,location);continue
            if resp.status!=200:raise HTTPFailure(resp.status,headers.get('retry-after'))
            if headers.get('content-encoding','identity').lower()!='identity':raise AcquisitionError('Compressed provider response is not accepted')
            if headers.get('content-length') and int(headers['content-length'])>max_bytes:raise AcquisitionError('Provider payload too large')
            chunks=[];size=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise AcquisitionError('Provider response exceeded total time budget')
                transport_socket.settimeout(min(timeout,remaining))
                block=resp.read1(min(65536,max_bytes+1-size))
                if not block:break
                chunks.append(block);size+=len(block)
                if size>max_bytes:raise AcquisitionError('Provider payload too large')
            body=b''.join(chunks)
            return body,headers,url
        finally:conn.close();raw.close()
    raise AcquisitionError('Too many redirects')

def retry_delay(attempt,header=None,now=None):
    delay=min(30,2**attempt)
    if header:
        try:
            wait=float(header) if re.fullmatch(r'\d+(?:\.\d+)?',header) else (parsedate_to_datetime(header)-(now or datetime.now(timezone.utc))).total_seconds()
            delay=max(delay,max(0,wait))
        except (ValueError,TypeError,OverflowError):pass
    if delay>60:raise AcquisitionError('Provider requested a longer pause; defer to next scheduled run')
    return delay

class SourceClient:
    def __init__(self,*,transport=fetch_public,clock=time.monotonic,sleep=time.sleep,interval=60):
        self.transport=transport;self.clock=clock;self.sleep=sleep;self.interval=max(10,interval);self.next_due=0;self.failures=0;self.open_until=0;self.lock=threading.Lock()
    def get(self,url,*,html=False,allowed_hosts=(),headers=None):
        with self.lock:
            at=self.clock()
            if at<self.open_until:raise AcquisitionError('Source circuit open')
            if at<self.next_due:raise AcquisitionError('Source request budget exhausted')
            self.next_due=at+self.interval
            try:
                if html:
                    p=urlsplit(url);robots=p.scheme+'://'+p.netloc+'/robots.txt'
                    try:body,_,_=self.transport(robots,allowed_hosts=allowed_hosts,headers=headers)
                    except HTTPFailure as e:
                        if e.status not in (404,410):raise
                        body=b''
                    parser=RobotFileParser();parser.parse(body.decode('utf-8',errors='replace').splitlines())
                    if not parser.can_fetch('DRAGONHYDRA-Research',url):raise AcquisitionError('robots.txt disallows this path')
                    delay=parser.crawl_delay('DRAGONHYDRA-Research') or parser.crawl_delay('*') or 0
                    if delay>60:raise AcquisitionError('Crawl delay exceeds configured request budget')
                    if delay:self.sleep(delay)
                for attempt in range(3):
                    try:result=self.transport(url,allowed_hosts=allowed_hosts,headers=headers);break
                    except (OSError,HTTPFailure) as e:
                        if attempt==2 or isinstance(e,HTTPFailure) and e.status not in (429,500,502,503,504):raise
                        self.sleep(retry_delay(attempt,getattr(e,'retry_after',None)))
                self.failures=0;return result
            except Exception:
                self.failures+=1
                if self.failures>=3:self.open_until=self.clock()+300
                raise

def extract_table(html,*,selector='table[data-domain="measurements"]',expected_units=None):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser');tables=soup.select(selector)
    if len(tables)!=1:raise SchemaMismatch('Expected exactly one labelled measurements table')
    table=tables[0];headers=[x.get_text(' ',strip=True) for x in table.select('thead th')]
    if headers!=['Metric','Value','Unit']:raise SchemaMismatch('Table headers changed')
    result=[];seen=set()
    for tr in table.select('tbody tr'):
        cells=tr.find_all('td',recursive=False)
        if len(cells)!=3:raise SchemaMismatch('Measurement row shape changed')
        key,value,unit=[c.get_text(' ',strip=True) for c in cells]
        if key in seen or not expected_units or expected_units.get(key)!=unit:raise SchemaMismatch('Unexpected/duplicate metric or unit')
        seen.add(key);decimal_value(value);result.append(dict(key=key,value=value,unit=unit))
    if seen!=set(expected_units):raise SchemaMismatch('Expected metric missing')
    return result

def extract_field(html,rule):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser');elements=soup.select(rule['selector'])
    if len(elements)!=1:raise SchemaMismatch('Field absent or ambiguous')
    el=elements[0]
    if el.get('data-field')!=rule['field'] or el.get('data-unit')!=rule['unit']:raise SchemaMismatch('Field identity/unit not proven')
    value=decimal_value(el.get_text(' ',strip=True),rule.get('decimal_mark','.'))
    if not DecimalRange(rule,value):raise SchemaMismatch('Field outside declared range')
    return str(value)

def DecimalRange(rule,value):
    return decimal_value(rule['min'])<=value<=decimal_value(rule['max'])

def validate_rule_candidate(candidate,examples):
    if not examples:raise SchemaMismatch('Saved validation examples required')
    for example in examples:
        if extract_field(example['html'],candidate)!=str(decimal_value(example['expected'])):raise SchemaMismatch('Candidate changes field identity/value')
    return {'status':'validated_candidate','rule':candidate,'examples':len(examples),'activation':'Requires recorded prior version and atomic configuration update'}
