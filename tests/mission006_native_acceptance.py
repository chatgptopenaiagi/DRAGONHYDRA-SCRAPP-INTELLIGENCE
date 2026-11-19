"""Click actual packaged Tk controls; capture OS browser handoff into isolated Edge."""
import ctypes,json,os,subprocess,sys,time
from ctypes import wintypes
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.launcher import running,stop
from browser_cdp import Browser
OUT=ROOT/'evidence/mission-006'/('native-acceptance-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));OUT.mkdir();portable=json.loads((ROOT/'evidence/mission-006/PORTABLE-LOCATION.json').read_text());data=OUT/'data';handoff=OUT/'browser-handoff.json';helper=OUT/'browser-handoff.py';helper.write_text('import sys,json\nfrom pathlib import Path\nPath('+repr(str(handoff))+').write_text(json.dumps(sys.argv[1]))\n');env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV'))};env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot'];env['BROWSER']='"'+Path(sys.executable).as_posix()+'" "'+helper.as_posix()+'" %s';checks=[];browser=None
ctypes.windll.user32.SetProcessDPIAware()
user=ctypes.windll.user32;user.GetWindowRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)];user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM];callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
process=subprocess.Popen([portable['exe'],'--data-dir',str(data),'--port','0'],env=env,cwd=Path(portable['exe']).parent,creationflags=subprocess.CREATE_NO_WINDOW)
def check(name,ok,detail=None):checks.append({'name':name,'status':'PASS' if ok else 'FAIL','detail':detail});(OUT/'results.json').write_text(json.dumps({'checks':checks},indent=2));assert ok,name
def window_list():
    result=[]
    def call(hwnd,lparam):
        pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value==process.pid and user.IsWindowVisible(hwnd):result.append(hwnd)
        return True
    user.EnumWindows(callback(call),0);return result
def controls(hwnd):
    result=[]
    def call(child,lparam):
        r=wintypes.RECT();user.GetWindowRect(child,ctypes.byref(r));result.append((child,[r.left,r.top,r.right,r.bottom]));return True
    user.EnumChildWindows(hwnd,callback(call),0)
    user.GetParent.argtypes=[wintypes.HWND];user.GetParent.restype=wintypes.HWND
    groups={}
    for x in result:
        if 250<x[1][2]-x[1][0]<400 and 25<x[1][3]-x[1][1]<40:groups.setdefault(user.GetParent(x[0]),[]).append(x)
    return sorted(max(groups.values(),key=len),key=lambda x:(x[1][1],x[1][0])) if groups else []
def click(hwnd):
    if os.environ.get('DH_NATIVE_TEST_MODE')=='control-messages':
        # Target only this process-owned native widget. This is message automation,
        # not a physical-pointer test; backend effects are still independently checked.
        r=wintypes.RECT();user.GetClientRect(hwnd,ctypes.byref(r));x,y=r.right//2,r.bottom//2;point=(y<<16)|x
        user.PostMessageW(hwnd,0x200,0,point);user.PostMessageW(hwnd,0x201,1,point);user.PostMessageW(hwnd,0x202,0,point)
        with (OUT/'native-control-events.jsonl').open('a') as f:f.write(json.dumps({'hwnd':hwnd,'method':'Windows native widget messages; no physical pointer claim'})+'\n')
        return
    user.GetAncestor.argtypes=[wintypes.HWND,wintypes.UINT];user.GetAncestor.restype=wintypes.HWND;user.GetForegroundWindow.restype=wintypes.HWND;user.SetForegroundWindow.argtypes=[wintypes.HWND]
    top=user.GetAncestor(hwnd,2);user.ShowWindow(top,9)
    user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
    user.SetWindowPos(top,-1,0,0,0,0,3)
    # A normal Alt key release gives this authorized operator a foreground opportunity.
    user.keybd_event(0x12,0,0,0);user.keybd_event(0x12,0,2,0);user.SetForegroundWindow(top);time.sleep(.4)
    r=wintypes.RECT();user.GetWindowRect(hwnd,ctypes.byref(r));foreground=user.GetForegroundWindow()==top
    if not foreground:
        current=ctypes.windll.kernel32.GetCurrentThreadId();fg=user.GetForegroundWindow();thread=user.GetWindowThreadProcessId(fg,None);attached=user.AttachThreadInput(current,thread,True) if thread else False
        try:user.BringWindowToTop(top);user.SetForegroundWindow(top)
        finally:
            if attached:user.AttachThreadInput(current,thread,False)
        time.sleep(.4);foreground=user.GetForegroundWindow()==top
    if not foreground:
        # Bring only this owned test window above the terminal; the real pointer activates it.
        user.SetWindowPos.argtypes=[wintypes.HWND,wintypes.HWND,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,wintypes.UINT]
        user.SetWindowPos(top,-1,0,0,0,0,3);time.sleep(.3)
    user.WindowFromPoint.argtypes=[wintypes.POINT];user.WindowFromPoint.restype=wintypes.HWND
    x,y=(r.left+r.right)//2,(r.top+r.bottom)//2;point=wintypes.POINT();user.GetCursorPos(ctypes.byref(point));hit=user.WindowFromPoint(wintypes.POINT(x,y))
    detail={'requested_control':hwnd,'foreground':foreground,'requested_point':[x,y],'actual_point':[point.x,point.y],'hit_control':hit,'hit_root':user.GetAncestor(hit,2),'expected_root':top}
    with (OUT/'pointer-events.jsonl').open('a') as f:f.write(json.dumps(detail)+'\n')
    if hit!=hwnd:raise RuntimeError('Pointer hit test did not reach the requested native control; see pointer-events.jsonl')
    class Mouse(ctypes.Structure):_fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),('data',wintypes.DWORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
    class Union(ctypes.Union):_fields_=[('mouse',Mouse)]
    class Input(ctypes.Structure):_anonymous_=('u',);_fields_=[('type',wintypes.DWORD),('u',Union)]
    def send_pointer(px,py):
        events=(Input*3)();left,top_screen,width,height=[user.GetSystemMetrics(i) for i in (76,77,78,79)]
        events[0].mouse.dx=round((px-left)*65535/(width-1));events[0].mouse.dy=round((py-top_screen)*65535/(height-1));events[0].mouse.flags=0xC001
        events[1].mouse.flags=2;events[2].mouse.flags=4
        if user.SendInput(3,events,ctypes.sizeof(Input))!=3:raise RuntimeError('Windows did not accept the atomic move/down/up input batch')
    if user.GetForegroundWindow()!=top:
        # An inactive Tk window may consume the first click for activation. Activate
        # its owned title bar first, then verify foreground before clicking an action.
        outer=wintypes.RECT();user.GetWindowRect(top,ctypes.byref(outer));ax,ay=outer.left+60,outer.top+12
        assert user.GetAncestor(user.WindowFromPoint(wintypes.POINT(ax,ay)),2)==top
        send_pointer(ax,ay);time.sleep(.5)
        with (OUT/'pointer-events.jsonl').open('a') as f:f.write(json.dumps({'action':'owned title bar activation','foreground_verified':user.GetForegroundWindow()==top})+'\n')
        if user.GetForegroundWindow()!=top:raise RuntimeError('Interactive desktop did not activate the owned test window; pointer acceptance is blocked')
    send_pointer(x,y)
    time.sleep(.15);actual=wintypes.POINT();user.GetCursorPos(ctypes.byref(actual))
    with (OUT/'pointer-events.jsonl').open('a') as f:f.write(json.dumps({'action':'control input delivered','requested':[x,y],'actual':[actual.x,actual.y],'foreground_verified':user.GetForegroundWindow()==top})+'\n')
    time.sleep(.4);user.SetWindowPos(top,-2,0,0,0,0,3)

try:
    deadline=time.monotonic()+20
    while not window_list() and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
    windows=window_list();check('Packaged native launcher creates an ordinary Windows window',bool(windows));hwnd=windows[0];buttons=controls(hwnd);deadline=time.monotonic()+10
    title=ctypes.create_unicode_buffer(256);user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int];user.GetWindowTextW(hwnd,title,256)
    check('Native title matches the packaged version',json.loads((ROOT/'evidence/mission-006/latest-build.json').read_text())['version'] in title.value,title.value)
    while len(buttons)!=10 and time.monotonic()<deadline:time.sleep(.1);buttons=controls(hwnd)
    check('Ten functional native action controls present',len(buttons)==10,buttons)
    browser=Browser(OUT/'edge');click(buttons[0][0]);deadline=time.monotonic()+35
    while (not running(data) or not handoff.exists()) and time.monotonic()<deadline:time.sleep(.1)
    check('Native Start button starts the selected dataset and emits browser handoff',bool(running(data)) and handoff.exists());pid=running(data)['pid'];url=json.loads(handoff.read_text());browser.goto(url);browser.wait("document.querySelector('#state')?.textContent.includes('Ready')");handoff.write_text(json.dumps({'consumed':True,'ticket_redacted':True}));check('Native browser handoff authenticates successfully',browser.js("document.querySelector('#state').textContent.includes('Ready')&&location.hash===''") and running(data)['mode']=='offline')
    # Click Start a second time, then navigate the same tab with the new one-use ticket.
    click(buttons[0][0]);deadline=time.monotonic()+15
    while not isinstance(json.loads(handoff.read_text()),str) and time.monotonic()<deadline:time.sleep(.1)
    url=json.loads(handoff.read_text());assert isinstance(url,str);browser.goto(url);browser.wait("document.querySelector('#state').textContent.includes('Ready')&&location.hash===''");handoff.write_text(json.dumps({'consumed':True,'ticket_redacted':True}));check('Native reopen reuses correct service and authenticates existing tab',running(data)['pid']==pid)
    click(buttons[2][0]);deadline=time.monotonic()+15
    while not isinstance(json.loads(handoff.read_text()),str) and time.monotonic()<deadline:time.sleep(.1)
    url=json.loads(handoff.read_text());browser.goto(url);browser.wait("document.querySelector('#title').textContent==='Data sources'");handoff.write_text(json.dumps({'consumed':True,'ticket_redacted':True}));check('Native Data sources opens the real import workflow',browser.js("document.querySelector('#csv-preview')!==null"));browser.screenshot('native-opened-import.png')
    click(buttons[9][0]);deadline=time.monotonic()+30
    while running(data) and time.monotonic()<deadline:time.sleep(.1)
    check('Native Stop gracefully closes its own service',running(data) is None);user.PostMessageW(hwnd,0x10,0,0);process.wait(15);check('Native launcher closes cleanly',process.returncode==0)
    (OUT/'results.json').write_text(json.dumps({'status':'PASS','checks':checks,'physical_pointer_test':'NOT_RUN_CONTROL_MESSAGES' if os.environ.get('DH_NATIVE_TEST_MODE')=='control-messages' else 'PASS','method':('Targeted Windows native control messages with independently verified application effects. Not a physical pointer test.' if os.environ.get('DH_NATIVE_TEST_MODE')=='control-messages' else 'Real Windows pointer input with exact control hit-testing; the owned window alone is temporarily raised when Windows refuses foreground activation. OS browser handoff routed to isolated Edge through the standard BROWSER override.'),'candidate':portable['exe']},indent=2));print(json.dumps({'status':'PASS','checks':len(checks),'output':str(OUT)}))
except BaseException:
    # Do not capture screen regions if another owner window overlaps the test window.
    raise
finally:
    if browser:browser.close()
    if running(data):stop(data)
    if process.poll() is None:
        for w in window_list():user.PostMessageW(w,0x10,0,0)
        try:process.wait(15)
        except subprocess.TimeoutExpired:process.terminate();process.wait(10)
