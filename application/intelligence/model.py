"""Exact values and independently meaningful clocks. External labels are untrusted."""
import json,re,unicodedata
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo
from dragonhydra.domain import identity,now

KINDS={'NUMBER','PERCENTAGE','SPORTS_ODDS','PRICE','DATE','TIME','DURATION','WEATHER_OBSERVATION','WEATHER_FORECAST','HISTORICAL_MODEL_DATA','STATISTICAL_RESULT','SHORT_TEXT','SENTIMENT_SIGNAL','UNKNOWN'}
NUMERIC={'NUMBER','PERCENTAGE','SPORTS_ODDS','PRICE','DURATION','WEATHER_OBSERVATION','WEATHER_FORECAST','HISTORICAL_MODEL_DATA','STATISTICAL_RESULT'}
ORIGINS={'synthetic','imported','observed'}

def stamp(value,zone=None):
    try: dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except (ValueError,TypeError):raise ValueError('Timestamp must be ISO 8601') from None
    if dt.tzinfo is None:
        if not zone:raise ValueError('Timestamp requires an explicit offset')
        tz=ZoneInfo(zone); a=dt.replace(tzinfo=tz,fold=0); b=dt.replace(tzinfo=tz,fold=1)
        if a.utcoffset()!=b.utcoffset():raise ValueError('Ambiguous or nonexistent local time; supply an offset')
        if a.astimezone(timezone.utc).astimezone(tz).replace(tzinfo=None)!=dt:raise ValueError('Nonexistent local time')
        dt=a
    return dt.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

def decimal_value(value,decimal_mark='.',group_mark=None):
    if isinstance(value,(bool,float)) or value is None:raise ValueError('Exact numbers require a string, integer or Decimal')
    if decimal_mark not in ('.',',') or group_mark==decimal_mark:raise ValueError('Invalid declared number format')
    text=str(value).strip()
    if len(text)>80:raise ValueError('Number too long')
    if group_mark:
        if group_mark not in ('.',',',' ','\u00a0'):raise ValueError('Unsupported grouping mark')
        pattern=r'[+-]?(?:\d{1,3}(?:'+re.escape(group_mark)+r'\d{3})+|\d+)(?:'+re.escape(decimal_mark)+r'\d+)?'
        if not re.fullmatch(pattern,text):raise ValueError('Inconsistent number grouping')
        text=text.replace(group_mark,'')
    elif not re.fullmatch(r'[+-]?\d+(?:'+re.escape(decimal_mark)+r'\d+)?',text):raise ValueError('Number does not match declared locale')
    try:n=Decimal(text.replace(decimal_mark,'.'))
    except InvalidOperation:raise ValueError('Invalid decimal') from None
    if not n.is_finite() or abs(n)>=Decimal('1e18') or n.as_tuple().exponent < -10:raise ValueError('Value exceeds decimal(28,10) precision')
    return n

def label(value,maxlen=180):
    if not isinstance(value,str) or not value.strip() or len(value)>maxlen or any(ord(c)<32 and c not in '\n\t' for c in value):raise ValueError('Invalid text field')
    return unicodedata.normalize('NFC',value).strip()

def normalize(raw,*,origin,received_at=None):
    if origin not in ORIGINS:raise ValueError('Origin is assigned by a trusted ingestion path')
    if not isinstance(raw,dict):raise ValueError('Observation must be an object')
    source=label(raw.get('source_id'),100); key=label(raw.get('key'),160); kind=raw.get('kind')
    if kind not in KINDS:raise ValueError('Explicit supported data kind required; numbers are never inferred to be odds')
    receipt=stamp(received_at or now())
    clocks={k:stamp(raw[k]) if raw.get(k) else None for k in ('observed_at','published_at','issue_at','valid_at')}
    if clocks['published_at'] and clocks['published_at']>receipt:raise ValueError('Publication is after receipt')
    if clocks['issue_at'] and clocks['issue_at']>receipt:raise ValueError('Forecast issue is after receipt')
    if kind=='WEATHER_FORECAST':
        if not clocks['valid_at']:raise ValueError('Forecast requires valid time')
        if clocks['issue_at'] and clocks['valid_at']<clocks['issue_at']:raise ValueError('Forecast valid time precedes issue')
    elif clocks['issue_at']:raise ValueError('Issue time applies only to forecasts')
    if kind not in ('WEATHER_FORECAST','HISTORICAL_MODEL_DATA') and clocks['observed_at'] and clocks['observed_at']>receipt:raise ValueError('Observed time cannot be in the future')
    if kind=='WEATHER_OBSERVATION' and not clocks['observed_at']:raise ValueError('Measurement requires observed time')
    if kind=='HISTORICAL_MODEL_DATA' and not clocks['valid_at']:raise ValueError('Model data requires valid time')
    value=None;unit=raw.get('unit');original=raw.get('value')
    if kind in NUMERIC:
        value=str(decimal_value(original,raw.get('decimal_mark','.'),raw.get('group_mark')))
        unit=label(unit,32)
        if kind=='PERCENTAGE' and not 0<=Decimal(value)<=100:raise ValueError('Percentage outside 0..100 points')
        if kind=='SPORTS_ODDS':
            if Decimal(value)<=1 or unit!='decimal_odds' or not raw.get('metadata',{}).get('market_id'):raise ValueError('Odds require explicit market identity and decimal price > 1')
        if kind.startswith('WEATHER') or kind=='HISTORICAL_MODEL_DATA':
            ranges={'degC':(-100,70),'m/s':(0,150),'%':(0,100),'hPa':(100,1200),'mm':(0,5000),'deg':(0,360)}
            if unit not in ranges or not Decimal(ranges[unit][0])<=Decimal(value)<=Decimal(ranges[unit][1]):raise ValueError('Unsupported weather unit or implausible value')
    text=label(raw['text'],4000) if raw.get('text') is not None else None
    if kind in ('SHORT_TEXT','SENTIMENT_SIGNAL') and text is None:raise ValueError('Text observation requires text')
    metadata=raw.get('metadata',{})
    if not isinstance(metadata,dict) or len(json.dumps(metadata,ensure_ascii=False))>16000:raise ValueError('Metadata must be a bounded object')
    source_url=label(raw.get('source_url','fixture://'+source),2000)
    if origin=='observed' and not source_url.startswith(('https://','http://')):raise ValueError('Observed records require an actual source address')
    canonical=dict(source_id=source,key=key,kind=kind,value=value,unit=unit,text=text,origin=origin,received_at=receipt,source_url=source_url,metadata=metadata,**clocks)
    raw_json=json.dumps(raw,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    canonical['raw_json']=raw_json;canonical['raw_hash']=identity('raw',raw_json)
    # New source revisions/time slices survive. Exact retries of the same receipt are idempotent.
    canonical['id']=identity('observation',source,key,origin,receipt,canonical['raw_hash'])
    canonical['verification']='synthetic' if origin=='synthetic' else 'imported_unverified' if origin=='imported' else 'schema_validated_observation'
    canonical['original_value']=None if original is None else str(original)
    canonical['engine_version']='scrapp-contract/1'
    return canonical

def available_at(row,cutoff):
    at=stamp(cutoff)
    return all(not row.get(k) or row[k]<=at for k in ('received_at','published_at','issue_at'))

def freshness(row,cutoff,ttl=600):
    if not available_at(row,cutoff):return 'NOT_YET_AVAILABLE'
    basis=row.get('observed_at') or row.get('published_at') or row['received_at']
    age=(datetime.fromisoformat(stamp(cutoff).replace('Z','+00:00'))-datetime.fromisoformat(basis.replace('Z','+00:00'))).total_seconds()
    return 'STALE' if age>ttl else 'FRESH'
