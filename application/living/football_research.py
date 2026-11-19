"""Bounded, read-only football browsing. Link quotations only by source-owned identity."""
from decimal import Decimal,InvalidOperation
from .contracts import now

def research(store,filters):
    if set(filters)-{'source','origin','search','from','to','limit','offset'}:raise ValueError('Unknown football research filter')
    limit=int(filters.get('limit',25));offset=int(filters.get('offset',0))
    if not 1<=limit<=50 or not 0<=offset<=10000:raise ValueError('Choose 1–50 matches per page')
    search=str(filters.get('search','')).strip().casefold()
    if len(search)>120:raise ValueError('Search is limited to 120 characters')
    data=store.query({k:filters[k] for k in ('source','origin') if filters.get(k)},10000)
    if data['total']>10000:raise ValueError('Choose one football source to search fewer than 10,001 records. No records were silently omitted.')
    results=[];quotes={};unlinked=0
    def match_key(row,m,quote=False):
        explicit=m.get('match_id') if quote else m.get('provider_event_id') or m.get('fixture_id') or m.get('id')
        if explicit:return (row['source_id'],'id',str(explicit))
        parts=[m.get('competition'),m.get('season'),m.get('home_team') or m.get('home'),m.get('away_team') or m.get('away'),m.get('date') or (m.get('scheduled_at') or '')[:10]]
        return (row['source_id'],'exact',*map(str,parts)) if all(x is not None and x!='' for x in parts) else None
    for r in data['rows']:
        m=r.get('metadata',{})
        if r['kind']=='SPORTS_ODDS':
            key=match_key(r,m,True)
            if key:quotes.setdefault(key,[]).append(r)
            else:unlinked+=1
    linked=set()
    for r in data['rows']:
        m=r.get('metadata',{});contract=m.get('contract','')
        if r['kind']!='SPORTS_RESULT' and contract not in ('football.fixture/1','football.result/1'):continue
        home=m.get('home_team') or m.get('home');away=m.get('away_team') or m.get('away')
        if not home or not away:continue
        day=m.get('date') or (m.get('scheduled_at') or '')[:10] or (r.get('observed_at') or '')[:10] or None
        if search and search not in ' '.join(str(x or '') for x in (home,away,m.get('competition'),m.get('season'))).casefold():continue
        if filters.get('from') and (not day or day<filters['from']):continue
        if filters.get('to') and (not day or day>filters['to']):continue
        key=match_key(r,m);available=[]
        for q in quotes.get(key,[]):
            linked.add(q['id']);qm=q['metadata']
            try:price=Decimal(q['value']);probability=str(Decimal(100)/price) if price>1 else None
            except (InvalidOperation,TypeError):probability=None
            available.append({'id':q['id'],'bookmaker':qm.get('bookmaker') or 'Not supplied','market':qm.get('market') or q['key'],'outcome':qm.get('outcome') or 'Not supplied','decimal_odds':q['value'],'implied_percent':probability,'quote_time':q.get('observed_at'),'origin':q['origin'],'evidence':q})
        results.append({'id':r['id'],'source':r['source_id'],'origin':r['origin'],'home':home,'away':away,'home_goals':m.get('home_goals',m.get('hg')),'away_goals':m.get('away_goals',m.get('ag')),'date':day,'competition':m.get('competition'),'season':m.get('season'),'match_status':m.get('status') or ('Historical result' if m.get('classification')=='HISTORICAL_RESULT' or r['kind']=='SPORTS_RESULT' else 'Not supplied'),'observed_at':r.get('observed_at'),'collected_at':r['collected_at'],'odds':available,'evidence':r})
    results.sort(key=lambda r:(r['date'] or '',r['source'],r['id']),reverse=True)
    return {'rows':results[offset:offset+limit],'total':len(results),'offset':offset,'limit':limit,'read_at':now(),'datastore':data.get('datastore','SQLITE_OFFLINE'),'unlinked_quotes':unlinked+sum(1 for rows in quotes.values() for r in rows if r['id'] not in linked),'limitations':['Sources remain separate; similar team names are never automatically merged.','Quotations are linked by a source-owned match ID or a complete exact source/competition/season/teams/date identity.','Implied probability = 100 / decimal odds. It includes bookmaker margin and is not a calibrated prediction.','Unknown quote timestamps stay unknown. Stored quotations are not advertised as live or currently available prices.']}
