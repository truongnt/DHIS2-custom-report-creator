# Heatmap — matrix (`heatmap`)

> Plugin: `charts/plugins/heatmap.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> A grid of colored cells: rows × columns (e.g. org unit × period), cell color = metric value.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | required — defines the **columns** (e.g. option value); rows = OU; or rows=OU, cols=period |
| Time grain | optional — when columns are periods, sets their granularity |

## Options

From COMMON: `y_format`.

Heatmap-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `rows` | Rows | Org Unit / Dimension | **Org Unit** | what the Y axis lists |
| `columns` | Columns | Period / Dimension | **Period** | what the X axis lists |
| `color_scheme` | Color scheme | Blues / Greens / Reds / Oranges / Purples / RdYlGn | **Blues** | sequential ramp (like maps, **not** categorical COMMON) |
| `normalize` | Normalize | None / Per row / Per column | **None** | scale colors within each row/column instead of globally |
| `show_values` | Cell values | Hide / Show | **Hide** | print the number in each cell |

> Overrides COMMON `color_scheme` (sequential) and `show_values` (Hide/Show, like maps).

## Provenance & feasibility

- **Source:** Superset ("Heatmap").
- **Equivalent in:** Superset *Heatmap* (DHIS2 pivot table with color ~ `table_view` heatmap option).
- **Rendering:** lib `chartjs-chart-matrix`.
- **Difficulty / priority:** Medium · Medium.
- **Notes:** Overlaps `table_view` heatmap mode; this is the dense grid form. Reuse map `_SCHEMES` ramp.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_heatmap_checklist.py`.
- E2E: `tests/e2e/test_render_heatmap.py`.
- REQ ids: REQ-HEATMAP-RENDER-01, REQ-HEATMAP-AXES-01, REQ-HEATMAP-COLOR-01, REQ-HEATMAP-NORMALIZE-01, REQ-HEATMAP-VALUES-01.
