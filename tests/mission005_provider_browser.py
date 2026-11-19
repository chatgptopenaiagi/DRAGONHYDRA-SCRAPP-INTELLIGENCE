"""Actual Edge provider operations; controlled mocks or explicitly public free endpoints."""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.launcher import request,running,stop
from browser_cdp import Browser
from football_mock import Mock
p=argparse.ArgumentParser();p.add_argument('--exe');p.add_argument('--live',action='store_true');args=p.parse_args();mode='live' if args.live else 'mock'
out=ROOT/'evidence/mission-005'/('providers-browser-'+mode+'-'+('packaged-' if args.exe else 'source-')+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));out.mkdir();data=out/'data';checks=[];mocks=[];browser=None;process=None
def record(name,ok,detail=None,status=None):
    checks.append({'name':name,'status':(status or ('LIVE_PASS' if args.live else 'MOCK_PASS')) if ok else 'FAIL','detail':detail});(out/'results.json').write_text(json.dumps({'checks':checks},indent=2));assert ok,name
def launch():
    global process
    command=[args.exe] if args.exe else [sys.executable,'-B',str(ROOT/'application/living_launch.py')];command+=['--serve','--data-dir',str(data),'--port','0','--mode','connected']
    for m in mocks:command+=['--mock-provider-origin',m.origin]
    log=(out/('server-'+str(time.time_ns())+'.log')).open('w');process=subprocess.Popen(command,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();deadline=time.monotonic()+30
    while not running(data) and process.poll() is None and time.monotonic()<deadline:time.sleep(.1)
    assert running(data);return 'http://127.0.0.1:'+str(json.loads((data/'ready.json').read_text())['port'])+'/'
def auth(url):
    ticket=request(data,'/api/session-ticket',{})['ticket'];browser.goto(url+'#ticket='+ticket+'&view=football');browser.wait("document.querySelectorAll('.provider-card').length===6")
def jscheck(selector,on=True):browser.js('document.querySelector('+json.dumps(selector)+').checked='+str(on).lower())
def waitslot(slot,state,seconds=45):browser.wait(f"document.querySelector('#p{slot}-status').textContent.startsWith('{state}')",seconds)
def operation(slot,button,state='CONNECTED',seconds=45):
    previous={t['id'] for t in request(data,'/api/tasks')};browser.click(f'#p{slot}-{button}');deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        tasks=[t for t in request(data,'/api/tasks') if t['id'] not in previous]
        if tasks and tasks[0]['state'] not in ('QUEUED','RUNNING'):
            browser.click('#refresh');waitslot(slot,state,10);return tasks[0]
        time.sleep(.15)
    raise AssertionError(f'Provider {slot} {button} did not finish')
try:
    if not args.live:mocks=[Mock(i) for i in range(1,7)]
    url=launch()
    if mocks:
        for i,m in enumerate(mocks,1):request(data,'/api/provider/configure',{'slot':str(i),'mock_origin':m.origin,'season':'2020','enabled':False,'approved':False,'category':'competitions'})
    browser=Browser(out/'edge');auth(url);record('Six named provider cards',browser.js("document.querySelectorAll('.provider-card').length===6"),status='PASS')
    slots=(3,6) if args.live else range(1,7)
    for slot in slots:
        jscheck(f'#p{slot}-enabled');jscheck(f'#p{slot}-approved');browser.fill(f'#p{slot}-season','2025' if args.live else '2020');browser.click(f'#p{slot}-save');waitslot(slot,'CONFIGURED')
        if not args.live and slot in (1,2,4,5):
            browser.click(f'#p{slot}-test');browser.wait("!document.querySelector('#error').hidden");record(f'Provider {slot} explains missing credentials',browser.js("document.querySelector('#error').textContent.includes('API key')"));browser.fill(f'#p{slot}-key',mocks[slot-1].key);browser.click(f'#p{slot}-show');record(f'Provider {slot} show/hide affects new entry only',browser.js(f"document.querySelector('#p{slot}-key').type==='text'"),status='PASS');browser.click(f'#p{slot}-save-key');browser.wait(f"document.querySelector('#p{slot}-key').value===''&&document.querySelector('#p{slot}-status').textContent.includes('SAVED')")
        t=operation(slot,'test');record(f'Provider {slot} genuine connection button validates response',t['state']=='COMPLETE',{'evidence_class':t.get('result',{}).get('evidence_class'),'rows_validated':t.get('result',{}).get('rows_validated')})
        if args.live and slot==3:browser.fill('#p3-category','teams');browser.fill('#p3-team','Arsenal')
        else:
            browser.fill(f'#p{slot}-category','results');browser.fill(f'#p{slot}-competition','bl1' if args.live else '1');browser.fill(f'#p{slot}-date-from','2020-01-01');browser.fill(f'#p{slot}-date-to','2020-01-01')
            if slot==6:browser.fill('#p6-matchday','1')
        browser.click(f'#p{slot}-save');waitslot(slot,'CONFIGURED');t=operation(slot,'collect');record(f'Provider {slot} collection commits actual parsed observations',t['state']=='COMPLETE' and t['result']['inserted']>0,{'inserted':t.get('result',{}).get('inserted'),'origin':t.get('result',{}).get('origin')})
        before=request(data,'/api/observations?source=football-api-'+str(slot))['total'];t=operation(slot,'collect');after=request(data,'/api/observations?source=football-api-'+str(slot))['total'];record(f'Provider {slot} identical repeat preserves identities',before==after,{'before':before,'after':after,'duplicates':t.get('result',{}).get('duplicates')});browser.click(f'#p{slot}-receipt');browser.wait("document.querySelector('#evidence').open");browser.click('#close-evidence')
    if args.live:
        teams=request(data,'/api/observations?source=football-api-3')['rows'];record('Real Arsenal identity and provider provenance',any(r['metadata']['original_provider_record'].get('strTeam')=='Arsenal' and r['origin']=='COLLECTED' for r in teams));record('Four credential-gated providers remain unconfigured',all(x['state']=='UNCONFIGURED' for x in request(data,'/api/providers') if x['slot'] in ('1','2','4','5')),status='PASS')
    else:
        browser.fill('#p1-key',mocks[1].key);browser.click('#p1-save-key');browser.wait("document.querySelector('#p1-key').value===''");t=operation(1,'test','AUTHENTICATION_FAILED');record('Provider 1 rejects provider 2 credential without disabling provider 2',t['state']=='FAILED' and next(x for x in request(data,'/api/providers') if x['slot']=='2')['state']=='CONNECTED')
        browser.fill('#p1-key',mocks[0].key);browser.click('#p1-save-key');browser.wait("document.querySelector('#p1-key').value===''")
        mocks[1].case='malformed';t=operation(2,'test','UNAVAILABLE');record('Malformed JSON displayed as unavailable',t['state']=='FAILED');mocks[1].case='ok'
        mocks[2].case='disconnect';count=len(mocks[2].calls);t=operation(3,'test','UNAVAILABLE');record('Disconnect retries are bounded at three',t['state']=='FAILED' and len(mocks[2].calls)-count==3);mocks[2].case='ok'
        mocks[3].case='timeout';count=len(mocks[3].calls);t=operation(4,'test','UNAVAILABLE',50);record('Timeout is bounded and visible',t['state']=='FAILED' and len(mocks[3].calls)-count==3);mocks[3].case='ok'
        mocks[4].case='rate';count=len(mocks[4].calls);t=operation(5,'test','RATE_LIMITED');browser.click('#p5-test');browser.wait("document.querySelector('#error').textContent.includes('retry time')");record('429 respects Retry-After without repeated requests',len(mocks[4].calls)-count==1 and t['state']=='FAILED')
        browser.click('#p1-remove-key');browser.wait("document.querySelector('#p1-status').textContent.includes('MISSING')");record('Remove credential is reflected in the UI',True,status='PASS');browser.fill('#p1-key',mocks[0].key);browser.click('#p1-save-key');browser.wait("document.querySelector('#p1-key').value===''")
        jscheck('#p6-schedule');jscheck('#p6-enabled',False);browser.click('#p6-save');waitslot(6,'DISABLED');count=len(mocks[5].calls);time.sleep(.5);record('Disabled provider does not schedule collection',len(mocks[5].calls)==count)
    browser.fill('#connection-mode','offline');browser.click('#change-mode');browser.wait("document.querySelector('#provider-mode-note').textContent.startsWith('OFFLINE')");calls=sum(len(m.calls) for m in mocks);browser.click('#p3-collect');browser.wait("document.querySelector('#error').textContent.includes('Online collection is disabled')");record('Offline collection is blocked with an explanation',sum(len(m.calls) for m in mocks)==calls,status='PASS');browser.screenshot('offline-controls.png')
    browser.click('nav [data-view="history"]');browser.fill('#source','football-api-3');browser.click('#apply');browser.wait("document.querySelector('#rows').textContent.includes('football')");record('Collected football records visible in the dashboard',True);browser.screenshot('collected-data.png')
    before=request(data,'/api/status')['summary']['observations'];stop(data);process.wait(30);url=launch();auth(url);record('Provider configuration and observations survive restart',request(data,'/api/status')['summary']['observations']==before,status='PASS')
    if mocks:record('Independent DPAPI credentials survive restart',all(x['credential_status']=='SAVED' for x in request(data,'/api/providers') if x['slot'] in ('1','2','4','5')),status='PASS')
    record('No JavaScript exceptions',not browser.errors,browser.errors,status='PASS');stop(data);process.wait(30);record('Clean shutdown',process.returncode==0,status='PASS')
    if mocks:
        for file in data.rglob('*'):
            if file.is_file() and file.suffix!='.dpapi':
                raw=file.read_bytes();assert not any(m.key.encode() in raw for m in mocks),file.name
        record('No test credentials in database, logs or response evidence',True,status='PASS')
    (out/'results.json').write_text(json.dumps({'status':'LIVE_PASS' if args.live else 'MOCK_PASS','checks':checks,'candidate':args.exe or 'source','output':str(out),'live_credentials_used':False},indent=2));print(json.dumps({'status':'LIVE_PASS' if args.live else 'MOCK_PASS','checks':len(checks),'output':str(out)}))
finally:
    if browser:browser.close()
    if process and process.poll() is None:stop(data);process.wait(30)
    for m in mocks:m.close()
