"""Shared geometry helpers and the case configuration.

SYNTHETIC: the zone and road below are invented for this Quest.
They are placed near Seoul only so that UTC+9 is a natural local time.
"""
import math

EARTH_RADIUS_M = 6_371_000

# Campaign zone: a simple rectangle (assumption, the case does not define a shape)
ZONE = {"lat_min": 37.4950, "lat_max": 37.5150, "lon_min": 127.0200, "lon_max": 127.0500}

# Road path: a synthetic loop that runs through the zone and leaves it on the east side
ROAD = [
    (37.5000, 127.0100),  # west, outside zone
    (37.5000, 127.0300),  # inside
    (37.5100, 127.0300),  # inside
    (37.5100, 127.0450),  # inside
    (37.5050, 127.0600),  # east, outside zone
    (37.4980, 127.0600),  # outside
    (37.4980, 127.0400),  # back inside
    (37.5000, 127.0100),  # close the loop (west, outside)
]

NOISE_MAX_OFF_ROAD_M = 100
NOISE_MAX_SPEED_KMH = 150
LOCAL_UTC_OFFSET_HOURS = 9
PING_INTERVAL_S = 10


def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _to_xy(lat, lon, lat0):
    """Local flat projection in metres (fine at city scale)."""
    x = math.radians(lon) * EARTH_RADIUS_M * math.cos(math.radians(lat0))
    y = math.radians(lat) * EARTH_RADIUS_M
    return x, y


def distance_to_road_m(lat, lon, road=ROAD):
    """Shortest distance in metres from a point to the road polyline."""
    lat0 = road[0][0]
    px, py = _to_xy(lat, lon, lat0)
    best = float("inf")
    for (alat, alon), (blat, blon) in zip(road, road[1:]):
        ax, ay = _to_xy(alat, alon, lat0)
        bx, by = _to_xy(blat, blon, lat0)
        dx, dy = bx - ax, by - ay
        seg2 = dx * dx + dy * dy
        t = 0 if seg2 == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / seg2))
        cx, cy = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(px - cx, py - cy))
    return best


def in_zone(lat, lon, zone=ZONE):
    return zone["lat_min"] <= lat <= zone["lat_max"] and zone["lon_min"] <= lon <= zone["lon_max"]


def road_length_m(road=ROAD):
    return sum(haversine_m(*a, *b) for a, b in zip(road, road[1:]))


def point_along_road(dist_m, road=ROAD):
    """Point at dist_m metres along the road loop (wraps around)."""
    total = road_length_m(road)
    d = dist_m % total
    for a, b in zip(road, road[1:]):
        seg = haversine_m(*a, *b)
        if d <= seg:
            t = d / seg if seg else 0
            return a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
        d -= seg
    return road[-1]
