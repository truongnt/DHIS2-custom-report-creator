# Area — trend over time (`area`)

> Plugin: `charts/plugins/area.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Line chart with the area under each series filled — emphasises magnitude over time.

## Data controls

| Control | Value |
|---|---|
| Metric | 1–3 (`max_count=3`); types: tracker_numeric / tracker_option / aggregate / indicator; agg picker shown |
| Dimension | optional — one filled series per option value (e.g. PF vs PV) |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`, `x_rotation`, `log_scale`.

Area-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `line_tension` | Line curve | Smooth / Straight | **Smooth** | bezier vs straight segments (same as line_trend) |
| `fill_opacity` | Fill opacity | 0.1 / 0.25 / 0.5 / 0.8 *(or custom 0–1)* | **0.25** | translucency of the filled area (`backgroundColor` alpha) |
| `stack_mode` | Stack mode | None / Stack / Expand | **None** | None = overlapping areas; Stack = cumulative; Expand = 100% — *if not split into [stacked_area](stacked_area.md)* |

> Custom value (REQ-UI-OPT-01): `fill_opacity` accepts a freeform 0–1 number.

## Provenance & feasibility

- **Source:** DHIS2 Data Visualizer ("Area"); Superset ("Area Chart" / time-series area).
- **Equivalent in:** DHIS2 *Area* · Superset *Area Chart*.
- **Rendering:** native Chart.js (`type:'line'`, `fill:true`).
- **Difficulty / priority:** Low · High (common, easy).
- **Notes:** ~95% shared with `line_trend`; could be a `fill_area` preset on line_trend, but a
  dedicated type matches DHIS2 + is clearer in the picker.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_area_checklist.py` (one BEFORE/AFTER pair per option).
- E2E: `tests/e2e/test_render_area.py`.
- REQ ids: REQ-AREA-RENDER-01, REQ-AREA-FILL-01, REQ-AREA-TENSION-01, REQ-AREA-STACK-01, REQ-AREA-DIM-01.
