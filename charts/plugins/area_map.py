"""
AreaMapPlugin — choropleth map: org unit regions colored by metric value.

Real data flow:
  1. Fetch /api/geoFeatures?ou=ou:{ou};LEVEL-{n} → polygon boundaries
  2. Fetch /api/analytics.json (aggregate) or analytics/events/aggregate (tracker) → values per OU
  3. Join by OU id, color-fill via linear interpolation

Options:
  - Data level (Level 2–5)
  - Base map tile (CartoDB Light/Dark, OSM, Satellite, None)
  - Boundary overlay (show additional level borders as context lines)
  - Color scheme
  - Labels (permanent tooltips)

Sample data: static SVG demo — no network needed.
"""
from __future__ import annotations

import json as _json

from charts.plugins.base import (
    ChartPlugin,
    CheckboxGroupControl,
    MetricControl,
    SelectControl,
    TimeGrainControl,
)

# ── Color schemes: [from_rgb, to_rgb] ─────────────────────────────────────────
_SCHEMES: dict[str, list[list[int]]] = {
    "Blues":   [[222, 235, 247], [8,  48,  107]],
    "Greens":  [[229, 245, 224], [0,  109,  44]],
    "Reds":    [[254, 229, 217], [179,  0,    0]],
    "Oranges": [[254, 237, 222], [166, 54,    3]],
    "Purples": [[242, 240, 247], [84,  39,  143]],
}

# Leaflet tile layer URL templates
_TILE_URLS: dict[str, str] = {
    "CartoDB Light": "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "CartoDB Dark":  "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "OpenStreetMap": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "Satellite":     "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
}

# All available overlay level choices
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

# Demo SVG: rough Laos-shaped trapezoid split into fake provinces
_DEMO_SVG = """\
<svg viewBox="0 0 180 260" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;height:calc(100% - 24px);max-height:240px">
  <rect x="55" y="10"  width="65" height="45" rx="3" fill="#2171b5"/>
  <rect x="48" y="55"  width="55" height="40" rx="3" fill="#6baed6"/>
  <rect x="65" y="55"  width="50" height="40" rx="3" fill="#4292c6"/>
  <rect x="42" y="95"  width="60" height="38" rx="3" fill="#c6dbef"/>
  <rect x="62" y="95"  width="55" height="38" rx="3" fill="#9ecae1"/>
  <rect x="38" y="133" width="65" height="35" rx="3" fill="#deebf7"/>
  <rect x="58" y="133" width="55" height="35" rx="3" fill="#084594"/>
  <rect x="45" y="168" width="70" height="38" rx="3" fill="#2171b5"/>
  <rect x="50" y="206" width="60" height="38" rx="3" fill="#6baed6"/>
  <text x="90" y="252" text-anchor="middle" font-size="9" fill="#888"
        font-family="sans-serif">Sample — connect to see real data</text>
</svg>"""


def _po(po: dict, key: str, default: str) -> str:
    return po.get(key, default) or default


def _leaflet_loader() -> str:
    """JS snippet that loads Leaflet once per page, deduplicating concurrent calls."""
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


class AreaMapPlugin(ChartPlugin):
    id          = "area_map"
    label       = "Choropleth Map"
    icon        = "🗺️"
    description = "Choropleth: regions shaded by metric value using DHIS2 org unit boundaries."
    preview_id  = "area_map"

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
    options = [
        SelectControl("ou_level",          "Data level",
                      ("Level 2", "Level 3", "Level 4", "Level 5"), "Level 2"),
        SelectControl("base_map",          "Base map",
                      ("CartoDB Light", "OpenStreetMap", "CartoDB Dark", "Satellite", "None"),
                      "CartoDB Light"),
        CheckboxGroupControl("overlay_levels", "Overlay borders",
                             _ALL_OVERLAY_CHOICES, ()),
        SelectControl("border_color",      "Border color",
                      ("Auto", "White", "Black", "Grey", "Red", "Blue"), "Auto"),
        SelectControl("border_weight",     "Border width",
                      ("Thin", "Normal", "Thick"), "Normal"),
        SelectControl("color_scheme",      "Color scheme",
                      tuple(_SCHEMES.keys()), "Blues"),
        SelectControl("show_labels",       "Labels",
                      ("Hide", "Show"), "Hide"),
    ]
    time_grain = TimeGrainControl()

    @classmethod
    def build_js(cls, n: int, config: dict) -> str:
        metrics = config.get("metrics") or []
        if not metrics:
            return _error_js(n, "Area Map: no metric configured.")

        m         = metrics[0]
        de_uid    = m.get("uid", "")
        de_type   = m.get("type", "aggregate")
        agg       = m.get("agg", "SUM")
        metric_label_js = _json.dumps(m.get("name") or "Value")
        prog_uid  = m.get("prog_uid", "") or (config.get("source") or {}).get("prog_uid", "")
        stage_uid = m.get("stage_uid", "") or (config.get("source") or {}).get("stage_uid", "")

        po             = config.get("plugin_options") or {}
        ou_level_str   = _po(po, "ou_level", "Level 2")
        level_num      = int(ou_level_str.split()[-1])
        color_scheme      = _po(po, "color_scheme", "Blues")
        show_labels       = _po(po, "show_labels", "Hide") == "Show"
        base_map          = _po(po, "base_map", "CartoDB Light")
        ov_raw            = po.get("overlay_levels", "")  # comma-separated, e.g. "Level 2,Level 4"
        border_color_val  = _po(po, "border_color", "Auto")
        border_weight_val = _po(po, "border_weight", "Normal")

        scheme_js  = _json.dumps(_SCHEMES.get(color_scheme, _SCHEMES["Blues"]))
        label_js   = "true" if show_labels else "false"
        extra      = cls._extra_params(config)
        border_color_js  = "null" if border_color_val == "Auto" else f'"{_BORDER_COLORS.get(border_color_val, "#666")}"'
        border_weight_js = str(_BORDER_WEIGHTS.get(border_weight_val, 1.5))

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
            # Event COUNT per OU. NOTE: do NOT send aggregationType without a value=
            # (DHIS2 E7204 "Value dimension ... must be specified"). The DE dimension
            # makes events/aggregate return counts; the map sums them per OU.
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

        return f"""\
        // ── AreaMap card {n} ──────────────────────────────────────────────────
        (function() {{
          {_leaflet_loader()}

          const SCHEME{n}        = {scheme_js};
          const SHOW_LABELS{n}   = {label_js};
          const DARK_MAP{n}      = {dark_js};
          const OV_LEVELS{n}     = {ov_levels_json};
          const BORDER_COLOR{n}  = {border_color_js};
          const BORDER_WEIGHT{n} = {border_weight_js};
          const METRIC_LABEL{n}  = {metric_label_js};

          function _colorForVal{n}(val, minV, maxV) {{
            const t = maxV > minV ? (val - minV) / (maxV - minV) : 0.5;
            const c = Math.max(0, Math.min(1, t));
            const [fr, to] = SCHEME{n};
            const lerp = (a,b) => Math.round(a + (b - a) * c);
            return 'rgb(' + lerp(fr[0],to[0]) + ',' + lerp(fr[1],to[1]) + ',' + lerp(fr[2],to[2]) + ')';
          }}

          function _mapDiv{n}(cardBody) {{
            // Reload (e.g. applying a filter) re-runs init → destroy any prior Leaflet map
            // and recreate a FRESH container, else Leaflet throws "already initialized".
            let old = document.getElementById('mapArea{n}');
            if (old) {{
              if (old._leafletMap) {{ try {{ old._leafletMap.remove(); }} catch(e) {{}} }}
              old.remove();
            }}
            const d = document.createElement('div');
            d.id = 'mapArea{n}';
            d.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;border-radius:4px;overflow:hidden;';
            cardBody.appendChild(d);
            return d;
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
            if (window._dbg) window._dbg('AreaMap{n} borderLayer' + level + ': ' + feats.length + ' polys from ' + (Array.isArray(geoRaw)?geoRaw.length:0));
            return feats.length
              ? L.geoJSON({{ type:'FeatureCollection', features:feats }},
                  {{ style:{{ fill:false, color:color, weight:BORDER_WEIGHT{n}, opacity:0.8, dashArray:'4 3' }} }})
              : null;
          }}

          async function renderChart{n}Real(cardBody, geoRaw, analytics, ovGeos) {{
            if (window._dbg) {{
              const geo0 = Array.isArray(geoRaw) && geoRaw[0];
              window._dbg('AreaMap{n} geoRaw: count=' + (Array.isArray(geoRaw)?geoRaw.length:'NOT_ARRAY')
                + ' first_ty=' + (geo0?geo0.ty:'?'));
              const poly = Array.isArray(geoRaw) && geoRaw.find(f=>f.ty===2||f.ty===6);
              if (poly) {{
                const parsed = typeof poly.co==='string'?JSON.parse(poly.co):poly.co;
                const depth = (function d(a){{return Array.isArray(a)?1+d(a[0]):0;}})(parsed);
                window._dbg('AreaMap{n} poly ty=' + poly.ty + ' co_depth=' + depth);
              }}
              window._dbg('AreaMap{n} analytics: headers=' + JSON.stringify((analytics.headers||[]).map(h=>h.name))
                + ' rows=' + (analytics.rows||[]).length);
            }}

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
            const vals = Object.values(byOu);
            const minV = vals.length ? Math.min(...vals) : 0;
            const maxV = vals.length ? Math.max(...vals) : 1;
            const totalV = vals.reduce((s, x) => s + x, 0);
            // Rank OUs by value (1 = highest) for the tooltip.
            const _ranked = Object.entries(byOu).sort((a, b) => b[1] - a[1]);
            const rankOf = {{}};
            _ranked.forEach(([id], i) => {{ rankOf[id] = i + 1; }});
            const nOu = _ranked.length;

            const features = (Array.isArray(geoRaw) ? geoRaw : [])
              .filter(f => f.ty === 2 || f.ty === 6)
              .map(f => {{
                let co;
                try {{ co = typeof f.co === 'string' ? JSON.parse(f.co) : f.co; }} catch(_) {{ return null; }}
                if (!Array.isArray(co) || !co.length) return null;
                let el = co, depth = 0;
                while (Array.isArray(el) && el.length) {{ depth++; el = el[0]; }}
                const need = depth >= 4 ? 4 : 3;
                let coords = co;
                while (depth < need) {{ coords = [coords]; depth++; }}
                return {{ type:'Feature',
                          properties:{{ id:f.id, name:f.na, value: byOu[f.id] ?? null }},
                          geometry:{{ type: need===4?'MultiPolygon':'Polygon', coordinates:coords }} }};
              }}).filter(Boolean);

            if (!features.length) throw new Error(
              'No polygon boundaries at this OU level — try Level 2 or Level 3, or use Point Map for facility-level data');

            await window._leafletLoad;
            const mapDiv = _mapDiv{n}(cardBody);
            const map = L.map(mapDiv, {{ zoomControl:true, attributionControl:false, zoomSnap:0.5 }});
            mapDiv._leafletMap = map;   // tracked so a reload can destroy it (avoid re-init error)

            // Base tile layer (bottom)
            {tile_js}

            // Choropleth fill layer
            const layer = L.geoJSON({{ type:'FeatureCollection', features }}, {{
              style: feat => {{
                const v = feat.properties.value;
                return {{
                  fillColor: v !== null ? _colorForVal{n}(v, minV, maxV) : '#e0e0e0',
                  weight: 1,
                  color: DARK_MAP{n} ? 'rgba(255,255,255,0.2)' : 'rgba(255,255,255,0.6)',
                  fillOpacity: 0.85
                }};
              }},
              onEachFeature: (feat, lyr) => {{
                const v   = feat.properties.value;
                const fmt = v === null ? 'No data'
                  : v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toLocaleString();
                // Richer hover tooltip: metric name, value, % of total, rank.
                let tip = '<b>' + feat.properties.name + '</b><br>'
                        + METRIC_LABEL{n} + ': ' + fmt;
                if (v !== null && totalV > 0) {{
                  tip += ' (' + (v / totalV * 100).toFixed(1) + '%)';
                  if (rankOf[feat.properties.id]) tip += '<br>Rank ' + rankOf[feat.properties.id] + ' of ' + nOu;
                }}
                lyr.bindTooltip(tip, {{ sticky:true }});
                if (SHOW_LABELS{n} && v !== null) {{
                  lyr.bindTooltip('<b>' + feat.properties.name + '</b><br>' + fmt,
                    {{ permanent:true, direction:'center', className:'map-label' }});
                }}
              }}
            }});

            // Set the view BEFORE adding the choropleth so permanent labels
            // (Leaflet tooltips) can project/position; otherwise they never appear.
            map.fitBounds(layer.getBounds(), {{ padding:[8,8] }});
            layer.addTo(map);

            // ── Legend: sequential color ramp from min → max ──────────────────
            if (vals.length) {{
              const legend = L.control({{ position: 'bottomright' }});
              legend.onAdd = function() {{
                const div = L.DomUtil.create('div');
                div.style.cssText = 'background:rgba(255,255,255,0.9);padding:6px 9px;'
                  + 'border-radius:4px;font:11px sans-serif;color:#333;line-height:1.4;'
                  + 'box-shadow:0 1px 4px rgba(0,0,0,0.3);';
                const fmtV = x => x >= 1000 ? (x/1000).toFixed(1)+'k' : Math.round(x).toLocaleString();
                const grad = 'linear-gradient(to right,' + _colorForVal{n}(minV, minV, maxV)
                  + ',' + _colorForVal{n}((minV+maxV)/2, minV, maxV)
                  + ',' + _colorForVal{n}(maxV, minV, maxV) + ')';
                div.innerHTML = '<div style="font-weight:bold;margin-bottom:3px;">' + METRIC_LABEL{n} + '</div>'
                  + '<div style="width:120px;height:10px;border-radius:2px;background:' + grad + ';"></div>'
                  + '<div style="display:flex;justify-content:space-between;">'
                  + '<span>' + fmtV(minV) + '</span><span>' + fmtV(maxV) + '</span></div>';
                return div;
              }};
              legend.addTo(map);
            }}

            // Overlay boundary layers (on top of choropleth)
            if (window._dbg) window._dbg('AreaMap{n} overlays: ' + (ovGeos||[]).length + ' layers, levels=' + JSON.stringify(OV_LEVELS{n}));
            (ovGeos || []).forEach((geo, i) => {{
              if (window._dbg) window._dbg('AreaMap{n} overlay['+i+'] isArr=' + Array.isArray(geo) + ' len=' + (Array.isArray(geo)?geo.length:0));
              const bl = _borderLayer{n}(geo, OV_LEVELS{n}[i]);
              if (bl) bl.addTo(map);
            }});

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
              const _res = await Promise.all([
                dhis2Get('{geo_url}'),
                dhis2Get('{analytics_url}'){ov_fetch_str}
              ]);
              const geoRaw    = _res[0];
              const analytics = _res[1];
              const ovGeos    = _res.slice(2);
              await renderChart{n}Real(cardBody, geoRaw, analytics, ovGeos);
            }} catch(e) {{
              console.error('[AreaMap{n}]', e);
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
