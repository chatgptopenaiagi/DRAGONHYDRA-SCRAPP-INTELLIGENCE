"""Windows end-to-end acceptance with synthetic evidence, a new profile and an ephemeral port."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'application'))
from living import VERSION
from living.contracts import now
from living.football_contracts import match, quote
from living.launcher import request as call, stop
from living.normalization import normalize
from living.scoreboards import source_for, parse_scoreboard
from living.storage import Store
from browser_cdp import Browser


def seed(data):
    store=Store(data/'intelligence.sqlite3')
    try:
        src=source_for('nba','2024-01-01')
        doc={'leagues':[{'slug':'nba','name':'Synthetic league'}], 'events':[{'id':'demo','competitions':[{
            'date':'2024-01-01T14:30:00Z','status':{'type':{'description':'Scheduled','state':'pre'}},
            'competitors':[{'homeAway':s,'team':{'id':s,'displayName':'Demo '+s}} for s in ('home','away')]}]}]}
        rows=[normalize(r,src,'SYNTHETIC') for r in parse_scoreboard(doc,'nba')]
        store.source(src);store.ingest(rows,{'id':'synthetic-board','source_id':src['id'],'scoreboard_ids':[r['id'] for r in rows],
            'content_hash':'synthetic fixture','acquired_at':now()})
        empty=source_for('nba','2024-01-02');store.source(empty)
        store.ingest([],{'id':'empty-board','source_id':empty['id'],'scoreboard_ids':[],'content_hash':'synthetic empty fixture','acquired_at':now()})
        src={'id':'demo-football','name':'Synthetic football','adapter':'upload','origin':'SYNTHETIC','enabled':False}
        event=match('f1','Demo City','Demo United','2024-01-02','FINAL',(2,1),{})
        quotes=[quote('f1',book,'1X2','H',price,{},f'2024-01-01T0{hour}:00:00Z',period='90min',settlement='regulation')
                for book,price,hour in [('Book A','2',1),('Book A','2.5',2),('Book B','3',2)]]
        store.source(src);store.ingest([normalize(r,src,'SYNTHETIC') for r in [event,*quotes]],{'id':'synthetic-market','source_id':src['id']})
        store.state('ui','preferences',{'beginner':False,'tour_complete':True})
    finally:store.close()


def run(out,exe=None):
    out.mkdir(parents=True,exist_ok=False);data=out/'data';seed(data)
    checks=[];browser=None
    env=os.environ.copy()
    if exe:
        env={k:v for k,v in env.items() if not k.startswith(('PYTHON','CONDA','VIRTUAL_ENV'))}
        env['PATH']=os.environ['SystemRoot']+'\\System32;'+os.environ['SystemRoot']
    command=[str(exe.resolve())] if exe else [sys.executable,str(ROOT/'application/living_launch.py')]
    t=time.perf_counter()
    with (out/'app.log').open('w') as log:
        proc=subprocess.Popen(command+['--serve','--port','0','--data-dir',str(data),'--mode','offline'],
            cwd=out,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    def check(name,ok):
        if not ok:raise AssertionError(name)
        checks.append(name)
    try:
        while not (data/'ready.json').exists() and proc.poll() is None and time.perf_counter()-t<40:time.sleep(.1)
        state=call(data,'/api/status');startup=time.perf_counter()-t
        check('fresh offline startup',state['mode']=='offline' and state['version']==VERSION and state['summary']['observations']==5)
        port=json.loads((data/'ready.json').read_text())['port'];base=f'http://127.0.0.1:{port}'
        try:urlopen(base+'/api/scoreboard/events?league=nba&day=2024-01-01');raise AssertionError('unrestricted endpoint')
        except HTTPError as e:check('anonymous request rejected',e.code==401)
        browser=Browser(out/'edge');browser.goto(base+'/#ticket='+call(data,'/api/session-ticket',{})['ticket'])
        browser.wait("document.querySelector('#state')?.textContent.includes('Ready')")
        browser.click('nav [data-view="sports-desk"]');browser.fill('#board-day','2024-01-01')
        browser.wait("document.querySelector('#board-events').textContent.includes('Demo home')")
        check('synthetic provenance rendered','SYNTHETIC' in browser.js("document.querySelector('#board-events').textContent"))
        browser.fill('#board-day','2024-01-02')
        browser.wait("document.querySelector('#board-state').textContent.includes('zero events')")
        check('confirmed empty day retains exportable receipt',not browser.js("document.querySelector('#board-export').disabled"))
        browser.fill('#board-day','2024-01-01')
        browser.wait("document.querySelector('#board-events').textContent.includes('Demo home')")
        browser.click('#board-collect');browser.wait("document.querySelector('#board-state').textContent.includes('Connected mode')")
        check('offline collection remains disabled',len(call(data,'/api/tasks'))==0)
        browser.click('#model-panel summary');browser.wait("document.querySelector('#model-results').textContent.includes('2024-25')")
        check('four holdouts rendered',browser.js("document.querySelectorAll('#model-results tbody tr').length")==4)
        browser.click('nav [data-view="sports"]');browser.fill('#market-format','fractional')
        for k,v in [('home','1/1'),('draw','2/1'),('away','3/1')]:browser.fill('input[name="'+k+'"]',v)
        browser.js("document.querySelector('#market-form details').open=true")
        browser.fill('#ev-p','.6');browser.fill('#ev-basis','Synthetic sensitivity');browser.click('#market-form [type=submit]')
        browser.wait("document.querySelector('#market-output').textContent.includes('0.2000')")
        check('overround and margin displayed','8.33%' in browser.js("document.querySelector('#market-state').textContent") and '7.69%' in browser.js("document.querySelector('#market-state').textContent"))
        downloads=out/'downloads';downloads.mkdir();browser.call('Browser.setDownloadBehavior',behavior='allow',downloadPath=str(downloads.resolve()))
        browser.click('#market-export');target=downloads/'dragonhydra-market.json';end=time.monotonic()+10
        while not target.exists() and time.monotonic()<end:time.sleep(.1)
        check('downloaded scenario reproduces EV',json.loads(target.read_text())['expected_value']['net_per_unit']=='0.2')
        browser.click('#market-ai');browser.wait("document.querySelector('#error').textContent.includes('disabled')")
        check('optional AI failure preserves evidence',not browser.js("document.querySelector('#market-export').disabled"))
        browser.click('nav [data-view="football-research"]');browser.wait("document.querySelector('.movement summary')!==null")
        browser.click('.movement summary');browser.wait("document.querySelector('.movement canvas')!==null")
        check('two bookmakers and timestamped dispersion displayed','Decimal range' in browser.js("document.querySelector('.movement').textContent") and 'Book B' in browser.js("document.querySelector('.movement').textContent"))
        browser.call('Emulation.setDeviceMetricsOverride',width=390,height=844,deviceScaleFactor=1,mobile=False)
        browser.click('nav [data-view="sports-desk"]');browser.wait("!document.querySelector('#sports-desk').hidden")
        check('scoreboard fits mobile viewport',browser.js("document.querySelector('#sports-desk').getBoundingClientRect().right<=391"))
        check('mobile navigation leaves the competition visible',browser.js("document.querySelector('#sports-desk').getBoundingClientRect().top<innerHeight"))
        browser.screenshot('sports-desk-mobile.png')
        check('no browser runtime errors',not browser.errors)
        result={'status':'PASS','version':VERSION,'checks':checks,'startup_seconds':round(startup,3),
                'sha256':hashlib.file_digest(exe.open('rb'),'sha256').hexdigest() if exe else None}
    finally:
        if browser:browser.close()
        try:
            if proc.poll() is None:stop(data)
            proc.wait(15)
        finally:
            if proc.poll() is None:proc.terminate();proc.wait(10)
    check('graceful process exit',proc.returncode==0)
    (out/'result.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--exe',type=Path)
    args=parser.parse_args();run(args.out.resolve(),args.exe)
