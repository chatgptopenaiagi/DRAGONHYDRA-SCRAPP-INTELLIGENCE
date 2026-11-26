"""Read-only football research. Match within one source and one provenance class."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from unicodedata import normalize

from .contracts import now
from .market_history import movement
from .normalization import timestamp


def label(value):
    return ' '.join(normalize('NFKC', str(value or '')).casefold().split())


def teams(m):
    return m.get('home_team') or m.get('home'), m.get('away_team') or m.get('away')


def match_key(row, quote=False):
    m = row['metadata']
    fields = ('provider_match_id', 'match_id') if quote else ('provider_match_id', 'provider_event_id', 'fixture_id', 'id')
    scope = (row['source_id'], row['origin'])
    for field in fields:
        if type(m.get(field)) in (str, int) and str(m[field]).strip():
            return (*scope, 'id', str(m[field]))
    home, away = teams(m)
    parts = (m.get('competition'), m.get('season'), home, away, m.get('date') or (m.get('scheduled_at') or '')[:10])
    if all(isinstance(x, (str, int)) and label(x) for x in parts) and label(home) != label(away):
        return (*scope, 'exact', *(label(x) for x in parts))
    return None


def quote_view(q):
    m = q['metadata']
    status = str(m.get('quote_status') or m.get('status') or '').upper()
    unavailable = m.get('suspended') is True or status in {'SUSPENDED','WITHDRAWN','CLOSED','UNAVAILABLE','INACTIVE'}
    price = None
    try:
        n = Decimal(q['value'])
        if n.is_finite() and 1 < n <= Decimal('1e100') and q['unit'] == 'decimal_odds':
            price = n
    except (InvalidOperation, ValueError, TypeError):
        pass
    stamp = q.get('observed_at') or m.get('quote_time')
    try:
        stamp = timestamp(stamp)
    except (ValueError, TypeError, OverflowError):
        stamp = None
    return {'id': q['id'], 'bookmaker': m.get('bookmaker') or 'Not supplied',
            'market': m.get('market') or q['key'], 'outcome': m.get('outcome') or 'Not supplied',
            'decimal_odds': q['value'], 'implied_percent': str(Decimal(100) / price) if price and not unavailable else None,
            'quote_time': stamp, 'origin': q['origin'], 'phase': m.get('phase'), 'evidence': q,
            'quality': 'UNAVAILABLE' if unavailable else 'INVALID_PRICE' if price is None else 'UNKNOWN_TIME' if not stamp else 'TIMESTAMPED'}


def research(store, filters):
    if set(filters) - {'source','origin','search','from','to','limit','offset'}:
        raise ValueError('Unknown football research filter')
    limit, offset = int(filters.get('limit', 25)), int(filters.get('offset', 0))
    if not 1 <= limit <= 50 or not 0 <= offset <= 10000:
        raise ValueError('Choose 1–50 matches per page')
    search = label(filters.get('search'))
    if len(search) > 120:
        raise ValueError('Search is limited to 120 characters')
    data = store.query({k: filters[k] for k in ('source', 'origin') if filters.get(k)}, 10000)
    if data['total'] > 10000:
        raise ValueError('Choose a narrower source or provenance. No records were silently omitted.')
    matches, quotes, identities = [], defaultdict(list), defaultdict(set)
    counts = defaultdict(int)
    for r in data['rows']:
        m = r['metadata']
        if r['kind'] == 'SPORTS_ODDS':
            quotes[match_key(r, True)].append(r)
            continue
        if r['kind'] != 'SPORTS_RESULT' and m.get('contract') not in ('football.fixture/1', 'football.result/1'):
            continue
        home, away = teams(m)
        if not home or not away:
            continue
        key = match_key(r)
        day = m.get('date') or (m.get('scheduled_at') or '')[:10] or (r.get('observed_at') or '')[:10] or None
        if key:
            counts[key] += 1
            identities[key].add((label(home), label(away), str(day or ''), label(m.get('competition')), label(m.get('season')), str(m.get('scheduled_at') or '')))
        if search and search not in label(' '.join(str(v or '') for v in (home, away, m.get('competition'), m.get('season')))):
            continue
        if filters.get('from') and (not day or day < filters['from']):
            continue
        if filters.get('to') and (not day or day > filters['to']):
            continue
        matches.append((day or '', r['source_id'], r['id'], key, r))
    matches.sort(key=lambda v: v[:3], reverse=True)
    def unique(key):
        return key is not None and len(identities[key]) == 1 and (key[2] == 'id' or counts[key] == 1)

    def consistent(key, quote):
        if not unique(key):
            return False
        home, away, day, comp, season, start = next(iter(identities[key]))
        m = quote['metadata']
        qhome, qaway = teams(m)
        for supplied, expected in [(qhome,home),(qaway,away),(m.get('date'),day),(m.get('competition'),comp),(m.get('season'),season)]:
            if supplied and expected and label(supplied) != expected:
                return False
        return True

    linked_quotes = {k: [q for q in records if consistent(k,q)] for k,records in quotes.items()}
    page = []
    for day, source, _, key, r in matches[offset:offset+limit]:
        m = r['metadata']
        home, away = teams(m)
        linked = linked_quotes.get(key, ())
        prices = [quote_view(q) for q in linked]
        page.append({'id': r['id'], 'sport': 'Football', 'source': source, 'origin': r['origin'],
                     'home': home, 'away': away, 'home_goals': m.get('home_goals', m.get('hg')),
                     'away_goals': m.get('away_goals', m.get('ag')), 'date': day or None, 'competition': m.get('competition'),
                     'season': m.get('season'), 'match_status': m.get('status') or ('Historical result' if r['kind']=='SPORTS_RESULT' else 'Not supplied'),
                     'observed_at': r.get('observed_at'), 'collected_at': r['collected_at'],
                     'odds': prices, 'history': movement(prices), 'evidence': r})
    return {'rows': page, 'total': len(matches), 'offset': offset, 'limit': limit, 'read_at': now(),
            'datastore': data.get('datastore', 'SQLITE_OFFLINE'),
            'unlinked_quotes': sum(len(v)-len(linked_quotes[k]) for k,v in quotes.items()),
            'ambiguous_match_keys': sum(not unique(k) for k in counts),
            'limitations': ['Stored source records may include revisions of the same event.',
                            'Quotes require an unambiguous identity within one source and origin.',
                            'Collection time never substitutes for a missing quote time.']}
