"""Bounded HTTPS transport for explicit integrations; no redirects or credential logging."""
import http.client,ipaddress,json,socket,ssl,time
from urllib.parse import urlsplit,urlencode
from .provider_transport import redact
class NetworkError(ValueError):
    def __init__(self,message,status=None,headers=None,code=None):super().__init__(message);self.status=status;self.headers=headers or {};self.code=code
def request(base,path,method='GET',query=None,body=None,headers=None,timeout=20,limit=1024*1024,mock_origins=(),allow_local=False):
    p=urlsplit(base)
    if p.username or p.password or p.query or p.fragment or p.path not in ('','/'):raise ValueError('Use a base origin without credentials, path or query')
    if not path.startswith('/') or path.startswith('//') or any(x in path for x in ('?','#','\r','\n','..')):raise ValueError('Invalid API path')
    local=base in mock_origins or allow_local and p.scheme=='http' and p.hostname=='127.0.0.1'
    if not local and (p.scheme!='https' or p.port not in (None,443)):raise ValueError('Cloud and public sources require HTTPS')
    if local and (p.scheme!='http' or p.hostname!='127.0.0.1'):raise ValueError('Local test endpoint must be loopback HTTP')
    rawbody=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    if rawbody and len(rawbody)>128*1024:raise ValueError('Request exceeds the 128 KiB sharing limit')
    timeout=max(1,min(int(timeout),45));host=p.hostname;port=p.port or (80 if p.scheme=='http' else 443);addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    if not addresses or not local and any(not ipaddress.ip_address(a[4][0].split('%')[0]).is_global for a in addresses):raise NetworkError('Endpoint did not resolve to a permitted public address')
    family,kind,proto,_,target=addresses[0];sock=socket.socket(family,kind,proto);sock.settimeout(timeout);conn=http.client.HTTPConnection(host,port,timeout=timeout);deadline=time.monotonic()+timeout
    try:
        sock.connect(target);conn.sock=sock if local else ssl.create_default_context().wrap_socket(sock,server_hostname=host);tls=conn.sock
        conn.request(method,path+('?' +urlencode(query) if query else ''),rawbody,{'User-Agent':'DRAGONHYDRA/0.2.0-beta.3','Accept':'application/json, text/html;q=0.8','Accept-Encoding':'identity','Content-Type':'application/json','Connection':'close',**(headers or {})});r=conn.getresponse();safe={k.lower():v[:500] for k,v in r.getheaders() if k.lower() in ('content-type','retry-after','location','etag','last-modified','x-request-id','request-id','x-ratelimit-remaining-requests','x-ratelimit-remaining-tokens')}
        if int(r.getheader('Content-Length','0'))>limit:raise NetworkError('Response exceeds the configured byte limit',r.status)
        buf=bytearray()
        while not r.isclosed():
            left=deadline-time.monotonic()
            if left<=0:raise NetworkError('Request timed out; no automatic inference retry was attempted')
            tls.settimeout(min(timeout,left));chunk=r.read1(min(65536,limit+1-len(buf)))
            if not chunk:break
            buf.extend(chunk)
            if len(buf)>limit:raise NetworkError('Response exceeds the configured byte limit',r.status)
        return r.status,safe,bytes(buf)
    except (OSError,http.client.HTTPException):raise NetworkError('Connection failed or timed out. No automatic paid request retry was attempted.') from None
    finally:conn.close();sock.close()
def json_request(*args,secrets=(),**kwargs):
    status,headers,raw=request(*args,**kwargs)
    if status not in (200,201,202):
        label='Authentication or account access rejected' if status in (401,403) else 'Provider rate limit or quota reached' if status==429 else 'Provider returned an unsuccessful response'
        try:
            error=json.loads(raw).get('error',{});code=error.get('code');kind=error.get('type')
        except (ValueError,AttributeError):code=kind=None
        quota=code in ('insufficient_quota','credit_balance_exhausted','billing_hard_limit_reached','billing_not_active') or kind=='insufficient_quota'
        if quota:label='Provider account has no available API balance or billing allowance. Review your provider billing account; no purchase or automatic retry was attempted'
        raise NetworkError(label+' (HTTP '+str(status)+')',status,redact(headers,secrets),'ACCOUNT_ALLOWANCE_EXHAUSTED' if quota else None)
    try:value=json.loads(raw,parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
    except (ValueError,UnicodeError):raise NetworkError('Provider returned malformed JSON',status) from None
    return redact(value,secrets),redact(headers,secrets),status
