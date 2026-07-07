# Stacked area (`stacked_area`)

> Plugin: `charts/plugins/stacked_area.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Areas stacked so the top edge is the total — shows composition of a total over time.

## Data controls

| Control | Value |
|---|---|
| Metric | 1–3 (`max_count=3`); types: tracker_numeric / aggregate / indicator; agg picker shown |
| Dimension | optional — one stacked band per option value |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`, `y_format`, `x_rotation`.

Stacked-area-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `stack_mode` | Stack mode | Stack / Expand | **Stack** | Stack = cumulative totals; Expand = 100% normalized |
| `fill_opacity` | Fill opacity | 0.25 / 0.5 / 0.8 *(or custom 0–1)* | **0.5** | translucency of each band |
| `line_tension` | Line curve | Smooth / Straight | **Smooth** | bezier vs straight |

> No `log_scale` (meaningless on a stacked composition).

## Provenance & feasibility

- **Source:** DHIS2 Data Visualizer ("Stacked area"); Superset ("Area Chart" stacked).
- **Equivalent in:** DHIS2 *Stacked area* · Superset *Area Chart (stacked)*.
- **Rendering:** native Chart.js (`type:'line'`, `fill:true`, `scales.y.stacked:true`; Expand = normalize).
- **Difficulty / priority:** Low · Medium.
- **Notes:** Could be folded into [area](area.md) via `stack_mode`. Keep separate only if
  the picker should list it like DHIS2 does. Reuse `_expand_normalize_js` from `bar.py`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_stacked_area_checklist.py`.
- E2E: `tests/e2e/test_render_stacked_area.py`.
- REQ ids: REQ-STACKAREA-RENDER-01, REQ-STACKAREA-STACK-01, REQ-STACKAREA-EXPAND-01, REQ-STACKAREA-FILL-01.
