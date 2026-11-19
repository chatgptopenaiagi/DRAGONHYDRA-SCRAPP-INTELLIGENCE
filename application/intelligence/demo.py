"""Fictional deterministic observations, never presented as collected live data."""
from datetime import datetime,timedelta,timezone
from .model import normalize,stamp
from .providers import mirror_records
BASE=datetime(2026,1,10,12,tzinfo=timezone.utc)
TIMES=[stamp(BASE+timedelta(minutes=5*i)) for i in range(6)]

def fixtures():
    rows=[]
    for i,at in enumerate(TIMES):
        examples=[dict(source_id='demo-numerical',key='training_attendance',kind='NUMBER',value=str(120+i*3),unit='people',observed_at=at),
         dict(source_id='demo-weather-station',key='temperature',kind='WEATHER_OBSERVATION',value=str(12+i),unit='degC',observed_at=at,metadata={'latitude':'52.52','longitude':'13.405','location':'Fictional test venue'}),
         dict(source_id='demo-weather-model',key='wind_forecast',kind='WEATHER_FORECAST',value=str(4+i),unit='m/s',issue_at=at,valid_at='2026-01-10T15:00:00Z',metadata={'model':'fictional-model-v1','latitude':'52.52','longitude':'13.405'}),
         dict(source_id='demo-weather-model',key='rain_probability',kind='WEATHER_FORECAST',value=str(20+i*5),unit='%',issue_at=at,valid_at='2026-01-10T15:00:00Z',metadata={'model':'fictional-model-v1'}),
         dict(source_id='demo-public-text',key='statement-'+str(i),kind='SHORT_TEXT',text=['The training was excellent.','The weather is bad but the team is good.','Echipa este bună.','Das Training ist gut.','Maybe this is great.','The match starts at three.'][i],published_at=at,metadata={'language':['en','en','ro','de','en','en'][i],'topic':'fictional football','confirmed_entities':['Fictional Falcons']})]
        rows.extend(normalize(r,origin='synthetic',received_at=at) for r in examples)
        snapshots=[]
        for j,book in enumerate(('Demo North','Demo South','Demo West')):
            snapshots.append(dict(event={'sport':'football','competition':'Fictional Research League','home':'Fictional Falcons','away':'Fictional Owls','kickoff':'2026-01-10T15:00:00Z'},provider='demo mirror',source_event_id='demo-001',bookmaker=book,origin='synthetic',observed_at=at,received_at=at,commission='0',market={'type':'1x2','period':'full_time','settlement':'football.regulation.90min.v1','status':'prematch','line':None},quotes={name:{'odds':str(value),'format':'decimal','available':True} for name,value in [('home',round(2.1+j*.05+i*.01,2)),('draw',round(3.3+j*.1,2)),('away',round(3.4-j*.05,2))]}))
        rows.extend(mirror_records({'schema':'mirror.import/1','records':snapshots}))
    return rows
