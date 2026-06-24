"""Run all plugin checklist tests sequentially and report PASS/FAIL summary."""
import subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).parent

TESTS = [
    ("bar",           "test_bar_checklist.py",       "C:/Temp/bar_checks"),
    ("line_trend",    "test_line_trend_checklist.py", "C:/Temp/line_trend_checks"),
    ("line_multi",    "test_line_multi_checklist.py", "C:/Temp/line_multi_checks"),
    ("pie_cat",       "test_pie_checklist.py",        "C:/Temp/pie_checks"),
    ("scorecard",     "test_scorecard_checklist.py",  "C:/Temp/scorecard_checks"),
    ("combined",      "test_combined_checklist.py",   "C:/Temp/combined_checks"),
    ("table_view",    "test_table_checklist.py",      "C:/Temp/table_checks"),
]

results = []
for name, script, crop_dir in TESTS:
    print(f"\n{'='*60}")
    print(f"  Running: {script}")
    print(f"{'='*60}")
    t0 = time.time()
    r = subprocess.run(
        [sys.executable, script],
        cwd=str(REPO),
        capture_output=False,   # show live output
    )
    elapsed = time.time() - t0
    status = "OK" if r.returncode == 0 else "FAIL"
    n_imgs = len(list(Path(crop_dir).glob("*.png"))) if Path(crop_dir).exists() else 0
    results.append((name, script, status, n_imgs, elapsed))
    if r.returncode != 0:
        print(f"\n!!! {script} FAILED (exit {r.returncode})")

print(f"\n\n{'='*60}")
print("  SUMMARY")
print(f"{'='*60}")
for name, script, status, n_imgs, elapsed in results:
    mark = "✓" if status == "OK" else "✗"
    print(f"  {mark} {name:16s}  {status}   {n_imgs:3d} images   {elapsed:.0f}s")
