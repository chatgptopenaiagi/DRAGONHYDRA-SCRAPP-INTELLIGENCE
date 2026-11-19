"""Durable provider-bound conversations. Bounded calls, explicit retries, no paid replay."""
import json,threading,time,uuid
from concurrent.futures import ThreadPoolExecutor
from .contracts import now,fingerprint,Blocked,Cancelled
from .cloud_manager import scrub
from . import conversation_protocols as protocol

ACTIVE=('QUEUED','RUNNING','CANCELLING')
class Conversations:
    def __init__(self,rt):
        self.rt=rt;self.store=rt.store;self.cloud=rt.cloud;self.registry=rt.registry;self.lock=threading.RLock();self.events={};self.pool=ThreadPoolExecutor(max_workers=2,thread_name_prefix='dh-chat');self.closed=False
        for t in self.store.states('chat-turn'):
            if t['state'] in ACTIVE:t.update(state='INTERRUPTED',error='The response outcome is unknown after interruption. Inspect the provider before explicitly retrying; no automatic paid replay.');self.store.state('chat-turn',t['id'],t)
        for a in self.store.states('owner-action'):
            if a['state']=='EXECUTING':a.update(state='INTERRUPTED',error='Owner action was interrupted. Reconcile its receipt before resubmitting.');self.store.state('owner-action',a['id'],a)
    def create(self,b):
        provider=b.get('provider');c=self.cloud.config(provider);tools=b.get('tools',[]);title=b.get('title','New conversation')
        if not isinstance(title,str) or not 1<=len(title)<=120:raise ValueError('Conversation title must be 1–120 characters')
        if not isinstance(tools,list) or len(tools)>17 or any(not isinstance(n,str) or n not in {t['name'] for t in self.registry.contracts()} for n in tools):raise ValueError('Choose documented tools for this conversation')
        if tools and b.get('allow_tool_sharing') is not True:raise ValueError('Approve sharing the selected bounded tool outputs with this provider')
        if provider in ('manus','copilot-studio') and tools:raise ValueError('This provider protocol has no verified local function-call interface. Attach explicitly selected tool receipts instead.')
        s={'id':uuid.uuid4().hex,'provider':provider,'endpoint':c['endpoint'],'model':c['model'],'title':scrub(title,self.cloud.secrets()),'at':now(),'updated_at':now(),'tools':list(dict.fromkeys(tools)),'tool_sharing_approved':bool(tools),'remote_task_id':None,'context_policy':'Last 20 user/assistant messages, at most 32 KB. Saved history remains complete; old turns are not automatically summarized. Tool outputs are re-queried when needed.'}
        self.store.state('chat-session',s['id'],s);return s
    def session(self,id):
        s=self.store.state('chat-session',id)
        if not s:raise ValueError('Conversation not found')
        return s
    def list(self,search=''):
        if not isinstance(search,str) or len(search)>200:raise ValueError('History search exceeds 200 characters')
        matches=set()
        if search:
            with self.store.lock:
                for r in self.store.c.execute("SELECT payload FROM component_state WHERE scope='chat-message' AND payload LIKE ? ESCAPE '~' LIMIT 1000",('%'+search.replace('~','~~').replace('%','~%').replace('_','~_')+'%',)):matches.add(json.loads(r[0])['session_id'])
        return sorted([s for s in self.store.states('chat-session') if not search or search.casefold() in s['title'].casefold() or s['id'] in matches],key=lambda s:s['updated_at'],reverse=True)[:100]
    def detail(self,id):
        s=self.session(id)
        with self.store.lock:
            messages=[json.loads(r[0]) for r in self.store.c.execute("SELECT payload FROM component_state WHERE scope='chat-message' AND json_extract(payload,'$.session_id')=? ORDER BY json_extract(payload,'$.at'),rowid",(id,))]
            turns=[json.loads(r[0]) for r in self.store.c.execute("SELECT payload FROM component_state WHERE scope='chat-turn' AND json_extract(payload,'$.session_id')=? ORDER BY json_extract(payload,'$.at'),rowid",(id,))]
        return {'session':s,'messages':messages,'turns':turns,'classification':'AI_INTERPRETATION','source_records_modified':False}
    def message(self,s,role,text,turn,**extra):
        m={'id':uuid.uuid4().hex,'session_id':s['id'],'provider':s['provider'],'model':s['model'],'role':role,'text':scrub(text,self.cloud.secrets()),'at':now(),'turn_id':turn,**extra};self.store.state('chat-message',m['id'],m);return m
    def ready(self,s):
        c,a=self.cloud.ready(s['provider'])
        if (c['endpoint'],c['model'])!=(s['endpoint'],s['model']):raise Blocked('Provider endpoint or model changed. Restore the original configuration or start a new conversation; history will not be sent to another backend.')
        if c.get('state')=='ACCOUNT_ALLOWANCE_EXHAUSTED':raise Blocked('This account has no usable API allowance. Restore credits through the provider, then explicitly test the connection before retrying. No paid plan is enabled here.')
        return c,a
    def send(self,b):
        with self.lock:
            if self.closed:raise Blocked('Application is shutting down')
            s=self.session(b.get('session_id'));text=b.get('text');retry=b.get('retry_turn')
            if retry:
                prior=self.store.state('chat-turn',retry)
                if not prior or prior['session_id']!=s['id'] or prior['state'] not in ('FAILED','BLOCKED','CANCELLED','INTERRUPTED'):raise ValueError('Only failed, cancelled or interrupted turns can be explicitly retried')
                text=prior['input']
            if not isinstance(text,str) or not 1<=len(text)<=8000:raise ValueError('Enter a message of 1–8000 characters')
            active=[t for t in self.store.states('chat-turn') if t['state'] in ACTIVE]
            if any(t['session_id']==s['id'] for t in active):raise Blocked('This conversation already has a response in progress')
            if len(active)>=5:raise Blocked('Five responses are already running or queued. Wait or cancel one.')
            self.ready(s);attached=b.get('receipt_ids',[])
            if not isinstance(attached,list) or len(attached)>5:raise ValueError('Attach at most five inspected tool receipts')
            context=[]
            for id in attached:
                if not isinstance(id,str):raise ValueError('Invalid tool receipt')
                r=self.store.state('tool-receipt',id)
                if not r:raise ValueError('Tool receipt no longer exists')
                context.append(r)
            if len(json.dumps(context).encode())>24000:raise ValueError('Attached tool evidence exceeds 24 KB; narrow the selection')
            id=uuid.uuid4().hex;clean=scrub(text,self.cloud.secrets());turn={'id':id,'session_id':s['id'],'provider':s['provider'],'model':s['model'],'at':now(),'state':'QUEUED','input':clean,'attached_receipts':context,'retry_of':retry,'requests':[],'tool_receipts':[],'usage':[]}
            if not retry:self.message(s,'user',clean,id,attached_receipt_ids=attached)
            self.store.state('chat-turn',id,turn);s['updated_at']=now();self.store.state('chat-session',s['id'],s);self.events[id]=threading.Event();future=self.pool.submit(self.work,id);future.add_done_callback(lambda f:self.worker_finished(id,f));return turn
    def worker_finished(self,id,future):
        if future.exception():
            t=self.store.state('chat-turn',id);t.update(state='FAILED',error='Conversation worker failed ('+type(future.exception()).__name__+'). Retained inputs remain available for an explicit retry.',completed_at=now());self.store.state('chat-turn',id,t);self.store.event('ERROR','CHAT_WORKER_FAILURE',type(future.exception()).__name__)
            with self.lock:self.events.pop(id,None)
    def work(self,id):
        turn=self.store.state('chat-turn',id);s=self.session(turn['session_id']);event=self.events[id];started=time.monotonic()
        def check():
            if event.is_set():raise Cancelled('Stopped waiting. No further requests or tool calls will start. A provider may still finish an already submitted request.')
            return self.ready(s)
        try:
            check();turn['state']='RUNNING';self.store.state('chat-turn',id,turn);c,a=check()
            if s['provider'] in ('manus','copilot-studio'):
                self.cloud.reserve(c);payload=turn['input']
                if turn['attached_receipts']:payload+='\nOwner-selected bounded evidence:\n'+json.dumps(turn['attached_receipts'],ensure_ascii=False)
                r=protocol.remote_send(a,s['remote_task_id'],payload);s['remote_task_id']=r['task_id'];self.store.state('chat-session',s['id'],s);turn.update(state='REMOTE_WAIT',remote_task_id=r['task_id'],message='Submitted to the real remote task. Use Inspect response; no response has been fabricated.',usage=[r.get('usage',{})]);check()
            else:
                history=self.detail(s['id'])['messages'];history=[m for m in history if m['role'] in ('user','assistant')][-20:]
                if turn['retry_of'] and (not history or history[-1]['text']!=turn['input']):history.append({'role':'user','text':turn['input']})
                while len(json.dumps(history).encode())>32000 and len(history)>1:history.pop(0)
                wire=protocol.initial(s['provider'],history)
                if turn['attached_receipts']:wire[-1]['content']+='\nOwner-selected bounded evidence:\n'+json.dumps(turn['attached_receipts'],ensure_ascii=False)
                contracts=[t for t in self.registry.contracts() if t['name'] in s['tools'] and t['enabled']];allowed={t['name'] for t in contracts}
                for iteration in range(3):
                    c,a=check();self.cloud.reserve(c);r=protocol.step(a,wire,contracts);r=scrub(r,self.cloud.secrets());turn['requests'].append({k:r.get(k) for k in ('http_status','response_id','model')});turn['usage'].append(r['usage']);check()
                    budget=self.store.state('cloud-budget',c['id']);budget['last_usage']=r['usage'];budget['reported_tokens']+=sum(int(r['usage'].get(k,0) or 0) for k in ('input_tokens','output_tokens','prompt_tokens','completion_tokens'));self.store.state('cloud-budget',c['id'],budget)
                    if not r['calls']:
                        m=self.message(s,'assistant',r['text'],id,reported_model=r['model'],usage=turn['usage'],tool_receipt_ids=turn['tool_receipts']);turn.update(state='COMPLETE',assistant_message_id=m['id']);break
                    if iteration==2:raise Blocked('Three-request conversation limit reached. Inspect the retained tool evidence and ask a narrower follow-up; no automatic continuation.')
                    items=[]
                    for call in r['calls']:
                        check()
                        if call['name'] not in allowed:raise Blocked('Provider requested a tool outside this conversation’s owner-approved scope')
                        receipt=self.registry.run(call['name'],call['arguments'],s['id']);turn['tool_receipts'].append(receipt['id']);items.append((call,receipt));self.store.state('chat-turn',id,turn)
                    protocol.results(s['provider'],wire,items)
                    if len(json.dumps(wire).encode())>100000:raise Blocked('Tool conversation exceeded the 100 KB bound; inspect receipts and narrow the query')
                c=self.cloud.config(s['provider']);c.update(state='CONNECTED',last_success=now());self.store.state('cloud',c['id'],c)
        except Cancelled as e:turn.update(state='CANCELLED',error=str(e))
        except Exception as e:
            message=scrub(str(e) if isinstance(e,(ValueError,Blocked)) else 'Conversation failed ('+type(e).__name__+'); inspect local diagnostics',self.cloud.secrets());turn.update(state='BLOCKED' if isinstance(e,Blocked) else 'FAILED',error=message,http_status=getattr(e,'status',None))
            if not isinstance(e,Blocked):self.cloud.failure(self.cloud.config(s['provider']),e)
        finally:
            turn.update(completed_at=now(),latency_ms=round((time.monotonic()-started)*1000,1));self.store.state('chat-turn',id,turn)
            with self.lock:self.events.pop(id,None)
    def cancel(self,id):
        with self.lock:
            t=self.store.state('chat-turn',id)
            if not t:raise ValueError('Response not found')
            if id in self.events:self.events[id].set();t.update(state='CANCELLING',message='Stopping after the current bounded request; no further tools or retries');self.store.state('chat-turn',id,t)
            elif t['state']=='REMOTE_WAIT' and t['provider']=='manus':
                s=self.session(t['session_id']);c,a=self.ready(s);self.cloud.reserve(c);t.update(a.inspect(s['remote_task_id'],True));t['state']='CANCELLED';self.store.state('chat-turn',id,t)
            elif t['state']=='REMOTE_WAIT':
                t.update(state='CANCELLED',message='Local response waiting stopped. This channel has no verified remote cancellation API; the remote agent may still finish.');self.store.state('chat-turn',id,t)
            return t
    def inspect_remote(self,id):
        with self.lock:
            s=self.session(id);c,a=self.ready(s)
            if not s.get('remote_task_id'):raise ValueError('No remote task exists for this conversation')
            self.cloud.reserve(c);r=scrub(a.inspect(s['remote_task_id']),self.cloud.secrets());seen=set(s.get('remote_seen',[]));added=[]
            for item in r.get('messages',[]):
                if s['provider']=='manus':
                    if item.get('type')!='assistant_message':continue
                    content=item.get('assistant_message',{}).get('content','');text=content if isinstance(content,str) else '\n'.join(x.get('text','') for x in content if isinstance(x,dict))
                else:
                    if item.get('type')!='message' or item.get('from',{}).get('id')=='dragonhydra-owner':continue
                    text=item.get('text','')
                digest=fingerprint(item)
                if text and digest not in seen:added.append(self.message(s,'assistant',text,'remote:'+digest,remote_task_id=s['remote_task_id']));seen.add(digest)
            s['remote_seen']=list(seen);s['updated_at']=now();self.store.state('chat-session',id,s);return {'added':len(added),'remote_state':r,'automatic_action_approval':False}
    def roundtable(self,b):
        providers=b.get('providers',[])
        if b.get('confirm_multiple_requests') is not True or not isinstance(providers,list) or not 2<=len(providers)<=5 or len(set(providers))!=len(providers):raise ValueError('Explicitly select two to five independent providers for separate requests')
        companies=['microsoft' if p in ('foundry','azure-openai','copilot-studio') else p for p in providers]
        if len(set(companies))!=len(companies):raise ValueError('Choose one Microsoft service per roundtable')
        result={'id':uuid.uuid4().hex,'at':now(),'question':scrub(b.get('text',''),self.cloud.secrets()),'responses':[],'comparison':'Independent responses to the same owner-selected evidence; agreement does not establish truth.'}
        for p in providers:
            try:
                s=self.create({'provider':p,'title':'Roundtable: '+result['question'][:90]});t=self.send({'session_id':s['id'],'text':result['question'],'receipt_ids':b.get('receipt_ids',[])});result['responses'].append({'provider':p,'session_id':s['id'],'turn_id':t['id'],'state':t['state']})
            except (ValueError,Blocked) as e:result['responses'].append({'provider':p,'state':'NOT_CONFIGURED' if not self.cloud.config(p)['enabled'] else 'BLOCKED','error':str(e)})
        self.store.state('chat-roundtable',result['id'],result);return result
    def close(self):
        with self.lock:
            self.closed=True
            for e in self.events.values():e.set()
        self.pool.shutdown(wait=True,cancel_futures=False)
