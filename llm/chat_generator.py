"""Multi-turn chat generation for DHIS2 reports."""
from __future__ import annotations
import os
import anthropic
from llm.html_utils import fix_cdn_links

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PLAN = """\
Bạn là trợ lý giúp người dùng xác định yêu cầu báo cáo DHIS2.
Trả lời bằng tiếng Việt, ngắn gọn (3-5 câu mỗi lượt).

## Lượt đầu tiên — LUÔN làm 2 việc này trước:
1. Tóm tắt nhanh metadata đang có: liệt kê programs, datasets, nhóm chỉ số chính.
   Ví dụ: "Metadata có 3 programs (ANC, Malaria, HIV), 2 datasets (OPD, IPD),
   ~120 indicators chưa lọc — nếu generate ngay có thể bị bias (chọn sai chỉ số)."
2. Hỏi 1 câu để thu hẹp phạm vi (mảng nào, chương trình nào).

## Các lượt tiếp theo — làm rõ dần:
- Chỉ số / data element cụ thể cần hiển thị
- Kỳ báo cáo (tháng, quý, năm) và khoảng thời gian
- Phân tích theo đơn vị gì (tỉnh, huyện, cơ sở…)
- Loại biểu đồ (nếu có yêu cầu)
- Bộ lọc (giới tính, nhóm tuổi…)

## Khi đã đủ thông tin:
Tóm tắt: chỉ số đã chọn + kỳ + đơn vị + loại biểu đồ.
Bảo người dùng bấm "Generate HTML Report".
KHÔNG tự tạo HTML.

## Lưu ý:
Metadata chưa lọc rất lớn → LLM dễ chọn sai UID (bias). Phải hỏi để thu hẹp scope
trước khi generate. Nếu metadata quá nhiều thông tin không liên quan, hãy nói thẳng.
"""

_SYSTEM_GENERATE = """\
You are an expert DHIS2 developer. Based on the conversation history below,
generate a complete production-ready DHIS2 Standard HTML report.

## Rules
1. Output ONLY valid HTML — no markdown, no explanations, no code fences.
2. Bootstrap 5.3.2 CDN (full absolute URLs):
   https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css
   https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js
3. Chart.js 4.4.0 CDN (full absolute URL):
   https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js
4. Only use UIDs from ★ PINNED metadata. Fall back to Frequently used.
5. CRITICAL — dimension= must contain 11-char alphanumeric UIDs ONLY.
   NEVER put display names or non-ASCII text in URLs. That causes HTTP 400.
6. .demo-banner { background:#fff3cd;color:#856404;border:1px solid #ffc107;
   border-radius:4px;padding:3px 10px;font-size:11px;margin-bottom:6px;
   text-align:center;display:none; }

## Analytics API — two endpoints, different response structures

### Org unit dimension values (same for both endpoints)
  USER_ORGUNIT             — user's own assigned org units (DHIS2 Visualizer default)
  USER_ORGUNIT_CHILDREN    — one level below user's org units
  USER_ORGUNIT_GRANDCHILDREN — two levels below
  {specificUID}            — a single specific org unit
  Use as dimension= for OU breakdown charts; use as filter= for totals/trend.

### Aggregate analytics  (for data elements & indicators from dataSets)
  GET ../api/analytics.json?dimension=dx:{deUID}&dimension=pe:{pe}&dimension=ou:{ou}
  Response headers always: dx | pe | ou | value
  Parse:  const valIdx = d.headers.findIndex(h => h.name === 'value');
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');
  Relative periods (LAST_MONTH, LAST_12_MONTHS, THIS_YEAR…) are supported here directly.

### Event analytics  (for tracker programs — programStages)
  Use /events/AGGREGATE (not /events/query) — response includes a "value" column:
  GET ../api/analytics/events/aggregate/{programUID}?stage={stageUID}&dimension=pe:{rpe}&dimension=ou:{ou}&aggregationType=COUNT
  Response headers: pe | ou | value   (value = count of events)
  Parse:  const valIdx = d.headers.findIndex(h => h.name === 'value');
          const peIdx  = d.headers.findIndex(h => h.name === 'pe');
          const ouIdx  = d.headers.findIndex(h => h.name === 'ou');

  To break down by a categorical DE option (e.g. test result):
  GET .../events/aggregate/{programUID}?stage={stageUID}&dimension={stageUID}.{deUID}&dimension=pe:{rpe}&filter=ou:{ou}&aggregationType=COUNT
  Response headers: {stageUID}.{deUID} | pe | value
  Parse:  const catIdx = d.headers.findIndex(h => h.name === '{stageUID}.{deUID}');

  ALWAYS call resolveRelativePeriod(pe) before using pe in /events/aggregate URLs:
    const rpe = resolveRelativePeriod(pe);   // converts LAST_MONTH → '202504' etc.
  Reason: some DHIS2 servers reject relative period strings in this endpoint.
  NEVER use /events/query for charting — it returns raw event rows with no "value" column.

## Language & labels
- All user-visible text in the report MUST be in English only — no Vietnamese, no Lao.
- Org unit selector label: "Org unit:" (never "Province:", "Tỉnh:", "Đơn vị:")
- Period selector label: "Period:" (never "Kỳ báo cáo:")
- Load button: "↻ Load data" (never "Tải dữ liệu")
- Period dropdown: relative periods first (LAST_MONTH, LAST_12_MONTHS, THIS_YEAR…), then fixed monthly/quarterly/yearly
- Chart titles, axis labels, legends, table headers: English only
- Org unit names: always use o.displayName from DHIS2 — never hardcode place names
- Demo banner: "⚠ Sample data — DHIS2 not connected"

## Interactive Selectors (mandatory — NO Velocity variables)

Place immediately after <body> opening tag:
<div id="controls" style="background:#f0f4f8;border-bottom:1px solid #d0dde8;padding:10px 20px;display:flex;gap:12px;align-items:center;flex-wrap:wrap;position:sticky;top:0;z-index:100;">
  <label style="font-weight:600;margin:0;font-size:13px">Org unit:</label>
  <select id="ouSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <label style="font-weight:600;margin:0;font-size:13px">Period:</label>
  <select id="peSelect" style="padding:4px 8px;border:1px solid #ced4da;border-radius:4px;font-size:13px"></select>
  <button id="loadBtn" onclick="loadData()" style="padding:5px 16px;background:#1a6fa8;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:13px">↻ Load data</button>
  <span id="lastUpdated" style="font-size:11px;color:#6c757d;margin-left:8px"></span>
</div>

Declare at top of <script>:
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district

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
  }

  async function loadData() {
    const ou = document.getElementById('ouSelect').value;
    const pe = document.getElementById('peSelect').value;
    const btn = document.getElementById('loadBtn');
    btn.disabled = true; btn.textContent = '⏳ Loading...';
    try {
      await initChart(ou, pe);  // for multi-chart: Promise.all([initChart1(ou,pe), ...])
      document.getElementById('lastUpdated').textContent =
        'Updated: ' + new Date().toLocaleTimeString();
    } finally { btn.disabled = false; btn.textContent = '↻ Load data'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (PREVIEW) { await loadData(); return; }
    try { await loadOrgUnits(); generatePeriods(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## PREVIEW MODE (mandatory for every chart)

Every chart init MUST accept (ou, pe) and follow this EXACT two-path structure:
  async function initChart(ou, pe) {
    if (PREVIEW) { showBanner(); renderSample(cvs); return; }
    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      renderReal(cvs, d);   // ← receives actual API response
    } catch(e) { console.error('[DHIS2]', e); showBanner(); renderSample(cvs); }
  }

## CRITICAL — Two separate render functions, zero crossover

renderSample(canvas):
  - Contains ALL hardcoded arrays (e.g. [120,145,98,...])
  - Called ONLY when PREVIEW=true or API fails
  - NEVER called on the host with real data

renderReal(canvas, apiData):
  - MUST compute every value from apiData.rows — NO hardcoded numbers
  - Parse d.headers to find column indices, then map d.rows
  - NEVER copy sample arrays into this function
  - Fallback value for missing data: 0, not a hardcoded number

WRONG (do NOT do this):
  function renderReal(canvas, d) {
    const values = [120, 145, 98, ...];  // ← hardcoded — this is a BUG
    new Chart(canvas, {data: {datasets: [{data: values}]}});
  }

CORRECT:
  function renderReal(canvas, d) {
    const dxIdx = d.headers.findIndex(h => h.name === 'value');
    const peIdx = d.headers.findIndex(h => h.name === 'pe');
    const values = d.rows.map(r => parseFloat(r[dxIdx]) || 0);
    new Chart(canvas, {data: {datasets: [{data: values}]}});
  }

Sample data (for renderSample ONLY): Line/Bar ['T1'…'T12'] [120,145,98,167,134,189,210,156,143,178,192,165]
  Bar OUs ['Tỉnh A'…'E'] [85,102,67,143,91] | Pie/Donut [45,30,15,10]
  Scorecard 78/100 green | Table 5×3 rows
"""

_SYSTEM_REFINE = """\
You are an expert DHIS2 developer. Apply the user's modification to the HTML report.
Output the complete UPDATED HTML — apply the change, keep everything else intact.

## Rules (same as original generation — preserve all of these)
1. Output ONLY valid HTML — no markdown, no explanations, no code fences.
2. Keep Bootstrap 5.3.2 and Chart.js 4.4.0 CDN absolute URLs.
3. Keep ../api/analytics.json with credentials:'include'.
4. Keep the interactive controls bar (#ouSelect, #peSelect, #loadBtn).
5. Keep PREVIEW pattern (const PREVIEW = window.location.protocol === 'file:';).
6. Keep initChart(ou, pe) signatures — charts receive ou and pe from loadData().
7. CRITICAL: dimension= must contain 11-char alphanumeric UIDs ONLY. Never display names.
8. Apply ONLY the requested changes — do not restructure or rewrite unnecessarily.
"""


def chat_plan(messages: list[dict], metadata_context: str, api_key: str,
              model: str | None = None) -> str:
    """Get assistant response during pre-generate planning phase. Returns plain text."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)
    _model = model or _DEFAULT_MODEL

    # The metadata context turn is the same across all planning messages in a session
    # — cache it so repeated turns only pay the cheap cache-read rate.
    meta_turn = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": (
                    f"[Metadata DHIS2 — đã tải, dùng để tư vấn và lọc, không hiển thị cho user]\n"
                    f"{metadata_context}\n"
                    f"---\n"
                    f"Hãy tóm tắt metadata này (programs, datasets, số lượng chỉ số) "
                    f"và hỏi để thu hẹp scope khi user gửi tin đầu tiên."
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }
    ack_turn = {
        "role": "assistant",
        "content": (
            "Đã tải metadata DHIS2. Tôi sẽ tóm tắt những gì có và hỏi để lọc "
            "thông tin phù hợp trước khi generate — tránh bias do metadata quá lớn."
        ),
    }
    full_messages = [meta_turn, ack_turn] + messages

    response = client.messages.create(
        model=_model,
        max_tokens=512,
        system=_SYSTEM_PLAN,
        messages=full_messages,
    )
    return response.content[0].text.strip()


def generate_from_chat(
    messages: list[dict],
    metadata_context: str,
    api_key: str,
    model: str | None = None,
) -> str:
    """
    Generate HTML from conversation history (no layout — from scratch).
    For layout-based generation, app_window uses dashboard_generator/report_generator directly.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)
    _model = model or _DEFAULT_MODEL

    conversation = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages
    )

    response = client.messages.create(
        model=_model,
        max_tokens=8192,
        system=[{"type": "text", "text": _SYSTEM_GENERATE,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"## Available DHIS2 Metadata\n\n{metadata_context}\n\n---\n\n",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": (
                        f"## Conversation (requirements):\n\n{conversation}\n\n"
                        f"---\n\nGenerate the complete HTML report based on the conversation above."
                    ),
                },
            ],
        }],
    )

    html = response.content[0].text.strip()
    if html.startswith("```"):
        lines = html.splitlines()
        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return fix_cdn_links(html)


_SYSTEM_FILTER_CONTEXT = """\
You are a DHIS2 metadata filter.

Given a planning conversation and full metadata context, output a COMPACT version
containing ONLY what is needed for the described report.

Rules:
1. Always keep the entire ★ PINNED section.
2. Keep ONLY programs, datasets, indicator groups, and indicators that are
   mentioned or clearly relevant to the report topic in the conversation.
3. Remove ALL unrelated programs, datasets, and their indicators.
4. Preserve the exact text format of every section you keep.
5. Output ONLY the filtered metadata text — no explanations, no extra headings.
"""


def filter_metadata_context(
    conversation_messages: list[dict],
    full_context: str,
    api_key: str,
) -> str:
    """
    Return a compact metadata context filtered to only what the planning
    conversation is about. Uses Haiku for speed/cost.
    Falls back to full_context on any error.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return full_context

    conv_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in conversation_messages
    )
    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            system=_SYSTEM_FILTER_CONTEXT,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## Full Metadata Context\n\n{full_context}\n\n---\n\n",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": (
                            f"## Planning Conversation\n\n{conv_text}\n\n"
                            f"---\n\nOutput the filtered metadata context."
                        ),
                    },
                ],
            }],
        )
        filtered = resp.content[0].text.strip()
        return filtered if filtered else full_context
    except Exception:
        return full_context


_SYSTEM_PLAN_DES = """\
You are a DHIS2 analytics planner. Given a planning conversation and metadata context,
identify the specific data elements or indicators that would be queried in the analytics API.

Return ONLY a valid JSON array — no markdown fences, no explanation:
[
  {
    "id": "<11-char UID from metadata>",
    "displayName": "<exact name from metadata>",
    "type": "data_element",
    "reason": "<tại sao chọn cái này, tiếng Việt, tối đa 8 chữ>"
  }
]

Rules:
- 1-10 items maximum
- All UIDs MUST come from the provided metadata — never invent UIDs
- type: data_element | program_indicator | indicator
- Only items you would use in dimension=dx: in the analytics API
- If no matching DE found, return []
"""


def plan_des_for_report(
    messages: list[dict],
    context: str,
    api_key: str,
    swaps: dict[str, str] | None = None,
    base_url: str | None = None,
) -> list[dict]:
    """
    Ask LLM (Haiku) to select which DEs it would query for the report.
    Returns list of {id, displayName, type, reason}, applying any known swaps.
    Returns [] on failure (caller should skip DE review step).
    """
    import json as _json

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return []

    # Load known-bad UIDs (avoid) and top confirmed UIDs (prefer)
    known_invalid: set[str] = set()
    top_confirmed: list[tuple[str, str]] = []
    if base_url:
        try:
            from dhis2.de_preferences import get_known_invalid_uids, get_top_confirmed_uids
            known_invalid  = get_known_invalid_uids(base_url)
            top_confirmed  = get_top_confirmed_uids(base_url, top_n=20)
        except Exception:
            pass

    conv_text = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages
    )

    dynamic_tail = f"## Planning conversation\n\n{conv_text}\n\n---\n\n"
    if top_confirmed:
        hints = "\n".join(f"  - {uid}  {name}" for uid, name in top_confirmed)
        dynamic_tail += (
            f"## PREFERRED UIDs — user-confirmed in past reports (prefer these if relevant)\n"
            f"{hints}\n\n---\n\n"
        )
    if known_invalid:
        uid_list = "\n".join(f"  - {uid}" for uid in sorted(known_invalid))
        dynamic_tail += (
            f"## KNOWN INVALID UIDs — DO NOT USE THESE\n"
            f"These UIDs have failed verification in past reports — never include them:\n"
            f"{uid_list}\n\n---\n\n"
        )
    dynamic_tail += "Select the DEs for this report."

    try:
        client = anthropic.Anthropic(api_key=key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=_SYSTEM_PLAN_DES,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"## Available metadata\n\n{context}\n\n---\n\n",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": dynamic_tail,
                    },
                ],
            }],
        )
        raw = resp.content[0].text.strip()
        # Strip accidental markdown fences
        if raw.startswith("```"):
            lines = raw.splitlines()
            raw = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        # Extract just the JSON array — handles extra text before/after the array
        start = raw.find('[')
        end   = raw.rfind(']')
        if start != -1 and end != -1 and end > start:
            raw = raw[start:end + 1]
        planned: list[dict] = _json.loads(raw)
        if not isinstance(planned, list):
            return []
        # Apply saved swaps: replace original id with preferred id from metadata
        if swaps:
            for item in planned:
                preferred = swaps.get(item.get("id", ""))
                if preferred:
                    item["id"] = preferred
                    item["_was_swapped"] = True
        return planned
    except Exception as exc:
        import traceback
        traceback.print_exc()
        print(f"[plan_des_for_report] failed: {exc}")
        return []


def refine_from_chat(
    request: str,
    current_html: str,
    metadata_context: str,
    api_key: str,
    model: str | None = None,
) -> str:
    """
    Refine current HTML based on the user's latest request.
    Returns updated complete HTML.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)
    _model = model or _DEFAULT_MODEL

    # Metadata context is identical across all refine calls in a session — cache it.
    # HTML goes after (changes each refine, not cacheable).
    response = client.messages.create(
        model=_model,
        max_tokens=8192,
        system=[{"type": "text", "text": _SYSTEM_REFINE,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"## Available DHIS2 Metadata (for UID lookups)\n\n{metadata_context}\n\n---\n\n",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": (
                        f"## Current HTML Report\n\n```html\n{current_html}\n```\n\n"
                        f"---\n\n"
                        f"## Modification Request\n\n{request}\n\n"
                        f"---\n\nApply the modification and output the complete updated HTML."
                    ),
                },
            ],
        }],
    )

    html = response.content[0].text.strip()
    if html.startswith("```"):
        lines = html.splitlines()
        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return fix_cdn_links(html)
