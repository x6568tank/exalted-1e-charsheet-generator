"""exalted_builder/qt/gear.py — the Gear tab: everything the character OWNS.

Input: a RuleSet and the shared context's Character. Output: one scrollable surface
carrying the inventory (every owned row, filterable, each expanding to the editor for
its kind), the Buy shop, the artifacts budget panel and the services price list.
Mechanism: `reload()` rebuilds the body; a row's editor is built on first expand and
torn down on collapse, and anything a keystroke touches writes straight to the model
and re-syncs only its own labels.

⚠ Keep the four lists on ONE tab. Splitting an artifact daiklave's STATS onto one
surface and its BUDGET onto another is what let the same object be entered twice and
charged twice (`docs/status/rated-artifacts.md`).

Zero game logic. Every mutation goes through `engine.gear_actions`, every derived list
and every line of text through `ui/view.py` — the milestone-2 question was asked of
this tab before it was ported and the answer was yes, unlike Advantages.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSpinBox,
    QVBoxLayout, QWidget,
)

from exalted_builder import custom_content as customs
from exalted_builder.engine import (artifacts as artifactsmod, derive as derivemod,
                                    gear_actions, validate)
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

from .catalogue import CatalogueDialog
from .editor import _FilterCombo, _Panel
from .theme import MUTED, accent as accent_light

# The issue codes this tab can do something about. ⚠ Artifact findings belong HERE,
# with the panel that produces them — a report sitting on a surface that no longer
# edits the thing it reports about is the house bug in UI form. The Advantages tab
# renders the same findings beside the Artifact Background; one issue list, so the two
# cannot disagree.
_MY_ISSUES = ("artifact", "hearthstone")

# The per-kind stat editors, as `(field, label, signed)`. A table rather than fifteen
# hand-built spin boxes, so the two kinds cannot drift in layout or in bounds.
#
# ⚠ `mobility_penalty` is stored NEGATIVE (`docs/status/gear-and-inventory.md`), so it
# is signed and its floor is below zero. A consumer that reads it as a magnitude adds
# dice instead of removing them.
_WEAPON_STATS = (("speed", "Spd", True), ("accuracy", "Acc", True),
                 ("damage", "Dmg", True), ("defense", "Def", True),
                 ("rate", "Rate", False), ("range", "Rng", False),
                 ("min_strength", "Min Str", False),
                 ("min_dexterity", "Min Dex", False),
                 ("min_martial_arts", "Min MA", False),
                 ("max_strength", "Max Str", False),
                 ("artifact_rating", "Art", False), ("attunement", "Attune", False),
                 ("resources_cost", "Res", False))

_ARMOR_STATS = (("soak_lethal", "Soak L", False), ("soak_bashing", "Soak B", False),
                ("mobility_penalty", "Mob", True), ("fatigue", "Ftg", False),
                ("artifact_rating", "Art", False), ("attunement", "Attune", False),
                ("resources_cost", "Res", False))

_SHOP_SUBTITLE = ("Everything a book prices, against your Resources, plus your own "
                  "library. Nothing is deducted — the cost is a hint (core p.325).")

_RES_TOOLTIP = ("The Resources rating needed to buy one (M&C p.123). A record of the "
                "price, not a trait.")


class GearPage(QWidget):
    """The tab widget. `reload()` rebuilds the body for the character in ctx; `notify`
    surfaces transient messages; `on_change` pings the shell so its readout bar and
    status strip re-derive."""

    def __init__(self, ruleset, ctx, *, notify=None, on_change=None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx
        self._notify = notify or (lambda text, kind="info": None)
        self._on_change = on_change
        self._filter = "all"
        # Which inventory rows are expanded, keyed by `(list_name, index)` so the set
        # survives a rebuild. ⚠ Keyed on POSITION, and a delete shifts every later row —
        # so `_changed` clears it rather than leaving a stale key pointing at whatever
        # slid into that slot.
        self._open_rows: set[tuple[str, int]] = set()

        self.readout = QLabel("")
        self.readout.setWordWrap(True)
        self.readout.setContentsMargins(8, 4, 8, 4)

        self._body_container = QWidget()
        self._body_lay = QVBoxLayout(self._body_container)
        self._body_lay.setContentsMargins(0, 0, 0, 0)
        self._body_lay.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._body_container)
        self._scroll = scroll

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.readout)
        outer.addWidget(scroll, 1)
        self.reload()

    # ------------------------------------------------------------------ #
    # plumbing
    # ------------------------------------------------------------------ #

    def _char(self):
        return self._ctx["char"]

    def _pal(self):
        return theme.palette(self._char().exalt_type)

    def _accent(self) -> str:
        return accent_light(self._pal())

    def _clear_lay(self, lay) -> None:
        """Remove every widget/layout from `lay` and detach it NOW.

        ⚠ RECURSES into nested layouts: `item.widget()` is None for a `QLayout`, so a
        widget-only sweep detaches nothing inside a row and the previous build paints
        ON TOP of the next. ⚠ `deleteLater()` alone is deferred to the event loop, so
        hide and unparent now. (The same shape as the Edit, Charms and Advantages tabs —
        this has bitten three times; copy it, do not write a fresh loop.)
        """
        while lay.count():
            item = lay.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                self._clear_lay(item.layout())

    def reload(self) -> None:
        self._clear_lay(self._body_lay)
        self._build_body()
        self._body_lay.addStretch(1)
        self._sync_readout()

    def _rebuild(self) -> None:
        """A change that moved the LISTS — rebuild the body and ping the shell.

        ⚠ Clears the expanded-row set first. Those keys are positions, and adding or
        deleting a row renumbers every row after it, so a surviving key would re-open
        whatever slid into that slot.
        """
        self._open_rows.clear()
        self.reload()
        if self._on_change is not None:
            self._on_change()

    def _changed(self) -> None:
        """A change that only moves the readouts — a stat edit, a rename, a quantity."""
        self._sync_readout()
        if self._on_change is not None:
            self._on_change()

    def _sync_readout(self) -> None:
        ruleset, char = self._ruleset, self._char()
        rows = viewmod.inventory_rows(ruleset, char)
        res = validate.effective_background_rating(ruleset, char, "Resources")
        bits = [f"{len(rows)} items owned",
                f"Resources {'•' * res if res else '—'}"]
        issues = [i for i in viewmod.build_sheet_view(ruleset, char).issues
                  if any(k in i.code for k in _MY_ISSUES)]
        self.readout.setText(" · ".join(bits)
                             + ("" if not issues
                                else "\n" + "\n".join(f"• {i.message}" for i in issues)))
        worst = ("#b91c1c" if any(i.severity == "error" for i in issues)
                 else "#b45309" if issues else self._accent())
        self.readout.setStyleSheet(f"color:{worst};")

    def _panel(self, title: str, parent_lay=None) -> QVBoxLayout:
        card = _Panel(title, self._pal())
        (parent_lay if parent_lay is not None else self._body_lay).addWidget(card)
        return card.body()

    def _muted(self, text: str, *, italic: bool = False) -> QLabel:
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(f"color:{MUTED};"
                            + (" font-style:italic;" if italic else ""))
        return label

    # ------------------------------------------------------------------ #
    # body
    # ------------------------------------------------------------------ #

    def _build_body(self) -> None:
        self._inventory_panel()
        self._buy_row()
        self._artifacts_panel()
        self._prices_panel()

    # ---- inventory ---------------------------------------------------- #

    def _inventory_panel(self) -> None:
        ruleset, char = self._ruleset, self._char()
        rows = viewmod.inventory_rows(ruleset, char)
        counts = viewmod.inventory_counts(rows)
        lay = self._panel(viewmod.inventory_heading(rows, counts, self._filter))
        if not rows:
            lay.addWidget(self._muted(
                "Nothing owned yet — Buy below, or add something of your own."))
            return

        chips = QHBoxLayout()
        for kind in viewmod.INVENTORY_FILTERS:
            n = counts.get(kind, 0)
            if kind != "all" and not n:
                continue          # an empty filter is noise, not a choice
            chip = QPushButton(viewmod.inventory_filter_label(kind, n))
            chip.setCheckable(True)
            chip.setChecked(kind == self._filter)
            chip.clicked.connect(lambda _c=False, k=kind: self._set_filter(k))
            chips.addWidget(chip)
        chips.addStretch(1)
        lay.addLayout(chips)
        # ⚠ The counts SUM TO MORE than the row count whenever anything overlaps — an
        # artifact daiklave is both a weapon and an artifact — and that is correct. The
        # filters are not a partition.
        for row in viewmod.filter_inventory(rows, self._filter):
            self._inventory_row(lay, row)

    def _set_filter(self, kind: str) -> None:
        self._filter = kind
        self.reload()

    def _inventory_row(self, lay, row) -> None:
        """One owned thing: its summary line, and an Edit toggle that reveals the
        editor for its kind.

        ⚠ Each row carries its OWN editor. There are no per-kind panels (human's call,
        2026-08-13): an inventory beside three panels editing the same objects is four
        surfaces for one job, and the list is the only one that can show a daiklave as
        both weapon and artifact. `row.list_name` / `row.index` are what make it
        possible — the view records where each row came FROM.
        """
        head = QHBoxLayout()
        name = QLabel(row.name or "—")
        name.setStyleSheet("font-weight:600;")
        head.addWidget(name)
        if row.quantity > 1:
            head.addWidget(self._muted(f"×{row.quantity}"))
        detail = QLabel(row.detail)
        detail.setStyleSheet(f"color:{MUTED};")
        head.addWidget(detail, 1)
        for tag in viewmod.inventory_row_tags(row):
            chip = QLabel(tag)
            chip.setStyleSheet(f"color:{self._accent()};")
            head.addWidget(chip)
        if row.resources_cost:
            res = QLabel("Res " + "•" * row.resources_cost)
            res.setStyleSheet(f"color:{MUTED};")
            res.setToolTip(_RES_TOOLTIP)
            head.addWidget(res)

        key = (row.list_name, row.index)
        toggle = QPushButton("Edit")
        toggle.setCheckable(True)
        toggle.setChecked(key in self._open_rows)
        head.addWidget(toggle)
        lay.addLayout(head)

        editor_box = QWidget()
        editor_lay = QVBoxLayout(editor_box)
        editor_lay.setContentsMargins(16, 0, 0, 6)
        lay.addWidget(editor_box)

        def sync_editor(open_: bool) -> None:
            # Built on expand and torn down on collapse. Eager construction would put
            # a dozen spin boxes behind every row in a long inventory, which is the
            # cost the Charms tab already paid once.
            self._clear_lay(editor_lay)
            editor_box.setVisible(open_)
            if not open_:
                self._open_rows.discard(key)
                return
            self._open_rows.add(key)
            self._row_editor(editor_lay, row.list_name, row.index)
            # A merged row is one object with TWO stored halves — the artifact and the
            # stat line `grant_gear` stamped for it — so its editor is both, under one
            # Edit. ⚠ Without this the stat line is uneditable: there are no per-kind
            # panels, and the merged row is the only place it appears.
            if row.linked_list_name:
                editor_lay.addWidget(self._muted("Stat line"))
                self._row_editor(editor_lay, row.linked_list_name, row.linked_index)

        toggle.toggled.connect(sync_editor)
        sync_editor(toggle.isChecked())

    def _row_editor(self, lay, list_name: str, index: int) -> None:
        owner = getattr(self._char(), list_name)
        if not (0 <= index < len(owner)):
            return
        item = owner[index]
        builder = {"weapons": self._weapon_editor, "armor": self._armor_editor,
                   "gear": self._goods_editor, "artifacts": self._artifact_editor}
        builder[list_name](lay, index, item)

    # ---- the per-kind editors ------------------------------------------ #

    def _delete_button(self, list_name: str, index: int) -> QPushButton:
        button = QPushButton("Delete")
        button.setToolTip("Deleting a row IS selling it — core p.145 prints no rate "
                          "for a sale, so nothing is refunded.")
        if list_name == "artifacts":
            button.clicked.connect(
                lambda: (gear_actions.remove_artifact(self._char(), index),
                         self._rebuild()))
        else:
            button.clicked.connect(
                lambda: (gear_actions.remove_row(self._char(), list_name, index),
                         self._rebuild()))
        return button

    def _library_button(self, kind: str, item) -> QPushButton:
        button = QPushButton("Save to library")
        button.setToolTip("Save to my library — it becomes buyable for every character")
        button.clicked.connect(lambda: self._save_to_library(kind, item))
        return button

    def _save_to_library(self, kind: str, item) -> None:
        """Put this row in the user's library so every future character can buy it."""
        try:
            customs.save_gear_row(kind, gear_actions.library_payload(kind, item),
                                  reserved_ids=gear_actions.reserved_ids(self._ruleset))
        except customs.CustomContentError as ex:
            self._notify(str(ex), "warning")
            return
        # ⚠ The armour default is SAID OUT LOUD rather than guessed silently: a
        # character's armour row carries no weight and `ArmorType` requires one.
        extra = " (armour weight defaults to Light)" if kind == "armor" else ""
        self._notify(f"Saved {item.name} to your library{extra}. It will appear in Buy "
                     f"the next time the app loads its rules.", "positive")

    def _stat_row(self, lay, item, specs, resync) -> None:
        """A grid of spin boxes over `specs`, each writing its field and re-running
        `resync` so the summary line beside the row tracks the edit live."""
        row = QHBoxLayout()
        for field, label, signed in specs:
            caption = QLabel(label)
            caption.setStyleSheet(f"color:{MUTED};")
            row.addWidget(caption)
            spin = QSpinBox()
            # Named after the field it writes, so a test addresses the stat it means
            # rather than a position in the child list — the head row's quantity box is
            # a QSpinBox too, and indexing found that one first.
            spin.setObjectName(f"stat.{field}")
            spin.setRange(-20 if signed else 0, 99)
            spin.setValue(getattr(item, field))
            # No inline stylesheet: the window QSS names QSpinBox, and setting only
            # `background` here would win and drop its colour, padding and radius.
            # (Advantages does the same and is human-verified inside a `_Panel`.)
            spin.valueChanged.connect(
                lambda v, f=field: (setattr(item, f, v), resync(), self._changed()))
            row.addWidget(spin)
        row.addStretch(1)
        lay.addLayout(row)

    def _material_combo(self, item, resync) -> QComboBox:
        """The magical material. "" is mundane; the bonus applies only for the matching
        Exalt (p.341), which `derive.applied_material` decides — not this combo."""
        combo = QComboBox()
        combo.addItem("— none —", "")
        for material in self._ruleset.material_catalog.values():
            combo.addItem(material.name, material.id)
        combo.setCurrentIndex(max(0, combo.findData(item.material or "")))
        combo.currentIndexChanged.connect(
            lambda _i: (setattr(item, "material", combo.currentData() or ""),
                        resync(), self._changed()))
        return combo

    def _name_combo(self, names, current, on_pick) -> _FilterCombo:
        """An editable combo over a catalogue: pick an entry to autofill, or type a name
        the catalogue does not hold. Free text is a rename, never a failed lookup.

        ⚠ Fires only when the text actually CHANGED. `editingFinished` fires on every
        focus loss, and `on_pick` rebuilds the body — so tabbing past an untouched combo
        would collapse the row the player is working in, for no edit at all.
        """
        combo = _FilterCombo()
        combo.setEditable(True)
        combo.addItems(names)
        combo.setCurrentText(current or "")
        seen = {"text": current or ""}

        def fire() -> None:
            text = combo.currentText()
            if text == seen["text"]:
                return
            seen["text"] = text
            on_pick(text)

        combo.lineEdit().editingFinished.connect(fire)
        combo.activated.connect(lambda _i: fire())
        return combo

    def _weapon_editor(self, lay, index, weapon) -> None:
        ruleset, char = self._ruleset, self._char()
        summary = QLabel("")
        summary.setStyleSheet(f"color:{MUTED};")

        def resync() -> None:
            # The EFFECTIVE stats (material folded in) and the wielder's material tag —
            # `view.weapon_stat_line` is the one copy of the format, shared with the
            # shop's pre-pick rows.
            material = derivemod.applied_material(ruleset, char, weapon)
            summary.setText(viewmod.weapon_stat_line(
                derivemod.effective_weapon(ruleset, char, weapon),
                material=material.name if material else ""))

        head = QHBoxLayout()
        names = [w.name for w in ruleset.weapon_catalog.values()]
        head.addWidget(self._name_combo(
            names, weapon.name,
            lambda text: (gear_actions.set_weapon(ruleset, char, index, text),
                          self._rebuild())), 1)
        head.addWidget(summary)
        qty = QLabel("Qty")
        qty.setStyleSheet(f"color:{MUTED};")
        head.addWidget(qty)
        # Stackable gear. Ammunition is the case that put it here — a player holds
        # arrows by the score — but nothing stops a stack of javelins. It is a COUNT
        # and nothing more: no engine reads it, because nothing derives an attack
        # (decision 0008).
        spin = QSpinBox()
        spin.setRange(1, 999)
        spin.setValue(weapon.quantity)
        spin.valueChanged.connect(
            lambda v: (setattr(weapon, "quantity", v), self._changed()))
        head.addWidget(spin)
        head.addWidget(self._library_button("weapons", weapon))
        head.addWidget(self._delete_button("weapons", index))
        lay.addLayout(head)

        self._stat_row(lay, weapon, _WEAPON_STATS[:6], resync)
        self._stat_row(lay, weapon, _WEAPON_STATS[6:], resync)

        tail = QHBoxLayout()
        dtype = QComboBox()
        dtype.addItems(["L", "B"])
        dtype.setCurrentText(weapon.damage_type or "L")
        dtype.currentTextChanged.connect(
            lambda t: (setattr(weapon, "damage_type", t or "L"), resync(),
                       self._changed()))
        tail.addWidget(QLabel("Type"))
        tail.addWidget(dtype)
        tail.addWidget(QLabel("Material"))
        tail.addWidget(self._material_combo(weapon, resync))
        notes = QLineEdit(weapon.notes)
        notes.setPlaceholderText("notes")
        notes.textChanged.connect(
            lambda t: (setattr(weapon, "notes", t), self._changed()))
        tail.addWidget(notes, 1)
        lay.addLayout(tail)
        resync()

    def _armor_editor(self, lay, index, armor) -> None:
        ruleset, char = self._ruleset, self._char()
        summary = QLabel("")
        summary.setStyleSheet(f"color:{MUTED};")

        def resync() -> None:
            material = derivemod.applied_material(ruleset, char, armor)
            summary.setText(viewmod.armor_stat_line(
                derivemod.effective_armor(ruleset, char, armor),
                material=material.name if material else ""))

        head = QHBoxLayout()
        names = [a.name for a in ruleset.armor_catalog.values()]
        head.addWidget(self._name_combo(
            names, armor.name,
            lambda text: (gear_actions.set_armor(ruleset, char, index, text),
                          self._rebuild())), 1)
        head.addWidget(summary)
        head.addWidget(self._library_button("armor", armor))
        head.addWidget(self._delete_button("armor", index))
        lay.addLayout(head)

        self._stat_row(lay, armor, _ARMOR_STATS, resync)
        tail = QHBoxLayout()
        tail.addWidget(QLabel("Material"))
        tail.addWidget(self._material_combo(armor, resync))
        tail.addStretch(1)
        lay.addLayout(tail)
        resync()

    def _goods_editor(self, lay, index, item) -> None:
        head = QHBoxLayout()
        name = QLineEdit(item.name)
        name.setPlaceholderText("item")
        name.textChanged.connect(
            lambda t: (setattr(item, "name", t), self._changed()))
        head.addWidget(name, 1)
        qty = QLabel("Qty")
        qty.setStyleSheet(f"color:{MUTED};")
        head.addWidget(qty)
        spin = QSpinBox()
        spin.setRange(1, 999)
        spin.setValue(item.quantity)
        spin.valueChanged.connect(
            lambda v: (setattr(item, "quantity", v), self._changed()))
        head.addWidget(spin)
        # LABELLED. A bare "•••" beside an item is unreadable — the browser asked what
        # it meant (2026-08-13), and every other dot column on the sheet is a rated
        # trait, which this is not: it is what the thing COST.
        res = QLabel(f"Res {'•' * item.resources_cost}" if item.resources_cost
                     else "Res —")
        res.setStyleSheet(f"color:{MUTED};")
        res.setToolTip(_RES_TOOLTIP)
        head.addWidget(res)
        head.addWidget(self._library_button("gear", item))
        head.addWidget(self._delete_button("gear", index))
        lay.addLayout(head)

        note = QLineEdit(item.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t: (setattr(item, "note", t), self._changed()))
        lay.addWidget(note)

    def _artifact_editor(self, lay, index, artifact) -> None:
        ruleset, char = self._ruleset, self._char()
        catalog = artifactsmod.purchasable_artifacts(ruleset.artifact_catalog, char)
        description = QLabel("")
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{MUTED};")

        rating = QSpinBox()
        rating.setRange(1, 5)
        rating.setValue(artifact.rating)

        def sync_description() -> None:
            entry = next((a for a in catalog if a.name == artifact.name), None)
            description.setText(entry.description if entry else "")
            description.setVisible(bool(description.text()))

        def on_name(text: str) -> None:
            if gear_actions.set_artifact(ruleset, char, index, text):
                # A catalogue pick may have granted a stat line and changed the budget,
                # so the whole body goes — but the spin box is pushed first so the
                # rebuild reads the new rating rather than the stale one.
                rating.setValue(artifact.rating)
                self._rebuild()
                return
            sync_description()
            self._changed()

        head = QHBoxLayout()
        head.addWidget(self._name_combo(
            [a.name for a in catalog], artifact.name, on_name), 1)
        note = QLineEdit(artifact.note)
        note.setPlaceholderText("note")
        note.textChanged.connect(
            lambda t: (setattr(artifact, "note", t), self._changed()))
        head.addWidget(note, 1)
        head.addWidget(QLabel("Rating"))
        rating.valueChanged.connect(
            lambda v: (setattr(artifact, "rating", v), self._changed()))
        head.addWidget(rating)
        # How it was acquired. POST-LOCK ONLY: at creation the Background is the only
        # channel there is (core p.342, "to start the game owning"), so offering the
        # choice would be offering an illegal pick. `validate` bars it either way; this
        # stops the player reaching the bar.
        if char.chargen_locked:
            acquired = QComboBox()
            for value, label in ((artifactsmod.ACQUIRED_BACKGROUND, "Background"),
                                 (artifactsmod.ACQUIRED_PURCHASED, "Bought"),
                                 (artifactsmod.ACQUIRED_LEGENDARY, "Merit")):
                acquired.addItem(label, value)
            acquired.setCurrentIndex(max(0, acquired.findData(artifact.acquired)))
            acquired.currentIndexChanged.connect(
                lambda _i: (setattr(artifact, "acquired",
                                    acquired.currentData()
                                    or artifactsmod.ACQUIRED_BACKGROUND),
                            self._rebuild()))
            head.addWidget(QLabel("Acquired"))
            head.addWidget(acquired)
        head.addWidget(self._library_button("artifacts", artifact))
        head.addWidget(self._delete_button("artifacts", index))
        lay.addLayout(head)
        lay.addWidget(description)
        sync_description()

    # ---- Buy ------------------------------------------------------------ #

    def _buy_row(self) -> None:
        row = QHBoxLayout()
        button = QPushButton("Buy")
        button.setObjectName("buyButton")
        button.clicked.connect(self._open_shop)
        row.addWidget(button)
        row.addWidget(self._muted(
            "Weapons, armour and goods — everything a book prices."), 1)
        self._body_lay.addLayout(row)

    def _build_shop_dialog(self) -> CatalogueDialog:
        """One shop over every priced catalogue, BUILT but not run.

        ⚠ It replaced four per-panel dialogs, which were four shops; the kind rides in
        the row KEY so one dialog appends to four differently typed lists
        (`gear_actions.buy` reads it back).

        Split from `_open_shop` because `exec()` blocks a headless run, so this is the
        seam the tests drive — the same shape `AdvantagesPage` uses.
        """
        shop = viewmod.shop_rows(self._ruleset, self._char())
        return CatalogueDialog(
            self._pal(), "Buy",
            [(r.key, r.name, r.summary, r.full) for r in shop],
            self._buy,
            subtitle=_SHOP_SUBTITLE,
            group_of={r.key: r.group for r in shop},
            dimmed={r.key for r in shop if r.affordability == "unaffordable"},
            custom_kinds=viewmod.shop_custom_kinds(self._char()),
            parent=self)

    def _open_shop(self) -> None:
        self._build_shop_dialog().exec()

    def _buy(self, key) -> None:
        message = gear_actions.buy(self._ruleset, self._char(), key or "")
        if message:
            self._notify(message, "positive")
        self._rebuild()

    # ---- artifacts -------------------------------------------------------- #

    def _artifacts_panel(self) -> None:
        """The standalone artifacts — those that are neither weapon nor armour — under
        the budget line that governs them.

        ⚠ Artifact weapons and armour are NOT edited here; they are equipment, and they
        appear in the inventory above. They are only COUNTED, which the "also counted"
        line says out loud so the combined total does not look wrong.
        """
        char = self._char()
        lay = self._panel(viewmod.artifacts_header(self._ruleset, char))
        lay.addWidget(self._muted("bought with the Artifact Background"))
        bought = viewmod.artifacts_bought_note(char)
        if bought:
            lay.addWidget(self._muted(bought))
        also = viewmod.artifacts_also_counted(char)
        if also:
            lay.addWidget(self._muted(also, italic=True))
        add = QPushButton("+ Add artifact")
        add.clicked.connect(self._open_artifact_catalogue)
        lay.addWidget(add)

    def _build_artifact_dialog(self) -> CatalogueDialog:
        # ⚠ Recomputed per OPEN, never captured. The list depends on character state
        # that changes on ANOTHER tab — taking or dropping the Legendary Artifact Merit
        # — and a captured copy is the stale-closure trap verbatim: a player takes the
        # Merit, comes back, and the artifact she just paid ten bonus points for is not
        # in the list.
        catalog = artifactsmod.purchasable_artifacts(
            self._ruleset.artifact_catalog, self._char())
        rows = [(a.name, a.name, f"{a.rating_notes or ('•' * a.rating)} — "
                 f"{a.description}", a.description) for a in catalog]
        return CatalogueDialog(self._pal(), "Artifacts", rows, self._pick_artifact,
                               custom_label="Custom artifact", parent=self)

    def _open_artifact_catalogue(self) -> None:
        self._build_artifact_dialog().exec()

    def _pick_artifact(self, name) -> None:
        gear_actions.add_artifact(self._ruleset, self._char(), name)
        self._rebuild()

    # ---- the services price list ------------------------------------------ #

    def _prices_panel(self) -> None:
        """The other half of the same tables, and NOT inventory: upkeep, events,
        commissions and rentals.

        ⚠ A character does not carry a month of stabling in her pack, so these are a
        price list she can consult and never own (human's ruling 2026-08-13) — the
        ruling holds at the OFFER too, which is why `view.shop_rows` skips them.
        """
        services = viewmod.service_rows(self._ruleset, self._char())
        if not services:
            return
        lay = self._panel("Prices — services & upkeep")
        lay.addWidget(self._muted(
            "Reference only — not owned, and nothing here is tracked. Jade and silver "
            "are the printed equivalents (M&C p.123); the conversion is the "
            "Storyteller's call, so nothing is computed from them."))
        last_category = ""
        for category, name, dots, cash, notes, affordable in services:
            if category != last_category:
                last_category = category
                heading = QLabel(category)
                heading.setStyleSheet(f"font-weight:600; color:{self._accent()};")
                lay.addWidget(heading)
            row = QHBoxLayout()
            dot_label = QLabel("•" * dots)
            dot_label.setMinimumWidth(56)
            row.addWidget(dot_label)
            name_label = QLabel(name)
            row.addWidget(name_label, 1)
            if cash:
                # ⚠ `GearType.cash` is reference text, never arithmetic. M&C p.122 says
                # outright that the Resources ladder is not linear and converting it is
                # a Storyteller judgement, so this is printed verbatim and nothing
                # computes from it. It is also this panel's whole point: a PRICE list
                # showing no prices is the house bug, and it shipped that way once.
                cash_label = QLabel(cash)
                cash_label.setStyleSheet(f"color:{MUTED};")
                row.addWidget(cash_label)
            if not affordable:
                for widget in (dot_label, name_label):
                    widget.setStyleSheet(f"color:{MUTED};")
            lay.addLayout(row)
            if notes:
                lay.addWidget(self._muted(notes, italic=True))
