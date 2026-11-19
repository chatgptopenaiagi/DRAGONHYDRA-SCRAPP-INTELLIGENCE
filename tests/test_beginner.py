import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'application')]
from living.storage import Store
from living.normalization import normalize
from living.analytics import calculate
from living.football_research import research
from living.postgres_control import PostgresControl
class BeginnerTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'intelligence.sqlite3')
    def tearDown(self):self.store.close();self.tmp.cleanup()
    def insert(self,rows,source='fixture'):
        config={'id':source,'kind':'NUMBER','unit':'unknown'};self.store.source({'id':source,'name':source,'adapter':'upload','origin':'SYNTHETIC','enabled':False});obs=[normalize(r,config,'SYNTHETIC') for r in rows];self.store.ingest(obs,{'id':source+str(len(rows)),'source_id':source});return obs
    def test_units_filter_and_mathematics(self):
        self.insert([{'key':'temperature','identity':'c1','value':'10','unit':'degC'},{'key':'temperature','identity':'c2','value':'20','unit':'degC'},{'key':'temperature','identity':'f1','value':'100','unit':'degF'}])
        with self.assertRaises(ValueError):calculate(self.store.query()['rows'])
        chosen=self.store.query({'unit':'degC'});self.assertEqual(chosen['total'],2);self.assertEqual(calculate(chosen['rows'])['output']['mean'],'15');self.assertEqual(sum(x['numeric_n'] for x in self.store.summary()['series']),3)
    def test_fictional_fixture_link_is_source_scoped(self):
        result={'key':'goals','value':3,'kind':'SPORTS_RESULT','unit':'goals','metadata':{'id':'m1','home':'Alpha','away':'Beta','hg':2,'ag':1,'competition':'TEST','season':'TEST','date':'2020-01-01'}}
        quote={'key':'home','value':'2.50','kind':'SPORTS_ODDS','unit':'decimal_odds','metadata':{'match_id':'m1','market':'1X2','outcome':'H','bookmaker':'TEST'}}
        self.insert([result,quote]);self.insert([quote],'other-fixture');r=research(self.store,{'search':'Alpha'});self.assertEqual(r['total'],1);self.assertEqual(len(r['rows'][0]['odds']),1);self.assertEqual(r['rows'][0]['odds'][0]['implied_percent'],'4E+1');self.assertIsNone(r['rows'][0]['odds'][0]['quote_time']);self.assertEqual(r['rows'][0]['origin'],'SYNTHETIC')
    def test_unknown_score_is_not_zero(self):
        self.insert([{'key':'fixture','kind':'SPORTS_RESULT','value':None,'metadata':{'home':'A','away':'B'}}]);r=research(self.store,{});self.assertIsNone(r['rows'][0]['home_goals']);self.assertIsNone(r['rows'][0]['date'])
    def test_research_bounds_and_no_silent_truncation(self):
        for f in ({'limit':51},{'offset':-1},{'unknown':'x'}):
            with self.assertRaises(ValueError):research(self.store,f)
        with patch.object(self.store,'query',return_value={'total':10001,'rows':[]}):
            with self.assertRaisesRegex(ValueError,'No records were silently omitted'):research(self.store,{})
    def test_constructor_does_not_rewrite_another_session_health(self):
        prior={'state':'CONNECTED','last_successful_query':'2020-01-01T00:00:00Z'};self.store.state('postgres','connection',prior);p=PostgresControl(self.store,Path(self.tmp.name));self.assertEqual(self.store.state('postgres','connection'),prior);p.configure({'enabled':True});self.assertEqual(p.status()['state'],'NOT_CHECKED');p._query_health={'state':'CONNECTED','last_successful_query':'2026-11-19T00:00:00Z'};other=PostgresControl(self.store,Path(self.tmp.name));self.assertEqual(p.status()['state'],'CONNECTED');self.assertEqual(other.status()['state'],'NOT_CHECKED')
    def test_help_and_preferences_require_correct_http_security(self):
        import http.client,threading
        from types import SimpleNamespace
        from living.server import Server
        server=Server(('127.0.0.1',0),SimpleNamespace(store=self.store),'SYNTHETIC-admin-test');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def call(method,path,body=None,headers=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port);c.request(method,path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json',**(headers or {})});r=c.getresponse();value=json.loads(r.read());c.close();return r.status,value
        try:
            code,manual=call('GET','/help.json');self.assertEqual(code,200);self.assertGreater(len(manual['topics']),20)
            self.assertEqual(call('GET','/api/preferences')[0],401)
            self.assertEqual(call('POST','/api/preferences',{'beginner':False})[0],401)
            token,csrf=server.auth.exchange(server.auth.ticket());headers={'Cookie':server.cookie+'='+token,'Origin':server.origin}
            self.assertEqual(call('POST','/api/preferences',{'beginner':False},headers)[0],403)
            headers['X-DH-CSRF']=csrf;self.assertEqual(call('POST','/api/preferences',{'beginner':False},headers)[0],200)
            self.assertFalse(call('GET','/api/preferences',headers=headers)[1]['beginner'])
            self.assertEqual(call('POST','/api/preferences',{'beginner':'false'},headers)[0],400)
            self.assertEqual(call('POST','/api/preferences',{'unknown':True},headers)[0],400)
            self.assertEqual(call('POST','/api/preferences',{'beginner':True},{**headers,'Origin':'https://example.invalid'})[0],403)
        finally:server.shutdown();thread.join();server.server_close()
if __name__=='__main__':unittest.main()
