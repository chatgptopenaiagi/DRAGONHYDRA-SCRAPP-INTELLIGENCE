"""Click the complete CSV workflow in Edge, with genuine owner CSV, in isolated state."""
import argparse,json,subprocess,sys,time,statistics,hashlib,csv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'application'))
from living.launcher import request,running,stop
from browser_cdp import Browser
parser=argparse.ArgumentParser();parser.add_argument('--exe');parser.add_argument('--csv',type=Path,required=True,help='Owner-supplied genuine 217-row champs.csv; never distributed with the test');args=parser.parse_args()
out=ROOT/'evidence/mission-005'/('csv-browser-'+('packaged-' if args.exe else 'source-')+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime()));out.mkdir();data=out/'data';checks=[];browser=None;process=None
def record(name,condition,detail=None):
    checks.append({'name':name,'status':'PASS' if condition else 'FAIL','detail':detail});(out/'results.json').write_text(json.dumps({'checks':checks},indent=2));assert condition,name
def launch():
    global process
    command=[args.exe] if args.exe else [sys.executable,'-B',str(ROOT/'application/living_launch.py')]
    log=(out/('startup-'+str(time.time_ns())+'.log')).open('w');process=subprocess.Popen(command+['--serve','--data-dir',str(data),'--port','0'],stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW);log.close();deadline=time.monotonic()+30
    while not running(data) and process.poll() is None and time.monotonic()<deadline:time.sleep(.15)
    record('Isolated application startup',bool(running(data)));return 'http://127.0.0.1:'+str(json.loads((data/'ready.json').read_text())['port'])+'/'
def authenticate(url):
    ticket=request(data,'/api/session-ticket',{})['ticket'];browser.goto(url+'#ticket='+ticket+'&view=sources');browser.wait("document.querySelector('#state')?.textContent.includes('Ready')");browser.wait("document.querySelector('#csv-preview')!==null")
try:
    url=launch();browser=Browser(out/'edge');authenticate(url)
    record('Empty source explains create-source workflow',browser.js("document.querySelector('#csv-source').textContent.includes('No source configured')"))
    browser.upload('#csv-file',args.csv);browser.click('#csv-preview');browser.wait("!document.querySelector('#csv-steps').hidden")
    record('Actual owner CSV preview shows 217 records',browser.js("document.querySelector('#csv-file-info').textContent.includes('217 records')"))
    record('Combined score and date-only mapping suggested',browser.js("document.querySelector('#csv-map-score').value==='FT'&&document.querySelector('#csv-date-format').value==='champs'"))
    browser.fill('#csv-competition','UEFA Champions League');browser.fill('#csv-season','2015-2016');browser.click('#csv-create-source');browser.wait("document.querySelector('#csv-source').value!==''");source=browser.js("document.querySelector('#csv-source').value")
    browser.click('#csv-validate');browser.wait("!document.querySelector('#csv-confirm').disabled");record('All actual CSV rows validate through GUI',browser.js("document.querySelector('#csv-result').textContent.includes('217 observations ready')"))
    browser.click('#csv-confirm');browser.wait("document.querySelector('#csv-result').textContent.includes('COMPLETE')",30)
    rows=request(data,'/api/observations?source='+source+'&limit=10000')['rows'];record('217 genuine results committed with original cells',len(rows)==217 and all(r['origin']=='IMPORTED' and 'original_csv_row' in r['metadata'] for r in rows))
    record('No date-only timestamps fabricated',all(r['observed_at'] is None and len(r['metadata']['date'])==10 for r in rows))
    record('Extra-time and penalties retained separately',sum('score_note' in r['metadata'] for r in rows)==3)
    browser.click('#csv-view-records');browser.wait("document.querySelector('#pagination').textContent.includes('217')");record('Imported records visible in Historical observations',browser.js("document.querySelector('#title').textContent==='Historical observations'"))
    browser.click('nav [data-view="sources"]');browser.click('#csv-analyze-records');browser.wait("document.querySelector('#analysis').textContent.includes('Mean')||document.querySelector('#analysis').textContent.includes('mean')")
    analysis=request(data,'/api/analyses')[0];reference=statistics.mean(int(r['metadata']['original_csv_row']['FT'].split('-')[0])+int(r['metadata']['original_csv_row']['FT'].split('-')[1].split()[0]) for r in rows)
    record('GUI analysis agrees with independent score arithmetic',abs(float(analysis['output']['mean'])-reference)<1e-10,{'n':len(rows),'mean':reference})
    browser.click('nav [data-view="sources"]');browser.click('#csv-validate');browser.wait("!document.querySelector('#csv-confirm').disabled");browser.click('#csv-confirm');browser.wait("document.querySelector('#csv-result').textContent.includes('COMPLETE')&&document.querySelector('#csv-result').textContent.includes('duplicates')")
    time.sleep(.5);record('Repeated file import preserves identities',request(data,'/api/observations?source='+source)['total']==217)
    malformed=out/'invalid.csv';malformed.write_text('value,unit\n1,m\nnot-a-number,m\n');browser.upload('#csv-file',malformed);browser.click('#csv-preview');browser.wait("document.querySelector('#csv-file-info').textContent.includes('invalid.csv')");browser.click('#csv-validate');browser.wait("document.querySelector('#csv-result').textContent.includes('INVALID')");record('Invalid row diagnostics and atomic rejection',browser.js("document.querySelector('#csv-result').textContent.includes('Row 3')&&document.querySelector('#csv-confirm').disabled") and request(data,'/api/status')['summary']['observations']==217)
    browser.click('nav [data-view="football"]');browser.wait("document.querySelectorAll('.provider-card').length===6");record('Six named independent provider cards visible',browser.js("document.querySelectorAll('.provider-card').length===6"));browser.screenshot('providers.png')
    browser.click('nav [data-view="recovery"]');browser.click('#backup');browser.wait("document.querySelector('#evidence').open");record('Backup creation through GUI',bool(list((data/'backups').glob('*.sqlite3'))));browser.click('#close-evidence')
    stop(data);process.wait(30);url=launch();authenticate(url);record('Source and record identities survive restart',request(data,'/api/observations?source='+source)['total']==217 and any(s['id']==source for s in request(data,'/api/status')['sources']))
    browser.click('nav [data-view="history"]');browser.fill('#search','Real Madrid');browser.click('#apply');browser.wait("document.querySelector('#rows').textContent.length>0");record('Historical search operates on imported evidence',browser.js("document.querySelector('#pagination').textContent")!='0–0 of 0');browser.screenshot('historical-results.png')
    record('No JavaScript runtime exceptions',not browser.errors,browser.errors);stop(data);process.wait(30);record('Clean shutdown',process.returncode==0)
    (out/'results.json').write_text(json.dumps({'status':'PASS','checks':checks,'actual_csv_sha256':hashlib.sha256(args.csv.read_bytes()).hexdigest(),'candidate':args.exe or 'source','output':str(out)},indent=2));print(json.dumps({'status':'PASS','checks':len(checks),'output':str(out)}))
finally:
    if browser:browser.close()
    if process and process.poll() is None:
        stop(data);process.wait(30)
