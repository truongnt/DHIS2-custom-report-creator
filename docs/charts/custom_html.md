# Custom HTML (`custom_html`)

> Plugin: `charts/plugins/custom_html.py`. Common controls/options: [COMMON.md](COMMON.md).
> Render a user-supplied HTML/CSS/JS template inside a **sandboxed iframe**, bound to the
> chart's data. Inspired by Superset's "ECDS HTML Widget" (github.com/truongnt/Superset).

## Data controls

| Control | Value |
|---|---|
| Metric | 1–8 DEs (`max_count=8`); aggregate / indicator / tracker_numeric / tracker_option → **columns** |
| Dimension | 0–4 DE/PA (`max_count=4`, `show_alias=True`); option-set DE/PA → **rows** (same model as the Data Table) |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

| key | label | choices / type | default | behavior |
|---|---|---|---|---|
| `mode` | Data | Aggregated / Raw | Aggregated | same as `table_view` — totals/grouped vs per-event rows |
| `min_height` | Min height | 200 / 300 / 400 / 600 *(or custom px)* | 300 | iframe minimum height; auto-grows to content |
| `html` | HTML / JS template | **TextAreaControl** (tall editor) | starter template | the HTML/CSS/JS to render |

## Data contract (inside the iframe)

The computed `{cols, rows}` (identical to what the Data Table would produce for the same
metrics/dimensions/mode) are exposed to the template:

| Global | Shape |
|---|---|
| `window.__chartData` / `window.DATA` | `Array<Object>` — one object per row keyed by column name |
| `window.FIRST` | `__chartData[0] || {}` |
| `window.__columnNames` | `Array<String>` column headers |
| `window.__metricLabels` | `Array<String>` selected metric names |
| `{{Column name}}` | replaced **before render** with the FIRST row's value (numbers get thousands separators / 2 decimals) |

## Implementation notes

- **Reuses the Data Table pipeline**: `build_js` emits `TablePlugin.build_js(...)` then
  **overrides `_tMount{n}`** (function-declaration hoisting → the later definition wins) so the
  rows render as an HTML widget instead of a table. No table code is modified.
- **Sandboxed**: `<iframe sandbox="allow-scripts allow-popups allow-popups-to-escape-sandbox">`
  via `srcdoc`; auto-resizes to content via `postMessage` + `ResizeObserver`.
- **Script-safe**: every `<` in the embedded template/labels is written as `<`, and the
  override's own HTML scaffold strings use `\x3c` — so the host page's HTML "script data"
  tokenizer never sees a `<script`/`</script`/`</body` token (which would otherwise merge or
  truncate the inline scripts and leave `initChart{n}` undefined). Runtime values are unchanged.
- **Editor**: `html` uses a `TextAreaControl` → a tall monospace editor with HTML syntax
  highlighting (`{{column}}` green if known, red if not); the debounced browser preview
  refreshes as you type.
- **AI generate from image** (`llm/html_from_image.py`): a "🤖 Generate from image…" button
  uploads a screenshot/mock-up, downscales it (≤1568px), and sends it to Claude (vision) which
  returns a self-contained HTML snippet inserted into the editor. Static-layout reproduction;
  the image is sent to the Anthropic API (user confirms first). Runs off the UI thread.

## Acceptance

- Unit: `tests/test_preview.py::TestCustomHtml` (registered/visible, override-after-table,
  script-safety, default template, min-height) + generic `TestPluginJsGeneration`.
- E2E render: `tests/e2e/test_render_custom_html.py` — iframe renders, `window.DATA` bound,
  `{{Column}}` substituted (REQ-HTML-RENDER-01).
- REQ ids: REQ-HTML-REG-01, REQ-HTML-RENDER-01, REQ-HTML-SAFE-01, REQ-HTML-DEFAULT-01, REQ-HTML-HEIGHT-01.
