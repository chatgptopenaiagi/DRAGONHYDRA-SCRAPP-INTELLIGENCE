"""Conservative syntax classification; domain assertions require explicit context."""
import re
from datetime import date,time
from .model import decimal_value

def classify(value,*,decimal_mark='.',context=None):
    context=context or {};text=str(value).strip()
    if context.get('kind') in ('SPORTS_ODDS','WEATHER_OBSERVATION','WEATHER_FORECAST','HISTORICAL_MODEL_DATA'):
        required=('market_id',) if context['kind']=='SPORTS_ODDS' else ('unit','source_type')
        if not all(context.get(k) for k in required):return {'kind':'UNKNOWN','reason':'Domain evidence incomplete'}
        return {'kind':context['kind'],'reason':'Explicit source contract; full normalization still required'}
    if text.endswith('%'):
        try:
            number=decimal_value(text[:-1],decimal_mark)
            if 0<=number<=100:return {'kind':'PERCENTAGE','value':str(number),'unit':'%','reason':'Explicit percent symbol'}
        except ValueError:pass
        return {'kind':'UNKNOWN','reason':'Malformed percentage'}
    try:return {'kind':'NUMBER','value':str(decimal_value(value,decimal_mark)),'reason':'Exact numeric syntax; no odds or probability inference'}
    except ValueError:pass
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',text):
        try:date.fromisoformat(text);return {'kind':'DATE','value':text,'reason':'ISO calendar date; time zone not inferred'}
        except ValueError:pass
    if re.fullmatch(r'\d{2}:\d{2}(?::\d{2})?',text):
        try:time.fromisoformat(text);return {'kind':'TIME','value':text,'reason':'Clock value without inferred date/zone'}
        except ValueError:pass
    if 0<len(text)<=4000 and any(c.isalpha() for c in text):return {'kind':'SHORT_TEXT','reason':'Text syntax; sentiment requires interpretation'}
    return {'kind':'UNKNOWN','reason':'Insufficient typed evidence'}
