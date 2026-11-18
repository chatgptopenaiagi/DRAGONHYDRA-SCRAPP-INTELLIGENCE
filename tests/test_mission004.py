"""Isolated behavioral acceptance: real SQLite/HTTP, independent numerical expectations."""
import base64,http.client,json,os,socket,sqlite3,sys,tempfile,threading,time,unittest,zipfile,io
from contextlib import closing
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.storage import Store
from living.normalization import normalize,convert,timestamp
from living.analytics import calculate,correlate,evaluate,odds,sentiment
from living.acquisition import parse,validate_source,Acquisition
from unittest.mock import patch
from living.security import Sessions
from living.core import Runtime
from living.server import Server
from living.launcher import Lease,restore
from living.connectors import sql_connect
from living.contracts import Blocked,Cancelled

SOURCE={'id':'fixture','adapter':'upload','mapping':{},'origin':'IMPORTED'}
def row(value,**kw):return normalize({'key':'temperature','value':value,'unit':'degC',**kw},SOURCE)
class DataTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.data=Path(self.tmp.name);self.s=Store(self.data/'intelligence.sqlite3')
    def tearDown(self):self.s.close();self.tmp.cleanup()
    def test_atomic_duplicate_receipt(self):
        r=row('0.1');self.s.ingest([r],{'id':'a'});self.assertEqual(self.s.ingest([r],{'id':'b'})['duplicates'],1);self.assertEqual(self.s.ingest([r],{'id':'a'})['inserted'],1);self.assertEqual(self.s.summary()['observations'],1)
    def test_cancel_rolls_back_batch(self):
        calls=[False,True]
        with self.assertRaises(Cancelled):self.s.ingest([row(1),row(2)],{'id':'a'},lambda:calls.pop(0))
        self.assertEqual(self.s.summary()['observations'],0);self.assertIsNone(self.s.receipt('a'))
    def test_immutable_original(self):
        self.s.ingest([row(1)],{'id':'a'})
        with self.assertRaises(sqlite3.IntegrityError):self.s.c.execute('UPDATE observations SET series=?',('tamper',))
        self.s.c.rollback()
        with self.assertRaises(sqlite3.IntegrityError):self.s.c.execute('DELETE FROM observations')
        self.s.c.rollback()
    def test_conflicting_identity_retains_originals(self):
        self.s.ingest([row(1,identity='event'),row(2,identity='event')],{'id':'a'});self.assertEqual(self.s.summary()['observations'],2);self.assertEqual(self.s.receipt('a')['conflicts'],1)
    def test_future_schema_rejected_unchanged(self):
        p=self.data/'future.sqlite3'
        with closing(sqlite3.connect(p)) as c:c.executescript("CREATE TABLE metadata(key PRIMARY KEY,value); INSERT INTO metadata VALUES('owner','dragonhydra.living-intelligence'); PRAGMA user_version=99;")
        original=p.read_bytes()
        with self.assertRaises(ValueError):Store(p)
        self.assertEqual(p.read_bytes(),original)
    def test_migrate_schema1(self):
        self.s.c.execute('PRAGMA user_version=1');self.s.close();self.s=Store(self.data/'intelligence.sqlite3');self.assertEqual(self.s.summary()['schema'],2)
    def test_backup_and_restore(self):
        self.s.ingest([row(1)],{'id':'a'});backup=self.data/'saved.sqlite3';self.s.backup(backup);self.s.ingest([row(2)],{'id':'b'});self.s.close();restore(self.data,backup);self.s=Store(self.data/'intelligence.sqlite3');self.assertEqual(self.s.summary()['observations'],1);self.assertTrue(list((self.data/'backups').glob('before-restore-*')))
    def test_unknown_time_not_invented(self):
        r=row(1);self.assertIsNone(r['observed_at']);self.assertTrue(r['quality']['missing_observation_time'])
    def test_import_cannot_self_verify(self):
        r=row(1,origin='COLLECTED',verification='VERIFIED');self.assertEqual(r['origin'],'IMPORTED')
    def test_invalid_numerics(self):
        for value in ['NaN','Infinity',True,'bad']:
            with self.subTest(value=value),self.assertRaises(ValueError):row(value)
    def test_timezone_and_forecast(self):
        self.assertEqual(timestamp('2020-01-01T12:00:00+02:00'),'2020-01-01T10:00:00Z')
        with self.assertRaises(ValueError):timestamp('2020-01-01')
        with self.assertRaises(ValueError):row(12,kind='WEATHER_FORECAST',issue_at='2020-01-02T00:00:00Z',valid_at='2020-01-01T00:00:00Z')
    def test_units_derived_not_rewritten(self):self.assertEqual(convert('32','degF','degC'),'0');self.assertEqual(convert('36','km/h','m/s'),'1E+1')
    def test_task_recovered_after_restart(self):
        id=self.s.task({'source_id':'a'});self.s.task_update(id,'RUNNING',42);self.s.close();self.s=Store(self.data/'intelligence.sqlite3');self.assertEqual(self.s.tasks()[0]['state'],'INTERRUPTED')
    def test_source_single_worker(self):
        self.s.task({'source_id':'a'})
        with self.assertRaises(ValueError):self.s.task({'source_id':'a'})
    def test_config_validation(self):
        for conf in [dict(SOURCE,interval=1),dict(SOURCE,password='secret'),dict(SOURCE,origin='VERIFIED'),dict(SOURCE,adapter='http',location='http://localhost/',approved=False)]:
            with self.assertRaises(ValueError):validate_source(conf)
    def test_real_task_validation_and_commit(self):
        self.s.source(validate_source(SOURCE));a=Acquisition(self.s,self.data);id=a.submit('fixture',base64.b64encode(b'key,value,unit\ntemp,12,degC\n').decode(),'actual.csv');a.execute(self.s.tasks()[0]);self.assertEqual(self.s.tasks()[0]['state'],'COMPLETE');self.assertEqual(self.s.summary()['observations'],1)
    def test_invalid_batch_is_not_partially_saved(self):
        self.s.source(validate_source(SOURCE));a=Acquisition(self.s,self.data);a.submit('fixture',base64.b64encode(b'key,value\ntemp,12\ntemp,bad\n').decode(),'actual.csv');a.execute(self.s.tasks()[0]);self.assertEqual(self.s.tasks()[0]['state'],'FAILED');self.assertEqual(self.s.summary()['observations'],0)
    def test_source_content_tampering_rejected(self):
        self.s.source(validate_source(SOURCE));a=Acquisition(self.s,self.data);a.submit('fixture',base64.b64encode(b'key,value\ntemp,12\n').decode(),'actual.csv');t=self.s.tasks()[0];Path(t['payload']['staged_file']).write_text('key,value\ntemp,99\n');a.execute(t);self.assertEqual(self.s.summary()['observations'],0)
    def test_closed_sql_guard_never_calls_connector(self):
        p=self.data/'guard.json';p.write_text('{"status":"WAITING_MAINTENANCE_WINDOW","sql_tests_allowed":false}')
        with self.assertRaises(Blocked):sql_connect(p,lambda:self.fail('SQL connector must not be called'))
    def test_offline_blocks_http_before_transport(self):
        src=validate_source({'id':'api','adapter':'http','location':'https://example.org/data','approved':True});self.s.source(src);a=Acquisition(self.s,self.data);a.submit('api')
        with patch('intelligence.acquisition.fetch_public',side_effect=AssertionError('No network permitted')):a.execute(self.s.tasks()[0])
        self.assertEqual(self.s.tasks()[0]['state'],'BLOCKED')
    def test_connected_receipt_preserves_transport_hash(self):
        src=validate_source({'id':'api','adapter':'http','location':'https://example.org/data','approved':True});self.s.source(src);a=Acquisition(self.s,self.data,'connected');a.submit('api')
        with patch('intelligence.acquisition.fetch_public',return_value=(b'[{"key":"x","value":12}]',{'etag':'fixture-v1'},src['location'])):a.execute(self.s.tasks()[0])
        self.assertEqual(self.s.query()['rows'][0]['origin'],'COLLECTED');self.assertEqual(self.s.tasks()[0]['result']['dataset_version'],'fixture-v1')
    def test_legacy_receipt_keeps_synthetic_provenance(self):
        self.s.source(validate_source({'id':'legacy','adapter':'legacy','location':'isolated-fixture'}));a=Acquisition(self.s,self.data);a.submit('legacy')
        with patch('living.connectors.legacy_rows',return_value=([{'key':'x','value':1,'_legacy_synthetic':True}],{'dataset_fingerprint':'fixture'})):a.execute(self.s.tasks()[0])
        receipt=self.s.tasks()[0]['result'];self.assertEqual(receipt['origin'],'SYNTHETIC');self.assertEqual(receipt['observation_origins'],{'SYNTHETIC':1})
    def test_http_retries_are_bounded(self):
        from intelligence.acquisition import HTTPFailure
        src=validate_source({'id':'api','adapter':'http','location':'https://example.org/data','approved':True});self.s.source(src);a=Acquisition(self.s,self.data,'connected');a.submit('api')
        with patch('intelligence.acquisition.fetch_public',side_effect=HTTPFailure(503)) as fetch,patch.object(a.stop,'wait',return_value=False):a.execute(self.s.tasks()[0])
        self.assertEqual(fetch.call_count,3);self.assertEqual(self.s.tasks()[0]['state'],'FAILED')
    def test_local_ai_scoped_fixture_does_not_write_observations(self):
        from http.server import HTTPServer,BaseHTTPRequestHandler
        from living.connectors import local_ai
        captured=[]
        class FakeModel(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                captured.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));body=b'{"choices":[{"message":{"content":"Fixture interpretation, not an observation"}}]}'
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=HTTPServer(('127.0.0.1',0),FakeModel);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            result=local_ai({'enabled':True,'endpoint':f'http://127.0.0.1:{server.server_port}/v1/chat/completions','model':'explicit-fixture'},{'rows':[row(7)]})
            self.assertEqual(result['classification'],'AI_INTERPRETATION');self.assertEqual(captured[0]['model'],'explicit-fixture');self.assertEqual(self.s.summary()['observations'],0)
        finally:server.shutdown();server.server_close();thread.join()
class ParserTests(unittest.TestCase):
    def test_csv_tsv_json_jsonl(self):
        for name,data in [('a.csv',b'key,value\nx,1\n'),('a.tsv',b'key\tvalue\nx\t1\n'),('a.json',b'[{"key":"x","value":"1"}]'),('a.jsonl',b'{"key":"x","value":"1"}\n')]:self.assertEqual(str(parse(data,name)[0]['value']),'1')
    def test_xml_and_html(self):
        self.assertEqual(parse(b'<rows><row><key>x</key><value>1</value></row></rows>','a.xml')[0]['value'],'1')
        self.assertEqual(parse(b'<table><tr><th>key</th><th>value</th></tr><tr><td>x</td><td>1</td></tr></table>','a.html')[0]['value'],'1')
    def test_xml_entities_rejected(self):
        with self.assertRaises(ValueError):parse(b'<!DOCTYPE foo><rows/>','a.xml')
    def test_xlsx_sparse_columns(self):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w') as z:z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1" t="inlineStr"><is><t>key</t></is></c><c r="C1" t="inlineStr"><is><t>value</t></is></c></row><row><c r="A2" t="inlineStr"><is><t>x</t></is></c><c r="C2"><v>1.25</v></c></row></sheetData></worksheet>')
        self.assertEqual(parse(stream.getvalue(),'a.xlsx')[0]['value'],'1.25')
class MathTests(unittest.TestCase):
    def test_reference_statistics(self):
        result=calculate([row(v) for v in [1,2,3,4,5]],{'window':3})['output'];self.assertEqual(result['mean'],'3');self.assertAlmostEqual(float(result['population_sd']),2**.5);self.assertEqual(result['moving_average'],['1','1.5','2','3','4']);self.assertEqual(sum(result['histogram']['bins']),5)
    def test_reproducible_analysis_id(self):
        rows=[row(i) for i in range(5)];self.assertEqual(calculate(rows)['id'],calculate(rows)['id'])
    def test_mixed_units_rejected(self):
        with self.assertRaises(ValueError):calculate([row(1),row(2,unit='m/s')])
    def test_correlation_known_timestamps(self):
        a=[row(i,observed_at=f'2020-01-0{i}T00:00:00Z') for i in [1,2,3]];b=[row(i*2,observed_at=f'2020-01-0{i}T00:00:00Z') for i in [1,2,3]];self.assertAlmostEqual(correlate(a,b)['r'],1)
        with self.assertRaises(ValueError):correlate([row(1)],b)
    def test_prediction_reference(self):self.assertAlmostEqual(evaluate([.8,.2],[1,0])['brier'],.04)
    def test_core_probability(self):self.assertEqual(odds('2.5')['implied_probability'],'0.4')
    def test_sentiment_abstention(self):self.assertEqual(sentiment(normalize({'kind':'SHORT_TEXT','text':'gut','metadata':{'language':'de'}},SOURCE))['label'],'uncertain')
class SessionTests(unittest.TestCase):
    def test_ticket_one_use_and_expiry(self):
        clock=[100];s=Sessions('x'*64,clock=lambda:clock[0]);code=s.ticket();s.exchange(code)
        with self.assertRaises(PermissionError):s.exchange(code)
        code=s.ticket();clock[0]+=46
        with self.assertRaises(PermissionError):s.exchange(code)
    def test_session_expiration_revocation(self):
        clock=[100];s=Sessions('x'*64,clock=lambda:clock[0],ttl=30);token,csrf=s.exchange(s.ticket());self.assertTrue(s.get(token));clock[0]+=31;self.assertIsNone(s.get(token));token,csrf=s.exchange(s.ticket());s.revoke(token);self.assertIsNone(s.get(token))
class HttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.rt=Runtime(self.tmp.name);self.server=Server(('127.0.0.1',0),self.rt,'x'*64,'b'*64);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.origin=self.server.origin
    def tearDown(self):self.server.shutdown();self.thread.join();self.server.server_close();self.rt.close();self.tmp.cleanup()
    def req(self,path,body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_address[1]);h={'Content-Type':'application/json',**(headers or {})};c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,h);r=c.getresponse();data=r.read();head=dict(r.getheaders());code=r.status;c.close();return code,data,head
    def login(self):
        code,body,headers=self.req('/api/session-ticket',{}, {'X-DH-Local':'x'*64});ticket=json.loads(body)['ticket'];code,body,headers=self.req('/auth/exchange',{'ticket':ticket},{'Origin':self.origin});return headers['Set-Cookie'].split(';')[0],json.loads(body)['csrf']
    def test_unauthorized_and_host_rejected(self):self.assertEqual(self.req('/api/status')[0],401);self.assertEqual(self.req('/api/status',headers={'Host':'evil.example'})[0],403)
    def test_session_cookie_and_csrf(self):
        cookie,csrf=self.login();self.assertEqual(self.req('/api/status',headers={'Cookie':cookie})[0],200);self.assertEqual(self.req('/api/backup',{}, {'Cookie':cookie,'Origin':self.origin})[0],403);self.assertEqual(self.req('/api/backup',{}, {'Cookie':cookie,'Origin':self.origin,'X-DH-CSRF':csrf})[0],200)
    def test_cross_origin_same_host_other_port(self):self.assertEqual(self.req('/api/status',headers={'Origin':'http://127.0.0.1:1','X-DH-Local':'x'*64})[0],403)
    def test_logout_revokes(self):
        cookie,csrf=self.login();self.assertEqual(self.req('/api/logout',{}, {'Cookie':cookie,'Origin':self.origin,'X-DH-CSRF':csrf})[0],200);self.assertEqual(self.req('/api/status',headers={'Cookie':cookie})[0],401)
    def test_security_headers(self):
        code,body,headers=self.req('/');self.assertEqual(code,200);self.assertIn("frame-ancestors 'none'",headers['Content-Security-Policy']);self.assertEqual(headers['Referrer-Policy'],'no-referrer')
    def test_bridge_can_only_read_scoped_endpoints(self):
        self.assertEqual(self.req('/api/status',headers={'X-DH-Bridge':'b'*64})[0],200);self.assertEqual(self.req('/api/backup',{},headers={'X-DH-Bridge':'b'*64})[0],403);self.assertEqual(self.req('/api/session-ticket',{},headers={'X-DH-Bridge':'b'*64})[0],403);self.assertEqual(self.req('/api/analyses',headers={'X-DH-Bridge':'b'*64})[0],403)
    def test_port_conflict_does_not_replace(self):
        with self.assertRaises(OSError):Server(self.server.server_address,self.rt,'y'*64)
    def test_dataset_lease(self):
        with Lease(Path(self.tmp.name)/'test.lock'):
            with self.assertRaises(RuntimeError):
                with Lease(Path(self.tmp.name)/'test.lock'):pass
if __name__=='__main__':unittest.main(verbosity=2)
