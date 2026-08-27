"""exalted_builder/qt/party.py — the Storyteller's Party window (a SECOND window).

Input: a RuleSet and the builder's shared context (`party`, `party_path`,
`adversary_catalog`). Output: a top-level window — a toolbar (the party name, Add
character, Save / Load party, Print all, New party) over three tabs: **Party** (a live
card per member), **Adversaries** (`qt/adversaries.py`) and **Reference** (the ST
screen). Mechanism: `reload()` redraws the cards from `view.build_party_card_view`;
every play-state click goes through `engine.play`, every roster mutation through
`engine.adversaries`; "Open in builder" calls back into the MainWindow, which re-points
itself at that member's Character — the same object, so nothing needs syncing.

⚠ **A WINDOW, not a tab** (human, 2026-08-27). The builder and the party are two
surfaces a Storyteller uses at once — the settled tab layout never decided this one,
because the shape was never a tab. A QDialog was rejected for the same reason: you must
be able to read a character sheet and the party at the same time.

⚠ **The Party tab is the THIRD written exception to the collection layout**, and it is
Play's exception for Play's reason: these cards are live TRACKERS. There is nothing to
select and a detail pane would hide the health tracks the surface exists to show. The
Adversaries tab beside it IS a collection, because its entries are edited as well as
tracked — the two halves of this window are deliberately different shapes.

⚠ **Play-state stays isolated (decision 0006).** Nothing on this window enters chargen
validation, the XP audit or a permanent derivation. There is ZERO game logic here: every
number comes from `view.build_party_card_view`.

⚠ **Members are held BY REFERENCE.** A card and the builder edit one Character object,
which is what makes "Open in builder" need no syncing code — and what makes removing a
member from the roster leave the builder pointing at a character that is no longer in
it, so `on_close_member` is called on every path that drops or replaces the roster.
"""

from __future__ import annotations

import html as _html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSpinBox, QTabWidget, QTextBrowser, QToolBar, QVBoxLayout, QWidget,
)

from exalted_builder import persistence
from exalted_builder.engine import derive, play as engineplay
from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.ui import pdf, theme
from exalted_builder.ui import view as viewmod

from . import theme as qtheme
from .adversaries import AdversariesPage
from .layout import clear_layout
from .sheet import build_document, sheet_html
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL, box as tracker_box

_BOXES_PER_ROW = 10

# One card is unreadable much under this; the grid takes as many columns as fit.
_CARD_WIDTH = 430

# The Great Geas, core CH6 p.235 (Mountain Folk). Divergence is Storyteller-adjudicated
# and never engine-enforced — whether an oath was broken is an ST call — so the nine
# clauses ride the card as the sheet's copy of the page (the human's ruling, 2026-08-07).
_GEAS = (
    "Breaking a sworn oath — 5 points (once broken, an oath no longer has power).",
    "Fighting against a Celestial Exalt except in self-defense or at the behest of "
    "another Celestial Exalt — 5 points at the beginning of hostilities.",
    "Slaying one of the Exalted — 5 points for striking the deathblow against a "
    "Celestial, 3 against a Terrestrial.",
    "Giving aid to an enemy of Creation (the banished and dead Primordials and their "
    "servants, denizens of the Wyld, most Darkbroods) — 4 points per instance.",
    "Associating with the enemies of Creation in any nonhostile manner — 2 points per "
    "week.",
    "Accepting worship from mortals — 3 points per week.",
    "Asserting authority and leadership over a community of mortals — 1 point per week.",
    "Dwelling more than a month aboveground except in service to the Exalted — 1 point "
    "per month after the first.",
    "Refusing to build an artifact for a Celestial Exalt of higher Essence when properly "
    "commanded — 1 point per week of disobedience (Enlightened only).",
)

_GEAS_TAIL = ("When Divergence reaches 10 the pool resets to 0 and the character suffers "
              "misfortune as though they broke an oath sanctified by an Eclipse Caste "
              "Solar. For every full month the Jadeborn live underground without gaining "
              "Divergence, they lose one point.")


# --------------------------------------------------------------------------- #
# The Party tab — live cards
# --------------------------------------------------------------------------- #

class PartyPage(QWidget):
    """The member cards. `reload()` redraws every card for the party in ctx.

    `on_open`, `on_sheet`, `on_pdf` and `on_remove` are the window's — the card owns the
    trackers and nothing else."""

    def __init__(self, ruleset, ctx, *, on_open, on_sheet, on_pdf, on_remove,
                 parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._on_open = on_open
        self._on_sheet = on_sheet
        self._on_pdf = on_pdf
        self._on_remove = on_remove
        self._columns = 0

        body = QWidget()
        self._grid = QGridLayout(body)
        self._grid.setContentsMargins(8, 8, 8, 8)
        self._grid.setSpacing(8)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(body)

        notes_panel = QWidget()
        notes_lay = QVBoxLayout(notes_panel)
        notes_lay.setContentsMargins(8, 0, 8, 4)
        notes_lay.setSpacing(2)
        heading = QLabel("SESSION NOTES")
        heading.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED};")
        notes_lay.addWidget(heading)
        self.session_notes = QPlainTextEdit()
        self.session_notes.setObjectName("party.session_notes")
        self.session_notes.setPlaceholderText(
            "What happened, what's next, who owes whom…")
        self.session_notes.setFixedHeight(76)
        self.session_notes.textChanged.connect(self._write_session_notes)
        notes_lay.addWidget(self.session_notes)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(notes_panel)
        self.reload()

    # ---- plumbing -------------------------------------------------------- #

    def _party(self) -> Party:
        return self._ctx["party"]

    def _accent(self, character: Character | None = None) -> str:
        pal = theme.palette(character.exalt_type if character is not None else None)
        return accent_light(pal)

    def _write_session_notes(self) -> None:
        self._party().session_notes = self.session_notes.toPlainText()

    def resizeEvent(self, event: QResizeEvent) -> None:      # noqa: N802 - Qt override
        """Re-flow the cards when the column count changes.

        ⚠ Only when it CHANGES. A redraw on every resize event would tear down the card
        the Storyteller is typing notes into, on a window drag."""
        super().resizeEvent(event)
        if self._fit_columns() != self._columns:
            self.reload()

    def _fit_columns(self) -> int:
        return max(1, (self._scroll.viewport().width() - 16) // _CARD_WIDTH)

    def reload(self) -> None:
        """Redraw every card, and re-read the session notes from the party."""
        # ⚠ The notes box is refilled only when the model and the widget actually
        # disagree — setPlainText moves the cursor to the end, so an unconditional
        # refill would jump the caret on every reload.
        notes = self._party().session_notes
        if self.session_notes.toPlainText() != notes:
            self.session_notes.blockSignals(True)
            self.session_notes.setPlainText(notes)
            self.session_notes.blockSignals(False)

        clear_layout(self._grid)
        self._columns = self._fit_columns()
        members = self._party().members
        if not members:
            empty = QLabel("No characters in the party yet.\nUse “Add character” to "
                           "load a .character.json, or load a saved .party.json.")
            empty.setStyleSheet(f"color:{MUTED};")
            self._grid.addWidget(empty, 0, 0)
            return
        for index, member in enumerate(members):
            # ⚠ Aligned TOP, per card. Without it the grid stretches every card in a row
            # to the height of the tallest, and a QVBoxLayout hands that spare height to
            # the gaps between panels — a Solar beside a Sidereal came out with 40px of
            # nothing under each heading.
            self._grid.addWidget(self._card(index, member),
                                 index // self._columns, index % self._columns,
                                 Qt.AlignmentFlag.AlignTop)

    # ---- one card -------------------------------------------------------- #

    def _panel(self, lay, title: str, accent: str) -> QVBoxLayout:
        head = QLabel(title)
        head.setWordWrap(True)
        head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{accent};"
                           f" font-size:11px;")
        lay.addWidget(head)
        body = QVBoxLayout()
        # ⚠ Margins zeroed. A nested QVBoxLayout inherits an 11px default on all four
        # sides, and six of them down a card add 130px of nothing between the heading
        # and the boxes it labels.
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)
        lay.addLayout(body)
        return body

    def _card(self, index: int, member: PartyMember) -> QFrame:
        character = member.character
        cv = viewmod.build_party_card_view(self._ruleset, character)
        accent = self._accent(character)
        cur = character.play or PlayState()
        marks = list(cur.health)[:len(cv.play.health_boxes)]
        marks += [None] * (len(cv.play.health_boxes) - len(marks))

        card = QFrame()
        card.setObjectName("partyCard")
        # ⚠ Inline, on the widget itself. An ancestor stylesheet beats a set palette
        # every time, so a card that relied on a QPalette would paint the page shade.
        card.setStyleSheet(f"QFrame#partyCard {{ background:{CARD}; border-radius:6px; }}")
        card.setMinimumWidth(_CARD_WIDTH - 40)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        title = QLabel(cv.name + ("   🔒" if cv.chargen_locked else ""))
        title.setToolTip("Chargen locked — in play" if cv.chargen_locked else "")
        title.setStyleSheet(f"font-weight:700; font-size:14px; color:{accent};")
        lay.addWidget(title)
        identity = QLabel(cv.identity_line)
        identity.setWordWrap(True)
        identity.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        lay.addWidget(identity)

        self._health(lay, index, character, cv, marks, accent)
        self._motes(lay, index, character, cv, cur, accent)
        self._willpower(lay, index, character, cv, cur, accent)
        self._limit(lay, index, character, cur, accent)

        stats = QLabel(f"Soak {cv.soak.bashing}B / {cv.soak.lethal}L / "
                       f"{cv.soak.aggravated}A   ·   Dodge {cv.dodge}   ·   "
                       f"Essence {cv.essence_rating}")
        stats.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        lay.addWidget(stats)

        # ⚠ No reload on change: redrawing the card per keystroke would delete the box
        # mid-word and steal the focus. Nothing else on the card reads the notes.
        notes = QPlainTextEdit(member.notes)
        notes.setObjectName(f"party.{index}.notes")
        notes.setPlaceholderText("Notes…")
        notes.setFixedHeight(52)
        notes.setStyleSheet(f"background:{INPUT};")
        notes.textChanged.connect(
            lambda m=member, w=notes: setattr(m, "notes", w.toPlainText()))
        lay.addWidget(notes)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        for label, tip, slot in (
                ("Sheet", "The character sheet, read-only",
                 lambda: self._on_sheet(character)),
                ("PDF", "Export a print-ready PDF sheet",
                 lambda: self._on_pdf(character)),
                ("Builder", "Point the builder window at this character",
                 lambda: self._on_open(index)),
                ("Remove", "Remove from the party",
                 lambda: self._on_remove(index))):
            button = QPushButton(label)
            button.setObjectName(f"party.{index}.{label.lower()}")
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        lay.addLayout(buttons)
        return card

    def _health(self, lay, index, character, cv, marks, accent) -> None:
        counts = {d: sum(1 for m in marks if m == d) for d in Damage}
        body = self._panel(
            lay, f"HEALTH   ·   penalty {viewmod.worst_penalty(cv.play, marks)}   ·   "
                 f"{counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                 f"{counts[Damage.AGGRAVATED]}*", accent)
        row = None
        for i, box in enumerate(cv.play.health_boxes):
            if i % _BOXES_PER_ROW == 0:
                row = QHBoxLayout()
                row.setSpacing(3)
                body.addLayout(row)
            mark = marks[i]
            # The wound penalty is CAPTIONED, not just a tooltip: which box to mark next
            # is the thing a Storyteller reads off a card mid-fight, and a hover is no
            # use when six cards are on screen.
            cell = QVBoxLayout()
            cell.setSpacing(0)
            caption = QLabel(box.label)
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            caption.setStyleSheet(f"color:{MUTED}; font-size:9px;")
            cell.addWidget(caption)
            button = tracker_box(f"party.{index}.health.{i}", 24,
                                 MARK_FILL[mark] if mark else INPUT, accent,
                                 mark.value if mark else "")
            button.setToolTip(f"Wound penalty {box.label}")
            button.clicked.connect(
                lambda _c=False, c=character, i=i, n=len(cv.play.health_boxes):
                (engineplay.cycle_mark(c, i, n), self.reload()))
            cell.addWidget(button)
            row.addLayout(cell)
        if row is not None:
            row.addStretch(1)

    def _motes(self, lay, index, character, cv, cur, accent) -> None:
        """The Essence pools.

        ⚠ A merged pool is ONE track — "all of which is considered Peripheral" (p.41) —
        so a Personal box would sit at a permanent 0/0 and read as broken. `single_pool`
        is carried on the view for exactly this, and the card honours it the way the Play
        tab does."""
        body = self._panel(lay, "ESSENCE — SINGLE POOL (motes spent)" if cv.play.single_pool
                           else "ESSENCE (motes spent)", accent)
        row = QHBoxLayout()
        row.setSpacing(8)
        if not cv.play.single_pool:
            self._mote_input(row, index, character, "Personal", "motes_personal_spent",
                             cur.motes_personal_spent, cv.play.personal_max, accent)
        self._mote_input(row, index, character,
                         "All motes" if cv.play.single_pool else "Peripheral",
                         "motes_peripheral_spent", cur.motes_peripheral_spent,
                         cv.play.peripheral_max, accent)
        row.addStretch(1)
        body.addLayout(row)

    def _mote_input(self, row, index, character, caption, field, value, cap, accent) -> None:
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        row.addWidget(label)
        spin = QSpinBox()
        spin.setObjectName(f"party.{index}.{field}")
        spin.setRange(0, cap)
        spin.setValue(min(value, cap))
        spin.setToolTip(f"{cap} motes in this pool")
        row.addWidget(spin)
        left = QLabel(f"{max(0, cap - value)}/{cap}")
        left.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        row.addWidget(left)
        # ⚠ No card reload from a spin box: the redraw would delete it mid-keystroke and
        # take the focus with it. The one label that depends on the value is re-texted
        # in place instead — a "left" count that only moved on the next full reload was
        # worse than no count at all.
        spin.valueChanged.connect(
            lambda v, c=character, f=field, m=cap: (
                engineplay.set_motes(c, f, v, m),
                left.setText(f"{max(0, m - v)}/{m}")))

    def _willpower(self, lay, index, character, cv, cur, accent) -> None:
        body = self._panel(
            lay, f"WILLPOWER   ({cv.play.willpower_max - cur.willpower_spent}"
                 f"/{cv.play.willpower_max})", accent)
        self._count_track(body, index, character, "willpower_spent",
                          cur.willpower_spent, cv.play.willpower_max, accent)

    def _limit(self, lay, index, character, cur, accent) -> None:
        """Limit, or Clarity for an Alchemical (p.69) — never both. Only the temporary
        half of Clarity is clickable; the permanent half is derived."""
        ruleset = self._ruleset
        if derive.uses_clarity(ruleset, character):
            cl = derive.clarity(ruleset, character)
            body = self._panel(
                lay, f"CLARITY   ({cl.total}/{derive.CLARITY_MAX}  ·  {cl.permanent} perm "
                     f"+ {cl.temporary} temp  ·  band {cl.band})", accent)
            self._count_track(body, index, character, "clarity_temporary",
                              cur.clarity_temporary, derive.CLARITY_MAX, accent)
            return
        label = derive.limit_label(ruleset, character).upper()   # "PARADOX" for a Sidereal
        body = self._panel(
            lay, f"{label}   ({cur.limit}/10"
                 f"{f'  — {label} BREAK' if cur.limit >= 10 else ''})", accent)
        self._count_track(body, index, character, "limit", cur.limit, 10, accent)
        if derive.limit_label(ruleset, character) == "Divergence":
            # ⚠ A BUTTON, not a hover. Divergence is Storyteller-adjudicated and never
            # engine-enforced, so the nine clauses are the card's copy of the page — and
            # a page nobody can find is not on the card.
            geas = QPushButton("The Great Geas — Divergence triggers…")
            geas.setObjectName(f"party.{index}.geas")
            geas.clicked.connect(self._show_geas)
            body.addWidget(geas)

    def _show_geas(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("The Great Geas (CH6 p.235)")
        box.setText("\n\n".join(f"• {clause}" for clause in _GEAS)
                    + "\n\n" + _GEAS_TAIL)
        box.exec()

    def _count_track(self, body, index, character, field, spent, cap, accent) -> None:
        row = None
        for i in range(cap):
            if i % 20 == 0:
                row = QHBoxLayout()
                row.setSpacing(3)
                body.addLayout(row)
            button = tracker_box(f"party.{index}.{field}.{i}", 16,
                                 accent if i < spent else INPUT, accent)
            button.clicked.connect(
                lambda _c=False, c=character, i=i, f=field, m=cap:
                (engineplay.set_count(c, f, i, m), self.reload()))
            row.addWidget(button)
        if row is not None:
            row.addStretch(1)


# --------------------------------------------------------------------------- #
# The Reference tab — the ST screen
# --------------------------------------------------------------------------- #

class ReferencePage(QWidget):
    """The Storyteller's reference screen (`RuleSet.st_screen`) as one scrollable
    document. Read-only and purely presentational — the tables are already
    render-ready, so there is no logic here.

    ⚠ It lives on THIS window rather than on the builder's ST Options tab (human,
    2026-08-27): it is a Storyteller-at-the-table surface and belongs beside the party
    and the opposition. Absent (an explanatory line) when no `st_screen.json` shipped."""

    def __init__(self, ruleset, parent=None):
        super().__init__(parent)
        self.view = QTextBrowser()
        # ⚠ Styled inline: a QTextBrowser is a document, and this one is REFERENCE — it
        # stays light "paper" like the Sheet tab rather than taking the card shade the
        # shell QSS gives QTextBrowser.
        self.view.setStyleSheet("QTextBrowser { background:#fffdf7; color:#1a1a1a; }")
        self.view.setDocument(build_document(reference_html(ruleset)))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view, 1)


def reference_html(ruleset) -> str:
    """The ST screen as HTML: a heading per group, a table per RefTable. A
    `columns`-less table renders as a bare list of rows (a step sequence)."""
    screen = ruleset.st_screen
    esc = _html.escape
    if screen is None:
        return ("<p>No Storyteller reference screen is loaded "
                "(<code>data/st_screen.json</code> is absent).</p>")
    accent = "#8a5a1a"
    parts = [f"<h1 style='color:{accent};font-size:18pt;margin:0'>"
             f"{esc(screen.title)}</h1>"]
    for group in screen.groups:
        parts.append(f"<h2 style='color:{accent};border-bottom:2px solid {accent};"
                     f"font-size:13pt;margin:10px 0 4px 0'>{esc(group.title)}</h2>")
        for table in group.tables:
            parts.append(f"<h3 style='font-size:11pt;margin:6px 0 2px 0'>"
                         f"{esc(table.title)}</h3>")
            if table.columns:
                head = "".join(f"<th align='left' style='border-bottom:1px solid "
                               f"{accent}'>{esc(c)}</th>" for c in table.columns)
                rows = "".join(
                    "<tr>" + "".join(f"<td style='padding-right:12px'>{esc(cell)}</td>"
                                     for cell in row) + "</tr>"
                    for row in table.rows)
                parts.append(f"<table width='100%' style='border-collapse:collapse'>"
                             f"<tr>{head}</tr>{rows}</table>")
            else:
                for row in table.rows:
                    parts.append(f"<p style='margin:1px 0'>"
                                 f"{esc('  ·  '.join(row))}</p>")
            if table.note:
                parts.append(f"<p style='font-style:italic;color:#555;margin:2px 0'>"
                             f"{esc(table.note)}</p>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #

class PartyWindow(QMainWindow):
    """The Storyteller's second window. `on_open_member(index)` re-points the builder;
    `on_close_member()` tells it to stop pointing at one."""

    def __init__(self, ruleset, ctx, *, on_open_member, on_close_member, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._on_open_member = on_open_member
        self._on_close_member = on_close_member
        # ⚠ No `notify` hook from the builder: this window has its own status bar, and a
        # second unused messaging channel is the shape a dead field takes.

        self.resize(1180, 860)
        self._build_toolbar()

        self.party_page = PartyPage(
            ruleset, ctx, on_open=self._open_member, on_sheet=self._show_sheet,
            on_pdf=lambda c: self._export_pdf(c), on_remove=self._remove_member)
        self.adversaries_page = AdversariesPage(ruleset, ctx, notify=self._notify_status)
        self.reference_page = ReferencePage(ruleset)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.party_page, "Party")
        self.tabs.addTab(self.adversaries_page, "Adversaries")
        self.tabs.addTab(self.reference_page, "Reference")
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("")
        self.apply_chrome()

    # ---- chrome ---------------------------------------------------------- #

    def _party(self) -> Party:
        return self._ctx["party"]

    def _pal(self):
        """The party's chrome: the shared splat when every member is the same Exalt
        type, else the default. A mixed party carries its identity on the cards, which
        are always tinted per character."""
        splats = {m.character.exalt_type for m in self._party().members}
        return theme.palette(splats.pop() if len(splats) == 1 else None)

    def apply_chrome(self) -> None:
        """Re-theme the window for whatever the party is now.

        ⚠ Its OWN `qtheme.apply`. This is a top-level window, so it inherits neither the
        builder's palette nor its stylesheet — the same trap that left every QDialog in
        the port drawing the platform light grey."""
        name = self._party().name or "(unnamed)"
        self.setWindowTitle(f"Exalted 1e — Party: {name}")
        qtheme.apply(self, self._pal())

    def _notify_status(self, text: str, kind: str = "info") -> None:
        if kind == "warning":
            QMessageBox.warning(self, "Exalted 1e — Party", text)
        else:
            self.statusBar().showMessage(text, 8000)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Party")
        tb.setMovable(False)
        self.addToolBar(tb)
        label = QLabel("Party  ")
        tb.addWidget(label)
        self.name_edit = QLineEdit(self._ctx["party"].name)
        self.name_edit.setObjectName("party.name")
        self.name_edit.setPlaceholderText("Party name")
        self.name_edit.setFixedWidth(220)
        self.name_edit.textChanged.connect(self._rename)
        tb.addWidget(self.name_edit)
        tb.addSeparator()
        tb.addAction("Add character", self._add_character)
        tb.addAction("Save party", self._save_party)
        tb.addAction("Load party", self._load_party)
        tb.addAction("Print all", lambda: self._export_pdf(None))
        tb.addAction("New party", self._confirm_new_party)

    def _rename(self, text: str) -> None:
        # ⚠ The title only. Re-theming here would rebuild the toolbar's own line edit
        # on every keystroke; the palette does not depend on the name anyway.
        self._party().name = text
        self.setWindowTitle(f"Exalted 1e — Party: {text or '(unnamed)'}")

    def reload(self) -> None:
        """Redraw both live tabs. Called when the builder has changed a character the
        party holds — the objects are shared, so only the DRAWING is stale."""
        if self.name_edit.text() != self._party().name:
            self.name_edit.blockSignals(True)
            self.name_edit.setText(self._party().name)
            self.name_edit.blockSignals(False)
        self.party_page.reload()
        self.adversaries_page.reload()
        self.apply_chrome()

    # ---- members --------------------------------------------------------- #

    def add_character(self, character: Character) -> PartyMember:
        """Append a character to the roster BY REFERENCE — editing it in the builder
        keeps the card in step with no syncing code."""
        member = PartyMember(character=character)
        self._party().members.append(member)
        self.party_page.reload()
        self.apply_chrome()
        return member

    def build_add_character_dialog(self) -> QDialog:
        """⚠ Three sources, not just the file picker. Jumping straight to the OS dialog
        would make the character open in the builder — the commonest case at a table —
        unreachable from here.

        BUILT but not run, like the other modals here: `exec()` blocks a headless run,
        so this is the seam the tests drive."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add a character to the party")
        lay = QVBoxLayout(dialog)
        note = QLabel("Stored in the party bundle — the character's own file is "
                      "untouched.")
        note.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(note)

        def finish(character: Character, label: str) -> None:
            self.add_character(character)
            dialog.accept()
            self._notify_status(f"Added {character.name or label} to the party")

        browse = QPushButton("Browse for a .character.json…")
        browse.clicked.connect(lambda: self._browse_for_character(finish, dialog))
        lay.addWidget(browse)

        open_char = self._ctx["char"]
        # Identity, not equality: two characters may legitimately share a name.
        if not any(m.character is open_char for m in self._party().members):
            take = QPushButton(f"Add “{open_char.name or 'the character in the builder'}”")
            take.setObjectName("party.addOpen")
            take.setToolTip("The character currently open on the builder tabs")
            take.clicked.connect(lambda: finish(open_char, "the open character"))
            lay.addWidget(take)

        blank = QPushButton("Add a blank character")
        blank.setObjectName("party.addBlank")
        blank.clicked.connect(lambda: finish(Character(id="char.new"), "a blank character"))
        lay.addWidget(blank)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        lay.addWidget(cancel)
        return dialog

    def _add_character(self) -> None:
        self.build_add_character_dialog().exec()

    def _browse_for_character(self, finish, dialog) -> None:
        path, _ = QFileDialog.getOpenFileName(
            dialog, "Add a character", str(self._ctx["dir"]),
            "Character files (*.json);;All files (*)")
        if not path:
            return
        try:
            loaded = persistence.load_character(path)
        except Exception as ex:               # noqa: BLE001 - surface any load error
            self._notify_status(f"Load failed: {ex}", "warning")
            return
        finish(loaded, Path(path).stem)

    def _open_member(self, index: int) -> None:
        """Hand this member to the builder window and raise it. The Character object is
        shared, so whatever the builder does lands back on this card."""
        self._on_open_member(index)
        self.party_page.reload()

    def _remove_member(self, index: int) -> None:
        member = self._party().members[index]
        name = member.character.name or "(unnamed)"
        answer = QMessageBox.question(
            self, "Remove from the party?",
            f"Remove {name} from the party?\n\nTheir notes and tracked play-state in "
            f"this party are lost. Any separately saved .character.json is untouched.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        del self._party().members[index]
        # ⚠ The builder may be pointed at the member that just went away, or at one
        # whose index has shifted. Drop the pointer rather than leave it stale.
        self._on_close_member()
        self.party_page.reload()
        self.apply_chrome()
        self._notify_status(f"Removed {name} from the party")

    # ---- the read-only sheet --------------------------------------------- #

    def build_sheet_dialog(self, character: Character) -> QDialog:
        """One member's sheet as a document, BUILT but not run — `exec()` blocks a
        headless run, so this is the seam the tests drive."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Sheet — {character.name or '(unnamed)'}")
        dialog.resize(900, 800)
        view = QTextBrowser()
        view.setStyleSheet("QTextBrowser { background:#fffdf7; color:#1a1a1a; }")
        view.setDocument(build_document(sheet_html(
            viewmod.build_sheet_view(self._ruleset, character))))
        lay = QVBoxLayout(dialog)
        lay.addWidget(view, 1)
        close = QPushButton("Close")
        close.clicked.connect(dialog.accept)
        lay.addWidget(close)
        return dialog

    def _show_sheet(self, character: Character) -> None:
        self.build_sheet_dialog(character).exec()

    # ---- save / load / new ----------------------------------------------- #

    def _save_party(self) -> None:
        default = persistence.suggested_party_filename(self._party())
        start = self._ctx["party_path"] or (self._ctx["dir"] / default)
        path, _ = QFileDialog.getSaveFileName(self, "Save party", str(start),
                                              "Party files (*.json)")
        if not path:
            return
        try:
            persistence.save_party(self._party(), path)
        except Exception as ex:               # noqa: BLE001 - surface write errors
            self._notify_status(f"Save failed: {ex}", "warning")
            return
        self._ctx["party_path"] = Path(path)
        self._notify_status(f"Saved party to {path}")

    def _load_party(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load a party", str(self._ctx["dir"]),
                                              "Party files (*.json);;All files (*)")
        if not path:
            return
        try:
            loaded = persistence.load_party(path)
        except Exception as ex:               # noqa: BLE001 - surface any load error
            self._notify_status(f"Load failed: {ex}", "warning")
            return
        self.apply_party(loaded, Path(path))
        self._notify_status(f"Loaded party {loaded.name or '(unnamed)'} "
                            f"({len(loaded.members)} character(s))")

    def apply_party(self, loaded: Party, path: Path | None) -> None:
        """Swap the whole bundle in. ⚠ The builder is pointed at a member of the party
        that just went away — drop that pointer, or a later save is attributed to a
        member of a roster nobody is holding any more."""
        self._ctx["party"] = loaded
        self._ctx["party_path"] = path
        self._on_close_member()
        self.reload()

    def _confirm_new_party(self) -> None:
        answer = QMessageBox.question(
            self, "Start a new party?",
            "Any unsaved changes to the current party will be lost.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.apply_party(Party(id="party.new"), None)
        self._notify_status("Started a new party")

    # ---- PDF ------------------------------------------------------------- #

    def build_export_dialog(self, character: Character | None) -> QDialog | None:
        """The export dialog for one member, or for the whole party when `character` is
        None. BUILT but not run, like the other modals here. None when there is nothing
        to export."""
        members = ([character] if character is not None
                   else [m.character for m in self._party().members])
        if not members:
            self._notify_status("The party is empty.")
            return None
        views = [viewmod.build_sheet_view(self._ruleset, c) for c in members]
        default = (pdf.suggested_filename(views[0]) if character is not None
                   else f"{(self._party().name or 'party').replace(' ', '-')}-sheets.pdf")

        dialog = QDialog(self)
        dialog.setWindowTitle("Export character sheet" if character is not None
                              else f"Export {len(views)} character sheets")
        lay = QVBoxLayout(dialog)
        if character is None:
            lay.addWidget(QLabel("One party member per page."))
        lay.addWidget(QLabel("Paper size:"))
        paper = QComboBox()
        paper.addItems(list(pdf.PAPER_SIZES))
        paper.setCurrentText("A4")
        lay.addWidget(paper)

        def go() -> None:
            path, _ = QFileDialog.getSaveFileName(dialog, "Export sheets",
                                                  str(self._ctx["dir"] / default),
                                                  "PDF (*.pdf)")
            if not path:
                return
            try:
                # ⚠ A party export is NOT a loop over single-sheet exports: `build_pdf`
                # and `build_party_pdf` are two documents, and the party one names
                # itself after the party rather than after its first member.
                data = (pdf.build_pdf(views[0], paper=paper.currentText())
                        if len(views) == 1
                        else pdf.build_party_pdf(views, paper=paper.currentText(),
                                                 party_name=self._party().name))
                Path(path).write_bytes(data)
            except Exception as ex:           # noqa: BLE001 - surface render/write errors
                self._notify_status(f"Export failed: {ex}", "warning")
                return
            self._notify_status(f"Sheets written to {path}")
            dialog.accept()

        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        export = QPushButton("Export PDF")
        export.clicked.connect(go)
        buttons.addWidget(export)
        lay.addLayout(buttons)
        return dialog

    def _export_pdf(self, character: Character | None) -> None:
        dialog = self.build_export_dialog(character)
        if dialog is not None:
            dialog.exec()
