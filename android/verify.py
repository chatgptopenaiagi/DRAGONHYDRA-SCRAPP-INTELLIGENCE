"""Exercise a release APK on an explicitly selected disposable Android emulator (English DocumentsUI)."""
import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import time

APP = "io.github.chatgptopenaiagi.dragonhydra"
TEST = APP+".acceptance"
ROOT = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument("--serial",required=True)
p.add_argument("--apk",required=True,type=Path)
p.add_argument("--test-apk",required=True,type=Path)
p.add_argument("--out",required=True,type=Path)
args=p.parse_args()
if not args.serial.startswith("emulator-"):
    p.error("Select a dedicated emulator for this clean installation test")
args.out.mkdir(parents=True,exist_ok=True)
def adb(*cmd):
    return subprocess.check_output(["adb","-s",args.serial,*map(str,cmd)],text=True,encoding="utf-8",errors="replace")
def shell(*cmd):
    return adb("shell",*cmd)
def instrument(stage):
    result=shell("am","instrument","-w","-e","stage",stage,TEST+"/.Acceptance")
    (args.out/(stage+".log")).write_text(result,encoding="utf-8")
    match=re.search(r"^INSTRUMENTATION_RESULT: report=(.*)$",result,re.M)
    if not match or "INSTRUMENTATION_CODE: -1" not in result: raise RuntimeError(result)
    return json.loads(match[1])
def main():
    sdk=shell("getprop","ro.build.version.sdk").strip()
    abi=shell("getprop","ro.product.cpu.abi").strip()
    for name in (TEST,APP):
        if ("package:"+name in shell("pm","list","packages",name).splitlines()): assert "Success" in adb("uninstall",name)
    shell("wm","dismiss-keyguard")
    shell("cmd","connectivity","airplane-mode","enable")
    shell("svc","wifi","disable");shell("svc","data","disable")
    assert shell("cmd","connectivity","airplane-mode").strip()=="enabled"
    for ext in ("json","csv"):
        shell("rm","-f","/sdcard/Download/dragonhydra-history."+ext)
    for path in (args.apk,args.test_apk): assert "Success" in adb("install",path)
    fixture=ROOT/"test/assets/fixture.json"
    adb("push",fixture,"/sdcard/Download/dragonhydra-qa-fixture.json")
    shell("am","broadcast","-a","android.intent.action.MEDIA_SCANNER_SCAN_FILE","-d","file:///sdcard/Download/dragonhydra-qa-fixture.json")
    startup=shell("am","start","-W","-n",APP+"/.MainActivity")
    assert "Status: ok" in startup
    time.sleep(3)
    memory=shell("dumpsys","meminfo","-s",APP)
    (args.out/"meminfo.txt").write_text(memory)
    pid=shell("pidof",APP).strip()
    cpu=shell("top","-b","-n","2","-d","1","-p",pid)
    (args.out/"idle-cpu.txt").write_text(cpu)
    report=instrument("full")
    report.update(android_api=int(sdk),abi=abi,cold_activity_ms=int(re.search(r"TotalTime:\s*(\d+)",startup)[1]),
                  airplane_mode=True,webview=shell("dumpsys","webviewupdate").split("Current WebView package (name, version):")[-1].splitlines()[0].strip())
    for ext in ("json","csv"): adb("pull","/sdcard/Download/dragonhydra-history."+ext,args.out/("history."+ext))
    rows=json.loads((args.out/"history.json").read_text())["observations"]
    with (args.out/"history.csv").open(newline="") as f: exported=list(csv.DictReader(f))
    assert len(rows)==len(exported)==3
    for actual,record,expected in zip(rows,exported,json.loads(fixture.read_text())["observations"]):
        assert all(record[k]==v for k,v in actual.items())
        assert all(actual[k]==v for k,v in expected.items() if k!="at")
        assert actual["at"].replace(".000000000Z","Z")==expected["at"]
    shell("am","force-stop",APP)
    report["restart"]=instrument("persist")["checks"]
    assert "Success" in adb("install","-r",args.apk)
    report["same_version_update"]=instrument("persist")["checks"]
    for name in (TEST,APP):
        assert "Success" in adb("uninstall",name) and not ("package:"+name in shell("pm","list","packages",name).splitlines())
    report["uninstall"]=True
    (args.out/"report.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(len(report["checks"]),"acceptance groups, exports verified, package removed")
if __name__=="__main__":main()
