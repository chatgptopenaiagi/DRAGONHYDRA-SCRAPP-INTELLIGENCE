import csv,hmac,io,json,os,secrets,subprocess,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .model import stamp
from .storage import StorageUnavailable
from .demo import TIMES

def private_token(data_dir):
    folder=Path(data_dir)/'private';fresh=not folder.exists();folder.mkdir(parents=True,exist_ok=True)
    if fresh and os.name=='nt':
        sid=list(csv.reader(io.StringIO(subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True))))[0][1]
        if not sid.startswith('S-1-'):raise RuntimeError('Windows SID lookup failed')
        subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r','*S-1-5-18:(OI)(CI)F','*'+sid+':(OI)(CI)F'],check=True,capture_output=True)
    path=folder/'api-token.txt'
    if not path.exists():
        with path.open('x',encoding='ascii') as f:f.write(secrets.token_urlsafe(48))
    token=path.read_text(encoding='ascii').strip()
    if len(token)<40:raise RuntimeError('API token is invalid')
    return token,path

class Server(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,runtime,token):
        self.runtime=runtime;self.token=token;self.slots=threading.BoundedSemaphore(8)
        super().__init__(address,Handler)
    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False):
            request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nContent-Length: 0\r\n\r\n');self.shutdown_request(request);return
        try:super().process_request(request,client_address)
        except Exception:self.slots.release();raise
    def process_request_thread(self,request,client_address):
        try:super().process_request_thread(request,client_address)
        finally:self.slots.release()

class Handler(BaseHTTPRequestHandler):
    server_version='DRAGONHYDRA/0.1';sys_version=''
    def setup(self):super().setup();self.connection.settimeout(10)
    def log_message(self,*args):pass # No tokens, provider URLs or payloads in access logs.
    def send(self,status,payload,content_type='application/json; charset=utf-8',filename=None):
        body=json.dumps(payload,ensure_ascii=False,default=str,allow_nan=False).encode() if content_type.startswith('application/json') else payload if isinstance(payload,bytes) else str(payload).encode()
        self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'")
        if filename:self.send_header('Content-Disposition','attachment; filename="'+filename+'"')
        self.end_headers();self.wfile.write(body)
    def allowed(self):
        if self.client_address[0]!='127.0.0.1':return False
        if urlsplit('http://'+self.headers.get('Host','')).hostname not in ('127.0.0.1','localhost','::1'):return False
        origin=self.headers.get('Origin')
        return not origin or urlsplit(origin).hostname in ('127.0.0.1','localhost','::1')
    def authenticated(self):return hmac.compare_digest(self.headers.get('X-Dragonhydra-Token',''),self.server.token)
    def do_GET(self):self.handle_route(False)
    def do_POST(self):self.handle_route(True)
    def handle_route(self,post):
        try:
            if not self.allowed():return self.send(403,{'error':'Loopback host/origin required'})
            if len(self.path)>8000:return self.send(414,{'error':'URL too long'})
            parsed=urlsplit(self.path);path=parsed.path;rt=self.server.runtime
            assets={'/':'dashboard.html','/dashboard.js':'dashboard.js','/dashboard.css':'dashboard.css'}
            if not post and path in assets:
                p=Path(__file__).with_name('web')/assets[path];mime='text/html' if path=='/' else 'text/javascript' if path.endswith('.js') else 'text/css'
                return self.send(200,p.read_bytes(),mime+'; charset=utf-8')
            if not self.authenticated():return self.send(401,{'error':'Authenticated application API required'})
            args={k:v[0] for k,v in parse_qs(parsed.query).items()}
            if post:
                if self.headers.get('Transfer-Encoding'):return self.send(400,{'error':'Chunked requests not supported'})
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2_000_000:return self.send(413,{'error':'Request requires a bounded JSON body'})
                body=json.loads(self.rfile.read(length),parse_float=str,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON number')))
                if not isinstance(body,dict):raise ValueError('Expected JSON object')
                if path=='/api/import':return self.send(200,rt.import_rows(body.get('records')))
                if path=='/api/classify':return self.send(200,rt.operation('cognition','classify',body.get('value'),body.get('context')))
                if path=='/api/demo':return self.send(200,rt.seed())
                if path=='/api/replay':
                    index=body.get('index')
                    if type(index) is not int or not 0<=index<len(TIMES):raise ValueError('Replay index must be 0..5')
                    rt.demo_index=index;return self.send(200,{'index':index,'cutoff':TIMES[index]})
                if path=='/api/collect':return self.send(200,rt.operation('acquisition','collect',body.get('source_id')))
                if path=='/api/sources':return self.send(200,rt.configure_source(body))
                if path=='/api/mirror':return self.send(200,rt.mirror_import(int(body['port']),body['market'],body.get('at')))
                if path=='/api/shutdown':
                    self.send(200,{'status':'stopping'});threading.Thread(target=self.server.shutdown,daemon=True).start();return
            else:
                if path=='/api/status':return self.send(200,rt.status())
                if path=='/api/calculate':return self.send(200,rt.operation('probability','calculate',args.get('value'),args.get('format','decimal')))
                if path in ('/api/observations','/api/export.json','/api/export.csv'):
                    supported={'source','kind','origin','start','at','search','limit','offset','order'}
                    if set(args)-supported:raise ValueError('Unknown query parameter')
                    result=rt.query(**args)
                    if path.endswith('.csv'):
                        buffer=io.StringIO(newline='');writer=csv.writer(buffer);fields=['id','source_id','source_url','key','kind','value','original_value','unit','text','origin','verification','received_at','observed_at','published_at','issue_at','valid_at','freshness','raw_hash','engine_version','metadata','interpretations']
                        writer.writerow(fields)
                        for row in result['rows']:writer.writerow([('' if row.get(f) is None else row[f]) if f=='value' else csv_safe(json.dumps(row.get(f),ensure_ascii=False) if f in ('metadata','interpretations') else row.get(f)) for f in fields])
                        return self.send(200,buffer.getvalue(),'text/csv; charset=utf-8','dragonhydra-observations.csv')
                    return self.send(200,result,filename='dragonhydra-observations.json' if path.endswith('.json') else None)
            return self.send(404,{'error':'Unknown API operation'})
        except StorageUnavailable as e:return self.send(503,{'error':str(e),'status':'SQL_NOT_VERIFIED'})
        except (ValueError,KeyError,TypeError) as e:return self.send(400,{'error':str(e)[:300]})
        except Exception as e:return self.send(500,{'error':'Operation failed','error_class':type(e).__name__})

def csv_safe(value):
    text='' if value is None else str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text
