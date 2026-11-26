"""Measure warm local reads against a temporary online backup of an owned SQLite store."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import tempfile
import time


def measure(fn,n):
    fn();times=[]
    for _ in range(n):
        start=time.perf_counter();fn();times.append((time.perf_counter()-start)*1000)
    return {'n':n,'median_ms':round(statistics.median(times),3),'max_ms':round(max(times),3)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--database',required=True,type=Path);p.add_argument('--source',required=True)
    p.add_argument('--checkout',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args()
    sys.path.insert(0,str(a.checkout.resolve()/'application'))
    from living.storage import Store
    from living.football_research import research
    with tempfile.TemporaryDirectory() as tmp:
        copy=Path(tmp)/'snapshot.sqlite3'
        with closing(sqlite3.connect(a.database.resolve().as_uri()+'?mode=ro',uri=True)) as original, closing(sqlite3.connect(copy)) as dest:
            original.backup(dest)
        store=Store(copy)
        try:
            print(json.dumps({'rows':store.query({},1)['total'],'history25':measure(lambda:store.query({},25),31),
                              'research25':measure(lambda:research(store,{'source':a.source,'limit':25}),11)}))
        finally:store.close()
