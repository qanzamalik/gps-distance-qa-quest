"""The case rules as small, separate steps, so each one can be switched on and
measured on its own. Used by checker.py (to measure impact) and fixed_calc.py.
None of these functions read the generator's `fault_type` label."""
from datetime import datetime, timedelta, timezone

import geo

SESSION_GAP_S = 3600  # pings more than 1 hour apart belong to different trips
LOCAL_TZ = timezone(timedelta(hours=geo.LOCAL_UTC_OFFSET_HOURS))


def secs(iso_ts):
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).timestamp()


def utc_day(iso_ts):
    return iso_ts[:10]


def local_day(iso_ts):
    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).astimezone(LOCAL_TZ).date().isoformat()


# ---------- detectors (return the rows that break a rule, with a reason) ----------

def find_duplicates(rows):
    """Same driver + same timestamp: every copy after the first received is a duplicate."""
    seen, dups = set(), []
    for r in sorted(rows, key=lambda r: r["received_at_utc"]):
        key = (r["driver_id"], r["ts_utc"])
        if key in seen:
            dups.append(r)
        seen.add(key)
    return dups


def find_out_of_order(rows):
    """A ping that arrives after a later-timestamped ping from the same driver.
    Duplicates are excluded first, otherwise a late duplicate is counted twice."""
    dup_ids = {id(r) for r in find_duplicates(rows)}
    latest, late = {}, []
    for r in sorted((r for r in rows if id(r) not in dup_ids), key=lambda r: r["received_at_utc"]):
        d = r["driver_id"]
        if d in latest and r["ts_utc"] < latest[d]:
            late.append(r)
        latest[d] = max(latest.get(d, r["ts_utc"]), r["ts_utc"])
    return late


def kmh(a, b):
    dt = secs(b["ts_utc"]) - secs(a["ts_utc"])
    if dt <= 0:
        return 0.0
    return geo.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) / dt * 3.6


def same_trip(a, b):
    return a["driver_id"] == b["driver_id"] and abs(secs(b["ts_utc"]) - secs(a["ts_utc"])) <= SESSION_GAP_S


def find_noise(rows):
    """GPS noise: >100 m from the road, or implied speed >150 km/h.

    Speed is measured against the last VALID ping, not the last raw ping.
    Two edge cases found by the checker's self-check (v1 got these wrong):
      - Trip start: if the FIRST ping is noise there is nothing before it to compare
        with, so it is checked against the next two pings instead.
      - Accepted outlier: if a new ping is too fast from the last valid ping but fits
        the valid ping before that, the last valid ping was the outlier. It is
        reclassified as noise and the new ping is kept.
    """
    seq = [r for r in sorted(rows, key=lambda r: (r["driver_id"], r["ts_utc"]))]
    noise, flagged, valid = [], set(), []
    for i, r in enumerate(seq):
        off_road = geo.distance_to_road_m(r["lat"], r["lon"])
        if off_road > geo.NOISE_MAX_OFF_ROAD_M:
            noise.append((r, f"{off_road:.0f} m off road"))
            flagged.add(id(r))
            continue
        if valid and not same_trip(valid[-1], r):
            valid = []
        if not valid:
            ahead = [x for x in seq[i + 1:i + 6] if same_trip(r, x)
                     and geo.distance_to_road_m(x["lat"], x["lon"]) <= geo.NOISE_MAX_OFF_ROAD_M][:2]
            if len(ahead) == 2 and kmh(r, ahead[0]) > geo.NOISE_MAX_SPEED_KMH \
                    and kmh(ahead[0], ahead[1]) <= geo.NOISE_MAX_SPEED_KMH:
                noise.append((r, f"{kmh(r, ahead[0]):.0f} km/h to next ping (trip start)"))
                flagged.add(id(r))
                continue
            valid.append(r)
            continue
        v = kmh(valid[-1], r)
        nxt = next((x for x in seq[i + 1:i + 6] if same_trip(r, x)
                    and geo.distance_to_road_m(x["lat"], x["lon"]) <= geo.NOISE_MAX_OFF_ROAD_M), None)
        if v <= geo.NOISE_MAX_SPEED_KMH:
            valid.append(r)
            continue
        # Too fast. Either the new ping (A) or the last accepted ping (B) is the outlier.
        # Pick the explanation that leaves the smoother track (lower worst speed).
        inf = float("inf")
        worst_a = kmh(valid[-1], nxt) if nxt else inf
        worst_b = max(kmh(valid[-2], r), kmh(r, nxt) if nxt else 0) if len(valid) >= 2 else inf
        if worst_a <= geo.NOISE_MAX_SPEED_KMH and worst_a <= worst_b:
            noise.append((r, f"{v:.0f} km/h from last valid ping"))
            flagged.add(id(r))
        elif worst_b <= geo.NOISE_MAX_SPEED_KMH:
            outlier = valid.pop()
            noise.append((outlier, "disagrees with pings before and after it"))
            flagged.add(id(outlier))
            valid.append(r)
        else:
            noise.append((r, f"{v:.0f} km/h from last valid ping"))
            flagged.add(id(r))
    return noise


# ---------- the calculation, with each rule as a switch ----------

def distance_km(rows, *, dedupe=False, sort_by_ts=False, drop_noise=False,
                zone_only=False, local_days=False):
    if dedupe:
        dup_ids = {id(r) for r in find_duplicates(rows)}
        rows = [r for r in rows if id(r) not in dup_ids]
    if drop_noise:
        noise_ids = {id(r) for r, _ in find_noise(rows)}
        rows = [r for r in rows if id(r) not in noise_ids]
    order = "ts_utc" if sort_by_ts else "received_at_utc"
    rows = sorted(rows, key=lambda r: (r["driver_id"], r[order]))
    day_of = local_day if local_days else utc_day

    totals = {}
    for a, b in zip(rows, rows[1:]):
        if a["driver_id"] != b["driver_id"]:
            continue
        if abs(secs(b[order]) - secs(a[order])) > SESSION_GAP_S:
            continue
        if zone_only and not (geo.in_zone(a["lat"], a["lon"]) and geo.in_zone(b["lat"], b["lon"])):
            continue
        key = (a["driver_id"], day_of(a["ts_utc"]))
        totals[key] = totals.get(key, 0) + geo.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
    return {k: v / 1000 for k, v in totals.items()}
