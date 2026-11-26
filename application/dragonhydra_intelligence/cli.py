import argparse
import json
import os
from pathlib import Path
import sys
from . import __version__, market_csv, odds


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dragonhydra")
    parser.add_argument("--version", action="version", version=__version__)
    cmds = parser.add_subparsers(dest="command", required=True)
    calc = cmds.add_parser("calculator", help="Convert a quote to decimal and implied probability")
    calc.add_argument("price")
    calc.add_argument("--format", choices=["decimal", "fractional", "american"], default="decimal")
    for name in ("analyze", "export"):
        sub = cmds.add_parser(name, help="Calculate an exhaustive market from a JSON document")
        sub.add_argument("input", type=Path)
        if name == "export":
            sub.add_argument("output", type=Path, help="Output filename ending in .json or .csv")
    dash = cmds.add_parser("dashboard", help="Launch the offline dashboard in your browser")
    dash.add_argument("--data-dir", type=Path, default=Path(os.getenv("LOCALAPPDATA", Path.home()))/"DRAGONHYDRA"/"Python")
    dash.add_argument("--port", type=int, default=0)
    group = dash.add_mutually_exclusive_group()
    group.add_argument("--no-browser", action="store_true")
    group.add_argument("--stop", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "dashboard":
            from living import launcher
            if args.stop:
                launcher.stop(args.data_dir)
                return 0
            if args.port and not 1024 <= args.port <= 65535:
                raise ValueError("Use port 0 or a port between 1024 and 65535")
            launcher.ensure(args.data_dir, args.port, "offline")
            if not args.no_browser:
                launcher.open_dashboard(args.data_dir)
            print("Offline dashboard running. Profile:", args.data_dir.resolve())
            return 0
        if args.command == "calculator":
            result = odds.analyze_decimal(odds.to_decimal(args.price, args.format))
        else:
            body = json.loads(args.input.read_text(encoding="utf-8-sig"))
            if not isinstance(body, dict):
                raise ValueError("Expected a JSON object")
            result = odds.calculate_market(body)
        if args.command == "export":
            ext = args.output.suffix.lower()
            if ext not in (".csv", ".json"):
                raise ValueError("Choose a .csv or .json output")
            data = market_csv(result) if ext == ".csv" else json.dumps(result, indent=2)
            args.output.write_text(data, encoding="utf-8", newline="")
        else:
            print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, TypeError) as exc:
        parser.exit(2, f"dragonhydra: {exc}\n")
