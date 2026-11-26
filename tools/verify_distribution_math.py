"""Run the shared synthetic market vectors through both original HTTP servers and the installed wheel."""
import argparse
import json
import subprocess
import tempfile
import time
from decimal import Decimal
from pathlib import Path
from living import launcher
from dragonhydra_intelligence import odds

ROOT = Path(__file__).resolve().parents[1]
VECTORS = json.loads((ROOT/"android/test/assets/scenarios.json").read_text())


def cases(call):
    out = {}
    for sample in VECTORS:
        try:
            value = call(sample["body"])
        except (ValueError, RuntimeError):
            if sample["valid"]:
                raise
            value = {"invalid": True}
        assert ("invalid" not in value) == sample["valid"], sample["id"]
        out[sample["id"]] = value
    return out


def service(command):
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        proc = subprocess.Popen(command+["--serve","--mode","offline","--port","0","--data-dir",tmp],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(200):
                if launcher.running(folder):
                    break
                if proc.poll() is not None:
                    raise RuntimeError("Server exited early")
                time.sleep(.15)
            assert launcher.running(folder), "Server startup timed out"
            return cases(lambda body: launcher.request(folder,"/api/market/calculation",body))
        finally:
            launcher.stop(folder)
            if proc.poll() is None:
                try: proc.wait(timeout=15)
                except subprocess.TimeoutExpired: proc.terminate(); proc.wait()


def compare(reference, observed):
    assert set(reference) == set(observed)
    def equal(a,b):
        x,y=Decimal(a),Decimal(b)
        assert x.is_finite() and y.is_finite() and abs(x-y)<=Decimal("1e-30")*max(abs(x),Decimal("1e-25")), (a,b)
    for name,r in reference.items():
        v=observed[name]
        if "invalid" in r:
            assert v==r
            continue
        for k in ("book_total","overround","theoretical_margin"):
            equal(r[k],v[k])
        assert set(r["outcomes"])==set(v["outcomes"])
        for outcome, fields in r["outcomes"].items():
            for k,x in fields.items():
                equal(x,v["outcomes"][outcome][k])
        if r["expected_value"]:
            for k in ("net_per_unit","probability"):
                equal(r["expected_value"][k],v["expected_value"][k])
            for k in ("basis","outcome"):
                assert r["expected_value"][k]==v["expected_value"][k]
        else: assert v["expected_value"] is None


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--python",required=True);p.add_argument("--source-launcher",required=True)
    p.add_argument("--portable",required=True);p.add_argument("--out",type=Path,required=True)
    p.add_argument("--android",type=Path)
    a=p.parse_args()
    results={"wheel":cases(odds.calculate_market),"source":service([a.python,a.source_launcher]),
             "portable":service([a.portable])}
    if a.android: results["android"]=json.loads(a.android.read_text(encoding="utf-8-sig"))["vectors"]
    for key,result in results.items(): compare(results["wheel"],result)
    a.out.write_text(json.dumps(results,indent=2),encoding="utf-8")
    print(len(VECTORS),"vectors passed per platform:",", ".join(results))
