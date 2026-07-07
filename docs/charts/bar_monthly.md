# Bar — monthly trend (`bar_monthly`)

> Plugin: `charts/plugins/bar_monthly.py`. Common controls: [COMMON.md](COMMON.md).
> A bar variant fixed to a monthly time axis. **No SelectControl options** (`options` not defined)
> — appearance is driven entirely by the data controls below.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 DE (`max_count=1`); types: tracker_numeric / aggregate / indicator; agg SUM |
| Dimension | none |
| Time grain | Monthly (default) |

## Behavior

One bar per month for the selected period. Rendering reuses the bar palette/options conventions;
since no `options` list is defined, only the standard data controls apply.

## Acceptance: covered by `tests/test_preview.py` generation checks (no dedicated checklist script).
