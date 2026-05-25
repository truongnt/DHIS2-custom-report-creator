# DHIS2 Custom Report Creator

A Windows desktop app that generates production-ready DHIS2 Standard HTML reports from natural language descriptions, powered by Claude AI.

## Features

- **AI-powered report generation** — describe your report in Vietnamese or English; Claude writes the complete HTML/JS
- **Multi-turn chat** — plan your report interactively, then generate; refine with follow-up messages
- **Dashboard builder** — drag-and-drop layout with per-card chart type selection
- **Interactive selectors** — reports include built-in OU and period dropdowns; no DHIS2 filter UI needed
- **Live preview** — opens in browser with sample data before deploying
- **One-click deploy** — pushes directly to your DHIS2 instance via REST API
- **Credential manager** — passwords stored in Windows Credential Manager (DPAPI encrypted)
- **13 chart templates** — bar, line, pie/donut, scorecard, traffic light, data table, combined, and more

## Requirements

- Python 3.11+
- Windows (uses Windows Credential Manager for password storage)
- Access to a DHIS2 instance
- An Anthropic API key

## Installation

```powershell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Running

```powershell
python main.py
```

## How It Works

1. **Connect** — enter your DHIS2 URL and credentials; the app fetches available indicators, data elements, programs, and datasets
2. **Describe** — chat with the AI to plan your report (which indicators, period type, chart style)
3. **Generate** — click "Generate HTML Report"; Claude writes a complete Bootstrap + Chart.js report
4. **Preview** — open in browser to see the report with sample data
5. **Deploy** — publish directly to DHIS2 as a Standard HTML report

Generated reports include:
- Interactive OU and period selectors (populated from the DHIS2 API at runtime)
- DHIS2 analytics API calls with `credentials: 'include'`
- Sample/demo data shown automatically in preview mode (`file://` protocol)

## Architecture

```
main.py                  # App entry point
ui/
  app_window.py          # Main window — connection, chat, generate, deploy
  chat_panel.py          # Multi-turn chat widget
  dashboard_builder.py   # Drag-drop dashboard layout editor
  report_view.py         # HTML preview panel with toolbar
dhis2/
  client.py              # DHIS2Client — auth, requests, pagination
  metadata.py            # Fetches indicators, data elements, programs
  report_api.py          # Deploy report via POST /api/reports
llm/
  report_generator.py    # Single-chart report generation (template fill or from scratch)
  dashboard_generator.py # Multi-chart dashboard generation
  chat_generator.py      # Multi-turn chat: plan → generate → refine
  context_builder.py     # Converts DHIS2 metadata to LLM context string
  html_utils.py          # CDN link fixer (handles browser "Save As" rewrites)
charts/
  templates.py           # 13 built-in chart HTML templates
  preview_canvas.py      # Thumbnail renderer for dashboard builder palette
```

## Security Notes

- DHIS2 credentials are entered at runtime and never written to disk
- Passwords are stored in Windows Credential Manager via `keyring`
- The `.env` file holds only `ANTHROPIC_API_KEY`

## License

Internal tool — CHAI Laos.
