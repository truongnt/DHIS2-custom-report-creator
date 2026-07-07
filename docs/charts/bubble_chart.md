# Bubble chart (`bubble_chart`)

> Plugin: `charts/plugins/bubble_chart.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Scatter where each point's radius encodes a third metric — (X, Y, size) per entity. Not a map.

## Data controls

| Control | Value |
|---|---|
| Metric | exactly 3 (`max_count=3`, **required**): X, Y, size; types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | optional — color bubbles by category |
| Time grain | none — bubbles are entities (org units) |

## Options

From COMMON: `color_scheme`, `show_legend`, `y_format`, `log_scale`.

Bubble-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `max_radius` | Max bubble size | Small / Medium / Large *(or custom px)* | **Medium** | radius of the largest bubble (∝ sqrt(size)) |
| `fill_opacity` | Fill opacity | 0.25 / 0.5 / 0.8 *(or custom 0–1)* | **0.5** | bubble translucency |
| `label_points` | Bubble labels | Off / On | **Off** | entity name on each bubble |

> Distinct from `point_map` (geographic bubbles). Custom values per REQ-UI-OPT-01.

## Provenance & feasibility

- **Source:** Superset ("Bubble Chart").
- **Equivalent in:** Superset *Bubble Chart* (DHIS2 has no non-geographic bubble chart).
- **Rendering:** native Chart.js (`type:'bubble'`); radius from sqrt scaling like `point_map`.
- **Difficulty / priority:** Low · Medium.
- **Notes:** Three-metric join per OU; reuse the sqrt radius helper from `point_map`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_bubble_chart_checklist.py`.
- E2E: `tests/e2e/test_render_bubble_chart.py`.
- REQ ids: REQ-BUBBLECHART-RENDER-01, REQ-BUBBLECHART-RADIUS-01, REQ-BUBBLECHART-OPACITY-01, REQ-BUBBLECHART-LABELS-01.
