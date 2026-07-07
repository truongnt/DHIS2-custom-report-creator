# Facility map (`facility_map`)

> Plugin: `charts/plugins/facility_map.py` (proposed). Common controls: [COMMON.md](COMMON.md).
> Leaflet markers at org-unit point locations (facilities) — icon/label markers, **no metric value**.
> Maps do **not** use the categorical COMMON options — full option set below.

## Data controls

| Control | Value |
|---|---|
| Metric | none (this layer shows locations, not values) |
| Dimension | optional — color/icon markers by an org-unit group |
| Time grain | none |

## Options

| key | type | choices | default | behavior |
|---|---|---|---|---|
| `ou_level` | Select | Level 2 / 3 / 4 / 5 | **Level 4** | OU level whose point features are shown (facilities) |
| `base_map` | Select | CartoDB Light / OpenStreetMap / CartoDB Dark / Satellite / None | CartoDB Light | Leaflet tile layer |
| `overlay_levels` | CheckboxGroup | Level 2 / 3 / 4 / 5 | (Level 2) | boundary context lines |
| `marker_style` | Select | Pin / Circle / Icon | **Pin** | marker glyph |
| `marker_color` | Select | Blue / Red / Green / Orange / Purple *(or #hex)* | **Blue** | marker color |
| `show_labels` | Select | Hide / Show | **Hide** | org-unit name beside each marker |
| `cluster` | Select | Off / On | **On** | cluster dense markers (reuse point_map screen-grid clustering) |

> Custom value: `marker_color` accepts a #hex (REQ-UI-OPT-01). No `color_scheme`/value ramp (no metric).

## Provenance & feasibility

- **Source:** DHIS2 Maps ("Facility layer").
- **Equivalent in:** DHIS2 *Facility* (icon markers at facilities).
- **Rendering:** Leaflet markers — reuse loader/overlay/cluster from `point_map.py`.
- **Difficulty / priority:** Medium · Medium (reuses existing map infra; value-less variant of bubble map).
- **Notes:** Distinct from `point_map` (which sizes by value). Source = `geoFeatures` points only.

## Acceptance (to create on implementation)

- Unit: `tests/test_preview.py` (`TestFacilityMap`) + brace/URL checks per CLAUDE.md map protocol.
- E2E: `tests/e2e/test_render_map.py` / `test_map_options.py`.
- REQ ids: REQ-MAP-FAC-RENDER-01, REQ-MAP-FAC-OULEVEL-01, REQ-MAP-FAC-MARKER-01, REQ-MAP-FAC-CLUSTER-01, REQ-MAP-FAC-LABELS-01.
