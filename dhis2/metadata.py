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
    Ref: GET /api/dataElements
    Supports filtering by DE groups, dataset IDs, or keyword.
    When dataset_ids is set, fetches DEs belonging to those datasets.
    When domain_type is None, skips the AGGREGATE filter (useful for program DEs).
    """
    cfg         = cfg or {}
    group_ids   = cfg.get("de_group_ids") or []
    dataset_ids = cfg.get("dataset_ids") or []
    name        = cfg.get("de_name", "").strip()
    domain_type = cfg.get("domain_type", "AGGREGATE")

    filters = _build_filters(
        (domain_type, f"domainType:eq:{domain_type}"),
        (group_ids,   _in_filter("dataElementGroups.id", group_ids)),
        (dataset_ids, _in_filter("dataSets.id", dataset_ids)),
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


def fetch_program_data_elements(client: DHIS2Client,
                                  program_ids: list[str]) -> list[dict]:
    """
    Ref: GET /api/programs?filter=id:in:[...]&fields=programStages[...]
    Extracts data elements from all stages of the given programs.
    Returns a de-duplicated list using the same shape as fetch_data_elements().
    """
    if not program_ids:
        return []

    params = {
        "filter": _in_filter("id", program_ids),
        "fields": (
            "id,displayName,"
            "programStages[programStageDataElements["
            "dataElement[id,displayName,code,valueType,domainType]"
            "]]"
        ),
        "paging": "false",
    }
    data = client.get("programs.json", params=params)

    seen: set[str] = set()
    result: list[dict] = []
    for prog in data.get("programs", []):
        for stage in prog.get("programStages", []):
            for psde in stage.get("programStageDataElements", []):
                de = psde.get("dataElement", {})
                uid = de.get("id")
                if uid and uid not in seen:
                    seen.add(uid)
                    result.append(de)
    return result


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
        "fields": "id,displayName,code,programType",
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
      - program_ids set  → fetch PI for those programs AND their stage DEs
      - dataset_ids set  → fetch DEs from those datasets (merged with group-filtered DEs)
      - Both can combine: program DEs + dataset DEs are union-merged, de-duplicated
    """
    cfg = cfg or {}
    program_ids = cfg.get("program_ids") or []
    dataset_ids = cfg.get("dataset_ids") or []

    # ── Data elements: aggregate (group/keyword filter) ──
    agg_des = fetch_data_elements(client, cfg)

    # ── Data elements: from selected programs' stages ──
    prog_des: list[dict] = []
    if program_ids:
        prog_des = fetch_program_data_elements(client, program_ids)

    # ── Data elements: from selected datasets (if dataset_ids but no de_group_ids) ──
    # dataset_ids filter is already applied inside fetch_data_elements via cfg
    # (no extra call needed — it's part of agg_des already)

    # Merge & de-duplicate (program DEs may overlap with aggregate DEs)
    seen_de: set[str] = {de.get("id") for de in agg_des}
    merged_des = list(agg_des)
    for de in prog_des:
        if de.get("id") not in seen_de:
            seen_de.add(de.get("id"))
            merged_des.append(de)

    return {
        "indicators":         fetch_indicators(client, cfg),
        "program_indicators": fetch_program_indicators(client, cfg),
        "data_elements":      merged_des,
        "datasets":           fetch_datasets(client, cfg),
        "programs":           fetch_programs(client, cfg),
        "org_unit_levels":    fetch_org_unit_levels(client),
        "_filter_config":     cfg,
    }
