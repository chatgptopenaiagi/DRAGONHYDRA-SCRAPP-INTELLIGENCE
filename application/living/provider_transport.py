"""GET-only HTTPS transport: pinned public DNS, no redirects, bounded bytes/time."""
import http.client,ipaddress,json,socket,ssl,time
from urllib.parse import urlsplit,urlencode,quote
from .contracts import Cancelled
from .football_providers.base import ProviderError

MAX_BYTES=5*1024*1024
def redact(value,secrets):
    variants=set()
    for s in secrets:
        if s:variants.update((s,quote(s,safe='')))
    if isinstance(value,dict):return {redact(k,secrets):redact(v,secrets) for k,v in value.items()}
    if isinstance(value,list):return [redact(v,secrets) for v in value]
    if isinstance(value,str):
        for s in sorted(variants,key=len,reverse=True):value=value.replace(s,'[REDACTED]')
    return value

def get(base,path,params,headers,cancel=lambda:False,mock_origins=(),timeout=8):
    p=urlsplit(base)
    if p.username or p.password or p.query or p.fragment or p.path not in ('','/'):raise ProviderError('Invalid provider base URL')
    if not path.startswith('/') or path.startswith('//') or any(x in path for x in ('?','#','\r','\n','..')):raise ProviderError('Invalid provider path')
    mock=base in mock_origins
    if mock:
        if p.scheme!='http' or p.hostname!='127.0.0.1':raise ProviderError('Mock origins must be exact loopback HTTP endpoints')
    elif p.scheme!='https' or p.port not in (None,443):raise ProviderError('Provider connections require HTTPS')
    if cancel():raise Cancelled('Online request cancelled')
    host=p.hostname;port=p.port or 443;addresses=socket.getaddrinfo(host,port,type=socket.SOCK_STREAM)
    if not addresses:raise ProviderError('Provider address is unavailable')
    if not mock and any(not ipaddress.ip_address(a[4][0].split('%')[0]).is_global for a in addresses):raise ProviderError('Provider resolved to a private or reserved address; request rejected')
    family,kind,proto,_,endpoint=addresses[0];raw=socket.socket(family,kind,proto);raw.settimeout(timeout);conn=http.client.HTTPConnection(host,port,timeout=timeout);deadline=time.monotonic()+20
    try:
        raw.connect(endpoint);conn.sock=raw if mock else ssl.create_default_context().wrap_socket(raw,server_hostname=host);sock=conn.sock
        if cancel():raise Cancelled('Online request cancelled before transmission')
        sent={'User-Agent':'DRAGONHYDRA/0.2.0-beta.2 (+https://github.com/chatgptopenaiagi/DRAGONHYDRA-SCRAPP-INTELLIGENCE)','Accept':'application/json','Accept-Encoding':'identity','Connection':'close',**headers}
        conn.request('GET',path+('?' +urlencode(params) if params else ''),headers=sent);resp=conn.getresponse()
        safe={k.lower():v[:200] for k,v in resp.getheaders() if k.lower() in ('retry-after','etag','last-modified','content-type','x-ratelimit-requests-limit','x-ratelimit-requests-remaining','x-ratelimit-limit','x-ratelimit-remaining','x-requestcounter-reset','x-requests-available-minute')}
        if resp.status in (401,403):raise ProviderError('Provider rejected authentication or access. Verify the saved credential and free-plan permissions.','AUTHENTICATION_FAILED',resp.status)
        if resp.status==429:raise ProviderError('The provider has temporarily limited requests. Collection is paused until the displayed retry time.','RATE_LIMITED',429,safe.get('retry-after'))
        if resp.status==304:return None,safe,304
        if resp.status!=200:raise ProviderError('Provider returned HTTP '+str(resp.status)+'. No observations were imported.','UNAVAILABLE',resp.status)
        if resp.getheader('Content-Encoding','identity')!='identity':raise ProviderError('Unexpected compressed response; collection refused')
        if int(resp.getheader('Content-Length','0'))>MAX_BYTES:raise ProviderError('Provider response exceeds the 5 MiB limit')
        data=bytearray()
        while True:
            # HTTPResponse closes its file as soon as Content-Length is satisfied.
            # Do not touch the now-closed socket while checking for another block.
            if resp.isclosed():break
            if cancel():raise Cancelled('Online request cancelled; no batch committed')
            remaining=deadline-time.monotonic()
            if remaining<=0:raise ProviderError('Provider response exceeded the total timeout')
            sock.settimeout(min(timeout,remaining));chunk=resp.read1(min(65536,MAX_BYTES+1-len(data)))
            if not chunk:break
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise ProviderError('Provider response exceeds the 5 MiB limit')
        return bytes(data),safe,200
    except (OSError,http.client.HTTPException):raise ProviderError('Provider connection failed or timed out. Check connectivity and retry later.','UNAVAILABLE') from None
    finally:conn.close();raw.close()
