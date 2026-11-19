import json,sys,tempfile,time,unittest,threading,http.client
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
from living.core import Runtime
from living.contracts import Blocked
from living.server import Server
from mission006_chat_mock import ChatMock

class Cockpit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='dh006-chat-test-');self.mock=ChatMock();self.rt=Runtime(self.tmp.name,'connected',mock_origins=(self.mock.origin,));self.chat=self.rt.conversations
    def tearDown(self):self.rt.close();self.mock.close();self.tmp.cleanup()
    def configure(self,p='openai'):
        self.rt.cloud.configure({'id':p,'enabled':True,'endpoint':self.mock.origin,'model':'mock-chat-model','max_daily_requests':50});self.rt.cloud.credential({'id':p,'key':p+'-distinct-synthetic-key'})
    def create(self,p='openai',tools=None):
        self.configure(p);return self.chat.create({'provider':p,'tools':tools or [],'allow_tool_sharing':True})
    def wait(self,t):
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            r=self.rt.store.state('chat-turn',t['id'])
            if r['state'] not in ('QUEUED','RUNNING','CANCELLING'):return r
            time.sleep(.03)
        self.fail('Conversation did not finish within test bound')
    def send(self,s,text='hello'):
        return self.wait(self.chat.send({'session_id':s['id'],'text':text}))
    def test_multiturn_all_synchronous_protocols(self):
        for p in ('openai','anthropic','xai','foundry','azure-openai','local'):
            s=self.create(p);self.assertEqual(self.send(s)['state'],'COMPLETE');self.assertEqual(self.send(s,'Remember my previous message')['state'],'COMPLETE');d=self.chat.detail(s['id']);self.assertEqual(len(d['messages']),4);self.assertEqual({m['provider'] for m in d['messages']},{p});body=self.mock.calls[-1]['body'];self.assertEqual(len(body.get('input',body.get('messages'))),4 if p in ('foundry','local') else 3)
    def test_real_tool_dispatch_for_six_wire_adapters(self):
        self.mock.tool='get_system_status'
        for p in ('openai','anthropic','xai','foundry','azure-openai','local'):
            s=self.create(p,['get_system_status']);r=self.send(s);self.assertEqual(r['state'],'COMPLETE',r);self.assertEqual(len(r['requests']),2);receipt=self.rt.store.state('tool-receipt',r['tool_receipts'][0]);self.assertEqual(receipt['state'],'PASS');self.assertEqual(receipt['output']['observations'],0);self.assertIn('tool evidence received',self.chat.detail(s['id'])['messages'][-1]['text'])
    def test_remote_followup_reuses_task_and_inspect_deduplicates(self):
        for p in ('manus','copilot-studio'):
            s=self.create(p);self.assertEqual(self.send(s)['state'],'REMOTE_WAIT');self.assertEqual(self.chat.inspect_remote(s['id'])['added'],1);self.assertEqual(self.chat.inspect_remote(s['id'])['added'],0);self.assertEqual(self.send(s,'follow up')['state'],'REMOTE_WAIT')
        paths=[x['path'] for x in self.mock.calls];self.assertEqual(paths.count('/v2/task.create'),1);self.assertEqual(paths.count('/v2/task.sendMessage'),1);self.assertEqual(paths.count('/v3/directline/conversations'),1)
    def test_unapproved_tool_never_executes(self):
        self.mock.tool='get_hardware_metrics';s=self.create();r=self.send(s);self.assertEqual(r['state'],'BLOCKED');self.assertEqual(self.rt.store.states('tool-receipt'),[])
    def test_disabled_tool_and_invalid_arguments(self):
        r=self.rt.registry;self.assertEqual(r.run('run_bounded_sql_select',{'query_id':'DROP TABLE observations'})['state'],'FAIL');r.enable('get_system_status',False);self.assertEqual(r.run('get_system_status',{})['state'],'BLOCKED');self.assertEqual(r.run('query_football_results',{'limit':100000})['state'],'FAIL')
    def test_owner_action_never_changes_data_or_starts_codex(self):
        r=self.rt.registry.run('request_engineering_diagnostic',{'instruction':'Inspect CSV error'});self.assertEqual(r['output']['state'],'AWAITING_OWNER');self.assertFalse(self.rt.store.states('engineering-job'));a=self.rt.registry.action(r['output']['id'],False);self.assertEqual(a['state'],'DECLINED')
    def test_cancel_suppresses_reply_and_subsequent_tools(self):
        self.mock.delay=.3;self.mock.tool='get_system_status';s=self.create(tools=['get_system_status']);t=self.chat.send({'session_id':s['id'],'text':'slow'});time.sleep(.1);self.chat.cancel(t['id']);r=self.wait(t);self.assertEqual(r['state'],'CANCELLED');self.assertEqual(len(self.mock.calls),1);self.assertFalse(self.rt.store.states('tool-receipt'));self.assertEqual(len(self.chat.detail(s['id'])['messages']),1)
    def test_cannot_send_duplicate_active_turn(self):
        self.mock.delay=.3;s=self.create();t=self.chat.send({'session_id':s['id'],'text':'one'})
        with self.assertRaises(Blocked):self.chat.send({'session_id':s['id'],'text':'two'})
        self.wait(t)
    def test_endpoint_model_binding_preserves_history(self):
        s=self.create();self.send(s);self.rt.cloud.configure({'id':'openai','model':'different'})
        with self.assertRaises(Blocked):self.chat.send({'session_id':s['id'],'text':'do not leak'})
        self.assertEqual(len(self.mock.calls),1)
    def test_secret_redaction_in_chat_backups_and_tool_receipts(self):
        s=self.create();self.mock.echo=True;r=self.send(s,'The secret is openai-distinct-synthetic-key');self.assertEqual(r['state'],'COMPLETE');d=self.chat.detail(s['id']);self.assertNotIn('openai-distinct-synthetic-key',json.dumps(d));self.rt.backup();self.assertNotIn(b'openai-distinct-synthetic-key',next((Path(self.tmp.name)/'backups').glob('*')).read_bytes())
    def test_rate_limit_no_retry_and_explicit_retry_after_recovery(self):
        s=self.create();self.mock.status=429;r=self.send(s);self.assertEqual(r['state'],'FAILED');self.assertEqual(len(self.mock.calls),1);self.mock.status=200;r2=self.wait(self.chat.send({'session_id':s['id'],'retry_turn':r['id']}));self.assertEqual(r2['state'],'BLOCKED');self.assertEqual(len(self.mock.calls),1);b=self.rt.store.state('cloud-budget','openai');b['retry_at']=0;self.rt.store.state('cloud-budget','openai',b);r3=self.wait(self.chat.send({'session_id':s['id'],'retry_turn':r['id']}));self.assertEqual(r3['state'],'COMPLETE');self.assertEqual(len(self.chat.detail(s['id'])['messages']),2)
    def test_account_no_credits_prevents_repeated_inference(self):
        s=self.create();c=self.rt.cloud.config('openai');c['state']='ACCOUNT_ALLOWANCE_EXHAUSTED';self.rt.store.state('cloud','openai',c)
        with self.assertRaises(Blocked):self.send(s)
        self.assertEqual(self.mock.calls,[])
    def test_offline_blocks_cloud_but_allows_local(self):
        s=self.create();local=self.create('local');self.rt.set_mode('offline')
        with self.assertRaises(Blocked):self.send(s)
        self.assertEqual(self.send(local)['state'],'COMPLETE')
    def test_restart_persists_history_dpapi_and_marks_interruption(self):
        s=self.create();self.send(s);self.rt.store.state('chat-turn','interrupted',{'id':'interrupted','session_id':s['id'],'state':'RUNNING','at':'z'});self.rt.close();self.rt=Runtime(self.tmp.name,'connected',mock_origins=(self.mock.origin,));self.chat=self.rt.conversations;self.assertEqual(len(self.chat.detail(s['id'])['messages']),2);self.assertEqual(self.rt.store.state('chat-turn','interrupted')['state'],'INTERRUPTED');self.assertEqual(self.rt.cloud.public(self.rt.cloud.config('openai'))['credential_status'],'SAVED');self.assertEqual(len(self.mock.calls),1)
    def test_search_and_provider_independence(self):
        a=self.create();b=self.create('anthropic');self.send(a,'Arsenal historical evidence');self.send(b,'Chelsea');matches=self.chat.list('Arsenal');self.assertEqual([s['id'] for s in matches],[a['id']]);keys=[x['key'] for x in self.mock.calls];self.assertIn('Bearer openai-distinct-synthetic-key',keys);self.assertIn('anthropic-distinct-synthetic-key',keys)
    def test_roundtable_explicit_and_separate(self):
        self.configure();self.configure('anthropic')
        with self.assertRaises(ValueError):self.chat.roundtable({'providers':['openai','anthropic'],'text':'hello'})
        r=self.chat.roundtable({'providers':['openai','anthropic','xai'],'text':'Compare the same question','confirm_multiple_requests':True});self.assertEqual(r['responses'][2]['state'],'NOT_CONFIGURED');self.assertEqual(len({x['session_id'] for x in r['responses'][:2]}),2)
        for x in r['responses'][:2]:self.assertEqual(self.wait({'id':x['turn_id']})['state'],'COMPLETE')
    def test_sql_guard_blocks_before_driver(self):
        with patch('living.postgres_control.PostgresControl.connect',wraps=self.rt.postgres.connect) as call:
            r=self.rt.registry.run('run_bounded_postgresql_select',{'table':'observations'});self.assertEqual(r['state'],'BLOCKED');self.assertIn('disabled',r['error']);self.assertEqual(call.call_count,1)
    def test_hardware_matches_independent_memory_and_process(self):
        import os,psutil
        h=self.rt.hardware.sample();self.assertEqual(h['status'],'MEASURED');self.assertEqual(h['ram']['total_bytes'],psutil.virtual_memory().total);self.assertTrue(any(p['pid']==os.getpid() for p in h['processes']));self.assertEqual(h['cpu']['temperature']['status'],'UNAVAILABLE')
    def test_mcp_readonly_protocol_and_scoped_credential(self):
        e=self.rt.extensions;self.assertFalse(e.authorized(e.secret));e.configure(True,'http://127.0.0.1:12345');self.assertTrue(e.authorized(e.secret));self.assertFalse(e.authorized('bad'));init=e.call({'jsonrpc':'2.0','id':1,'method':'initialize','params':{}});self.assertEqual(init['result']['protocolVersion'],'2025-06-18');lst=e.call({'jsonrpc':'2.0','id':2,'method':'tools/list'})['result']['tools'];self.assertTrue(all(not x['name'].startswith('request_') for x in lst));r=e.call({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'get_system_status'}});self.assertFalse(r['result']['isError']);self.assertIn('error',e.call({'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'request_database_sync'}}))
    def test_new_routes_reject_unauthenticated_and_missing_csrf(self):
        server=Server(('127.0.0.1',0),self.rt,'synthetic-admin-secret');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();paths=['chat/create','chat/send','chat/cancel','chat/inspect','chat/roundtable','registry/run','registry/enable','registry/action','engineering/configure','engineering/connect','engineering/submit','extensions/configure']
        try:
            token,csrf=server.auth.exchange(server.auth.ticket())
            for path in paths:
                for cookie,expected in [('',401),(server.cookie+'='+token,403)]:
                    c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('POST','/api/'+path,'{}',{'Content-Type':'application/json','Cookie':cookie,'Origin':server.origin});r=c.getresponse();r.read();self.assertEqual(r.status,expected,path);c.close()
        finally:server.shutdown();server.server_close();thread.join()
    def test_engineering_never_spawns_and_cannot_cross_workspace(self):
        with patch('living.codex_bridge.RPC') as rpc:
            with self.assertRaises(Blocked):self.rt.engineering.submit('Inspect state')
            rpc.assert_not_called()
        from living.codex_bridge import Engineering
        class Client:
            def call(self,*args):return {'thread':{'cwd':'C:/unrelated-project'}}
        with self.assertRaises(Blocked):self.rt.engineering.metadata(Client(),{'thread_id':'test','workspace':self.tmp.name})
    def test_launcher_refuses_older_version_before_mode_or_state_changes(self):
        from living.launcher import ensure
        with patch('living.launcher.running',return_value={'version':'0.2.0-beta.2','mode':'connected'}),patch('living.launcher.request') as request:
            with self.assertRaisesRegex(ValueError,'already served'):ensure(self.tmp.name,0,'offline')
            request.assert_not_called()
    def test_known_secrets_removed_before_owner_action_persistence(self):
        self.configure();secret='openai-distinct-synthetic-key';r=self.rt.registry.run('request_engineering_diagnostic',{'instruction':'Never send '+secret});self.assertEqual(r['state'],'PASS');self.assertNotIn(secret,json.dumps(self.rt.store.states('owner-action')));self.assertNotIn(secret,self.rt.engineering.sanitize('Never send '+secret))
    def test_channel_stop_explains_remote_cancellation_limit(self):
        s=self.create('copilot-studio');t=self.send(s);before=len(self.mock.calls);r=self.chat.cancel(t['id']);self.assertEqual(r['state'],'CANCELLED');self.assertIn('no verified remote cancellation',r['message']);self.assertEqual(len(self.mock.calls),before)
    def test_mcp_http_auth_origin_and_endpoint_scope(self):
        server=Server(('127.0.0.1',0),self.rt,'synthetic-admin-secret');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.rt.extensions.configure(True,server.origin)
        def call(path,headers,body):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request('POST',path,json.dumps(body),{'Content-Type':'application/json',**headers});r=c.getresponse();data=json.loads(r.read());c.close();return r.status,data
        try:
            body={'jsonrpc':'2.0','id':1,'method':'tools/list'};key={'X-DH-MCP':self.rt.extensions.secret}
            self.assertEqual(call('/api/mcp',{},body)[0],401);self.assertEqual(call('/api/mcp',key|{'Origin':'https://unrelated.invalid'},body)[0],403);status,data=call('/api/mcp',key,body);self.assertEqual(status,200);self.assertTrue(data['result']['tools']);self.assertEqual(call('/api/chat/create',key,{'provider':'openai'})[0],401);status,data=call('/api/mcp',key,{'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'request_database_sync'}});self.assertIn('error',data)
        finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
