# Checker report (SYNTHETIC data)

Input: `data/pings_synthetic.csv`, 2775 pings, 5 drivers

## 1. Rule breaks found

| Problem | Pings |
|---|---|
| Duplicate (same driver + timestamp) | 75 |
| Arrived out of order | 103 |
| GPS noise: >100 m off road | 44 |
| GPS noise: >150 km/h | 35 |
| Outside campaign zone | 1128 |

## 2. Where the extra km come from (all drivers, all days)

| Step | Total km | Change |
|---|---|---|
| Old calculation (as billed) | 717.4 |  |
| + remove duplicates | 711.3 | -6.1 |
| + order by own timestamp | 465.1 | -246.2 |
| + drop GPS noise | 268.8 | -196.3 |
| + count inside zone only | 154.9 | -113.9 |

Billed km are **4.6x** the km after all rules are applied.

## 3. Day cut-off: UTC vs local (UTC+9)

Total km do not change, but these driver-days get the wrong km:

| Driver | Day | km (UTC cut) | km (local cut) |
|---|---|---|---|
| D03 | 2026-11-02 | 10.81 | 5.05 |
| D03 | 2026-11-03 | 11.39 | 17.14 |
| D05 | 2026-11-03 | 19.98 | 3.94 |
| D05 | 2026-11-04 | 0.00 | 16.04 |

## 4. Root cause evidence: worst GPS noise pings

Each noise ping makes the old calculation drive out to a false point and back.

**P02272** (D02, 2026-11-04T01:30:20Z): 942 km/h from last valid ping, adds **4.81 km**

| Ping | Time (UTC) | Lat | Lon | Off road |
|---|---|---|---|---|
| P02271 | 2026-11-04T01:30:10Z | 37.510035 | 127.03203 | 4 m |
| P02272 | 2026-11-04T01:30:20Z | 37.502162 | 127.06 | 0 m |
| P02273 | 2026-11-04T01:30:30Z | 37.509995 | 127.034513 | 1 m |

**P00963** (D04, 2026-11-03T00:37:00Z): 922 km/h from last valid ping, adds **4.76 km**

| Ping | Time (UTC) | Lat | Lon | Off road |
|---|---|---|---|---|
| P00962 | 2026-11-03T00:36:50Z | 37.497962 | 127.046952 | 4 m |
| P00963 | 2026-11-03T00:37:00Z | 37.499467 | 127.017993 | 0 m |
| P00964 | 2026-11-03T00:37:10Z | 37.498006 | 127.044928 | 1 m |

**P00838** (D03, 2026-11-02T15:00:20Z): 904 km/h from last valid ping, adds **4.58 km**

| Ping | Time (UTC) | Lat | Lon | Off road |
|---|---|---|---|---|
| P00837 | 2026-11-02T15:00:10Z | 37.497982 | 127.042718 | 2 m |
| P00838 | 2026-11-02T15:00:20Z | 37.49971 | 127.014344 | 0 m |
| P00839 | 2026-11-02T15:00:30Z | 37.497994 | 127.040243 | 1 m |

## 5. Checker self-check against the generator's labels

| Detector | Planted | Caught | Missed | False alarms |
|---|---|---|---|---|
| Duplicates | 75 | 75 | 0 | 0 |
| Out of order | 103 | 103 | 0 | 0 |
| GPS noise | 82 | 81 | 1 | 0 |
