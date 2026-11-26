"""Event-only ESPN scoreboard import. Competition slugs explicitly identify supported leagues."""
from datetime import date, datetime
from .normalization import timestamp

LEAGUES = {'nba': 'basketball', 'nhl': 'hockey', 'mlb': 'baseball', 'nfl': 'football', 'eng.1': 'soccer'}
SPORTS = {'basketball': 'Basketball', 'hockey': 'Ice hockey', 'baseball': 'Baseball',
          'football': 'American football', 'soccer': 'Football'}


def source_for(league, day):
    if league not in LEAGUES:
        raise ValueError('Unsupported scoreboard league')
    day = date.fromisoformat(day).isoformat()
    slug = LEAGUES[league]
    location = f'https://site.api.espn.com/apis/site/v2/sports/{slug}/{league}/scoreboard?dates={day.replace("-", "")}'
    return {'id': 'espn-' + league.replace('.', '-') + '-' + day, 'name': f'ESPN {league.upper()} {day}',
            'adapter': 'http', 'location': location, 'approved': True, 'enabled': False,
            'options': {'format': 'espn-scoreboard/1', 'league': league}}


def parse_scoreboard(data, league):
    if league not in LEAGUES or not isinstance(data, dict):
        raise ValueError('Expected a scoreboard and a supported league')
    league_info = next((v for v in data.get('leagues', []) if isinstance(v, dict) and v.get('slug') == league), None)
    if not league_info or not isinstance(data.get('events'), list) or len(data['events']) > 200:
        raise ValueError('Missing or inconsistent league or event list')
    seen = set()
    rows = []
    for event in data['events']:
        if not isinstance(event, dict) or not isinstance(event.get('competitions'), list) or len(event['competitions']) != 1:
            raise ValueError('Expected one contest per team event')
        contest = event['competitions'][0]
        sides = {}
        for entry in contest.get('competitors', []):
            side = entry.get('homeAway')
            team = entry.get('team') or {}
            if side not in ('home', 'away') or side in sides or not team.get('id') or not team.get('displayName'):
                raise ValueError('Invalid scoreboard participants')
            sides[side] = {'id': str(team['id']), 'name': team['displayName'], 'score': entry.get('score')}
        event_id = event.get('id')
        if not event_id or event_id in seen or set(sides) != {'home', 'away'} or sides['home']['id'] == sides['away']['id']:
            raise ValueError('Missing or duplicate scoreboard identity')
        seen.add(event_id)
        status = (contest.get('status') or event.get('status') or {}).get('type') or {}
        start = timestamp(contest.get('date') or event.get('date'))
        state = status.get('state')
        if state not in ('pre', 'in', 'post'):
            state = 'unknown'
        metadata = {'contract': 'sports.event/1', 'provider': 'ESPN', 'provider_event_id': str(event_id),
                    'sport': SPORTS[LEAGUES[league]], 'competition': league_info.get('name') or league,
                    'league': league, 'country': None, 'season': (event.get('season') or {}).get('year'),
                    'participants': sides, 'scheduled_at': start, 'status': status.get('description'),
                    'state': state, 'markets': None, 'source_timestamp': None, 'original_provider_record': event}
        rows.append({'identity': f'{league}|{event_id}', 'key': league, 'kind': 'SPORT_EVENT',
                     'unit': 'event', 'text': sides['home']['name'] + ' — ' + sides['away']['name'],
                     'value': None, 'metadata': metadata})
    return rows


def saved_events(store, filters):
    source = source_for(filters['league'], filters['day'])
    receipt = store.latest_scoreboard(source['id'])
    current = set(receipt['scoreboard_ids']) if receipt else set()
    data = store.query({'source': source['id'], 'kind': 'SPORT_EVENT'}, 10000)
    if data['total'] > 10000:
        raise ValueError('Too many revisions for one scoreboard day')
    groups = {}
    for r in data['rows']:
        m = r['metadata']
        if m.get('contract') != 'sports.event/1' or m.get('league') != filters['league']:
            continue
        groups.setdefault((r['origin'], m['provider_event_id']), []).append(r)
    rows = []
    for records in groups.values():
        records.sort(key=lambda r: (datetime.fromisoformat(r['collected_at']), r['id']))
        latest = records[-1]
        in_snapshot = [r for r in records if r['id'] in current]
        if in_snapshot:
            latest = in_snapshot[-1]
        m = latest['metadata']
        rows.append({k: m.get(k) for k in ('sport','competition','season','participants','scheduled_at','status','provider','provider_event_id','source_timestamp','markets')} |
                    {'source_id': latest['source_id'], 'source_url': latest['source_url'], 'origin': latest['origin'],
                     'category': 'PROVIDER-REPORTED DATA' if latest['origin'] == 'COLLECTED' else latest['origin'],
                     'collected_at': latest['collected_at'], 'snapshot_presence': ('PRESENT' if in_snapshot else 'ABSENT') if receipt else 'UNKNOWN',
                     'snapshot_at': receipt['acquired_at'] if receipt else None, 'observation_ids': [r['id'] for r in records],
                     'conflicting_latest': len(records)>1 and records[-2]['collected_at']==latest['collected_at']})
    return {'schema': 'dh.scoreboard/1', 'events': sorted(rows, key=lambda r: r['scheduled_at'] or ''),
            'source': source['location'], 'snapshot_receipt': {k:receipt[k] for k in ('id','content_hash','acquired_at')} if receipt else None, 'stored_observations': data['total']}
