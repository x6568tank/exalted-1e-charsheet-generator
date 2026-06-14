"""
ui/assets.py — bundled front-end assets.

Vendors third-party JS locally so the app works offline and in a packaged build
(no CDN dependency). The Cytoscape source is read from ui/vendor/ and inlined
into the page head.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_VENDOR = Path(__file__).parent / "vendor"


@lru_cache(maxsize=1)
def cytoscape_head_html() -> str:
    """A <script> tag with the vendored Cytoscape source inlined."""
    js = (_VENDOR / "cytoscape.min.js").read_text(encoding="utf-8")
    return f"<script>{js}</script>"
