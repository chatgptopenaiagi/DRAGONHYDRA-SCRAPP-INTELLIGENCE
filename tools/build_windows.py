"""Build the Windows application and its per-user installer in a versioned staging directory."""
import hashlib,json,shutil,subprocess,sys,time,zipfile,importlib.metadata,argparse
from pathlib import Path
parser=argparse.ArgumentParser();parser.add_argument('--mission',default='006',choices=['004','005','006']);parser.add_argument('--version',default='0.3.0-beta.1');parser.add_argument('--reuse-build',type=Path,help='Reuse verified frozen Python only when all executable source inputs are unchanged');args=parser.parse_args();VERSION=args.version
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/('evidence/mission-'+args.mission);DOCS='docs/mission-'+args.mission;OUT.mkdir(parents=True,exist_ok=True);(ROOT/'dist').mkdir(exist_ok=True);
tag=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());run=OUT/('build-'+tag);run.mkdir();dist=run/'portable';work=run/'work';spec=run/'spec';spec.mkdir()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
sys.path.insert(0,str(ROOT/'application'))
from living.tk_runtime import configure
from tkinter import Tcl
configure()
Tcl().eval('info patchlevel')
assert VERSION in (ROOT/'application/living/__init__.py').read_text(), 'Source and requested package version disagree'
inputs={str(p.relative_to(ROOT)):sha(p) for folder in ('application/living','application/dragonhydra','application/intelligence','installer',DOCS,'docs/next-generation') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(run/'source-inputs.json').write_text(json.dumps(inputs,indent=2))
command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','DragonhydraIntelligence','--distpath',str(dist),'--workpath',str(work),'--specpath',str(spec),'--paths',str(ROOT/'application'),'--hidden-import','psutil','--hidden-import','websocket','--collect-all','psycopg','--collect-all','psycopg_binary','--hidden-import','pyodbc','--hidden-import','pypdf','--hidden-import','tkinter','--hidden-import','tkinter.ttk','--hidden-import','tkinter.messagebox','--hidden-import','tkinter.filedialog','--add-data',str(ROOT/'application/living/web')+';living/web',str(ROOT/'application/living_launch.py')]
if args.reuse_build:
    previous=json.loads((args.reuse_build/'source-inputs.json').read_text())
    assert all(previous.get(p)==h for p,h in inputs.items() if not p.replace('\\','/').startswith(('application/living/web/',DOCS+'/'))),'Executable inputs changed; full recompilation required'
    old=args.reuse_build/'portable/DragonhydraIntelligence';old_hashes=json.loads((old/'FILES-SHA256.json').read_text())
    assert all(sha(old/p)==h for p,h in old_hashes.items()),'Previous bundle hash mismatch'
    shutil.copytree(old,dist/'DragonhydraIntelligence')
    shutil.copytree(ROOT/'application/living/web',dist/'DragonhydraIntelligence/_internal/living/web',dirs_exist_ok=True)
    (run/'pyinstaller.log').write_text('Frozen executable reused after source and bundle hash verification. Only static web/documentation inputs may change.\n')
else:
    with (run/'pyinstaller.log').open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
bundle=dist/'DragonhydraIntelligence';shutil.copytree(ROOT/DOCS,bundle/'Documentation',dirs_exist_ok=True);shutil.copytree(ROOT/'docs/next-generation',bundle/'Documentation/next-generation',dirs_exist_ok=True)
licenses=bundle/'ThirdParty';licenses.mkdir(exist_ok=True)
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
for distribution in ('pypdf','pyinstaller','psutil','websocket-client'):
    d=importlib.metadata.distribution(distribution)
    for f in d.files or []:
        if any(word in str(f).lower() for word in ('license','copying')) and '..' not in f.parts:
            source=Path(d.locate_file(f))
            if source.is_file():shutil.copy2(source,licenses/(distribution+'-'+source.name))
(licenses/'DEPENDENCIES.json').write_text(json.dumps({'python':sys.version,'pypdf':importlib.metadata.version('pypdf'),'packager':importlib.metadata.version('pyinstaller'),'note':'Tcl/Tk and standard-library runtime resources are bundled by the existing packager. DRAGONHYDRA CORE code is retained from the owner-provided project.'},indent=2))
(bundle/'README.txt').write_text('DRAGONHYDRA SCRAPP INTELLIGENCE '+VERSION+'\nRun DragonhydraIntelligence.exe. Use Start / open dashboard in the native launcher.\nDefault user state: %LOCALAPPDATA%/DRAGONHYDRA/LivingIntelligence. No source directory, Conda, or Python installation required.\nSQLite is the default. An explicitly configured local PostgreSQL datastore is optional. No live bookmaker feed is included.\nNo private datasets or machine-specific evidence are included in this package. See Documentation.\n',encoding='utf-8')
if not any(bundle.rglob('_tkinter.pyd')) or not any(bundle.rglob('init.tcl')) or not any(bundle.rglob('tk.tcl')):
    raise RuntimeError('The native launcher requires the bundled Tk extension and Tcl/Tk scripts')
hashes={p.relative_to(bundle).as_posix():sha(p) for p in bundle.rglob('*') if p.is_file() and p.name!='FILES-SHA256.json'};(bundle/'FILES-SHA256.json').write_text(json.dumps(hashes,indent=2))
archive=ROOT/'dist'/('DRAGONHYDRA-Intelligence-'+VERSION+'-portable-'+tag+'.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in bundle.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(dist))
archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
payload=run/'installer_payload';payload.mkdir();shutil.copy2(archive,payload/'portable.zip');(payload/'portable.sha256').write_text(sha(archive))
installer_dist=run/'installer';command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--windowed','--name','DRAGONHYDRA-Intelligence-Setup-'+VERSION,'--distpath',str(installer_dist),'--workpath',str(run/'installer-work'),'--specpath',str(spec),'--add-data',str(payload)+';installer_payload',str(ROOT/'installer/installer.py')]
with (run/'installer-build.log').open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
setup=installer_dist/('DRAGONHYDRA-Intelligence-Setup-'+VERSION+'.exe');destination=ROOT/'dist'/('DRAGONHYDRA-Intelligence-Setup-'+VERSION+'-'+tag+'.exe');shutil.copy2(setup,destination)
assert all(sha(ROOT/p)==h for p,h in inputs.items()),'Source changed while packaging; preserve this attempt and rebuild the stable checkpoint'
result={'status':'BUILT_NOT_YET_INDEPENDENTLY_TESTED','version':VERSION,'build':str(run),'portable':str(archive),'portable_sha256':sha(archive),'portable_bytes':archive.stat().st_size,'installer':str(destination),'installer_sha256':sha(destination),'installer_bytes':destination.stat().st_size,'bundled_files':len(hashes),'private_datasets_included':False,'development_interpreter':sys.executable,'source_inputs':str(run/'source-inputs.json'),'source_unchanged_during_build':True}
(OUT/'latest-build.json').write_text(json.dumps(result,indent=2));(run/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
