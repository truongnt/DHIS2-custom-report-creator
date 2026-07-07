"""
PointMapPlugin — bubble map: circles at org unit locations sized by metric value.

Real data flow:
  1. Fetch /api/geoFeatures?ou=ou:{ou};LEVEL-{n} → point coordinates (ty=1)
  2. Fetch /api/analytics.json or analytics/events/aggregate → values per OU
  3. Join by OU id, draw Leaflet CircleMarker sized ∝ sqrt(value)

Options:
  - OU level (Level 2–5)
  - Base map tile (CartoDB Light/Dark, OSM, Satellite, None)
  - Boundary overlay (show level borders as context lines)
  - Bubble size (Small/Medium/Large max-radius)
  - Bubble color (fixed color or value gradient)
  - Show value labels on bubbles

Sample data: static SVG demo — no network needed.
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import (
    ChartPlugin,
    CheckboxGroupControl,
    DimensionControl,
    MetricControl,
    SelectControl,
    TimeGrainControl,
)

# Demo SVG: rough Laos outline + scattered circles
_DEMO_SVG = """\
<svg viewBox="0 0 180 260" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:calc(100% - 24px);max-height:240px">
  <rect x="40" y="10" width="100" height="235" rx="8" fill="#f0f4f8"/>
  <circle cx="90"  cy="50"  r="12" fill="#3182bd" opacity="0.7"/>
  <circle cx="70"  cy="90"  r="8"  fill="#3182bd" opacity="0.7"/>
  <circle cx="110" cy="80"  r="16" fill="#3182bd" opacity="0.7"/>
  <circle cx="85"  cy="130" r="6"  fill="#3182bd" opacity="0.7"/>
  <circle cx="100" cy="155" r="10" fill="#3182bd" opacity="0.7"/>
  <circle cx="75"  cy="170" r="18" fill="#3182bd" opacity="0.7"/>
  <circle cx="95"  cy="200" r="9"  fill="#3182bd" opacity="0.7"/>
  <circle cx="115" cy="185" r="5"  fill="#3182bd" opacity="0.7"/>
  <text x="90" y="252" text-anchor="middle" font-size="9" fill="#888"
        font-family="sans-serif">Sample — connect to see real data</text>
</svg>"""

_SCALE_FACTORS = {"Small": 20, "Medium": 35, "Large": 55}

# Color hex values for fixed-color mode
_COLOR_HEX = {
    "Blue": "#3182bd", "Red": "#e74c3c", "Green": "#27ae60",
    "Orange": "#f39c12", "Purple": "#8e44ad",
}

# [low_rgb, high_rgb] for gradient mode per color
_GRADIENTS = {
    "Blue":   [[198, 219, 239], [8,  48,  107]],
    "Red":    [[254, 224, 210], [165, 15,   21]],
    "Green":  [[229, 245, 224], [0,  109,   44]],
    "Orange": [[254, 237, 222], [127,  39,    4]],
    "Purple": [[242, 240, 247], [63,    0,  125]],
}

# Leaflet tile layer URL templates
_TILE_URLS: dict[str, str] = {
    "CartoDB Light": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "CartoDB Dark":  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "OpenStreetMap": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Satellite":     "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
}

# Available overlay level choices (checkboxes)
_ALL_OVERLAY_CHOICES = ("Level 2", "Level 3", "Level 4", "Level 5")

# Overlay border color options (null = Auto = adapts to basemap)
_BORDER_COLORS = {
    "White":  "#ffffff",
    "Black":  "#111111",
    "Grey":   "#666666",
    "Red":    "#cc3322",
    "Blue":   "#1155aa",
}
_BORDER_WEIGHTS = {"Thin": 0.8, "Normal": 1.5, "Thick": 2.5}


def _po(po: dict, key: str, default: str) -> str:
    return po.get(key, default) or default


def _leaflet_loader() -> str:
    return """\
      if (!window._leafletLoad) {
        window._leafletLoad = new Promise((res, rej) => {
          if (window.L) { res(); return; }
          const link = document.createElement('link');
          link.rel = 'stylesheet';
          link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
          document.head.appendChild(link);
          const s = document.createElement('script');
          s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
          s.onload = res; s.onerror = rej;
          document.head.appendChild(s);
        });
      }"""


class PointMapPlugin(ChartPlugin):
    id          = "point_map"
    label       = "Bubble Map"
    icon        = "📍"
    description = "Bubble map: proportional symbols at org unit locations, sized by metric value."
    preview_id  = "point_map"

    metrics = [
        MetricControl(
            id="metric",
            label="Metric",
            max_count=1,
            allowed_types=("aggregate", "indicator", "tracker_numeric", "tracker_option"),
            default_agg="SUM",
            show_agg_picker=True,
            required=True,
        )
    ]
    dimensions = [
        DimensionControl(
            id="dimension",
            label="Color by (category)",
            allowed_types=("tracker_option",),
            required=False,
            hint="Option-set DE/PA: one bubble per event, coloured by its value (e.g. PF vs PV)",
        )
    ]
    options = [
        SelectControl("coordinates",      "Coordinates",
                      ("Org Unit", "Event"), "Org Unit"),
        SelectControl("ou_level",         "OU level",
                      ("Level 2", "Level 3", "Level 4", "Level 5"), "Level 4"),
        SelectControl("base_map",         "Base map",
                      ("CartoDB Light", "OpenStreetMap", "CartoDB Dark", "Satellite", "None"),
                      "CartoDB Light"),
        CheckboxGroupControl("overlay_levels", "Overlay borders",
                             _ALL_OVERLAY_CHOICES, ("Level 2",)),
        SelectControl("show_empty",       "Empty OUs",
                      ("Hide", "Show"), "Hide"),
        SelectControl("border_color",     "Border color",
                      ("Auto", "White", "Black", "Grey", "Red", "Blue"), "Auto"),
        SelectControl("border_weight",    "Border width",
                      ("Thin", "Normal", "Thick"), "Normal"),
        SelectControl("point_scale",      "Bubble size",
                      ("Small", "Medium", "Large"), "Medium"),
        SelectControl("point_color",      "Bubble color",
                      ("Blue", "Red", "Green", "Orange", "Purple"), "Blue"),
        SelectControl("bubble_gradient",  "Color by value",
                      ("None", "Gradient"), "None"),
        SelectControl("show_values",      "Show values",
                      ("Hide", "Show"), "Hide"),
    ]
    time_grain = TimeGrainControl()

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        metrics = config.get("metrics") or []
        if not metrics:
            return _error_js(n, "Point Map: no metric configured.")

        m         = metrics[0]
        de_uid    = m.get("uid", "")
        de_type   = m.get("type", "aggregate")
        agg       = m.get("agg", "SUM")
        metric_label_js = _json.dumps(m.get("name") or "Value")
        prog_uid  = m.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
        stage_uid = m.get("stage_uid", "") or (config.get("source") or {}).get("stage_uid", "")
        prog_uid_js = _json.dumps(prog_uid)

        po              = config.get("plugin_options") or {}
        ou_level_str    = _po(po, "ou_level", "Level 4")
        level_num       = int(ou_level_str.split()[-1])
        point_scale     = _po(po, "point_scale", "Medium")
        point_color     = _po(po, "point_color", "Blue")
        base_map        = _po(po, "base_map", "CartoDB Light")
        ov_raw            = po.get("overlay_levels", "Level 2")
        use_gradient      = _po(po, "bubble_gradient", "None") == "Gradient"
        show_values       = _po(po, "show_values", "Hide") == "Show"
        hide_empty        = _po(po, "show_empty", "Hide") == "Hide"
        border_color_val  = _po(po, "border_color", "Auto")
        border_weight_val = _po(po, "border_weight", "Normal")

        # Presets OR custom values: a numeric point_scale = max radius in px; a #hex
        # point_color is used directly (REQ-UI-OPT-01 custom option values).
        max_radius      = (int(point_scale) if str(point_scale).strip().isdigit()
                           else _SCALE_FACTORS.get(point_scale, 35))
        color_hex       = (point_color if str(point_color).startswith("#")
                           else _COLOR_HEX.get(point_color, "#3182bd"))
        gradient_js     = _json.dumps(_GRADIENTS.get(point_color, _GRADIENTS["Blue"]))
        use_gradient_js  = "true" if use_gradient else "false"
        show_values_js   = "true" if show_values else "false"
        hide_empty_js    = "true" if hide_empty else "false"
        border_color_js  = "null" if border_color_val == "Auto" else f'"{_BORDER_COLORS.get(border_color_val, "#666")}"'
        border_weight_js = str(_BORDER_WEIGHTS.get(border_weight_val, 1.5))
        extra            = cls._extra_params(config)

        # Base tile layer
        tile_url = _TILE_URLS.get(base_map, "")
        is_dark  = base_map in ("CartoDB Dark", "Satellite")
        dark_js  = "true" if is_dark else "false"
        if tile_url:
            tile_js = f"L.tileLayer('{tile_url}', {{attribution:'', opacity:0.6}}).addTo(map);"
        else:
            tile_js = ""

        # Overlay boundary levels (parsed from comma-separated checkbox values)
        # Accept either a comma-string ("Level 2,Level 3") from the UI or a list/tuple
        # (["Level 2"]) from programmatic/AI configs — both must yield borders.
        ov_items = ov_raw if isinstance(ov_raw, (list, tuple)) else str(ov_raw).split(",")
        overlay_levels: list[int] = []
        for v in ov_items:
            v = str(v).strip()
            if v.startswith("Level ") and v[6:].isdigit():
                overlay_levels.append(int(v[6:]))
        ov_levels_json = _json.dumps(overlay_levels)
        ov_fetch_str   = "".join(
            f",\n                dhis2Get('api/geoFeatures?ou=ou:'+ou+';LEVEL-{lvl}&displayProperty=NAME&pr=false')"
            for lvl in overlay_levels
        )

        # Analytics URL
        if de_type in ("aggregate", "indicator"):
            analytics_url = (
                f"api/analytics.json"
                f"?dimension=dx:{de_uid}"
                f"&dimension=ou:'+ou+';LEVEL-{level_num}"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'"
                f"&displayProperty=NAME{extra}"
            )
        elif de_type == "tracker_option":
            # Event COUNT per OU — no aggregationType without a value= (DHIS2 E7204).
            analytics_url = (
                f"api/analytics/events/aggregate/{prog_uid}"
                f"?stage={stage_uid}&dimension={stage_uid}.{de_uid}"
                f"&dimension=ou:'+ou+';LEVEL-{level_num}"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'{extra}"
            )
        else:
            analytics_url = (
                f"api/analytics/events/aggregate/{prog_uid}"
                f"?stage={stage_uid}&value={de_uid}&aggregationType={agg}"
                f"&dimension=ou:'+ou+';LEVEL-{level_num}"
                f"&dimension=pe:'+encodeURIComponent(rpe)+'{extra}"
            )

        geo_url = f"api/geoFeatures?ou=ou:'+ou+';LEVEL-{level_num}&displayProperty=NAME&pr=false"

        # Coordinate source: OU centroids (geoFeatures) or each EVENT's own lon/lat.
        # Event coordinates only apply to tracker sources.
        coord_mode = _po(po, "coordinates", "Org Unit")
        if de_type in ("aggregate", "indicator"):
            coord_mode = "Org Unit"
        coord_mode_js = "true" if coord_mode == "Event" else "false"
        ev_val_js = "parseFloat(r[deI])||0" if de_type == "tracker_numeric" else "1"
        # A count metric (tracker_option) has value 1 per event → uniform bubble size.
        ev_uniform_js = "false" if de_type in ("tracker_numeric", "aggregate", "indicator") else "true"
        events_url = (
            f"api/analytics/events/query/{prog_uid}?stage={stage_uid}"
            f"&dimension={stage_uid}.{de_uid}"
            f"&dimension=pe:'+encodeURIComponent(rpe)+'"
            f"&dimension=ou:'+ou+'"
            f"&coordinatesOnly=true&paging=false{extra}"
        )

        # Colour-by-category dimension → one bubble per EVENT coloured by its option value.
        dim_de   = (config.get("dimensions") or {}).get("dimension") or {}
        has_dim  = bool(dim_de.get("uid"))
        dim_uid  = dim_de.get("uid", "")
        dim_stg  = dim_de.get("stage_uid", "") or stage_uid
        dim_opts_js = _json.dumps(dim_de.get("options", []))
        dim_token = dim_uid if dim_de.get("is_tea") else f"{dim_stg}.{dim_uid}"
        # Bubble SIZE still follows the metric: include the metric DE column when it's a
        # numeric value distinct from the colour dimension; otherwise size = event count.
        size_by_value = de_type == "tracker_numeric"
        size_by_value_js = "true" if size_by_value else "false"
        metric_dim = (f"&dimension={stage_uid}.{de_uid}"
                      if size_by_value and de_uid and de_uid != dim_uid else "")
        dim_val_js = ("(valI>=0?parseFloat(r[valI])||0:0)" if size_by_value else "1")
        dim_events_url = (
            f"api/analytics/events/query/{prog_uid}?stage={stage_uid}"
            f"&dimension={dim_token}{metric_dim}"
            f"&dimension=pe:'+encodeURIComponent(rpe)+'"
            f"&dimension=ou:'+ou+'"
            f"&coordinatesOnly=true&paging=false{extra}"
        )
        has_dim_js = "true" if has_dim else "false"

        return f"""\
        // ── PointMap card {n} ─────────────────────────────────────────────────
        (function() {{
          {_leaflet_loader()}

          const MAX_R{n}         = {max_radius};
          const COLOR{n}         = '{color_hex}';
          const DARK_MAP{n}      = {dark_js};
          const USE_GRADIENT{n}  = {use_gradient_js};
          const GRADIENT{n}      = {gradient_js};
          const SHOW_VALUES{n}   = {show_values_js};
          const HIDE_EMPTY{n}    = {hide_empty_js};
          const OV_LEVELS{n}     = {ov_levels_json};
          const BORDER_COLOR{n}  = {border_color_js};
          const BORDER_WEIGHT{n} = {border_weight_js};
          const EVENT_COORDS{n}  = {coord_mode_js};
          const METRIC_LABEL{n}  = {metric_label_js};
          const HAS_DIM{n}       = {has_dim_js};
          const DIM_OPTIONS{n}   = {dim_opts_js};
          const CAT_PALETTE{n}   = ["#e74c3c","#3498db","#f39c12","#27ae60","#9b59b6","#1abc9c","#e67e22","#2980b9"];
          // DHIS2 root (same base dhis2Get's '../' resolves against) → Capture deep-link.
          // Use document.baseURI, NOT window.location: deployed reports run inside an
          // about:srcdoc iframe where window.location.href is 'about:srcdoc' (an invalid
          // URL base → 'new URL' throws and aborts the whole card). In a srcdoc document
          // baseURI falls back to the parent DHIS2 page, matching dhis2Get's fetch base.
          let CAPTURE_ROOT{n} = '';
          try {{ CAPTURE_ROOT{n} = new URL('../', document.baseURI).href; }} catch(_e) {{ CAPTURE_ROOT{n} = ''; }}
          const PROGRAM_UID{n}   = {prog_uid_js};
          // Deep-link into the (legacy) Tracker Capture app's TEI dashboard:
          //   .../dhis-web-tracker-capture/index.html#/dashboard?tei=..&program=..&ou=..
          function _captureUrl{n}(ev) {{
            if (!ev || !ev.tei || !CAPTURE_ROOT{n}) return '';
            const q = 'tei=' + ev.tei + '&program=' + PROGRAM_UID{n}
              + (ev.ou ? '&ou=' + ev.ou : '');
            return CAPTURE_ROOT{n} + 'dhis-web-tracker-capture/index.html#/dashboard?' + q;
          }}

          function _bubbleColor{n}(v, maxVal) {{
            if (!USE_GRADIENT{n} || maxVal <= 0 || v <= 0) return v > 0 ? COLOR{n} : '#aaa';
            const t = Math.min(1, v / maxVal);
            const [fr, to] = GRADIENT{n};
            const lerp = (a, b) => Math.round(a + (b - a) * t);
            return 'rgb(' + lerp(fr[0],to[0]) + ',' + lerp(fr[1],to[1]) + ',' + lerp(fr[2],to[2]) + ')';
          }}

          function _mapDiv{n}(cardBody) {{
            // Reload (e.g. applying a filter) re-runs init → destroy any prior Leaflet map
            // and recreate a FRESH container, else Leaflet throws "already initialized".
            let old = document.getElementById('mapPt{n}');
            if (old) {{
              if (old._leafletMap) {{ try {{ old._leafletMap.remove(); }} catch(e) {{}} }}
              old.remove();
            }}
            const d = document.createElement('div');
            d.id = 'mapPt{n}';
            d.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;border-radius:4px;overflow:hidden;';
            cardBody.appendChild(d);
            return d;
          }}

          // Empty result (e.g. a filter excludes everything): tear down any prior map and
          // show a plain "No data" message instead of a red "Map error" / unhandled throw.
          function _emptyMap{n}(msg) {{
            const old = document.getElementById('mapPt{n}');
            if (old) {{ if (old._leafletMap) {{ try {{ old._leafletMap.remove(); }} catch(e) {{}} }} old.remove(); }}
            const errEl = document.getElementById('error{n}');
            if (errEl) {{ errEl.textContent = msg; errEl.style.display = 'block'; }}
            const ld = document.getElementById('loading{n}'); if (ld) ld.style.display = 'none';
          }}

          function _borderLayer{n}(geoRaw, level) {{
            const color  = BORDER_COLOR{n} || (DARK_MAP{n} ? '#ccc' : '#444');
            const feats  = (Array.isArray(geoRaw) ? geoRaw : [])
              .filter(f => f.ty == 2 || f.ty == 6)
              .map(f => {{
                let co;
                try {{ co = typeof f.co === 'string' ? JSON.parse(f.co) : f.co; }} catch(_) {{ return null; }}
                if (!Array.isArray(co) || !co.length) return null;
                let el = co, d = 0;
                while (Array.isArray(el) && el.length) {{ d++; el = el[0]; }}
                const need = d >= 4 ? 4 : 3;
                let coords = co, dd = d;
                while (dd < need) {{ coords = [coords]; dd++; }}
                return {{ type:'Feature', properties:{{}},
                          geometry:{{ type:need===4?'MultiPolygon':'Polygon', coordinates:coords }} }};
              }}).filter(Boolean);
            if (window._dbg) window._dbg('PointMap{n} borderLayer' + level + ': ' + feats.length + ' polys from ' + (Array.isArray(geoRaw)?geoRaw.length:0));
            return feats.length
              ? L.geoJSON({{ type:'FeatureCollection', features:feats }},
                  {{ style:{{ fill:false, color:color, weight:BORDER_WEIGHT{n}, opacity:0.8, dashArray:'4 3' }} }})
              : null;
          }}

          // Build points from OU centroids (geoFeatures) + aggregated values, then draw.
          async function renderChart{n}Real(cardBody, geoRaw, analytics, ovGeos) {{
            const h      = analytics.headers || [];
            const ouIdx  = h.findIndex(x => x.name === 'ou');
            const valIdx = h.findIndex(x => x.name === 'value');
            if (ouIdx < 0 || valIdx < 0) {{
              throw new Error('No ou/value columns in analytics response');
            }}
            const byOu = {{}};
            for (const row of (analytics.rows || [])) {{
              const id = row[ouIdx], v = parseFloat(row[valIdx]) || 0;
              byOu[id] = (byOu[id] || 0) + v;
            }}
            // geoFeatures type 1 = point, co = "[lon,lat]" string
            const points = (Array.isArray(geoRaw) ? geoRaw : [])
              .filter(f => f.ty === 1 && f.co)
              .map(f => {{
                let coords;
                try {{ coords = typeof f.co === 'string' ? JSON.parse(f.co) : f.co; }} catch(_) {{ return null; }}
                if (!Array.isArray(coords) || coords.length < 2) return null;
                return {{ id:f.id, name:f.na, lon:coords[0], lat:coords[1],
                          value: byOu[f.id] ?? null }};
              }}).filter(Boolean);
            if (!points.length) {{ _emptyMap{n}('No data for the current selection.'); return; }}
            await renderPoints{n}(cardBody, points, ovGeos, {{}});   // OU centroids: no clustering
          }}

          // Draw bubbles for rawPoints[] = [{{name,lon,lat,value,cat?}}].
          // opts = {{ catInfo, eventBased, uniformSize, cluster }}.
          // cluster=true → events are grouped by on-screen proximity and RE-grouped on
          // zoom, so zooming in splits a merged bubble back into individual points.
          async function renderPoints{n}(cardBody, rawPoints, ovGeos, opts) {{
            opts = opts || {{}};
            const catInfo     = opts.catInfo || null;
            const eventBased  = !!opts.eventBased;
            const uniformSize = !!opts.uniformSize;
            const cluster     = !!opts.cluster;
            if (!rawPoints.length) {{ _emptyMap{n}('No data for the current selection.'); return; }}

            await window._leafletLoad;
            const mapDiv = _mapDiv{n}(cardBody);
            const map = L.map(mapDiv, {{ zoomControl:true, attributionControl:false, zoomSnap:0.5, maxZoom:19 }});
            mapDiv._leafletMap = map;   // tracked so a reload can destroy it (avoid re-init error)

            {tile_js}

            // Set the view BEFORE adding vector layers (Leaflet projects against it).
            const _ptBounds = rawPoints
              .filter(p => !(HIDE_EMPTY{n} && (p.value ?? 0) === 0))
              .map(p => [p.lat, p.lon]);
            if (_ptBounds.length) map.fitBounds(_ptBounds, {{ padding:[16,16] }});
            else map.setView([17.9, 102.6], 6);

            (ovGeos || []).forEach((geo, i) => {{
              const bl = _borderLayer{n}(geo, OV_LEVELS{n}[i]);
              if (bl) bl.addTo(map);
            }});

            const bubbleLayer = L.layerGroup().addTo(map);
            let legendMax = 1;
            // Many tracker events share the SAME coordinate (geocoded to the facility,
            // not per-event GPS), so zooming can never separate them. Once the user is
            // near max zoom we "spiderfy" coincident events — fan them out into a ring so
            // each event becomes its own individual, hoverable point.
            const SPIDER_ZOOM{n} = (map.getMaxZoom() || 19) - 2;

            // Grid clustering in SCREEN space at the given zoom (≈44 px cells). Re-run on
            // zoom → cells shrink in geo terms → fewer merges → bubbles split apart. Each
            // group keeps its member events so they can be spiderfied at high zoom.
            function _clusterAt(zoom) {{
              const cell = 44, groups = {{}};
              for (const p of rawPoints) {{
                const xy = map.project([p.lat, p.lon], zoom);
                const key = Math.floor(xy.x/cell) + '_' + Math.floor(xy.y/cell) + '|' + (p.cat || '');
                let g = groups[key];
                if (!g) g = groups[key] = {{ sx:0, sy:0, value:0, count:0, name:p.name, cat:p.cat, members:[] }};
                g.sx += xy.x; g.sy += xy.y; g.value += (p.value || 0); g.count += 1; g.members.push(p);
              }}
              return Object.values(groups).map(g => {{
                const ll = map.unproject([g.sx/g.count, g.sy/g.count], zoom);
                return {{ lat:ll.lat, lon:ll.lng, value:g.value, count:g.count,
                          name:g.name, cat:g.cat, members:g.members }};
              }});
            }}

            // Draw a single bubble (+ optional value label) for value v / category cat.
            // forceSmall = a spiderfied individual event (uniform small radius).
            // ev = the single underlying event ({{tei,pi,ou}}) → adds a click popup that
            // deep-links into the Capture app. Only set for a one-event bubble / leaf.
            function _drawOne(lat, lon, v, cat, name, maxVal, forceSmall, ev) {{
              if (HIDE_EMPTY{n} && (v || 0) === 0) return;
              const uni = forceSmall || uniformSize || (catInfo && !catInfo.sizeByValue);
              const r   = uni ? 6 : ((v || 0) > 0 ? Math.max(4, MAX_R{n} * Math.sqrt(v / maxVal)) : 4);
              const fmt = v == null ? 'No data'
                : v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toLocaleString();
              const label = catInfo ? catInfo.nameOf(cat) : METRIC_LABEL{n};
              let tip = '';
              if (eventBased) tip += '📍 ' + (+lat).toFixed(5) + ', ' + (+lon).toFixed(5) + '<br>';
              tip += '<b>' + (name || '(no name)') + '</b><br>' + label + ': ' + fmt;
              const mk = L.circleMarker([lat, lon], {{
                radius:r, fillColor: catInfo ? catInfo.colorOf(cat) : _bubbleColor{n}(v, maxVal),
                color:'#ffffff', weight:1, opacity:1, fillOpacity:0.85
              }}).bindTooltip(tip, {{ sticky:true }});
              // Clickable Capture deep-link (popup, since hover tooltips aren't clickable).
              const _url = (eventBased && ev) ? _captureUrl{n}(ev) : '';
              if (_url) {{
                mk.bindPopup(tip + '<br><a href="' + _url + '" target="_blank" rel="noopener noreferrer" '
                  + 'class="capLink{n}" style="color:#1a6fa8;font-weight:600;text-decoration:none;">'
                  + 'Open in Tracker Capture \\u2197</a>');
                // Deployed reports run in a (sandboxed) srcdoc iframe where a bare
                // target=_blank link is often blocked. The iframe is same-origin, so open
                // via the TOP window on click → reliably lands in a NEW browser tab.
                mk.on('popupopen', function(e) {{
                  const a = e.popup.getElement().querySelector('a.capLink{n}');
                  if (!a) return;
                  a.addEventListener('click', function(ev2) {{
                    ev2.preventDefault(); ev2.stopPropagation();
                    try {{ (window.top || window).open(_url, '_blank', 'noopener'); }}
                    catch(_e) {{ window.open(_url, '_blank', 'noopener'); }}
                  }});
                }});
              }}
              bubbleLayer.addLayer(mk);
              if (SHOW_VALUES{n} && (v || 0) > 0 && r >= 9) {{
                const fs = Math.max(8, Math.min(Math.round(r * 0.9), 15));
                bubbleLayer.addLayer(L.marker([lat, lon], {{ interactive:false,
                  icon: L.divIcon({{ className:'',
                    iconSize:[Math.ceil(r*2), fs+2], iconAnchor:[Math.ceil(r), (fs+2)/2],
                    html:'<div style="font:bold '+fs+'px sans-serif;color:#fff;text-align:center;'
                      + 'line-height:'+(fs+2)+'px;text-shadow:0 0 2px #000,0 0 2px #000;'
                      + 'white-space:nowrap;">'+fmt+'</div>' }})
                }}));
              }}
            }}

            // Fan a group of (near-)coincident events out around their centroid so each
            // event becomes an individual point with its own tooltip / coordinate.
            function _spiderfy(grp, zoom, maxVal) {{
              const c = map.project([grp.lat, grp.lon], zoom);
              const k = grp.members.length;
              grp.members.forEach((p, i) => {{
                let rad, ang;
                if (k <= 9) {{ ang = (i / k) * 2 * Math.PI; rad = 14 + (k > 4 ? 8 : 0); }}
                else        {{ ang = i * 0.7; rad = 12 + 7 * (ang / (2 * Math.PI)); }}  // spiral
                const ll = map.unproject(L.point(c.x + rad * Math.cos(ang),
                                                 c.y + rad * Math.sin(ang)), zoom);
                bubbleLayer.addLayer(L.polyline([[grp.lat, grp.lon], [ll.lat, ll.lng]],
                  {{ color:'#888', weight:1, opacity:0.45, interactive:false }}));
                _drawOne(ll.lat, ll.lng, (p.value ?? 0), p.cat, p.name, maxVal, true, p);
              }});
            }}

            function _draw() {{
              const zoom = map.getZoom();
              const pts  = cluster ? _clusterAt(zoom) : rawPoints;
              const spider = cluster && eventBased && zoom >= SPIDER_ZOOM{n};
              const vals = pts.map(p => p.value).filter(v => v != null && v > 0);
              const maxVal = vals.length ? Math.max(...vals) : 1;
              legendMax = maxVal;
              bubbleLayer.clearLayers();
              for (const pt of pts) {{
                if (spider && pt.members && pt.members.length > 1) {{
                  _spiderfy(pt, zoom, maxVal);
                }} else {{
                  // Single-event bubble → carry its identifiers so the popup can deep-link.
                  const ev = (pt.members && pt.members.length === 1) ? pt.members[0] : null;
                  _drawOne(pt.lat, pt.lon, (pt.value ?? 0), pt.cat, pt.name, maxVal, false, ev);
                }}
              }}
            }}

            _draw();
            if (cluster) map.on('zoomend', _draw);

            // ── Legend ──────────────────────────────────────────────────────
            const legend = L.control({{ position: 'bottomright' }});
            legend.onAdd = function() {{
              const div = L.DomUtil.create('div');
              div.style.cssText = 'background:rgba(255,255,255,0.9);padding:6px 9px;'
                + 'border-radius:4px;font:11px sans-serif;color:#333;line-height:1.4;'
                + 'box-shadow:0 1px 4px rgba(0,0,0,0.3);';
              const fmtV = x => x >= 1000 ? (x/1000).toFixed(1)+'k' : Math.round(x).toLocaleString();
              if (catInfo) {{
                let html = '<div style="font-weight:bold;margin-bottom:3px;">' + METRIC_LABEL{n} + '</div>';
                catInfo.cats.forEach(c => {{
                  html += '<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">'
                    + '<span style="width:11px;height:11px;border-radius:50%;background:'
                    + catInfo.colorOf(c) + ';border:1px solid #fff;"></span>'
                    + '<span>' + catInfo.nameOf(c) + '</span></div>';
                }});
                div.innerHTML = html;
                return div;
              }}
              const swatch = USE_GRADIENT{n}
                ? '<span style="display:inline-block;width:30px;height:9px;border-radius:2px;'
                  + 'background:linear-gradient(90deg,'+_bubbleColor{n}(0.01,1)+','+_bubbleColor{n}(1,1)+');"></span>'
                : '<span style="display:inline-block;width:11px;height:11px;border-radius:50%;'
                  + 'background:'+COLOR{n}+';vertical-align:middle;"></span>';
              function sizeRow(disp, val) {{
                const d = Math.max(6, Math.min(disp, 22));
                return '<div style="display:flex;align-items:center;gap:6px;margin-top:2px;">'
                  + '<span style="display:inline-flex;width:24px;justify-content:center;">'
                  + '<span style="width:'+d+'px;height:'+d+'px;border-radius:50%;background:'+COLOR{n}
                  + ';opacity:0.7;border:1px solid #fff;"></span></span>'
                  + '<span>' + fmtV(val) + '</span></div>';
              }}
              let html = '<div style="font-weight:bold;margin-bottom:3px;">' + METRIC_LABEL{n}
                + ' ' + swatch + '</div>';
              if (legendMax > 0) {{
                html += sizeRow(MAX_R{n}, legendMax);
                html += sizeRow(MAX_R{n} * Math.sqrt(0.25), legendMax * 0.25);
              }}
              div.innerHTML = html;
              return div;
            }};
            legend.addTo(map);

            document.getElementById('loading{n}').style.display = 'none';
          }}

          window.initChart{n} = async function(ou, pe) {{
            const cvs = document.getElementById('chart{n}');
            const cardBody = cvs.closest('.card-body') || cvs.parentElement;
            cvs.style.display = 'none';

            if (PREVIEW) {{
              const b = document.getElementById('demoBanner{n}');
              if (b) b.style.display = 'block';
              const demo = document.createElement('div');
              demo.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;';
              demo.innerHTML = '{_DEMO_SVG.replace(chr(10)," ").replace("'","\\'")}';
              cardBody.appendChild(demo);
              document.getElementById('loading{n}').style.display = 'none';
              return;
            }}

            document.getElementById('demoBanner{n}').style.display = 'none';
            const errEl = document.getElementById('error{n}');
            errEl.style.display = 'none';
            try {{
              const rpe = resolveRelativePeriod(pe);
              if (HAS_DIM{n}) {{
                // One bubble per EVENT at its coordinate, coloured by its category value.
                const _res = await Promise.all([
                  dhis2Get('{dim_events_url}'){ov_fetch_str}
                ]);
                const evd = _res[0];
                const ovGeos = _res.slice(1);
                const hh = evd.headers || [];
                const lonI = hh.findIndex(x => x.name === 'longitude');
                const latI = hh.findIndex(x => x.name === 'latitude');
                const ounI = hh.findIndex(x => x.name === 'ouname');
                const teiI = hh.findIndex(x => x.name === 'tei');
                const piI  = hh.findIndex(x => x.name === 'pi');
                const ouI  = hh.findIndex(x => x.name === 'ou');
                const catI = hh.findIndex(x => x.name === '{dim_stg}.{dim_uid}' || x.name === '{dim_uid}');
                const valI = hh.findIndex(x => x.name === '{stage_uid}.{de_uid}' || x.name === '{de_uid}');
                // Raw per-event points; renderPoints clusters them (by location AND category)
                // and re-clusters on zoom so they split apart when you zoom in.
                const points = (evd.rows || []).map(r => {{
                  const lon = parseFloat(r[lonI]), lat = parseFloat(r[latI]);
                  if (isNaN(lon) || isNaN(lat)) return null;
                  return {{ name:(ounI>=0?r[ounI]:''), lon, lat, value:({dim_val_js}),
                            cat:(catI>=0?r[catI]:''),
                            tei:(teiI>=0?r[teiI]:''), pi:(piI>=0?r[piI]:''), ou:(ouI>=0?r[ouI]:'') }};
                }}).filter(Boolean);
                if (!points.length) {{
                  _emptyMap{n}((evd.rows && evd.rows.length)
                    ? 'No located events for the current filter.' : 'No data for the current filter.');
                  return;
                }}
                // Category order: declared options first, then any extra values found.
                const fromData = [...new Set(points.map(p => p.cat))];
                const declared = DIM_OPTIONS{n}.map(o => o.code).filter(c => fromData.includes(c));
                const cats = declared.length ? declared.concat(fromData.filter(c => !declared.includes(c)))
                                             : fromData;
                const colorIdx = {{}}; cats.forEach((c,i) => colorIdx[c] = i);
                const nameMap = {{}}; DIM_OPTIONS{n}.forEach(o => nameMap[o.code] = o.name);
                const catInfo = {{
                  cats: cats,
                  sizeByValue: true,   // bubbles now carry an aggregate (count/sum) per location
                  colorOf: c => CAT_PALETTE{n}[(colorIdx[c]||0) % CAT_PALETTE{n}.length],
                  nameOf:  c => nameMap[c] || c || '(blank)',
                }};
                await renderPoints{n}(cardBody, points, ovGeos,
                  {{ catInfo:catInfo, eventBased:true, cluster:true }});
              }} else if (EVENT_COORDS{n}) {{
                // One bubble per EVENT at its own captured coordinate.
                const _res = await Promise.all([
                  dhis2Get('{events_url}'){ov_fetch_str}
                ]);
                const evd = _res[0];
                const ovGeos = _res.slice(1);
                const hh = evd.headers || [];
                const lonI = hh.findIndex(x => x.name === 'longitude');
                const latI = hh.findIndex(x => x.name === 'latitude');
                const ounI = hh.findIndex(x => x.name === 'ouname');
                const teiI = hh.findIndex(x => x.name === 'tei');
                const piI  = hh.findIndex(x => x.name === 'pi');
                const ouI  = hh.findIndex(x => x.name === 'ou');
                const deI  = hh.findIndex(x => x.name === '{stage_uid}.{de_uid}' || x.name === '{de_uid}');
                // Raw per-event points; renderPoints clusters by on-screen proximity and
                // re-clusters on zoom (zoom in → merged bubbles split into individual points).
                const points = (evd.rows || []).map(r => {{
                  const lon = parseFloat(r[lonI]), lat = parseFloat(r[latI]);
                  if (isNaN(lon) || isNaN(lat)) return null;
                  return {{ name:(ounI>=0?r[ounI]:''), lon, lat, value:({ev_val_js}),
                            tei:(teiI>=0?r[teiI]:''), pi:(piI>=0?r[piI]:''), ou:(ouI>=0?r[ouI]:'') }};
                }}).filter(Boolean);
                if (!points.length) {{
                  _emptyMap{n}((evd.rows && evd.rows.length)
                    ? 'Events have no captured location for the current filter.'
                    : 'No data for the current filter.');
                  return;
                }}
                await renderPoints{n}(cardBody, points, ovGeos, {{ eventBased:true, cluster:true }});
              }} else {{
                const _res = await Promise.all([
                  dhis2Get('{geo_url}'),
                  dhis2Get('{analytics_url}'){ov_fetch_str}
                ]);
                const geoRaw    = _res[0];
                const analytics = _res[1];
                const ovGeos    = _res.slice(2);
                await renderChart{n}Real(cardBody, geoRaw, analytics, ovGeos);
              }}
            }} catch(e) {{
              console.error('[PointMap{n}]', e);
              errEl.textContent = 'Map error: ' + (e.message || e);
              errEl.style.display = 'block';
              document.getElementById('loading{n}').style.display = 'none';
            }}
          }};

        }})();"""


def _error_js(n: int, msg: str) -> str:
    return f"""\
        window.initChart{n} = async function() {{
          document.getElementById('loading{n}').style.display = 'none';
          document.getElementById('error{n}').textContent = {_json.dumps(msg)};
          document.getElementById('error{n}').style.display = 'block';
        }};"""
