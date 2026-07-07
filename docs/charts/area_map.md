# Area Map (`area_map`)

> Plugin: `charts/plugins/area_map.py`. Common controls: [COMMON.md](COMMON.md).
> Choropleth: regions colored by metric value using DHIS2 org-unit boundaries (Leaflet).
> Maps do **not** use the categorical COMMON options — full option set below.
> Manual acceptance criteria & debug-log checks: [../../CLAUDE.md](../../CLAUDE.md) (Area Map tables).

## Data controls

| Control | Value |
|---|---|
| Metric | 1 DE (`max_count=1`, **required**); types: aggregate / indicator / tracker_numeric / tracker_option; agg picker shown |
| Dimension | none |
| Time grain | enabled (default Monthly) |

## Options

| key | type | choices | default | behavior |
|---|---|---|---|---|
| `ou_level` | Select | Level 2 / 3 / 4 / 5 | **Level 2** | OU level whose polygons are colored; drives `LEVEL-N` in geoFeatures + analytics URL |
| `base_map` | Select | CartoDB Light / OpenStreetMap / CartoDB Dark / Satellite / None | CartoDB Light | Leaflet tile layer (None = no tiles) |
| `overlay_levels` | CheckboxGroup | Level 2 / 3 / 4 / 5 | (none) | extra dashed border layers drawn over the choropleth |
| `border_color` | Select | Auto / White / Black / Grey / Red / Blue | Auto | polygon border color |
| `border_weight` | Select | Thin / Normal / Thick | Normal | polygon border width |
| `color_scheme` | Select | Blues / Greens / Reds / Oranges / Purples | **Blues** | sequential ramp (`_SCHEMES`) — *not* the categorical COMMON schemes |
| `show_labels` | Select | Hide / Show | Hide | value label on each polygon |

## Behaviors (not options)

- **Legend** (always on when there's data): bottom-right sequential color ramp from min→max
  using the selected `color_scheme`, captioned with the metric name.
- **Tooltip**: `<name>` → `metric: value (X% of total)` → `Rank N of M` (OUs ranked by value).

## Acceptance

- **REQ-MAP-AM-LEGEND-01** — color-ramp legend present. **REQ-MAP-AM-TOOLTIP-01** — tooltip shows
  metric name, % of total, rank. Unit: `tests/test_preview.py::TestAreaMapLegendTooltip`.
- Unit: `tests/test_preview.py` (`TestAreaMapOptions`, `TestAreaMapLegendTooltip`)
- Manual: CLAUDE.md "Area Map — option-by-option acceptance criteria" + `geoRaw:` debug log lines
