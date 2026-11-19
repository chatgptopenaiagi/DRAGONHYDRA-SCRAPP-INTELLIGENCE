from .base import Adapter,array,required,competition
from ..football_contracts import match,standing,entity
class FootballData(Adapter):
    name='football-data.org';website='https://www.football-data.org/';docs='https://docs.football-data.org/general/v4/index.html';base='https://api.football-data.org';auth='header';key_name='X-Auth-Token';window_limit=10;daily_cap=100
    categories=('competitions','fixtures','results','standings','teams');limitations='Free: 12 competitions, delayed scores and schedules, 10 requests/minute. Live scores and deeper data require paid plans; no odds connector is enabled.'
    def request(self,c,operation,page=1):
        cat='competitions' if operation=='test' else c['category'];path='/v4/competitions';params={}
        if cat!='competitions':path+='/'+required(c,'competition')+'/'+('matches' if cat in ('fixtures','results') else cat)
        if c.get('season') and cat!='competitions':params['season']=c['season']
        if cat=='results':params['status']='FINISHED'
        if c.get('date_from') and cat in ('fixtures','results'):params.update(dateFrom=c['date_from'],dateTo=required(c,'date_to'))
        return path,params,cat
    def parse(self,data,category,c):
        out=[]
        if category=='standings':
            for group in array(data,'standings'):
                for r in array(group,'table'):out.append(standing(r['team']['id'],r['team']['name'],r.get('points'),r,data['competition']['id'],data.get('season',{}).get('startDate'),r.get('position')))
            return out
        for r in array(data,'matches' if category in ('fixtures','results') else category):
            if category=='competitions':
                if r.get('plan')=='TIER_ONE':out.append(competition(r['id'],r['name'],r,[str(r.get('currentSeason',{}).get('startDate',''))[:4]],code=r.get('code')))
            elif category=='teams':out.append(entity('team',r['id'],r['name'],r,competition=c['competition']))
            else:
                final=r['status']=='FINISHED';status='FINAL' if final else 'SCHEDULED' if r['status'] in ('SCHEDULED','TIMED') else 'LIVE_OR_OTHER';g=r.get('score',{}).get('fullTime') or {}
                if category=='results' and not final:continue
                out.append(match(r['id'],r['homeTeam']['name'],r['awayTeam']['name'],r.get('utcDate'),status,(g.get('home'),g.get('away')),r,r['competition']['id'],str(r.get('season',{}).get('startDate',''))[:4],r['homeTeam']['id'],r['awayTeam']['id'],r.get('lastUpdated'),period=r.get('score',{}).get('duration','UNKNOWN')))
        return out
