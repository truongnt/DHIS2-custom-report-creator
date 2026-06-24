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

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# ── System prompts ─────────────────────────────────────────────────────────────

_SYS_STATIC_DASHBOARD = """\
You are an expert data visualisation developer.

Your task: generate a complete, self-contained HTML dashboard that visualises
DHIS2 data that has ALREADY been fetched and is supplied in the prompt.

## Rules
1. Output ONLY valid HTML — no markdown fences, no explanations.
2. Use Bootstrap 5.3.2 and Chart.js 4.4.0 from CDN (full absolute URLs).
3. DO NOT make any fetch() or XMLHttpRequest calls to DHIS2 or any other server.
   All data is already embedded in the page as JavaScript arrays.
4. For each chart, parse the data table in the prompt and convert it to
   Chart.js labels + datasets arrays.
5. If a chart section shows "FAILED" or "No data", render an empty placeholder
   card with a clear message — do not invent fake numbers.
6. Include a simple static header showing the dashboard title and period/scope.
7. Arrange charts in a responsive Bootstrap grid (col-md-6 for 2-per-row,
   col-md-12 for single wide chart).
8. All text (labels, titles, tooltips) must be in English.
9. Each chart must have a visible title above the <canvas>.
10. Use appropriate Chart.js type: bar, line, pie, doughnut, or table (HTML table).
"""

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
   CRITICAL: PREVIEW, OU_LEVEL, dhis2Get, resolveRelativePeriod must be declared ONLY in this
   shared block. Per-card fragments must NOT redeclare them — duplicate `const` across <script>
   tags causes SyntaxError and the entire shared script (loadData, DOMContentLoaded) fails silently.
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
10a. Analytics API — two endpoints, different response structures:

   Org unit dimension values (work in both endpoints):
     USER_ORGUNIT              — user's own org units (DHIS2 Visualizer default)
     USER_ORGUNIT_CHILDREN     — one level below user's org units
     USER_ORGUNIT_GRANDCHILDREN — two levels below
     {specificUID}             — a single specific org unit
     Use as dimension=ou: for OU breakdown; use as filter=ou: for aggregated totals.

   Aggregate (dataSets/indicators):
     GET ../api/analytics.json?dimension=dx:{uid}&dimension=pe:{pe}&dimension=ou:{ou}
     Response headers: dx | pe | ou | value
     Parse: const valIdx = d.headers.findIndex(h => h.name === 'value');
     Relative periods (LAST_MONTH, LAST_12_MONTHS, THIS_YEAR…) are supported directly.

   Event analytics (tracker programs) — always use /events/AGGREGATE not /events/query:
     ALWAYS use resolveRelativePeriod(pe) → rpe before building event analytics URLs.

     Case A — count events with NO category breakdown:
       GET .../events/aggregate/{programUID}?stage={stageUID}&dimension=pe:{rpe}&dimension=ou:{ou}&aggregationType=COUNT
       Response: pe | ou | value

     Case B — break down by option set / text DE (e.g. classification, result):
       GET .../events/aggregate/{programUID}?stage={stageUID}&dimension={stageUID}.{deUID}&dimension=pe:{rpe}&dimension=ou:{ou}
       *** DIMENSION ORDER IS CRITICAL: stageUID comes FIRST, then deUID — NEVER swap them ***
       *** dimension=stageUID.deUID  ← correct   |   dimension=deUID.stageUID ← WRONG (E7226) ***
       NO aggregationType parameter — count per category is automatic.
       Adding aggregationType=COUNT here → HTTP 409 E7204 error.
       RESPONSE HEADER NAME: just the deUID alone — NOT stageUID.deUID
         {"name":"deUID","column":"DE display name",...}
       Parse: const catIdx = d.headers.findIndex(h => h.name === '{deUID}');
       Values in rows are option CODES (e.g. "PF", "PV") — use metaData.items[code].name for labels.

     Case C — aggregate a numeric DE (sum, average…):
       GET .../events/aggregate/{programUID}?stage={stageUID}&value={deUID}&aggregationType=SUM&dimension=pe:{rpe}&dimension=ou:{ou}
       Response: pe | ou | value

     NEVER use /events/query for charting — raw event rows, no "value" column.
10. CDN links must be full absolute URLs:
    Bootstrap CSS: https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
    Bootstrap JS : https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js
    Chart.js     : https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js

## Language & labels — MANDATORY

All user-visible text MUST be in English. Never output Vietnamese or Lao.
- Org unit selector label: "Org unit:" (never "Province:", "Tỉnh:", "Đơn vị:")
- Period selector label: "Period:" (never "Kỳ báo cáo:")
- Load button: "↻ Load data" / loading state: "⏳ Loading..."
- Period dropdown: relative periods first (LAST_MONTH, LAST_12_MONTHS, THIS_YEAR…), then fixed monthly/quarterly/yearly
- Timestamp: "Updated: ..."
- Demo banner: "⚠ Sample data — DHIS2 not connected"
- Chart titles, axis labels, table headers, tooltips: English only
- Org unit names: always use o.displayName from DHIS2 — never hardcode place names

## Interactive Selectors (mandatory — NO Velocity variables)

Place after the dashboard header bar, before chart rows:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Org unit:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Period:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Load data</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare ONCE at top of shared <script>:
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district — match dashboard scope

  async function dhis2Get(path) {
    const url = '../' + path;
    const r = await fetch(url, {credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status + ' — ' + url);
    return r.json();
  }

  // Resolve relative period codes to concrete DHIS2 period strings.
  // REQUIRED for /events/aggregate — that endpoint does NOT accept LAST_MONTH etc.
  // Optional (but harmless) for /api/analytics.json which accepts both.
  function resolveRelativePeriod(pe) {
    const now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1;
    const pad = n => String(n).padStart(2, '0');
    const prevMonth = i => { let mo = m - i, yr = y; while (mo <= 0) { mo += 12; yr--; } return yr + pad(mo); };
    const q = Math.ceil(m / 3);
    switch (pe) {
      case 'LAST_MONTH':     return prevMonth(1);
      case 'LAST_3_MONTHS':  return [1,2,3].map(prevMonth).join(';');
      case 'LAST_6_MONTHS':  return [1,2,3,4,5,6].map(prevMonth).join(';');
      case 'LAST_12_MONTHS': return [1,2,3,4,5,6,7,8,9,10,11,12].map(prevMonth).join(';');
      case 'THIS_QUARTER':   return y + 'Q' + q;
      case 'LAST_QUARTER':   { let lq = q-1, yr = y; if (lq<=0){lq=4;yr--;} return yr+'Q'+lq; }
      case 'THIS_YEAR':      return String(y);
      case 'LAST_YEAR':      return String(y - 1);
      default:               return pe;  // already a concrete code: 202504, 2025Q1, 2025, …
    }
  }

  async function loadOrgUnits() {
    const sel = document.getElementById('ouSelect');
    sel.innerHTML = '';
    // Scope shortcuts — mirrors DHIS2 Visualizer, always available without an API call
    const scopeGrp = document.createElement('optgroup');
    scopeGrp.label = 'User organisation unit';
    [['User organisation unit',  'USER_ORGUNIT'],
     ['User sub-units',          'USER_ORGUNIT_CHILDREN'],
     ['User sub-x2-units',       'USER_ORGUNIT_GRANDCHILDREN'],
    ].forEach(([l, v]) => scopeGrp.appendChild(new Option(l, v)));
    sel.appendChild(scopeGrp);
    sel.value = 'USER_ORGUNIT';   // default — same as DHIS2 Visualizer
    // Load user's own org units for individual selection
    try {
      const me = await dhis2Get('api/me.json?fields=organisationUnits[id,displayName,level]');
      const myOUs = (me.organisationUnits || []).sort((a, b) => a.displayName.localeCompare(b.displayName));
      if (myOUs.length > 0) {
        const myGrp = document.createElement('optgroup');
        myGrp.label = 'Org units';
        myOUs.forEach(o => myGrp.appendChild(new Option(o.displayName, o.id)));
        sel.appendChild(myGrp);
      }
      // Load level-N units under user's roots (useful for national-level users)
      const roots = myOUs.filter(o => o.level < OU_LEVEL);
      if (roots.length > 0) {
        let url = 'api/organisationUnits.json?fields=id,displayName&level=' + OU_LEVEL + '&paging=false';
        if (roots.length === 1) url += '&filter=path:like:' + roots[0].id;
        const d = await dhis2Get(url);
        const lvlOUs = (d.organisationUnits || []).sort((a, b) => a.displayName.localeCompare(b.displayName));
        if (lvlOUs.length > 0) {
          const lvlGrp = document.createElement('optgroup');
          lvlGrp.label = 'Level ' + OU_LEVEL + ' (specific)';
          lvlOUs.forEach(o => lvlGrp.appendChild(new Option(o.displayName, o.id)));
          sel.appendChild(lvlGrp);
        }
      }
    } catch(e) {
      console.error('[DHIS2]', e);
    }
  }

  function generatePeriods() {
    const sel = document.getElementById('peSelect');
    sel.innerHTML = '';
    const rel = document.createElement('optgroup');
    rel.label = 'Relative';
    [['Last month',     'LAST_MONTH'],
     ['Last 3 months',  'LAST_3_MONTHS'],
     ['Last 6 months',  'LAST_6_MONTHS'],
     ['Last 12 months', 'LAST_12_MONTHS'],
     ['This quarter',   'THIS_QUARTER'],
     ['Last quarter',   'LAST_QUARTER'],
     ['This year',      'THIS_YEAR'],
     ['Last year',      'LAST_YEAR'],
    ].forEach(([l, v]) => rel.appendChild(new Option(l, v)));
    sel.appendChild(rel);
    const mfix = document.createElement('optgroup');
    mfix.label = 'Monthly';
    const now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1;
    for (let i = 0; i < 12; i++) {
      let mo = m - i, yr = y;
      if (mo <= 0) { mo += 12; yr--; }
      mfix.appendChild(new Option('Month ' + mo + '/' + yr, yr + String(mo).padStart(2, '0')));
    }
    sel.appendChild(mfix);
    const qfix = document.createElement('optgroup');
    qfix.label = 'Quarterly';
    for (let i = 0; i < 8; i++) {
      let q = Math.ceil(m / 3) - i, yr = y;
      if (q <= 0) { q += 4; yr--; }
      qfix.appendChild(new Option('Q' + q + ' ' + yr, yr + 'Q' + q));
    }
    sel.appendChild(qfix);
    const yfix = document.createElement('optgroup');
    yfix.label = 'Yearly';
    for (let yr = y; yr >= y - 4; yr--) yfix.appendChild(new Option(String(yr), String(yr)));
    sel.appendChild(yfix);
    sel.value = 'LAST_12_MONTHS';  // default
  }

  // Convert DHIS2 period code to readable label: 202604→Apr 2026, 2025Q3→Q3 2025
  function formatPeriodLabel(pe) {
    const mm = pe.match(/^(\d{4})(\d{2})$/);
    if (mm) {
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return months[parseInt(mm[2],10)-1] + ' ' + mm[1];
    }
    const qm = pe.match(/^(\d{4})Q(\d)$/);
    if (qm) return 'Q' + qm[2] + ' ' + qm[1];
    return pe;
  }

  async function loadData() {
    const ou = document.getElementById('ouSelect').value;
    const pe = document.getElementById('peSelect').value;
    const btn = document.getElementById('loadBtn');
    btn.disabled = true; btn.textContent = '⏳ Loading...';
    try {
      await Promise.all([initChart1(ou, pe), initChart2(ou, pe) /* add ALL N charts */]);
      document.getElementById('lastUpdated').textContent =
        'Updated: ' + new Date().toLocaleTimeString();
    } finally { btn.disabled = false; btn.textContent = '↻ Load data'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    generatePeriods();  // ALWAYS populate periods first — even in preview
    if (PREVIEW) {
      const sel = document.getElementById('ouSelect');
      [['User organisation unit',  'USER_ORGUNIT'],
       ['User sub-units',          'USER_ORGUNIT_CHILDREN'],
       ['User sub-x2-units',       'USER_ORGUNIT_GRANDCHILDREN'],
      ].forEach(([l, v]) => sel.appendChild(new Option(l, v)));
      sel.value = 'USER_ORGUNIT';
      await loadData();
      return;
    }
    try { await loadOrgUnits(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## JAVASCRIPT STRING LITERAL RULE — CRITICAL

Every string value in JS must have BOTH opening and closing quotes.
WRONG: `borderColor: #2e7d32'`   ← missing opening quote → syntax error
RIGHT: `borderColor: '#2e7d32'`

A single JS syntax error causes ALL functions in that script block to be undefined.
Double-check every string literal before outputting.

## SAMPLE DATA / PREVIEW MODE  (bắt buộc với mỗi chart)

RULE: Sample/fake data shown ONLY in PREVIEW (file://).
      On DHIS2 host (https://) — show a clear message on error/no-data, NEVER fake data.

Every initChartN(ou, pe) MUST follow this exact pattern:

  async function initChartN(ou, pe) {
    document.getElementById('loadingN').style.display = 'none';
    const cvs = document.getElementById('chartN');
    cvs.style.display = 'block';

    if (PREVIEW) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);   // preview only — no DHIS2 call
      return;
    }

    // On host: fetch real data — on failure show error, NEVER call renderChartNSample
    document.getElementById('demoBannerN').style.display = 'none';
    try {
      const rpe = resolveRelativePeriod(pe);
      const d = await dhis2Get('...');  // replace with actual URL
      if (!d.rows || d.rows.length === 0) {
        document.getElementById('errorN').textContent = 'No data for the selected period / org unit.';
        document.getElementById('errorN').style.display = 'block';
        return;
      }
      renderChartNReal(cvs, d);
    } catch(e) {
      console.error('[ChartN]', e);
      document.getElementById('errorN').textContent = 'Failed to load data: ' + e.message;
      document.getElementById('errorN').style.display = 'block';
    }
  }

Add inside each card HTML (above canvas):
  <div id="demoBannerN" class="demo-banner">⚠ Sample data — preview mode</div>
  <div id="errorN" style="display:none;background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;border-radius:4px;padding:10px;font-size:13px;margin-top:8px;"></div>

## CRITICAL — Two separate render functions, zero crossover

renderChartNSample(canvas):
  - Contains ALL hardcoded arrays
  - Called ONLY when PREVIEW=true — NEVER on API failure

renderChartNReal(canvas, apiData):
  - MUST compute every value from apiData.rows — NO hardcoded numbers whatsoever
  - Parse d.headers to find column indices dynamically, then map d.rows
  - Fallback for missing/null values: 0, not a hardcoded sample number
  - Example: const valIdx = d.headers.findIndex(h => h.name==='value');
             const vals = d.rows.map(r => parseFloat(r[valIdx]) || 0);
  - COLOR RULE: use indexed palette — NEVER a name-keyed map with a single ugly fallback.
    const PALETTE = ['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9','#8e44ad','#16a085'];
    datasets = categories.map((cat, i) => ({ ..., backgroundColor: PALETTE[i % PALETTE.length] }));
  - For option set DEs: use d.metaData.items[code]?.name || code as the dataset label.
  - PERIOD LABELS: always use formatPeriodLabel(pe) for x-axis labels — never raw codes like '202604'.
    labels: periods.map(formatPeriodLabel)  // → 'Apr 2026', 'Mar 2026', …
    formatPeriodLabel is declared in the shared <script> block.

Sample data (for renderChartNSample ONLY):
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
   Per-card <script> blocks must contain ONLY: initChartN, renderChartNSample, renderChartNReal,
   and a chart instance variable (let chartNInst = null).
   NEVER put PREVIEW, OU_LEVEL, dhis2Get, or resolveRelativePeriod inside per-card scripts —
   they live in the ONE shared <script> at the bottom of <body>.
   Duplicate `const` declarations across <script> blocks cause SyntaxError and break the page.
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
10. Analytics API — TWO endpoints, different rules:

   Aggregate (dataSets / indicators):
     GET ../api/analytics.json?dimension=dx:{uid}&dimension=pe:{pe}&dimension=ou:{ou}
     Response headers: dx | pe | ou | value

   Event analytics (tracker) — ALWAYS /events/aggregate, never /events/query:
     ALWAYS convert pe → rpe = resolveRelativePeriod(pe) first.

     Case A — count events, no category breakdown:
       .../events/aggregate/{progUID}?stage={stgUID}&dimension=pe:{rpe}&dimension=ou:{ou}&aggregationType=COUNT

     Case B — breakdown by option set / text DE (most common — classification, result…):
       .../events/aggregate/{progUID}?stage={stgUID}&dimension={stgUID}.{deUID}&dimension=pe:{rpe}&dimension=ou:{ou}
       *** DIMENSION ORDER IS CRITICAL: stageUID comes FIRST, then deUID — NEVER swap them ***
       *** dimension=stgUID.deUID  ← correct   |   dimension=deUID.stgUID ← WRONG (E7226) ***
       NO aggregationType — count per category is automatic.
       Adding aggregationType=COUNT here → HTTP 409 E7204 error.
       RESPONSE HEADER NAME: just {deUID} alone — NOT {stgUID}.{deUID}
         Parse: const catIdx = d.headers.findIndex(h => h.name === '{deUID}');
       Values in rows are option CODES — use d.metaData.items[code].name for display labels.

     Case C — aggregate numeric DE:
       .../events/aggregate/{progUID}?stage={stgUID}&value={deUID}&aggregationType=SUM&dimension=pe:{rpe}&dimension=ou:{ou}

11. JAVASCRIPT STRING LITERALS — every string must have BOTH opening and closing quote.
    WRONG: `borderColor: #2e7d32'`  → syntax error → all chart functions undefined → spinner never stops
    RIGHT: `borderColor: '#2e7d32'`

## Language & labels — MANDATORY

All user-visible text MUST be in English. Never output Vietnamese or Lao.
- Org unit selector label: "Org unit:" (never "Province:", "Tỉnh:", "Đơn vị:")
- Period selector label: "Period:" (never "Kỳ báo cáo:")
- Load button: "↻ Load data" / loading state: "⏳ Loading..."
- Period dropdown: relative periods first (LAST_MONTH, LAST_12_MONTHS, THIS_YEAR…), then fixed monthly/quarterly/yearly
- Timestamp: "Updated: ..."
- Demo banner: "⚠ Sample data — DHIS2 not connected"
- Chart titles, axis labels, table headers, tooltips: English only
- Org unit names: always use o.displayName from DHIS2 — never hardcode place names

## Interactive Selectors (mandatory — NO Velocity variables)

Place after dashboard header, before chart rows:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Org unit:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Period:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Load data</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare ONCE at top of shared <script>:
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district — match dashboard scope

  async function dhis2Get(path) {
    const url = '../' + path;
    const r = await fetch(url, {credentials:'include'});
    if (!r.ok) throw new Error('HTTP ' + r.status + ' — ' + url);
    return r.json();
  }

  // Resolve relative period codes to concrete DHIS2 period strings.
  // REQUIRED for /events/aggregate — that endpoint does NOT accept LAST_MONTH etc.
  // Optional (but harmless) for /api/analytics.json which accepts both.
  function resolveRelativePeriod(pe) {
    const now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1;
    const pad = n => String(n).padStart(2, '0');
    const prevMonth = i => { let mo = m - i, yr = y; while (mo <= 0) { mo += 12; yr--; } return yr + pad(mo); };
    const q = Math.ceil(m / 3);
    switch (pe) {
      case 'LAST_MONTH':     return prevMonth(1);
      case 'LAST_3_MONTHS':  return [1,2,3].map(prevMonth).join(';');
      case 'LAST_6_MONTHS':  return [1,2,3,4,5,6].map(prevMonth).join(';');
      case 'LAST_12_MONTHS': return [1,2,3,4,5,6,7,8,9,10,11,12].map(prevMonth).join(';');
      case 'THIS_QUARTER':   return y + 'Q' + q;
      case 'LAST_QUARTER':   { let lq = q-1, yr = y; if (lq<=0){lq=4;yr--;} return yr+'Q'+lq; }
      case 'THIS_YEAR':      return String(y);
      case 'LAST_YEAR':      return String(y - 1);
      default:               return pe;  // already a concrete code: 202504, 2025Q1, 2025, …
    }
  }

  async function loadOrgUnits() {
    const sel = document.getElementById('ouSelect');
    sel.innerHTML = '';
    // Scope shortcuts — mirrors DHIS2 Visualizer, always available without an API call
    const scopeGrp = document.createElement('optgroup');
    scopeGrp.label = 'User organisation unit';
    [['User organisation unit',  'USER_ORGUNIT'],
     ['User sub-units',          'USER_ORGUNIT_CHILDREN'],
     ['User sub-x2-units',       'USER_ORGUNIT_GRANDCHILDREN'],
    ].forEach(([l, v]) => scopeGrp.appendChild(new Option(l, v)));
    sel.appendChild(scopeGrp);
    sel.value = 'USER_ORGUNIT';   // default — same as DHIS2 Visualizer
    // Load user's own org units for individual selection
    try {
      const me = await dhis2Get('api/me.json?fields=organisationUnits[id,displayName,level]');
      const myOUs = (me.organisationUnits || []).sort((a, b) => a.displayName.localeCompare(b.displayName));
      if (myOUs.length > 0) {
        const myGrp = document.createElement('optgroup');
        myGrp.label = 'Org units';
        myOUs.forEach(o => myGrp.appendChild(new Option(o.displayName, o.id)));
        sel.appendChild(myGrp);
      }
      // Load level-N units under user's roots (useful for national-level users)
      const roots = myOUs.filter(o => o.level < OU_LEVEL);
      if (roots.length > 0) {
        let url = 'api/organisationUnits.json?fields=id,displayName&level=' + OU_LEVEL + '&paging=false';
        if (roots.length === 1) url += '&filter=path:like:' + roots[0].id;
        const d = await dhis2Get(url);
        const lvlOUs = (d.organisationUnits || []).sort((a, b) => a.displayName.localeCompare(b.displayName));
        if (lvlOUs.length > 0) {
          const lvlGrp = document.createElement('optgroup');
          lvlGrp.label = 'Level ' + OU_LEVEL + ' (specific)';
          lvlOUs.forEach(o => lvlGrp.appendChild(new Option(o.displayName, o.id)));
          sel.appendChild(lvlGrp);
        }
      }
    } catch(e) {
      console.error('[DHIS2]', e);
    }
  }

  function generatePeriods() {
    const sel = document.getElementById('peSelect');
    sel.innerHTML = '';
    const rel = document.createElement('optgroup');
    rel.label = 'Relative';
    [['Last month',     'LAST_MONTH'],
     ['Last 3 months',  'LAST_3_MONTHS'],
     ['Last 6 months',  'LAST_6_MONTHS'],
     ['Last 12 months', 'LAST_12_MONTHS'],
     ['This quarter',   'THIS_QUARTER'],
     ['Last quarter',   'LAST_QUARTER'],
     ['This year',      'THIS_YEAR'],
     ['Last year',      'LAST_YEAR'],
    ].forEach(([l, v]) => rel.appendChild(new Option(l, v)));
    sel.appendChild(rel);
    const mfix = document.createElement('optgroup');
    mfix.label = 'Monthly';
    const now = new Date(), y = now.getFullYear(), m = now.getMonth() + 1;
    for (let i = 0; i < 12; i++) {
      let mo = m - i, yr = y;
      if (mo <= 0) { mo += 12; yr--; }
      mfix.appendChild(new Option('Month ' + mo + '/' + yr, yr + String(mo).padStart(2, '0')));
    }
    sel.appendChild(mfix);
    const qfix = document.createElement('optgroup');
    qfix.label = 'Quarterly';
    for (let i = 0; i < 8; i++) {
      let q = Math.ceil(m / 3) - i, yr = y;
      if (q <= 0) { q += 4; yr--; }
      qfix.appendChild(new Option('Q' + q + ' ' + yr, yr + 'Q' + q));
    }
    sel.appendChild(qfix);
    const yfix = document.createElement('optgroup');
    yfix.label = 'Yearly';
    for (let yr = y; yr >= y - 4; yr--) yfix.appendChild(new Option(String(yr), String(yr)));
    sel.appendChild(yfix);
    sel.value = 'LAST_12_MONTHS';  // default
  }

  // Convert DHIS2 period code to readable label: 202604→Apr 2026, 2025Q3→Q3 2025
  function formatPeriodLabel(pe) {
    const mm = pe.match(/^(\d{4})(\d{2})$/);
    if (mm) {
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return months[parseInt(mm[2],10)-1] + ' ' + mm[1];
    }
    const qm = pe.match(/^(\d{4})Q(\d)$/);
    if (qm) return 'Q' + qm[2] + ' ' + qm[1];
    return pe;
  }

  async function loadData() {
    const ou = document.getElementById('ouSelect').value;
    const pe = document.getElementById('peSelect').value;
    const btn = document.getElementById('loadBtn');
    btn.disabled = true; btn.textContent = '⏳ Loading...';
    try {
      await Promise.all([initChart1(ou, pe), initChart2(ou, pe) /* add ALL N charts */]);
      document.getElementById('lastUpdated').textContent =
        'Updated: ' + new Date().toLocaleTimeString();
    } finally { btn.disabled = false; btn.textContent = '↻ Load data'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    generatePeriods();  // ALWAYS populate periods first — even in preview
    if (PREVIEW) {
      // preview (file://) mode: populate org unit with static options, render sample data
      const sel = document.getElementById('ouSelect');
      [['User organisation unit',  'USER_ORGUNIT'],
       ['User sub-units',          'USER_ORGUNIT_CHILDREN'],
       ['User sub-x2-units',       'USER_ORGUNIT_GRANDCHILDREN'],
      ].forEach(([l, v]) => sel.appendChild(new Option(l, v)));
      sel.value = 'USER_ORGUNIT';
      await loadData();
      return;
    }
    try { await loadOrgUnits(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## JAVASCRIPT STRING LITERAL RULE — CRITICAL

Every string value in JS must have BOTH opening and closing quotes.
WRONG: `borderColor: #2e7d32'`   ← missing opening quote → syntax error
RIGHT: `borderColor: '#2e7d32'`

A single JS syntax error in a <script> block causes ALL functions in that block to be
undefined, so the chart never initialises and the "Loading..." spinner never disappears.
Double-check every string literal before outputting.

## PER-CARD SCRIPT STRUCTURE — MANDATORY

Each per-card <script> block contains ONLY these — nothing else:

  let chartNInst = null;  // chart instance tracker — needed to destroy before re-render

  function renderChartNSample(cvs) {
    if (chartNInst) { chartNInst.destroy(); chartNInst = null; }
    chartNInst = new Chart(cvs.getContext('2d'), { /* sample data */ });
  }

  function renderChartNReal(cvs, data) {
    if (chartNInst) { chartNInst.destroy(); chartNInst = null; }
    // parse data.rows dynamically using d.headers.findIndex
    chartNInst = new Chart(cvs.getContext('2d'), { /* real data */ });
  }

  async function initChartN(ou, pe) { ... }

DO NOT put PREVIEW, OU_LEVEL, dhis2Get, or resolveRelativePeriod here.
Those are declared once in the shared <script> at the end of <body>.
Duplicate `const` declarations → SyntaxError → shared script never runs → chart never loads.

## SAMPLE DATA / PREVIEW MODE  (bắt buộc với mỗi chart)

Every chart init MUST accept (ou, pe) and check PREVIEW first:

  async function initChartN(ou, pe) {
    document.getElementById('loadingN').style.display = 'none';
    const cvs = document.getElementById('chartN');
    cvs.style.display = 'block';

    if (PREVIEW) {
      document.getElementById('demoBannerN').style.display = 'block';
      renderChartNSample(cvs);   // preview only
      return;
    }

    // On DHIS2 host: fetch real data — show error on failure, NEVER fake data
    document.getElementById('demoBannerN').style.display = 'none';
    try {
      const rpe = resolveRelativePeriod(pe);
      const d = await dhis2Get('...');  // replace with actual analytics URL
      if (!d.rows || d.rows.length === 0) {
        document.getElementById('errorN').textContent = 'No data for the selected period / org unit.';
        document.getElementById('errorN').style.display = 'block';
        return;
      }
      renderChartNReal(cvs, d);
    } catch(e) {
      console.error('[ChartN]', e);
      document.getElementById('errorN').textContent = 'Failed to load data: ' + e.message;
      document.getElementById('errorN').style.display = 'block';
    }
  }

Add above each canvas:
  <div id="demoBannerN" class="demo-banner">⚠ Sample data — preview mode</div>
  <div id="errorN" style="display:none;background:#f8d7da;color:#721c24;border:1px solid #f5c6cb;border-radius:4px;padding:10px;font-size:13px;margin-top:8px;"></div>

## COLOR RULE for renderChartNReal — MANDATORY

Never use a name-keyed color map with a single fallback — all categories end up the same color.
Always use an indexed palette so every category gets a distinct, bright color:

  const PALETTE = ['#e74c3c','#3498db','#f39c12','#27ae60','#9b59b6','#1abc9c','#e67e22','#2980b9','#8e44ad','#16a085'];
  datasets = categories.map((cat, i) => ({
    label: d.metaData?.items?.[cat]?.name || cat,
    data: periods.map(p => grouped[cat]?.[p] || 0),
    backgroundColor: PALETTE[i % PALETTE.length],
    borderWidth: 1
  }));
  labels: periods.map(formatPeriodLabel)  // → 'Apr 2026', 'Mar 2026', NOT '202604'
  // formatPeriodLabel is in the shared <script> block

Sample data by chart type (for renderChartNSample ONLY — never show on host):
  Line/Bar monthly : labels=['Jan'…'Dec'], values=[120,145,98,167,134,189,210,156,143,178,192,165]
  Bar OUs          : labels=['Province A'…'E'], values=[85,102,67,143,91]
  Pie/Donut        : ['Positive','Negative','Pending','Other'] → [45,30,15,10]
  Scorecard        : value=78 / target=100, green background
  Traffic light    : 3 rows 🟢🟡🔴 based on thresholds
  Table            : 5 rows × 3 cols, generic names + numbers
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_body(html: str) -> str:
    """Extract everything between <body …> and </body> (exclusive)."""
    m = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    if m:
        content = m.group(1).strip()
        # Drop the existing hidden Velocity comment
        content = re.sub(
            r'<!--\s*reportingPeriod=.*?-->\s*', '', content, flags=re.DOTALL)
        # Drop the existing report-header block (we'll add a shared dashboard header)
        content = re.sub(
            r'<div class="report-header">.*?</div>\s*', '', content, flags=re.DOTALL)
        # Fix any broken CDN links before handing the fragment to the LLM
        content = fix_cdn_links(content)
        return content.strip()
    return fix_cdn_links(html)


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
                                    metadata_context: str) -> list[dict]:
    """Returns content blocks list: [cached metadata block, dynamic block]."""
    rows = _group_into_rows(cards)
    lines: list[str] = [
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
    return [
        {
            "type": "text",
            "text": f"## Available DHIS2 Metadata\n\n{metadata_context}\n\n---\n\n",
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": "\n".join(lines)},
    ]


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
                                 metadata_context: str) -> list[dict]:
    """Returns content blocks list: [cached metadata block, dynamic block]."""
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

    dynamic_text = (
        _build_chart_catalog_snippet()
        + "\n---\n\n"
        + "\n".join(layout_lines)
        + "\n---\n\n"
        "Generate the complete multi-chart dashboard HTML now.\n"
        "Follow every rule from the system prompt. Output only the HTML."
    )
    return [
        {
            "type": "text",
            "text": f"## Available DHIS2 Metadata\n\n{metadata_context}\n\n---\n\n",
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": dynamic_text},
    ]


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_from_chart_configs(
    configs: list[dict],
    metadata_context: str,
    context_hint: str = "",
    analytics_params: dict | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> str:
    """
    Generate a DHIS2 dashboard HTML from user-defined chart specifications.

    The generated HTML calls DHIS2 analytics API at runtime (in the browser) so
    that data never leaves the DHIS2 system. configs must include:
      - metric_uid   : data element UID
      - stage_uid    : program stage UID  (event analytics)
      - program_uid  : program UID        (event analytics)
      If stage_uid/program_uid absent → aggregate analytics endpoint.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    params     = analytics_params or {}
    time_range = params.get("time_range", "Last 12 months")
    ou_level   = params.get("ou_level", "(all)")

    # Map human-readable time_range → DHIS2 relative period code
    _PERIOD_MAP = {
        "Last 12 months": "LAST_12_MONTHS",
        "Current year":   "THIS_YEAR",
        "Last quarter":   "LAST_QUARTER",
        "Last 6 months":  "LAST_6_MONTHS",
        "Last 2 years":   "LAST_2_YEARS",
    }
    default_period = _PERIOD_MAP.get(time_range, "LAST_12_MONTHS")

    import re as _re
    m = _re.match(r"Level (\d+)", ou_level)
    default_ou = f"USER_ORGUNIT;LEVEL-{m.group(1)}" if m else "USER_ORGUNIT"

    n = len(configs)
    lines: list[str] = [
        f"Build a DHIS2 HTML dashboard with {n} chart{'s' if n != 1 else ''}.\n",
    ]
    if context_hint:
        lines.append(f"{context_hint}\n")

    lines.append(f"Default period : {default_period}")
    lines.append(f"Default ou     : {default_ou}")
    lines.append("")

    lines.append("## CHART SPECIFICATIONS — use the UIDs below exactly as given\n")
    for c in configs:
        idx        = c.get("index", "?")
        title      = c.get("title", "")
        chart_type = c.get("chart_type", "")
        de_uid     = c.get("metric_uid", "")
        prog_uid   = c.get("program_uid", "")
        stage_uid  = c.get("stage_uid", "")
        prog_name  = c.get("program_name", "")
        stage_name = c.get("stage_name", "")
        notes      = c.get("notes", "")

        lines.append(f"### Chart {idx}: {title}")
        lines.append(f"- Type         : {chart_type}")
        if notes:
            lines.append(f"- Notes        : {notes}")

        if de_uid and stage_uid and prog_uid:
            lines.append(f"- API endpoint : /api/analytics/events/aggregate/{prog_uid}")
            lines.append(f"  stage UID  = {stage_uid}   ← use in stage= param AND first part of dimension")
            lines.append(f"  DE UID     = {de_uid}   ← use in second part of dimension AND header lookup")
            lines.append(f"  COMPLETE JS FETCH URL (copy exactly, do NOT swap the UIDs):")
            lines.append(f"    dhis2Get('api/analytics/events/aggregate/{prog_uid}?stage={stage_uid}&dimension={stage_uid}.{de_uid}&dimension=pe:'+encodeURIComponent(rpe)+'&dimension=ou:'+encodeURIComponent(ou))")
            lines.append(f"  CRITICAL: dimension={stage_uid}.{de_uid}  ← stageUID.deUID order is MANDATORY")
            lines.append(f"  NO aggregationType — breakdown by option set, count is automatic")
            lines.append(f"  Response header name: '{de_uid}'  (just deUID, NOT stageUID.deUID)")
            lines.append(f"  Parse: const catIdx = d.headers.findIndex(h => h.name === '{de_uid}');")
            lines.append(f"  Row values are option CODES — use d.metaData.items[code].name for labels")
            lines.append(f"  (Program: {prog_name}, Stage: {stage_name})")
        elif de_uid:
            lines.append(f"- API endpoint : /api/analytics.json")
            lines.append(f"  params: dimension=dx:{de_uid}")
            lines.append(f"          dimension=pe:{{pe}}")
            lines.append(f"          dimension=ou:{{ou}}")
            lines.append(f"          displayProperty=NAME")
            lines.append(f"  Response columns: dx | pe | ou | value")
        else:
            lines.append("- WARNING: No data element UID configured. Render placeholder only.")
        lines.append("")

    lines.append("Arrange charts in a responsive Bootstrap grid (1–2 per row).")
    lines.append("Generate the complete dashboard HTML now.")

    dynamic_text = (
        _build_chart_catalog_snippet()
        + "\n---\n\n"
        + "\n".join(lines)
    )
    content = [
        {
            "type": "text",
            "text": f"## Available DHIS2 Metadata\n\n{metadata_context}\n\n---\n\n",
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": dynamic_text},
    ]

    # ── Debug: save prompt to disk ──────────────────────────────────────────
    try:
        from pathlib import Path
        from datetime import datetime as _dt
        _debug = Path(__file__).resolve().parent.parent / "debug"
        _debug.mkdir(exist_ok=True)
        _ts = _dt.now().strftime("%Y%m%d_%H%M%S")
        (_debug / f"{_ts}_prompt.txt").write_text(
            "=== SYSTEM PROMPT ===\n" + _SYS_FROM_SCRATCH +
            "\n\n=== USER CONTENT [0] (metadata) ===\n" + content[0]["text"] +
            "\n\n=== USER CONTENT [1] (chart specs) ===\n" + content[1]["text"],
            encoding="utf-8"
        )
    except Exception:
        pass

    client = anthropic.Anthropic(api_key=key)
    resp = client.beta.messages.create(
        model=model or _DEFAULT_MODEL,
        max_tokens=8192,
        system=[{"type": "text", "text": _SYS_FROM_SCRATCH}],
        messages=[{"role": "user", "content": content}],
        betas=["prompt-caching-2024-07-31"],
    )

    html = resp.content[0].text.strip()
    if html.startswith("```"):
        html = re.sub(r"^```[^\n]*\n", "", html)
        html = re.sub(r"\n```$", "", html.rstrip())
    return fix_cdn_links(html)


def generate_dashboard_html(
    user_prompt: str,
    cards: list[dict],
    metadata_context: str,
    api_key: str | None = None,
    model: str | None = None,
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
    _model = model or _DEFAULT_MODEL
    response = client.messages.create(
        model=_model,
        max_tokens=8192,
        system=[{"type": "text", "text": system,
                 "cache_control": {"type": "ephemeral"}}],
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
  <div id="demoBannerN" class="demo-banner">⚠ Sample data — DHIS2 not connected</div>

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
    model: str | None = None,
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

    spec_lines = [
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
        spec_lines += [
            f"\nTemplate body to adapt (chart type: {tmpl['name']}):",
            "```html", body, "```",
            "\nAdapt the template: rename IDs per spec, fill UIDs, wrap with CARD-START/END markers.",
        ]
    else:
        spec_lines.append("\nGenerate a suitable chart. Wrap output with CARD-START/END markers.")

    spec_lines.append("\nOutput ONLY the HTML fragment — no <html>/<head>/<body>.")

    client = anthropic.Anthropic(api_key=key)
    _model = model or _DEFAULT_MODEL
    response = client.messages.create(
        model=_model,
        max_tokens=4096,
        system=[{"type": "text", "text": _SYS_SINGLE_CARD,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"## Available DHIS2 Metadata\n\n{metadata_context}\n\n---\n\n",
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": "\n".join(spec_lines)},
            ],
        }],
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
