from .base import Adapter,array,required,competition
from ..football_contracts import match,standing,entity
class OpenLigaDB(Adapter):
    name='OpenLigaDB';website='https://www.openligadb.de/';docs='https://api.openligadb.de/index.html';base='https://api.openligadb.de';auth='none';daily_cap=24;window_limit=60;minimum_interval=21600
    categories=('competitions','fixtures','results','teams','standings');limitations='Public community data under ODbL 1.0; no key. 60 requests/minute/IP. This client uses a conservative 24/day cap and six-hour minimum schedule; cache historical seasons. Accuracy is not guaranteed.'
    def request(self,c,operation,page=1):
        cat='competitions' if operation=='test' else c['category']
        if cat=='competitions':path='/getavailableleagues/'+required(c,'season')
        else:
            path={'teams':'/getavailableteams/','standings':'/getbltable/','fixtures':'/getmatchdata/','results':'/getmatchdata/'}[cat]+required(c,'competition')+'/'+required(c,'season')
            if c.get('matchday') and cat in ('fixtures','results'):path+='/'+str(c['matchday'])
        return path,{},cat
    def parse(self,data,category,c):
        out=[]
        for r in array(data):
            if category=='competitions':
                if r.get('sport',{}).get('sportName') not in (None,'Fußball','Football','Soccer'):continue
                out.append(competition(r['leagueShortcut'],r['leagueName'],r,[r['leagueSeason']],league_id=r.get('leagueId')))
            elif category=='teams':out.append(entity('team',r['teamId'],r['teamName'],r,competition=c['competition']))
            elif category=='standings':out.append(standing(r['teamInfoId'],r['teamName'],r.get('points'),r,c['competition'],c['season']))
            else:
                final=r['matchIsFinished'];g=next((x for x in r.get('matchResults',[]) if x.get('resultTypeID')==2),{})
                if category=='results' and not final:continue
                out.append(match(r['matchID'],r['team1']['teamName'],r['team2']['teamName'],r.get('matchDateTimeUTC'),'FINAL' if final else 'UNKNOWN',(g.get('pointsTeam1'),g.get('pointsTeam2')),r,r.get('leagueShortcut'),r.get('leagueSeason'),r['team1']['teamId'],r['team2']['teamId'],r.get('lastUpdateDateTime'),period=g.get('resultTypeKind','PROVIDER_FINAL')))
        return out
