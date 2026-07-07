# Tracked entity map (`te_map`)

> Plugin: `charts/plugins/te_map.py` (proposed). Common controls: [COMMON.md](COMMON.md).
> Tracked entity instances (e.g. patients/households) plotted at their geometry, optionally
> styled by a tracked-entity attribute. Maps do **not** use the categorical COMMON options.

## Data controls

| Control | Value |
|---|---|
| Metric | none (each TEI is one marker) |
| Dimension | optional — color markers by a tracked-entity attribute (option set) |
| Time grain | none (enrollment/period filter applies) |

## Options

| key | type | choices | default | behavior |
|---|---|---|---|---|
| `base_map` | Select | CartoDB Light / OpenStreetMap / CartoDB Dark / Satellite / None | CartoDB Light | tile layer |
| `overlay_levels` | CheckboxGroup | Level 2 / 3 / 4 / 5 | (Level 2) | boundary context lines |
| `marker_color` | Select | Blue / Red / Green / Orange / Purple *(or #hex)* | **Blue** | marker color (when no dimension) |
| `marker_style` | Select | Pin / Circle | **Circle** | marker glyph |
| `cluster` | Select | Off / On | **On** | cluster dense markers |
| `show_labels` | Select | Hide / Show | **Hide** | attribute label at each marker |

> Custom value: `marker_color` accepts #hex. Requires a program with TEI geometry/coordinate field.

## Provenance & feasibility

- **Source:** DHIS2 Maps ("Tracked entity layer").
- **Equivalent in:** DHIS2 *Tracked entity*.
- **Rendering:** Leaflet — fetch `tracker/trackedEntities` with geometry; reuse map loader/cluster.
- **Difficulty / priority:** Medium · Low–Medium (depends on TEIs having coordinates; many don't).
- **Notes:** Closely related to `event_map`; share the marker/cluster code. New data source = trackedEntities.

## Acceptance (to create on implementation)

- Unit: `tests/test_preview.py` (`TestTeMap`) + CLAUDE.md map debug-log protocol.
- E2E: `tests/e2e/test_map_options.py`.
- REQ ids: REQ-MAP-TE-RENDER-01, REQ-MAP-TE-COLOR-01, REQ-MAP-TE-CLUSTER-01, REQ-MAP-TE-DIM-01.
