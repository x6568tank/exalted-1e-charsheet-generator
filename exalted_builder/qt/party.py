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

⚠ **A LIST plus a fixed rail, not a card grid** (human, 2026-09-09, from the
`spikes/qt_party_dense` spike — *"it's currently card-based, which feels off compared to
the rest of the app… for gm management i don't think we need to use that much space &
scrolling"*). Members are two-line blocks stacked one per row; adversaries go two-up
underneath; the batch roller and the session notes live in a fixed-width rail OUTSIDE the
scroll area. Measured on ten combatants at 1250x950: 2,097px of scrolling content became
505px, so a full table fits above the fold. **This did not make it a collection** — there
is still nothing to select and no detail pane. What changed is the card grid, which was
never what made this tab an exception.

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
# ⚠ The trait ORDER is imported, not re-listed. A fourth copy of the nine Attributes is
# how the roster card and the roster editor come to print them in different orders.
from .adversaries import (AdversariesPage, AdversaryTrackers,
                          _ATTRIBUTES as _ADV_ATTRIBUTES, _VIRTUES as _ADV_VIRTUES)
from .layout import clear_layout
from .sheet import (SheetColors, build_document, print_colors, screen_colors,
                    screen_colors_for, sheet_html)
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL, box as tracker_box, restyle as restyle_box

# ⚠ 16, not 10. A member's track wraps at this, and wrapping costs the block a whole
# extra line — with the block down to two lines that is the difference between four
# members on screen and two. It is not higher because the block's second line has to hold
# the Essence, Willpower and Limit panels BESIDE the track: 16 boxes is what leaves room
# for them at the narrowest window worth supporting. 7 base levels covers everyone who
# has not bought Ox-Body; a heavy Solar at 19 wraps, and the wrap rules in `_health`
# are what make that safe.
#
# ⚠ This number, the tracker box sizes and `_RAIL_WIDTH` are ONE budget. Line 2 holds the
# track, the Essence pools, Willpower and Limit side by side, and the widest real member
# (a 19-level Ox-Body Solar) came to 887px against an 856px viewport — a horizontal
# scrollbar on the shipped window at its design size. Changing any one of them without
# re-measuring the others brings it back. Below 1250px wide the scrollbar is the
# intended degradation; at 1250 it must not appear.
_BOXES_PER_ROW = 14

# The batch roll's name column. Fixed so every row's dice box lines up.
# ⚠ Narrower than the Play tab's: the roller now lives in a fixed-width rail.
_BATCH_NAME_WIDTH = 104

# A botched row in a batch log, the same amber the Play tab uses for "your call".
_BATCH_BOTCH = "#d9a441"

# The right rail — the batch roller and the session notes. FIXED, and outside every
# scroll area: the roller being a function of how many combatants are on the board is
# exactly the complaint this layout answers (human, 2026-09-09).
# ⚠ Sized by the BATCH ROW, which is the widest thing in it: a tick, a name column, a
# dice box, a repeat box and a free-text label. Narrower and the label field is unusably
# small — and it is the only place the Storyteller can say what a row's dice were for.
_RAIL_WIDTH = 380

# One adversary block is unreadable much under this; the roster grid takes as many
# columns as fit. ⚠ The MEMBERS are no longer a grid — see `reload`.
_CARD_WIDTH = 400

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


def _row_button(label: str, tip: str) -> QPushButton:
    """A block's action button: small, quiet, and BORDERED.

    ⚠ The border is the whole point (human, 2026-09-09). These sit inline on a stat line
    rather than in a button row of their own, and the spike drew them as flat muted text
    — at which weight they read as more stat text. A full-weight QPushButton beside four
    others on every row is too loud; an outline is what says "clickable" for the least
    ink. ⚠ Its OWN border rule, so the shell QSS's `:disabled` and `:hover` rules still
    apply — a colour set here would not have replaced those, and none of these is ever
    disabled anyway.
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
        outer_body.setSpacing(6)
        # ⚠ A LIST, not a grid. One member per row, full width — the two-line block reads
        # left-to-right, so a second column would halve the space the health track needs
        # and buy back nothing (a block is ~62px tall either way).
        self._members_lay = QVBoxLayout()
        self._members_lay.setContentsMargins(0, 0, 0, 0)
        self._members_lay.setSpacing(4)
        outer_body.addLayout(self._members_lay)
        # The opposition, under the party it is fighting — the ONE screen a fight is run
        # off. `_roster_lay` holds a heading and its own block grid, both rebuilt
        # together. This one IS a grid: an adversary block is short and narrow enough
        # that two-up wastes nothing.
        self._roster_lay = QVBoxLayout()
        self._roster_lay.setContentsMargins(0, 0, 0, 0)
        self._roster_lay.setSpacing(4)
        outer_body.addLayout(self._roster_lay)
        outer_body.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setWidget(body)

        # ---- the rail ---------------------------------------------------- #
        # ⚠ Fixed width, and OUTSIDE the scroll area. The batch roller used to sit under
        # both rosters, so three characters pushed it entirely off the window — the
        # complaint this layout answers. Nothing in here may be a function of how many
        # combatants are on the board.
        rail = QWidget()
        rail.setObjectName("partyRail")
        rail.setFixedWidth(_RAIL_WIDTH)
        # ⚠ Inline, on the widget itself — an ancestor stylesheet beats a set palette.
        rail.setStyleSheet(f"QWidget#partyRail {{ background:{CARD}; }}")
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(8, 8, 8, 6)
        rail_lay.setSpacing(6)
        # The batch roll rolls for BOTH rosters: its rows are party members and
        # adversaries alike (a dice count does not care which). Decision 0019 —
        # read `_build_batch` before changing it.
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

        ⚠ Only when it CHANGES. A redraw on every resize event would tear down the block
        the Storyteller is typing notes into, on a window drag.

        ⚠ Only the roster reflows now — the members are a full-width list and have no
        column count to change. `_reload_roster` is therefore the redraw, not `reload`,
        which is also what keeps a member's notes box alive through a window drag."""
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

        clear_layout(self._members_lay)
        # ⚠ Cleared with the blocks it points at. These are the widgets a play-state
        # click repaints IN PLACE rather than rebuilding, so a stale entry here is a
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
        """A section rule over a stack of blocks. The count is live — an empty roster
        must say so, and "ADVERSARIES (0)" says it before the note underneath does."""
        label = QLabel(f"{title}  ({count})")
        label.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED}; "
                            f"font-size:10px;")
        return label

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
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        # Line 1: who it is, then the actions, on ONE row. The old block spent a line on
        # the title, a line on the sub-line and a line on the button row.
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
            button = _row_button(label, tip)
            button.setObjectName(f"adv.{entry.id}.{label.lower()}")
            button.clicked.connect(slot)
            head.addWidget(button)
        lay.addLayout(head)

        # ⚠ `dense` — the three tracker panels SIDE BY SIDE rather than stacked. Stacked
        # they are ~130px per adversary and six of them are a screenful on their own.
        trackers = AdversaryTrackers(
            entry, accent, prefix=f"adv.{entry.id}", framed=False, box_size=20,
            dense=True, on_change=self._on_roster_change)
        self._adv_trackers[entry.id] = trackers
        lay.addWidget(trackers)
        self._adversary_stats(lay, entry)
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

    # ---- the batch roll (decision 0019) ---------------------------------- #

    def _build_batch(self) -> None:
        """The Storyteller's batch roll, built ONCE: a name for the batch, the two
        switches, a Roll button, then a rebuilt row list and a rebuilt log.

        ⚠ Read 0019 first. Every count is TYPED — nothing here reads a character's
        pool, and nothing may. With six rows on screen, filling them from a named
        roll is the obvious convenience and is exactly what the decision rejects:
        the app would claim to know what six sheets are rolling, and "add their
        Charm dice" is the next ask. A row's name is the CHARACTER's, which
        asserts nothing about a pool; a roll's name would.

        ⚠ The controls are built once and only `_batch_rows_lay` / `_batch_log_lay`
        are cleared, so a roll or a roster change cannot delete the button under
        the Storyteller's cursor.
        """
        body = self._panel(self._batch_lay, "BATCH ROLL", self._accent())
        # ⚠ TWO rows, because the panel is now a fixed-width rail rather than a
        # full-width band under the rosters. On one row the name field, the target and
        # the Roll button each clipped the next; the batch name is the field that wants
        # the width, so it gets a row to itself.
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

        # ⚠ The row list SCROLLS inside the rail. It is the one thing in here that grows
        # with the roster, and a rail that grows with the roster re-creates the defect
        # the rail exists to fix — it just eats the note and the log from below instead
        # of pushing the whole roller off the window.
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

        ⚠ An unconditional rebuild deletes a spin box mid-keystroke: `reload()`
        runs on every roster change, and the Storyteller may be typing counts
        while adding the last adversary. The typed values themselves survive
        regardless — they live in `_batch_state`, keyed by row id, never by
        position (a positional key moves one character's dice onto another's row).
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
            # Rebuilt from state on every repaint: typing dice ticks the row on
            # (view.set_batch_count), so the box cannot own its own value.
            tick = QCheckBox()
            tick.setObjectName(f"party.batch.include.{key}")
            tick.setChecked(brow.included)
            tick.setToolTip("Roll for this one")
            tick.toggled.connect(
                lambda on, k=key: viewmod.set_batch_included(
                    self._batch_state, k, on))
            row.addWidget(tick)
            # ⚠ A FIXED width, and elided HERE rather than by `_StatLine`. A
            # minimum width lets "Gearheart-of-the-Ninefold-Cog" — a real
            # character name — push that row's dice box out of line with every
            # other row's; `_StatLine` cannot be used because its `Ignored`
            # horizontal policy beats a fixed width and collapses the column to
            # nothing. The width is known here, so the elision can be too.
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
        """Repaint the log alone. Each batch is a fold captioned with the
        Storyteller's name for it; opening one shows a line per row."""
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
        """Open or close one fold. A visibility change ONLY — rebuilding the log
        here would delete the button being clicked."""
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

        `self._last_head` is the heading just added — every one of these carries a live
        count that is re-texted rather than rebuilt. `title` of None is a body with no
        heading, which is what the health strip wants: its counts ride the stat line on
        the row above, so a second copy here would be two things to keep in step.

        ⚠ A column, not two additions to `lay`. The blocks lay their panels out
        HORIZONTALLY now, and a heading added straight to a QHBoxLayout lands *beside*
        the boxes it labels rather than over them.
        """
        column = QVBoxLayout()
        # ⚠ Margins zeroed. A nested QVBoxLayout inherits an 11px default on all four
        # sides, and six of them down a block add 130px of nothing between each heading
        # and the boxes it labels.
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
        # ⚠ Inline, on the widget itself. An ancestor stylesheet beats a set palette
        # every time, so a block that relied on a QPalette would paint the page shade.
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
        # ⚠ `_StatLine`, so it ELIDES under pressure instead of forcing the line wider
        # than the window. Line 1 carries six things and four of them have a hard minimum
        # (the name, the live health readout, the notes box, the four buttons); if the
        # two informational labels could not shrink, the buttons were pushed off the
        # right edge and the page grew a horizontal scrollbar — which is what the first
        # render of this layout did.
        identity = _StatLine(cv.identity_line)
        identity.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        head.addWidget(identity, 1)
        # The permanent numbers a Storyteller calls a roll against. ⚠ Kept SEPARATE from
        # the live label beside it: nothing here changes from a play-state click, so
        # folding the two into one string would make `_sync_card` rewrite three derived
        # numbers on every health box press for no reason — and `dodge` is a stored
        # Ability rating, not a pool, which is a distinction a shared label loses.
        permanent = _StatLine(f"Soak {cv.soak.bashing}B/{cv.soak.lethal}L/"
                              f"{cv.soak.aggravated}A · Dodge {cv.dodge} · "
                              f"Essence {cv.essence_rating}")
        permanent.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        head.addWidget(permanent, 2)
        # ⚠ This label is `health_head`, and it is the one `_sync_card` re-texts. The
        # heading it replaces read "HEALTH · penalty -1 · 1/ 0x 0*" over its own boxes;
        # with the boxes on the line below, the same live counts ride the stat line. A
        # repaint that moved the boxes and not this reads as a card that did nothing.
        stats = QLabel(self._health_title(cv, marks))
        stats.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        self._card_boxes[index]["health_head"] = stats
        head.addWidget(stats)

        # ⚠ No reload on change: redrawing the block per keystroke would delete the box
        # mid-word and steal the focus. Nothing else on the block reads the notes.
        # ⚠ It takes the STRETCH on this line rather than a line of its own — a
        # third line for a field that is empty on most members is what the card grid
        # was spending height on.
        notes = QPlainTextEdit(member.notes)
        notes.setObjectName(f"party.{index}.notes")
        notes.setPlaceholderText("Notes…")
        notes.setFixedHeight(22)
        # ⚠ A FIXED width, not a stretch. Given the stretch it wins the whole line's
        # slack and squeezes the two elided labels beside it to nothing.
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
        # ⚠ Aligned BOTTOM. The health cells are two rows tall (a wound-penalty caption
        # over each box) and everything beside them is one; aligned any other way the
        # spin boxes float against the captions instead of lining up with the boxes.
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
        """The track, with no heading of its own — `_card` puts the live counts on the
        stat line and keeps the handle to re-text them."""
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
            # The wound penalty is CAPTIONED, not just a tooltip: which box to mark next
            # is the thing a Storyteller reads off a card mid-fight, and a hover is no
            # use when six cards are on screen.
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
        # ⚠ EVERY row, not just the last — the same defect the Play tab carried. A
        # QHBoxLayout of fixed-size cells with no trailing stretch spreads its slack
        # BETWEEN them, so a track that wraps draws its full rows justified and the
        # short final row packed left, changing pitch mid-track. Only an Ox-Body
        # character wraps at all, which is why every fixture missed it.
        for lay_ in rows:
            lay_.addStretch(1)

    def _motes(self, lay, index, character, cv, cur, accent) -> None:
        """The Essence pools.

        ⚠ A merged pool is ONE track — "all of which is considered Peripheral" (p.41) —
        so a Personal box would sit at a permanent 0/0 and read as broken. `single_pool`
        is carried on the view for exactly this, and the card honours it the way the Play
        tab does."""
        # ⚠ The heading is short because the panel is now a COLUMN in a row of them, not
        # a full-width band — "ESSENCE — SINGLE POOL (motes spent)" set the whole block's
        # minimum width on its own. The distinction it drew is kept in the input's own
        # caption ("All motes") and its tooltip, which is where it is read anyway.
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
        # ⚠ The COMPACT form. These cards are one row per party member, so the Play
        # tab's full sentence would bury the numbers the card exists to show — but a
        # short pool with no explanation at all reads as a defect, which is the whole
        # reason the note exists.
        committed = viewmod.committed_note(cv.play, compact=True)
        if committed:
            note = QLabel(committed)
            note.setObjectName("committedNote")
            note.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            body.addWidget(note)

    def _mote_input(self, row, index, character, caption, field, value, cap, accent) -> None:
        # ⚠ The caption is ABBREVIATED on the block and spelled out in the tooltip. Two
        # of these sit side by side in a column a few hundred pixels wide; "Personal" and
        # "Peripheral" both start "Per" and neither fits, so the short forms are the ones
        # that can actually be told apart at a glance.
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
            # ⚠ The label is short and the sentence moved into the tooltip: this sits in
            # a column beside three others now, and a button captioned with a full clause
            # sets the whole block's minimum width on its own.
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
