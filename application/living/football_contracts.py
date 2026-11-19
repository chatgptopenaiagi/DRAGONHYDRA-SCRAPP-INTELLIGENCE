"""Canonical football records retain provider identities, clocks and score periods."""
from .contracts import fingerprint
from .normalization import timestamp,number

CONTRACTS={name:'football.'+name+'/1' for name in ('competition','team','fixture','result','event','standing','odds.quote','player.statistic')}
def clock(value):
    try:return timestamp(value)
    except (ValueError,TypeError):return None
def entity(category,id,name,raw,**meta):
    if id in (None,''):raise ValueError('Provider record lacks its required identifier')
    return {'key':'football.'+category,'kind':'FOOTBALL_RECORD','value':None,'unit':'record','identity':category+'|'+str(id),'text':str(name or id),'metadata':{'contract':CONTRACTS[category],'provider_record_id':str(id),'original_provider_record':raw,**meta}}
def match(id,home,away,day,status,goals,raw,competition='',season='',home_id=None,away_id=None,reported=None,period='REGULATION'):
    if not home or not away:raise ValueError('Provider match is missing team identities')
    final=status=='FINAL';hg,ag=goals
    if hg not in (None,'') and ag not in (None,''):
        if any(isinstance(x,bool) or str(x).isdigit()==False or int(x)>100 for x in (hg,ag)):raise ValueError('Provider goal counts are invalid')
        hg,ag=int(hg),int(ag)
    else:hg=ag=None
    if final and hg is None:raise ValueError('Provider marks a final result but supplies no complete score')
    category='result' if final else 'fixture';r=entity(category,id,home+' — '+away,raw,provider_match_id=str(id),home_team=home,away_team=away,home_id=home_id,away_id=away_id,competition=str(competition),season=str(season),scheduled_at=clock(day),date=str(day)[:10] if day else None,scheduled_original=day,status=status,home_goals=hg,away_goals=ag,score_period=period,reported_at=clock(reported),reported_original=reported,identity_status='UNRECONCILED')
    r['observed_at']=clock(reported)
    if final:r.update(key='football.total_goals',kind='SPORTS_RESULT',value=hg+ag,unit='goals')
    return r
def standing(id,name,points,raw,competition,season,rank=None):
    r=entity('standing',str(competition)+'|'+str(season)+'|'+str(id),name,raw,team=name,team_id=id,competition=str(competition),season=str(season),rank=rank)
    r.update(value=number(points),unit='points',key='football.standing.points');return r
def quote(id,bookmaker,market,outcome,price,raw,reported=None,**meta):
    if not bookmaker or not market or not outcome:raise ValueError('Odds quote lacks bookmaker, market or outcome identity')
    r=entity('odds.quote',str(id)+'|'+str(bookmaker)+'|'+str(market)+'|'+str(outcome),outcome,raw,provider_match_id=str(id),bookmaker=str(bookmaker),market=str(market),outcome=str(outcome),quote_time=clock(reported),quote_time_original=reported,quote_status='RECORDED_PROVIDER_QUOTE_NOT_EXECUTABLE',**meta)
    r.update(kind='SPORTS_ODDS',key='football.odds.'+str(market)+'.'+str(outcome),value=number(price),unit='decimal_odds',observed_at=clock(reported));return r
