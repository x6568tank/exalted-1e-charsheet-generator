"""Advantages layout spike — four shapes for one tab, on one character.

Run: `.venv/bin/python -m spikes.qt_advantages [path/to/character.json]`

A top tab bar switches between the SHIPPED Advantages page and the surviving candidate
redesigns, all reading the same live character, so the comparison is direct rather than
remembered. Nothing in `exalted_builder/` is edited; the shipped tab is the real
`qt.advantages.AdvantagesPage`.

⚠ A third candidate — the shipped structure natively dressed — was ruled out by the
human on sight (2026-08-21) and removed. It is in git at 2a45a34.

⚠ The candidates are LAYOUT MOCKUPS. They render real data and their controls
move, but they do not buy, price or validate anything — the point is the shape, and
wiring three throwaway surfaces to `engine.advancement` would cost more than the
answer is worth. Read them as "what would this feel like", not "does this work".
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMainWindow, QScrollArea, QSplitter,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import exalted_builder
from exalted_builder import persistence, rules_db
from exalted_builder.engine import merits as meritsmod, validate
from exalted_builder.models.character import Character
from exalted_builder.qt import theme as qtheme
from exalted_builder.qt.advantages import AdvantagesPage
from exalted_builder.qt.editor import DotTrack
from exalted_builder.qt.layout import clear_layout
from exalted_builder.qt.theme import MUTED, accent as accent_light
from exalted_builder.ui import theme
from exalted_builder.ui import view as viewmod

DEFAULT = (Path(exalted_builder.__file__).parent.parent / "examples"
           / "ashes-of-dawn.character.json")


# --------------------------------------------------------------------------- #
# the rows every candidate renders — one derivation, so the shapes differ
# only in LAYOUT and a difference on screen is never a difference in data
# --------------------------------------------------------------------------- #

def advantage_rows(ruleset, character) -> list[dict]:
    """Everything this tab owns, flattened: Backgrounds, M&F, Fetters, Passions."""
    rows: list[dict] = []
    # ⚠ The SPLAT-FILTERED catalogue, not the global one. Several Background NAMES
    # belong to two splats with different printed text (a Dragon-Blooded's Connections
    # is not a Sidereal's), and `BackgroundEntry` stores a name rather than an id — so
    # a global lookup would hand this character another splat's rungs.
    bg_catalog = validate.background_catalogue_for(ruleset, character)
    for index, bg in enumerate(character.backgrounds):
        rows.append({"kind": "Background", "name": bg.name or "—",
                     "rating": bg.rating, "cost": "", "note": bg.note,
                     "obj": bg, "index": index, "list": "backgrounds",
                     "bg_catalog": bg_catalog})
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


def describe(row, accent: str) -> list[QLabel]:
    """The full printed text for one advantage — the thing the human asked both
    candidates for (2026-08-21).

    A Merit or Flaw has one description. A **Background has a LADDER**: the printed
    text differs per rating, and the rung you hold is the part that matters, so the
    whole ladder shows with your rung marked. `view.background_ladder` already renders
    it for the catalogue dialog, so the spike reuses that rather than inventing a
    second format.
    """
    out: list[QLabel] = []
    definition = row.get("definition")
    if definition is not None:
        out.append(muted(definition.description))
        if getattr(definition, "cost_note", ""):
            out.append(muted(definition.cost_note))
        return out
    catalog = row.get("bg_catalog")
    if catalog is None:
        return out
    entry = next((b for b in catalog if b.name == row["name"]), None)
    if entry is None:
        # Backgrounds are free text; a name no catalogue holds simply has no printed
        # text to show, which is not an error.
        return out
    out.append(muted(entry.description))
    ladder = viewmod.background_ladder(catalog, row["name"])
    if not ladder:
        return out
    out.append(heading("What each rating buys", accent))
    for rung, (dot_text, text) in enumerate(ladder):
        line = QLabel(f"{dot_text}  {text}")
        line.setWordWrap(True)
        if rung == row["rating"]:
            # The rung actually held, called out — it is the one line on the panel
            # that describes this character rather than the Background in general.
            line.setStyleSheet(f"color:{accent}; font-weight:600;")
        else:
            line.setStyleSheet(f"color:{MUTED};")
        out.append(line)
    return out


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
        # ⚠ `clear_layout`, not a hand-written loop. The first version of this spike
        # wrote one and got it wrong: it skipped nested layouts, so the QFormLayout
        # holding each DotTrack was never torn down and every Background you clicked
        # left its dots painted on top of the next — the "ghosty effect" the human
        # reported (2026-08-21). Fourth occurrence of that trap; hence the helper.
        clear_layout(self._detail_lay)
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
        for widget in describe(row, accent):
            self._detail_lay.addWidget(widget)
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
        # ⚠ `clear_layout`, not a hand-written loop. The first version of this spike
        # wrote one and got it wrong: it skipped nested layouts, so the QFormLayout
        # holding each DotTrack was never torn down and every Background you clicked
        # left its dots painted on top of the next — the "ghosty effect" the human
        # reported (2026-08-21). Fourth occurrence of that trap; hence the helper.
        clear_layout(self._detail_lay)
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
        for widget in describe(row, accent):
            self._detail_lay.addWidget(widget)
        self._detail_lay.addStretch(1)


# --------------------------------------------------------------------------- #
# the window
# --------------------------------------------------------------------------- #

# ⚠ Candidate C (the shipped structure natively dressed) was RULED OUT on sight by the
# human, 2026-08-21, and removed rather than left as noise. It is in git at 2a45a34 if
# anyone wants to look again.
NOTES = {
    0: "SHIPPED — the real qt/advantages.py. Card stack, rows edited in place.",
    1: "A · ONE TABLE — Gear's shape exactly. Maximum consistency; you see one "
       "rating at a time.",
    2: "B · SUB-TABS — Charms' shape. Categories stay distinct; the two budgets "
       "can no longer be read together.",
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
