"""FIXED reference calculation, plus the before/after comparison.

Order of steps matters:
  1. remove duplicates (same driver + timestamp, keep first received)
  2. order pings by their OWN timestamp, not arrival time
  3. drop GPS noise (>100 m off road, or >150 km/h vs the last valid ping)
  4. count a segment only when both pings are inside the zone
  5. cut days at 00:00 local time (UTC+9)

Run: python fixed_calc.py   -> results/before_after.csv
"""
import csv
import os
import sys

import rules
from reference_calc import load, old_distance_km


def fixed_distance_km(rows):
    km = rules.distance_km(rows, dedupe=True, sort_by_ts=True, drop_noise=True,
                           zone_only=True, local_days=True)
    return {k: round(v, 3) for k, v in km.items()}


def main(path="data/pings_synthetic.csv"):
    rows = load(path)
    old = old_distance_km(rows)
    new = fixed_distance_km(rows)
    with open("data/truth_km_synthetic.csv") as f:
        truth = {(r["driver_id"], r["local_day"]): float(r["expected_km"]) for r in csv.DictReader(f)}

    os.makedirs("results", exist_ok=True)
    keys = sorted(set(old) | set(new) | set(truth))
    with open("results/before_after.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["driver_id", "day", "km_before (old, UTC day)", "km_after (fixed, local day)",
                    "difference_km", "expected_km (generator)", "after_minus_expected"])
        for k in keys:
            b, a, t = old.get(k, 0), new.get(k, 0), truth.get(k, 0)
            w.writerow([k[0], k[1], b, a, round(a - b, 3), t, round(a - t, 3)])

    print(f"{'driver':<7}{'day':<12}{'before':>9}{'after':>9}{'expected':>10}")
    for k in keys:
        print(f"{k[0]:<7}{k[1]:<12}{old.get(k, 0):>9.2f}{new.get(k, 0):>9.2f}{truth.get(k, 0):>10.2f}")
    tb, ta, tt = sum(old.values()), sum(new.values()), sum(truth.values())
    print(f"{'TOTAL':<19}{tb:>9.2f}{ta:>9.2f}{tt:>10.2f}")
    print("\nWritten: results/before_after.csv")


if __name__ == "__main__":
    main(*sys.argv[1:])
