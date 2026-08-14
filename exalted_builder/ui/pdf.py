"""
ui/pdf.py — the printed character sheet, as a generated PDF.

Why this exists rather than a print stylesheet: `Ctrl+P` on the Sheet tab prints
the app's DOM — tinted cards, truncated flex rows, tab chrome — and no amount of
`@media print` turns a screen layout into a sheet. The human tried it and rejected
it. So this lays out a document designed for paper, from the same data the screen
sheet renders from.

Three constraints, each load-bearing (docs/plans/print-pdf.md):

1. `build_pdf` takes a `SheetView` and NOTHING else — no RuleSet, no Character, no
   callbacks. That is the purity `app.render_sheet` already has, and it is what
   lets the builder, the GM party screen and the tests share one renderer.
2. This module must not import `nicegui`. It imports reportlab and `theme` (itself
   pure). A test asserts it. That keeps the PDF export in the set of modules a
   future PySide6 build carries over unchanged (docs/plans/qt-port.md).
3. No game logic. Page geometry is presentation; everything mechanical was already
   decided by the engine before `build_sheet_view` handed us this dataclass.

⚠ EVERY GLYPH IS DRAWN OR ASCII. reportlab's base-14 fonts are latin-1, so the
marks the screen sheet leans on — the caste dot, the favoured star, the crossed
swords, the shield, the custom-content pencil — are not available and would print
as blanks or black boxes. Dots and health boxes are vector art (which is crisper
anyway); the rest became words. Do not paste a glyph in here from ui/app.py.

The human's content rulings, all four recorded in docs/plans/print-pdf.md:
Charms and spells print as NAMES AND COSTS ONLY (no description text anywhere);
notes print but rules text does not; neither the validation panel nor the XP
ledger prints; splat-themed accent on a white page, no filled card tints.
"""

from __future__ import annotations

import io
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (CondPageBreak, Flowable, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from . import theme
from .view import SheetView

# --------------------------------------------------------------------------- #
# What this renderer does NOT print, declared rather than merely absent.
#
# tests/test_pdf.py walks dataclasses.fields(SheetView) and fails on any field
# that is neither read below nor named here. That is deliberate: this project's
# recurring bug is a field nothing reads, and on a PDF an unread field is simply
# missing from the paper — the one failure mode nobody notices. A new splat that
# adds a panel to the screen sheet now has to decide about the printed one too.
# --------------------------------------------------------------------------- #

#: Ruled off the printed sheet by the human, 2026-08-14 (decision 4 of the plan).
#: `issues` and the four `xp_*` ledger fields are build-time tools, not table-time
#: ones; the experience TOTAL still prints. `charms` is the flat concatenation of
#: `charm_sections`, which is what we render — printing both would duplicate every
#: Charm on the page.
DELIBERATELY_OMITTED = {
    "issues", "xp_log", "xp_earned", "xp_spent", "xp_available", "charms",
}

#: Fields read through a SheetView method rather than directly. The essence pools
#: must go through `essence_pool_label`, which knows that a merged pool prints as
#: one figure and that Personal 0 can be a RULE (Beacon of Power) rather than an
#: arithmetic result — reading the ints raw would print "Personal 0" at a
#: character who has plenty of Essence.
READ_VIA_METHOD = {
    "essence_personal": "essence_pool_label",
    "essence_peripheral": "essence_pool_label",
    "essence_single_pool": "essence_pool_label",
    "essence_free": "essence_pool_label",
}

PAPER_SIZES = {"A4": A4, "Letter": LETTER}

_MARGIN = 12 * mm
_GAP = 3 * mm            # gutter between panels in a band
_HAIRLINE = 0.4


# --------------------------------------------------------------------------- #
# Drawn marks — everything the screen sheet does with a Unicode glyph
# --------------------------------------------------------------------------- #

class _Dots(Flowable):
    """A rating as filled/hollow circles, e.g. 3 of 5. Drawn rather than typed:
    the base-14 fonts have no U+25CF, and vector circles print crisper at any
    size. Values above `total` get a "+N" suffix, as the screen sheet does."""

    def __init__(self, value: int, total: int = 5, *, radius: float = 1.15 * mm,
                 gap: float = 0.7 * mm, color=colors.black):
        super().__init__()
        self.value, self.total, self.radius, self.gap = value, total, radius, gap
        self.color = color
        self.overflow = f"+{value - total}" if value > total else ""
        d = radius * 2
        self.width = total * d + (total - 1) * gap
        if self.overflow:
            self.width += 1 * mm + stringWidth(self.overflow, "Helvetica", 6)
        self.height = d

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.setStrokeColor(self.color)
        canv.setFillColor(self.color)
        canv.setLineWidth(0.5)
        d = self.radius * 2
        filled = min(max(self.value, 0), self.total)
        for i in range(self.total):
            cx = i * (d + self.gap) + self.radius
            canv.circle(cx, self.radius, self.radius, stroke=1, fill=1 if i < filled else 0)
        if self.overflow:
            canv.setFont("Helvetica", 6)
            canv.drawString(self.total * (d + self.gap) + 0.3 * mm, 0.2 * mm, self.overflow)


class _Mark(Flowable):
    """The caste / favoured marker beside a trait. A filled disc for caste, a
    hollow diamond for favoured, blank otherwise — the screen sheet's ● and ✦,
    redrawn because neither is printable in a base-14 font."""

    def __init__(self, kind: str, *, size: float = 2.2 * mm, color=colors.black):
        super().__init__()
        self.kind, self.color = kind, color
        self.width = self.height = size

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        r = self.width / 2
        canv.setStrokeColor(self.color)
        canv.setFillColor(self.color)
        canv.setLineWidth(0.5)
        if self.kind == "caste":
            canv.circle(r, r, r * 0.8, stroke=0, fill=1)
        elif self.kind == "favored":
            canv.lines([(r, 0, self.width, r), (self.width, r, r, self.height),
                        (r, self.height, 0, r), (0, r, r, 0)])


class _HealthTrack(Flowable):
    """The health track as real boxes with their penalties beneath, rather than
    the screen sheet's run of text labels. Widths are measured per box so 'Incap'
    does not overlap its neighbour.

    ⚠ It WRAPS. An Ox-Body Solar has nineteen levels and a Mountain Folk can have
    more; a single-row track ran straight out of its panel and over the Virtues
    beside it. The row count follows the width it is given, so nothing here
    assumes seven boxes.

    ⚠ `view.health` labels carry '★' for a Charm-granted level (view._health_label).
    That glyph does not exist in a base-14 font, so it becomes '*' with a printed
    legend — the mark means nothing if the sheet never says what it is.
    """

    _BOX = 4.2 * mm
    _LABEL = 5.5
    _GUTTER = 1.2 * mm
    _ROW_GAP = 1.0 * mm
    STAR = "*"

    def __init__(self, labels: list[str], max_width: float, *, color=colors.black):
        super().__init__()
        self.color = color
        self.labels = [l.replace("★", f" {self.STAR}").strip() for l in labels]
        self.granted = any(self.STAR in l for l in self.labels)
        cols = [max(self._BOX, stringWidth(l, "Helvetica", self._LABEL) + 1)
                for l in self.labels]

        self.rows: list[list[tuple[str, float]]] = []
        row: list[tuple[str, float]] = []
        used = 0.0
        for label, col in zip(self.labels, cols):
            step = col + (self._GUTTER if row else 0)
            if row and used + step > max_width:
                self.rows.append(row)
                row, used = [], 0.0
                step = col
            row.append((label, col))
            used += step
        if row:
            self.rows.append(row)

        self.width = max_width
        row_h = self._BOX + self._LABEL + 1.5
        self.height = len(self.rows) * row_h + (len(self.rows) - 1) * self._ROW_GAP
        if self.granted:
            self.height += self._LABEL + 1.5

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.setStrokeColor(self.color)
        canv.setFillColor(self.color)
        canv.setLineWidth(0.5)
        row_h = self._BOX + self._LABEL + 1.5
        # Rows fill from the TOP; the legend's reserved strip is already at the
        # bottom of `height`, so nothing is subtracted here — doing so pushed the
        # last row down onto the legend.
        y = self.height - row_h
        for row in self.rows:
            x = 0.0
            for label, col in row:
                canv.rect(x + (col - self._BOX) / 2, y + self._LABEL + 1.5,
                          self._BOX, self._BOX, stroke=1, fill=0)
                canv.setFont("Helvetica", self._LABEL)
                canv.drawCentredString(x + col / 2, y, label)
                x += col + self._GUTTER
            y -= row_h + self._ROW_GAP
        if self.granted:
            canv.setFont("Helvetica", self._LABEL)
            canv.setFillColor(colors.HexColor("#666666"))
            canv.drawString(0, 0, f"{self.STAR} Charm-granted level")


class _Legend(Flowable):
    """'● caste · ◆ favoured' — drawn, because both marks are drawn."""

    def __init__(self, width: float, color, caste_noun: str):
        super().__init__()
        self.width, self.color, self.height = width, color, 8
        self.caste_noun = (caste_noun or "Caste").lower()

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.setFont("Helvetica", 6)
        canv.setFillColor(colors.HexColor("#666666"))
        canv.setStrokeColor(self.color)
        x, y = 0.0, 2.0
        canv.setFillColor(self.color)
        canv.circle(x + 1, y + 1.2, 0.9 * mm, stroke=0, fill=1)
        canv.setFillColor(colors.HexColor("#666666"))
        canv.drawString(x + 3 * mm, y, self.caste_noun)
        x = 3 * mm + stringWidth(self.caste_noun, "Helvetica", 6) + 4 * mm
        r = 1.1 * mm
        canv.lines([(x, y + 1.2, x + r, y + 1.2 + r), (x + r, y + 1.2 + r, x + 2 * r, y + 1.2),
                    (x + 2 * r, y + 1.2, x + r, y + 1.2 - r), (x + r, y + 1.2 - r, x, y + 1.2)])
        canv.drawString(x + 2 * r + 1.5 * mm, y, "favored")


class _Heading(Flowable):
    """A section heading: accent text with a hairline rule running out either
    side, the paper equivalent of app._heading."""

    def __init__(self, text: str, width: float, color):
        super().__init__()
        self.text, self.width, self.color = text.upper(), width, color
        self.height = 7

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.setFont("Helvetica-Bold", 7.5)
        canv.setFillColor(self.color)
        text_w = stringWidth(self.text, "Helvetica-Bold", 7.5) + 4 * mm
        canv.drawCentredString(self.width / 2, 2, self.text)
        canv.setStrokeColor(self.color)
        canv.setLineWidth(_HAIRLINE)
        mid, y = self.width / 2, 3.6
        canv.line(0, y, mid - text_w / 2, y)
        canv.line(mid + text_w / 2, y, self.width, y)


# --------------------------------------------------------------------------- #
# Styles and small builders
# --------------------------------------------------------------------------- #

def _styles(accent) -> dict[str, ParagraphStyle]:
    return {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=16,
                                leading=18),
        "subtitle": ParagraphStyle("subtitle", fontName="Helvetica", fontSize=9,
                                   leading=11, textColor=accent),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=7.5,
                               leading=9.5, textColor=colors.HexColor("#555555")),
        "panel": ParagraphStyle("panel", fontName="Helvetica-Bold", fontSize=6.8,
                                leading=8.5, textColor=accent),
        "panel_c": ParagraphStyle("panel_c", fontName="Helvetica-Bold", fontSize=6.8,
                                  leading=8.5, textColor=accent, alignment=TA_CENTER),
        "row": ParagraphStyle("row", fontName="Helvetica", fontSize=7.2, leading=8.6),
        "row_b": ParagraphStyle("row_b", fontName="Helvetica-Bold", fontSize=7.2,
                                leading=8.6),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=6.3,
                                leading=7.8, textColor=colors.HexColor("#555555")),
        "mono": ParagraphStyle("mono", fontName="Courier", fontSize=6.8, leading=8.4),
    }


def _esc(text: str) -> str:
    """Paragraph text is mini-HTML, so a character named 'Sword & Shield' or a
    note containing '<' would raise or vanish. Free text is never trusted here:
    every string on this sheet can come from a save file or the custom library."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _flat(text: str) -> str:
    """Strip the Unicode marks that ui/view.py bakes into display strings, so a
    base-14 font never has to render one. `PathRow.favored` is literally '★' or
    '✚'; the middle dot is latin-1 and survives."""
    return (str(text).replace("★", "").replace("✚", "").replace("●", "")
            .replace("✦", "").replace("−", "-").strip())


def _plain_table(data, widths, extra=()) -> Table:
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        *extra,
    ]))
    return t


class _Panel:
    """A bordered box with a coloured title — the paper equivalent of app._panel.
    Built as a one-column Table so it can sit in a band beside its siblings."""

    PAD = 3.0

    def __init__(self, title: str, width: float, st, accent, *, centered=False):
        self.width, self.st, self.accent = width, st, accent
        self.inner = width - 2 * self.PAD
        self.rows: list = []
        if title:
            self.rows.append(Paragraph(_esc(title),
                                       st["panel_c" if centered else "panel"]))

    # -- content helpers, all sized against self.inner ---------------------- #

    def text(self, value: str, style: str = "row") -> "_Panel":
        self.rows.append(Paragraph(_esc(value), self.st[style]))
        return self

    def trait(self, label: str, value: int, *, total: int = 5, mark: str = "") -> "_Panel":
        dots = _Dots(value, total, color=colors.black)
        mark_w = 3 * mm
        self.rows.append(_plain_table(
            [[_Mark(mark, color=self.accent) if mark else "",
              Paragraph(_esc(label), self.st["row"]), dots]],
            [mark_w, self.inner - mark_w - dots.width - 1.5, dots.width + 1.5]))
        return self

    def rated(self, label: str, value: int, *, total: int = 5) -> "_Panel":
        return self.trait(label, value, total=total)

    def pair(self, left: str, right: str) -> "_Panel":
        """A label and a right-aligned value, for things with no dot track."""
        rw = stringWidth(right, "Helvetica", 7.2) + 2
        self.rows.append(_plain_table(
            [[Paragraph(_esc(left), self.st["row"]),
              Paragraph(_esc(right), self.st["row"])]],
            [self.inner - rw, rw],
            [("ALIGN", (1, 0), (1, 0), "RIGHT")]))
        return self

    def gap(self, height: float = 1.5) -> "_Panel":
        self.rows.append(Spacer(1, height))
        return self

    def rule(self) -> "_Panel":
        self.rows.append(_HRule(self.inner, self.accent))
        return self

    def flowable(self, f) -> "_Panel":
        self.rows.append(f)
        return self

    def build(self) -> Table:
        t = Table([[r] for r in self.rows] or [[""]], colWidths=[self.width])
        t.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), _HAIRLINE, colors.HexColor("#999999")),
            ("LEFTPADDING", (0, 0), (-1, -1), self.PAD),
            ("RIGHTPADDING", (0, 0), (-1, -1), self.PAD),
            ("TOPPADDING", (0, 0), (-1, -1), 1.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return t


class _HRule(Flowable):
    def __init__(self, width: float, color):
        super().__init__()
        self.width, self.color, self.height = width, color, 2.5

    def wrap(self, *_args):
        return self.width, self.height

    def draw(self):
        self.canv.setStrokeColor(self.color)
        self.canv.setLineWidth(_HAIRLINE)
        self.canv.line(0, 1.2, self.width, 1.2)


def _band(panels: list, total_width: float, columns: int | None = None) -> Table:
    """Lay panels side by side across the page, one row of `columns`."""
    columns = columns or len(panels)
    col_w = total_width / columns
    cells = [p if not isinstance(p, _Panel) else p.build() for p in panels]
    cells += [""] * (columns - len(cells))
    t = Table([cells], colWidths=[col_w] * columns)
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), _GAP),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), _GAP / 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _panel_width(total_width: float, columns: int) -> float:
    return total_width / columns - _GAP


def _chunk(items: list, size: int) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


# --------------------------------------------------------------------------- #
# The sheet
# --------------------------------------------------------------------------- #

def _header(view: SheetView, width: float, st, accent) -> Table:
    left = [Paragraph(_esc(view.name) or "&nbsp;", st["title"])]
    line = " ".join(x for x in (view.caste, view.caste_noun, view.exalt_type) if x)
    if line.strip():
        left.append(Paragraph(_esc(line), st["subtitle"]))
    if view.player:
        left.append(Paragraph(f"Player: {_esc(view.player)}", st["meta"]))

    right = []
    for label, value in (("Concept", view.concept), ("Nature", view.nature)):
        if value:
            right.append(Paragraph(f"{label}: {_esc(value)}", st["meta"]))
    right.append(Paragraph(
        "Chargen locked" if view.chargen_locked else "In creation", st["meta"]))
    right.append(Paragraph(f"Experience: {view.experience}", st["meta"]))

    t = Table([[left, right]], colWidths=[width * 0.62, width * 0.38])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.8, accent),
    ]))
    return t


def _mark_for(row) -> str:
    if getattr(row, "caste", False):
        return "caste"
    if getattr(row, "favored", False):
        return "favored"
    return ""


def _trait_panels(view: SheetView, groups, width: float, st, accent,
                  columns: int) -> list:
    panels = []
    for label, rows in groups:
        p = _Panel(label, _panel_width(width, columns), st, accent, centered=True)
        for row in rows:
            p.trait(row.label, row.value, mark=_mark_for(row))
        panels.append(p)
    return panels


def _advantage_panels(view: SheetView, width: float, st, accent, columns: int) -> list:
    """Backgrounds, artifacts, ghost Fetters/Passions, specialties, M&F, colleges
    and thaumaturgy. Each is dropped entirely when empty, exactly as the screen
    sheet drops it — an empty panel saying "—" on every sheet is worse than none."""
    pw = _panel_width(width, columns)
    out = []

    if view.backgrounds:
        p = _Panel("Backgrounds", pw, st, accent)
        for name, rating, note in view.backgrounds:
            p.trait(f"{name}{' · ' + note if note else ''}", rating)
        out.append(p)

    if view.artifacts:
        p = _Panel("Artifacts", pw, st, accent)
        for name, rating, source, damage in view.artifacts:
            label = f"{name}{' · ' + source if source else ''}"
            # A damaged artifact says so: its soak is already reduced above, and an
            # unexplained low figure reads as a bug.
            if damage:
                label += f" (-{damage})"
            p.trait(label, rating)
        out.append(p)

    if view.fetters:
        p = _Panel("Fetters", pw, st, accent)
        total = sum(r for _n, r, _t in view.fetters)
        p.text(f"{total}/{view.fetter_cap} allotted", "small")
        for name, rating, note in view.fetters:
            p.trait(f"{name}{' · ' + note if note else ''}", rating)
        out.append(p)

    if view.passions:
        p = _Panel("Passions", pw, st, accent)
        for virtue, distributed, pool in view.passion_pools:
            rows = [(n, r) for v, n, r in view.passions if v == virtue]
            if not rows and distributed == pool:
                continue
            p.text(f"{virtue} — {distributed}/{pool}", "small")
            for name, rating in rows:
                p.trait(f"  {name}", rating)
        out.append(p)

    # Dropped when empty, like every other panel in this band. ui/app.py prints a
    # box containing "—" instead, which is right on screen (the panel is a landmark
    # you return to) and wrong on paper, where it is an empty rectangle taking a
    # third of a row to say nothing. Human's call, 2026-08-14.
    if view.specialties:
        p = _Panel("Specialties", pw, st, accent)
        for ability, name, rating in view.specialties:
            p.pair(f"{ability} — {name}", f"({rating})")
        out.append(p)

    if view.merits_flaws:
        p = _Panel("Merits & Flaws", pw, st, accent)
        # The tooltip's rules-text half is dropped on the human's ruling (notes yes,
        # rules text no); the printed COST it also carries prints as `points`.
        for name, points, detail, _kind, _tip in view.merits_flaws:
            p.pair(f"{name}{' · ' + detail if detail else ''}", points)
        out.append(p)

    if view.colleges:
        p = _Panel("Astrological Colleges", pw, st, accent)
        for name, rating, house_label, own in view.colleges:
            # `own` is the screen sheet's ★ and `house_label` its tooltip; on paper
            # both become words, since neither hover nor that glyph exists here.
            label = f"{name} ({house_label})" if house_label else name
            p.trait(label, rating, mark="caste" if own else "")
        out.append(p)

    if view.thaumaturgy:
        p = _Panel("Thaumaturgy", pw, st, accent)
        if view.thaumaturgy_note:
            p.text(view.thaumaturgy_note, "small")
        for section, items in view.thaumaturgy:
            p.text(section, "small")
            for item in items:
                p.text(item)
        out.append(p)

    return out


def _equipment_panel(view: SheetView, pw: float, st, accent) -> _Panel | None:
    """The left panel of the bottom band: gear, then Forms / Anima / Virtue Flaw.

    None when it would hold nothing at all. Note it is NOT empty merely because the
    character carries no gear — an Alchemical with no weapons still has an Anima,
    and the panel used to print "—" above it for the gear that was not there.
    """
    if not any((view.weapons, view.armor, view.totem, view.animal_forms,
                view.anima, view.virtue_flaw)):
        return None
    # Untitled when it holds no gear: what remains (Forms / Anima / Virtue Flaw)
    # already carries its own sub-headings, and any title here would sit directly
    # under the band's own "TRAITS" rule saying the same word twice.
    p = _Panel("Equipment" if (view.weapons or view.armor) else "", pw, st, accent)
    for w in view.weapons:
        art = f" · A{w.artifact_rating}/{w.attunement}m" if w.artifact_rating else ""
        rng = f" · rng {w.range}" if w.range else ""
        mat = f" · {w.material}" if w.material else ""
        qty = f" x{w.quantity}" if getattr(w, "quantity", 1) > 1 else ""
        p.text(f"{w.name}{qty}", "row_b")
        # ⚠ mobility_penalty and the rest are stored SIGNED; these format strings are
        # ui/app.py's verbatim, because armour mobility is stored NEGATIVE and a
        # re-derived sign here would silently flip it (docs/status/dice-pools.md).
        p.text(f"  Spd{w.speed:+d} Acc{w.accuracy:+d} Dmg{w.damage:+d}{w.damage_type} "
               f"Def{w.defense:+d}{rng}{art}{mat}", "small")
    for a in view.armor:
        art = f" · A{a.artifact_rating}/{a.attunement}m" if a.artifact_rating else ""
        mat = f" · {a.material}" if a.material else ""
        p.text(a.name, "row_b")
        p.text(f"  Soak {a.soak_lethal}L/{a.soak_bashing}B "
               f"Mob{a.mobility_penalty:+d} Ftg{a.fatigue}{art}{mat}", "small")

    if view.totem or view.animal_forms:
        p.rule().text("Forms", "panel")
        if view.totem:
            p.text(f"Totem: {view.totem}")
        for animal, note in view.animal_forms:
            p.text(f"{animal}{' · ' + note if note else ''}")
    if view.anima:
        p.rule().text("Anima", "panel").text(view.anima, "small")
    if view.virtue_flaw:
        p.rule().text("Virtue Flaw", "panel").text(view.virtue_flaw, "small")
    return p


def _has_equipment_panel(view: SheetView) -> bool:
    return any((view.weapons, view.armor, view.totem, view.animal_forms,
                view.anima, view.virtue_flaw))


def _bottom_band(view: SheetView, width: float, st, accent) -> Table:
    # The column count is decided BEFORE anything is built. A panel's inner tables
    # are laid out against the width it was constructed with, so widening one
    # afterwards leaves its contents at the old width — the dots detach from their
    # labels and the panel looks half-empty.
    columns = 3 if _has_equipment_panel(view) else 2
    pw = _panel_width(width, columns)

    center = _Panel("Willpower", pw, st, accent)
    center.flowable(_Dots(view.willpower, 10))
    center.rule().text("Soak", "panel")
    s = view.soak
    center.text(f"Bashing {s.bashing} · Lethal {s.lethal} · Aggravated {s.aggravated}")
    center.text(f"(Stamina {s.natural_bashing}/{s.natural_lethal} + "
                f"armor {s.armor_bashing}/{s.armor_lethal})", "small")
    center.rule().text("Health", "panel")
    center.flowable(_HealthTrack(view.health, center.inner))

    right = _Panel("Virtues", pw, st, accent)
    for row in view.virtues:
        right.rated(row.label, row.value)
    right.rule().text("Essence", "panel")
    right.rated("Rating", view.essence_rating)
    right.text(view.essence_pool_label(), "small")
    right.rule().pair("Experience", str(view.experience))

    panels = [p for p in (_equipment_panel(view, pw, st, accent), center, right)
              if p is not None]
    return _band(panels, width, columns)


# --------------------------------------------------------------------------- #
# Holdings — names and costs only (the human's ruling); no description text
# --------------------------------------------------------------------------- #

def _provenance(row) -> str:
    """The screen sheet's ✎ / ⚠ markers as words. Custom content must stay
    obvious at a glance on a sheet (the human's requirement, 2026-07-29), and on
    paper a hover tooltip is not a way to say so."""
    if getattr(row, "missing", False):
        return " [missing]"
    if getattr(row, "custom", False):
        return " [custom]"
    return ""


def _pretty_category(category: str) -> str:
    """'martial_arts:snake-style' -> 'Martial Arts: Snake-Style'. The screen sheet
    prints the raw id-ish string; on paper it reads as a leaked internal. The
    namespaced form (docs/ARCHITECTURE.md) is preserved, only spaced and cased."""
    head, sep, tail = category.partition(":")
    out = head.replace("_", " ").title()
    return f"{out}: {tail.replace('_', ' ').title()}" if sep else out


def _listing(title: str, rows: list[list[str]], headers: list[str],
             width: float, st, accent) -> list:
    """A full-width table that may split across pages, with its header repeated.
    Charms are the one part of this sheet allowed to run long, so they are laid
    out as flowing rows rather than as side-by-side panels that cannot break."""
    fracs = [0.46, 0.2, 0.19, 0.15][:len(headers)]
    widths = [width * f for f in fracs]
    data = [[Paragraph(f"<b>{_esc(h)}</b>", st["panel"]) for h in headers]]
    for row in rows:
        data.append([Paragraph(_esc(c), st["row"] if i == 0 else st["small"])
                     for i, c in enumerate(row)])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), _HAIRLINE, accent),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f4f4")]),
    ]))
    return [Paragraph(_esc(title), st["panel"]), Spacer(1, 1), t, Spacer(1, 3 * mm)]


def _holdings(view: SheetView, width: float, st, accent) -> list:
    story: list = []
    # The heading is emitted only if something follows it. A Sidereal fresh out of
    # chargen owns no Charms, and an empty "CHARMS" rule across the page reads as a
    # renderer that lost the list rather than a character who has none.
    charm_body: list = []
    for section_name, rows in view.charm_sections:
        if not rows:
            continue
        charm_body += _listing(
            f"{section_name} ({len(rows)})",
            [[c.name + _provenance(c), _pretty_category(c.category), c.duration,
              c.cost] for c in rows],
            ["Name", "Category", "Duration", "Cost"], width, st, accent)

    if view.spells:
        charm_body += _listing(
            f"Spells ({len(view.spells)})",
            [[s.name + _provenance(s), s.circle, "", s.cost] for s in view.spells],
            ["Name", "Circle", "", "Cost"], width, st, accent)

    if charm_body:
        heading = ("Charms & Sorcery" if (view.spells or view.elemental_powers)
                   else "Charms")
        story.append(_Heading(heading, width, accent))
        story.append(Spacer(1, 2 * mm))
        story += charm_body

    if view.paths:
        story.append(_Heading("Paths of Prehuman Mastery", width, accent))
        story.append(Spacer(1, 2 * mm))
        for p in view.paths:
            # `favored` is a raw glyph in the view model ('★' breed / '✚' chosen);
            # neither is printable, so it becomes a word.
            tag = {"★": " (breed)", "✚": " (chosen)"}.get(p.favored, "")
            story += _listing(
                f"{_flat(p.name)}{tag} · {p.element_label} · {p.rating} dots",
                [[f"{pw.dot}. {pw.name}", pw.type, pw.duration, pw.cost]
                 for pw in p.powers],
                ["Power", "Type", "Duration", "Cost"], width, st, accent)

    if view.combos:
        story.append(_Heading("Combos", width, accent))
        story.append(Spacer(1, 2 * mm))
        story += _listing(
            "Combos",
            [[name, ", ".join(members), "", f"{cost} Charm{'s' if cost != 1 else ''}"]
             for name, members, cost in view.combos],
            ["Name", "Members", "", "Cost"], width, st, accent)

    return story


# --------------------------------------------------------------------------- #
# Entry points
# --------------------------------------------------------------------------- #

def suggested_filename(view: SheetView) -> str:
    """A safe download name derived from the character. Never a path: the caller
    hands this straight to a browser download or an OS save dialog."""
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", (view.name or "character")).strip("-")
    return f"{stem or 'character'}.pdf"


def normalize_pdf_filename(name: str, view: SheetView, *, fallback: str = "") -> str:
    """A user-typed export name, made safe and given a .pdf extension. Mirrors
    persistence.normalize_save_filename: the player may type anything into the
    dialog, including nothing, and the result is handed straight to a browser
    download or an OS save dialog.

    `fallback` names the document when the field is left empty and `view` is not
    the whole story — a PARTY export cleared to blank must not be named after
    whichever member happens to be first in the list.
    """
    raw = (name or "").strip()
    if raw.lower().endswith(".pdf"):
        raw = raw[:-4]
    # Dots go too, not just separators: stripping only '/' leaves '..' segments in
    # the name, which is a traversal shape surviving a sanitiser that "passed".
    stem = re.sub(r"[^A-Za-z0-9_ -]+", "-", raw).strip(" -")
    if stem:
        return f"{stem}.pdf"
    if fallback:
        return normalize_pdf_filename(fallback, view)
    return suggested_filename(view)


def _character_story(view: SheetView, width: float) -> list:
    """One character's flowables. Split out from `build_pdf` so the party export
    can concatenate several without a second layout to keep in step — each
    character carries its OWN splat palette, so the styles are built per view
    rather than once for the document."""
    pal = theme.palette(view.exalt_type)
    accent = colors.HexColor(pal.accent)
    st = _styles(accent)

    story: list = [_header(view, width, st, accent), Spacer(1, 3 * mm)]

    story.append(_Heading("Attributes", width, accent))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_band(_trait_panels(view, view.attributes, width, st, accent, 3),
                       width, 3))

    if view.breed_weapons:
        story.append(_Heading("Innate Weapons", width, accent))
        story.append(Spacer(1, 1.5 * mm))
        p = _Panel("", width, st, accent)
        for name, speed, acc, dmg, dmg_type, defense in view.breed_weapons:
            p.text(f"{name} — Spd{speed:+d} Acc{acc:+d} Dmg{dmg:+d}{dmg_type} "
                   f"Def{defense:+d}", "small")
        story.append(p.build())
        story.append(Spacer(1, 2 * mm))

    story.append(_Heading("Abilities", width, accent))
    story.append(_Legend(width, accent, view.caste_noun))
    story.append(Spacer(1, 1.5 * mm))
    for chunk in _chunk(list(view.ability_groups), 3):
        story.append(_band(_trait_panels(view, chunk, width, st, accent, 3),
                           width, 3))

    # Now that every panel in the band drops when empty, the band itself can be
    # empty — a blank character has no Backgrounds and no Specialties. Same rule as
    # the Charms heading: a heading must not outlive its content.
    advantages = _advantage_panels(view, width, st, accent, 3)
    if advantages:
        story.append(_Heading("Advantages", width, accent))
        story.append(Spacer(1, 1.5 * mm))
        for chunk in _chunk(advantages, 3):
            story.append(_band(chunk, width, 3))

    story.append(_Heading("Traits", width, accent))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_bottom_band(view, width, st, accent))

    # No forced page break. A Solar's Charm list is often short enough to sit under
    # the sheet, and a hard break spent a third of a page on nothing; CondPageBreak
    # moves the holdings on only when there is too little room left to start them.
    holdings = _holdings(view, width, st, accent)
    if holdings:
        story.append(Spacer(1, 4 * mm))
        story.append(CondPageBreak(45 * mm))
        story += holdings

    return story


def _render(views: list[SheetView], paper: str, *, title: str) -> bytes:
    if paper not in PAPER_SIZES:
        raise ValueError(
            f"unknown paper size {paper!r}; expected one of {sorted(PAPER_SIZES)}")
    size = PAPER_SIZES[paper]
    width = size[0] - 2 * _MARGIN

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=size,
        leftMargin=_MARGIN, rightMargin=_MARGIN,
        topMargin=_MARGIN, bottomMargin=_MARGIN,
        title=title,
        author=views[0].player if views else "",
        subject=views[0].exalt_type if views else "")

    story: list = []
    for i, view in enumerate(views):
        if i:
            # Every character starts on a fresh page. Two half-sheets sharing one
            # page would be unusable at a table, where sheets get handed out.
            story.append(PageBreak())
        story += _character_story(view, width)
    doc.build(story)
    return buf.getvalue()


def build_pdf(view: SheetView, *, paper: str = "A4") -> bytes:
    """Render `view` as a PDF and return the bytes.

    Takes a SheetView and nothing else — see the module docstring for why that
    matters. `paper` is one of PAPER_SIZES; the human chooses it at export time
    rather than it being a stored setting.
    """
    return _render([view], paper,
                   title=f"{view.name} — Exalted 1e character sheet")


def build_party_pdf(views: list[SheetView], *, paper: str = "A4",
                    party_name: str = "") -> bytes:
    """Every party member in one document, one starting per page. Same renderer
    as the single sheet — a party export that drifted from the character export
    would be two layouts of one thing."""
    views = list(views)
    if not views:
        raise ValueError("a party export needs at least one character")
    label = party_name.strip() or "Party"
    return _render(views, paper, title=f"{label} — Exalted 1e character sheets")
