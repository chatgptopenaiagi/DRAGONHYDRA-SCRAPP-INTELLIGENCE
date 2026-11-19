from .base import Adapter,array,required,competition,ProviderError
from ..football_contracts import match,standing,quote,entity
class ApiSports(Adapter):
    name='API-Football (API-Sports)';website='https://www.api-football.com/';docs='https://www.api-football.com/documentation-v3';base='https://v3.football.api-sports.io';auth='header';key_name='x-apisports-key';daily_cap=100;window_limit=10
    categories=('competitions','fixtures','results','standings','teams','odds');limitations='Free: 100 requests/day; seasons restricted. Coverage and odds availability must be checked for the selected competition. Only direct API-Sports keys are supported.'
    def request(self,c,operation,page=1):
        if operation=='status':return '/status',{},'account_status'
        cat='competitions' if operation=='test' else c['category'];endpoint={'competitions':'leagues','fixtures':'fixtures','results':'fixtures','standings':'standings','teams':'teams','odds':'odds'}[cat];params={}
        if cat!='competitions':params.update(league=required(c,'competition'),season=required(c,'season'))
        if cat=='results':params['status']='FT-AET-PEN'
        if c.get('date_from') and cat in ('fixtures','results'):params.update({'from':c['date_from'],'to':required(c,'date_to')})
        if page>1:params['page']=page
        return '/'+endpoint,params,cat
    def parse(self,data,category,c):
        if not isinstance(data,dict):raise ProviderError('Expected API-Sports response envelope')
        if data.get('errors'):
            keys=' '.join(data['errors']) if isinstance(data['errors'],dict) else ''
            raise ProviderError('Provider rejected authentication, quota or selected coverage. Inspect the provider account.','RATE_LIMITED' if 'rate' in keys.lower() or 'requests' in keys.lower() else 'AUTHENTICATION_FAILED' if 'token' in keys.lower() or 'key' in keys.lower() else 'UNAVAILABLE')
        if category=='account_status':
            r=data.get('response',{});q=r.get('requests',{}) if isinstance(r,dict) else {}
            if type(q.get('current')) is not int or type(q.get('limit_day')) is not int or min(q['current'],q['limit_day'])<0:raise ProviderError('Provider status quota schema is invalid')
            if r.get('subscription',{}).get('active') is not True:raise ProviderError('Provider subscription is inactive; no collection was started.','AUTHENTICATION_FAILED')
            return []
        out=[]
        for r in array(data,'response'):
            if category=='competitions':out.append(competition(r['league']['id'],r['league']['name'],r,[s['year'] for s in r.get('seasons',[])],country=r.get('country',{}).get('name')))
            elif category=='teams':out.append(entity('team',r['team']['id'],r['team']['name'],r,competition=c['competition']))
            elif category=='standings':
                league=r['league']
                for group in league['standings']:
                    for s in group:out.append(standing(s['team']['id'],s['team']['name'],s.get('points'),s,league['id'],league.get('season'),s.get('rank')))
            elif category=='odds':
                for b in r['bookmakers']:
                    for bet in b['bets']:
                        for v in bet['values']:out.append(quote(r['fixture']['id'],b['name'],str(bet['id'])+':'+bet['name'],v['value'],v['odd'],{'fixture':r['fixture'],'league':r.get('league'),'bookmaker':b['id'],'bet':bet['id'],'value':v,'update':r.get('update')},r.get('update'),competition=c['competition'],season=c.get('season')))
            else:
                f=r['fixture'];s=f['status']['short'];final=s in ('FT','AET','PEN');status='FINAL' if final else 'SCHEDULED' if s in ('NS','TBD') else 'LIVE_OR_OTHER';g=r.get('score',{}).get('fulltime') or {}
                if category=='results' and not final:continue
                out.append(match(f['id'],r['teams']['home']['name'],r['teams']['away']['name'],f.get('date'),status,(g.get('home'),g.get('away')) if final else (r.get('goals',{}).get('home'),r.get('goals',{}).get('away')),r,r['league']['id'],r['league'].get('season'),r['teams']['home']['id'],r['teams']['away']['id']))
        return out
    def next_page(self,data,page):
        p=data.get('paging',{});current=int(p.get('current',page));total=int(p.get('total',1))
        if current!=page or total<0:raise ProviderError('Invalid provider pagination')
        return page+1 if current<total else None
