"""Generate a SYNTHETIC, labelled GPS ping dataset for the MUST Quest.

Every row is invented. Faults are injected on purpose and labelled in `fault_type`
so the checker can be validated. The billing calculations must NOT read that column.

Outputs:
  data/pings_synthetic.csv   - all pings (with faults), in arrival order
  data/truth_km_synthetic.csv - expected in-zone km per driver per local day,
                                computed from the clean pings only

Run: python generate_data.py
"""
import csv
import random
from datetime import datetime, timedelta, timezone

import geo

SEED = 42
DRIVERS = ["D01", "D02", "D03", "D04", "D05"]
LOCAL_DAYS = ["2026-11-02", "2026-11-03", "2026-11-04"]
PINGS_PER_TRIP = 180  # 30 minutes at one ping every 10 s
MIDNIGHT_TRIPS = {("D03", "2026-11-02"), ("D05", "2026-11-03")}  # start 23:45 local

RATE_NOISE_OFF_ROAD = 0.015
RATE_NOISE_SPEED = 0.015
RATE_DUPLICATE = 0.03
RATE_OUT_OF_ORDER = 0.04

LOCAL_TZ = timezone(timedelta(hours=geo.LOCAL_UTC_OFFSET_HOURS))


def iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_trip(rng, driver, local_day):
    if (driver, local_day) in MIDNIGHT_TRIPS:
        start_local = datetime.fromisoformat(local_day + "T23:45:00").replace(tzinfo=LOCAL_TZ)
    else:
        start_local = datetime.fromisoformat(local_day + "T08:00:00").replace(tzinfo=LOCAL_TZ)
        start_local += timedelta(minutes=rng.randint(0, 12 * 60))

    pos_m = rng.uniform(0, geo.road_length_m())
    stop_left = 0
    rows = []
    for i in range(PINGS_PER_TRIP):
        ts = start_local + timedelta(seconds=i * geo.PING_INTERVAL_S)
        if stop_left == 0 and rng.random() < 0.02:
            stop_left = 6  # traffic light: one minute stopped
        if stop_left:
            stop_left -= 1
        elif i:
            pos_m += rng.uniform(20, 60) / 3.6 * geo.PING_INTERVAL_S
        lat, lon = geo.point_along_road(pos_m)
        lat += rng.gauss(0, 0.00002)  # ~2 m normal GPS jitter
        lon += rng.gauss(0, 0.00002)
        rows.append({
            "driver_id": driver,
            "ts_utc": iso(ts),
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "received_at_utc": iso(ts + timedelta(seconds=rng.randint(1, 3))),
            "fault_type": "clean",
            "_road_pos_m": pos_m,
        })
    return rows


def inject_faults(rng, rows):
    out = []
    for r in rows:
        roll = rng.random()
        ts = datetime.fromisoformat(r["ts_utc"].replace("Z", "+00:00"))
        if roll < RATE_NOISE_OFF_ROAD:
            # Point thrown 200-1500 m away from the road (retry until it is really off the road)
            while True:
                lat = r["lat"] + rng.choice([-1, 1]) * rng.uniform(0.002, 0.0135)
                lon = r["lon"] + rng.choice([-1, 1]) * rng.uniform(0.002, 0.0135)
                if geo.distance_to_road_m(lat, lon) > 200:
                    break
            r["lat"], r["lon"] = round(lat, 6), round(lon, 6)
            r["fault_type"] = "noise_off_road"
        elif roll < RATE_NOISE_OFF_ROAD + RATE_NOISE_SPEED:
            # Point still on the road but 1.5-3 km ahead: implies 540+ km/h
            lat, lon = geo.point_along_road(r["_road_pos_m"] + rng.uniform(1500, 3000))
            r["lat"], r["lon"] = round(lat, 6), round(lon, 6)
            r["fault_type"] = "noise_speed"
        elif roll < RATE_NOISE_OFF_ROAD + RATE_NOISE_SPEED + RATE_OUT_OF_ORDER:
            # Arrives 30 s to 5 min late, so arrival order is wrong
            r["received_at_utc"] = iso(ts + timedelta(seconds=rng.randint(30, 300)))
            r["fault_type"] = "out_of_order"
        out.append(r)
        if rng.random() < RATE_DUPLICATE and r["fault_type"] == "clean":
            dup = dict(r)
            dup["received_at_utc"] = iso(ts + timedelta(seconds=rng.randint(4, 20)))
            if rng.random() < 0.3:  # some duplicates carry slightly different coordinates
                dup["lat"] = round(dup["lat"] + rng.uniform(-0.0001, 0.0001), 6)
            dup["fault_type"] = "duplicate"
            out.append(dup)
    return out


def local_day(ts_utc):
    ts = datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
    return ts.astimezone(LOCAL_TZ).date().isoformat()


def truth_km(rows):
    """Expected km from clean + out_of_order pings (real readings), by timestamp.
    A segment counts when both pings are inside the zone; it belongs to the
    local day of its starting ping."""
    real = [r for r in rows if r["fault_type"] in ("clean", "out_of_order")]
    real.sort(key=lambda r: (r["driver_id"], r["ts_utc"]))
    totals = {}
    for a, b in zip(real, real[1:]):
        if a["driver_id"] != b["driver_id"]:
            continue
        gap = (datetime.fromisoformat(b["ts_utc"][:-1]) - datetime.fromisoformat(a["ts_utc"][:-1])).total_seconds()
        if gap > 3600:
            continue  # different trips: never join the end of one trip to the start of the next
        if geo.in_zone(a["lat"], a["lon"]) and geo.in_zone(b["lat"], b["lon"]):
            key = (a["driver_id"], local_day(a["ts_utc"]))
            totals[key] = totals.get(key, 0) + geo.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    return totals


def main():
    rng = random.Random(SEED)
    rows = []
    for d in DRIVERS:
        for day in LOCAL_DAYS:
            rows += inject_faults(rng, make_trip(rng, d, day))

    truth = truth_km(rows)
    rows.sort(key=lambda r: r["received_at_utc"])  # file is in ARRIVAL order
    for i, r in enumerate(rows, 1):
        r["ping_id"] = f"P{i:05d}"

    cols = ["ping_id", "driver_id", "ts_utc", "lat", "lon", "received_at_utc", "fault_type"]
    with open("data/pings_synthetic.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    with open("data/truth_km_synthetic.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["driver_id", "local_day", "expected_km"])
        for (d, day), m in sorted(truth.items()):
            w.writerow([d, day, round(m / 1000, 3)])

    counts = {}
    for r in rows:
        counts[r["fault_type"]] = counts.get(r["fault_type"], 0) + 1
    print(f"SYNTHETIC dataset: {len(rows)} pings written to data/pings_synthetic.csv")
    for k, v in sorted(counts.items()):
        print(f"  {k:<16}{v}")


if __name__ == "__main__":
    main()
