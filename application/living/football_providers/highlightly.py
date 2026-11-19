import re
from .base import Adapter,array,required,competition,ProviderError
from ..football_contracts import match,standing,entity
class Highlightly(Adapter):
    name='Highlightly';website='https://highlightly.net/football-api/';docs='https://highlightly.net/football-api/documentation/';base='https://soccer.highlightly.net';auth='header';key_name='x-rapidapi-key';daily_cap=100;window_limit=10
    categories=('competitions','fixtures','results','standings');limitations='Free Basic: 100 requests/day. Odds are excluded from the free plan and disabled. Results may be restricted by plan; returned plan notices are retained. Direct Highlightly keys only.'
    def request(self,c,operation,page=1):
        cat='competitions' if operation=='test' else c['category'];params={}
        if cat!='competitions':params['leagueId']=required(c,'competition')
        if cat=='standings':params['season']=required(c,'season')
        else:
            params.update(limit=100,offset=(page-1)*100)
            if c.get('season') and cat!='competitions':params['season']=c['season']
        return {'competitions':'/leagues','standings':'/standings','fixtures':'/matches','results':'/matches'}[cat],params,cat
    def parse(self,data,category,c):
        out=[]
        if category=='standings':
            for group in array(data,'groups'):
                for r in array(group,'standings'):out.append(standing(r['team']['id'],r['team']['name'],r.get('points'),r,data['league']['id'],data['league'].get('season'),r.get('position')))
            return out
        for r in array(data,'data'):
            if category=='competitions':out.append(competition(r['id'],r['name'],r,[s['season'] for s in r.get('seasons',[])],country=r.get('country',{}).get('name')))
            else:
                state=r['state']['description'];final=state in ('Finished','Finished after penalties','Finished after extra time');status='FINAL' if final else 'SCHEDULED' if state in ('Not started','To be announced') else 'LIVE_OR_OTHER';g=re.fullmatch(r'(\d+)\s*-\s*(\d+)',r['state'].get('score',{}).get('current') or '')
                if category=='results' and not final:continue
                out.append(match(r['id'],r['homeTeam']['name'],r['awayTeam']['name'],r.get('date'),status,(g[1],g[2]) if g else (None,None),r,r['league']['id'],r['league'].get('season'),r['homeTeam']['id'],r['awayTeam']['id'],period='REGULATION' if state=='Finished' else 'PROVIDER_CURRENT'))
        return out
    def next_page(self,data,page):
        p=data.get('pagination')
        if not p:return None
        if int(p['offset'])!=(page-1)*100 or not 0<int(p['limit'])<=100:raise ProviderError('Unexpected pagination window; no partial batch committed')
        if int(p['limit'])!=100 and int(p['totalCount'])>int(p['offset'])+int(p['limit']):raise ProviderError('Provider altered page size; narrow the request before retrying')
        return page+1 if int(p['offset'])+int(p['limit'])<int(p['totalCount']) else None
