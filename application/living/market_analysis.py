"""Deterministic calculations for a user-specified exhaustive win market."""
from decimal import Decimal, DecimalException, localcontext
from dragonhydra.market_signals import convert_odds, implied_probability, PRECISION

MARKETS = {'1X2': ('home', 'draw', 'away'), 'two-way': ('first', 'second')}


def price(value, fmt):
    if not isinstance(value, (str, int, float, Decimal)) or isinstance(value, bool) or len(str(value)) > 80:
        raise ValueError('Supply a quoted price of at most 80 characters')
    try:
        # Bound exponents before performing arithmetic on untrusted input.
        if fmt != 'fractional':
            number = Decimal(str(value))
            if not number.is_finite() or abs(number.adjusted()) > 25:
                raise ValueError('Price exceeds the supported range')
        return convert_odds(value, fmt)
    except DecimalException as exc:
        raise ValueError('Invalid quoted price') from exc


def calculate_market(body):
    market = body.get('market')
    outcomes = MARKETS.get(market)
    prices = body.get('prices')
    if not outcomes or not isinstance(prices, dict) or set(prices) != set(outcomes):
        raise ValueError('Supply exactly one price per outcome in the selected exhaustive market')
    if set(body) - {'market', 'format', 'prices', 'assumption'}:
        raise ValueError('Unexpected calculation input')
    fmt = body.get('format', 'decimal')
    with localcontext() as ctx:
        ctx.prec = PRECISION
        decimals = {k: price(prices[k], fmt) for k in outcomes}
        implied = {k: implied_probability(d) for k, d in decimals.items()}
        book = sum(implied.values())
        rows = {}
        for k, q in implied.items():
            norm = q / book
            rows[k] = {'decimal': str(decimals[k]), 'implied': str(q), 'normalized': str(norm),
                       'fair_decimal': str(1 / norm)}
        assumption = body.get('assumption')
        ev = None
        if assumption is not None:
            if not isinstance(assumption, dict) or set(assumption) != {'outcome', 'probability', 'basis'}:
                raise ValueError('Expected value requires an outcome, probability and named basis')
            k, basis = assumption['outcome'], assumption['basis']
            if k not in decimals or not isinstance(basis, str) or not 1 <= len(basis.strip()) <= 200:
                raise ValueError('Select an outcome and explain the probability assumption')
            try:
                raw = str(assumption['probability'])
                if len(raw) > 80:
                    raise ValueError('Probability is too long')
                p = Decimal(raw)
                if not p.is_finite() or not 0 <= p <= 1 or (p and p.adjusted() < -100):
                    raise ValueError('Assumed probability must be between 0 and 1 at supported precision')
            except DecimalException as exc:
                raise ValueError('Invalid assumed probability') from exc
            ev = {'outcome': k, 'probability': str(p), 'basis': basis.strip(), 'net_per_unit': str(p * decimals[k] - 1)}
        return {'schema': 'dh.market/1', 'category': 'MATHEMATICAL CALCULATION',
                'basis': 'User-supplied scenario, mutually exclusive and exhaustive outcomes, no pushes, fees or taxes',
                'input': body, 'book_total': str(book), 'overround': str(book - 1),
                'theoretical_margin': str(1 - 1 / book), 'outcomes': rows, 'expected_value': ev}
