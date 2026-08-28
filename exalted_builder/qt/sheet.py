"""exalted_builder/qt/sheet.py — the Sheet tab: the printable sheet as a QTextDocument.

Input: a RuleSet and a Character (from the shared context). Output: a QTextBrowser
showing the sheet as a scrollable document, re-rendered from `build_sheet_view` on
every reload. Mechanism: `sheet_html` builds the sections in pdf.py's order (header,
Attributes, Abilities, Advantages, Traits, Holdings) with the splat accent colour;
`build_document` lays that into a paginated QTextDocument; `print_pdf` writes the same
document via QPdfWriter — one source for the on-screen sheet and the printed page.

This is the port of spikes/qt_sheet/ (human-approved 2026-08-20); the HTML builders
and the print path are that spike's tested core, carried over.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget,
)

from exalted_builder.ui import theme
from exalted_builder.ui.view import (armor_stat_line, build_sheet_view,
                                     weapon_stat_line)

from . import theme as qtheme


# --------------------------------------------------------------------------- #
# The sheet's colours — one set for PAPER, one for the SCREEN
#
# ⚠ The sheet used to be light "paper" on screen as well as in print (the human's
# 2026-08-20 direction). Reversed 2026-08-27: on a dark app a white page is a
# flashbang, and the Reference tab had inherited the same treatment by copying it.
# The PRINTED document keeps the paper set — ink on white is what a sheet at the
# table should be — so this is one document with two palettes rather than two
# documents, which is what kept `print_pdf` honest in the first place.
#
# ⚠ The printed palette accents are DARK (Solar amber #8a5a1a) and vanish on the dark
# base, so the screen set lightens the accent exactly as `qt/theme.py::accent` does
# for every other widget. A sheet is not exempt from that rule just because it is a
# document.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SheetColors:
    """Every colour the sheet draws with. `label` is the health track's monospace
    penalty caption and the identity line; `faint` is an UNFILLED dot or box, which
    must read as empty without disappearing; `rule` is the vertical column divider.

    `ink` and `paper` are the body text and page shade. ⚠ They are the only two the
    HTML does NOT carry — a QTextBrowser takes them from the widget's own stylesheet,
    so a caller that renders on screen must set them there as well as build the HTML."""
    accent: str
    ink: str
    label: str
    muted: str
    faint: str
    rule: str
    paper: str


def print_colors(exalt_type: str | None) -> SheetColors:
    """Ink on paper — the printed PDF, and the default for `sheet_html`."""
    return print_colors_for(theme.palette(exalt_type))


def screen_colors(exalt_type: str | None) -> SheetColors:
    """The same sheet on the dark app chrome."""
    return screen_colors_for(theme.palette(exalt_type))


def print_colors_for(pal: theme.Palette) -> SheetColors:
    """`print_colors` for a caller that already holds the Palette (the party window's
    chrome is a palette, not an Exalt type)."""
    return SheetColors(accent=pal.accent, ink="#1a1a1a",
                       label="#555555", muted="#888888", faint="#aaaaaa",
                       rule="#e0e0e0", paper="#fffdf7")


def screen_colors_for(pal: theme.Palette) -> SheetColors:
    """`screen_colors` for a caller that already holds the Palette."""
    return SheetColors(accent=qtheme.accent(pal), ink=qtheme.INK,
                       label=qtheme.MUTED, muted=qtheme.MUTED, faint="#6f6f79",
                       rule="#55555f", paper=qtheme.CARD)


# --------------------------------------------------------------------------- #
# HTML rendering — one section at a time, in the order pdf.py assembles them.
# --------------------------------------------------------------------------- #

def _section(title, c, extra_style=""):
    return (f"<h2 style='{extra_style}color:{c.accent};border-bottom:2px solid {c.accent};"
            f"font-size:13pt;margin:10px 0 4px 0'>{_html.escape(title)}</h2>")


def _dots(rating, c, max_dots=5):
    """A trait rating as a dot track: filled dots in the accent, empty in grey."""
    filled = min(rating, max_dots)
    return (f"<span style='color:{c.accent}'>{'●' * filled}</span>"
            f"<span style='color:{c.faint}'>{'○' * (max_dots - filled)}</span>")


def _trait_table(label, rows, c, footer=""):
    """One labelled trait column (an Attributes/Abilities group, or a derived stat)."""
    esc = _html.escape
    inner = "".join(
        f"<tr><td>{esc(r.label)}"
        f"{'*' if r.caste else '^' if r.favored else ''}</td>"
        f"<td style='padding-left:8px'>{_dots(r.value, c)}</td></tr>" for r in rows)
    if footer:
        inner += f"<tr><td colspan='2' style='color:{c.accent}'>{esc(footer)}</td></tr>"
    return (f"<table width='100%' style='border-collapse:collapse'>"
            f"<tr><th colspan='2' style='text-align:left;color:{c.accent};"
            f"border-bottom:1px solid {c.accent}'>{esc(label)}</th></tr>{inner}</table>")


def _columns(tables, columns, c):
    """Lay `tables` (HTML fragments) into rows of `columns` cells, each column after
    the first separated from its neighbour by a light vertical rule."""
    rows = []
    for i in range(0, len(tables), columns):
        chunk = tables[i:i + columns]
        cells = []
        for j, t in enumerate(chunk):
            sep = f"border-left:1px solid {c.rule};padding-left:10px;" if j > 0 else ""
            cells.append(f"<td valign='top' width='{100 // columns}%' style='{sep}'>{t}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table width='100%' style='border-collapse:collapse'>{''.join(rows)}</table>"


def _advantages_blocks(view, c):
    """The non-empty Advantage panels (Backgrounds, Artifacts, Merits, …), as a list
    of HTML fragments for `_columns` to lay side by side."""
    esc = _html.escape
    blocks = []
    if view.backgrounds:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td>{_dots(r, c)}</td>"
                       f"<td style='color:{c.muted};padding-left:14px'>{esc(note)}</td></tr>"
                       for n, r, note in view.backgrounds)
        blocks.append(f"<b>Backgrounds</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.artifacts:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td>{_dots(r, c)}</td>"
                       f"<td style='color:{c.muted};padding-left:14px'>{esc(note)}{' · damaged' if d else ''}</td></tr>"
                       for n, r, note, d in view.artifacts)
        blocks.append(f"<b>Artifacts</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.merits_flaws:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td style='text-align:right'>{esc(cost)}</td>"
                       f"<td style='color:{c.muted};padding-left:14px'>{esc(detail)}</td></tr>"
                       for n, cost, detail, _kind, _tip in view.merits_flaws)
        blocks.append(f"<b>Merits &amp; Flaws</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.specialties:
        # A specialty is an INSTANCE, not a rated trait: "multiple dots" means
        # multiple copies of the same specialty (human 2026-08-20). Merge the copies
        # and show the count as plain dots — NO 5-dot track, which implies a rating
        # the 1e rule does not have.
        counts: dict[tuple[str, str], int] = {}
        for ability, name, rating in view.specialties:
            counts[(ability, name)] = counts.get((ability, name), 0) + rating
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(a)}</td>"
                       f"<td>{esc(n)}</td>"
                       f"<td style='padding-left:8px'>"
                       f"<span style='color:{c.accent}'>{'●' * count}</span></td></tr>"
                       for (a, n), count in counts.items())
        blocks.append(f"<b>Specialties</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.thaumaturgy:
        rows = "".join(f"<tr><td><b>{esc(sec)}</b></td>"
                       f"<td style='color:{c.muted};padding-left:14px'>{esc(', '.join(items))}</td></tr>"
                       for sec, items in view.thaumaturgy)
        blocks.append(f"<b>Thaumaturgy</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.colleges:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td>{_dots(r, c)}</td>"
                       f"<td style='color:{c.muted};padding-left:14px'>{esc(hl)}</td></tr>"
                       for n, r, hl, _own in view.colleges)
        blocks.append(f"<b>Colleges</b><table style='border-collapse:collapse'>{rows}</table>")
    return blocks


def _willpower_html(rating, c):
    """Willpower as a 10-dot track with a 10-square tracker underneath."""
    return (f"<table width='100%'><tr><th style='text-align:left;color:{c.accent};"
            f"border-bottom:1px solid {c.accent}'>Willpower</th></tr>"
            f"<tr><td>{_dots(rating, c, 10)}</td></tr>"
            f"<tr><td style='color:{c.faint}'>{'□' * 10}</td></tr></table>")


def _health_track_html(levels, c):
    """The health track as one row per level: the penalty label on the left, the
    level's boxes to its right. Boxes of one level are a single text run, so they
    never split across lines. The ★ marker for Charm-granted levels is dropped — the
    boxes are mechanically identical in play (human 2026-08-20) — and it is stripped
    BEFORE grouping, so natural and Charm-granted levels merge into one row."""
    clean = [label.split("★")[0].strip() for label in levels]
    groups = []
    for label in clean:
        if groups and groups[-1][0] == label:
            groups[-1][1] += 1
        else:
            groups.append([label, 1])
    labels = [(_html.escape(label), count) for label, count in groups]
    # Pad every label to the widest one with non-breaking spaces, so the boxes column
    # starts at the same x on every row. The label is MONOSPACE: in a proportional
    # font, character-count padding does not equal pixel width, so "Incap" pushed its
    # boxes right of the padded shorter labels; monospace makes every char (and every
    # nbsp) the same width, so padding to the same length IS padding to the same x.
    width = max(len(label) for label, _ in labels)
    rows = "".join(
        # Label and boxes on ONE line (same text line ⇒ same baseline). Separate
        # table cells with different font sizes misalign baselines, so the small
        # label rendered superscripted above the boxes. Boxes wrap at the column
        # boundary — a ten-wide -2 row keeps 8 on the first line and wraps the rest
        # onto the next line WITHIN the column; nbsp-joining the run instead made it
        # overflow the column edge (human 2026-08-20).
        f"<tr><td><span style='font-family:monospace;color:{c.label};font-size:8pt'>{label}"
        f"{'&nbsp;' * (width - len(label))}</span>"
        f"<span style='color:{c.faint};font-size:10pt'>&nbsp;{'□' * count}</span></td></tr>"
        for label, count in labels)
    return f"<table style='border-collapse:collapse'>{rows}</table>"


def _health_cell(view, c):
    """The health track as a trait-band COLUMN, alongside the other stats."""
    return (f"<table width='100%'><tr><th style='text-align:left;color:{c.accent};"
            f"border-bottom:1px solid {c.accent}'>Health</th></tr>"
            f"<tr><td>{_health_track_html(view.health, c)}</td></tr></table>")


def _equipment_cell(view, c):
    """Equipment (Weapons / Armour) as a trait-band COLUMN, alongside Willpower,
    Virtues, Essence and Soak — not a block below the band."""
    esc = _html.escape
    rows = []
    for w in view.weapons:
        rows.append(f"<tr><td>{esc(w.name)}</td>"
                    f"<td style='color:{c.muted}'>{esc(weapon_stat_line(w))}</td></tr>")
    for a in view.armor:
        rows.append(f"<tr><td>{esc(a.name)}</td>"
                    f"<td style='color:{c.muted}'>{esc(armor_stat_line(a))}</td></tr>")
    if not rows:
        return ""
    return (f"<table width='100%'><tr><th colspan='2' style='text-align:left;color:{c.accent};"
            f"border-bottom:1px solid {c.accent}'>Equipment</th></tr>{''.join(rows)}</table>")


def _traits_html(view, c):
    """Willpower, Virtues, Essence pools, Soak, Health, and Equipment — the trait band."""
    soak = view.soak
    soak_line = (f"Soak {soak.bashing}B / {soak.lethal}L"
                 + (f" / {soak.aggravated}A" if soak.aggravated else ""))
    cells = [
        _willpower_html(view.willpower, c),
        _trait_table("Virtues", view.virtues, c),
        _trait_table("Essence", [], c, footer=view.essence_pool_label()),
        _trait_table("Soak", [], c, footer=soak_line),
        _health_cell(view, c),
    ]
    equipment = _equipment_cell(view, c)
    if equipment:
        cells.append(equipment)
    # THREE columns (two rows of three), not one row of six: at A4 width a six-column
    # band truncates the content ("Compa", "Daikla") — the on-screen window is wide
    # enough to hide it, the printed page is not.
    return _columns(cells, 3, c)


def _holdings_html(view, c):
    """The Charm/Spell/Path/Combo lists — rendered only when non-empty."""
    esc = _html.escape
    blocks = []
    for label, rows in view.charm_sections:
        if not rows:
            continue
        items = "".join(
            f"<tr><td style='padding-right:10px'>{esc(r.name)}</td>"
            f"<td style='color:{c.muted};padding-left:8px'>{esc(r.cost)}{f' · {esc(r.duration)}' if r.duration else ''}</td></tr>"
            for r in rows)
        blocks.append(f"<b>{esc(label)}</b><table style='border-collapse:collapse'>{items}</table>")
    if view.spells:
        items = "".join(
            f"<tr><td style='padding-right:10px'>{esc(s.name)}</td>"
            f"<td style='color:{c.muted};padding-left:8px'>{esc(s.circle)}{f' · {esc(s.cost)}' if s.cost else ''}</td></tr>"
            for s in view.spells)
        blocks.append(f"<b>Spells</b><table style='border-collapse:collapse'>{items}</table>")
    if view.paths:
        items = "".join(
            f"<tr><td>{esc(p.name)}</td><td style='text-align:right'>{p.rating}</td></tr>"
            for p in view.paths)
        blocks.append(f"<b>Paths</b><table style='border-collapse:collapse'>{items}</table>")
    if view.combos:
        items = "".join(
            f"<tr><td>{esc(n)}</td><td style='color:{c.muted}'>{esc(', '.join(m))}</td></tr>"
            for n, m, _cost in view.combos)
        blocks.append(f"<b>Combos</b><table style='border-collapse:collapse'>{items}</table>")
    return "<br>".join(blocks)


def sheet_html(view, colors: SheetColors | None = None):
    """Full HTML for one SheetView, sections in pdf.py's order, splat accent headers.

    `colors` defaults to the PAPER set, so a caller that just wants a printable sheet
    is unchanged; the on-screen tabs pass `screen_colors(...)`."""
    c = colors if colors is not None else print_colors(view.exalt_type)
    esc = _html.escape
    parts = [f"<h1 style='color:{c.accent};font-size:20pt;margin:0'>{esc(view.name)}</h1>"]
    meta = [f"<b>{esc(view.exalt_type)}</b>"]
    if view.caste:
        meta.append(f"{esc(view.caste_noun)}: {esc(view.caste)}")
    for label, val in (("Player", view.player), ("Concept", view.concept),
                       ("Nature", view.nature), ("Anima", view.anima)):
        if val:
            meta.append(f"{label}: {esc(val)}")
    parts.append(f"<div style='color:{c.label};margin:2px 0 6px 0'>" + " · ".join(meta) + "</div>")

    parts.append(_section("Attributes", c))
    parts.append(_columns([_trait_table(label, rows, c)
                           for label, rows in view.attributes], 3, c))

    parts.append(_section("Abilities", c))
    parts.append(_columns([_trait_table(label, rows, c)
                           for label, rows in view.ability_groups], 3, c))

    advantages = _advantages_blocks(view, c)
    if advantages:
        parts.append(_section("Advantages", c))
        # TWO columns, not three: at A4 width the three-up advantages cram the names
        # and notes into mid-word-wrapped fragments ("Reinforce d Buﬀ").
        parts.append(_columns(advantages, 2, c))

    # Force the break before Traits: the trait band straddled the natural page break
    # (page 1 ended mid-band). Starting Traits on a fresh page keeps the whole band —
    # and Charms after it — on page 2, un-split.
    parts.append(_section("Traits", c, "page-break-before:always;"))
    parts.append(_traits_html(view, c))

    holdings = _holdings_html(view, c)
    if holdings:
        parts.append(_section("Charms & Spells", c))
        parts.append(holdings)
    return "".join(parts)


# --------------------------------------------------------------------------- #
# QTextDocument + printing
# --------------------------------------------------------------------------- #

def build_document(html_text, paper="A4"):
    """A QTextDocument holding the sheet HTML, paginated for `paper`."""
    doc = QTextDocument()
    doc.setHtml(html_text)
    doc.setDocumentMargin(12)
    size = QPageSize(QPageSize.A4 if paper == "A4" else QPageSize.Letter).sizePoints()
    doc.setPageSize(QSizeF(size.width(), size.height()))
    return doc


def print_pdf(doc, path, paper="A4"):
    """Write `doc`, paginated, to a PDF at `path` via QPdfWriter.

    ⚠ `doc` must be built from `sheet_html(view)` — the PAPER colours. The on-screen
    document is the screen set, and printing that one puts a dark page on white paper.

    ⚠ The document's page size is reset to the paper FIRST: a doc shown in a
    QTextBrowser has had its page size rewritten to the viewport (unbounded height,
    for scrolling), and printing such a doc makes Qt render page numbers — the
    on-screen window's print always carried a footer the offline path never did."""
    size = QPageSize(QPageSize.A4 if paper == "A4" else QPageSize.Letter).sizePoints()
    doc.setPageSize(QSizeF(size.width(), size.height()))
    writer = QPdfWriter(path)
    writer.setResolution(300)                       # print-grade, not screen (120)
    writer.setPageSize(QPageSize(QPageSize.A4 if paper == "A4" else QPageSize.Letter))
    writer.setPageMargins(QMarginsF(12, 12, 12, 12))
    doc.print_(writer)


# --------------------------------------------------------------------------- #
# The Sheet tab widget
# --------------------------------------------------------------------------- #

class SheetPage(QWidget):
    """The read-only Sheet tab: a scrollable QTextDocument re-rendered on reload.

    Takes the shared (ruleset, ctx); `reload()` re-reads ctx['char'], so a New/Load
    or a lock re-themes and re-fills the sheet without rebuilding the window. The
    on-screen view scrolls continuously and is drawn in the SCREEN colours; the
    printed PDF is the same HTML in the paper set (`print_pdf`, or `ui/pdf.py`)."""

    def __init__(self, ruleset, ctx, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._doc = None
        self.view = QTextBrowser()
        hint = QLabel("The on-screen sheet; Print PDF… exports the same document.")
        hint.setStyleSheet(f"color:{qtheme.MUTED};")
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.view, 1)
        self.reload()

    def reload(self):
        sheet = build_sheet_view(self._ruleset, self._ctx["char"])
        colors = screen_colors(sheet.exalt_type)
        self._doc = build_document(sheet_html(sheet, colors))
        # ⚠ The document's own colours are not enough: the widget's background is the
        # shell QSS's, so the page shade has to be set here for the two to agree — and
        # a splat change re-renders, so it is set on every reload, not once.
        self.view.setStyleSheet(
            f"QTextBrowser {{ background:{colors.paper}; color:{colors.ink}; }}")
        self.view.setDocument(self._doc)
