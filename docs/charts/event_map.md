# Event map (`event_map`)

> Plugin: `charts/plugins/event_map.py` (proposed). Common controls: [COMMON.md](COMMON.md).
> Individual tracker events plotted at their own coordinates, optionally styled by a data element,
> with a density heat mode. Maps do **not** use the categorical COMMON options.

## Data controls

| Control | Value |
|---|---|
| Metric | optional — a DE to style/size points by (else uniform event dots) |
| Dimension | optional — color points by an option-set DE/PA value (e.g. PF vs PV) |
| Time grain | none (events filtered by the dashboard period) |

## Options

| key | type | choices | default | behavior |
|---|---|---|---|---|
| `render_mode` | Select | Points / Heat / Cluster | **Points** | individual dots, density heatmap, or clustered counts |
| `coordinate_field` | Select | Event / Org unit / Tracked entity | **Event** | which coordinate the point uses |
| `base_map` | Select | CartoDB Light / OpenStreetMap / CartoDB Dark / Satellite / None | CartoDB Light | tile layer |
| `overlay_levels` | CheckboxGroup | Level 2 / 3 / 4 / 5 | (Level 2) | boundary context lines |
| `point_color` | Select | Blue / Red / Green / Orange / Purple *(or #hex)* | **Blue** | dot color (when no dimension) |
| `point_size` | Select | Small / Medium / Large *(or px)* | **Small** | dot radius |
| `show_values` | Select | Hide / Show | **Hide** | value/category label at each point |

> Custom values per REQ-UI-OPT-01. Overlaps `point_map`'s Event-coordinate mode, but this is a
> dedicated event layer (per-event points + heat/cluster), not OU-aggregated bubbles.

## Provenance & feasibility

- **Source:** DHIS2 Maps ("Event layer"); Superset deck.gl scatter/screengrid (heat).
- **Equivalent in:** DHIS2 *Event* (points/heat/cluster) · Superset *deck.gl Scatterplot/Screen Grid*.
- **Rendering:** Leaflet + `leaflet.heat` (heat) + cluster from `point_map.py`.
- **Difficulty / priority:** Medium · Medium–High (rich tracker analysis; much infra already exists).
- **Notes:** Reuse `point_map` event-coordinate fetch (`analytics/events/query?coordinatesOnly=true`)
  and the spiderfy/cluster logic; add a heat render mode.

## Acceptance (to create on implementation)

- Unit: `tests/test_preview.py` (`TestEventMap`) + CLAUDE.md map debug-log protocol.
- E2E: `tests/e2e/test_map_options.py`.
- REQ ids: REQ-MAP-EVT-RENDER-01, REQ-MAP-EVT-MODE-01, REQ-MAP-EVT-COORD-01, REQ-MAP-EVT-COLOR-01, REQ-MAP-EVT-DIM-01.
