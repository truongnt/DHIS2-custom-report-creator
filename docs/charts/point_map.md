# Point Map (`point_map`)

> Plugin: `charts/plugins/point_map.py`. Common controls: [COMMON.md](COMMON.md).
> Bubbles at org-unit locations, sized by metric value (Leaflet).
> Manual acceptance criteria & debug-log checks: [../../CLAUDE.md](../../CLAUDE.md) (Point Map tables).

## Data controls

| Control | Value |
|---|---|
| Metric | 1 DE (`max_count=1`, **required**); types: aggregate / indicator / tracker_numeric / tracker_option; agg picker shown |
| Dimension | optional — `tracker_option` DE/PA → one bubble per event coloured by its value (e.g. PF vs PV) |
| Time grain | enabled (default Monthly) |

## Options

| key | type | choices | default | behavior |
|---|---|---|---|---|
| `coordinates` | Select | Org Unit / Event | **Org Unit** | Org Unit = OU centroids (static); Event = each event's own lat/lon (tracker only) |
| `ou_level` | Select | Level 2 / 3 / 4 / 5 | **Level 4** | OU level whose points are plotted (note: default is deeper than area map) |
| `base_map` | Select | CartoDB Light / OpenStreetMap / CartoDB Dark / Satellite / None | CartoDB Light | Leaflet tile layer |
| `overlay_levels` | CheckboxGroup | Level 2 / 3 / 4 / 5 | **Level 2** | border layers drawn behind bubbles (default shows province borders) |
| `show_empty` | Select | Hide / Show | Hide | whether OUs with no value get a bubble |
| `border_color` | Select | Auto / White / Black / Grey / Red / Blue | Auto | bubble border color |
| `border_weight` | Select | Thin / Normal / Thick | Normal | bubble border width |
| `point_scale` | Select | Small / Medium / Large | Medium | max bubble radius (`MAX_R`) — Small < Medium < Large |
| `point_color` | Select | Blue / Red / Green / Orange / Purple | Blue | flat bubble fill (when not gradient) |
| `bubble_gradient` | Select | None / Gradient | None | Gradient = bubble color varies light→dark by value (`USE_GRADIENT`) |
| `show_values` | Select | Hide / Show | Hide | value number inside/beside bubble (`L.divIcon`) |

## Behaviors (not options)

- **Clustering + zoom-split** (Event coords): nearby events merge in screen space (~44px grid)
  and re-cluster on `zoomend`; near max zoom, coincident events **spiderfy** (fan into a ring)
  so each becomes an individual point. OU coords stay static (cannot split).
- **Tracker Capture deep-link**: when a bubble is a single event (or a spiderfied leaf),
  clicking it opens a popup with **"Open in Tracker Capture ↗"** →
  `dhis-web-tracker-capture/index.html#/dashboard?tei=…&program=…&ou=…`. Root resolved at
  runtime from `document.baseURI` (srcdoc-safe; same base `dhis2Get`'s `../` uses). The link
  opens a **new tab via the top window** (`window.top.open`) because deployed reports run in a
  sandboxed `srcdoc` iframe that blocks a bare `target=_blank`. Only shown when the event row
  carries a `tei` (offline fixtures have none).
- **Tooltip**: coordinate (event mode) → name → `metric/category: value`.

## Acceptance

- **REQ-MAP-PM-01** — E2E render: bubbles drawn at point locations, sized by value
  (`tests/e2e/test_render_map.py::test_point_map_renders_bubbles`, screenshot evidence).
- **REQ-MAP-PM-OVERLAY-01** — E2E render: `overlay_levels` draws administrative border lines
  (`tests/e2e/test_render_map.py::test_point_map_overlay_borders`).
  > Note: overlay layers must be added **after** the map view is set, else Leaflet throws
  > `_clipPoints` and the borders silently disappear; `overlay_levels` accepts a list or a
  > comma-string.
- **REQ-MAP-PM-CAPTURE-01/02** — event bubbles deep-link a single event into the Capture app
  (popup); OU-centroid bubbles carry no `tei` so no link. Unit: `tests/test_preview.py::TestBubbleMapCaptureLink`.
- Unit: `tests/test_preview.py` (`TestPointMapOptions`, `TestBubbleMapCaptureLink`,
  `test_bubble_map_event_clusters_ou_does_not`, `test_bubble_map_event_spiderfies_coincident_points`)
- Manual: CLAUDE.md "Point Map — option-by-option acceptance criteria" + `geoRaw:` debug log lines
