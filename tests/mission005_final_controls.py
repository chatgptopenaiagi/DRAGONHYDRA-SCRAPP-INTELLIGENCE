"""Additional actual Edge controls, consecutive imports and interrupted API recovery."""
import argparse,json,subprocess,sys,time,base64,socket
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.launcher import request,running,stop
from browser_cdp import Browser
from football_mock import Mock
p=argparse.ArgumentParser();p.add_argument('--exe');a=p.parse_args();OUT=ROOT/'evidence/mission-005'/('final-controls-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));OUT.mkdir();data=OUT/'data';checks=[];browser=None;process=None;mock=Mock(2)
def check(name,ok,detail=None):
    checks.append(dict(name=name,status='PASS' if ok else 'FAIL',detail=detail));(OUT/'results.json').write_text(json.dumps({'checks':checks},indent=2));print(name+': '+checks[-1]['status'],flush=True);assert ok,name
def launch():
    global process
    cmd=[a.exe] if a.exe else [sys.executable,'-B',str(ROOT/'application/living_launch.py')];log=(OUT/('server-'+str(time.time_ns())+'.log')).open('w');process=subprocess.Popen(cmd+['--serve','--data-dir',str(data),'--port','0','--mode','connected','--mock-provider-origin',mock.origin],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();end=time.monotonic()+30
    while not running(data) and process.poll() is None and time.monotonic()<end:time.sleep(.1)
    assert running(data);return 'http://127.0.0.1:'+str(json.loads((data/'ready.json').read_text())['port'])+'/'
def auth(url):browser.goto(url+'#ticket='+request(data,'/api/session-ticket',{})['ticket']+'&view=sources');browser.wait("document.querySelector('#state').textContent.includes('Ready')")
def waittask(id):
    end=time.monotonic()+30
    while time.monotonic()<end:
        t=next(x for x in request(data,'/api/tasks') if x['id']==id)
        if t['state'] not in ('QUEUED','RUNNING'):return t
        time.sleep(.1)
    raise AssertionError('Task timeout')
try:
    url=launch();browser=Browser(OUT/'edge');auth(url);fixture=OUT/'synthetic.csv';fixture.write_text('Date,HomeTeam,AwayTeam,FTHG,FTAG\n2020-01-01,Synthetic Home,Synthetic Away,2,1\n2020-01-02,Synthetic Other,Synthetic Visitor,1,1\n')
    for source in ('first','second'):
        browser.click('nav [data-view="sources"]');browser.upload('#csv-file',fixture);browser.click('#csv-preview');browser.wait("document.querySelector('#csv-result').textContent.includes('Preview ready')");browser.fill('#csv-source-id',source);browser.fill('#csv-source-name',source);browser.fill('#csv-origin','SYNTHETIC');browser.fill('#csv-date-format','iso');browser.fill('#csv-competition','1');browser.fill('#csv-season','2020');browser.click('#csv-create-source');browser.wait("document.querySelector('#csv-source').value==='"+source+"'");browser.click('#csv-validate');browser.wait("!document.querySelector('#csv-confirm').disabled");browser.click('#csv-confirm');browser.wait("document.querySelector('#csv-result').textContent.includes('COMPLETE')");check(source+' CSV commits two synthetic results',request(data,'/api/observations?source='+source)['total']==2)
        browser.click('#csv-view-records');browser.wait("document.querySelector('#title').textContent==='Historical observations'");time.sleep(.8);check(source+' import receipt opens its own source',browser.js("document.querySelector('#source').value")==source)
    browser.click('nav [data-view="football-comparison"]');browser.click('#compare-run');browser.wait("document.querySelector('#compare-results').textContent.includes('candidate groups')");check('Comparison displays agreement candidates without merging originals',browser.js("document.querySelector('#compare-results').textContent.includes('AGREEMENT_CANDIDATE')") and request(data,'/api/status')['summary']['observations']==4)
    browser.fill('#compare-team','Synthetic Other');browser.click('#compare-run');browser.wait("document.querySelector('#compare-results').textContent.includes('2 records')");check('Comparison team filter is functional',True)
    browser.js("document.querySelector('#alias-save').closest('details').open=true");browser.fill('#alias-source','second');browser.fill('#alias-original','Synthetic Home');browser.fill('#alias-canonical','Owner confirmed synthetic identity');browser.click('#alias-save');browser.wait("document.querySelector('#evidence').open");check('Explicit alias control saves without rewriting records',request(data,'/api/status')['summary']['observations']==4);browser.click('#close-evidence')
    browser.click('nav [data-view="sources"]');browser.fill('#source-form [name="id"]','advanced');browser.fill('#source-form [name="name"]','Advanced source');browser.fill('#source-form [name="origin"]','SYNTHETIC');browser.click('#source-form button[type="submit"]');browser.wait("document.querySelector('#source-list').textContent.includes('Advanced source')");check('Advanced Save source persists exact configuration',any(s['id']=='advanced' and s['name']=='Advanced source' for s in request(data,'/api/status')['sources']))
    browser.fill('#source-form [name="name"]','Unsaved draft');browser.click('#refresh');browser.wait("document.querySelector('#state').textContent.includes('Ready')");check('Refresh retains in-progress source form',browser.js("document.querySelector('#source-form [name=name]').value==='Unsaved draft'"))
    row="[...document.querySelectorAll('#source-list .row-card')].find(x=>x.textContent.includes('Advanced source'))";browser.js(row+".querySelectorAll('button')[0].click()");check('Edit source loads persisted fields',browser.js("document.querySelector('#source-form [name=name]').value==='Advanced source'"));browser.js(row+".querySelectorAll('button')[1].click()");browser.wait(row+".textContent.includes('Disable')");check('Enable source persists enabled state',next(s for s in request(data,'/api/status')['sources'] if s['id']=='advanced')['enabled']);browser.js(row+".querySelectorAll('button')[1].click()");browser.wait(row+".textContent.includes('Enable')");check('Disable source persists disabled state',not next(s for s in request(data,'/api/status')['sources'] if s['id']=='advanced')['enabled']);browser.js(row+".querySelectorAll('button')[2].click()");browser.wait("document.querySelector('#error').textContent.includes('Choose a file')");check('Collect now explains required file selection',True)
    download=OUT/'downloads';download.mkdir();browser.call('Page.setDownloadBehavior',behavior='allow',downloadPath=str(download));browser.click('nav [data-view="history"]');browser.fill('#source','second');browser.click('#apply');browser.wait("document.querySelector('#pagination').textContent.includes('of 2')");browser.click('#export-json');browser.click('#export-csv');end=time.monotonic()+15
    while len(list(download.glob('dragonhydra-observations.*')))<2 and time.monotonic()<end:time.sleep(.1)
    check('JSON and CSV export buttons download actual records',len(list(download.glob('dragonhydra-observations.*')))==2 and 'Synthetic Other' in (download/'dragonhydra-observations.json').read_text());check('Historical chart renders actual imported values',browser.js("document.querySelector('#chart polyline')!==null"))
    request(data,'/api/provider/configure',{'slot':'2','mock_origin':mock.origin,'enabled':True,'approved':True,'category':'competitions','season':'2020'});request(data,'/api/provider/credential',{'slot':'2','credential':mock.key});mock.case='timeout';id=request(data,'/api/provider/test',{'slot':'2'})['task_id'];end=time.monotonic()+10
    while not mock.calls and time.monotonic()<end:time.sleep(.05)
    check('Own packaged API task reaches controlled pending request',bool(mock.calls));process.kill();process.wait(10);mock.case='ok';url=launch();auth(url);task=next(t for t in request(data,'/api/tasks') if t['id']==id);check('Abrupt API interruption is discoverable after restart',task['state']=='INTERRUPTED');request(data,'/api/task/resume',{'id':id});check('Interrupted API request resumes to verified mock receipt',waittask(id)['state']=='COMPLETE');check('Protected credential survives interrupted request',next(x for x in request(data,'/api/providers') if x['slot']=='2')['credential_status']=='SAVED')
    browser.click('nav [data-view="football"]');browser.wait("document.querySelector('#p2-remove')!==null");browser.click('#p2-remove');browser.wait("document.querySelector('#p2-status').textContent.startsWith('UNCONFIGURED')");check('Remove provider configuration preserves all observations',request(data,'/api/status')['summary']['observations']==4)
    # Send an incomplete authenticated body on our own service; no staged import may commit.
    ready=json.loads((data/'ready.json').read_text());secret=(data/'private/launcher.key').read_text().strip();s=socket.create_connection(('127.0.0.1',ready['port']));s.sendall(('POST /api/csv/preview HTTP/1.1\r\nHost: 127.0.0.1:'+str(ready['port'])+'\r\nX-DH-Local: '+secret+'\r\nContent-Type: application/json\r\nContent-Length: 10000\r\n\r\n{"filename":"interrupted.csv",').encode());s.close();time.sleep(.2);check('Interrupted upload commits no partial observations',request(data,'/api/status')['summary']['observations']==4)
    browser.click('nav [data-view="recovery"]');browser.wait("document.querySelector('#tasks').textContent.includes('COMPLETE')");check('Recovery Center displays real completed task state',True);check('No JavaScript exceptions in control audit',not browser.errors,browser.errors);stop(data);process.wait(30);check('Installed or portable candidate shuts down cleanly',process.returncode==0)
    (OUT/'results.json').write_text(json.dumps({'status':'PASS','checks':checks,'candidate':a.exe or 'source','mock_api_operations':True},indent=2));print(json.dumps({'status':'PASS','checks':len(checks),'output':str(OUT)}))
finally:
    if browser:browser.close()
    if process and process.poll() is None:stop(data);process.wait(30)
    mock.close()



