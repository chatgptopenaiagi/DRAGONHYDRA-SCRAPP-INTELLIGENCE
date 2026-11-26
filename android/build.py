"""Build with stock Android SDK CLI tools and JDK. Signing passwords come from the environment."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--keystore", type=Path, required=True)
parser.add_argument("--alias", default="dragonhydra")
parser.add_argument("--instrumentation", action="store_true")
args = parser.parse_args()
sdk = Path(os.environ["ANDROID_HOME"])
jdk = Path(os.environ["JAVA_HOME"]) / "bin"
tools = sdk / "build-tools" / "36.0.0"
platform = sdk / "platforms/android-36/android.jar"
windows = os.name == "nt"
exe = ".exe" if windows else ""
batch = ".bat" if windows else ""
out = args.out.resolve()
out.parent.mkdir(parents=True, exist_ok=True)
def run(*argv):
    subprocess.run(list(map(str, argv)), check=True)
with tempfile.TemporaryDirectory() as folder:
    t = Path(folder)
    classes, dex, assets = t/"classes", t/"dex", t/"assets"
    classes.mkdir(); dex.mkdir()
    base = ROOT/"test" if args.instrumentation else ROOT
    shutil.copytree(base/"assets", assets)
    if not args.instrumentation:
        shutil.copy(ROOT.parent/"application/living/web/backtest.json", assets)
    aapt = tools/("aapt2"+exe)
    resources = []
    if (base/"res").is_dir():
        run(aapt,"compile","--dir",base/"res","-o",t/"res.zip")
        resources.append(t/"res.zip")
    run(aapt,"link","-I",platform,"--manifest",base/"AndroidManifest.xml","-A",assets,"-o",t/"app.apk",*resources)
    run(jdk/("javac"+exe),"-encoding","UTF-8","--release","8","-classpath",platform,"-d",classes,*sorted((base/"src").glob("*.java")))
    run(jdk/("jar"+exe),"cf",t/"classes.jar","-C",classes,".")
    run(tools/("d8"+batch),"--min-api","26","--lib",platform,"--output",dex,t/"classes.jar")
    with zipfile.ZipFile(t/"app.apk","a") as package:
        entry = zipfile.ZipInfo("classes.dex", (1980, 1, 1, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        package.writestr(entry, (dex/"classes.dex").read_bytes())
    run(tools/("zipalign"+exe),"-f","4",t/"app.apk",t/"aligned.apk")
    run(tools/("apksigner"+batch),"sign","--ks",args.keystore,"--ks-key-alias",args.alias,
        "--ks-pass","env:DH_SIGN_PASSWORD","--v4-signing-enabled","false","--out",out,t/"aligned.apk")
    run(tools/("apksigner"+batch),"verify","--verbose","--print-certs",out)
