"""
Generate a single multi-chart DHIS2 HTML report from a DashboardBuilder layout.

Two modes, chosen automatically:

  MODE A — Template-inject  (cards have template_id with existing HTML)
    Each card's <body> content is extracted from its template and injected into
    the prompt.  The LLM is asked ONLY to:
      1. Fill <!-- INDICATOR_UID --> placeholders with the card's pinned UIDs
      2. Rename canvas/variable IDs to be unique (chart → chart1, chart2 …)
      3. Wrap everything in one Bootstrap-grid page (CDN loaded once)
    This avoids the LLM having to re-invent Chart.js from scratch and is
    much more reliable.

  MODE B — From scratch  (no layout, or prompt-driven without templates)
    The LLM receives the chart-type catalog + metadata and writes the full HTML.
"""
from __future__ import annotations
import os
import re
import anthropic
from charts.templates import get_by_id, TEMPLATES
from llm.html_utils import fix_cdn_links

MODEL = "claude-sonnet-4-6"

# ── System prompts ─────────────────────────────────────────────────────────────

_SYS_TEMPLATE_INJECT = """\
You are an expert DHIS2 developer.

Your task: combine several individual DHIS2 HTML chart fragments into ONE
Bootstrap-grid dashboard page.

## Rules — follow every rule, no exceptions
1. Output ONLY valid HTML — no markdown fences, no explanations.
2. One shared <head>:
   - Bootstrap 5.3.2 CSS CDN (full absolute URL)
   - Chart.js 4.4.0 CDN (full absolute URL)
   - Shared CSS: .report-header, .card, .spinner-wrap, .error-box
   - Add: .demo-banner { background:#fff3cd; color:#856404; border:1px solid #ffc107;
     border-radius:4px; padding:3px 10px; font-size:11px; margin-bottom:6px;
     text-align:center; display:none; }
3. For EACH card fragment provided:
   a. The fragment already contains a <div> layout and <script>.
   b. Place the fragment inside the correct Bootstrap col (col-md-N given).
   c. Rename  id="chart"  →  id="chartN"  and update every reference to it
      inside that fragment's <script> (getElementById, Chart constructor, etc.).
   d. Rename the self-invoking async IIFE to a named function  initChartN(ou, pe)
      to avoid scope collisions; call it from loadData().
   e. Rename id="loading" → id="loadingN" and update references.
   f. Replace EVERY  <!-- INDICATOR_UID -->  and  <!-- INDICATOR_UID_N -->
      placeholder with UIDs from the card's "Pinned UIDs" list (in order).
      If a template uses a list (DX_LIST), replace EACH placeholder element.
   g. Replace  <!-- REPORT_TITLE -->  with the card's title.
   h. Keep analytics URL structure EXACTLY:  ../api/analytics.json
      with  credentials: 'include'  — do NOT change these.
   i. Replace any $!{reportingPeriod} with the pe parameter and
      $!{organisationUnit} with the ou parameter in analytics URLs.
      These values come from initChartN(ou, pe) function arguments.
4. One shared <script> block at end of <body>:
   - Declare PREVIEW, OU_LEVEL, dhis2Get, loadOrgUnits, generatePeriods, loadData (see below)
   - All initChartN(ou, pe) functions inline
   - ONE document.addEventListener('DOMContentLoaded', ...) that sets up selectors then calls loadData()
5. Add a dashboard header bar at the very top of <body> (blue, white text, dashboard title).
6. Place the interactive controls div immediately after the header (before chart rows).
7. Do NOT add, remove, or change Chart.js dataset structure — only swap IDs and UIDs.
8. Wrap each Bootstrap column with edit markers using the card's ID:
   <!-- CARD-START:{card_id} -->
   <div class="col-md-N"> ... </div>
   <script> function initChartN(ou, pe) { ... } </script>
   <!-- CARD-END:{card_id} -->
   The card_id values are provided in each card spec below.
9. CRITICAL — analytics URL dimension= values must be 11-char alphanumeric UIDs ONLY.
   NEVER put display names, Lao/non-ASCII text, or spaces in any URL.
   Wrong: dimension=dx:ຈຳນວນຜູ້ປ່ວຍ  ← causes HTTP 400 on the DHIS2 server
   Right: dimension=dx:abc12345XYZ
10. CDN links must be full absolute URLs:
    Bootstrap CSS: https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
    Bootstrap JS : https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js
    Chart.js     : https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js

## Interactive Selectors (mandatory — NO Velocity variables)

Place after the dashboard header bar, before chart rows:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Đơn vị:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Kỳ báo cáo:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Tải dữ liệu</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare ONCE at top of shared <script>:
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district — match dashboard scope

  async function dhis2Get(path) {
    const r = await fetch('../' + path, {credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  async function loadOrgUnits() {
    const d = await dhis2Get('api/organisationUnits.json?fields=id,displayName&level=' + OU_LEVEL + '&paging=false');
    const sel = document.getElementById('ouSelect');
    sel.innerHTML = '';
    (d.organisationUnits || []).forEach(o => sel.appendChild(new Option(o.displayName, o.id)));
  }

  function generatePeriods() {
    const sel = document.getElementById('peSelect');
    sel.innerHTML = '';
    const now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1;
    for (let yr = y; yr >= y-1; yr--)
      for (let mo = (yr===y ? m : 12); mo >= 1; mo--)
        sel.appendChild(new Option('Tháng ' + mo + '/' + yr, yr + String(mo).padStart(2,'0')));
    for (let yr = y; yr >= y-1; yr--)
      for (let q = (yr===y ? Math.ceil(m/3) : 4); q >= 1; q--)
        sel.appendChild(new Option('Quý ' + q + '/' + yr, yr + 'Q' + q));
    for (let yr = y; yr >= y-2; yr--)
      sel.appendChild(new Option('Năm ' + yr, String(yr)));
  }

  async function loadData() {
    const ou = document.getElementById('ouSelect').value;
    const pe = document.getElementById('peSelect').value;
    const btn = document.getElementById('loadBtn');
    btn.disabled = true; btn.textContent = '⏳ Đang tải...';
    try {
      await Promise.all([initChart1(ou, pe), initChart2(ou, pe) /* add ALL N charts */]);
      document.getElementById('lastUpdated').textContent =
        'Cập nhật: ' + new Date().toLocaleTimeString('vi-VN');
    } finally { btn.disabled = false; btn.textContent = '↻ Tải dữ liệu'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (PREVIEW) { await loadData(); return; }
    try { await loadOrgUnits(); generatePeriods(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## SAMPLE DATA / PREVIEW MODE  (bắt buộc với mỗi chart)

Every initChartN(ou, pe) MUST follow this pattern — no DHIS2 call at all when PREVIEW:

  async function initChartN(ou, pe) {
    document.getElementById('loadingN').style.display = 'none';
    const cvs = document.getElementById('chartN');
    cvs.style.display = 'block';

    if (PREVIEW) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);   // immediate, no DHIS2 fetch
      return;
    }

    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      document.getElementById('demoBannerN').style.display = 'none';
      renderChartNReal(cvs, d);
    } catch(e) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);
    }
  }

Add inside each card (above canvas):
  <div id="demoBannerN" class="demo-banner">⚠ Dữ liệu mẫu — chưa kết nối DHIS2</div>

Sample data by chart type:
  Line / Bar monthly : labels=['T1'…'T12'], values=[120,145,98,167,134,189,210,156,143,178,192,165]
  Bar grouped (OUs)  : labels=['Tỉnh A'…'E'], datasets: [85,102,67,143,91] and [72,88,54,120,78]
  Bar stacked        : same OU labels, 3 stacked datasets
  Bar horizontal     : same OU labels, horizontal bars
  Pie / Donut        : ['Dương tính','Âm tính','Chờ kết quả','Khác'] → [45,30,15,10]
  Scorecard          : value=78, target=100, large colored number panel
  Traffic light      : 3 rows 🟢🟡🔴 based on 80%/60% thresholds
  Data table         : 5 rows × 3 cols, fake org unit names + numbers
  Combined           : each sub-chart gets its own sample data
"""

_SYS_FROM_SCRATCH = """\
You are an expert DHIS2 developer specialising in custom HTML reports.

Your task: generate a complete, production-ready DHIS2 multi-chart HTML dashboard
from a user prompt and available DHIS2 metadata.

## Rules
1. Output ONLY valid HTML — no markdown fences, no explanations.
2. Use Bootstrap 5.3.2 CDN — full absolute URLs required:
   https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
   https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js
3. Use Chart.js 4.4.0 CDN (full absolute URL, load ONCE):
   https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
4. Each chart panel has its own <canvas id="chartN"> and named init function initChartN(ou, pe).
5. Only use UIDs from the ★ PINNED section of the metadata.
   Fall back to Frequently used if pinned is empty.
6. Choose chart types from the catalog provided (use the template_id names as hints).
7. Wrap each Bootstrap column with edit markers:
   <!-- CARD-START:{card_id} -->
   <div class="col-md-N"> ... </div>
   <script> function initChartN(ou, pe) { ... } </script>
   <!-- CARD-END:{card_id} -->
   The card_id is provided in each panel spec below.
8. CRITICAL — analytics URL dimension= values must be 11-char alphanumeric UIDs ONLY.
   NEVER put display names, Lao/non-ASCII text, or spaces in any URL.
   Wrong: dimension=dx:ຈຳນວນຜູ້ປ່ວຍ  ← causes HTTP 400 on the DHIS2 server
   Right: dimension=dx:abc12345XYZ
9. Add to <style>:
   .demo-banner { background:#fff3cd; color:#856404; border:1px solid #ffc107;
     border-radius:4px; padding:3px 10px; font-size:11px; margin-bottom:6px;
     text-align:center; display:none; }

## Interactive Selectors (mandatory — NO Velocity variables)

Place after dashboard header, before chart rows:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Đơn vị:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Kỳ báo cáo:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Tải dữ liệu</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare ONCE at top of shared <script>:
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district — match dashboard scope

  async function dhis2Get(path) {
    const r = await fetch('../' + path, {credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
  }

  async function loadOrgUnits() {
    const d = await dhis2Get('api/organisationUnits.json?fields=id,displayName&level=' + OU_LEVEL + '&paging=false');
    const sel = document.getElementById('ouSelect');
    sel.innerHTML = '';
    (d.organisationUnits || []).forEach(o => sel.appendChild(new Option(o.displayName, o.id)));
  }

  function generatePeriods() {
    const sel = document.getElementById('peSelect');
    sel.innerHTML = '';
    const now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1;
    for (let yr = y; yr >= y-1; yr--)
      for (let mo = (yr===y ? m : 12); mo >= 1; mo--)
        sel.appendChild(new Option('Tháng ' + mo + '/' + yr, yr + String(mo).padStart(2,'0')));
    for (let yr = y; yr >= y-1; yr--)
      for (let q = (yr===y ? Math.ceil(m/3) : 4); q >= 1; q--)
        sel.appendChild(new Option('Quý ' + q + '/' + yr, yr + 'Q' + q));
    for (let yr = y; yr >= y-2; yr--)
      sel.appendChild(new Option('Năm ' + yr, String(yr)));
  }

  async function loadData() {
    const ou = document.getElementById('ouSelect').value;
    const pe = document.getElementById('peSelect').value;
    const btn = document.getElementById('loadBtn');
    btn.disabled = true; btn.textContent = '⏳ Đang tải...';
    try {
      await Promise.all([initChart1(ou, pe), initChart2(ou, pe) /* add ALL N charts */]);
      document.getElementById('lastUpdated').textContent =
        'Cập nhật: ' + new Date().toLocaleTimeString('vi-VN');
    } finally { btn.disabled = false; btn.textContent = '↻ Tải dữ liệu'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (PREVIEW) { await loadData(); return; }
    try { await loadOrgUnits(); generatePeriods(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## SAMPLE DATA / PREVIEW MODE  (bắt buộc với mỗi chart)

Every chart init MUST accept (ou, pe) and check PREVIEW first:

  async function initChartN(ou, pe) {
    document.getElementById('loadingN').style.display = 'none';
    const cvs = document.getElementById('chartN');
    cvs.style.display = 'block';

    if (PREVIEW) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);
      return;
    }

    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      document.getElementById('demoBannerN').style.display = 'none';
      renderChartNReal(cvs, d);
    } catch(e) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);
    }
  }

Add above each canvas:
  <div id="demoBannerN" class="demo-banner">⚠ Dữ liệu mẫu — chưa kết nối DHIS2</div>

Sample data by chart type:
  Line/Bar monthly : labels=['T1'…'T12'], values=[120,145,98,167,134,189,210,156,143,178,192,165]
  Bar OUs          : labels=['Tỉnh A'…'E'], values=[85,102,67,143,91]
  Pie/Donut        : ['Dương tính','Âm tính','Chờ kết quả','Khác'] → [45,30,15,10]
  Scorecard        : value=78 / target=100, green background
  Traffic light    : 3 rows 🟢🟡🔴 based on thresholds
  Table            : 5 rows × 3 cols, fake org unit names + numbers
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_body(html: str) -> str:
    """Extract everything between <body …> and </body> (exclusive)."""
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        content = m.group(1).strip()
        # Drop the existing hidden Velocity comment (we'll add one at the top)
        content = re.sub(
            r'<!--\s*reportingPeriod=.*?-->\s*', '', content, flags=re.DOTALL)
        # Drop the existing report-header block (we'll add a shared dashboard header)
        content = re.sub(
            r'<div class="report-header">.*?</div>\s*', '', content, flags=re.DOTALL)
        return content.strip()
    return html


def _group_into_rows(cards: list[dict], row_gap: int = 60) -> list[list[dict]]:
    if not cards:
        return []
    by_y = sorted(cards, key=lambda c: (c["y"], c["x"]))
    rows: list[list[dict]] = [[by_y[0]]]
    for card in by_y[1:]:
        if abs(card["y"] - rows[-1][0]["y"]) < row_gap:
            rows[-1].append(card)
        else:
            rows[-1].sort(key=lambda c: c["x"])
            rows.append([card])
    rows[-1].sort(key=lambda c: c["x"])
    return rows


def _bs_cols(card_w: int, row_total_w: int) -> int:
    if row_total_w <= 0:
        return 6
    return max(3, min(12, round((card_w / row_total_w) * 12)))


def _uid_list(card: dict) -> list[str]:
    p = card.get("pinned", {})
    return (p.get("indicators", []) +
            p.get("program_indicators", []) +
            p.get("data_elements", []))


# ── Mode A — Template inject ───────────────────────────────────────────────────

def _build_template_inject_message(cards: list[dict], user_prompt: str,
                                    metadata_context: str) -> str:
    rows = _group_into_rows(cards)
    lines: list[str] = [
        "## Available DHIS2 Metadata\n",
        metadata_context,
        "---\n",
        f"## Dashboard Title\n{user_prompt}\n",
        "## Grid Layout\n",
    ]

    # Layout summary
    for ri, row in enumerate(rows, 1):
        row_w = sum(c["w"] for c in row)
        cols_str = ", ".join(
            f"\"{c.get('title', '?')}\" col-md-{_bs_cols(c['w'], row_w)}"
            for c in row)
        lines.append(f"Row {ri}: {cols_str}")
    lines.append("\n---\n")

    # Per-card fragments
    chart_idx = 1
    for row in rows:
        row_w = sum(c["w"] for c in row)
        for card in row:
            bs = _bs_cols(card["w"], row_w)
            tmpl = get_by_id(card.get("template_id", ""))
            uids = _uid_list(card)
            title = card.get("title") or (tmpl["name"] if tmpl else "Chart")

            lines.append(f"## Card {chart_idx}: \"{title}\"")
            lines.append(f"Card ID (for markers): {card.get('id', f'card{chart_idx}')}")
            lines.append(f"Bootstrap column : col-md-{bs}")
            lines.append(f"Canvas id to use : chart{chart_idx}  (rename from 'chart')")
            lines.append(f"Loading id to use: loading{chart_idx}  (rename from 'loading')")
            lines.append(f"Init function    : initChart{chart_idx}  (rename the IIFE)")

            if uids:
                lines.append(f"Pinned UIDs      : {', '.join(uids)}")
                lines.append("  (replace <!-- INDICATOR_UID -->, <!-- INDICATOR_UID_1 -->,")
                lines.append("   <!-- INDICATOR_UID_2 -->, DX_LIST entries, etc. in order)")
            else:
                lines.append("Pinned UIDs      : (none — pick best-matching from metadata)")

            if tmpl:
                body = _extract_body(tmpl["html"])
                lines.append(f"\nTemplate body to adapt (chart type: {tmpl['name']}):")
                lines.append("```html")
                lines.append(body)
                lines.append("```")
            else:
                lines.append(f"\n(No template — generate a suitable chart for this panel.)")

            lines.append("")
            chart_idx += 1

    lines.append("---\n")
    lines.append(
        "Now combine all card fragments into ONE complete HTML file.\n"
        "Follow every rule from the system prompt. Output only the HTML."
    )
    return "\n".join(lines)


# ── Mode B — From scratch ──────────────────────────────────────────────────────

def _build_chart_catalog_snippet() -> str:
    """Compact chart type catalog to inject into from-scratch prompts."""
    lines = ["## Available Chart Types (use these as panel types)\n"]
    for t in TEMPLATES:
        tmpl_id = t["id"]
        lines.append(
            f"  {tmpl_id:<25}  {t['name']:<30}  — {t['short']}"
        )
    lines.append("")
    return "\n".join(lines)


def _build_from_scratch_message(cards: list[dict], user_prompt: str,
                                 metadata_context: str) -> str:
    rows = _group_into_rows(cards)

    # Build layout description
    layout_lines: list[str] = [
        f"## Dashboard Title\n{user_prompt}\n",
        f"## Grid Layout  ({len(cards)} panels, {len(rows)} rows)\n",
    ]
    chart_idx = 1
    for ri, row in enumerate(rows, 1):
        row_w = sum(c["w"] for c in row)
        layout_lines.append(f"### Row {ri}")
        for card in row:
            bs = _bs_cols(card["w"], row_w)
            tmpl = get_by_id(card.get("template_id", ""))
            chart_type = tmpl["name"] if tmpl else "auto"
            uids = _uid_list(card)
            layout_lines.append(
                f"  Panel {chart_idx}: \"{card.get('title', chart_type)}\"\n"
                f"    chart type : {chart_type}  (template_id: {card.get('template_id', 'any')})\n"
                f"    bootstrap  : col-md-{bs}\n"
                f"    canvas id  : chart{chart_idx}\n"
                f"    pinned UIDs: {', '.join(uids) if uids else '(pick from metadata)'}"
            )
            chart_idx += 1
        layout_lines.append("")

    return (
        "## Available DHIS2 Metadata\n\n"
        + metadata_context
        + "\n---\n\n"
        + _build_chart_catalog_snippet()
        + "\n---\n\n"
        + "\n".join(layout_lines)
        + "\n---\n\n"
        "Generate the complete multi-chart dashboard HTML now.\n"
        "Follow every rule from the system prompt. Output only the HTML."
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_dashboard_html(
    user_prompt: str,
    cards: list[dict],
    metadata_context: str,
    api_key: str | None = None,
) -> str:
    """
    Generate a combined multi-chart DHIS2 HTML dashboard.

    Automatically picks Mode A (template-inject) when all cards have a known
    template_id, or Mode B (from-scratch) otherwise.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    all_have_templates = all(
        get_by_id(c.get("template_id", "")) is not None for c in cards
    )

    if all_have_templates:
        system  = _SYS_TEMPLATE_INJECT
        content = _build_template_inject_message(cards, user_prompt, metadata_context)
        mode    = "template-inject"
    else:
        system  = _SYS_FROM_SCRATCH
        content = _build_from_scratch_message(cards, user_prompt, metadata_context)
        mode    = "from-scratch"

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": content}],
    )

    html = response.content[0].text.strip()

    # Strip accidental markdown fences
    if html.startswith("```"):
        lines = html.splitlines()
        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    return fix_cdn_links(html)


# ── Single-card regeneration ───────────────────────────────────────────────────

_SYS_SINGLE_CARD = """\
You are an expert DHIS2 developer.

Generate a SINGLE Bootstrap column for a DHIS2 dashboard.
Output ONLY the column HTML fragment — no <html>/<head>/<body> tags.

Wrap the output with edit markers using the card's ID:
  <!-- CARD-START:{card_id} -->
  <div class="col-md-N">...</div>
  <script>function initChartN(ou, pe) {...}</script>
  <!-- CARD-END:{card_id} -->
Replace {card_id} with the actual Card ID provided in the spec.

Assume already present in the page:
  - Bootstrap 5.3, Chart.js 4.4 loaded
  - const PREVIEW = window.location.protocol === 'file:';  (declared once)
  - async function dhis2Get(path) {...}  (standard DHIS2 fetch helper, uses '../' prefix)
  - .demo-banner CSS class
  - loadData() function that calls initChartN(ou, pe) for all cards

## PREVIEW pattern (mandatory for every card)

  async function initChartN(ou, pe) {
    document.getElementById('loadingN').style.display = 'none';
    const cvs = document.getElementById('chartN');
    cvs.style.display = 'block';

    if (PREVIEW) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);   // no DHIS2 fetch
      return;
    }

    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      document.getElementById('demoBannerN').style.display = 'none';
      renderChartNReal(cvs, d);
    } catch(e) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);
    }
  }

  function renderChartNSample(cvs) { new Chart(cvs, { /* sample data */ }); }

Add above canvas:
  <div id="demoBannerN" class="demo-banner">⚠ Dữ liệu mẫu — chưa kết nối DHIS2</div>

Sample data by chart type:
  Line/Bar monthly : labels=['T1'…'T12'], values=[120,145,98,167,134,189,210,156,143,178,192,165]
  Bar OUs          : labels=['Tỉnh A'…'E'], values=[85,102,67,143,91]
  Pie/Donut        : ['Dương tính','Âm tính','Chờ kết quả','Khác'] → [45,30,15,10]
  Scorecard        : value=78 / target=100, green background
  Traffic light    : 3 rows 🟢🟡🔴 based on thresholds
  Table            : 5 rows × 3 cols, fake org unit names + numbers

Keep analytics URL: ../api/analytics.json with credentials:'include'.
Replace any $!{reportingPeriod} with the pe parameter and $!{organisationUnit} with the ou parameter.
The function signature is initChartN(ou, pe) — called from the parent page's loadData().
"""


def regenerate_single_card(
    card: dict,
    chart_index: int,
    metadata_context: str,
    bs_cols: int,
    api_key: str | None = None,
) -> str:
    """
    Generate one Bootstrap column HTML fragment for a dashboard card.
    Returns column HTML wrapped with CARD-START / CARD-END markers.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    card_id = card.get("id", f"card{chart_index}")
    tmpl    = get_by_id(card.get("template_id", ""))
    uids    = _uid_list(card)
    title   = card.get("title") or (tmpl["name"] if tmpl else f"Chart {chart_index}")

    parts = [
        "## Available DHIS2 Metadata\n",
        metadata_context,
        "\n---\n",
        "## Card Specification",
        f"Card ID (for markers): {card_id}",
        f"Bootstrap column     : col-md-{bs_cols}",
        f"Canvas id            : chart{chart_index}",
        f"Loading id           : loading{chart_index}",
        f"Demo banner id       : demoBanner{chart_index}",
        f"Init function name   : initChart{chart_index}",
        f"Title                : {title}",
        f"Pinned UIDs          : {', '.join(uids) if uids else '(none — pick from metadata)'}",
    ]

    if tmpl:
        body = _extract_body(tmpl["html"])
        parts += [
            f"\nTemplate body to adapt (chart type: {tmpl['name']}):",
            "```html", body, "```",
            "\nAdapt the template: rename IDs per spec, fill UIDs, wrap with CARD-START/END markers.",
        ]
    else:
        parts.append("\nGenerate a suitable chart. Wrap output with CARD-START/END markers.")

    parts.append("\nOutput ONLY the HTML fragment — no <html>/<head>/<body>.")

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=_SYS_SINGLE_CARD,
        messages=[{"role": "user", "content": "\n".join(parts)}],
    )

    fragment = response.content[0].text.strip()
    if fragment.startswith("```"):
        lines = fragment.splitlines()
        fragment = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    return fix_cdn_links(fragment)


def splice_card_in_html(full_html: str, card_id: str, new_col_html: str) -> str:
    """
    Replace the section between CARD-START:{card_id} and CARD-END:{card_id}
    markers (inclusive) with new_col_html.
    Raises ValueError if markers are not found.
    """
    pattern = (
        rf'<!--\s*CARD-START:{re.escape(card_id)}\s*-->'
        rf'.*?'
        rf'<!--\s*CARD-END:{re.escape(card_id)}\s*-->'
    )
    if not re.search(pattern, full_html, re.DOTALL):
        raise ValueError(f"Card markers not found for card_id='{card_id}'")
    return re.sub(pattern, new_col_html, full_html, flags=re.DOTALL)
