"""Chronological summaries for one source-owned event. Preserve unavailable observations."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from statistics import pstdev


def movement(quotes):
    books = defaultdict(lambda: defaultdict(list))
    unknown = 0
    for q in quotes:
        m = q['evidence']['metadata']
        if not q['quote_time'] or not all(m.get(k) for k in ('market','bookmaker','outcome')):
            unknown += 1
            continue
        key = tuple(('' if v is None else str(v)) for v in (m['market'], m['outcome'], m.get('line'), m.get('period'),
                                           m.get('settlement'), m.get('bookmaker')))
        books[key][datetime.fromisoformat(q['quote_time'])].append(q)
    series = []
    synchronized = defaultdict(list)
    for key, times in sorted(books.items()):
        points = []
        for stamp, batch in sorted(times.items()):
            values = {Decimal(q['decimal_odds']) for q in batch if q['implied_percent'] is not None}
            valid = len(values) == 1 and all(q['implied_percent'] is not None for q in batch)
            points.append({'at': stamp.isoformat(), 'decimal': str(next(iter(values))) if valid else None,
                           'state': 'OBSERVED' if valid else 'CONFLICT_OR_UNAVAILABLE',
                           'phase': sorted({str(q['phase']) for q in batch if q['phase']}),
                           'ids': [q['id'] for q in batch]})
        change = None
        if len(points)>1 and points[0]['decimal'] and points[-1]['decimal']:
            change = str(1/Decimal(points[-1]['decimal']) - 1/Decimal(points[0]['decimal']))
        changes = []
        for left, right in zip(points, points[1:]):
            if left['decimal'] and right['decimal']:
                changes.append((Decimal(right['decimal']) / Decimal(left['decimal'])).ln())
        if all(key[i] for i in (3,4)):
            for point in points:
                if point['decimal']:
                    synchronized[key[:-1]+(point['at'],)].append((key[-1], Decimal(point['decimal']), point['ids']))
        def reported(phase):
            return [p for p in points if p['decimal'] and phase in {v.casefold() for v in p['phase']}]
        series.append(dict(zip(('market','outcome','line','period','settlement','bookmaker'),key),
                           points=points, implied_change=change, reported_opening=reported('opening'),
                           reported_closing=reported('closing'), log_change_sd=str(pstdev(changes)) if len(changes)>1 else None))
    comparisons = []
    for (market,outcome,line,period,settlement,at), records in sorted(synchronized.items()):
        if len(records) < 2:
            continue
        values = [r[1] for r in records]
        comparisons.append({'market':market, 'outcome':outcome, 'line':line, 'period':period, 'settlement':settlement,
                            'at':at, 'bookmakers':[r[0] for r in records], 'decimal_range':str(max(values)-min(values)),
                            'ids':[i for r in records for i in r[2]]})
    return {'series':series, 'comparisons':comparisons, 'excluded_time_or_identity':unknown}
