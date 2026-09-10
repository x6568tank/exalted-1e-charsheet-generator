"""exalted_builder/qt/sheet.py — the Sheet tab: the printable sheet as a QTextDocument.

Input: a RuleSet and a Character from the shared context. Output: a QTextBrowser that
shows the sheet as a scrollable document. Each reload renders it again from
`build_sheet_view`. Mechanism: `sheet_html` builds the sections in the order of `pdf.py`
(header, Attributes, Abilities, Advantages, Traits, Holdings), in the accent colour of the
splat. `build_document` puts that HTML into a paginated QTextDocument. `print_pdf` writes
the same document with QPdfWriter. Thus the screen sheet and the printed page have one
source.
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
# ⚠ The SCREEN set is dark. A white page in a dark app is too bright (human's ruling).
# The PRINTED document keeps the paper set, because a sheet at the table is ink on white.
# This is ONE document with two palettes. Do not make it two documents. One document is
# what keeps `print_pdf` and the screen sheet the same.
#
# ⚠ The printed accents are DARK (Solar amber #8a5a1a) and are not visible on the dark
# base. Thus the screen set makes the accent lighter, in the same way as
# `qt/theme.py::accent` does for every other widget. This rule also applies to a document.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class SheetColors:
    """Every colour that the sheet uses. `label` is the monospace penalty caption of the
    health track, and the identity line. `faint` is an UNFILLED dot or box. It must read
    as empty, and it must stay visible. `rule` is the vertical column divider.

    `ink` and `paper` are the body text and the page shade. ⚠ The HTML does NOT carry
    these two colours. A QTextBrowser takes them from the stylesheet of the widget. Thus a
    caller that renders on the screen must set them on the widget and build the HTML."""
    accent: str
    ink: str
    label: str
    muted: str
    faint: str
    rule: str
    paper: str


def print_colors(exalt_type: str | None) -> SheetColors:
    """Ink on paper. This set prints the PDF, and it is the default for `sheet_html`."""
    return print_colors_for(theme.palette(exalt_type))


def screen_colors(exalt_type: str | None) -> SheetColors:
    """The same sheet on the dark app chrome."""
    return screen_colors_for(theme.palette(exalt_type))


def print_colors_for(pal: theme.Palette) -> SheetColors:
    """`print_colors` for a caller that holds the Palette. The chrome of the party window
    is a Palette, not an Exalt type."""
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
                       f"<td style='color:{c.muted};padding-left:14px'>"
                       f"{esc(' · '.join(x for x in (note, att) if x))}"
                       f"{' · damaged' if d else ''}</td></tr>"
                       for n, r, note, d, att in view.artifacts)
        blocks.append(f"<b>Artifacts</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.merits_flaws:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td style='text-align:right'>{esc(cost)}</td>"
                       f"<td style='color:{c.muted};padding-left:14px'>{esc(detail)}</td></tr>"
                       for n, cost, detail, _kind, _tip in view.merits_flaws)
        blocks.append(f"<b>Merits &amp; Flaws</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.specialties:
        # A specialty is an INSTANCE, not a rated trait. More than one dot means more than
        # one copy of the same specialty (human's ruling). Merge the copies and show the
        # count as plain dots. ⚠ Do NOT draw a 5-dot track. A track shows a rating, and
        # the 1E rule has no rating here.
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
    """The health track, with one row for each level. The penalty label is on the left,
    and the boxes of that level are on the right. The boxes of one level are one text run.
    Thus they do not divide across two lines. This code removes the ★ marker of a
    Charm-granted level, because the boxes operate in the same way in play (human's
    ruling). It removes the marker BEFORE it groups the levels. Thus a natural level and a
    Charm-granted level become one row."""
    clean = [label.split("★")[0].strip() for label in levels]
    groups = []
    for label in clean:
        if groups and groups[-1][0] == label:
            groups[-1][1] += 1
        else:
            groups.append([label, 1])
    labels = [(_html.escape(label), count) for label, count in groups]
    # Pad each label to the width of the widest label with non-breaking spaces. Thus the
    # column of boxes starts at the same x on every row. ⚠ The label must be MONOSPACE. In
    # a proportional font, a pad by character count is not a pad by pixel width, and
    # "Incap" then puts its boxes to the right of the shorter labels. In a monospace font,
    # each character and each nbsp has the same width. Thus a pad to the same length is a
    # pad to the same x.
    width = max(len(label) for label, _ in labels)
    rows = "".join(
        # Put the label and the boxes on ONE text line. One text line gives one baseline.
        # ⚠ Two table cells with different font sizes do not share a baseline, and the
        # small label then prints above the boxes. The boxes wrap at the column edge. A
        # ten-box -2 row keeps 8 boxes on the first line and wraps the rest WITHIN the
        # column. ⚠ Do not join the run with nbsp. The run then goes past the column edge.
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
    """Equipment (Weapons / Armour) as a COLUMN in the trait band, next to Willpower,
    Virtues, Essence and Soak. It is not a block below the band."""
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
    # ⚠ Use THREE columns, in two rows of three. Do not use one row of six. At A4 width, a
    # six-column band cuts the content, for example "Compa" and "Daikla". The screen
    # window is wide, thus it hides this fault. The printed page shows it.
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
    """The full HTML for one SheetView. The sections are in the order of `pdf.py`, and the
    headers take the accent of the splat.

    The default of `colors` is the PAPER set. Thus a caller that wants a printable sheet
    supplies no colours. The screen tabs supply `screen_colors(...)`."""
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
        # ⚠ Use TWO columns, not three. At A4 width, three columns of Advantages divide
        # the names and the notes in the middle of a word, for example "Reinforce d Buﬀ".
        parts.append(_columns(advantages, 2, c))

    # Force a page break before Traits. Without it, the natural page break divides the
    # trait band, and page 1 ends in the middle of the band. A break here keeps the full
    # band, and the Charms after it, together on page 2.
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

    ⚠ Build `doc` from `sheet_html(view)`, which uses the PAPER colours. The screen
    document uses the screen set, and it prints a dark page onto white paper.

    ⚠ Set the page size of the document to the paper FIRST. A document that a QTextBrowser
    shows has the page size of the viewport, which has no height limit for scrolling. When
    Qt prints such a document, it renders page numbers. Thus a print from the screen window
    carries a footer, and a print from the offline path does not."""
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
    """The read-only Sheet tab. It holds a scrollable QTextDocument, and each reload
    renders it again.

    Input: the shared (ruleset, ctx). `reload()` reads ctx['char'] again. Thus a New, a
    Load or a lock re-themes and re-fills the sheet, and the window stays. The screen view
    scrolls continuously in the SCREEN colours. The printed PDF is the same HTML in the
    paper set (`print_pdf`, or `ui/pdf.py`)."""

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
        # ⚠ The colours of the document are not sufficient. The shell QSS supplies the
        # background of the widget. Thus you must set the page shade here, and the two
        # then agree. A splat change renders the sheet again. Thus set the shade on every
        # reload, not one time.
        self.view.setStyleSheet(
            f"QTextBrowser {{ background:{colors.paper}; color:{colors.ink}; }}")
        self.view.setDocument(self._doc)
