"""Post-processing helpers for generated DHIS2 HTML reports."""
from __future__ import annotations
import re

_CDN_BOOTSTRAP_CSS = (
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css"
)
_CDN_BOOTSTRAP_JS = (
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"
)
_CDN_CHARTJS = (
    "https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"
)

# Match both single-quoted and double-quoted attribute values.
# Allow optional whitespace around the = sign (e.g. src = "...").
_Q  = r"""["']"""           # opening/closing quote (single or double)
_EQ = r"""\s*=\s*"""        # equals sign with optional surrounding spaces
_NQ = r"""[^"']*"""         # non-quote characters (matches _files/ paths etc.)


def fix_cdn_links(html: str) -> str:
    """
    Replace any relative / _files/ Bootstrap and Chart.js references
    with correct CDN absolute URLs.

    Handles:
    - Browser "Save As Complete Webpage" (_files/ rewrite, e.g. 2_files/)
    - Both single-quoted and double-quoted attribute values
    - Optional spaces around the = sign  (src = "..." or src="...")
    - Any path containing 'bootstrap'/'chart' ending in .js/.css that is
      NOT already an absolute http/https URL
    """
    # Bootstrap CSS
    html = re.sub(
        rf'href{_EQ}{_Q}(?!https?://)({_NQ}bootstrap{_NQ}\.css{_NQ}){_Q}',
        f'href="{_CDN_BOOTSTRAP_CSS}"',
        html, flags=re.IGNORECASE,
    )
    # Bootstrap JS bundle
    html = re.sub(
        rf'src{_EQ}{_Q}(?!https?://)({_NQ}bootstrap{_NQ}\.js{_NQ}){_Q}',
        f'src="{_CDN_BOOTSTRAP_JS}"',
        html, flags=re.IGNORECASE,
    )
    # Chart.js — match chart.umd.min.js, chart.js, 2_files/chart.umd.min.js, etc.
    html = re.sub(
        rf'src{_EQ}{_Q}(?!https?://)({_NQ}chart{_NQ}\.js{_NQ}){_Q}',
        f'src="{_CDN_CHARTJS}"',
        html, flags=re.IGNORECASE,
    )
    return html
