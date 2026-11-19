from ..football_contracts import entity
class ProviderError(ValueError):
    def __init__(self,message,state='UNAVAILABLE',status=None,retry_after=None):super().__init__(message);self.state=state;self.status=status;self.retry_after=retry_after
def array(data,key=None):
    value=data.get(key) if key and isinstance(data,dict) else data if key is None else None
    if value is None and isinstance(data,dict) and key in data:return []
    if not isinstance(value,list) or not all(isinstance(x,dict) for x in value):raise ProviderError('Provider JSON does not match the documented response schema')
    return value
def required(config,key):
    value=config.get(key)
    if not value:raise ProviderError('Choose '+key.replace('_',' ')+' before collection','CONFIGURED')
    return str(value)
def competition(id,name,raw,seasons=(),**meta):
    result=entity('competition',id,name,raw,competition=str(id),seasons=[str(x) for x in seasons],**meta)
    result['metadata']['name']=str(name);return result
class Adapter:
    auth='none';key_name=None;categories=('competitions','fixtures','results');daily_cap=100;window_limit=60;window_seconds=60;minimum_interval=900
    def request(self,c,operation,page=1):raise NotImplementedError
    def parse(self,data,category,c):raise NotImplementedError
    def next_page(self,data,page):return None
    def metadata(self):return {k:getattr(self,k) for k in ('name','website','docs','base','auth','key_name','categories','daily_cap','window_limit','window_seconds','minimum_interval','limitations')}
