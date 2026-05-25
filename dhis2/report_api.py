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

_DEFAULT_REPORT_PARAMS = {
    "reportingPeriod": True,
    "organisationUnit": True,
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


def report_url(base_url: str, report_uid: str) -> str:
    """Direct URL to run the report in DHIS2 web UI."""
    base = base_url.rstrip("/").replace("/api", "")
    return f"{base}/dhis-web-reporting/getReport.action?uid={report_uid}&type=HTML&mode=REPORT"
