"""Run the regression tests against the old or the fixed calculation.

    python run_tests.py old     # expected: tests FAIL (the old bugs are caught)
    python run_tests.py fixed   # expected: all tests PASS

Saves the output to results/test_<calc>.txt so it can be linked as evidence.
Needs: pip install pytest
"""
import os
import subprocess
import sys

calc = sys.argv[1] if len(sys.argv) > 1 else "fixed"
os.makedirs("results", exist_ok=True)
env = dict(os.environ, CALC=calc)
proc = subprocess.run([sys.executable, "-m", "pytest", "tests", "-v", "--no-header", "-p", "no:cacheprovider"],
                      env=env, capture_output=True, text=True)
output = f"Calculation under test: {calc}\n\n" + proc.stdout + proc.stderr
with open(f"results/test_{calc}.txt", "w") as f:
    f.write(output)
print(output)
sys.exit(proc.returncode)
