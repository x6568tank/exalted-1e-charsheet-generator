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

from fastapi.responses import HTMLResponse, RedirectResponse
from nicegui import __version__ as nicegui_version
from nicegui import app
from nicegui.storage import request_contextvar

from ..ui import theme
from . import db, nav

SITE_NAME = "Exalted 1e"


def esc(value: object) -> str:
    """Return `value` as text that is safe in HTML content and in a quoted attribute."""
    return escape(str(value), quote=True)


def href(path: str, **params: object) -> str:
    """Return `path` with the query parameters in `params` that are not empty."""
    query = urlencode({k: v for k, v in params.items() if v not in ("", None)})
    return f"{path}?{query}" if query else path


def replace_route(path: str, endpoint, *, name: str) -> None:
    """Add a GET and HEAD route for `path` that returns HTML. Remove each earlier
    route of `path` first.

    ⚠ HEAD is explicit. FastAPI does not add it to a GET route, and a monitor or a
    link checker that sends HEAD then gets 405.

    ⚠ Starlette uses the FIRST route that matches. Each call of
    `server/main.build_server` registers the routes again, and the tests call it
    more than once in one process. Without the removal the first ruleset stays in
    use. `ui.page` removes the earlier route in the same way.
    """
    app.remove_route(path)
    app.add_api_route(path, endpoint, methods=["GET", "HEAD"], response_class=HTMLResponse,
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


# --------------------------------------------------------------------------- #
# The site colours of the visitor
# --------------------------------------------------------------------------- #

THEME_PATH = "/theme"
# The cookie holds the Exalt type of the palette that the visitor selected. A visitor
# with no login has the cookie only. An account also keeps the value in the database,
# thus each device of the login shows it.
THEME_COOKIE = "site_theme"
_THEME_SECONDS = 400 * 24 * 3600


def _account():
    """Return (database path, account id) of the current request, or None."""
    from . import auth                               # auth imports this module
    user_id = auth.current_user_id()
    path = auth.db_path()
    return None if user_id is None or path is None else (path, user_id)


def visitor_theme() -> str:
    """Return the Exalt type of the site colours of the current request, or "".

    The colours of the account come first, then the cookie. A request with no
    login has the cookie only. No request, for example a timer, gives "".
    ⚠ A value that is not a palette gives "". The cookie comes from the browser.
    """
    request = request_contextvar.get()
    if request is None:
        return ""
    account = _account()
    value = (db.theme_for(*account) if account is not None else None) \
        or request.cookies.get(THEME_COOKIE, "")
    return value if value in theme.splat_keys() else ""


def site_palette() -> theme.Palette:
    """Return the palette of a page that shows no one splat: the site colours of
    the visitor, or the default palette."""
    return theme.palette(visitor_theme() or None)


def _here() -> str:
    """Return the path and the query of the current request, or "/"."""
    request = request_contextvar.get()
    if request is None:
        return "/"
    query = request.url.query
    return request.url.path + (f"?{query}" if query else "")


def _local(path: str) -> str:
    """Return `path` if it is a path of this server. Return "/" in all other cases.

    ⚠ An absolute URL sends the browser to any site. "//host" is an absolute URL too.
    """
    if not path or not path.startswith("/") or path.startswith("//") or "\\" in path:
        return "/"
    return path


def theme_href(splat: str, back: str = "") -> str:
    """Return the address that selects the site colours of `splat` and then opens
    `back`. An empty `back` gives the current page."""
    return href(THEME_PATH, splat=splat, back=_local(back or _here()))


def theme_swatches(back: str = "") -> str:
    """Return a row of colour swatches. Each swatch is a link that selects the site
    colours of one splat. The swatch of the current colours has a ring."""
    current = visitor_theme() or "Solar"
    links = []
    for splat in theme.splat_keys():
        pal = theme.palette(splat)
        on = ' class="on" aria-current="true"' if splat == current else ""
        links.append(f'<a href="{esc(theme_href(splat, back))}"{on} '
                     f'title="{esc(pal.splat_label)}" aria-label="{esc(pal.splat_label)} colours" '
                     f'style="--c:{pal.accent};--b:{pal.bg}"></a>')
    return f'<div class="swatches">{"".join(links)}</div>'


def theme_choices(back: str = "") -> str:
    """Return one labelled link for each splat palette. Each link selects the site
    colours of that splat. The link of the current colours is marked."""
    current = visitor_theme() or "Solar"
    links = []
    for splat in theme.splat_keys():
        pal = theme.palette(splat)
        on = ' class="on" aria-current="true"' if splat == current else ""
        links.append(f'<a href="{esc(theme_href(splat, back))}"{on} '
                     f'data-splat="{esc(splat)}" style="--c:{pal.accent};--b:{pal.bg}">'
                     f'<span class="dot"></span>{esc(pal.splat_label)}</a>')
    return f'<div class="theme-grid">{"".join(links)}</div>'


def _select_theme(splat: str = "", back: str = "/") -> RedirectResponse:
    response = RedirectResponse(_local(back), status_code=303)
    if splat not in theme.splat_keys():
        splat = ""
    account = _account()
    if account is not None:
        db.set_theme(*account, splat)
    if splat:
        response.set_cookie(THEME_COOKIE, splat, max_age=_THEME_SECONDS, path="/",
                            samesite="lax", httponly=True)
    else:
        response.delete_cookie(THEME_COOKIE, path="/")
    return response


def register_theme_route() -> None:
    """Register `THEME_PATH`. Replace an earlier route of the path.

    `?splat=` sets the cookie, and the colours of the account if there is a login.
    An unknown value removes both. `?back=` gives the page that opens after it.
    """
    app.remove_route(THEME_PATH)
    app.add_api_route(THEME_PATH, _select_theme, methods=["GET"], name="theme",
                      include_in_schema=False)


def _palette_css(exalt_type: str) -> str:
    """Return the CSS variables of the builder palette of `exalt_type`. An empty
    `exalt_type` gives the site colours of the visitor."""
    pal = theme.palette(exalt_type or visitor_theme() or None)
    tint, edge = _FAMILY.get(pal.fam, _FAMILY["amber"])
    return (f":root{{--accent:{pal.accent};--accent-dark:{pal.accent_dark};--ink:{pal.ink};"
            f"--bg:{pal.bg};--node:{pal.node_bg};--tint:{tint};--edge:{edge};}}")


# The swatches of the site colours. The NiceGUI menu adds this CSS too, thus it names
# no variable of `_palette_css`.
SWATCH_CSS = """
.colours { padding: 6px 16px 4px; }
.colours .cap { font-size: 12px; margin: 0 0 6px; opacity: .7; }
.swatches { display: flex; flex-wrap: wrap; gap: 8px; }
.swatches a {
  display: block; width: 24px; height: 24px; border-radius: 50%; background: var(--c);
  border: 3px solid var(--b); box-shadow: 0 0 0 1px rgba(0,0,0,.25);
  transition: transform .1s;
}
.swatches a:hover { transform: scale(1.15); text-decoration: none; }
.swatches a.on { box-shadow: 0 0 0 2px currentColor; }
"""

_CSS = SWATCH_CSS + """
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
.bar { position: sticky; top: 0; z-index: 20; }
.bar .title { font-size: 18px; font-weight: 700; color: #fff; }
.bar nav.quick { display: flex; flex-wrap: wrap; gap: 0 .25rem; }

/* The site menu: a drawer below the header bar */
.menu summary {
  display: flex; align-items: center; gap: 10px; list-style: none; cursor: pointer;
  color: #fff; padding: 6px 10px 6px 6px; margin-left: -6px; border-radius: 4px; user-select: none;
}
.menu summary::-webkit-details-marker { display: none; }
.menu summary:hover, .menu[open] summary { background: rgba(255,255,255,.12); }
.menu .scrim { position: fixed; inset: 0; background: rgba(0,0,0,.4); z-index: 21; }
.drawer {
  position: fixed; top: 0; bottom: 0; left: 0; width: 280px; max-width: 85vw; overflow-y: auto;
  z-index: 22; padding: 0 0 8px; background: var(--bg); color: var(--ink);
  box-shadow: 0 8px 10px -5px rgba(0,0,0,.2), 0 16px 24px 2px rgba(0,0,0,.14), 0 6px 30px 5px rgba(0,0,0,.12);
}
.drawer .head {
  display: flex; align-items: center; gap: 10px; height: 64px; padding: 0 16px; margin-bottom: 8px; flex-shrink: 0;
  background: var(--accent); color: #fff; font-size: 18px; font-weight: 700; cursor: pointer; user-select: none;
}
.drawer a { display: flex; align-items: center; gap: 16px; min-height: 48px; padding: 8px 16px; color: var(--ink); font-weight: 500; }
.drawer a:hover { background: rgba(0,0,0,.05); text-decoration: none; }
.drawer a .mi { color: var(--accent); font-size: 22px; }
.drawer a.sub { min-height: 32px; padding: 4px 16px 4px 40px; font-weight: 400; font-size: 13.5px; }
.drawer a.sub .mi { font-size: 18px; opacity: .8; }
.drawer a.on { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent); }
.drawer a .ext { margin-left: auto; font-size: 16px; color: inherit; opacity: .5; }
.drawer .who { display: flex; align-items: center; gap: 16px; min-height: 40px; padding: 8px 16px; color: var(--ink); opacity: .75; font-size: 13.5px; }
.drawer .who .mi { color: var(--accent); font-size: 22px; }
/* ⚠ The rules of `.drawer a` match the swatches too. These undo them. */
.drawer .swatches a { min-height: 0; padding: 0; }
.drawer .swatches a.on { background: var(--c); }
.drawer hr { border: 0; border-top: 1px solid color-mix(in srgb, var(--edge) 18%, transparent); margin: 6px 0; }
.btn {
  display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 4px;
  color: #fff; font-weight: 500; font-size: 14px; text-transform: uppercase; letter-spacing: .0892em;
}
.btn:hover { background: rgba(255,255,255,.12); text-decoration: none; }
.btn .mi { font-size: 22px; }
.btn.on { background: rgba(255,255,255,.18); }

/* The tab strip of the builder */
.tabs { display: flex; flex-wrap: wrap; justify-content: center; gap: 0; margin: 4px 0 16px; }
.tabs::-webkit-scrollbar { display: none; }
.tab {
  display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 12px 12px 10px;
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

/* The login and signup pages. They are NiceGUI pages, thus Quasar draws the fields. */
.auth { max-width: 400px; margin: 40px auto 0; padding: 20px 24px 22px; }
.auth h1 { color: var(--accent); font-size: 20px; line-height: 1.3; font-weight: 700; letter-spacing: normal; margin: 0 0 2px; }
.auth .lead { font-size: 14px; margin: 0 0 8px; }
.auth .aside { margin: 14px -24px -22px; padding: 12px 24px; font-size: 13px;
  border-top: 1px solid color-mix(in srgb, var(--edge) 15%, transparent); }
.auth .aside p { margin: 0; }
.auth .aside p + p { margin-top: 6px; }
.auth + .auth { margin-top: 16px; }
.auth.danger h1 { color: #b91c1c; }
/* The account page: a grid of the form cards */
.account-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px;
  max-width: 1100px; margin: 32px auto 0; align-items: stretch;
}
.account-grid .auth { max-width: none; margin: 0; display: flex; flex-direction: column; }
.account-grid .auth + .auth { margin-top: 0; }
.account-grid .auth > .q-btn { margin-top: auto !important; }
.account-grid .auth > :nth-last-child(2) { margin-bottom: 16px; }
.account-grid .auth.danger { border-top: 3px solid #b91c1c; }
.theme-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(128px, 1fr)); gap: 6px; margin-top: 8px; }
.theme-grid a {
  display: flex; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 4px; color: var(--ink);
  border: 1px solid color-mix(in srgb, var(--edge) 18%, transparent); font-size: 13.5px;
}
.theme-grid a:hover { background: rgba(0,0,0,.04); text-decoration: none; }
.theme-grid a.on { border-color: var(--accent); background: color-mix(in srgb, var(--accent) 12%, transparent); font-weight: 500; }
.theme-grid .dot {
  flex: none; width: 16px; height: 16px; border-radius: 50%; background: var(--c);
  border: 2px solid var(--b); box-shadow: 0 0 0 1px rgba(0,0,0,.25);
}
.auth ul.campaigns { margin: 0 0 4px; padding-left: 20px; font-size: 14px; list-style: disc; }

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
h2.ref { font-size: 14px; font-weight: 700; margin: 16px 0 4px; }
h2.ref:first-of-type { margin-top: 4px; }
.table.ref td:first-child { font-weight: 500; }
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
  .bar nav.quick { display: none; }
  .btn .t { display: none; }
  .btn { padding: 6px 8px; }
  .tabs { flex-wrap: nowrap; justify-content: flex-start; overflow-x: auto; scrollbar-width: none; }
  .tab { padding: 10px 12px 8px; font-size: 12px; }
  .table thead { display: none; }
  .table, .table tbody, .table tr, .table td { display: block; }
  .table tr { padding: 6px 0; border-bottom: 1px solid color-mix(in srgb, var(--edge) 15%, transparent); }
  .table td { border: 0; padding: 0; display: inline; }
  .table td.name { display: block; }
  .table td:not(.name)::before { content: attr(data-label) ": "; color: color-mix(in srgb, var(--ink) 62%, transparent); font-size: 12px; }
  .table td:not(.name):not(:last-child)::after { content: " · "; }
  .table td.nil { display: none; }
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
    """Return the buttons of the header bar: the account controls only. The site
    menu holds the places. `current` is the section of the page."""
    if username:
        return _button("/logout", "account_circle", nav.logout_label(username))
    return (_button("/login", "login", "Log in", current == "login")
            + _button("/signup", "person_add", "Sign up", current == "signup"))


def style_sheet(splat: str = "") -> str:
    """Return the CSS of the public pages, with the builder palette of `splat`."""
    return _palette_css(splat) + _CSS


def _colours_html() -> str:
    return (f'<hr><div class="colours" data-testid="nav-colours">'
            f'<p class="cap muted">Site colours</p>{theme_swatches()}</div>')


def drawer_html(username: Optional[str], current: str = "", *, live: bool = False) -> str:
    """Return the links of the site menu. `current` marks the entry of that key.

    The swatches of the site colours come before the build line. `live` removes
    them: a swatch opens the page again, and a live page holds work in progress.
    """
    parts = []
    groups = nav.groups(username, live=live)
    colours = nav.colours_position(groups) if not live else -1
    for number, group in enumerate(groups):
        if number == colours:
            parts.append(_colours_html())
        if number:
            parts.append("<hr>")
        for link in group:
            classes = " ".join(c for c in ("sub" if link.sub else "",
                                           "on" if current and link.key == current else "")
                               if c)
            attrs = f' class="{classes}"' if classes else ""
            if current and link.key == current:
                attrs += ' aria-current="page"'
            if not link.href:
                parts.append(f'<div class="who">{icon(link.icon)}'
                             f"<span>{esc(link.label)}</span></div>")
                continue
            if link.new_tab:
                attrs += ' target="_blank" rel="noopener"'
            tail = icon("open_in_new", "ext") if link.new_tab else ""
            parts.append(f'<a href="{esc(link.href)}"{attrs}>{icon(link.icon)}'
                         f"<span>{esc(link.label)}</span>{tail}</a>")
    if colours == len(groups):
        parts.append(_colours_html())
    return "".join(parts)


def header_bar(current: str, username: Optional[str], heading: str = SITE_NAME) -> str:
    """Return the header bar of a public page, with the site menu. `current` marks
    one button and one menu entry.

    ⚠ The menu is a `<details>` element, thus it opens with no script. `MENU_SCRIPT`
    closes it: on Escape, on the scrim, and on the head of the drawer.
    """
    return (f'<header class="bar"><details class="menu">'
            f'<summary aria-label="Site menu" data-testid="nav-menu">{icon("menu")}'
            f'<span class="title">{esc(heading)}</span></summary>'
            f'<div class="scrim"></div>'
            f'<nav class="drawer" aria-label="Site menu"><div class="head shut">{icon("menu")}'
            f"<span>{esc(SITE_NAME)}</span></div>{drawer_html(username, current)}</nav>"
            f'</details><nav class="quick" aria-label="Site">{_nav(current, username)}</nav>'
            "</header>")


# Close each open site menu on Escape and on a click on the scrim or on the head of
# the drawer (class "shut"). The listeners are
# on the document, thus the script works before and after the menu is in the page.
MENU_SCRIPT = (
    "<script>(function(){function shut(){document.querySelectorAll('details.menu[open]')"
    ".forEach(function(d){d.open=false;});}"
    "document.addEventListener('click',function(e){if(e.target.closest&&"
    "e.target.closest('.scrim, .shut'))shut();});"
    "document.addEventListener('keydown',function(e){if(e.key==='Escape')shut();});"
    "})();</script>")


FOOTER = ('<footer class="footer muted">An unofficial fan site, not affiliated with the '
          'publisher of Exalted. <a href="/about">About this site</a>.</footer>')


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
        f"<style>{style_sheet(splat)}</style></head><body>"
        f"{header_bar(current, username, heading)}"
        f'<main class="page">{body}</main>{FOOTER}{MENU_SCRIPT}'
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
