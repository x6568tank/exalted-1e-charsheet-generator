"""
server/wiki.py — the public wiki of the hosted server.

Section 9.5 of `docs/plans/vtt.md`. The routes under `/wiki` need no login. They
return plain HTML. `ui/wiki_view.py` supplies the content, and this module only
renders it.

⚠ BOOK DATA ONLY. `register_wiki` must receive a ruleset with no custom layer,
from `rules_db.load_ruleset`. `rules_db.load_app_ruleset` merges the homebrew
library of the process, and a wiki that reads it publishes the homebrew of each
player. `tests/test_public_pages.py` authors a custom Charm and asserts that the
wiki does not show it.
"""

from __future__ import annotations

from typing import Callable, Optional

from ..models.rules import RuleSet
from ..ui import wiki_view as wv
from . import auth
from .site import SITE_NAME, esc, href, icon, item_list, not_found, page, replace_route

_WIKI = f"{SITE_NAME} Wiki"
_HEADING = f"{SITE_NAME} — Wiki"

# The icon of each section in the tab strip. "Merits & Flaws" takes the icon of the
# builder's Advantages tab, and "Charms" the icon of its Charms tab.
_TAB_ICONS = {"charms": "account_tree", "martial-arts": "sports_martial_arts",
              "spells": "auto_fix_high", "merits": "workspace_premium",
              "backgrounds": "diversity_3"}


def _mark(accent: str) -> str:
    """Return the small square in the colour of a splat, or "" for no colour."""
    return f'<span class="mark" style="--c:{esc(accent)}"></span>' if accent else ""


def _keep_together(value: str) -> str:
    """Return `value` with the spaces in each short comma-separated item made
    non-breaking. Thus "Melee 2, Essence 1" breaks only after the comma."""
    return ", ".join(item.replace(" ", "\u00a0") if len(item) <= 16 else item
                     for item in value.split(", "))


def _table(columns: list[str], rows: list[wv.Row]) -> str:
    """Return an HTML table of `rows`, with no group headings."""
    head = "".join(f'<th scope="col">{esc(c)}</th>' for c in ["Name", *columns])
    body = []
    for row in rows:
        cells = "".join(f'<td class="dim" data-label="{esc(label)}">{esc(value)}</td>'
                        if label == wv.SUMMARY else
                        f'<td data-label="{esc(label)}">{esc(_keep_together(value))}</td>'
                        for label, value in zip(columns, row.cells))
        body.append(f'<tr><td class="name"><a href="{esc(row.href)}">{esc(row.title)}</a></td>'
                    f"{cells}</tr>")
    return (f'<table class="table"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def _group_cards(columns: list[str], rows: list[wv.Row]) -> str:
    """Return one card for each group of `rows`, in order. Rows with no group go in
    one card with no title."""
    cards, group, members = [], None, []

    def flush() -> None:
        if members:
            title = (f'<p class="card-title">{_mark(members[0].accent)}{esc(group)}</p>'
                     if group else "")
            cards.append(f'<section class="card">{title}{_table(columns, members)}</section>')

    for row in rows:
        if row.group != group:
            flush()
            group, members = row.group, []
        members.append(row)
    flush()
    return "".join(cards)


def _tabs(ruleset: RuleSet, current: str) -> str:
    """Return the tab strip of the wiki sections, in the style of the builder."""
    tabs = []
    for section in wv.section_counts(ruleset):
        on = ' class="tab on" aria-current="page"' if section.slug == current else ' class="tab"'
        tabs.append(f'<a href="/wiki/{section.slug}"{on}>{icon(_TAB_ICONS[section.slug])}'
                    f'<span>{esc(section.title)}</span><span class="n">{section.count:,}</span></a>')
    return f'<nav class="tabs" aria-label="Wiki sections">{"".join(tabs)}</nav>'


def _filter_card(action: str, listing: wv.ListPage) -> str:
    fields = [f'<label class="field wide"><span>Search {esc(listing.title.lower())}</span>'
              f'<input type="search" name="q" value="{esc(listing.query)}"></label>']
    for f in listing.filters:
        options = [f'<option value="">{esc(f.label)}</option>']
        options += [f'<option value="{esc(o.value)}"{" selected" if o.value == f.value else ""}>'
                    f"{esc(o.label)}</option>" for o in f.options]
        fields.append(f'<label class="field"><span>{esc(f.title or f.label)}</span>'
                      f'<select name="{esc(f.name)}" onchange="this.form.submit()">'
                      f'{"".join(options)}</select></label>')
    noun = "entry" if listing.total == 1 else "entries"
    return (f'<section class="card"><p class="card-title">{esc(listing.title)}</p>'
            f'<form class="filters" method="get" action="{esc(action)}" role="search">'
            f'{"".join(fields)}<button class="run" type="submit">Search</button></form>'
            f'<p class="count muted">{listing.total:,} {noun}</p></section>')


def _pager(action: str, listing: wv.ListPage) -> str:
    if listing.pages <= 1:
        return ""
    params = {f.name: f.value for f in listing.filters}
    params["q"] = listing.query

    def link(number: int, glyph: str, text: str) -> str:
        return (f'<a class="run" href="{esc(href(action, **params, page=number))}">'
                f"{text}</a>")

    parts = []
    if listing.page > 1:
        parts.append(link(listing.page - 1, "chevron_left", "Previous"))
    parts.append(f'<span class="muted">Page {listing.page} of {listing.pages}</span>')
    if listing.page < listing.pages:
        parts.append(link(listing.page + 1, "chevron_right", "Next"))
    return f'<nav class="pager" aria-label="Pages">{"".join(parts)}</nav>'


def _list_page(ruleset: RuleSet, listing: wv.ListPage, description: str):
    """Return a list page. `description` goes to search engines only."""
    action = f"/wiki/{listing.section}"
    results = (_group_cards(listing.columns, listing.rows) if listing.rows
               else '<section class="card empty muted">Nothing matches this search.</section>')
    content = (f"{_tabs(ruleset, listing.section)}{_filter_card(action, listing)}"
               f"{results}{_pager(action, listing)}")
    return page(f"{listing.title} — {_WIKI}", content, current="wiki",
                username=auth.current_username(), description=description,
                heading=_HEADING, splat=listing.theme)


def _prerequisite_line(groups: list[list[wv.Link]]) -> str:
    """Return the prerequisites as the book prints them: groups separated by commas,
    the choices in one group joined by "or"."""
    return ", ".join(
        " or ".join(f'<a href="{esc(link.href)}">{esc(link.text)}</a>' if link.href
                    else esc(link.text) for link in group)
        for group in groups)


def _entry_page(ruleset: RuleSet, entry: wv.EntryPage):
    section_title = dict(wv.SECTIONS)[entry.section]
    lines = [f"<dt>{esc(f.label)}</dt><dd>{esc(f.value)}</dd>" for f in entry.facts]
    if entry.section == "charms":
        prerequisites = _prerequisite_line(entry.prerequisites) or "None"
        lines.append(f"<dt>Prerequisite Charms</dt><dd>{prerequisites}</dd>")
    stat = f'<dl class="stat">{"".join(lines)}</dl>' if lines else ""
    text = "".join(f"<p>{esc(p)}</p>" for p in entry.paragraphs)
    extra = ""
    if entry.extra_lines:
        items = "".join(f"<li>{esc(line)}</li>" for line in entry.extra_lines)
        extra = f'<p class="card-title" style="margin-top:14px">{esc(entry.extra_title)}</p><ul>{items}</ul>'
    source = f'<p class="source muted">{esc(entry.source)}</p>' if entry.source else ""
    charms = (f'<section class="card"><p class="card-title">Charms</p>'
              f"{_table(entry.columns, entry.rows)}</section>" if entry.rows else "")
    content = (f"{_tabs(ruleset, entry.section)}<div class=\"entry\">"
               f'<p class="crumbs"><a href="/wiki">Wiki</a> › '
               f'<a href="/wiki/{entry.section}">{esc(section_title)}</a></p>'
               f'<article class="card"><p class="card-title">{_mark(entry.accent)}'
               f"{esc(entry.kicker)}</p><h1>{esc(entry.title)}</h1>{stat}"
               f'<div class="text">{text}</div>{extra}{source}</article>{charms}</div>')
    description = entry.paragraphs[0] if entry.paragraphs else entry.title
    return page(f"{entry.title} — {_WIKI}", content, current="wiki",
                username=auth.current_username(), description=description,
                heading=_HEADING, splat=entry.theme)


_SECTION_CAPTIONS = {
    "charms": "Every Charm, by Exalt type and category",
    "martial-arts": "The styles, their form rules and their Charm trees",
    "spells": "Sorcery, necromancy and the Alchemical protocols, by Circle",
    "merits": "The Merits and Flaws",
    "backgrounds": "Each Background and the text of each rating",
}


def _index_page(ruleset: RuleSet, q: str = ""):
    search = ('<section class="card"><p class="card-title">Search the wiki</p>'
              '<form class="filters" method="get" action="/wiki" role="search">'
              f'<label class="field wide"><span>Words to find</span><input type="search" '
              f'name="q" value="{esc(q)}"></label>'
              '<button class="run" type="submit">Search</button></form></section>')
    if q.strip():
        sections = []
        for listing, action in wv.search_all(ruleset, q):
            more = (f'<p><a href="{esc(href(action, q=q))}">All {listing.total:,} '
                    f"results in {esc(listing.title)}</a></p>"
                    if listing.total > len(listing.rows) else "")
            sections.append(f'<section class="card"><p class="card-title">{esc(listing.title)}'
                            f"</p>{_table(listing.columns, listing.rows)}{more}</section>")
        results = "".join(sections) or '<section class="card empty muted">Nothing matches this search.</section>'
    else:
        items = [(f"/wiki/{s.slug}", _TAB_ICONS[s.slug], f"{s.title} ({s.count:,})",
                  _SECTION_CAPTIONS[s.slug]) for s in wv.section_counts(ruleset)]
        results = (f'<section class="card"><p class="card-title">Sections</p>'
                   f"{item_list(items)}</section>")
    content = f'{_tabs(ruleset, "")}<div class="entry">{search}{results}</div>'
    return page(_WIKI, content, current="wiki", username=auth.current_username(),
                heading=_HEADING,
                description="Charms, spells, martial arts, Merits and Flaws, and "
                            "Backgrounds for Exalted First Edition.")


def _entry_route(ruleset: RuleSet, lookup: Callable[[RuleSet, str], Optional[wv.EntryPage]]):
    """Return an endpoint that shows the entry with the id of the path, or a 404."""
    def endpoint(entry_id: str):
        entry = lookup(ruleset, entry_id)
        if entry is None:
            return not_found(f"The wiki has no entry {entry_id!r}.",
                             auth.current_username(), current="wiki")
        return _entry_page(ruleset, entry)
    return endpoint


def _positive(page: int) -> int:
    return page if page > 0 else 1


def register_wiki(ruleset: RuleSet) -> None:
    """Register the wiki routes against the BOOK ruleset `ruleset`. Replace earlier
    routes of the same paths.

    ⚠ `ruleset` must have no custom layer. See the module docstring.
    """
    def index(q: str = ""):
        return _index_page(ruleset, q)

    def charms(splat: str = "", category: str = "", q: str = "", page: int = 1):
        return _list_page(ruleset, wv.charm_list(ruleset, splat=splat, category=category,
                                                 query=q, page=_positive(page)),
                          "Every Charm in the builder, by Exalt type and category, "
                          "for Exalted First Edition.")

    def styles(tier: str = "", q: str = "", page: int = 1):
        return _list_page(ruleset, wv.style_list(ruleset, tier=tier, query=q,
                                                 page=_positive(page)),
                          "The martial-arts styles of Exalted First Edition, with their Charms.")

    def spells(circle: str = "", q: str = "", page: int = 1):
        return _list_page(ruleset, wv.spell_list(ruleset, circle=circle, query=q,
                                                 page=_positive(page)),
                          "The spells of Exalted First Edition, by Circle.")

    def merits(kind: str = "", category: str = "", q: str = "", page: int = 1):
        return _list_page(ruleset, wv.merit_list(ruleset, kind=kind, category=category,
                                                 query=q, page=_positive(page)),
                          "The Merits and Flaws of Exalted First Edition.")

    def backgrounds(splat: str = "", q: str = "", page: int = 1):
        return _list_page(ruleset, wv.background_list(ruleset, splat=splat, query=q,
                                                      page=_positive(page)),
                          "The Backgrounds of Exalted First Edition, with the text of each rating.")

    replace_route("/wiki", index, name="wiki")
    replace_route("/wiki/charms", charms, name="wiki-charms")
    replace_route("/wiki/charms/{entry_id}", _entry_route(ruleset, wv.charm_page),
                  name="wiki-charm")
    replace_route("/wiki/martial-arts", styles, name="wiki-styles")
    replace_route("/wiki/martial-arts/{entry_id}",
                  _entry_route(ruleset, wv.style_page), name="wiki-style")
    replace_route("/wiki/spells", spells, name="wiki-spells")
    replace_route("/wiki/spells/{entry_id}", _entry_route(ruleset, wv.spell_page),
                  name="wiki-spell")
    replace_route("/wiki/merits", merits, name="wiki-merits")
    replace_route("/wiki/merits/{entry_id}", _entry_route(ruleset, wv.merit_page),
                  name="wiki-merit")
    replace_route("/wiki/backgrounds", backgrounds, name="wiki-backgrounds")
    replace_route("/wiki/backgrounds/{entry_id}",
                  _entry_route(ruleset, wv.background_page),
                  name="wiki-background")
