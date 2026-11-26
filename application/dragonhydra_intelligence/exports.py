import csv
import io
import json


def market_csv(result):
    """One row per outcome with its complete source scenario and EV assumption."""
    buf = io.StringIO(newline="")
    writer = csv.writer(buf)
    writer.writerow(("schema", "category", "scenario_json", "outcome", "decimal",
                     "implied", "normalized", "fair_decimal", "book_total", "overround",
                     "theoretical_margin", "assumed_probability", "basis_json", "net_per_unit"))
    ev = result["expected_value"]
    for name, row in result["outcomes"].items():
        assumed = ev if ev and ev["outcome"] == name else {}
        writer.writerow([result["schema"], result["category"], json.dumps(result["input"]), name,
                         row["decimal"], row["implied"], row["normalized"], row["fair_decimal"],
                         result["book_total"], result["overround"], result["theoretical_margin"],
                         assumed.get("probability"), json.dumps(assumed.get("basis")), assumed.get("net_per_unit")])
    return buf.getvalue()
