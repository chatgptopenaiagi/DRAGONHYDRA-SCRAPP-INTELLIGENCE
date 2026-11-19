"""One loopback HTTP server; strict origins, session exchange and explicit API contracts."""
import base64,csv,hmac,io,json,threading,time
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from .security import Sessions
from .contracts import encode,now,atomic_json,Blocked
from .analytics import calculate,correlate,evaluate,sentiment,odds

class Server(ThreadingHTTPServer):
    daemon_threads=True;allow_reuse_address=False
    def __init__(self,address,runtime,secret,bridge_secret=None):
        self.runtime=runtime;self.auth=Sessions(secret);self.slots=threading.BoundedSemaphore(12)
        self.bridge_secret=bridge_secret
        super().__init__(address,Handler);self.origin=f'http://127.0.0.1:{self.server_address[1]}';self.cookie='dh_session_'+str(self.server_address[1])
    def process_request(self,request,address):
        if not self.slots.acquire(False):self.shutdown_request(request);return
        try:super().process_request(request,address)
        except BaseException:self.slots.release();raise
    def process_request_thread(self,request,address):
        try:super().process_request_thread(request,address)
        finally:self.slots.release()
class Handler(BaseHTTPRequestHandler):
    server_version='DRAGONHYDRA/0.2';sys_version=''
    def setup(self):super().setup();self.connection.settimeout(20)
    def log_message(self,*args):pass
    def send(self,status,data,mime='application/json',cookie=None,download=None):
        body=encode(data).encode() if mime=='application/json' else data if isinstance(data,bytes) else str(data).encode()
        self.send_response(status)
        for k,v in {'Content-Type':mime+'; charset=utf-8','Content-Length':str(len(body)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",'Cross-Origin-Resource-Policy':'same-origin'}.items():self.send_header(k,v)
        if cookie is not None:self.send_header('Set-Cookie',f'{self.server.cookie}={cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age={3600 if cookie else 0}')
        if download:self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.end_headers();self.wfile.write(body)
    def do_GET(self):self.route(False)
    def do_POST(self):self.route(True)
    def route(self,post):
        try:
            server=self.server;rt=server.runtime
            if self.client_address[0]!='127.0.0.1' or self.headers.get('Host')!=urlsplit(server.origin).netloc:return self.send(403,{'error':'Exact loopback host and port required'})
            origin=self.headers.get('Origin')
            if origin and origin!=server.origin:return self.send(403,{'error':'Cross-origin requests are rejected'})
            if self.headers.get('Sec-Fetch-Site') in ('cross-site','same-site'):return self.send(403,{'error':'Cross-site requests are rejected'})
            if len(self.path)>8000:return self.send(414,{'error':'URL too long'})
            p=urlsplit(self.path);path=p.path;query={k:v[0] for k,v in parse_qs(p.query).items()}
            if not post and path in ('/','/app.js','/sources.js','/workstation.js','/cockpit.js','/cockpit.css','/app.css'):
                name='index.html' if path=='/' else path[1:]
                return self.send(200,(Path(__file__).with_name('web')/name).read_bytes(),'text/html' if path=='/' else 'text/css' if path.endswith('.css') else 'text/javascript')
            if not post and path=='/auth/identity':
                from .contracts import fingerprint
                challenge=query.get('challenge','')
                if len(challenge)!=64 or any(c not in '0123456789abcdef' for c in challenge):raise ValueError('Invalid identity challenge')
                data_id=fingerprint(str(rt.data));proof=hmac.new(server.auth.secret.encode(),(challenge+'|'+data_id).encode(),'sha256').hexdigest()
                return self.send(200,{'data_id':data_id,'proof':proof,'product':'DRAGONHYDRA SCRAPP INTELLIGENCE'})
            body={}
            if post:
                length=int(self.headers.get('Content-Length','0'))
                if self.headers.get('Transfer-Encoding') or not 0<length<=29*1024*1024:return self.send(413,{'error':'Bounded JSON request required'})
                if self.headers.get_content_type()!='application/json':return self.send(415,{'error':'application/json is required'})
                body=json.loads(self.rfile.read(length),parse_float=str,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
                if not isinstance(body,dict):raise ValueError('JSON object required')
            if post and path=='/auth/exchange':
                if origin!=server.origin:return self.send(403,{'error':'Same-origin browser exchange required'})
                token,csrf=server.auth.exchange(str(body.get('ticket','')));return self.send(200,{'csrf':csrf,'expires_in':3600},cookie=token)
            if path=='/api/mcp':
                if not rt.extensions.authorized(self.headers.get('X-DH-MCP','')):return self.send(401,{'error':'A configured, separate read-only MCP credential is required'})
                if not post:return self.send(405,{'error':'This stateless MCP endpoint supports POST JSON responses; SSE is not enabled'})
                if len(json.dumps(body))>32000:return self.send(413,{'error':'MCP request exceeds 32 KB'})
                result=rt.extensions.call(body);return self.send(202 if result is None else 200,result if result is not None else '',mime='text/plain' if result is None else 'application/json')
            admin=server.auth.admin(self.headers.get('X-DH-Local',''))
            bridge=bool(server.bridge_secret) and hmac.compare_digest(self.headers.get('X-DH-Bridge',''),server.bridge_secret)
            cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''));token=cookies.get(server.cookie);token=token.value if token else ''
            session=server.auth.get(token) if token else None
            if not admin and not session and not bridge:return self.send(401,{'error':'Authentication required. Reopen this dashboard from the DRAGONHYDRA launcher.'})
            if bridge and not admin and not session and (post or path not in ('/api/status','/api/observations')):return self.send(403,{'error':'Joomla bridge credential is read-only and endpoint-scoped'})
            if post and not admin and (origin!=server.origin or not hmac.compare_digest(self.headers.get('X-DH-CSRF',''),session['csrf'])):return self.send(403,{'error':'Same-origin request and CSRF token required'})
            if post:
                if path=='/api/chat/create':return self.send(200,rt.conversations.create(body))
                if path=='/api/chat/send':return self.send(202,rt.conversations.send(body))
                if path=='/api/chat/cancel':return self.send(200,rt.conversations.cancel(body['turn_id']))
                if path=='/api/chat/inspect':return self.send(200,rt.conversations.inspect_remote(body['session_id']))
                if path=='/api/chat/roundtable':return self.send(202,rt.conversations.roundtable(body))
                if path=='/api/registry/run':return self.send(200,rt.registry.run(body['name'],body.get('arguments',{})))
                if path=='/api/registry/enable':return self.send(200,rt.registry.enable(body['name'],body['enabled']))
                if path=='/api/registry/action':return self.send(200,rt.registry.action(body['id'],body.get('approve') is True))
                if path=='/api/engineering/configure':return self.send(200,rt.engineering.configure(body))
                if path=='/api/engineering/connect':return self.send(200,rt.engineering.connect())
                if path=='/api/engineering/submit':return self.send(202,rt.engineering.submit(body.get('instruction'),body.get('area','general')))
                if path=='/api/extensions/configure':return self.send(200,rt.extensions.configure(body['enabled'],server.origin))
                if path=='/api/sql/configure':return self.send(200,rt.sql.configure(body))
                if path=='/api/sql/discover':return self.send(200,rt.sql.discover())
                if path=='/api/sql/test':return self.send(200,rt.sql.test())
                if path=='/api/sql/databases':return self.send(200,rt.sql.databases())
                if path=='/api/sql/schemas':return self.send(200,rt.sql.schemas(body.get('database')))
                if path=='/api/sql/tables':return self.send(200,rt.sql.tables(body.get('database'),body.get('schema',''),body.get('include_system',False)))
                if path=='/api/sql/describe':return self.send(200,rt.sql.describe(body.get('database'),body.get('schema','dbo'),body.get('table','')))
                if path=='/api/sql/query':return self.send(200,rt.sql.readonly_query(body))
                if path=='/api/sql/inventory':return self.send(200,rt.sql.inventory())
                if path=='/api/sql/provision':return self.send(200,rt.sql.provision(body.get('confirmation')))
                if path=='/api/sql/sync':return self.send(200,rt.sql.sync(body.get('source'),body.get('limit',1000),body.get('offset',0)))
                if path=='/api/sql/backups':return self.send(200,rt.sql.backup_info())
                if path=='/api/knowledge/configure':return self.send(200,rt.knowledge.configure(body))
                if path=='/api/knowledge/refresh':return self.send(200,rt.knowledge.refresh(body['id']))
                if path=='/api/tools/run':return self.send(200,rt.evidence_tools.run(body['name'],body.get('arguments',{})))
                if path=='/api/cloud/configure':return self.send(200,rt.cloud.configure(body))
                if path=='/api/cloud/credential':return self.send(200,rt.cloud.credential(body))
                if path=='/api/cloud/credential/remove':return self.send(200,rt.cloud.credential(body,True))
                if path=='/api/cloud/test':return self.send(200,rt.cloud.test(body['id']))
                if path=='/api/cloud/preview':return self.send(200,rt.cloud.preview(body))
                if path=='/api/cloud/run':return self.send(200,rt.cloud.run(body))
                if path=='/api/cloud/inspect':return self.send(200,rt.cloud.inspect(body['receipt_id']))
                if path=='/api/cloud/stop':return self.send(200,rt.cloud.inspect(body['receipt_id'],True))
                if path=='/api/provider/status':return self.send(202,rt.providers.submit(body['slot'],'status'))
                if path=='/api/session-ticket':
                    if not admin:return self.send(403,{'error':'Only the local launcher can issue browser tickets'})
                    return self.send(200,{'ticket':server.auth.ticket(),'expires_in':45})
                if path=='/api/logout':server.auth.revoke(token);return self.send(200,{'status':'LOGGED_OUT'},cookie='')
                if path=='/api/revoke':server.auth.revoke_all();return self.send(200,{'status':'REVOKED'},cookie='')
                if path=='/api/source':return self.send(200,rt.configure_source(body))
                if path=='/api/mode':return self.send(200,rt.set_mode(body.get('mode')))
                if path=='/api/provider/configure':return self.send(200,rt.providers.configure(body))
                if path=='/api/provider/credential':return self.send(200,rt.providers.credential(body))
                if path=='/api/provider/credential/remove':return self.send(200,rt.providers.credential(body,True))
                if path=='/api/provider/remove':return self.send(200,rt.providers.remove(body['slot']))
                if path=='/api/provider/test':return self.send(202,rt.providers.submit(body['slot'],'test'))
                if path=='/api/provider/collect':return self.send(202,rt.providers.submit(body['slot']))
                if path=='/api/football/alias':
                    from .football_comparison import save_alias
                    return self.send(200,save_alias(rt.store,body))
                if path=='/api/import':return self.send(202,{'task_id':rt.acquisition.submit(body['source_id'],body.get('content'),body.get('filename'))})
                if path=='/api/csv/preview':return self.send(200,rt.acquisition.csv.preview(body))
                if path=='/api/csv/validate':return self.send(200,rt.acquisition.csv.validate(body))
                if path=='/api/csv/confirm':return self.send(202,rt.acquisition.csv.confirm(body))
                if path=='/api/task/cancel':rt.acquisition.cancelled.add(body['id']);return self.send(200,{'status':'CANCELLATION_REQUESTED'})
                if path=='/api/task/resume':rt.acquisition.resume(body['id']);return self.send(200,{'status':'QUEUED'})
                if path=='/api/backup':return self.send(200,rt.backup())
                if path=='/api/analyze':
                    result=rt.store.query(body.get('filters'),10000)
                    if result['total']>10000:raise ValueError('Narrow the analysis to at most 10000 rows')
                    output=calculate(result['rows'],body.get('configuration'));rt.store.save_analysis(output);return self.send(200,output)
                if path=='/api/correlation':
                    left=rt.store.query(body['left'],10000);right=rt.store.query(body['right'],10000)
                    if max(left['total'],right['total'])>10000:raise ValueError('Narrow each correlation input to at most 10000 rows')
                    return self.send(200,correlate(left['rows'],right['rows']))
                if path=='/api/evaluate':return self.send(200,evaluate([float(v) for v in body['predictions']],body['outcomes']))
                if path=='/api/ai/config':
                    ai={k:body.get(k) for k in ('enabled','endpoint','model')}
                    if type(ai['enabled']) is not bool:raise ValueError('AI enabled must be a boolean')
                    endpoint=urlsplit(ai['endpoint'] or '')
                    if ai['enabled'] and (endpoint.scheme!='http' or endpoint.hostname!='127.0.0.1' or not endpoint.port or endpoint.username or endpoint.password or endpoint.query):raise ValueError('Configure a loopback HTTP endpoint; cloud AI is disabled')
                    rt.config['ai']=ai;atomic_json(rt.config_path,rt.config);return self.send(200,{'status':'CONFIGURED','enabled':ai['enabled']})
                if path=='/api/ai/explain':
                    from .connectors import local_ai
                    evidence=rt.store.query(body.get('filters'),50);return self.send(200,local_ai(rt.config.get('ai',{}),evidence))
                if path=='/api/shutdown':
                    self.send(200,{'status':'STOPPING'});threading.Thread(target=server.shutdown,daemon=True).start();return
            else:
                if path=='/api/chat/sessions':return self.send(200,rt.conversations.list(query.get('search','')))
                if path=='/api/chat/session':return self.send(200,rt.conversations.detail(query.get('id')))
                if path=='/api/chat/export':return self.send(200,rt.conversations.detail(query.get('id')),download='dragonhydra-conversation.json')
                if path=='/api/registry':return self.send(200,{'tools':rt.registry.contracts(),'actions':rt.store.states('owner-action')[-50:],'receipts':sorted(rt.store.states('tool-receipt'),key=lambda r:r['at'],reverse=True)[:50]})
                if path=='/api/engineering':return self.send(200,rt.engineering.status())
                if path=='/api/hardware':return self.send(200,rt.hardware.sample())
                if path=='/api/extensions':return self.send(200,rt.extensions.status())
                if path=='/api/sql':return self.send(200,rt.sql.status())
                if path=='/api/knowledge':return self.send(200,rt.knowledge.list(query.get('search','')))
                if path=='/api/knowledge/evidence':return self.send(200,rt.knowledge.query(query.get('search',''),[query['id']] if query.get('id') else None))
                if path=='/api/tools':return self.send(200,rt.evidence_tools.contracts())
                if path=='/api/cloud':return self.send(200,rt.cloud.list())
                if path=='/api/cloud/receipts':return self.send(200,sorted(rt.store.states('cloud-receipt'),key=lambda r:r['at'],reverse=True)[:100])
                if path=='/api/session':return self.send(200,{'csrf':session['csrf'] if session else None,'authenticated':True})
                if path=='/api/status':return self.send(200,rt.status())
                if path=='/api/tasks':return self.send(200,rt.store.tasks())
                if path=='/api/providers':return self.send(200,rt.providers.list())
                if path=='/api/football/comparison':
                    from .football_comparison import compare
                    return self.send(200,compare(rt.store,query))
                if path=='/api/analyses':return self.send(200,rt.store.analyses())
                if path=='/api/backups':return self.send(200,[{'name':p.name,'bytes':p.stat().st_size} for p in sorted((rt.data/'backups').glob('*.sqlite3'))])
                if path=='/api/odds':return self.send(200,odds(query['value']))
                if path=='/api/sentiment':return self.send(200,[sentiment(r) for r in rt.store.query({'kind':'SHORT_TEXT'},500)['rows']])
                if path in ('/api/observations','/api/export.json','/api/export.csv'):
                    limit=query.pop('limit',100 if path=='/api/observations' else 10000);offset=query.pop('offset',0)
                    if set(query)-{'source','kind','origin','series','search','start','end'}:raise ValueError('Unknown filter')
                    result=rt.store.query(query,limit,offset)
                    if path.endswith('.csv'):
                        stream=io.StringIO(newline='');fields=['id','source_id','key','kind','origin','value','unit','observed_at','collected_at','issue_at','valid_at','raw_hash','text'];writer=csv.writer(stream);writer.writerow(fields)
                        for r in result['rows']:
                            writer.writerow([("'"+str(r[k]) if k!='value' and str(r.get(k,'')).startswith(('=','+','-','@','\t','\r')) else r.get(k,'')) for k in fields])
                        return self.send(200,stream.getvalue(),'text/csv',download='dragonhydra-observations.csv')
                    return self.send(200,result,download='dragonhydra-observations.json' if path.endswith('.json') else None)
            self.send(404,{'error':'Unknown operation'})
        except PermissionError as e:self.send(401,{'error':str(e)})
        except Blocked as e:self.send(409,{'error':str(e),'status':'BLOCKED'})
        except (ValueError,KeyError,TypeError,OverflowError) as e:self.send(400,{'error':str(e)[:600]})
        except (BrokenPipeError,ConnectionResetError):pass
        except Exception as e:
            self.server.runtime.store.event('ERROR','API_FAILURE',type(e).__name__)
            self.send(500,{'error':type(e).__name__+'; operation failed; inspect diagnostics'})
