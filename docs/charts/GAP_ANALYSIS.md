# Chart gap analysis — DHIS2 + Superset vs Auto Report

Comparison of every chart/visualization type offered by **DHIS2 Data Visualizer**,
**DHIS2 Maps**, and the **Apache Superset** viz gallery against what this app already
ships. Each "Missing — new plugin" row has a per-chart requirement file in this folder.

> This is a planning artifact. The app's source of truth is still the `options=[...]` of
> each `charts/plugins/<id>.py`. Files for not-yet-built charts mark the plugin as
> *(proposed)* and declare their REQ ids so traceability shows them as GAP until built.

**Sources (verified):**
- DHIS2 Data Visualizer — https://docs.dhis2.org/en/use/user-guides/dhis-core-version-master/analysing-data/data-visualizer.html
- DHIS2 Maps — https://docs.dhis2.org/en/use/user-guides/dhis-core-version-master/analysing-data/maps.html
- Superset chart gallery — https://superset.apache.org/docs/using-superset/exploring-data/ and the ECharts plugin set (4.x)

Verdict legend: **Have** = already a plugin · **Variant** = covered by an option on an
existing plugin · **Missing** = new plugin proposed (own req file).

---

## 1. DHIS2 Data Visualizer

| Source type | App | Verdict | Proposed id / file |
|---|---|---|---|
| Column | `bar` (Vertical) | Have | — |
| Stacked column | `bar` (stack_mode=Stack/Expand) | Have | — |
| Bar | `bar` (Horizontal) | Have | — |
| Stacked bar | `bar` (Horizontal + stack) | Have | — |
| Line | `line_trend` / `line_multi` | Have | — |
| **Area** | — | Missing | [area](area.md) |
| **Stacked area** | — | Missing | [stacked_area](stacked_area.md) |
| Pie | `pie_cat` | Have | — |
| **Radar** | — | Missing | [radar](radar.md) |
| **Gauge** | — | Missing | [gauge](gauge.md) |
| **Year over year (line)** | — | Missing | [year_over_year](year_over_year.md) |
| Single value | `scorecard` | Have | — |
| Pivot table | `table_view` | Have | — |
| **Scatter** | — | Missing | [scatter](scatter.md) |
| Combined (line + column) | `combined_bar_line` | Have | — |
| **Outlier table** (data quality) | — | Missing | [outlier_table](outlier_table.md) |

---

## 2. DHIS2 Maps (layers)

| Source layer | App | Verdict | Proposed id / file |
|---|---|---|---|
| Thematic — choropleth | `area_map` | Have | — |
| Thematic — bubble / proportional symbol | `point_map` | Have | — |
| **Facility** (org-unit icon markers) | — | Missing | [facility_map](facility_map.md) |
| **Event** (per-event points + heat/cluster) | partial (`point_map` event coords) | Missing | [event_map](event_map.md) |
| **Tracked entity** | — | Missing | [te_map](te_map.md) |
| Org unit (boundaries) | partial (`area_map` overlay_levels) | Variant | — |
| **Google Earth Engine** (raster) | — | Missing (likely out-of-scope) | [earth_engine_map](earth_engine_map.md) |

---

## 3. Apache Superset gallery

| Source viz | Category | App | Verdict | Proposed id / file |
|---|---|---|---|---|
| Big Number | KPI | `scorecard` | Have | — |
| **Big Number with Trendline** | KPI | partial | Missing | [big_number_trend](big_number_trend.md) |
| Table | Table | `table_view` (Raw) | Have | — |
| Pivot Table v2 | Table | `table_view` (Aggregated) | Variant | — |
| Time-series Line / Bar / Area | Evolution | `line_*` / `bar` / area* | Have/Missing | area* → [area](area.md) |
| Mixed time-series | Evolution | `combined_bar_line` | Have | — |
| **Scatter (time-series)** | Evolution/Correlation | — | Missing | [scatter](scatter.md) |
| Pie / Donut | Part of a whole | `pie_cat` | Have | — |
| **Funnel** | Part of a whole | — | Missing | [funnel](funnel.md) |
| **Treemap** | Part of a whole | — | Missing | [treemap](treemap.md) |
| **Sunburst** | Part of a whole | — | Missing | [sunburst](sunburst.md) |
| **Partition / Icicle** | Part of a whole | — | Missing | [partition](partition.md) |
| **Nightingale / Rose** | Part of a whole | — | Missing | [rose](rose.md) |
| **Histogram** | Distribution | — | Missing | [histogram](histogram.md) |
| **Box Plot** | Distribution | — | Missing | [box_plot](box_plot.md) |
| **Bubble chart** (x/y/size) | Correlation | — | Missing | [bubble_chart](bubble_chart.md) |
| **Heatmap** (matrix) | Correlation | — | Missing | [heatmap](heatmap.md) |
| **Calendar Heatmap** | Distribution | — | Missing | [calendar_heatmap](calendar_heatmap.md) |
| **Waterfall** | Ranking | — | Missing | [waterfall](waterfall.md) |
| **Sankey** | Flow | — | Missing | [sankey](sankey.md) |
| **Chord** | Flow | — | Missing | [chord](chord.md) |
| **Graph / Network** | Flow | — | Missing | [network](network.md) |
| **Bullet** | Ranking | — | Missing | [bullet](bullet.md) |
| **Radar** | Part of a whole | — | Missing | [radar](radar.md) |
| **Gauge** | KPI | — | Missing | [gauge](gauge.md) |
| **Word Cloud** | Distribution | — | Missing | [word_cloud](word_cloud.md) |
| Country / World Map | Map | `area_map` | Variant | — |
| deck.gl (scatter/hex/path/arc/polygon) | Map | partial | Variant/Out-of-scope | (noted in [event_map](event_map.md)) |

---

## 4. Implementation feasibility summary

Quick reference for deciding what to build. "Native" = Chart.js core; "lib" = one extra
JS plugin (loaded the same way Leaflet is loaded by the map plugins).

| Difficulty | Charts |
|---|---|
| **Low** — native Chart.js / small | area, stacked_area, year_over_year, radar, scatter, bubble_chart, rose, histogram, waterfall, big_number_trend |
| **Medium** — one extra JS lib | gauge, treemap, heatmap, calendar_heatmap, box_plot, sankey, funnel |
| **Medium** — Leaflet (reuse map infra) | facility_map, event_map, te_map |
| **High / niche** — D3/ECharts/custom | sunburst, partition, chord, network, word_cloud |
| **Table / non-chart** | outlier_table |
| **Likely out-of-scope** (needs GEE auth + raster) | earth_engine_map |

See each chart's file for its full option set, provenance, and acceptance plan.
