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

# Match both single-quoted and double-quoted attribute values
_Q = r"""["']"""          # opening quote (either)
_NQ = r"""[^"']*"""       # non-quote characters


def fix_cdn_links(html: str) -> str:
    """
    Replace any relative / _files/ Bootstrap and Chart.js references
    with correct CDN absolute URLs.

    Handles:
    - Browser "Save As Complete Webpage" (_files/ rewrite)
    - Both single-quoted and double-quoted attribute values
    - Any path that contains 'bootstrap' or 'chart' and ends with .js/.css
      but is NOT already an absolute http/https URL
    """
    # Bootstrap CSS
    html = re.sub(
        rf'href={_Q}(?!https?://)({_NQ}bootstrap{_NQ}\.css{_NQ}){_Q}',
        f'href="{_CDN_BOOTSTRAP_CSS}"',
        html, flags=re.IGNORECASE,
    )
    # Bootstrap JS bundle
    html = re.sub(
        rf'src={_Q}(?!https?://)({_NQ}bootstrap{_NQ}\.js{_NQ}){_Q}',
        f'src="{_CDN_BOOTSTRAP_JS}"',
        html, flags=re.IGNORECASE,
    )
    # Chart.js — match chart.umd.min.js, chart.js, 1_files/chart.umd.min.js, etc.
    html = re.sub(
        rf'src={_Q}(?!https?://)({_NQ}chart{_NQ}\.js{_NQ}){_Q}',
        f'src="{_CDN_CHARTJS}"',
        html, flags=re.IGNORECASE,
    )
    return html
