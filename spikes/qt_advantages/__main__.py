"""Advantages layout spike — four shapes for one tab, on one character.

Run: `.venv/bin/python -m spikes.qt_advantages [path/to/character.json]`

A top tab bar switches between the SHIPPED Advantages page and three candidate
redesigns, all reading the same live character, so the comparison is direct rather
than remembered. Nothing in `exalted_builder/` is edited; the shipped tab is the real
`qt.advantages.AdvantagesPage`.

⚠ The three candidates are LAYOUT MOCKUPS. They render real data and their controls
move, but they do not buy, price or validate anything — the point is the shape, and
wiring three throwaway surfaces to `engine.advancement` would cost more than the
answer is worth. Read them as "what would this feel like", not "does this work".
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFormLayout, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QScrollArea, QSpinBox, QSplitter,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.engine import merits as meritsmod, validate
from exalted_builder.models.character import Character
from exalted_builder.qt import theme as qtheme
from exalted_builder.qt.advantages import AdvantagesPage
from exalted_builder.qt.editor import DotTrack
from exalted_builder.qt.theme import CARD, MUTED, accent as accent_light
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

DEFAULT = (Path(exalted_builder.__file__).parent.parent / "examples"
           / "ashes-of-dawn.character.json")


# --------------------------------------------------------------------------- #
# the rows every candidate renders — one derivation, so the four shapes differ
# only in LAYOUT and a difference on screen is never a difference in data
# --------------------------------------------------------------------------- #

def advantage_rows(ruleset, character) -> list[dict]:
    """Everything this tab owns, flattened: Backgrounds, M&F, Fetters, Passions."""
    rows: list[dict] = []
    for index, bg in enumerate(character.backgrounds):
        rows.append({"kind": "Background", "name": bg.name or "—",
                     "rating": bg.rating, "cost": "", "note": bg.note,
                     "obj": bg, "index": index, "list": "backgrounds"})
    for index, mp in enumerate(character.merits_flaws):
        definition = ruleset.merits_flaws.get(mp.merit_id)
        # ⚠ The custom-row discriminator is the EMPTY merit_id, never custom_name's
        # truthiness — the name box writes that field on every keystroke.
        name = (definition.name if definition is not None
                else (mp.custom_name or "Custom"))
        kind = ("Flaw" if (mp.taken_as or (definition.kind if definition else ""))
                == "flaw" else "Merit")
        tier = viewmod.merit_tier_label(mp.tier) if mp.tier else ""
        rows.append({"kind": kind, "name": name, "rating": None,
                     "cost": f"{mp.points:+d}" if mp.points else tier,
                     "note": mp.detail, "obj": mp, "index": index,
                     "list": "merits_flaws", "definition": definition, "tier": tier})
    for index, f in enumerate(character.fetters):
        rows.append({"kind": "Fetter", "name": f.name or "—", "rating": f.rating,
                     "cost": "", "note": f.note, "obj": f, "index": index,
                     "list": "fetters"})
    for index, p in enumerate(character.passions):
        rows.append({"kind": "Passion", "name": p.name or "—", "rating": p.rating,
                     "cost": "", "note": p.note, "obj": p, "index": index,
                     "list": "passions"})
    return rows


def dots(n) -> str:
    return "" if not n else "●" * n


def muted(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color:{MUTED};")
    return label


def heading(text: str, accent: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(f"font-weight:700; color:{accent};")
    return label


# --------------------------------------------------------------------------- #
# Candidate A — ONE table for everything, Gear's exact shape
# --------------------------------------------------------------------------- #

class CandidateA(QWidget):
    """Every advantage in one filterable table, editor on the right.

    The maximally consistent answer: Gear's layout, applied unchanged. Its bet is that
    a Background and a Merit are both just "a thing the character has", and that one
    surface with a Kind column beats four sections.

    ⚠ The cost it pays is the at-a-glance read. On the shipped page every Background
    dot track is visible at once, which is how a sheet is normally scanned; here you
    see one rating at a time and the rest are numbers in a column.
    """

    def __init__(self, ruleset, character, parent=None):
        super().__init__(parent)
        self._ruleset, self._char = ruleset, character
        accent = accent_light(theme.palette(character.exalt_type))

        bar = QHBoxLayout()
        bar.addWidget(QLabel("Show:"))
        self.filter = QComboBox()
        self.filter.addItem("Everything", "")
        for kind in ("Background", "Merit", "Flaw", "Fetter", "Passion"):
            self.filter.addItem(kind, kind)
        self.filter.currentIndexChanged.connect(self._fill)
        bar.addWidget(self.filter)
        self.search = QLineEdit()
        self.search.setPlaceholderText("filter by name…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._fill)
        bar.addWidget(self.search, 1)

        self.table = QTreeWidget()
        self.table.setHeaderLabels(["Kind", "Name", "Rating", "Cost", "Note"])
        self.table.setRootIsDecorated(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self._show_detail)

        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet(f"font-weight:700; font-size:14px; color:{accent};")
        self._detail_body = QWidget()
        self._detail_lay = QVBoxLayout(self._detail_body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._detail_body)
        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.addWidget(self.detail_title)
        pl.addWidget(scroll, 1)

        split = QSplitter()
        split.addWidget(self.table)
        split.addWidget(panel)
        split.setSizes([700, 420])

        outer = QVBoxLayout(self)
        outer.addLayout(bar)
        outer.addWidget(split, 1)
        self._fill()

    def _fill(self, *_):
        want = self.filter.currentData()
        needle = self.search.text().strip().lower()
        self.table.setSortingEnabled(False)
        self.table.clear()
        for row in advantage_rows(self._ruleset, self._char):
            if want and row["kind"] != want:
                continue
            if needle and needle not in row["name"].lower():
                continue
            item = QTreeWidgetItem([row["kind"], row["name"], dots(row["rating"]),
                                    row["cost"], row["note"]])
            item.setData(0, Qt.UserRole, row)
            self.table.addTopLevelItem(item)
        self.table.setSortingEnabled(True)
        if self.table.topLevelItemCount():
            self.table.setCurrentItem(self.table.topLevelItem(0))

    def _show_detail(self):
        while self._detail_lay.count():
            item = self._detail_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        item = self.table.currentItem()
        if item is None:
            return
        row = item.data(0, Qt.UserRole)
        accent = accent_light(theme.palette(self._char.exalt_type))
        self.detail_title.setText(f"{row['name']}")
        self._detail_lay.addWidget(muted(row["kind"]))
        form = QFormLayout()
        if row["rating"] is not None:
            form.addRow("Rating", DotTrack(lambda r=row: r["obj"].rating,
                                           lambda v, r=row: setattr(r["obj"], "rating", v),
                                           0, 5, accent=accent))
        if row.get("definition") is not None:
            form.addRow("Cost", QLabel(viewmod.merit_option_label(row["definition"])))
        note = QLineEdit(row["note"])
        note.setPlaceholderText("note")
        form.addRow("Note", note)
        self._detail_lay.addLayout(form)
        if row.get("definition") is not None:
            self._detail_lay.addWidget(muted(row["definition"].description))
        self._detail_lay.addStretch(1)


# --------------------------------------------------------------------------- #
# Candidate B — sub-tabs per kind, Charms' shape
# --------------------------------------------------------------------------- #

class CandidateB(QWidget):
    """A sub-tab per category, each a table beside one shared detail pane.

    The Charms answer. Its bet is that Backgrounds and Merits are DIFFERENT GAME
    CONCEPTS with different rules and different budgets, so they deserve separate
    surfaces — while still being tables rather than card stacks.

    ⚠ It costs a click to see the other half, and the two budgets (Background dots
    and bonus points) can no longer be read at the same time.
    """

    def __init__(self, ruleset, character, parent=None):
        super().__init__(parent)
        self._ruleset, self._char = ruleset, character
        accent = accent_light(theme.palette(character.exalt_type))
        rows = advantage_rows(ruleset, character)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self._tables = []
        groups = [("Backgrounds", ("Background",)),
                  ("Merits & Flaws", ("Merit", "Flaw"))]
        if any(r["kind"] in ("Fetter", "Passion") for r in rows):
            groups.append(("Fetters & Passions", ("Fetter", "Passion")))
        for label, kinds in groups:
            table = QTreeWidget()
            table.setHeaderLabels(["Name", "Rating", "Cost", "Note"])
            table.setRootIsDecorated(False)
            table.setAlternatingRowColors(True)
            table.setSortingEnabled(True)
            table.header().setSectionResizeMode(0, QHeaderView.Stretch)
            table.header().setSectionResizeMode(3, QHeaderView.Stretch)
            for row in rows:
                if row["kind"] not in kinds:
                    continue
                item = QTreeWidgetItem([row["name"], dots(row["rating"]),
                                        row["cost"], row["note"]])
                item.setData(0, Qt.UserRole, row)
                table.addTopLevelItem(item)
            table.itemSelectionChanged.connect(
                lambda t=table: self._show_detail(t))
            self.tabs.addTab(table, label)
            self._tables.append(table)
        self.tabs.currentChanged.connect(
            lambda i: self._show_detail(self._tables[i]))

        self.detail_title = QLabel("")
        self.detail_title.setStyleSheet(
            f"font-weight:700; font-size:14px; color:{accent};")
        self._detail_body = QWidget()
        self._detail_lay = QVBoxLayout(self._detail_body)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._detail_body)
        panel = QWidget()
        pl = QVBoxLayout(panel)
        pl.addWidget(self.detail_title)
        pl.addWidget(scroll, 1)

        split = QSplitter()
        split.addWidget(self.tabs)
        split.addWidget(panel)
        split.setSizes([700, 420])
        outer = QVBoxLayout(self)
        outer.addWidget(split, 1)
        if self._tables:
            self._show_detail(self._tables[0])

    def _show_detail(self, table):
        while self._detail_lay.count():
            item = self._detail_lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        item = table.currentItem()
        if item is None:
            self.detail_title.setText("")
            return
        row = item.data(0, Qt.UserRole)
        accent = accent_light(theme.palette(self._char.exalt_type))
        self.detail_title.setText(row["name"])
        self._detail_lay.addWidget(muted(row["kind"]))
        form = QFormLayout()
        if row["rating"] is not None:
            form.addRow("Rating", DotTrack(lambda r=row: r["obj"].rating,
                                           lambda v, r=row: setattr(r["obj"], "rating", v),
                                           0, 5, accent=accent))
        if row.get("definition") is not None:
            form.addRow("Cost", QLabel(viewmod.merit_option_label(row["definition"])))
        form.addRow("Note", QLineEdit(row["note"]))
        self._detail_lay.addLayout(form)
        if row.get("definition") is not None:
            self._detail_lay.addWidget(muted(row["definition"].description))
        self._detail_lay.addStretch(1)


# --------------------------------------------------------------------------- #
# Candidate C — the shipped structure, natively dressed
# --------------------------------------------------------------------------- #

class CandidateC(QWidget):
    """One scroll, sections instead of cards, everything aligned in a form grid.

    The conservative answer, and the one that takes the human's "it's fine as is"
    seriously: keep the shipped page's structure — every Background visible at once,
    edited in place — and remove only what makes it read as a web page. No card
    chrome; a rule beneath each section heading; ratings, names and notes on aligned
    columns rather than each row laying itself out.

    ⚠ Its bet is that Advantages is a FORM, not a list of objects: you fill it in
    once at chargen and rarely revisit it, and a form wants every field visible.
    """

    def __init__(self, ruleset, character, parent=None):
        super().__init__(parent)
        self._ruleset, self._char = ruleset, character
        accent = accent_light(theme.palette(character.exalt_type))
        rows = advantage_rows(ruleset, character)

        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(4)

        groups = [("Backgrounds", ("Background",)),
                  ("Merits & Flaws", ("Merit", "Flaw")),
                  ("Fetters", ("Fetter",)), ("Passions", ("Passion",))]
        for label, kinds in groups:
            mine = [r for r in rows if r["kind"] in kinds]
            if not mine and label in ("Fetters", "Passions"):
                continue
            lay.addWidget(heading(label.upper(), accent))
            rule = QFrame()
            rule.setFrameShape(QFrame.HLine)
            rule.setStyleSheet(f"color:{CARD};")
            lay.addWidget(rule)
            grid = QFormLayout()
            grid.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.setHorizontalSpacing(16)
            for row in mine:
                right = QHBoxLayout()
                if row["rating"] is not None:
                    right.addWidget(DotTrack(
                        lambda r=row: r["obj"].rating,
                        lambda v, r=row: setattr(r["obj"], "rating", v),
                        0, 5, accent=accent))
                if row["cost"]:
                    cost = QLabel(row["cost"])
                    cost.setStyleSheet(f"color:{MUTED};")
                    cost.setMinimumWidth(48)
                    right.addWidget(cost)
                note = QLineEdit(row["note"])
                note.setPlaceholderText("note")
                right.addWidget(note, 1)
                holder = QWidget()
                holder.setLayout(right)
                grid.addRow(row["name"], holder)
            lay.addLayout(grid)
            lay.addSpacing(12)
        lay.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)


# --------------------------------------------------------------------------- #
# the window
# --------------------------------------------------------------------------- #

NOTES = {
    0: "SHIPPED — the real qt/advantages.py. Card stack, rows edited in place.",
    1: "A · ONE TABLE — Gear's shape exactly. Maximum consistency; you see one "
       "rating at a time.",
    2: "B · SUB-TABS — Charms' shape. Categories stay distinct; the two budgets "
       "can no longer be read together.",
    3: "C · NATIVE FORM — the shipped structure with the web chrome removed. "
       "Everything visible at once.",
}


class Window(QMainWindow):
    def __init__(self, ruleset, character):
        super().__init__()
        self.setWindowTitle(f"Advantages layout spike — {character.name or 'unnamed'}")
        self.resize(1280, 860)
        pal = theme.palette(character.exalt_type)
        qtheme.apply(self, pal)

        budgets = validate.effective_budgets(ruleset, character)
        calc = meritsmod.merits_and_flaws_calc(ruleset, character)
        summary = QLabel(
            f"{character.name or 'unnamed'} · {character.exalt_type} · "
            f"{len(character.backgrounds)} Backgrounds "
            f"({validate.background_dots_budget(budgets, character)} dots) · "
            f"{len(character.merits_flaws)} Merits & Flaws "
            f"(grants {calc.bonus_point_grant} bonus points)")
        summary.setStyleSheet(f"color:{MUTED}; padding:6px 10px;")

        self.note = QLabel(NOTES[0])
        self.note.setWordWrap(True)
        self.note.setStyleSheet(
            f"color:{accent_light(pal)}; font-weight:600; padding:4px 10px;")

        tabs = QTabWidget()
        tabs.addTab(AdvantagesPage(ruleset, {"char": character}), "As shipped")
        tabs.addTab(CandidateA(ruleset, character), "A · One table")
        tabs.addTab(CandidateB(ruleset, character), "B · Sub-tabs")
        tabs.addTab(CandidateC(ruleset, character), "C · Native form")
        tabs.currentChanged.connect(lambda i: self.note.setText(NOTES.get(i, "")))

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(summary)
        lay.addWidget(self.note)
        lay.addWidget(tabs, 1)
        self.setCentralWidget(central)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    ruleset = rules_db.load_app_ruleset(
        Path(exalted_builder.__file__).parent / "data")
    if path.exists():
        character = persistence.load_character(path)
    else:
        character = Character(id="char.spike", name="Spike", exalt_type="Solar",
                              caste="dawn")
    app = QApplication(sys.argv)
    window = Window(ruleset, character)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
