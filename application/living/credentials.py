"""Windows user-scoped DPAPI. No API exists to return a saved credential to a browser."""
import ctypes,json,os,threading,uuid
from ctypes import wintypes
from pathlib import Path
from .contracts import fingerprint
from .security import local_secret

class Blob(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]

def protect(raw,entropy,decrypt=False):
    if os.name!='nt':raise ValueError('Protected provider credentials require Windows DPAPI')
    crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)];fn.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    buf=ctypes.create_string_buffer(raw);ebuf=ctypes.create_string_buffer(entropy)
    src=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));ent=Blob(len(entropy),ctypes.cast(ebuf,ctypes.POINTER(ctypes.c_ubyte)));out=Blob()
    if not fn(ctypes.byref(src),None,ctypes.byref(ent),None,None,1,ctypes.byref(out)):raise ValueError('Credential protection is unavailable for this Windows user or dataset. Save the credential again.')
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:
        if out.pbData:ctypes.memset(out.pbData,0,out.cbData);kernel.LocalFree(out.pbData)
        ctypes.memset(buf,0,len(raw));ctypes.memset(ebuf,0,len(entropy))

class Vault:
    def __init__(self,data,namespace='providers'):
        if namespace not in ('providers','cloud'):raise ValueError('Unknown credential namespace')
        self.namespace=namespace;self.data=Path(data).resolve();local_secret(self.data);self.folder=self.data/'private'/namespace;self.folder.mkdir(exist_ok=True);self.lock=threading.RLock()
    def path(self,slot):
        allowed=('1','2','3','4','5','6') if self.namespace=='providers' else ('openai','anthropic','xai','foundry','azure-openai','copilot-studio','manus','local')
        if str(slot) not in allowed:raise ValueError('Unknown provider slot')
        return self.folder/(str(slot)+'.dpapi')
    def entropy(self,slot,binding):
        values=['dh.credentials/1',str(self.data),str(slot),binding] if self.namespace=='providers' else ['dh.credentials/2',str(self.data),self.namespace,str(slot),binding]
        return fingerprint(values).encode()
    def save(self,slot,binding,value):
        if not isinstance(value,str) or not 8<=len(value)<=4096 or any(ord(c)<33 or ord(c)>126 for c in value):raise ValueError('API key must contain 8–4096 printable non-space ASCII characters')
        with self.lock:
            path=self.path(slot);raw=json.dumps({'credential':value,'binding':binding},separators=(',',':')).encode();encrypted=protect(raw,self.entropy(slot,binding));stage=self.folder/(uuid.uuid4().hex+'.partial')
            with stage.open('xb') as f:f.write(encrypted);f.flush();os.fsync(f.fileno())
            os.replace(stage,path)
        return {'credential_status':'SAVED','protection':'Windows user-scoped DPAPI'}
    def get(self,slot,binding):
        with self.lock:
            path=self.path(slot)
            if not path.exists():raise ValueError('Enter an API key for this provider before testing the connection')
            data=json.loads(protect(path.read_bytes(),self.entropy(slot,binding),True))
            if data.get('binding')!=binding:raise ValueError('Credentials belong to a different provider configuration')
            return data['credential']
    def status(self,slot,binding):
        if not self.path(slot).exists():return 'MISSING'
        try:self.get(slot,binding);return 'SAVED'
        except (ValueError,OSError):return 'REENTRY_REQUIRED'
    def remove(self,slot):
        with self.lock:self.path(slot).unlink(missing_ok=True)
        return {'credential_status':'REMOVED','note':'Removed from this application. Revoke at the provider website if required.'}
