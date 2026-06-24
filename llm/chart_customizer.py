"""
AI-powered Chart.js options customizer.

User types natural language requests ("show data labels", "thinner bars",
"change color to green") and Claude returns a JSON patch of Chart.js options
that is merged into the chart's config at render time.
"""
from __future__ import annotations
import json
import re
import anthropic

SYSTEM_PROMPT = """\
You are a Chart.js v4 expert. The user wants to customize a chart.
Given the chart type and user request, return ONLY a JSON object with
Chart.js options/dataset properties to merge into the existing chart config.

Rules:
- Return ONLY valid JSON, no markdown fences, no explanation text.
- Only include fields that need to change.
- Use Chart.js v4 (not v2/v3) syntax.
- For colors use hex strings like "#e74c3c".
- Dataset-level properties go inside: {"datasets": [{"key": value}]}
- Chart-level options go directly: {"plugins": {...}, "scales": {...}}

Common examples:
"show data labels / hiển thị số / show values on bars"
  → {"plugins":{"showValues":{"display":true,"color":"#333","fontSize":11}}}

"show values inside bars / label màu trắng bên trong"
  → {"plugins":{"showValues":{"display":true,"color":"white","fontSize":10}}}

"no legend / ẩn legend"
  → {"plugins":{"legend":{"display":false}}}

"thinner bars / cột mỏng hơn"
  → {"datasets":[{"barThickness":18,"maxBarThickness":24}]}

"wider bars / cột dày hơn"
  → {"datasets":[{"barThickness":40,"maxBarThickness":50}]}

"smooth line / line mượt"
  → {"datasets":[{"tension":0.5,"fill":true}]}

"no fill under line"
  → {"datasets":[{"fill":false}]}

"change color to red / đổi màu đỏ"
  → {"datasets":[{"backgroundColor":"#e74c3c","borderColor":"#e74c3c"}]}

"add title: My Chart"
  → {"plugins":{"title":{"display":true,"text":"My Chart","font":{"size":16}}}}

"no grid lines"
  → {"scales":{"x":{"grid":{"display":false}},"y":{"grid":{"display":false}}}}

"start y-axis at 0"
  → {"scales":{"y":{"beginAtZero":true}}}

"horizontal bars"
  → {"indexAxis":"y"}

"show percentage labels"
  → {"plugins":{"showValues":{"display":true,"color":"#333","fontSize":10}}}
"""


def customize_chart(
    template_label: str,
    current_custom_options: dict,
    user_request: str,
    api_key: str,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """
    Call Claude with the user's customization request.
    Returns a JSON dict of Chart.js options to merge into current_custom_options.
    """
    client = anthropic.Anthropic(api_key=api_key)

    context = (
        f"Chart template: {template_label}\n"
        f"Existing custom options so far: {json.dumps(current_custom_options) if current_custom_options else 'none'}\n"
        f"User request: {user_request}"
    )

    msg = client.messages.create(
        model=model,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
    )

    text = msg.content[0].text.strip()

    # Strip markdown fences if present
    text = re.sub(r"^```[a-z]*\n?", "", text).rstrip("`").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting first JSON object from text
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        return {}


def deep_merge(base: dict, patch: dict) -> dict:
    """Deep-merge patch into base, returning new dict."""
    result = dict(base)
    for k, v in patch.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        elif k == "datasets" and isinstance(v, list) and isinstance(result.get(k), list):
            # Merge first dataset entry
            merged_ds = []
            for i, ds in enumerate(result[k]):
                patch_ds = v[i] if i < len(v) else {}
                merged_ds.append({**ds, **patch_ds})
            result[k] = merged_ds
        else:
            result[k] = v
    return result
