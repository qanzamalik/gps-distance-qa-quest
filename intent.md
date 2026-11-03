# Intent — GPS Distance Billing Quest

Author: Qanza Azam
Case: MUST suggested fictional case (assessment rules, not a live MUST product)
Data: 100% SYNTHETIC, generated for this Quest. No real users, drivers or locations.

## Problem
Advertisers pay per kilometre driven inside a campaign zone. Distance is calculated
from GPS pings sent by drivers' phones every 10 seconds. The current reference
calculation does not handle GPS noise, duplicates, out-of-order pings, the local-day
cut-off or the zone boundary, so km per driver per day is wrong. Advertisers can be
over-billed and drivers can be under- or over-credited.

## Goal
Show exactly where and why the distance is wrong, fix the highest-impact problem
first, prove the fix with before/after numbers per driver per day, and lock it in
with a regression test.

## Scope
- 5 synthetic drivers, 3 local days, ~2,500 pings, 1 rectangular campaign zone
- Python + pytest, everything in one public GitHub repo, runnable with 3 commands
- Problem to fix first: GPS noise (point >100 m off the road path, or implied speed
  >150 km/h). Reason: it inflates billed km the most and hits the advertiser directly.
- Other faults (duplicates, out-of-order, UTC vs UTC+9 day cut, outside-zone distance)
  will be detected and measured; fixed too if time allows, otherwise listed as open.

## Success looks like
1. A checker anyone can run that lists every fault type with counts and km impact
2. Root cause shown on real rows from the dataset (which pings, why they are wrong)
3. Before/after km per driver per local day
4. A regression test that FAILS on the old calculation and PASSES on the fixed one
5. An honest list of what is still not solved

## Assumptions (the case does not specify these)
- Road path: a synthetic polyline I define when generating data
- Campaign zone: a rectangle (min/max latitude and longitude)
- Distance between two pings: straight line (haversine)
- Speed is checked against the last VALID ping, not the last raw ping, so one noise
  ping does not cause the next good ping to be rejected
- Duplicate (same driver, same timestamp): keep the first one received
- A segment counts only when both of its pings are inside the zone
- Local day = UTC+9; a ping at 2 Nov 16:00 UTC belongs to the 3 Nov report
- Drivers are credited per km like advertisers are billed (case does not say)

## Out of scope
- Real map matching to actual roads
- Long signal gaps (straight line will under-count curved roads)
- GPS jitter right on the zone boundary
- Any real or confidential data

## How I will use AI
AI will draft the data generator, checker, fix and tests. I will check every output
against the rules above and log what I accepted, changed or rejected in directive.md.

## Effort
Planned: 8 hours over 5 days. Actual effort will be reported in directive.md.
