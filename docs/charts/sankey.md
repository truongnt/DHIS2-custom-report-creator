# Sankey diagram (`sankey`)

> Plugin: `charts/plugins/sankey.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Flow diagram: nodes linked by ribbons whose width encodes the volume flowing source→target.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`) = flow magnitude; types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | **two** required: `source` and `target` category dimensions (the flow endpoints) |
| Time grain | none (snapshot) |

## Options

From COMMON: `color_scheme`, `y_format`.

Sankey-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `node_color` | Node color | By source / By target / Single | **By source** | how link/node colors are assigned |
| `node_align` | Node alignment | Justify / Left / Right | **Justify** | horizontal node placement |
| `show_values` | Link labels | Hide / Show | **Hide** | print flow magnitude on links |

> Needs a 2-dimension data model (source, target) — distinct from every current plugin.

## Provenance & feasibility

- **Source:** Superset ("Sankey Diagram").
- **Equivalent in:** Superset *Sankey* (DHIS2 n/a).
- **Rendering:** lib `chartjs-chart-sankey`.
- **Difficulty / priority:** Medium · Low–Medium (powerful but needs source/target pairs, uncommon in DHIS2 aggregate data).
- **Notes:** Requires event/enrollment data that has both a "from" and "to" category (e.g. referral path).

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_sankey_checklist.py`.
- E2E: `tests/e2e/test_render_sankey.py`.
- REQ ids: REQ-SANKEY-RENDER-01, REQ-SANKEY-NODECOLOR-01, REQ-SANKEY-ALIGN-01, REQ-SANKEY-VALUES-01.
