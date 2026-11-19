"""Synthetic protocol server. Never evidence of a live company response."""
import json,threading,time
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit
class ChatMock:
    def __init__(self):
        self.calls=[];self.status=200;self.delay=0;self.tool=None;self.arguments={};self.malformed=False;self.echo=False
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.run()
            def do_POST(self):self.run()
            def run(self):
                path=urlsplit(self.path).path;body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}');key=self.headers.get('Authorization',self.headers.get('x-api-key',self.headers.get('api-key',self.headers.get('x-manus-api-key',''))));owner.calls.append({'path':path,'body':body,'key':key});time.sleep(owner.delay)
                status=owner.status
                if key.endswith('invalid-test-key'):status=401
                if status!=200:d={'error':{'code':'rate_limit' if status==429 else 'authentication_error','message':'SYNTHETIC FAILURE'}}
                elif path.endswith('/models'):d={'data':[{'id':'mock-chat-model'}]}
                elif path.endswith('/info'):d={'model_name':'mock-chat-model'}
                elif path=='/v2/user.me':d={'ok':True}
                elif path=='/v2/task.create':d={'ok':True,'task_id':'mock_task_1'}
                elif path in ('/v2/task.sendMessage','/v2/task.stop'):d={'ok':True}
                elif path=='/v2/task.listMessages':d={'ok':True,'messages':[{'id':'m1','type':'assistant_message','assistant_message':{'content':'MOCK Manus retained reply'}}]}
                elif path.endswith('/tokens/generate'):d={'token':'SYNTHETIC-CHANNEL-TOKEN'}
                elif path.endswith('/conversations'):d={'conversationId':'mockconversation1','token':'SYNTHETIC-CHANNEL-TOKEN'}
                elif path.endswith('/activities'):d={'activities':[{'id':'a1','type':'message','from':{'id':'bot'},'text':'MOCK Microsoft agent reply'}]}
                else:
                    wire=body.get('input',body.get('messages',[]));flat=json.dumps(wire);done='function_call_output' in flat or 'tool_result' in flat or '"role": "tool"' in flat;tool=owner.tool if not done else None;text=key if owner.echo else 'MOCK '+('tool evidence received' if done else 'conversation reply')+'; retained messages='+str(len(wire));usage={'input_tokens':20,'output_tokens':10}
                    if path.endswith('/responses'):d={'id':'mock-response','model':body.get('model'),'output':[{'type':'function_call','call_id':'call1','name':tool,'arguments':json.dumps(owner.arguments)}] if tool else [{'type':'message','role':'assistant','content':[{'type':'output_text','text':text}]}],'usage':usage}
                    elif path=='/v1/messages':d={'id':'mock-claude','model':body.get('model'),'content':[{'type':'tool_use','id':'call1','name':tool,'input':owner.arguments}] if tool else [{'type':'text','text':text}],'usage':usage}
                    else:d={'id':'mock-chat','model':body.get('model'),'choices':[{'message':{'role':'assistant','content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':tool,'arguments':json.dumps(owner.arguments)}}]} if tool else {'role':'assistant','content':text}}],'usage':usage}
                raw=b'not-json' if owner.malformed else json.dumps(d).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Retry-After','90');self.end_headers()
                try:self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.origin='http://127.0.0.1:'+str(self.server.server_port);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
