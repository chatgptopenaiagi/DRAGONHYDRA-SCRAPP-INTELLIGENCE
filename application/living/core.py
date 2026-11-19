"""DH-CORE/DIAGNOSTICS: sole composition root, durable operations, explicit mode."""
import json,os,shutil,threading,time
from pathlib import Path
from . import VERSION
from .contracts import MODULES,now,atomic_json,fingerprint
from .storage import Store
from .acquisition import Acquisition,validate_source
from .connectors import sql_status

class Runtime:
    def __init__(self,data,mode='offline',guard=None,mock_origins=()):
        if mode not in ('offline','connected'):raise ValueError('Mode must be offline or connected')
        self.data=Path(data).resolve();self.data.mkdir(parents=True,exist_ok=True)
        if (self.data/'offline-demo.sqlite3').exists():raise ValueError('Select a new candidate data directory; legacy data is read-only')
        self.mode=mode;self.guard=guard;self.started=time.monotonic();self.closed=False
        self.store=Store(self.data/'intelligence.sqlite3');self.acquisition=Acquisition(self.store,self.data,mode)
        from .provider_manager import ProviderManager
        self.providers=ProviderManager(self.store,self.data,self.acquisition,mock_origins);self.acquisition.providers=self.providers
        from .sql_control import SqlControl
        from .knowledge import Knowledge
        from .evidence_tools import EvidenceTools
        from .cloud_manager import Cloud,scrub
        self.sql=SqlControl(self.store,self.data,guard);self.knowledge=Knowledge(self.store,lambda:self.mode,mock_origins);self.evidence_tools=EvidenceTools(self.store,self.sql)
        self.cloud=Cloud(self.store,self.data,lambda:self.mode,self.knowledge,self.evidence_tools,mock_origins);self.acquisition.knowledge=self.knowledge
        self.config_path=self.data/'settings.json';self.config=json.loads(self.config_path.read_text()) if self.config_path.exists() else {'ai':{'enabled':False}}
        from .hardware import Hardware
        from .codex_bridge import Engineering
        from .tool_registry import Registry
        from .conversations import Conversations
        from .extensions import Extensions
        self.hardware=Hardware(self.data);self.engineering=Engineering(self.store,lambda value:scrub(value,self.cloud.secrets()));self.registry=Registry(self);self.conversations=Conversations(self);self.extensions=Extensions(self)
        self.acquisition.start()
    def status(self):
        disk=shutil.disk_usage(self.data);tasks=self.store.tasks();summary=self.store.summary()
        return dict(product='DRAGONHYDRA SCRAPP INTELLIGENCE',version=VERSION,mode=self.mode,storage='READY',database=str(self.store.path),data_id=fingerprint(str(self.data)),uptime_seconds=round(time.monotonic()-self.started,2),pid=os.getpid(),disk_free=disk.free,database_bytes=self.store.path.stat().st_size,summary=summary,sources=self.store.sources(),tasks=tasks,modules=[{'id':k,'dependencies':v,'state':'READY','contract':'dh.module/1'} for k,v in MODULES.items()],sql=self.sql.status(),integrations={'football':'Configured read-only adapter; historical data only','joomla':'BLOCKED until explicitly installed and actual site communication verified','ARX':'UNCONFIGURED','local_ai':'DISABLED' if not self.config.get('ai',{}).get('enabled') else 'CONFIGURED_NOT_VERIFIED','cloud_ai':'EXPLICIT_PER_REQUEST_APPROVAL'},recovery={'interrupted':sum(t['state']=='INTERRUPTED' for t in tasks),'failed':sum(t['state']=='FAILED' for t in tasks),'integrity':self.store.integrity},ai_config=self.config.get('ai',{}))
    def configure_source(self,source):
        if str(source.get('id','')).startswith('football-api-'):raise ValueError('Use Football API Control Center to configure provider sources')
        source=validate_source(source);self.store.source(source);self.store.event('INFO','SOURCE_CONFIGURED',source['id']);return source
    def set_mode(self,mode):
        if mode not in ('offline','connected'):raise ValueError('Choose Offline or Configured connections')
        self.mode=mode;self.acquisition.mode=mode
        if mode=='offline':
            for slot in range(1,7):self.providers.cancel_slot(str(slot))
        self.store.event('INFO','MODE_CHANGED',mode);return {'mode':mode,'pid':os.getpid()}
    def backup(self):
        return self.store.backup(self.data/'backups'/('intelligence-'+str(time.time_ns())+'.sqlite3'))
    def close(self):
        if self.closed:return
        self.conversations.close();self.acquisition.close();self.store.event('INFO','CLEAN_SHUTDOWN','All owned worker operations stopped');self.store.close();self.closed=True
