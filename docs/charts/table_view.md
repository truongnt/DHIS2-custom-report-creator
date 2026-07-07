# Data Table (`table_view`)

> Plugin: `charts/plugins/table_view.py`. Common controls/options: [COMMON.md](COMMON.md).
> Tabular display with sort, filter, heatmap and CSV download. Not a Chart.js chart.

## Data controls

| Control | Value |
|---|---|
| Metric | 1–8 DEs (`max_count=8`); types: aggregate / indicator / tracker_numeric / tracker_option → **columns** |
| Dimension | **0–4 DE/PA** (`max_count=4`, `show_alias=True`); option-set DE/PA → **rows** (each becomes a column; alias = header). Disaggregation comes from here. |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options (all table-specific — none from COMMON)

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `mode` | Mode | Aggregated / Raw | Aggregated | Aggregated = analytics totals; Raw = per-event rows |
| `ou_hierarchy` | OU hierarchy | Off / On | Off | **raw tracker only** — adds ancestor columns (e.g. Province, District) before "Org unit", via `hierarchyMeta=true` + `organisationUnitLevels` names |
| `tracker_link` | Tracker link | Off / On | Off | **raw tracker only** — appends an "Open" column deep-linking each event's TEI to Tracker Capture (`#/dashboard?tei=…&program=…&ou=…`); opens a new tab via the top window |
| `theme` | Theme | Default / Blue / Green / Light / Dark | Default | header/row color theme |
| `heatmap` | Heatmap | Off / On | Off | On = cells shaded by value |
| `stripe` | Stripe rows | On / Off | On | zebra striping |
| `border` | Border | Light / None / Dark | Light | cell border style |
| `font_size` | Font size | Medium / Small / Large | Medium | table text size |

## Interactive behaviors (not options)

- **Click a row** → highlights it (amber); clicking another moves the highlight.
- **Typed per-column filters**: a column is auto-classified for its filter UI —
  *date* columns (`YYYY-MM-DD`) get **from/to** pickers (range), low-cardinality
  columns (option sets, org unit, sex…) get a **dropdown** of distinct values, everything
  else stays free-text. Header click still sorts; the filter row is frozen under the header.

## Acceptance — per-option E2E render (`tests/e2e/test_render_table.py`, screenshots)

Each option is verified by its **real rendered effect** (`getComputedStyle` on the table):

- **REQ-TABLE-MODE-01** — Aggregated mode: columns = selected metrics; **no auto org/time split** → single total row by default.
- **REQ-TABLE-DISAGG-01/02** — adding **dimensions** (DE/PA, e.g. Sex, Species) splits rows by them; each dimension is a row column (alias = header), metrics stay columns. Tracker source → events grouped & aggregated per metric `agg`.
- **REQ-TABLE-MODE-02** — Raw mode shows flat event rows (Facility/Period/Age/Sex/Cases, 8 rows).
- **REQ-TABLE-THEME-01** — `theme` sets header background (Default/Blue/Green/Light/Dark).
- **REQ-TABLE-HEATMAP-01** — `heatmap` On shades numeric cells by value; Off = no shading.
- **REQ-TABLE-STRIPE-01** — `stripe` On = alternating row background; Off = transparent.
- **REQ-TABLE-BORDER-01** — `border` Light/None/Dark sets cell border width+style.
- **REQ-TABLE-FONT-01** — `font_size` Small/Medium/Large sets cell font-size (11/13/15px).

New features:
- **REQ-TABLE-OUHIER-01/02** — `ou_hierarchy` adds ancestor columns (raw tracker). Unit: `tests/test_preview.py::TestTableNewFeatures`.
- **REQ-TABLE-TLINK-01/02** — `tracker_link` adds the Tracker Capture column. Unit: same class.
- **REQ-TABLE-FILTER-DD-01** — categorical columns get a dropdown filter. E2E: `tests/e2e/test_render_table.py::test_table_filter_dropdown_for_categorical`.
- **REQ-TABLE-FILTER-DATE-01** — date columns get from/to range pickers. Unit: `TestTableNewFeatures::test_typed_filters_present`.
- **REQ-TABLE-ROWSEL-01** — click a row to highlight it. E2E: `test_table_row_click_highlights`.

Also: `scripts/checklists/test_table_checklist.py` (12 manual BEFORE/AFTER pairs).
