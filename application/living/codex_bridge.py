"""Attach the existing Codex App Server. Never spawn, fork or restart a Codex worker."""
import ctypes,json,os,re,socket,threading,time,uuid
from pathlib import Path
from .contracts import now,atomic_json,Blocked

class RPC:
    def __init__(self,path):
        import websocket
        self.serial=0;raw=str(path).encode('utf-8')
        if len(raw)>=108:raise ValueError('Local Codex socket path is too long')
        sock=socket.socket(getattr(socket,'AF_UNIX',1),socket.SOCK_STREAM)
        try:
            if os.name=='nt' and not hasattr(socket,'AF_UNIX'):
                class Address(ctypes.Structure):_fields_=[('family',ctypes.c_ushort),('path',ctypes.c_char*108)]
                address=Address(1,raw);dll=ctypes.WinDLL('ws2_32');dll.connect.argtypes=[ctypes.c_size_t,ctypes.c_void_p,ctypes.c_int];dll.connect.restype=ctypes.c_int
                if dll.connect(sock.fileno(),ctypes.byref(address),ctypes.sizeof(address))!=0:raise OSError('Existing Codex socket is unavailable')
            else:sock.connect(str(path))
            sock.settimeout(10);self.ws=websocket.create_connection('ws://localhost/',socket=sock,suppress_origin=True,timeout=10)
            self.call('initialize',{'clientInfo':{'name':'dragonhydra_operator','version':'0.2.0-beta.3'},'capabilities':{'experimentalApi':True}});self.ws.send(json.dumps({'method':'initialized','params':{}}))
        except Exception:sock.close();raise
    def call(self,method,params):
        if method not in ('initialize','thread/read','thread/turns/list','turn/steer','turn/start'):raise ValueError('Codex method is outside this bridge contract')
        self.serial+=1;id=self.serial;self.ws.send(json.dumps({'id':id,'method':method,'params':params}));deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            raw=self.ws.recv()
            if len(raw)>2*1024*1024:raise ValueError('Codex response exceeded metadata limit')
            r=json.loads(raw)
            if r.get('id')==id:
                if 'error' in r:raise ValueError('Codex rejected '+method+' (code '+str(r['error'].get('code'))+'). Review the existing CLI session.')
                return r.get('result',{})
            # Unrequested events and other thread content are deliberately discarded.
        raise ValueError('Codex metadata request timed out')
    def close(self):self.ws.close()

class Engineering:
    def __init__(self,store,sanitize=None):
        from .cloud_manager import scrub
        self.store=store;self.lock=threading.RLock();self.sanitize=sanitize or scrub
        if not store.state('engineering','config'):store.state('engineering','config',{'enabled':False,'workspace':'','thread_id':os.environ.get('CODEX_THREAD_ID',''),'socket_path':str(Path.home()/'.codex/app-server-control/app-server-control.sock')})
    def configure(self,b):
        if set(b)-{'enabled','workspace','thread_id','socket_path'}:raise ValueError('Unknown engineering option')
        c={**self.store.state('engineering','config'),**b}
        if type(c['enabled']) is not bool or not re.fullmatch('[A-Za-z0-9_-]{1,100}',c['thread_id']):raise ValueError('Select the existing Codex thread ID')
        folder=Path(c['workspace']).resolve();sock=Path(c['socket_path']).resolve()
        if not folder.is_dir() or not (folder/'application').is_dir():raise ValueError('Select the authorized existing engineering project directory')
        if not sock.is_relative_to((Path.home()/'.codex').resolve()) or not sock.exists():raise ValueError('Select the existing current-user Codex control socket')
        c.update(workspace=str(folder),socket_path=str(sock));self.store.state('engineering','config',c);return self.status()
    def metadata(self,client,c):
        t=client.call('thread/read',{'threadId':c['thread_id'],'includeTurns':False}).get('thread',{})
        if Path(t.get('cwd','')).resolve()!=Path(c['workspace']).resolve():raise Blocked('The Codex thread belongs to another project. It will not be steered or resumed.')
        turns=client.call('thread/turns/list',{'threadId':c['thread_id'],'limit':1,'itemsView':'notLoaded','sortDirection':'desc'}).get('data',[])
        return {'thread_id':t.get('id'),'workspace':t.get('cwd'),'state':t.get('status',{}).get('type'),'active_turn':next(({'id':x['id'],'state':x['status']} for x in turns if x.get('status')=='inProgress'),None),'checked_at':now(),'history_text_read':False,'new_worker_started':False}
    def connect(self):
        c=self.store.state('engineering','config')
        if not c['enabled']:raise Blocked('Enable attachment to the explicitly selected existing Codex thread')
        client=None
        try:client=RPC(c['socket_path']);r=self.metadata(client,c);r['connection']='CONNECTED';self.store.state('engineering','connection',r);return r
        except Exception as e:self.store.state('engineering','connection',{'connection':'BLOCKED','checked_at':now(),'error':str(e) if isinstance(e,(ValueError,Blocked)) else 'Existing Codex App Server is unavailable. Start it through the normal Codex application; DRAGONHYDRA will not create another worker.'});raise Blocked(self.store.state('engineering','connection')['error']) from None
        finally:
            if client:client.close()
    def submit(self,instruction,area='general'):
        if not isinstance(instruction,str) or not 1<=len(instruction)<=2000 or area not in ('general','csv','sql','openai','ui','hardware'):raise ValueError('Enter a bounded engineering instruction')
        from .cloud_manager import scrub
        instruction=self.sanitize(instruction);c=self.store.state('engineering','config')
        if not c['enabled']:raise Blocked('Codex attachment is disabled')
        id=uuid.uuid4().hex;folder=Path(c['workspace'])/'evidence/mission-006/engineering-jobs';folder.mkdir(parents=True,exist_ok=True);result=folder/(id+'.result.json');job={'id':id,'state':'SUBMITTING','area':area,'instruction':instruction,'at':now(),'thread_id':c['thread_id'],'result_path':str(result)};self.store.state('engineering-job',id,job)
        client=None
        try:
            client=RPC(c['socket_path']);meta=self.metadata(client,c);text='Owner instruction from the authenticated DRAGONHYDRA Engineering tab. Continue the existing mission and preserve all boundaries. Diagnostic job '+id+': '+instruction+'\nWhen this bounded diagnostic is executed, save a redacted JSON receipt with job_id, status, summary and evidence_paths to '+str(result)+'. Do not start another Codex session or expose credentials.';params={'threadId':c['thread_id'],'input':[{'type':'text','text':text}]}
            if meta['active_turn']:params['expectedTurnId']=meta['active_turn']['id'];r=client.call('turn/steer',params)
            elif meta['state']=='idle':r=client.call('turn/start',params)
            else:raise Blocked('Existing thread is not active or idle. Reopen it in Codex; no competing thread will be created.')
            job.update(state='SUBMITTED',turn_id=r.get('turnId') or r.get('turn',{}).get('id'),submitted_at=now(),new_worker_started=False)
        except Exception as e:job.update(state='BLOCKED',error=str(e) if isinstance(e,(ValueError,Blocked)) else 'Existing Codex connection failed; no duplicate task was created')
        finally:
            if client:client.close()
        self.store.state('engineering-job',id,job);return job
    def status(self):
        c=self.store.state('engineering','config');jobs=self.store.states('engineering-job')
        for job in jobs:
            p=Path(job['result_path'])
            if job['state']=='SUBMITTED' and p.is_file() and p.stat().st_size<128000:
                try:
                    r=json.loads(p.read_text(encoding='utf-8'))
                    if r.get('job_id')==job['id'] and r.get('status') in ('PASS','FAIL','BLOCKED','PARTIAL'):
                        from .cloud_manager import scrub
                        job.update(state=r['status'],result=self.sanitize(r));self.store.state('engineering-job',job['id'],job)
                except (ValueError,OSError):pass
        workspace=Path(c['workspace']) if c.get('workspace') else None;checkpoint=None
        if workspace:
            p=workspace/'evidence/mission-006/MISSION-006-STATE.json'
            if p.is_file() and p.stat().st_size<100000:
                try:v=json.loads(p.read_text());checkpoint={k:v.get(k) for k in ('status','checkpoint','version','updated_at','publication','remaining')}
                except (OSError,ValueError):checkpoint={'status':'UNREADABLE_CHECKPOINT','recovery':'Inspect retained mission evidence'}
        return {'configuration':c,'connection':self.store.state('engineering','connection') or {'connection':'DISCONNECTED'},'jobs':jobs[-50:],'mission_checkpoint':checkpoint,'worker_policy':'Attach existing thread only; no shell access from cloud tools, no daemon restart, no new Codex worker','recovery':'Reconnect to the existing thread; submitted diagnostics retain their receipts'}
