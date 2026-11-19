"""Six separate synthetic football providers. Never presented as live evidence."""
import json,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs

def payload(slot,path,query):
    league={'id':1,'name':'Synthetic League','season':2020};team={'id':10,'name':'Synthetic Home'};away={'id':20,'name':'Synthetic Away'}
    if slot==1:
        action=query.get('action',[''])[0]
        if action=='get_leagues':return [{'league_id':'1','league_name':'Synthetic League','league_season':'2020'}]
        if action=='get_odds':return [{'match_id':'100','odd_bookmakers':'Synthetic Book','odd_1':'2.5','odd_x':'3.1','odd_2':'3.2','odd_date':'2020-01-01 10:00:00'}]
        return [{'match_id':'100','match_hometeam_name':'Synthetic Home','match_awayteam_name':'Synthetic Away','match_date':'2020-01-01','match_status':'Finished','match_hometeam_score':'2','match_awayteam_score':'1','league_id':'1','league_year':'2020'}]
    if slot==2:
        if path=='/leagues':rows=[{'league':league,'country':{'name':'Synthetic Country'},'seasons':[{'year':2020}]}]
        elif path=='/odds':rows=[{'fixture':{'id':100},'update':'2020-01-01T10:00:00Z','bookmakers':[{'id':1,'name':'Synthetic Book','bets':[{'id':1,'name':'Match Winner','values':[{'value':'Home','odd':'2.5'}]}]}]}]
        else:rows=[{'fixture':{'id':100,'date':'2020-01-01T12:00:00Z','status':{'short':'FT'}},'league':league,'teams':{'home':team,'away':away},'score':{'fulltime':{'home':2,'away':1}},'goals':{'home':2,'away':1}}]
        return {'errors':[],'results':len(rows),'paging':{'current':int(query.get('page',['1'])[0]),'total':1},'response':rows}
    if slot==3:
        if path.endswith('all_leagues.php'):return {'leagues':[{'idLeague':'1','strLeague':'Synthetic League','strSport':'Soccer'}]}
        if path.endswith('searchteams.php'):return {'teams':[{'idTeam':'10','strTeam':'Synthetic Home','strSport':'Soccer','idLeague':'1'}]}
        return {'events':[{'idEvent':'100','strHomeTeam':'Synthetic Home','strAwayTeam':'Synthetic Away','dateEvent':'2020-01-01','strStatus':'Match Finished','intHomeScore':'2','intAwayScore':'1','idLeague':'1','strSeason':'2020'}]}
    if slot==4:
        if path=='/leagues':rows=[{'id':1,'name':'Synthetic League','country':{'name':'Synthetic Country'},'seasons':[{'season':2020}]}]
        else:rows=[{'id':100,'homeTeam':team,'awayTeam':away,'date':'2020-01-01T12:00:00Z','league':league,'state':{'description':'Finished','score':{'current':'2 - 1'}}}]
        return {'data':rows,'pagination':{'totalCount':1,'offset':int(query.get('offset',['0'])[0]),'limit':100},'plan':{'tier':'BASIC','message':'SYNTHETIC ACCEPTANCE ONLY'}}
    if slot==5:
        if path=='/v4/competitions':return {'competitions':[{'id':1,'name':'Synthetic League','plan':'TIER_ONE','currentSeason':{'startDate':'2020-01-01'}}]}
        return {'matches':[{'id':100,'homeTeam':team,'awayTeam':away,'utcDate':'2020-01-01T12:00:00Z','status':'FINISHED','competition':league,'season':{'startDate':'2020-01-01'},'score':{'fullTime':{'home':2,'away':1},'duration':'REGULAR'},'lastUpdated':'2020-01-01T14:00:00Z'}]}
    if path.startswith('/getavailableleagues'):return [{'leagueShortcut':'1','leagueName':'Synthetic League','leagueSeason':2020,'leagueId':1,'sport':{'sportName':'Fußball'}}]
    return [{'matchID':100,'team1':{'teamId':10,'teamName':'Synthetic Home'},'team2':{'teamId':20,'teamName':'Synthetic Away'},'matchDateTimeUTC':'2020-01-01T12:00:00Z','matchIsFinished':True,'leagueShortcut':'1','leagueSeason':2020,'matchResults':[{'resultTypeID':2,'resultTypeKind':'After90Minutes','pointsTeam1':2,'pointsTeam2':1}],'lastUpdateDateTime':'2020-01-01T14:00:00'}]

class Mock:
    def __init__(self,slot):
        self.slot=slot;self.key=f'SYNTHETIC-KEY-PROVIDER-{slot}-ONLY';self.case='ok';self.calls=[];parent=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                p=urlsplit(self.path);q=parse_qs(p.query);provided=q.get('APIkey',[None])[0] if slot==1 else self.headers.get({2:'x-apisports-key',4:'x-rapidapi-key',5:'X-Auth-Token'}.get(slot,'X-unused'))
                parent.calls.append({'path':p.path,'authenticated':provided==parent.key if slot in (1,2,4,5) else True,'case':parent.case})
                status=200;data=payload(slot,p.path,q);headers={}
                if slot in (1,2,4,5) and provided!=parent.key:status=401;data={'error':'Synthetic authentication rejection'}
                elif parent.case=='unauthorized':status=403;data={}
                elif parent.case=='rate':status=429;data={};headers['Retry-After']='120'
                elif parent.case=='timeout':time.sleep(9)
                elif parent.case=='disconnect':self.connection.close();return
                elif parent.case=='schema':data={'unexpected':True}
                elif parent.case=='echo':data['echoed_secret']=parent.key if isinstance(data,dict) else None
                elif parent.case=='pagination' and slot==2:
                    page=int(q.get('page',['1'])[0]);data['paging']={'current':page,'total':2};data['response'][0]['league']['id']=page
                elif parent.case=='endless' and slot==2:data['paging']['total']=20
                raw=b'{invalid-json' if parent.case=='malformed' else json.dumps(data).encode()
                try:
                    self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)))
                    for k,v in headers.items():self.send_header(k,v)
                    self.end_headers();self.wfile.write(raw)
                except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True;self.origin=f'http://127.0.0.1:{self.server.server_port}';self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(5)
