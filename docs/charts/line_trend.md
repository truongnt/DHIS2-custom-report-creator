# Line — trend over time (`line_trend`)

> Plugin: `charts/plugins/line_trend.py`. Common controls/options: [COMMON.md](COMMON.md).
> Single metric tracked over time with full formatting options.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 DE (`max_count=1`); types: tracker_numeric / aggregate / indicator; agg SUM |
| Dimension | none |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

All from COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`, `x_rotation`, `log_scale`.

Line-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `line_tension` | Line curve | Smooth / Straight | Smooth | Smooth = bezier (`tension>0`), Straight = `tension:0` |
| `fill_area` | Fill area | None / Fill | None | Fill = area under line (`fill:true` + translucent bg) |

## Acceptance: `scripts/checklists/test_line_trend_checklist.py` (18 pairs)
