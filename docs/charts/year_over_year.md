# Year over year — line (`year_over_year`)

> Plugin: `charts/plugins/year_over_year.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> One line per year, X-axis = month/period within the year — compare the same period across years.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: tracker_numeric / aggregate / indicator; agg picker shown |
| Dimension | none (the year IS the series split) |
| Time grain | none — fixed to the within-year period (set by `category`) |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`, `x_rotation`.

Year-over-year-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `years` | Years | Last 1 / Last 2 / Last 3 / Last 5 | **Last 3** | how many trailing years become lines |
| `category` | Within-year period | Months / Quarters | **Months** | X-axis granularity (the "series" is months-in-year) |
| `line_tension` | Line curve | Smooth / Straight | **Smooth** | bezier vs straight |

> DHIS2 builds this from `yearlySeries` + a category dimension; offline we map each year to
> its own `pe` set (e.g. `LAST_12_MONTHS` per year) and align by month index.

## Provenance & feasibility

- **Source:** DHIS2 Data Visualizer ("Year over year (line)").
- **Equivalent in:** DHIS2 *Year over year* · Superset *Time-series with time comparison*.
- **Rendering:** native Chart.js (multi-line, X = month index 1–12, one dataset per year).
- **Difficulty / priority:** Low · Medium (clean DHIS2 parity; needs per-year period queries).
- **Notes:** New plugin (no existing equivalent); period-resolution helper differs from `line_trend`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_year_over_year_checklist.py`.
- E2E: `tests/e2e/test_render_yoy.py`.
- REQ ids: REQ-YOY-RENDER-01, REQ-YOY-YEARS-01, REQ-YOY-CATEGORY-01, REQ-YOY-TENSION-01.
