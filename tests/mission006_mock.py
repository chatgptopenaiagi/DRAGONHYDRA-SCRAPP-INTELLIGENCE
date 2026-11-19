"""Isolated protocol fixtures. All credentials and responses here are synthetic."""
import json,threading
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit
class Mock:
    def __init__(self):
        self.calls=[];self.status=200;self.malformed=False;self.echo=False
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):self.run()
            def do_POST(self):self.run()
            def run(self):
                path=urlsplit(self.path).path;body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}');key=self.headers.get('Authorization',self.headers.get('x-api-key',self.headers.get('api-key',self.headers.get('x-manus-api-key',''))));owner.calls.append({'path':self.path,'method':self.command,'body':body,'credential':key})
                status=owner.status
                if key.endswith('invalid-test-credential'):status=401
                if status!=200:data={'error':{'code':'rate_limit' if status==429 else 'authentication_error','message':'SYNTHETIC_FAILURE'}}
                elif path.endswith('/models'):data={'data':[{'id':'mock-text-model'}]}
                elif path.endswith('/info'):data={'model_name':'mock-deployment','model_type':'chat-completion'}
                elif path=='/v2/user.me':data={'ok':True,'user':{'email':'private-synthetic@example.invalid'}}
                elif path=='/v2/task.create':data={'ok':True,'task_id':'mock_task_1'}
                elif path=='/v2/task.stop':data={'ok':True}
                elif path=='/v2/task.listMessages':data={'ok':True,'messages':[{'type':'assistant_message','assistant_message':{'content':'MOCK interpretation'}}]}
                elif path.endswith('/tokens/generate'):data={'token':'SYNTHETIC-DIRECTLINE-SECRET','expires_in':1800}
                elif path.endswith('/conversations'):data={'conversationId':'mockconversation1','token':'SYNTHETIC-DIRECTLINE-SECRET'}
                elif path.endswith('/activities'):data={'activities':[{'type':'message','text':'MOCK interpretation'}]}
                elif path.endswith('/responses'):data={'id':'mock-response','model':body.get('model'),'output':[{'type':'message','content':[{'type':'output_text','text':key if owner.echo else 'MOCK interpretation; no verified football facts.'}]}],'usage':{'input_tokens':10,'output_tokens':8}}
                elif path=='/v1/messages':data={'content':[{'type':'text','text':'MOCK Claude interpretation'}],'usage':{'input_tokens':10,'output_tokens':5}}
                else:data={'choices':[{'message':{'content':'MOCK compatible interpretation'}}],'usage':{'prompt_tokens':10,'completion_tokens':7}}
                raw=b'invalid-json' if owner.malformed else json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.send_header('Retry-After','120');self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.origin='http://127.0.0.1:'+str(self.server.server_port);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()
