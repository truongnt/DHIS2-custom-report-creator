# Gauge (`gauge`)

> Plugin: `charts/plugins/gauge.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> A radial dial showing one value against a min–max range, often a % toward a target.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`); types: aggregate / indicator / tracker_numeric; agg picker shown |
| Dimension | none |
| Time grain | none (single value for the selected period) |

## Options

From COMMON: `y_format`.

Gauge-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `min` | Min | 0 *(or custom number)* | **0** | start of the dial |
| `max` | Max | 100 *(or custom number)* | **100** | end of the dial (e.g. target or denominator) |
| `target` | Target | Off *(or custom number)* | **Off** | marker line on the arc |
| `bands` | Color bands | None / Traffic light / Sequential | **Traffic light** | red/amber/green thresholds vs single ramp |
| `arc` | Arc | Half / Three-quarter / Full | **Half** | sweep angle of the dial |
| `value_color` | Needle/fill color | Auto *(or custom #hex)* | **Auto** | overrides band color for the value arc |

> Custom values per REQ-UI-OPT-01 (numbers / hex). DHIS2 gauges show a % of a target/total.

## Provenance & feasibility

- **Source:** DHIS2 Data Visualizer ("Gauge"); Superset ("Gauge Chart").
- **Equivalent in:** DHIS2 *Gauge* · Superset *Gauge Chart*.
- **Rendering:** lib `chartjs-gauge` / `chartjs-plugin-doughnutlabel`, or a custom canvas arc (no native gauge in Chart.js core).
- **Difficulty / priority:** Medium · High (very common KPI viz, esp. coverage %).
- **Notes:** Decide the extra-lib vs custom-arc approach at implementation; load lib like Leaflet is loaded.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_gauge_checklist.py`.
- E2E: `tests/e2e/test_render_gauge.py`.
- REQ ids: REQ-GAUGE-RENDER-01, REQ-GAUGE-RANGE-01, REQ-GAUGE-TARGET-01, REQ-GAUGE-BANDS-01, REQ-GAUGE-ARC-01.
