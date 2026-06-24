"""
Fetch DHIS2 metadata with optional group/program filters.

FilterConfig dict shape (all keys optional):
{
  "indicator_group_ids":    [str, ...]   # only indicators in these groups
  "indicator_name":         str          # case-insensitive name search
  "de_group_ids":           [str, ...]   # only data elements in these groups
  "de_name":                str
  "program_ids":            [str, ...]   # only program indicators for these programs
  "program_indicator_name": str
  "dataset_ids":            [str, ...]   # only these specific datasets
  "domain_type":            "AGGREGATE" | "TRACKER" | None  (default AGGREGATE)
}
"""
from __future__ import annotations
from dhis2.client import DHIS2Client


# ── Helpers ───────────────────────────────────────────────────────────────────

def _in_filter(field: str, ids: list[str]) -> str:
    """Build DHIS2 in-filter string: field:in:[id1,id2,...]"""
    return f"{field}:in:[{','.join(ids)}]"


def _build_filters(*pairs) -> list[str]:
    """
    Each pair is (condition, filter_string).
    Returns list of filter strings where condition is truthy.
    """
    return [f for cond, f in pairs if cond]


# ── Individual fetchers ───────────────────────────────────────────────────────

def fetch_indicators(client: DHIS2Client, cfg: dict | None = None) -> list[dict]:
    """
    Ref: GET /api/indicators
    Fields: id, displayName, code, numeratorDescription, denominatorDescription,
            indicatorType[displayName], indicatorGroups[id,displayName]
    """
    cfg = cfg or {}
    group_ids = cfg.get("indicator_group_ids") or []
    name      = cfg.get("indicator_name", "").strip()

    filters = _build_filters(
        (group_ids, _in_filter("indicatorGroups.id", group_ids)),
        (name,      f"displayName:ilike:{name}"),
    )

    params: dict = {
        "fields": (
            "id,displayName,code,"
            "numeratorDescription,denominatorDescription,"
            "indicatorType[displayName],"
            "indicatorGroups[id,displayName]"
        ),
        "paging": "false",
        "order":  "displayName:asc",
    }
    if filters:
        params["filter"] = filters  # list → multiple filter= params

    data = client.get("indicators.json", params=params)
    return data.get("indicators", [])


def fetch_program_indicators(client: DHIS2Client, cfg: dict | None = None) -> list[dict]:
    """
    Ref: GET /api/programIndicators
    Fields: id, displayName, code, description, aggregationType,
            program[id,displayName], analyticsType
    """
    cfg = cfg or {}
    prog_ids = cfg.get("program_ids") or []
    name     = cfg.get("program_indicator_name", "").strip()

    filters = _build_filters(
        (prog_ids, _in_filter("program.id", prog_ids)),
        (name,     f"displayName:ilike:{name}"),
    )

    params: dict = {
        "fields": (
            "id,displayName,code,description,aggregationType,analyticsType,"
            "program[id,displayName]"
        ),
        "paging": "false",
        "order":  "displayName:asc",
    }
    if filters:
        params["filter"] = filters

    data = client.get("programIndicators.json", params=params)
    return data.get("programIndicators", [])


def fetch_data_elements(client: DHIS2Client, cfg: dict | None = None) -> list[dict]:
    """
    Fetch aggregate data elements filtered by DE groups and/or keyword.
    Note: dataset_ids filtering is handled separately via fetch_des_from_datasets.
    """
    cfg         = cfg or {}
    group_ids   = cfg.get("de_group_ids") or []
    name        = cfg.get("de_name", "").strip()
    domain_type = cfg.get("domain_type", "AGGREGATE")

    filters = _build_filters(
        (domain_type, f"domainType:eq:{domain_type}"),
        (group_ids,   _in_filter("dataElementGroups.id", group_ids)),
        (name,        f"displayName:ilike:{name}"),
    )

    params: dict = {
        "fields": (
            "id,displayName,code,valueType,domainType,"
            "dataElementGroups[id,displayName]"
        ),
        "paging": "false",
        "order":  "displayName:asc",
    }
    if filters:
        params["filter"] = filters

    data = client.get("dataElements.json", params=params)
    return data.get("dataElements", [])


def fetch_des_from_datasets(client: DHIS2Client, dataset_ids: list[str]) -> list[dict]:
    """
    Fetch data elements from specific datasets via the dataSets endpoint.
    More reliable than filtering dataElements by dataSets.id (which causes 409 on some versions).
    """
    if not dataset_ids:
        return []
    params = {
        "filter": _in_filter("id", dataset_ids),
        "fields": (
            "dataSetElements[dataElement["
            "id,displayName,valueType,domainType,"
            "dataElementGroups[id,displayName]"
            "]]"
        ),
        "paging": "false",
    }
    data = client.get("dataSets.json", params=params)
    seen: set[str] = set()
    result: list[dict] = []
    for ds in data.get("dataSets", []):
        for dse in ds.get("dataSetElements", []):
            de = dse.get("dataElement", {})
            uid = de.get("id")
            if uid and uid not in seen:
                seen.add(uid)
                result.append(de)
    return result


def fetch_program_stage_data_elements(client: DHIS2Client,
                                       program_ids: list[str]) -> list[dict]:
    """
    Fetch data elements collected in program stages, grouped by program + stage.
    Returns list of dicts: {id, displayName, valueType, program, stage}
    """
    if not program_ids:
        return []

    params = {
        "filter": _in_filter("id", program_ids),
        "fields": (
            "id,displayName,"
            "programStages[id,displayName,"
            "programStageDataElements["
            "dataElement[id,displayName,valueType]"
            "]]"
        ),
        "paging": "false",
    }
    data = client.get("programs.json", params=params)

    seen: set[str] = set()
    result: list[dict] = []
    for prog in data.get("programs", []):
        prog_name = prog.get("displayName", "")
        for stage in prog.get("programStages", []):
            stage_name = stage.get("displayName", "")
            for psde in stage.get("programStageDataElements", []):
                de = psde.get("dataElement", {})
                uid = de.get("id")
                if uid and uid not in seen:
                    seen.add(uid)
                    result.append({
                        "id":          uid,
                        "displayName": de.get("displayName", ""),
                        "valueType":   de.get("valueType", ""),
                        "program":     {"displayName": prog_name, "id": prog.get("id", "")},
                        "stage":       {"displayName": stage_name, "id": stage.get("id", "")},
                    })
    return result


def fetch_tracked_entity_attributes(client: DHIS2Client,
                                     program_ids: list[str] | None = None) -> list[dict]:
    """
    Fetch tracked entity attributes for specified programs (or all if no program filter).
    Returns list of {id, displayName, valueType, program: {displayName, id}}
    """
    _TEA_FIELDS = (
        "id,displayName,valueType,"
        "optionSet[id,displayName,options[id,code,displayName]]"
    )
    if program_ids:
        params = {
            "filter": _in_filter("id", program_ids),
            "fields": (
                f"id,displayName,"
                f"programTrackedEntityAttributes["
                f"trackedEntityAttribute[{_TEA_FIELDS}]"
                f"]"
            ),
            "paging": "false",
        }
        data = client.get("programs.json", params=params)
        seen: set[str] = set()
        result: list[dict] = []
        for prog in data.get("programs", []):
            prog_name = prog.get("displayName", "")
            prog_id   = prog.get("id", "")
            for ptea in prog.get("programTrackedEntityAttributes", []):
                tea = ptea.get("trackedEntityAttribute", {})
                uid = tea.get("id")
                if uid and uid not in seen:
                    seen.add(uid)
                    result.append({
                        "id":          uid,
                        "displayName": tea.get("displayName", ""),
                        "valueType":   tea.get("valueType", ""),
                        "optionSet":   tea.get("optionSet"),
                        "program":     {"displayName": prog_name, "id": prog_id},
                    })
        return result
    else:
        params = {
            "fields": _TEA_FIELDS,
            "paging": "false",
            "order":  "displayName:asc",
        }
        data = client.get("trackedEntityAttributes.json", params=params)
        return [
            {"id": t.get("id"), "displayName": t.get("displayName", ""),
             "valueType": t.get("valueType", ""), "optionSet": t.get("optionSet"),
             "program": {}}
            for t in data.get("trackedEntityAttributes", [])
        ]


def enrich_with_option_sets(client: "DHIS2Client", metadata: dict) -> dict:
    """
    Lazy-fetch optionSet for DEs in metadata (called after scope filter).
    Mutates and returns the metadata dict.
    """
    _FIELDS = "optionSet[id,displayName,options[id,code,displayName]]"

    # Collect unique DE UIDs from both aggregate and stage DEs
    de_ids: list[str] = []
    seen: set[str] = set()
    for kind in ("data_elements", "program_stage_data_elements"):
        for de in metadata.get(kind, []):
            uid = de.get("id")
            if uid and uid not in seen:
                seen.add(uid)
                de_ids.append(uid)

    if not de_ids:
        return metadata

    # Batch fetch — DHIS2 supports up to ~200 IDs in an :in: filter
    BATCH = 150
    uid_to_os: dict[str, dict] = {}
    for i in range(0, len(de_ids), BATCH):
        batch = de_ids[i:i + BATCH]
        params = {
            "filter": _in_filter("id", batch),
            "fields": f"id,{_FIELDS}",
            "paging": "false",
        }
        try:
            data = client.get("dataElements.json", params=params)
            for de in data.get("dataElements", []):
                os_ = de.get("optionSet")
                if os_:
                    uid_to_os[de["id"]] = os_
        except Exception:
            pass  # best-effort — missing option sets just won't show

    # Enrich both DE lists
    for kind in ("data_elements", "program_stage_data_elements"):
        for de in metadata.get(kind, []):
            uid = de.get("id")
            if uid in uid_to_os:
                de["optionSet"] = uid_to_os[uid]

    return metadata


# kept for backward compatibility — programs' stage DEs merged into agg DEs pool
def fetch_program_data_elements(client: DHIS2Client,
                                  program_ids: list[str]) -> list[dict]:
    """Legacy: returns flat list of DEs from program stages (no stage/program grouping)."""
    full = fetch_program_stage_data_elements(client, program_ids)
    return [{"id": x["id"], "displayName": x["displayName"],
             "valueType": x.get("valueType", "")} for x in full]


def fetch_datasets(client: DHIS2Client, cfg: dict | None = None) -> list[dict]:
    """
    Ref: GET /api/dataSets
    Fields: id, displayName, code, periodType
    """
    cfg        = cfg or {}
    ds_ids     = cfg.get("dataset_ids") or []

    params: dict = {
        "fields": "id,displayName,code,periodType",
        "paging": "false",
        "order":  "displayName:asc",
    }
    if ds_ids:
        params["filter"] = _in_filter("id", ds_ids)

    data = client.get("dataSets.json", params=params)
    return data.get("dataSets", [])


def fetch_programs(client: DHIS2Client, cfg: dict | None = None) -> list[dict]:
    """
    Ref: GET /api/programs
    programType: WITH_REGISTRATION (tracker) | WITHOUT_REGISTRATION (event)
    """
    cfg      = cfg or {}
    prog_ids = cfg.get("program_ids") or []

    params: dict = {
        "fields": "id,displayName,code,programType,programStages[id,displayName]",
        "paging": "false",
        "order":  "displayName:asc",
    }
    if prog_ids:
        params["filter"] = _in_filter("id", prog_ids)

    data = client.get("programs.json", params=params)
    return data.get("programs", [])


def fetch_org_unit_levels(client: DHIS2Client) -> list[dict]:
    """Ref: GET /api/organisationUnitLevels"""
    data = client.get("organisationUnitLevels.json", params={
        "fields": "id,level,displayName,name",
        "order":  "level:asc",
        "paging": "false",
    })
    return data.get("organisationUnitLevels", [])


# ── Bundle fetch ──────────────────────────────────────────────────────────────

def fetch_all(client: DHIS2Client, cfg: dict | None = None) -> dict:
    """
    Fetch all metadata categories with optional FilterConfig.

    Smart scoping rules:
      - program_ids set, no indicator_group_ids, no dataset_ids
          → tracker scope: fetch program indicators + program stage DEs only,
            skip aggregate indicators (they belong to a different domain)
      - dataset_ids set, no program_ids
          → aggregate scope: fetch DEs from datasets + aggregate indicators,
            skip program indicators
      - indicator_group_ids set (with or without other filters)
          → always fetch aggregate indicators (explicitly requested)
      - No filter at all → fetch everything (slow but complete)
    """
    cfg = cfg or {}
    program_ids         = cfg.get("program_ids") or []
    dataset_ids         = cfg.get("dataset_ids") or []
    indicator_group_ids = cfg.get("indicator_group_ids") or []
    de_group_ids        = cfg.get("de_group_ids") or []

    # Determine what to fetch based on selected scope
    tracker_only  = bool(program_ids) and not indicator_group_ids and not dataset_ids
    aggregate_only = bool(dataset_ids) and not program_ids

    # ── Aggregate indicators ──
    if tracker_only:
        indicators = []
    else:
        indicators = fetch_indicators(client, cfg)

    # ── Program indicators ──
    if aggregate_only:
        prog_indicators = []
    else:
        prog_indicators = fetch_program_indicators(client, cfg)

    # ── Data elements: from DE groups / keyword ──
    if tracker_only:
        agg_des = []
    else:
        agg_des = fetch_data_elements(client, cfg)

    # ── Data elements: from selected datasets (via dataSets endpoint) ──
    if dataset_ids:
        ds_des = fetch_des_from_datasets(client, dataset_ids)
        seen_ds = {de.get("id") for de in agg_des}
        for de in ds_des:
            if de.get("id") not in seen_ds:
                seen_ds.add(de.get("id"))
                agg_des.append(de)

    # ── Program stage data elements (grouped, primary for tracker) ──
    prog_stage_des: list[dict] = []
    if program_ids:
        prog_stage_des = fetch_program_stage_data_elements(client, program_ids)

    # ── Tracked entity attributes ──
    tracked_entity_attrs: list[dict] = []
    if program_ids:
        tracked_entity_attrs = fetch_tracked_entity_attributes(client, program_ids)

    # Merge aggregate DEs + flat program stage DEs (de-duplicated)
    seen_de: set[str] = {de.get("id") for de in agg_des}
    merged_des = list(agg_des)
    for de in prog_stage_des:
        if de.get("id") not in seen_de:
            seen_de.add(de.get("id"))
            merged_des.append(de)

    return {
        "indicators":              indicators,           # derived / secondary
        "program_indicators":      prog_indicators,      # derived / secondary
        "data_elements":           merged_des,           # primary: aggregate DEs
        "program_stage_data_elements": prog_stage_des,  # primary: tracker stage DEs (grouped)
        "tracked_entity_attributes":   tracked_entity_attrs,  # tracker demographics
        "datasets":                fetch_datasets(client, cfg),
        "programs":                fetch_programs(client, cfg),
        "org_unit_levels":         fetch_org_unit_levels(client),
        "_filter_config":          cfg,
    }
