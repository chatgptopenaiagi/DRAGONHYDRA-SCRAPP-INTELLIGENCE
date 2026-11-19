"""Independent portable/installer Windows acceptance; existing owner registration is read-only."""
import ctypes,hashlib,json,os,shutil,sqlite3,subprocess,sys,tempfile,time,traceback,winreg
from pathlib import Path
from contextlib import closing
import psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.launcher import request,running,stop
from living.contracts import file_hash
OUT=ROOT/'evidence/mission-006'/('windows-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));OUT.mkdir();work=Path(tempfile.mkdtemp(prefix='DRAGONHYDRA-M006-Windows-')).resolve();build=json.loads((ROOT/'evidence/mission-006/latest-build.json').read_text());setup=Path(build['installer']);portable=json.loads((ROOT/'evidence/mission-006/PORTABLE-LOCATION.json').read_text());target=work/'installed';data=work/'user-data';checks=[];process=None;performance={};KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\DRAGONHYDRA-LivingIntelligence'
env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV'))};env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot']
def registration(key):
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key) as k:
            return {winreg.EnumValue(k,i)[0]:winreg.EnumValue(k,i)[1] for i in range(winreg.QueryInfoKey(k)[1])}
    except FileNotFoundError:return None
original_registration=registration(KEY);shortcut=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/DRAGONHYDRA Intelligence.lnk';original_shortcut=file_hash(shortcut) if shortcut.exists() else None
def save(status='RUNNING',error=None):
    result={'status':status,'checks':checks,'performance':performance,'work':str(work),'error':error,'portable_sha256':build['portable_sha256'],'installer_sha256':build['installer_sha256'],'owner_registration_preserved':registration(KEY)==original_registration};(OUT/'results.json').write_text(json.dumps(result,indent=2));return result
def check(name,ok,detail=None):checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail});save();print(name+': '+checks[-1]['status'],flush=True);assert ok,name
def install(name,expected=True,uninstall=False):
    receipt=OUT/(name+'.json');p=subprocess.run([str(setup),'--silent','--isolated-registration','--target',str(target),'--receipt',str(receipt)]+(['--uninstall'] if uninstall else []),cwd=work,env=env,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW);r=json.loads(receipt.read_text());check(name,(p.returncode==0 and r['status']=='PASS') if expected else (p.returncode!=0 and r['status']=='FAIL'),r);return r
def launch(exe,label):
    global process
    t=time.perf_counter();log=(OUT/(label+'.log')).open('w');process=subprocess.Popen([str(exe),'--serve','--data-dir',str(data),'--port','0'],cwd=work,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();deadline=time.monotonic()+35
    while not running(data) and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
    check(label+' starts with PATH excluding development tools',bool(running(data)));performance[label+'_startup_seconds']=time.perf_counter()-t;performance[label+'_rss_bytes']=psutil.Process(process.pid).memory_info().rss;performance[label+'_idle_cpu_percent_0_2s']=psutil.Process(process.pid).cpu_percent(.2)
def shutdown(label):
    t=time.perf_counter();stop(data);process.wait(35);performance[label+'_shutdown_seconds']=time.perf_counter()-t;check(label+' clean shutdown',process.returncode==0)
def identities(db):
    with closing(sqlite3.connect(Path(db).as_uri()+'?mode=ro',uri=True)) as c:return hashlib.sha256('\n'.join(r[0] for r in c.execute('SELECT payload FROM observations ORDER BY id')).encode()).hexdigest()
try:
    check('Acceptance uses ordinary Windows token',not ctypes.windll.shell32.IsUserAnAdmin())
    check('Portable folder is independent of source',not Path(portable['directory']).is_relative_to(ROOT))
    data.mkdir();baseline=json.loads((ROOT/'evidence/mission-006/BASELINE-POINTER.json').read_text());dbs=json.loads((Path(baseline['directory'])/'databases.json').read_text());source=Path(next(x['snapshot'] for x in dbs if x['observations']==3124));(data/'intelligence.sqlite3').write_bytes(source.read_bytes());original_ids=identities(data/'intelligence.sqlite3')
    launch(portable['exe'],'portable');check('Schema upgrade retains all 3124 original payloads',request(data,'/api/status')['summary']['observations']==3124 and identities(data/'intelligence.sqlite3')==original_ids);check('Existing compatible schema preserved',True,'Schema 3 from immutable Mission 006 baseline; no migration required');request(data,'/api/provider/credential',{'slot':'1','credential':'SYNTHETIC-WINDOWS-UPGRADE-SECRET'});shutdown('portable');credential=file_hash(data/'private/providers/1.dpapi');db_hash=file_hash(data/'intelligence.sqlite3')
    install('fresh-install');record=json.loads((target/'INSTALLATION.json').read_text());isolated_key=record['registration_key'];check('Isolated uninstall registration and shortcut created',registration(isolated_key)['DisplayVersion']==build['version'] and Path(record['shortcut']).exists());manifest=json.loads((target/'FILES-SHA256.json').read_text());check('Installed files match portable manifest',all(file_hash(target/p)==h for p,h in manifest.items()))
    launch(target/'DragonhydraIntelligence.exe','installed');check('Installed candidate preserves 3124 payload identities',identities(data/'intelligence.sqlite3')==original_ids);check('Installed candidate reads protected credentials',next(p for p in request(data,'/api/providers') if p['slot']=='1')['credential_status']=='SAVED');install('running-upgrade-refused',False)
    # A second --serve invocation against the same dataset must fail without touching the first service.
    child=subprocess.run([str(target/'DragonhydraIntelligence.exe'),'--serve','--data-dir',str(data),'--port','0'],cwd=work,env=env,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW);check('Single dataset worker enforced',child.returncode!=0 and running(data)['pid']==process.pid);shutdown('installed');(target/'owner-note.txt').write_text('Unowned user file retained');db_hash=file_hash(data/'intelligence.sqlite3')
    with (OUT/'installed-postgresql-gui.log').open('w') as log:
        subprocess.run([sys.executable,str(ROOT/'tests/mission006_postgres_browser.py'),'--exe',str(target/'DragonhydraIntelligence.exe')],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    check('Installed executable passes genuine PostgreSQL browser and CSV workflow',True,'See installed-postgresql-gui.log and its linked 29-check receipt')
    with (OUT/'installed-beginner-gui.log').open('w') as log:
        subprocess.run([sys.executable,str(ROOT/'tests/beginner_browser.py'),'--exe',str(target/'DragonhydraIntelligence.exe'),'--label','installed'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=240)
    check('Installed beginner help, research and real PostgreSQL workflow',True,'See installed-beginner-gui.log')
    install('upgrade-existing-installation');check('Upgrade preserves data, credentials and unowned files',file_hash(data/'intelligence.sqlite3')==db_hash and file_hash(data/'private/providers/1.dpapi')==credential and (target/'owner-note.txt').exists())
    with (target/'DragonhydraIntelligence.exe').open('rb'):install('locked-file-upgrade-refused',False)
    check('Failed upgrade retains all verified files and data',all(file_hash(target/p)==h for p,h in manifest.items()) and file_hash(data/'intelligence.sqlite3')==db_hash)
    stages=set(work.glob('installed.stage-*'));p=subprocess.Popen([str(setup),'--silent','--isolated-registration','--target',str(target),'--receipt',str(OUT/'interrupted-installer.json')],cwd=work,env=env,creationflags=subprocess.CREATE_NO_WINDOW);deadline=time.monotonic()+30;found=set()
    while p.poll() is None and time.monotonic()<deadline:
        found=set(work.glob('installed.stage-*'))-stages
        if found:break
        time.sleep(.005)
    check('Disposable installer reached staged extraction',bool(found) and p.poll() is None);owned=[c for c in psutil.Process(p.pid).children(recursive=True) if Path(c.exe()).resolve()==setup.resolve()]
    for c in owned:c.kill()
    if p.poll() is None:p.kill()
    p.wait(15);check('Interrupted upgrade preserves old executable and user data',all(file_hash(target/name)==h for name,h in manifest.items()) and file_hash(data/'intelligence.sqlite3')==db_hash);install('resume-interrupted-upgrade')
    launch(target/'DragonhydraIntelligence.exe','upgraded');check('Resumed installation operates on preserved data',running(data)['summary']['observations']==3124);shutdown('upgraded');db_hash=file_hash(data/'intelligence.sqlite3');record=json.loads((target/'INSTALLATION.json').read_text());install('uninstall',uninstall=True);check('Uninstall removes owned program and rollback executables',not (target/'DragonhydraIntelligence.exe').exists() and not list(work.glob('installed.previous-*/DragonhydraIntelligence.exe')));check('Uninstall retains database, credentials and unowned files',file_hash(data/'intelligence.sqlite3')==db_hash and file_hash(data/'private/providers/1.dpapi')==credential and (target/'owner-note.txt').exists());check('Owned isolated registration and shortcut removed',registration(isolated_key) is None and not Path(record['shortcut']).exists())
    # Actual beta.2 program bytes and its ownership manifest copied to a separate fixture.
    target=work/'beta2-upgrade';owner=Path(original_registration['InstallLocation']);shutil.copytree(owner,target);prior=json.loads((target/'INSTALLATION.json').read_text());prior.update(prior_installation=None,shortcut=None,isolated_registration=True);(target/'INSTALLATION.json').write_text(json.dumps(prior));old_exe=file_hash(target/'DragonhydraIntelligence.exe');install('beta2-to-'+build['version']+'-upgrade');check('Original beta2 program retained for rollback',any(file_hash(p)==old_exe for p in work.glob('beta2-upgrade.previous-*/DragonhydraIntelligence.exe')));launch(target/'DragonhydraIntelligence.exe','beta2-upgraded');check('Beta2 upgrade retains all records and credential availability',identities(data/'intelligence.sqlite3')==original_ids and next(x for x in request(data,'/api/providers') if x['slot']=='1')['credential_status']=='SAVED');shutdown('beta2-upgraded');install('beta2-upgrade-fixture-uninstall',uninstall=True)
    check('Owner beta2 registry and shortcut unchanged',registration(KEY)==original_registration and (file_hash(shortcut) if shortcut.exists() else None)==original_shortcut);performance.update(archive_bytes=build['portable_bytes'],installer_bytes=build['installer_bytes'],startup_conditions='Warm OS cache; antivirus and simultaneous acceptance workloads not controlled. No cold-start claim.');save('PASS');print(json.dumps({'status':'PASS','checks':len(checks),'output':str(OUT)}),flush=True)
except BaseException:save('FAIL',traceback.format_exc());raise
finally:
    if process and process.poll() is None:stop(data);process.wait(35)

