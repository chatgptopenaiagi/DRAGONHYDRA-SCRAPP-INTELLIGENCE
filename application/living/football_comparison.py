"""Conservative comparisons. No automatic merging or modification of observations."""
import unicodedata
from .contracts import now,fingerprint
def label(value):return unicodedata.normalize('NFKC',str(value or '')).strip().casefold()
def save_alias(store,body):
    scope=body.get('scope');source=body.get('source');original=body.get('original');canonical=body.get('canonical')
    if scope not in ('team','competition','season') or not all(isinstance(v,str) and 0<len(v)<=200 for v in (source,original,canonical)):raise ValueError('Select a scope, source and explicit original/canonical names')
    value={'scope':scope,'source':source,'original':original,'canonical':canonical,'at':now(),'basis':'OWNER_CONFIRMED_ALIAS'};store.state('football-alias',fingerprint([scope,source,label(original)]),value);return value
def compare(store,filters):
    query={k:filters[k] for k in ('source','search','origin') if filters.get(k)};data=store.query(query,10000)
    if data['total']>10000:raise ValueError('Narrow the comparison to at most 10000 records')
    aliases={(a['scope'],a['source'],label(a['original'])):label(a['canonical']) for a in store.states('football-alias')};groups={};other=[]
    legacy_matches={(r['source_id'],r['metadata']['id']):r['metadata'] for r in data['rows'] if r.get('metadata',{}).get('classification')=='HISTORICAL_RESULT' and 'id' in r['metadata']}
    for r in data['rows']:
        m=dict(r.get('metadata',{}))
        if m.get('classification')=='HISTORICAL_RESULT':
            m.update(contract='football.result/1',home_team=m.get('home'),away_team=m.get('away'),home_goals=m.get('hg'),away_goals=m.get('ag'),score_period='REGULATION',status='FINAL',projection='READ_ONLY_LEGACY_ADAPTER')
        elif m.get('classification')=='HISTORICAL_PRICE':
            linked=legacy_matches.get((r['source_id'],m.get('match_id')),{});m.update(contract='football.odds.quote/1',home_team=linked.get('home'),away_team=linked.get('away'),competition=linked.get('competition'),season=linked.get('season'),date=linked.get('date'),projection='READ_ONLY_LEGACY_ADAPTER')
        if m.get('score_period') in ('After90Minutes','REGULAR'):m['score_period']='REGULATION'
        contract=m.get('contract','')
        if not contract.startswith('football.'):continue
        if filters.get('category') and contract!='football.'+filters['category']+'/1':continue
        if filters.get('competition') and label(filters['competition']) not in label(m.get('competition')):continue
        if filters.get('season') and label(filters['season'])!=label(m.get('season')):continue
        if filters.get('team') and label(filters['team']) not in label(str(m.get('home_team',''))+' '+str(m.get('away_team',''))+' '+str(m.get('team',''))):continue
        day=m.get('date') or (m.get('scheduled_at') or '')[:10]
        if filters.get('from') and (not day or day<filters['from']):continue
        if filters.get('to') and (not day or day>filters['to']):continue
        item={'id':r['id'],'source':r['source_id'],'origin':r['origin'],'contract':contract,'metadata':{k:v for k,v in m.items() if k not in ('original_provider_record','original_csv_row')},'value':r['value'],'observed_at':r['observed_at'],'retrieved_at':r['collected_at'],'limitations':r['quality']['warnings']}
        if not m.get('home_team') or not m.get('away_team') or not m.get('competition') or not m.get('season') or not day:
            other.append(item|{'comparison_status':'INSUFFICIENT_IDENTITY'});continue
        def canon(scope,value):return aliases.get((scope,r['source_id'],label(value)),label(value))
        key=(canon('competition',m['competition']),canon('season',m['season']),canon('team',m['home_team']),canon('team',m['away_team']),day,contract,m.get('score_period'),m.get('bookmaker'),m.get('market'),m.get('outcome'))
        groups.setdefault(key,[]).append(item)
    results=[]
    for key,records in groups.items():
        sources={r['source'] for r in records};scores={(r['metadata'].get('home_goals'),r['metadata'].get('away_goals'),r['value']) for r in records};state='SINGLE_SOURCE' if len(sources)<2 else 'AGREEMENT_CANDIDATE' if len(scores)==1 else 'CONFLICT_REQUIRES_REVIEW'
        results.append({'identity_evidence':list(key),'status':state,'records':records,'limitation':'Exact or explicitly mapped names and date are candidate identity evidence. Upstream lineage may be shared; agreement does not prove truth. No originals are merged.'})
    return {'groups':results,'unmatched':other,'aliases':store.states('football-alias'),'method':'football.compare/1','checked_at':now(),'record_count':sum(len(g['records']) for g in results)+len(other)}
