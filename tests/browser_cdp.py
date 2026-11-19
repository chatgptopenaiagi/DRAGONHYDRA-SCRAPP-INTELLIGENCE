"""Small Edge DevTools harness using the already installed websocket-client."""
import base64,json,subprocess,time,urllib.request
from pathlib import Path
import websocket

class Browser:
    def __init__(self,folder):
        self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=False)
        self.log=(self.folder/'edge.log').open('w')
        self.process=subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe','--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--remote-debugging-port=0','--remote-allow-origins=http://127.0.0.1','--user-data-dir='+str(self.folder/'profile'),'about:blank'],stdout=self.log,stderr=self.log,creationflags=subprocess.CREATE_NO_WINDOW)
        active=self.folder/'profile/DevToolsActivePort';deadline=time.monotonic()+25
        port=None
        while self.process.poll() is None and time.monotonic()<deadline:
            try:port=int(active.read_text().splitlines()[0]);break
            except (OSError,ValueError,IndexError):time.sleep(.1)
        if port is None:raise RuntimeError('Edge did not expose its isolated DevTools endpoint')
        self.port=port;self.serial=0;self.errors=[];self.interactions=[]
        pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{self.port}/json/list'))
        self.ws=websocket.create_connection(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'),origin='http://127.0.0.1',timeout=30)
        self.call('Page.enable');self.call('Runtime.enable');self.call('Emulation.setDeviceMetricsOverride',width=1440,height=1000,deviceScaleFactor=1,mobile=False)
    def call(self,method,**params):
        self.serial+=1;self.ws.send(json.dumps({'id':self.serial,'method':method,'params':params}))
        while True:
            r=json.loads(self.ws.recv())
            if r.get('method')=='Runtime.exceptionThrown':self.errors.append(r['params']['exceptionDetails'].get('text','JavaScript exception'))
            if r.get('id')==self.serial:
                if 'error' in r:raise RuntimeError(r['error'])
                return r.get('result',{})
    def js(self,expression):
        r=self.call('Runtime.evaluate',expression=expression,returnByValue=True,awaitPromise=True)
        if 'exceptionDetails' in r:raise RuntimeError(r['exceptionDetails'])
        return r.get('result',{}).get('value')
    def wait(self,expression,seconds=20):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if self.js(expression):return
            time.sleep(.15)
        raise AssertionError('Browser condition timed out: '+expression)
    def goto(self,url):self.call('Page.navigate',url=url)
    def click(self,selector):self.interactions.append({'selector':selector,'method':'DOM click'});self.js('document.querySelector('+json.dumps(selector)+').click()')
    def fill(self,selector,value):self.interactions.append({'selector':selector,'method':'input/change event; value deliberately omitted'});self.js('(()=>{let e=document.querySelector('+json.dumps(selector)+');e.value='+json.dumps(value)+';e.dispatchEvent(new Event("input",{bubbles:true}));e.dispatchEvent(new Event("change",{bubbles:true}))})()')
    def upload(self,selector,file):
        root=self.call('DOM.getDocument')['root']['nodeId'];node=self.call('DOM.querySelector',nodeId=root,selector=selector)['nodeId'];self.call('DOM.setFileInputFiles',nodeId=node,files=[str(Path(file).resolve())])
    def screenshot(self,name):
        (self.folder/name).write_bytes(base64.b64decode(self.call('Page.captureScreenshot',format='png',captureBeyondViewport=True)['data']))
    def close(self):
        try:self.call('Browser.close')
        except Exception:pass
        self.ws.close()
        try:self.process.wait(15)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(10)
        self.log.close()
