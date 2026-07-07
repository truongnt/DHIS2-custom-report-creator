# Funnel (`funnel`)

> Plugin: `charts/plugins/funnel.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Descending stacked segments showing drop-off through ordered stages — ideal for care cascades.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric / tracker_option; agg picker shown |
| Dimension | required — ordered stages (one segment per option value, e.g. Tested → Positive → Treated) |
| Time grain | none (snapshot for the selected period) |

## Options

From COMMON: `color_scheme`, `show_legend`, `y_format`.

Funnel-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `label_mode` | Segment label | Value / Percent of first / Percent of previous | **Percent of first** | what each stage shows |
| `order` | Stage order | As selected / Descending value | **As selected** | keep metric order vs auto-sort by size |
| `orientation` | Orientation | Vertical / Horizontal | **Vertical** | funnel direction |

> `label_mode` percentages are the cascade conversion rates (health-relevant).

## Provenance & feasibility

- **Source:** Superset ("Funnel Chart").
- **Equivalent in:** Superset *Funnel* (DHIS2 n/a).
- **Rendering:** lib `chartjs-plugin-funnel` (or custom trapezoids on a canvas).
- **Difficulty / priority:** Medium · **High** — directly models continuum-of-care / cascade analyses.
- **Notes:** Stage order matters; default preserves the user's metric/option order.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_funnel_checklist.py`.
- E2E: `tests/e2e/test_render_funnel.py`.
- REQ ids: REQ-FUNNEL-RENDER-01, REQ-FUNNEL-LABEL-01, REQ-FUNNEL-ORDER-01, REQ-FUNNEL-ORIENT-01.
