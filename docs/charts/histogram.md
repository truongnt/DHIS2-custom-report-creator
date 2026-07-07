# Histogram (`histogram`)

> Plugin: `charts/plugins/histogram.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Distribution of one metric across entities: values are binned and each bin's count is a bar.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | optional — overlay one histogram series per category |
| Time grain | none — the population is entities (org units / events) for the selected period |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`.

Histogram-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `bins` | Bins | Auto / 5 / 10 / 20 / 50 *(or custom int)* | **Auto** | number of equal-width buckets (Auto = Sturges/Freedman–Diaconis) |
| `normalize` | Y axis | Count / Percent | **Count** | raw frequency vs % of total |
| `x_rotation` | X rotation | 0 / 45 / 90 | **45** | bin-edge label rotation (overrides COMMON default 0) |

> Custom value: `bins` accepts a freeform integer (REQ-UI-OPT-01).

## Provenance & feasibility

- **Source:** Superset ("Histogram").
- **Equivalent in:** Superset *Histogram* (DHIS2 n/a).
- **Rendering:** native Chart.js (`type:'bar'` with `categoryPercentage:1, barPercentage:1`); binning in JS.
- **Difficulty / priority:** Low · Medium.
- **Notes:** Binning helper is new; otherwise reuses bar rendering. One row per entity needed (raw values).

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_histogram_checklist.py`.
- E2E: `tests/e2e/test_render_histogram.py`.
- REQ ids: REQ-HISTOGRAM-RENDER-01, REQ-HISTOGRAM-BINS-01, REQ-HISTOGRAM-NORMALIZE-01.
