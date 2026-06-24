"""
Build the LLM context string from DHIS2 metadata.

Priority order in context:
  1. PINNED items — always included, marked clearly
  2. PRIMARY raw data:
       • Aggregate Data Elements (from datasets)
       • Program Stage Data Elements grouped by program+stage (tracker)
       • Tracked Entity Attributes grouped by program (tracker demographics)
  3. SECONDARY derived data:
       • Aggregate Indicators (formulas — use only if no suitable DE)
  4. REST — datasets, OU levels, chart catalog
"""
from __future__ import annotations

MAX_HIGH_USAGE        = 50
MAX_DATA_ELEM         = 200
MAX_PROG_DE_PER_PROG  = 80   # stage DEs shown for each program
MAX_TEA_PER_PROG      = 30   # tracked entity attributes per program
MAX_INDICATORS        = 100  # indicators shown (secondary)
MAX_DATASETS          = 40
MAX_PROGRAMS          = 20
MAX_OPTIONS           = 10   # max option values shown per DE

# valueTypes with no analytics value when there is no optionSet
_TEXT_ONLY_TYPES = {
    "TEXT", "LONG_TEXT", "EMAIL", "URL", "FILE_RESOURCE",
    "IMAGE", "COORDINATE", "PHONE_NUMBER", "USERNAME", "GEOJSON",
}


def _lookup(items: list[dict], uids: list[str]) -> list[dict]:
    uid_set = set(uids)
    return [x for x in items if x.get("id") in uid_set]


def _exclude(items: list[dict], uids: set[str]) -> list[dict]:
    return [x for x in items if x.get("id") not in uids]


def _sort_by_usage(items: list[dict], counts: dict[str, int]) -> list[dict]:
    return sorted(items, key=lambda x: counts.get(x.get("id", ""), 0), reverse=True)


def _option_suffix(item: dict) -> str:
    """Return ' [Options: A, B, C]' if item has an optionSet, else ''."""
    os = item.get("optionSet") or {}
    opts = os.get("options", [])
    if not opts:
        return ""
    names = [o.get("displayName") or o.get("code", "?") for o in opts[:MAX_OPTIONS]]
    suffix = ", ".join(names)
    if len(opts) > MAX_OPTIONS:
        suffix += f" +{len(opts)-MAX_OPTIONS} more"
    return f"  [Options: {suffix}]"


def _is_analytics_de(item: dict) -> bool:
    """Return False for free-text DEs with no optionSet (useless for charts)."""
    vt = item.get("valueType", "")
    if vt not in _TEXT_ONLY_TYPES:
        return True
    return bool(item.get("optionSet"))


def _fmt_item(item: dict, kind: str, count: int = 0) -> str:
    uid  = item.get("id", "?")
    name = item.get("displayName", "?")
    if kind == "indicators":
        extra = item.get("indicatorType", {}).get("displayName", "")
    elif kind in ("data_elements", "program_stage_data_elements"):
        extra = item.get("valueType", "")
    elif kind == "tracked_entity_attributes":
        extra = item.get("valueType", "")
    elif kind == "program_indicators":
        extra = item.get("program", {}).get("displayName", "")
    else:
        extra = ""
    usage   = f"  [used {count}x]" if count > 0 else ""
    opt_sfx = _option_suffix(item) if kind in (
        "data_elements", "program_stage_data_elements", "tracked_entity_attributes") else ""
    return f"  {uid}  {name}  | {extra}{opt_sfx}{usage}"


def filter_metadata_by_scope(
    metadata: dict,
    prog_name: str,
    stage_names: "str | list[str]" = "",
) -> dict:
    """
    Return a shallow copy of metadata filtered to the selected program/stage(s).
    Keeps aggregate data_elements as-is (they belong to datasets, not programs).
    """
    result = dict(metadata)

    # Normalise stage_names to a set (empty = all stages)
    if isinstance(stage_names, str):
        stage_set: set[str] = {stage_names} if stage_names else set()
    else:
        stage_set = set(stage_names)

    # Filter program_stage_data_elements to selected program (and optionally stages)
    psde = metadata.get("program_stage_data_elements", [])
    result["program_stage_data_elements"] = [
        de for de in psde
        if de.get("program", {}).get("displayName") == prog_name
        and (not stage_set or de.get("stage", {}).get("displayName") in stage_set)
    ]

    # Filter data_elements to only those in the scoped stage DEs.
    # The merged data_elements list includes DEs from all stages — when a specific
    # program+stage is selected we keep only the relevant subset so that
    # enrich_with_option_sets doesn't fetch option sets for unrelated stages.
    scoped_uids = {de.get("id") for de in result["program_stage_data_elements"]}
    result["data_elements"] = [
        de for de in metadata.get("data_elements", [])
        if de.get("id") in scoped_uids
    ]

    # Filter tracked_entity_attributes to selected program
    teas = metadata.get("tracked_entity_attributes", [])
    result["tracked_entity_attributes"] = [
        t for t in teas
        if t.get("program", {}).get("displayName") == prog_name
    ]

    # Keep only the selected program in the programs list
    result["programs"] = [
        p for p in metadata.get("programs", [])
        if p.get("displayName") == prog_name
    ]

    return result


def build_context(
    metadata: dict,
    base_url: str,
    pinned: dict | None = None,
    usage_counts: dict | None = None,
) -> str:
    pinned       = pinned       or {}
    usage_counts = usage_counts or {}
    api          = base_url.rstrip("/")

    parts = [
        "# DHIS2 Metadata Context\n",
        f"Base URL: {base_url}",
        f"Aggregate analytics: {api}/api/analytics.json",
        f"Event analytics:     {api}/api/analytics/events/query/{{programUID}}",
        "",
        "## Analytics dimension format",
        "  Aggregate DE:  dimension=dx:{dataElementUID}",
        "  Event DE:      dimension={stageUID}.{dataElementUID}",
        "  TEA filter:    dimension={teaUID}:{value}   (in event analytics)",
        "",
    ]

    # ── Pinned items (all kinds) ──────────────────────────────────────────────
    any_pinned = False
    for kind, label in [
        ("data_elements",              "Aggregate Data Elements"),
        ("program_stage_data_elements","Program Stage Data Elements"),
        ("tracked_entity_attributes",  "Tracked Entity Attributes"),
    ]:
        all_items   = metadata.get(kind, [])
        pinned_uids = list(pinned.get(kind, []))
        pinned_items = _lookup(all_items, pinned_uids)
        counts = usage_counts.get(kind, {})
        if pinned_items:
            if not any_pinned:
                parts.append("## ★ PINNED FOR THIS REPORT — use these UIDs")
                any_pinned = True
            parts.append(f"### {label} ({len(pinned_items)} items)")
            for item in pinned_items:
                parts.append(_fmt_item(item, kind, counts.get(item.get("id", ""), 0)))
    if any_pinned:
        parts.append("")

    # ── PRIMARY: Aggregate Data Elements ─────────────────────────────────────
    all_des    = [x for x in metadata.get("data_elements", []) if _is_analytics_de(x)]
    pinned_de  = set(pinned.get("data_elements", []))
    counts_de  = usage_counts.get("data_elements", {})
    rest_de    = _exclude(all_des, pinned_de)
    rest_de_s  = _sort_by_usage(rest_de, counts_de)

    section_de = [f"## Aggregate Data Elements  (total: {len(all_des)})"]
    high_de    = [x for x in rest_de_s if counts_de.get(x.get("id",""), 0) > 0][:MAX_HIGH_USAGE]
    if high_de:
        section_de.append(f"### Frequently used (top {len(high_de)})")
        for item in high_de:
            section_de.append(_fmt_item(item, "data_elements", counts_de.get(item.get("id",""), 0)))
        section_de.append("")
    already_de = pinned_de | {x.get("id") for x in high_de}
    rest2_de   = [x for x in rest_de_s if x.get("id") not in already_de][:MAX_DATA_ELEM]
    if rest2_de:
        section_de.append(f"### Other ({len(rest2_de)} shown)")
        for item in rest2_de:
            section_de.append(_fmt_item(item, "data_elements", 0))
        section_de.append("")
    parts.append("\n".join(section_de))

    # ── PRIMARY: Program Stage Data Elements (grouped by program → stage) ─────
    prog_stage_des = [x for x in metadata.get("program_stage_data_elements", [])
                      if _is_analytics_de(x)]
    if prog_stage_des:
        from collections import defaultdict
        prog_map: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        for item in prog_stage_des:
            pname = item.get("program", {}).get("displayName", "—")
            sname = item.get("stage",   {}).get("displayName", "—")
            prog_map[pname][sname].append(item)

        counts_psde = usage_counts.get("program_stage_data_elements", {})
        section_psde = [f"## Program Stage Data Elements  (total: {len(prog_stage_des)}, use in event analytics)"]
        for pname, stages in sorted(prog_map.items()):
            section_psde.append(f"### {pname}")
            for sname, items in sorted(stages.items()):
                shown = items[:MAX_PROG_DE_PER_PROG]
                trunc = len(items) > MAX_PROG_DE_PER_PROG
                section_psde.append(
                    f"#### Stage: {sname}  ({len(items)} data elements"
                    + (f", top {MAX_PROG_DE_PER_PROG} shown" if trunc else "") + ")"
                )
                for item in shown:
                    section_psde.append(_fmt_item(item, "program_stage_data_elements",
                                                  counts_psde.get(item.get("id",""), 0)))
                if trunc:
                    section_psde.append(f"  ... {len(items)-MAX_PROG_DE_PER_PROG} more")
                section_psde.append("")
        parts.append("\n".join(section_psde))

    # ── PRIMARY: Tracked Entity Attributes (grouped by program) ───────────────
    teas = metadata.get("tracked_entity_attributes", [])
    if teas:
        from collections import defaultdict
        tea_prog_map: dict[str, list[dict]] = defaultdict(list)
        for item in teas:
            pname = item.get("program", {}).get("displayName", "—")
            tea_prog_map[pname].append(item)

        counts_tea = usage_counts.get("tracked_entity_attributes", {})
        section_tea = [f"## Tracked Entity Attributes  (total: {len(teas)}, use for filtering/grouping in event analytics)"]
        for pname, items in sorted(tea_prog_map.items()):
            shown = items[:MAX_TEA_PER_PROG]
            trunc = len(items) > MAX_TEA_PER_PROG
            section_tea.append(f"### {pname}  ({len(items)} attributes)")
            for item in shown:
                section_tea.append(_fmt_item(item, "tracked_entity_attributes",
                                             counts_tea.get(item.get("id",""), 0)))
            if trunc:
                section_tea.append(f"  ... {len(items)-MAX_TEA_PER_PROG} more")
            section_tea.append("")
        parts.append("\n".join(section_tea))

    # ── Datasets ─────────────────────────────────────────────────────────────
    datasets = metadata.get("datasets", [])
    if datasets:
        parts.append(f"## Data Sets ({len(datasets)} total)")
        for ds in datasets[:MAX_DATASETS]:
            parts.append(f"  {ds.get('id')}  {ds.get('displayName')}  | {ds.get('periodType', '')}")
        parts.append("")

    # ── Tracker Programs ──────────────────────────────────────────────────────
    programs = metadata.get("programs", [])
    if programs:
        parts.append(f"## Tracker Programs ({len(programs)} total)")
        for pg in programs[:MAX_PROGRAMS]:
            parts.append(f"  {pg.get('id')}  {pg.get('displayName')}  | {pg.get('programType', '')}")
        parts.append("")

    # ── Org unit levels ───────────────────────────────────────────────────────
    levels = metadata.get("org_unit_levels", [])
    if levels:
        parts.append("## Organisation Unit Levels")
        for lv in levels:
            parts.append(f"  Level {lv.get('level')}  {lv.get('displayName', '')}")
        parts.append("")

    parts.append(_chart_catalog())
    return "\n".join(parts)


def build_summary_context(
    metadata: dict,
    base_url: str,
    pinned: dict | None = None,
    usage_counts: dict | None = None,
) -> str:
    """Compact planning context for chat phase — no full DE lists, just overview."""
    pinned       = pinned       or {}
    usage_counts = usage_counts or {}

    parts = [
        "# DHIS2 Metadata Summary (Planning Context)\n",
        f"Base URL: {base_url}",
        "",
    ]

    # Pinned items
    any_pinned = False
    for kind, label in [
        ("data_elements",              "Aggregate Data Elements"),
        ("program_stage_data_elements","Program Stage Data Elements"),
        ("tracked_entity_attributes",  "Tracked Entity Attributes"),
    ]:
        all_items    = metadata.get(kind, [])
        pinned_items = _lookup(all_items, pinned.get(kind, []))
        counts       = usage_counts.get(kind, {})
        if pinned_items:
            if not any_pinned:
                parts.append("## ★ PINNED — use these UIDs")
                any_pinned = True
            parts.append(f"### {label} ({len(pinned_items)} items)")
            for item in pinned_items:
                parts.append(_fmt_item(item, kind, counts.get(item.get("id", ""), 0)))
    if any_pinned:
        parts.append("")

    # Programs overview — names + stage DE counts
    prog_stage_des = metadata.get("program_stage_data_elements", [])
    if prog_stage_des:
        from collections import defaultdict
        prog_map: dict[str, int] = defaultdict(int)
        for item in prog_stage_des:
            prog_map[item.get("program", {}).get("displayName", "—")] += 1
        sorted_progs = sorted(prog_map.items(), key=lambda kv: kv[1], reverse=True)
        shown = sorted_progs[:3]
        parts.append(f"## Programs ({len(sorted_progs)} total — top {len(shown)} shown)")
        for pname, cnt in shown:
            parts.append(f"  {pname}: {cnt} stage data elements")
        if len(sorted_progs) > 3:
            rest_names = ", ".join(p for p, _ in sorted_progs[3:])
            parts.append(f"  ... {len(sorted_progs)-3} more: {rest_names}")
        parts.append("")

    # Top 10 data elements by usage
    data_elems = metadata.get("data_elements", [])
    counts_de  = usage_counts.get("data_elements", {})
    top_de = sorted(data_elems, key=lambda x: counts_de.get(x.get("id",""), 0), reverse=True)[:10]
    if data_elems:
        parts.append(f"## Aggregate Data Elements ({len(data_elems)} total — top {len(top_de)})")
        for item in top_de:
            parts.append(_fmt_item(item, "data_elements", counts_de.get(item.get("id",""), 0)))
        parts.append("")

    # Datasets — top 3
    datasets = metadata.get("datasets", [])
    if datasets:
        parts.append(f"## Data Sets ({len(datasets)} total — top 3)")
        for ds in datasets[:3]:
            parts.append(f"  {ds.get('id')}  {ds.get('displayName')}  | {ds.get('periodType', '')}")
        parts.append("")

    # Org unit levels
    levels = metadata.get("org_unit_levels", [])
    if levels:
        parts.append("## Organisation Unit Levels")
        for lv in levels:
            parts.append(f"  Level {lv.get('level')}  {lv.get('displayName', '')}")
        parts.append("")

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
