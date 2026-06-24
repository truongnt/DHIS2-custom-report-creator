# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**Auto Report** is a Windows desktop app for building DHIS2-backed charts and dashboards. Users connect to a DHIS2 instance, browse data elements, configure chart templates, preview them in a browser, then assemble and deploy dashboards. An AI Customize feature lets users describe chart changes in natural language.

Typical DHIS2 instance used in development: `https://hmis.gov.la/hmis` (Laos national HMIS).

## Stack

- **Python 3.11+** — all backend logic and UI
- **PySide6 6.11.1** — Qt-based Windows desktop UI (migrated from CustomTkinter in 2025)
- **`requests`** — DHIS2 REST API calls (Basic Auth, JSON)
- **Anthropic Python SDK** — LLM calls for AI chart customization
- **`openpyxl`** — Excel export
- **`python-dotenv`** — local `.env` for `ANTHROPIC_API_KEY` (never hardcode)
- **Windows Credential Manager** (`keyring`) — saves DHIS2 profiles and API key

## Architecture

```
auto_report/
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
    fixed_templates.py       # 11 templates: bar, line_trend, line_multi, pie_cat, scorecard,
                             #   combined_bar_line, table_view, bar_monthly, stacked_cat,
                             #   grouped_bar, bar_ou
    plugins/
      bar.py                 # Chart.js JS generator for bar/stacked/grouped charts
      # ... one file per template
  config/
    chart_library.py         # Save/load user's saved charts (JSON)
    profile_manager.py       # DHIS2 connection profiles via keyring
  .env                       # ANTHROPIC_API_KEY (gitignored)
```

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
- Credentials passed in-memory only — never written to disk

## Security Constraints

- DHIS2 credentials: entered in UI at runtime, held in-memory, **never written to disk**
- Generated HTML calls DHIS2 API at runtime in the browser — Python never fetches analytics data
- `.env` holds only `ANTHROPIC_API_KEY` (allowed on disk)
- DHIS2 profiles saved to Windows Credential Manager via `keyring` (encrypted)

## Development Commands

```powershell
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py

# Run chart rendering simulation tests (no network needed)
python test_preview_app_sim.py
```

## LLM Integration

AI Customize uses `claude-haiku-4-5-20251001` / `claude-sonnet-4-6` / `claude-opus-4-8` (user-selectable in Config panel). Chart config dict is serialized and sent as context. The LLM returns updated `custom_options` which are merged into the chart config before re-rendering.
