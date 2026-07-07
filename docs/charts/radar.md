# Radar / Spider (`radar`)

> Plugin: `charts/plugins/radar.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Values plotted on axes radiating from a centre — compares several categories across one or more series.

## Data controls

| Control | Value |
|---|---|
| Metric | 1–3 (`max_count=3`); types: tracker_numeric / aggregate / indicator; agg picker shown |
| Dimension | required — each option value / period / OU becomes one spoke (axis) |
| Time grain | optional (default none; if set, one polygon per period) |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`.

Radar-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `fill` | Fill area | None / Fill | **Fill** | filled translucent polygon vs outline only |
| `scale_max` | Axis max | Auto *(or custom number)* | **Auto** | fixes the outer ring value for comparability |
| `start_angle` | Start angle | 0 / 90 | **0** | rotation of the first spoke |

> No `x_rotation` / `log_scale` (radial layout). Custom value: `scale_max` accepts a number.

## Provenance & feasibility

- **Source:** DHIS2 Data Visualizer ("Radar"); Superset ("Radar Chart").
- **Equivalent in:** DHIS2 *Radar* · Superset *Radar Chart*.
- **Rendering:** native Chart.js (`type:'radar'`).
- **Difficulty / priority:** Low · Medium.
- **Notes:** Best for ≤8 spokes; document a soft cap + warning when the dimension has many values.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_radar_checklist.py`.
- E2E: `tests/e2e/test_render_radar.py`.
- REQ ids: REQ-RADAR-RENDER-01, REQ-RADAR-FILL-01, REQ-RADAR-SCALEMAX-01, REQ-RADAR-ANGLE-01.
