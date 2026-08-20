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

from PySide6.QtCore import QMarginsF, QSizeF
from PySide6.QtGui import QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget,
)

from exalted_builder.ui import theme
from exalted_builder.ui.view import (armor_stat_line, build_sheet_view,
                                     weapon_stat_line)


# --------------------------------------------------------------------------- #
# HTML rendering — one section at a time, in the order pdf.py assembles them.
# --------------------------------------------------------------------------- #

def _section(title, accent, extra_style=""):
    return (f"<h2 style='{extra_style}color:{accent};border-bottom:2px solid {accent};"
            f"font-size:13pt;margin:10px 0 4px 0'>{_html.escape(title)}</h2>")


def _dots(rating, accent, max_dots=5):
    """A trait rating as a dot track: filled dots in the accent, empty in grey."""
    filled = min(rating, max_dots)
    return (f"<span style='color:{accent}'>{'●' * filled}</span>"
            f"<span style='color:#ccc'>{'○' * (max_dots - filled)}</span>")


def _trait_table(label, rows, accent, footer=""):
    """One labelled trait column (an Attributes/Abilities group, or a derived stat)."""
    esc = _html.escape
    inner = "".join(
        f"<tr><td>{esc(r.label)}"
        f"{'*' if r.caste else '^' if r.favored else ''}</td>"
        f"<td style='padding-left:8px'>{_dots(r.value, accent)}</td></tr>" for r in rows)
    if footer:
        inner += f"<tr><td colspan='2' style='color:{accent}'>{esc(footer)}</td></tr>"
    return (f"<table width='100%' style='border-collapse:collapse'>"
            f"<tr><th colspan='2' style='text-align:left;color:{accent};"
            f"border-bottom:1px solid {accent}'>{esc(label)}</th></tr>{inner}</table>")


def _columns(tables, columns):
    """Lay `tables` (HTML fragments) into rows of `columns` cells, each column after
    the first separated from its neighbour by a light vertical rule."""
    rows = []
    for i in range(0, len(tables), columns):
        chunk = tables[i:i + columns]
        cells = []
        for j, t in enumerate(chunk):
            sep = "border-left:1px solid #e0e0e0;padding-left:10px;" if j > 0 else ""
            cells.append(f"<td valign='top' width='{100 // columns}%' style='{sep}'>{t}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table width='100%' style='border-collapse:collapse'>{''.join(rows)}</table>"


def _advantages_blocks(view, accent):
    """The non-empty Advantage panels (Backgrounds, Artifacts, Merits, …), as a list
    of HTML fragments for `_columns` to lay side by side."""
    esc = _html.escape
    blocks = []
    if view.backgrounds:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td>{_dots(r, accent)}</td>"
                       f"<td style='color:#888;padding-left:14px'>{esc(note)}</td></tr>"
                       for n, r, note in view.backgrounds)
        blocks.append(f"<b>Backgrounds</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.artifacts:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td>{_dots(r, accent)}</td>"
                       f"<td style='color:#888;padding-left:14px'>{esc(note)}{' · damaged' if d else ''}</td></tr>"
                       for n, r, note, d in view.artifacts)
        blocks.append(f"<b>Artifacts</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.merits_flaws:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td style='text-align:right'>{esc(cost)}</td>"
                       f"<td style='color:#888;padding-left:14px'>{esc(detail)}</td></tr>"
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
                       f"<span style='color:{accent}'>{'●' * count}</span></td></tr>"
                       for (a, n), count in counts.items())
        blocks.append(f"<b>Specialties</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.thaumaturgy:
        rows = "".join(f"<tr><td><b>{esc(sec)}</b></td>"
                       f"<td style='color:#888;padding-left:14px'>{esc(', '.join(items))}</td></tr>"
                       for sec, items in view.thaumaturgy)
        blocks.append(f"<b>Thaumaturgy</b><table style='border-collapse:collapse'>{rows}</table>")
    if view.colleges:
        rows = "".join(f"<tr><td style='padding-right:10px'>{esc(n)}</td>"
                       f"<td>{_dots(r, accent)}</td>"
                       f"<td style='color:#888;padding-left:14px'>{esc(hl)}</td></tr>"
                       for n, r, hl, _own in view.colleges)
        blocks.append(f"<b>Colleges</b><table style='border-collapse:collapse'>{rows}</table>")
    return blocks


def _willpower_html(rating, accent):
    """Willpower as a 10-dot track with a 10-square tracker underneath."""
    return (f"<table width='100%'><tr><th style='text-align:left;color:{accent};"
            f"border-bottom:1px solid {accent}'>Willpower</th></tr>"
            f"<tr><td>{_dots(rating, accent, 10)}</td></tr>"
            f"<tr><td style='color:#aaa'>{'□' * 10}</td></tr></table>")


def _health_track_html(levels):
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
        f"<tr><td><span style='font-family:monospace;color:#555;font-size:8pt'>{label}"
        f"{'&nbsp;' * (width - len(label))}</span>"
        f"<span style='color:#aaa;font-size:10pt'>&nbsp;{'□' * count}</span></td></tr>"
        for label, count in labels)
    return f"<table style='border-collapse:collapse'>{rows}</table>"


def _health_cell(view, accent):
    """The health track as a trait-band COLUMN, alongside the other stats."""
    return (f"<table width='100%'><tr><th style='text-align:left;color:{accent};"
            f"border-bottom:1px solid {accent}'>Health</th></tr>"
            f"<tr><td>{_health_track_html(view.health)}</td></tr></table>")


def _equipment_cell(view, accent):
    """Equipment (Weapons / Armour) as a trait-band COLUMN, alongside Willpower,
    Virtues, Essence and Soak — not a block below the band."""
    esc = _html.escape
    rows = []
    for w in view.weapons:
        rows.append(f"<tr><td>{esc(w.name)}</td>"
                    f"<td style='color:#888'>{esc(weapon_stat_line(w))}</td></tr>")
    for a in view.armor:
        rows.append(f"<tr><td>{esc(a.name)}</td>"
                    f"<td style='color:#888'>{esc(armor_stat_line(a))}</td></tr>")
    if not rows:
        return ""
    return (f"<table width='100%'><tr><th colspan='2' style='text-align:left;color:{accent};"
            f"border-bottom:1px solid {accent}'>Equipment</th></tr>{''.join(rows)}</table>")


def _traits_html(view, accent):
    """Willpower, Virtues, Essence pools, Soak, Health, and Equipment — the trait band."""
    soak = view.soak
    soak_line = (f"Soak {soak.bashing}B / {soak.lethal}L"
                 + (f" / {soak.aggravated}A" if soak.aggravated else ""))
    cells = [
        _willpower_html(view.willpower, accent),
        _trait_table("Virtues", view.virtues, accent),
        _trait_table("Essence", [], accent, footer=view.essence_pool_label()),
        _trait_table("Soak", [], accent, footer=soak_line),
        _health_cell(view, accent),
    ]
    equipment = _equipment_cell(view, accent)
    if equipment:
        cells.append(equipment)
    # THREE columns (two rows of three), not one row of six: at A4 width a six-column
    # band truncates the content ("Compa", "Daikla") — the on-screen window is wide
    # enough to hide it, the printed page is not.
    return _columns(cells, 3)


def _holdings_html(view, accent):
    """The Charm/Spell/Path/Combo lists — rendered only when non-empty."""
    esc = _html.escape
    blocks = []
    for label, rows in view.charm_sections:
        if not rows:
            continue
        items = "".join(
            f"<tr><td style='padding-right:10px'>{esc(r.name)}</td>"
            f"<td style='color:#888;padding-left:8px'>{esc(r.cost)}{f' · {esc(r.duration)}' if r.duration else ''}</td></tr>"
            for r in rows)
        blocks.append(f"<b>{esc(label)}</b><table style='border-collapse:collapse'>{items}</table>")
    if view.spells:
        items = "".join(
            f"<tr><td style='padding-right:10px'>{esc(s.name)}</td>"
            f"<td style='color:#888;padding-left:8px'>{esc(s.circle)}{f' · {esc(s.cost)}' if s.cost else ''}</td></tr>"
            for s in view.spells)
        blocks.append(f"<b>Spells</b><table style='border-collapse:collapse'>{items}</table>")
    if view.paths:
        items = "".join(
            f"<tr><td>{esc(p.name)}</td><td style='text-align:right'>{p.rating}</td></tr>"
            for p in view.paths)
        blocks.append(f"<b>Paths</b><table style='border-collapse:collapse'>{items}</table>")
    if view.combos:
        items = "".join(
            f"<tr><td>{esc(n)}</td><td style='color:#888'>{esc(', '.join(m))}</td></tr>"
            for n, m, _cost in view.combos)
        blocks.append(f"<b>Combos</b><table style='border-collapse:collapse'>{items}</table>")
    return "<br>".join(blocks)


def sheet_html(view):
    """Full HTML for one SheetView, sections in pdf.py's order, splat accent headers."""
    accent = theme.palette(view.exalt_type).accent
    esc = _html.escape
    parts = [f"<h1 style='color:{accent};font-size:20pt;margin:0'>{esc(view.name)}</h1>"]
    meta = [f"<b>{esc(view.exalt_type)}</b>"]
    if view.caste:
        meta.append(f"{esc(view.caste_noun)}: {esc(view.caste)}")
    for label, val in (("Player", view.player), ("Concept", view.concept),
                       ("Nature", view.nature), ("Anima", view.anima)):
        if val:
            meta.append(f"{label}: {esc(val)}")
    parts.append("<div style='color:#555;margin:2px 0 6px 0'>" + " · ".join(meta) + "</div>")

    parts.append(_section("Attributes", accent))
    parts.append(_columns([_trait_table(label, rows, accent)
                           for label, rows in view.attributes], 3))

    parts.append(_section("Abilities", accent))
    parts.append(_columns([_trait_table(label, rows, accent)
                           for label, rows in view.ability_groups], 3))

    advantages = _advantages_blocks(view, accent)
    if advantages:
        parts.append(_section("Advantages", accent))
        # TWO columns, not three: at A4 width the three-up advantages cram the names
        # and notes into mid-word-wrapped fragments ("Reinforce d Buﬀ").
        parts.append(_columns(advantages, 2))

    # Force the break before Traits: the trait band straddled the natural page break
    # (page 1 ended mid-band). Starting Traits on a fresh page keeps the whole band —
    # and Charms after it — on page 2, un-split.
    parts.append(_section("Traits", accent, "page-break-before:always;"))
    parts.append(_traits_html(view, accent))

    holdings = _holdings_html(view, accent)
    if holdings:
        parts.append(_section("Charms & Spells", accent))
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
    on-screen view scrolls continuously; the printed PDF comes from the same document
    via `print_pdf` (the page size is reset there)."""

    def __init__(self, ruleset, ctx, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._doc = None
        self.view = QTextBrowser()
        # The sheet is a DOCUMENT — it stays light "paper" on the dark app chrome,
        # and the printed PDF comes from the same document (page size reset in print).
        self.view.setStyleSheet("QTextBrowser { background:#fffdf7; color:#1a1a1a; }")
        hint = QLabel("The on-screen sheet; Print PDF… exports the same document.")
        hint.setStyleSheet("color:#6b7280;")
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.view, 1)
        self.reload()

    def reload(self):
        sheet = build_sheet_view(self._ruleset, self._ctx["char"])
        self._doc = build_document(sheet_html(sheet))
        self.view.setDocument(self._doc)
