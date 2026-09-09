"""Spike: two denser shapes for the Qt Party tab, against the card grid it has now.

Throwaway — run to LOOK, then decide (the same deal as spikes/qt_edit). Nothing in
`exalted_builder/` is edited; both spikes read the SAME presenters the shipped tab reads
(`view.build_party_card_view`, `view.batch_roster` / `batch_rows`) so what is on screen is
the real numbers off a real party, not a mock.

The complaint being answered (human, 2026-09-09): *"it's currently card-based, which feels
off compared to the rest of the app… for gm management i don't think we need to use that
much space & scrolling"* — three characters fill a 1250x950 window and push the batch
roller entirely below the fold.

  A — THE COMBAT LINE. One row per combatant, party and adversaries in ONE list. Health
      inline and uncaptioned, the pools as text, everything else (notes, buttons, mote
      spinners) behind a per-row ▸ expander. The batch roller is DOCKED at the bottom and
      never scrolls away.

  B — TWO COLUMNS. A two-line block per combatant on the left — the stat line, then the
      trackers with the mote spinners still visible — and the batch roller plus session
      notes in a fixed RIGHT rail. Spends the horizontal space the card grid wastes.

⚠ Neither is a master-detail. The Party tab is the THIRD written exception to the port's
collection layout *because* these are live trackers with nothing to select
(`docs/plans/qt-port.md`), and a detail pane would hide the health tracks the surface
exists to show. What is being attacked here is the card-grid-and-scroll structure, which
is not what makes it an exception.

⚠ Play-state is REAL and shared (decision 0006 still holds — nothing here enters chargen
validation). Clicks go through `engine.play` exactly as the shipped tab does, so a box
ticked in spike A is ticked in spike B on the next redraw.

Run:  .venv/bin/python -m spikes.qt_party_dense           # the window, both spikes + today
      .venv/bin/python -m spikes.qt_party_dense --render  # three PNGs at 1250x950
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget,
)

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.engine import adversaries as adv, derive, play as engineplay
from exalted_builder.models.character import Character, Damage, PlayState
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.qt import theme as qtheme
from exalted_builder.qt.party import PartyPage
from exalted_builder.qt.trackers import MARK_FILL, box as tracker_box
from exalted_builder.qt.theme import CARD, INPUT, MUTED, accent as accent_light
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

ROOT = Path(exalted_builder.__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
DATA = Path(exalted_builder.__file__).resolve().parent / "data"

# The window the human measured the complaint against.
WINDOW = (1250, 950)


# --------------------------------------------------------------------------- #
# The demo party — REAL characters and REAL adversaries
#
# ⚠ Shipped data, not fixtures. A fixture named "Bandit" is too short to reach a card
# edge, so only the real catalogue finds clipped text and blown-out columns.
# --------------------------------------------------------------------------- #

def demo_party(ruleset) -> Party:
    party = Party(id="party.spike", name="The Thousand-Scale Court")
    for path in sorted(EXAMPLES.glob("*.character.json")):
        party.members.append(PartyMember(character=persistence.load_character(path)))
    # Some damage on the board, or every track reads empty and the spike proves nothing
    # about how a marked track scans at a glance.
    for offset, member in enumerate(party.members):
        character = member.character
        boxes = len(viewmod.build_play_view(ruleset, character).health_boxes)
        for i in range(min(offset + 1, boxes)):
            engineplay.cycle_mark(character, i, boxes)
        state = character.play or PlayState()
        state.willpower_spent = offset
        state.limit = offset * 2
        state.motes_peripheral_spent = offset * 3
        character.play = state

    catalog = rules_db.load_adversary_catalog(DATA)
    for template in list(catalog.values())[:6]:
        adv.add_from_template(party, template)
    return party


# --------------------------------------------------------------------------- #
# Shared bits
# --------------------------------------------------------------------------- #

def _muted(text: str, size: int = 11, *, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(wrap)
    label.setStyleSheet(f"color:{MUTED}; font-size:{size}px;")
    return label


def _column(text: str, width: int, style: str) -> QLabel:
    """A fixed-width column of text, elided HERE against the width it is given.

    ⚠ Not `_Elided`. That class is `Ignored` horizontally so it can size itself down
    inside a stretchy row — and `Ignored` BEATS `setFixedWidth`, which collapses the label
    to nothing and lets the next widget draw over it. The trap is already written up
    against the batch roll's name column in `qt/party.py`; it bit again here on the first
    render, where "Dawn Caste · Solar" was painted under the health boxes.
    """
    label = QLabel()
    label.setFixedWidth(width)
    label.setToolTip(text)
    label.setStyleSheet(style)
    label.setText(label.fontMetrics().elidedText(
        text, Qt.TextElideMode.ElideRight, width - 6))
    return label


class _Elided(QLabel):
    """A one-line label that elides into whatever width it is given.

    ⚠ Not a wrapped QLabel: a wrapped label answers `heightForWidth` and the layouts here
    do not honour it — the same trap `qt/party._StatLine` carries. Unlike `_StatLine` this
    one keeps a Preferred policy, because these rows are in a QVBoxLayout rather than a
    QGridLayout and nothing here can blow a grid apart.
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

    def resizeEvent(self, event) -> None:          # noqa: N802 - Qt override
        super().resizeEvent(event)
        self._elide()


def _health_strip(parent_lay, *, prefix, boxes, marks, accent, size, on_click,
                  per_row=None):
    """The health track as a run of small boxes, UNCAPTIONED.

    ⚠ The captions are what make the shipped card tall: a per-box wound-penalty label
    doubles the track's height and triples it for an Ox-Body character who wraps. The
    penalty is carried once, as text, beside the strip — and per box on hover.

    ⚠ Every wrapped row gets a trailing stretch, not just the last one. A QHBoxLayout of
    fixed cells with no stretch spreads its slack BETWEEN them, so a short final row draws
    at a different pitch from the full ones above it (`status/dice-roller.md`).
    """
    rows: list[QHBoxLayout] = []
    row = None
    for i, box in enumerate(boxes):
        if row is None or (per_row and i % per_row == 0):
            row = QHBoxLayout()
            row.setSpacing(2)
            rows.append(row)
            parent_lay.addLayout(row)
        mark = marks[i] if i < len(marks) else None
        button = tracker_box(f"{prefix}.health.{i}", size,
                             MARK_FILL[mark] if mark else INPUT, accent,
                             mark.value if mark else "")
        button.setToolTip(f"{box.label} — wound penalty")
        button.clicked.connect(lambda _c=False, i=i: on_click(i))
        row.addWidget(button)
    for each in rows:
        each.addStretch(1)


def _count_strip(parent_lay, *, prefix, spent, cap, accent, size, on_click):
    row = QHBoxLayout()
    row.setSpacing(2)
    for i in range(cap):
        button = tracker_box(f"{prefix}.{i}", size,
                             accent if i < spent else INPUT, accent)
        button.clicked.connect(lambda _c=False, i=i: on_click(i))
        row.addWidget(button)
    row.addStretch(1)
    parent_lay.addLayout(row)


def _batch_panel(ruleset, party, *, accent) -> QWidget:
    """The batch roller, read off the SAME presenter both shells use.

    ⚠ Decision 0019's no-wire rule is untouched here and must stay so: every count is
    typed, no row offers a named roll, and nothing reads a pool. A denser layout is not a
    licence to fill these boxes from a `PoolRow`.
    """
    state = viewmod.new_batch_state()
    panel = QWidget()
    lay = QVBoxLayout(panel)
    lay.setContentsMargins(8, 6, 8, 6)
    lay.setSpacing(4)
    head = QLabel("BATCH ROLL")
    head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{accent}; "
                       f"font-size:11px;")
    lay.addWidget(head)

    controls = QHBoxLayout()
    name = QLineEdit()
    name.setPlaceholderText("Name this roll — e.g. Join Battle")
    controls.addWidget(name, 1)
    controls.addWidget(QLabel("Target"))
    target = QSpinBox()
    target.setRange(2, 10)
    target.setValue(state["target_number"])
    controls.addWidget(target)
    controls.addWidget(QPushButton("Roll all"))
    lay.addLayout(controls)

    log_lay = QVBoxLayout()
    log_lay.setSpacing(1)

    rows_lay = QVBoxLayout()
    rows_lay.setSpacing(1)
    for brow in viewmod.batch_rows(state, viewmod.batch_roster(party)):
        row = QHBoxLayout()
        row.setSpacing(4)
        tick = QPushButton("☐")
        tick.setFlat(True)
        tick.setFixedWidth(20)
        row.addWidget(tick)
        who = _Elided(brow.name)
        who.setStyleSheet("font-size:11px;")
        row.addWidget(who, 1)
        dice = QSpinBox()
        dice.setRange(0, 30)
        dice.setFixedWidth(56)
        row.addWidget(dice)
        times = QSpinBox()
        times.setRange(1, 9)
        times.setPrefix("x")
        times.setFixedWidth(48)
        row.addWidget(times)
        rows_lay.addLayout(row)
    # ⚠ The rows SCROLL inside the dock. A roster of ten is ten rows, and a dock that
    # grows with the roster re-creates the very problem the dock exists to fix — it just
    # eats the list from the bottom instead of pushing the roller off it.
    rows_box = QWidget()
    rows_box.setLayout(rows_lay)
    rows_scroll = QScrollArea()
    rows_scroll.setWidgetResizable(True)
    rows_scroll.setFrameShape(QFrame.Shape.NoFrame)
    rows_scroll.setMaximumHeight(150)
    rows_scroll.setWidget(rows_box)
    lay.addWidget(rows_scroll)
    lay.addWidget(_muted("Tick who is rolling and type the dice each picks up. "
                         "Stunts, difficulty and Charms are yours — this does not know.",
                         wrap=True))
    lay.addLayout(log_lay)
    return panel


# --------------------------------------------------------------------------- #
# Spike A — the combat line
# --------------------------------------------------------------------------- #

class SpikeA(QWidget):
    """One ROW per combatant, party and adversaries in one list, roller docked below.

    The row is: ▸ · name · what it is · health strip · penalty · E · WP · Limit. The
    expander opens the rest IN PLACE (mote spinners, notes, the four buttons), so nothing
    is lost — it is one click away instead of always on screen.

    ⚠ The expander is per row and several can be open at once. This is not a selection: a
    tracker surface has nothing to select, and a "current" row would be exactly the detail
    pane the Party tab is a written exception to.
    """

    ROW_H = 30

    def __init__(self, ruleset, party, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._party = party
        self._open: set[str] = set()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._body = QWidget()
        self._lay = QVBoxLayout(self._body)
        self._lay.setContentsMargins(8, 6, 8, 6)
        self._lay.setSpacing(2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

        # ⚠ DOCKED, outside the scroll area. The whole complaint is that the roller is
        # below the fold; putting it in the scroll with a denser list only raises the
        # number of combatants it takes to push it off again.
        dock = _batch_panel(ruleset, party, accent=self._accent())
        dock.setStyleSheet(f"background:{CARD};")
        outer.addWidget(dock)

        self.reload()

    def _accent(self, character: Character | None = None) -> str:
        return accent_light(theme.palette(
            character.exalt_type if character is not None else None))

    def reload(self) -> None:
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                _drop(item.layout())
        self._lay.addWidget(self._header("PARTY", len(self._party.members)))
        for index, member in enumerate(self._party.members):
            self._lay.addWidget(self._member_row(index, member))
        self._lay.addSpacing(6)
        self._lay.addWidget(self._header("ADVERSARIES", len(self._party.adversaries)))
        for entry in self._party.adversaries:
            self._lay.addWidget(self._adversary_row(entry))
        self._lay.addStretch(1)

    def _header(self, title: str, count: int) -> QLabel:
        label = QLabel(f"{title}  ({count})")
        label.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED}; "
                            f"font-size:10px;")
        return label

    def _row_frame(self) -> tuple[QFrame, QVBoxLayout]:
        frame = QFrame()
        frame.setObjectName("lineRow")
        frame.setStyleSheet(f"QFrame#lineRow {{ background:{CARD}; border-radius:4px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.setSpacing(2)
        return frame, lay

    def _member_row(self, index: int, member: PartyMember) -> QFrame:
        character = member.character
        cv = viewmod.build_party_card_view(self._ruleset, character)
        accent = self._accent(character)
        cur = character.play or PlayState()
        marks = list(cur.health)[:len(cv.play.health_boxes)]
        marks += [None] * (len(cv.play.health_boxes) - len(marks))
        key = f"m{index}"

        frame, lay = self._row_frame()
        line = QHBoxLayout()
        line.setSpacing(6)

        toggle = QPushButton("▾" if key in self._open else "▸")
        toggle.setFlat(True)
        toggle.setFixedWidth(18)
        toggle.clicked.connect(lambda _c=False, k=key: self._toggle(k))
        line.addWidget(toggle)

        line.addWidget(_column(cv.name + ("  \U0001f512" if cv.chargen_locked else ""), 180,
                               f"font-weight:700; font-size:12px; color:{accent};"))
        line.addWidget(_column(cv.identity_line, 150,
                               f"color:{MUTED}; font-size:10px;"))

        strip = QVBoxLayout()
        strip.setSpacing(1)
        _health_strip(strip, prefix=f"a.{index}", boxes=cv.play.health_boxes,
                      marks=marks, accent=accent, size=14,
                      on_click=lambda i, c=character, n=len(cv.play.health_boxes):
                      (engineplay.cycle_mark(c, i, n), self.reload()))
        line.addLayout(strip, 1)

        spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
        pool = (f"{cv.play.peripheral_max - spent_pp}/{cv.play.peripheral_max}"
                if cv.play.single_pool else
                f"{cv.play.personal_max - spent_p}/{cv.play.personal_max}"
                f" · {cv.play.peripheral_max - spent_pp}/{cv.play.peripheral_max}")
        readout = QLabel(
            f"pen {viewmod.worst_penalty(cv.play, marks)}   ·   E {pool}   ·   "
            f"WP {cv.play.willpower_max - cur.willpower_spent}/{cv.play.willpower_max}"
            f"   ·   {derive.limit_label(self._ruleset, character)[:3]} {cur.limit}")
        readout.setStyleSheet(f"color:{MUTED}; font-size:10px;")
        line.addWidget(readout)
        lay.addLayout(line)

        if key in self._open:
            lay.addWidget(self._member_detail(index, character, cv, cur, accent))
        return frame

    def _member_detail(self, index, character, cv, cur, accent) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(24, 2, 0, 4)
        lay.setSpacing(3)

        pools = QHBoxLayout()
        pools.setSpacing(6)
        spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
        if not cv.play.single_pool:
            pools.addWidget(_muted("Personal", 10))
            personal = QSpinBox()
            personal.setRange(0, cv.play.personal_max)
            personal.setValue(spent_p)
            pools.addWidget(personal)
        pools.addWidget(_muted("All motes" if cv.play.single_pool else "Peripheral", 10))
        peripheral = QSpinBox()
        peripheral.setRange(0, cv.play.peripheral_max)
        peripheral.setValue(spent_pp)
        pools.addWidget(peripheral)
        note = viewmod.committed_note(cv.play, compact=True)
        if note:
            pools.addWidget(_muted(note, 10))
        pools.addSpacing(12)
        pools.addWidget(_muted("WP", 10))
        _count_strip(pools, prefix=f"a.{index}.wp", spent=cur.willpower_spent,
                     cap=cv.play.willpower_max, accent=accent, size=13,
                     on_click=lambda i, c=character, m=cv.play.willpower_max:
                     (engineplay.set_count(c, "willpower_spent", i, m), self.reload()))
        pools.addSpacing(12)
        pools.addWidget(_muted(derive.limit_label(self._ruleset, character), 10))
        _count_strip(pools, prefix=f"a.{index}.limit", spent=cur.limit, cap=10,
                     accent=accent, size=13,
                     on_click=lambda i, c=character:
                     (engineplay.set_count(c, "limit", i, 10), self.reload()))
        pools.addStretch(1)
        lay.addLayout(pools)

        bottom = QHBoxLayout()
        bottom.setSpacing(6)
        notes = QPlainTextEdit(self._party.members[index].notes)
        notes.setPlaceholderText("Notes…")
        notes.setFixedHeight(44)
        notes.setStyleSheet(f"background:{INPUT};")
        bottom.addWidget(notes, 1)
        buttons = QVBoxLayout()
        buttons.setSpacing(2)
        for label in ("Sheet", "PDF", "Builder", "Remove"):
            buttons.addWidget(QPushButton(label))
        bottom.addLayout(buttons)
        lay.addLayout(bottom)
        lay.addWidget(_muted(
            f"Soak {cv.soak.bashing}B / {cv.soak.lethal}L / {cv.soak.aggravated}A"
            f"   ·   Dodge {cv.dodge}   ·   Essence {cv.essence_rating}", 10))
        return panel

    def _adversary_row(self, entry) -> QFrame:
        accent = accent_light(theme.palette(None))
        key = f"a{entry.id}"
        frame, lay = self._row_frame()
        line = QHBoxLayout()
        line.setSpacing(6)

        toggle = QPushButton("▾" if key in self._open else "▸")
        toggle.setFlat(True)
        toggle.setFixedWidth(18)
        toggle.clicked.connect(lambda _c=False, k=key: self._toggle(k))
        line.addWidget(toggle)

        line.addWidget(_column(entry.name or "(unnamed)", 180,
                               f"font-weight:700; font-size:12px; color:{accent};"))
        line.addWidget(_column("  \u00b7  ".join(
            x for x in (adv.category_label(entry), entry.nature) if x), 150,
            f"color:{MUTED}; font-size:10px;"))

        strip = QVBoxLayout()
        strip.setSpacing(1)
        # ⚠ `health_levels` is a LIST of wound penalties, and `damage` is the tracker
        # aligned POSITIONALLY to it — not a count and a total.
        row = QHBoxLayout()
        row.setSpacing(2)
        marks = list(entry.damage)[:len(entry.health_levels)]
        marks += [None] * (len(entry.health_levels) - len(marks))
        for i, penalty in enumerate(entry.health_levels):
            button = tracker_box(f"a.{entry.id}.h.{i}", 14,
                                 MARK_FILL[marks[i]] if marks[i] else INPUT, accent,
                                 marks[i].value if marks[i] else "")
            button.setToolTip(f"−{penalty} wound penalty")
            row.addWidget(button)
        row.addStretch(1)
        strip.addLayout(row)
        line.addLayout(strip, 1)

        line.addWidget(_muted(viewmod.summary_line(self._ruleset, entry), 10))
        lay.addLayout(line)
        if key in self._open:
            detail = QWidget()
            dlay = QVBoxLayout(detail)
            dlay.setContentsMargins(24, 2, 0, 4)
            dlay.setSpacing(1)
            for text in ([adv.attack_line(a) for a in entry.attacks]
                         + ([adv.trait_line(entry.abilities)] if entry.abilities else [])
                         + ([entry.notes] if entry.notes else [])):
                if text:
                    dlay.addWidget(_muted(text, 10))
            buttons = QHBoxLayout()
            buttons.addStretch(1)
            for label in ("Reset", "Duplicate", "Edit"):
                buttons.addWidget(QPushButton(label))
            dlay.addLayout(buttons)
            lay.addWidget(detail)
        return frame

    def _toggle(self, key: str) -> None:
        self._open.symmetric_difference_update({key})
        self.reload()


def _drop(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _drop(item.layout())


# --------------------------------------------------------------------------- #
# Spike B — two columns
# --------------------------------------------------------------------------- #

class SpikeB(QWidget):
    """A two-line block per combatant on the left; the roller and notes in a fixed rail.

    Middle density: the mote spinners and the Willpower/Limit strips stay on screen (spike
    A hides them behind the expander), and the height is bought back by dropping the card
    frame, the per-box captions and the button row — buttons become a hover-weight text
    strip on the right of the stat line.

    ⚠ The rail is FIXED width and outside every scroll area. Same reasoning as spike A's
    dock: the roller must not be a function of how many combatants are on the board.
    """

    RAIL = 330

    def __init__(self, ruleset, party, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._party = party

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._body = QWidget()
        self._lay = QVBoxLayout(self._body)
        self._lay.setContentsMargins(8, 6, 8, 6)
        self._lay.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body)
        outer.addWidget(scroll, 1)

        rail = QWidget()
        rail.setFixedWidth(self.RAIL)
        rail.setStyleSheet(f"background:{CARD};")
        rail_lay = QVBoxLayout(rail)
        rail_lay.setContentsMargins(0, 0, 0, 8)
        rail_lay.setSpacing(6)
        rail_lay.addWidget(_batch_panel(ruleset, party,
                                        accent=accent_light(theme.palette(None))))
        rail_lay.addStretch(1)
        notes_head = QLabel("SESSION NOTES")
        notes_head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED}; "
                                 f"font-size:11px;")
        rail_lay.addWidget(notes_head)
        session = QPlainTextEdit(party.session_notes)
        session.setPlaceholderText("What happened, what's next, who owes whom…")
        session.setFixedHeight(120)
        rail_lay.addWidget(session)
        outer.addWidget(rail)

        self.reload()

    def reload(self) -> None:
        _drop(self._lay)
        self._lay.addWidget(self._header("PARTY", len(self._party.members)))
        for index, member in enumerate(self._party.members):
            self._lay.addWidget(self._member_block(index, member))
        self._lay.addSpacing(6)
        self._lay.addWidget(self._header("ADVERSARIES", len(self._party.adversaries)))
        grid = QGridLayout()
        grid.setSpacing(4)
        for i, entry in enumerate(self._party.adversaries):
            grid.addWidget(self._adversary_block(entry), i // 2, i % 2)
        for column in range(2):
            grid.setColumnStretch(column, 1)
        self._lay.addLayout(grid)
        self._lay.addStretch(1)

    def _header(self, title: str, count: int) -> QLabel:
        label = QLabel(f"{title}  ({count})")
        label.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{MUTED}; "
                            f"font-size:10px;")
        return label

    def _member_block(self, index: int, member: PartyMember) -> QFrame:
        character = member.character
        cv = viewmod.build_party_card_view(self._ruleset, character)
        accent = accent_light(theme.palette(character.exalt_type))
        cur = character.play or PlayState()
        marks = list(cur.health)[:len(cv.play.health_boxes)]
        marks += [None] * (len(cv.play.health_boxes) - len(marks))

        frame = QFrame()
        frame.setObjectName("block")
        frame.setStyleSheet(f"QFrame#block {{ background:{CARD}; border-radius:4px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(6)
        name = QLabel(cv.name + ("  🔒" if cv.chargen_locked else ""))
        name.setStyleSheet(f"font-weight:700; font-size:13px; color:{accent};")
        top.addWidget(name)
        top.addWidget(_muted(cv.identity_line, 10))
        top.addSpacing(10)
        top.addWidget(_muted(
            f"Soak {cv.soak.bashing}B/{cv.soak.lethal}L/{cv.soak.aggravated}A · "
            f"Dodge {cv.dodge} · Essence {cv.essence_rating} · "
            f"pen {viewmod.worst_penalty(cv.play, marks)}", 10))
        top.addStretch(1)
        for label in ("Sheet", "PDF", "Builder", "Remove"):
            button = QPushButton(label)
            button.setFlat(True)
            button.setStyleSheet(f"color:{MUTED}; font-size:10px; text-align:right;")
            top.addWidget(button)
        lay.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        strip = QVBoxLayout()
        strip.setSpacing(1)
        _health_strip(strip, prefix=f"b.{index}", boxes=cv.play.health_boxes,
                      marks=marks, accent=accent, size=16, per_row=20,
                      on_click=lambda i, c=character, n=len(cv.play.health_boxes):
                      (engineplay.cycle_mark(c, i, n), self.reload()))
        bottom.addLayout(strip)

        spent_p, spent_pp = viewmod.spent_motes(cv.play, cur)
        if not cv.play.single_pool:
            bottom.addWidget(_muted("P", 10))
            personal = QSpinBox()
            personal.setRange(0, cv.play.personal_max)
            personal.setValue(spent_p)
            personal.setFixedWidth(56)
            bottom.addWidget(personal)
        bottom.addWidget(_muted("All" if cv.play.single_pool else "Pp", 10))
        peripheral = QSpinBox()
        peripheral.setRange(0, cv.play.peripheral_max)
        peripheral.setValue(spent_pp)
        peripheral.setFixedWidth(56)
        bottom.addWidget(peripheral)
        bottom.addWidget(_muted(f"{cv.play.peripheral_max - spent_pp}"
                                f"/{cv.play.peripheral_max}", 10))
        bottom.addSpacing(8)
        bottom.addWidget(_muted("WP", 10))
        _count_strip(bottom, prefix=f"b.{index}.wp", spent=cur.willpower_spent,
                     cap=cv.play.willpower_max, accent=accent, size=14,
                     on_click=lambda i, c=character, m=cv.play.willpower_max:
                     (engineplay.set_count(c, "willpower_spent", i, m), self.reload()))
        bottom.addWidget(_muted(derive.limit_label(self._ruleset, character)[:3], 10))
        _count_strip(bottom, prefix=f"b.{index}.limit", spent=cur.limit, cap=10,
                     accent=accent, size=14,
                     on_click=lambda i, c=character:
                     (engineplay.set_count(c, "limit", i, 10), self.reload()))
        bottom.addStretch(1)
        lay.addLayout(bottom)
        return frame

    def _adversary_block(self, entry) -> QFrame:
        accent = accent_light(theme.palette(None))
        frame = QFrame()
        frame.setObjectName("block")
        frame.setStyleSheet(f"QFrame#block {{ background:{CARD}; border-radius:4px; }}")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)
        top = QHBoxLayout()
        name = QLabel(entry.name or "(unnamed)")
        name.setStyleSheet(f"font-weight:700; font-size:12px; color:{accent};")
        top.addWidget(name)
        top.addWidget(_muted(adv.category_label(entry), 10))
        top.addStretch(1)
        for label in ("Reset", "Dup", "Edit"):
            button = QPushButton(label)
            button.setFlat(True)
            button.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            top.addWidget(button)
        lay.addLayout(top)
        row = QHBoxLayout()
        row.setSpacing(2)
        marks = list(entry.damage)[:len(entry.health_levels)]
        marks += [None] * (len(entry.health_levels) - len(marks))
        for i in range(len(entry.health_levels)):
            row.addWidget(tracker_box(f"b.{entry.id}.h.{i}", 14,
                                      MARK_FILL[marks[i]] if marks[i] else INPUT, accent,
                                      marks[i].value if marks[i] else ""))
        row.addStretch(1)
        lay.addLayout(row)
        lay.addWidget(_Elided(viewmod.summary_line(self._ruleset, entry)))
        return frame


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #

def build_window(ruleset, party) -> QMainWindow:
    win = QMainWindow()
    win.setWindowTitle("SPIKE — the Party tab, three densities")
    win.resize(*WINDOW)
    tabs = QTabWidget()
    tabs.setDocumentMode(True)
    tabs.addTab(SpikeA(ruleset, party), "A — combat line")
    tabs.addTab(SpikeB(ruleset, party), "B — two columns")
    # ⚠ The shipped page, in the same window and at the same size, or the comparison is
    # against a memory of it. It is the real `PartyPage`, unmodified.
    ctx = {"party": party, "party_path": None, "char": Character(id="char.spike"),
           "dir": ROOT, "adversary_catalog": {}}
    tabs.addTab(PartyPage(ruleset, ctx, on_open=lambda i: None, on_sheet=lambda c: None,
                          on_pdf=lambda c: None, on_remove=lambda i: None),
                "Today — cards")
    win.setCentralWidget(tabs)
    qtheme.apply(win, theme.palette(None))
    return win


def main() -> int:
    render = "--render" in sys.argv
    if render:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv[:1])
    ruleset = rules_db.load_ruleset(DATA)
    party = demo_party(ruleset)
    win = build_window(ruleset, party)
    win.show()
    if not render:
        return app.exec()

    out = Path(__file__).parent / "renders"
    out.mkdir(exist_ok=True)
    tabs = win.centralWidget()
    for index, stem in enumerate(("a-combat-line", "b-two-columns", "today-cards")):
        tabs.setCurrentIndex(index)
        # ⚠ Process events more than once, and wait. The first grab of a QScrollArea
        # reports a crushed body — panels overlapping, no scrollbar — because the layout
        # has not settled (`docs/plans/qt-port.md`). This is the same trap as
        # `qtbot.waitExposed` returning before a nested scroll area lays out.
        for _ in range(6):
            app.processEvents()
        # ⚠ The card page must be reloaded AFTER the layout settles, or the comparison is
        # unfair to it: `_fit_columns` measures the viewport, and a viewport measured
        # before the first pass reports one column where the real window reflows to two.
        page = tabs.widget(index)
        if isinstance(page, PartyPage):
            page.reload()
            for _ in range(4):
                app.processEvents()
        win.grab().save(str(out / f"{stem}.png"))
    print(f"wrote 3 renders to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
