# Earth Engine map (`earth_engine_map`)

> Plugin: `charts/plugins/earth_engine_map.py` (proposed). Common controls: [COMMON.md](COMMON.md).
> Google Earth Engine raster layer (population, elevation, land cover…) optionally aggregated to org units.
> Maps do **not** use the categorical COMMON options.

## Data controls

| Control | Value |
|---|---|
| Metric | none (the GEE dataset is the value) |
| Dimension | none |
| Time grain | dataset-dependent (some GEE layers are time-indexed) |

## Options

| key | type | choices | default | behavior |
|---|---|---|---|---|
| `dataset` | Select | Population / Elevation / Land cover / Precipitation / Night lights | **Population** | which GEE collection to render |
| `base_map` | Select | CartoDB Light / OpenStreetMap / Satellite / None | Satellite | tile layer |
| `aggregation` | Select | None / Sum per OU / Mean per OU | **None** | aggregate raster into org-unit values |
| `opacity` | Select | 0.4 / 0.6 / 0.8 *(or 0–1)* | **0.6** | raster layer opacity |
| `color_scheme` | Select | dataset default / Blues / Greens / Reds | **dataset default** | raster color ramp |

## Provenance & feasibility

- **Source:** DHIS2 Maps ("Google Earth Engine layer").
- **Equivalent in:** DHIS2 *Earth Engine* (no Superset equivalent).
- **Rendering:** requires a **Google Earth Engine token/service account** + the DHIS2 GEE proxy,
  plus Leaflet raster tiles. No offline preview possible.
- **Difficulty / priority:** High · **Likely out-of-scope** — external auth + raster pipeline the
  app doesn't have; documented here for completeness per the comprehensive scope.
- **Notes:** If pursued, depends on DHIS2 server GEE configuration; cannot be rendered from fixtures.

## Acceptance (to create on implementation)

- Manual only (live DHIS2 with GEE configured) — no offline fixture/E2E possible.
- REQ ids: REQ-MAP-EE-RENDER-01, REQ-MAP-EE-DATASET-01, REQ-MAP-EE-AGG-01, REQ-MAP-EE-OPACITY-01.
