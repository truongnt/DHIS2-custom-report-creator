# Nightingale / Rose (`rose`)

> Plugin: `charts/plugins/rose.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Polar-area chart: equal-angle segments whose radius encodes value — a circular bar chart.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | required — one wedge per option value / OU / period |
| Time grain | optional (default none) |

## Options

From COMMON: `color_scheme`, `show_legend`, `show_values`.

Rose-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `radius_scale` | Radius scale | Linear / Sqrt | **Sqrt** | Sqrt = area ∝ value (avoids exaggeration), Linear = radius ∝ value |
| `start_angle` | Start angle | 0 / 90 | **0** | rotation of the first wedge |

> No axis options (polar). `show_values` = Off/On (value at each wedge).

## Provenance & feasibility

- **Source:** Superset ("Nightingale Rose Chart").
- **Equivalent in:** Superset *Nightingale Rose* (DHIS2 n/a).
- **Rendering:** native Chart.js (`type:'polarArea'`).
- **Difficulty / priority:** Low · Low (niche but trivial).
- **Notes:** Same data shape as `pie_cat`; differs only in encoding. Could be a `pie_cat` mode.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_rose_checklist.py`.
- E2E: `tests/e2e/test_render_rose.py`.
- REQ ids: REQ-ROSE-RENDER-01, REQ-ROSE-SCALE-01, REQ-ROSE-ANGLE-01.
