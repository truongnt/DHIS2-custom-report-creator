"""AI dashboard planner — recommends which charts to build from user intent.

Usage (real API):
    context = build_context(metadata, descriptions)
    recs = recommend_charts(user_intent, context, ai_client=client)

Usage (mock / testing — no API calls):
    recs = recommend_charts(user_intent, context, mock_key="malaria_overview")
    # or:
    recs = recommend_charts(user_intent, context, mock_response=[...])

Returns list[dict]:
    [
      {
        "title":      "Monthly Malaria Cases",
        "chart_type": "bar_monthly",      ← template_id from FIXED_TEMPLATES
        "de_uid":     "abc123",
        "rationale":  "Track monthly caseload trend"
      },
      ...
    ]
Use recs_to_chart_configs() to convert to chart config dicts for generate_preview_page().
"""
from __future__ import annotations
import json
import re

# ── Template catalog ─────────────────────────────────────────────────────────

CHART_TYPE_CATALOG = [
    {"id": "bar",               "label": "Bar chart",              "best_for": "comparing values across categories or org units at one time point"},
    {"id": "bar_monthly",       "label": "Bar — monthly trend",    "best_for": "showing a single indicator's monthly progression over time"},
    {"id": "line_trend",        "label": "Line — trend over time", "best_for": "time-series trend of a single numeric indicator"},
    {"id": "line_multi",        "label": "Line — compare multiple","best_for": "comparing trends of 2–3 indicators on one chart"},
    {"id": "stacked_cat",       "label": "Stacked bar by category","best_for": "category breakdown totals per period (e.g. test outcomes by month)"},
    {"id": "pie_cat",           "label": "Pie — by category",      "best_for": "proportion breakdown of categorical indicator at one time point"},
    {"id": "grouped_bar",       "label": "Grouped bar",            "best_for": "side-by-side comparison of 2–3 indicators across periods"},
    {"id": "scorecard",         "label": "Scorecard",              "best_for": "displaying a single key number prominently as a KPI"},
    {"id": "bar_ou",            "label": "Bar — by org unit",      "best_for": "comparing same indicator across org units (facility/district ranking)"},
    {"id": "combined_bar_line", "label": "Combined bar + line",    "best_for": "volume (bars) vs rate/target (line) on the same chart"},
    {"id": "table_view",        "label": "Data Table",             "best_for": "detailed row-by-row data view with multiple columns"},
    {"id": "area_map",          "label": "Area Map (choropleth)",  "best_for": "geographic distribution by district/province colored by value"},
    {"id": "point_map",         "label": "Point Map (bubble)",     "best_for": "facility-level geographic distribution where bubble size = value"},
]

_CATALOG_TEXT = "\n".join(
    f"  {c['id']}: {c['label']} — {c['best_for']}"
    for c in CHART_TYPE_CATALOG
)

# ── Mock scenarios for offline/test use ─────────────────────────────────────

MOCK_SCENARIOS: dict[str, list[dict]] = {
    "malaria_overview": [
        {"title": "Monthly Malaria Cases",
         "chart_type": "bar_monthly",   "de_uid": "__FIRST__",
         "rationale": "Show monthly caseload trend for the primary indicator"},
        {"title": "Cases by District",
         "chart_type": "area_map",      "de_uid": "__FIRST__",
         "rationale": "Geographic spread — which districts have highest burden"},
        {"title": "Test Positivity Rate",
         "chart_type": "scorecard",     "de_uid": "__SECOND__",
         "rationale": "Key KPI visible at a glance"},
        {"title": "Cases by Test Result",
         "chart_type": "stacked_cat",   "de_uid": "__FIRST__",
         "rationale": "Breakdown by outcome category (positive/negative/pending)"},
        {"title": "Facility Ranking",
         "chart_type": "bar_ou",        "de_uid": "__FIRST__",
         "rationale": "Identify highest-burden facilities"},
    ],
    "supply_chain": [
        {"title": "Stock Status by Facility",
         "chart_type": "bar_ou",        "de_uid": "__FIRST__",
         "rationale": "Compare stock levels across facilities"},
        {"title": "Stock Trend Over Time",
         "chart_type": "line_trend",    "de_uid": "__FIRST__",
         "rationale": "Detect downward stock trends early"},
        {"title": "Supply Coverage Map",
         "chart_type": "area_map",      "de_uid": "__FIRST__",
         "rationale": "Geographic view of supply coverage by district"},
        {"title": "Current National Stock",
         "chart_type": "scorecard",     "de_uid": "__SECOND__",
         "rationale": "National aggregate KPI at a glance"},
    ],
    "performance_review": [
        {"title": "Key Indicator Trend",
         "chart_type": "line_trend",    "de_uid": "__FIRST__",
         "rationale": "Monthly performance trajectory for the primary indicator"},
        {"title": "Compare Indicators",
         "chart_type": "line_multi",    "de_uid": "__FIRST__",
         "rationale": "Multi-indicator comparison over time"},
        {"title": "District Performance Map",
         "chart_type": "area_map",      "de_uid": "__FIRST__",
         "rationale": "Identify which districts are lagging"},
        {"title": "Facility Ranking",
         "chart_type": "bar_ou",        "de_uid": "__FIRST__",
         "rationale": "Top/bottom facility performers"},
        {"title": "Actual vs Target",
         "chart_type": "combined_bar_line", "de_uid": "__FIRST__",
         "rationale": "Bars = actual volume, line = target for gap analysis"},
    ],
}


# ── Context builder ──────────────────────────────────────────────────────────

def build_context(
    metadata: dict,
    descriptions: dict[str, str],
    max_items: int = 80,
) -> dict:
    """Build planner context from loaded metadata + local descriptions.

    metadata   : dict returned by dhis2.metadata.fetch_all()
    descriptions: {uid: description_text} from config.descriptions.load_descriptions()
    Returns    : dict with keys: de_list, chart_types
    """
    de_list: list[dict] = []

    def _add(items: list[dict], kind: str) -> None:
        for item in items or []:
            uid  = item.get("id", "")
            name = item.get("displayName", "")
            desc = descriptions.get(uid, "")
            de_list.append({"uid": uid, "name": name, "kind": kind, "description": desc})

    _add(metadata.get("indicators", []),                    "indicator")
    _add(metadata.get("program_indicators", []),            "program_indicator")
    _add(metadata.get("data_elements", []),                 "data_element")
    _add(metadata.get("program_stage_data_elements", []),   "tracker_de")
    _add(metadata.get("tracked_entity_attributes", []),     "tracked_attr")

    return {
        "de_list":     de_list[:max_items],
        "chart_types": CHART_TYPE_CATALOG,
    }


# ── Prompt builder ───────────────────────────────────────────────────────────

def _build_prompt(user_intent: str, context: dict) -> str:
    de_lines = "\n".join(
        "  - uid={uid} name={name!r} kind={kind}".format(**d)
        + (f" description={d['description']!r}" if d["description"] else "")
        for d in context["de_list"]
    )
    return (
        f"You are a DHIS2 dashboard design assistant.\n\n"
        f"User request: {user_intent}\n\n"
        f"Available data elements / indicators:\n"
        f"{de_lines or '  (none provided)'}\n\n"
        f"Available chart types:\n{_CATALOG_TEXT}\n\n"
        f"Return a JSON array of 3–6 chart recommendations. Each item MUST have:\n"
        f"  - title: short descriptive chart title (string)\n"
        f"  - chart_type: one of the chart type IDs listed above (string)\n"
        f"  - de_uid: UID of the data element / indicator from the list above (string)\n"
        f"  - rationale: one sentence explaining why this chart is useful (string)\n\n"
        f"Return ONLY the JSON array, no markdown, no text outside the array."
    )


# ── UID placeholder resolution for mock scenarios ────────────────────────────

def _resolve_placeholders(recs: list[dict], de_list: list[dict]) -> list[dict]:
    """Replace __FIRST__ / __SECOND__ sentinel UIDs with real UIDs from context."""
    slots = {0: None, 1: None}
    for i, d in enumerate(de_list):
        if i < 2:
            slots[i] = d["uid"]
    mapping = {"__FIRST__": slots[0], "__SECOND__": slots[1]}
    result = []
    for rec in recs:
        raw = rec.get("de_uid", "")
        uid = mapping.get(raw, raw) if raw in mapping else raw
        if uid:
            result.append({**rec, "de_uid": uid})
    return result


# ── AI response parsing ──────────────────────────────────────────────────────

def _parse_response(text: str) -> list[dict]:
    cleaned = re.sub(r"```[a-z]*\n?", "", text).strip()
    m = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _validate(recs: list[dict], de_list: list[dict]) -> list[dict]:
    valid_types = {c["id"] for c in CHART_TYPE_CATALOG}
    valid_uids  = {d["uid"] for d in de_list}
    return [
        rec for rec in recs
        if rec.get("chart_type") in valid_types
        and rec.get("de_uid") in valid_uids
        and rec.get("title")
    ]


# ── Public API ───────────────────────────────────────────────────────────────

def recommend_charts(
    user_intent: str,
    context: dict,
    *,
    ai_client=None,
    mock_key: str | None = None,
    mock_response: list[dict] | None = None,
    model: str = "claude-haiku-4-5-20251001",
) -> list[dict]:
    """Return validated chart recommendation dicts.

    Provide ONE of:
      mock_key      — name from MOCK_SCENARIOS (for testing)
      mock_response — explicit list[dict] (for testing)
      ai_client     — anthropic.Anthropic instance (production)
    """
    de_list = context.get("de_list", [])

    # mock_response takes priority over mock_key
    if mock_response is not None:
        recs = _resolve_placeholders(list(mock_response), de_list)
        return _validate(recs, de_list)

    if mock_key is not None:
        raw = list(MOCK_SCENARIOS.get(mock_key, []))
        recs = _resolve_placeholders(raw, de_list)
        return _validate(recs, de_list)

    if ai_client is None:
        raise ValueError("Provide ai_client, mock_key, or mock_response")

    prompt  = _build_prompt(user_intent, context)
    message = ai_client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = message.content[0].text if message.content else ""
    recs = _parse_response(raw_text)
    return _validate(recs, de_list)


def _build_refine_prompt(rec: dict, instruction: str, context: dict) -> str:
    de_lines = "\n".join(
        "  - uid={uid} name={name!r} kind={kind}".format(**d)
        + (f" description={d['description']!r}" if d["description"] else "")
        for d in context["de_list"]
    )
    return (
        f"You are refining ONE chart in a DHIS2 dashboard.\n\n"
        f"Current chart JSON: {json.dumps(rec)}\n\n"
        f"Available data elements / indicators:\n{de_lines or '  (none)'}\n\n"
        f"Available chart types:\n{_CATALOG_TEXT}\n\n"
        f"User change request: {instruction}\n\n"
        f"Return ONE updated chart as a JSON object with keys: title, chart_type "
        f"(one of the IDs above), de_uid (a UID above), rationale. Keep fields that "
        f"shouldn't change. Return ONLY the JSON object, no markdown."
    )


def _parse_object(text: str) -> dict:
    cleaned = re.sub(r"```[a-z]*\n?", "", text).strip()
    m = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not m:
        return {}
    try:
        d = json.loads(m.group(0))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _mock_refine(rec: dict, instruction: str, context: dict) -> dict:
    """Offline/mock refine: switch chart_type if the instruction names one."""
    lo = (instruction or "").lower()
    type_words = {"pie": "pie_cat", "donut": "pie_cat", "line": "line_trend",
                  "trend": "line_trend", "bar": "bar", "column": "bar",
                  "map": "area_map", "choropleth": "area_map", "bubble": "point_map",
                  "table": "table_view", "scorecard": "scorecard", "kpi": "scorecard"}
    valid = {c["id"] for c in CHART_TYPE_CATALOG}
    upd = dict(rec)
    for w, cid in type_words.items():
        if w in lo and cid in valid:
            upd["chart_type"] = cid
            break
    return upd


def refine_chart(
    rec: dict,
    instruction: str,
    context: dict,
    *,
    ai_client=None,
    model: str = "claude-haiku-4-5-20251001",
    mock_response: dict | None = None,
) -> dict:
    """Return an updated single chart rec after applying a natural-language change.
    Falls back to the original rec if the AI output is invalid."""
    de_list = context.get("de_list", [])
    if mock_response is not None:
        upd = mock_response
    elif ai_client is None:
        upd = _mock_refine(rec, instruction, context)
    else:
        prompt = _build_refine_prompt(rec, instruction, context)
        msg = ai_client.messages.create(
            model=model, max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        upd = _parse_object(msg.content[0].text if msg.content else "")
    if not upd:
        return rec
    merged = {**rec, **{k: v for k, v in upd.items() if v}}
    ok = _validate([merged], de_list)
    return ok[0] if ok else rec


def recs_to_chart_configs(
    recs: list[dict],
    de_list: list[dict],
    base_ou_uid: str = "",
) -> list[dict]:
    """Convert recommendation dicts to chart config dicts for generate_preview_page()."""
    uid_to_meta = {d["uid"]: d for d in de_list}
    configs = []
    for rec in recs:
        de_meta = uid_to_meta.get(rec["de_uid"])
        if not de_meta:
            continue
        de_type = {
            "indicator":        "indicator",
            "program_indicator":"indicator",
            "data_element":     "aggregate",
            "tracker_de":       "tracker_numeric",
            "tracked_attr":     "tracker_numeric",
        }.get(de_meta.get("kind", ""), "aggregate")
        configs.append({
            "template_id":    rec["chart_type"],
            "title":          rec["title"],
            # NOTE: plugins read metric["uid"] (not "dx_uid") to build dimension=dx:<uid>.
            # Using the wrong key leaves dx empty → DHIS2 analytics 409 on deploy.
            "metrics":        [{"uid": rec["de_uid"], "label": de_meta["name"],
                                "type": de_type, "agg": "SUM"}],
            "dims":           {"ou_uid": base_ou_uid},
            "options":        {},
            "_ai_rationale":  rec.get("rationale", ""),
            "_ai_generated":  True,
        })
    return configs
