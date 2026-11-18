"""DH-CORE/DIAGNOSTICS: sole composition root, durable operations, explicit mode."""
import json,os,shutil,threading,time
from pathlib import Path
from . import VERSION
from .contracts import MODULES,now,atomic_json,fingerprint
from .storage import Store
from .acquisition import Acquisition,validate_source
from .connectors import sql_status

class Runtime:
    def __init__(self,data,mode='offline',guard=None):
        if mode not in ('offline','connected'):raise ValueError('Mode must be offline or connected')
        self.data=Path(data).resolve();self.data.mkdir(parents=True,exist_ok=True)
        if (self.data/'offline-demo.sqlite3').exists():raise ValueError('Select a new candidate data directory; legacy data is read-only')
        self.mode=mode;self.guard=guard;self.started=time.monotonic();self.closed=False
        self.store=Store(self.data/'intelligence.sqlite3');self.acquisition=Acquisition(self.store,self.data,mode)
        self.config_path=self.data/'settings.json';self.config=json.loads(self.config_path.read_text()) if self.config_path.exists() else {'ai':{'enabled':False}}
        self.acquisition.start()
    def status(self):
        disk=shutil.disk_usage(self.data);tasks=self.store.tasks();summary=self.store.summary()
        return dict(product='DRAGONHYDRA SCRAPP INTELLIGENCE',version=VERSION,mode=self.mode,storage='READY',database=str(self.store.path),data_id=fingerprint(str(self.data)),uptime_seconds=round(time.monotonic()-self.started,2),pid=os.getpid(),disk_free=disk.free,database_bytes=self.store.path.stat().st_size,summary=summary,sources=self.store.sources(),tasks=tasks,modules=[{'id':k,'dependencies':v,'state':'READY','contract':'dh.module/1'} for k,v in MODULES.items()],sql=sql_status(self.guard),integrations={'football':'Configured read-only adapter; historical data only','joomla':'BLOCKED until explicitly installed and actual site communication verified','ARX':'UNCONFIGURED','local_ai':'DISABLED' if not self.config.get('ai',{}).get('enabled') else 'CONFIGURED_NOT_VERIFIED','cloud_ai':'DISABLED'},recovery={'interrupted':sum(t['state']=='INTERRUPTED' for t in tasks),'failed':sum(t['state']=='FAILED' for t in tasks),'integrity':self.store.integrity},ai_config=self.config.get('ai',{}))
    def configure_source(self,source):
        source=validate_source(source);self.store.source(source);self.store.event('INFO','SOURCE_CONFIGURED',source['id']);return source
    def backup(self):
        return self.store.backup(self.data/'backups'/('intelligence-'+str(time.time_ns())+'.sqlite3'))
    def close(self):
        if self.closed:return
        self.acquisition.close();self.store.event('INFO','CLEAN_SHUTDOWN','All owned worker operations stopped');self.store.close();self.closed=True
