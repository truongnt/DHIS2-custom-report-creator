# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

**Auto Report** is a Windows desktop app that lets users describe a report in natural language and automatically generates it from DHIS2 data. It connects to any DHIS2 instance (URL + credentials supplied at runtime), collects metadata (programs, datasets, indicators, data elements), sends that metadata as context to an LLM, then queries the DHIS2 analytics API to produce a formatted report.

Typical DHIS2 instance used in development: `https://hmis.gov.la/hmis` (Laos national HMIS).

## Stack

- **Python 3.11+** — all backend logic and UI
- **CustomTkinter** (preferred) or **Tkinter** — Windows desktop UI
- **`requests`** — DHIS2 REST API calls (Basic Auth, JSON)
- **Anthropic Python SDK** — LLM calls to generate report structure and interpret metadata
- **`openpyxl`** — Excel export of reports
- **`python-dotenv`** — local `.env` for the Anthropic API key (never hardcode)

## Architecture

```
auto_report/
  main.py            # App entry point, launches UI
  ui/
    app_window.py    # Main window: URL/user/pass inputs, prompt box, run button
    report_view.py   # Renders the generated report (table + charts)
  dhis2/
    client.py        # DHIS2Client — wraps requests, handles auth, pagination
    metadata.py      # Fetches programs, datasets, indicators, data elements
    analytics.py     # Builds and executes analytics queries (/api/analytics)
  llm/
    context_builder.py  # Converts DHIS2 metadata into an LLM-ready context string
    report_generator.py # Sends user prompt + metadata context → structured report plan
  export/
    excel_export.py  # Writes report to .xlsx via openpyxl
  .env               # ANTHROPIC_API_KEY (gitignored)
```

## DHIS2 API Patterns

All requests use `Authorization: Basic <base64(user:pass)>` and `Content-Type: application/json`.

Key endpoints:
- Metadata: `GET /api/metadata.json` with `?programs:fields=...` or `?dataSets:fields=...`
- Indicators: `GET /api/indicators.json?fields=id,name,numerator,denominator,...&paging=false`
- Program indicators: `GET /api/programIndicators?fields=...&paging=false`
- Dataset elements: `GET /api/dataSets/{id}.json?fields=dataSetElements[dataElement[...]]`
- Analytics (aggregate): `GET /api/analytics?dimension=dx:...&dimension=pe:...&dimension=ou:...`
- Analytics (events): `GET /api/analytics/events/query/{programId}?...`
- Expression description: `GET /api/expressions/description?expression=<urlencoded>`

Always request `paging=false` when you need all records. DHIS2 returns 50 by default.

## LLM Integration

The LLM receives: system prompt describing the DHIS2 context + serialized metadata relevant to the user's prompt. It returns a structured report plan (which indicators/data elements to query, period, org unit level, table structure). The app then executes those queries and formats the output.

Use `claude-sonnet-4-6` for report generation. Enable prompt caching on the static metadata context block (it can be large). See the `claude-api` skill for caching patterns.

## Development Commands

```powershell
# Install dependencies
pip install customtkinter requests anthropic openpyxl python-dotenv

# Run the app
python main.py

# Run a specific module standalone for testing
python -m dhis2.metadata
```

## Key Conventions

- `DHIS2Client` in `dhis2/client.py` is the single place that holds the session and base URL. All other modules receive a client instance; they do not construct their own sessions.
- Credentials are entered in the UI and passed in-memory — never written to disk.
- The `.env` file holds only `ANTHROPIC_API_KEY`. DHIS2 credentials are runtime-only.
- Metadata fetches can be slow; run them in a background thread so the UI stays responsive. Use `threading.Thread` with a callback, not `asyncio`.
- Period notation follows DHIS2 conventions: `2024`, `2024Q1`, `202401`, `LAST_12_MONTHS`, etc.
