"""exalted_builder/qt/editor.py — the Edit tab: chargen and XP on one trait surface.

Input: a RuleSet and a Character (from the shared context). Output: a scrollable form
of dot-track trait rows (Attributes, Abilities, Crafts, Virtues, Essence, Willpower),
the identity/structural controls, and a sticky side column — Live Validation + Bonus
Points while chargen is open, the XP card + ledger after the lock. Mechanism:
retained-mode widgets built once and mutated; a dot click sets the rating (chargen) or
hands the click to engine.advancement (post-lock, decision 0013); the side column
re-derives from view.build_sheet_view + validate on every change.

This is a re-architecture, not a transliteration (docs/plans/qt-port.md, "What does
NOT translate"): the NiceGUI editor rebuilds the page per click; this rebuilds only
what a change moves (a dot click touches its row + the side column; a structural
change — Exalt type, caste, origin, favoured picks — rebuilds the body).

Deferred from this milestone (still on the webapp): Training Camp & Calling, the
Astrological Colleges, Specialties editing, Permanent Resonance/Limit, the Virtue
Flaw, bonus health levels and the Downtime calculator. A note in the body says so.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSpinBox,
    QSplitter, QVBoxLayout, QWidget,
)

from exalted_builder.engine import advancement, costs, derive, elder, merits, validate
from exalted_builder.models.character import (
    AbilityName, AttributeName, Character, CraftRating, VirtueName,
)
from exalted_builder.models.rules import RuleSet
from .theme import CARD, accent as accent_light

from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

# XP-log targets whose change moves OTHER rows' ceilings, so buying one has to rebuild
# the whole body rather than its own dot row. ⚠ Omit a target here and its dependants
# keep their stale pips until the tab is re-entered. Essence is the only member: past
# 5 it IS the ceiling on every Ability and Attribute (engine.elder).
BODY_REBUILD_TARGETS = {"essence"}


class _Pip(QLabel):
    """One clickable pip of a dot track. Emits its 1-based pip index on click."""

    clicked = Signal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self._index = index
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(self._index)


class DotTrack(QWidget):
    """A clickable dot-track rating control (decision 0013: the buy control on both
    sides of the lock). `get`/`setv` read and write the rating; pre-lock a click is a
    free setter, post-lock `buy` (when a `target` is named) prices and validates it.
    Clicking the current top pip steps it back down. `refresh()` re-reads `get()` and
    rebuilds the pips — always showing enough to step a too-high value down."""

    def __init__(self, get, setv, lo, hi, *, accent, target=None, detail="",
                 buy=None, on_change=None, parent=None):
        super().__init__(parent)
        self._get, self._setv = get, setv
        self._lo, self._hi = lo, hi
        self._accent = accent
        self._target, self._detail = target, detail
        self._buy = buy
        self._on_change = on_change
        self._pips: list[_Pip] = []
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(3)
        self.refresh()

    def refresh(self):
        value = self._get()
        top = max(self._hi, value)
        for pip in self._pips:
            pip.hide()
            pip.setParent(None)
            pip.deleteLater()
        self._pips.clear()
        for i in range(1, top + 1):
            pip = _Pip(i, self)
            pip.setText("●" if i <= value else "○")
            pip.setStyleSheet("color:%s;" % self._accent if i <= value else "color:#aaaaaa;")
            pip.clicked.connect(self._click)
            self._layout.addWidget(pip)
            self._pips.append(pip)

    def _click(self, i: int) -> None:
        current = self._get()
        wanted = max(self._lo, min(self._hi, i - 1 if i == current else i))
        # Post-lock, the click is a purchase, a refund or a curse — never a write.
        # `buy` returns True when it has taken responsibility for it.
        if self._buy is not None and self._target is not None:
            if self._buy(self._target, current, wanted, self.refresh, self._detail):
                return
        self._setv(wanted)
        self.refresh()
        if self._on_change is not None:
            self._on_change()


class _FilterCombo(QComboBox):
    """An editable combo that opens its list on click — type to filter (the
    completer), click to see everything. Plain QComboBox only opens the list from its
    arrow; clicking the text area just focuses it."""

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self.view().isVisible():
            self.showPopup()


class _FavoredPicker(QWidget):
    """Type-to-filter multi-pick with chips — the web app's use-chips select.

    An editable combo holding every option, whose completer filters the labels as you
    type; clicking opens the full list. Picking (dropdown, completer or Enter) adds the
    option as a chip, capped at `cap`. `on_change` fires with the current picks whenever
    a chip is added or removed. Disabled when frozen (chargen choices are fixed at the
    lock)."""

    def __init__(self, options: dict, current: list, cap: int, accent: str,
                 on_change, *, frozen: bool = False, parent=None):
        super().__init__(parent)
        self._options = options
        self._picked = list(current)
        self._cap = cap
        self._accent = accent
        self._on_change = on_change
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.combo = _FilterCombo()
        self.combo.setEditable(True)
        for key, label in options.items():
            self.combo.addItem(label, key)
        self.combo.setCurrentText("")          # blank so the placeholder shows
        completer = QCompleter(sorted(options.values()), self.combo)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.combo.setCompleter(completer)
        self.combo.lineEdit().setPlaceholderText(f"Type a name… (pick {cap})")
        self.combo.lineEdit().returnPressed.connect(self._add_current)
        # Both paths: activated(int) on a dropdown pick, textActivated(str) from the
        # completer. `_add_current` is idempotent, so double-fires are safe.
        self.combo.activated[int].connect(lambda _i: self._add_current())
        self.combo.textActivated.connect(lambda _s: self._add_current())
        self.combo.setEnabled(not frozen)
        lay.addWidget(self.combo)
        self._chips_row = QHBoxLayout()
        self._chips_row.setContentsMargins(0, 0, 0, 0)
        self._chips_row.setSpacing(4)
        self._chips_row.addStretch(1)
        lay.addLayout(self._chips_row)
        self._render_chips()

    def _add_current(self):
        text = self.combo.currentText().strip()
        self.combo.setCurrentText("")
        key = next((k for k, v in self._options.items() if v.lower() == text.lower()), None)
        if key is None or key in self._picked or len(self._picked) >= self._cap:
            return
        self._picked.append(key)
        self._render_chips()
        self._on_change(list(self._picked))

    def _render_chips(self):
        while self._chips_row.count():
            item = self._chips_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        for key in self._picked:
            chip = QFrame()
            chip.setStyleSheet(f"QFrame {{ background:{self._accent}; border-radius:8px; }}")
            h = QHBoxLayout(chip)
            h.setContentsMargins(8, 2, 6, 2)
            h.setSpacing(4)
            label = QLabel(self._options.get(key, key))
            label.setStyleSheet("color:#1a1a1a;")
            h.addWidget(label)
            remove = QPushButton("✕")
            remove.setStyleSheet("background:transparent; color:#1a1a1a; border:none; padding:0;")
            remove.clicked.connect(lambda _, k=key: self._remove(k))
            h.addWidget(remove)
            self._chips_row.addWidget(chip)
        self._chips_row.addStretch(1)

    def _remove(self, key):
        if key in self._picked:
            self._picked.remove(key)
            self._render_chips()
            self._on_change(list(self._picked))


class _Panel(QFrame):
    """A titled card — the editor's section container. node_bg fill with an
    accent-tinted border, like the web app's card tint."""

    def __init__(self, title: str, pal, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:none; border-radius:6px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(4)
        heading = QLabel(title)
        heading.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(heading)
        self._lay = lay

    def body(self) -> QVBoxLayout:
        return self._lay


class EditPage(QWidget):
    """The Edit tab. See the module docstring; `reload()` rebuilds the body + side
    column from the character in ctx, `_changed()` re-derives only the side column and
    the registered tallies. `notify` is a (text, kind) callback for transient
    messages; `on_theme_change` fires after the Exalt type changes."""

    def __init__(self, ruleset, ctx, *, notify=None, on_theme_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_theme_change = on_theme_change
        self._tallies: list[callable] = []

        self._body_container = QWidget()
        self._body_lay = QVBoxLayout(self._body_container)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body_container)

        self._side = QWidget()
        self._side.setFixedWidth(320)
        self._side_lay = QVBoxLayout(self._side)
        self._side_lay.setContentsMargins(0, 0, 0, 0)
        self._side_lay.setSpacing(8)

        split = QSplitter()
        split.addWidget(scroll)
        split.addWidget(self._side)
        split.setSizes([900, 320])
        outer = QVBoxLayout(self)
        outer.addWidget(split)
        self.reload()

    def _char(self) -> Character:
        return self._ctx["char"]

    # ------------------------------------------------------------------ #
    # panels
    # ------------------------------------------------------------------ #

    def _panel(self, title: str, parent_lay=None) -> QVBoxLayout:
        pal = theme.palette(self._char().exalt_type)
        card = _Panel(title, pal)
        (parent_lay if parent_lay is not None else self._body_lay).addWidget(card)
        return card.body()

    def _row(self, parent_lay) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        parent_lay.addLayout(row)
        return row

    def _vsep(self) -> QFrame:
        """A 1px vertical rule between columns (the web app's `border-left`)."""
        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet("background:#55535a;")
        return line

    def _combo(self, options: dict, value, *, frozen: bool, on_change) -> QComboBox:
        combo = QComboBox()
        for key, label in options.items():
            combo.addItem(label, key)
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.setEnabled(not frozen)
        combo.currentIndexChanged.connect(lambda _: on_change(combo.currentData()))
        return combo

    def _trait_row(self, lay, mark: str, label: str, accent: str, track: DotTrack,
                   extra: QWidget | None = None):
        row = self._row(lay)
        m = QLabel(mark)
        m.setFixedWidth(12)
        m.setStyleSheet(f"color:{accent};")
        row.addWidget(m)
        name = QLabel(label)
        row.addWidget(name, 1)
        if extra is not None:
            row.addWidget(extra)
        row.addWidget(track)

    # ------------------------------------------------------------------ #
    # side column
    # ------------------------------------------------------------------ #

    def _clear_lay(self, lay: QVBoxLayout) -> None:
        """Remove every widget/layout from `lay` and detach it NOW.

        ⚠ `deleteLater()` alone is deferred to the event loop: `reload()` runs
        synchronously several times at startup (the constructor, the first tab-change
        signal, `_sync_tabs`), and a build whose children are merely pending-delete
        keeps painting at stale geometry on top of the next build — every element
        stacked with its own ghost border. `setParent(None)` detaches it from
        rendering immediately; `deleteLater()` still frees the C++ object."""
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
            elif item.layout() is not None:
                self._clear_lay(item.layout())

    def _issues(self, lay, view, ok_text: str) -> None:
        """The findings into `lay` (a card's layout) — status line then each issue."""
        errors = [i for i in view.issues if i.severity == "error"]
        status = ok_text if not errors else f"✗ {len(errors)} error(s)"
        label = QLabel(status)
        label.setStyleSheet("font-weight:bold; color:%s;" % ("#15803d" if not errors else "#b91c1c"))
        lay.addWidget(label)
        for issue in view.issues:
            if issue.code in ("bonus-points", "xp-summary"):
                continue
            color = {"error": "#b91c1c", "warning": "#b45309"}.get(issue.severity, "#a8a5a0")
            l = QLabel(f"• {issue.message}")
            l.setStyleSheet(f"color:{color};")
            l.setWordWrap(True)
            lay.addWidget(l)

    def _card(self) -> QVBoxLayout:
        card = QFrame()
        card.setStyleSheet(f"QFrame {{ background:{CARD}; border:none; "
                           f"border-radius:6px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(10, 6, 10, 8)
        lay.setSpacing(2)
        self._side_lay.addWidget(card)
        return lay

    def _card_title(self, lay, title: str) -> None:
        accent = theme.palette(self._char().exalt_type).accent
        t = QLabel(title)
        t.setStyleSheet(f"font-weight:bold; color:{accent};")
        lay.addWidget(t)

    def _build_side(self) -> None:
        self._clear_lay(self._side_lay)
        char = self._char()
        pal = theme.palette(char.exalt_type)
        if char.chargen_locked:
            self._xp_card()
            self._xp_log_card()
            view = viewmod.build_sheet_view(self._ruleset, char)
            if any(i.code != "xp-summary" for i in view.issues):
                lay = self._card()
                self._card_title(lay, "Validation")
                self._issues(lay, view, "✓ Legal")
        else:
            lay = self._card()
            self._card_title(lay, "Live Validation")
            view = viewmod.build_sheet_view(self._ruleset, char)
            bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
            if bp:
                b = QLabel(bp)
                b.setStyleSheet("font-weight:600; color:%s;" % accent_light(pal))
                lay.addWidget(b)
            row = self._row(lay)
            row.addWidget(QLabel(f"Willpower {view.willpower}"))
            row.addWidget(QLabel(view.essence_pool_label()))
            soak = QLabel(f"Soak  B{view.soak.bashing} / L{view.soak.lethal} / A{view.soak.aggravated}")
            lay.addWidget(soak)
            self._issues(lay, view, "✓ Legal chargen")
            self._bp_card()
        # The trailing stretch absorbs the splitter's extra height, so the cards keep
        # their natural height — otherwise the labels stretch to fill and each single
        # line of text floats in ~55px of empty space (the "Live Validation spaced
        # out" report).
        self._side_lay.addStretch(1)

    def _bp_card(self) -> None:
        bd = validate.bonus_point_breakdown(self._ruleset, self._char())
        lay = self._card()
        self._card_title(lay, "Bonus Points")
        color = "#b91c1c" if bd.over_budget else "#15803d"
        total = QLabel(f"{bd.total} / {bd.available} spent")
        total.setStyleSheet(f"font-weight:600; color:{color};")
        lay.addWidget(total)
        for line in bd.lines:
            row = self._row(lay)
            domain = QLabel(line.domain)
            if not line.points:
                domain.setStyleSheet("color:#a8a5a0;")
            row.addWidget(domain, 1)
            pts = QLabel(str(line.points))
            if not line.points:
                pts.setStyleSheet("color:#a8a5a0;")
            row.addWidget(pts)

    def _xp_card(self) -> None:
        char = self._char()
        pal = theme.palette(char.exalt_type)
        lay = self._card()
        self._card_title(lay, "Experience")
        available = advancement.xp_available(char)
        row = self._row(lay)
        av = QLabel(str(available))
        av.setStyleSheet("font-weight:bold; font-size:18pt; color:%s;" % ("#15803d" if available >= 0 else "#b91c1c"))
        row.addWidget(av)
        row.addWidget(QLabel("XP available"))
        earned = QLabel(f"earned {char.xp_earned} · spent {advancement.xp_spent(char)}")
        earned.setStyleSheet("color:#a8a5a0;")
        lay.addWidget(earned)
        # Adjust XP
        row = self._row(lay)
        amount = QSpinBox()
        amount.setRange(-999, 9999)
        amount.setValue(5)
        row.addWidget(amount, 1)
        adjust = QPushButton("Adjust XP")
        adjust.setStyleSheet(f"background:{accent_light(pal)}; color:#1a1a1a; border:none; border-radius:4px; padding:4px 8px;")
        adjust.clicked.connect(lambda: self._do_add_xp(amount.value()))
        row.addWidget(adjust)
        # Downtime + undo
        row = self._row(lay)
        downtime = QPushButton("Downtime…")
        downtime.setToolTip("The p.259 calculator is not ported to the native app yet.")
        downtime.setEnabled(False)
        row.addWidget(downtime, 1)
        rows = viewmod.build_xp_log(self._ruleset, char)
        if rows:
            undo = QPushButton(f"Undo last: {rows[-1].label}")
            undo.clicked.connect(self._do_undo)
            lay.addWidget(undo)
        granted, remaining = validate.withheld_charm_credits(self._ruleset, char)
        if granted:
            note = QLabel(f"{remaining} of {granted} withheld Charm(s) in reserve — the next "
                          f"{remaining or 'no'} cost no XP.")
            note.setStyleSheet(f"color:{accent_light(pal)}; font-weight:600;")
            note.setWordWrap(True)
            lay.addWidget(note)

    def _xp_log_card(self) -> None:
        char = self._char()
        rows = viewmod.build_xp_log(self._ruleset, char)
        lay = self._card()
        self._card_title(lay, "Experience Ledger")
        if not rows:
            empty = QLabel("No XP spent yet.")
            empty.setStyleSheet("color:#a8a5a0;")
            lay.addWidget(empty)
        for r in rows:
            row = self._row(lay)
            row.addWidget(QLabel(r.label), 1)
            cost = QLabel(f"{r.cost} XP")
            cost.setStyleSheet("color:#a8a5a0;")
            row.addWidget(cost)

    def _do_add_xp(self, amount: int) -> None:
        advancement.add_xp(self._char(), amount)
        self._changed()

    def _do_undo(self) -> None:
        try:
            advancement.undo_last(self._ruleset, self._char())
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self.reload()

    # ------------------------------------------------------------------ #
    # post-lock buying (decision 0013)
    # ------------------------------------------------------------------ #

    def _buy(self, target: str, current: int, wanted: int, refresh, detail: str = "") -> bool:
        """Handle a post-lock dot click. Returns False pre-lock, so the track falls
        through to its ordinary free-setter behaviour."""
        if not self._char().chargen_locked:
            return False
        if wanted > current:
            try:
                advancement.raise_to(self._ruleset, self._char(), target, wanted, detail)
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
            else:
                self._refresh_after(target, refresh)
                self._changed()
            return True
        if wanted < current:
            self._downward_dialog(target, current, wanted, refresh, detail)
        return True

    def _refresh_after(self, target: str, refresh) -> None:
        """Redraw what the change actually moved. A dot click normally only has to
        redraw its own row; ESSENCE is the exception — it is the ceiling on every
        other track past 5, so the whole body has to rebuild. One or the other, never
        both: rebuilding the body replaces the very row `refresh` belongs to."""
        if target in BODY_REBUILD_TARGETS:
            self.reload()
        else:
            refresh()

    def _downward_dialog(self, target: str, current: int, wanted: int, refresh,
                         detail: str = "") -> None:
        """Ask which downward event this is — taking XP back and suffering a curse
        both move the same dots and differ in price, log and floor. Refund is capped
        by `refundable_depth` (undo is LIFO across the whole log); a curse reaches
        chargen dots, so its only limit is the trait's own floor — probed on a
        throwaway copy."""
        char = self._char()
        dots_down = current - wanted
        depth = advancement.refundable_depth(char, target, detail)
        can_refund = depth >= dots_down
        try:
            advancement.lower_to(char.model_copy(deep=True), target, wanted, "probe", detail)
            can_reduce = True
        except advancement.AdvancementError:
            can_reduce = False
        if not can_refund and not can_reduce:
            self._notify("Nothing to take back here — no recent purchase of this trait, "
                         "and it is already at its minimum.", "warning")
            refresh()
            return
        refund_xp = sum(e.cost for e in char.xp_log[len(char.xp_log) - dots_down:]) \
            if can_refund else 0
        noun = "dot" if dots_down == 1 else "dots"

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Lower by {dots_down} {noun}")
        lay = QVBoxLayout(dialog)
        intro = QLabel("Taking experience back and suffering a permanent loss are "
                       "different events. Which is this?")
        intro.setWordWrap(True)
        lay.addWidget(intro)

        def _go(action) -> None:
            try:
                action()
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
                return
            dialog.accept()
            self._refresh_after(target, refresh)
            self._changed()

        refund = QPushButton(f"Undo purchase — refund {refund_xp} XP")
        refund.setEnabled(can_refund)
        refund.clicked.connect(lambda: _go(
            lambda: advancement.refund_to(self._ruleset, char, target, wanted, detail)))
        lay.addWidget(refund)
        if not can_refund:
            note = QLabel(f"Only {depth} recent purchase(s) of this trait can be refunded — "
                          f"undo is last-in-first-out, so anything bought since must go first.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#a8a5a0; font-style:italic;")
            lay.addWidget(note)
        reason = QLineEdit()
        reason.setPlaceholderText("reason (e.g. a curse, a Charm's permanent cost)")
        lay.addWidget(reason)
        curse = QPushButton("Permanent loss — free, refunds no XP")
        curse.setEnabled(can_reduce)
        curse.clicked.connect(lambda: _go(
            lambda: advancement.lower_to(self._ruleset, char, target, wanted,
                                         reason.text().strip(), detail)))
        lay.addWidget(curse)
        if not can_reduce:
            note = QLabel("A permanent loss is logged and undoable, reaches chargen "
                          "dots, and gives back no experience.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#a8a5a0;")
            lay.addWidget(note)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        lay.addWidget(cancel)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # structural mutators
    # ------------------------------------------------------------------ #

    def _reset_camp_for_origin(self) -> None:
        camp, calling, granted = validate.default_camp_and_calling(self._ruleset, self._char())
        char = self._char()
        char.camp, char.calling = camp, calling
        char.granted_charms = granted

    def _drop_orphaned_elemental_powers(self) -> None:
        char = self._char()
        legal = validate.legal_elemental_powers(self._ruleset, char)
        if char.elemental_powers != legal:
            n = len(char.elemental_powers)
            char.elemental_powers = legal
            self._notify(f"Cleared {n} Elemental Power{'s' if n != 1 else ''} — they belong "
                         "to the Elemental heritage (PG p.68).", "warning")

    def set_exalt_type(self, value: str) -> None:
        char = self._char()
        char.exalt_type = value
        valid = [cd.id for cd in self._ruleset.castes.values() if cd.exalt_type == value]
        if char.caste not in valid:
            char.caste = valid[0] if valid else ""
        origins = viewmod._origin_options(self._ruleset, char)
        char.origin = next(iter(origins)) if origins else ""
        nb = self._ruleset.budgets_for(value, char.origin, char.upbringing)
        if char.essence_rating < nb.essence_start:
            char.essence_rating = nb.essence_start
        elif nb.essence_start_cap and char.essence_rating > nb.essence_start_cap:
            char.essence_rating = nb.essence_start
        self._reset_camp_for_origin()
        self._drop_orphaned_elemental_powers()
        self.reload()
        if self._on_theme_change is not None:
            self._on_theme_change()

    def set_caste(self, value: str) -> None:
        char = self._char()
        char.caste = value
        origins = viewmod._origin_options(self._ruleset, char)
        if char.origin not in origins:
            char.origin = next(iter(origins)) if origins else ""
            char.upbringing = ""
            self._reset_camp_for_origin()
        self._drop_orphaned_elemental_powers()
        self.reload()

    def set_origin(self, value: str) -> None:
        char = self._char()
        char.origin = value
        char.upbringing = ""
        self._reset_camp_for_origin()
        self._drop_orphaned_elemental_powers()
        self.reload()

    def set_upbringing(self, value: str) -> None:
        self._char().upbringing = value
        self.reload()

    def set_favored(self, values: list) -> None:
        self._char().favored_abilities = list(values)
        self.reload()

    def set_favored_attributes(self, values: list) -> None:
        self._char().favored_attributes = list(values)
        self.reload()

    def add_craft(self) -> None:
        self._char().crafts.append(CraftRating(focus="", rating=1))
        self.reload()

    def remove_craft(self, idx: int) -> None:
        del self._char().crafts[idx]
        self.reload()

    def _do_trait(self, action) -> None:
        try:
            action()
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self.reload()

    def _lower_willpower(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Permanent Willpower loss")
        lay = QVBoxLayout(dialog)
        intro = QLabel("Free, refunds no XP, logged and undoable. To take back a "
                       "PURCHASE instead, use Undo in the Experience card.")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        reason = QLineEdit()
        reason.setPlaceholderText("reason (e.g. a curse)")
        lay.addWidget(reason)

        def _go() -> None:
            try:
                advancement.lower_willpower(self._char(), reason.text().strip(),
                                            ruleset=self._ruleset)
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
                return
            dialog.accept()
            self.reload()

        go = QPushButton("Lower by 1")
        go.clicked.connect(_go)
        lay.addWidget(go)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        lay.addWidget(cancel)
        dialog.exec()

    # ------------------------------------------------------------------ #
    # body
    # ------------------------------------------------------------------ #

    def _cap_for(self, mf_effects, a: AttributeName, b, attr_trait_cap) -> int:
        cap = mf_effects.attribute_caps.get(a.value, attr_trait_cap)
        origin_cap = b.attribute_caps.get(a.value)
        return min(cap, origin_cap) if origin_cap else cap

    def reload(self) -> None:
        """Rebuild the body + side column from the character in ctx. Called on
        structural changes (Exalt type, caste, origin, favoured picks), on load/new/
        lock/unlock, and on any change to a BODY_REBUILD_TARGET. Dot clicks use
        `_changed()` instead and do not rebuild the body."""
        self._clear_lay(self._body_lay)
        self._tallies.clear()
        char = self._char()
        pal = theme.palette(char.exalt_type)
        locked = char.chargen_locked
        ruleset = self._ruleset
        caste_def = ruleset.castes.get(char.caste)
        caste_abilities = set(caste_def.caste_abilities) if caste_def else set()
        caste_attributes = set(caste_def.caste_attributes) if caste_def else set()
        breed_bonus = (caste_def.breed_traits.attribute_bonuses
                       if caste_def and caste_def.breed_traits else {})
        cf_attr_mode = viewmod.uses_caste_favored_attributes(ruleset, char)
        favored_attrs = set(char.favored_attributes)
        b = validate.effective_budgets(ruleset, char)
        mf = merits.merits_and_flaws_calc(ruleset, char)
        essence_cap, _ = elder.essence_cap(ruleset, char)
        if mf.essence_cap_override is not None:
            essence_cap = mf.essence_cap_override
        attr_trait_cap = elder.trait_ceiling(char, ruleset, domain="attribute")
        abil_trait_cap = elder.trait_ceiling(char, ruleset, domain="ability")
        virtue_cap = (mf.virtue_cap if mf.virtue_cap is not None else merits.DOT_MAX)
        exalt_def = ruleset.exalt_for(char.exalt_type)
        caste_noun = exalt_def.caste_noun
        splat_has_castes = any(cd.exalt_type == char.exalt_type
                               for cd in ruleset.castes.values())

        def buy(target, current, wanted, refresh, detail=""):
            return self._buy(target, current, wanted, refresh, detail)

        def track(get, setv, lo, hi, target=None, detail=""):
            return DotTrack(get, setv, lo, hi, accent=accent_light(pal), target=target,
                            detail=detail, buy=buy, on_change=self._changed)

        def dot_row(row, label, get, setv, lo, hi, target=None, detail="",
                    extra=None, mark=""):
            t = track(get, setv, lo, hi, target=target, detail=detail)
            self._trait_row(row, mark, label, accent_light(pal), t, extra=extra)
            return t

        # ---- deferred-panels note (milestone scope) -------------------- #
        note = QLabel("Native Edit covers the trait surface. Training Camp & Calling, "
                      "the Colleges, Specialties, Permanent Resonance, the Virtue Flaw, "
                      "bonus health levels and Downtime still live on the webapp.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a8a5a0; font-size:9pt;")
        self._body_lay.addWidget(note)

        # ---- caste info (left card) + identity (right panel) ------------ #
        # Mirrors the web app's row: a fixed-width caste card on the left, the
        # Identity panel filling the rest. Keeps its place even for a splat with no
        # caste so the identity controls don't jump width between splats.
        id_row = QHBoxLayout()
        id_row.setSpacing(8)
        self._body_lay.addLayout(id_row)

        caste_card = QFrame()
        caste_card.setFixedWidth(280)
        caste_card.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:none; border-radius:6px; }}")
        caste_lay = QVBoxLayout(caste_card)
        caste_lay.setContentsMargins(10, 8, 10, 10)
        caste_lay.setSpacing(4)
        if caste_def:
            info = QLabel(f"{caste_def.label} {caste_noun}")
            info.setWordWrap(True)
            info.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
            caste_lay.addWidget(info)
            if caste_def.description:
                desc = QLabel(caste_def.description)
                desc.setWordWrap(True)
                desc.setStyleSheet("color:#a8a5a0;")
                caste_lay.addWidget(desc)
            if caste_def.caste_attributes:
                attr_line = QLabel(f"{caste_noun} Attributes: " + ", ".join(
                    _label(a.value) for a in caste_def.caste_attributes))
                attr_line.setWordWrap(True)
                attr_line.setStyleSheet("font-style:italic; color:#a8a5a0;")
                caste_lay.addWidget(attr_line)
            elif caste_def.caste_abilities:
                ab_line = QLabel(f"{caste_noun} Abilities: " + ", ".join(
                    _label(a.value) for a in caste_def.caste_abilities))
                ab_line.setWordWrap(True)
                ab_line.setStyleSheet("font-style:italic; color:#a8a5a0;")
                caste_lay.addWidget(ab_line)
            if caste_def.anima_powers:
                anima = QLabel("Anima Power")
                anima.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
                caste_lay.addWidget(anima)
                ap_text = QLabel(caste_def.anima_powers)
                ap_text.setWordWrap(True)
                ap_text.setStyleSheet("color:#a8a5a0;")
                caste_lay.addWidget(ap_text)
        elif splat_has_castes:
            caste_lay.addWidget(QLabel("Unknown caste"))
        else:
            splat = QLabel(exalt_def.label)
            splat.setWordWrap(True)
            splat.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
            caste_lay.addWidget(splat)
            caste_lay.addWidget(QLabel("Not one of the Chosen — no caste, no Charms, "
                                      "Essence 1."))
        caste_lay.addStretch(1)
        id_row.addWidget(caste_card)

        lay = self._panel("Identity", id_row)
        if locked:
            frozen_note = QLabel("Caste, Exalt type, origin and Favoured picks are fixed "
                                 "at the lock — they set the rates every later purchase "
                                 "is priced at.")
            frozen_note.setWordWrap(True)
            frozen_note.setStyleSheet("font-style:italic; color:#a8a5a0;")
            lay.addWidget(frozen_note)

        def identity_field(label, text, on_change, frozen=False):
            box = QHBoxLayout()
            box.addWidget(QLabel(label))
            edit = QLineEdit(text)
            edit.setEnabled(not (locked and frozen))
            edit.textChanged.connect(on_change)
            box.addWidget(edit, 1)
            lay.addLayout(box)
            return edit

        identity_field("Name", char.name, lambda t: (setattr(char, "name", t), self._changed()))
        identity_field("Concept", char.concept, lambda t: setattr(char, "concept", t))

        # exalt type
        box = QHBoxLayout()
        box.addWidget(QLabel("Exalt type"))
        exalt_opts = {ex.id: ex.label for ex in ruleset.exalts.values()}
        exalt_opts.setdefault(char.exalt_type, char.exalt_type)
        box.addWidget(self._combo(exalt_opts, char.exalt_type, frozen=locked,
                                  on_change=self.set_exalt_type), 1)
        lay.addLayout(box)
        # caste
        caste_opts = {cd.id: cd.label for cd in ruleset.castes.values()
                      if cd.exalt_type == char.exalt_type}
        if caste_opts:
            caste_opts.setdefault(char.caste, char.caste)
            box = QHBoxLayout()
            box.addWidget(QLabel(caste_noun))
            box.addWidget(self._combo(caste_opts, char.caste, frozen=locked,
                                      on_change=self.set_caste), 1)
            lay.addLayout(box)
        # origin / upbringing
        origins = viewmod._origin_options(ruleset, char)
        if origins:
            if char.origin and char.origin not in origins:
                origins = {**origins, char.origin: char.origin}
            box = QHBoxLayout()
            box.addWidget(QLabel("Origin"))
            box.addWidget(self._combo(origins, char.origin, frozen=locked,
                                      on_change=self.set_origin), 1)
            lay.addLayout(box)
            ups = viewmod.upbringing_options(char.exalt_type,
                                             char.origin or next(iter(origins)))
            if ups:
                box = QHBoxLayout()
                box.addWidget(QLabel("Upbringing"))
                value = char.upbringing if char.upbringing in ups else next(iter(ups))
                box.addWidget(self._combo(ups, value, frozen=locked,
                                          on_change=self.set_upbringing), 1)
                lay.addLayout(box)
        # nature
        box = QHBoxLayout()
        box.addWidget(QLabel("Nature"))
        nature = QComboBox()
        nature.setEditable(True)
        for n in ruleset.nature_catalog.values():
            nature.addItem(n.name)
        if char.nature and nature.findText(char.nature) < 0:
            nature.addItem(char.nature)
        nature.setCurrentText(char.nature or "")
        nature.setEnabled(not locked)
        nature.currentTextChanged.connect(lambda t: (setattr(char, "nature", t), self._changed()))
        box.addWidget(nature, 1)
        lay.addLayout(box)
        # anima
        identity_field("Anima", char.anima, lambda t: setattr(char, "anima", t))
        # favored abilities / attributes — type-to-filter pickers with chips.
        fav_n = validate.favored_ability_count(ruleset, char)
        if fav_n:
            label = QLabel(f"Favored abilities (pick {fav_n})")
            label.setContentsMargins(0, 4, 0, 2)       # clear of the combo below
            lay.addWidget(label)
            lay.addWidget(_FavoredPicker(
                {a: _label(a.value) for a in AbilityName},
                list(char.favored_abilities), fav_n, accent_light(pal),
                self.set_favored, frozen=locked))
        if cf_attr_mode:
            label = QLabel(f"Favored Attributes (pick {b.attribute_favored_count})")
            label.setContentsMargins(0, 4, 0, 2)
            lay.addWidget(label)
            lay.addWidget(_FavoredPicker(
                {a: _label(a.value) for a in AttributeName},
                list(char.favored_attributes), b.attribute_favored_count, accent_light(pal),
                self.set_favored_attributes, frozen=locked))

        # ---- attributes --------------------------------------------------- #
        ap = "/".join(str(p) for p in validate.effective_attribute_pools(ruleset, char))
        header = viewmod.attribute_budget_summary(ruleset, char) or f"prioritise {ap}"
        attr_lay = self._panel("Attributes" if locked else f"Attributes ({header})")
        # The three categories as side-by-side COLUMNS (Physical | Social | Mental),
        # mirroring the web app — not stacked full-width groups.
        cols = QHBoxLayout()
        cols.setSpacing(24)
        attr_lay.addLayout(cols)
        for i, (category, members) in enumerate(validate.ATTRIBUTE_CATEGORIES.items()):
            if i > 0:
                cols.addWidget(self._vsep())
            group = QVBoxLayout()
            spent_label = QLabel("")
            spent_label.setStyleSheet("font-weight:600; color:#a8a5a0;")

            def _spent_updater(label=spent_label, members=members, category=category):
                spent = sum(char.attributes[a] - min(1, self._cap_for(mf, a, b, attr_trait_cap))
                            for a in members)
                label.setText(f"{category} — {spent} spent")

            if not locked:
                _spent_updater()
                self._tallies.append(_spent_updater)
            group.addWidget(spent_label)
            for a in members:
                mark = "●" if a in caste_attributes else ("✦" if a in favored_attrs else "")
                extra = None
                breed = breed_bonus.get(a, 0)
                if breed:
                    extra = QLabel(f"+{breed} breed")
                    extra.setStyleSheet("color:#a8a5a0; font-style:italic;")
                row = QHBoxLayout()
                m = QLabel(mark)
                m.setFixedWidth(12)
                m.setStyleSheet(f"color:{accent_light(pal)};")
                row.addWidget(m)
                name = QLabel(_label(a.value))
                name.setMinimumWidth(80)
                row.addWidget(name, 1)
                if extra is not None:
                    row.addWidget(extra)
                cap = self._cap_for(mf, a, b, attr_trait_cap)
                lo = min(b.attribute_min or b.attribute_base, cap)
                t = track(lambda a=a: char.attributes[a],
                          lambda v, a=a: char.attributes.__setitem__(a, v),
                          lo, cap, target=f"attributes.{a.value}")
                row.addWidget(t)
                group.addLayout(row)
            cols.addLayout(group, 1)

        # ---- abilities ---------------------------------------------------- #
        ab_header = ("Abilities" if locked else
                     f"Abilities ({b.ability_dots} dots; ≥{b.ability_min_caste_favored} "
                     f"caste/favoured; ≤{b.ability_cap_pre_bp} each pre-bonus)")
        ab_lay = self._panel(ab_header)
        if not locked:
            tally = QLabel("")
            tally.setStyleSheet("font-weight:600;")

            def _ability_tally(label=tally):
                if b.ability_favored_dots:
                    spent, _bp = validate.two_pool_ability_accounting(
                        b, char, char.abilities, char.crafts)
                    total = b.ability_dots + b.ability_favored_dots
                else:
                    cap = b.ability_cap_pre_bp
                    spent = (sum(min(v, cap) for a, v in char.abilities.items()
                                 if a != AbilityName.CRAFT)
                             + sum(min(cr.rating, cap) for cr in char.crafts))
                    total = b.ability_dots
                over = spent > total
                label.setText(f"{spent} / {total} dots spent")
                label.setStyleSheet("font-weight:600; color:%s;" % ("#b91c1c" if over else accent_light(pal)))

            _ability_tally()
            self._tallies.append(_ability_tally)
            ab_lay.addWidget(tally)
        groups = viewmod.ability_group_defs(ruleset, char.exalt_type)
        calling_marks = viewmod.calling_ability_marks(ruleset, char)
        # Rows of three per-caste columns, mirroring the web app — not one stacked
        # group after another.
        for start in range(0, len(groups), 3):
            cols = QHBoxLayout()
            cols.setSpacing(24)
            ab_lay.addLayout(cols)
            for j, (group_label, abilities) in enumerate(groups[start:start + 3]):
                if j > 0:
                    cols.addWidget(self._vsep())
                group = QVBoxLayout()
                if group_label:
                    g = QLabel(group_label)
                    g.setStyleSheet(f"font-weight:600; color:{accent_light(pal)};")
                    group.addWidget(g)
                for a in abilities:
                    mark = "●" if a in caste_abilities else ("✦" if a in char.favored_abilities else "")
                    if a in calling_marks:
                        mark += "✧"
                    if a == AbilityName.CRAFT:
                        row = QHBoxLayout()
                        m = QLabel(mark)
                        m.setFixedWidth(12)
                        m.setStyleSheet(f"color:{accent_light(pal)};")
                        row.addWidget(m)
                        row.addWidget(QLabel("Craft"), 1)
                        row.addWidget(QLabel("↓ per-focus"))
                        group.addLayout(row)
                        continue
                    row = QHBoxLayout()
                    m = QLabel(mark)
                    m.setFixedWidth(12)
                    m.setStyleSheet(f"color:{accent_light(pal)};")
                    row.addWidget(m)
                    name = QLabel(_label(a.value))
                    name.setMinimumWidth(80)
                    row.addWidget(name, 1)
                    t = track(lambda a=a: char.abilities[a],
                              lambda v, a=a: char.abilities.__setitem__(a, v),
                              0, abil_trait_cap, target=f"abilities.{a.value}")
                    row.addWidget(t)
                    group.addLayout(row)
                cols.addLayout(group, 1)

        # ---- crafts ------------------------------------------------------- #
        craft_cf = AbilityName.CRAFT in caste_abilities or AbilityName.CRAFT in char.favored_abilities
        cf_tag = " · Caste/Favoured" if craft_cf else ""
        craft_lay = self._panel(f"Crafts (each focus a separate Ability{cf_tag})")
        for idx, cr in enumerate(char.crafts):
            row = QHBoxLayout()
            focus = QLineEdit(cr.focus)
            focus.setPlaceholderText("craft (e.g. Smithing)")
            focus.textChanged.connect(lambda t, cr=cr: (setattr(cr, "focus", t), self._changed()))
            row.addWidget(focus, 1)
            row.addWidget(track(lambda cr=cr: cr.rating, lambda v, cr=cr: setattr(cr, "rating", v),
                                0, abil_trait_cap, target="crafts", detail=cr.focus))
            remove = QPushButton("✕")
            remove.clicked.connect(lambda _, idx=idx: self.remove_craft(idx))
            row.addWidget(remove)
            craft_lay.addLayout(row)
        add_craft = QPushButton("+ Add craft")
        add_craft.clicked.connect(self.add_craft)
        craft_lay.addWidget(add_craft)

        # ---- virtues + essence + willpower -------------------------------- #
        ve_row = QHBoxLayout()
        ve_row.setSpacing(24)
        self._body_lay.addLayout(ve_row)
        virtues_lay = self._panel("Virtues" if locked else
                                  f"Virtues ({b.virtue_dots} dots; ≤{b.virtue_cap_pre_bp} pre-bonus)",
                                  ve_row)
        for v in VirtueName:
            row = QHBoxLayout()
            row.addWidget(QLabel(_label(v.value)))
            row.addWidget(track(lambda v=v: char.virtues[v],
                                lambda val, v=v: char.virtues.__setitem__(v, val),
                                1, virtue_cap, target=f"virtues.{v.value}"))
            virtues_lay.addLayout(row)
        ew_lay = self._panel("Essence & Willpower", ve_row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Essence"))
        row.addWidget(track(lambda: char.essence_rating,
                            lambda v: setattr(char, "essence_rating", v),
                            1, essence_cap if locked else min(elder.DOT_MAX, essence_cap),
                            target="essence"))
        ew_lay.addLayout(row)
        if locked:
            wp = derive.willpower(char, ruleset)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Willpower {wp}"))
            plus = QPushButton(f"+1 · {costs.willpower_step(ruleset, char, wp)} XP")
            plus.clicked.connect(lambda: self._do_trait(
                lambda: advancement.raise_willpower(ruleset, char)))
            row.addWidget(plus)
            down = QPushButton("↓")
            down.setToolTip("Permanent loss (a curse) — free, refunds no XP")
            down.clicked.connect(self._lower_willpower)
            row.addWidget(down)
            ew_lay.addLayout(row)
        else:
            row = QHBoxLayout()
            row.addWidget(QLabel("Willpower purchased"))
            spin = QSpinBox()
            spin.setRange(0, 10)
            spin.setValue(char.willpower_purchased)
            spin.valueChanged.connect(lambda v: (setattr(char, "willpower_purchased", v), self._changed()))
            row.addWidget(spin, 1)
            ew_lay.addLayout(row)

        # ---- charms/spells — read-only here ------------------------------ #
        _slots = viewmod.charm_slot_budget(ruleset, char)
        if _slots is not None:
            charm_hdr = (f"Charm Slots {_slots.installed}/{_slots.general + _slots.dedicated} "
                         f"(G {_slots.general} · D {_slots.dedicated})")
        else:
            charm_hdr = f"Charms ({validate.charm_pick_count(ruleset, char)})"
        view = viewmod.build_sheet_view(ruleset, char)
        ep = f" & Elemental Powers ({len(view.elemental_powers)})" if view.elemental_powers else ""
        charms_lay = self._panel(f"{charm_hdr} & Spells ({len(char.spells)}){ep} — edit via the picker")
        for c in view.charms:
            charms_lay.addWidget(QLabel(f"{c.name} · {c.category}"))
        for s in view.spells:
            charms_lay.addWidget(QLabel(f"{s.name} · {s.circle}"))
        for e in view.elemental_powers:
            charms_lay.addWidget(QLabel(f"{e.name} · Elemental Powers"))

        self._body_lay.addStretch(1)
        self._build_side()

    def _changed(self) -> None:
        """A change that only moves the readouts — dot clicks, name edits, Adjust XP.
        Rebuilds the side column and re-runs the registered tallies; the body's dot
        tracks have already refreshed themselves."""
        for tally in self._tallies:
            tally()
        self._build_side()


def _label(value: str) -> str:
    return value.replace("_", " ").title()
