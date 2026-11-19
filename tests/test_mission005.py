import base64,json,sqlite3,sys,tempfile,time,unittest,hashlib,os
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.csv_import import read_csv,suggestions,mapped_rows,decimal
from living.storage import Store
from living.acquisition import Acquisition
from living.credentials import Vault
from living.provider_manager import ProviderManager
from living.contracts import Blocked
from living.football_providers import ADAPTERS
from living.football_comparison import compare,save_alias
from football_mock import Mock,payload

class CsvTests(unittest.TestCase):
    def mapped(self,raw,options=None):
        p=read_csv(raw);o=suggestions(p['headers']);o.update(options or {});return mapped_rows(p,o,{'id':'fixture','origin':'SYNTHETIC'})
    def test_utf8_bom_quoted_and_line_endings(self):
        rows,e=self.mapped('\ufeffkey;value;text\r\n"a;b";2;"line1\nline2"\r\n'.encode());self.assertFalse(e);self.assertEqual(rows[0]['key'],'a;b')
    def test_windows_encoding(self):
        p=read_csv('key,value\nMünchen,2\n'.encode('cp1252'));self.assertEqual(p['encoding'],'cp1252');self.assertTrue(p['warnings']);self.assertEqual(p['rows'][0][1]['key'],'München')
    def test_tab_header_spaces_decimal_comma(self):
        p=read_csv('Measurement name\tMeasurement value\na\t1,25\n'.encode());o=suggestions(p['headers']);o.update(mapping={'key':'Measurement name','value':'Measurement value'},decimal=',');r,e=mapped_rows(p,o,{'id':'x'});self.assertFalse(e);self.assertEqual(r[0]['value'],'1.25')
    def test_explicit_grouping(self):
        self.assertEqual(decimal('1.234,50',{'decimal':',','thousands':'.'}),'1234.50')
        with self.assertRaises(ValueError):decimal('12,34.5',{'decimal':'.','thousands':','})
    def test_missing_invalid_physical_lines(self):
        rows,e=self.mapped(b'value,key\n1,a\n,b\ninvalid,c\n');self.assertEqual([x['row'] for x in e],[3,4])
    def test_bad_quotes_duplicate_headers_extra_cells(self):
        with self.assertRaises(ValueError):read_csv(b'value,key\n"unterminated,a')
        with self.assertRaises(ValueError):read_csv(b'value,value\n1,2')
        self.assertEqual(read_csv(b'value,key\n1,a,x')['errors'][0]['row'],2)
    def test_limits_no_truncation(self):
        with patch('living.csv_import.MAX_ROWS',2):
            with self.assertRaises(ValueError):read_csv(b'value\n1\n2\n3')
        with patch('living.csv_import.MAX_BYTES',3):
            with self.assertRaises(ValueError):read_csv(b'value\n1')
    def test_dates_not_timestamps(self):
        p=read_csv(b'Date,HomeTeam,AwayTeam,FTHG,FTAG,B365H,B365D,B365A\n01/02/2020,A,B,2,1,2.5,3.2,3.4');o=suggestions(p['headers']);r,e=mapped_rows(p,o,{'id':'csv'});self.assertFalse(e);self.assertEqual(len(r),4);self.assertTrue(all(x['observed_at'] is None for x in r));self.assertEqual(r[0]['metadata']['date'],'2020-02-01');self.assertEqual(r[1]['metadata']['bookmaker'],'Bet365')
    def test_owner_champs_profile(self):
        path=os.environ.get('DH_ACCEPTANCE_CSV')
        if not path:self.skipTest('Private genuine champs.csv is not distributed; set DH_ACCEPTANCE_CSV for owner-file acceptance')
        p=read_csv(Path(path).read_bytes());r,e=mapped_rows(p,suggestions(p['headers']),{'id':'champs'});self.assertEqual(len(r),217);self.assertFalse(e);self.assertEqual(sum('score_note' in x['metadata'] for x in r),3)
    def test_impossible_date_rejected(self):
        _,e=self.mapped(b'Date,value\n2020-02-31,1');self.assertEqual(e[0]['field'],'date')

class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='dh005-test-');self.data=Path(self.temp.name);self.store=Store(self.data/'intelligence.sqlite3');self.worker=Acquisition(self.store,self.data);self.source={'id':'test','adapter':'upload','name':'Fixture','kind':'NUMBER','unit':'m','origin':'SYNTHETIC','mapping':{}};self.store.source(self.source)
    def tearDown(self):self.worker.close();self.store.close();self.temp.cleanup()
    def draft(self,content=b'value\n1\n2'):
        d=self.worker.csv.preview({'filename':'fixture.csv','content':base64.b64encode(content).decode()});return self.worker.csv.validate({'draft_id':d['id'],'source_id':'test','options':d['suggested']})
    def test_atomic_duplicate_and_receipt(self):
        d=self.draft();task=self.worker.csv.confirm({'draft_id':d['id'],'validation_id':d['validation_id']});self.worker.execute(self.store.tasks()[0]);self.assertEqual(self.store.query()['total'],2)
        d=self.draft();self.worker.csv.confirm({'draft_id':d['id'],'validation_id':d['validation_id']});self.worker.execute(self.store.tasks()[0]);self.assertEqual(self.store.query()['total'],2);self.assertEqual(self.store.tasks()[0]['result']['duplicates'],2)
    def test_invalid_draft_never_commits(self):
        d=self.draft(b'value\n1\ninvalid');self.assertEqual(d['state'],'INVALID')
        with self.assertRaises(ValueError):self.worker.csv.confirm({'draft_id':d['id'],'validation_id':d['validation_id']})
        self.assertEqual(self.store.query()['total'],0)
    def test_staged_hash_change_rejected(self):
        d=self.draft();stored=self.worker.csv.get(d['id']);Path(stored['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.worker.csv.confirm({'draft_id':d['id'],'validation_id':d['validation_id']})
    def test_cancel_and_resume(self):
        d=self.draft();id=self.worker.csv.confirm({'draft_id':d['id'],'validation_id':d['validation_id']})['task_id'];self.worker.cancelled.add(id);self.worker.execute(self.store.tasks()[0]);self.assertEqual(self.store.tasks()[0]['state'],'CANCELLED');self.assertEqual(self.store.query()['total'],0);self.worker.resume(id);self.worker.execute(self.store.tasks()[0]);self.assertEqual(self.store.query()['total'],2)
    def test_backup_keeps_drafts_and_no_plaintext_credentials(self):
        d=self.draft();v=Vault(self.data);v.save(1,'fixture','SYNTHETIC-secret-for-test');path=self.data/'backup.sqlite3';self.store.backup(path)
        with closing(sqlite3.connect(path)) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM component_state WHERE scope="csv"').fetchone()[0],1)
        self.assertNotIn(b'SYNTHETIC-secret-for-test',path.read_bytes());self.assertNotIn(b'SYNTHETIC-secret-for-test',v.path(1).read_bytes());self.assertEqual(v.status(1,'fixture'),'SAVED');self.assertEqual(v.status(1,'other'),'REENTRY_REQUIRED');self.assertEqual(v.status(2,'fixture'),'MISSING');v.remove(1);self.assertEqual(v.status(1,'fixture'),'MISSING')
    def test_tampered_vault_fails_closed(self):
        v=Vault(self.data);v.save(1,'x','SYNTHETIC-test-secret');raw=bytearray(v.path(1).read_bytes());raw[-4]^=1;v.path(1).write_bytes(raw);self.assertEqual(v.status(1,'x'),'REENTRY_REQUIRED')
    def test_calendar_query_order_does_not_invent_times(self):
        from living.normalization import normalize
        rows=[normalize({'key':'x','value':v,'metadata':{'date':d}},self.source) for v,d in [(2,'2020-02-01'),(1,'2020-01-01')]];self.store.ingest(rows,{'id':'calendar'});result=self.store.query()['rows'];self.assertEqual([x['value'] for x in result],['1','2']);self.assertTrue(all(x['observed_at'] is None for x in result))
    def test_cross_provider_comparison_preserves_ambiguity(self):
        from living.football_contracts import match
        from living.normalization import normalize
        rows=[]
        for source,home in [('a','Alpha'),('b','ALPHA'),('c','Alpha FC')]:
            r=match('one',home,'Beta','2020-01-01','FINAL',(2,1),{},'League','2020');rows.append(normalize(r,{'id':source},'SYNTHETIC'))
        self.store.ingest(rows,{'id':'matches'});result=compare(self.store,{});self.assertEqual(sorted(len(g['records']) for g in result['groups']),[1,2]);self.assertEqual(self.store.query()['total'],3)
        save_alias(self.store,{'scope':'team','source':'c','original':'Alpha FC','canonical':'Alpha'});result=compare(self.store,{});self.assertEqual(len(result['groups']),1);self.assertEqual(result['groups'][0]['status'],'AGREEMENT_CANDIDATE');self.assertEqual(self.store.query()['total'],3)

class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='dh005-provider-');self.data=Path(self.temp.name);self.store=Store(self.data/'intelligence.sqlite3');self.worker=Acquisition(self.store,self.data,'connected');self.mocks=[Mock(i) for i in range(1,7)];self.pm=ProviderManager(self.store,self.data,self.worker,[m.origin for m in self.mocks]);self.worker.providers=self.pm
        for i,m in enumerate(self.mocks,1):
            self.pm.configure({'slot':str(i),'enabled':True,'approved':True,'mock_origin':m.origin,'season':'2020','category':'competitions'})
            if i in (1,2,4,5):self.pm.credential({'slot':str(i),'credential':m.key})
    def tearDown(self):
        self.worker.close();self.store.close()
        for m in self.mocks:m.close()
        self.temp.cleanup()
    def execute(self,slot,operation='test'):
        id=self.pm.submit(str(slot),operation)['task_id'];task=next(t for t in self.store.tasks() if t['id']==id);self.worker.execute(task);return next(t for t in self.store.tasks() if t['id']==id)
    def test_six_independent_adapters_and_collect(self):
        for slot in range(1,7):
            with self.subTest(slot=slot):
                t=self.execute(slot);self.assertEqual(t['state'],'COMPLETE',t.get('result'));self.assertEqual(t['result']['evidence_class'],'MOCK_PASS');self.assertEqual(t['result']['inserted'],0)
                self.pm.configure({'slot':str(slot),'competition':'1','category':'results','date_from':'2020-01-01','date_to':'2020-01-01'});t=self.execute(slot,'collect');self.assertEqual(t['state'],'COMPLETE',t.get('result'));self.assertEqual(t['result']['inserted'],1);self.assertEqual(t['result']['origin'],'SYNTHETIC')
        self.assertEqual(self.store.query()['total'],6);self.assertTrue(all(x['origin']=='SYNTHETIC' for x in self.store.query()['rows']))
    def test_credentials_wrong_independent_and_removal(self):
        self.pm.credential({'slot':'1','credential':self.mocks[1].key});t=self.execute(1);self.assertEqual(t['state'],'FAILED');self.assertEqual(self.pm.public('1')['state'],'AUTHENTICATION_FAILED');self.assertEqual(self.execute(2)['state'],'COMPLETE');self.pm.credential({'slot':'2'},True)
        with self.assertRaises(Blocked):self.pm.submit('2')
    def test_offline_no_outbound(self):
        self.worker.mode='offline'
        for s in range(1,7):
            with self.assertRaises(Blocked):self.pm.submit(str(s))
        self.assertEqual(sum(len(m.calls) for m in self.mocks),0)
    def test_429_no_retry(self):
        self.mocks[0].case='rate';self.execute(1);self.assertEqual(len(self.mocks[0].calls),1);self.assertEqual(self.pm.public('1')['state'],'RATE_LIMITED')
        with self.assertRaises(Blocked):self.pm.submit('1')
        self.assertEqual(self.execute(2)['state'],'COMPLETE')
    def test_pagination_and_redaction(self):
        self.mocks[1].case='pagination';t=self.execute(2);self.assertEqual(len(t['result']['pages']),2);self.assertEqual(len(self.pm.public('2')['competitions']),2)
        self.mocks[1].case='echo';self.execute(2)
        for p in self.data.rglob('*'):
            if p.is_file() and p.suffix!='.dpapi':self.assertNotIn(self.mocks[1].key.encode(),p.read_bytes(),p.name)
    def test_malformed_json_no_import(self):
        self.mocks[0].case='malformed';self.assertEqual(self.execute(1)['state'],'FAILED');self.assertEqual(self.store.query()['total'],0)
    def test_budget_and_disable(self):
        c=self.store.state('provider','1');c['budget']['requests']=[time.time()]*180;self.store.state('provider','1',c);self.execute(1);self.assertEqual(len(self.mocks[0].calls),0);self.assertEqual(self.pm.public('1')['state'],'RATE_LIMITED')
        self.pm.configure({'slot':'2','enabled':False});self.pm.schedule();self.assertFalse(self.mocks[1].calls)
    def test_unknown_premium_and_private_endpoint_rejected(self):
        with self.assertRaises(ValueError):self.pm.configure({'slot':'4','category':'odds'})
        with self.assertRaises(ValueError):self.pm.configure({'slot':'1','mock_origin':'http://127.0.0.1:9999'})
        with self.assertRaises(ValueError):self.pm.configure({'slot':'1','credential':'not-metadata'})
    def test_slot_binding_and_restart(self):
        status=self.pm.public('1');self.assertEqual(status['credential_status'],'SAVED');vault=Vault(self.data);self.assertEqual(vault.status('1',self.pm.binding('2',self.store.state('provider','2'))),'REENTRY_REQUIRED')
        new=ProviderManager(self.store,self.data,self.worker,[m.origin for m in self.mocks]);self.assertEqual(new.public('1')['credential_status'],'SAVED')

if __name__=='__main__':unittest.main(verbosity=2)
