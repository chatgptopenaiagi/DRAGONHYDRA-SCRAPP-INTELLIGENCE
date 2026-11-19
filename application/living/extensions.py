"""Local stateless MCP over the existing authenticated loopback HTTP server."""
import hmac
from .security import local_secret
from .contracts import atomic_json,Blocked
class Extensions:
    def __init__(self,rt):self.rt=rt;self.secret=local_secret(rt.data,'mcp.key')
    def status(self):
        return {'local_mcp':{'enabled':bool(self.rt.store.state('extensions','mcp-enabled')),'transport':'Streamable HTTP, JSON responses, stateless; GET/SSE not supported','protocol':'2025-06-18','path':'/api/mcp','permission':'Enabled read-only tools only; imports, SQL writes and Codex steering are excluded','credential':'Separate current-user ACL-protected local client credential; never returned to JavaScript'},'openai_function_calling':'SUPPORTED','anthropic_tool_use':'SUPPORTED','xai_function_calling':'SUPPORTED','microsoft_chat_tools':'SUPPORTED_WHEN_DEPLOYMENT_SUPPORTS_TOOLS','manus_local_function_calls':'NOT_SUPPORTED_BY_VERIFIED_TASK_PROTOCOL','chatgpt_plugins':{'status':'INCOMPATIBLE_WITH_DIRECT_IMPORT','reason':'Host account plugins are not standalone application credentials or runtimes. Use the provider API or an explicitly configured external MCP client.'},'remote_mcp':{'status':'NOT_CONFIGURED','note':'No remote servers are called automatically. Compatible clients can connect to this local MCP endpoint. Remote MCP server execution is not implemented in this beta.'}}
    def configure(self,enabled,origin):
        if type(enabled) is not bool:raise ValueError('Invalid MCP switch')
        self.rt.store.state('extensions','mcp-enabled',enabled)
        config=self.rt.data/'private/mcp-client.json'
        atomic_json(config,{'mcpServers':{'dragonhydra':{'url':origin+'/api/mcp','headers':{'X-DH-MCP':self.secret}}}})
        return {'enabled':enabled,'private_client_configuration':str(config),'note':'Configure a compatible authorized local MCP client using this private file. Do not publish it.'}
    def authorized(self,value):return bool(self.rt.store.state('extensions','mcp-enabled')) and bool(value) and hmac.compare_digest(value,self.secret)
    def call(self,b):
        id=b.get('id')
        def error(code,message):return {'jsonrpc':'2.0','id':id,'error':{'code':code,'message':message}}
        if b.get('jsonrpc')!='2.0' or not isinstance(b.get('method'),str):return error(-32600,'Invalid JSON-RPC request')
        method=b['method'];p=b.get('params',{})
        if not isinstance(p,dict):return error(-32602,'Object parameters required')
        if method=='notifications/initialized' and id is None:return None
        if method=='initialize':result={'protocolVersion':'2025-06-18','capabilities':{'tools':{'listChanged':False}},'serverInfo':{'name':'dragonhydra-local','version':'0.2.0-beta.3'}}
        elif method=='ping':result={}
        elif method=='tools/list':result={'tools':[{'name':t['name'],'description':t['description'],'inputSchema':t['input_schema'],'annotations':{'readOnlyHint':True,'destructiveHint':False}} for t in self.rt.registry.contracts() if t['enabled'] and t['permission']=='BOUNDED_READ']}
        elif method=='tools/call':
            name=p.get('name')
            if not isinstance(name,str) or name.startswith('request_'):return error(-32602,'MCP permits only enabled bounded read tools')
            r=self.rt.registry.run(name,p.get('arguments',{}),'mcp');import json
            result={'content':[{'type':'text','text':json.dumps(r,ensure_ascii=False)}],'isError':r['state']!='PASS'}
        else:return error(-32601,'Method not supported')
        return {'jsonrpc':'2.0','id':id,'result':result}
