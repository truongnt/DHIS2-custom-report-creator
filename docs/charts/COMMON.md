# Chart Requirements — Common (shared across plugins)

This file defines the controls and options that **every** (or most) chart plugin shares.
Each per-chart file in this folder lists **only what is specific to that chart** and links back here.

> Source of truth: the `metrics` / `dimensions` / `options` / `time_grain` class attributes in
> `charts/plugins/<name>.py`. If code and this doc disagree, **the code wins** — update the doc.
> Process for adding/changing options: [../CHART_PLUGIN_PROCESS.md](../CHART_PLUGIN_PROCESS.md).

---

## 1. Data controls (the control *framework*)

These control *types* (defined in `charts/plugins/base.py`) appear on most plugins; each plugin
sets their parameters. Per-chart files document the concrete values.

| Control | Purpose | Per-plugin parameters |
|---|---|---|
| `MetricControl` | Which numeric DE(s)/indicator(s) to plot | `max_count`, `allowed_types`, `default_agg` (SUM/COUNT/AVG/MIN/MAX), `show_agg_picker`, `required` |
| `DimensionControl` | "Split by" — one series/slice/layer per value | `allowed_types`, `required`, `hint` |
| `TimeGrainControl` | Period bucketing | `default` = Monthly / Quarterly / Yearly. `None` = chart has no time axis |
| `SelectControl` | A segmented-button option | `(key, label, choices, default)` |
| `CheckboxGroupControl` | Multi-select option | `(key, label, choices, default_tuple)` |

**`allowed_types`** values: `tracker_numeric`, `tracker_option`, `aggregate`, `indicator`.

---

## 2. Common visual options

Most visual (non-map) plugins reuse these `SelectControl`s with identical choices/defaults.
A per-chart file only re-documents one of these if it **deviates** (different choices/default).

| key | label | choices | default | applies to |
|---|---|---|---|---|
| `color_scheme` | Color scheme | Default / DHIS2 / Warm / Cool / Earth / Pastel | Default | all categorical charts (bar, line, pie, combined) |
| `show_legend` | Legend | Off / Bottom / Top / Right | Bottom | charts with multiple series |
| `show_values` | Data labels | Off / On | Off | bar, line, combined |
| `y_format` | Y format | Default / 1,234 / 1.2K / % | Default | bar, line, combined, scorecard |
| `x_rotation` | X rotation | 0 / 45 / 90 | 0 | bar, line, combined |
| `log_scale` | Log scale | Off / On | Off | line |

> **Maps are different.** `area_map` / `point_map` use a *sequential* `color_scheme`
> (Blues / Greens / Reds / Oranges / Purples) and their own option set — see their files.
> Likewise `show_values` is `Off/On` here but `Percent/Value` for pie and `Hide/Show` for maps.

---

## 3. Color palettes (`color_scheme`)

Categorical palettes live in `_PALETTES` (copied from `bar.py` into each visual plugin):
`Default`, `DHIS2`, `Warm`, `Cool`, `Earth`, `Pastel`. Applied via `_palette_js(color_scheme)`.

Map sequential ramps live in `area_map._SCHEMES` (2-stop RGB interpolation).

---

## 4. Chart.js rendering contract (visual plugins)

Every `_chartjs_options()` / `_sample_js()` must (see CHART_PLUGIN_PROCESS §3):

- Read all options via `_po(po, key, default)` — every visible option must affect the preview
- Set `maintainAspectRatio: false` (fixed-height flex containers)
- Apply `minRotation + maxRotation` together for `x_rotation`
- Apply the `y_format` callback to both `scales.y.ticks.callback` and tooltip callbacks
- Destroy any existing chart instance before re-creating

---

## 5. Acceptance testing

- **REQ-CHART-RENDER-01** — Mọi plugin visual (bar, line_trend, line_multi, pie_cat,
  combined_bar_line, table_view, scorecard) **render được ở sample mode, KHÔNG lỗi console JS**,
  có canvas/table/giá trị thật. Kiểm bằng **E2E render thật + screenshot**:
  `tests/e2e/test_render_charts.py` (Selenium headless, bằng chứng dưới `test-evidence/`).
- **Per-option E2E** (real render, verified via live Chart.js config / Leaflet DOM, with screenshots):
  - Charts (`tests/e2e/test_chart_options.py`): **REQ-BAR-ORIENT-01 / REQ-BAR-STACK-01 / REQ-BAR-COLOR-01**,
    **REQ-LINE-TENSION-01 / REQ-LINE-FILL-01 / REQ-LINE-LOG-01 / REQ-LINE-LEGEND-01**,
    **REQ-PIE-TYPE-01**, **REQ-COMBINED-DUALY-01**, **REQ-SCORECARD-COLOR-01**.
  - Table (`tests/e2e/test_render_table.py`): **REQ-TABLE-MODE-01/02, THEME-01, HEATMAP-01, STRIPE-01, BORDER-01, FONT-01**.
  - Maps (`tests/e2e/test_map_options.py`): **REQ-MAP-AM-OULEVEL-01 / COLOR-01 / BASEMAP-01 / LABELS-01**,
    **REQ-MAP-PM-COLOR-01 / GRADIENT-01 / VALUES-01 / OVERLAY-01**.
- **Map plugins** base render: `tests/e2e/test_render_map.py` (REQ-MAP-AM-01, REQ-MAP-PM-01) + unit `tests/test_preview.py`;
  bảng acceptance thủ công trong [../../CLAUDE.md](../../CLAUDE.md).
- **Visual checklist** per plugin (thủ công, theo option): `scripts/checklists/test_<plugin>_checklist.py`
  — one BEFORE/AFTER pair per option. Run all: `python scripts/checklists/run_all_checklists.py`.
- Completion = mọi option tạo khác biệt thấy được trong ảnh AFTER. No option skipped.
