# Stacked bar — by category (`stacked_cat`)

> Plugin: `charts/plugins/stacked_cat.py`. Common controls: [COMMON.md](COMMON.md).
> Stacked bars where each option-set value is one stack layer. **No SelectControl options.**

## Data controls

| Control | Value |
|---|---|
| Metric | 0–1 DE (`max_count=1`, **optional** — empty = event count); agg picker shown |
| Dimension | **required** — option-set DE; each option value becomes one stack layer |
| Time grain | Monthly (default), Quarterly, Yearly |

## Behavior

Per period, a single bar split into layers by the dimension's option values.
(Contrast with `bar` stack_mode=Stack, which is the configurable general version;
this plugin is the dedicated category-stack variant.)

## Acceptance: covered by `tests/test_preview.py` generation checks (no dedicated checklist script).
