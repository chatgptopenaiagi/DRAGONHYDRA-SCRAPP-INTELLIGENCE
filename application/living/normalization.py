"""DH-NORMALIZATION/DH-WEATHER: preserve unknown clocks and raw records."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from .contracts import encode,fingerprint,now

ORIGINS={'SYNTHETIC','IMPORTED','COLLECTED','INFERRED'}
KINDS={'NUMBER','PRICE','PERCENTAGE','SHORT_TEXT','SPORTS_RESULT','SPORTS_ODDS','WEATHER_OBSERVATION','WEATHER_FORECAST','STATISTICAL_RESULT'}
def timestamp(value):
    if value in (None,''): return None
    dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('Timestamp must include an explicit UTC offset; dates belong in metadata')
    return dt.astimezone(timezone.utc).isoformat().replace('+00:00','Z')
def number(value):
    if value in (None,''): return None
    if isinstance(value,bool): raise ValueError('Boolean is not a measurement')
    try: result=Decimal(str(value))
    except InvalidOperation: raise ValueError('Invalid decimal') from None
    if not result.is_finite() or abs(result)>Decimal('1e100'): raise ValueError('Nonfinite or excessive decimal')
    return str(result)
def normalize(raw,source,origin='IMPORTED',collected=None):
    if not isinstance(raw,dict): raise ValueError('Record must be an object')
    if origin not in ORIGINS: raise ValueError('Unknown provenance class')
    if len(encode(raw))>100000: raise ValueError('Record exceeds 100 KB')
    mapping=source.get('mapping',{})
    def field(key,default=None): return raw.get(mapping.get(key,key),default)
    key=str(field('key',source['id'])).strip()
    kind=str(field('kind',source.get('kind','NUMBER'))).upper()
    if not key or len(key)>200 or kind not in KINDS: raise ValueError('Invalid key or kind')
    value=number(field('value'))
    text=field('text')
    if text is not None: text=str(text)[:20000]
    if kind=='SHORT_TEXT' and not text: raise ValueError('Text observation has no text')
    if kind!='SHORT_TEXT' and value is None and kind!='SPORTS_RESULT': raise ValueError('Measurement is missing')
    if kind=='SPORTS_ODDS' and (value is None or Decimal(value)<=1): raise ValueError('Decimal odds must exceed 1')
    if kind=='PERCENTAGE' and not Decimal(0)<=Decimal(value)<=Decimal(100): raise ValueError('Percentage outside 0..100')
    unit=str(field('unit',source.get('unit','unknown')) or 'unknown')[:80]
    observed=timestamp(field('observed_at')); issued=timestamp(field('issue_at')); valid=timestamp(field('valid_at'))
    if kind=='WEATHER_OBSERVATION' and not observed: raise ValueError('Weather measurement requires observation time')
    if kind=='WEATHER_FORECAST' and (not issued or not valid or valid<issued): raise ValueError('Forecast requires issue and validity clocks with valid >= issue')
    warnings=[]
    if not observed: warnings.append('Observation time unavailable; collection time is not a substitute')
    if unit=='unknown' and value is not None: warnings.append('Measurement unit is unknown')
    metadata=field('metadata',{})
    if not isinstance(metadata,dict): raise ValueError('Metadata must be an object')
    raw_hash=fingerprint(raw)
    row=dict(source_id=source['id'],key=key,kind=kind,value=value,text=text,unit=unit,origin=origin,
             observed_at=observed,collected_at=timestamp(collected or now()),issue_at=issued,valid_at=valid,
             metadata=metadata,raw=raw,raw_hash=raw_hash,source_url=source.get('location','local-upload'),
             quality={'state':origin,'schema_valid':True,'warnings':warnings,'missing_observation_time':not bool(observed),'unit_known':unit!='unknown'},contract='dh.observation/2')
    row['id']=fingerprint([source['id'],origin,raw_hash,mapping,source.get('kind'),source.get('unit')])
    row['identity']=str(field('identity',key+'|'+str(observed or metadata.get('date',''))))
    return row
def convert(value,unit,target):
    d=Decimal(number(value))
    conversions={('degF','degC'):lambda x:(x-32)*5/9,('K','degC'):lambda x:x-Decimal('273.15'),('km/h','m/s'):lambda x:x/Decimal('3.6')}
    if unit==target:return str(d)
    if (unit,target) not in conversions:raise ValueError('Unsupported explicit unit conversion')
    return str(conversions[unit,target](d))
