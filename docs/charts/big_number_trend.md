# Big Number with Trendline (`big_number_trend`)

> Plugin: `charts/plugins/big_number_trend.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> A large KPI value with a small sparkline of its recent trend and an optional period-over-period delta.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric / tracker_option; agg picker shown |
| Dimension | none |
| Time grain | Monthly (default), Quarterly, Yearly — drives the sparkline series |

## Options

From COMMON: `y_format`.

Big-number-specific (extends `scorecard`):

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `value_color` | Value color | Green / Blue / Red / Orange *(or custom #hex)* | **Blue** | color of the big number (same as scorecard) |
| `font_size` | Font size | Large / Medium / Small *(or custom px)* | **Large** | size of the big number |
| `subtitle` | Subtitle | Period / Comparison / None | **Comparison** | small caption: period label, Δ vs previous period, or hidden |
| `spark_type` | Trend style | Line / Bar / Area | **Line** | how the sparkline renders |
| `spark_color` | Trend color | Auto *(or custom #hex)* | **Auto** | sparkline color (Auto = value_color) |

> Custom values per REQ-UI-OPT-01 (hex / px). Reuses scorecard's number formatting.

## Provenance & feasibility

- **Source:** Superset ("Big Number with Trendline").
- **Equivalent in:** Superset *Big Number with Trendline* · DHIS2 *Single value* (no trend).
- **Rendering:** scorecard HTML/canvas + a small Chart.js sparkline.
- **Difficulty / priority:** Low · High (upgrades the existing KPI tile).
- **Notes:** Could be a `scorecard` mode (`trend=On`) rather than a separate plugin; needs the
  metric's recent period series in addition to the single aggregate.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_big_number_trend_checklist.py`.
- E2E: `tests/e2e/test_render_big_number_trend.py`.
- REQ ids: REQ-BIGNUM-RENDER-01, REQ-BIGNUM-SUBTITLE-01, REQ-BIGNUM-SPARKTYPE-01, REQ-BIGNUM-COLOR-01.
