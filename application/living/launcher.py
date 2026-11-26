"""DH-UI native launcher and process ownership. Never stops a process by stale PID."""
import argparse,json,os,sqlite3,subprocess,sys,time,webbrowser,hmac,secrets,socket
from contextlib import closing
from pathlib import Path
from .contracts import now,atomic_json,fingerprint,file_hash
from .security import local_secret

class Lease:
    def __init__(self,path):self.path=Path(path);self.stream=None
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True);self.stream=self.path.open('a+b');self.stream.seek(0);self.stream.write(b'0');self.stream.flush();self.stream.seek(0)
        try:
            if os.name=='nt':__import__('msvcrt').locking(self.stream.fileno(),__import__('msvcrt').LK_NBLCK,1)
            else:__import__('fcntl').flock(self.stream,__import__('fcntl').LOCK_EX|__import__('fcntl').LOCK_NB)
        except OSError:self.stream.close();raise RuntimeError('This dataset already has a running DRAGONHYDRA worker') from None
        return self
    def __exit__(self,*args):self.stream.close()
def request(data,path,body=None):
    import http.client
    ready=json.loads((Path(data)/'ready.json').read_text());port=ready['port']
    if not isinstance(port,int) or not 1024<=port<=65535:raise ValueError('Invalid ready-file port')
    secret=(Path(data)/'private/launcher.key').read_text().strip();c=http.client.HTTPConnection('127.0.0.1',port,timeout=10)
    try:
        challenge=secrets.token_hex(32);c.request('GET','/auth/identity?challenge='+challenge);probe=c.getresponse();identity=json.loads(probe.read(4096));data_id=fingerprint(str(Path(data).resolve()))
        proof=hmac.new(secret.encode(),(challenge+'|'+data_id).encode(),'sha256').hexdigest()
        if probe.status!=200 or identity.get('data_id')!=data_id or not hmac.compare_digest(identity.get('proof',''),proof):raise RuntimeError('The listening service does not own this data directory. Its credentials were not sent.')
        c.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,{'X-DH-Local':secret,'Content-Type':'application/json'})
        r=c.getresponse();result=json.loads(r.read())
        if r.status>=400:raise RuntimeError(result.get('error','Operation failed'))
        return result
    finally:c.close()
def running(data):
    try:
        state=request(data,'/api/status')
        return state if state['data_id']==fingerprint(str(Path(data).resolve())) else None
    except (OSError,ValueError,KeyError,RuntimeError):return None
def open_dashboard(data,view='overview'):
    ticket=request(data,'/api/session-ticket',{})['ticket'];ready=json.loads((Path(data)/'ready.json').read_text());url=f'http://127.0.0.1:{ready["port"]}/#ticket={ticket}&view={view}'
    webbrowser.open(url)
def ensure(data,port=18977,mode='offline',guard=None):
    data=Path(data).resolve()
    existing=running(data)
    if existing:
        from . import VERSION
        if existing.get('version')!=VERSION:raise ValueError('This data directory is already served by DRAGONHYDRA '+str(existing.get('version','unknown'))+'. This launcher is '+VERSION+'. Keep that instance for rollback and select a separate data directory and free port, or stop it deliberately before a verified upgrade. No running service was changed.')
        if existing['mode']!=mode:request(data,'/api/mode',{'mode':mode});existing=running(data)
        return existing
    data.mkdir(parents=True,exist_ok=True)
    if (data/'offline-demo.sqlite3').exists():raise ValueError('The original candidate data directory is protected; select another directory')
    with Lease(data/'worker.lock'):pass
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',port))
        except OSError:raise ValueError(f'Port {port} is occupied by another service. Select port 0 (Find free port) to use an independent service. No process was stopped.') from None
    ready=data/'ready.json'
    if ready.exists():ready.rename(data/('ready.stale-'+str(time.time_ns())+'.json'))
    cmd=[sys.executable]+([] if getattr(sys,'frozen',False) else [str(Path(__file__).parents[1]/'living_launch.py')])
    cmd+=['--serve','--data-dir',str(data),'--port',str(port),'--mode',mode]
    if guard:cmd+=['--sql-guard',str(guard)]
    log=(data/('startup-'+str(time.time_ns())+'.log')).open('w')
    process=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));log.close()
    deadline=time.monotonic()+25
    while time.monotonic()<deadline and process.poll() is None:
        state=running(data)
        if state:return state
        time.sleep(.15)
    raise RuntimeError('Startup failed or port is occupied. Inspect the timestamped startup log; the original instance was not stopped.')
def stop(data):
    if not running(data):return
    request(data,'/api/shutdown',{})
    deadline=time.monotonic()+35
    while running(data) and time.monotonic()<deadline:time.sleep(.1)
    if running(data):raise RuntimeError('Shutdown has not completed; data retained')
def restore(data,backup):
    data=Path(data).resolve();backup=Path(backup).resolve()
    if running(data):raise ValueError('Stop this candidate before restoring')
    from .storage import Store,OWNER
    with Lease(data/'worker.lock'):
        with closing(sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True)) as c:
            if dict(c.execute('SELECT key,value FROM metadata')).get('owner')!=OWNER or c.execute('PRAGMA user_version').fetchone()[0] not in (2,3) or c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid or foreign backup')
            target=data/('restore-'+str(time.time_ns())+'.sqlite3')
            with closing(sqlite3.connect(target)) as out:c.backup(out)
        current=data/'intelligence.sqlite3'
        if current.exists():
            store=Store(current)
            try:store.backup(data/'backups'/('before-restore-'+str(time.time_ns())+'.sqlite3'))
            finally:store.close()
            # Closed SQLite connections have checkpointed WAL; preserve any sidecars rather than delete them.
            for suffix in ('-wal','-shm'):
                side=Path(str(current)+suffix)
                if side.exists():side.rename(data/(side.name+'.preserved-'+str(time.time_ns())))
        os.replace(target,current)
def serve(args):
    from .core import Runtime
    from .server import Server
    data=Path(args.data_dir).resolve();data.mkdir(parents=True,exist_ok=True)
    if (data/'offline-demo.sqlite3').exists():raise ValueError('Original legacy database directory is protected')
    with Lease(data/'worker.lock'):
        rt=None;server=None
        try:
            secret=local_secret(data);bridge_secret=local_secret(data,'bridge.key');rt=Runtime(data,args.mode,args.sql_guard,getattr(args,'mock_provider_origin',()));server=Server(('127.0.0.1',args.port),rt,secret,bridge_secret)
            atomic_json(data/'ready.json',dict(pid=os.getpid(),port=server.server_address[1],data_id=fingerprint(str(data)),started_at=now(),version=__import__('living').VERSION))
            server.serve_forever(poll_interval=.1)
        except BaseException as e:
            atomic_json(data/('crash-'+str(time.time_ns())+'.json'),{'at':now(),'error_type':type(e).__name__,'message':'Startup/runtime failed; original evidence retained'})
            raise
        finally:
            if server:server.server_close()
            if rt:rt.close()
            if (data/'ready.json').exists():
                ready=json.loads((data/'ready.json').read_text())
                if ready.get('pid')==os.getpid():(data/'ready.json').rename(data/('ready.stopped-'+str(time.time_ns())+'.json'))
def native(args):
    from .tk_runtime import configure
    configure()
    import tkinter as tk
    from tkinter import ttk,messagebox,filedialog
    from . import VERSION
    root=tk.Tk();root.title('DRAGONHYDRA Intelligence · '+VERSION);root.geometry('700x650');root.minsize(660,600)
    style=ttk.Style();style.theme_use('clam')
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='DRAGONHYDRA',font=('Segoe UI',24,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Living Intelligence Center · evidence before interpretation').pack(anchor='w',pady=(0,18))
    data=tk.StringVar(value=str(args.data_dir));mode=tk.StringVar(value=args.mode);status=tk.StringVar(value='Checking local application…')
    ttk.Label(frame,text='Selected data directory').pack(anchor='w');ttk.Entry(frame,textvariable=data).pack(fill='x',pady=5)
    modes=ttk.Frame(frame);modes.pack(fill='x')
    ttk.Radiobutton(modes,text='Offline',variable=mode,value='offline').pack(side='left');ttk.Radiobutton(modes,text='Configured connections',variable=mode,value='connected').pack(side='left',padx=20)
    port=tk.IntVar(value=args.port);ports=ttk.Frame(frame);ports.pack(fill='x',pady=8);ttk.Label(ports,text='Local port (0 chooses a free port)').pack(side='left');ttk.Entry(ports,textvariable=port,width=8).pack(side='left',padx=8);ttk.Button(ports,text='Find free port',command=lambda:port.set(0)).pack(side='left')
    ttk.Label(frame,textvariable=status,wraplength=610).pack(fill='x',pady=16)
    def action(fn):
        try:fn();refresh()
        except Exception as e:messagebox.showerror('DRAGONHYDRA',str(e))
    def start():ensure(data.get(),port.get(),mode.get(),args.sql_guard);open_dashboard(data.get())
    def view(name):ensure(data.get(),port.get(),mode.get(),args.sql_guard);open_dashboard(data.get(),name)
    def backup():
        ensure(data.get(),port.get(),mode.get(),args.sql_guard);r=request(data.get(),'/api/backup',{});messagebox.showinfo('Verified backup',r['name']+'\nSHA-256: '+r['sha256'])
    def restore_ui():
        state=running(data.get())
        if state and state.get('postgresql',{}).get('primary')=='POSTGRESQL':view('postgresql');return
        path=filedialog.askopenfilename(title='Select DRAGONHYDRA backup',filetypes=[('SQLite backup','*.sqlite3')])
        if path and messagebox.askyesno('Restore selected candidate','Stop this candidate and restore the selected backup? The current database will be backed up first.'):
            stop(data.get());restore(data.get(),path);ensure(data.get(),port.get(),mode.get(),args.sql_guard)
    buttons=ttk.Frame(frame);buttons.pack(fill='x')
    entries=[('Start / open dashboard',start),('System health',lambda:view('overview')),('Data sources',lambda:view('sources')),('Active tasks',lambda:view('recovery')),('Selected database',lambda:messagebox.showinfo('Database',str((running(data.get()) or {}).get('database',Path(data.get())/'intelligence.sqlite3')))),('Create verified backup',backup),('Restore a backup',restore_ui),('Diagnostics',lambda:view('diagnostics')),('Revoke browser sessions',lambda:request(data.get(),'/api/revoke',{})),('Stop gracefully',lambda:stop(data.get()))]
    for i,(label,fn) in enumerate(entries):ttk.Button(buttons,text=label,command=lambda f=fn:action(f)).grid(row=i//2,column=i%2,sticky='ew',padx=4,pady=5)
    buttons.columnconfigure(0,weight=1);buttons.columnconfigure(1,weight=1)
    ttk.Label(frame,text='Closing this launcher leaves the intelligence service running.\nUse Stop gracefully to stop collection and close the database.',wraplength=610).pack(anchor='w',pady=18)
    def refresh():
        state=running(data.get());status.set(f"Ready · {state['mode']} · {state['summary']['observations']} observations · PostgreSQL {state['postgresql']['state']}" if state else 'Stopped · Start to check database integrity and open an authenticated session')
    refresh();root.mainloop()
def main():
    default=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'DRAGONHYDRA/LivingIntelligence'
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');p.add_argument('--open',action='store_true');p.add_argument('--stop',action='store_true');p.add_argument('--data-dir',type=Path,default=default);p.add_argument('--port',type=int,default=18977);p.add_argument('--mode',choices=['offline','connected'],default='offline');p.add_argument('--sql-guard');p.add_argument('--mock-provider-origin',action='append',default=[],help=argparse.SUPPRESS);a=p.parse_args()
    if a.port!=0 and not 1024<=a.port<=65535:p.error('Port must be zero or 1024..65535')
    if a.serve:serve(a)
    elif a.stop:stop(a.data_dir)
    elif a.open:ensure(a.data_dir,a.port,a.mode,a.sql_guard);open_dashboard(a.data_dir)
    else:native(a)
