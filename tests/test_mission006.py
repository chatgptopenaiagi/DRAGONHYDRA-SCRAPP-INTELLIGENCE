import json,sys,tempfile,unittest,time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
from living.core import Runtime
from living.contracts import Blocked,fingerprint
from living.cloud_adapters import CATALOG,validate_endpoint
from living.cloud_manager import scrub
from living.sql_control import guard_state
from mission006_mock import Mock

class Mission006(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='dh006-tests-');self.m=Mock();self.rt=Runtime(self.tmp.name,mock_origins=(self.m.origin,));self.rt.set_mode('connected');self.cloud=self.rt.cloud
    def tearDown(self):self.rt.close();self.m.close();self.tmp.cleanup()
    def configure(self,id='openai'):
        self.cloud.configure({'id':id,'enabled':True,'endpoint':self.m.origin,'model':'mock-text-model'});self.cloud.credential({'id':id,'key':id+'-synthetic-credential-006'})
    def run_ai(self,id='openai'):
        p=self.cloud.preview({'id':id,'prompt':'Explain no facts beyond the evidence'});return self.cloud.run({'preview_id':p['id'],'fingerprint':p['fingerprint'],'confirm_share':True})
    def test_eight_independent_protocols(self):
        for id in CATALOG:
            self.configure(id);self.assertEqual(self.cloud.test(id)['state'],'CONNECTED');r=self.run_ai(id);self.assertIn(r['state'],('COMPLETE','REMOTE_TASK_CREATED'))
            if id in ('manus','copilot-studio'):self.assertEqual(self.cloud.inspect(r['id'])['state'],'REMOTE_PROGRESS')
        keys=[r['credential'] for r in self.m.calls];self.assertTrue(any('anthropic-synthetic' in x for x in keys));self.assertTrue(any('openai-synthetic' in x for x in keys))
    def test_no_secrets_in_metadata_receipts_or_backup(self):
        self.configure();self.m.echo=True;r=self.run_ai();serialized=json.dumps([self.cloud.list(),r]);self.assertNotIn('openai-synthetic-credential-006',serialized);self.assertIn('[REDACTED]',serialized);backup=self.rt.backup();self.assertNotIn(b'openai-synthetic-credential-006',next((Path(self.tmp.name)/'backups').glob('*.sqlite3')).read_bytes())
    def test_provider_binding_rejects_other_key(self):
        self.configure();a=self.cloud.config('openai');self.cloud.vault.path('anthropic').write_bytes(self.cloud.vault.path('openai').read_bytes());self.assertEqual(self.cloud.vault.status('anthropic',self.cloud.binding(self.cloud.config('anthropic'))),'REENTRY_REQUIRED')
    def test_offline_blocks_without_network(self):
        self.configure();self.rt.set_mode('offline')
        with self.assertRaises(Blocked):self.cloud.test('openai')
        self.assertEqual(self.m.calls,[])
    def test_local_allowed_offline(self):
        self.configure('local');self.rt.set_mode('offline');self.assertEqual(self.cloud.test('local')['state'],'CONNECTED')
    def test_approval_and_single_use_preview(self):
        self.configure();p=self.cloud.preview({'id':'openai','prompt':'hello'})
        with self.assertRaises(ValueError):self.cloud.run({'preview_id':p['id'],'fingerprint':p['fingerprint']})
        b={'preview_id':p['id'],'fingerprint':p['fingerprint'],'confirm_share':True};self.assertEqual(self.cloud.run(b)['state'],'COMPLETE')
        with self.assertRaises(ValueError):self.cloud.run(b)
    def test_changed_configuration_invalidates_preview(self):
        self.configure();p=self.cloud.preview({'id':'openai','prompt':'hello'});self.cloud.configure({'id':'openai','max_output_tokens':100})
        with self.assertRaises(ValueError):self.cloud.run({'preview_id':p['id'],'fingerprint':p['fingerprint'],'confirm_share':True})
        self.assertEqual(self.m.calls,[])
    def test_expired_preview(self):
        self.configure();p=self.cloud.preview({'id':'openai','prompt':'hello'});self.cloud.previews[p['id']]['expires_at']=0
        with self.assertRaises(ValueError):self.cloud.run({'preview_id':p['id'],'fingerprint':p['fingerprint'],'confirm_share':True})
    def test_budget_no_automatic_retry(self):
        self.configure();self.cloud.configure({'id':'openai','max_daily_requests':1});self.cloud.test('openai')
        with self.assertRaises(Blocked):self.cloud.test('openai')
        self.assertEqual(len(self.m.calls),1)
    def test_rate_limit_backoff(self):
        self.configure();self.m.status=429
        with self.assertRaises(ValueError):self.cloud.test('openai')
        self.assertEqual(self.cloud.config('openai')['state'],'RATE_LIMITED')
        with self.assertRaises(Blocked):self.cloud.test('openai')
        self.assertEqual(len(self.m.calls),1)
    def test_invalid_credentials_remove_and_restart(self):
        self.configure();self.cloud.credential({'id':'openai','key':'invalid-test-credential'})
        with self.assertRaises(ValueError):self.cloud.test('openai')
        self.assertEqual(self.cloud.config('openai')['state'],'AUTHENTICATION_FAILED');self.cloud.credential({'id':'openai'},True);self.assertFalse(self.cloud.config('openai')['enabled']);self.assertEqual(self.cloud.public(self.cloud.config('openai'))['credential_status'],'MISSING')
    def test_malformed_json(self):
        self.configure();self.m.malformed=True
        with self.assertRaisesRegex(ValueError,'malformed JSON'):self.cloud.test('openai')
    def test_recovery_retains_uncertain_request(self):
        self.configure();self.rt.store.state('cloud-receipt','crash',{'id':'crash','state':'RUNNING','at':'test'});self.rt.close();self.rt=Runtime(self.tmp.name,mock_origins=(self.m.origin,));self.cloud=self.rt.cloud;self.assertEqual(self.rt.store.state('cloud-receipt','crash')['state'],'INTERRUPTED');self.assertEqual(self.cloud.public(self.cloud.config('openai'))['credential_status'],'SAVED')
    def test_no_arbitrary_cloud_endpoint(self):
        for u in ('http://example.com','https://evil.example','https://api.openai.com@evil.example','https://api.openai.com/v1','https://api.openai.com?key=secret'):
            with self.assertRaises(ValueError):validate_endpoint('openai',u)
    def test_readonly_tools_reject_sql_and_unknown_fields(self):
        with self.assertRaises(ValueError):self.rt.evidence_tools.run('run_bounded_readonly_query',{'query_id':'DROP TABLE observations'})
        with self.assertRaises(ValueError):self.rt.evidence_tools.run('list_data_sources',{'sql':'SELECT * FROM secrets'})
        with self.assertRaises(ValueError):self.rt.evidence_tools.run('describe_table_schema',{'table':'component_state'})
        self.assertEqual(len(self.rt.evidence_tools.contracts()),11)
    def test_guard_blocks_before_driver(self):
        with patch('pyodbc.connect',side_effect=AssertionError('must not connect')):
            with self.assertRaises(Blocked):self.rt.sql.test()
        self.assertEqual(self.rt.sql.status()['state'],'BLOCKED')
    def test_readonly_guard_does_not_allow_writes(self):
        p=Path(self.tmp.name)/'fixture-guard.json';p.write_text(json.dumps({'status':'MAINTENANCE','sql_read_only_allowed':True}));self.assertTrue(guard_state(p)['allowed']);self.assertFalse(guard_state(p,True)['allowed'])
    def test_local_sql_only(self):
        with self.assertRaises(ValueError):self.rt.sql.configure({'server':'external.example'})
        with self.assertRaises(ValueError):self.rt.sql.configure({'database':'x;DROP DATABASE y'})
    def test_knowledge_offline_and_disabled(self):
        id=self.rt.knowledge.list()[0]['id'];self.rt.set_mode('offline')
        with self.assertRaises(Blocked):self.rt.knowledge.refresh(id)
        self.rt.set_mode('connected')
        with self.assertRaises(Blocked):self.rt.knowledge.refresh(id)
    def test_knowledge_is_not_observation(self):
        id=self.rt.knowledge.list()[0]['id'];d=self.rt.store.state('knowledge',id);d.update(enabled=True);self.rt.store.state('knowledge',id,d)
        with patch('living.net.request',return_value=(200,{'content-type':'text/html'},b'<h1>Fixture schema</h1><script>ignored</script><p>Verified document text</p>')):r=self.rt.knowledge.refresh(id)
        self.assertEqual(r['status'],'VERIFIED_RETRIEVAL');self.assertEqual(self.rt.store.summary()['observations'],0);self.assertNotIn('ignored',self.rt.knowledge.query(ids=[id])[0]['excerpt'])
    def test_scope_limits(self):
        with self.assertRaises(ValueError):self.cloud.preview({'id':'openai','prompt':'hello','observation_ids':['a']*21})
        with self.assertRaises(ValueError):self.cloud.preview({'id':'openai','prompt':'hello','tool':{'name':'inspect_sql_health'}})
    def test_source_secret_scrubbing(self):
        self.assertEqual(scrub({'api_key':'anything','ordinary':'sk-proj-'+'a'*30}),{'api_key':'[REDACTED]','ordinary':'[REDACTED]'})
    def test_credit_exhaustion_is_not_transient_rate_limit(self):
        from living.net import json_request,NetworkError
        response=(429,{},json.dumps({'error':{'code':'credit_balance_exhausted','type':'insufficient_quota'}}).encode())
        with patch('living.net.request',return_value=response):
            with self.assertRaises(NetworkError) as caught:json_request('https://api.openai.com','/v1/responses')
        self.assertEqual(caught.exception.code,'ACCOUNT_ALLOWANCE_EXHAUSTED');self.configure();self.cloud.failure(self.cloud.config('openai'),caught.exception);self.assertEqual(self.cloud.config('openai')['state'],'ACCOUNT_ALLOWANCE_EXHAUSTED')
    def test_all_new_http_mutations_require_authentication_and_csrf(self):
        import http.client,threading
        from living.server import Server
        s=Server(('127.0.0.1',0),self.rt,'synthetic-local-admin-006');t=threading.Thread(target=s.serve_forever);t.start()
        try:
            paths=['sql/'+x for x in ('configure','discover','test','inventory','provision','sync','backups','databases','schemas','tables','describe','query')]+['cloud/'+x for x in ('configure','credential','credential/remove','test','preview','run','inspect','stop')]+['knowledge/configure','knowledge/refresh','tools/run','provider/status']
            token,csrf=s.auth.exchange(s.auth.ticket())
            for path in paths:
                for cookie,expected in [(None,401),(token,403)]:
                    c=http.client.HTTPConnection('127.0.0.1',s.server_port);headers={'Content-Type':'application/json','Origin':s.origin}
                    if cookie:headers['Cookie']=s.cookie+'='+cookie
                    c.request('POST','/api/'+path,'{}',headers);r=c.getresponse();r.read();c.close();self.assertEqual(r.status,expected,path)
            self.assertIsNone(self.rt.store.state('sql','discovery'));self.assertEqual(self.m.calls,[])
        finally:s.shutdown();s.server_close();t.join()
if __name__=='__main__':unittest.main()
