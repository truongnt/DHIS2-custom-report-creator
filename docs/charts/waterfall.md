# Waterfall (`waterfall`)

> Plugin: `charts/plugins/waterfall.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Floating bars showing how an initial value grows/shrinks step by step to a final total.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | required — ordered steps (one bar per category / period) |
| Time grain | optional — when dimension is a period, steps = periods |

## Options

From COMMON: `show_legend`, `show_values`, `y_format`, `x_rotation`.

Waterfall-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `mode` | Mode | Delta / Absolute | **Delta** | Delta = each bar is the change vs previous; Absolute = each bar is a value, deltas computed |
| `total_bar` | Total bar | Off / On | **On** | append a final cumulative "Total" bar |
| `up_color` | Increase color | green *(or custom #hex)* | **#27ae60** | color for positive steps |
| `down_color` | Decrease color | red *(or custom #hex)* | **#e74c3c** | color for negative steps |

> Uses fixed up/down colors instead of `color_scheme`. Custom values per REQ-UI-OPT-01.

## Provenance & feasibility

- **Source:** Superset ("Waterfall Chart").
- **Equivalent in:** Superset *Waterfall* (DHIS2 n/a).
- **Rendering:** native Chart.js (`type:'bar'` with floating `[start,end]` bar values).
- **Difficulty / priority:** Low · Medium.
- **Notes:** Cumulative-offset computation in JS; reuses bar scaffolding.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_waterfall_checklist.py`.
- E2E: `tests/e2e/test_render_waterfall.py`.
- REQ ids: REQ-WATERFALL-RENDER-01, REQ-WATERFALL-MODE-01, REQ-WATERFALL-TOTAL-01, REQ-WATERFALL-COLOR-01.
