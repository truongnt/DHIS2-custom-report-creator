"""
Simulated app-preview E2E test.

Builds a config that exactly matches what chart_editor_panel._build_config()
produces when the user selects the Malaria Case Register DE and clicks Preview.
Then calls generate_preview_page → preview_server → screenshots localhost:15432.

PASS criteria per scenario:
  1. Badge div has CSS class 'fixture' (green, not yellow)
  2. Badge text contains "Fixture sample"
  3. renderChartNSample JS does NOT contain the hardcoded demo array [40,55,30
  4. (with dim) JS contains per-species label (e.g. "P. vivax" or "PV")
  5. Screenshot is captured and saved for visual inspection

Run:
  python test_preview_app_sim.py
"""
import sys, time, json, re, subprocess, importlib
from pathlib import Path

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from charts.fixed_templates import generate_preview_page

# ── Malaria Case Register constants (from hmis.gov.la) ───────────────────────
PROG_UID  = "yAKTrPUMAuU"
STAGE_UID = "h86ikuTvjuP"
DE_UID    = "qf5LcIDIXSJ"
DE_NAME   = "Diagnosis Test Result"

MALARIA_OPTIONS = [
    {"code": "PF",    "name": "P. falciparum"},
    {"code": "PV",    "name": "P. vivax"},
    {"code": "PO",    "name": "P. ovale"},
    {"code": "PM",    "name": "P. malariae"},
    {"code": "PK",    "name": "P. knowlesi"},
    {"code": "Mixed", "name": "Mixed"},
]

# ── Dimension DE (what _build_config puts in dimensions.dimension) ───────────
DIM_DE = {
    "uid":       DE_UID,
    "name":      DE_NAME,
    "type":      "tracker_option",
    "prog_uid":  PROG_UID,
    "stage_uid": STAGE_UID,
    "options":   MALARIA_OPTIONS,
}

# ── Helper: build config matching _build_config() output ─────────────────────

def _make_config(with_dimension: bool, stack_mode: str = "Stack") -> dict:
    """
    Mirrors exactly what _build_config() produces.
    Note: metrics fallback does NOT include prog_uid (matches real app behaviour).
    prog_uid is only in source + optionally dimensions.dimension.
    """
    metrics_fallback = [
        # No prog_uid here — matches _build_config line 1549-1552
        {"uid": DE_UID, "name": DE_NAME, "type": "tracker_numeric", "agg": "SUM"}
    ]
    # _build_config() only applies color_base when NO dimension is set.
    # When dimension IS set, custom_options has no dataset color override.
    _user_color = "#3498db"  # default selected color in app
    if not with_dimension:
        custom_options = {"datasets": [{"backgroundColor": _user_color,
                                        "borderColor":     _user_color}]}
    else:
        custom_options = {}

    return {
        "plugin_id":      "bar",
        "plugin_options": {
            "stack_mode":   stack_mode,
            "show_legend":  True,
            "show_values":  True,
            "only_total":   True,
            "color_scheme": "Default",
        },
        "custom_options": custom_options,
        "source": {
            "type":       "tracker_numeric",
            "prog_uid":   PROG_UID,           # _build_config line 1603
            "prog_name":  "Malaria Case Register",
            "stage_uid":  STAGE_UID,
            "stage_name": "Malaria Case Register",
        },
        "metrics": metrics_fallback,
        "dimensions": {
            "time_grain": "Monthly",
            "dimension":  DIM_DE if with_dimension else None,
            "group_by":   [DIM_DE] if with_dimension else [],
            "filters":    [],
            "row_limit":  0,
            "sort_by":    "None",
            "sort_dir":   "Asc",
            "breakdown":  None,
        },
        "template_id":    "ft_bar",
        "template_label": "Bar chart",
        "title":          f"Malaria Cases {'by Species' if with_dimension else '(total)'}",
        "mode":           "chart",
        "col_width":      6,
    }


# ── Check HTML for PASS criteria ──────────────────────────────────────────────

def _check_html(html: str, with_dim: bool) -> list[tuple[bool, str]]:
    results = []

    # 1. Badge has fixture CSS class (green)
    has_fixture_class = 'class="preview-badge fixture"' in html
    results.append((has_fixture_class, "Badge has CSS class 'fixture' (green)"))

    # 2. Badge text contains "Fixture sample"
    has_fixture_text = "Fixture sample" in html
    results.append((has_fixture_text, "Badge text contains 'Fixture sample'"))

    # 3. No hardcoded demo arrays in renderChartNSample
    # Demo arrays always start with [40,55,30 or [30,40,20
    has_demo = bool(re.search(r'\[40,55,30', html))
    results.append((not has_demo, "renderChartNSample does NOT use hardcoded demo arrays"))

    if with_dim:
        # 4. Per-species label present in JS (fixture loaded)
        has_species = "P. vivax" in html or '"PV"' in html
        results.append((has_species, "Species label (P. vivax / PV) found in sample JS"))
        # 5. No single-color override in custom_options (multi-series needs PALETTE)
        has_color_override = '"datasets"' in html and '"backgroundColor":"#3498db"' in html
        results.append((not has_color_override,
                        "custom_options does NOT override all dataset colors (PALETTE preserved)"))

    return results


# ── Start preview server and screenshot ───────────────────────────────────────

def _serve_and_screenshot(html: str, label: str, out_png: Path) -> bool:
    from ui.preview_server import update_preview
    update_preview(html)
    time.sleep(1.5)  # let server settle

    # Try selenium screenshot
    return _selenium_screenshot(out_png)


def _selenium_screenshot(out_png: Path) -> bool:
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
    except ImportError:
        print("    [skip screenshot] selenium not installed")
        return False

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1200,800")
    opts.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=opts)
        driver.get("http://localhost:15432")
        # Wait for canvas to appear (chart rendered)
        try:
            WebDriverWait(driver, 8).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "canvas"))
            )
        except Exception:
            pass
        time.sleep(1.5)  # extra wait for chart.js animation
        driver.save_screenshot(str(out_png))
        driver.quit()
        sz = out_png.stat().st_size if out_png.exists() else 0
        if sz > 10_000:
            print(f"    Screenshot: {out_png} ({sz:,} bytes)")
            return True
        print("    [skip screenshot] screenshot too small")
        return False
    except Exception as e:
        print(f"    [skip screenshot] selenium error: {e}")
        return False


# ── Main test runner ──────────────────────────────────────────────────────────

SCENARIOS = [
    ("A — no dimension, stack=Stack  (single series total)", False, "Stack"),
    ("B — with dimension, stack=Stack (stacked species)",    True,  "Stack"),
    ("C — no dimension, stack=None   (single series total)", False, "None"),
    ("D — with dimension, stack=None (grouped species bars)", True,  "None"),
    ("E — with dimension, stack=Expand (100% species)",      True,  "Expand"),
]

def main():
    fixture_path = Path(f"C:/Temp/test_fixture_{PROG_UID}.json")
    if not fixture_path.exists():
        print(f"ERROR: Fixture not found at {fixture_path}")
        print("Run first: python run_malaria_real_test.py")
        sys.exit(1)

    n_rows = len(json.loads(fixture_path.read_text(encoding="utf-8")).get("rows", []))
    print(f"Fixture: {fixture_path} ({n_rows} rows)\n")

    all_pass = True

    for scenario_label, with_dim, stack_mode in SCENARIOS:
        print(f"{'='*60}")
        print(f"Scenario {scenario_label}")
        print(f"{'='*60}")

        cfg  = _make_config(with_dimension=with_dim, stack_mode=stack_mode)
        html = generate_preview_page(cfg)

        # Check HTML criteria
        checks = _check_html(html, with_dim=with_dim)
        scenario_pass = True
        for ok, desc in checks:
            mark = "PASS" if ok else "FAIL"
            print(f"  [{mark}] {desc}")
            if not ok:
                scenario_pass = False
                all_pass = False

        # Screenshot
        slug = scenario_label.split("—")[0].strip().replace(" ", "_").lower()
        out_png = Path(f"C:/Temp/preview_sim_{slug}.png")
        _serve_and_screenshot(html, scenario_label, out_png)

        print(f"  => Scenario {'PASS' if scenario_pass else 'FAIL'}\n")

    print(f"{'='*60}")
    print(f"OVERALL: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
