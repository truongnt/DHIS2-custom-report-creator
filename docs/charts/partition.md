# Partition / Icicle (`partition`)

> Plugin: `charts/plugins/partition.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Hierarchy drawn as nested adjacent rectangles (a rectangular sunburst) — width/height = value.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | 1–2 required — hierarchy levels |
| Time grain | none (snapshot) |

## Options

From COMMON: `color_scheme`, `show_values`, `y_format`.

Partition-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `orientation` | Orientation | Horizontal / Vertical | **Horizontal** | icicle direction (rows vs columns of the hierarchy) |
| `levels` | Hierarchy | OU hierarchy / Dimension chain | **OU hierarchy** | what the levels represent |
| `label_mode` | Labels | Name / Name+Value / None | **Name** | block labels |

## Provenance & feasibility

- **Source:** Superset ("Partition Chart" / Icicle).
- **Equivalent in:** Superset *Partition* (DHIS2 n/a).
- **Rendering:** D3 / ECharts (no Chart.js equivalent).
- **Difficulty / priority:** High · Low (niche; same data as sunburst, different layout).
- **Notes:** Consider building only if `sunburst` is built — they share the hierarchy pipeline.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_partition_checklist.py`.
- E2E: `tests/e2e/test_render_partition.py`.
- REQ ids: REQ-PARTITION-RENDER-01, REQ-PARTITION-ORIENT-01, REQ-PARTITION-LEVELS-01, REQ-PARTITION-LABEL-01.
