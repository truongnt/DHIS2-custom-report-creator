"""
Fetch actual analytics data from DHIS2 for chart configs.

Flow: form selects DE → app calls DHIS2 analytics API → returns rows → sent to Claude.
This avoids Claude needing to know/guess stage UIDs in generated JS.
"""
from __future__ import annotations
import re

_PERIOD_MAP = {
    "Last 12 months": "LAST_12_MONTHS",
    "Current year":   "THIS_YEAR",
    "Last quarter":   "LAST_QUARTER",
    "Last 6 months":  "LAST_6_MONTHS",
    "Last 2 years":   "LAST_2_YEARS",
}

_PERIOD_TYPE_MAP = {
    "Monthly":   "MONTHLY",
    "Quarterly": "QUARTERLY",
    "Yearly":    "YEARLY",
}


def period_param(time_range: str) -> str:
    return _PERIOD_MAP.get(time_range, "LAST_12_MONTHS")


def ou_param(ou_level_str: str) -> str:
    """Convert form OU string to DHIS2 analytics ou= parameter."""
    if not ou_level_str or ou_level_str == "(all)":
        return "USER_ORGUNIT"
    m = re.match(r"Level (\d+)", ou_level_str)
    if m:
        return f"USER_ORGUNIT;LEVEL-{m.group(1)}"
    return "USER_ORGUNIT"


def _parse_headers(resp: dict) -> list[str]:
    return [h.get("column", h.get("name", "")) for h in resp.get("headers", [])]


def _rows_to_dicts(resp: dict) -> list[dict]:
    headers = _parse_headers(resp)
    return [dict(zip(headers, row)) for row in resp.get("rows", [])]


def fetch_aggregate_data(client, de_uid: str, period: str, ou: str) -> list[dict]:
    """GET /api/analytics.json for an aggregate data element."""
    params = {
        "dimension": [f"dx:{de_uid}", f"pe:{period}", f"ou:{ou}"],
        "displayProperty": "NAME",
        "paging": "false",
    }
    resp = client.get("/api/analytics.json", params=params)
    return _rows_to_dicts(resp)


def fetch_event_data(client, program_uid: str, stage_uid: str,
                     de_uid: str, period: str, ou: str) -> list[dict]:
    """GET /api/analytics/events/aggregate/{programUID} for a stage DE."""
    params = {
        "dimension": [f"pe:{period}", f"ou:{ou}", f"{stage_uid}.{de_uid}"],
        "stage":     stage_uid,
        "displayProperty": "NAME",
        "paging":    "false",
        "outputType": "EVENT",
    }
    resp = client.get(f"/api/analytics/events/aggregate/{program_uid}", params=params)
    return _rows_to_dicts(resp)


def fetch_chart_data(client, config: dict, metadata: dict,
                     time_range: str, ou_str: str) -> dict:
    """
    Fetch actual DHIS2 analytics data for one chart config.
    Returns the config dict enriched with 'rows', 'headers', and 'error' keys.
    """
    period = period_param(time_range)
    ou     = ou_param(ou_str)
    de_uid = config.get("metric_uid", "").strip()

    psde_list = metadata.get("program_stage_data_elements", [])
    psde_match = next((d for d in psde_list if d.get("id") == de_uid), None) if de_uid else None

    # Fallback: if UID missing, try to match by display name from metric text
    if not de_uid:
        metric_text = config.get("metric", "").strip().lower()
        if metric_text:
            for de in psde_list:
                name = de.get("displayName", "").lower()
                if name and (name in metric_text or metric_text in name):
                    de_uid    = de.get("id", "")
                    psde_match = de
                    break
        if not de_uid:
            for de in metadata.get("data_elements", []):
                name = de.get("displayName", "").lower()
                if name and (name in metric_text or metric_text in name):
                    de_uid = de.get("id", "")
                    break

    if not de_uid:
        return {**config, "rows": [], "fetch_error": "No DE selected — pick a data element from the dropdown"}

    try:
        if psde_match:
            prog_uid  = psde_match.get("program", {}).get("id", "")
            stage_uid = psde_match.get("stage",   {}).get("id", "")
            if not prog_uid or not stage_uid:
                return {**config, "rows": [], "fetch_error": "Missing program/stage UID in metadata"}
            rows = fetch_event_data(client, prog_uid, stage_uid, de_uid, period, ou)
        else:
            rows = fetch_aggregate_data(client, de_uid, period, ou)

        return {**config, "rows": rows, "fetch_error": None}

    except Exception as exc:
        return {**config, "rows": [], "fetch_error": str(exc)}


def format_data_for_prompt(enriched_configs: list[dict]) -> str:
    """
    Format fetched data into a readable block for the LLM prompt.
    Each chart gets a section with its rows as a markdown table.
    """
    parts: list[str] = []
    for c in enriched_configs:
        idx   = c.get("index", "?")
        title = c.get("title", "—")
        ctype = c.get("chart_type", "")
        notes = c.get("notes", "")
        err   = c.get("fetch_error")
        rows  = c.get("rows", [])

        parts.append(f"## Chart {idx}: {title}")
        parts.append(f"- Chart type : {ctype}")
        if notes:
            parts.append(f"- Notes      : {notes}")

        if err:
            parts.append(f"- Data fetch : FAILED — {err}")
            parts.append("  Use placeholder/empty chart with error note.")
        elif not rows:
            parts.append("- Data       : No data returned for this period/org unit.")
        else:
            # Build markdown table from first row's keys
            cols = list(rows[0].keys())
            header = " | ".join(cols)
            sep    = " | ".join(["---"] * len(cols))
            parts.append(f"- Data ({len(rows)} rows):")
            parts.append(f"  | {header} |")
            parts.append(f"  | {sep} |")
            for row in rows[:50]:  # cap at 50 rows to keep prompt size manageable
                vals = " | ".join(str(row.get(c, "")) for c in cols)
                parts.append(f"  | {vals} |")
            if len(rows) > 50:
                parts.append(f"  ... {len(rows) - 50} more rows (omitted)")
        parts.append("")

    return "\n".join(parts)
