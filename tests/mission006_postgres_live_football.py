"""Four bounded genuine API-Football requests with owner-authorized protected credential."""
import json,os,sqlite3,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'application'),str(ROOT/'.build-deps-postgresql')]
from living.core import Runtime
from living.credentials import Vault
from living.contracts import fingerprint,now,atomic_json
from living.football_providers import ADAPTERS
from living.launcher import request,running,stop
from browser_cdp import Browser
out=ROOT/'evidence/mission-006/postgresql'/('football-live-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));out.mkdir();data=out/'data';data.mkdir();owner=Path(os.environ['LOCALAPPDATA'])/'DRAGONHYDRA/LivingIntelligence';exe=json.loads((ROOT/'evidence/mission-006/PORTABLE-LOCATION.json').read_text())['exe'];checks=[];browser=None;process=None
def check(name,ok,detail=None):
    checks.append({'name':name,'status':'LIVE_PASS' if ok else 'FAIL','detail':detail});atomic_json(out/'results.json',{'checks':checks,'exe':exe});print(name+': '+checks[-1]['status'],flush=True);assert ok,name
def collect(id):
    prior={t['id'] for t in request(data,'/api/tasks')};browser.click(id);end=time.monotonic()+60
    while time.monotonic()<end:
        tasks=[t for t in request(data,'/api/tasks') if t['id'] not in prior and t['payload'].get('provider_slot')=='2']
        if tasks and tasks[0]['state'] not in ('QUEUED','RUNNING'):return tasks[0]
        time.sleep(.25)
    raise AssertionError('Provider operation did not finish within its bound')
try:
    rt=Runtime(data);rt.postgres.configure({'enabled':True,'schema':'dragonhydra_test_'+uuid.uuid4().hex[:12]});rt.postgres.import_existing_credentials();rt.postgres.provision();rt.postgres.activate('POSTGRESQL')
    with sqlite3.connect((owner/'intelligence.sqlite3').as_uri()+'?mode=ro',uri=True) as c:prior=json.loads(c.execute("SELECT payload FROM component_state WHERE scope='provider' AND id='2'").fetchone()[0])
    a=ADAPTERS['2'];binding=fingerprint(['2',a.name,prior.get('mock_origin') or a.base,a.auth,a.key_name]);key=Vault(owner).get('2',binding);rt.providers.configure({'slot':'2','enabled':True,'approved':True,'schedule':False});rt.providers.credential({'slot':'2','credential':key});del key;rt.close()
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV'))};env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot'];log=(out/'server.log').open('w');process=subprocess.Popen([exe,'--serve','--data-dir',str(data),'--port','0','--mode','connected'],cwd=Path(exe).parent,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();end=time.monotonic()+35
    while not running(data) and process.poll() is None and time.monotonic()<end:time.sleep(.1)
    assert running(data),'Packaged startup failed';browser=Browser(out/'edge');port=json.loads((data/'ready.json').read_text())['port'];browser.goto('http://127.0.0.1:'+str(port)+'/#ticket='+request(data,'/api/session-ticket',{})['ticket']+'&view=football');browser.wait("document.querySelector('#p2-account')!==null")
    task=collect('#p2-account');check('Real API-Football status through packaged GUI',task['state']=='COMPLETE',task);provider=next(x for x in request(data,'/api/providers') if x['slot']=='2');account=provider['reported_account'];atomic_json(out/'reported-quota.json',account)
    if account['remaining']<4:raise RuntimeError('Provider allowance is insufficient for three further bounded requests; collection deferred')
    task=collect('#p2-test');check('Actual provider league discovery',task['state']=='COMPLETE',{'task_id':task['id']});browser.click('#refresh');browser.wait("document.querySelector('#p2-competition').options.length>1");browser.fill('#p2-category','results');browser.fill('#p2-competition','39');browser.fill('#p2-season','2023');browser.fill('#p2-date-from','2023-08-11');browser.fill('#p2-date-to','2023-08-14');browser.click('#p2-save');browser.wait("document.querySelector('#p2-status').textContent.startsWith('CONFIGURED')");task=collect('#p2-collect');check('Genuine fixtures committed into PostgreSQL',task['state']=='COMPLETE',task)
    rows=request(data,'/api/observations?source=football-api-2&limit=100')['rows'];check('Real provider identities and timestamps retained',len(rows)==10 and all(r['origin']=='COLLECTED' and r['metadata']['provider_slot']=='2' for r in rows),{'ids':[r['id'] for r in rows],'count':len(rows)});tool=request(data,'/api/registry/run',{'name':'query_football_results','arguments':{'source':'football-api-2','limit':20}});check('AI football tool reads those PostgreSQL results',tool['state']=='PASS' and {r['id'] for r in tool['output']['records']}=={r['id'] for r in rows});atomic_json(out/'ai-tool.json',tool)
    task=collect('#p2-collect');check('Repeated live collection detects duplicates',task['state']=='COMPLETE' and request(data,'/api/observations?source=football-api-2')['total']==10,task)
    browser.click('nav [data-view="history"]');browser.fill('#source','football-api-2');browser.click('#apply');browser.wait("document.querySelector('#pagination').textContent.includes('10')");check('Actual live-acquired historical records visible',browser.js("document.querySelector('#rows').textContent.length>0"));browser.screenshot('football-postgresql.png');check('PostgreSQL relational projection contains ten results',len(request(data,'/api/postgresql/query',{'table':'match_results','limit':100})['rows'])==10)
    check('No JavaScript exceptions',not browser.errors);stop(data);process.wait(30);check('Packaged clean shutdown',process.returncode==0);atomic_json(out/'results.json',{'status':'LIVE_PASS','checks':checks,'exe':exe,'data':str(data),'requests':'One status, one league discovery, two bounded historical fixture requests; no odds or paid feature enabled'});atomic_json(ROOT/'evidence/mission-006/postgresql/latest-football.json',{'directory':str(out),'status':'LIVE_PASS','checks':len(checks)})
except Exception as e:
    atomic_json(out/'failure.json',{'status':'BLOCKED' if isinstance(e,RuntimeError) else 'FAIL','error':str(e) if isinstance(e,(ValueError,RuntimeError,AssertionError)) else type(e).__name__});raise
finally:
    if browser:browser.close()
    if process and process.poll() is None:stop(data);process.wait(30)
