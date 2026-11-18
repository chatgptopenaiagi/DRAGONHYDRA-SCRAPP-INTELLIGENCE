"""Reuse the installed PyInstaller toolchain; all outputs belong to Mission 004."""
import hashlib,json,shutil,subprocess,sys,time,zipfile,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evidence/mission-004';tag=time.strftime('%Y%m%dT%H%M%SZ',time.gmtime());run=OUT/('build-'+tag);OUT.mkdir(parents=True,exist_ok=True);(ROOT/'dist').mkdir(exist_ok=True);run.mkdir();dist=run/'portable';work=run/'work';spec=run/'spec';spec.mkdir()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
inputs={str(p.relative_to(ROOT)):sha(p) for folder in ('application/living','installer','docs/mission-004') for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(run/'source-inputs.json').write_text(json.dumps(inputs,indent=2))
command=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','DragonhydraIntelligence','--distpath',str(dist),'--workpath',str(work),'--specpath',str(spec),'--paths',str(ROOT/'application'),'--hidden-import','pypdf','--hidden-import','tkinter','--hidden-import','tkinter.ttk','--hidden-import','tkinter.messagebox','--hidden-import','tkinter.filedialog','--add-data',str(ROOT/'application/living/web')+';living/web',str(ROOT/'application/living_launch.py')]
with (run/'pyinstaller.log').open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
bundle=dist/'DragonhydraIntelligence';shutil.copytree(ROOT/'docs/mission-004',bundle/'Documentation')
licenses=bundle/'ThirdParty';licenses.mkdir()
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copy2(python_license,licenses/'Python-LICENSE.txt')
for distribution in ('pypdf','pyinstaller'):
    d=importlib.metadata.distribution(distribution)
    for f in d.files or []:
        if any(word in str(f).lower() for word in ('license','copying')) and '..' not in f.parts:
            source=Path(d.locate_file(f))
            if source.is_file():shutil.copy2(source,licenses/(distribution+'-'+source.name))
(licenses/'DEPENDENCIES.json').write_text(json.dumps({'python':sys.version,'pypdf':importlib.metadata.version('pypdf'),'packager':importlib.metadata.version('pyinstaller'),'note':'Tcl/Tk and standard-library runtime resources are bundled by the existing packager. DRAGONHYDRA CORE code is retained from the owner-provided project.'},indent=2))
(bundle/'README.txt').write_text('DRAGONHYDRA SCRAPP INTELLIGENCE 0.2.0-beta.1\nRun DragonhydraIntelligence.exe. Use Start / open dashboard in the native launcher.\nDefault user state: %LOCALAPPDATA%/DRAGONHYDRA/LivingIntelligence. No source directory, Conda, or Python installation required.\nOffline and configured connected modes use SQLite. SQL integration remains BLOCKED. No live bookmaker feed is included.\nNo private datasets or machine-specific evidence are included in this package. See Documentation.\n',encoding='utf-8')
hashes={p.relative_to(bundle).as_posix():sha(p) for p in bundle.rglob('*') if p.is_file()};(bundle/'FILES-SHA256.json').write_text(json.dumps(hashes,indent=2))
archive=ROOT/'dist'/('DRAGONHYDRA-Intelligence-0.2.0-beta.1-portable-'+tag+'.zip')
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in bundle.rglob('*'):
        if p.is_file():z.write(p,p.relative_to(dist))
archive.with_suffix('.zip.sha256').write_text(sha(archive)+'  '+archive.name+'\n')
payload=run/'installer_payload';payload.mkdir();shutil.copy2(archive,payload/'portable.zip');(payload/'portable.sha256').write_text(sha(archive))
installer_dist=run/'installer';command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--windowed','--name','DRAGONHYDRA-Intelligence-Setup-0.2.0-beta.1','--distpath',str(installer_dist),'--workpath',str(run/'installer-work'),'--specpath',str(spec),'--add-data',str(payload)+';installer_payload',str(ROOT/'installer/installer.py')]
with (run/'installer-build.log').open('w') as log:subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
setup=installer_dist/'DRAGONHYDRA-Intelligence-Setup-0.2.0-beta.1.exe';destination=ROOT/'dist'/('DRAGONHYDRA-Intelligence-Setup-0.2.0-beta.1-'+tag+'.exe');shutil.copy2(setup,destination)
assert all(sha(ROOT/p)==h for p,h in inputs.items()),'Source changed while packaging; preserve this attempt and rebuild the stable checkpoint'
result={'status':'BUILT_NOT_YET_INDEPENDENTLY_TESTED','version':'0.2.0-beta.1','build':str(run),'portable':str(archive),'portable_sha256':sha(archive),'portable_bytes':archive.stat().st_size,'installer':str(destination),'installer_sha256':sha(destination),'installer_bytes':destination.stat().st_size,'bundled_files':len(hashes),'private_datasets_included':False,'development_interpreter':sys.executable,'source_inputs':str(run/'source-inputs.json'),'source_unchanged_during_build':True}
(OUT/'latest-build.json').write_text(json.dumps(result,indent=2));(run/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
