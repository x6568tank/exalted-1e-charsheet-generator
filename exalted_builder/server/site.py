"""
server/site.py — the HTML frame of the public pages.

The public pages are the front page, About and the wiki. Section 9.4 of
`docs/plans/vtt.md` gives the site map. Each public page is plain HTML that the
server makes for each request.

⚠ Plain HTML, not a NiceGUI page. A crawler reads plain HTML, and an anonymous
visitor then holds no NiceGUI client and no socket. See vtt.md section 9.5.

⚠ Escape each value that comes from data or from the request with `esc`. The
wiki shows book text and the search box shows the query of the visitor.

The pages copy the look of the NiceGUI builder: the accent header bar, the tab
strip, the tinted cards, Roboto and the Material icons. The colours come from
`ui/theme.palette`, thus a page for one splat has the palette of the builder for
that splat. The fonts are the files that NiceGUI serves.
"""

from __future__ import annotations

from html import escape
from typing import Optional
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse
from nicegui import __version__ as nicegui_version
from nicegui import app

from ..ui import theme

SITE_NAME = "Exalted 1e"


def esc(value: object) -> str:
    """Return `value` as text that is safe in HTML content and in a quoted attribute."""
    return escape(str(value), quote=True)


def href(path: str, **params: object) -> str:
    """Return `path` with the query parameters in `params` that are not empty."""
    query = urlencode({k: v for k, v in params.items() if v not in ("", None)})
    return f"{path}?{query}" if query else path


def replace_route(path: str, endpoint, *, name: str) -> None:
    """Add a GET route for `path` that returns HTML. Remove each earlier route of
    `path` first.

    ⚠ Starlette uses the FIRST route that matches. Each call of
    `server/main.build_server` registers the routes again, and the tests call it
    more than once in one process. Without the removal the first ruleset stays in
    use. `ui.page` removes the earlier route in the same way.
    """
    app.remove_route(path)
    app.add_api_route(path, endpoint, methods=["GET"], response_class=HTMLResponse,
                      name=name, include_in_schema=False)


# The Tailwind colours of each `Palette.fam`: (the 50 shade, the 900 shade). The
# builder tints its cards with these two shades. ⚠ These are Tailwind values, not
# a second palette. Add a row when `ui/theme.py` gets a new family.
_FAMILY = {
    "amber": ("#fffbeb", "#78350f"), "red": ("#fef2f2", "#7f1d1d"),
    "neutral": ("#fafafa", "#171717"), "slate": ("#f8fafc", "#0f172a"),
    "purple": ("#faf5ff", "#581c87"), "yellow": ("#fefce8", "#713f12"),
    "stone": ("#fafaf9", "#1c1917"), "zinc": ("#fafafa", "#18181b"),
    "teal": ("#f0fdfa", "#134e4a"), "emerald": ("#ecfdf5", "#064e3b"),
    "cyan": ("#ecfeff", "#164e63"),
}


def _palette_css(exalt_type: str) -> str:
    """Return the CSS variables of the builder palette of `exalt_type`."""
    pal = theme.palette(exalt_type or None)
    tint, edge = _FAMILY.get(pal.fam, _FAMILY["amber"])
    return (f":root{{--accent:{pal.accent};--accent-dark:{pal.accent_dark};--ink:{pal.ink};"
            f"--bg:{pal.bg};--node:{pal.node_bg};--tint:{tint};--edge:{edge};}}")


_CSS = """
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 14px/1.5 Roboto, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
.mi {
  font-family: "Material Icons"; font-weight: normal; font-style: normal; font-size: 24px;
  line-height: 1; letter-spacing: normal; text-transform: none; display: inline-block;
  white-space: nowrap; direction: ltr; -webkit-font-feature-settings: "liga"; font-feature-settings: "liga";
}

/* The header bar of the builder */
.bar {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap;
  gap: .25rem 1rem; min-height: 64px; padding-inline: 16px; background: var(--accent); color: #fff;
  box-shadow: 0 2px 4px -1px rgba(0,0,0,.2), 0 4px 5px rgba(0,0,0,.14), 0 1px 10px rgba(0,0,0,.12);
}
.bar .title { font-size: 18px; font-weight: 700; color: #fff; }
.bar .title:hover { text-decoration: none; }
.bar nav { display: flex; flex-wrap: wrap; gap: 0 .25rem; }
.btn {
  display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 4px;
  color: #fff; font-weight: 500; font-size: 14px; text-transform: uppercase; letter-spacing: .0892em;
}
.btn:hover { background: rgba(255,255,255,.12); text-decoration: none; }
.btn .mi { font-size: 22px; }
.btn.on { background: rgba(255,255,255,.18); }

/* The tab strip of the builder */
.tabs { display: flex; justify-content: center; gap: 0; overflow-x: auto; margin: 4px 0 16px; scrollbar-width: none; }
.tabs::-webkit-scrollbar { display: none; }
.tab {
  display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 12px 18px 10px;
  color: var(--ink); opacity: .85; font-weight: 500; text-transform: uppercase; letter-spacing: .0892em;
  font-size: 14px; white-space: nowrap; border-bottom: 2px solid transparent;
}
.tab:hover { text-decoration: none; background: rgba(0,0,0,.04); opacity: 1; }
.tab.on { opacity: 1; border-bottom-color: var(--ink); }
.tab .n { font-size: 11px; opacity: .7; letter-spacing: normal; }

.page { max-width: 1200px; margin: 0 auto; padding-inline: 16px; padding-block: 8px 40px; }
.card {
  background: color-mix(in srgb, var(--tint) 60%, var(--bg));
  border: 1px solid color-mix(in srgb, var(--edge) 30%, transparent); border-radius: 4px;
  box-shadow: 0 1px 5px rgba(0,0,0,.2), 0 2px 2px rgba(0,0,0,.14), 0 3px 1px -2px rgba(0,0,0,.12);
  padding: 16px; margin-bottom: 12px;
}
.card-title { color: var(--accent); font-weight: 700; font-size: 14px; letter-spacing: .05em; margin: 0 0 8px; }
.card-title .mark { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; background: var(--c); }
.muted { color: color-mix(in srgb, var(--ink) 62%, transparent); }
.footer { max-width: 1200px; margin: 0 auto; padding: 8px 16px 32px; font-size: 12px; }
.footer a { color: inherit; text-decoration: underline; }

/* The front page and About */
.narrow { max-width: 720px; margin: 24px auto 0; }
.lead { font-size: 16px; margin: 0; }
.list { display: flex; flex-direction: column; margin: 0 -16px -16px; }
.item {
  display: flex; align-items: center; gap: 16px; padding: 12px 16px; color: var(--ink);
  border-top: 1px solid color-mix(in srgb, var(--edge) 15%, transparent);
}
.item:hover { background: rgba(0,0,0,.04); text-decoration: none; }
.item .mi { color: var(--accent); }
.item .label { font-weight: 500; font-size: 15px; }
.item .caption { font-size: 12.5px; }
.item .go { margin-left: auto; opacity: .45; }
.prose p { margin: 0 0 10px; font-size: 15px; }

/* The wiki */
.filters { display: flex; flex-wrap: wrap; align-items: end; gap: 8px 20px; }
.field { display: flex; flex-direction: column; flex: 1 1 180px; min-width: 0; }
.field.wide { flex: 3 1 260px; }
.field span { font-size: 12px; color: color-mix(in srgb, var(--ink) 62%, transparent); }
.field input, .field select {
  font: inherit; font-size: 15px; padding: 6px 0; border: 0; border-bottom: 1px solid rgba(0,0,0,.24);
  background: transparent; color: var(--ink); border-radius: 0; max-width: 100%;
}
.field input:focus, .field select:focus { outline: none; border-bottom: 2px solid var(--accent); padding-bottom: 5px; }
.run {
  font: inherit; font-weight: 500; text-transform: uppercase; letter-spacing: .0892em; border: 0;
  border-radius: 4px; padding: 8px 16px; background: var(--accent); color: #fff; cursor: pointer;
  box-shadow: 0 1px 5px rgba(0,0,0,.2), 0 2px 2px rgba(0,0,0,.14);
}
.count { margin: 10px 0 0; font-size: 13px; }
.table { width: 100%; border-collapse: collapse; }
.table th, .table td { text-align: left; vertical-align: top; padding: 7px 12px 7px 0; border-bottom: 1px solid color-mix(in srgb, var(--edge) 15%, transparent); }
.table thead th { font-size: 12px; font-weight: 500; color: color-mix(in srgb, var(--ink) 62%, transparent); }
.table tr:last-child td { border-bottom: 0; }
.table td.name { font-weight: 500; min-width: 190px; }
.table td.dim { color: color-mix(in srgb, var(--ink) 70%, transparent); font-size: 13px; }
.pager { display: flex; gap: 16px; justify-content: center; align-items: center; margin-top: 12px; }
.crumbs { font-size: 13px; margin: 0 0 8px; }
.entry { max-width: 820px; margin: 0 auto; }
.entry h1 { font-size: 22px; margin: 0 0 12px; color: var(--accent); font-weight: 700; }
.stat { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; margin: 0 0 14px; padding: 10px 12px; border-radius: 4px; background: color-mix(in srgb, var(--node) 70%, transparent); border: 1px solid color-mix(in srgb, var(--edge) 15%, transparent); }
.stat dt { font-weight: 500; color: color-mix(in srgb, var(--ink) 62%, transparent); }
.stat dd { margin: 0; }
.entry .text p { margin: 0 0 10px; font-size: 15px; line-height: 1.6; white-space: pre-line; }
.entry ul { margin: 0; padding-left: 18px; }
.entry li { margin: 0 0 6px; font-size: 15px; white-space: pre-line; }
.source { margin: 12px 0 0; font-size: 12.5px; font-style: italic; }
.empty { padding: 8px 0; }
@media (max-width: 720px) {
  .btn .t { display: none; }
  .btn { padding: 6px 8px; }
  .tabs { justify-content: flex-start; }
  .tab { padding: 10px 12px 8px; font-size: 12px; }
  .table thead { display: none; }
  .table, .table tbody, .table tr, .table td { display: block; }
  .table tr { padding: 6px 0; border-bottom: 1px solid color-mix(in srgb, var(--edge) 15%, transparent); }
  .table td { border: 0; padding: 0; display: inline; }
  .table td.name { display: block; }
  .table td:not(.name)::before { content: attr(data-label) ": "; color: color-mix(in srgb, var(--ink) 62%, transparent); font-size: 12px; }
  .table td:not(.name):not(:last-child)::after { content: " · "; }
  .stat { grid-template-columns: minmax(0, 1fr); gap: 0; }
  .stat dd { margin-bottom: 4px; }
}
"""

_FONTS = f'<link rel="stylesheet" href="/_nicegui/{nicegui_version}/static/fonts.css">'


def icon(name: str, extra: str = "") -> str:
    """Return a Material icon, as the builder shows it. `extra` adds CSS classes."""
    classes = f"mi {extra}".strip()
    return f'<span class="{classes}" aria-hidden="true">{esc(name)}</span>'


def _button(link: str, glyph: str, label: str, on: bool = False) -> str:
    mark = ' class="btn on" aria-current="page"' if on else ' class="btn"'
    return f'<a href="{link}"{mark}>{icon(glyph)}<span class="t">{esc(label)}</span></a>'


def _nav(current: str, username: Optional[str]) -> str:
    """Return the buttons of the header bar. `current` is the section of the page."""
    parts = [_button("/wiki", "menu_book", "Wiki", current == "wiki"),
             _button("/about", "info", "About", current == "about")]
    if username:
        parts.append(_button("/home", "edit", "Your characters"))
        parts.append(_button("/logout", "logout", "Log out"))
    else:
        parts.append(_button("/login", "login", "Log in"))
        parts.append(_button("/signup", "person_add", "Sign up"))
    return "".join(parts)


def page(title: str, body: str, *, current: str = "", username: Optional[str] = None,
         description: str = "", heading: str = SITE_NAME, splat: str = "") -> HTMLResponse:
    """Return a complete public page.

    `title` goes in the browser tab. `body` is HTML that the caller escaped.
    `current` marks one button of the header bar. `username` selects the buttons
    for a visitor with a login. `description` is the summary that a search engine
    shows. `heading` is the text of the header bar. `splat` selects the builder
    palette of that Exalt type; "" gives the default palette.
    """
    meta = f'<meta name="description" content="{esc(description[:300])}">' if description else ""
    html = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)}</title>{meta}{_FONTS}"
        f"<style>{_palette_css(splat)}{_CSS}</style></head><body>"
        f'<header class="bar"><a class="title" href="/">{esc(heading)}</a>'
        f'<nav aria-label="Site">{_nav(current, username)}</nav></header>'
        f'<main class="page">{body}</main>'
        '<footer class="footer muted">An unofficial fan site, not affiliated with the '
        'publisher of Exalted. <a href="/about">About this site</a>.</footer>'
        "</body></html>")
    return HTMLResponse(html)


def item_list(items: list[tuple[str, str, str, str]]) -> str:
    """Return a list of links in the style of a Quasar list. Each item is
    (address, icon, label, caption)."""
    rows = "".join(
        f'<a class="item" href="{esc(link)}">{icon(glyph)}<span><div class="label">'
        f'{esc(label)}</div><div class="caption muted">{esc(caption)}</div></span>'
        f'{icon("chevron_right", "go")}</a>'
        for link, glyph, label, caption in items)
    return f'<div class="list">{rows}</div>'


def not_found(title: str, username: Optional[str], current: str = "") -> HTMLResponse:
    """Return a 404 page with a link back to the wiki."""
    response = page(f"Not found — {SITE_NAME}",
                    f'<div class="card narrow"><p class="card-title">Not found</p>'
                    f"<p>{esc(title)}</p><p><a href=\"/wiki\">Go to the wiki</a></p></div>",
                    current=current, username=username)
    response.status_code = 404
    return response
