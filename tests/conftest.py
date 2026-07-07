"""
Shared pytest fixtures — see docs/TESTING_PROCESS.md.

Key fixture: `render_preview` (E2E tier). It renders the app's real preview HTML in a
headless browser and returns OBSERVABLE evidence — console logs, screenshot, canvas size —
so a test can prove the chart actually renders (not just that the HTML string contains text).

Offline: Chart.js / datalabels are vendored in tests/assets/ and swapped in for the CDN URLs;
Bootstrap/Leaflet CDN tags are neutralised so no network is required.
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Qt integration tests run headless (no display) — must be set before any QApplication.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_ASSETS = REPO / "tests" / "assets"

# ── Requirement traceability state (filled during the run) ───────────────────
_EVIDENCE_DIR: Path | None = None
_REQ_RESULTS: dict[str, list[tuple[str, str]]] = {}   # req_id -> [(nodeid, outcome)]
_REQ_RE = re.compile(r"REQ-(?:[A-Z]+-)*[A-Z]+-\d+(?:/\d+)*")


def _extract_reqs(text: str) -> set[str]:
    """Pull REQ-IDs from a docstring, expanding shorthand 'REQ-DESC-01/02/04'."""
    out: set[str] = set()
    for m in _REQ_RE.finditer(text or ""):
        tok = m.group(0)
        parts = tok.split("/")
        base = parts[0]                       # REQ-DESC-01
        prefix = base.rsplit("-", 1)[0]       # REQ-DESC
        out.add(base)
        for extra in parts[1:]:               # '02', '04'
            out.add(f"{prefix}-{extra}")
    return out


# ── Evidence directory (one per test session) ───────────────────────────────

def pytest_sessionstart(session):
    global _EVIDENCE_DIR
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _EVIDENCE_DIR = REPO / "test-evidence" / ts
    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def evidence_dir() -> Path:
    """test-evidence/<timestamp>/ — screenshots, console logs, rendered HTML, report."""
    print(f"\n[evidence] {_EVIDENCE_DIR}")
    return _EVIDENCE_DIR


# ── HTML localisation (CDN → vendored / neutralised) ─────────────────────────

def _localize(html: str) -> str:
    """Swap CDN script/style refs so the page renders headless & offline."""
    chart = (_ASSETS / "chart.umd.min.js").as_uri()
    labels = (_ASSETS / "chartjs-datalabels.min.js").as_uri()
    repl = {
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js": chart,
        "https://cdn.jsdelivr.net/npm/chartjs-plugin-datalabels@2.2.0/dist/chartjs-plugin-datalabels.min.js": labels,
        # Neutralise libs we don't need for canvas assertions (avoid network):
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css": "data:text/css,",
        "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js": "data:text/javascript,",
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css": "data:text/css,",
        "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js": "data:text/javascript,",
    }
    for src, dst in repl.items():
        html = html.replace(src, dst)
    return html


# ── Selenium driver (session-scoped; skips E2E if unavailable) ───────────────

@pytest.fixture(scope="session")
def _chrome_driver():
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
    except Exception as exc:
        pytest.skip(f"selenium not available: {exc}")

    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1100,800")
    # Capture browser console (JS errors land here at level SEVERE)
    opts.set_capability("goog:loggingPrefs", {"browser": "ALL"})

    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as exc:
        pytest.skip(f"Chrome/Selenium could not start: {exc}")

    yield driver
    driver.quit()


# ── render_preview: the E2E evidence engine ──────────────────────────────────

@pytest.fixture
def render_preview(_chrome_driver, evidence_dir):
    """
    Return render(html, name) → dict with observable evidence:
      { "console": [...], "severe": [...], "screenshot": Path,
        "html_path": Path, "canvas_present": bool, "canvas_size": (w,h) }
    """
    from selenium.webdriver.support.ui import WebDriverWait

    def render(html: str, name: str) -> dict:
        html_path = evidence_dir / f"{name}.html"
        html_path.write_text(_localize(html), encoding="utf-8")

        driver = _chrome_driver
        driver.get(html_path.as_uri())

        # Wait until the card finished initialising (loading spinner gone) — works for
        # canvas charts, tables and scorecards alike.
        def _ready(d):
            return d.execute_script(
                "var l=document.getElementById('loading1');"
                "return !!l && l.style.display==='none';"
            )
        try:
            WebDriverWait(driver, 12).until(_ready)
        except Exception:
            pass  # let assertions below report what actually rendered

        import time as _t
        _t.sleep(0.7)   # let Chart.js entry animation finish before the screenshot

        probe = driver.execute_script(
            "var c=document.getElementById('chart1');"
            "var err=document.getElementById('error1');"
            "return {canvas: c?[c.width,c.height]:null,"
            " has_table: !!document.querySelector('table'),"
            " text_len: (document.body.innerText||'').trim().length,"
            " err_shown: !!(err && err.style.display!=='none' && err.textContent),"
            " err_text: err?err.textContent:''};"
        )
        shot = evidence_dir / f"{name}.png"
        driver.save_screenshot(str(shot))

        logs = driver.get_log("browser")
        severe = [e for e in logs if e.get("level") == "SEVERE"]

        # Persist console log as evidence
        (evidence_dir / f"{name}.console.log").write_text(
            "\n".join(f"[{e.get('level')}] {e.get('message','')}" for e in logs),
            encoding="utf-8",
        )
        canvas = probe.get("canvas")
        return {
            "console": logs,
            "severe": severe,
            "screenshot": shot,
            "html_path": html_path,
            "driver": driver,          # page stays loaded → tests can probe further
            "canvas_present": canvas is not None,
            "canvas_size": tuple(canvas) if canvas else (0, 0),
            "has_table": probe.get("has_table", False),
            "text_len": probe.get("text_len", 0),
            "err_shown": probe.get("err_shown", False),
            "err_text": probe.get("err_text", ""),
        }

    return render


# ── Map E2E: serve via preview_server (so /api/geoFeatures resolves) ─────────
# Maps need Leaflet + geoFeatures over HTTP (file:// can't reach /api/*).
# We serve the page through the real preview_server and inline Leaflet (data: URI)
# so the test runs offline and same-origin.

def _inline_leaflet(html: str) -> str:
    import base64
    js = (_ASSETS / "leaflet.js").read_bytes()
    css = (_ASSETS / "leaflet.css").read_bytes()
    js_uri = "data:text/javascript;base64," + base64.b64encode(js).decode()
    css_uri = "data:text/css;base64," + base64.b64encode(css).decode()
    return (html
            .replace("https://unpkg.com/leaflet@1.9.4/dist/leaflet.js", js_uri)
            .replace("https://unpkg.com/leaflet@1.9.4/dist/leaflet.css", css_uri))


_TEST_PORT = 15555   # dedicated — avoid colliding with a running app on 15432


def _serve_http(html: str) -> str:
    """Serve html via preview_server on a dedicated test port (no browser popup).

    Verifies OUR server is the one answering (guards against a stale app instance
    holding the port → which would silently serve the wrong page = false pass).
    """
    import hashlib
    import threading
    import time
    import urllib.request
    import ui.preview_server as ps

    ps.PORT = _TEST_PORT
    ps._html_content = html
    ps._html_version = hashlib.md5(html.encode()).hexdigest()[:8]
    if not ps._server_started:
        ps._server_started = True
        threading.Thread(target=ps._start_server, daemon=True).start()

    # Poll until OUR server answers with OUR version (robust to slow bind under load,
    # and guards against a stale app instance holding the port).
    url = f"http://localhost:{_TEST_PORT}/"
    deadline = time.monotonic() + 10
    last = None
    while time.monotonic() < deadline:
        try:
            last = urllib.request.urlopen(url + "version", timeout=2).read().decode()
            if last == ps._html_version:
                return url
        except Exception as exc:
            last = repr(exc)
        time.sleep(0.2)
    raise RuntimeError(
        f"preview_server on port {_TEST_PORT} not ready/correct (last={last!r}, "
        f"expected {ps._html_version!r})")


@pytest.fixture
def render_map_preview(_chrome_driver, evidence_dir):
    """render(html, name) for Leaflet maps → evidence dict (leaflet present, polygon
    path count, error banner text, screenshot, console)."""
    from selenium.webdriver.support.ui import WebDriverWait

    def render(html: str, name: str) -> dict:
        url = _serve_http(_inline_leaflet(html))
        (evidence_dir / f"{name}.html").write_text(html, encoding="utf-8")
        driver = _chrome_driver
        driver.get(url)
        try:
            WebDriverWait(driver, 15).until(lambda d: d.execute_script(
                "var l=document.getElementById('loading1');"
                "return !!l && l.style.display==='none';"))
        except Exception:
            pass
        import time as _t
        _t.sleep(0.8)   # let Leaflet finish layers/labels (permanent tooltips) after fitBounds

        probe = driver.execute_script(
            "var err=document.getElementById('error1');"
            "var lc=document.querySelector('.leaflet-container');"
            "var r=lc?lc.getBoundingClientRect():null;"
            "return {err_shown: !!(err && err.style.display==='block'),"
            " err_text: err?err.textContent:'',"
            " leaflet: !!lc, w:r?r.width:0, h:r?r.height:0,"
            " polygons: document.querySelectorAll('.leaflet-overlay-pane path').length};"
        )
        shot = evidence_dir / f"{name}.png"
        driver.save_screenshot(str(shot))
        logs = driver.get_log("browser")
        severe = [e for e in logs
                  if e.get("level") == "SEVERE"
                  and "favicon" not in (e.get("message") or "").lower()
                  and "/__dbg" not in (e.get("message") or "")
                  and "/version" not in (e.get("message") or "")]
        (evidence_dir / f"{name}.console.log").write_text(
            "\n".join(f"[{e.get('level')}] {e.get('message','')}" for e in logs),
            encoding="utf-8")
        probe.update({"screenshot": shot, "severe": severe, "console": logs,
                      "driver": driver})   # page stays loaded → tests can probe further
        return probe

    return render


# ── Requirement traceability: REQ → test result → evidence ───────────────────

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "req(*ids): requirement IDs this test verifies (in addition to docstring)")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    reqs = _extract_reqs(item.obj.__doc__ or "")
    marker = item.get_closest_marker("req")
    if marker:
        reqs |= set(marker.args)
    for rid in reqs:
        _REQ_RESULTS.setdefault(rid, []).append((item.nodeid, rep.outcome))


def _master_reqs() -> set[str]:
    """Every REQ-ID declared in docs/ + CLAUDE.md = the requirements that need scenarios."""
    out: set[str] = set()
    sources = list((REPO / "docs").rglob("*.md")) + [REPO / "CLAUDE.md"]
    for p in sources:
        try:
            out |= _extract_reqs(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return out


def pytest_sessionfinish(session, exitstatus):
    if _EVIDENCE_DIR is None:
        return
    master = _master_reqs()
    tested = set(_REQ_RESULTS)
    all_reqs = sorted(master | tested)

    def status(rid: str) -> str:
        res = _REQ_RESULTS.get(rid)
        if not res:
            return "GAP"          # requirement has no scenario yet
        if any(o == "failed" for _, o in res):
            return "FAIL"
        if all(o == "passed" for _, o in res):
            return "PASS"
        return "OTHER"

    rows = [(rid, status(rid)) for rid in all_reqs]
    n_pass = sum(1 for _, s in rows if s == "PASS")
    n_fail = sum(1 for _, s in rows if s == "FAIL")
    n_gap  = sum(1 for _, s in rows if s == "GAP")

    lines = [
        "# Requirement Traceability Report",
        "",
        f"- Total REQ (docs ∪ tested): **{len(all_reqs)}**",
        f"- ✅ PASS: **{n_pass}**  ·  ❌ FAIL: **{n_fail}**  ·  ⚠️ GAP (no scenario): **{n_gap}**",
        f"- Evidence dir: `{_EVIDENCE_DIR}`",
        "",
        "| REQ | Status | Test(s) / note |",
        "|---|---|---|",
    ]
    sym = {"PASS": "✅", "FAIL": "❌", "GAP": "⚠️", "OTHER": "❓"}
    for rid, st in rows:
        res = _REQ_RESULTS.get(rid)
        note = "; ".join(f"{n} ({o})" for n, o in res) if res else "no scenario yet"
        lines.append(f"| {rid} | {sym.get(st,'')} {st} | {note} |")

    report = _EVIDENCE_DIR / "traceability.md"
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[traceability] {report}")
    print(f"[traceability] PASS={n_pass} FAIL={n_fail} GAP={n_gap} of {len(all_reqs)} REQ")
