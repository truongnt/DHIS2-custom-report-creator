"""Unit: filter query builder — program attributes (TEA) use a bare-uid dimension,
data elements use stage.uid. (User report 2026-06-26: PA missing/incorrect.)"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from charts.plugins.base import ChartPlugin


def test_filter_params_tea_vs_de():
    """REQ-CE-PA-01: TEA filter → bare uid; stage DE filter → stage-prefixed uid."""
    cfg = {"source": {"stage_uid": "STG1"}, "dimensions": {"filters": [
        {"de_uid": "deX0000001", "op": "EQ", "value": "PF", "is_tea": False},
        {"de_uid": "teaG000001", "op": "EQ", "value": "M",  "is_tea": True},
    ]}}
    out = ChartPlugin._filter_params(cfg)
    assert "filter=STG1.deX0000001:EQ:PF" in out
    assert "filter=teaG000001:EQ:M" in out
    assert "STG1.teaG000001" not in out          # PA must NOT be stage-prefixed
