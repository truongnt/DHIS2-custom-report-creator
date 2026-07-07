# Word cloud (`word_cloud`)

> Plugin: `charts/plugins/word_cloud.py` (proposed). Common controls/options: [COMMON.md](COMMON.md).
> Category labels sized by value and laid out without overlap — quick eyeball of relative magnitude.

## Data controls

| Control | Value |
|---|---|
| Metric | 1 (`max_count=1`) = word size; types: aggregate / indicator / tracker_numeric / tracker_option |
| Dimension | required — each option value becomes a word |
| Time grain | none (snapshot) |

## Options

From COMMON: `color_scheme`.

Word-cloud-specific:

| key | label | choices | default | behavior |
|---|---|---|---|---|
| `size_range` | Size range | Small / Medium / Large | **Medium** | min→max font size span |
| `rotation` | Word rotation | None / ±45 / Random | **None** | angle variety of words |
| `max_words` | Max words | 25 / 50 / 100 *(or custom int)* | **50** | cap on number of words (largest by value) |

> Custom value: `max_words` accepts a freeform integer (REQ-UI-OPT-01).

## Provenance & feasibility

- **Source:** Superset ("Word Cloud").
- **Equivalent in:** Superset *Word Cloud* (DHIS2 n/a).
- **Rendering:** `d3-cloud` layout (no Chart.js equivalent).
- **Difficulty / priority:** High · Low (niche; rarely used for clinical indicators).
- **Notes:** Lowest analytical value of the set; include for completeness only.

## Acceptance (to create on implementation)

- Checklist: `scripts/checklists/test_word_cloud_checklist.py`.
- E2E: `tests/e2e/test_render_word_cloud.py`.
- REQ ids: REQ-WORDCLOUD-RENDER-01, REQ-WORDCLOUD-SIZE-01, REQ-WORDCLOUD-ROTATION-01, REQ-WORDCLOUD-MAX-01.
