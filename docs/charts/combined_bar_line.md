# Combined bar + line (`combined_bar_line`)

> Plugin: `charts/plugins/combined_bar_line.py`. Common controls/options: [COMMON.md](COMMON.md).
> First metric drawn as bars, second metric as a line overlay — two sources required.

## Data controls

| Control | Value |
|---|---|
| Metric (bar) | 1 DE, **required** — `metric_bar` |
| Metric (line) | 1 DE, **required** — `metric_line` |
| Dimension | none |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`, `x_rotation`.

Combined-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `dual_y_axis` | Dual Y axis | No / Yes | No | Yes = line metric gets its own right-hand Y axis (independent scale) |

## Acceptance: `scripts/checklists/test_combined_checklist.py` (15 pairs)
