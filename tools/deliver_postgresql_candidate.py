"""Associate exact tested inputs with a local Git commit and preserve a new release folder."""
import hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.contracts import atomic_json,now,file_hash
OUT=ROOT/'evidence/mission-006/postgresql';mission=OUT.parent
build=json.loads((mission/'latest-build.json').read_text());b=Path(build['build'])
final=json.loads((Path(json.loads((OUT/'latest-final-package.json').read_text())['directory'])/'results.json').read_text())
assert final['status']=='PASS' and final['build']['portable_sha256']==build['portable_sha256']
inputs=json.loads(Path(build['source_inputs']).read_text());repo=mission/'public-source'
assert all(file_hash(ROOT/p)==h for p,h in inputs.items())
for name in inputs:
    target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
# Include the unchanged executable entry point and reproducible transition tests/tools.
extra=['application/living_launch.py','tools/build_mission004.py','tools/verify_postgresql_transition.py','tools/deliver_postgresql_candidate.py','tools/report_postgresql_transition.py']
extra += [str(p.relative_to(ROOT)) for p in (ROOT/'tests').glob('*postgres*.py')]
extra += ['tests/mission006_native_acceptance.py','tests/mission006_windows.py']
for name in extra:
    target=repo/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
attributes=repo/'.gitattributes';content=attributes.read_text()
for rule in ('tools/** -text','tests/** -text'):
    if rule not in content:content+=rule+'\n'
attributes.write_text(content)
def git(*args):return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.PIPE)
git('add','--','.gitattributes',*inputs,*extra)
git('-c','user.name=chatgptopenaiagi','-c','user.email=chatgptopenaiagi@users.noreply.github.com','commit','-m','Verify PostgreSQL beta.4 packages and correct visible version and database layout')
commit=git('rev-parse','HEAD').decode().strip()
assert all(hashlib.sha256(git('show',commit+':'+p.replace('\\','/'))).hexdigest()==h for p,h in inputs.items())
assert all(git('show',commit+':'+p.replace('\\','/'))==(ROOT/p).read_bytes() for p in extra)
dest=ROOT/'releases'/build['version']/b.name.replace('build-','candidate-');dest.mkdir(parents=True,exist_ok=False)
bundle=b/'portable/DragonhydraIntelligence';shutil.copytree(bundle,dest/bundle.name)
for name in ('portable','installer'):shutil.copy2(build[name],dest/Path(build[name]).name)
source=dest/('DRAGONHYDRA-Intelligence-'+build['version']+'-source.zip');git('archive','--format=zip','--output='+str(source),commit)
assets={p.name:{'sha256':file_hash(p),'bytes':p.stat().st_size} for p in dest.iterdir() if p.is_file()}
files=json.loads((bundle/'FILES-SHA256.json').read_text());assert all(file_hash(dest/bundle.name/p)==h for p,h in files.items())
with zipfile.ZipFile(build['portable']) as z:
    private=[n for n in z.namelist() if Path(n).suffix.lower() in ('.dpapi','.sqlite3','.docx','.dump','.env')];assert not private
association={'at':now(),'status':'PASS','commit':commit,'build':str(b),'source_inputs':len(inputs),'exact_git_blob_hash_matches':len(inputs),'additional_verified_files':len(extra),'private_data_files_in_portable':private,'published':False,'byte_preservation':'Repository-local attributes; no global Git settings changed'}
manifest={'at':now(),'status':'LOCAL_VERIFIED_CANDIDATE','version':build['version'],'directory':str(dest),'exe':str(dest/bundle.name/'DragonhydraIntelligence.exe'),'source_commit':commit,'source_input_hash_matches':len(inputs),'portable_files_verified':len(files),'assets':assets,'published':False}
for name,value in [('SOURCE-PACKAGE-ASSOCIATION.json',association),('PACKAGE-MANIFEST.json',manifest)]:
    if (OUT/name).exists():shutil.copy2(OUT/name,OUT/(b.name+'-previous-'+name))
    atomic_json(OUT/name,value)
atomic_json(dest/'PACKAGE-MANIFEST.json',manifest);atomic_json(dest/'RELEASE-SHA256.json',assets)
print(json.dumps({'status':'PASS','directory':str(dest),'commit':commit,'assets':assets}))
