# GPS Distance Billing — QA Quest

> **All data in this repo is SYNTHETIC**, generated for the MUST hiring Quest
> (fictional case: assessment rules, not a live MUST product). No real drivers,
> users or locations.

## Run it (Python 3.9+, no extra packages)

```bash
python generate_data.py     # creates data/pings_synthetic.csv (~2,775 pings) + truth file
python reference_calc.py    # OLD calculation (wrong on purpose) -> km per driver per day
python checker.py           # QA checker -> reports/checker_report.md
python fixed_calc.py        # FIXED calculation -> results/before_after.csv

pip install pytest
python run_tests.py old     # regression tests on OLD calc  -> expected to FAIL
python run_tests.py fixed   # regression tests on FIXED calc -> expected to PASS
```

## Files

| File | What it is |
|---|---|
| `geo.py` | Zone, road path, rules (100 m / 150 km/h / UTC+9) and geometry helpers |
| `generate_data.py` | Seeded synthetic data with labelled faults |
| `reference_calc.py` | The old, wrong calculation under test |
| `rules.py` | Each case rule as a separate step (dedupe, order, noise, zone, local day) |
| `checker.py` | QA tool: finds rule breaks, measures km impact of each, shows root-cause rows, self-checks against labels |
| `reports/checker_report.md` | Latest checker output |
| `fixed_calc.py` | Corrected calculation + before/after per driver per day |
| `tests/test_regression.py` | 8 regression checks on hand-built tracks with known answers |
| `run_tests.py` | Runs the same tests against `old` or `fixed` and saves the output |
| `results/` | `before_after.csv`, `test_old.txt` (7 fail), `test_fixed.txt` (8 pass) |
| `data/pings_synthetic.csv` | Pings in arrival order; `fault_type` is the generator's label |
| `data/truth_km_synthetic.csv` | Expected in-zone km per driver per local day |

`fault_type` exists only to validate the checker. No billing calculation reads it.
