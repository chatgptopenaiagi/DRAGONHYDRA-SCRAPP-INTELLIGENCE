"""DH-CORE: small explicit contracts shared by independent modules."""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MODULES = {
 'DH-CORE': [], 'DH-NORMALIZATION': [], 'DH-STORAGE': ['DH-NORMALIZATION'],
 'DH-ACQUISITION': ['DH-STORAGE','DH-NORMALIZATION'], 'DH-ANALYTICS': ['DH-STORAGE'],
 'DH-SPORTS': ['DH-ANALYTICS'], 'DH-SENTIMENT': ['DH-ANALYTICS'],
 'DH-WEATHER': ['DH-NORMALIZATION'], 'DH-DIAGNOSTICS': ['DH-CORE','DH-STORAGE'],
 'DH-CONNECTORS': ['DH-ACQUISITION'], 'DH-UI': ['DH-CORE'],
}
def now(): return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
def encode(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False,separators=(',',':'))
def fingerprint(value): return hashlib.sha256(encode(value).encode()).hexdigest()
def file_hash(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def atomic_json(path,value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            stream.write(encode(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(name,path)
    except BaseException:
        # Keep interrupted checkpoint bytes as recovery evidence.
        raise
class Blocked(RuntimeError): pass
class Cancelled(RuntimeError): pass
