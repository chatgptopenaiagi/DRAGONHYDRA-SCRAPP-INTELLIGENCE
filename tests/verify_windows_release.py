"""Check an extracted release ZIP and install/upgrade/uninstall in a fresh per-user target."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile
from next_windows import run, VERSION


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def native(exe, data):
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV','TCL_','TK_'))}
    env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot']
    p=subprocess.Popen([str(exe),'--data-dir',str(data),'--port','0'],cwd=data.parent,env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    user=ctypes.windll.user32;windows=[]
    @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd,_):
        pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value==p.pid:
            text=ctypes.create_unicode_buffer(300);user.GetWindowTextW(hwnd,text,len(text))
            if text.value=='DRAGONHYDRA Intelligence · '+VERSION:windows.append(hwnd)
        return True
    try:
        end=time.monotonic()+30
        while time.monotonic()<end and not windows and p.poll() is None:
            user.EnumWindows(visit,0);time.sleep(.1)
        if not windows:raise RuntimeError('Versioned native launcher window did not open')
        user.PostMessageW(wintypes.HWND(windows[0]),0x10,0,0)
        if p.wait(15)!=0:raise RuntimeError('Native launcher failed to close cleanly')
    finally:
        if p.poll() is None:p.terminate();p.wait(10)


def verify(portable, installer, out):
    out.mkdir(parents=True,exist_ok=False)
    extracted=out/'extracted'
    with zipfile.ZipFile(portable) as archive:
        assert archive.testzip() is None
        for item in archive.infolist():
            dest=(extracted/item.filename).resolve()
            assert dest.is_relative_to(extracted/'DragonhydraIntelligence')
        archive.extractall(extracted)
    bundle=extracted/'DragonhydraIntelligence';manifest=json.loads((bundle/'FILES-SHA256.json').read_text())
    files={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file()}
    assert files==set(manifest)|{'FILES-SHA256.json'}
    assert all(sha(bundle/name)==digest for name,digest in manifest.items())
    assert not any(Path(k).suffix.lower() in {'.dpapi','.db','.sqlite','.sqlite3','.docx','.env','.dump','.key'} for k in files)
    exe=bundle/'DragonhydraIntelligence.exe';native(exe,out/'native-portable')
    run(out/'portable-browser',exe)
    target=out/'installation'
    def setup(label,remove=False):
        receipt=out/(label+'.json');args=[str(installer),'--silent','--isolated-registration','--target',str(target),'--receipt',str(receipt)]
        subprocess.run(args+(['--uninstall'] if remove else []),check=True,cwd=out,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
        assert json.loads(receipt.read_text())['status']=='PASS'
    setup('install')
    assert all(sha(target/name)==digest for name,digest in manifest.items())
    native(target/exe.name,out/'native-installed')
    run(out/'installed-browser',target/exe.name)
    marker=target/'user-preservation.txt';marker.write_text('synthetic local note')
    setup('upgrade');assert marker.read_text()=='synthetic local note'
    assert sha(target/exe.name)==sha(exe)
    setup('uninstall',True);assert marker.read_text()=='synthetic local note' and not (target/exe.name).exists()
    assert (out/'installed-browser/data/intelligence.sqlite3').exists()
    result={'status':'PASS','version':VERSION,'manifest_files':len(manifest),'portable_sha256':sha(portable),'installer_sha256':sha(installer),
            'executable_sha256':sha(exe),'native_windows_opened_and_closed':2,'install_upgrade_uninstall':'PASS',
            'browser_runs':{k:json.loads((out/k/'result.json').read_text()) for k in ('portable-browser','installed-browser')}}
    (out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ['portable','installer','out']:p.add_argument('--'+arg,required=True,type=Path)
    a=p.parse_args();verify(a.portable.resolve(),a.installer.resolve(),a.out.resolve())
