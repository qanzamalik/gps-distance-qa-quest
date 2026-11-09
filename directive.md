# Directive: GPS Distance Billing Quest

Author: Qanza Azam
Repo: https://github.com/qanzamalik/gps-distance-qa-quest
Loom: https://www.loom.com/share/19203059c6184aabbdd1158480e9e064
Case: MUST suggested fictional case (assessment rules, not a live MUST product)
Data: **100% SYNTHETIC**, generated for this Quest. No real users, drivers, locations or incidents.

## Links

| What | Link |
|---|---|
| Plan (written before the work) | [intent.md](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/intent.md) |
| Synthetic data (2,775 pings, labelled) | [data/pings_synthetic.csv](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/data/pings_synthetic.csv) |
| Data generator | [generate_data.py](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/generate_data.py) |
| Old (wrong) calculation | [reference_calc.py](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/reference_calc.py) |
| QA tool (checker) | [checker.py](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/checker.py) |
| Checker report | [reports/checker_report.md](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/reports/checker_report.md) |
| Fix | [fixed_calc.py](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/fixed_calc.py), [rules.py](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/rules.py) |
| Before/after per driver per day | [results/before_after.csv](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/results/before_after.csv) |
| Regression tests | [tests/test_regression.py](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/tests/test_regression.py) |
| Test run on OLD calc (7 fail) | [results/test_old.txt](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/results/test_old.txt) |
| Test run on FIXED calc (8 pass) | [results/test_fixed.txt](https://github.com/qanzamalik/gps-distance-qa-quest/blob/main/results/test_fixed.txt) |

**Reproduce (Python 3.9+):**

```bash
python generate_data.py
python checker.py
python fixed_calc.py
pip install pytest
python run_tests.py old      # expected: 7 failed, 1 passed
python run_tests.py fixed    # expected: 8 passed
```

## 1. Problems found, ranked by impact

The checker switches the case rules on one at a time and measures how many km each one removes (all drivers, 3 days).

| Rank | Problem | Km impact | Who is hurt | How I found it |
|---|---|---|---|---|
| 1 | **Pings summed in arrival order, not by their own timestamp.** Late pings create a zig-zag track. | +246 km billed | Advertiser (overbilled) | Checker counts pings that arrive after a later-timestamped ping (103), then measures km before and after re-ordering |
| 2 | **GPS noise counted as distance.** One false point = a drive out and back. | +195 km billed | Advertiser (overbilled) | Every ping checked for >100 m off the road polyline and for >150 km/h against the last valid ping (82 found). Worst single ping adds 4.8 km |
| 3 | **Distance outside the campaign zone counted.** | +114 km billed | Advertiser (overbilled) | 1,128 pings outside the zone rectangle; km measured with and without the zone rule |
| 4 | **Day cut at 00:00 UTC instead of 00:00 local (UTC+9).** | 0 km in total, but wrong per day | Driver and advertiser (daily reports and payouts wrong) | Checker compares the same km under both day cuts. D05 drove 16 km on 4 Nov local; the old report shows 0 km for that day |
| 5 | **Duplicates counted twice.** | +6 km billed | Advertiser | Same driver and timestamp seen more than once (75) |

**Overall:** the old calculation bills **717.4 km**. The correct figure is **154.9 km**, so advertisers are billed **4.6x** what was actually driven inside the zone.

**Note on ranking:** the impact numbers depend on the order in which the rules are switched on. For example, noise looks smaller once pings are already in the right order. The ranking shows the order the checker applies the rules in, which is also the order the fix needs.

## 2. What I solved first, and why

intent.md planned to start with GPS noise. The checker showed that out-of-order pings were the bigger problem (246 km vs 195 km). Noise detection also only works once pings are in timestamp order, because speed has to be measured between the right neighbours. So I solved **ordering and noise together, as the first fix**. After that I added zone filtering, the local-day cut and de-duplication, so the final calculation applies all five case rules.

## 3. The tool

`checker.py` takes one command and writes `reports/checker_report.md`. The report has five parts:

1. Counts of every rule break
2. The km impact of each rule, applied one at a time
3. Driver-days that land on the wrong day under the UTC cut
4. Root-cause evidence: the worst noise pings, with the rows before and after each one
5. **A self-check against the generator's planted labels**: how many faults the checker caught, missed and raised as false alarms. This is how I verified the tool itself. It does not read the labels for any calculation.

Current self-check: duplicates 75/75, out-of-order 103/103, GPS noise 81/82, 0 false alarms.

## 4. Root cause

The old calculation trusts every ping as it arrives. It has no ordering step, no noise check, no zone check and no local-day cut. It simply sums the straight-line distance between consecutive rows in arrival order.

**Example from the data:** ping P02272 (D02, 04 Nov 01:30:20 UTC) sits 3 km away from its neighbours, which would mean 942 km/h. The old calculation drives out to that point and back, which adds 4.81 km of distance that never happened. More examples are in the checker report, section 4.

## 5. Fix and before/after

`fixed_calc.py` applies the rules in this order:

1. Remove duplicates
2. Sort pings by their own timestamp
3. Drop GPS noise (speed measured against the last valid ping)
4. Count a segment only when both pings are inside the zone
5. Cut days at 00:00 local time

| | Old | Fixed | Expected (from generator) |
|---|---|---|---|
| Total km | 717.4 | 154.9 | 154.8 |

14 of 15 driver-days match the expected value exactly. The one that doesn't (D03, 3 Nov, +0.1 km) is explained in section 7. The full table per driver per day is in `results/before_after.csv`. Biggest single change: D05 on 3 Nov was billed 112.9 km and actually drove 3.9 km.

## 6. Regression check

`tests/test_regression.py` contains 8 hand-built tracks, each with a known answer. There is one test per case rule, plus one for an edge case:

- off-road noise
- too-fast noise
- **noise on the first ping of a trip** (the edge case)
- duplicate with slightly different coordinates
- late ping
- outside zone
- local midnight cut
- a clean baseline

| Run against | Result |
|---|---|
| Old calculation | **7 failed**, 1 passed |
| Fixed calculation | **8 passed** |

The one test that passes on the old code is the clean baseline. It has no faults, and it proves the tests measure fairly.

## 7. What is still not solved

1. **Noise the rules cannot see.** Ping P01319 was planted as noise, but it sits on the road and implies only 58 km/h, so under the case rules it is a valid ping. It adds 0.1 km to D03 on 3 Nov. Catching this would need a stricter rule, such as a heading check or a maximum acceleration.
2. **Straight lines between pings.** Distance is measured as a straight line between pings, so curves and signal gaps longer than 10 s are under-counted. Real map matching would fix this.
3. **Zone boundary.** A segment that crosses the boundary is dropped entirely, which slightly under-counts. Clipping the segment at the boundary would be more exact.
4. **Noise tie-break.** When a ping is too fast, the code keeps whichever explanation leaves the smoother track. Two noise pings in a row could fool it. This is not covered by a test yet.
5. **Assumptions the case does not settle:** which duplicate to keep (I keep the first one received), how drivers are paid, and the zone shape. These need a product decision, not a code change.
6. **Scope.** Everything was verified on synthetic data and one simplified road. Nothing here has been checked against real GPS traces.

## 8. How AI was used, and what I checked, changed or rejected

AI tool: Claude, used to draft the generator, checker, fix and tests. Each draft was run and checked against the case rules and against the checker's self-check. **These AI drafts were wrong and were caught:**

| # | What the AI draft did | How it was caught | What changed |
|---|---|---|---|
| 1 | Made "off-road" noise by shifting latitude only. On the north-south road section, these pings stayed on the road, so they were not noise at all | A verification script showed some "off-road" noise pings 0 m from the road | Noise is now pushed in both directions and re-tried until it is more than 200 m off the road |
| 2 | Speed filter trusted the first ping of a trip. If that ping was noise, the next 3 good pings were rejected | Checker self-check: 4 missed, 5 false alarms | Trip start is now checked against the next two pings. Locked in by a regression test |
| 3 | The first fix for #2 rejected good pings next to a noise ping instead of the noise ping itself | Self-check moved from 79 caught / 2 false alarms to 81 caught / 0 false alarms only after a second change | Keep whichever explanation leaves the smoother track |
| 4 | Out-of-order detector also flagged late duplicates (33 false alarms) | Self-check | Duplicates are removed before the order check |
| 5 | Expected-km file joined the last ping of one trip to the first ping of the next day's trip | Fixed results differed from expected by 1 to 1.7 km on several days, so I investigated the expected values themselves | A trip break (>1 h gap) is now applied to the expected values too |

**What I checked and changed myself:**

- **Changed the plan based on evidence.** intent.md said to fix GPS noise first. When the checker showed out-of-order pings caused more extra km (246 vs 195), and that noise detection depends on correct ordering, I changed the first fix to ordering and noise together, rather than keep the original plan.
- **Repo check before submitting.** I compared the repo against the README and found that `fixed_calc.py`, `run_tests.py` and `README.md` had been uploaded into `tests/` by mistake, and that `tests/test_regression.py` was missing. A reviewer running `python run_tests.py` would have hit an error. I moved the files to the repo root and uploaded the test file to `tests/`. The commit history shows these fixes.

## 9. Effort and what existed before

- **Existing work reused:** none. Everything in the repo was created for this Quest.
- **Actual effort:** about 14 hours, on 3, 4 and 9 November 2026.
- - **Compared with the plan:** intent.md planned 8 hours, and the suggested range was 6–10. The extra time went into verifying the AI's work: building the checker's self-check, tracing the five AI mistakes listed above, and cross-checking the expected values. It also covered fixing the repo structure before submission, and recording the Loom.
- 
