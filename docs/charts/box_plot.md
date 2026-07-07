# Box plot (`box_plot`)

> Plugin: `charts/plugins/box_plot.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Five-number summary (min, Q1, median, Q3, max) per category — shows spread and outliers.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | required — one box per category (e.g. OU group, option value) |
| Time grain | optional — one box per period when no dimension |

## Options

From COMMON: `color_scheme`, `show_legend`, `y_format`, `log_scale`.

Box-plot-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `whisker` | Whiskers | Min/Max / 1.5 IQR | **1.5 IQR** | whisker extent; 1.5·IQR flags points beyond as outliers |
| `show_outliers` | Outliers | Hide / Show | **Show** | draw individual outlier points |
| `orientation` | Orientation | Vertical / Horizontal | **Vertical** | box direction |

## Provenance & feasibility

- **Source:** Superset ("Box Plot").
- **Equivalent in:** Superset *Box Plot* (DHIS2 n/a).
- **Rendering:** lib `chartjs-chart-boxplot`; quartiles computed in JS from per-entity values.
- **Difficulty / priority:** Medium · Low (needs raw per-entity values, not aggregates).
- **Notes:** Requires the underlying distribution (one row per OU/event), like `histogram`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_box_plot_checklist.py`.
- E2E: `tests/e2e/test_render_box_plot.py`.
- REQ ids: REQ-BOXPLOT-RENDER-01, REQ-BOXPLOT-WHISKER-01, REQ-BOXPLOT-OUTLIERS-01, REQ-BOXPLOT-ORIENT-01.
