"""Per-user Windows installer with manifest-scoped upgrades and data-preserving uninstall."""
import argparse,hashlib,json,os,shutil,subprocess,sys,tempfile,time,zipfile
from pathlib import Path

OWNER='DRAGONHYDRA-LivingIntelligence';VERSION='0.2.0-beta.5';KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\DRAGONHYDRA-LivingIntelligence';ISOLATED=False;SHORTCUT='DRAGONHYDRA Intelligence.lnk'

def registration_scope(target,isolated=False):
    global KEY,ISOLATED,SHORTCUT
    marker=Path(target)/'INSTALLATION.json'
    prior=json.loads(marker.read_text()) if marker.is_file() else {}
    ISOLATED=bool(isolated or prior.get('isolated_registration'))
    if ISOLATED:
        suffix=hashlib.sha256(str(Path(target).resolve()).encode()).hexdigest()[:12]
        KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\DRAGONHYDRA-LivingIntelligence-Acceptance-'+suffix
        SHORTCUT='DRAGONHYDRA Intelligence Acceptance '+suffix+'.lnk'
def save(path,value):
    temporary=path.with_name(path.name+'.tmp')
    with temporary.open('w',encoding='utf-8') as stream:json.dump(value,stream,indent=2);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)
def digest(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def root_path(path):
    path=Path(path).resolve()
    if path==Path(path.anchor) or len(path.parts)<3:raise ValueError('Unsafe installation target')
    return path
def contained(root,relative):
    path=(root/relative).resolve()
    if not path.is_relative_to(root) or path==root:raise ValueError('Manifest path escaped installation')
    return path
def active(target):
    if os.name!='nt':return False
    import ctypes
    from ctypes import wintypes
    processes=(wintypes.DWORD*8192)();needed=wintypes.DWORD()
    ctypes.windll.psapi.EnumProcesses(processes,ctypes.sizeof(processes),ctypes.byref(needed))
    kernel=ctypes.windll.kernel32;kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.QueryFullProcessImageNameW.argtypes=[wintypes.HANDLE,wintypes.DWORD,wintypes.LPWSTR,ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    for pid in processes[:needed.value//4]:
        if pid==os.getpid():continue
        handle=kernel.OpenProcess(0x1000,False,pid)
        if not handle:continue
        try:
            buf=ctypes.create_unicode_buffer(32768);size=wintypes.DWORD(len(buf))
            if kernel.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(size)) and Path(buf.value).resolve().is_relative_to(target):return True
        finally:kernel.CloseHandle(handle)
    return False
def shortcut(target):
    scripts=target/'shortcut.ps1'
    # Paths are literal PowerShell single-quoted values; embedded quotes are escaped.
    q=lambda s:"'"+str(s).replace("'","''")+"'"
    menu=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'/SHORTCUT
    content="$w=New-Object -ComObject WScript.Shell\n$s=$w.CreateShortcut("+q(menu)+")\n$s.TargetPath="+q(target/'DragonhydraIntelligence.exe')+"\n$s.WorkingDirectory="+q(target)+"\n$s.Description='DRAGONHYDRA Living Intelligence Center'\n$s.Save()\n"
    scripts.write_text(content,encoding='utf-8')
    powershell=Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
    result=subprocess.run([str(powershell),'-NoProfile','-ExecutionPolicy','Bypass','-File',str(scripts)],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Start-menu shortcut creation failed')
    return str(menu)
def register(target):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,KEY) as key:
        for name,value in {'DisplayName':'DRAGONHYDRA Intelligence','DisplayVersion':VERSION,'Publisher':'DRAGONHYDRA','InstallLocation':str(target),'DisplayIcon':str(target/'DragonhydraIntelligence.exe'),'UninstallString':'"'+str(target/'Uninstall-DRAGONHYDRA.exe')+'" --uninstall --target "'+str(target)+'"','NoModify':1,'NoRepair':1}.items():winreg.SetValueEx(key,name,0,winreg.REG_DWORD if isinstance(value,int) else winreg.REG_SZ,value)
def install(target):
    target=root_path(target)
    if active(target):raise ValueError('Close the launcher and stop this installed candidate before upgrading')
    prior=None
    if target.exists() and any(target.iterdir()):
        marker=target/'INSTALLATION.json'
        if not marker.exists() or json.loads(marker.read_text()).get('owner')!=OWNER:raise ValueError('Refusing an unowned installation directory')
        prior=json.loads(marker.read_text())
    payload=Path(getattr(sys,'_MEIPASS',Path(__file__).parent))/'installer_payload/portable.zip'
    expected=(payload.parent/'portable.sha256').read_text().strip()
    if digest(payload)!=expected:raise ValueError('Installer payload hash mismatch')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=target.name+'.stage-',dir=target.parent)).resolve()
    files=[]
    with zipfile.ZipFile(payload) as z:
        if z.testzip():raise ValueError('Installer payload CRC failure')
        for item in z.infolist():
            parts=Path(item.filename).parts
            if not parts or parts[0]!='DragonhydraIntelligence':raise ValueError('Unexpected archive root')
            relative=Path(*parts[1:])
            if not relative.parts:continue
            dest=contained(stage,relative)
            if item.is_dir():dest.mkdir(parents=True,exist_ok=True);continue
            dest.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as src,dest.open('wb') as out:shutil.copyfileobj(src,out)
            files.append(relative.as_posix())
    hashes=json.loads((stage/'FILES-SHA256.json').read_text())
    if not all(digest(contained(stage,p))==h for p,h in hashes.items()):raise ValueError('Extracted installation hash mismatch')
    if getattr(sys,'frozen',False):shutil.copy2(sys.executable,stage/'Uninstall-DRAGONHYDRA.exe');files.append('Uninstall-DRAGONHYDRA.exe')
    # Preserve unowned extras on upgrade; do not silently drop user files.
    if prior:
        owned=set(prior['files'])|{'INSTALLATION.json'}
        for p in target.rglob('*'):
            if p.is_file() and p.relative_to(target).as_posix() not in owned:
                dest=contained(stage,p.relative_to(target));dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists():raise ValueError('Unowned file conflicts with new release')
                shutil.copy2(p,dest)
    old=None
    if target.exists():
        old=target.with_name(target.name+'.previous-'+str(time.time_ns()))
        if old.exists() or not old.resolve().is_relative_to(target.parent):raise ValueError('Unsafe upgrade preservation path')
        target.rename(old)
    try:stage.rename(target)
    except BaseException:
        if old:old.rename(target)
        raise
    files.append('shortcut.ps1')
    marker={'owner':OWNER,'version':VERSION,'files':files,'shortcut':None,'isolated_registration':ISOLATED,'registration_key':KEY,'data_preserved':True,'prior_installation':str(old) if old else None,'payload_sha256':expected,'status':'REGISTRATION_PENDING'}
    save(target/'INSTALLATION.json',marker)
    link=shortcut(target);register(target);marker.update(shortcut=link,status='INSTALLED')
    save(target/'INSTALLATION.json',marker)
    return marker
def uninstall(target):
    target=root_path(target);marker=target/'INSTALLATION.json'
    if not marker.exists():raise ValueError('Installation ownership record missing')
    record=json.loads(marker.read_text())
    if record.get('owner')!=OWNER:raise ValueError('Refusing unowned directory')
    if active(target):raise ValueError('Stop the installed candidate and close its launcher first')
    # A copied uninstaller runs outside the installation to avoid deleting a running image.
    if getattr(sys,'frozen',False) and Path(sys.executable).resolve().is_relative_to(target):
        temp=Path(tempfile.mkdtemp(prefix='DRAGONHYDRA-uninstall-'))/'uninstall.exe';shutil.copy2(sys.executable,temp)
        subprocess.Popen([str(temp),'--uninstall','--silent','--target',str(target)],creationflags=subprocess.CREATE_NO_WINDOW);return {'status':'UNINSTALLING','helper':str(temp)}
    current_root=target;current_record=record;visited=set()
    while True:
        if current_root in visited:raise ValueError('Invalid rollback chain')
        visited.add(current_root)
        for relative in current_record['files']:
            p=contained(current_root,relative)
            if p.is_file():p.unlink()
        (current_root/'INSTALLATION.json').unlink()
        for p in sorted(current_root.rglob('*'),key=lambda x:len(x.parts),reverse=True):
            if p.is_dir() and p.resolve().is_relative_to(current_root) and not any(p.iterdir()):p.rmdir()
        if not any(current_root.iterdir()):current_root.rmdir()
        previous=current_record.get('prior_installation')
        if not previous:break
        previous=Path(previous).resolve()
        if previous.parent!=target.parent or not previous.name.startswith(target.name+'.previous-'):raise ValueError('Rollback folder lies outside the owned installation chain')
        if not (previous/'INSTALLATION.json').is_file():break
        previous_record=json.loads((previous/'INSTALLATION.json').read_text())
        if previous_record.get('owner')!=OWNER:raise ValueError('Rollback folder ownership mismatch')
        current_root=previous;current_record=previous_record
    expected=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'/SHORTCUT
    if record.get('shortcut')==str(expected) and expected.exists():expected.unlink()
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,KEY) as key:installed=winreg.QueryValueEx(key,'InstallLocation')[0]
        if Path(installed).resolve()==target:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,KEY)
    except FileNotFoundError:pass
    # User data and unowned extra files survive; owned rollback program files are removed.
    return {'status':'UNINSTALLED','user_data_preserved':True}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target',type=Path,default=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Programs/DRAGONHYDRA Intelligence');parser.add_argument('--silent',action='store_true');parser.add_argument('--uninstall',action='store_true');parser.add_argument('--receipt',type=Path);parser.add_argument('--isolated-registration',action='store_true',help=argparse.SUPPRESS);a=parser.parse_args();registration_scope(a.target,a.isolated_registration)
    if a.silent:
        try:
            result=uninstall(a.target) if a.uninstall else install(a.target)
            if a.receipt:a.receipt.write_text(json.dumps({'status':'PASS','result':result},indent=2))
        except Exception as e:
            if a.receipt:a.receipt.write_text(json.dumps({'status':'FAIL','error':str(e),'error_type':type(e).__name__},indent=2))
            sys.exit(1)
        return
    import tkinter as tk
    from tkinter import ttk,messagebox,filedialog
    root=tk.Tk();root.title('DRAGONHYDRA Intelligence Setup');root.geometry('650x300');frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='DRAGONHYDRA Intelligence',font=('Segoe UI',22,'bold')).pack(anchor='w');ttk.Label(frame,text=VERSION+' · per-user Windows x64 installation').pack(anchor='w',pady=8)
    path=tk.StringVar(value=str(a.target));ttk.Entry(frame,textvariable=path).pack(fill='x',pady=10)
    ttk.Label(frame,text='Your observations remain in your local application data directory.\nUpgrades preserve the previous program folder for rollback.\nPostgreSQL integration is explicitly configured; SQLite offline operation remains available.').pack(anchor='w',pady=8)
    def go():
        try:
            result=uninstall(path.get()) if a.uninstall else install(path.get());messagebox.showinfo('DRAGONHYDRA',('Uninstall requested. User data is preserved.' if a.uninstall else 'Installation complete. Open DRAGONHYDRA from the Start menu.'));root.destroy()
        except Exception as e:messagebox.showerror('Setup did not complete',str(e))
    ttk.Button(frame,text='Uninstall' if a.uninstall else 'Install / upgrade',command=go).pack(anchor='e',pady=12);root.mainloop()
if __name__=='__main__':main()
