"""
Build the LLM context string from DHIS2 metadata.

Priority order in context:
  1. PINNED items (explicitly selected for this report) — always included, marked clearly
  2. HIGH-USAGE items (used in past reports, sorted by count) — top N included
  3. REST of metadata — truncated to fit token budget
"""
from __future__ import annotations

# How many non-pinned items to include per category
MAX_HIGH_USAGE   = 50
MAX_INDICATORS   = 200
MAX_PROG_IND     = 150
MAX_DATA_ELEM    = 200
MAX_DATASETS     = 40
MAX_PROGRAMS     = 20


def _lookup(items: list[dict], uids: list[str]) -> list[dict]:
    uid_set = set(uids)
    return [x for x in items if x.get("id") in uid_set]


def _exclude(items: list[dict], uids: set[str]) -> list[dict]:
    return [x for x in items if x.get("id") not in uids]


def _sort_by_usage(items: list[dict], counts: dict[str, int]) -> list[dict]:
    return sorted(items, key=lambda x: counts.get(x.get("id", ""), 0), reverse=True)


def _fmt_item(item: dict, kind: str, count: int = 0) -> str:
    uid  = item.get("id", "?")
    name = item.get("displayName", "?")
    if kind == "indicators":
        extra = item.get("indicatorType", {}).get("displayName", "")
    elif kind == "program_indicators":
        extra = item.get("program", {}).get("displayName", "")
    elif kind == "data_elements":
        extra = item.get("valueType", "")
    else:
        extra = ""
    usage = f"  [used {count}×]" if count > 0 else ""
    return f"  {uid}  {name}  | {extra}{usage}"


def build_context(
    metadata: dict,
    base_url: str,
    pinned: dict | None = None,
    usage_counts: dict | None = None,
) -> str:
    """
    pinned       = {"indicators": [uid, ...], "program_indicators": [...], "data_elements": [...]}
    usage_counts = {"indicators": {uid: count}, "program_indicators": {...}, "data_elements": {...}}
    """
    pinned       = pinned       or {}
    usage_counts = usage_counts or {}

    parts = [
        "# DHIS2 Metadata Context\n",
        f"Base URL: {base_url}",
        f"Analytics API: {base_url.rstrip('/')}/analytics",
        "",
    ]

    for kind, label, max_rest in [
        ("indicators",         "Aggregate Indicators",   MAX_INDICATORS),
        ("program_indicators", "Program Indicators",     MAX_PROG_IND),
        ("data_elements",      "Aggregate Data Elements", MAX_DATA_ELEM),
    ]:
        all_items   = metadata.get(kind, [])
        pinned_uids = list(pinned.get(kind, []))
        counts      = usage_counts.get(kind, {})

        pinned_items = _lookup(all_items, pinned_uids)
        rest         = _exclude(all_items, set(pinned_uids))
        rest_sorted  = _sort_by_usage(rest, counts)

        section = [f"## {label}  (total: {len(all_items)})"]

        if pinned_items:
            section.append(f"### ★ PINNED FOR THIS REPORT ({len(pinned_items)} items) — use these UIDs in analytics calls")
            for item in pinned_items:
                count = counts.get(item.get("id", ""), 0)
                section.append(_fmt_item(item, kind, count))
            section.append("")

        # High-usage non-pinned
        high_usage = [x for x in rest_sorted if counts.get(x.get("id", ""), 0) > 0][:MAX_HIGH_USAGE]
        if high_usage:
            section.append(f"### Frequently used (top {len(high_usage)})")
            for item in high_usage:
                count = counts.get(item.get("id", ""), 0)
                section.append(_fmt_item(item, kind, count))
            section.append("")

        # Remaining up to max_rest
        already = set(pinned_uids) | {x.get("id") for x in high_usage}
        remaining = [x for x in rest_sorted if x.get("id") not in already][:max_rest]
        if remaining:
            section.append(f"### Other available ({len(remaining)} shown of {len(rest) - len(high_usage)} remaining)")
            for item in remaining:
                section.append(_fmt_item(item, kind, 0))
            section.append("")

        parts.append("\n".join(section))

    # Datasets
    datasets = metadata.get("datasets", [])
    if datasets:
        parts.append(f"## Data Sets ({len(datasets)} total)")
        for ds in datasets[:MAX_DATASETS]:
            parts.append(f"  {ds.get('id')}  {ds.get('displayName')}  | {ds.get('periodType', '')}")
        parts.append("")

    # Programs
    programs = metadata.get("programs", [])
    if programs:
        parts.append(f"## Tracker Programs ({len(programs)} total)")
        for pg in programs[:MAX_PROGRAMS]:
            parts.append(f"  {pg.get('id')}  {pg.get('displayName')}  | {pg.get('programType', '')}")
        parts.append("")

    # Org unit levels
    levels = metadata.get("org_unit_levels", [])
    if levels:
        parts.append("## Organisation Unit Levels")
        for lv in levels:
            parts.append(f"  Level {lv.get('level')}  {lv.get('displayName', '')}")
        parts.append("")

    # Chart type catalog (always included so LLM knows available templates)
    parts.append(_chart_catalog())

    return "\n".join(parts)


def _chart_catalog() -> str:
    """Compact list of available chart templates to guide the LLM."""
    try:
        from charts.templates import TEMPLATES, CATEGORIES
    except ImportError:
        return ""

    cat_map = {c["id"]: c["name"] for c in CATEGORIES}
    lines = ["## Available Chart Templates (for report design reference)"]
    current_cat = None
    for t in TEMPLATES:
        cat = cat_map.get(t.get("category", ""), t.get("category", ""))
        if cat != current_cat:
            lines.append(f"### {cat}")
            current_cat = cat
        lines.append(
            f"  {t['id']:<25}  {t['name']:<30}  ({t.get('short', '')})"
            f"  — best for: {t.get('best_for', '')}"
        )
    lines.append("")
    return "\n".join(lines)
