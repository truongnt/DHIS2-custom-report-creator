# Outlier table (`outlier_table`)

> Plugin: `charts/plugins/outlier_table.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> A data-quality table listing values flagged as statistical outliers for a metric over a period.

## Data controls

| Control | Value |
|---|---|
| Metric | 1+ (`max_count=8`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | none (rows are OU × period outliers) |
| Time grain | Monthly (default), Quarterly, Yearly |

## Options

From COMMON: `font_size` (via table conventions).

Outlier-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `method` | Method | Z-score / Modified Z / IQR | **Z-score** | outlier detection algorithm |
| `threshold` | Threshold | 2 / 2.5 / 3 *(or custom number)* | **3** | cutoff (std-devs or IQR multiplier) |
| `sort` | Sort | By score / By value / By OU | **By score** | row ordering |
| `theme` | Theme | Default / Blue / Green / Light / Dark | **Default** | table styling (reuse table_view themes) |

> Custom value: `threshold` accepts a freeform number (REQ-UI-OPT-01). Reuse `table_view` rendering.

## Provenance & feasibility

- **Source:** DHIS2 (Data Quality / "Outlier detection"; also a Data Visualizer surfacing).
- **Equivalent in:** DHIS2 *Outlier detection table* (no direct Superset equivalent).
- **Rendering:** HTML table (reuse `table_view.py` scaffolding) + JS outlier computation, OR the
  DHIS2 `/api/outlierDetection` endpoint when online.
- **Difficulty / priority:** Medium · Medium (valuable for data-quality dashboards).
- **Notes:** Offline mode computes outliers from fixture rows; online mode can call the API.

## Acceptance (to create on implementation)

- Checklist/unit: `scripts/checklists/test_outlier_table_checklist.py` + `tests/test_preview.py`.
- E2E: `tests/e2e/test_render_table.py` (reuses table render harness).
- REQ ids: REQ-OUTLIER-RENDER-01, REQ-OUTLIER-METHOD-01, REQ-OUTLIER-THRESHOLD-01, REQ-OUTLIER-SORT-01.
