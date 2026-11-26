"""Execute with an installed wheel from outside its source checkout."""
from contextlib import closing
import csv
import hashlib
from importlib import metadata, resources
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import urllib.request

import dragonhydra_intelligence as dh
import living
from living import launcher

def run():
    prefix = Path(sys.prefix).resolve()
    assert all(Path(m.__file__).resolve().is_relative_to(prefix) for m in (dh,living))
    assert metadata.version("dragonhydra-intelligence") == dh.__version__ == "0.3.0b1"
    cli = Path(sys.executable).with_name("dragonhydra.exe" if sys.platform=="win32" else "dragonhydra")
    def command(*args):
        return subprocess.check_output([str(cli),*map(str,args)],text=True)
    assert command("--version").strip() == dh.__version__
    assert "dashboard" in subprocess.check_output([sys.executable,"-I","-m","dragonhydra_intelligence","--help"],text=True)
    assert json.loads(command("calculator","5/2","--format","fractional"))["decimal"] == "3.5"
    assert dh.odds.analyze_decimal("2.50")["implied"] == "0.4"
    body = {"market":"two-way","format":"decimal","prices":{"first":"2.50","second":"1.60"},
            "assumption":{"outcome":"first","probability":"0.45","basis":"User scenario"}}
    r = dh.odds.calculate_market(body)
    assert float(r["expected_value"]["net_per_unit"]) == .125
    stats = dh.evaluate_binary([.7,.2],[1,0])
    assert math.isclose(stats["brier"],.065) and math.isclose(stats["log_loss"],-(math.log(.7)+math.log(.8))/2)
    assert len(json.loads(resources.files("living").joinpath("web/backtest.json").read_text())["leagues"]) == 2
    raw={"kind":"SPORT_EVENT","key":"fixture","text":"Synthetic A versus B"}
    row=dh.normalize_observation(raw,{"id":"qa"},origin="SYNTHETIC")
    assert row["raw"] == raw and row["origin"]=="SYNTHETIC" and len(row["raw_hash"])==64
    assert dh.parse_scoreboard({"leagues":[{"slug":"nba"}],"events":[]},"nba") == []
    assert dh.historical_market([])["series"] == []
    with TemporaryDirectory() as tmp:
        base=Path(tmp)
        with closing(dh.Store(base/"test.sqlite3")) as store:
            store.state("test","record",{"value":"retained"})
        with closing(dh.Store(base/"test.sqlite3")) as store:
            assert store.state("test","record") == {"value":"retained"} and store.integrity=="ok"
        scenario=base/"input.json";scenario.write_text(json.dumps(body))
        assert json.loads(command("analyze",scenario))==r
        for ext in ("csv","json"):
            dest=base/("result."+ext);command("export",scenario,dest)
            if ext=="csv":
                records=list(csv.DictReader(dest.read_text().splitlines()))
                assert len(records)==2 and json.loads(records[0]["scenario_json"])==body
            else: assert json.loads(dest.read_text())==r
        profile=base/"dashboard"
        try:
            command("dashboard","--data-dir",profile,"--no-browser")
            assert launcher.running(profile)["mode"]=="offline"
            port=json.loads((profile/"ready.json").read_text())["port"]
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as page:
                assert b"DRAGONHYDRA" in page.read()
            assert launcher.request(profile,"/api/market/calculation",body)==r
        finally: command("dashboard","--data-dir",profile,"--stop")
    print(json.dumps({"python":sys.version.split()[0],"platform":sys.platform,"version":dh.__version__,
                      "checks":["installed module paths","metadata","console and module entry points","calculator and market API",
                                "binary Brier and log loss","archived model resource","provenance","provider adapter","historic series",
                                "SQLite persistence","JSON and CSV export","offline dashboard page, authenticated calculation and shutdown"]}))

if __name__=="__main__":
    run()
