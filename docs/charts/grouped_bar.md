# Grouped bar — compare sources (`grouped_bar`)

> Plugin: `charts/plugins/grouped_bar.py`. Common controls: [COMMON.md](COMMON.md).
> Side-by-side bars per period, one group per data element (up to 3 sources).
> **No SelectControl options.**

## Data controls

| Control | Value |
|---|---|
| Metrics | 1–3 DEs (`max_count=3`, **required**); types: tracker_numeric / aggregate / indicator; agg SUM |
| Dimension | none (each metric = one bar group) |
| Time grain | Monthly (default), Quarterly, Yearly |

## Behavior

Per period, draws one bar per selected DE grouped together. (Contrast with `bar` stack_mode=None +
2–3 metrics, which also groups — this plugin is the dedicated multi-source variant.)

## Acceptance: covered by `tests/test_preview.py` generation checks (no dedicated checklist script).
