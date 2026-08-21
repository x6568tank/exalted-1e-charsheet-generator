"""Spike: the overhauled Edit tab as a native master-detail, Charms-style.

Throwaway — run to LOOK, then decide (the same deal as spikes/qt_tree and
spikes/qt_sheet). Loads a real character and renders the proposed layout:

  - a LEFT RAIL of sections (Identity / Attributes / Abilities / Crafts /
    Virtues / Essence) that are clicked through — the Charms tab's tab-bar pattern;
  - the selected section's trait rows on the right (real DotTracks bound to the
    character, real favoured-pick chips);
  - a TOP READOUT BAR with the budget/validation summary, whose "≡ details" is a
    click-to-open popover with the full issue list and bonus-point breakdown;
  - a BOTTOM STATUS STRIP (Willpower · pools · Soak).

It reuses qt/theme.py and qt/editor.py's widgets unchanged; nothing in
exalted_builder/ is edited. If the direction lands, a follow-up ports this layout
into exalted_builder/qt/editor.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QPushButton, QSpinBox, QStackedWidget,
    QTextEdit, QToolBar, QVBoxLayout, QWidget,
)

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.engine import derive, validate
from exalted_builder.models.character import (
    AbilityName, AttributeName, Character, VirtueName,
)
from exalted_builder.qt import theme as qtheme
from exalted_builder.qt.editor import DotTrack, _FavoredPicker
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

EXAMPLES = Path(exalted_builder.__file__).resolve().parent.parent / "examples"
MUTED = "#9a9894"
OK = "#15803d"
ERR = "#b91c1c"
WARN = "#b45309"


def _load_character(ruleset):
    """The spike's test character — a real chargen Solar from examples/, else a
    fresh one."""
    path = EXAMPLES / "ashes-of-dawn.character.json"
    if path.exists():
        try:
            return persistence.load_character(path, absorb_custom=False)
        except Exception:                                   # noqa: BLE001
            pass
    return Character(id="spike", exalt_type="Solar", caste="dawn")


class EditSpike(QMainWindow):
    """The whole app in the master-detail pattern — the Edit spike extended to a
    shell: a left rail of app tabs, a top toolbar, and the Edit content nested."""

    _APP_TABS = ("Identity", "Traits", "Gear", "Advantages", "Charms", "Combos",
                 "Play", "ST Options", "Custom", "Sheet")

    def __init__(self, ruleset, char):
        super().__init__()
        self._ruleset = ruleset
        self._char = char
        pal = theme.palette(char.exalt_type)
        qtheme.apply(self, pal)
        self._accent = qtheme.accent(pal)
        self.setWindowTitle(f"Builder spike — {pal.splat_label}")
        self.resize(1280, 820)

        # ---- top toolbar (the app's actions, accent-filled by the QSS) --- #
        tb = QToolBar("Actions")
        tb.setMovable(False)
        for name in ("New", "Load", "Save", "Print", "Finish && Lock", "Unlock"):
            tb.addAction(name, lambda: None)
        tb.addSeparator()
        tb.addAction("Party", lambda: None)
        self.addToolBar(tb)

        # ---- readout bar (app-level) ------------------------------------- #
        self.readout = QLabel("")
        self.readout.setStyleSheet(
            f"color:{self._accent}; font-weight:600; padding:4px 8px;")
        details = QPushButton("≡ details")
        details.setToolTip("Validation issues and the bonus-point breakdown")
        details.clicked.connect(self._open_popover)
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.readout, 1)
        bar.addWidget(details)

        # ---- app rail (left) + content stack ----------------------------- #
        self.app_rail = QListWidget()
        self.app_rail.setFixedWidth(170)
        self.app_rail.setStyleSheet(
            f"QListWidget {{ background:{qtheme.BG}; border:none; }}"
            f"QListWidget::item {{ padding:9px 12px; border-radius:4px; }}"
            f"QListWidget::item:hover {{ background:{qtheme.CARD}; }}"
            f"QListWidget::item:selected {{ background:{self._accent}; "
            f"color:#1a1a1a; font-weight:600; }}")
        for name in self._APP_TABS:
            self.app_rail.addItem(QListWidgetItem(name))

        self.app_stack = QStackedWidget()
        self._build_identity()
        self._build_traits()
        for tab in self._APP_TABS[2:]:
            self.app_stack.addWidget(self._placeholder(tab))
        self.app_rail.currentRowChanged.connect(self.app_stack.setCurrentIndex)
        self.app_rail.setCurrentRow(0)

        mid = QHBoxLayout()
        mid.setSpacing(8)
        mid.addWidget(self.app_rail)
        mid.addWidget(self.app_stack, 1)

        # ---- bottom status strip ------------------------------------------ #
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{MUTED}; padding:4px 8px;")

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        lay.addLayout(bar)
        lay.addLayout(mid, 1)
        lay.addWidget(self.status)
        self.setCentralWidget(central)
        self._refresh()

    def _placeholder(self, tab: str) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(12, 10, 12, 10)
        head = QLabel(tab)
        head.setStyleSheet(f"font-weight:bold; color:{self._accent}; font-size:13pt;")
        lay.addWidget(head)
        sub = QLabel("Ported in a later milestone — this spike shows the shell.")
        sub.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(sub)
        lay.addStretch(1)
        return page

    # ------------------------------------------------------------------ #
    # sections                                                            #
    # ------------------------------------------------------------------ #

    def _section(self) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)
        self.app_stack.addWidget(page)
        return page, lay

    def _heading(self, text: str) -> QLabel:
        """A section heading — the native accent title, like the Charms tab's."""
        head = QLabel(text)
        head.setStyleSheet(f"font-weight:bold; color:{self._accent}; "
                           f"font-size:13pt; margin-bottom:2px;")
        return head

    def _subheading(self, text: str) -> QLabel:
        """A sub-block header inside a section."""
        head = QLabel(text)
        head.setStyleSheet(f"font-weight:600; color:{self._accent}; "
                           f"margin-top:8px; margin-bottom:2px;")
        return head

    def _hrule(self) -> QFrame:
        """A thin muted rule separating sub-blocks."""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color:{MUTED}; background:{MUTED}; max-height:1px;")
        return line

    def _trait_dot(self, get, setv, lo, hi):
        return DotTrack(get, setv, lo, hi, accent=self._accent,
                        on_change=self._refresh)

    def _trait_row(self, label: str, track: DotTrack, mark: str = "") -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        m = QLabel(mark)
        m.setFixedWidth(12)
        m.setStyleSheet(f"color:{self._accent};")
        row.addWidget(m)
        name = QLabel(label)
        name.setMinimumWidth(84)
        row.addWidget(name, 1)
        row.addWidget(track)
        return row

    def _combo(self, options: dict, value, on_change) -> QComboBox:
        combo = QComboBox()
        for key, label in options.items():
            combo.addItem(label, key)
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        combo.currentIndexChanged.connect(lambda _: on_change(combo.currentData()))
        return combo

    def _build_identity(self):
        char, ruleset = self._char, self._ruleset
        page, lay = self._section()
        lay.addWidget(self._heading("Identity"))

        def field(label, text, on_change):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            edit = QLineEdit(text)
            edit.textChanged.connect(on_change)
            row.addWidget(edit, 1)
            lay.addLayout(row)
            return edit

        field("Name", char.name, lambda t: setattr(char, "name", t))
        field("Concept", char.concept, lambda t: setattr(char, "concept", t))
        field("Anima", char.anima, lambda t: setattr(char, "anima", t))

        ex_opts = {ex.id: ex.label for ex in ruleset.exalts.values()}
        ex_opts.setdefault(char.exalt_type, char.exalt_type)
        row = QHBoxLayout()
        row.addWidget(QLabel("Exalt type"))
        row.addWidget(self._combo(ex_opts, char.exalt_type, lambda v: None), 1)
        lay.addLayout(row)

        castes = {cd.id: cd.label for cd in ruleset.castes.values()
                  if cd.exalt_type == char.exalt_type}
        if castes:
            castes.setdefault(char.caste, char.caste)
            row = QHBoxLayout()
            row.addWidget(QLabel(ruleset.exalt_for(char.exalt_type).caste_noun))
            row.addWidget(self._combo(castes, char.caste, lambda v: None), 1)
            lay.addLayout(row)

        origins = viewmod._origin_options(ruleset, char)
        if origins:
            origins.setdefault(char.origin, char.origin)
            row = QHBoxLayout()
            row.addWidget(QLabel("Origin"))
            row.addWidget(self._combo(origins, char.origin, lambda v: None), 1)
            lay.addLayout(row)
            ups = viewmod.upbringing_options(char.exalt_type,
                                             char.origin or next(iter(origins)))
            if ups:
                row = QHBoxLayout()
                row.addWidget(QLabel("Upbringing"))
                value = char.upbringing if char.upbringing in ups else next(iter(ups))
                row.addWidget(self._combo(ups, value, lambda v: None), 1)
                lay.addLayout(row)

        # Nature (free-text, like the editor's)
        row = QHBoxLayout()
        row.addWidget(QLabel("Nature"))
        nature = QComboBox()
        nature.setEditable(True)
        for n in ruleset.nature_catalog.values():
            nature.addItem(n.name)
        if char.nature and nature.findText(char.nature) < 0:
            nature.addItem(char.nature)
        nature.setCurrentText(char.nature or "")
        nature.currentTextChanged.connect(lambda t: setattr(char, "nature", t))
        row.addWidget(nature, 1)
        lay.addLayout(row)

        # Free-fill biography — under the favoured picks. Local to the spike (the
        # Character model has no such fields yet; if the design lands, these need a
        # home or a notes surface).
        lay.addWidget(self._subheading("Biography"))
        for label in ("Sex", "Age", "Eye color", "Hair color", "Skin color",
                      "Height", "Weight"):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(QLineEdit(), 1)
            lay.addLayout(row)
        # "Backstory", not "Background" — Backgrounds are a real in-game mechanic.
        for label in ("Description", "Backstory"):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            edit = QTextEdit()
            edit.setFixedHeight(64)
            row.addWidget(edit, 1)
            lay.addLayout(row)
        # Misc notes
        row = QHBoxLayout()
        row.addWidget(QLabel("Notes"))
        notes = QTextEdit()
        notes.setFixedHeight(64)
        row.addWidget(notes, 1)
        lay.addLayout(row)

        # Caste / splat info — the description, caste abilities/attributes and anima
        # the original caste card carried; kept under the biography.
        lay.addWidget(self._subheading("Caste"))
        caste_def = ruleset.castes.get(char.caste)
        splat_has_castes = any(cd.exalt_type == char.exalt_type
                               for cd in ruleset.castes.values())
        noun = ruleset.exalt_for(char.exalt_type).caste_noun
        if caste_def:
            info = QLabel(f"{caste_def.label} {noun}")
            info.setStyleSheet(f"font-weight:600; color:{self._accent};")
            lay.addWidget(info)
            if caste_def.description:
                desc = QLabel(caste_def.description)
                desc.setWordWrap(True)
                desc.setStyleSheet(f"color:{MUTED};")
                lay.addWidget(desc)
            if caste_def.caste_attributes:
                line = QLabel(f"{noun} Attributes: " +
                              ", ".join(a.value.title() for a in caste_def.caste_attributes))
            elif caste_def.caste_abilities:
                line = QLabel(f"{noun} Abilities: " +
                              ", ".join(a.value.title() for a in caste_def.caste_abilities))
            else:
                line = None
            if line:
                line.setWordWrap(True)
                line.setStyleSheet(f"color:{MUTED}; font-style:italic;")
                lay.addWidget(line)
            if caste_def.anima_powers:
                anima = QLabel("Anima Power")
                anima.setStyleSheet(f"font-weight:600; color:{self._accent};")
                lay.addWidget(anima)
                ap = QLabel(caste_def.anima_powers)
                ap.setWordWrap(True)
                ap.setStyleSheet(f"color:{MUTED};")
                lay.addWidget(ap)
        elif splat_has_castes:
            lay.addWidget(QLabel("Unknown caste"))
        else:
            splat = QLabel(ruleset.exalt_for(char.exalt_type).label)
            splat.setStyleSheet(f"font-weight:600; color:{self._accent};")
            lay.addWidget(splat)
            lay.addWidget(QLabel("Not one of the Chosen — no caste, no Charms, "
                                 "Essence 1."))
        lay.addStretch(1)

    def _build_traits(self):
        char = self._char
        ruleset = self._ruleset
        page, lay = self._section()
        lay.addWidget(self._heading("Traits"))

        # Attributes — three columns under its own sub-header
        lay.addWidget(self._subheading("Attributes"))
        if viewmod.uses_caste_favored_attributes(ruleset, char):
            b = validate.effective_budgets(ruleset, char)
            opts = {a.value: _label(a) for a in AttributeName}
            label = QLabel(f"Favored Attributes (pick {b.attribute_favored_count})")
            label.setStyleSheet(f"color:{MUTED};")
            lay.addWidget(label)
            lay.addWidget(_FavoredPicker(
                opts, list(char.favored_attributes), b.attribute_favored_count,
                self._accent, lambda v: setattr(char, "favored_attributes", v)))
        rows = QHBoxLayout()
        rows.setSpacing(28)
        for cat, names in validate.ATTRIBUTE_CATEGORIES.items():
            col = QVBoxLayout()
            col.setSpacing(4)
            hdr = QLabel(cat)
            hdr.setStyleSheet(f"font-weight:600; color:{self._accent};")
            col.addWidget(hdr)
            for a in names:
                col.addLayout(self._trait_row(
                    a.value.title(),
                    self._trait_dot(lambda a=a: char.attributes[a],
                                    lambda v, a=a: setattr(char.attributes, a, v),
                                    1, 5)))
            rows.addLayout(col, 1)
        lay.addLayout(rows)

        # A rule, then Abilities under its own sub-header, the favoured picker
        # right above the actual list
        lay.addWidget(self._hrule())
        lay.addWidget(self._subheading("Abilities"))
        fav_n = validate.favored_ability_count(ruleset, char)
        if fav_n:
            opts = {a.value: _label(a) for a in AbilityName}
            label = QLabel(f"Favored abilities (pick {fav_n})")
            label.setStyleSheet(f"color:{MUTED};")
            lay.addWidget(label)
            lay.addWidget(_FavoredPicker(opts, list(char.favored_abilities), fav_n,
                                         self._accent,
                                         lambda v: setattr(char, "favored_abilities", v)))
        groups = viewmod.ability_group_defs(self._ruleset, char.exalt_type)
        for i in range(0, len(groups), 3):
            row = QHBoxLayout()
            row.setSpacing(28)
            for name, abilities in groups[i:i + 3]:
                col = QVBoxLayout()
                col.setSpacing(4)
                hdr = QLabel(name)
                hdr.setStyleSheet(f"font-weight:600; color:{self._accent};")
                col.addWidget(hdr)
                for a in abilities:
                    if a == AbilityName.CRAFT:
                        # Craft's dots live on its focuses — see the block below.
                        r = QHBoxLayout()
                        r.addWidget(QLabel("Craft"))
                        r.addStretch(1)
                        per = QLabel("↓ per-focus")
                        per.setStyleSheet(f"color:{MUTED};")
                        r.addWidget(per)
                        col.addLayout(r)
                        continue
                    col.addLayout(self._trait_row(
                        a.value.title(),
                        self._trait_dot(lambda a=a: char.abilities[a],
                                        lambda v, a=a: setattr(char.abilities, a, v),
                                        0, 5)))
                row.addLayout(col, 1)
            lay.addLayout(row)

        # Crafts — merged in here, same sub-heading treatment
        lay.addWidget(self._subheading("Crafts  (each focus a separate Ability)"))
        self._crafts_lay = QVBoxLayout()
        lay.addLayout(self._crafts_lay)
        add = QPushButton("+ Add craft")
        add.clicked.connect(self._add_craft)
        lay.addWidget(add)
        self._rebuild_crafts()

        # Virtues & Essence — its own sub-section, ruled off from the abilities.
        lay.addWidget(self._hrule())
        lay.addWidget(self._subheading("Virtues & Essence"))
        mid = QHBoxLayout()
        mid.setSpacing(28)
        vcol = QVBoxLayout()
        vcol.setSpacing(4)
        for v in VirtueName:
            vcol.addLayout(self._trait_row(
                v.value.title(),
                self._trait_dot(lambda v=v: char.virtues[v],
                                lambda val, v=v: setattr(char.virtues, v, val),
                                1, 5)))
        mid.addLayout(vcol, 1)
        ecol = QVBoxLayout()
        ecol.setSpacing(4)
        ecol.addLayout(self._trait_row(
            "Essence",
            self._trait_dot(lambda: char.essence_rating,
                            lambda v: setattr(char, "essence_rating", v),
                            1, 5)))
        if char.chargen_locked:
            wp = derive.willpower(char, self._ruleset)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"Willpower {wp}"))
            row.addStretch(1)
            row.addWidget(QLabel(f"+1 · XP"))
            ecol.addLayout(row)
        else:
            row = QHBoxLayout()
            row.addWidget(QLabel("Willpower purchased"))
            spin = QSpinBox()
            spin.setRange(0, 10)
            spin.setValue(char.willpower_purchased)
            spin.valueChanged.connect(lambda v: setattr(char, "willpower_purchased", v))
            row.addWidget(spin, 1)
            ecol.addLayout(row)
        mid.addLayout(ecol, 1)
        lay.addLayout(mid)
        lay.addStretch(1)

    def _rebuild_crafts(self):
        char = self._char
        while self._crafts_lay.count():
            item = self._crafts_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        for i, cr in enumerate(char.crafts):
            row = QHBoxLayout()
            focus = QLineEdit(cr.focus)
            focus.setPlaceholderText("craft (e.g. Smithing)")
            focus.textChanged.connect(lambda t, c=cr: setattr(c, "focus", t))
            row.addWidget(focus, 1)
            row.addWidget(self._trait_dot(lambda c=cr: c.rating,
                                          lambda v, c=cr: setattr(c, "rating", v),
                                          0, 5))
            rm = QPushButton("✕")
            rm.clicked.connect(lambda _=None, idx=i: self._remove_craft(idx))
            row.addWidget(rm)
            self._crafts_lay.addLayout(row)

    def _add_craft(self):
        from exalted_builder.models.character import CraftRating
        self._char.crafts.append(CraftRating(focus="", rating=1))
        self._rebuild_crafts()

    def _remove_craft(self, idx: int):
        del self._char.crafts[idx]
        self._rebuild_crafts()

    # ------------------------------------------------------------------ #
    # readout + popover + status                                          #
    # ------------------------------------------------------------------ #

    def _refresh(self):
        """Budget line + validation status on the readout bar; the status strip."""
        ruleset, char = self._ruleset, self._char
        view = viewmod.build_sheet_view(ruleset, char)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        status = "✓ Legal" if not errors else f"✗ {len(errors)} error(s)"
        self.readout.setText(f"{bp} · {status}")
        self.status.setText(
            f"Willpower {view.willpower} · {view.essence_pool_label()} · "
            f"Soak B{view.soak.bashing} / L{view.soak.lethal} / A{view.soak.aggravated}")

    def _open_popover(self):
        """The click-to-open panel: full issue list + bonus-point breakdown."""
        ruleset, char = self._ruleset, self._char
        view = viewmod.build_sheet_view(ruleset, char)
        dialog = QDialog(self)
        dialog.setWindowTitle("Validation & bonus points")
        lay = QVBoxLayout(dialog)
        lay.setSpacing(4)
        errors = [i for i in view.issues if i.severity == "error"]
        head = QLabel("✓ Legal" if not errors else f"✗ {len(errors)} error(s)")
        head.setStyleSheet(f"font-weight:700; color:{OK if not errors else ERR};")
        lay.addWidget(head)
        for issue in view.issues:
            if issue.code in ("bonus-points", "xp-summary"):
                continue
            color = ERR if issue.severity == "error" else \
                    WARN if issue.severity == "warning" else MUTED
            line = QLabel(f"• {issue.message}")
            line.setWordWrap(True)
            line.setStyleSheet(f"color:{color};")
            lay.addWidget(line)
        bd = validate.bonus_point_breakdown(ruleset, char)
        sep = QLabel("─" * 36)
        sep.setStyleSheet(f"color:{MUTED};")
        lay.addWidget(sep)
        total = QLabel(f"Bonus Points  {bd.total} / {bd.available} spent")
        total.setStyleSheet(f"font-weight:600; color:{ERR if bd.over_budget else OK};")
        lay.addWidget(total)
        for line in bd.lines:
            row = QHBoxLayout()
            domain = QLabel(line.domain)
            if not line.points:
                domain.setStyleSheet(f"color:{MUTED};")
            row.addWidget(domain, 1)
            pts = QLabel(str(line.points))
            if not line.points:
                pts.setStyleSheet(f"color:{MUTED};")
            row.addWidget(pts)
            lay.addLayout(row)
        done = QPushButton("Done")
        done.clicked.connect(dialog.accept)
        lay.addWidget(done)
        dialog.exec()


def _label(value: str) -> str:
    return value.replace("_", " ").title()


def main() -> int:
    app = QApplication(sys.argv)
    ruleset = rules_db.load_app_ruleset(
        Path(exalted_builder.__file__).parent / "data")
    char = _load_character(ruleset)
    win = EditSpike(ruleset, char)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
