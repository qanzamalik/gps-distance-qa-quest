"""Regression checks. Small hand-built SYNTHETIC tracks with a known answer.

The same tests run against either calculation:
    python run_tests.py fixed   -> all must PASS
    python run_tests.py old     -> they must FAIL (proves the tests catch the old bugs)
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo  # noqa: E402
import fixed_calc  # noqa: E402
import reference_calc  # noqa: E402

CALC = os.environ.get("CALC", "fixed")
calculate = reference_calc.old_distance_km if CALC == "old" else fixed_calc.fixed_distance_km

STEP_LAT = 0.001  # ~111 m per ping = 40 km/h, on the north-south road section inside the zone
LON = 127.0300
START = datetime(2026, 11, 3, 3, 0, 0, tzinfo=timezone.utc)  # 12:00 local, same day in UTC and UTC+9
TOL_KM = 0.01


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def track(n=10, start=START, lat0=37.5000, delay_s=1):
    """n clean pings, 10 s apart, driving north on the road inside the zone."""
    rows = []
    for i in range(n):
        ts = start + timedelta(seconds=10 * i)
        rows.append({"ping_id": f"T{i:02d}", "driver_id": "TEST", "ts_utc": iso(ts),
                     "lat": round(lat0 + i * STEP_LAT, 6), "lon": LON,
                     "received_at_utc": iso(ts + timedelta(seconds=delay_s))})
    return rows


def expected_km(rows):
    return sum(geo.haversine_m(a["lat"], a["lon"], b["lat"], b["lon"]) for a, b in zip(rows, rows[1:])) / 1000


def total(result):
    return sum(result.values())


CLEAN = track()
EXPECTED = expected_km(CLEAN)  # ~1.0 km


def test_clean_track_baseline():
    assert total(calculate(CLEAN)) == pytest.approx(EXPECTED, abs=TOL_KM)


def test_gps_noise_off_road_is_ignored():
    rows = [dict(r) for r in CLEAN]
    rows[4]["lon"] = 127.0400  # ~880 m east of the road
    assert total(calculate(rows)) == pytest.approx(expected_km(CLEAN[:4] + CLEAN[5:]), abs=TOL_KM)


def test_gps_noise_too_fast_is_ignored():
    rows = [dict(r) for r in CLEAN]
    rows[4]["lat"] = 37.5090  # on the road but 500 m ahead in 10 s = 180 km/h
    assert total(calculate(rows)) == pytest.approx(expected_km(CLEAN[:4] + CLEAN[5:]), abs=TOL_KM)


def test_noise_on_first_ping_does_not_reject_good_pings():
    # Edge case found by the checker: v1 trusted a bad first ping and dropped the good ones after it
    rows = [dict(r) for r in CLEAN]
    rows[0]["lat"] = 37.5080  # first ping 800 m ahead of the real start
    assert total(calculate(rows)) == pytest.approx(expected_km(CLEAN[1:]), abs=TOL_KM)


def test_duplicate_counts_once():
    rows = [dict(r) for r in CLEAN]
    dup = dict(rows[5])
    dup["lat"] = round(dup["lat"] + 0.00009, 6)  # same timestamp, slightly different reading
    dup["received_at_utc"] = iso(START + timedelta(seconds=95))  # arrives after later pings
    rows.append(dup)
    assert total(calculate(rows)) == pytest.approx(EXPECTED, abs=TOL_KM)


def test_late_ping_is_placed_by_its_own_timestamp():
    rows = [dict(r) for r in CLEAN]
    rows[3]["received_at_utc"] = iso(START + timedelta(seconds=200))  # arrives last
    assert total(calculate(rows)) == pytest.approx(EXPECTED, abs=TOL_KM)


def test_distance_outside_zone_is_not_counted():
    inside = track(n=6, lat0=37.5050)
    outside = track(n=6, lat0=37.4800, start=START + timedelta(minutes=5))  # south of the zone
    outside = [dict(r, lon=127.0100) for r in outside]
    assert total(calculate(inside + outside)) == pytest.approx(expected_km(inside), abs=TOL_KM)


def test_day_is_cut_at_local_midnight():
    # 23:59:20 local -> 00:00:50 local on 3-4 Nov (14:59:20Z -> 15:00:50Z, all on 3 Nov in UTC)
    rows = track(n=10, start=datetime(2026, 11, 3, 14, 59, 20, tzinfo=timezone.utc))
    result = calculate(rows)
    before_midnight = expected_km(rows[:5])  # segments starting 23:59:20 .. 23:59:50 local
    assert result.get(("TEST", "2026-11-03"), 0) == pytest.approx(before_midnight, abs=TOL_KM)
    assert result.get(("TEST", "2026-11-04"), 0) == pytest.approx(EXPECTED - before_midnight, abs=TOL_KM)
