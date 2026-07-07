# Pie — by category (`pie_cat`)

> Plugin: `charts/plugins/pie_cat.py`. Common controls/options: [COMMON.md](COMMON.md).
> Breakdown by option-set category for the selected period.

## Data controls

| Control | Value |
|---|---|
| Metric | 0–1 DE (`max_count=1`, **optional** — empty = event count); agg picker shown |
| Dimension | **required** — option-set DE; each option value becomes one slice |
| Time grain | none (`time_grain = None`) |

## Options

From COMMON: `color_scheme`, `show_legend`.

Pie-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `chart_type` | Chart type | Pie / Donut | Pie | Donut = `cutout` ring |
| `show_values` | Labels | Off / **Percent / Value** | Off | overrides COMMON's Off/On — Percent shows %, Value shows raw number on each slice (painted by the shared `showValues` canvas plugin — datalabels is NOT used, it duplicated bar totals) |
| `label_pos` | Label position | Inside / Outside | Inside | Inside = white labels centred on slice; Outside = dark labels past the rim (`anchor/align:'end'`, `clip:false`, chart padding) |
| `show_empty` | Empty slices | Hide / Show | Hide | Hide drops zero-value categories from both the pie **and the legend** (real data) |

## Acceptance

- `scripts/checklists/test_pie_checklist.py` (pairs incl. label_pos, show_empty)
- Unit: `tests/test_preview.py::TestPieOptions` (REQ-PIE-LABELPOS-01/02, REQ-PIE-EMPTY-01/02)
- E2E: `tests/e2e/test_chart_options.py` (REQ-PIE-TYPE-01, REQ-PIE-VALUES-01 — datalabels registered so labels draw, not hover-only)
