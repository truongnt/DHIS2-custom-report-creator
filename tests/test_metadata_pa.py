"""Program-attribute (PA / tracked-entity-attribute) metadata fetching.

Regression (user report 2026-06-26 "phải lấy hết cả PA của prog không để sót" —
must capture EVERY PA of a program, miss none): a PA shared by two programs was
deduplicated GLOBALLY and so only appeared under the first program, going missing
for the others. Each program must carry its full PA set.
"""
import pytest

from dhis2.metadata import fetch_tracked_entity_attributes


class _FakeClient:
    """Minimal stand-in: returns one canned payload for programs.json."""
    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return self._payload


def _tea(uid, name, vt="TEXT"):
    return {"id": uid, "displayName": name, "valueType": vt, "optionSet": None}


def test_pa_shared_by_two_programs_appears_under_both():
    """REQ-META-PA-01: a PA on programs A and B is returned for BOTH, not just the first."""
    sex = _tea("DmuazFb368B", "Sex")
    payload = {"programs": [
        {"id": "PROGA000001", "displayName": "Malaria",
         "programTrackedEntityAttributes": [
             {"trackedEntityAttribute": sex},
             {"trackedEntityAttribute": _tea("ageUid00001", "Age", "INTEGER")}]},
        {"id": "PROGB000001", "displayName": "TB",
         "programTrackedEntityAttributes": [
             {"trackedEntityAttribute": sex}]},   # same PA, different program
    ]}
    out = fetch_tracked_entity_attributes(_FakeClient(payload), ["PROGA000001", "PROGB000001"])
    progs_with_sex = {r["program"]["id"] for r in out if r["id"] == "DmuazFb368B"}
    assert progs_with_sex == {"PROGA000001", "PROGB000001"}, \
        f"Sex must appear under BOTH programs, got {progs_with_sex}"


def test_pa_full_set_per_program():
    """REQ-META-PA-02: every PA declared on a program is captured (none dropped)."""
    payload = {"programs": [
        {"id": "PROGA000001", "displayName": "Malaria",
         "programTrackedEntityAttributes": [
             {"trackedEntityAttribute": _tea("tea00000001", "Sex")},
             {"trackedEntityAttribute": _tea("tea00000002", "Age", "INTEGER")},
             {"trackedEntityAttribute": _tea("tea00000003", "Village")}]},
    ]}
    out = fetch_tracked_entity_attributes(_FakeClient(payload), ["PROGA000001"])
    uids = {r["id"] for r in out if r["program"]["id"] == "PROGA000001"}
    assert uids == {"tea00000001", "tea00000002", "tea00000003"}


def test_pa_dedup_within_one_program():
    """REQ-META-PA-03: a PA listed twice on the SAME program is not duplicated."""
    sex = _tea("DmuazFb368B", "Sex")
    payload = {"programs": [
        {"id": "PROGA000001", "displayName": "Malaria",
         "programTrackedEntityAttributes": [
             {"trackedEntityAttribute": sex},
             {"trackedEntityAttribute": sex}]},
    ]}
    out = fetch_tracked_entity_attributes(_FakeClient(payload), ["PROGA000001"])
    assert len([r for r in out if r["id"] == "DmuazFb368B"]) == 1
