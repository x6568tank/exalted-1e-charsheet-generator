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

Deferred from this milestone (still on the webapp): Training Camp & Calling and the
Downtime calculator. A note in the body says so.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from exalted_builder.engine import (advancement, costs, derive, elder,
                                    health_actions, merits, validate)
from exalted_builder.models.character import (
    AbilityName, AttributeName, Character, CollegeRating, CraftRating, Specialty,
    VirtueFlaw, VirtueName,
)
from exalted_builder.models.rules import RuleSet
from .theme import CARD, INPUT, accent as accent_light

from .layout import clear_layout
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


# ⚠ A nested layout whose spacing is unset (-1) INHERITS its parent's, so the 24px gap
# set between the COLUMNS became the gap between the ROWS inside each column — the
# attribute rows sat 41px apart against the Virtues' 21px, which reads as the card
# trying to fill itself vertically (human, 2026-08-22). Set it explicitly.
_ROW_SPACING = 4

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
        if key not in self._picked:
            return
        # The clicked ✕ has focus; deleting it lets Qt's focus handling scroll the
        # surrounding scroll area to whatever focusable widget it picks next (a
        # QSpinBox deep in the form), yanking the view to the bottom. Park focus on
        # the combo — part of this picker, already on screen — before deleting.
        self.combo.setFocus()
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
        # A card takes its content's natural height and never expands vertically —
        # otherwise a card beside a taller sibling (the caste card next to the
        # Identity panel) is stretched to match, and the extra height is spread
        # across its labels. The body's trailing stretch absorbs leftover space.
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(4)
        heading = QLabel(title)
        heading.setStyleSheet(f"font-weight:bold; color:{accent_light(pal)};")
        lay.addWidget(heading)
        self._lay = lay

    def body(self) -> QVBoxLayout:
        return self._lay


class _EditorPage(QWidget):
    """Shared machinery for the Identity and Traits pages: a retained-mode scrollable
    body, the dot-track buying / downward-dialog plumbing, scroll-hold and layout
    clearing. `reload()` rebuilds the body from the character in ctx; a subclass's
    `_build_body()` supplies the content. `notify` surfaces transient messages;
    `on_change` fires whenever the character changed so the shell can refresh its
    readout/status (the old side column now lives in the shell's popover)."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        self._tallies: list[callable] = []
        self._body_container = QWidget()
        self._body_lay = QVBoxLayout(self._body_container)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body_container)
        self._body_scroll = scroll
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.reload()

    def reload(self) -> None:
        """Rebuild the body from the character in ctx, then ping the shell. Pin the
        body's height across the rebuild (clearing the layout collapses the content
        under the scrollbar, clamping the saved value), then re-apply the scroll
        position for a short settle window (see _hold_scroll).

        ⚠ The `on_change` ping lives HERE, not at the call sites. A full reload is what
        every structural change does — Exalt type, caste, origin, favoured picks, a
        craft row, `_do_trait`'s purchases, `_lower_willpower` — and all ten sites
        moved the bonus-point spend or the validation errors while leaving the shell's
        readout bar showing the previous answer. One ping in the wrapper is a mechanism;
        ten remembered call sites is the same house bug waiting for an eleventh.
        Re-entry is not a risk: the shell's `_refresh` writes labels and never reloads a
        page."""
        saved = self._body_scroll.verticalScrollBar().value()
        self._body_container.setMinimumHeight(self._body_container.height())
        self._clear_lay(self._body_lay)
        self._tallies.clear()
        self._build_body()
        self._body_lay.addStretch(1)
        self._body_container.setMinimumHeight(0)
        self._hold_scroll(saved)
        if self._on_change is not None:
            self._on_change()

    def _build_body(self) -> None:
        raise NotImplementedError

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
        """A select over `options` {key: label}, calling `on_change(key)` with the key
        the caller supplied.

        ⚠ **The key is looked up by INDEX, never read back out of the widget.** Qt
        stores item data as a QVariant, and a `str`-valued Enum comes back out of
        `currentData()` as a plain `str` — so a handler doing `setattr(row, "ability",
        …)` writes "dodge" onto a field typed `AbilityName`, and the model has no
        `validate_assignment` to catch it. Nothing fails at the write; it fails later
        at the first `.value` on what is no longer an enum. Indexing the original dict
        hands back the identical object for every key type."""
        combo = QComboBox()
        keys = list(options)
        for key in keys:
            combo.addItem(options[key], key)
        if value in keys:
            combo.setCurrentIndex(keys.index(value))
        combo.setEnabled(not frozen)
        combo.currentIndexChanged.connect(
            lambda i: on_change(keys[i] if 0 <= i < len(keys) else None))
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

    def _clear_lay(self, lay) -> None:
        """Empty `lay`, detaching every descendant NOW. One line, because the shape is
        subtle enough that six hand-written copies produced a wrong one — see
        `qt/layout.py`, which owns both traps and the reason they matter."""
        clear_layout(lay)

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

    def add_college(self) -> None:
        """A fresh College row, defaulting to one of the character's own Maiden's house
        so it already counts toward the own-house minimum rather than starting in
        violation of it."""
        ruleset, char = self._ruleset, self._char()
        own = next((cid for cid, col in ruleset.colleges.items()
                    if col.house == char.caste), None)
        char.colleges.append(
            CollegeRating(college_id=own or next(iter(ruleset.colleges), ""), rating=1))
        self.reload()

    def remove_college(self, idx: int) -> None:
        del self._char().colleges[idx]
        self.reload()

    def add_spec(self) -> None:
        """A blank chargen row. The per-Ability cap is NOT enforced here — the row
        starts on Melee and the player retargets it, so blocking the ADD would block it
        on the wrong Ability. `validate.check_specialties` reports an over-capped
        Ability instead, which is also what covers a save that arrives over the cap."""
        self._char().specialties.append(
            Specialty(ability=AbilityName.MELEE, name="", rating=1))
        self.reload()

    def remove_spec(self, idx: int) -> None:
        del self._char().specialties[idx]
        self.reload()

    def set_virtue_flaw_virtue(self, virtue: VirtueName) -> None:
        """Set which Virtue is flawed, keeping any description already written.

        ⚠ Reloads rather than redrawing in place: the sample-Flaw dropdown beside this
        one is built from the flawed Virtue, so without the rebuild it keeps offering
        the OLD Virtue's Flaws — wrong exactly while it is being read."""
        char = self._char()
        desc = char.virtue_flaw.description if char.virtue_flaw else ""
        char.virtue_flaw = VirtueFlaw(virtue=virtue, description=desc)
        self.reload()

    def set_virtue_flaw_sample(self, flaw_id: str) -> None:
        """Copy a sample Flaw's printed text into the free-text description.

        A COPY, not a reference (decision 0007: ids for invariant content, inline
        copies for variable). The player is expected to edit the text — the book offers
        these as a guide to severity for Flaws of their own — so storing the id would
        make an edited Flaw claim to be the printed one."""
        flaw = self._ruleset.virtue_flaw_catalog.get(flaw_id or "")
        if flaw is None:
            return
        self.set_virtue_flaw_desc(flaw.description)
        self.reload()

    def set_virtue_flaw_desc(self, text: str) -> None:
        char = self._char()
        if char.virtue_flaw is None:
            char.virtue_flaw = VirtueFlaw(virtue=VirtueName.COMPASSION, description=text)
        else:
            char.virtue_flaw.description = text

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

    def _hold_scroll(self, saved: int) -> None:
        """Keep the body scrolled where it was across the rebuild just done.

        Belt-and-braces on top of the height pin above: the rebuild's relayout can
        still yank the scrollbar (a direct setValue, not just a range change, on the
        real display), so this re-applies the saved position on every range and value
        change for a short settle window, then releases so the user's own scrolling
        is free again. A prior hold is dropped first — reload() runs several times in
        a row at startup, and a stale hold must not resurrect an old position."""
        bar = self._body_scroll.verticalScrollBar()
        self._drop_scroll_hold()
        self._scroll_hold_saved = saved

        def restore(*_args) -> None:
            bar.setValue(min(saved, bar.maximum()))

        self._scroll_hold_restore = restore
        bar.rangeChanged.connect(restore)
        bar.valueChanged.connect(restore)
        bar.setValue(min(saved, bar.maximum()))

        def release() -> None:
            if self._scroll_hold_restore is restore:
                self._drop_scroll_hold()

        QTimer.singleShot(120, release)

    def _drop_scroll_hold(self) -> None:
        hold = getattr(self, "_scroll_hold_restore", None)
        self._scroll_hold_restore = None
        if hold is None:
            return
        try:
            bar = self._body_scroll.verticalScrollBar()
            bar.rangeChanged.disconnect(hold)
            bar.valueChanged.disconnect(hold)
        except (RuntimeError, TypeError):
            pass

    def _changed(self) -> None:
        """A change that only moves the readouts — dot clicks, name edits, Adjust XP.
        Re-runs the registered tallies (the body's dot tracks have already refreshed
        themselves) and pings the shell's readout/status via `on_change`."""
        for tally in self._tallies:
            tally()
        if self._on_change is not None:
            self._on_change()


class IdentityPage(_EditorPage):
    """The Identity tab: name/concept/anima, the structural selectors (Exalt type,
    caste, origin, upbringing, nature), the free-fill biography, and the caste-info
    block. Structural changes rebuild this page and re-theme the shell; the Traits
    page stays fresh via reload-on-show."""

    def __init__(self, ruleset, ctx, *, notify=None, on_theme_change=None,
                 on_change=None, parent=None):
        self._on_theme_change = on_theme_change
        super().__init__(ruleset, ctx, notify=notify, on_change=on_change, parent=parent)

    def _build_body(self) -> None:
        char = self._char()
        pal = theme.palette(char.exalt_type)
        locked = char.chargen_locked
        ruleset = self._ruleset
        accent = accent_light(pal)

        if locked:
            note = QLabel("Caste, Exalt type, origin and Favoured picks are fixed "
                          "at the lock — they set the rates every later purchase "
                          "is priced at.")
            note.setWordWrap(True)
            note.setStyleSheet("font-style:italic; color:#a8a5a0;")
            self._body_lay.addWidget(note)

        id_lay = self._panel("Identity")

        def field(label, text, on_change, frozen=False):
            box = QHBoxLayout()
            box.addWidget(QLabel(label))
            edit = QLineEdit(text)
            edit.setEnabled(not (locked and frozen))
            edit.textChanged.connect(on_change)
            box.addWidget(edit, 1)
            id_lay.addLayout(box)
            return edit

        field("Name", char.name, lambda t: (setattr(char, "name", t), self._changed()))
        field("Concept", char.concept, lambda t: setattr(char, "concept", t))

        # exalt type
        box = QHBoxLayout()
        box.addWidget(QLabel("Exalt type"))
        exalt_opts = {ex.id: ex.label for ex in ruleset.exalts.values()}
        exalt_opts.setdefault(char.exalt_type, char.exalt_type)
        box.addWidget(self._combo(exalt_opts, char.exalt_type, frozen=locked,
                                  on_change=self.set_exalt_type), 1)
        id_lay.addLayout(box)
        # caste
        caste_noun = ruleset.exalt_for(char.exalt_type).caste_noun
        caste_opts = {cd.id: cd.label for cd in ruleset.castes.values()
                      if cd.exalt_type == char.exalt_type}
        if caste_opts:
            caste_opts.setdefault(char.caste, char.caste)
            box = QHBoxLayout()
            box.addWidget(QLabel(caste_noun))
            box.addWidget(self._combo(caste_opts, char.caste, frozen=locked,
                                      on_change=self.set_caste), 1)
            id_lay.addLayout(box)
        # origin / upbringing
        origins = viewmod._origin_options(ruleset, char)
        if origins:
            if char.origin and char.origin not in origins:
                origins = {**origins, char.origin: char.origin}
            box = QHBoxLayout()
            box.addWidget(QLabel("Origin"))
            box.addWidget(self._combo(origins, char.origin, frozen=locked,
                                      on_change=self.set_origin), 1)
            id_lay.addLayout(box)
            ups = viewmod.upbringing_options(char.exalt_type,
                                             char.origin or next(iter(origins)))
            if ups:
                box = QHBoxLayout()
                box.addWidget(QLabel("Upbringing"))
                value = char.upbringing if char.upbringing in ups else next(iter(ups))
                box.addWidget(self._combo(ups, value, frozen=locked,
                                          on_change=self.set_upbringing), 1)
                id_lay.addLayout(box)
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
        id_lay.addLayout(box)
        field("Anima", char.anima, lambda t: setattr(char, "anima", t))

        # biography — free-fill flavour on real Character fields
        bio_lay = self._panel("Biography")
        for label, attr in (("Sex", "sex"), ("Age", "age"), ("Eye color", "eye_color"),
                            ("Hair color", "hair_color"), ("Skin color", "skin_color"),
                            ("Height", "height"), ("Weight", "weight")):
            box = QHBoxLayout()
            box.addWidget(QLabel(label))
            edit = QLineEdit(getattr(char, attr))
            edit.textChanged.connect(lambda t, a=attr: setattr(char, a, t))
            box.addWidget(edit, 1)
            bio_lay.addLayout(box)
        for label, attr in (("Description", "description"), ("Backstory", "backstory"),
                            ("Notes", "notes")):
            box = QHBoxLayout()
            box.addWidget(QLabel(label))
            edit = QTextEdit(getattr(char, attr))
            edit.setFixedHeight(56)
            # ⚠ QTextEdit is a QAbstractScrollArea inside a _Panel whose own
            # stylesheet forces the QSS renderer onto every descendant — the viewport
            # then paints the CARD shade no matter what the QTextEdit palette says,
            # and the theme's window QSS `background` paints only the frame. A widget
            # stylesheet on the QTextEdit ITSELF wins over both and paints the text
            # area the INPUT shade, so the fill-in reads like the line edits.
            edit.setStyleSheet(
                f"QTextEdit {{ background:{INPUT}; border:none; border-radius:4px; }}")
            # QTextEdit.textChanged carries NO argument (unlike QLineEdit's) — read
            # the text off the edit itself.
            edit.textChanged.connect(lambda a=attr, e=edit: setattr(char, a, e.toPlainText()))
            box.addWidget(edit, 1)
            bio_lay.addLayout(box)

        # caste info — the description, caste abilities/attributes and anima the old
        # left-hand card carried, now a panel under the identity fields.
        caste_lay = self._panel("Caste")
        caste_def = ruleset.castes.get(char.caste)
        splat_has_castes = any(cd.exalt_type == char.exalt_type
                               for cd in ruleset.castes.values())
        if caste_def:
            info = QLabel(f"{caste_def.label} {caste_noun}")
            info.setStyleSheet(f"font-weight:bold; color:{accent};")
            caste_lay.addWidget(info)
            if caste_def.description:
                desc = QLabel(caste_def.description)
                desc.setWordWrap(True)
                desc.setStyleSheet("color:#a8a5a0;")
                caste_lay.addWidget(desc)
            if caste_def.caste_attributes:
                line = QLabel(f"{caste_noun} Attributes: " + ", ".join(
                    _label(a.value) for a in caste_def.caste_attributes))
            elif caste_def.caste_abilities:
                line = QLabel(f"{caste_noun} Abilities: " + ", ".join(
                    _label(a.value) for a in caste_def.caste_abilities))
            else:
                line = None
            if line:
                line.setWordWrap(True)
                line.setStyleSheet("font-style:italic; color:#a8a5a0;")
                caste_lay.addWidget(line)
            if caste_def.anima_powers:
                anima = QLabel("Anima Power")
                anima.setStyleSheet(f"font-weight:bold; color:{accent};")
                caste_lay.addWidget(anima)
                ap = QLabel(caste_def.anima_powers)
                ap.setWordWrap(True)
                ap.setStyleSheet("color:#a8a5a0;")
                caste_lay.addWidget(ap)
        elif splat_has_castes:
            caste_lay.addWidget(QLabel("Unknown caste"))
        else:
            splat = QLabel(ruleset.exalt_for(char.exalt_type).label)
            splat.setStyleSheet(f"font-weight:bold; color:{accent};")
            caste_lay.addWidget(splat)
            caste_lay.addWidget(QLabel("Not one of the Chosen — no caste, no Charms, "
                                      "Essence 1."))


class TraitsPage(_EditorPage):
    """The Traits tab: the favoured-pick chips, the Attribute / Ability / Craft /
    Virtue / Essence dot tracks, and the read-only Charm & Spells count. Dot clicks
    buy on both sides of the lock (decision 0013); the validation/bonus/XP content
    lives in the shell's popover."""

    def _build_body(self) -> None:
        char = self._char()
        pal = theme.palette(char.exalt_type)
        locked = char.chargen_locked
        ruleset = self._ruleset
        accent = accent_light(pal)
        caste_def = ruleset.castes.get(char.caste)
        caste_abilities = set(caste_def.caste_abilities) if caste_def else set()
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

        def buy(target, current, wanted, refresh, detail=""):
            return self._buy(target, current, wanted, refresh, detail)

        def track(get, setv, lo, hi, target=None, detail=""):
            return DotTrack(get, setv, lo, hi, accent=accent, target=target,
                            detail=detail, buy=buy, on_change=self._changed)

        note = QLabel("Native Edit covers the trait surface. Training Camp & Calling "
                      "and Downtime still live on the webapp.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a8a5a0; font-size:9pt;")
        self._body_lay.addWidget(note)

        # favoured picks
        fav_lay = self._panel("Favoured Picks")
        fav_n = validate.favored_ability_count(ruleset, char)
        if fav_n:
            label = QLabel(f"Favored abilities (pick {fav_n})")
            label.setContentsMargins(0, 2, 0, 0)
            fav_lay.addWidget(label)
            fav_lay.addWidget(_FavoredPicker(
                {a: _label(a.value) for a in AbilityName},
                list(char.favored_abilities), fav_n, accent,
                self.set_favored, frozen=locked))
        if cf_attr_mode:
            label = QLabel(f"Favored Attributes (pick {b.attribute_favored_count})")
            label.setContentsMargins(0, 2, 0, 0)
            fav_lay.addWidget(label)
            fav_lay.addWidget(_FavoredPicker(
                {a: _label(a.value) for a in AttributeName},
                list(char.favored_attributes), b.attribute_favored_count, accent,
                self.set_favored_attributes, frozen=locked))

        # attributes
        ap = "/".join(str(p) for p in validate.effective_attribute_pools(ruleset, char))
        header = viewmod.attribute_budget_summary(ruleset, char) or f"prioritise {ap}"
        attr_lay = self._panel("Attributes" if locked else f"Attributes ({header})")
        cols = QHBoxLayout()
        cols.setSpacing(24)
        attr_lay.addLayout(cols)
        for i, (category, members) in enumerate(validate.ATTRIBUTE_CATEGORIES.items()):
            if i > 0:
                cols.addWidget(self._vsep())
            group = QVBoxLayout()
            group.setSpacing(_ROW_SPACING)          # ⚠ see _ROW_SPACING
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
                mark = "●" if a in caste_abilities else ("✦" if a in favored_attrs else "")
                extra = None
                breed = breed_bonus.get(a, 0)
                if breed:
                    extra = QLabel(f"+{breed} breed")
                    extra.setStyleSheet("color:#a8a5a0; font-style:italic;")
                row = QHBoxLayout()
                m = QLabel(mark)
                m.setFixedWidth(12)
                m.setStyleSheet(f"color:{accent};")
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

        # abilities
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
                label.setStyleSheet("font-weight:600; color:%s;" % ("#b91c1c" if over else accent))

            _ability_tally()
            self._tallies.append(_ability_tally)
            ab_lay.addWidget(tally)
        groups = viewmod.ability_group_defs(ruleset, char.exalt_type)
        calling_marks = viewmod.calling_ability_marks(ruleset, char)
        for start in range(0, len(groups), 3):
            cols = QHBoxLayout()
            cols.setSpacing(24)
            ab_lay.addLayout(cols)
            for j, (group_label, abilities) in enumerate(groups[start:start + 3]):
                if j > 0:
                    cols.addWidget(self._vsep())
                group = QVBoxLayout()
                group.setSpacing(_ROW_SPACING)      # ⚠ see _ROW_SPACING
                if group_label:
                    g = QLabel(group_label)
                    g.setStyleSheet(f"font-weight:600; color:{accent};")
                    group.addWidget(g)
                for a in abilities:
                    mark = "●" if a in caste_abilities else ("✦" if a in char.favored_abilities else "")
                    if a in calling_marks:
                        mark += "✧"
                    if a == AbilityName.CRAFT:
                        row = QHBoxLayout()
                        m = QLabel(mark)
                        m.setFixedWidth(12)
                        m.setStyleSheet(f"color:{accent};")
                        row.addWidget(m)
                        row.addWidget(QLabel("Craft"), 1)
                        row.addWidget(QLabel("↓ per-focus"))
                        group.addLayout(row)
                        continue
                    row = QHBoxLayout()
                    m = QLabel(mark)
                    m.setFixedWidth(12)
                    m.setStyleSheet(f"color:{accent};")
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

        # crafts
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

        # virtues + essence + willpower
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

        # Astrological Colleges (Sidereal) — a rated Advantage with its own pool. Shown
        # only for splats that ship colleges, which `b.college_dots` is the test for.
        # Options are grouped by house label and the character's own Maiden's house is
        # marked ★, because the budget has a minimum in it.
        if b.college_dots > 0 and ruleset.colleges:
            own_house = char.caste
            college_opts = {
                col.id: (f"{'★ ' if col.house == own_house else ''}{col.name}"
                         f"  ·  {col.house_label}")
                for col in ruleset.colleges.values()
            }
            own_dots = sum(cr.rating for cr in char.colleges
                           if (c := ruleset.colleges.get(cr.college_id))
                           and c.house == own_house)
            col_lay = self._panel(
                f"Astrological Colleges ({b.college_dots} dots; "
                f"≥{b.college_min_own_house} in your Maiden's ★ house — have {own_dots}; "
                f"≤{b.college_cap_pre_bp} pre-bonus)")
            for idx, cr in enumerate(char.colleges):
                row = QHBoxLayout()
                # ⚠ An off-catalogue id from an old save keeps its own row entry, so the
                # combo can show it instead of silently snapping to another college.
                row_opts = (college_opts if cr.college_id in college_opts
                            else {**college_opts, cr.college_id: cr.college_id})
                row.addWidget(self._combo(
                    row_opts, cr.college_id, frozen=False,
                    on_change=lambda cid, cr=cr: (setattr(cr, "college_id", cid),
                                                  self._changed())), 1)
                # lo=0: Colleges can be REDUCED. A usability escape hatch, not a printed
                # rule — same as Crafts (docs/status/edit-xp-merge.md).
                row.addWidget(track(lambda cr=cr: cr.rating,
                                    lambda v, cr=cr: setattr(cr, "rating", v),
                                    0, 5, target="colleges", detail=cr.college_id))
                drop = QPushButton("✕")
                drop.setFixedWidth(28)
                drop.clicked.connect(lambda _=False, idx=idx: self.remove_college(idx))
                row.addWidget(drop)
                col_lay.addLayout(row)
            add_col = QPushButton("+ Add college")
            add_col.clicked.connect(self.add_college)
            col_lay.addWidget(add_col)

        # Specialties. ⚠ A specialty is an INSTANCE, not a rated trait (human, rules
        # authority, 2026-07-31): you do not raise one, you take the same one again, so
        # there is no dot track here — "Swords" twice means two rows — and the cap of 3
        # counts ROWS per Ability.
        sp_lay = self._panel("Specialties (max 3 per Ability; take one twice to stack it)")
        for idx, sp in enumerate(char.specialties):
            row = QHBoxLayout()
            if locked:
                # Read-only after the lock for the reason the Charms tab's rows are:
                # removal in play is undo, not deletion.
                row.addWidget(QLabel(f"{_label(sp.ability.value)} — {sp.name}"), 1)
                sp_lay.addLayout(row)
                continue
            # ⚠ BOTH handlers must fire `_changed()`. A row is appended blank on Melee
            # and retargeted afterwards, so the add itself can legitimately push Melee
            # over the cap until the real Ability is picked — and that transient
            # `specialty-cap` error is already on screen. Without the re-run the
            # retarget fixes the MODEL and leaves the stale error up: three Melee plus
            # three Dodge reads back as "Melee has 4".
            row.addWidget(self._combo(
                {a: _label(a.value) for a in AbilityName}, sp.ability, frozen=False,
                on_change=lambda a, sp=sp: (setattr(sp, "ability", a), self._changed())), 1)
            name = QLineEdit(sp.name)
            name.setPlaceholderText("Specialty")
            name.textChanged.connect(
                lambda t, sp=sp: (setattr(sp, "name", t), self._changed()))
            row.addWidget(name, 1)
            drop = QPushButton("✕")
            drop.setFixedWidth(28)
            drop.clicked.connect(lambda _=False, idx=idx: self.remove_spec(idx))
            row.addWidget(drop)
            sp_lay.addLayout(row)
        if locked:
            # Post-lock a specialty is a PURCHASE, so it is named and priced up front
            # rather than appended blank — an empty row would already have cost XP.
            row = QHBoxLayout()
            row.addWidget(QLabel("Specialty in"))
            pick = {"ability": AbilityName.MELEE}
            row.addWidget(self._combo(
                {a: _label(a.value) for a in AbilityName}, AbilityName.MELEE,
                frozen=False, on_change=lambda a: pick.__setitem__("ability", a)), 1)
            new_name = QLineEdit()
            new_name.setObjectName("specialty.new")
            new_name.setPlaceholderText("specialty name")
            row.addWidget(new_name, 1)
            row.addWidget(QLabel(f"{costs.specialty_cost(ruleset, char)} XP"))
            buy = QPushButton("Buy")
            buy.clicked.connect(lambda: self._do_trait(
                lambda: advancement.add_specialty(
                    ruleset, char, pick["ability"], new_name.text().strip())))
            row.addWidget(buy)
            sp_lay.addLayout(row)
        else:
            add = QPushButton("Add specialty")
            add.clicked.connect(self.add_spec)
            sp_lay.addWidget(add)

        # Permanent Resonance — the Abyssal Death's Taint counterpart to the temporary
        # track (p.41). Post-lock only, and only where the cap is non-zero, which is the
        # engine's way of saying "this character has the Flaw" without naming a Merit id.
        # ⚠ This is the EDIT surface for it: qt/play.py shows the same number READ-ONLY
        # and points here, because gain and shed both go through the XP ledger.
        perm_cap = derive.permanent_limit_cap(ruleset, char) if locked else 0
        if perm_cap:
            lim = derive.limit_label(ruleset, char)
            res_lay = self._panel(f"Permanent {lim}")
            note = QLabel(f"{char.limit_permanent} of {perm_cap} (capped at Essence). "
                          f"Gained when the temporary track overflows; shed with a "
                          f"Harrowing.")
            note.setWordWrap(True)
            note.setStyleSheet("color:#a8a5a0;")
            res_lay.addWidget(note)
            row = QHBoxLayout()
            reason = QLineEdit()
            reason.setPlaceholderText("reason (e.g. Resonance overflowed)")
            row.addWidget(reason, 1)
            gain = QPushButton("Gain (free)")
            gain.clicked.connect(lambda: self._do_trait(
                lambda: advancement.gain_permanent_resonance(
                    ruleset, char, reason.text().strip())))
            row.addWidget(gain)
            shed = QPushButton(f"Shed ({merits.PERMANENT_RESONANCE_SHED_XP} XP)")
            shed.clicked.connect(lambda: self._do_trait(
                lambda: advancement.shed_permanent_resonance(
                    ruleset, char, reason.text().strip())))
            row.addWidget(shed)
            res_lay.addLayout(row)

        # Virtue Flaw — splat-gated: the Dragon-Blooded, Sidereals and Alchemicals have
        # none. ⚠ NOT the same question as having a Limit track (a Sidereal has Paradox
        # and no flawed Virtue), which is why this asks derive.has_virtue_flaw and not
        # the limit label.
        vf_row = QHBoxLayout()
        vf_row.setSpacing(24)
        self._body_lay.addLayout(vf_row)
        if derive.has_virtue_flaw(ruleset, char):
            vf = char.virtue_flaw
            vf_lay = self._panel("Virtue Flaw", vf_row)
            row = QHBoxLayout()
            row.addWidget(QLabel("Flawed Virtue"))
            # A blank leading entry only while none is chosen — Qt has no empty state
            # for a combo, and defaulting to Compassion would write a pick the player
            # never made.
            opts = {} if vf else {None: "—"}
            opts.update({v: _label(v.value) for v in VirtueName})
            # ⚠ Named, not found by position. Three combos sit in this half of the page
            # and `findChildren(QComboBox)[0]` is the Flawed Virtue box for all three
            # callers that want a different one.
            virtue_combo = self._combo(
                opts, vf.virtue if vf else None, frozen=locked,
                on_change=lambda v: v is not None and self.set_virtue_flaw_virtue(v))
            virtue_combo.setObjectName("virtue_flaw.virtue")
            row.addWidget(virtue_combo, 1)
            vf_lay.addLayout(row)

            # The book's SAMPLE Flaws for the Virtue that is actually flawed
            # (pp.131-133) — offering a Compassion Flaw beside a flawed Valor would be
            # offering an illegal pick. The list is a shortcut into the free-text field
            # below, never a replacement for it: the page says in as many words that
            # these are not the only Flaws an Exalt might develop.
            samples = [f for f in ruleset.virtue_flaw_catalog.values()
                       if vf is not None and f.virtue == vf.virtue]
            if samples:
                row = QHBoxLayout()
                row.addWidget(QLabel("Sample Flaw"))
                sample_opts = {None: "— fills the description —"}
                sample_opts.update({f.id: f.name
                                    for f in sorted(samples, key=lambda f: f.name)})
                sample_combo = self._combo(
                    sample_opts, None, frozen=False,
                    on_change=lambda fid: fid and self.set_virtue_flaw_sample(fid))
                sample_combo.setObjectName("virtue_flaw.sample")
                row.addWidget(sample_combo, 1)
                vf_lay.addLayout(row)

            row = QHBoxLayout()
            row.addWidget(QLabel("Description"))
            desc = QLineEdit(vf.description if vf else "")
            desc.setObjectName("virtue_flaw.description")
            desc.textChanged.connect(self.set_virtue_flaw_desc)
            row.addWidget(desc, 1)
            vf_lay.addLayout(row)

            # The Limit Break Condition is the half that gets consulted at the table, so
            # it is shown rather than folded into the description.
            picked = next((f for f in samples
                           if vf is not None and f.description == vf.description), None)
            if picked is not None and picked.limit_break:
                lb = QLabel(f"Limit Break: {picked.limit_break}")
                lb.setWordWrap(True)
                lb.setStyleSheet("color:#a8a5a0;")
                vf_lay.addWidget(lb)

        # Bonus health levels per tier. The stored list is a DELTA from the printed
        # track, which is why the box shows a TOTAL and the engine works out whether
        # that means added levels or removed ones (engine/health_actions).
        hl_lay = self._panel("Bonus health levels per tier "
                             "(charms raise, curses lower)", vf_row)
        hl_row = QHBoxLayout()
        for p in health_actions.EDITABLE_TIERS:
            col = QVBoxLayout()
            col.addWidget(QLabel("-0" if p == 0 else str(p)))
            spin = QSpinBox()
            # ⚠ Named, not positional: the Attributes panel's spin boxes are the ones a
            # `findChildren(QSpinBox)[0]` would reach.
            spin.setObjectName(f"health.{p}")
            spin.setRange(0, 20)
            spin.setValue(health_actions.level_total(char, p))
            spin.valueChanged.connect(
                lambda v, p=p: (health_actions.set_level_total(char, p, v),
                                self._changed()))
            col.addWidget(spin)
            hl_row.addLayout(col)
        hl_row.addStretch(1)
        hl_lay.addLayout(hl_row)

        # charms/spells — read-only here
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

def _label(value: str) -> str:
    return value.replace("_", " ").title()
