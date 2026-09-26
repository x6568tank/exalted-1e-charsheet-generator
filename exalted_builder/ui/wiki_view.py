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
from typing import Callable, Optional, Sequence

from pydantic import ValidationError

from ..models.rules import Charm, RuleSet, Spell, SpellCircle, ThaumaturgicRitual
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
    ("thaumaturgy", "Thaumaturgy"),
    ("powers", "Paths & Powers"),
    ("merits", "Merits & Flaws"),
    ("backgrounds", "Backgrounds"),
    ("traits", "Traits"),
    ("castes", "Castes"),
    ("equipment", "Equipment"),
    ("artifacts", "Artifacts"),
    ("st-screen", "ST Screen"),
)

_MA_PREFIX = "martial_arts:"


@dataclass
class Row:
    """One entry in a table. `cells` match the `columns` of its table. `href` is ""
    for an entry with no page."""
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
class Block:
    """A titled run of paragraphs on an entry page: the anima powers, a Path power."""
    title: str
    paragraphs: list[str]


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
    # Titled paragraphs after the text.
    blocks: list[Block] = field(default_factory=list)
    # A table after the text: the Charms of a style, the formulas of a Science.
    rows_title: str = "Charms"
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
    # The columns of the rows of one group, when they differ from `columns`.
    group_columns: dict[str, list[str]] = field(default_factory=dict)


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
# Shared helpers of the reference sections
# --------------------------------------------------------------------------- #


def _name(value) -> str:
    """Return the display name of a trait id: "martial_arts" gives "Martial Arts"."""
    return view._ability_label(str(getattr(value, "value", value)))


def _names(values) -> str:
    return ", ".join(_name(v) for v in values)


def _dots(rating: int) -> str:
    return view._DOTS[rating] if 0 <= rating < len(view._DOTS) else str(rating)


def _motes(count: int) -> str:
    return f"{count} mote" if count == 1 else f"{count} motes"


def _ladder(ladder: dict[int, str]) -> list[str]:
    """Return the lines of a rating ladder, lowest rating first."""
    return [f"{_dots(rating)} {text}" for rating, text in sorted(ladder.items())]


def _minimums(minimums) -> str:
    """Return ability floors as the book prints them: "Archery or Brawl 1, Lore 3"."""
    return ", ".join(f"{' or '.join(_name(a) for a in m.abilities)} {m.rating}"
                     for m in minimums)


def _charm_names(ruleset: RuleSet, charm_ids: Sequence[str]) -> str:
    return ", ".join(ruleset.charms[c].name if c in ruleset.charms else c for c in charm_ids)


def _set(model, name: str) -> bool:
    """Return True if the data row gives field `name`. A default 0 is not a value."""
    return name in model.model_fields_set


def _signed(model, name: str) -> str:
    return f"{getattr(model, name):+d}" if _set(model, name) else "—"


def _plain(model, name: str) -> str:
    return str(getattr(model, name)) if _set(model, name) else "—"


def _kind_filter(kinds: Sequence[Option], kind: str) -> tuple[str, Filter]:
    kind = _selected(kind, kinds)
    return kind, Filter("kind", "All kinds", list(kinds), kind, "Kind")


def _search(rows: list[tuple[str, Row, str]], kind: str, query: str) -> list[Row]:
    """Keep the rows of `kind` ("" for all) that match `query`. Each item of `rows` is
    (kind, row, the text to search besides the name)."""
    return [row for row_kind, row, text in rows
            if (not kind or row_kind == kind) and (not query or _matches(query, row.title, text))]


# --------------------------------------------------------------------------- #
# Traits: Attributes, Abilities, Virtues, Natures, Virtue Flaws
# --------------------------------------------------------------------------- #


def trait_href(key: str) -> str:
    return f"/wiki/traits/{key}"


_TRAIT_KINDS = (Option("attribute", "Attributes"), Option("ability", "Abilities"),
                Option("virtue", "Virtues"), Option("nature", "Natures"),
                Option("flaw", "Virtue Flaws"))
_FLAWS = "Virtue Flaws"


def trait_list(ruleset: RuleSet, *, kind: str = "", query: str = "",
               page: int = 1) -> ListPage:
    """Return one page of the traits, filtered by kind and by the words of `query`."""
    td = ruleset.trait_descriptions
    rows: list[tuple[str, Row, str]] = []
    if td is not None:
        rows += [("attribute", Row(trait_href(f"attribute.{a.id.value}"), a.name,
                                   [excerpt(a.description)], group=f"{a.category} Attributes"),
                  a.description) for a in td.attributes]
        rows += [("ability", Row(trait_href(f"ability.{a.id.value}"), a.name,
                                 [excerpt(a.description)], group="Abilities"), a.description)
                 for a in td.abilities]
        rows += [("virtue", Row(trait_href(f"virtue.{v.id.value}"), v.name,
                                [excerpt(v.description)], group="Virtues"), v.description)
                 for v in td.virtues]
    rows += [("nature", Row(trait_href(f"nature.{n.id}"), n.name, [excerpt(n.description)],
                            group="Natures"), n.description)
             for n in sorted(ruleset.nature_catalog.values(), key=lambda n: n.name)]
    rows += [("flaw", Row(trait_href(f.id), f.name, [_name(f.virtue), excerpt(f.description)],
                          group=_FLAWS), f"{f.description} {f.limit_break}")
             for f in sorted(ruleset.virtue_flaw_catalog.values(),
                             key=lambda f: (f.virtue.value, f.name))]
    kind, kind_filter = _kind_filter(_TRAIT_KINDS, kind)
    listing = _page("traits", "Traits", [kind_filter], query, [SUMMARY],
                    _search(rows, kind, query), page)
    listing.group_columns = {_FLAWS: ["Virtue", SUMMARY]}
    return listing


def trait_page(ruleset: RuleSet, key: str) -> Optional[EntryPage]:
    """Return the page of the trait `key`: "<kind>.<id>", or the id of a Virtue Flaw."""
    flaw = ruleset.virtue_flaw_catalog.get(key)
    if flaw is not None:
        blocks = [Block("Limit Break", _paragraphs(flaw.limit_break))] if flaw.limit_break else []
        if flaw.notes:
            blocks.append(Block("Notes", _paragraphs(flaw.notes)))
        return EntryPage(section="traits", title=flaw.name,
                         kicker=f"Virtue Flaw · {_name(flaw.virtue)}",
                         facts=[Fact("Virtue", _name(flaw.virtue))],
                         paragraphs=_paragraphs(flaw.description), source=flaw.source,
                         blocks=blocks)
    kind, _, ident = key.partition(".")
    if kind == "nature":
        nature = ruleset.nature_catalog.get(ident)
        if nature is None:
            return None
        return EntryPage(section="traits", title=nature.name, kicker="Nature", facts=[],
                         paragraphs=_paragraphs(nature.description), source="")
    td = ruleset.trait_descriptions
    if td is None:
        return None
    source = view.source_label(td.source)
    if kind == "attribute":
        for a in td.attributes:
            if a.id.value == ident:
                ladder = _ladder(a.ladder)
                return EntryPage(section="traits", title=a.name,
                                 kicker=f"{a.category} Attribute", facts=[],
                                 paragraphs=_paragraphs(a.description), source=source,
                                 extra_title="Ratings" if ladder else "", extra_lines=ladder)
    if kind == "ability":
        for a in td.abilities:
            if a.id.value == ident:
                facts = [Fact("Specialties", ", ".join(a.specialties))] if a.specialties else []
                blocks = [Block(title, _paragraphs(text)) for title, text in
                          (("Specialties", a.specialties_note), ("Standard", a.standard),
                           ("Challenging", a.challenging), ("Legendary", a.legendary)) if text]
                ladder = _ladder(td.ability_ladder)
                return EntryPage(section="traits", title=a.name, kicker="Ability",
                                 facts=facts, paragraphs=_paragraphs(a.description),
                                 source=source, blocks=blocks,
                                 extra_title="Ratings" if ladder else "", extra_lines=ladder)
    if kind == "virtue":
        for v in td.virtues:
            if v.id.value == ident:
                facts = [Fact(label, text) for label, text in
                         (("Aids in", v.aids_in), ("Must fail a check to", v.must_fail_check_to))
                         if text]
                ladder = _ladder(v.ladder)
                return EntryPage(section="traits", title=v.name, kicker="Virtue", facts=facts,
                                 paragraphs=_paragraphs(v.description), source=source,
                                 extra_title="Ratings" if ladder else "", extra_lines=ladder)
    return None


# --------------------------------------------------------------------------- #
# Castes: castes and aspects, training camps, Callings, Astrological Colleges
# --------------------------------------------------------------------------- #

# ⚠ The one splat that has Astrological Colleges. `College` rows name no Exalt type.
_COLLEGE_SPLAT = "Sidereal"


def caste_href(key: str) -> str:
    return f"/wiki/castes/{key}"


def _caste_noun(ruleset: RuleSet, exalt_type: str) -> str:
    exalt = ruleset.exalts.get(exalt_type)
    return exalt.caste_noun if exalt and exalt.caste_noun else "Caste"


def _caste_traits(caste) -> str:
    return _names(caste.caste_abilities) or _names(caste.caste_attributes)


def caste_list(ruleset: RuleSet, *, splat: str = "", query: str = "",
               page: int = 1) -> ListPage:
    """Return one page of the castes, the training camps, the Callings and the
    Astrological Colleges, under one heading for each Exalt type and kind."""
    rows: list[tuple[str, Row, str]] = []
    group_columns: dict[str, list[str]] = {}
    for exalt_type in ruleset.exalts:
        label, accent = splat_label(ruleset, exalt_type), splat_accent(exalt_type)
        noun = _caste_noun(ruleset, exalt_type)
        rows += [(exalt_type, Row(caste_href(c.id), c.label, [_caste_traits(c), excerpt(c.description)],
                                  group=f"{label} · {noun}s", accent=accent),
                  f"{c.description} {c.anima_powers}")
                 for c in ruleset.castes.values() if c.exalt_type == exalt_type]
        camps = f"{label} · Training camps"
        group_columns[camps] = ["Required", SUMMARY]
        rows += [(exalt_type, Row(caste_href(f"camp.{c.id}"), c.label,
                                  [_minimums(c.required_min_abilities), excerpt(c.description)],
                                  group=camps, accent=accent), c.description)
                 for c in ruleset.camps.values() if c.exalt_type == exalt_type]
        callings = f"{label} · Callings"
        group_columns[callings] = ["Abilities", SUMMARY]
        rows += [(exalt_type, Row(caste_href(f"calling.{c.id}"), c.label,
                                  [_names(c.abilities), excerpt(c.description)],
                                  group=callings, accent=accent), c.description)
                 for c in ruleset.callings.values() if c.exalt_type == exalt_type]
        if exalt_type == _COLLEGE_SPLAT:
            colleges = f"{label} · Astrological Colleges"
            group_columns[colleges] = ["House"]
            rows += [(exalt_type, Row("", c.name, [c.house_label], group=colleges, accent=accent),
                      c.house_label) for c in ruleset.colleges.values()]
    present = {row_splat for row_splat, _row, _text in rows}
    options = [Option(e, splat_label(ruleset, e)) for e in ruleset.exalts if e in present]
    splat = _selected(splat, options)
    listing = _page("castes", "Castes", [Filter("splat", "All Exalt types", options, splat,
                                                "Exalt type")],
                    query, ["Traits", SUMMARY], _search(rows, splat, query), page)
    listing.group_columns = group_columns
    listing.theme = splat
    return listing


def caste_page(ruleset: RuleSet, key: str) -> Optional[EntryPage]:
    """Return the page of a caste (its id), a camp ("camp.<id>") or a Calling
    ("calling.<id>")."""
    kind, _, ident = key.partition(".")
    if kind == "camp" and ident in ruleset.camps:
        camp = ruleset.camps[ident]
        facts = [Fact(label, value) for label, value in (
            ("Required", _minimums(camp.required_min_abilities)),
            ("Granted Charms", _charm_names(ruleset, camp.granted_charms))) if value]
        facts += [Fact("Charm choice", choice.label) for choice in camp.granted_charm_choices]
        return EntryPage(section="castes", title=camp.label,
                         kicker=f"{splat_label(ruleset, camp.exalt_type)} · Training camp",
                         accent=splat_accent(camp.exalt_type), facts=facts,
                         paragraphs=_paragraphs(camp.description),
                         source=view.source_label(camp.source), theme=camp.exalt_type)
    if kind == "calling" and ident in ruleset.callings:
        calling = ruleset.callings[ident]
        camp = ruleset.camps.get(calling.camp)
        abilities = ", ".join(
            f"{_name(a)} ({calling.ability_focus[a.value]})" if a.value in calling.ability_focus
            else _name(a) for a in calling.abilities)
        facts = [Fact(label, value) for label, value in (
            ("Camp", camp.label if camp else calling.camp), ("Abilities", abilities),
            ("Charms", _charm_names(ruleset, calling.charms))) if value]
        return EntryPage(section="castes", title=calling.label,
                         kicker=f"{splat_label(ruleset, calling.exalt_type)} · Calling",
                         accent=splat_accent(calling.exalt_type), facts=facts,
                         paragraphs=_paragraphs(calling.description),
                         source=view.source_label(calling.source), theme=calling.exalt_type)
    caste = ruleset.castes.get(key)
    if caste is None:
        return None
    noun = _caste_noun(ruleset, caste.exalt_type)
    facts = [Fact(label, value) for label, value in (
        (f"{noun} Abilities", _names(caste.caste_abilities)),
        (f"{noun} Attributes", _names(caste.caste_attributes)),
        ("Required", _minimums(caste.required_min_abilities))) if value]
    blocks = [Block("Anima powers", _paragraphs(caste.anima_powers))] if caste.anima_powers else []
    return EntryPage(section="castes", title=caste.label,
                     kicker=f"{splat_label(ruleset, caste.exalt_type)} · {noun}",
                     accent=splat_accent(caste.exalt_type), facts=facts,
                     paragraphs=_paragraphs(caste.description), source="", blocks=blocks,
                     theme=caste.exalt_type)


# --------------------------------------------------------------------------- #
# Equipment: weapons, armor, goods and services, magical materials
# --------------------------------------------------------------------------- #


def equipment_href(item_id: str) -> str:
    return f"/wiki/equipment/{item_id}"


_EQUIPMENT_KINDS = (Option("weapon", "Weapons"), Option("armor", "Armor"),
                    Option("gear", "Goods and services"), Option("material", "Magical materials"))
# The weapon headings, in order. A weapon goes under the first of its tags in this list.
_WEAPON_TAGS = ("melee", "martial_arts", "brawl", "thrown", "archery")
_WEAPON_COLUMNS = ["Speed", "Accuracy", "Damage", "Defense", "Rate", "Range", "Cost"]
_ARMOR_COLUMNS = ["Soak", "Mobility", "Fatigue", "Weight", "Cost"]


def _weapon_group(weapon) -> str:
    if weapon.artifact_rating:
        return "Artifact weapons"
    tag = next((t for t in _WEAPON_TAGS if t in weapon.tags), "")
    return f"Weapons · {_name(tag)}" if tag else "Weapons · Other"


def _item_cost(item) -> str:
    """Return "Artifact ••", "Resources 2" or "—"."""
    if getattr(item, "artifact_rating", 0):
        return f"Artifact {_dots(item.artifact_rating)}"
    return f"Resources {item.resources_cost}" if _set(item, "resources_cost") else "—"


def _damage(weapon) -> str:
    return f"{weapon.damage:+d}{weapon.damage_type}" if _set(weapon, "damage") else "—"


def _gear_cost(gear) -> str:
    return " · ".join(part for part in (f"Resources {gear.resources_cost}", gear.cash) if part)


def equipment_list(ruleset: RuleSet, *, kind: str = "", query: str = "",
                   page: int = 1) -> ListPage:
    """Return one page of the equipment, filtered by kind and by the words of `query`.
    Each kind has its own columns."""
    rows: list[tuple[str, Row, str]] = []
    order = [f"Weapons · {_name(t)}" for t in _WEAPON_TAGS] + ["Weapons · Other", "Artifact weapons"]
    weapons = sorted(ruleset.weapon_catalog.values(),
                     key=lambda w: (order.index(_weapon_group(w)), w.name))
    rows += [("weapon", Row(equipment_href(w.id), w.name,
                            [_signed(w, "speed"), _signed(w, "accuracy"), _damage(w),
                             _signed(w, "defense"), _plain(w, "rate"), _plain(w, "range"),
                             _item_cost(w)], group=_weapon_group(w)), w.notes)
             for w in weapons]
    armor = sorted(ruleset.armor_catalog.values(), key=lambda a: (bool(a.artifact_rating), a.name))
    rows += [("armor", Row(equipment_href(a.id), a.name,
                           [f"{a.soak_lethal}L/{a.soak_bashing}B", str(a.mobility_penalty),
                            str(a.fatigue), a.weight.value, _item_cost(a)],
                           group="Artifact armor" if a.artifact_rating else "Armor"), a.notes)
             for a in armor]
    gear = sorted(ruleset.gear_catalog.values(), key=lambda g: (g.category, g.name))
    rows += [("gear", Row(equipment_href(g.id), g.name, [_gear_cost(g), excerpt(g.notes)],
                          group=g.category or "Goods and services"), g.notes) for g in gear]
    rows += [("material", Row(equipment_href(m.id), m.name,
                              [splat_label(ruleset, m.exalt_type) if m.exalt_type else "",
                               excerpt(m.notes)], group="Magical materials"), m.notes)
             for m in sorted(ruleset.material_catalog.values(), key=lambda m: m.name)]
    kind, kind_filter = _kind_filter(_EQUIPMENT_KINDS, kind)
    listing = _page("equipment", "Equipment", [kind_filter], query, ["Cost", SUMMARY],
                    _search(rows, kind, query), page)
    listing.group_columns = {group: _WEAPON_COLUMNS for group in order}
    listing.group_columns.update({"Armor": _ARMOR_COLUMNS, "Artifact armor": _ARMOR_COLUMNS,
                                  "Magical materials": ["Exalt type", SUMMARY]})
    return listing


def _stat_facts(item, stats: Sequence[tuple[str, str, str]]) -> list[Fact]:
    """Return a fact for each stat that the data row gives. Each stat is (label, field,
    format): "signed", "plain", "motes" or "dots"."""
    facts = []
    for label, name, style in stats:
        if not _set(item, name):
            continue
        value = getattr(item, name)
        text = {"signed": f"{value:+d}" if isinstance(value, int) else str(value),
                "motes": _motes(value), "dots": _dots(value)}.get(style, str(value))
        facts.append(Fact(label, text))
    return facts


def equipment_page(ruleset: RuleSet, item_id: str) -> Optional[EntryPage]:
    weapon = ruleset.weapon_catalog.get(item_id)
    if weapon is not None:
        facts = _stat_facts(weapon, (("Speed", "speed", "signed"), ("Accuracy", "accuracy", "signed")))
        if _set(weapon, "damage"):
            facts.append(Fact("Damage", _damage(weapon)))
        facts += _stat_facts(weapon, (
            ("Defense", "defense", "signed"), ("Rate", "rate", "plain"),
            ("Range", "range", "plain"), ("Maximum Strength", "max_strength", "plain"),
            ("Minimum Strength", "min_strength", "plain"),
            ("Minimum Dexterity", "min_dexterity", "plain"),
            ("Minimum Martial Arts", "min_martial_arts", "plain"),
            ("Artifact", "artifact_rating", "dots"), ("Attunement", "attunement", "motes"),
            ("Resources", "resources_cost", "plain")))
        return EntryPage(section="equipment", title=weapon.name, kicker=_weapon_group(weapon),
                         facts=facts, paragraphs=_paragraphs(weapon.notes),
                         source=view.source_label(weapon.source))
    armor = ruleset.armor_catalog.get(item_id)
    if armor is not None:
        facts = [Fact("Soak", f"{armor.soak_lethal}L/{armor.soak_bashing}B"),
                 Fact("Mobility penalty", str(armor.mobility_penalty)),
                 Fact("Fatigue", str(armor.fatigue)), Fact("Weight", armor.weight.value)]
        facts += _stat_facts(armor, (
            ("Melee difficulty", "difficulty_melee", "signed"),
            ("Ranged difficulty", "difficulty_ranged", "signed"),
            ("Artifact", "artifact_rating", "dots"), ("Attunement", "attunement", "motes"),
            ("Resources", "resources_cost", "plain")))
        return EntryPage(section="equipment", title=armor.name,
                         kicker="Artifact armor" if armor.artifact_rating else "Armor",
                         facts=facts, paragraphs=_paragraphs(armor.notes), source="")
    gear = ruleset.gear_catalog.get(item_id)
    if gear is not None:
        facts = [Fact(label, value) for label, value in (
            ("Category", gear.category), ("Resources", str(gear.resources_cost)),
            ("Price", gear.cash)) if value]
        return EntryPage(section="equipment", title=gear.name,
                         kicker="Service" if gear.kind == "service" else "Goods",
                         facts=facts, paragraphs=_paragraphs(gear.notes),
                         source=view.source_label(gear.source))
    material = ruleset.material_catalog.get(item_id)
    if material is not None:
        weapon_bonus = ", ".join(f"{label} {value:+d}" for label, value in (
            ("Speed", material.weapon_speed), ("Accuracy", material.weapon_accuracy),
            ("Damage", material.weapon_damage), ("Defense", material.weapon_defense)) if value)
        armor_bonus = ", ".join(part for part in (
            f"Soak {material.armor_soak_lethal:+d}L/{material.armor_soak_bashing:+d}B"
            if material.armor_soak_lethal or material.armor_soak_bashing else "",
            "no mobility penalty" if material.armor_negate_mobility_penalty else "",
            "no fatigue" if material.armor_negate_fatigue else "") if part)
        facts = [Fact(label, value) for label, value in (
            ("Exalt type", splat_label(ruleset, material.exalt_type) if material.exalt_type else ""),
            ("Weapon bonus", weapon_bonus), ("Armor bonus", armor_bonus)) if value]
        return EntryPage(section="equipment", title=material.name, kicker="Magical material",
                         accent=splat_accent(material.exalt_type) if material.exalt_type else "",
                         facts=facts, paragraphs=_paragraphs(material.notes), source="")
    return None


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #


def artifact_href(artifact_id: str) -> str:
    return f"/wiki/artifacts/{artifact_id}"


def _artifact_group(rating: int) -> str:
    return f"Artifact {_dots(rating)}"


def artifact_list(ruleset: RuleSet, *, rating: str = "", tag: str = "", query: str = "",
                  page: int = 1) -> ListPage:
    """Return one page of the artifacts, filtered by rating, by tag and by the words
    of `query`. The rows are under one heading for each rating."""
    rows = list(ruleset.artifact_catalog.values())
    ratings = [Option(str(r), _dots(r)) for r in sorted({a.rating for a in rows})]
    rating = _selected(rating, ratings)
    if rating:
        rows = [a for a in rows if str(a.rating) == rating]
    tags = [Option(t, _name(t)) for t in sorted({t for a in rows for t in a.tags})]
    tag = _selected(tag, tags)
    if tag:
        rows = [a for a in rows if tag in a.tags]
    if query:
        rows = [a for a in rows if _matches(query, a.name, a.description)]
    rows.sort(key=lambda a: (a.rating, a.name))
    table = [Row(artifact_href(a.id), a.name,
                 [_motes(a.attunement) if a.attunement else "—", excerpt(a.description)],
                 group=_artifact_group(a.rating)) for a in rows]
    return _page("artifacts", "Artifacts",
                 [Filter("rating", "All ratings", ratings, rating, "Rating"),
                  Filter("tag", "All kinds", tags, tag, "Kind")],
                 query, ["Attunement", SUMMARY], table, page)


def artifact_page(ruleset: RuleSet, artifact_id: str) -> Optional[EntryPage]:
    artifact = ruleset.artifact_catalog.get(artifact_id)
    if artifact is None:
        return None
    rating = _dots(artifact.rating) + (f" ({artifact.rating_notes})" if artifact.rating_notes else "")
    background = ruleset.background_catalog.get(artifact.background)
    merit = ruleset.merits_flaws.get(artifact.requires_merit)
    facts = [Fact(label, value) for label, value in (
        ("Rating", rating),
        ("Attunement", _motes(artifact.attunement) if artifact.attunement else ""),
        ("Resources", str(artifact.resources_cost) if artifact.resources_cost else ""),
        ("Background", background.name if background else artifact.background),
        ("Requires", merit.name if merit else artifact.requires_merit),
        ("Kind", _names(artifact.tags))) if value]
    return EntryPage(section="artifacts", title=artifact.name,
                     kicker=_artifact_group(artifact.rating), facts=facts,
                     paragraphs=_paragraphs(artifact.description), source=artifact.source)


# --------------------------------------------------------------------------- #
# Thaumaturgy: Arts, Sciences, rituals, formulas
# --------------------------------------------------------------------------- #


def thaumaturgy_href(entry_id: str) -> str:
    return f"/wiki/thaumaturgy/{entry_id}"


_THAUM_KINDS = (Option("art", "Arts"), Option("science", "Sciences"),
                Option("ritual", "Rituals"), Option("formula", "Formulas"))


def _formula_group(ruleset: RuleSet, formula) -> str:
    science = ruleset.thaum_sciences.get(formula.science_id)
    return f"Formulas · {science.name if science else formula.science_id}"


def thaumaturgy_list(ruleset: RuleSet, *, kind: str = "", query: str = "",
                     page: int = 1) -> ListPage:
    """Return one page of the thaumaturgy, filtered by kind and by the words of `query`."""
    rows: list[tuple[str, Row, str]] = []
    rows += [("art", Row(thaumaturgy_href(a.id), a.name, [str(a.min_occult), a.roll],
                         group="Arts"), a.description) for a in ruleset.thaum_arts.values()]
    rows += [("science", Row(thaumaturgy_href(s.id), s.name, [s.roll, str(s.max_rating)],
                             group="Sciences"), s.description)
             for s in ruleset.thaum_sciences.values()]
    rituals = sorted(ruleset.thaum_rituals.values(), key=lambda r: (r.level, r.name))
    rows += [("ritual", Row(thaumaturgy_href(r.id), r.name, [str(r.level), excerpt(r.description)],
                            group="Rituals"), r.description) for r in rituals]
    formulas = sorted(ruleset.thaum_formulas.values(),
                      key=lambda f: (_formula_group(ruleset, f), f.level, f.name))
    rows += [("formula", Row(thaumaturgy_href(f.id), f.name,
                             [str(f.level), str(f.difficulty) if f.difficulty else "—",
                              excerpt(f.effects)], group=_formula_group(ruleset, f)), f.effects)
             for f in formulas]
    kind, kind_filter = _kind_filter(_THAUM_KINDS, kind)
    listing = _page("thaumaturgy", "Thaumaturgy", [kind_filter], query, ["Level", SUMMARY],
                    _search(rows, kind, query), page)
    listing.group_columns = {"Arts": ["Minimum Occult", "Roll"], "Sciences": ["Roll", "Maximum"]}
    listing.group_columns.update({_formula_group(ruleset, f): ["Level", "Difficulty", SUMMARY]
                                  for f in formulas})
    return listing


def thaumaturgy_page(ruleset: RuleSet, entry_id: str) -> Optional[EntryPage]:
    art = ruleset.thaum_arts.get(entry_id)
    if art is not None:
        facts = [Fact(label, value) for label, value in (
            ("Minimum Occult", str(art.min_occult)), ("Roll", art.roll), ("Cost", art.cost),
            ("Specialties", ", ".join(art.specialties))) if value]
        blocks = [Block(f"{a.name} (Occult {a.min_occult})", _paragraphs(a.description))
                  for a in art.aspects]
        return EntryPage(section="thaumaturgy", title=art.name, kicker="Thaumaturgy · Art",
                         facts=facts, paragraphs=_paragraphs(art.description),
                         source=view.source_label(art.source), blocks=blocks)
    science = ruleset.thaum_sciences.get(entry_id)
    if science is not None:
        facts = [Fact(label, value) for label, value in (
            ("Roll", science.roll), ("Cost", science.cost), ("Time", science.time),
            ("Duration", science.duration), ("Maximum rating", str(science.max_rating))) if value]
        blocks = [Block(f"Level {_dots(level.rating)}", _paragraphs(level.description))
                  for level in science.levels]
        formulas = sorted((f for f in ruleset.thaum_formulas.values() if f.science_id == science.id),
                          key=lambda f: (f.level, f.name))
        return EntryPage(section="thaumaturgy", title=science.name, kicker="Thaumaturgy · Science",
                         facts=facts, paragraphs=_paragraphs(science.description),
                         source=view.source_label(science.source), blocks=blocks,
                         columns=["Level", SUMMARY], rows_title="Formulas",
                         rows=[Row(thaumaturgy_href(f.id), f.name, [str(f.level), excerpt(f.effects)])
                               for f in formulas])
    ritual = ruleset.thaum_rituals.get(entry_id)
    if ritual is not None:
        return EntryPage(section="thaumaturgy", title=ritual.name,
                         kicker=f"Thaumaturgy · Ritual {_dots(ritual.level)}",
                         facts=[Fact(label, value) for label, value
                                in view._thaum_entry_detail(ritual, "ritual")],
                         paragraphs=_paragraphs(ritual.description),
                         source=view.source_label(ritual.source))
    formula = ruleset.thaum_formulas.get(entry_id)
    if formula is not None:
        facts = [Fact(label, value) for label, value in view._thaum_entry_detail(formula, "formula")
                 if label != "Effects"]
        return EntryPage(section="thaumaturgy", title=formula.name,
                         kicker=f"{_formula_group(ruleset, formula)[len('Formulas · '):]} formula"
                                f" · Level {_dots(formula.level)}",
                         facts=facts, paragraphs=_paragraphs(formula.effects),
                         source=view.source_label(formula.source))
    return None


# --------------------------------------------------------------------------- #
# Paths and powers: the Dragon-King Paths, the elemental powers
# --------------------------------------------------------------------------- #


def power_href(entry_id: str) -> str:
    return f"/wiki/powers/{entry_id}"


_POWER_KINDS = (Option("path", "Dragon-King Paths"), Option("elemental", "Elemental powers"))
_PATHS = "Dragon-King Paths"
_ELEMENTAL = "Elemental powers"


def power_list(ruleset: RuleSet, *, kind: str = "", query: str = "",
               page: int = 1) -> ListPage:
    """Return one page of the Paths and the elemental powers, filtered by kind and by
    the words of `query`."""
    rows: list[tuple[str, Row, str]] = []
    rows += [("path", Row(power_href(p.id), p.name, [p.element_label, excerpt(p.description)],
                          group=_PATHS), " ".join([p.description, *(x.name for x in p.powers)]))
             for p in ruleset.paths.values()]
    rows += [("elemental", Row(power_href(e.id), e.name,
                               [str(e.bp_cost), str(e.min_essence), excerpt(e.description)],
                               group=_ELEMENTAL), e.description)
             for e in sorted(ruleset.elemental_powers.values(), key=lambda e: e.name)]
    kind, kind_filter = _kind_filter(_POWER_KINDS, kind)
    listing = _page("powers", "Paths & Powers", [kind_filter], query, ["Element", SUMMARY],
                    _search(rows, kind, query), page)
    listing.group_columns = {_ELEMENTAL: ["Bonus points", "Minimum Essence", SUMMARY]}
    return listing


def power_page(ruleset: RuleSet, entry_id: str) -> Optional[EntryPage]:
    path = ruleset.paths.get(entry_id)
    if path is not None:
        blocks = []
        for power in sorted(path.powers, key=lambda x: x.dot):
            stats = " · ".join(part for part in (
                f"Type: {power.type.value}", f"Cost: {view._cost_str(power.cost)}",
                f"Duration: {power.duration}" if power.duration else "",
                f"Keywords: {', '.join(power.keywords)}" if power.keywords else "") if part)
            blocks.append(Block(f"{_dots(power.dot)} {power.name}", [stats, *_paragraphs(power.text)]))
        return EntryPage(section="powers", title=path.name,
                         kicker=f"Dragon-King Path · {path.element_label}",
                         facts=[Fact("Element", path.element_label)],
                         paragraphs=_paragraphs(path.description), source="", blocks=blocks)
    power = ruleset.elemental_powers.get(entry_id)
    if power is not None:
        merits = ", ".join(ruleset.merits_flaws[m].name if m in ruleset.merits_flaws else m
                           for m in power.required_merits)
        facts = [Fact(label, value) for label, value in (
            ("Bonus points", str(power.bp_cost)), ("Minimum Essence", str(power.min_essence)),
            ("Requires", merits), ("Activation", power.activation)) if value]
        return EntryPage(section="powers", title=power.name, kicker="Elemental power",
                         facts=facts, paragraphs=_paragraphs(power.description),
                         source=view.source_label(power.source))
    return None


# --------------------------------------------------------------------------- #
# The Storyteller screen
# --------------------------------------------------------------------------- #


def st_screen_count(ruleset: RuleSet) -> int:
    """Return the number of tables of the Storyteller screen."""
    screen = ruleset.st_screen
    return sum(len(group.tables) for group in screen.groups) if screen else 0


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
        "thaumaturgy": (len(ruleset.thaum_arts) + len(ruleset.thaum_sciences)
                        + len(ruleset.thaum_rituals) + len(ruleset.thaum_formulas)),
        "powers": len(ruleset.paths) + len(ruleset.elemental_powers),
        "traits": trait_list(ruleset).total,
        "castes": caste_list(ruleset).total,
        "equipment": equipment_list(ruleset).total,
        "artifacts": len(ruleset.artifact_catalog),
        "st-screen": st_screen_count(ruleset),
    }
    return [SectionSummary(slug, title, counts[slug]) for slug, title in SECTIONS]


def search_all(ruleset: RuleSet, query: str, limit: int = 12) -> list[tuple[ListPage, str]]:
    """Return the first matches of `query` in each section that has a match, with the
    address of the full result list of that section."""
    if not query.strip():
        return []
    lists = (charm_list(ruleset, query=query), style_list(ruleset, query=query),
             spell_list(ruleset, query=query), thaumaturgy_list(ruleset, query=query),
             power_list(ruleset, query=query), merit_list(ruleset, query=query),
             background_list(ruleset, query=query), trait_list(ruleset, query=query),
             caste_list(ruleset, query=query), equipment_list(ruleset, query=query),
             artifact_list(ruleset, query=query))
    results = []
    for result in lists:
        if result.total:
            result.rows = result.rows[:limit]
            results.append((result, f"/wiki/{result.section}"))
    return results


# --------------------------------------------------------------------------- #
# A homebrew row that is not in a ruleset: a proposal or a carried row
# --------------------------------------------------------------------------- #


# The model, the pool of the ruleset, and the page function of each kind.
_HOMEBREW_KINDS = {"charms": (Charm, "charms", charm_page),
                   "spells": (Spell, "spells", spell_page),
                   "rituals": (ThaumaturgicRitual, "thaum_rituals", thaumaturgy_page)}


def homebrew_page(ruleset: RuleSet, kind: str, rows: Sequence[dict],
                  row_id: str) -> Optional[EntryPage]:
    """Return the page of row `row_id` of `rows`, or None if that row does not load.

    `rows` are raw rows of one `kind`: "charms", "spells" or "rituals". Validate
    each row with its model. Put the rows over a copy of `ruleset`, thus a row
    wins an id clash and names the other rows as prerequisites. Then make the page
    with the page function of the kind. `ruleset` does not change.
    """
    model, pool, page = _HOMEBREW_KINDS[kind]
    merged = dict(getattr(ruleset, pool))
    for row in rows:
        try:
            entry = model(**row)
        except (ValidationError, TypeError):
            continue
        merged[entry.id] = entry.model_copy(update={"custom": True})
    if row_id not in merged or not merged[row_id].custom:
        return None
    return page(ruleset.model_copy(update={pool: merged}), row_id)


# --------------------------------------------------------------------------- #
# The entry list, for the sitemap
# --------------------------------------------------------------------------- #

# The list page of each section that has entry pages. The ST Screen has none.
_LIST_BUILDERS: tuple[Callable[..., ListPage], ...] = (
    charm_list, style_list, spell_list, thaumaturgy_list, power_list, merit_list,
    background_list, trait_list, caste_list, equipment_list, artifact_list)


def entry_hrefs(ruleset: RuleSet) -> list[str]:
    """Return the address of each entry page, one time each, in section order.

    Read each page of each unfiltered list. Keep each row that has an address.
    ⚠ Give the BOOK ruleset. The result is public.
    """
    hrefs: dict[str, None] = {}
    for build in _LIST_BUILDERS:
        pages = build(ruleset).pages
        for number in range(1, pages + 1):
            hrefs.update((row.href, None) for row in build(ruleset, page=number).rows
                         if row.href)
    return list(hrefs)
