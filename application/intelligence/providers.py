import json,http.client
from decimal import Decimal
from datetime import datetime,timezone
from urllib.parse import urlencode
from .model import normalize,stamp,now
from .odds_contract import normalize_record
from .acquisition import SchemaMismatch,SourceClient

def parse_open_meteo(body,received_at,source_url):
    data=json.loads(body,parse_float=str)
    if data.get('utc_offset_seconds')!=0:raise SchemaMismatch('Weather provider must return UTC')
    hourly=data.get('hourly',{});units=data.get('hourly_units',{});times=hourly.get('time',[])
    fields={'temperature_2m':('°C','degC'),'wind_speed_10m':('m/s','m/s'),'precipitation_probability':('%','%')}
    if not times or len(times)>400:raise SchemaMismatch('Missing or oversized weather timeline')
    rows=[]
    for field,(provider_unit,unit) in fields.items():
        values=hourly.get(field)
        if units.get(field)!=provider_unit or not isinstance(values,list) or len(values)!=len(times):raise SchemaMismatch('Weather field/unit/timeline changed')
        for valid,value in zip(times,values):
            if value is None:continue  # Missing forecasts remain missing; never fabricate.
            valid=stamp(valid+'Z' if len(valid)==16 else valid)
            if valid<stamp(received_at):continue
            rows.append(normalize(dict(source_id='open-meteo',source_url=source_url,key=field,kind='WEATHER_FORECAST',value=str(value),unit=unit,valid_at=valid,issue_at=None,metadata={'model':'Open-Meteo best_match forecast models','issue_time_status':'not supplied by this endpoint','latitude':data.get('latitude'),'longitude':data.get('longitude'),'physical_measurement':False}),origin='observed',received_at=received_at))
    if not rows:raise SchemaMismatch('No current/future forecasts in response')
    return rows

def weather_url(latitude,longitude):
    lat=Decimal(str(latitude));lon=Decimal(str(longitude))
    if not lat.is_finite() or not lon.is_finite() or not -90<=lat<=90 or not -180<=lon<=180:raise ValueError('Invalid confirmed coordinates')
    return 'https://api.open-meteo.com/v1/forecast?'+urlencode(dict(latitude=str(lat),longitude=str(lon),hourly='temperature_2m,wind_speed_10m,precipitation_probability',wind_speed_unit='ms',timezone='UTC',forecast_days=1))

def mirror_records(payload,received_at=None):
    if not isinstance(payload,dict) or payload.get('schema')!='mirror.import/1' or not isinstance(payload.get('records'),list):raise SchemaMismatch('Unsupported ODDS MIRROR exchange schema')
    if len(payload['records'])>1000:raise SchemaMismatch('Mirror batch too large')
    rows=[]
    for raw in payload['records']:
        record=normalize_record(raw)
        origin='synthetic' if record['origin']=='synthetic' else 'imported'
        receipt=record['received_at'] if origin=='synthetic' else received_at or now()
        for outcome,quote in record['quotes'].items():
            if not quote['available']:continue
            meta=dict(event=record['event'],market=record['market'],market_id=record['market']['id'],bookmaker=record['bookmaker'],outcome=outcome,provider=record['provider'],source_event_id=record['source_event_id'],commission=record['commission'],original_origin=record['origin'])
            rows.append(normalize(dict(source_id='mirror:'+record['provider'],source_url='http://127.0.0.1/odds-mirror',key=record['market']['id']+':'+record['bookmaker_id'][:12]+':'+outcome,kind='SPORTS_ODDS',value=quote['odds'],unit='decimal_odds',observed_at=record['observed_at'],metadata=meta),origin=origin,received_at=receipt))
    return rows

def read_mirror(port,market,cutoff=None):
    if not isinstance(port,int) or not 1024<=port<=65535:raise ValueError('Invalid configured mirror port')
    params={'market':market}
    if cutoff:params['at']=stamp(cutoff)
    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
    try:
        connection.request('GET','/api/export.json?'+urlencode(params));response=connection.getresponse()
        if response.status!=200:raise SchemaMismatch('ODDS MIRROR API unavailable: '+str(response.status))
        body=response.read(2_000_001)
        if len(body)>2_000_000:raise SchemaMismatch('Mirror response too large')
        return mirror_records(json.loads(body))
    finally:connection.close()
