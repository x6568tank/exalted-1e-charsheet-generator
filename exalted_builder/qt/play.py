"""exalted_builder/qt/play.py — the Play tab: the in-play tracker.

Input: a RuleSet and the shared context's Character. Output: a toolbar of scene
actions over two panelled columns — the tracker (health, armour fatigue, motes,
temporary Willpower, Limit/Clarity, luck, the custom dice pool) on the left, and the
dice-pool list on the right. Mechanism: every capacity comes from
`view.build_play_view` / `view.build_pool_sidebar`, every mutation from
`engine.play`; a click on a box rebuilds both columns, because a health mark moves the
wound penalty and the wound penalty is a term in every pool.

⚠ **This tab is the ONE stated exception to the collection layout** (human,
2026-08-22). Everywhere else a Qt tab is a table with a detail pane; Play is a live
TRACKER with nothing to select — you click a health box, you glance at a mote count
mid-roll — so a detail pane would hide the numbers the surface exists to show. It gets
a **toolbar over panels** instead. An exception that is written down is not drift; a
second unwritten one is.

⚠ **A DUMB tracker, and it must stay one.** No auto mote-accounting, no
damage-wrapping, no auto-healing — see `engine/play.py`, which owns that rule and
decision 0006's isolation with it. Nothing here feeds back into chargen, the XP audit
or a permanent derivation.

⚠ The pool rows must keep showing their `compact` breakdown and the exclusions block
must stay put — that presentation is what decision 0016 accepted in narrowing 0008, not
decoration. Read 0016 before changing the right-hand column.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from exalted_builder.engine import derive, merits, play as engineplay
from exalted_builder.models.character import Damage, PlayState
from exalted_builder.models.rules import AbilityName, AttributeName
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .layout import clear_layout
from .theme import CARD, INPUT, MUTED, accent as accent_light
from .trackers import MARK_FILL as _MARK_FILL, box as _tracker_box

# Health tracks run to a dozen boxes and more with Ox-Body. Qt has no flex-wrap, so
# the row wraps by construction.
_BOXES_PER_ROW = 10

_AMBER = "#d9a441"                   # the "your call, Storyteller" note colour

_FATIGUE_NOTE = ("Each failed Stamina + Endurance roll against the armour's fatigue "
                 "value adds a point; each dissipates after eight hours of rest out of "
                 "the armour (p.332). Both are the Storyteller's call — this counter is "
                 "manual, like Limit.")


class PlayPage(QWidget):
    """The tab widget. `reload()` re-derives every capacity for the character in ctx
    and redraws both columns; `notify` surfaces transient messages."""

    def __init__(self, ruleset, ctx, *, notify=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        # ⚠ Created ONCE, here, and never inside a rebuild. The columns are redrawn on
        # every health click, and selections owned by the redrawn widgets would reset
        # the player's chosen weapon on exactly the click that makes them want the
        # pools. Same reasoning as `ui/play.new_pool_state`, which owns the shape.
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
        self._pools_lay, pools = self._column()
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
        """The dice-pool column's selections, or {} when no roll catalogue shipped.
        Defaults chosen so the custom block shows a real number the moment it renders."""
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

    def _refresh(self) -> None:
        """A play-state change. BOTH columns, always: a health mark or a fatigue point
        is a term in every pool row on the right, and the custom-pool block on the left
        reads the same toggles as the sidebar."""
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
        """One clickable tracker box — `qt/trackers.py` owns the drawing, because the
        party cards and the adversary roster draw the same box and a Storyteller must
        not have to learn two damage trackers."""
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
        # ⚠ Read through `char.play or PlayState()`, never `engineplay.play_state`:
        # merely LOOKING at the tab must not write a PlayState onto a character who has
        # never been played, or a freshly-made sheet saves dirty.
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
        for i, box in enumerate(play.health_boxes):
            if i % _BOXES_PER_ROW == 0:
                row = QHBoxLayout()
                row.setSpacing(4)
                body.addLayout(row)
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
        if row is not None:
            row.addStretch(1)

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

        Shown only where it can matter: armour is worn, or points are already on the
        clock — they outlive taking the armour off, since they dissipate with rest and
        not with undressing. A character who never wears armour should not carry a
        permanently-zero control.
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
        # ⚠ The whole tab is NOT rebuilt from a spin box: a redraw deletes the widget
        # mid-keystroke and takes the focus with it. Only the pools re-derive, and the
        # panel's own title is left until the next `reload()`.
        points.valueChanged.connect(
            lambda v: (engineplay.set_fatigue(self._char(), v), self._fill_pools()))
        self._labelled(body, "Points", points)
        if play.fatigue_difficulties:
            body.addWidget(self._note("Fatigue roll difficulty: "
                                      + ", ".join(play.fatigue_difficulties)))
        body.addWidget(self._note(_FATIGUE_NOTE))

    def _motes_panel(self, play, cur) -> None:
        """The Essence pools.

        A merged pool is ONE track — "all of which is considered Peripheral" (p.41) —
        so the Personal box would sit at a permanent 0/0 and read as broken. The rule
        goes in the heading instead of rendering a dead input.
        """
        body = self._panel(
            self._tracker_lay,
            "ESSENCE — SINGLE POOL (motes spent — manual)" if play.single_pool
            else "ESSENCE (motes spent — manual)")
        if not play.single_pool:
            self._mote_input(body, "Personal", "motes_personal_spent",
                             cur.motes_personal_spent, play.personal_max)
        self._mote_input(body, "Peripheral" if not play.single_pool else "All motes",
                         "motes_peripheral_spent", cur.motes_peripheral_spent,
                         play.peripheral_max)
        if play.free_max is not None:
            # Essence Awareness unlocks only a third of the pool freely; the rest needs
            # a Willpower roll the table makes, not this app. The inputs still run to
            # the full maximum — those motes are spendable — so this is a note under
            # them, never a second cap.
            body.addWidget(self._note(
                f"{play.free_max} of these may be spent freely; the rest need a "
                f"Willpower roll (Essence Awareness)."))

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

        # Only its own readout moves — a full redraw would delete the spin box the
        # player is still typing in. See `_fatigue_panel`.
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
            # Two different causes, and the ST needs to know which: a Flaw shortened the
            # track outright, or permanent Resonance is occupying part of it (ruled
            # 2026-07-31 — permanent is headroom off the maximum, not a rating riding
            # alongside).
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
            # READ-ONLY here. Permanent Resonance is a permanent trait, not play-state:
            # it is gained and shed through the XP ledger so the change has an audit
            # trail, exactly as decision 0006 requires of a curse. The tracker shows it
            # because it is cumulative with the temporary half and the ST needs the
            # total at the table.
            body.addWidget(self._note(
                f"Permanent {lim}: {char.limit_permanent} / {perm_cap} (capped at "
                f"Essence). It occupies {char.limit_permanent} of the "
                f"{merits.LIMIT_MAX}, so the track above runs to {lim_max}. Gain or "
                f"shed it on the Traits tab, not here."))

    def _luck_panel(self) -> None:
        """Luck pools exist only because the Lucky / Unlucky Merits do. Spending them
        is rerolling (decision 0009) and stays out — these are counters."""
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

        ⚠ The `compact` breakdown is NOT optional decoration. A column of bare totals is
        precisely the "looks authoritative" surface decision 0008 rejected, and 0016
        narrowed 0008 only on the promise that every pool shown is itemised. One
        function so the preset list and the custom block cannot drift apart on it.

        ⚠ **Both labels go STRAIGHT into the caller's QVBoxLayout, never into a nested
        QHBoxLayout.** A word-wrapped QLabel sizes itself through `heightForWidth`, and
        QHBoxLayout does not propagate that from its children — the first build put the
        total in a column beside a nested QVBoxLayout and every row in the list drew on
        top of the one below it. The aligned total column was worth less than a legible
        list.

        `row.note` is a printed rider, sometimes a whole paragraph. It rides as a
        TOOLTIP: sixty rows each carrying one is a wall of text, and the thing this list
        exists for is scanning.
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

    def _set_pool(self, key: str, value) -> None:
        self._pool_state[key] = value
        self._refresh()

    def _fill_pools(self) -> None:
        """The right-hand column: the shared controls, every roll the catalogue knows
        with its own arithmetic, and the standing exclusions.

        A LIST, not a picker — a player scans for the row they need instead of driving a
        dropdown mid-turn.
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
        # ⚠ `state` outlives the weapon list it indexes — a weapon deleted on the Gear
        # tab renumbers it. `view.clamp_pool_selection` owns that rule.
        viewmod.clamp_pool_selection(state, sidebar)

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
            # Not clamped: the book floors range penalties and nothing else (p.229), so
            # a general floor would be invented. Say what happened instead.
            body.addWidget(self._note(
                "Rows in amber have been taken below one die by the penalties. The core "
                "floors range penalties at 1 die and prints no general rule, so that is "
                "the Storyteller's call.", color=_AMBER))
        # ---- the standing caveat ---------------------------------------- #
        # NOT collapsible and NOT dismissible: this is the whole reason decision 0016
        # could narrow 0008. See the module docstring.
        caveat = QLabel("These are BASE pools. They do not include:")
        caveat.setStyleSheet("font-weight:600; font-size:11px; margin-top:6px;")
        body.addWidget(caveat)
        for line in sidebar.excludes:
            body.addWidget(self._note(f"·  {line}"))
        body.addWidget(self._note("No dice are rolled here, and nothing is resolved."))
        self._pools_lay.addStretch(1)

    def _pool_controls(self, body, sidebar, state) -> None:
        if sidebar.weapons:
            # Labelled "Attack with" rather than "Weapon": the Gear tab already owns a
            # control called Weapon, and two identically labelled controls are
            # indistinguishable to a test harness as well as to a player.
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
            # ⚠ This `else` belongs to `sidebar.weapons` and must stay attached to it.
            # Moved below the arrow controls it re-parents onto `arrow_note`, and an
            # armed character with nothing nocked — the ordinary case — is then told
            # they own no weapon.
            body.addWidget(self._note("No weapon owned — the attack rows are unarmed."))
        if sidebar.arrows:
            # Only for a weapon that fires them, and deliberately a SEPARATE control
            # from "Attack with": the bow is what you roll, the arrow is what lands.
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
            # Reference text, sitting with the controls rather than inside a pool row so
            # it cannot read as a term in the arithmetic. An arrow contributes no dice —
            # core p.330 gives arrows a base damage and a soak clause and no accuracy —
            # and this build derives no damage at all (decision 0008).
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
        """The player's own Attribute + Ability pool — a builder, not data.

        The catalogue covers the rolls the corebook spells out by name; the rest of 1e
        is "roll Attribute + Ability" for whatever the table is doing, and there is no
        printed roster of those to author (see `pools.custom_roll`).

        It sits in the TRACKER column, not with the roll list: the list is long and the
        tracker beside it is short, so this fills the space under the tracker rather
        than adding to the taller side. It shares `_pool_state` with the roll list,
        which is why the sidebar's penalty switches govern these rows too.
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
            # p.332's discretionary clause is the Storyteller's call, so it is a control
            # rather than a guess — see `view.build_custom_pool`.
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

        ⚠ MOTES ONLY — `engine.play.clear_motes` owns the reason. Willpower, health and
        Limit recover on their own terms, so a "clear everything" button would be the
        tracker deciding a recovery rule.
        """
        engineplay.clear_motes(self._char())
        self._refresh()
        self._notify("Motes spent cleared.", "info")
