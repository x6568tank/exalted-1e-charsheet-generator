"""exalted_builder/qt/editor.py — the Edit tab: chargen and XP on one trait surface.

Input: a RuleSet and a Character from the shared context. Output: a scrollable form of
dot-track trait rows (Attributes, Abilities, Crafts, Virtues, Essence, Willpower), the
identity and structural controls, and a side column. During chargen, the side column shows
the live validation and the bonus points. After the lock, it shows the XP card and the
ledger. Mechanism: this page builds its widgets one time and changes them. During chargen,
a dot click sets the rating. After the lock, the click goes to `engine.advancement`
(decision 0013). Each change calculates the side column again from `view.build_sheet_view`
and `validate`.

⚠ This page is not a copy of the NiceGUI editor (`docs/plans/qt-port.md`, "What does NOT
translate"). The NiceGUI editor rebuilds the page on each click. This page rebuilds only
what a change moves: a dot click changes its own row and the side column. A structural
change (Exalt type, caste, origin, favoured picks) rebuilds the body.

⚠ The Downtime calculator is with the other XP controls, in the popover of the shell. See
`qt/main_window.py::_downtime_dialog`. It is not on this tab.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSizePolicy,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from exalted_builder.engine import (advancement, camp_actions, costs, derive,
                                    elder, health_actions, merits, validate)
from exalted_builder.models.character import (
    AbilityName, AttributeName, Character, CollegeRating, CraftRating, Specialty,
    VirtueFlaw, VirtueName,
)
from exalted_builder.models.rules import RuleSet
from .theme import CARD, INPUT, MUTED, accent as accent_light

from .layout import clear_layout
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

# The XP-log targets that move the maximum of OTHER rows. A purchase of one of these must
# rebuild the full body, not its own dot row. ⚠ If you omit a target here, the rows that
# depend on it keep their old pips until the user opens the tab again. Essence is the one
# member. Above 5, Essence IS the maximum of every Ability and Attribute (`engine.elder`).
BODY_REBUILD_TARGETS = {"essence"}

# ⚠ The QSS gives `background:CARD` to every QPushButton. CARD is the shade of the _Panel
# below the button. Thus a small button on a card is INVISIBLE. An ancestor stylesheet
# beats a palette that you set on the widget. The correction is an inline stylesheet on the
# widget. INPUT is a clear step lighter than CARD.
_TINY_BUTTON = (f"background:{INPUT}; color:#e8e6e1; border:none; border-radius:3px; "
                f"padding:0px; font-weight:700;")


def _trait_reference_dialog(parent, info, accent_colour: str) -> None:
    """Open `_build_trait_dialog` as a modal. `_build_trait_dialog` is a separate function,
    thus a headless test can build the dialog. `exec()` stops a headless run."""
    _build_trait_dialog(parent, info, accent_colour).exec()


def _build_trait_dialog(parent, info, accent_colour: str) -> QDialog:
    """Build the read-only modal showing one trait's core-book text (`viewmod.TraitInfo`).

    This dialog agrees with `ui.catalogue.trait_reference_dialog`. It uses the same
    TraitInfo and the same order: the description, then the rung ladder with the rung of
    the character in bold, then the sections. Thus the two shells describe a trait in the
    same way.

    ⚠ Set the colour of each label that wraps inline. A parent stylesheet beats a palette
    that you set on the widget, and the stylesheet of the editor is on an ancestor of this
    dialog."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"{info.title} — {info.subtitle}")
    dialog.resize(560, 620)
    outer = QVBoxLayout(dialog)

    title = QLabel(info.title)
    title.setStyleSheet(f"font-size:15px; font-weight:700; color:{accent_colour};")
    outer.addWidget(title)
    subtitle = QLabel(info.subtitle)
    subtitle.setStyleSheet(f"color:{MUTED};")
    outer.addWidget(subtitle)

    inner = QWidget()
    lay = QVBoxLayout(inner)
    lay.setSpacing(8)
    for para in info.description.split("\n\n"):
        if para.strip():
            text = QLabel(para)
            text.setWordWrap(True)
            lay.addWidget(text)
    for rating, rung, current in info.ladder:
        row = QHBoxLayout()
        # Rung 0 is "Unskilled". The page prints it as a cross, not as zero dots. An empty
        # cell reads as a missing value, not as a rung.
        pips = QLabel("●" * rating if rating else "✕")
        pips.setFixedWidth(64)
        pips.setAlignment(Qt.AlignTop)
        pips.setStyleSheet(f"color:{accent_colour};")
        row.addWidget(pips)
        text = QLabel(rung)
        text.setWordWrap(True)
        text.setStyleSheet("font-weight:700;" if current else "")
        row.addWidget(text, 1)
        lay.addLayout(row)
    for heading, body in info.sections:
        head = QLabel(heading)
        head.setStyleSheet(f"font-weight:700; color:{accent_colour};")
        lay.addWidget(head)
        text = QLabel(body)
        text.setWordWrap(True)
        lay.addWidget(text)
    lay.addStretch(1)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(inner)
    outer.addWidget(scroll, 1)

    close = QPushButton("Close")
    close.clicked.connect(dialog.accept)
    outer.addWidget(close)
    return dialog


class _Pip(QLabel):
    """One clickable pip of a dot track. Emits its 1-based pip index on click."""

    clicked = Signal(int)

    def __init__(self, index: int, parent=None):
        super().__init__(parent)
        self._index = index
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.clicked.emit(self._index)


# ⚠ Set the spacing of a nested layout. A layout with unset spacing (-1) TAKES the spacing
# of its parent. Thus a 24px gap between the COLUMNS becomes the gap between the ROWS in
# each column. The Attribute rows are then 41px apart and the Virtue rows are 21px apart,
# and the card reads as too tall.
_ROW_SPACING = 4

class DotTrack(QWidget):
    """A clickable dot-track rating control. It is the buy control on both sides of the
    lock (decision 0013). `get` reads the rating, and `setv` writes it. Before the lock, a
    click sets the rating and costs nothing. After the lock, `buy` prices and validates the
    click, if the caller names a `target`. A click on the current top pip decreases the
    rating. `refresh()` reads `get()` again and rebuilds the pips. It always shows enough
    pips to decrease a rating that is too high."""

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
        # ⚠ After the lock, a click is a purchase, a refund or a curse. It is never a
        # direct write. `buy` returns True when it accepts the click.
        if self._buy is not None and self._target is not None:
            if self._buy(self._target, current, wanted, self.refresh, self._detail):
                return
        self._setv(wanted)
        self.refresh()
        if self._on_change is not None:
            self._on_change()


class _FilterCombo(QComboBox):
    """An editable combo box that opens its list on a click. The user types to filter the
    list with the completer, or clicks to see all of it. ⚠ A plain QComboBox opens its list
    from the arrow only. A click on its text area sets the focus and does nothing else."""

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self.view().isVisible():
            self.showPopup()


class _FavoredPicker(QWidget):
    """A multiple-selection control with chips and a type-to-filter box.

    Input: every option, in an editable combo box. The completer filters the labels while
    the user types, and a click opens the full list. A selection from the dropdown, the
    completer or the Enter key adds the option as a chip, up to `cap`. `on_change` sends
    the current selections after the user adds or removes a chip. The control is disabled
    when it is frozen, because the lock fixes the chargen choices.

    ⚠ **`cap=None` means NO LIMIT.** It is not the same as a large number. The placeholder
    PRINTS the cap. Thus a caller that passes 999 to mean "no limit" shows "Type a name…
    (pick 999)". The models put no limit on the lists of the Custom tab: prerequisites,
    extra-requirement traits and open-to tiers."""

    def __init__(self, options: dict, current: list, cap: int | None, accent: str,
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
        self.combo.lineEdit().setPlaceholderText(
            "Type a name…" if cap is None else f"Type a name… (pick {cap})")
        self.combo.lineEdit().returnPressed.connect(self._add_current)
        # Connect both signals: `activated(int)` for a dropdown selection, and
        # `textActivated(str)` for the completer. `_add_current` gives the same result on a
        # second call, thus two signals for one selection are safe.
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
        if key is None or key in self._picked:
            return
        if self._cap is not None and len(self._picked) >= self._cap:
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
        # ⚠ Move the focus to the combo box BEFORE you delete the chip. The ✕ that the user
        # clicked holds the focus. When you delete it, Qt gives the focus to the next
        # focusable widget, which can be a QSpinBox at the end of the form, and the scroll
        # area scrolls to that widget. The combo box is part of this picker and is on the
        # screen.
        self.combo.setFocus()
        self._picked.remove(key)
        self._render_chips()
        self._on_change(list(self._picked))


class _Panel(QFrame):
    """A card with a title. It is the section container of the editor. It has a `node_bg`
    fill and a border in the accent colour."""

    def __init__(self, title: str, pal, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background:{CARD}; border:none; border-radius:6px; }}")
        # ⚠ A card takes the height of its content, and it never expands vertically.
        # Without this rule, a card next to a taller card, for example the caste card next
        # to the Identity panel, becomes as tall as that card, and the extra height goes
        # between its labels. The stretch at the end of the body takes the free space.
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
    """The shared parts of the Identity page and the Traits page. It supplies a scrollable
    body that it builds one time, the dot-track purchase path, the decrease dialog, the
    scroll hold and the layout teardown. `reload()` rebuilds the body from the character in
    ctx. The `_build_body()` of a subclass supplies the content. `notify` shows a temporary
    message. `on_change` sends a signal after the character changes, thus the shell can
    refresh its readout and its status strip. The popover of the shell holds the side
    column."""

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
        """Rebuild the body from the character in ctx, then call the shell. Hold the height
        of the body across the rebuild, because a cleared layout makes the content shorter
        than the scrollbar and limits the saved value. Then apply the scroll position again
        for a short period (see `_hold_scroll`).

        ⚠ Call `on_change` HERE, not at the call sites. Every structural change does a full
        reload: Exalt type, caste, origin, favoured picks, a craft row, the purchases of
        `_do_trait`, and `_lower_willpower`. All ten sites move the bonus-point spend or
        the validation errors. One call in this wrapper is a mechanism. Ten call sites are
        the house bug, and an eleventh site will omit the call. A second entry is not a
        risk, because the `_refresh` of the shell writes labels and never reloads a
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
        """A vertical divider of 1px between two columns."""
        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet("background:#55535a;")
        return line

    def _combo(self, options: dict, value, *, frozen: bool, on_change,
               placeholder: str | None = None) -> QComboBox:
        """A select over `options` {key: label}, calling `on_change(key)` with the key
        the caller supplied.

        ⚠ **Index the key. NEVER read it back from the widget.** Qt stores item data as a
        QVariant, and `currentData()` returns an Enum with a `str` value as a plain `str`.
        Thus a handler that calls `setattr(row, "ability", …)` writes "dodge" onto a field
        of type `AbilityName`. The model has no `validate_assignment`, thus it accepts the
        write. The failure occurs later, at the first `.value` on a value that is no longer
        an enum. An index into the original dict returns the same object for every key type.

        ⚠ **Supply a `placeholder` where "nothing chosen" is a real state.** A Qt combo box
        has no empty state. With a `value` that is not one of the keys, it shows index 0.
        Thus the control REPORTS a selection that the character does not hold. The camp
        style select showed the first martial art while the package was unresolved, and it
        showed no Charm list below it. This code adds the placeholder row only while the
        value is absent. Thus a resolved control has no blank option.
        """
        combo = QComboBox()
        keys = list(options)
        if placeholder is not None and value not in keys:
            keys.insert(0, None)
            combo.addItem(placeholder, None)
        for key in (k for k in keys if k is not None):
            combo.addItem(options[key], key)
        combo.setCurrentIndex(keys.index(value) if value in keys else 0)
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
        """Empty `lay`, and detach every descendant immediately. ⚠ Call `qt/layout.py`.
        That module holds the two traps in this operation."""
        clear_layout(lay)

    def _buy(self, target: str, current: int, wanted: int, refresh, detail: str = "") -> bool:
        """Handle a dot click after the lock. Returns False before the lock. The track then
        sets the rating directly, at no cost."""
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
        """Draw what the change moved. A dot click draws its own row. ⚠ ESSENCE is the
        exception. Above 5, Essence is the maximum of every other track, thus the full body
        must rebuild. ⚠ Do one or the other, never both. A rebuild of the body replaces the
        row that `refresh` belongs to."""
        if target in BODY_REBUILD_TARGETS:
            self.reload()
        else:
            refresh()

    def _downward_dialog(self, target: str, current: int, wanted: int, refresh,
                         detail: str = "") -> None:
        """Ask the user which decrease this is. A refund of XP and a curse move the same
        dots, and they differ in price, in the log entry and in the floor.
        `refundable_depth` limits a refund, because an undo takes the last entry of the
        full log. A curse can remove chargen dots, thus its only limit is the floor of the
        trait. This method finds that floor on a copy of the character."""
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

    def set_camp(self, camp_id: str) -> None:
        camp_actions.set_camp(self._ruleset, self._char(), camp_id)
        self.reload()

    def set_calling(self, calling_id: str) -> None:
        camp_actions.set_calling(self._char(), calling_id)
        self.reload()

    def set_camp_choice(self, choice_index: int, key: str) -> None:
        self._camp_write(camp_actions.set_camp_choice(
            self._ruleset, self._char(), choice_index, key))

    def set_camp_choice_charms(self, choice_index: int, ids: list) -> None:
        self._camp_write(camp_actions.set_camp_choice_charms(
            self._ruleset, self._char(), choice_index, ids))

    def _camp_write(self, refusal) -> None:
        """⚠ A refusal needs BOTH actions: show the reason, and RELOAD in every case. After
        a refusal, the control shows a value that the character does not hold. The rebuild
        returns the control to the correct value. Without it, the dropdown looks broken."""
        if refusal:
            self._notify(refusal, "warning")
        self.reload()

    def add_college(self) -> None:
        """A new College row. Its default is a house of the character's own Maiden. Thus the
        row counts toward the own-house minimum, and it does not start as an error."""
        ruleset, char = self._ruleset, self._char()
        own = next((cid for cid, col in ruleset.colleges.items()
                    if col.house == char.caste), None)
        char.colleges.append(
            CollegeRating(college_id=own or next(iter(ruleset.colleges), ""), rating=1))
        self.reload()

    def remove_college(self, idx: int) -> None:
        del self._char().colleges[idx]
        self.reload()

    def _info_button(self, row, make_info, accent_colour: str) -> None:
        """Append the ⓘ that opens a trait's core-book reference text to `row`.

        `make_info` returns a `viewmod.TraitInfo` or None. This method calls it now, to
        decide if the button exists. A ruleset with no trait text gets no button. ⚠ It
        calls `make_info` AGAIN on the click. Thus the marked rung is the rating at the
        time of the click."""
        if make_info() is None:
            return
        btn = QPushButton("i")
        btn.setFixedSize(18, 18)
        btn.setStyleSheet(_TINY_BUTTON)
        btn.setToolTip("What this rating means (core rulebook)")
        btn.clicked.connect(
            lambda _=False: _trait_reference_dialog(self, make_info(), accent_colour))
        row.addWidget(btn)

    def _specialty_rows(self, group, ability: AbilityName, locked: bool) -> None:
        """One indented child row per specialty GROUP under its Ability's dot row.

        Before the lock, the user can edit the name, and ✕ removes one instance. After the
        lock, the row is read-only, because a removal in play is an undo, not a delete. The
        Charms rows follow the same rule."""
        char = self._char()
        for name, count in viewmod.specialty_groups(char, ability):
            row = QHBoxLayout()
            row.setContentsMargins(24, 0, 0, 0)
            if locked:
                label = QLabel(f"{name or '(unnamed)'}{f'  ×{count}' if count > 1 else ''}")
                label.setStyleSheet("color:#a8a5a0; font-size:9pt;")
                row.addWidget(label, 1)
            else:
                edit = QLineEdit(name)
                edit.setObjectName(f"specialty.name.{ability.value}.{name}")
                edit.setPlaceholderText("specialty")
                edit.setMaximumWidth(150)
                edit.setStyleSheet("font-size:9pt;")
                edit.editingFinished.connect(
                    lambda a=ability, old=name, e=edit:
                    e.text() != old and self.rename_spec_group(a, old, e.text()))
                row.addWidget(edit)
                if count > 1:
                    tally = QLabel(f"×{count}")
                    tally.setStyleSheet("color:#a8a5a0; font-size:9pt;")
                    row.addWidget(tally)
                drop = QPushButton("✕")
                drop.setFixedSize(18, 18)
                drop.setStyleSheet(_TINY_BUTTON)
                drop.setToolTip("Remove one instance")
                drop.clicked.connect(
                    lambda _=False, a=ability, n=name: self.drop_spec_instance(a, n))
                row.addWidget(drop)
                row.addStretch(1)
            group.addLayout(row)

    def _add_specialty(self, ability: AbilityName) -> None:
        """Before the lock, add a blank row, and the user names it in place. After the lock,
        a specialty is a PURCHASE. Thus the user names it and the engine prices it first. An
        empty row after the lock has already cost XP."""
        if not self._char().chargen_locked:
            self.add_spec_to(ability)
            return
        ruleset, char = self._ruleset, self._char()
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Buy a specialty in {_label(ability.value)}")
        lay = QVBoxLayout(dialog)
        lay.addWidget(QLabel(f"{_label(ability.value)} — "
                             f"{costs.specialty_cost(ruleset, char)} XP"))
        name = QLineEdit()
        name.setObjectName("specialty.new")
        name.setPlaceholderText("specialty name")
        lay.addWidget(name)
        note = QLabel("Max 3 per Ability; take the same one twice to stack it.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#a8a5a0;")
        lay.addWidget(note)

        def _go() -> None:
            try:
                advancement.add_specialty(ruleset, char, ability, name.text().strip())
            except advancement.AdvancementError as ex:
                self._notify(str(ex), "warning")
                return
            dialog.accept()
            self.reload()

        buy = QPushButton("Buy")
        buy.clicked.connect(_go)
        lay.addWidget(buy)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        lay.addWidget(cancel)
        dialog.exec()

    def add_spec_to(self, ability: AbilityName, name: str = "") -> None:
        """Append one instance of a specialty to a NAMED Ability.

        The control of each Ability knows its Ability. Thus the user does not add a blank
        row and then change its target. ⚠ Do NOT apply the limit here. Chargen writes the
        list, and `validate.check_specialties` reports an Ability above the limit. That
        check also covers a save that arrives above the limit. A limit on the add is a rule
        that the engine does not state."""
        self._char().specialties.append(
            Specialty(ability=ability, name=name, rating=1))
        self.reload()

    def rename_spec_group(self, ability: AbilityName, old: str, new: str) -> None:
        """Rename every instance in a group. ⚠ The group IS the specialty. Two rows named
        "Swords" are one specialty that the character took two times. If you rename one row
        and not the other, the group divides into two specialties."""
        for sp in self._char().specialties:
            if sp.ability == ability and sp.name == old:
                sp.name = new
        self._changed()

    def drop_spec_instance(self, ability: AbilityName, name: str) -> None:
        """Remove ONE instance from a group. The row goes away with the last instance."""
        specialties = self._char().specialties
        for i, sp in enumerate(specialties):
            if sp.ability == ability and sp.name == name:
                del specialties[i]
                break
        self.reload()

    def set_virtue_flaw_virtue(self, virtue: VirtueName) -> None:
        """Set which Virtue is flawed, keeping any description already written.

        ⚠ Reload the page. Do not draw the control in place. The sample-Flaw dropdown next
        to this control is built from the flawed Virtue. Without the rebuild, it offers the
        Flaws of the OLD Virtue, at the moment when the user reads it."""
        char = self._char()
        desc = char.virtue_flaw.description if char.virtue_flaw else ""
        char.virtue_flaw = VirtueFlaw(virtue=virtue, description=desc)
        self.reload()

    def set_virtue_flaw_sample(self, flaw_id: str) -> None:
        """Copy a sample Flaw's printed text into the free-text description.

        ⚠ Store a COPY, not a reference (decision 0007: ids for invariant content, inline
        copies for variable content). The user edits this text, because the book gives
        these Flaws as a guide to severity. A stored id makes an edited Flaw report that it
        is the printed Flaw."""
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

        This method operates with the height hold above. The layout pass of a rebuild can
        move the scrollbar with a direct `setValue`, not with a range change only. Thus
        this method applies the saved position again on each range change and each value
        change, for a short period. It then releases the scrollbar, and the user controls
        it again. ⚠ Drop a previous hold first. `reload()` runs more than one time at
        start, and an old hold restores an old position."""
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
        """Apply a change that moves the readouts only, for example a dot click, a name
        edit or an XP adjustment. This method runs the registered totals again, and it
        calls `on_change` for the readout and the status strip of the shell. The dot tracks
        of the body have already refreshed themselves."""
        for tally in self._tallies:
            tally()
        if self._on_change is not None:
            self._on_change()


class IdentityPage(_EditorPage):
    """The Identity tab. It holds the name, the concept and the anima, the structural
    selectors (Exalt type, caste, origin, upbringing, nature), the free-text biography, and
    the caste-info block. A structural change rebuilds this page and themes the shell
    again. The Traits page reloads when the shell shows it."""

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
            # ⚠ Set a stylesheet on the QTextEdit ITSELF. A QTextEdit is a
            # QAbstractScrollArea inside a _Panel, and the stylesheet of the _Panel gives
            # every descendant to the QSS renderer. The viewport then paints the CARD
            # shade, and it ignores the palette of the QTextEdit. The window QSS of the
            # theme paints the frame only. A stylesheet on the widget beats both, and it
            # paints the text area the INPUT shade. Thus the field looks like a line edit.
            edit.setStyleSheet(
                f"QTextEdit {{ background:{INPUT}; border:none; border-radius:4px; }}")
            # ⚠ `QTextEdit.textChanged` sends NO argument. The signal of a QLineEdit sends
            # one. Thus read the text from the widget.
            edit.textChanged.connect(lambda a=attr, e=edit: setattr(char, a, e.toPlainText()))
            box.addWidget(edit, 1)
            bio_lay.addLayout(box)

        # The caste info panel. It holds the description, the caste Abilities or
        # Attributes, and the anima. It goes below the identity fields.
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

        self._build_camp_panel(locked, accent)

    def _build_camp_panel(self, locked: bool, accent: str) -> None:
        """The Training Camp & Calling panel (Cult of the Illuminated), or nothing.

        Draw this panel only when the ORIGIN uses camps. In any other case,
        `build_camp_view` returns None, thus no other splat gets an empty panel. Every
        write goes through `engine.camp_actions`. This method draws the view only."""
        ruleset, char = self._ruleset, self._char()
        cv = viewmod.build_camp_view(ruleset, char)
        if cv is None:
            return
        # Cult p.96 gives a Dragon-Blooded a camp and no Calling. Thus the heading names
        # what the panel CONTAINS. It must not name a control that is absent.
        camp_lay = self._panel("Training Camp & Calling" if cv.calling_options
                               else "Training Camp")
        # ⚠ Use TWO columns only when a Calling fills the second column. A Cult
        # Dragon-Blooded has a camp and no Calling (p.96). An empty half of the panel reads
        # as content that did not load.
        two_columns = bool(cv.calling_options)
        if two_columns:
            row = QHBoxLayout()
            row.setSpacing(24)
            camp_lay.addLayout(row)
        else:
            row = None

        # The left column holds the camp, its minimums and its free-Charm package.
        left = QVBoxLayout()
        left.setSpacing(_ROW_SPACING)
        (row.addLayout(left, 1) if two_columns else camp_lay.addLayout(left))
        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel("Training camp"))
        camp_combo = self._combo(
            dict(cv.camp_options), cv.camp_id or None, frozen=locked,
            placeholder="— choose a camp —",
            on_change=lambda cid: cid and self.set_camp(cid))
        camp_combo.setObjectName("camp.camp")
        pick_row.addWidget(camp_combo, 1)
        left.addLayout(pick_row)
        for text, italic in ((cv.camp_description, False),
                             ("Required Abilities: " + " · ".join(cv.minimums)
                              if cv.minimums else "", True),
                             ("Free Charms: " + ", ".join(n for _, n in cv.granted_fixed)
                              if cv.granted_fixed else "", True)):
            if not text:
                continue
            label = QLabel(text)
            label.setWordWrap(True)
            label.setStyleSheet("color:#a8a5a0;" + (" font-style:italic;" if italic else ""))
            left.addWidget(label)

        for idx, choice in enumerate(cv.choices):
            # ⚠ Read `pick`, not `is_category_choice`. A flat-pool choice also selects N
            # entries. A fixed-set choice leaves `pick` at 0, and it has no count to show.
            suffix = f" (pick {choice.pick})" if choice.pick else ""
            # ⚠ Keep an option that the page offers and `data/` cannot supply. It stays in
            # the LIST, because a hidden option misreports the rulebook. Mark that option,
            # and `camp_actions` refuses it. It must not assign nothing.
            opts = {o.key: (o.label if o.available else f"{o.label} — {o.reason}")
                    for o in choice.options}
            # A flat-pool choice has no options and no style step. The Charm list below is
            # the full control. Thus do not draw a select box with no options.
            if opts:
                sub = QHBoxLayout()
                sub.addWidget(QLabel(choice.label + suffix))
                style_combo = self._combo(
                    opts, choice.chosen_key or None, frozen=locked,
                    placeholder="— choose one —",
                    on_change=lambda key, i=idx: key and self.set_camp_choice(i, key))
                style_combo.setObjectName(f"camp.choice.{idx}")
                sub.addWidget(style_combo, 1)
                left.addLayout(sub)
            # The style is half of the choice. The package is "two Charms from ONE of four
            # martial arts" (p.90). Thus the user also selects WHICH style.
            if choice.charm_options:
                heading = QLabel(f"Which {choice.pick}?" if opts
                                 else choice.label + suffix)
                left.addWidget(heading)
                picks = QListWidget()
                picks.setObjectName(f"camp.charms.{idx}")
                picks.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
                picks.setMaximumHeight(140)
                for o in choice.charm_options:
                    item = QListWidgetItem(
                        o.label if o.meets_minimums else f"{o.label} — {o.reason}")
                    item.setData(Qt.ItemDataRole.UserRole, o.charm_id)
                    picks.addItem(item)
                    if o.charm_id in choice.chosen_charm_ids:
                        item.setSelected(True)
                picks.setEnabled(not locked)
                picks.itemSelectionChanged.connect(
                    lambda lw=picks, i=idx: self.set_camp_choice_charms(
                        i, [lw.item(r).data(Qt.ItemDataRole.UserRole)
                            for r in range(lw.count()) if lw.item(r).isSelected()]))
                left.addWidget(picks)

        # right: the Calling and what it discounts
        if two_columns:
            right = QVBoxLayout()
            right.setSpacing(_ROW_SPACING)
            row.addLayout(right, 1)
            sub = QHBoxLayout()
            sub.addWidget(QLabel("Calling"))
            calling_combo = self._combo(
                dict(cv.calling_options), cv.calling_id or None, frozen=locked,
                placeholder="— choose a Calling —",
                on_change=lambda cid: cid and self.set_calling(cid))
            calling_combo.setObjectName("camp.calling")
            sub.addWidget(calling_combo, 1)
            right.addLayout(sub)
            for text in (cv.calling_description,
                         "✧ Calling Abilities: " + ", ".join(cv.calling_abilities)
                         if cv.calling_abilities else "",
                         f"✧ {len(cv.calling_charms)} Calling Charms — discounted at "
                         f"chargen and in play" if cv.calling_charms else ""):
                if not text:
                    continue
                label = QLabel(text)
                label.setWordWrap(True)
                label.setStyleSheet("color:#a8a5a0;")
                right.addWidget(label)
            right.addStretch(1)


class TraitsPage(_EditorPage):
    """The Traits tab. It holds the favoured-pick chips, the dot tracks for Attributes,
    Abilities, Crafts, Virtues and Essence, and the read-only count of Charms and Spells. A
    dot click buys on both sides of the lock (decision 0013). The popover of the shell
    holds the validation, the bonus points and the XP."""

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
                self._info_button(row, lambda a=a: viewmod.attribute_info(
                    ruleset, a, char.attributes[a]), accent)
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
                        # No single rating to highlight: the rungs are per focus, so
                        # the ladder shows unmarked.
                        self._info_button(row, lambda a=a: viewmod.ability_info(ruleset, a),
                                          accent)
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
                    self._info_button(row, lambda a=a: viewmod.ability_info(
                        ruleset, a, char.abilities[a]), accent)
                    t = track(lambda a=a: char.abilities[a],
                              lambda v, a=a: char.abilities.__setitem__(a, v),
                              0, abil_trait_cap, target=f"abilities.{a.value}")
                    row.addWidget(t)
                    add = QPushButton("+")
                    add.setObjectName(f"specialty.add.{a.value}")
                    add.setFixedSize(18, 18)
                    add.setStyleSheet(_TINY_BUTTON)
                    add.setToolTip(f"Add a specialty in {_label(a.value)}")
                    add.clicked.connect(lambda _=False, a=a: self._add_specialty(a))
                    row.addWidget(add)
                    group.addLayout(row)
                    self._specialty_rows(group, a, locked)
                cols.addLayout(group, 1)

        # ⚠ There is no Specialties PANEL (human's ruling). A specialty belongs to one
        # Ability. Thus this code draws it as a child row below that Ability. Do not put it
        # in its own section, where the user must select the Ability again from a dropdown.
        # `_specialty_rows` above is the full implementation.

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
            self._info_button(row, lambda v=v: viewmod.virtue_info(
                ruleset, v, char.virtues[v]), accent)
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
        # A mortal with an unlocked pool has a maximum Essence of 3. The book gives the
        # reason in the fiction: "the limit of human potential — mortals that exceed
        # Essence 3 become gods" (PG p.114).
        #
        # ⚠ This note is for DISPLAY ONLY. `advancement.raise_essence` applies the limit,
        # and the mortal XP table prices nothing above 3. This note gives the reason for
        # the refusal. It does not refuse anything. Without it, the track stops and the
        # screen gives no reason.
        #
        # ⚠ Read the CALC. Never read a Merit id. No module outside `engine/merits.py` can
        # name one. The trigger is the field that supplied the limit. Thus this note appears
        # only where the maximum is a raised 3. A mortal with an Awareness-only pool has a
        # maximum of 1, and this clause does not apply to that character.
        if char.exalt_type == "Mortal" and mf.essence_cap_override is not None \
                and char.essence_rating >= mf.essence_cap_override:
            note = QLabel("the limit of human potential — mortals that exceed "
                          "Essence 3 become gods (PG p.114)")
            note.setObjectName("essence.mortal_ceiling")
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{MUTED};")
            ew_lay.addWidget(note)
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

        # Astrological Colleges (Sidereal). A College is a rated Advantage with its own
        # pool. Show this panel only for a splat that has colleges. `b.college_dots` is the
        # test. This code groups the options by house label, and it marks the house of the
        # character's own Maiden with ★, because the budget has a minimum for that house.
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
                # ⚠ Keep the row entry for an id that the catalogue does not hold. Thus the
                # combo shows that id, and it does not change to a different college.
                row_opts = (college_opts if cr.college_id in college_opts
                            else {**college_opts, cr.college_id: cr.college_id})
                row.addWidget(self._combo(
                    row_opts, cr.college_id, frozen=False,
                    on_change=lambda cid, cr=cr: (setattr(cr, "college_id", cid),
                                                  self._changed())), 1)
                # `lo=0`, because the user can DECREASE a College. ⚠ This is a usability
                # rule, not a printed rule. Crafts have the same rule
                # (`docs/status/edit-xp-merge.md`).
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

        # Permanent Resonance. It is the Abyssal Death's Taint counterpart to the temporary
        # track (p.41). Show it after the lock only, and only when the limit is not zero. A
        # limit above zero is how the engine reports that this character has the Flaw, and
        # it names no Merit id.
        # ⚠ This is the EDIT surface for that value. `qt/play.py` shows the same number
        # READ-ONLY and directs the user here, because a gain and a loss both go through
        # the XP ledger.
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

        # The Virtue Flaw. The splat controls it. The Dragon-Blooded, the Sidereals and the
        # Alchemicals have none. ⚠ A Limit track is a DIFFERENT question. A Sidereal has
        # Paradox and no flawed Virtue. Thus read `derive.has_virtue_flaw`. Do not read the
        # limit label.
        vf_row = QHBoxLayout()
        vf_row.setSpacing(24)
        self._body_lay.addLayout(vf_row)
        if derive.has_virtue_flaw(ruleset, char):
            vf = char.virtue_flaw
            vf_lay = self._panel("Virtue Flaw", vf_row)
            row = QHBoxLayout()
            row.addWidget(QLabel("Flawed Virtue"))
            opts = {v: _label(v.value) for v in VirtueName}
            # ⚠ Give this combo a NAME. Do not find it by position. This half of the page
            # holds three combos, and `findChildren(QComboBox)[0]` returns the Flawed
            # Virtue box to each of the three callers.
            virtue_combo = self._combo(
                opts, vf.virtue if vf else None, frozen=locked,
                placeholder="— none —",
                on_change=lambda v: v is not None and self.set_virtue_flaw_virtue(v))
            virtue_combo.setObjectName("virtue_flaw.virtue")
            row.addWidget(virtue_combo, 1)
            vf_lay.addLayout(row)

            # The SAMPLE Flaws of the book, for the Virtue that is flawed (pp.131-133). ⚠ A
            # Compassion Flaw next to a flawed Valor is an illegal pick. This list fills the
            # free-text field below. ⚠ It does not replace that field. The page states that
            # these are not the only Flaws that an Exalt can develop.
            samples = [f for f in ruleset.virtue_flaw_catalog.values()
                       if vf is not None and f.virtue == vf.virtue]
            if samples:
                row = QHBoxLayout()
                row.addWidget(QLabel("Sample Flaw"))
                sample_opts = {f.id: f.name
                               for f in sorted(samples, key=lambda f: f.name)}
                sample_combo = self._combo(
                    sample_opts, None, frozen=False,
                    placeholder="— fills the description —",
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

            # The user reads the Limit Break Condition at the table. Thus show it as its own
            # field. Do not put it in the description.
            picked = next((f for f in samples
                           if vf is not None and f.description == vf.description), None)
            if picked is not None and picked.limit_break:
                lb = QLabel(f"Limit Break: {picked.limit_break}")
                lb.setWordWrap(True)
                lb.setStyleSheet("color:#a8a5a0;")
                vf_lay.addWidget(lb)

        # The bonus health levels for each tier. ⚠ The stored list is a DIFFERENCE from the
        # printed track. Thus the box shows a TOTAL, and `engine/health_actions` calculates
        # the added levels or the removed levels from that total.
        hl_lay = self._panel("Bonus health levels per tier "
                             "(charms raise, curses lower)", vf_row)
        hl_row = QHBoxLayout()
        for p in health_actions.EDITABLE_TIERS:
            col = QVBoxLayout()
            col.addWidget(QLabel("-0" if p == 0 else str(p)))
            spin = QSpinBox()
            # ⚠ Give this box a NAME. Do not find it by position.
            # `findChildren(QSpinBox)[0]` returns a spin box of the Attributes panel.
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
