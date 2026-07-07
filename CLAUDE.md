# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**DHIS2 Dashboard Builder** (repo dir still named `Auto report`) is a Windows desktop app for building DHIS2-backed charts and dashboards. Users connect to a DHIS2 instance, browse data elements, configure chart templates, preview them in a browser, then assemble and deploy dashboards. An AI Customize feature lets users describe chart changes in natural language.

Typical DHIS2 instance used in development: `https://hmis.gov.la/hmis` (Laos national HMIS).

## Stack

- **Python 3.11+** — all backend logic and UI
- **PySide6 (≥6.5, dev on 6.11.1)** — Qt-based Windows desktop UI (migrated from CustomTkinter in 2025)
- **`requests`** — DHIS2 REST API calls (Basic Auth, JSON)
- **Anthropic Python SDK** — LLM calls for AI chart customization
- **`openpyxl`** — Excel export
- **`python-dotenv`** — local `.env` for `ANTHROPIC_API_KEY` (never hardcode)
- **Windows Credential Manager** (`keyring`) — saves DHIS2 profiles and API key

## Architecture

All modules live at the **repository root** (there is no `auto_report/` package). Run from the repo root; `python main.py` is the entry point.

```
<repo root>/
  main.py                    # Qt entry point — QApplication + AppWindow
  ui/
    app_window.py            # QMainWindow: sidebar nav, QStackedWidget (config/chart_editor/dashboard)
    chart_editor_panel.py    # Full chart config UI: type picker, metrics, dims, style, AI, My Charts
    dashboard_builder_panel.py # Library + canvas for assembling multi-chart dashboards
    filter_config_dialog.py  # QDialog: program/dataset/DE-group filters
    qt_utils.py              # Shared QSS, SegmentedButton widget, helper fns
    preview_server.py        # Local HTTP server on port 15432 serving preview HTML
    preview_window.py        # Thin wrapper for update_preview()
  dhis2/
    client.py                # DHIS2Client — auth, pagination, caching
    metadata.py              # Fetches programs, datasets, DEs, indicators
    analytics.py             # Builds/executes analytics queries
  llm/
    chart_customizer.py      # AI Customize: sends chart config + user prompt to LLM
    context_builder.py       # Serializes DHIS2 metadata for LLM context
  charts/
    fixed_templates.py       # Template registry + all JS generators; generate_preview_page() /
                             #   generate_card_fragment() / assemble_dashboard() live here
    plugins/                 # One JS generator per chart family:
      bar.py                 #   bar/stacked/grouped, bar_monthly, bar_ou
      line_trend.py / line_multi.py / pie_cat.py / scorecard.py
      combined_bar_line.py / table_view.py / stacked_cat.py / grouped_bar.py
      area_map.py / point_map.py   # Leaflet choropleth + bubble maps (geoFeatures + analytics)
      shared_js.py / base.py       # Common JS helpers (dhis2Get, color scales) + base class
  config/
    chart_library.py         # Save/load user's saved charts (JSON)
    dashboard_library.py     # Save/load assembled dashboards (config/dashboard_library.json)
    credentials.py           # DHIS2 connection profiles + API key via keyring (NOT profile_manager)
    descriptions.py          # Per-instance DE/indicator/PA local annotations
  .env                       # ANTHROPIC_API_KEY (gitignored)
```

**Legacy modules (present but NOT wired into the current Qt app):** the chat-driven "generate full HTML report" flow described in `README.md` (`llm/report_generator.py`, `llm/chat_generator.py`, `ui/chat_panel.py`, `ui/report_view.py`, `ui/dashboard_panel.py`, `ui/chart_config_panel.py`) is from the pre-Qt / early-Qt era. `app_window.py` now installs a `_ChatPanelStub` and the live flow is Chart Editor + Dashboard Builder. Treat README's "describe → generate" feature as historical; don't assume those modules run.

## Key Architectural Flows

**Connect → Load Metadata → Edit Chart → Preview → Dashboard → Deploy**

1. `AppWindow._on_connect()` — runs in thread, calls `DHIS2Client.connect()`, on success calls `_unlock_ui()` + switches to chart_editor panel
2. `ChartEditorPanel._on_preview_browser()` — calls `generate_preview_page(cfg)`, then `update_preview(html)` which serves via local HTTP and opens browser
3. `DashboardBuilderPanel.on_export/on_deploy` — assembles all canvas cards into a single HTML file or POSTs to DHIS2

## DHIS2 API Patterns

All requests: `Authorization: Basic <base64(user:pass)>`, `Content-Type: application/json`.

Key endpoints:
- Metadata: `GET /api/metadata.json`, programs, dataSets, indicators with `paging=false`
- Analytics aggregate: `GET /api/analytics?dimension=dx:...&dimension=pe:...&dimension=ou:...`
- Analytics events: `GET /api/analytics/events/query/{programId}?...`

Always request `paging=false` for full result sets.

## Qt / PySide6 Conventions

- `QStackedWidget` at indices: 0=config, 1=chart_editor, 2=dashboard
- `SegmentedButton` in `qt_utils.py` replaces CTkSegmentedButton — mutually-exclusive checkable QPushButtons with `changed = Signal(str)`, `.get()`, `.set(value)`
- `QTimer.singleShot(0, cb)` replaces Tkinter's `self.after(0, cb)`
- Debounced preview: `QTimer(setSingleShot=True, interval=400ms)` connected to `_do_refresh`
- `&&` in button/label text for literal `&` (single `&` is Qt accelerator prefix)
- Modal dialogs use `QDialog.exec()` with `self.result` attribute pattern
- Passwords/API keys never stored as plaintext on disk (Windows Credential Manager only); only URL + username persist to `config/profiles.json`

## Security Constraints

- DHIS2 password + Anthropic API key: held in-memory at runtime and saved **only** to Windows Credential Manager (DPAPI) — **never plaintext on disk**. URL + username (non-sensitive) persist to `config/profiles.json`
- Generated HTML calls DHIS2 API at runtime in the browser — Python never fetches analytics data
- `.env` holds only `ANTHROPIC_API_KEY` (allowed on disk)
- DHIS2 profiles saved to Windows Credential Manager via `keyring` (encrypted)

## Development Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Run the app (console window — handy for stack traces)
python main.py

# Run WITHOUT a console window (GUI only): use pythonw, or double-click start.pyw
pythonw main.py

# Run unit tests (no network needed)
python -m pytest tests/test_preview.py -v

# Run chart rendering simulation tests
python scripts/manual/test_preview_app_sim.py

# Per-template HTML checklist scripts; run all at once:
python scripts/checklists/run_all_checklists.py
```

**Repo layout for non-pytest code** — only `tests/` holds pytest suites; everything else lives under `scripts/`:
- `scripts/checklists/` — per-template HTML-generation checks (`test_*_checklist.py`, shared `test_checklist_base.py`, `test_bar_real.py`) + `run_all_checklists.py` to run them together
- `scripts/manual/` — manual/interactive checks: `test_ui.py` (Qt integration), `test_preview_app_sim.py`, `test_bar_preview.py`, `preview_malaria_real.py`, `run_malaria_real_test.py`
- `scripts/data/` — one-off DHIS2 data/fixture utilities: `download_sample.py`, `fetch_*.py`, `find_malaria_uids.py`, `export_villages.py`
- `docs/` — design/requirements docs (`CHART_PLUGIN_PROCESS.md`, `UI_GUIDELINES.md`, `LOGIN_REQUIREMENTS.md`, `METADATA_FILTER_REQUIREMENTS.md`, `DATA_EXPORT_REQUIREMENTS.md`)
- `docs/charts/` — per-chart requirements: `COMMON.md` (shared controls/options) + one `<plugin>.md` per chart; `README.md` indexes them. Authoritative source for options is each plugin's `options=[...]` list.

> Scripts under `scripts/<group>/` set `REPO = Path(__file__).parent.parent.parent` (repo root) and `sys.path.insert(0, REPO)` so `import charts`/`dhis2` works. **If you move a script to a different depth, fix that `.parent` chain.**

## Testing Requirements — MANDATORY

A fix is NOT done until it passes **all three** layers:

### 1. Unit tests (automated)
```
python -m pytest tests/test_preview.py -v  →  137 collected, all pass (counts grow as map options are added; assert "all pass", not an exact number)
```
Tests cover: JS generation logic, brace balance, every map option, fixture injection, OU hierarchy.

### 2. HTML inspection (per-option)

After changing any map option, generate and inspect the HTML:
```python
# Quick check script — run in Auto report\ directory
from charts.fixed_templates import generate_preview_page
html = generate_preview_page(config)
# Check: brace balance, expected URL fragments, variable values
```

**What to verify per option:**

| Option | What to look for in generated HTML |
|--------|------------------------------------|
| `ou_level: Level N` | `LEVEL-N` in geoFeatures URL AND analytics `dimension=ou:...;LEVEL-N` |
| `base_map: CartoDB Light` | `cartocdn.com/light_all` in `L.tileLayer(...)` call |
| `base_map: CartoDB Dark` | `cartocdn.com/dark_all` AND `DARK_MAP1 = true` |
| `base_map: OpenStreetMap` | `tile.openstreetmap.org` |
| `base_map: Satellite` | `arcgisonline.com` |
| `base_map: None` | NO `tileLayer` call present |
| `overlay_levels: Level 2` | `OV_LEVELS1 = [2]`, Promise.all has 3 `dhis2Get` calls |
| `overlay_levels: Level 2,Level 3` | `OV_LEVELS1 = [2, 3]`, 4 `dhis2Get` calls |
| `overlay_levels: (empty)` | `OV_LEVELS1 = []`, 2 `dhis2Get` calls |
| `show_labels: Show` (area map) | `SHOW_LABELS = true` |
| `bubble_gradient: Gradient` (point map) | `USE_GRADIENT = true`, `GRADIENT1` array present |
| `show_values: Show` (point map) | `SHOW_VALUES = true`, `L.divIcon` code present |
| `point_scale: Small/Medium/Large` | `MAX_R` constant — must increase Small < Medium < Large |

### 3. Manual browser test (per option changed)

**Protocol for every map fix/feature — each option must be tested independently:**

1. Open app → do NOT connect (fixture mode uses downloaded data)
2. Select chart type: **Area Map** or **Point Map**
3. Source: Malaria Case Register `yAKTrPUMAuU`, stage `KqjOmlBpYtd`
4. Metric: pick any `tracker_option` DE (e.g. first one in the list)
5. Set the option to test (see table below)
6. Click **Preview**
7. **Check debug log**: open `logs/debug_YYYYMMDD_HHMMSS.log` — look for the `AreaMap1 geoRaw:` or `PointMap1` lines
8. **Take screenshot** or note visual result
9. Compare against expected visual (see table below)
10. **ONLY PASS** if: no JS errors in log AND visual matches expected AND no "Map error:" red banner

**Area Map — option-by-option acceptance criteria:**

| Option value | Log must show | Visual must show |
|---|---|---|
| `ou_level: Level 2` | `geoRaw: count=21` (provinces) | 18 colored province polygons |
| `ou_level: Level 3` | `geoRaw: count=272` (districts) | Colored district polygons |
| `base_map: CartoDB Light` | no tile error | Light grey/white tile background |
| `base_map: CartoDB Dark` | no tile error | Dark background tiles |
| `base_map: OpenStreetMap` | no tile error | OSM street map background |
| `base_map: Satellite` | no tile error | Satellite imagery background |
| `base_map: None` | no tile error | White/plain background only |
| `overlay_levels: Level 2` | no error | Dashed province border lines visible on top of choropleth |
| `overlay_levels: Level 2,Level 3` | no error | Both province AND district borders visible simultaneously |
| `overlay_levels: (none)` | no error | No extra border lines |
| `color_scheme: Reds` | no error | Choropleth colors are red gradient |
| `show_labels: Show` | no error | Value labels on each polygon |

**Point Map — option-by-option acceptance criteria:**

| Option value | Log must show | Visual must show |
|---|---|---|
| `ou_level: Level 4` | `geoRaw: count>0, first_ty=1` | Bubbles at health center locations |
| `ou_level: Level 3` | `geoRaw: count>0` | Bubbles at district level |
| `base_map: *` | no tile error | (Same as Area Map basemap criteria) |
| `overlay_levels: Level 2,Level 3` | no error | Province + district border lines visible behind bubbles |
| `bubble_gradient: Gradient` | no error | Bubble colors vary light→dark by value |
| `bubble_gradient: None` | no error | All bubbles same flat color |
| `show_values: Show` | no error | Value numbers appear inside/beside bubbles |
| `point_scale: Large` | no error | Largest bubbles clearly bigger than Small |
| `point_color: Red` | no error | Bubbles are red |

### 4. Debug log location and what to check

Log file: `Auto report\logs\debug_YYYYMMDD_HHMMSS.log`

Key lines to look for:
```
[debug] AreaMap1 geoRaw: count=272 first_ty=2   ← count>0 and ty=2 = polygons for area map
[debug] AreaMap1 analytics: headers=["ou","...","value"] rows=12  ← rows>0 = data
[error] Map error: No polygon boundaries ...   ← FAIL: wrong level for area map
[error] Map error: No point coordinates ...    ← FAIL: wrong level for point map
[unhandled] ...                                ← FAIL: JS runtime error
```

If log shows `rows=0` for analytics: check `_ou_parents` is in `window.__DEMO_FX__` (view-source in browser) and that the event OUs have entries at the requested level.

## LLM Integration

AI Customize uses `claude-haiku-4-5-20251001` / `claude-sonnet-4-6` / `claude-opus-4-8` (user-selectable in Config panel). Chart config dict is serialized and sent as context. The LLM returns updated `custom_options` which are merged into the chart config before re-rendering.

## Metadata Library (curation + local descriptions)

Sidebar "Metadata Library" button (enabled after connect) → `ui/metadata_editor_panel.py`
(embedded panel, QStackedWidget index 3). Two jobs:

1. **Curate the in-use set** — filter all metadata by type (**DE / PA / I / PI**) and move
   items between an **Available** list and an **In use** list (dual-list transfer: `→ « » ←`,
   double-click, respects the type filter + search). The Chart Editor then offers metrics &
   dimensions **only** from the in-use set. An **empty** in-use set offers **nothing** — the
   metric/dimension pickers show a prompt to open the Metadata Library and add items.
   - **Storage**: `config/selection.py` → `cache/<url_slug>/selection.json` (`{"in_use": [...]}`), per-instance.
   - **Wiring**: `app_window` loads the selection after connect and calls
     `chart_editor.set_in_use(...)`; on leaving the editor it re-pushes `get_selection()`.
     Chart Editor filters in `_refresh_de_list()` (`self._in_use`).
2. **Local descriptions** — annotate any DE/indicator/PA; used as AI context, stored locally,
   never sent to DHIS2. Storage: `config/descriptions.py` → `cache/<url_slug>/descriptions.json`.

### Testing (REQ-DESC / REQ-META-SEL / REQ-META-EDIT)
```
python -m pytest tests/test_descriptions.py tests/test_selection.py tests/integration/test_metadata_editor.py -v
```
Key requirements:
- REQ-DESC-04: Blank/empty description removes the key; REQ-DESC-07: per-instance isolation
- REQ-META-SEL-02/04: selection save/load round-trip, per-instance isolation
- REQ-META-EDIT-01/02: type filter + dual-list transfer; REQ-META-EDIT-04: Chart Editor
  metrics/dimensions restricted to the in-use set (empty = none, with a configure prompt)

## Dashboard Builder — Manual Mode

Dashboard canvas (`ui/dashboard_builder_panel.py`) features:
- **Add charts**: from Chart Library left panel
- **Save Dashboard**: locally to `config/dashboard_library.json` keyed by name
- **Load Dashboard**: via `ui/load_dashboard_dialog.py` — replaces canvas with saved cards
- **Export HTML**: calls `on_export` callback
- **Deploy to DHIS2**: calls `on_deploy` callback

### Testing (REQ-DASH-SAVE)
Covered in `tests/test_ai_planner.py::TestDashboardLibrary`:
- REQ-PLANNER-13: save + load round-trip
- REQ-PLANNER-14: delete removes entry

## Dashboard Builder — AI Generate Mode

### Flow
1. User clicks **"🤖 AI Generate"** in Dashboard Canvas header
2. `ui/ai_dashboard_dialog.py` opens
3. User types an intent or picks a quick-start preset
4. System calls `llm.ai_dashboard_planner.recommend_charts()`:
   - Context: loaded metadata + local descriptions
   - Mock mode (no API key): uses preset scenarios from `MOCK_SCENARIOS`
   - Real mode: sends structured prompt to Claude Haiku
5. AI returns JSON list of chart recommendations (title, chart_type, de_uid, rationale)
6. Dialog shows checkboxes — user selects which charts to add
7. Selected recs → `recs_to_chart_configs()` → added to canvas

### Mock scenarios (for offline test)
`llm.ai_dashboard_planner.MOCK_SCENARIOS` keys: `malaria_overview`, `supply_chain`, `performance_review`

### Testing (REQ-PLANNER)
```
python -m pytest tests/test_ai_planner.py -v
```
All tests must pass (currently 25, includes `TestDashboardLibrary`). Key requirements:
- REQ-PLANNER-04/05: mock_key scenario + placeholder UID resolution
- REQ-PLANNER-06/07/08: validation filters bad chart_type / de_uid / title
- REQ-PLANNER-09: mock_response overrides mock_key
- REQ-PLANNER-12: AI JSON with markdown fences is parsed correctly
- REQ-PLANNER-10: recs_to_chart_configs produces valid config dicts

### Full test requirement
```
python -m pytest tests/ -v  →  all pass
```
