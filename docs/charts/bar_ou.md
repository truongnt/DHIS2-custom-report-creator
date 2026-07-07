# Bar — by org unit (`bar_ou`)

> Plugin: `charts/plugins/bar_ou.py`. Common controls: [COMMON.md](COMMON.md).
> Horizontal bar comparing values across org units. **No SelectControl options**.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 DE (`max_count=1`); types: tracker_option / tracker_numeric / aggregate / indicator; agg picker shown |
| Dimension | none |
| Time grain | none — uses the selected period as a fixed window, no time axis |

## Behavior

One horizontal bar per org unit (children of the selected OU). No time bucketing.

## Acceptance: covered by `tests/test_preview.py` generation checks (no dedicated checklist script).
