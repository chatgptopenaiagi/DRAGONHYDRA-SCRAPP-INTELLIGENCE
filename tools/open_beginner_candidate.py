"""Open a separate owner review workspace; keep earlier programs, data and credentials intact."""
import json,os,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'application'),str(ROOT/'tests'),str(ROOT/'.build-deps-postgresql')]
from living.contracts import atomic_json,now,file_hash
from living.storage import Store
from living.credentials import Vault
from living.provider_manager import ProviderManager
from living.cloud_manager import Cloud
from living.postgres_control import PostgresControl,PURPOSES
from living.launcher import request,running,open_dashboard,stop
from browser_cdp import Browser
mission=ROOT/'evidence/mission-006';out=Path(json.loads((mission/'BEGINNER-LATEST.json').read_text())['directory']);manifest=json.loads((out/'PACKAGE-MANIFEST.json').read_text());exe=Path(manifest['exe']);assert file_hash(exe)==manifest['exe_sha256']
old=json.loads((out/'REPRODUCTION-INSTANCE.json').read_text());original=Path(old['data']);data=Path(os.environ['LOCALAPPDATA'])/'DRAGONHYDRA'/('BeginnerReview-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));data.mkdir()
private={str(p.relative_to(original)):file_hash(p) for p in (original/'private').rglob('*') if p.is_file()}
source=sqlite3.connect((original/'intelligence.sqlite3').as_uri()+'?mode=ro',uri=True);target=sqlite3.connect(data/'intelligence.sqlite3')
try:source.backup(target)
finally:source.close();target.close()
for name in ('settings.json',):
    if (original/name).exists():shutil.copy2(original/name,data/name)
for name in ('backups','postgresql-backups'):
    if (original/name).exists():shutil.copytree(original/name,data/name)
src=Store(original/'intelligence.sqlite3');dst=Store(data/'intelligence.sqlite3');copied=[]
try:
    oldpg=PostgresControl(src,original);newpg=PostgresControl(dst,data)
    for purpose in PURPOSES:
        if oldpg.vault.status(purpose,oldpg.binding(purpose))=='SAVED':
            value=oldpg.vault.get(purpose,oldpg.binding(purpose));newpg.vault.save(purpose,newpg.binding(purpose),value);del value;copied.append('postgres/'+purpose)
    pm=ProviderManager(src,original,SimpleNamespace(mode='offline'));destvault=Vault(data)
    for slot in map(str,range(1,7)):
        binding=pm.binding(slot,src.state('provider',slot))
        if pm.vault.status(slot,binding)=='SAVED':
            value=pm.vault.get(slot,binding);destvault.save(slot,binding,value);del value;copied.append('providers/'+slot)
    cv=Vault(original,'cloud');dv=Vault(data,'cloud')
    for cfg in src.states('cloud'):
        binding=Cloud.binding(None,cfg)
        if cv.status(cfg['id'],binding)=='SAVED':
            value=cv.get(cfg['id'],binding);dv.save(cfg['id'],binding,value);del value;copied.append('cloud/'+cfg['id'])
    dst.state('ui','preferences',{'beginner':True,'tour_complete':False})
finally:src.close();dst.close()
assert all(file_hash(original/p)==h for p,h in private.items())
env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV'))};env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot'];log=(out/'owner-review-server.log').open('w')
process=subprocess.Popen([str(exe),'--serve','--data-dir',str(data),'--port','0','--mode','offline'],env=env,cwd=exe.parent,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();end=time.monotonic()+35
while not running(data) and process.poll() is None and time.monotonic()<end:time.sleep(.1)
assert running(data),'New candidate did not start; previous programs remain available'
status=request(data,'/api/status');assert status['version']=='0.2.0-beta.5' and status['summary']['observations']==5840 and status['postgresql']['state']=='CONNECTED'
port=json.loads((data/'ready.json').read_text())['port'];browser=Browser(out/'owner-review-edge')
try:
    browser.goto('http://127.0.0.1:'+str(port)+'/#ticket='+request(data,'/api/session-ticket',{})['ticket']);browser.wait("document.querySelector('#guided-tour').open");browser.click('#tour-skip');browser.wait("!document.querySelector('#guided-tour').open");browser.wait("document.querySelector('#data-supplied').textContent.includes('5,840')");assert browser.js("document.querySelector('#state').textContent.includes('PostgreSQL CONNECTED')");browser.call('Page.captureScreenshot')
    (out/'owner-review-edge/overview.png').write_bytes(__import__('base64').b64decode(browser.call('Page.captureScreenshot',format='png',captureBeyondViewport=False)['data']))
    browser.click('nav [data-view="football-research"]');browser.wait("document.querySelectorAll('.research-match').length>0");browser.click('#help-open');browser.wait("document.querySelector('#help-center').open");assert not browser.errors
    (out/'owner-review-edge/help-center.png').write_bytes(__import__('base64').b64decode(browser.call('Page.captureScreenshot',format='png',captureBeyondViewport=False)['data']))
finally:browser.close()
# Restore only the new workspace's first-run tour so the owner sees the introduction.
request(data,'/api/preferences',{'tour_complete':False,'beginner':True})
native=subprocess.Popen([str(exe),'--data-dir',str(data),'--port','0','--mode','offline'],env=env,cwd=exe.parent,creationflags=subprocess.CREATE_NO_WINDOW)
result={'at':now(),'status':'LIVE_PASS','version':status['version'],'exe':str(exe),'exe_sha256':file_hash(exe),'data':str(data),'pid':process.pid,'native_pid':native.pid,'port':port,'mode':'offline','datastore':'POSTGRESQL','observations':5840,'postgresql_status':status['postgresql']['state'],'protected_credentials_rebound':copied,'original_private_hashes_unchanged':len(private),'older_installations_replaced':False,'database':'codex_engineering.dragonhydra_intelligence','note':'New local control-state copy; same preserved canonical PostgreSQL research schema. Acceptance fault injection used separate schemas.'}
atomic_json(out/'OWNER-REVIEW-APPLICATION.json',result)
# Only the beta.4 reproduction service started by this repair may be stopped.
if old.get('started_by_this_task') and running(original):
    import psutil
    ready=json.loads((original/'ready.json').read_text());p=psutil.Process(ready['pid'])
    if ready['pid']==old['pid'] and Path(p.exe()).resolve()==Path(old['exe']).resolve():stop(original);p.wait(35)
open_dashboard(data)
print(json.dumps({'status':'LIVE_PASS','exe':str(exe),'data':str(data),'port':port,'observations':5840,'credentials_rebound':len(copied)}))
