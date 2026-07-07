# Graph / Network (`network`)

> Plugin: `charts/plugins/network.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Force-directed node-link graph — entities as nodes, relationships as edges.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`) = edge weight (and/or node size); types: aggregate / indicator / tracker_numeric |
| Dimension | **two** required: `source` and `target` node dimensions |
| Time grain | none (snapshot) |

## Options

From COMMON: `color_scheme`, `show_legend`.

Network-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `layout` | Layout | Force / Circular | **Force** | node placement algorithm |
| `node_size` | Node size | Uniform / By degree / By value | **By degree** | what scales node radius |
| `show_labels` | Node labels | Hide / Show | **Show** | print node names |

## Provenance & feasibility

- **Source:** Superset ("Graph Chart").
- **Equivalent in:** Superset *Graph/Network* (DHIS2 n/a).
- **Rendering:** ECharts graph or `vis-network` (no Chart.js equivalent).
- **Difficulty / priority:** High · Low (niche; needs relationship data).
- **Notes:** Same source/target prerequisite as `sankey`/`chord`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_network_checklist.py`.
- E2E: `tests/e2e/test_render_network.py`.
- REQ ids: REQ-NETWORK-RENDER-01, REQ-NETWORK-LAYOUT-01, REQ-NETWORK-NODESIZE-01, REQ-NETWORK-LABELS-01.
