"""Deliver only independently accepted bytes; preserve every previous candidate."""
import hashlib,json,re,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.contracts import atomic_json,now,file_hash
mission=ROOT/'evidence/mission-006';out=Path(json.loads((mission/'BEGINNER-LATEST.json').read_text())['directory'])
read=lambda p:json.loads(Path(p).read_text())
build=read(mission/'latest-build.json');b=Path(build['build']);assert build['version']=='0.2.0-beta.5'
receipts={}
for kind in ('portable','installed'):
    latest=read(out/('latest-'+kind+'.json'));r=read(Path(latest['directory'])/'results.json');assert r['status']=='PASS' and all(c['status']=='PASS' for c in r['checks']);assert r['exe_sha256']==file_hash(b/'portable/DragonhydraIntelligence/DragonhydraIntelligence.exe');receipts[kind]={'path':str(Path(latest['directory'])/'results.json'),'checks':len(r['checks'])}
windows=read(out/'WINDOWS-ACCEPTANCE-POINTER.json');w=read(Path(windows['directory'])/'results.json');assert w['status']=='PASS' and w['installer_sha256']==build['installer_sha256'];receipts['windows']={'path':str(Path(windows['directory'])/'results.json'),'checks':len(w['checks'])}
assert re.search(r'Ran 55 tests.*\sOK\s*$',(out/'regression-retest.log').read_text(),re.S)
assert read(out/'PRESERVATION-VERIFICATION.json')['status']=='PASS'
native=read(out/'NATIVE-ACCEPTANCE-POINTER.json');n=read(Path(native['directory'])/'results.json');assert n['status']=='PASS' and n['physical_pointer_test']=='PASS' and file_hash(Path(n['candidate']))==file_hash(b/'portable/DragonhydraIntelligence/DragonhydraIntelligence.exe');receipts['native']={'path':str(Path(native['directory'])/'results.json'),'checks':len(n['checks']),'physical_pointer_test':'PASS'}
assert read(out/'OFFLINE-MANUAL-ACCEPTANCE.json')['status']=='PASS'
assert file_hash(Path(read(out/'OFFLINE-MANUAL-ACCEPTANCE.json')['path']))==file_hash(b/'portable/DragonhydraIntelligence/Documentation/USER-MANUAL.html')
inputs=read(build['source_inputs']);repo=mission/'public-source';assert all(file_hash(ROOT/p)==h for p,h in inputs.items())
assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain']).strip(),'Preserve unexpected work in the source publication checkout'
assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD']).decode().strip()==read(out/'baseline/beta4-package.json')['source_commit'],'Source checkout advanced outside this checkpoint'
extra=['application/living_launch.py','tools/build_mission004.py','tools/write_beginner_help.py','tools/verify_beginner_preservation.py','tools/deliver_beginner_candidate.py','tools/open_beginner_candidate.py','tools/report_beginner_candidate.py','tests/test_beginner.py','tests/beginner_browser.py','tests/mission006_windows.py','tests/mission006_postgres_browser.py','tests/mission006_native_acceptance.py']
for name in [*inputs,*extra]:
    target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE)
git('add','--',*inputs,*extra);git('add','--renormalize','--',*inputs,*extra)
git('-c','user.name=chatgptopenaiagi','-c','user.email=chatgptopenaiagi@users.noreply.github.com','commit','-m','Add offline beginner guidance, football research and verified database health for beta.5')
commit=git('rev-parse','HEAD').decode().strip();assert all(hashlib.sha256(git('show',commit+':'+p.replace('\\','/'))).hexdigest()==h for p,h in inputs.items())
assert all(git('show',commit+':'+p.replace('\\','/'))==(ROOT/p).read_bytes() for p in extra)
dest=ROOT/'releases'/build['version']/b.name.replace('build-','candidate-');dest.mkdir(parents=True,exist_ok=False)
bundle=b/'portable/DragonhydraIntelligence';shutil.copytree(bundle,dest/bundle.name)
for name in ('portable','installer'):shutil.copy2(build[name],dest/Path(build[name]).name)
source=dest/('DRAGONHYDRA-Intelligence-'+build['version']+'-source.zip');git('archive','--format=zip','--output='+str(source),commit)
assets={p.name:{'sha256':file_hash(p),'bytes':p.stat().st_size} for p in dest.iterdir() if p.is_file()};files=read(bundle/'FILES-SHA256.json');assert all(file_hash(dest/bundle.name/p)==h for p,h in files.items())
with zipfile.ZipFile(build['portable']) as z:assert not [n for n in z.namelist() if Path(n).suffix.lower() in ('.dpapi','.sqlite3','.docx','.dump','.env')]
manifest={'at':now(),'status':'LOCAL_VERIFIED_CANDIDATE','version':build['version'],'directory':str(dest),'exe':str(dest/bundle.name/'DragonhydraIntelligence.exe'),'exe_sha256':file_hash(dest/bundle.name/'DragonhydraIntelligence.exe'),'source_commit':commit,'source_input_hash_matches':len(inputs),'portable_files_verified':len(files),'assets':assets,'published':False,'acceptance':receipts}
atomic_json(out/'PACKAGE-MANIFEST.json',manifest);atomic_json(dest/'PACKAGE-MANIFEST.json',manifest);atomic_json(dest/'RELEASE-SHA256.json',assets)
atomic_json(out/'SOURCE-PACKAGE-ASSOCIATION.json',{'status':'PASS','commit':commit,'build':str(b),'exact_git_blob_hash_matches':len(inputs),'private_data_files_in_portable':False,'published':False})
print(json.dumps({'status':'PASS','directory':str(dest),'commit':commit,'assets':assets}))
