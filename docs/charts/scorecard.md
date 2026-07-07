# Scorecard (`scorecard`)

> Plugin: `charts/plugins/scorecard.py`. Common controls/options: [COMMON.md](COMMON.md).
> Single KPI value with a period label. Not a Chart.js chart — renders styled HTML.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 DE (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg SUM |
| Dimension | none |
| Time grain | none |

## Options

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `y_format` | Format | Default / 1,234 / 1.2K / % | Default | number formatting (same semantics as COMMON `y_format`) |
| `value_color` | Value color | Green / Blue / Red / Orange | Green | color of the big number |
| `font_size` | Font size | Large / Medium / Small | Large | size of the big number |

No `color_scheme` / `show_legend` (single value, no series).

## Acceptance: `scripts/checklists/test_scorecard_checklist.py` (9 pairs)
