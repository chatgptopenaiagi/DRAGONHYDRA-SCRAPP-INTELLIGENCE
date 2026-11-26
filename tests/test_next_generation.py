"""Synthetic fixtures except for the pinned aggregate backtest artifact."""
import copy
from contextlib import closing
from datetime import date
from decimal import Decimal as D
from fractions import Fraction as F
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'application'),str(ROOT/'tools')]
from living.market_analysis import calculate_market
from living.football_contracts import match, quote
from living.football_research import research
from living.normalization import normalize
from living.storage import Store
from living.scoreboards import parse_scoreboard, source_for, saved_events
from living.connectors import local_ai
from living.contracts import Blocked
from backtest_seasons import evaluate


def scenario(fmt='decimal', prices=('2','3','4')):
    return {'market':'1X2','format':fmt,'prices':dict(zip(('home','draw','away'),prices))}


def fictional_scoreboard():
    return {'leagues':[{'slug':'nba','name':'Synthetic league'}], 'events':[{'id':'T0','competitions':[{
        'date':'2024-01-01T09:30:00-05:00','status':{'type':{'description':'Scheduled','state':'pre'}},
        'competitors':[{'homeAway':'home','team':{'id':'a','displayName':'Synthetic A'}},
                       {'homeAway':'away','team':{'id':'b','displayName':'Synthetic B'}}]}]}]}


class MathTests(unittest.TestCase):
    def test_equal_format_results(self):
        rows=calculate_market(scenario())['outcomes']
        for fmt,vals in [('american',('+100','+200','+300')),('fractional',('1/1','2/1','3/1'))]:
            self.assertEqual(rows, calculate_market(scenario(fmt,vals))['outcomes'])
        self.assertEqual(calculate_market(scenario('american',('-200','+100','+300')))['outcomes']['home']['decimal'],'1.5')

    def test_independent_rational_oracle(self):
        for prices in [('2','3','4'),('1.01','12.3','99'),('3.3','4.4','6.1')]:
            q=[1/F(p) for p in prices];total=sum(q);r=calculate_market(scenario(prices=prices))
            pairs=[(r['overround'],total-1),(r['theoretical_margin'],1-1/total)]
            for v,p in zip(r['outcomes'].values(),q):
                pairs.extend([(v['implied'],p),(v['normalized'],p/total),(v['fair_decimal'],total/p)])
            for actual,expected in pairs:self.assertLess(abs(F(actual)-expected),F(1,10**28))

    def test_two_way_and_ev(self):
        b={'market':'two-way','prices':{'first':'2','second':'2'}}
        self.assertIsNone(calculate_market(b)['expected_value'])
        for p,net in [('0','-1'),('0.6','0.2'),('1','1')]:
            b['assumption']={'outcome':'first','probability':p,'basis':'Synthetic sensitivity input'}
            self.assertEqual(D(calculate_market(b)['expected_value']['net_per_unit']),D(net))
        for key,val in [('basis',' '),('outcome','draw'),('probability','NaN'),('probability','-0.01'),('probability','1.1')]:
            with self.subTest(key=key,val=val),self.assertRaises(ValueError):
                calculate_market(b|{'assumption':b['assumption']|{key:val}})

    def test_missing_and_invalid(self):
        for fmt,val in [('decimal','Infinity'),('decimal','1'),('decimal',None),('decimal',True),('decimal','1e9999999'),
                        ('american','-99'),('american','100.5'),('fractional','1/0'),('fractional','0/1'),('decimal','suspended')]:
            with self.subTest(fmt=fmt,val=val),self.assertRaises(ValueError):calculate_market(scenario(fmt,(val,'2','3')))
        for body in [scenario()|{'prices':{'home':'2'}},scenario()|{'unknown':1}]:
            with self.assertRaises(ValueError):calculate_market(body)

    def test_frozen_chronology(self):
        cutoff=date(2021,4,28);train=[(date(2020,5,1),0)]
        for d in [cutoff,date(2019,1,1)]:
            with self.assertRaises(ValueError):evaluate(train,[(d,2)],cutoff)
        with self.assertRaises(ValueError):evaluate([(cutoff,2)],[(date(2022,1,1),0)],cutoff)
        a=evaluate(train,[(date(2022,1,1),0)],cutoff);b=evaluate(train,[(date(2022,1,1),2)],cutoff)
        self.assertEqual(a['prior'],b['prior']);self.assertAlmostEqual(a['uniform']['brier'],2/3)
        self.assertLess(a['frequency']['log_loss'],b['frequency']['log_loss'])

    def test_no_inference_dependency(self):
        with self.assertRaises(Blocked):local_ai({},scenario())
        with patch('http.client.HTTPConnection.request',side_effect=ConnectionRefusedError),self.assertRaises(Blocked):
            local_ai({'enabled':True,'endpoint':'http://127.0.0.1:8765/v1/chat/completions'},scenario())


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'test.sqlite3';self.store=Store(self.path);self.addCleanup(self.store.close)
        self.source={'id':'fictional','kind':'NUMBER','unit':'unknown'}

    def insert(self,rows,receipt='test',source=None,origin='SYNTHETIC',extra=None):
        src=source or self.source
        obs=[normalize(r,src,origin) for r in rows]
        self.store.ingest(obs,{'id':receipt,'source_id':src['id'],**(extra or {})})
        return obs

    def test_provider_identity_and_search_quality(self):
        a=match('1','Alpha','Beta','2020-01-01','FINAL',(1,0),{},'C','S')
        b=match('2','Gamma','Delta','2020-01-02','FINAL',(2,0),{},'C','S')
        q=quote('1','TestBook','1X2','H','2',{})
        self.insert([a,b,q,quote('2','TestBook','1X2','A','3',{})])
        r=research(self.store,{'search':' ALPHA '});self.assertEqual(r['unlinked_quotes'],0)
        self.assertEqual(r['rows'][0]['odds'][0]['id'],normalize(q,self.source,'SYNTHETIC')['id'])
        self.insert([q],'other-origin',origin='IMPORTED')
        self.insert([q],'other-source',{'id':'another'})
        self.insert([quote('1','Other','1X2','H','2',{},competition='X')],'conflict')
        self.assertEqual(research(self.store,{})['unlinked_quotes'],3)
        self.insert([match('1','Different','Beta','2020-01-01','FINAL',(1,0),{},'C','S')],'reused')
        self.assertFalse(research(self.store,{'search':'Alpha'})['rows'][0]['odds'])

    def test_fallback_names_and_doubleheader(self):
        base={'competition':'CZ','season':'2025','date':'2025-10-10','home':'Ａlpha  Team','away':'Beta'}
        a={'kind':'SPORTS_RESULT','key':'score','metadata':base}
        q={'kind':'SPORTS_ODDS','key':'odds','value':'3','unit':'decimal_odds','metadata':base|{'home':'alpha team','outcome':'H','market':'1X2','bookmaker':'B'}}
        self.insert([a,q]);self.assertEqual(len(research(self.store,{})['rows'][0]['odds']),1)
        self.insert([a|{'metadata':base|{'scheduled_at':'2025-10-10T21:00:00Z'}}],'second')
        r=research(self.store,{});self.assertEqual(r['ambiguous_match_keys'],1);self.assertEqual(r['unlinked_quotes'],1)

    def test_timeline_conflicts_suspension_and_dispersion(self):
        a=match('1','A','B','2024-01-01','FINAL',(2,2),{})
        def q(n,t,book='X',**kw):
            return quote('1',book,'1X2','H',str(n),{},t,period='90min',settlement='regulation',**kw)
        times=[f'2024-01-01T0{n}:00:00Z' for n in range(5)]
        rows=[a,q(2,times[0],phase='opening'),q(4,times[1]),q(3,times[1]),q(2,times[2],suspended=True),
              q(2,times[3]),q(3,times[4],phase='closing'),q(4,None),q(3,times[0],book='Y')]
        self.insert(rows);h=research(self.store,{})['rows'][0]['history'];s=h['series'][0]
        self.assertEqual(h['excluded_time_or_identity'],1);self.assertEqual([p['decimal'] for p in s['points']],['2',None,None,'2','3'])
        self.assertEqual(s['reported_closing'][0]['decimal'],'3');self.assertEqual(len(s['reported_opening']),1)
        self.assertEqual(h['comparisons'][0]['decimal_range'],'1');self.assertEqual(len(h['comparisons'][0]['ids']),2)
        self.assertIsNone(s['log_change_sd'])
        self.assertEqual(self.store.query({},1)['total'],len(rows))

    def test_scoreboard_archive_membership_and_replay(self):
        doc=fictional_scoreboard();src=source_for('nba','2024-01-01');raw=parse_scoreboard(doc,'nba')
        def capture(data,i):
            records=[normalize(row,src,'COLLECTED') for row in data]
            self.store.ingest(records,{'id':str(i),'source_id':src['id'],'scoreboard_ids':[r['id'] for r in records],
                                      'acquired_at':f'2024-01-0{i}T10:00:00Z','content_hash':str(i)})
            return saved_events(self.store,{'league':'nba','day':'2024-01-01'})
        event=capture(raw,1)['events'][0]
        self.assertIsNone(event['source_timestamp']);self.assertEqual(event['scheduled_at'],'2024-01-01T14:30:00Z')
        correction=copy.deepcopy(doc);correction['events'][0]['competitions'][0]['status']['type']['description']='Postponed'
        self.assertEqual(capture(parse_scoreboard(correction,'nba'),2)['events'][0]['status'],'Postponed')
        r=capture(raw,3);self.assertEqual(r['stored_observations'],2);self.assertEqual(r['events'][0]['status'],'Scheduled')
        r=capture([],4);self.assertEqual(r['events'][0]['snapshot_presence'],'ABSENT')

    def test_reject_wrong_sport_or_unidentified_event(self):
        d=fictional_scoreboard()
        with self.assertRaises(ValueError):parse_scoreboard(d,'nhl')
        d['events']*=2
        with self.assertRaises(ValueError):parse_scoreboard(d,'nba')
        for bad in ['2024-02-31','not-a-day']:
            with self.assertRaises(ValueError):source_for('nba',bad)

    def test_index_recovery(self):
        self.insert([match('a','A','B','2024-01-01','FINAL',(1,0),{})])
        self.store.c.execute('DROP INDEX observation_display_time');self.store.c.commit()
        upgraded=Store(self.path);self.addCleanup(upgraded.close)
        backup,=self.path.parent.glob('*.before-display-index-*')
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('SELECT count(*) FROM observations').fetchone()[0],1)
            self.assertFalse(db.execute("SELECT 1 FROM sqlite_master WHERE name='observation_display_time'").fetchone())
        plan=upgraded.c.execute("EXPLAIN QUERY PLAN SELECT payload FROM observations ORDER BY COALESCE(observed_at,json_extract(payload,'$.metadata.date'),collected_at),id LIMIT 25").fetchall()
        self.assertIn('observation_display_time',str([tuple(row) for row in plan]))
