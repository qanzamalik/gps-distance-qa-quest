"""OLD reference calculation. It is WRONG ON PURPOSE (this is the system under test).

What it does, as a naive first version would:
  - reads pings in ARRIVAL order (received_at_utc), not by their own timestamp
  - keeps duplicates and GPS noise
  - counts distance everywhere, not only inside the campaign zone
  - cuts the day at 00:00 UTC instead of 00:00 local (UTC+9)

Run: python reference_calc.py
"""
import csv
import sys

from datetime import datetime

import geo

SESSION_GAP_S = 3600


def _secs(iso_ts):
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).timestamp()


def load(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
    return rows


def old_distance_km(rows):
    rows = sorted(rows, key=lambda r: (r["driver_id"], r["received_at_utc"]))
    totals = {}
    for a, b in zip(rows, rows[1:]):
        if a["driver_id"] != b["driver_id"]:
            continue
        if abs(_secs(b["received_at_utc"]) - _secs(a["received_at_utc"])) > SESSION_GAP_S:
            continue  # different trip (the old version did handle trip breaks)
        day = a["ts_utc"][:10]  # UTC date
        key = (a["driver_id"], day)
        totals[key] = totals.get(key, 0) + geo.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    return {k: round(v / 1000, 3) for k, v in totals.items()}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "data/pings_synthetic.csv"
    result = old_distance_km(load(path))
    print("driver_id,day,km_billed_old")
    for (d, day), km in sorted(result.items()):
        print(f"{d},{day},{km}")
