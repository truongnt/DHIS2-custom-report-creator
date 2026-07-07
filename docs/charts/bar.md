# Bar Chart Plugin — Requirements (v2 — Full)

> Plugin: `charts/plugins/bar.py` (`id = "bar"`). Common controls/options: [COMMON.md](COMMON.md).
> This is the **reference implementation** — its spec is the most detailed; other charts reuse its
> common options and document only their deltas.
>
> **Bar-specific options** (beyond COMMON's `color_scheme`):
> `x_axis` (Period / Org Unit, default Period) · `stack_mode` (None / Stack / Expand) ·
> `orientation` (Vertical / Horizontal) · `series_limit` (All / 5 / 10 / 20).

Dựa trên `controlPanel.tsx` + `controls.tsx` của Apache Superset  
`plugin-chart-echarts/src/Timeseries/Regular/Bar`

---

## 1. DATA

| Control | Choices / default | Notes |
|---|---|---|
| **Metrics** | 1–3 numeric DEs | tracker_numeric / aggregate / indicator, each with agg picker (SUM/COUNT/AVG/MIN/MAX) |
| **Dimension (Group by)** | 0–1 DE | Any DE; option-set DE → series per option value; numeric DE → no grouping |
| **X Axis** | Period / Org Unit | Period = bars per time period; Org Unit = bars per facility |
| **Time Grain** | Monthly / Quarterly / Yearly | Only when X Axis = Period |
| **Series limit** | 0 (All) / 5 / 10 / 20 | Limit number of dimension series shown |
| **Row limit** | 0 (All) / 100 / 500 / 1000 / 5000 | Limit total API rows |
| **Sort** | None / Value / Label + Asc/Desc | Superset: sort_series_type (Sum/Min/Max/Avg/Name) |
| **Filters** | DE + op + value rows | Append as &filter=stg.uid:EQ:val |

---

## 2. BAR STYLE

| Control | Choices | Default | Superset equivalent |
|---|---|---|---|
| **Stack mode** | None / Stack / Expand | None | `stack`: null / Stack / Expand |
| **Orientation** | Vertical / Horizontal | Vertical | `orientation`: vertical / horizontal |

### Stack × Data combinations

| Stack | Dimension | Metrics | Behaviour |
|---|---|---|---|
| None | — | 1 | Simple bars: 1 bar per period |
| None | 1 option-set DE | 1 | Grouped: 1 bar per option value per period |
| None | — | 2–3 | Grouped: 1 bar per metric per period |
| Stack | 1 option-set DE | 1 | Stacked: each option value is one layer |
| Stack | — | 2–3 | Stacked: each metric is one layer |
| Expand | 1 option-set DE | 1 | 100 % stacked by option values |

---

## 3. CHART OPTIONS (Customize tab)

### 3a. Series / Labels
| Control | Type | Default | Superset |
|---|---|---|---|
| **Show value labels** | checkbox | false | `show_value` |
| **Only total** (stacked mode only) | checkbox | true | `only_total` — show sum label on top of stack |

### 3b. Legend
| Control | Type | Default | Superset |
|---|---|---|---|
| **Show legend** | checkbox | true | `show_legend` |
| **Legend position** | segment: Top / Bottom / Left / Right | Bottom | `legendOrientation` |

### 3c. X Axis
| Control | Type | Default | Superset |
|---|---|---|---|
| **X Axis title** | text entry | "" | `x_axis_title` |
| **Label rotation** | segment: 0° / 45° / 90° | 45° | `xAxisLabelRotation` |
| **Label interval** | segment: Auto / All | Auto | `xAxisLabelInterval` |

### 3d. Y Axis
| Control | Type | Default | Superset |
|---|---|---|---|
| **Y Axis title** | text entry | "" | `y_axis_title` |
| **Y Axis format** | segment: Default / 1,234 / 1.2K / % | Default | `y_axis_format` |
| **Log scale** | checkbox | false | `logAxis` |

### 3e. Tooltip
| Control | Type | Default | Superset |
|---|---|---|---|
| **Rich tooltip** | checkbox | true | `rich_tooltip` — shows all series at that point |
| **Show total in tooltip** | checkbox | true | `showTooltipTotal` (only when rich + stacked) |

### 3f. Bar style
| Control | Type | Default | Superset |
|---|---|---|---|
| **Bar width** | segment: Auto / Thin / Normal / Wide | Auto | custom (no direct Superset equivalent) |
| **Color scheme** | palette picker (8 presets) | DHIS2 palette | `color_scheme` |

---

## 4. CONFIG SHAPE

```json
{
  "plugin_id": "bar",
  "title": "...",
  "col_width": 6,
  "chart_color": "#3498db",

  "metrics": [
    {"uid": "...", "name": "...", "type": "tracker_numeric",
     "agg": "SUM", "prog_uid": "...", "stage_uid": "..."}
  ],

  "dimensions": {
    "x_axis": "Period",
    "time_grain": "Monthly",
    "dimension": {"uid":"...", "name":"...", "type":"tracker_option",
                  "options":[{"code":"M","name":"Male"},...],
                  "prog_uid":"...", "stage_uid":"..."},
    "filters": [{"de_uid":"...", "op":"EQ", "value":"..."}],
    "series_limit": 0,
    "row_limit": 0,
    "sort_by": "None",
    "sort_dir": "Desc"
  },

  "plugin_options": {
    "stack_mode":    "None",
    "orientation":   "Vertical",
    "show_values":   false,
    "only_total":    true,
    "show_legend":   true,
    "legend_pos":    "Bottom",
    "x_title":       "",
    "x_rotation":    "45",
    "x_interval":    "Auto",
    "y_title":       "",
    "y_format":      "Default",
    "log_scale":     false,
    "rich_tooltip":  true,
    "tooltip_total": true,
    "bar_width":     "Auto"
  },

  "custom_options": {}
}
```

---

## 5. DHIS2 API

### Period X Axis
| Case | API |
|---|---|
| tracker numeric, no dim | `events/aggregate/{prog}?stage={stg}&value={de}&aggregationType={agg}&dimension=pe:{rpe}&dimension=ou:{ou}` |
| tracker option-set dim | `events/aggregate/{prog}?stage={stg}&dimension={stg}.{dim_de}&dimension=pe:{rpe}&dimension=ou:{ou}` |
| aggregate/indicator | `analytics.json?dimension=dx:{de1};{de2}&dimension=pe:{pe}&dimension=ou:{ou}&displayProperty=NAME` |
| mixed | parallel fetch, merge by period |

### Org Unit X Axis
```
events/aggregate/{prog}?stage={stg}&value={de}&aggregationType={agg}
  &dimension=ou:LEVEL-{level};&rows=ou&dimension=pe:{rpe}
```

---

## 6. JAVASCRIPT GENERATION (Chart.js)

```js
// Stack mode → Chart.js datasets
// None    → each dataset has NO stack property (grouped side-by-side)
// Stack   → each dataset: { stack: 'total' }
// Expand  → each dataset: { stack: 'total' } + beforeDraw: normalize to %

// Orientation
// Vertical   → indexAxis: 'x'  (default)
// Horizontal → indexAxis: 'y'

// Show value labels
// plugins: { datalabels: { display: true, anchor: 'end', align: 'end' } }
// (Chart.js datalabels plugin already included)

// Only total (stacked)
// Show label only on top-most dataset item, value = sum of stack

// Legend
// plugins: { legend: { display: true, position: 'bottom' } }

// X Axis title  →  scales.x.title = { display: true, text: '...' }
// Y Axis title  →  scales.y.title = { display: true, text: '...' }

// Rich tooltip → tooltip.mode: 'index', tooltip.intersect: false
// tooltip callbacks: footer = 'Total: ' + sum (when stacked + tooltip_total)

// Y format
// Default → no formatter
// 1,234   → Intl.NumberFormat
// 1.2K    → divide by 1000 with K suffix
// %       → append %

// Bar width
// Auto   → omit barThickness (Chart.js default)
// Thin   → barThickness: 12
// Normal → barThickness: 22
// Wide   → barThickness: 36

// Log scale → scales.y.type: 'logarithmic'
```

---

## 7. UI LAYOUT (chart_editor_panel.py)

### Dimensions section — new controls:
```
┌─ Dimensions ──────────────────────────────────┐
│ Time grain:   [Monthly] [Quarterly] [Yearly]  │  ← existing
│ X Axis:       [Period]  [Org Unit]             │  ← NEW SelectControl
│ Stack mode:   [None]    [Stack]    [Expand]   │  ← NEW SelectControl
│ Orientation:  [Vertical][Horizontal]           │  ← NEW SelectControl
│ Dimension:    [─ pick a data element ─────▼]  │  ← existing (single DE)
│ ─────────────────────────────────────────────  │
│ Filters   [+ Add filter]                       │  ← existing
│   [DE ▼] [EQ ▼] [value____] [✕]              │
│ ─────────────────────────────────────────────  │
│ Limit: [All▼]  Sort: [None▼] [Desc▼]          │  ← existing
│ Series limit: [All▼]                           │  ← NEW
└───────────────────────────────────────────────┘
```

### Chart Options (Style section right column) — new entries for "bar":
```
CHART OPTIONS
───────────────────────────────
☐ Show value labels
☐ Show legend        [Bottom▼]
───────────────────────────────
X Axis title: [_______________]
Rotation:  [0°][45°][90°]
Interval:  [Auto][All]
───────────────────────────────
Y Axis title: [_______________]
Y format:  [Default][1,234][1.2K][%]
☐ Log scale
───────────────────────────────
☐ Rich tooltip
☐ Show total in tooltip
───────────────────────────────
Bar width: [Auto][Thin][Normal][Wide]
```

---

## 8. PLUGIN REGISTRY CHANGES

| Plugin ID | Action |
|---|---|
| `bar` | NEW — unified bar chart |
| `bar_monthly` | hidden=True (backward compat only) |
| `stacked_cat` | hidden=True (backward compat only) |
| `grouped_bar` | hidden=True (backward compat only) |
| `bar_ou` | hidden=True (org unit logic rolled into `bar`) |
| Others | unchanged |

---

## 9. Out of scope (v1)

- Zoom slider
- Forecast / rolling mean
- Annotations
- Multiple group-by columns
- Minor ticks / split lines
- X Axis bounds / truncation
- Color By Primary Axis
- Percentage threshold labels
- Legend sort
- Tooltip sort by metric / time format
