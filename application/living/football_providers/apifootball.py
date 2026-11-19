from .base import Adapter,array,required,competition,ProviderError
from ..football_contracts import match,standing,quote,entity
class ApiFootballCom(Adapter):
    name='APIfootball.com';website='https://apifootball.com/';docs='https://apifootball.com/documentation/';base='https://apiv3.apifootball.com';auth='query';key_name='APIkey';window_limit=180;window_seconds=3600;daily_cap=180
    categories=('competitions','fixtures','results','standings','teams','odds');limitations='Free: England Championship and France Ligue 2; odds advertised, access unverified until returned. Query authentication is required by this provider; requests and secrets are never logged.'
    def request(self,c,operation,page=1):
        category='competitions' if operation=='test' else c['category'];actions={'competitions':'get_leagues','fixtures':'get_events','results':'get_events','standings':'get_standings','teams':'get_teams','odds':'get_odds'};params={'action':actions[category]}
        if category!='competitions':params['league_id']=required(c,'competition')
        if category in ('fixtures','results','odds'):params.update({'from':required(c,'date_from'),'to':required(c,'date_to')})
        return '/',params,category
    def parse(self,data,category,c):
        if isinstance(data,dict) and data.get('error'):
            code=str(data['error']);raise ProviderError('Provider rejected the request. Check the key and free competition access.','AUTHENTICATION_FAILED' if code in ('401','403') else 'UNAVAILABLE')
        rows=array(data);out=[]
        for r in rows:
            if category=='competitions':out.append(competition(r['league_id'],r['league_name'],r,[r.get('league_season','')],country=r.get('country_name')))
            elif category=='teams':out.append(entity('team',r['team_key'],r['team_name'],r,competition=c['competition']))
            elif category=='standings':out.append(standing(r['team_id'],r['team_name'],r.get('overall_league_PTS'),r,c['competition'],c.get('season'),r.get('overall_league_position')))
            elif category=='odds':
                # Only documented decimal fields; unknown markets remain in the original response.
                fields={'odd_1':('1X2','H'),'odd_x':('1X2','D'),'odd_2':('1X2','A'),'bts_yes':('BTS','Yes'),'bts_no':('BTS','No')}
                for k in r:
                    if k.startswith('o+') or k.startswith('u+'):fields[k]=('O/U '+k[2:],'Over' if k[0]=='o' else 'Under')
                for field,(market,outcome) in fields.items():
                    if r.get(field) not in (None,'','0'):out.append(quote(r['match_id'],r.get('odd_bookmakers'),market,outcome,r[field],r,r.get('odd_date'),competition=c['competition']))
            else:
                final=r.get('match_status') in ('Finished','After ET','After Pen.');status='FINAL' if final else 'SCHEDULED' if not r.get('match_status') else 'LIVE_OR_OTHER'
                if category=='results' and not final:continue
                out.append(match(r['match_id'],r['match_hometeam_name'],r['match_awayteam_name'],r.get('match_date'),status,(r.get('match_hometeam_score'),r.get('match_awayteam_score')),r,r.get('league_id'),r.get('league_year') or c.get('season',''),r.get('match_hometeam_id'),r.get('match_awayteam_id'),period='REGULATION' if r.get('match_status')=='Finished' else 'PROVIDER_FINAL'))
        return out
