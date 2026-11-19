"""Conservative identities: no probabilistic or nearest-name automatic merges."""
import re,unicodedata
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from dragonhydra.domain import identity
from dragonhydra.market_signals import convert_odds

OUTCOMES={'1x2':('home','draw','away'),'double_chance':('home_draw','home_away','draw_away'),'totals':('over','under')}
RULE='football.regulation.90min.v1'

def stamp(value):
    try:d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except (TypeError,ValueError):raise ValueError('Invalid timestamp; use ISO 8601 with UTC offset') from None
    if d.tzinfo is None:raise ValueError('Timestamp requires an explicit UTC offset')
    return d.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')

def instant(value):return datetime.fromisoformat(stamp(value).replace('Z','+00:00'))
def utcnow():return stamp(datetime.now(timezone.utc))

def label(value):
    if not isinstance(value,str) or not value.strip() or len(value)>180 or any(ord(c)<32 for c in value):raise ValueError('Invalid identity label')
    return ' '.join(unicodedata.normalize('NFKC',value).split())

def normalized(value):
    result=re.sub(r'[^\w]+',' ',label(value).casefold(),flags=re.UNICODE).strip()
    if not result:raise ValueError('Empty normalized identity')
    return result

def number(value):
    if isinstance(value,bool) or value is None or len(str(value))>80:raise ValueError('Invalid finite number')
    try:n=Decimal(str(value))
    except (ValueError,InvalidOperation):raise ValueError('Invalid finite number') from None
    if not n.is_finite() or abs(n)>1000000 or abs(n.as_tuple().exponent)>20:raise ValueError('Number outside supported range')
    return n

def canonical_number(n):return format(n.normalize(),'f')

def normalize_record(raw,aliases=None):
    if not isinstance(raw,dict):raise ValueError('Each snapshot must be an object')
    aliases=aliases or {};e=raw.get('event',{});m=raw.get('market',{})
    provider=normalized(raw.get('provider'));book=label(raw.get('bookmaker'))
    sport=normalized(e.get('sport'))
    if sport!='football':raise ValueError('Initial release supports football only')
    competition=label(e.get('competition'));comp=normalized(competition)
    participants=[]
    for side in ('home','away'):
        original=label(e.get(side));name=aliases.get('teams',{}).get('|'.join((provider,comp,normalized(original))),original)
        participants.append(label(name))
    home,away=participants
    if normalized(home)==normalized(away):raise ValueError('Home and away identities must differ')
    kickoff=stamp(e.get('kickoff'));origin=raw.get('origin')
    if origin not in ('synthetic','imported','captured'):raise ValueError('Explicit data origin required')
    event_id=identity('event',sport,comp,normalized(home),normalized(away),kickoff)
    source_id=label(raw.get('source_event_id'))
    book_key=aliases.get('bookmakers',{}).get(provider+'|'+normalized(book),provider+'|'+normalized(book))
    bookmaker_id=identity('bookmaker',book_key)
    market_type={'h2h':'1x2','over_under':'totals','over/under':'totals'}.get(m.get('type'),m.get('type'))
    if market_type not in OUTCOMES:raise ValueError('Unsupported market type')
    period=label(m.get('period'));settlement=label(m.get('settlement'))
    status=m.get('status')
    if status not in ('prematch','live'):raise ValueError('Market status must be prematch or live')
    line=None
    if market_type=='totals':
        n=number(m.get('line'))
        if n<0 or n>100:raise ValueError('Invalid total line')
        line=canonical_number(n)
    elif m.get('line') is not None:raise ValueError('This market must not have a line')
    # Unknown semantics never cross source/bookmaker boundaries.
    scope=provider+'|'+bookmaker_id if settlement=='unknown' or period=='unknown' else ''
    market_id=identity('market',event_id,origin,market_type,period,settlement,status,line,scope)
    observed=stamp(raw.get('observed_at'));received=stamp(raw.get('received_at'))
    if observed>received:raise ValueError('Source observation cannot follow receipt time')
    if status=='prematch' and observed>=kickoff:raise ValueError('Prematch observation must precede kickoff')
    commission=raw.get('commission')
    if commission is not None:
        fee=number(commission)
        if not 0<=fee<1:raise ValueError('Commission must be a net-win fraction in [0,1)')
        commission=canonical_number(fee)
    quotes=raw.get('quotes')
    if not isinstance(quotes,dict) or set(quotes)-set(OUTCOMES[market_type]):raise ValueError('Invalid canonical outcome set')
    observation_kind=raw.get('observation_kind','quotes')
    if observation_kind not in ('quotes','absence') or (observation_kind=='absence' and quotes):raise ValueError('Invalid absence observation')
    clean={}
    for outcome,q in quotes.items():
        if not isinstance(q,dict) or type(q.get('available',True)) is not bool:raise ValueError('Invalid quote availability')
        original=q.get('odds');fmt=q.get('format','decimal')
        if len(str(original))>80:raise ValueError('Odds input too long')
        price=convert_odds(original,fmt)
        if price>1000000:raise ValueError('Odds outside supported range')
        clean[outcome]={'odds':str(price),'original':str(original),'format':fmt,'available':q.get('available',True)}
    return {'event':{'id':event_id,'sport':sport,'competition':competition,'competition_key':comp,'home':home,'away':away,'kickoff':kickoff},
            'market':{'id':market_id,'event_id':event_id,'origin':origin,'type':market_type,'period':period,'settlement':settlement,'status':status,'line':line,'unknown_scope':scope},
            'provider':provider,'bookmaker':book,'bookmaker_id':bookmaker_id,'source_event_id':source_id,'origin':origin,
            'observed_at':observed,'received_at':received,'commission':commission,'quotes':clean,'observation_kind':observation_kind}
