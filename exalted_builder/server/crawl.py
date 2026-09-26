"""
server/crawl.py — the two files for search engines: `/robots.txt` and `/sitemap.xml`.

The sitemap lists the public pages: the front page, About, the wiki sections and
each wiki entry. `robots.txt` closes the pages of an account to crawlers.

⚠ The gate lets a visitor open both paths (`auth.OPEN_PATHS`).
"""

from __future__ import annotations

from xml.sax.saxutils import escape

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response
from nicegui import app

from ..models.rules import RuleSet
from ..ui import wiki_view as wv
from . import nav

ROBOTS_PATH = "/robots.txt"
SITEMAP_PATH = "/sitemap.xml"

# The paths that a crawler must not open. Each needs a login, or sets up a login.
# ⚠ Do not close "/_nicegui/". The public pages load their icon font from it.
_CLOSED = ("/home", "/character/", "/table/", "/login", "/signup", "/logout",
           "/_nicegui_ws/")


def _base(request: Request) -> str:
    """Return the scheme and the host of the address that the visitor used.

    ⚠ The tunnel ends TLS before the server. It gives the scheme of the visitor in
    `X-Forwarded-Proto`. Without it, the request gives "http".
    """
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme).split(",")[0]
    host = request.headers.get("host", request.url.netloc)
    return f"{scheme.strip()}://{host}"


def robots_text(base: str) -> str:
    """Return the text of `robots.txt` for the site at `base`."""
    lines = ["User-agent: *", "Allow: /"]
    lines.extend(f"Disallow: {path}" for path in _CLOSED)
    lines.extend(["", f"Sitemap: {base}{SITEMAP_PATH}"])
    return "\n".join(lines) + "\n"


def sitemap_xml(base: str, paths: list[str]) -> str:
    """Return a sitemap that lists `paths` at the site `base`."""
    urls = "".join(f"<url><loc>{escape(base + path)}</loc></url>" for path in paths)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')


def register_crawl_files(ruleset: RuleSet) -> None:
    """Register `/robots.txt` and `/sitemap.xml`. Replace earlier routes of the paths.

    ⚠ `ruleset` must be the wiki's BOOK ruleset, with no homebrew. The sitemap is
    public. Calculate the paths one time, here: the book does not change while the
    server runs.
    """
    paths = [nav.FRONT_PATH, nav.ABOUT_PATH, nav.WIKI_PATH]
    paths.extend(f"{nav.WIKI_PATH}/{slug}" for slug, _title in wv.SECTIONS)
    paths.extend(wv.entry_hrefs(ruleset))

    def robots(request: Request) -> PlainTextResponse:
        return PlainTextResponse(robots_text(_base(request)))

    def sitemap(request: Request) -> Response:
        return Response(sitemap_xml(_base(request), paths), media_type="application/xml")

    for path, endpoint, name in ((ROBOTS_PATH, robots, "robots"),
                                 (SITEMAP_PATH, sitemap, "sitemap")):
        app.remove_route(path)
        app.add_api_route(path, endpoint, methods=["GET", "HEAD"], name=name,
                          include_in_schema=False)
