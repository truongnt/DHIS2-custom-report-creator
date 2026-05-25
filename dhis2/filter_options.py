"""
Lightweight fetch of groups and programs used to populate the filter config UI.
These calls are fast (metadata is small) and run right after connect.

Returns:
  indicator_groups  — list of {id, displayName, indicatorCount}
  de_groups         — list of {id, displayName, dataElementCount}
  programs          — list of {id, displayName, programType}
"""
from __future__ import annotations
from dhis2.client import DHIS2Client


def fetch_indicator_groups(client: DHIS2Client) -> list[dict]:
    """
    Ref: GET /api/indicatorGroups
    Returns all groups with member count.
    """
    data = client.get("indicatorGroups.json", params={
        "fields": "id,displayName,indicators~size",
        "paging": "false",
        "order":  "displayName:asc",
    })
    rows = []
    for g in data.get("indicatorGroups", []):
        rows.append({
            "id":           g.get("id"),
            "displayName":  g.get("displayName"),
            "count":        g.get("indicators", 0),
        })
    return rows


def fetch_de_groups(client: DHIS2Client) -> list[dict]:
    """
    Ref: GET /api/dataElementGroups
    Returns all groups with member count.
    """
    data = client.get("dataElementGroups.json", params={
        "fields": "id,displayName,dataElements~size",
        "paging": "false",
        "order":  "displayName:asc",
    })
    rows = []
    for g in data.get("dataElementGroups", []):
        rows.append({
            "id":          g.get("id"),
            "displayName": g.get("displayName"),
            "count":       g.get("dataElements", 0),
        })
    return rows


def fetch_programs_list(client: DHIS2Client) -> list[dict]:
    """
    Ref: GET /api/programs
    Returns all programs with type label.
    """
    data = client.get("programs.json", params={
        "fields": "id,displayName,programType",
        "paging": "false",
        "order":  "displayName:asc",
    })
    type_labels = {
        "WITH_REGISTRATION":    "Tracker",
        "WITHOUT_REGISTRATION": "Event",
    }
    rows = []
    for p in data.get("programs", []):
        ptype = p.get("programType", "")
        rows.append({
            "id":          p.get("id"),
            "displayName": p.get("displayName"),
            "type":        type_labels.get(ptype, ptype),
        })
    return rows


def fetch_datasets_list(client: DHIS2Client) -> list[dict]:
    """
    Ref: GET /api/dataSets
    Returns all datasets with data element count and period type.
    """
    data = client.get("dataSets.json", params={
        "fields": "id,displayName,periodType,dataSetElements~size",
        "paging": "false",
        "order":  "displayName:asc",
    })
    rows = []
    for d in data.get("dataSets", []):
        rows.append({
            "id":          d.get("id"),
            "displayName": d.get("displayName"),
            "periodType":  d.get("periodType", ""),
            "count":       d.get("dataSetElements", 0),
        })
    return rows


def fetch_all_filter_options(client: DHIS2Client) -> dict:
    """Fetch all lists in one call. Fast — only names/counts, no member details."""
    return {
        "indicator_groups": fetch_indicator_groups(client),
        "de_groups":        fetch_de_groups(client),
        "programs":         fetch_programs_list(client),
        "datasets":         fetch_datasets_list(client),
    }
