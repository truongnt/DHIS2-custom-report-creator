"""
Call Claude to generate a DHIS2 custom HTML report.

Two modes:
  1. template_html provided  → LLM fills in the UIDs and customizes the template
  2. no template             → LLM writes the full HTML from scratch
"""
from __future__ import annotations
import os
import anthropic
from llm.html_utils import fix_cdn_links

MODEL = "claude-sonnet-4-6"

_SYSTEM_FILL_TEMPLATE = """\
You are an expert DHIS2 developer.

Your task: given a base HTML report template and available DHIS2 metadata,
fill in the template with the correct indicator/data-element UIDs and customize
the report title, labels, and colors.

## Rules
1. Output ONLY valid HTML — no markdown, no explanations, no code fences.
2. Replace ALL placeholder comments:
   - <!-- REPORT_TITLE -->  → descriptive report title
   - <!-- INDICATOR_UID --> or <!-- INDICATOR_UID_N --> → real UID from the ★ PINNED or frequently-used metadata
   - <!-- BAR_INDICATOR_UID --> / <!-- LINE_INDICATOR_UID --> → real UIDs
   - <!-- TARGET_N --> → realistic numeric target (or 100 if unknown)
3. Keep ../api/analytics.json and credentials:'include' exactly as-is.
   Replace any $!{reportingPeriod} with the variable pe and $!{organisationUnit}
   with the variable ou in every analytics URL — these come from initChart(ou, pe) params.
4. Only use UIDs that exist in the provided metadata context.
   If a placeholder needs an indicator that's not pinned, pick the closest
   matching one from the "Frequently used" or "Other available" sections.
5. You MAY adjust colors (CSS hex values) to match the report theme.
6. Do NOT add or remove Chart.js datasets — keep the template structure intact.
7. If the user asks for a filter (e.g. by sex, age), add it as a filter= param
   to the analytics URL if possible (using category option combo UIDs).
8. CRITICAL — analytics URL must contain ONLY 11-character alphanumeric UIDs
   in dimension= parameters. NEVER put display names, Lao text, or any
   non-ASCII characters in a URL. UIDs look like: abc12345XYZ, gh3Kdp04NvR.

## Interactive Selectors (mandatory — NO Velocity variables)

Place immediately after <body> opening tag:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Đơn vị:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Kỳ báo cáo:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Tải dữ liệu</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare at top of <script> (once, before chart functions):
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district — match the report analysis scope

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
      await initChart(ou, pe);
      document.getElementById('lastUpdated').textContent =
        'Cập nhật: ' + new Date().toLocaleTimeString('vi-VN');
    } finally { btn.disabled = false; btn.textContent = '↻ Tải dữ liệu'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (PREVIEW) { await loadData(); return; }
    try { await loadOrgUnits(); generatePeriods(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## SAMPLE DATA / PREVIEW MODE  (bắt buộc)

Every chart init MUST accept (ou, pe) and follow this exact pattern:

  async function initChart(ou, pe) {
    document.getElementById('loading').style.display = 'none';
    const cvs = document.getElementById('chart');
    cvs.style.display = 'block';

    if (PREVIEW) {
      document.getElementById('demoBanner').style.display = 'block';
      renderChartSample(cvs);   // no DHIS2 call
      return;
    }

    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      document.getElementById('demoBanner').style.display = 'none';
      renderChartReal(cvs, d);
    } catch(e) {
      document.getElementById('demoBanner').style.display = 'block';
      renderChartSample(cvs);
    }
  }

Add above the canvas:
  <div id="demoBanner" style="background:#fff3cd;color:#856404;border:1px solid
   #ffc107;border-radius:4px;padding:3px 10px;font-size:11px;margin-bottom:6px;
   text-align:center;display:none">⚠ Dữ liệu mẫu — chưa kết nối DHIS2</div>

Sample data by chart type:
  Line/Bar monthly : labels=['T1'…'T12'], values=[120,145,98,167,134,189,210,156,143,178,192,165]
  Bar OUs          : labels=['Tỉnh A'…'E'], values=[85,102,67,143,91]
  Pie/Donut        : ['Dương tính','Âm tính','Chờ kết quả','Khác'] → [45,30,15,10]
  Scorecard        : big number 78 / target 100, green color
  Traffic light    : 3 rows with 🟢🟡🔴 icons
  Table            : 5 rows, fake org unit names + plausible numbers
"""

_SYSTEM_FROM_SCRATCH = """\
You are an expert DHIS2 developer specializing in custom HTML reports.

Your task: generate a complete, production-ready DHIS2 Standard HTML report
from a user prompt and available DHIS2 metadata.

## Rules
1. Output ONLY valid HTML — no markdown, no explanations, no code fences.
2. Use Bootstrap 5.3.2 CDN for layout (full absolute URL):
   https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
   https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js
3. Use Chart.js 4.4.0 CDN (full absolute URL):
   https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
4. Only use indicator/data-element UIDs from the ★ PINNED section of metadata.
   Fall back to "Frequently used" if pinned section is empty.
5. CRITICAL — analytics URL dimension= values must be 11-char alphanumeric UIDs ONLY.
   NEVER put display names, Lao/non-ASCII text, or spaces in any URL.
   Wrong: dimension=dx:ຈຳນວນຜູ້ປ່ວຍ  ← causes HTTP 400 on server
   Right: dimension=dx:abc12345XYZ
6. Add to <style>:
   .demo-banner { background:#fff3cd; color:#856404; border:1px solid #ffc107;
     border-radius:4px; padding:3px 10px; font-size:11px; margin-bottom:6px;
     text-align:center; display:none; }

## Interactive Selectors (mandatory — NO Velocity variables)

Place immediately after <body> opening tag:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Đơn vị:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Kỳ báo cáo:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Tải dữ liệu</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare at top of <script> (once, before chart functions):
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district — match the report analysis scope

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
      await initChart(ou, pe);
      document.getElementById('lastUpdated').textContent =
        'Cập nhật: ' + new Date().toLocaleTimeString('vi-VN');
    } finally { btn.disabled = false; btn.textContent = '↻ Tải dữ liệu'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (PREVIEW) { await loadData(); return; }
    try { await loadOrgUnits(); generatePeriods(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## SAMPLE DATA / PREVIEW MODE  (bắt buộc — chart phải luôn hiển thị)

Every initChart function MUST accept (ou, pe) and follow this pattern exactly:

  async function initChart(ou, pe) {
    document.getElementById('loading').style.display = 'none';
    const cvs = document.getElementById('chart');
    cvs.style.display = 'block';

    if (PREVIEW) {
      // Không gọi DHIS2 — hiển thị sample data ngay
      document.getElementById('demoBanner').style.display = 'block';
      renderChartSample(cvs);
      return;
    }

    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      document.getElementById('demoBanner').style.display = 'none';
      renderChartReal(cvs, d);
    } catch(e) {
      document.getElementById('demoBanner').style.display = 'block';
      renderChartSample(cvs);
    }
  }

  function renderChartSample(cvs) {
    new Chart(cvs, { /* sample data — see below */ });
  }

Place above each canvas:
  <div id="demoBanner" class="demo-banner">⚠ Dữ liệu mẫu — chưa kết nối DHIS2</div>

Sample data by chart type:
  Line/Bar monthly : labels=['T1','T2','T3','T4','T5','T6','T7','T8','T9','T10','T11','T12']
                     values=[120,145,98,167,134,189,210,156,143,178,192,165]
  Bar OUs          : labels=['Tỉnh A','Tỉnh B','Tỉnh C','Tỉnh D','Tỉnh E'], values=[85,102,67,143,91]
  Pie/Donut        : labels=['Dương tính','Âm tính','Chờ kết quả','Khác'], data=[45,30,15,10]
  Scorecard        : large number 78, target 100, background #27ae60 (green)
  Traffic light    : 3 rows with indicator name + value + 🟢/🟡/🔴 icon
  Table            : 5 rows × 3 cols, org unit names + plausible numbers
"""


def generate_report_html(
    user_prompt: str,
    metadata_context: str,
    api_key: str | None = None,
    template_html: str | None = None,
    template_name: str | None = None,
) -> str:
    """
    Returns the final HTML string.
    If template_html is provided, LLM fills placeholders.
    Otherwise LLM writes from scratch.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)

    if template_html:
        system = _SYSTEM_FILL_TEMPLATE
        user_content = (
            f"## Available DHIS2 Metadata\n\n"
            f"{metadata_context}\n\n"
            f"---\n\n"
            f"## Report Requirement\n\n"
            f"{user_prompt}\n\n"
            f"---\n\n"
            f"## Base Template to Fill In"
            + (f"  ({template_name})" if template_name else "") + "\n\n"
            f"```html\n{template_html}\n```\n\n"
            f"Fill in all <!-- ... --> placeholder comments with real values from the metadata above. "
            f"Output only the completed HTML."
        )
    else:
        system = _SYSTEM_FROM_SCRATCH
        user_content = (
            f"## Available DHIS2 Metadata\n\n"
            f"{metadata_context}\n\n"
            f"---\n\n"
            f"## Report Requirement\n\n"
            f"{user_prompt}\n\n"
            f"Generate the complete HTML report now."
        )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    html = response.content[0].text.strip()

    # Strip any accidental markdown fences
    if html.startswith("```"):
        lines = html.splitlines()
        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    return fix_cdn_links(html)
