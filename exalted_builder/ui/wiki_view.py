"""
ui/wiki_view.py — the presenter of the public wiki.

Input: a `RuleSet` and the filters of one wiki request. Output: display-ready view
models for the entry tables and the entry pages. Mechanism: each function reads the
catalogues of the ruleset and formats them with the formatters of `ui/view.py`.

It imports no UI toolkit and makes no HTML. `server/wiki.py` renders the result.

⚠ The wiki shows the BOOK. `server/main.build_server` gives it a ruleset with no
custom layer. This module does not remove homebrew itself. A filter here would make
the test of that wiring pass with the wiring broken. See `docs/plans/vtt.md` 9.5.

⚠ No function here takes a `Character`. The wiki has no reader character, thus it
shows no "owned" and no "available".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from ..models.rules import RuleSet, SpellCircle
from . import theme
from . import view

# The number of rows on one list page.
PAGE_SIZE = 100

# The length limit of the excerpt in a table cell.
EXCERPT_LENGTH = 110

# The heading of a table column that holds an excerpt of the text.
SUMMARY = "Summary"

# The sections of the wiki, in the order of the navigation: (slug, title).
SECTIONS: tuple[tuple[str, str], ...] = (
    ("charms", "Charms"),
    ("martial-arts", "Martial Arts"),
    ("spells", "Spells"),
    ("merits", "Merits & Flaws"),
    ("backgrounds", "Backgrounds"),
)

_MA_PREFIX = "martial_arts:"


@dataclass
class Row:
    """One entry in a table. `cells` match the `columns` of its table."""
    href: str
    title: str
    cells: list[str]
    group: str = ""                       # the heading that the row is under
    accent: str = ""                      # a CSS colour for the heading, "" for none


@dataclass
class Link:
    """A name with an optional wiki address. `href` is "" for a name with no page."""
    text: str
    href: str = ""


@dataclass
class Fact:
    """One labelled value on an entry page."""
    label: str
    value: str


@dataclass
class EntryPage:
    """One entry, with its full text."""
    section: str                          # the slug of its section
    title: str
    kicker: str                           # the line over the title, "Solar Exalted · Melee"
    facts: list[Fact]
    paragraphs: list[str]
    source: str                           # "<book> p.<page>", "" when unattributed
    accent: str = ""                      # a CSS colour for the kicker, "" for none
    # Groups of links. One link in a group satisfies it. Charms only.
    prerequisites: list[list[Link]] = field(default_factory=list)
    # A titled list of further lines: the Background ladder, the style mechanics.
    extra_title: str = ""
    extra_lines: list[str] = field(default_factory=list)
    # The Charms of a martial-arts style page.
    columns: list[str] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    # The Exalt type whose builder palette the page takes. "" for the default.
    theme: str = ""


@dataclass
class Option:
    value: str
    label: str


@dataclass
class Filter:
    """One dropdown of a list page. `value` is the current selection, "" for all."""
    name: str
    label: str                            # the text of the "all" choice
    options: list[Option]
    value: str = ""
    title: str = ""                       # the label over the dropdown


@dataclass
class ListPage:
    """One page of a filtered, searched table."""
    section: str
    title: str
    filters: list[Filter]
    query: str
    columns: list[str]                    # the headings of the cells after the name
    rows: list[Row]
    total: int                            # the number of matches on all pages
    page: int                             # 1-based
    pages: int
    # The Exalt type whose builder palette the page takes. "" for the default.
    theme: str = ""


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _matches(query: str, *texts: str) -> bool:
    """Return True if each word of `query` is in one of `texts`. Case is ignored."""
    haystack = " ".join(texts).lower()
    return all(word in haystack for word in query.lower().split())


def excerpt(text: str, limit: int = EXCERPT_LENGTH) -> str:
    """Return the start of `text`, cut at a word boundary and marked with "…" when
    it is longer than `limit`."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _page(section: str, title: str, filters: list[Filter], query: str,
          columns: list[str], rows: Sequence[Row], page: int) -> ListPage:
    """Cut `rows` to page `page` and return the list page."""
    pages = max(1, -(-len(rows) // PAGE_SIZE))
    page = min(max(1, page), pages)
    start = (page - 1) * PAGE_SIZE
    return ListPage(section=section, title=title, filters=filters, query=query,
                    columns=columns, rows=list(rows[start:start + PAGE_SIZE]),
                    total=len(rows), page=page, pages=pages)


def _selected(value: str, options: Sequence[Option]) -> str:
    """Return `value` if it is one of `options`. Return "" in all other cases."""
    return value if any(o.value == value for o in options) else ""


def splat_label(ruleset: RuleSet, exalt_type: str) -> str:
    """Return the display name of an Exalt type. An unknown type is its own name."""
    exalt = ruleset.exalts.get(exalt_type)
    return exalt.label if exalt else exalt_type


def splat_accent(exalt_type: str) -> str:
    """Return the accent colour of the palette of an Exalt type."""
    return theme.palette(exalt_type).accent


def _splat_order(ruleset: RuleSet, present: set[str]) -> list[str]:
    """Return the Exalt types in `present`: the ruleset order first, then the rest
    sorted by name."""
    known = [e for e in ruleset.exalts if e in present]
    return known + sorted(present - set(known))


def category_label(ruleset: RuleSet, category: str) -> str:
    """Return the display name of a Charm category.

    A martial-arts category gives its authored style name. Another category gives
    the title case of the part after the last colon.
    """
    if category.startswith(_MA_PREFIX):
        return view._style_label(category, ruleset)
    return view._label(category.split(":")[-1])


def _paragraphs(text: str) -> list[str]:
    """Split `text` at blank lines. Return one paragraph for text with none."""
    parts = [p.strip() for p in text.split("\n\n")]
    return [p for p in parts if p]


# --------------------------------------------------------------------------- #
# Charms
# --------------------------------------------------------------------------- #


CHARM_COLUMNS = ["Type", "Cost", "Duration", "Minimums"]


def charm_href(charm_id: str) -> str:
    return f"/wiki/charms/{charm_id}"


def _book_charms(ruleset: RuleSet) -> list:
    """Return the Charms that have a wiki page.

    ⚠ A virtual Charm is a Dragon-King Path power that the loader projects into the
    Charm list. It is not a Charm of the book, thus it has no page.
    """
    return [c for c in ruleset.charms.values() if not c.virtual]


def charm_row(ruleset: RuleSet, charm, *, group: str = "") -> Row:
    """Return the table row of `charm`. The cells match `CHARM_COLUMNS`."""
    requirement, _ = view.charm_requirements(ruleset, charm)
    return Row(href=charm_href(charm.id), title=charm.name,
               cells=[charm.type.value, view._cost_str(charm.cost), charm.duration,
                      requirement],
               group=group, accent=splat_accent(charm.exalt_type) if group else "")


def charm_list(ruleset: RuleSet, *, splat: str = "", category: str = "",
               query: str = "", page: int = 1) -> ListPage:
    """Return one page of the Charms, filtered by Exalt type, by category and by the
    words of `query`. The rows are under one heading for each Exalt type and
    category. An unknown filter value is ignored."""
    charms = _book_charms(ruleset)
    splat_options = [Option(s, splat_label(ruleset, s))
                     for s in _splat_order(ruleset, {c.exalt_type for c in charms})]
    splat = _selected(splat, splat_options)
    if splat:
        charms = [c for c in charms if c.exalt_type == splat]

    categories = {c.category for c in charms}
    category_options = sorted(
        (Option(cat, category_label(ruleset, cat)) for cat in categories),
        key=lambda o: (o.value.startswith(_MA_PREFIX), o.label))
    category = _selected(category, category_options)
    if category:
        charms = [c for c in charms if c.category == category]
    if query:
        charms = [c for c in charms if _matches(query, c.name, c.description,
                                                " ".join(c.keywords))]

    splat_rank = {s: i for i, s in enumerate(o.value for o in splat_options)}
    charms.sort(key=lambda c: (splat_rank.get(c.exalt_type, 0),
                               category_label(ruleset, c.category),
                               c.min_ability, c.min_essence, c.name))
    rows = [charm_row(ruleset, c, group=f"{splat_label(ruleset, c.exalt_type)} · "
                                        f"{category_label(ruleset, c.category)}")
            for c in charms]
    filters = [Filter("splat", "All Exalt types", splat_options, splat, "Exalt type"),
               Filter("category", "All categories", category_options, category, "Category")]
    listing = _page("charms", "Charms", filters, query, CHARM_COLUMNS, rows, page)
    listing.theme = splat
    return listing


def charm_page(ruleset: RuleSet, charm_id: str) -> Optional[EntryPage]:
    """Return the page of one Charm, or None if the wiki has no such Charm.

    The facts are in the order of the stat block of the book: cost, duration,
    type, minimums.
    """
    charm = ruleset.charms.get(charm_id)
    if charm is None or charm.virtual:
        return None
    requirement, _ = view.charm_requirements(ruleset, charm)
    facts = [Fact("Cost", view._cost_str(charm.cost)), Fact("Duration", charm.duration),
             Fact("Type", charm.type.value), Fact("Minimums", requirement)]
    if charm.keywords:
        facts.append(Fact("Keywords", ", ".join(charm.keywords)))
    prerequisites = [
        [Link(name, charm_href(cid) if cid and not ruleset.charms[cid].virtual else "")
         for name, cid in group]
        for group in view.charm_prerequisite_links(ruleset, charm)]
    return EntryPage(section="charms", title=charm.name,
                     kicker=f"{splat_label(ruleset, charm.exalt_type)} · "
                            f"{category_label(ruleset, charm.category)}",
                     accent=splat_accent(charm.exalt_type), facts=facts,
                     paragraphs=_paragraphs(view._charm_description(charm)),
                     source=view.source_label(charm.source), prerequisites=prerequisites,
                     theme=charm.exalt_type)


# --------------------------------------------------------------------------- #
# Martial arts
# --------------------------------------------------------------------------- #


def style_slug(category: str) -> str:
    """"martial_arts:ebon-shadow" -> "ebon-shadow"."""
    return category.removeprefix(_MA_PREFIX)


def style_href(category: str) -> str:
    return f"/wiki/martial-arts/{style_slug(category)}"


def _style_categories(ruleset: RuleSet) -> list[str]:
    """Return each martial-arts category that has a style entry or a Charm."""
    categories = {s.category for s in ruleset.martial_arts_styles.values()}
    categories |= {c.category for c in _book_charms(ruleset)
                   if c.category.startswith(_MA_PREFIX)}
    return sorted(categories, key=lambda cat: category_label(ruleset, cat))


def _tier_heading(tier: str) -> str:
    return f"{tier} styles" if tier else "Styles with no printed tier"


def style_list(ruleset: RuleSet, *, tier: str = "", query: str = "",
               page: int = 1) -> ListPage:
    """Return the martial-arts styles, filtered by tier and by the words of `query`.
    The rows are under one heading for each tier."""
    rows = []
    for category in _style_categories(ruleset):
        style = view.style_for_category(ruleset, category)
        count = sum(1 for c in _book_charms(ruleset) if c.category == category)
        rows.append((category, style, count))
    tier_options = [Option(t, t) for t in sorted({s.tier for _, s, _ in rows if s and s.tier})]
    tier = _selected(tier, tier_options)
    if tier:
        rows = [r for r in rows if r[1] and r[1].tier == tier]
    if query:
        rows = [r for r in rows
                if _matches(query, category_label(ruleset, r[0]),
                            r[1].preamble if r[1] else "")]
    order = {o.value: i for i, o in enumerate(tier_options)}
    rows.sort(key=lambda r: (order.get(r[1].tier if r[1] else "", len(order)),
                             category_label(ruleset, r[0])))
    table = [Row(href=style_href(category), title=category_label(ruleset, category),
                 cells=[str(count), excerpt(style.preamble) if style else ""],
                 group=_tier_heading(style.tier if style else ""))
             for category, style, count in rows]
    return _page("martial-arts", "Martial Arts",
                 [Filter("tier", "All tiers", tier_options, tier, "Tier")], query,
                 ["Charms", SUMMARY], table, page)


def style_page(ruleset: RuleSet, slug: str) -> Optional[EntryPage]:
    """Return the page of one martial-arts style, with its Charms, or None."""
    category = _MA_PREFIX + slug
    if category not in _style_categories(ruleset):
        return None
    style = view.style_for_category(ruleset, category)
    charms = sorted((c for c in _book_charms(ruleset) if c.category == category),
                    key=lambda c: (c.min_ability, c.min_essence, c.name))
    tier = style.tier if style else ""
    return EntryPage(
        section="martial-arts", title=category_label(ruleset, category),
        kicker=f"{tier} martial art" if tier else "Martial art",
        facts=[], paragraphs=_paragraphs(style.preamble) if style else [],
        source=style.source_label if style else "",
        extra_title="Style mechanics" if style and style.mechanics else "",
        extra_lines=list(style.mechanics) if style else [],
        columns=CHARM_COLUMNS, rows=[charm_row(ruleset, c) for c in charms])


# --------------------------------------------------------------------------- #
# Spells
# --------------------------------------------------------------------------- #


def spell_href(spell_id: str) -> str:
    return f"/wiki/spells/{spell_id}"


def _circle_order() -> dict[str, int]:
    return {c.value: i for i, c in enumerate(SpellCircle)}


def spell_list(ruleset: RuleSet, *, circle: str = "", query: str = "",
               page: int = 1) -> ListPage:
    """Return one page of the spells, filtered by Circle and by the words of `query`.
    The rows are under one heading for each Circle."""
    order = _circle_order()
    spells = list(ruleset.spells.values())
    present = {s.circle.value for s in spells}
    circle_options = [Option(c, f"{c} Circle") for c in sorted(present, key=order.get)]
    circle = _selected(circle, circle_options)
    if circle:
        spells = [s for s in spells if s.circle.value == circle]
    if query:
        spells = [s for s in spells if _matches(query, s.name, s.description)]
    spells.sort(key=lambda s: (order[s.circle.value], s.name))
    rows = [Row(href=spell_href(s.id), title=s.name,
                cells=[view._cost_str(s.cost), excerpt(s.description)],
                group=f"{s.circle.value} Circle")
            for s in spells]
    return _page("spells", "Spells",
                 [Filter("circle", "All Circles", circle_options, circle, "Circle")],
                 query, ["Cost", SUMMARY], rows, page)


def spell_page(ruleset: RuleSet, spell_id: str) -> Optional[EntryPage]:
    spell = ruleset.spells.get(spell_id)
    if spell is None:
        return None
    return EntryPage(section="spells", title=spell.name,
                     kicker=f"{spell.circle.value} Circle spell",
                     facts=[Fact("Cost", view._cost_str(spell.cost))],
                     paragraphs=_paragraphs(spell.description),
                     source=view.source_label(spell.source))


# --------------------------------------------------------------------------- #
# Merits and Flaws
# --------------------------------------------------------------------------- #


def merit_href(merit_id: str) -> str:
    return f"/wiki/merits/{merit_id}"


_KINDS = (Option("merit", "Merits"), Option("flaw", "Flaws"))


def _merit_points(definition) -> str:
    """Return the point value, with the printed cost note when there is one."""
    points = view.merit_price(definition)
    return f"{points} pt · {definition.cost_note}" if definition.cost_note else f"{points} pt"


def _merit_kicker(ruleset: RuleSet, definition) -> str:
    parts = [f"{definition.category} {definition.kind}" if definition.category
             else definition.kind.title()]
    if definition.exalt_types:
        parts.append(", ".join(splat_label(ruleset, e) for e in definition.exalt_types))
    return " · ".join(parts)


def merit_list(ruleset: RuleSet, *, kind: str = "", category: str = "",
               query: str = "", page: int = 1) -> ListPage:
    """Return one page of the Merits and Flaws, filtered by kind, by category and by
    the words of `query`. The rows are under one heading for each category."""
    rows = list(ruleset.merits_flaws.values())
    kind = _selected(kind, _KINDS)
    if kind:
        rows = [m for m in rows if m.kind == kind]
    category_options = [Option(c, c) for c in sorted({m.category for m in rows if m.category})]
    category = _selected(category, category_options)
    if category:
        rows = [m for m in rows if m.category == category]
    if query:
        rows = [m for m in rows if _matches(query, m.name, m.description)]
    rows.sort(key=lambda m: (m.category or "~", m.kind, m.name))
    table = [Row(href=merit_href(m.id), title=m.name,
                 cells=[m.kind.title(), view.merit_price(m), excerpt(m.description)],
                 group=m.category or "Uncategorised")
             for m in rows]
    filters = [Filter("kind", "Merits and Flaws", list(_KINDS), kind, "Kind"),
               Filter("category", "All categories", category_options, category, "Category")]
    return _page("merits", "Merits & Flaws", filters, query,
                 ["Kind", "Points", SUMMARY], table, page)


def merit_page(ruleset: RuleSet, merit_id: str) -> Optional[EntryPage]:
    definition = ruleset.merits_flaws.get(merit_id)
    if definition is None:
        return None
    return EntryPage(section="merits", title=definition.name,
                     kicker=_merit_kicker(ruleset, definition),
                     facts=[Fact("Points", _merit_points(definition))],
                     paragraphs=_paragraphs(definition.description),
                     source=view.source_label(definition.source))


# --------------------------------------------------------------------------- #
# Backgrounds
# --------------------------------------------------------------------------- #


def background_href(background_id: str) -> str:
    return f"/wiki/backgrounds/{background_id}"


def _background_heading(ruleset: RuleSet, background) -> str:
    """Return the Exalt type of a splat Background, or a heading for a shared one."""
    if background.exalt_type:
        return splat_label(ruleset, background.exalt_type)
    return "Shared Backgrounds"


def background_list(ruleset: RuleSet, *, splat: str = "", query: str = "",
                    page: int = 1) -> ListPage:
    """Return one page of the Backgrounds, filtered by Exalt type and by the words
    of `query`. The rows are under one heading for each Exalt type.

    The Exalt type filter keeps the Backgrounds that the builder offers to that
    splat, from `RuleSet.backgrounds_for`. Thus it keeps the shared Backgrounds and
    removes the Backgrounds that the splat is barred from.
    """
    rows = list(ruleset.background_catalog.values())
    splat_options = [Option(s, splat_label(ruleset, s)) for s in ruleset.exalts]
    splat = _selected(splat, splat_options)
    if splat:
        offered = {b.id for b in ruleset.backgrounds_for(splat)}
        rows = [b for b in rows if b.id in offered]
    if query:
        rows = [b for b in rows if _matches(query, b.name, b.description, *b.ladder)]
    rank = {s: i for i, s in enumerate(ruleset.exalts)}
    rows.sort(key=lambda b: (b.exalt_type != "", rank.get(b.exalt_type, len(rank)),
                             b.exalt_type, b.name))
    table = [Row(href=background_href(b.id), title=b.name, cells=[excerpt(b.description)],
                 group=_background_heading(ruleset, b),
                 accent=splat_accent(b.exalt_type) if b.exalt_type else "")
             for b in rows]
    listing = _page("backgrounds", "Backgrounds",
                    [Filter("splat", "All Exalt types", splat_options, splat, "Exalt type")],
                    query, [SUMMARY], table, page)
    listing.theme = splat
    return listing


def background_page(ruleset: RuleSet, background_id: str) -> Optional[EntryPage]:
    background = ruleset.background_catalog.get(background_id)
    if background is None:
        return None
    ladder = [f"{view._DOTS[i]} {text}" for i, text in enumerate(background.ladder)]
    return EntryPage(section="backgrounds", title=background.name,
                     kicker=f"Background · {_background_heading(ruleset, background)}",
                     accent=splat_accent(background.exalt_type) if background.exalt_type else "",
                     facts=[], paragraphs=_paragraphs(background.description),
                     source=view.source_label(background.source),
                     extra_title="Ratings" if ladder else "", extra_lines=ladder,
                     theme=background.exalt_type)


# --------------------------------------------------------------------------- #
# The index and the search of all sections
# --------------------------------------------------------------------------- #


@dataclass
class SectionSummary:
    slug: str
    title: str
    count: int


def section_counts(ruleset: RuleSet) -> list[SectionSummary]:
    """Return each section of the wiki with the number of its entries."""
    counts = {
        "charms": len(_book_charms(ruleset)),
        "martial-arts": len(_style_categories(ruleset)),
        "spells": len(ruleset.spells),
        "merits": len(ruleset.merits_flaws),
        "backgrounds": len(ruleset.background_catalog),
    }
    return [SectionSummary(slug, title, counts[slug]) for slug, title in SECTIONS]


def search_all(ruleset: RuleSet, query: str, limit: int = 12) -> list[tuple[ListPage, str]]:
    """Return the first matches of `query` in each section that has a match, with the
    address of the full result list of that section."""
    if not query.strip():
        return []
    lists = (charm_list(ruleset, query=query), style_list(ruleset, query=query),
             spell_list(ruleset, query=query), merit_list(ruleset, query=query),
             background_list(ruleset, query=query))
    results = []
    for result in lists:
        if result.total:
            result.rows = result.rows[:limit]
            results.append((result, f"/wiki/{result.section}"))
    return results
