# Sunburst (`sunburst`)

> Plugin: `charts/plugins/sunburst.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Concentric rings showing a hierarchy: inner ring = parent, outer rings = children, angle = value.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | 1–2 required — ring levels (e.g. OU level → option value; or province → district) |
| Time grain | none (snapshot) |

## Options

From COMMON: `color_scheme`, `show_values`, `y_format`.

Sunburst-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `levels` | Hierarchy | OU hierarchy / Dimension chain | **OU hierarchy** | what the rings represent |
| `label_mode` | Labels | Name / Name+Value / None | **Name** | arc labels |
| `color_by` | Color by | Top level / Value | **Top level** | inherit parent color vs sequential ramp by value |

## Provenance & feasibility

- **Source:** Superset ("Sunburst Chart").
- **Equivalent in:** Superset *Sunburst* (DHIS2 n/a).
- **Rendering:** ECharts or D3 (no clean Chart.js sunburst) — heaviest dependency of this set.
- **Difficulty / priority:** High · Low (niche; hierarchical data + new render lib).
- **Notes:** Reuses the OU-parent chain (already built for maps) to form the hierarchy.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_sunburst_checklist.py`.
- E2E: `tests/e2e/test_render_sunburst.py`.
- REQ ids: REQ-SUNBURST-RENDER-01, REQ-SUNBURST-LEVELS-01, REQ-SUNBURST-LABEL-01, REQ-SUNBURST-COLOR-01.
