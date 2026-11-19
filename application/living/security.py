"""DH session boundary: local launcher credential, one-use tickets, revocable cookies."""
import csv,hmac,io,os,secrets,subprocess,threading,time
from pathlib import Path

def local_secret(data,filename='launcher.key'):
    if filename not in ('launcher.key','bridge.key','mcp.key'):raise ValueError('Unknown credential purpose')
    folder=Path(data)/'private';folder.mkdir(exist_ok=True)
    if os.name=='nt':
        sid=list(csv.reader(io.StringIO(subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True,creationflags=subprocess.CREATE_NO_WINDOW))))[0][1]
        if not sid.startswith('S-1-'):raise RuntimeError('Cannot establish secret owner')
        subprocess.run(['icacls',str(folder),'/inheritance:r','/grant:r','*S-1-5-18:(OI)(CI)F','*'+sid+':(OI)(CI)F'],check=True,capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    path=folder/filename
    if not path.exists():
        with path.open('x',encoding='ascii') as f:f.write(secrets.token_urlsafe(48))
    secret=path.read_text().strip()
    if len(secret)<60:raise ValueError('Invalid launcher credential')
    return secret
class Sessions:
    def __init__(self,secret,clock=time.monotonic,ttl=3600,idle=900):
        self.secret=secret;self.clock=clock;self.ttl=ttl;self.idle=idle;self.tickets={};self.sessions={};self.lock=threading.RLock()
    def admin(self,value):return bool(value) and hmac.compare_digest(value,self.secret)
    def ticket(self):
        with self.lock:
            self.tickets={k:v for k,v in self.tickets.items() if v>self.clock()}
            if len(self.tickets)>=128:raise ValueError('Too many pending browser launches')
            code=secrets.token_urlsafe(32);self.tickets[code]=self.clock()+45;return code
    def exchange(self,code):
        with self.lock:
            expiry=self.tickets.pop(code,0)
            if expiry<=self.clock():raise PermissionError('Browser launch expired or already used. Reopen from the launcher.')
            self.sessions={k:v for k,v in self.sessions.items() if v['expires']>self.clock() and v['last']+self.idle>self.clock()}
            if len(self.sessions)>=128:raise PermissionError('Session limit reached; revoke sessions from launcher')
            token=secrets.token_urlsafe(32);csrf=secrets.token_urlsafe(32)
            self.sessions[token]={'expires':self.clock()+self.ttl,'last':self.clock(),'csrf':csrf};return token,csrf
    def get(self,token):
        with self.lock:
            session=self.sessions.get(token)
            if not session or session['expires']<=self.clock() or session['last']+self.idle<=self.clock():self.sessions.pop(token,None);return None
            session['last']=self.clock();return session.copy()
    def revoke(self,token):
        with self.lock:self.sessions.pop(token,None)
    def revoke_all(self):
        with self.lock:self.sessions.clear();self.tickets.clear()
