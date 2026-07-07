# Treemap (`treemap`)

> Plugin: `charts/plugins/treemap.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Nested rectangles sized by value — shows part-to-whole, optionally across an OU hierarchy.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | required — one tile per option value / OU; optional 2nd level for grouping |
| Time grain | none (snapshot for selected period) |

## Options

From COMMON: `color_scheme`, `show_values`, `y_format`.

Treemap-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `group_by` | Group level | None / OU parent / Dimension | **None** | adds a second nesting level (grouped tiles) |
| `label_mode` | Tile label | Name / Name+Value / None | **Name+Value** | what each tile shows |
| `color_by` | Color by | Category / Value | **Category** | distinct color per tile vs sequential ramp by value |

> When `color_by=Value`, uses a sequential ramp like the maps; else the categorical palette.

## Provenance & feasibility

- **Source:** Superset ("Treemap").
- **Equivalent in:** Superset *Treemap* (DHIS2 n/a).
- **Rendering:** lib `chartjs-chart-treemap`.
- **Difficulty / priority:** Medium · Medium (nice for OU-hierarchy breakdowns).
- **Notes:** Hierarchical data shape (parent→children); reuse OU-parent chain already built for maps.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_treemap_checklist.py`.
- E2E: `tests/e2e/test_render_treemap.py`.
- REQ ids: REQ-TREEMAP-RENDER-01, REQ-TREEMAP-GROUP-01, REQ-TREEMAP-LABEL-01, REQ-TREEMAP-COLOR-01.
