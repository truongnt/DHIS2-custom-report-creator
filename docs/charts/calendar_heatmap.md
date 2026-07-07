# Calendar heatmap (`calendar_heatmap`)

> Plugin: `charts/plugins/calendar_heatmap.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> A calendar grid (days as cells, weeks as columns) colored by a daily/weekly metric value.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | none |
| Time grain | Daily / Weekly (fixed — calendar granularity) |

## Options

From COMMON: `y_format`.

Calendar-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `cell_grain` | Cell | Day / Week | **Day** | one cell per day vs per ISO week |
| `color_scheme` | Color scheme | Greens / Blues / Reds / Oranges / Purples | **Greens** | sequential ramp (like maps) |
| `show_values` | Cell values | Hide / Show | **Hide** | print value in each cell |
| `start_weekday` | Week starts | Monday / Sunday | **Monday** | first row of the week |

> Overrides COMMON `color_scheme` (sequential) and `show_values` (Hide/Show).

## Provenance & feasibility

- **Source:** Superset ("Calendar Heatmap").
- **Equivalent in:** Superset *Calendar Heatmap* (DHIS2 n/a).
- **Rendering:** lib `chartjs-chart-matrix` (date-positioned cells) or a small D3/custom SVG.
- **Difficulty / priority:** Medium · Low (needs daily data; many aggregate sources are monthly).
- **Notes:** Only meaningful when the source has daily/weekly periods (e.g. event dates). Document this limit.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_calendar_heatmap_checklist.py`.
- E2E: `tests/e2e/test_render_calendar_heatmap.py`.
- REQ ids: REQ-CALHEAT-RENDER-01, REQ-CALHEAT-GRAIN-01, REQ-CALHEAT-COLOR-01, REQ-CALHEAT-WEEKDAY-01.
