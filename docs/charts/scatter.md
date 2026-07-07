# Scatter plot (`scatter`)

> Plugin: `charts/plugins/scatter.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Each point plots one entity at (X metric, Y metric) — reveals correlation between two measures.

## Data controls

| Control | Value |
|---|---|
| Metric | exactly 2 (`max_count=2`, both **required**): metric[0]=X, metric[1]=Y; types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | optional — color points by category (one series per value) |
| Time grain | none — points are entities (org units), not periods |

## Options

From COMMON: `color_scheme`, `show_legend`, `y_format`, `log_scale` (per axis).

Scatter-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `point_size` | Point size | Small / Medium / Large *(or custom px)* | **Medium** | marker radius |
| `trend_line` | Trend line | Off / Linear | **Off** | least-squares regression line overlay |
| `x_log` | X log scale | Off / On | **Off** | log X axis (Y log via COMMON `log_scale`) |
| `label_points` | Point labels | Off / On | **Off** | show entity (OU) name beside each point |

> Custom value: `point_size` accepts a freeform px number (REQ-UI-OPT-01).

## Provenance & feasibility

- **Source:** DHIS2 Data Visualizer ("Scatter"); Superset ("Scatter Plot" / time-series scatter).
- **Equivalent in:** DHIS2 *Scatter* · Superset *Scatter Plot*.
- **Rendering:** native Chart.js (`type:'scatter'`); regression computed in JS.
- **Difficulty / priority:** Low · High (distinct, useful, two-metric pattern reusable).
- **Notes:** Needs two metrics joined per OU (X,Y) — new join helper vs the per-period charts.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_scatter_checklist.py`.
- E2E: `tests/e2e/test_render_scatter.py`.
- REQ ids: REQ-SCATTER-RENDER-01, REQ-SCATTER-SIZE-01, REQ-SCATTER-TREND-01, REQ-SCATTER-LOG-01, REQ-SCATTER-LABELS-01.
