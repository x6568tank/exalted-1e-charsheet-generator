"""exalted_builder/qt/play.py — the Play tab: the in-play tracker.

Input: a RuleSet and the shared context's Character. Output: a toolbar of scene
actions over two panelled columns — the tracker (health, armour fatigue, motes,
temporary Willpower, Limit/Clarity, luck, the custom dice pool) on the left, and the
dice-pool list on the right. Mechanism: every capacity comes from
`view.build_play_view` / `view.build_pool_sidebar`, every mutation from
`engine.play`; a click on a box rebuilds both columns, because a health mark moves the
wound penalty and the wound penalty is a term in every pool.

⚠ **This tab is a written exception to the collection layout** (human's ruling). Each
other Qt tab is a table with a detail pane. Play is a live TRACKER, and it has nothing to
select. The user clicks a health box, and reads a mote count during a roll. Thus a detail
pane hides the numbers that this surface must show. Play uses a **toolbar over panels**.

⚠ **This is a DUMB tracker. Keep it one.** Do not add automatic mote accounting, damage
wrapping or automatic healing. `engine/play.py` holds that rule, and it holds the
isolation of decision 0006. No code here writes back to chargen, to the XP audit or to a
permanent derivation.

⚠ Keep the `compact` breakdown on the pool rows, and keep the exclusions block. Decision
0016 accepted that presentation when it narrowed 0008. It is not decoration. Read 0016
before you change the right column.

⚠ The **dice roller** above that column comes from decision 0019. Its no-wire rule is
necessary. It rolls a COUNT that the user types, under a LABEL that the user writes. It
must never know which roll it makes. A Roll button on a pool row, or a label that a pool
row fills in, restores what 0009 prevents. ⚠ NO TEST FAILS ON THAT CHANGE.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from exalted_builder.engine import derive, dice, merits, play as engineplay
from exalted_builder.models.character import Damage, PlayState
from exalted_builder.models.rules import AbilityName, AttributeName
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .layout import clear_layout
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL as _MARK_FILL, box as _tracker_box

# A health track has twelve boxes or more with Ox-Body. Qt has no flex-wrap. Thus this
# row wraps by construction.
_BOXES_PER_ROW = 10

_AMBER = "#d9a441"                   # the "your call, Storyteller" note colour

# A user looks for a 10 and a 1 in a transcript. The other faces are context. These are
# the same four kinds that the NiceGUI shell colours. Thus the two products agree.
_FACE_COLOR = {"double": _AMBER, "hit": "#d8d3c8", "one": "#c05a5a", "miss": MUTED}

_FATIGUE_NOTE = ("Each failed Stamina + Endurance roll against the armour's fatigue "
                 "value adds a point; each dissipates after eight hours of rest out of "
                 "the armour (p.332). Both are the Storyteller's call — this counter is "
                 "manual, like Limit.")


class PlayPage(QWidget):
    """The tab widget. `reload()` calculates every capacity for the character in ctx again,
    and it draws both columns again. `notify` shows a temporary message."""

    def __init__(self, ruleset, ctx, *, notify=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        # ⚠ Create this state ONCE, here. Never create it in a rebuild. The code draws the
        # columns again on each health click. If the redrawn widgets held the selections,
        # that click would clear the weapon that the user selected.
        # `ui/play.new_pool_state` holds the same shape.
        self._pool_state = self._new_pool_state()

        bar = QHBoxLayout()
        bar.setContentsMargins(8, 4, 8, 4)
        self.clear_damage_btn = QPushButton("Clear damage")
        self.clear_damage_btn.setToolTip(
            "Wipes every health mark. A convenience for \"the scene ended\", not a "
            "healing rule — nothing here knows how long a level takes to heal.")
        self.clear_damage_btn.clicked.connect(self._clear_damage)
        bar.addWidget(self.clear_damage_btn)
        self.clear_motes_btn = QPushButton("Clear motes spent")
        self.clear_motes_btn.clicked.connect(self._clear_motes)
        bar.addWidget(self.clear_motes_btn)
        bar.addStretch(1)

        self._tracker_lay, tracker = self._column()
        # ⚠ Give the roller its OWN layout in the pools column. `_fill_pools` clears
        # `_pools_lay` only. The controls of the roller must stay through a rebuild. A
        # health click draws both columns again, and a rebuild deletes the Roll button
        # below the pointer (`docs/plans/qt-port.md`). Build the roller ONCE, below.
        column_lay, pools = self._column()
        self._roller_lay = QVBoxLayout()
        self._pools_lay = QVBoxLayout()
        column_lay.addLayout(self._roller_lay)
        column_lay.addLayout(self._pools_lay)
        self._roller_state = viewmod.new_roller_state()
        self._roller_char = self._char().id
        self._build_roller()
        split = QSplitter()
        split.addWidget(tracker)
        split.addWidget(pools)
        split.setSizes([700, 480])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        self.reload()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _char(self):
        return self._ctx["char"]

    def _accent(self) -> str:
        return accent_light(theme.palette(self._char().exalt_type))

    def _column(self) -> tuple[QVBoxLayout, QScrollArea]:
        """A scrolling column of panels: (its layout, the scroll area to mount)."""
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        return lay, scroll

    def _new_pool_state(self) -> dict:
        """The selections of the dice-pool column. Returns {} when the app has no roll
        catalogue. The defaults make the custom block show a number at the first draw."""
        if not self._ruleset.roll_catalog:
            return {}
        return {"weapon": None, "arrow": None,
                "mobility": True, "wound": True, "fatigue": True,
                "custom_attribute": AttributeName.DEXTERITY.value,
                "custom_ability": AbilityName.ATHLETICS.value,
                "custom_agility": False}

    def reload(self) -> None:
        """Redraw both columns for the character in ctx."""
        self._fill_tracker()
        self._fill_pools()
        # A transcript belongs to the character that the user rolled for. Thus a SWITCH to
        # a different character empties it. ⚠ A health click must not empty it. Thus this
        # code compares the ids. `reload` is also the refresh.
        if self._char().id != self._roller_char:
            self._roller_char = self._char().id
            self._roller_state.update(viewmod.new_roller_state())
            self._sync_roller_controls()
            self._fill_roll_log()
        self._roller_head.setStyleSheet(
            f"font-weight:700; letter-spacing:1px; color:{self._accent()};")

    def _refresh(self) -> None:
        """Apply a play-state change. Always draw BOTH columns. A health mark and a fatigue
        point are terms in every pool row on the right. The custom-pool block on the left
        reads the same controls as the sidebar."""
        self.reload()

    # ---- the small parts ------------------------------------------------- #

    def _panel(self, lay, title: str) -> QVBoxLayout:
        """A titled card, appended to `lay`. Returns the body layout to fill."""
        frame = QFrame()
        frame.setObjectName("playPanel")
        frame.setStyleSheet(
            f"QFrame#playPanel {{ background:{CARD}; border-radius:6px; }}")
        body = QVBoxLayout(frame)
        body.setContentsMargins(10, 8, 10, 8)
        body.setSpacing(4)
        head = QLabel(title)
        head.setWordWrap(True)
        head.setStyleSheet(f"font-weight:700; letter-spacing:1px; color:{self._accent()};")
        body.addWidget(head)
        lay.addWidget(frame)
        return body

    def _note(self, text: str, *, color: str = MUTED) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{color}; font-size:11px;")
        return label

    def _box(self, name: str, size: int, fill: str, text: str = "") -> QPushButton:
        """One clickable tracker box. `qt/trackers.py` draws it. The party cards and the
        adversary roster draw the same box. Thus a Storyteller learns one damage
        tracker."""
        return _tracker_box(name, size, fill, self._accent(), text)

    def _labelled(self, lay, caption: str, widget) -> None:
        row = QHBoxLayout()
        label = QLabel(caption)
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(90)
        row.addWidget(label)
        row.addWidget(widget)
        row.addStretch(1)
        lay.addLayout(row)

    # ------------------------------------------------------------------ #
    # the tracker column
    # ------------------------------------------------------------------ #

    def _fill_tracker(self) -> None:
        clear_layout(self._tracker_lay)
        ruleset, char = self._ruleset, self._char()
        play = viewmod.build_play_view(ruleset, char)
        # ⚠ Read through `char.play or PlayState()`. Never use `engineplay.play_state`
        # here. To OPEN the tab must not write a PlayState onto a character that nobody has
        # played. If it does, a new sheet saves with play data.
        cur = char.play or PlayState()
        marks = list(cur.health)[:len(play.health_boxes)]
        marks += [None] * (len(play.health_boxes) - len(marks))

        self._health_panel(play, marks)
        self._fatigue_panel(play, cur)
        self._motes_panel(play, cur)
        self._willpower_panel(play, cur)
        if derive.uses_clarity(ruleset, char):
            self._clarity_panel(cur)
        else:
            self._limit_panel(cur)
        self._luck_panel()
        if self._pool_state:
            self._custom_pool_panel()
        self._tracker_lay.addStretch(1)

    def _health_panel(self, play, marks) -> None:
        body = self._panel(self._tracker_lay,
                           "HEALTH   ·   / bashing    x lethal    * aggravated")
        row = None
        rows: list[QHBoxLayout] = []
        for i, box in enumerate(play.health_boxes):
            if i % _BOXES_PER_ROW == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                body.addLayout(row)
                rows.append(row)
            mark = marks[i]
            cell = QVBoxLayout()
            cell.setSpacing(1)
            caption = QLabel(box.label)
            caption.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            caption.setStyleSheet(f"color:{MUTED}; font-size:10px;")
            cell.addWidget(caption)
            button = self._box(f"play.health.{i}", 30,
                               _MARK_FILL[mark] if mark else INPUT,
                               mark.value if mark else "")
            button.setToolTip(f"Wound penalty {box.label}")
            button.clicked.connect(
                lambda _c=False, index=i, n=len(play.health_boxes):
                (engineplay.cycle_mark(self._char(), index, n), self._refresh()))
            cell.addWidget(button)
            row.addLayout(cell)
        # ⚠ Add a stretch to EVERY row, not to the last row only. A QHBoxLayout of
        # fixed-size cells with no stretch at the end puts its free space BETWEEN the
        # cells. Thus the full rows spread across the panel, and the short last row stays
        # at the left. The box pitch then changes between the rows. ⚠ Only a character with
        # more than `_BOXES_PER_ROW` levels wraps. A short fixture cannot show this fault.
        for lay in rows:
            lay.addStretch(1)

        counts = {d: sum(1 for m in marks if m == d) for d in Damage}
        summary = QHBoxLayout()
        summary.addWidget(self._note(
            f"Marked: {counts[Damage.BASHING]}/  {counts[Damage.LETHAL]}x  "
            f"{counts[Damage.AGGRAVATED]}*"))
        worst = QLabel(f"Wound penalty: {viewmod.worst_penalty(play, marks)}")
        worst.setObjectName("play.woundPenalty")
        worst.setStyleSheet(f"font-weight:600; color:{self._accent()};")
        summary.addWidget(worst)
        summary.addStretch(1)
        body.addLayout(summary)

    def _fatigue_panel(self, play, cur) -> None:
        """Accumulated armour fatigue (p.332).

        Show this panel when the character wears armour, or when the character already has
        fatigue points. The points stay after the character removes the armour, because
        rest removes them. A character that never wears armour must not see a control that
        always shows zero.
        """
        if not (self._char().armor or cur.fatigue):
            return
        title = (f"ARMOUR FATIGUE  ({cur.fatigue} accumulated — -{cur.fatigue} to all "
                 f"actions)" if cur.fatigue else "ARMOUR FATIGUE  (none accumulated)")
        body = self._panel(self._tracker_lay, title)
        points = QSpinBox()
        points.setObjectName("play.fatigue")
        points.setRange(0, 99)
        points.setValue(cur.fatigue)
        # ⚠ Do NOT rebuild the full tab from a spin box. A redraw deletes the widget while
        # the user types, and it takes the focus. Calculate the pools only. The title of
        # the panel stays until the next `reload()`.
        points.valueChanged.connect(
            lambda v: (engineplay.set_fatigue(self._char(), v), self._fill_pools()))
        self._labelled(body, "Points", points)
        if play.fatigue_difficulties:
            body.addWidget(self._note("Fatigue roll difficulty: "
                                      + ", ".join(play.fatigue_difficulties)))
        body.addWidget(self._note(_FATIGUE_NOTE))

    def _motes_panel(self, play, cur) -> None:
        """The Essence pools.

        A merged pool is ONE track: "all of which is considered Peripheral" (p.41). Thus a
        Personal box stays at 0/0 and reads as broken. Put the rule in the heading. Do not
        draw an input that the user cannot use.
        """
        body = self._panel(
            self._tracker_lay,
            "ESSENCE — SINGLE POOL (motes spent — manual)" if play.single_pool
            else "ESSENCE (motes spent — manual)")
        # ⚠ Use `view.spent_motes`. Do not use `cur.*`. An attunement makes the maxima
        # smaller below a spend that was legal. Do not write the stored value back.
        spent_p, spent_pp = viewmod.spent_motes(play, cur)
        if not play.single_pool:
            self._mote_input(body, "Personal", "motes_personal_spent",
                             spent_p, play.personal_max)
        self._mote_input(body, "Peripheral" if not play.single_pool else "All motes",
                         "motes_peripheral_spent", spent_pp,
                         play.peripheral_max)
        self._committed_note(body, play)
        if play.free_max is not None:
            # Essence Awareness opens one third of the pool without a roll. The rest needs
            # a Willpower roll, and the table makes that roll. This app does not. ⚠ The
            # inputs go to the full maximum, because the user can spend those motes. Thus
            # this text is a note below the inputs. It is never a second limit.
            body.addWidget(self._note(
                f"{play.free_max} of these may be spent freely; the rest need a "
                f"Willpower roll (Essence Awareness)."))

    def _committed_note(self, lay, play) -> None:
        """The reason that the pool is small. `view.committed_note` supplies the text. The
        other three mote surfaces use the same text."""
        text = viewmod.committed_note(play)
        if not text:
            return
        note = QLabel(text)
        note.setObjectName("committedNote")
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{MUTED}; font-size:11px;")
        lay.addWidget(note)

    def _mote_input(self, lay, caption: str, field: str, value: int, cap: int) -> None:
        spin = QSpinBox()
        spin.setObjectName(f"play.{field}")
        spin.setRange(0, cap)
        spin.setValue(min(value, cap))
        available = QLabel("")
        available.setObjectName(f"play.{field}.available")
        available.setStyleSheet(f"color:{MUTED};")

        def sync(v: int) -> None:
            available.setText(f"{max(0, cap - v)} / {cap} available")

        # Change this readout only. ⚠ A full redraw deletes the spin box while the user
        # types. See `_fatigue_panel`.
        spin.valueChanged.connect(
            lambda v: (engineplay.set_motes(self._char(), field, v, cap), sync(v)))
        sync(spin.value())
        row = QHBoxLayout()
        label = QLabel(f"{caption} spent")
        label.setStyleSheet(f"color:{MUTED};")
        label.setMinimumWidth(90)
        row.addWidget(label)
        row.addWidget(spin)
        row.addWidget(available)
        row.addStretch(1)
        lay.addLayout(row)

    def _dot_track(self, body, field: str, filled: int, cap: int) -> None:
        """A plain click-to-set track (temporary Willpower, Limit, Clarity)."""
        row = None
        for i in range(cap):
            if i % _BOXES_PER_ROW == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                body.addLayout(row)
            button = self._box(f"play.{field}.{i}", 20,
                               self._accent() if i < filled else INPUT)
            button.clicked.connect(
                lambda _c=False, clicked=i + 1:
                (engineplay.set_count(self._char(), field, clicked, cap),
                 self._refresh()))
            row.addWidget(button)
        if row is not None:
            row.addStretch(1)

    def _willpower_panel(self, play, cur) -> None:
        body = self._panel(
            self._tracker_lay,
            f"TEMPORARY WILLPOWER  ({play.willpower_max - cur.willpower_spent} / "
            f"{play.willpower_max} available)")
        self._dot_track(body, "willpower_spent", cur.willpower_spent,
                        play.willpower_max)

    def _clarity_panel(self, cur) -> None:
        """Clarity, for the splats that have it instead of Limit.

        Alchemicals took no part in the Great Curse and have no Limit at all (p.69).
        Only the TEMPORARY half is a counter — the permanent half is derived from
        Essence and installed Charms, so it is shown read-only above the track.
        """
        ruleset, char = self._ruleset, self._char()
        cl = derive.clarity(ruleset, char)
        body = self._panel(self._tracker_lay,
                           f"CLARITY  ({cl.total} / {derive.CLARITY_MAX}  ·  "
                           f"{cl.permanent} permanent + {cl.temporary} temporary)")
        body.addWidget(self._note(
            "Permanent (derived): " + ", ".join(f"{label} +{dots}"
                                                for label, dots in cl.sources)
            if cl.sources else
            "No permanent Clarity — Essence 5 or below, and no Charm installed that "
            "grants it."))
        body.addWidget(self._note("Temporary (click to set):"))
        self._dot_track(body, "clarity_temporary", cur.clarity_temporary,
                        derive.CLARITY_MAX)
        if cl.capped:
            body.addWidget(self._note(
                f"Permanent + temporary exceeds {derive.CLARITY_MAX}; the total is "
                f"capped (p.69).", color=_AMBER))
        band = QLabel(f"{cl.band}: {cl.effects}")
        band.setWordWrap(True)
        band.setStyleSheet(f"color:{self._accent()}; font-size:11px;")
        body.addWidget(band)
        body.addWidget(self._note("Clarity never breaks or resets at 10, unlike Limit "
                                  "(p.70)."))

    def _limit_panel(self, cur) -> None:
        """Limit — or Paradox, which is the same 0-10 track under a Sidereal name
        (p.253), carried on `ExaltDefinition.limit_label` rather than being a second
        mechanic."""
        ruleset, char = self._ruleset, self._char()
        lim = derive.limit_label(ruleset, char)
        # Greater Curse lowers the maximum, so Limit Break arrives sooner — the track
        # is drawn to the derived maximum, never a hardcoded 10.
        lim_max = derive.limit_max(ruleset, char)
        broken = f"  —  {lim.upper()} BREAK" if cur.limit >= lim_max else ""
        body = self._panel(self._tracker_lay,
                           f"{lim.upper()}  ({cur.limit} / {lim_max}){broken}")
        self._dot_track(body, "limit", cur.limit, lim_max)
        if lim_max < merits.LIMIT_MAX:
            # There are two causes, and the Storyteller must know which one applies. A Flaw
            # made the track shorter, or permanent Resonance uses part of it. Permanent
            # Resonance subtracts from the maximum. It is not a second rating (human's
            # ruling).
            why = []
            if char.limit_permanent:
                why.append(f"{char.limit_permanent} permanent")
            curse = merits.LIMIT_MAX - lim_max - char.limit_permanent
            if curse > 0:
                why.append(f"{curse} by a Flaw")
            body.addWidget(self._note(
                f"Maximum {lim} reduced from {merits.LIMIT_MAX} "
                f"({', '.join(why)}).", color=_AMBER))
        # Death's Taint gives the Abyssal Curse a permanent counterpart, "cumulative
        # with temporary Resonance". Shown only where held.
        perm_cap = derive.permanent_limit_cap(ruleset, char)
        if perm_cap:
            # Make this control READ-ONLY. Permanent Resonance is a permanent trait, not
            # play state. The XP ledger adds and removes it. Thus the change has an audit
            # record, as decision 0006 requires. The tracker shows the value because it
            # adds to the temporary half, and the Storyteller needs the total.
            body.addWidget(self._note(
                f"Permanent {lim}: {char.limit_permanent} / {perm_cap} (capped at "
                f"Essence). It occupies {char.limit_permanent} of the "
                f"{merits.LIMIT_MAX}, so the track above runs to {lim_max}. Gain or "
                f"shed it on the Traits tab, not here."))

    def _luck_panel(self) -> None:
        """The luck pools. They exist because the Lucky and Unlucky Merits exist. ⚠ To
        spend one is a reroll (decision 0009), and this app does not reroll. These controls
        are counters."""
        luck, bad_luck = derive.luck_pools(self._ruleset, self._char())
        if not (luck or bad_luck):
            return
        body = self._panel(self._tracker_lay, "LUCK")
        if luck:
            body.addWidget(QLabel(f"Luck pool: {luck}"))
        if bad_luck:
            body.addWidget(QLabel(f"Bad luck pool (Storyteller): {bad_luck}"))
        body.addWidget(self._note("Refreshes at the end of each story. Spending luck is "
                                  "a reroll, which this build does not model."))

    # ------------------------------------------------------------------ #
    # the dice pools (decision 0016)
    # ------------------------------------------------------------------ #

    def _pool_row(self, lay, row) -> None:
        """One roll line: the total heading the name, and the arithmetic underneath.

        ⚠ The `compact` breakdown is NOT decoration. A column of totals with no terms is
        the authoritative-looking surface that decision 0008 refused. Decision 0016
        narrowed 0008 on the condition that every pool lists its terms. Use this one
        function, thus the preset list and the custom block always agree.

        ⚠ **Put both labels DIRECTLY into the QVBoxLayout of the caller. Never put them in
        a nested QHBoxLayout.** A QLabel that wraps calculates its height with
        `heightForWidth`, and QHBoxLayout does not use that value from its children. Thus
        each row in the list draws on top of the row below it.

        `row.note` is printed text, and it can be a full paragraph. Show it as a TOOLTIP.
        Sixty rows with a paragraph each are difficult to read, and the user reads this
        list quickly.
        """
        head = QLabel(f'<b><span style="color:'
                      f'{_AMBER if row.below_one else self._accent()}">{row.total}'
                      f'</span></b>&nbsp;&nbsp;{escape(row.name)}')
        head.setWordWrap(True)
        breakdown = self._note(row.compact)
        breakdown.setContentsMargins(20, 0, 0, 4)
        if row.note:
            head.setToolTip(row.note)
            breakdown.setToolTip(row.note)
        lay.addWidget(head)
        lay.addWidget(breakdown)

    # ------------------------------------------------------------------ #
    # the dumb roller (decision 0019)
    # ------------------------------------------------------------------ #

    def _build_roller(self) -> None:
        """The roller. Build it ONCE. It has a dice count, a label that the user writes,
        two switches, a button, and the session transcript below them.

        ⚠ Read decision 0019 before you change this, and read its no-wire rule first. What
        is ABSENT keeps the roller inside the boundary of decision 0008: no roll to select,
        no difficulty field, no stunt field, no odds, and no label that the app writes. A
        Roll button on a pool row, or a label that a pool row fills in, restores what 0009
        prevents. ⚠ NO TEST FAILS ON THAT CHANGE. Thus it is on the click-through list.

        ⚠ Clear `self._log_lay` only. The controls stay. Thus a roll cannot delete the
        button below the pointer of the user.
        """
        body = self._panel(self._roller_lay, "DICE ROLLER")
        self._roller_head = body.itemAt(0).widget()

        controls = QHBoxLayout()
        self._roll_count = QSpinBox()
        self._roll_count.setObjectName("play.roller.count")
        self._roll_count.setRange(0, dice.MAX_DICE)
        self._roll_count.setValue(self._roller_state["count"])
        self._roll_count.valueChanged.connect(
            lambda v: self._roller_state.update(count=v))
        controls.addWidget(QLabel("Dice"))
        controls.addWidget(self._roll_count)
        self._roll_target = QSpinBox()
        self._roll_target.setObjectName("play.roller.target")
        self._roll_target.setRange(2, 10)
        self._roll_target.setValue(self._roller_state["target_number"])
        self._roll_target.valueChanged.connect(
            lambda v: self._roller_state.update(target_number=v))
        controls.addWidget(QLabel("Target"))
        controls.addWidget(self._roll_target)
        # Free text, and the ONLY thing that names a roll. See the docstring.
        self._roll_label = QLineEdit()
        self._roll_label.setObjectName("play.roller.label")
        self._roll_label.setPlaceholderText("Label (yours) — e.g. attack on the bandit")
        self._roll_label.textChanged.connect(
            lambda t: self._roller_state.update(label=t))
        self._roll_label.returnPressed.connect(self._do_roll)
        controls.addWidget(self._roll_label, 1)
        self._roll_btn = QPushButton("Roll")
        self._roll_btn.setObjectName("play.roller.roll")
        self._roll_btn.clicked.connect(self._do_roll)
        controls.addWidget(self._roll_btn)
        body.addLayout(controls)

        switches = QHBoxLayout()
        # Both switches start ON. The printed rules are general, and each exception belongs
        # to one effect. Thus the user changes these switches on the instruction of the
        # Storyteller. ⚠ The app never determines which roll this is.
        self._roll_doubles = QCheckBox("10s count double")
        self._roll_doubles.setObjectName("play.roller.doubles")
        self._roll_doubles.setChecked(self._roller_state["doubles_tens"])
        self._roll_doubles.toggled.connect(
            lambda on: self._roller_state.update(doubles_tens=on))
        switches.addWidget(self._roll_doubles)
        self._roll_botch = QCheckBox("Can botch")
        self._roll_botch.setObjectName("play.roller.botch")
        self._roll_botch.setChecked(self._roller_state["can_botch"])
        self._roll_botch.toggled.connect(
            lambda on: self._roller_state.update(can_botch=on))
        switches.addWidget(self._roll_botch)
        switches.addStretch(1)
        body.addLayout(switches)

        body.addWidget(self._note(viewmod.ROLLER_CAVEAT))

        # ---- the transcript, newest line above the fold ------------------ #
        # ⚠ Build the button of the fold and its container ONCE. Refill their CONTENTS
        # only. Thus a change to the fold is a `setVisible` call, and never a rebuild. A
        # rebuild here deletes the button below the pointer. `_build_roller` avoids the
        # same fault for the Roll button.
        self._log_lay = QVBoxLayout()
        self._log_lay.setSpacing(2)
        body.addLayout(self._log_lay)
        self._older_btn = QPushButton()
        self._older_btn.setObjectName("play.roller.older")
        self._older_btn.setFlat(True)
        self._older_btn.setStyleSheet(f"text-align:left; color:{MUTED};")
        self._older_btn.clicked.connect(self._toggle_older)
        self._older_btn.hide()
        body.addWidget(self._older_btn)
        self._older_box = QWidget()
        self._older_lay = QVBoxLayout(self._older_box)
        self._older_lay.setContentsMargins(0, 0, 0, 0)
        self._older_lay.setSpacing(2)
        self._older_box.hide()
        body.addWidget(self._older_box)
        self._log_note = self._note(
            "This session only — rolls are not saved to the character.")
        self._log_note.hide()
        body.addWidget(self._log_note)

    def _sync_roller_controls(self) -> None:
        """Write `_roller_state` back onto the controls. One case changes that state
        without the controls: a switch to a different character resets the roller."""
        self._roll_count.setValue(self._roller_state["count"])
        self._roll_target.setValue(self._roller_state["target_number"])
        self._roll_label.clear()
        self._roll_doubles.setChecked(self._roller_state["doubles_tens"])
        self._roll_botch.setChecked(self._roller_state["can_botch"])

    def _do_roll(self) -> None:
        viewmod.roll_dice(self._roller_state)
        self._fill_roll_log()

    def _toggle_older(self) -> None:
        """Open or close the fold. Change the visibility ONLY. ⚠ A rebuild here deletes the
        button that the user clicks. See `_build_roller`."""
        self._roller_state["log_open"] = not self._roller_state["log_open"]
        self._sync_older()

    def _sync_older(self) -> None:
        """Point the fold's caption and its container at `log_open`."""
        older = len(self._roller_state["log"]) - 1
        open_ = self._roller_state["log_open"]
        self._older_btn.setText(
            ("▾  " if open_ else "▸  ") + viewmod.previous_rolls_label(max(0, older)))
        self._older_btn.setVisible(older > 0)
        self._older_box.setVisible(open_ and older > 0)

    def _fill_roll_log(self) -> None:
        """Paint the transcript again. ⚠ Never paint the panel again. The pointer of the
        user is on its Roll button. The newest line goes above the fold, and the other
        lines go in it. Thus a long session cannot push the controls off the panel."""
        clear_layout(self._log_lay)
        clear_layout(self._older_lay)
        newest, older = viewmod.roll_log_split(self._roller_state)
        self._log_note.setVisible(newest is not None)
        if newest is not None:
            self._roll_entry(self._log_lay, newest)
        for entry in older:
            self._roll_entry(self._older_lay, entry)
        self._sync_older()

    def _roll_entry(self, lay, entry) -> None:
        """One transcript line. It shows the outcome, the label of the user, the faces, and
        the switches of that roll.

        ⚠ Put every label DIRECTLY into the QVBoxLayout, as `_pool_row` does. A QLabel that
        wraps inside a nested QHBoxLayout draws over the line below it.
        """
        colour = _AMBER if entry.botch else self._accent()
        faces = " ".join(
            f'<span style="color:{_FACE_COLOR.get(face.kind, MUTED)}">'
            f'{"<b>" if face.kind in ("double", "one") else ""}{face.value}'
            f'{"</b>" if face.kind in ("double", "one") else ""}</span>'
            for face in entry.faces)
        head = QLabel(f'<b><span style="color:{colour}">{escape(entry.outcome)}'
                      f'</span></b>'
                      + (f'&nbsp;&nbsp;{escape(entry.label)}' if entry.label else ""))
        head.setWordWrap(True)
        lay.addWidget(head)
        if faces:
            dice_line = QLabel(faces)
            dice_line.setWordWrap(True)
            dice_line.setContentsMargins(20, 0, 0, 0)
            lay.addWidget(dice_line)
        detail = self._note(entry.detail)
        detail.setContentsMargins(20, 0, 0, 4)
        lay.addWidget(detail)

    def _set_pool(self, key: str, value) -> None:
        self._pool_state[key] = value
        self._refresh()

    def _fill_pools(self) -> None:
        """The right-hand column: the shared controls, every roll the catalogue knows
        with its own arithmetic, and the standing exclusions.

        Use a LIST, not a picker. The user reads the list for the row that they need. The
        user does not operate a dropdown during a turn.
        """
        clear_layout(self._pools_lay)
        if not self._pool_state:
            return
        ruleset, char = self._ruleset, self._char()
        state = self._pool_state
        sidebar = viewmod.build_pool_sidebar(
            ruleset, char, weapon_index=state["weapon"], arrow_index=state["arrow"],
            include_mobility=state["mobility"], include_wound=state["wound"],
            include_fatigue=state["fatigue"])
        # ⚠ `state` stays after the weapon list that it indexes changes. A delete on the
        # Gear tab gives a new number to each weapon. `view.clamp_pool_selection` holds
        # that rule.
        viewmod.clamp_pool_selection(state, sidebar)

        self._initiative_panel(state)

        body = self._panel(self._pools_lay, "DICE POOLS")
        body.setSpacing(2)
        self._pool_controls(body, sidebar, state)
        for category, rows in sidebar.groups:
            heading = QLabel(category.upper())
            heading.setStyleSheet(
                f"font-weight:700; letter-spacing:1px; font-size:11px; "
                f"color:{self._accent()}; margin-top:6px;")
            body.addWidget(heading)
            for row in rows:
                self._pool_row(body, row)
        if sidebar.any_below_one:
            # Do not limit this value. The book gives a floor to the range penalties only
            # (p.229). A general floor is not a printed rule. Show a note instead.
            body.addWidget(self._note(
                "Rows in amber have been taken below one die by the penalties. The core "
                "floors range penalties at 1 die and prints no general rule, so that is "
                "the Storyteller's call.", color=_AMBER))
        # ---- the standing caveat ---------------------------------------- #
        # ⚠ Do NOT make this block collapsible, and do NOT let the user dismiss it. This
        # block is the condition on which decision 0016 narrowed 0008. See the module
        # docstring.
        caveat = QLabel("These are BASE pools. They do not include:")
        caveat.setStyleSheet("font-weight:600; font-size:11px; margin-top:6px;")
        body.addWidget(caveat)
        for line in sidebar.excludes:
            body.addWidget(self._note(f"·  {line}"))
        # ⚠ The second clause states the no-wire rule of decision 0019 to the user. No row
        # here rolls itself, and the roller cannot know the source of a number. A "Roll"
        # button on a pool row is the defect that 0019 prevents.
        body.addWidget(self._note("Nothing is resolved here, and no row rolls "
                                  "itself — the roller takes a number you type."))
        self._pools_lay.addStretch(1)

    def _initiative_panel(self, state) -> None:
        """The initiative rating (core p.227). It reads the weapon that the "Attack with"
        control of the pool column names.

        ⚠ Give this rating its OWN panel, above DICE POOLS and outside it. A rating among
        the pool rows reads as a dice count, and the roller is on the same tab. The user
        then rolls nine dice for a number that needs ONE d10. Rebuild this panel with the
        pools, because it depends on the same weapon selection.
        """
        iv = viewmod.build_initiative(self._ruleset, self._char(),
                                      weapon_index=state["weapon"])
        body = self._panel(self._pools_lay, "INITIATIVE  ·  A RATING, NOT A POOL")
        head = QLabel(f'<b><span style="color:{self._accent()}; font-size:16px;">'
                      f'{iv.total}</span></b>&nbsp;&nbsp;'
                      f'{escape(iv.weapon or "Unarmed")}')
        head.setObjectName("play.initiative")
        head.setWordWrap(True)
        body.addWidget(head)
        breakdown = self._note(iv.compact)
        breakdown.setContentsMargins(20, 0, 0, 2)
        body.addWidget(breakdown)
        body.addWidget(self._note(iv.turn_note))
        body.addWidget(self._note(iv.tie_break))
        # This is the same condition that decisions 0016 and 0008 put on the pool list. A
        # surface that shows a total must also show what the total omits.
        excluded = QLabel("Not included:")
        excluded.setStyleSheet("font-weight:600; font-size:11px; margin-top:4px;")
        body.addWidget(excluded)
        for line in iv.excludes:
            body.addWidget(self._note(f"·  {line}"))

    def _pool_controls(self, body, sidebar, state) -> None:
        if sidebar.weapons:
            # Label this control "Attack with", not "Weapon". The Gear tab has a control
            # named Weapon. ⚠ A test harness and a user cannot tell two controls with the
            # same label apart.
            combo = QComboBox()
            combo.setObjectName("play.weapon")
            combo.addItem("— unarmed —", None)
            for index, name in sidebar.weapons:
                combo.addItem(name, index)
            combo.setCurrentIndex(max(0, combo.findData(state["weapon"])))
            combo.currentIndexChanged.connect(
                lambda _i: self._set_pool("weapon", combo.currentData()))
            self._labelled(body, "Attack with", combo)
        else:
            # ⚠ This `else` belongs to `sidebar.weapons`. Keep it there. Below the arrow
            # controls, it attaches to `arrow_note`. An armed character with no arrow
            # ready, which is the usual case, then reads that they own no weapon.
            body.addWidget(self._note("No weapon owned — the attack rows are unarmed."))
        if sidebar.arrows:
            # Show this control for a weapon that fires arrows only. Keep it SEPARATE from
            # "Attack with". The bow supplies the roll, and the arrow supplies the hit.
            arrows = QComboBox()
            arrows.setObjectName("play.arrow")
            arrows.addItem("— none nocked —", None)
            for index, name in sidebar.arrows:
                arrows.addItem(name, index)
            arrows.setCurrentIndex(max(0, arrows.findData(state["arrow"])))
            arrows.currentIndexChanged.connect(
                lambda _i: self._set_pool("arrow", arrows.currentData()))
            self._labelled(body, "Nocked arrow", arrows)
        if sidebar.arrow_note:
            # This is reference text. Put it with the controls, not in a pool row. Thus it
            # cannot read as a term in the total. ⚠ An arrow adds no dice. Core p.330 gives
            # an arrow a base damage and a soak clause, and no accuracy. This program
            # derives no damage (decision 0008).
            note = self._note(sidebar.arrow_note)
            note.setObjectName("play.arrowNote")
            body.addWidget(note)
            body.addWidget(self._note(
                "Damage only — an arrow adds no dice to the attack pool."))

        for key, caption in (
                ("wound", f"Wound penalty ({sidebar.wound_label})"
                    if sidebar.wound_label and sidebar.wound_label != "Incapacitated"
                    else ""),
                ("fatigue", f"Fatigue (-{sidebar.fatigue_points})"
                    if sidebar.fatigue_points else ""),
                ("mobility", f"Armour mobility ({', '.join(sidebar.mobility_lines)})"
                    if sidebar.mobility_lines else "")):
            if not caption:
                continue
            check = QCheckBox(caption)
            check.setObjectName(f"play.include.{key}")
            check.setChecked(state[key])
            check.toggled.connect(lambda on, k=key: self._set_pool(k, on))
            body.addWidget(check)
        if sidebar.wound_label == "Incapacitated":
            body.addWidget(self._note(
                "Deepest mark is Incapacitated — that level carries no dice penalty of "
                "its own; whether the character acts at all is the Storyteller's call.",
                color=_AMBER))

    def _custom_pool_panel(self) -> None:
        """The Attribute + Ability pool of the user. This is a builder, not data.

        The catalogue holds the rolls that the corebook names. The other 1E rolls are
        "roll Attribute + Ability" for the current action, and no book prints a list of
        them (see `pools.custom_roll`).

        Put this panel in the TRACKER column, not with the roll list. The list is long and
        the tracker is short. Thus this panel fills the space below the tracker. It shares
        `_pool_state` with the roll list. Thus the penalty switches of the sidebar also
        control these rows.
        """
        ruleset, char = self._ruleset, self._char()
        state = self._pool_state
        body = self._panel(self._tracker_lay,
                           "DICE POOL  ·  YOUR OWN ATTRIBUTE + ABILITY")
        attributes, abilities = viewmod.pool_trait_options()
        row = QHBoxLayout()
        for key, options, name in (("custom_attribute", attributes, "play.custom.attribute"),
                                   ("custom_ability", abilities, "play.custom.ability")):
            combo = QComboBox()
            combo.setObjectName(name)
            for value, label in options.items():
                combo.addItem(label, value)
            combo.setCurrentIndex(max(0, combo.findData(state[key])))
            combo.currentIndexChanged.connect(
                lambda _i, k=key, c=combo: self._set_pool(k, c.currentData()))
            row.addWidget(combo)
        row.addStretch(1)
        body.addLayout(row)
        if viewmod.pool_mobility_lines(ruleset, char):
            # The optional clause on p.332 is a decision of the Storyteller. Thus this is a
            # control. The app does not select a value. See `view.build_custom_pool`.
            agility = QCheckBox("Agility or balance (armour mobility applies)")
            agility.setObjectName("play.custom.agility")
            agility.setChecked(state["custom_agility"])
            agility.toggled.connect(lambda on: self._set_pool("custom_agility", on))
            body.addWidget(agility)
        for pool in viewmod.build_custom_pool(
                ruleset, char, AttributeName(state["custom_attribute"]),
                AbilityName(state["custom_ability"]),
                agility_based=state["custom_agility"],
                include_mobility=state["mobility"], include_wound=state["wound"],
                include_fatigue=state["fatigue"]):
            self._pool_row(body, pool)
        body.addWidget(self._note(
            "The wound, fatigue and mobility switches beside the roll list govern these "
            "rows too. Same caveats: a BASE pool, no Charms, no stunts, nothing rolled."))

    # ------------------------------------------------------------------ #
    # the toolbar actions
    # ------------------------------------------------------------------ #

    def _clear_damage(self) -> None:
        engineplay.clear_damage(self._char())
        self._refresh()

    def _clear_motes(self) -> None:
        """Reset the spent-mote fields to full.

        ⚠ Reset the MOTES ONLY. `engine.play.clear_motes` holds this rule. Willpower,
        health and Limit each have their own recovery rule. A "clear everything" button
        makes the tracker decide a recovery rule.
        """
        engineplay.clear_motes(self._char())
        self._refresh()
        self._notify("Motes spent cleared.", "info")
