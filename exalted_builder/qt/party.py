"""exalted_builder/qt/party.py — the Storyteller's Party window (a SECOND window).

Input: a RuleSet and the builder's shared context (`party`, `party_path`,
`adversary_catalog`). Output: a top-level window — a toolbar (the party name, Add
character, Save / Load party, Print all, New party) over three tabs: **Party** (a live
card per member), **Adversaries** (`qt/adversaries.py`) and **Reference** (the ST
screen). Mechanism: `reload()` redraws the cards from `view.build_party_card_view`;
every play-state click goes through `engine.play`, every roster mutation through
`engine.adversaries`; "Open in builder" calls back into the MainWindow, which re-points
itself at that member's Character — the same object, so nothing needs syncing.

⚠ **The Party tab also holds the ADVERSARY blocks**, below the members, because the user
runs a fight from one screen. Thus two tabs draw the roster, and a change on one tab must
reach the other. A discrete event goes through `on_roster_change` or `on_change`. A
keystroke edit reaches the other tab when the user next opens it (`_tab_shown`). ⚠ The user
edits an adversary on the Adversaries tab only. The "Edit" control on a roster block raises
that tab. Do not build a second editor here.

⚠ **A tracker click REPAINTS. It never rebuilds.** `_sync_card` restyles the boxes of one
card and writes its heading text again. A rebuild deletes the box below the pointer, Qt
gives the focus to a different widget, and the scroll area follows that widget. The
measured jump is 354px to 463px, with the focus in the toolbar. `trackers.restyle` holds
the full note.

⚠ **This is a WINDOW, not a tab** (human's ruling). A Storyteller uses the builder and the
party at the same time. A QDialog is also refused, for the same reason: the user must read
a character sheet and the party together.

⚠ **The Party tab is the THIRD written exception to the collection layout.** It has the
same reason as Play: these blocks are live TRACKERS. There is nothing to select, and a
detail pane hides the health tracks that this surface must show. The Adversaries tab IS a
collection, because the user edits its entries and tracks them. The two halves of this
window have different shapes, and that is correct.

⚠ **Use a LIST and a fixed rail. Do not use a card grid** (human's ruling). A card grid
uses too much space and needs too much scrolling for this task. Each member is a two-line
block, one for each row. The adversaries go below them, two for each row. The batch roller
and the session notes are in a fixed-width rail OUTSIDE the scroll area. Measured with ten
combatants at 1250x950: the scrolling content went from 2,097px to 505px, thus a full
table fits on one screen. ⚠ **This tab is still not a collection.** There is nothing to
select, and there is no detail pane.

⚠ **Play state stays isolated (decision 0006).** No value on this window enters chargen
validation, the XP audit or a permanent derivation. This module has ZERO game logic.
`view.build_party_card_view` supplies every number.

⚠ **The window holds each member BY REFERENCE.** A card and the builder edit one Character
object. Thus "Open in builder" needs no synchronising code. ⚠ Thus a member that you remove
from the roster leaves the builder pointing at a character that the roster does not hold.
Call `on_close_member` on every path that removes or replaces the roster.
"""

from __future__ import annotations

import html as _html
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QTabWidget, QTextBrowser, QToolBar, QVBoxLayout, QWidget,
)

from exalted_builder import persistence
from exalted_builder.engine import (adversaries as adv, derive, dice,
                                    play as engineplay)
from exalted_builder.models.character import Character, Damage, PlayState, new_character_id
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.ui import pdf, theme
from exalted_builder.ui import view as viewmod

from . import theme as qtheme
# ⚠ Import the trait ORDER. Do not write the list again. With a fourth copy of the nine
# Attributes, the roster block and the roster editor print them in different orders.
from .adversaries import (AdversariesPage, AdversaryTrackers,
                          _ATTRIBUTES as _ADV_ATTRIBUTES, _VIRTUES as _ADV_VIRTUES)
from .layout import clear_layout
from .sheet import (SheetColors, build_document, print_colors, screen_colors,
                    screen_colors_for, sheet_html)
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL, box as tracker_box, restyle as restyle_box

# ⚠ The value is 16, not 10. The track of a member wraps at this count, and a wrap adds a
# line to the block. The block has two lines, thus a wrap changes four members on the
# screen to two. ⚠ The value is not higher, because line 2 must hold the Essence, Willpower
# and Limit panels BESIDE the track. 16 boxes leave space for them at the narrowest
# supported window. 7 base levels cover a character with no Ox-Body. A Solar with 19 levels
# wraps, and the wrap rules in `_health` make that safe.
#
# ⚠ This number, the tracker box sizes and `_RAIL_WIDTH` are ONE budget. Line 2 holds the
# track, the Essence pools, Willpower and Limit side by side. The widest real member, a
# Solar with 19 Ox-Body levels, measured 887px against an 856px viewport. That gives a
# horizontal scrollbar at the design size. ⚠ If you change one of the three values, measure
# the other two again. Below 1250px wide, the scrollbar is the intended behaviour. At
# 1250px it must not appear.
_BOXES_PER_ROW = 14

# The name column of the batch roll. It is fixed, thus the dice box of every row aligns.
# ⚠ It is narrower than the column on the Play tab, because the roller is in a fixed-width
# rail.
_BATCH_NAME_WIDTH = 104

# A botched row in a batch log, the same amber the Play tab uses for "your call".
_BATCH_BOTCH = "#d9a441"

# The right rail. It holds the batch roller and the session notes. It is FIXED, and it is
# outside every scroll area. ⚠ The position of the roller must not depend on the number of
# combatants (human's ruling).
# ⚠ Size the rail from the BATCH ROW, which is the widest item in it: a tick, a name
# column, a dice box, a repeat box and a free-text label. A narrower rail makes the label
# field too small, and that field is the only place where the Storyteller can record the
# purpose of a row.
_RAIL_WIDTH = 380

# Below this width, an adversary block is difficult to read. The roster grid uses the
# number of columns that fit. ⚠ The MEMBERS are not a grid. See `reload`.
_CARD_WIDTH = 400

# The Great Geas, The Mountain Folk (CH6) p.235. ⚠ The Storyteller decides a divergence.
# The engine never enforces one, because a broken oath is a decision of the Storyteller.
# Thus the block shows the nine clauses as a copy of the page (human's ruling).
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

    ⚠ **Do NOT use a QLabel with word wrap.** A label that wraps answers `heightForWidth`,
    and the `QGridLayout` that lays out these blocks ignores that value. The block is then
    too short, and it paints the tracker boxes through the heading below them.

    ⚠ **Set the horizontal policy to `Ignored`.** An abilities line reads "Archery 1,
    Athletics 1, Awareness 1, Brawl 1, Bureaucracy 1, …", and a prose line reads "All Solar
    Charms the Storyteller cares to give him" (p.303). With a normal policy, one of those
    lines sets the minimum width of the block and makes the grid too wide. `Ignored` lets
    the block set its own width, and the text shortens to that width.

    ⚠ Do NOT shorten the text by CHARACTER COUNT. That cuts a line in the middle of a word
    and shows no "…". One count cannot be correct for a one-column layout and a
    three-column layout.
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


def _row_button(label: str, tip: str) -> QPushButton:
    """The action button of a block. It is small, quiet and BORDERED.

    ⚠ Keep the border (human's ruling). These buttons are inline on a stat line, not in a
    row of their own. As flat muted text, they read as more stat text. Four full-weight
    QPushButtons on each row are too prominent. An outline shows "clickable" with the least
    ink.

    ⚠ Set the border rule ONLY. Thus the `:disabled` and `:hover` rules of the shell QSS
    still apply.
    """
    button = QPushButton(label)
    button.setToolTip(tip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        f"QPushButton {{ color:{MUTED}; font-size:10px; padding:1px 6px; "
        f"border:1px solid {INPUT}; border-radius:3px; background:transparent; }}")
    return button


# --------------------------------------------------------------------------- #
# The Party tab — live blocks
# --------------------------------------------------------------------------- #

class PartyPage(QWidget):
    """The member blocks. `reload()` draws every block for the party in ctx again.

    The window supplies `on_open`, `on_sheet`, `on_pdf` and `on_remove`. A block owns its
    trackers only."""

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
        # ⚠ Use a hook. Do not call the other tab directly. TWO surfaces draw the roster,
        # thus a change on one must reach the other. The page must also operate alone in a
        # test. Thus the default hook does nothing.
        self._on_roster_change = on_roster_change or (lambda: None)
        self._columns = 0
        # The tracker widgets of each block, keyed by member index. `_sync_card` repaints
        # them.
        self._card_boxes: dict[int, dict] = {}
        # The tracker widgets of each adversary, keyed by entry id. ⚠ Repaint them. Never
        # rebuild them.
        self._adv_trackers: dict[str, AdversaryTrackers] = {}

        body = QWidget()
        outer_body = QVBoxLayout(body)
        outer_body.setContentsMargins(8, 8, 8, 8)
        outer_body.setSpacing(6)
        # ⚠ Use a LIST, not a grid. Put one member on each row, at full width. The two-line
        # block reads from left to right. A second column halves the space of the health
        # track and saves no height, because a block is approximately 62px high.
        self._members_lay = QVBoxLayout()
        self._members_lay.setContentsMargins(0, 0, 0, 0)
        self._members_lay.setSpacing(4)
        outer_body.addLayout(self._members_lay)
        # The adversaries, below the party that fights them. The user runs a fight from
        # this ONE screen. `_roster_lay` holds a heading and its own block grid, and this
        # code rebuilds both together. This part IS a grid. An adversary block is short and
        # narrow, thus two blocks on a row waste no space.
        self._roster_lay = QVBoxLayout()
        self._roster_lay.setContentsMargins(0, 0, 0, 0)
        self._roster_lay.setSpacing(4)
        outer_body.addLayout(self._roster_lay)
        outer_body.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(body)

        # ---- the rail ---------------------------------------------------- #
        # ⚠ Use a fixed width, and put the rail OUTSIDE the scroll area. Below both
        # rosters, three characters push the batch roller off the window. ⚠ No size in this
        # rail can depend on the number of combatants.
        rail = QWidget()
        rail.setObjectName("partyRail")
        rail.setFixedWidth(_RAIL_WIDTH)
        # ⚠ Set the stylesheet inline, on the widget. An ancestor stylesheet beats a
        # palette that you set on the widget.
        rail.setStyleSheet(f"QWidget#partyRail {{ background:{CARD}; }}")
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(8, 8, 8, 6)
        rail_lay.setSpacing(6)
        # The batch roll operates on BOTH rosters. Its rows hold party members and
        # adversaries, because a dice count is the same for both. ⚠ Read decision 0019 and
        # `_build_batch` before you change it.
        self._batch_lay = QVBoxLayout()
        self._batch_lay.setContentsMargins(0, 0, 0, 0)
        self._batch_lay.setSpacing(4)
        rail_lay.addLayout(self._batch_lay)
        self._batch_state = viewmod.new_batch_state()
        self._batch_keys: list[str] = []
        self._batch_folds: dict[int, tuple] = {}
        self._build_batch()
        rail_lay.addStretch(1)

        heading = QLabel("SESSION NOTES")
        heading.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED}; "
                              f"font-size:11px;")
        rail_lay.addWidget(heading)
        self.session_notes = QPlainTextEdit()
        self.session_notes.setObjectName("party.session_notes")
        self.session_notes.setPlaceholderText(
            "What happened, what's next, who owes whom…")
        self.session_notes.setFixedHeight(110)
        self.session_notes.textChanged.connect(self._write_session_notes)
        rail_lay.addWidget(self.session_notes)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(rail)
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
        """Re-flow the ADVERSARY blocks when their column count changes.

        ⚠ Reflow only when the column count CHANGES. A redraw on each resize event deletes
        the block that the Storyteller types notes into, during a window drag.

        ⚠ Only the roster reflows. The members are a full-width list, and they have no
        column count. Thus call `_reload_roster`, not `reload`. That also keeps the notes
        box of a member through a window drag."""
        super().resizeEvent(event)
        if self._fit_columns() != self._columns:
            self._columns = self._fit_columns()
            self._reload_roster()

    def _fit_columns(self) -> int:
        """How many ADVERSARY blocks fit across. The members do not use this."""
        return max(1, (self._scroll.viewport().width() - 16) // _CARD_WIDTH)

    @staticmethod
    def _even_columns(grid: QGridLayout, columns: int) -> None:
        """Give every column of `grid` the same width.

        ⚠ Without this, a grid creates a column only where it holds an item. Thus ONE block
        in a two-column layout draws at full width, and a full-width block above half-width
        blocks reads as two block sizes. ⚠ Set the stretch of each column after `columns` to
        zero. Without that, a narrower window keeps the old stretch."""
        for column in range(max(columns, grid.columnCount())):
            grid.setColumnStretch(column, 1 if column < columns else 0)

    def reload(self) -> None:
        """Redraw every card, and re-read the session notes from the party."""
        # ⚠ Refill the notes box only when the model and the widget disagree.
        # `setPlainText` moves the cursor to the end. Thus an unconditional refill moves
        # the cursor on each reload.
        notes = self._party().session_notes
        if self.session_notes.toPlainText() != notes:
            self.session_notes.blockSignals(True)
            self.session_notes.setPlainText(notes)
            self.session_notes.blockSignals(False)

        clear_layout(self._members_lay)
        # ⚠ Clear this map with the blocks that it points at. A play-state click repaints
        # these widgets IN PLACE and does not rebuild them. Thus an old entry here is a
        # reference to a deleted C++ object.
        self._card_boxes = {}
        self._columns = self._fit_columns()
        members = self._party().members
        self._members_lay.addWidget(self._section("PARTY", len(members)))
        if not members:
            empty = QLabel("No characters in the party yet.  Use “Add character” to "
                           "load a .character.json, or load a saved .party.json.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{MUTED};")
            self._members_lay.addWidget(empty)
        for index, member in enumerate(members):
            self._members_lay.addWidget(self._card(index, member))
        self._reload_roster()
        self._sync_batch_rows()

    @staticmethod
    def _section(title: str, count: int) -> QLabel:
        """A section heading over a stack of blocks. The count is live. An empty roster
        must state that, and "ADVERSARIES (0)" states it above the note below it."""
        label = QLabel(f"{title}  ({count})")
        label.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED}; "
                            f"font-size:10px;")
        return label

    # ---- the opposition -------------------------------------------------- #

    def reload_roster(self) -> None:
        """Draw the adversary blocks again, and no other block. An edit on the Adversaries
        tab needs this. ⚠ It must not delete a member block that the user types notes
        into."""
        self._reload_roster()

    def _reload_roster(self) -> None:
        clear_layout(self._roster_lay)
        # ⚠ Clear this map with the blocks. This is the rule of `_card_boxes`. An entry
        # that stays is a reference to a deleted C++ object.
        self._adv_trackers = {}
        entries = self._party().adversaries
        # ⚠ A caller can reach `reload_roster` before the first full `reload` measures the
        # viewport. A column count of 0 then causes a division by zero.
        columns = self._columns or self._fit_columns()
        self._roster_lay.addWidget(self._section("ADVERSARIES", len(entries)))
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

        ⚠ **Keep this block.** A table with ONE detail pane shows the health of one
        adversary at a time, and a Storyteller runs a fight against many (human's ruling).
        The table on the Adversaries tab is where the user types an entry from the page.
        This block is where the user runs a fight.

        ⚠ Show the trackers and a stat READOUT only. Add no editor. The user edits an
        adversary on the Adversaries tab, and "Edit" opens that tab.
        """
        accent = accent_light(self._pal_for_roster())
        card = QFrame()
        card.setObjectName("advCard")
        # ⚠ Set the stylesheet inline, on the widget. An ancestor stylesheet beats a
        # palette that you set on the widget.
        card.setStyleSheet(f"QFrame#advCard {{ background:{CARD}; border-radius:6px; }}")
        card.setMinimumWidth(_CARD_WIDTH - 40)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        # Line 1 holds the name and then the actions, on ONE row. Three separate lines for
        # the title, the sub-line and the buttons make the block too tall.
        head = QHBoxLayout()
        head.setSpacing(6)
        title = QLabel(entry.name or "(unnamed)")
        title.setStyleSheet(f"font-weight:700; font-size:13px; color:{accent};")
        head.addWidget(title)
        line = "  ·  ".join(x for x in (adv.category_label(entry), entry.nature,
                                        entry.caste) if x)
        if line:
            sub = _StatLine(line)
            sub.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            head.addWidget(sub, 1)
        else:
            head.addStretch(1)
        # ⚠ Put `_c=False` FIRST in each of these lambdas. `clicked` sends a `checked`
        # bool, and that value goes into the first default argument. Thus a
        # `lambda e=entry:` receives False as its entry and raises in the handler. The Qt
        # event loop does not show that traceback, and the button does nothing.
        for label, tip, slot in (
                ("Reset", "Clear damage and both spent pools",
                 lambda _c=False, e=entry: self._reset_adversary(e)),
                ("Duplicate", "Another one, with its own health track",
                 lambda _c=False, e=entry: self._duplicate_adversary(e)),
                ("Edit", "Open this entry on the Adversaries tab",
                 lambda _c=False, e=entry: self._on_edit_adversary(e.id))):
            button = _row_button(label, tip)
            button.setObjectName(f"adv.{entry.id}.{label.lower()}")
            button.clicked.connect(slot)
            head.addWidget(button)
        lay.addLayout(head)

        # ⚠ Use `dense`. It puts the three tracker panels SIDE BY SIDE. Stacked panels are
        # approximately 130px for each adversary, and six adversaries then fill the screen.
        trackers = AdversaryTrackers(
            entry, accent, prefix=f"adv.{entry.id}", framed=False, box_size=20,
            dense=True, on_change=self._on_roster_change)
        self._adv_trackers[entry.id] = trackers
        lay.addWidget(trackers)
        self._adversary_stats(lay, entry)
        return card

    def _pal_for_roster(self):
        """The roster takes the palette of the PARTY, not the palette of a member. An
        adversary has no splat."""
        splats = {m.character.exalt_type for m in self._party().members}
        return theme.palette(splats.pop() if len(splats) == 1 else None)

    def _adversary_stats(self, lay, entry) -> None:
        """The printed stat block, read-only. It holds the lines that a Storyteller uses to
        call a roll."""
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
        # ⚠ Do NOT set word wrap. This is a functional rule, not a style choice. A QLabel
        # that wraps answers `heightForWidth`, and the `QGridLayout` that lays out these
        # blocks ignores that value. The block then gets a height for one-line labels, its
        # content goes past that height, and it paints the health boxes through the heading
        # below them. Each label here is a printed single line. This code shortens the
        # longer prose and shows the full text on hover. The editor is one click away.
        for text in rows:
            if not text:
                continue
            label = _StatLine(text)
            label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
            lay.addWidget(label)

    def _reset_adversary(self, entry) -> None:
        """⚠ Repaint the boxes. Never rebuild them. A call to `_reload_roster` here deletes
        the Reset button that the user clicked. That causes the same focus and scroll
        defect as a rebuild of a tracker box."""
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

    # ---- the batch roll (decision 0019) ---------------------------------- #

    def _build_batch(self) -> None:
        """The batch roll of the Storyteller. Build it ONCE. It has a name for the batch,
        the two switches, a Roll button, a row list and a log. This code rebuilds the row
        list and the log.

        ⚠ Read decision 0019 first. The user TYPES every count. ⚠ No code here reads the
        pool of a character, and no code can. To fill six rows from a named roll is a
        convenience that decision 0019 refuses: the app then reports what six sheets roll,
        and the next request is "add their Charm dice". A row takes the name of the
        CHARACTER, which states nothing about a pool. The name of a roll states one.

        ⚠ Build the controls one time, and clear `_batch_rows_lay` and `_batch_log_lay`
        only. Thus a roll or a roster change cannot delete the button below the pointer.
        """
        body = self._panel(self._batch_lay, "BATCH ROLL", self._accent())
        # ⚠ Use TWO rows. The panel is a fixed-width rail, not a full-width band below the
        # rosters. On one row, the name field, the target and the Roll button cut each
        # other. The batch name needs the width, thus it gets its own row.
        self._batch_name = QLineEdit()
        self._batch_name.setObjectName("party.batch.name")
        self._batch_name.setPlaceholderText("Name this roll — e.g. Join Battle")
        self._batch_name.textChanged.connect(
            lambda t: self._batch_state.update(name=t))
        self._batch_name.returnPressed.connect(self._do_batch_roll)
        body.addWidget(self._batch_name)

        controls = QHBoxLayout()
        target = QSpinBox()
        target.setObjectName("party.batch.target")
        target.setRange(2, 10)
        target.setValue(self._batch_state["target_number"])
        target.valueChanged.connect(
            lambda v: self._batch_state.update(target_number=v))
        controls.addWidget(QLabel("Target"))
        controls.addWidget(target)
        controls.addStretch(1)
        roll = QPushButton("Roll all")
        roll.setObjectName("party.batch.roll")
        roll.clicked.connect(self._do_batch_roll)
        controls.addWidget(roll)
        body.addLayout(controls)

        switches = QHBoxLayout()
        doubles = QCheckBox("10s count double")
        doubles.setObjectName("party.batch.doubles")
        doubles.setChecked(self._batch_state["doubles_tens"])
        doubles.toggled.connect(lambda on: self._batch_state.update(doubles_tens=on))
        switches.addWidget(doubles)
        botch = QCheckBox("Can botch")
        botch.setObjectName("party.batch.botch")
        botch.setChecked(self._batch_state["can_botch"])
        botch.toggled.connect(lambda on: self._batch_state.update(can_botch=on))
        switches.addWidget(botch)
        switches.addStretch(1)
        body.addLayout(switches)

        # ⚠ The row list SCROLLS in the rail. It is the one item here that grows with the
        # roster. A rail that grows with the roster causes the defect that the rail
        # prevents: it removes the note and the log from the bottom of the rail.
        self._batch_rows_lay = QVBoxLayout()
        self._batch_rows_lay.setContentsMargins(0, 0, 0, 0)
        self._batch_rows_lay.setSpacing(2)
        rows_box = QWidget()
        rows_box.setLayout(self._batch_rows_lay)
        rows_scroll = QScrollArea()
        rows_scroll.setWidgetResizable(True)
        rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
        rows_scroll.setMaximumHeight(280)
        rows_scroll.setWidget(rows_box)
        body.addWidget(rows_scroll)
        note = QLabel("Tick who is rolling and type the dice each picks up; x2 "
                      "takes that many rolls for one character. An unticked row, "
                      "or one at 0 dice, sits out. "
                      "Stunts, difficulty and Charms are yours — this does not know.")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        body.addWidget(note)
        self._batch_log_lay = QVBoxLayout()
        self._batch_log_lay.setSpacing(2)
        body.addLayout(self._batch_log_lay)

    def _sync_batch_rows(self) -> None:
        """Rebuild the row list, but ONLY when the roster actually changed.

        ⚠ An unconditional rebuild deletes a spin box while the user types. `reload()` runs
        on each roster change, and the Storyteller can type counts while adding the last
        adversary. The typed values stay in either case. `_batch_state` holds them, keyed
        by row id. ⚠ Never key them by position. A positional key moves the dice of one
        character onto the row of another character.
        """
        rows = viewmod.batch_roster(self._party())
        keys = [key for key, _ in rows]
        if keys == self._batch_keys:
            return
        self._batch_keys = keys
        clear_layout(self._batch_rows_lay)
        if not rows:
            self._batch_rows_lay.addWidget(
                self._muted("No one on the roster to roll for yet."))
            return
        for brow in viewmod.batch_rows(self._batch_state, rows):
            key, name, count, label = brow.key, brow.name, brow.count, brow.label
            row = QHBoxLayout()
            # Build this box from the state on each repaint. A typed dice count also
            # selects the row (`view.set_batch_count`). Thus the box cannot hold its own
            # value.
            tick = QCheckBox()
            tick.setObjectName(f"party.batch.include.{key}")
            tick.setChecked(brow.included)
            tick.setToolTip("Roll for this one")
            tick.toggled.connect(
                lambda on, k=key: viewmod.set_batch_included(
                    self._batch_state, k, on))
            row.addWidget(tick)
            # ⚠ Use a FIXED width, and shorten the text HERE. Do not use `_StatLine`. With
            # a minimum width, a long character name moves the dice box of that row out of
            # line with the other rows. `_StatLine` does not operate here, because its
            # `Ignored` horizontal policy beats a fixed width and makes the column empty.
            # This code knows the width, thus it can shorten the text.
            who = QLabel()
            who.setFixedWidth(_BATCH_NAME_WIDTH)
            who.setToolTip(name)
            who.setText(who.fontMetrics().elidedText(
                name, Qt.TextElideMode.ElideRight, _BATCH_NAME_WIDTH - 6))
            row.addWidget(who)
            dice_box = QSpinBox()
            dice_box.setObjectName(f"party.batch.count.{key}")
            dice_box.setRange(0, dice.MAX_DICE)
            dice_box.setValue(count)
            dice_box.valueChanged.connect(
                lambda v, k=key, t=tick: (
                    viewmod.set_batch_count(self._batch_state, k, v),
                    t.setChecked(k in self._batch_state["included"])))
            row.addWidget(dice_box)
            times_box = QSpinBox()
            times_box.setObjectName(f"party.batch.times.{key}")
            times_box.setRange(1, viewmod.MAX_BATCH_REPEATS)
            times_box.setValue(brow.times)
            times_box.setPrefix("x")
            times_box.setToolTip("How many rolls for this one")
            times_box.valueChanged.connect(
                lambda v, k=key: viewmod.set_batch_times(self._batch_state, k, v))
            row.addWidget(times_box)
            text = QLineEdit(label)
            text.setObjectName(f"party.batch.label.{key}")
            text.setPlaceholderText("Label (yours)")
            text.textChanged.connect(
                lambda t, k=key: self._batch_state["labels"].__setitem__(k, t))
            row.addWidget(text, 1)
            self._batch_rows_lay.addLayout(row)

    def _muted(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        return label

    def _do_batch_roll(self) -> None:
        rows = viewmod.batch_roster(self._party())
        if viewmod.roll_batch(self._batch_state, rows) is None:
            self._notify("No rows to roll — tick someone and give them dice.")
            return
        self._fill_batch_log()

    def _notify(self, text: str) -> None:
        """The page stands alone in tests, so the status hook is optional."""
        hook = self._ctx.get("notify")
        if callable(hook):
            hook(text)

    def _fill_batch_log(self) -> None:
        """Paint the log again, and no other widget. Each batch is a fold, and its caption
        is the name that the Storyteller gave it. An open fold shows one line per row."""
        clear_layout(self._batch_log_lay)
        self._batch_folds = {}
        for batch in self._batch_state["log"]:
            open_ = batch.key in self._batch_state["open"]
            head = QPushButton()
            head.setObjectName(f"party.batch.fold.{batch.key}")
            head.setFlat(True)
            head.setStyleSheet(f"text-align:left; color:{MUTED};")
            box = QWidget()
            box_lay = QVBoxLayout(box)
            box_lay.setContentsMargins(16, 0, 0, 4)
            box_lay.setSpacing(1)
            for entry in batch.rolls:
                colour = _BATCH_BOTCH if entry.botch else self._accent()
                line = QLabel(
                    f'<b><span style="color:{colour}">{_html.escape(entry.outcome)}'
                    f'</span></b>&nbsp;&nbsp;{_html.escape(entry.label)}'
                    f'&nbsp;&nbsp;<span style="color:{MUTED}">'
                    f'{_html.escape(entry.faces_text)}</span>')
                line.setWordWrap(True)
                box_lay.addWidget(line)
            box_lay.addWidget(self._muted(batch.detail))
            box.setVisible(open_)
            head.clicked.connect(lambda _c=False, k=batch.key: self._toggle_batch(k))
            self._batch_folds[batch.key] = (head, box)
            self._batch_log_lay.addWidget(head)
            self._batch_log_lay.addWidget(box)
            self._sync_batch_caption(batch)
        if self._batch_state["log"]:
            self._batch_log_lay.addWidget(self._muted(
                "This session only — nothing is saved to any character."))

    def _sync_batch_caption(self, batch) -> None:
        head, _ = self._batch_folds[batch.key]
        open_ = batch.key in self._batch_state["open"]
        head.setText(("▾  " if open_ else "▸  ") + batch.caption)

    def _toggle_batch(self, key: int) -> None:
        """Open or close one fold. Change the visibility ONLY. ⚠ A rebuild of the log here
        deletes the button that the user clicks."""
        open_set = self._batch_state["open"]
        if key in open_set:
            open_set.discard(key)
        else:
            open_set.add(key)
        head, box = self._batch_folds[key]
        box.setVisible(key in open_set)
        batch = next(b for b in self._batch_state["log"] if b.key == key)
        self._sync_batch_caption(batch)

    def _panel(self, lay, title: str | None, accent: str) -> QVBoxLayout:
        """A heading over a body, as a COLUMN added to `lay`.

        `self._last_head` holds the new heading. Each heading carries a live count, and
        `_sync_card` writes that text again. A `title` of None gives a body with no
        heading. The health strip needs that, because its counts are on the stat line
        above. A second copy here gives two values to keep in agreement.

        ⚠ Add a column. Do not add two items to `lay`. The blocks lay out their panels
        HORIZONTALLY. Thus a heading that you add to a QHBoxLayout goes BESIDE its boxes,
        not above them.
        """
        column = QVBoxLayout()
        # ⚠ Set the margins to zero. A nested QVBoxLayout takes an 11px default on all four
        # sides. Six of them in one block add 130px of empty space between each heading and
        # its boxes.
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(1)
        self._last_head = None
        if title is not None:
            head = QLabel(title)
            head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{accent};"
                               f" font-size:9px;")
            self._last_head = head
            column.addWidget(head)
        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(3)
        column.addLayout(body)
        lay.addLayout(column)
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
        # ⚠ Set the stylesheet inline, on the widget. An ancestor stylesheet always beats a
        # palette that you set on the widget. Thus a block that uses a QPalette paints the
        # page shade.
        card.setStyleSheet(f"QFrame#partyCard {{ background:{CARD}; border-radius:4px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)
        self._card_boxes[index] = {"health": [], "willpower_spent": [], "count": [],
                                   "health_head": None, "willpower_head": None,
                                   "count_head": None, "character": character}

        # ---- line 1: who, what they can take, what to do with them -------- #
        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel(cv.name + ("  🔒" if cv.chargen_locked else ""))
        title.setToolTip("Chargen locked — in play" if cv.chargen_locked else "")
        title.setStyleSheet(f"font-weight:700; font-size:13px; color:{accent};")
        head.addWidget(title)
        # ⚠ Use `_StatLine`. It SHORTENS its text, and it does not make the line wider than
        # the window. Line 1 holds six items, and four of them have a hard minimum width:
        # the name, the live health readout, the notes box and the four buttons. If the two
        # information labels cannot become smaller, the buttons go past the right edge and
        # the page gets a horizontal scrollbar.
        identity = _StatLine(cv.identity_line)
        identity.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        head.addWidget(identity, 1)
        # The permanent numbers that a Storyteller uses to call a roll. ⚠ Keep these
        # SEPARATE from the live label next to them. A play-state click changes none of
        # these values. In one string, `_sync_card` writes three derived numbers again on
        # each health click with no cause. Also, `dodge` is a stored Ability rating, not a
        # pool, and one shared label loses that difference.
        permanent = _StatLine(f"Soak {cv.soak.bashing}B/{cv.soak.lethal}L/"
                              f"{cv.soak.aggravated}A · Dodge {cv.dodge} · "
                              f"Essence {cv.essence_rating}")
        permanent.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        head.addWidget(permanent, 2)
        # ⚠ This label is `health_head`, and `_sync_card` writes its text again. The boxes
        # are on the line below, thus the stat line carries the live counts. A repaint that
        # changes the boxes and not this label reads as a block that did nothing.
        stats = QLabel(self._health_title(cv, marks))
        stats.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        self._card_boxes[index]["health_head"] = stats
        head.addWidget(stats)

        # ⚠ Do not reload on a change. A redraw of the block on each keystroke deletes the
        # box and takes the focus. No other widget on the block reads the notes.
        # ⚠ Give this box the STRETCH on this line. Do not give it its own line. On most
        # members this field is empty, and a third line for it makes every block taller.
        notes = QPlainTextEdit(member.notes)
        notes.setObjectName(f"party.{index}.notes")
        notes.setPlaceholderText("Notes…")
        notes.setFixedHeight(22)
        # ⚠ Use a FIXED width. Do not use a stretch. With the stretch, this widget takes
        # all the free space of the line, and the two shortened labels become empty.
        notes.setFixedWidth(150)
        notes.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        notes.setStyleSheet(f"background:{INPUT}; font-size:10px;")
        notes.textChanged.connect(
            lambda m=member, w=notes: setattr(m, "notes", w.toPlainText()))
        head.addWidget(notes)

        for label, tip, slot in (
                ("Sheet", "The character sheet, read-only",
                 lambda: self._on_sheet(character)),
                ("PDF", "Export a print-ready PDF sheet",
                 lambda: self._on_pdf(character)),
                ("Builder", "Point the builder window at this character",
                 lambda: self._on_open(index)),
                ("Remove", "Remove from the party",
                 lambda: self._on_remove(index))):
            button = _row_button(label, tip)
            button.setObjectName(f"party.{index}.{label.lower()}")
            button.clicked.connect(slot)
            head.addWidget(button)
        lay.addLayout(head)

        # ---- line 2: everything that is clicked --------------------------- #
        # ⚠ Align this row to the BOTTOM. A health cell is two rows high, because a
        # wound-penalty caption is above each box. Each widget next to it is one row high.
        # With a different alignment, the spin boxes align with the captions, not with the
        # boxes.
        track = QHBoxLayout()
        track.setSpacing(10)
        track.setAlignment(Qt.AlignmentFlag.AlignBottom)
        self._health(track, index, character, cv, marks, accent)
        self._motes(track, index, character, cv, cur, accent)
        self._willpower(track, index, character, cv, cur, accent)
        self._limit(track, index, character, cur, accent)
        track.addStretch(1)
        lay.addLayout(track)
        return card

    @staticmethod
    def _health_title(cv, marks) -> str:
        counts = {d: sum(1 for m in marks if m == d) for d in Damage}
        return (f"HEALTH   ·   penalty {viewmod.worst_penalty(cv.play, marks)}   ·   "
                f"{counts[Damage.BASHING]}/ {counts[Damage.LETHAL]}x "
                f"{counts[Damage.AGGRAVATED]}*")

    def _health(self, lay, index, character, cv, marks, accent) -> None:
        """The health track. It has no heading. `_card` puts the live counts on the stat
        line, and it keeps the label to write those counts again."""
        body = self._panel(lay, None, accent)
        row = None
        rows: list[QHBoxLayout] = []
        for i, box in enumerate(cv.play.health_boxes):
            if i % _BOXES_PER_ROW == 0:
                row = QHBoxLayout()
                row.setSpacing(3)
                body.addLayout(row)
                rows.append(row)
            mark = marks[i]
            # Put the wound penalty in a CAPTION. Do not put it in a tooltip only. During a
            # fight, a Storyteller reads the next box to mark from the block. A tooltip
            # needs a hover, and six blocks can be on the screen.
            cell = QVBoxLayout()
            cell.setSpacing(0)
            caption = QLabel(box.label)
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            caption.setStyleSheet(f"color:{MUTED}; font-size:9px;")
            cell.addWidget(caption)
            button = tracker_box(f"party.{index}.health.{i}", 18,
                                 MARK_FILL[mark] if mark else INPUT, accent,
                                 mark.value if mark else "")
            button.setToolTip(f"Wound penalty {box.label}")
            button.clicked.connect(
                lambda _c=False, c=character, i=i, n=len(cv.play.health_boxes),
                x=index: (engineplay.cycle_mark(c, i, n), self._sync_card(x)))
            self._card_boxes[index]["health"].append(button)
            cell.addWidget(button)
            row.addLayout(cell)
        # ⚠ Add a stretch to EVERY row, not to the last row only. The Play tab has the same
        # rule. A QHBoxLayout of fixed-size cells with no stretch at the end puts its free
        # space BETWEEN the cells. Thus a track that wraps spreads its full rows and keeps
        # the short last row at the left, and the box pitch changes. ⚠ Only an Ox-Body
        # character wraps. A short fixture cannot show this fault.
        for lay_ in rows:
            lay_.addStretch(1)

    def _motes(self, lay, index, character, cv, cur, accent) -> None:
        """The Essence pools.

        ⚠ A merged pool is ONE track: "all of which is considered Peripheral" (p.41). Thus
        a Personal box stays at 0/0 and reads as broken. The view carries `single_pool` for
        this rule, and this block uses it as the Play tab does."""
        # ⚠ Keep this heading short. The panel is a COLUMN in a row of columns, not a
        # full-width band. A heading of "ESSENCE — SINGLE POOL (motes spent)" sets the
        # minimum width of the full block. The caption of the input ("All motes") and its
        # tooltip carry the same information.
        body = self._panel(lay, "ESSENCE" if cv.play.single_pool
                           else "ESSENCE (spent)", accent)
        row = QHBoxLayout()
        row.setSpacing(4)
        # ⚠ `view.spent_motes`, not `cur.*` — see its docstring.
        spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
        if not cv.play.single_pool:
            self._mote_input(row, index, character, "Personal", "motes_personal_spent",
                             spent_p, cv.play.personal_max, accent)
        self._mote_input(row, index, character,
                         "All motes" if cv.play.single_pool else "Peripheral",
                         "motes_peripheral_spent", spent_pp,
                         cv.play.peripheral_max, accent)
        row.addStretch(1)
        body.addLayout(row)
        # ⚠ Use the COMPACT form. These blocks are one row for each party member, and the
        # full sentence of the Play tab hides the numbers that the block must show. ⚠ Keep
        # the note. A small pool with no explanation reads as a defect.
        committed = viewmod.committed_note(cv.play, compact=True)
        if committed:
            note = QLabel(committed)
            note.setObjectName("committedNote")
            note.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            body.addWidget(note)

    def _mote_input(self, row, index, character, caption, field, value, cap, accent) -> None:
        # ⚠ ABBREVIATE the caption on the block, and give the full word in the tooltip. Two
        # of these are side by side in a column of a few hundred pixels. "Personal" and
        # "Peripheral" both start with "Per", and neither word fits. Thus the user can
        # identify the short forms and cannot identify the cut full words.
        label = QLabel({"Personal": "P", "Peripheral": "Pp"}.get(caption, caption))
        label.setToolTip(caption)
        label.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        row.addWidget(label)
        spin = QSpinBox()
        spin.setObjectName(f"party.{index}.{field}")
        spin.setRange(0, cap)
        spin.setValue(min(value, cap))
        spin.setToolTip(f"{caption} — {cap} motes in this pool")
        spin.setFixedWidth(54)
        row.addWidget(spin)
        left = QLabel(f"{max(0, cap - value)}/{cap}")
        left.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        row.addWidget(left)
        # ⚠ Do not reload the block from a spin box. The redraw deletes the box while the
        # user types, and it takes the focus. Write the one label that depends on the value
        # again, in place. ⚠ A "left" count that changes only on the next full reload is
        # worse than no count.
        spin.valueChanged.connect(
            lambda v, c=character, f=field, m=cap: (
                engineplay.set_motes(c, f, v, m),
                left.setText(f"{max(0, m - v)}/{m}")))

    @staticmethod
    def _willpower_title(cv, cur) -> str:
        return (f"WILLPOWER  ({cv.play.willpower_max - cur.willpower_spent}"
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
            return (f"CLARITY  ({cl.total}/{derive.CLARITY_MAX}  ·  {cl.permanent}p "
                    f"+ {cl.temporary}t  ·  band {cl.band})")
        label = derive.limit_label(ruleset, character).upper()   # "PARADOX" for a Sidereal
        return (f"{label}  ({cur.limit}/10"
                f"{f'  — {label} BREAK' if cur.limit >= 10 else ''})")

    def _limit(self, lay, index, character, cur, accent) -> None:
        """Limit, or Clarity for an Alchemical (p.69). ⚠ Never show both. The user can
        click the temporary half of Clarity only. The program derives the permanent
        half."""
        ruleset = self._ruleset
        body = self._panel(lay, self._count_title(character, cur), accent)
        self._card_boxes[index]["count_head"] = self._last_head
        if derive.uses_clarity(ruleset, character):
            self._count_track(body, index, character, "clarity_temporary",
                              cur.clarity_temporary, derive.CLARITY_MAX, accent)
            return
        self._count_track(body, index, character, "limit", cur.limit, 10, accent)
        if derive.limit_label(ruleset, character) == "Divergence":
            # ⚠ Use a BUTTON, not a hover. The Storyteller decides a divergence, and the
            # engine never enforces one. Thus the nine clauses are the copy of the page on
            # this block, and the user must be able to open them.
            # ⚠ Keep the label short, and put the sentence in the tooltip. This button is
            # in a column beside three others. A button with a full clause as its caption
            # sets the minimum width of the full block.
            geas = _row_button("Great Geas…", "The nine Divergence triggers (CH6 p.235)")
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
            button = tracker_box(f"party.{index}.{field}.{i}", 13,
                                 accent if i < spent else INPUT, accent)
            button.clicked.connect(
                lambda _c=False, c=character, i=i, f=field, m=cap, x=index:
                (engineplay.set_count(c, f, i, m), self._sync_card(x)))
            # ⚠ Key these boxes under "willpower_spent" or "count", not under `field`. The
            # third track is `limit` for most splats, and `clarity_temporary` for an
            # Alchemical. A sync that uses the field name skips the track that this
            # character does not have, and it reports no error.
            key = "willpower_spent" if field == "willpower_spent" else "count"
            self._card_boxes[index][key].append(button)
            row.addWidget(button)
        if row is not None:
            row.addStretch(1)

    def _sync_card(self, index: int) -> None:
        """Repaint ONE member card's tracker boxes and headings from the model.

        ⚠ **Never call `reload()` here.** A redraw of every block deletes the box below the
        pointer. Qt then gives the focus to a different widget, and the scroll area scrolls
        to that widget. Measured: a click on a health box of the third block of six moved
        the scroll from 354 to 463, and put the focus in the party-name field of the
        toolbar. The adversary detail pane has the same defect.

        A play click changes nothing structural. No limit moves, thus no track changes its
        length. Thus a repaint in place is correct here."""
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
    """The reference screen of the Storyteller (`RuleSet.st_screen`), as one scrollable
    document. It is read-only. The tables are ready to render, thus this class has no
    logic.

    ⚠ This screen is on THIS window, not on the ST Options tab of the builder (human's
    ruling). The Storyteller uses it at the table, thus it belongs next to the party and
    the adversaries. When the app has no `st_screen.json`, this tab shows a note."""

    def __init__(self, ruleset, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self.view = QTextBrowser()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.view, 1)
        self.apply_colors(theme.palette(None))

    def apply_colors(self, pal) -> None:
        """Draw the screen again, in the accent of `pal` on the dark base. `apply_chrome`
        of the window calls this. Thus a party that becomes one splat re-tints this
        reference with the other surfaces.

        ⚠ Set the widget background here, and the colours of the document. The shell QSS
        gives the card shade to every QTextBrowser, and an ancestor stylesheet beats the
        page colour of the document."""
        colors = screen_colors_for(pal)
        self.view.setStyleSheet(
            f"QTextBrowser {{ background:{colors.paper}; color:{colors.ink}; }}")
        self.view.setDocument(build_document(reference_html(self._ruleset, colors)))


def reference_html(ruleset, colors: SheetColors | None = None) -> str:
    """The ST screen as HTML. It has one heading for each group, and one table for each
    RefTable. A table with no `columns` renders as a list of rows, which is a sequence of
    steps.

    The default of `colors` is the PAPER set, as in `sheet_html`. The tab supplies the
    screen set."""
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
        # ⚠ Take no `notify` hook from the builder. This window has its own status bar. A
        # second messaging channel with no caller becomes a dead field.

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
        # ⚠ TWO tabs draw the roster, and the editor writes on each keystroke. An
        # `on_change` call from each keystroke rebuilds every roster block while the user
        # types a name. Thus a discrete event sends the signal, and a keystroke reaches the
        # other tab when the user next SHOWS it.
        self.tabs.currentChanged.connect(self._tab_shown)
        self.setCentralWidget(self.tabs)
        self.statusBar().showMessage("")
        self.apply_chrome()

    # ---- chrome ---------------------------------------------------------- #

    def _party(self) -> Party:
        return self._ctx["party"]

    def _pal(self):
        """The chrome of the party. It takes the shared splat when every member has the
        same Exalt type, and the default palette in any other case. A mixed party shows its
        identity on the blocks, which always take the colour of their character."""
        splats = {m.character.exalt_type for m in self._party().members}
        return theme.palette(splats.pop() if len(splats) == 1 else None)

    def apply_chrome(self) -> None:
        """Theme the window again for the current party.

        ⚠ Call `qtheme.apply` on THIS window. It is a top-level window. Thus it does not
        get the palette of the builder, and it does not get the stylesheet of the builder.
        A QDialog has the same behaviour, and it draws the light grey of the platform."""
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
        """Apply a change from the roster blocks of the Party tab. Refresh the table of the
        Adversaries tab. Thus the two surfaces always agree."""
        self.adversaries_page.reload()

    def _adversaries_changed(self) -> None:
        """Apply a change from the Adversaries tab to the blocks of the Party tab.

        ⚠ Draw the ROSTER only. A full `party_page.reload()` deletes the member block whose
        notes box the user types into. A member block shows nothing that an adversary edit
        changes."""
        self.party_page.reload_roster()

    def _edit_adversary(self, entry_id: str) -> None:
        """Apply "Edit" on a roster block. Show the Adversaries tab, with that entry
        selected.

        ⚠ A block has no editor. Two editors for one model cause a dead field, as the
        `powers` and `combat_pool` fields show."""
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
        # ⚠ Write the title only. A re-theme here rebuilds the line edit of the toolbar on
        # each keystroke. The palette does not depend on the name.
        self._party().name = text
        self.setWindowTitle(f"Exalted 1e — Party: {text or '(unnamed)'}")

    def reload(self) -> None:
        """Draw both live tabs again. The builder calls this after it changes a character
        that the party holds. The two windows share the objects, thus only the DRAWING is
        old."""
        if self.name_edit.text() != self._party().name:
            self.name_edit.blockSignals(True)
            self.name_edit.setText(self._party().name)
            self.name_edit.blockSignals(False)
        self.party_page.reload()
        self.adversaries_page.reload()
        self.apply_chrome()

    # ---- members --------------------------------------------------------- #

    def add_character(self, character: Character) -> PartyMember:
        """Add a character to the roster BY REFERENCE. Thus an edit in the builder appears
        on the block, and no code synchronises them."""
        member = PartyMember(character=character)
        self._party().members.append(member)
        self.party_page.reload()
        self.apply_chrome()
        return member

    def build_add_character_dialog(self) -> QDialog:
        """⚠ Offer three sources, not the file picker only. If this action opens the file
        dialog of the operating system directly, the user cannot add the character that the
        builder holds. At a table, that is the usual case.

        This function BUILDS the dialog and does not run it, as the other modals here do.
        `exec()` stops a headless run, thus the tests drive this seam."""
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
        # ⚠ Compare the objects, not their values. Two characters can have the same name.
        if not any(m.character is open_char for m in self._party().members):
            take = QPushButton(f"Add “{open_char.name or 'the character in the builder'}”")
            take.setObjectName("party.addOpen")
            take.setToolTip("The character currently open on the builder tabs")
            take.clicked.connect(lambda: finish(open_char, "the open character"))
            lay.addWidget(take)

        blank = QPushButton("Add a blank character")
        blank.setObjectName("party.addBlank")
        blank.clicked.connect(lambda: finish(Character(id=new_character_id()), "a blank character"))
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
        """Give this member to the builder window, and show that window. The two windows
        share the Character object. Thus each change in the builder appears on this
        block."""
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
        # ⚠ The builder can point at the member that this code removed, or at a member
        # whose index moved. Drop the pointer. Do not leave an old pointer.
        self._on_close_member()
        self.party_page.reload()
        self.apply_chrome()
        self._notify_status(f"Removed {name} from the party")

    # ---- the read-only sheet --------------------------------------------- #

    def build_sheet_dialog(self, character: Character) -> QDialog:
        """The sheet of one member, as a document. This function BUILDS the dialog and does
        not run it. `exec()` stops a headless run, thus the tests drive this seam."""
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
        """Replace the full party. ⚠ The builder points at a member of the party that this
        method removed. Drop that pointer. If it stays, a later save goes to a member of a
        roster that the program no longer holds."""
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
        """The export dialog for one member. With `character` as None, it exports the full
        party. This function BUILDS the dialog and does not run it, as the other modals
        here do. It returns None when the party holds nothing to export."""
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
                # ⚠ A party export is NOT a loop over single-sheet exports. `build_pdf` and
                # `build_party_pdf` make two different documents, and the party document
                # takes the name of the party, not the name of its first member.
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
