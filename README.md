# GPS Distance Billing — QA Quest

> **All data in this repo is SYNTHETIC**, generated for the MUST hiring Quest
> (fictional case: assessment rules, not a live MUST product). No real drivers,
> users or locations.

## Run it (Python 3.9+, no extra packages)

```bash
python generate_data.py     # creates data/pings_synthetic.csv (~2,775 pings) + truth file
python reference_calc.py    # OLD calculation (wrong on purpose) -> km per driver per day
```

## Files

| File | What it is |
|---|---|
| `geo.py` | Zone, road path, rules (100 m / 150 km/h / UTC+9) and geometry helpers |
| `generate_data.py` | Seeded synthetic data with labelled faults |
| `reference_calc.py` | The old, wrong calculation under test |
| `data/pings_synthetic.csv` | Pings in arrival order; `fault_type` is the generator's label |
| `data/truth_km_synthetic.csv` | Expected in-zone km per driver per local day |

`fault_type` exists only to validate the checker. No billing calculation reads it.
