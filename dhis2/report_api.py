"""
Create / update / list DHIS2 Standard Reports (type: HTML).

DHIS2 API: POST /api/reports
Payload shape:
{
  "name": "My Report",
  "type": "HTML",
  "relativePeriods": {"last12Months": true},
  "reportParams": {"reportingPeriod": true, "organisationUnit": true},
  "designContent": "<html>...</html>"
}
"""
from __future__ import annotations
from dhis2.client import DHIS2Client


_DEFAULT_RELATIVE_PERIODS = {
    "last12Months": True,
}

# Both set to False so DHIS2 runs the report directly without prompting user to pick org/period.
# The report HTML already has hardcoded analytics calls with the right filters.
_DEFAULT_REPORT_PARAMS = {
    "reportingPeriod": False,
    "organisationUnit": False,
}


def create_report(
    client: DHIS2Client,
    name: str,
    html_content: str,
    relative_periods: dict | None = None,
    report_params: dict | None = None,
) -> dict:
    """
    Create a new DHIS2 Standard HTML report.
    Returns the API response (includes the new report's UID in 'response.uid').
    """
    payload = {
        "name": name,
        "type": "HTML",
        "relativePeriods": relative_periods or _DEFAULT_RELATIVE_PERIODS,
        "reportParams":    report_params    or _DEFAULT_REPORT_PARAMS,
        "designContent":   html_content,
    }
    return client.post("reports", payload)


def update_report(
    client: DHIS2Client,
    report_uid: str,
    name: str,
    html_content: str,
    relative_periods: dict | None = None,
    report_params: dict | None = None,
) -> dict:
    """Update an existing DHIS2 HTML report by UID."""
    payload = {
        "name": name,
        "type": "HTML",
        "relativePeriods": relative_periods or _DEFAULT_RELATIVE_PERIODS,
        "reportParams":    report_params    or _DEFAULT_REPORT_PARAMS,
        "designContent":   html_content,
    }
    return client.put(f"reports/{report_uid}", payload)


def list_reports(client: DHIS2Client) -> list[dict]:
    """Return all existing HTML reports (id, displayName)."""
    data = client.get("reports.json", params={
        "fields": "id,displayName,type",
        "filter": "type:eq:HTML",
        "paging": "false",
    })
    return data.get("reports", [])


def deploy_report(
    client: DHIS2Client,
    name: str,
    html_content: str,
    relative_periods: dict | None = None,
    report_params: dict | None = None,
) -> dict:
    """
    Upsert an HTML report by NAME: if a report with the same name already exists it is
    UPDATED in place (same UID → its link stays valid); otherwise a new one is created.
    Re-deploying a dashboard therefore overwrites instead of piling up duplicates.

    Returns {"uid": <uid>, "updated": bool, "name": name}.
    """
    existing = next((r for r in list_reports(client)
                     if (r.get("displayName") or "") == name), None)
    if existing:
        uid = existing["id"]
        update_report(client, uid, name, html_content, relative_periods, report_params)
        return {"uid": uid, "updated": True, "name": name}
    res = create_report(client, name, html_content, relative_periods, report_params)
    uid = (res.get("response", {}) or {}).get("uid") or res.get("uid") or ""
    return {"uid": uid, "updated": False, "name": name}


def report_url(base_url: str, report_uid: str) -> str:
    """Direct URL to open the standard HTML report in the DHIS2 web UI."""
    base = base_url.rstrip("/").replace("/api", "")
    return f"{base}/dhis-web-reports/index.html#/standard-report/view/{report_uid}"
