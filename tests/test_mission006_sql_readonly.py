import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'application'))
from living.core import Runtime
from living.contracts import Blocked
from living.sql_readonly import quote
from living.sql_control import SqlControl

class SqlReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name);self.guard=self.path/'guard.json';self.guard.write_text(json.dumps({'sql_read_only_allowed':True,'sql_tests_allowed':False,'status':'WAITING_MAINTENANCE_WINDOW'}));self.rt=Runtime(self.path/'data','offline',self.guard);self.sql=SqlControl(self.rt.store,self.rt.data,self.guard);self.sql.configure({'enabled':True})
    def tearDown(self):self.rt.close();self.tmp.cleanup()
    def test_write_guard_before_driver(self):
        connector=Mock();self.sql.connector=connector
        with self.assertRaises(Blocked):self.sql.connect(write=True)
        self.sql=SqlControl(self.rt.store,self.rt.data,self.guard);self.sql.configure({'database':'DRAGONHYDRA_M006_DEV'})
        with self.assertRaises(Blocked):self.sql.provision('DRAGONHYDRA_M006_DEV')
        connector.assert_not_called()
    def test_reject_arbitrary_sql_and_injection(self):
        with patch.object(self.sql,'connect') as connect:
            for b in ({'sql':'SELECT 1; DELETE FROM teams'},{'query_id':'SELECT INTO x FROM teams'},{'query_id':'server_identity','timeout':0},{'query_id':'EXEC sp_executesql'},{'query_id':'sports_records','limit':True},{'query_id':'server_identity','limit':101}):
                with self.assertRaises(ValueError):self.sql.readonly_query(b)
            connect.assert_not_called()
    def test_metadata_identifiers_are_parameters(self):
        evil="team]; DELETE FROM fixtures;--"
        with patch.object(self.sql,'read',return_value={'rows':[]}) as read:
            with self.assertRaises(ValueError):self.sql.describe('master','dbo',evil)
            self.assertNotIn(evil,read.call_args.args[2]);self.assertIn(evil,read.call_args.args[3]);self.assertEqual(quote('x]y'),'[x]]y]')
    def test_sports_only_no_system_or_unrelated_records(self):
        for table,system,allowed in [('Credentials',False,True),('teams',True,True),('teams',False,False)]:
            d={'sports_candidate':table=='teams','object':{'system_object':system,'select_allowed':allowed}}
            with patch.object(self.sql,'describe',return_value=d),patch.object(self.sql,'read') as read:
                with self.assertRaises(Blocked):self.sql.readonly_query({'query_id':'sports_records','table':table})
                read.assert_not_called()
    def test_projection_excludes_secrets_and_bounds_rows(self):
        d={'sports_candidate':True,'object':{'system_object':False,'select_allowed':True},'column_list_truncated':False,'schema':'dbo','table':'teams','columns':[{'name':'team_id','data_type':'int'},{'name':'api_token','data_type':'nvarchar'}]}
        with patch.object(self.sql,'describe',return_value=d),patch.object(self.sql,'read',return_value={'rows':[]}) as read:
            r=self.sql.readonly_query({'query_id':'sports_records','table':'teams','limit':2});self.assertNotIn('api_token',read.call_args.args[2]);self.assertEqual(read.call_args.args[3],(3,));self.assertEqual(r['projection']['columns'],['team_id'])
    def test_read_receipt_closes_connection_and_caps_result(self):
        c=Mock();cur=c.cursor.return_value;cur.execute.return_value=cur;cur.description=[('name',)];cur.fetchmany.return_value=[('first',),('second',),('third',)];self.sql.connector=lambda *_:c
        r=self.sql.read('fixture','master','SELECT fixture',limit=2);self.assertEqual(r['returned'],2);self.assertTrue(r['truncated']);c.close.assert_called_once();c.commit.assert_not_called();self.assertEqual(self.sql.status()['last_query']['id'],r['id'])
    def test_disabled_guard_propagates_blocked(self):
        self.guard.write_text('{}')
        with self.assertRaises(Blocked):self.sql.readonly_query({'query_id':'database_catalog'})
    def test_ai_tools_validate_queries_and_limits(self):
        for name,args in [('run_bounded_readonly_query',{'query_id':'DELETE'}),('query_sports_data',{'sql':'EXEC x'}),('list_sql_tables',{'database':'master','limit':10000})]:self.assertEqual(self.rt.registry.run(name,args)['state'],'FAIL')
    def test_saved_connection_is_not_assumed_live_after_restart(self):
        from living.sql_control import SqlControl
        self.rt.store.state('sql','connection',{'state':'CONNECTED','last_successful_query':'earlier'});sql=SqlControl(self.rt.store,self.rt.data,self.guard);self.assertEqual(sql.status()['state'],'DISCONNECTED');self.assertEqual(sql.status()['connection']['last_successful_query'],'earlier')

if __name__=='__main__':unittest.main()
