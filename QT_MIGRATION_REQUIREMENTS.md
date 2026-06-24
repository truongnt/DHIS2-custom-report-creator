# Qt Migration Requirements Checklist

Checklist để verify từng chức năng sau khi migrate từ CustomTkinter sang PySide6.

## 1. Application Startup

| # | Requirement | Status |
|---|-------------|--------|
| 1.1 | App launches without error (`python main.py`) | ✅ |
| 1.2 | Window opens maximized | ✅ |
| 1.3 | Left sidebar visible with 3 nav buttons | ✅ |
| 1.4 | Config panel shown by default | ✅ |
| 1.5 | Chart Editor + Dashboard nav buttons disabled (not connected) | ✅ |
| 1.6 | Saved profile auto-loaded from Windows Credential Manager | ✅ |
| 1.7 | Auto-connect attempted if saved password found | ✅ |
| 1.8 | Anthropic API key restored from .env or Credential Manager | ✅ |

## 2. Config Panel — DHIS2 Connection

| # | Requirement | Status |
|---|-------------|--------|
| 2.1 | Profile dropdown populated with saved profiles | ✅ |
| 2.2 | Selecting a profile fills URL/user/pass fields | ✅ |
| 2.3 | Delete (✕) profile shows confirm dialog | ✅ |
| 2.4 | Server URL / Username / Password fields editable | ✅ |
| 2.5 | Password field masked (●●●) | ✅ |
| 2.6 | Connect button → progress indicator + "Connecting…" | ✅ |
| 2.7 | Successful connect: "✓ Connected" button, hide login fields | ✅ |
| 2.8 | Failed connect: error status, re-enable Connect button | ✅ |
| 2.9 | Connection status label shows user + DE/program count | ✅ |
| 2.10 | Cache info label shows "Cached" or "Freshly loaded" | ✅ |
| 2.11 | ↺ Refresh Metadata button force-fetches from server | ✅ |
| 2.12 | 💾 Save Profile saves to Windows Credential Manager | ✅ |
| 2.13 | "↺ Change connection" button appears after connect | ✅ |
| 2.14 | After connect: auto-switch to Chart Editor panel | ✅ |
| 2.15 | Chart Editor + Dashboard nav buttons enabled after connect | ✅ |

## 3. Config Panel — Filters & Metadata

| # | Requirement | Status |
|---|-------------|--------|
| 3.1 | ⚙ Filters button enabled after connect | ✅ |
| 3.2 | FilterConfigDialog opens (modal) | ✅ |
| 3.3 | Filter summary label updates after filter configured | ✅ |
| 3.4 | Metadata loads in background thread | ✅ |
| 3.5 | Progress indicator during metadata load | ✅ |

## 4. Config Panel — API Key & Model

| # | Requirement | Status |
|---|-------------|--------|
| 4.1 | API key field (masked) populated from .env | ✅ |
| 4.2 | 💾 Save API key → saves to Credential Manager | ✅ |
| 4.3 | AI Model dropdown has 3 options (Haiku/Sonnet/Opus) | ✅ |
| 4.4 | Selected model used for LLM calls | ✅ |

## 5. Navigation

| # | Requirement | Status |
|---|-------------|--------|
| 5.1 | Clicking nav button switches panel | ✅ |
| 5.2 | Active nav button highlighted (DHIS2 blue) | ✅ |
| 5.3 | Inactive buttons have transparent bg | ✅ |
| 5.4 | Switching to Dashboard refreshes library | ✅ |

## 6. Chart Editor — Chart Type Section

| # | Requirement | Status |
|---|-------------|--------|
| 6.1 | 11 chart type tiles displayed in 4 columns | ✅ |
| 6.2 | Each tile shows icon + label | ✅ |
| 6.3 | Hovering tile changes background | ✅ |
| 6.4 | Clicking tile: highlights with DHIS2 border | ✅ |
| 6.5 | Grid collapses after selection, shows summary row | ✅ |
| 6.6 | "Change ▼" re-expands tile grid | ✅ |
| 6.7 | Metrics section label updates (e.g. "TICK 1–3") | ✅ |

## 7. Chart Editor — Source Section

| # | Requirement | Status |
|---|-------------|--------|
| 7.1 | "Program (Tracker)" checkbox | ✅ |
| 7.2 | "Aggregate Dataset" checkbox | ✅ |
| 7.3 | Program dropdown populated after metadata load | ✅ |
| 7.4 | Selecting program → stage dropdown populated | ✅ |
| 7.5 | Stage selection → DE list updated | ✅ |
| 7.6 | Aggregate search box filters aggregate DEs | ✅ |
| 7.7 | Switching source type hides/shows appropriate controls | ✅ |

## 8. Chart Editor — Metrics Section

| # | Requirement | Status |
|---|-------------|--------|
| 8.1 | DE list scrollable, max 140px height | ✅ |
| 8.2 | Search box filters DE list live | ✅ |
| 8.3 | ✕ button clears search | ✅ |
| 8.4 | Checkboxes for each DE | ✅ |
| 8.5 | Agg dropdown (SUM/COUNT/AVG/MIN/MAX) for numeric DEs | ✅ |
| 8.6 | Max DE count enforced per chart type | ✅ |
| 8.7 | Selected DEs shown in status label below list | ✅ |

## 9. Chart Editor — Dimensions Section

| # | Requirement | Status |
|---|-------------|--------|
| 9.1 | SelectControls (stack_mode, orientation, x_axis) shown for bar plugin | ✅ |
| 9.2 | SegmentedButton highlights selected option | ✅ |
| 9.3 | Time grain row (Monthly/Quarterly/Yearly) | ✅ |
| 9.4 | Dimension picker dropdown (split-by field) | ✅ |
| 9.5 | Dimension hint text below dropdown | ✅ |
| 9.6 | "+ Add filter" button adds filter row | ✅ |
| 9.7 | Filter row: DE dropdown + operator + value + ✕ | ✅ |
| 9.8 | ✕ removes filter row | ✅ |
| 9.9 | Row Limit dropdown (10/20/50/100/200/All) | ✅ |
| 9.10 | Sort By + Sort Dir dropdowns | ✅ |

## 10. Chart Editor — Style Section

| # | Requirement | Status |
|---|-------------|--------|
| 10.1 | 8 color preset buttons (20x20) | ✅ |
| 10.2 | Selected color has white border highlight | ✅ |
| 10.3 | Title QLineEdit (placeholder "Auto from DE name") | ✅ |
| 10.4 | Col width SegmentedButton (Full/Half/Third) | ✅ |
| 10.5 | Mode radio buttons: Fixed / AI | ✅ |
| 10.6 | AI description textbox appears in AI mode | ✅ |
| 10.7 | "CHART OPTIONS" section with dynamic options | ✅ |
| 10.8 | Checkbox options appear 2 per row | ✅ |
| 10.9 | Segment options appear as SegmentedButton | ✅ |
| 10.10 | Entry options appear as QLineEdit | ✅ |

## 11. Chart Editor — AI Customize

| # | Requirement | Status |
|---|-------------|--------|
| 11.1 | "🤖 AI Customize ▶" toggle button | ✅ |
| 11.2 | Clicking expands AI chat panel | ✅ |
| 11.3 | Chat display shows "You:" / "AI:" exchanges | ✅ |
| 11.4 | Send button calls LLM (chart_customizer.customize_chart) | ✅ |
| 11.5 | Enter key in input sends | ✅ |
| 11.6 | "↺ Reset all" clears customizations | ✅ |

## 12. Chart Editor — My Charts Panel

| # | Requirement | Status |
|---|-------------|--------|
| 12.1 | "📚 My Charts ▶" toggle in header | ✅ |
| 12.2 | Expands to horizontal scrollable saved chart cards | ✅ |
| 12.3 | Each card: icon + name + template + "Load ↩" button | ✅ |
| 12.4 | Load restores template + title + color + DEs | ✅ |

## 13. Chart Editor — Actions

| # | Requirement | Status |
|---|-------------|--------|
| 13.1 | 💾 Save: asks name via dialog, saves to library | ✅ |
| 13.2 | + Add to Dashboard: adds config to dashboard panel | ✅ |
| 13.3 | 🌐 Preview in Browser: opens localhost:15432 | ✅ |
| 13.4 | Preview auto-refreshes 400ms after config change | ✅ |
| 13.5 | Preview uses fixture data when available | ✅ |
| 13.6 | Stacked bar uses PALETTE colors (no single-color override when dimension set) | ✅ |

## 14. Dashboard Builder Panel

| # | Requirement | Status |
|---|-------------|--------|
| 14.1 | Two-column layout: Chart Library (240px) | Dashboard Canvas | ✅ |
| 14.2 | Library shows saved charts from config.chart_library | ✅ |
| 14.3 | Each chart: name + template label + [+ Add] [✕ Delete] | ✅ |
| 14.4 | Delete chart: confirm dialog | ✅ |
| 14.5 | ↺ Refresh reloads library | ✅ |
| 14.6 | ← Chart Editor switches to chart editor panel | ✅ |
| 14.7 | Added cards shown in canvas with ●color + name + meta | ✅ |
| 14.8 | ✕ removes card from canvas | ✅ |
| 14.9 | Card count label updates | ✅ |
| 14.10 | Report name QLineEdit | ✅ |
| 14.11 | ⬇ Export HTML exports assembled dashboard | ✅ |
| 14.12 | 🚀 Deploy sends to DHIS2 | ✅ |
| 14.13 | Export/Deploy disabled when no cards | ✅ |
| 14.14 | 🗑 Clear all: confirm dialog, removes all cards | ✅ |

## 15. Status Bar

| # | Requirement | Status |
|---|-------------|--------|
| 15.1 | Status message visible at bottom | ✅ |
| 15.2 | Error messages shown in red | ✅ |
| 15.3 | Progress bar (indeterminate) during async operations | ✅ |
| 15.4 | Progress stops after operation completes | ✅ |

## 16. Non-UI Modules (Must Not Break)

| # | Requirement | Status |
|---|-------------|--------|
| 16.1 | dhis2/ modules unchanged and working | ✅ |
| 16.2 | llm/ modules unchanged and working | ✅ |
| 16.3 | charts/ modules unchanged and working | ✅ |
| 16.4 | config/ modules unchanged and working | ✅ |
| 16.5 | ui/preview_server.py unchanged (HTTP server) | ✅ |
| 16.6 | test_preview_app_sim.py still passes (chart rendering tests) | ✅ |

## 17. Performance Improvements (Qt-specific gains)

| # | Requirement | Status |
|---|-------------|--------|
| 17.1 | DE list scrolling smooth (no recreate-all on search) | ✅ |
| 17.2 | Debounce preview refresh via QTimer (400ms) | ✅ |
| 17.3 | No main thread blocking during connect/load | ✅ |

---
*Legend: ⬜ Not tested  ✅ PASS  ❌ FAIL*

## Notes

- 11 chart templates (not 13) — the unified `bar` plugin replaced several legacy templates
- Debug prints removed from `chart_editor_panel.py` and `charts/plugins/bar.py`
- `_ChartEditorPlaceholder` dead code removed from `app_window.py`
- `&&` used in button text to display literal `&` in Qt
