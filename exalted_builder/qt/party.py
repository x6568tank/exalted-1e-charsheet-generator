"""exalted_builder/qt/party.py — the Storyteller's Party window (a SECOND window).

Input: a RuleSet and the builder's shared context (`party`, `party_path`,
`adversary_catalog`). Output: a top-level window — a toolbar (the party name, Add
character, Save / Load party, Print all, New party) over three tabs: **Party** (a live
card per member), **Adversaries** (`qt/adversaries.py`) and **Reference** (the ST
screen). Mechanism: `reload()` redraws the cards from `view.build_party_card_view`;
every play-state click goes through `engine.play`, every roster mutation through
`engine.adversaries`; "Open in builder" calls back into the MainWindow, which re-points
itself at that member's Character — the same object, so nothing needs syncing.

⚠ **The Party tab carries the ADVERSARY cards too**, under the members, because a fight
is run off one screen. The roster is therefore drawn on two tabs and a change to either
has to reach the other: the discrete events push through `on_roster_change` /
`on_change`, and a per-keystroke edit is picked up when the other tab is next shown
(`_tab_shown`). Editing stays on the Adversaries tab alone — a roster card's "Edit"
raises it rather than growing a second editor.

⚠ **A tracker click REPAINTS, it never redraws.** `_sync_card` restyles one card's boxes
and re-texts its headings. Rebuilding deletes the box under the cursor, and Qt hands the
focus to whatever inherits it with the scroll area following: measured at 354 → 463 with
the focus thrown into the toolbar. `trackers.restyle` carries the full note.

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
    QSizePolicy, QSpinBox, QTabWidget, QTextBrowser, QToolBar, QVBoxLayout, QWidget,
)

from exalted_builder import persistence
from exalted_builder.engine import adversaries as adv, derive, play as engineplay
from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.ui import pdf, theme
from exalted_builder.ui import view as viewmod

from . import theme as qtheme
# ⚠ The trait ORDER is imported, not re-listed. A fourth copy of the nine Attributes is
# how the roster card and the roster editor come to print them in different orders.
from .adversaries import (AdversariesPage, AdversaryTrackers,
                          _ATTRIBUTES as _ADV_ATTRIBUTES, _VIRTUES as _ADV_VIRTUES)
from .layout import clear_layout
from .sheet import (SheetColors, build_document, print_colors, screen_colors,
                    screen_colors_for, sheet_html)
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL, box as tracker_box, restyle as restyle_box

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


class _StatLine(QLabel):
    """One line of a roster card's printed stats, elided to whatever width it is given.

    Input: the full text. Output: a single-line label showing as much as fits, ending in
    "…", with the whole line on hover. Mechanism: `resizeEvent` re-elides against the
    label's own width, which is the only place that width is known.

    ⚠ **Not a word-wrapped QLabel.** A wrapped label answers `heightForWidth`, and the
    `QGridLayout` that lays these cards out does not honour it — the card comes out too
    short and paints the tracker boxes through the heading below them.

    ⚠ **`Ignored` horizontally, and that is the point.** An abilities line runs to
    "Archery 1, Athletics 1, Awareness 1, Brawl 1, Bureaucracy 1, …" and a prose line to
    "All Solar Charms the Storyteller cares to give him" (p.303). A normal policy lets
    one of those set the card's minimum width and blow the grid apart; `Ignored` lets the
    card size itself and the text elide into it. ⚠ Eliding by CHARACTER COUNT instead was
    tried and shipped a card whose lines were CLIPPED mid-word with no ellipsis at all —
    one count cannot be right for both a one-column and a three-column layout.
    """

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._full = text
        self.setToolTip(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self._elide()

    def _elide(self) -> None:
        self.setText(self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, max(0, self.width() - 2)))

    def resizeEvent(self, event) -> None:            # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._elide()


# --------------------------------------------------------------------------- #
# The Party tab — live cards
# --------------------------------------------------------------------------- #

class PartyPage(QWidget):
    """The member cards. `reload()` redraws every card for the party in ctx.

    `on_open`, `on_sheet`, `on_pdf` and `on_remove` are the window's — the card owns the
    trackers and nothing else."""

    def __init__(self, ruleset, ctx, *, on_open, on_sheet, on_pdf, on_remove,
                 on_edit_adversary=None, on_roster_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._on_open = on_open
        self._on_sheet = on_sheet
        self._on_pdf = on_pdf
        self._on_remove = on_remove
        self._on_edit_adversary = on_edit_adversary or (lambda entry_id: None)
        # ⚠ A hook, not a direct call into the sibling tab. The roster is drawn on TWO
        # surfaces now, so a change made on either has to reach the other — and the page
        # must still stand alone in a test, which is why the default is a no-op.
        self._on_roster_change = on_roster_change or (lambda: None)
        self._columns = 0
        # Per-card tracker widgets, keyed by member index — what `_sync_card` repaints.
        self._card_boxes: dict[int, dict] = {}
        # Per-adversary tracker widgets, keyed by entry id — repainted, never rebuilt.
        self._adv_trackers: dict[str, AdversaryTrackers] = {}

        body = QWidget()
        outer_body = QVBoxLayout(body)
        outer_body.setContentsMargins(8, 8, 8, 8)
        outer_body.setSpacing(8)
        self._grid = QGridLayout()
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(8)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer_body.addLayout(self._grid)
        # The opposition, under the party it is fighting — the ONE screen a fight is run
        # off. `_roster_lay` holds a heading and its own card grid, both rebuilt together.
        self._roster_lay = QVBoxLayout()
        self._roster_lay.setContentsMargins(0, 0, 0, 0)
        self._roster_lay.setSpacing(6)
        outer_body.addLayout(self._roster_lay)
        outer_body.addStretch(1)
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

    @staticmethod
    def _even_columns(grid: QGridLayout, columns: int) -> None:
        """Give every column of `grid` the same width.

        ⚠ Without this a grid only ever creates the columns it has items in, so ONE card
        in a two-column layout is drawn full width. That was invisible while the members
        were the only cards on the tab; with the roster underneath it, a full-width lone
        member over half-width adversaries reads as two different card sizes. Columns
        past `columns` are zeroed, or a narrowed window keeps the stretch it had."""
        for column in range(max(columns, grid.columnCount())):
            grid.setColumnStretch(column, 1 if column < columns else 0)

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
        # ⚠ Cleared with the cards it points at. These are the widgets a play-state
        # click repaints IN PLACE rather than rebuilding, so a stale entry here is a
        # reference to a deleted C++ object.
        self._card_boxes = {}
        self._columns = self._fit_columns()
        members = self._party().members
        if not members:
            empty = QLabel("No characters in the party yet.\nUse “Add character” to "
                           "load a .character.json, or load a saved .party.json.")
            empty.setStyleSheet(f"color:{MUTED};")
            self._grid.addWidget(empty, 0, 0)
        for index, member in enumerate(members):
            # ⚠ Aligned TOP, per card. Without it the grid stretches every card in a row
            # to the height of the tallest, and a QVBoxLayout hands that spare height to
            # the gaps between panels — a Solar beside a Sidereal came out with 40px of
            # nothing under each heading.
            self._grid.addWidget(self._card(index, member),
                                 index // self._columns, index % self._columns,
                                 Qt.AlignmentFlag.AlignTop)
        self._even_columns(self._grid, self._columns)
        self._reload_roster()

    # ---- the opposition -------------------------------------------------- #

    def reload_roster(self) -> None:
        """Redraw the adversary cards only — what an edit on the Adversaries tab needs,
        without tearing down a member card someone is typing notes into."""
        self._reload_roster()

    def _reload_roster(self) -> None:
        clear_layout(self._roster_lay)
        # ⚠ Cleared with the cards. Same rule as `_card_boxes`: a surviving entry here is
        # a handle on a deleted C++ object.
        self._adv_trackers = {}
        entries = self._party().adversaries
        # `reload_roster` is reachable before the first full `reload` has measured the
        # viewport, and a column count of 0 is a division by zero rather than a layout.
        columns = self._columns or self._fit_columns()
        head = QHBoxLayout()
        title = QLabel(f"ADVERSARIES  ({len(entries)})")
        title.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED};")
        head.addWidget(title)
        head.addStretch(1)
        self._roster_lay.addLayout(head)
        if not entries:
            note = QLabel("No adversaries yet — add extras, beasts or NPCs on the "
                          "Adversaries tab and they appear here beside the party.")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED};")
            self._roster_lay.addWidget(note)
            return
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        for index, entry in enumerate(entries):
            grid.addWidget(self._adversary_card(entry),
                           index // columns, index % columns,
                           Qt.AlignmentFlag.AlignTop)
        self._even_columns(grid, columns)
        self._roster_lay.addLayout(grid)

    def _adversary_card(self, entry) -> QFrame:
        """One adversary as a live tracker card, beside the characters fighting it.

        ⚠ **This is what the port dropped.** The webapp renders the roster as a card
        grid on the party page; the native app compressed it into a table plus ONE detail
        pane, so a Storyteller could see exactly one bandit's health at a time — "gming
        combat is a challenge" (human, 2026-08-28). The table is still where an entry is
        typed off the page; this is where a fight is run.

        ⚠ Trackers and a stat READOUT only — no editor. Editing lives on the Adversaries
        tab, and "Edit" jumps there rather than growing a second one here.
        """
        accent = accent_light(self._pal_for_roster())
        card = QFrame()
        card.setObjectName("advCard")
        # ⚠ Inline, on the widget itself — an ancestor stylesheet beats a set palette.
        card.setStyleSheet(f"QFrame#advCard {{ background:{CARD}; border-radius:6px; }}")
        card.setMinimumWidth(_CARD_WIDTH - 40)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        title = QLabel(entry.name or "(unnamed)")
        title.setStyleSheet(f"font-weight:700; font-size:14px; color:{accent};")
        lay.addWidget(title)
        line = "  ·  ".join(x for x in (adv.category_label(entry), entry.nature,
                                        entry.caste) if x)
        if line:
            sub = _StatLine(line)
            sub.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            lay.addWidget(sub)

        trackers = AdversaryTrackers(
            entry, accent, prefix=f"adv.{entry.id}", framed=False, box_size=24,
            on_change=self._on_roster_change)
        self._adv_trackers[entry.id] = trackers
        lay.addWidget(trackers)
        self._adversary_stats(lay, entry)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        # ⚠ `_c=False` FIRST in every one of these. `clicked` carries a `checked` bool,
        # and it lands in the first default argument — a `lambda e=entry:` is handed
        # False as its entry and dies inside the handler, where the Qt event loop
        # swallows the traceback and the button simply does nothing.
        for label, tip, slot in (
                ("Reset", "Clear damage and both spent pools",
                 lambda _c=False, e=entry: self._reset_adversary(e)),
                ("Duplicate", "Another one, with its own health track",
                 lambda _c=False, e=entry: self._duplicate_adversary(e)),
                ("Edit", "Open this entry on the Adversaries tab",
                 lambda _c=False, e=entry: self._on_edit_adversary(e.id))):
            button = QPushButton(label)
            button.setObjectName(f"adv.{entry.id}.{label.lower()}")
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        lay.addLayout(buttons)
        return card

    def _pal_for_roster(self):
        """The roster takes the PARTY's palette, not a member's — an adversary has no
        splat of its own."""
        splats = {m.character.exalt_type for m in self._party().members}
        return theme.palette(splats.pop() if len(splats) == 1 else None)

    def _adversary_stats(self, lay, entry) -> None:
        """The printed block, read-only: the lines a Storyteller calls a roll against."""
        rows = [viewmod.summary_line(self._ruleset, entry),
                viewmod.trait_map_line(entry.attributes, _ADV_ATTRIBUTES)]
        virtues = viewmod.trait_map_line(entry.virtues, _ADV_VIRTUES)
        if virtues:
            rows.append(f"Virtues: {virtues}")
        rows += [adv.attack_line(atk) for atk in entry.attacks]
        if entry.abilities:
            rows.append(adv.trait_line(entry.abilities))
        if entry.backgrounds:
            rows.append(f"Backgrounds: {adv.trait_line(entry.backgrounds)}")
        for label, prose in (("Powers", entry.powers), ("Charms", entry.charms),
                             ("Spells", entry.spells)):
            if prose:
                rows.append(f"{label}: {prose}")
        if entry.notes:
            rows.append(entry.notes)
        # ⚠ NOT word-wrapped, and that is load-bearing rather than a style choice. A
        # wrapped QLabel answers `heightForWidth`, and `QGridLayout` — which is what lays
        # the cards out — does not honour it: the card was handed a height computed from
        # one-line labels, overflowed, and painted the health boxes through the heading
        # under them (2026-08-28). Every label here is a printed one-liner anyway; the
        # prose that isn't is elided with the full text on hover, which is the right
        # trade on a card you glance at mid-fight. The editor is one click away.
        for text in rows:
            if not text:
                continue
            label = _StatLine(text)
            label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            lay.addWidget(label)

    def _reset_adversary(self, entry) -> None:
        """⚠ Repaints, never rebuilds — for the button's OWN sake. `_reload_roster` here
        would delete the Reset button that was just clicked, which is the same
        focus-and-scroll defect one widget over from the one that was reported."""
        adv.reset_tracking(entry)
        trackers = self._adv_trackers.get(entry.id)
        if trackers is not None:
            trackers.sync()
        self._on_roster_change()

    def _duplicate_adversary(self, entry) -> None:
        entries = self._party().adversaries
        index = next((i for i, e in enumerate(entries) if e.id == entry.id), None)
        if index is None:
            return
        adv.duplicate(self._party(), index)
        self._reload_roster()
        self._on_roster_change()


    # ---- one card -------------------------------------------------------- #

    def _panel(self, lay, title: str, accent: str) -> QVBoxLayout:
        """A heading over a body. `self._last_head` is the heading just added — every
        one of these carries a live count that is re-texted rather than rebuilt."""
        head = QLabel(title)
        head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{accent};"
                           f" font-size:11px;")
        self._last_head = head
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
        self._card_boxes[index] = {"health": [], "willpower_spent": [], "count": [],
                                   "health_head": None, "willpower_head": None,
                                   "count_head": None, "character": character}

        title = QLabel(cv.name + ("   🔒" if cv.chargen_locked else ""))
        title.setToolTip("Chargen locked — in play" if cv.chargen_locked else "")
        title.setStyleSheet(f"font-weight:700; font-size:14px; color:{accent};")
        lay.addWidget(title)
        identity = QLabel(cv.identity_line)
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

    @staticmethod
    def _health_title(cv, marks) -> str:
        counts = {d: sum(1 for m in marks if m == d) for d in Damage}
        return (f"HEALTH   ·   penalty {viewmod.worst_penalty(cv.play, marks)}   ·   "
                f"{counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                f"{counts[Damage.AGGRAVATED]}*")

    def _health(self, lay, index, character, cv, marks, accent) -> None:
        body = self._panel(lay, self._health_title(cv, marks), accent)
        self._card_boxes[index]["health_head"] = self._last_head
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
                lambda _c=False, c=character, i=i, n=len(cv.play.health_boxes),
                x=index: (engineplay.cycle_mark(c, i, n), self._sync_card(x)))
            self._card_boxes[index]["health"].append(button)
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

    @staticmethod
    def _willpower_title(cv, cur) -> str:
        return (f"WILLPOWER   ({cv.play.willpower_max - cur.willpower_spent}"
                f"/{cv.play.willpower_max})")

    def _willpower(self, lay, index, character, cv, cur, accent) -> None:
        body = self._panel(lay, self._willpower_title(cv, cur), accent)
        self._card_boxes[index]["willpower_head"] = self._last_head
        self._count_track(body, index, character, "willpower_spent",
                          cur.willpower_spent, cv.play.willpower_max, accent)

    def _count_title(self, character, cur) -> str:
        """The Limit / Paradox / Clarity heading — whichever this character uses."""
        ruleset = self._ruleset
        if derive.uses_clarity(ruleset, character):
            cl = derive.clarity(ruleset, character)
            return (f"CLARITY   ({cl.total}/{derive.CLARITY_MAX}  ·  {cl.permanent} perm "
                    f"+ {cl.temporary} temp  ·  band {cl.band})")
        label = derive.limit_label(ruleset, character).upper()   # "PARADOX" for a Sidereal
        return (f"{label}   ({cur.limit}/10"
                f"{f'  — {label} BREAK' if cur.limit >= 10 else ''})")

    def _limit(self, lay, index, character, cur, accent) -> None:
        """Limit, or Clarity for an Alchemical (p.69) — never both. Only the temporary
        half of Clarity is clickable; the permanent half is derived."""
        ruleset = self._ruleset
        body = self._panel(lay, self._count_title(character, cur), accent)
        self._card_boxes[index]["count_head"] = self._last_head
        if derive.uses_clarity(ruleset, character):
            self._count_track(body, index, character, "clarity_temporary",
                              cur.clarity_temporary, derive.CLARITY_MAX, accent)
            return
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
                lambda _c=False, c=character, i=i, f=field, m=cap, x=index:
                (engineplay.set_count(c, f, i, m), self._sync_card(x)))
            # ⚠ Filed under "willpower_spent" or "count", not under `field`: the third
            # track is `limit` for most splats and `clarity_temporary` for an Alchemical,
            # and a sync keyed on the field name would silently skip whichever one this
            # character does not have.
            key = "willpower_spent" if field == "willpower_spent" else "count"
            self._card_boxes[index][key].append(button)
            row.addWidget(button)
        if row is not None:
            row.addStretch(1)

    def _sync_card(self, index: int) -> None:
        """Repaint ONE member card's tracker boxes and headings from the model.

        ⚠ **Never `reload()`.** A play-state click used to redraw every card on the tab,
        which deletes the box under the cursor — Qt hands the focus on to whatever
        inherits it and the scroll area scrolls to follow. Measured: clicking a health
        box on the third of six cards threw the scroll from 354 to 463 and left the
        focus in the toolbar's party-name field. This is the adversary detail pane's bug
        (human, 2026-08-28) on the surface one tab over; both were found by the same
        probe, and only one of them had been reported.

        Nothing structural can change from a play click — no cap moves, so no track
        changes length — which is what makes repainting in place sound here."""
        card = self._card_boxes.get(index)
        if card is None:
            return
        character = card["character"]
        cv = viewmod.build_party_card_view(self._ruleset, character)
        cur = character.play or PlayState()
        marks = list(cur.health)[:len(cv.play.health_boxes)]
        marks += [None] * (len(cv.play.health_boxes) - len(marks))
        accent = self._accent(character)
        for i, button in enumerate(card["health"]):
            mark = marks[i] if i < len(marks) else None
            restyle_box(button, MARK_FILL[mark] if mark else INPUT, accent,
                        mark.value if mark else "")
        for key, spent in (("willpower_spent", cur.willpower_spent),
                           ("count", cur.clarity_temporary
                            if derive.uses_clarity(self._ruleset, character)
                            else cur.limit)):
            for i, button in enumerate(card[key]):
                restyle_box(button, accent if i < spent else INPUT, accent)
        for key, text in (("health_head", self._health_title(cv, marks)),
                          ("willpower_head", self._willpower_title(cv, cur)),
                          ("count_head", self._count_title(character, cur))):
            if card[key] is not None:
                card[key].setText(text)


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
        self._ruleset = ruleset
        self.view = QTextBrowser()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view, 1)
        self.apply_colors(theme.palette(None))

    def apply_colors(self, pal) -> None:
        """Redraw the screen in `pal`'s accent on the dark base. Called from the
        window's `apply_chrome`, so a party that becomes single-splat re-tints the
        reference with everything else.

        ⚠ The widget background is set here as well as the document's colours: the
        shell QSS gives every QTextBrowser the card shade, and an ancestor stylesheet
        beats anything the document says about its own page."""
        colors = screen_colors_for(pal)
        self.view.setStyleSheet(
            f"QTextBrowser {{ background:{colors.paper}; color:{colors.ink}; }}")
        self.view.setDocument(build_document(reference_html(self._ruleset, colors)))


def reference_html(ruleset, colors: SheetColors | None = None) -> str:
    """The ST screen as HTML: a heading per group, a table per RefTable. A
    `columns`-less table renders as a bare list of rows (a step sequence).

    `colors` defaults to the PAPER set, like `sheet_html`; the tab passes the screen
    set."""
    screen = ruleset.st_screen
    esc = _html.escape
    if screen is None:
        return ("<p>No Storyteller reference screen is loaded "
                "(<code>data/st_screen.json</code> is absent).</p>")
    c = colors if colors is not None else print_colors(None)
    accent = c.accent
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
                parts.append(f"<p style='font-style:italic;color:{c.label};margin:2px 0'>"
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
            on_pdf=lambda c: self._export_pdf(c), on_remove=self._remove_member,
            on_edit_adversary=self._edit_adversary,
            on_roster_change=self._roster_changed)
        self.adversaries_page = AdversariesPage(ruleset, ctx, notify=self._notify_status,
                                                on_change=self._adversaries_changed)
        self.reference_page = ReferencePage(ruleset)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.party_page, "Party")
        self.tabs.addTab(self.adversaries_page, "Adversaries")
        self.tabs.addTab(self.reference_page, "Reference")
        # ⚠ The roster is drawn on TWO tabs, and the editor writes per keystroke. Firing
        # `on_change` from every one of those would rebuild every roster card while
        # someone types a name — so the discrete events push, and typing is picked up
        # when the other tab is next SHOWN.
        self.tabs.currentChanged.connect(self._tab_shown)
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
        self.reference_page.apply_colors(self._pal())

    # ---- the roster, drawn on two tabs ----------------------------------- #

    def _tab_shown(self, index: int) -> None:
        widget = self.tabs.widget(index)
        if widget is self.party_page:
            self.party_page.reload_roster()
        elif widget is self.adversaries_page:
            self.adversaries_page.reload()

    def _roster_changed(self) -> None:
        """A change made on the Party tab's roster cards — refresh the Adversaries
        tab's table so the two never disagree."""
        self.adversaries_page.reload()

    def _adversaries_changed(self) -> None:
        """The mirror: a change made on the Adversaries tab reaches the Party cards.

        ⚠ The ROSTER only. A full `party_page.reload()` would tear down the member card
        whose notes box someone is typing into, and a member card shows nothing an
        adversary edit can change."""
        self.party_page.reload_roster()

    def _edit_adversary(self, entry_id: str) -> None:
        """"Edit" on a roster card: raise the Adversaries tab with that entry selected.

        ⚠ The card carries no editor of its own. Two editors for one model is how the
        `powers`/`combat_pool` dead-field class of bug got in the first time."""
        self.adversaries_page.select(entry_id)
        self.tabs.setCurrentWidget(self.adversaries_page)

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
        colors = screen_colors(character.exalt_type)
        view.setStyleSheet(
            f"QTextBrowser {{ background:{colors.paper}; color:{colors.ink}; }}")
        view.setDocument(build_document(sheet_html(
            viewmod.build_sheet_view(self._ruleset, character), colors)))
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
