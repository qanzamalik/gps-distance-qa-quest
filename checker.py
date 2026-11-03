"""QA checker: makes the distance problems visible.

  1. Finds every rule break in the pings (duplicates, out-of-order, GPS noise, outside zone)
  2. Measures how many km each problem adds, by switching the rules on one at a time
  3. Shows the worst example rows (root cause evidence)
  4. Validates itself against the generator's labels (does the checker catch what was planted?)

Run: python checker.py            -> writes reports/checker_report.md
"""
import csv
import os
import sys

import geo
import rules

STAGES = [
    ("Old calculation (as billed)", {}),
    ("+ remove duplicates", {"dedupe": True}),
    ("+ order by own timestamp", {"dedupe": True, "sort_by_ts": True}),
    ("+ drop GPS noise", {"dedupe": True, "sort_by_ts": True, "drop_noise": True}),
    ("+ count inside zone only", {"dedupe": True, "sort_by_ts": True, "drop_noise": True, "zone_only": True}),
]


def load(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["lat"], r["lon"] = float(r["lat"]), float(r["lon"])
    return rows


def label_check(name, found_ids, rows, labels):
    planted = {r["ping_id"] for r in rows if r["fault_type"] in labels}
    hit = len(found_ids & planted)
    false_alarms = len(found_ids - planted)
    return f"| {name} | {len(planted)} | {hit} | {len(planted) - hit} | {false_alarms} |"


def main(path="data/pings_synthetic.csv"):
    rows = load(path)
    dups = rules.find_duplicates(rows)
    late = rules.find_out_of_order(rows)
    noise = rules.find_noise(rows)
    outside = [r for r in rows if not geo.in_zone(r["lat"], r["lon"])]

    out = ["# Checker report (SYNTHETIC data)", "",
           f"Input: `{path}`, {len(rows)} pings, {len({r['driver_id'] for r in rows})} drivers", "",
           "## 1. Rule breaks found", "",
           "| Problem | Pings |", "|---|---|",
           f"| Duplicate (same driver + timestamp) | {len(dups)} |",
           f"| Arrived out of order | {len(late)} |",
           f"| GPS noise: >100 m off road | {sum('off road' in why for _, why in noise)} |",
           f"| GPS noise: >150 km/h | {sum('km/h' in why for _, why in noise)} |",
           f"| Outside campaign zone | {len(outside)} |", ""]

    # 2. km impact, one rule at a time (all with the old UTC day cut, so stages compare like for like)
    results = [rules.distance_km(rows, **opts) for _, opts in STAGES]
    totals = [sum(r.values()) for r in results]
    out += ["## 2. Where the extra km come from (all drivers, all days)", "",
            "| Step | Total km | Change |", "|---|---|---|"]
    for i, (name, _) in enumerate(STAGES):
        change = "" if i == 0 else f"{totals[i] - totals[i - 1]:+.1f}"
        out.append(f"| {name} | {totals[i]:.1f} | {change} |")
    out += ["", f"Billed km are **{totals[0] / totals[-1]:.1f}x** the km after all rules are applied.", ""]

    # day cut: same km, different days
    utc = rules.distance_km(rows, **STAGES[-1][1])
    local = rules.distance_km(rows, **STAGES[-1][1], local_days=True)
    moved = [(k, utc.get(k, 0), local.get(k, 0)) for k in sorted(set(utc) | set(local))
             if abs(utc.get(k, 0) - local.get(k, 0)) > 0.001]
    out += ["## 3. Day cut-off: UTC vs local (UTC+9)", "",
            "Total km do not change, but these driver-days get the wrong km:", "",
            "| Driver | Day | km (UTC cut) | km (local cut) |", "|---|---|---|---|"]
    out += [f"| {d} | {day} | {a:.2f} | {b:.2f} |" for (d, day), a, b in moved]
    out.append("")

    # 4. root cause evidence: the noise pings that add the most distance
    by_ts = {}
    for r in sorted(rows, key=lambda r: (r["driver_id"], r["ts_utc"])):
        by_ts.setdefault(r["driver_id"], []).append(r)
    examples = []
    for r, why in noise:
        seq = by_ts[r["driver_id"]]
        i = seq.index(r)
        if 0 < i < len(seq) - 1:
            p, n = seq[i - 1], seq[i + 1]
            detour = (geo.haversine_m(p["lat"], p["lon"], r["lat"], r["lon"])
                      + geo.haversine_m(r["lat"], r["lon"], n["lat"], n["lon"])
                      - geo.haversine_m(p["lat"], p["lon"], n["lat"], n["lon"]))
            examples.append((detour, p, r, n, why))
    examples.sort(key=lambda e: -e[0])
    out += ["## 4. Root cause evidence: worst GPS noise pings", "",
            "Each noise ping makes the old calculation drive out to a false point and back.", ""]
    for detour, p, r, n, why in examples[:3]:
        out += [f"**{r['ping_id']}** ({r['driver_id']}, {r['ts_utc']}): {why}, adds **{detour / 1000:.2f} km**", "",
                "| Ping | Time (UTC) | Lat | Lon | Off road |", "|---|---|---|---|---|"]
        for x in (p, r, n):
            out.append(f"| {x['ping_id']} | {x['ts_utc']} | {x['lat']} | {x['lon']} | "
                       f"{geo.distance_to_road_m(x['lat'], x['lon']):.0f} m |")
        out.append("")

    # 5. self-check against planted labels
    out += ["## 5. Checker self-check against the generator's labels", "",
            "| Detector | Planted | Caught | Missed | False alarms |", "|---|---|---|---|---|",
            label_check("Duplicates", {r["ping_id"] for r in dups}, rows, {"duplicate"}),
            label_check("Out of order", {r["ping_id"] for r in late}, rows, {"out_of_order"}),
            label_check("GPS noise", {r["ping_id"] for r, _ in noise}, rows, {"noise_off_road", "noise_speed"}),
            ""]

    os.makedirs("reports", exist_ok=True)
    with open("reports/checker_report.md", "w") as f:
        f.write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main(*sys.argv[1:])
