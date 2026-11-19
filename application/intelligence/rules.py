import json,os
from pathlib import Path
from datetime import datetime,timezone
from .acquisition import validate_rule_candidate
from dragonhydra.domain import identity

class RuleHistory:
    def __init__(self,folder):self.folder=Path(folder);self.folder.mkdir(parents=True,exist_ok=True)
    def activate(self,source,candidate,examples):
        result=validate_rule_candidate(candidate,examples)
        identifier=identity('rule-source',source);active=self.folder/(identifier+'.json')
        previous=json.loads(active.read_text()) if active.exists() else None
        record={'source':source,'rule':candidate,'validated_examples':len(examples),'previous':previous,'recorded_at':datetime.now(timezone.utc).isoformat()}
        encoded=json.dumps(record,ensure_ascii=False,sort_keys=True);version=identity('rule-version',encoded)
        audit=self.folder/(version+'.history.json')
        with audit.open('x',encoding='utf-8') as f:f.write(encoded)
        temp=self.folder/(identifier+'.tmp');temp.write_text(encoded,encoding='utf-8');os.replace(temp,active)
        return {'version':version,**result,'activation':'recorded_and_active'}
    def rollback(self,source):
        active=self.folder/(identity('rule-source',source)+'.json');record=json.loads(active.read_text())
        if not record['previous']:raise ValueError('No prior rule')
        previous=record['previous'];record['rolled_back_at']=datetime.now(timezone.utc).isoformat()
        audit=self.folder/(identity('rollback',json.dumps(record,sort_keys=True))+'.history.json')
        audit.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8')
        temp=active.with_suffix('.tmp');temp.write_text(json.dumps(previous,ensure_ascii=False),encoding='utf-8');os.replace(temp,active)
        return previous
