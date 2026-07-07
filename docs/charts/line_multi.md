# Line — compare multiple (`line_multi`)

> Plugin: `charts/plugins/line_multi.py`. Common controls/options: [COMMON.md](COMMON.md).
> One line series per selected data element (up to 3 sources).

## Data controls

| Control | Value |
|---|---|
| Metrics | 1–3 DEs (`max_count=3`, **required**); types: tracker_numeric / aggregate / indicator; agg SUM |
| Dimension | none (each metric = one series) |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

Identical option set to [line_trend](line_trend.md): COMMON options +
`line_tension` (Smooth / Straight) + `fill_area` (None / Fill).

Difference from line_trend: multiple series → `show_legend` is meaningful; one color per DE from the palette.

## Acceptance: `scripts/checklists/test_line_multi_checklist.py` (18 pairs)
