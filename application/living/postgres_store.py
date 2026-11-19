"""Transactional PostgreSQL observations; no silent fallback to SQLite."""
import hashlib,json,re,uuid
from decimal import Decimal
from datetime import date
from .contracts import encode,now,fingerprint,Cancelled

def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
def calendar(value):
    if not value:return None
    try:return date.fromisoformat(str(value)) if re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(value)) else None
    except ValueError:return None
def timestamp(value):
    if not value:return None
    if not isinstance(value,str) or not re.search(r'T\d\d:\d\d.*(?:Z|[+-]\d\d:\d\d)$',value):raise ValueError('Timestamp must carry explicit time and timezone; date-only values stay DATE or original metadata')
    return value

class PostgresStore:
    def __init__(self,control):self.control=control
    def relation(self,name):return self.control.relation(name)
    def insert(self,c,rows,receipt,sources,cancel=lambda:False,originals=None,snapshot='acquisition'):
        from psycopg.types.json import Jsonb
        t=self.relation;inserted=duplicates=0
        for source in sources:c.execute('INSERT INTO '+t('providers')+' VALUES(%s,%s) ON CONFLICT(id) DO NOTHING',(source['id'],Jsonb(source)))
        for r in rows:
            if cancel():raise Cancelled('Cancelled before PostgreSQL commit; batch rolled back')
            raw_text=(originals or {}).get(r['id'],encode(r));h=digest(raw_text);prior=c.execute('SELECT payload_sha256 FROM '+t('observations')+' WHERE id=%s',(r['id'],)).fetchone()
            if prior:
                if prior[0]!=h:
                    old=json.loads(c.execute('SELECT payload_text FROM '+t('observations')+' WHERE id=%s',(r['id'],)).fetchone()[0])
                    # Reacquisition has a new collection time, but must not rewrite the first immutable record.
                    if originals is not None or any(old.get(k)!=r.get(k) for k in ('source_id','raw_hash','kind','origin','key','value','unit','identity','observed_at')):raise ValueError('Existing observation identity has different original content; no records overwritten')
                duplicates+=1
            else:
                c.execute('INSERT INTO '+t('providers')+' VALUES(%s,%s) ON CONFLICT DO NOTHING',(r['source_id'],Jsonb({'id':r['source_id'],'name':r['source_id'],'metadata_status':'SOURCE_METADATA_NOT_SUPPLIED'})))
                c.execute('INSERT INTO '+t('raw_evidence')+'(hash,original_json) VALUES(%s,%s) ON CONFLICT DO NOTHING',(r['raw_hash'],encode(r.get('raw',{}))))
                m=r.get('metadata',{});day=calendar(m.get('date'));value=Decimal(str(r['value'])) if r.get('value') is not None else None
                c.execute('INSERT INTO '+t('observations')+' VALUES('+','.join(['%s']*17)+')',(r['id'],r['source_id'],r['key'],r['kind'],r['origin'],r['unit'],timestamp(r.get('observed_at')),timestamp(r['collected_at']),day,timestamp(r.get('issue_at')),timestamp(r.get('valid_at')),value,r['identity'],r['raw_hash'],Jsonb(r),raw_text,h));self.sports(c,r,day,value);inserted+=1
            c.execute('INSERT INTO '+t('data_lineage')+' VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(r['id'],snapshot,r['id'],h))
        result=receipt|{'inserted':inserted,'duplicates':duplicates,'conflicts':0,'committed_at':now(),'datastore':'POSTGRESQL'}
        c.execute('INSERT INTO '+t('import_receipts')+' VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(result['id'],Jsonb(result),encode(result)));return result
    def sports(self,c,r,day,value):
        from psycopg.types.json import Jsonb
        t=self.relation;m=r.get('metadata',{});source=r['source_id'];legacy=m.get('legacy_original',{}).get('metadata',{});meta=legacy or m;contract=m.get('contract','')
        def dimension(table,identity,name=None):
            if identity is None or str(identity)=='':return None
            key=fingerprint([source,str(identity)]);cols='id,provider_id,label' if table=='seasons' else 'id,provider_id,name' if table in ('bookmakers','odds_markets') else 'id,provider_id,source_identity,name'
            vals=(key,source,str(identity)) if table in ('seasons','bookmakers','odds_markets') else (key,source,str(identity),None if name is None else str(name))
            c.execute('INSERT INTO '+t(table)+'('+cols+') VALUES('+','.join(['%s']*len(vals))+') ON CONFLICT DO NOTHING',vals);return key
        comp=dimension('competitions',meta.get('competition'),meta.get('competition_name',meta.get('competition')));season=dimension('seasons',meta.get('season'))
        if contract=='football.competition/1':dimension('competitions',meta.get('provider_record_id',meta.get('competition')),meta.get('name'))
        if contract=='football.team/1':dimension('teams',meta.get('provider_record_id',meta.get('team_id',meta.get('name'))),meta.get('name'))
        is_result=r['kind']=='SPORTS_RESULT';is_odds=r['kind']=='SPORTS_ODDS';event_id=meta.get('match_id') if is_odds else meta.get('provider_match_id') or meta.get('fixture_id') or meta.get('id') or (r['identity'] if is_result or contract in ('football.fixture/1','football.result/1') else None)
        fixture=None
        if event_id:
            fixture=fingerprint([source,str(event_id)]);home=meta.get('home_team',meta.get('home'));away=meta.get('away_team',meta.get('away'));home_id=dimension('teams',meta.get('home_id') or home,home);away_id=dimension('teams',meta.get('away_id') or away,away)
            c.execute('INSERT INTO '+t('fixtures')+' VALUES('+','.join(['%s']*10)+') ON CONFLICT(id) DO UPDATE SET competition_id=COALESCE(EXCLUDED.competition_id,fixtures.competition_id),season_id=COALESCE(EXCLUDED.season_id,fixtures.season_id),home_team_id=COALESCE(EXCLUDED.home_team_id,fixtures.home_team_id),away_team_id=COALESCE(EXCLUDED.away_team_id,fixtures.away_team_id),event_date=COALESCE(EXCLUDED.event_date,fixtures.event_date),scheduled_at=COALESCE(EXCLUDED.scheduled_at,fixtures.scheduled_at),status=COALESCE(EXCLUDED.status,fixtures.status)',(fixture,source,str(event_id),comp,season,home_id,away_id,day,timestamp(meta.get('scheduled_at')),meta.get('status')))
        if is_result:
            def goal(v):return v if type(v) is int else int(v) if isinstance(v,str) and v.isdecimal() else None
            c.execute('INSERT INTO '+t('match_results')+' VALUES(%s,%s,%s,%s,%s)',(r['id'],fixture,goal(meta.get('home_goals',meta.get('hg'))),goal(meta.get('away_goals',meta.get('ag'))),r['origin']))
        if is_odds:
            book=dimension('bookmakers',meta.get('bookmaker'));market=meta.get('market');market=market.get('type') if isinstance(market,dict) else market;market_id=dimension('odds_markets',market)
            c.execute('INSERT INTO '+t('odds_quotes')+' VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(r['id'],fixture,book,market_id,meta.get('outcome'),value,timestamp(meta.get('quote_time')),r['origin']+' / '+str(meta.get('classification','RECORDED_PRICE_TIME_NOT_INFERRED'))))
    def ingest(self,rows,receipt,cancel=lambda:False):
        from psycopg.types.json import Jsonb
        with self.control.connect('runtime',False) as c:
            self.control.owned(c);c.execute('SELECT pg_advisory_xact_lock(%s)',(self.control.lock_id(),));old=c.execute('SELECT payload FROM '+self.relation('import_receipts')+' WHERE id=%s',(receipt['id'],)).fetchone()
            if old:return old[0]
            result=self.insert(c,rows,receipt,self.control.local.sources(),cancel)
            c.execute('INSERT INTO '+self.relation('acquisition_tasks')+' VALUES(%s,%s,%s) ON CONFLICT(id) DO UPDATE SET state=EXCLUDED.state,payload=EXCLUDED.payload',(receipt['id'],'COMPLETE',Jsonb(result)));return result
    def query(self,filters=None,limit=100,offset=0):
        filters=filters or {};limit=int(limit);offset=int(offset)
        if not 1<=limit<=10000 or not 0<=offset<=1000000:raise ValueError('Invalid query bounds')
        clauses=[];params=[]
        for key,col in [('source','source'),('kind','kind'),('origin','origin'),('series','series')]:
            if filters.get(key):clauses.append(col+'=%s');params.append(filters[key])
        if filters.get('search'):clauses.append("payload_text ILIKE %s ESCAPE '~'");params.append('%'+str(filters['search'])[:120].replace('~','~~').replace('%','~%').replace('_','~_')+'%')
        for key,op in [('start','>='),('end','<=')]:
            if filters.get(key):clauses.append('collected_at'+op+'%s');params.append(timestamp(filters[key]))
        where=' WHERE '+' AND '.join(clauses) if clauses else ''
        with self.control.connect('readonly',True) as c:
            total=c.execute('SELECT COUNT(*) FROM '+self.relation('observations')+where,params).fetchone()[0];rows=[json.loads(r[0]) for r in c.execute('SELECT payload_text FROM '+self.relation('observations')+where+" ORDER BY COALESCE(payload->>'observed_at',payload->'metadata'->>'date',payload->>'collected_at'),id LIMIT %s OFFSET %s",params+[limit,offset])]
        return {'total':total,'rows':rows,'limit':limit,'offset':offset,'datastore':'POSTGRESQL'}
    def summary(self):
        with self.control.connect('readonly',True) as c:
            count=c.execute('SELECT COUNT(*) FROM '+self.relation('observations')).fetchone()[0];origins=dict(c.execute('SELECT origin,COUNT(*) FROM '+self.relation('observations')+' GROUP BY origin'));series=[dict(zip(('source','series','unit','origin','n'),r)) for r in c.execute('SELECT source,series,unit,origin,COUNT(*) FROM '+self.relation('observations')+' GROUP BY source,series,unit,origin')];receipts=[r[0] for r in c.execute('SELECT payload FROM '+self.relation('import_receipts')+' ORDER BY payload->>\'committed_at\' DESC NULLS LAST LIMIT 30')]
        return {'observations':count,'provenance':origins,'series':series,'receipts':receipts,'integrity':'ok','integrity_ms':None,'schema':'PostgreSQL 1','datastore':'POSTGRESQL'}
    def receipt(self,id):
        with self.control.connect('readonly',True) as c:r=c.execute('SELECT payload FROM '+self.relation('import_receipts')+' WHERE id=%s',(id,)).fetchone();return r[0] if r else None
    def analyses(self):
        with self.control.connect('readonly',True) as c:return [r[0] for r in c.execute('SELECT payload FROM '+self.relation('analysis_results')+" ORDER BY payload->>'calculated_at' DESC NULLS LAST,id LIMIT 50")]
    def save_analysis(self,value):
        from psycopg.types.json import Jsonb
        with self.control.connect('runtime',False) as c:self.control.owned(c);c.execute('INSERT INTO '+self.relation('analysis_results')+' VALUES(%s,%s) ON CONFLICT DO NOTHING',(value['id'],Jsonb(value)))
    def observations_by_ids(self,ids):
        with self.control.connect('readonly',True) as c:return [json.loads(r[0]) for r in c.execute('SELECT payload_text FROM '+self.relation('observations')+' WHERE id=ANY(%s)',(list(ids),))]
    def competitions(self,a):
        with self.control.connect('readonly',True) as c:
            return [dict(zip(('source','competition','season'),r)) for r in c.execute('SELECT DISTINCT source,payload->\'metadata\'->>\'competition\',payload->\'metadata\'->>\'season\' FROM '+self.relation('observations')+" WHERE payload->'metadata'->>'competition' IS NOT NULL AND (%s='' OR source=%s) AND (%s='' OR position(lower(%s) in lower(payload_text))>0) ORDER BY 1,2,3 LIMIT %s",(a.get('source',''),a.get('source',''),a.get('search',''),a.get('search',''),a.get('limit',20)))]
