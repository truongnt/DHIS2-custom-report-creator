"""dhis2.report_api — deploy upsert-by-name + correct report URL.

Regression (user 2026-06-28): re-deploying created a duplicate DHIS2 report and the
"open" link used the old dhis-web-reporting path. No network.
"""
import pytest

from dhis2 import report_api


class _FakeClient:
    """Records reports.json / POST / PUT calls; serves a preset report list."""
    def __init__(self, existing=None):
        self._existing = existing or []
        self.posts, self.puts = [], []

    def get(self, path, params=None):
        return {"reports": self._existing}

    def post(self, path, payload, timeout=30):
        self.posts.append((path, payload))
        return {"response": {"uid": "NEWuid00001"}}

    def put(self, path, payload, timeout=30):
        self.puts.append((path, payload))
        return {"status": "OK"}


def test_report_url_uses_standard_report_path():
    """REQ-REGR-DEPLOY-02: open link is the dhis-web-reports standard-report view."""
    u = report_api.report_url("https://hmis.gov.la/hmis", "Tx7QqMjJwvB")
    assert u == "https://hmis.gov.la/hmis/dhis-web-reports/index.html#/standard-report/view/Tx7QqMjJwvB"
    # works when base already ends with /api
    u2 = report_api.report_url("https://hmis.gov.la/hmis/api", "abc")
    assert u2.endswith("/dhis-web-reports/index.html#/standard-report/view/abc")


def test_deploy_creates_when_absent():
    """REQ-REGR-DEPLOY-01: a new name → POST (create), returns the new uid."""
    c = _FakeClient(existing=[])
    res = report_api.deploy_report(c, "My Dash", "<html>")
    assert res == {"uid": "NEWuid00001", "updated": False, "name": "My Dash"}
    assert len(c.posts) == 1 and not c.puts


def test_deploy_overwrites_when_name_exists():
    """REQ-REGR-DEPLOY-01: an existing name → PUT same uid (overwrite, no duplicate)."""
    c = _FakeClient(existing=[{"id": "EXISTuid001", "displayName": "My Dash", "type": "HTML"}])
    res = report_api.deploy_report(c, "My Dash", "<html>v2")
    assert res == {"uid": "EXISTuid001", "updated": True, "name": "My Dash"}
    assert c.puts and c.puts[0][0] == "reports/EXISTuid001"
    assert not c.posts, "must NOT create a duplicate when the report already exists"
