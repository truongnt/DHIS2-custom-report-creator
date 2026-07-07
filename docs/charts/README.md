# Chart Requirements

Per-chart requirements. Start with **[COMMON.md](COMMON.md)** for controls/options shared across
charts; each chart file below lists only what is specific to it.

> Source of truth = the `metrics` / `dimensions` / `options` / `time_grain` attributes in
> `charts/plugins/<name>.py`. Process for adding/changing options:
> [../CHART_PLUGIN_PROCESS.md](../CHART_PLUGIN_PROCESS.md).

> **Gap analysis:** [GAP_ANALYSIS.md](GAP_ANALYSIS.md) compares the DHIS2 (Data Visualizer +
> Maps) and Apache Superset catalogs against the app and lists every chart not yet built.
> The "Proposed charts" table below indexes those forward-looking req files — they describe
> charts that are **not implemented yet** (plugin marked *(proposed)*); their REQ ids show as
> GAP in traceability until built. The user selects which to implement.

| Chart | Plugin | Own options? | Checklist |
|---|---|---|---|
| [bar](bar.md) | `bar.py` | x_axis, stack_mode, orientation, series_limit | `test_bar_checklist.py` |
| [line_trend](line_trend.md) | `line_trend.py` | line_tension, fill_area | `test_line_trend_checklist.py` |
| [line_multi](line_multi.md) | `line_multi.py` | line_tension, fill_area | `test_line_multi_checklist.py` |
| [pie_cat](pie_cat.md) | `pie_cat.py` | chart_type, show_values(Percent/Value) | `test_pie_checklist.py` |
| [scorecard](scorecard.md) | `scorecard.py` | value_color, font_size | `test_scorecard_checklist.py` |
| [combined_bar_line](combined_bar_line.md) | `combined_bar_line.py` | dual_y_axis | `test_combined_checklist.py` |
| [table_view](table_view.md) | `table_view.py` | mode, theme, heatmap, stripe, border, font_size | `test_table_checklist.py` |
| [area_map](area_map.md) | `area_map.py` | ou_level, base_map, overlay_levels, border_*, color_scheme(seq), show_labels | `tests/test_preview.py` |
| [point_map](point_map.md) | `point_map.py` | ou_level, base_map, overlay_levels, show_empty, point_*, bubble_gradient, show_values | `tests/test_preview.py` |
| [custom_html](custom_html.md) | `custom_html.py` | mode, min_height, html (template) | `tests/e2e/test_render_custom_html.py` |
| [bar_monthly](bar_monthly.md) | `bar_monthly.py` | — (data-driven) | — |
| [bar_ou](bar_ou.md) | `bar_ou.py` | — (data-driven) | — |
| [grouped_bar](grouped_bar.md) | `grouped_bar.py` | — (data-driven) | — |
| [stacked_cat](stacked_cat.md) | `stacked_cat.py` | — (data-driven) | — |

## Proposed charts (not yet implemented)

Gap-analysis candidates — see [GAP_ANALYSIS.md](GAP_ANALYSIS.md) for the full DHIS2/Superset
comparison and feasibility. Grouped by build difficulty (see each file for options + provenance).

| Chart | Source(s) | Rendering | Difficulty |
|---|---|---|---|
| [area](area.md) | DHIS2 · Superset | Chart.js native | Low |
| [stacked_area](stacked_area.md) | DHIS2 · Superset | Chart.js native | Low |
| [year_over_year](year_over_year.md) | DHIS2 | Chart.js native | Low |
| [scatter](scatter.md) | DHIS2 · Superset | Chart.js native | Low |
| [bubble_chart](bubble_chart.md) | Superset | Chart.js native | Low |
| [radar](radar.md) | DHIS2 · Superset | Chart.js native | Low |
| [rose](rose.md) | Superset | Chart.js native | Low |
| [histogram](histogram.md) | Superset | Chart.js native | Low |
| [waterfall](waterfall.md) | Superset | Chart.js native | Low |
| [big_number_trend](big_number_trend.md) | Superset | scorecard + sparkline | Low |
| [gauge](gauge.md) | DHIS2 · Superset | needs lib | Medium |
| [treemap](treemap.md) | Superset | needs lib | Medium |
| [heatmap](heatmap.md) | Superset | needs lib | Medium |
| [calendar_heatmap](calendar_heatmap.md) | Superset | needs lib | Medium |
| [box_plot](box_plot.md) | Superset | needs lib | Medium |
| [funnel](funnel.md) | Superset | needs lib | Medium |
| [sankey](sankey.md) | Superset | needs lib | Medium |
| [bullet](bullet.md) | Superset | custom Chart.js | Medium |
| [outlier_table](outlier_table.md) | DHIS2 | HTML table | Medium |
| [facility_map](facility_map.md) | DHIS2 Maps | Leaflet | Medium |
| [event_map](event_map.md) | DHIS2 Maps · Superset | Leaflet | Medium |
| [te_map](te_map.md) | DHIS2 Maps | Leaflet | Medium |
| [sunburst](sunburst.md) | Superset | D3/ECharts | High (niche) |
| [partition](partition.md) | Superset | D3/ECharts | High (niche) |
| [chord](chord.md) | Superset | D3 | High (niche) |
| [network](network.md) | Superset | ECharts/vis-network | High (niche) |
| [word_cloud](word_cloud.md) | Superset | d3-cloud | High (niche) |
| [earth_engine_map](earth_engine_map.md) | DHIS2 Maps | Leaflet + GEE | Out-of-scope |
