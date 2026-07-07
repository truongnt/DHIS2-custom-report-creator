# Bullet chart (`bullet`)

> Plugin: `charts/plugins/bullet.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> A compact horizontal bar measuring one value against a target and qualitative ranges.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | none |
| Time grain | none (single value for the selected period) |

## Options

From COMMON: `y_format`.

Bullet-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `target` | Target | Off *(or custom number)* | **Off** | the comparison marker line |
| `ranges` | Qualitative ranges | None / Thirds / Custom | **Thirds** | poor/ok/good background bands |
| `max` | Max | Auto *(or custom number)* | **Auto** | end of the measure axis |
| `bar_color` | Measure color | Auto *(or custom #hex)* | **Auto** | color of the value bar |

> Custom values per REQ-UI-OPT-01 (numbers / hex).

## Provenance & feasibility

- **Source:** Superset ("Bullet Chart").
- **Equivalent in:** Superset *Bullet* · conceptually close to DHIS2 *Gauge* (linear form).
- **Rendering:** custom Chart.js (stacked horizontal bar + target annotation) — no native type.
- **Difficulty / priority:** Medium · Low (overlaps `gauge`; build one or the other first).
- **Notes:** Good dense KPI tile; shares the target/range model with `gauge`.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_bullet_checklist.py`.
- E2E: `tests/e2e/test_render_bullet.py`.
- REQ ids: REQ-BULLET-RENDER-01, REQ-BULLET-TARGET-01, REQ-BULLET-RANGES-01, REQ-BULLET-MAX-01.
