"""Final static-asset repair acceptance; live SELECT only, isolated Windows install."""
import json,os,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'application'),str(ROOT/'.build-deps-postgresql')]
from living.launcher import request,running,stop
from living.contracts import atomic_json,file_hash
from browser_cdp import Browser
out=ROOT/'evidence/mission-006/postgresql'/('final-package-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));out.mkdir()
build=json.loads((ROOT/'evidence/mission-006/latest-build.json').read_text())
previous=ROOT/'evidence/mission-006/build-20261119T094800Z'
inputs=json.loads(Path(build['source_inputs']).read_text());old=json.loads((previous/'source-inputs.json').read_text())
changed=[p for p in inputs if inputs[p]!=old.get(p)]
assert set(p.replace('\\','/') for p in changed)=={'application/living/web/app.css','application/living/web/index.html','application/living/launcher.py'}
work=Path(tempfile.mkdtemp(prefix='DRAGONHYDRA-M006-Final-')).resolve();data=work/'user-data';target=work/'installed';checks=[];process=None;browser=None
env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV'))};env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot']
def save(status='RUNNING'):
    atomic_json(out/'results.json',{'status':status,'checks':checks,'build':build,'work':str(work),'changed_inputs':changed,'unchanged_backend_acceptance_from':str(previous)})
def check(name,condition,detail=None):
    checks.append({'name':name,'status':'PASS' if condition else 'FAIL','detail':detail});save();print(name+': '+checks[-1]['status'],flush=True);assert condition,name
def verify(folder):
    files=json.loads((folder/'FILES-SHA256.json').read_text());assert all(file_hash(folder/n)==h for n,h in files.items());return len(files)
def launch(exe,label,configure=False):
    global process,browser
    log=(out/(label+'.log')).open('w');process=subprocess.Popen([str(exe),'--serve','--data-dir',str(data),'--port','0'],cwd=work,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();deadline=time.monotonic()+35
    while not running(data) and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
    check(label+' starts independently',bool(running(data)))
    if configure:
        request(data,'/api/postgresql/configure',{'enabled':True,'schema':'dragonhydra_intelligence'});request(data,'/api/postgresql/credentials/import',{})
    browser=Browser(out/(label+'-edge'));port=json.loads((data/'ready.json').read_text())['port'];browser.goto('http://127.0.0.1:'+str(port)+'/#ticket='+request(data,'/api/session-ticket',{})['ticket']);browser.wait("document.querySelector('#state').textContent.includes('Ready')");browser.click('nav [data-view="postgresql"]');browser.wait("document.querySelector('#pg-host')?.value==='127.0.0.1'");browser.click('#pg-test');browser.wait("!document.querySelector('#pg-test').disabled && document.querySelector('#pg-result').textContent.includes('last_successful_query')")
    check(label+' genuine PostgreSQL query through authenticated UI',request(data,'/api/postgresql')['connection']['user']=='codex_mcp_ro')
    browser.click('#pg-query');browser.wait("!document.querySelector('#pg-query').disabled && document.querySelector('#pg-result').textContent.includes('returned')")
    check(label+' actual bounded rows',browser.js("JSON.parse(document.querySelector('#pg-result').textContent).returned===10"))
    check(label+' correct displayed version',browser.js("document.querySelector('.rail-bottom').textContent.includes('0.2.0-beta.4')"))
def shutdown(label):
    global browser
    check(label+' no JavaScript exceptions',not browser.errors,browser.errors);browser.close();browser=None;stop(data);process.wait(30);check(label+' clean shutdown',process.returncode==0)
def install(name,uninstall=False):
    receipt=out/(name+'.json');r=subprocess.run([build['installer'],'--silent','--isolated-registration','--target',str(target),'--receipt',str(receipt)]+(['--uninstall'] if uninstall else []),cwd=work,env=env,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    result=json.loads(receipt.read_text());check(name,r.returncode==0 and result['status']=='PASS',result)
try:
    with zipfile.ZipFile(build['portable']) as z:
        assert z.testzip() is None
        assert all((work/n).resolve().is_relative_to(work) for n in z.namelist());z.extractall(work)
    bundle=work/'DragonhydraIntelligence';count=verify(bundle)
    check('All portable files match manifest',count==build['bundled_files'],count)
    check('Source changes limited to version labels and status layout',len(changed)==3,changed)
    atomic_json(ROOT/'evidence/mission-006/PORTABLE-LOCATION.json',{'status':'EXTRACTED_HASH_VERIFIED','archive':build['portable'],'archive_sha256':build['portable_sha256'],'directory':str(bundle),'exe':str(bundle/'DragonhydraIntelligence.exe'),'files':count,'outside_source_directory':True})
    launch(bundle/'DragonhydraIntelligence.exe','portable',True)
    for width in (1440,1050,720,500):
        browser.call('Emulation.setDeviceMetricsOverride',width=width,height=1000,deviceScaleFactor=1,mobile=False)
        geometry=browser.js("Array.from(document.querySelectorAll('#pg-health .card strong')).map(e=>({text:e.textContent,width:e.clientWidth,content:e.scrollWidth}))")
        check('Database identities fit cards at '+str(width),bool(geometry) and all(x['content']<=x['width']+1 for x in geometry),geometry)
    browser.call('Emulation.setDeviceMetricsOverride',width=1440,height=1000,deviceScaleFactor=1,mobile=False);browser.screenshot('postgresql-layout.png');shutdown('portable')
    install('fresh-install');check('Installed payload matches verified archive',verify(target)==count);record=json.loads((target/'INSTALLATION.json').read_text());launch(target/'DragonhydraIntelligence.exe','installed');shutdown('installed')
    protected={str(p.relative_to(data)):file_hash(p) for p in (data/'private').rglob('*.dpapi')};db_hash=file_hash(data/'intelligence.sqlite3')
    install('upgrade');check('Upgrade preserves database and protected credentials',file_hash(data/'intelligence.sqlite3')==db_hash and all(file_hash(data/p)==h for p,h in protected.items()))
    install('uninstall',True);check('Uninstall preserves user state',file_hash(data/'intelligence.sqlite3')==db_hash and all(file_hash(data/p)==h for p,h in protected.items()));check('Owned program and shortcut removed',not (target/'DragonhydraIntelligence.exe').exists() and not Path(record['shortcut']).exists())
    save('PASS');atomic_json(ROOT/'evidence/mission-006/postgresql/latest-final-package.json',{'directory':str(out),'status':'PASS','checks':len(checks)});print(json.dumps({'status':'PASS','checks':len(checks),'directory':str(out)}))
except BaseException:
    save('FAIL');raise
finally:
    if browser:browser.close()
    if process and process.poll() is None:stop(data);process.wait(30)
