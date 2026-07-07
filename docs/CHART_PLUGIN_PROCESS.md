# Chart Plugin Development Process

Standard workflow for creating or upgrading a chart plugin in this project.  
Reference implementation: `charts/plugins/bar.py` (27/27 tests pass).

---

## 1 — Requirements

Before writing any code, define the full option set by cross-referencing:

- **Chart.js docs** — what the library supports for this chart type (axes, scales, plugins, dataset properties)
- **Superset** — what visual controls Superset exposes for the equivalent chart type (use as a requirements checklist)
- **bar.py** — the reference implementation; most plugins should support the same common options

### Common options (all visual plugins should have these)

The full shared option set is documented in **[charts/COMMON.md](charts/COMMON.md)**
(`color_scheme`, `show_legend`, `show_values`, `y_format`, `x_rotation`, `log_scale`, …).

### Plugin-specific options (define per plugin)

Each chart's own options live in a dedicated file: **[charts/README.md](charts/README.md)**
indexes them (`charts/<plugin>.md`). Document each option with: key, type, choices/range,
default, behavior description. The authoritative source is the `options = [...]` list in
`charts/plugins/<name>.py`.

---

## 2 — Checklist (test_<plugin>_checklist.py)

One BEFORE/AFTER pair per option. Structure:

```
[00] default rendering (smoke test)
[01..N] one pair per option
  BEFORE = default plugin_options (baseline)
  AFTER  = only the option under test changed
```

Rules:
- Only ONE option changes per pair
- AFTER label states what changed and what to look for
- Descriptive footer text on the pair image states the expected visual difference
- Cover edge cases: extremes of ranges, off/on toggles, all enum values if visually distinct

### Pair image requirements
- BEFORE: always use default plugin_options (same chart every time)
- AFTER: delta is exactly one setting
- Both charts same size (flex 50%/50%), same sample data

### How to run
1. `python test_<plugin>_checklist.py` — generates `C:\Temp\<plugin>_checklist.html`
2. Node.js 22+ runs `C:\Temp\screenshot_<plugin>.mjs` via CDP → full-page PNG + bounding-box JSON
3. PIL crops per bounding box → `C:\Temp\<plugin>_checks\NN_name.png`
4. Read each pair image with Read tool, report PASS/FAIL

---

## 3 — Implementation

### File structure (follow bar.py exactly)

```python
# charts/plugins/<name>.py

_PALETTES = { ... }          # copy from bar.py

def _po(po, key, default):   # copy from bar.py
def _palette_js(cs):         # copy from bar.py
def _chartjs_options(n, po): # CHART-TYPE specific Chart.js options builder
def _sample_js(n, po, cs):   # preview renderer — uses _chartjs_options
def _real_js_*(n, ...):      # real-data renderer per DE type / fetch strategy

class <Name>Plugin(ChartPlugin):
    id          = "<name>"
    label       = "<Human name>"
    icon        = "<emoji>"
    description = "<one sentence>"
    preview_id  = "<preview_canvas key>"
    options     = [SelectControl(...), ...]   # shown as segmented buttons in UI
    metrics     = [MetricControl(...)]
    dimensions  = [DimensionControl(...)]     # if applicable
    time_grain  = TimeGrainControl(...)       # or None

    @classmethod
    def build_js(cls, n, config):
        po = config.get("plugin_options") or {}
        ...
```

### _chartjs_options() contract

Must:
- Read all options from `po` via `_po(po, key, default)`
- Return a complete Chart.js `options` object as a Python str (f-string)
- Set `maintainAspectRatio: false` (required for fixed-height flex containers)
- Apply `minRotation + maxRotation` together for x_rotation (not just maxRotation)
- Apply `y_fmt_fn` callback to both `scales.y.ticks.callback` and `tooltip callbacks`

### _sample_js() contract

Must:
- Call `_chartjs_options(n, po)` — every visible option must affect the preview
- Apply palette via `_palette_js(color_scheme)`
- For stacked bar: call `_expand_normalize_js()` for Expand mode
- Destroy existing chart instance before re-creating

---

## 4 — Test & Fix Loop

```
run checklist → read pair images → mark PASS/FAIL → fix FAILs → rerun → repeat
```

Completion criterion: **every pair image shows a visible difference in the AFTER chart
for the option under test**. No option may be skipped.

Fix strategy:
- If an option has no visual effect → the `_chartjs_options` or `_sample_js` is not reading it
- If the preview differs from real behavior → check `_real_js_*` is applying the same option
- If JS error → check Python f-string `{{}}` escaping and missing `+` operators

---

## 5 — Registration

Register in `charts/plugins/__init__.py`:
```python
try:
    from charts.plugins.<name> import <Name>Plugin
except Exception:
    <Name>Plugin = None

# Add to _ORDERED list (visible plugins before hidden legacy ones)
("name", <Name>Plugin),
```

---

## Plugin status

| Plugin | SelectControls | Options wired | Tests | Status |
|---|---|---|---|---|
| bar | color_scheme, stack_mode, orientation, x_axis, show_values, y_format, x_rotation, log_scale | ✓ all | 27/27 PASS | DONE |
| line_trend | color_scheme, line_tension, fill_area, show_legend, show_values, y_format, x_rotation, log_scale | ✓ all | 18/18 PASS | DONE |
| line_multi | color_scheme, line_tension, fill_area, show_legend, show_values, y_format, x_rotation, log_scale | ✓ all | 18/18 PASS | DONE |
| pie_cat | color_scheme, chart_type, show_legend, show_values | ✓ all | 10/10 PASS | DONE |
| scorecard | y_format, value_color, font_size | ✓ all | 9/9 PASS | DONE |
| combined_bar_line | color_scheme, show_legend, show_values, y_format, x_rotation, dual_y_axis | ✓ all | 15/15 PASS | DONE |
| table_view | mode, theme, heatmap, stripe, border, font_size | ✓ all | 12/12 PASS | DONE |
