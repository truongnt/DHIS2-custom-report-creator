"""Multi-turn chat generation for DHIS2 reports."""
from __future__ import annotations
import os
import anthropic
from llm.html_utils import fix_cdn_links

MODEL = "claude-sonnet-4-6"

_SYSTEM_PLAN = """\
Bạn là trợ lý giúp người dùng xác định yêu cầu báo cáo DHIS2.
Trả lời ngắn gọn bằng tiếng Việt (2-4 câu).

Những gì cần làm rõ (nếu chưa biết):
- Chỉ số / data element nào cần hiển thị
- Kỳ báo cáo (tháng, quý, năm)
- Phân tích theo gì (theo tỉnh, theo huyện, theo tháng…)
- Loại biểu đồ muốn dùng (nếu có yêu cầu)
- Bộ lọc nào (giới tính, nhóm tuổi…)

Khi đã đủ thông tin: tóm tắt lại yêu cầu và bảo người dùng bấm "Generate HTML Report".
KHÔNG tự tạo HTML — chờ người dùng bấm Generate.
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
4. DHIS2 analytics: ../api/analytics.json with credentials:'include'
5. Only use UIDs from ★ PINNED metadata. Fall back to Frequently used.
6. CRITICAL — dimension= must contain 11-char alphanumeric UIDs ONLY.
   NEVER put display names or non-ASCII text in URLs. That causes HTTP 400.
7. .demo-banner { background:#fff3cd;color:#856404;border:1px solid #ffc107;
   border-radius:4px;padding:3px 10px;font-size:11px;margin-bottom:6px;
   text-align:center;display:none; }

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

Declare at top of <script>:
  const PREVIEW = window.location.protocol === 'file:';
  const OU_LEVEL = 2;  // 2=province 3=district

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
      await initChart(ou, pe);  // for multi-chart: Promise.all([initChart1(ou,pe), ...])
      document.getElementById('lastUpdated').textContent =
        'Cập nhật: ' + new Date().toLocaleTimeString('vi-VN');
    } finally { btn.disabled = false; btn.textContent = '↻ Tải dữ liệu'; }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    if (PREVIEW) { await loadData(); return; }
    try { await loadOrgUnits(); generatePeriods(); await loadData(); }
    catch(e) { console.error('Init error:', e); }
  });

## PREVIEW MODE (mandatory for every chart)

Every chart init MUST accept (ou, pe) and follow:
  async function initChart(ou, pe) {
    if (PREVIEW) { showBanner(); renderSample(cvs); return; }
    try {
      const d = await dhis2Get('api/analytics.json?dimension=dx:UID&dimension=pe:' + pe + '&dimension=ou:' + ou + '&displayProperty=NAME');
      if (!d.rows || d.rows.length === 0) throw new Error('no-data');
      renderReal(cvs, d);
    } catch(e) { showBanner(); renderSample(cvs); }
  }

Sample data: Line/Bar ['T1'…'T12'] [120,145,98,167,134,189,210,156,143,178,192,165]
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


def chat_plan(messages: list[dict], metadata_context: str, api_key: str) -> str:
    """Get assistant response during pre-generate planning phase. Returns plain text."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)

    # Inject metadata as a hidden context turn before conversation
    full_messages = [
        {
            "role": "user",
            "content": (
                f"[Metadata DHIS2 hiện có — dùng để tư vấn, không hiển thị cho user]\n"
                f"{metadata_context}\n"
                f"Bắt đầu hỗ trợ người dùng."
            ),
        },
        {"role": "assistant", "content": "Xin chào! Tôi sẽ giúp bạn tạo báo cáo DHIS2. Bạn cần báo cáo gì?"},
    ] + messages

    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_SYSTEM_PLAN,
        messages=full_messages,
    )
    return response.content[0].text.strip()


def generate_from_chat(
    messages: list[dict],
    metadata_context: str,
    api_key: str,
) -> str:
    """
    Generate HTML from conversation history (no layout — from scratch).
    For layout-based generation, app_window uses dashboard_generator/report_generator directly.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)

    conversation = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages
    )

    user_content = (
        f"## Available DHIS2 Metadata\n\n{metadata_context}\n\n"
        f"---\n\n"
        f"## Conversation (requirements):\n\n{conversation}\n\n"
        f"---\n\n"
        f"Generate the complete HTML report based on the conversation above."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=_SYSTEM_GENERATE,
        messages=[{"role": "user", "content": user_content}],
    )

    html = response.content[0].text.strip()
    if html.startswith("```"):
        lines = html.splitlines()
        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return fix_cdn_links(html)


def refine_from_chat(
    request: str,
    current_html: str,
    metadata_context: str,
    api_key: str,
) -> str:
    """
    Refine current HTML based on the user's latest request.
    Returns updated complete HTML.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=key)

    user_content = (
        f"## Current HTML Report\n\n```html\n{current_html}\n```\n\n"
        f"---\n\n"
        f"## Modification Request\n\n{request}\n\n"
        f"---\n\n"
        f"## Available DHIS2 Metadata (for UID lookups)\n\n{metadata_context}\n\n"
        f"---\n\n"
        f"Apply the modification and output the complete updated HTML."
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=_SYSTEM_REFINE,
        messages=[{"role": "user", "content": user_content}],
    )

    html = response.content[0].text.strip()
    if html.startswith("```"):
        lines = html.splitlines()
        html = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    return fix_cdn_links(html)
