from .base import Adapter,array,required,competition
from ..football_contracts import match,standing,entity
class TheSportsDB(Adapter):
    name='TheSportsDB';website='https://www.thesportsdb.com/';docs='https://www.thesportsdb.com/documentation';base='https://www.thesportsdb.com';auth='public-demo';daily_cap=100;window_limit=30
    categories=('teams','competitions','fixtures','results','standings');limitations='Free public v1 demo key 123. Endpoint result caps apply; whole-season completeness is not guaranteed. V2 live scores require premium access and are disabled.'
    def request(self,c,operation,page=1):
        cat='competitions' if operation=='test' else c['category'];params={}
        if cat=='teams':path='searchteams.php';params={'t':c.get('team') or 'Arsenal'}
        elif cat=='competitions':path='all_leagues.php'
        elif cat=='standings':path='lookuptable.php';params={'l':required(c,'competition'),'s':required(c,'season')}
        else:path='eventsseason.php';params={'id':required(c,'competition'),'s':required(c,'season')}
        return '/api/v1/json/123/'+path,params,cat
    def parse(self,data,category,c):
        key={'teams':'teams','competitions':'leagues','standings':'table','fixtures':'events','results':'events'}[category];out=[]
        for r in array(data,key):
            if category=='teams':
                if r.get('strSport')!='Soccer':continue
                out.append(entity('team',r['idTeam'],r['strTeam'],r,competition=r.get('idLeague'),country=r.get('strCountry')))
            elif category=='competitions':
                if r.get('strSport')=='Soccer':out.append(competition(r['idLeague'],r['strLeague'],r))
            elif category=='standings':out.append(standing(r['idTeam'],r.get('strTeam'),r.get('intPoints'),r,c['competition'],r.get('strSeason') or c.get('season'),r.get('intRank')))
            else:
                final=r.get('strStatus') in ('Match Finished','FT','AET','AP');status='FINAL' if final else 'UNKNOWN'
                if category=='results' and not final:continue
                out.append(match(r['idEvent'],r['strHomeTeam'],r['strAwayTeam'],r.get('strTimestamp') or r.get('dateEvent'),status,(r.get('intHomeScore'),r.get('intAwayScore')),r,r.get('idLeague'),r.get('strSeason'),r.get('idHomeTeam'),r.get('idAwayTeam'),period='PROVIDER_FINAL'))
        return out
