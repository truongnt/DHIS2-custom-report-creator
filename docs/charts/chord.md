# Chord diagram (`chord`)

> Plugin: `charts/plugins/chord.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Nodes arranged on a circle with ribbons between them — shows pairwise flows/relationships.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`) = relationship magnitude; types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | **two** required: `source` and `target` (the same category set on both ends) |
| Time grain | none (snapshot) |

## Options

From COMMON: `color_scheme`, `show_values`.

Chord-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `directed` | Directed | No / Yes | **No** | symmetric relationships vs directional (source→target) ribbons |
| `sort` | Node order | By value / Alphabetical | **By value** | arrangement of nodes around the circle |

## Provenance & feasibility

- **Source:** Superset ("Chord Diagram").
- **Equivalent in:** Superset *Chord* (DHIS2 n/a).
- **Rendering:** D3 chord layout (no Chart.js equivalent).
- **Difficulty / priority:** High · Low (very niche for DHIS2 data).
- **Notes:** Needs a square source×target matrix; same data prerequisite as `sankey`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_chord_checklist.py`.
- E2E: `tests/e2e/test_render_chord.py`.
- REQ ids: REQ-CHORD-RENDER-01, REQ-CHORD-DIRECTED-01, REQ-CHORD-SORT-01.
