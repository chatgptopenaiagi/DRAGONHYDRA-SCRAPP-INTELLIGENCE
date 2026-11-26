"""Recompute the frozen preseason experiment. Only aggregate results are distributed."""
import argparse
import hashlib
import json
import math
import statistics
from datetime import date
from pathlib import Path
from urllib.request import urlopen

TRAIN = '808a728e95cf47d082c9667e18273f55d619932e'
TEST = 'a670c01830c68f759041b8fce2d3c60b6318ab7e'
AVAILABLE = date(2021, 4, 28)
SEASONS = ('2021-22', '2022-23', '2023-24', '2024-25')
OUTCOMES = ('home', 'draw', 'away')


def season(cache, commit, period, league):
    path = f'{period}/{league}.json'
    url = f'https://raw.githubusercontent.com/openfootball/football.json/{commit}/{path}'
    local = cache / commit / path
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(url, timeout=30) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Season exceeds 2 MB')
        json.loads(raw)
        local.write_bytes(raw)
    raw = local.read_bytes()
    data = json.loads(raw)
    rows, seen = [], set()
    for game in data['matches']:
        day = date.fromisoformat(game['date'])
        key = (game['team1'], game['team2'])
        if key in seen or key[0] == key[1]:
            raise ValueError('Ambiguous fixture in a double round-robin season')
        seen.add(key)
        score = game['score']['ft']
        if len(score) != 2 or any(type(n) is not int or n < 0 for n in score):
            raise ValueError('Incomplete full-time score')
        rows.append((day, 0 if score[0] > score[1] else 1 if score[0] == score[1] else 2))
    return rows, {'season': period, 'url': url, 'sha256': hashlib.sha256(raw).hexdigest(), 'n': len(rows),
                  'first_date': min(day for day, _ in rows).isoformat(), 'last_date': max(day for day, _ in rows).isoformat()}


def metrics(probabilities, labels):
    n = len(labels)
    shares = [labels.count(i) / n for i in range(3)]
    return {'brier': statistics.mean(sum((p - int(i == y))**2 for i, p in enumerate(probabilities)) for y in labels),
            'log_loss': statistics.mean(-math.log(probabilities[y]) for y in labels),
            'observed_shares': dict(zip(OUTCOMES, shares)),
            'calibration_gap': dict(zip(OUTCOMES, [p - share for p, share in zip(probabilities, shares)]))}


def evaluate(train, validation, cutoff):
    if not train or not validation or max(d for d, _ in train) >= cutoff or min(d for d, _ in validation) <= cutoff:
        raise ValueError('Training results must exist in the frozen snapshot before every evaluation fixture')
    labels = [y for _, y in train]
    prior = [(labels.count(i) + 1) / (len(labels) + 3) for i in range(3)]
    test_labels = [y for _, y in validation]
    return {'prior': dict(zip(OUTCOMES, prior)), 'frequency': metrics(prior, test_labels),
            'uniform': metrics([1/3]*3, test_labels), 'accuracy': test_labels.count(prior.index(max(prior))) / len(test_labels)}


def experiment(cache):
    result = {'schema': 'dh.preseason-evaluation/1', 'category': 'STATISTICAL ESTIMATE',
              'training_snapshot_date': AVAILABLE.isoformat(), 'leagues': {}}
    for league, expected in [('en.1', 380), ('de.1', 306)]:
        train, source = season(cache, TRAIN, '2019-20', league)
        if len(train) != expected:
            raise ValueError('Incomplete training season')
        holdouts = []
        for period in SEASONS:
            validation, evidence = season(cache, TEST, period, league)
            if len(validation) != expected:
                raise ValueError('Incomplete validation season')
            holdouts.append({'source': evidence, **evaluate(train, validation, AVAILABLE)})
        result['leagues'][league] = {'train': source, 'holdouts': holdouts}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(experiment(args.cache), indent=2, allow_nan=False)+'\n', encoding='utf-8')
