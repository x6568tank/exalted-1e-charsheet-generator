"""exalted_builder/qt/main_window.py — the native builder window (decision 0018).

The shell is a master-detail layout (human's ruling). It has a left RAIL of app tabs
(Identity / Traits / Gear / Advantages / Charms / Play / ST Options / Custom / Sheet)
next to a stack of pages. It has a top toolbar (New / Load / Save / Print / Finish & Lock
/ Unlock / Party). It has a readout bar, and its "≡ details" control opens a popover with
the validation issues, the bonus points and the Experience card that appears after the
lock. It has a bottom status strip (Willpower · pools · Soak).

Identity and Traits are two pages (`qt/editor.py`), and the webapp has one Edit tab. The
rail follows `view.visible_tabs`, and the old "Edit" key shows both pages. The `reload()`
of a page runs each time the shell shows that page. Thus a structural change on Identity
is current when the user opens Traits.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QToolBar, QVBoxLayout, QWidget,
)

import exalted_builder
from exalted_builder import custom_content, persistence, rules_db
from exalted_builder.engine import advancement, elder, lifecycle, validate
from exalted_builder.models.character import Character, new_character_id
from exalted_builder.models.party import Party
from exalted_builder.models.rules import RuleSet
from exalted_builder.ui import pdf, theme
from exalted_builder.ui import view as viewmod

from . import theme as qtheme
from .layout import clear_layout
from .advantages import AdvantagesPage
from .charms import CharmsPage
from .gear import GearPage
from .editor import IdentityPage, TraitsPage
from .custom import CustomPage
from .party import PartyWindow
from .play import PlayPage
from .sheet import SheetPage
from .storyteller import StorytellerPage

# The tabs of the rail. They are the `viewmod._TABS` of the app, with the "Edit" tab
# divided into Identity and Traits (human's ruling).
# ⚠ "Combos" is NOT here. In the native shell, Combos is a SUB-TAB of Charms (human's
# ruling), because a Combo is assembled from Charms that the character owns. The webapp
# keeps its top-level Combos tab. Thus `viewmod.visible_tabs` names one, and
# `_visible_rail_tabs` removes it. `CharmsPage` holds the show/hide rule.
_RAIL_TABS = ("Identity", "Traits", "Gear", "Advantages", "Charms",
              "Play", "ST", "Custom", "Sheet")
_RAIL_LABELS = {t: t for t in _RAIL_TABS}
_RAIL_LABELS["ST"] = "ST Options"
# Old tab keys ("Edit") ↔ rail keys. Everything else maps 1:1.
_OLD_TO_RAIL = {"Edit": "Identity"}
_RAIL_TO_OLD = {v: k for k, v in _OLD_TO_RAIL.items()}

# Where the adversary TEMPLATE catalogue is loaded from, on first use of the Party
# window. It is book data but not rules — see rules_db.load_adversary_catalog.
_DATA_DIR = Path(exalted_builder.__file__).parent / "data"


def make_context(character: Character, save_path: Path) -> dict:
    """The shared context of the app. It holds the character that the user edits, the save
    path, and the party slot. It agrees with `ui/builder.make_context`. ⚠ The native shell
    must not import the NiceGUI module to get this context."""
    return {"char": character, "path": Path(save_path), "dir": Path(save_path).parent,
            "party": Party(id="party.new"), "party_path": None, "member": None,
            "adversary_catalog": {}}


class MainWindow(QMainWindow):
    """The native builder: toolbar + readout bar, a left rail of app tabs, and a
    bottom status strip over the shared character context."""

    def __init__(self, ruleset: RuleSet, character: Character, save_path: Path,
                 *, ctx: dict | None = None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx if ctx is not None else make_context(character, save_path)
        self._state = {"tab": "Identity"}
        # ⚠ This is a CALCULATOR field, not a character trait. `Character.age` does not
        # exist, and age gates nothing (human's ruling). The window holds this value. Thus
        # a second downtime award starts at the end of the last award.
        self._downtime = {"age": 0, "years": 0}
        self._syncing = False
        self._pages: dict[str, QWidget] = {}
        # The Storyteller window, built on first use and kept — see `party_window`.
        self._party_window: PartyWindow | None = None

        self.resize(1280, 880)
        self._build_toolbar()
        self._build_shell()
        self.statusBar().showMessage("")
        self._apply_chrome()
        self._sync_tabs()

    # ---- chrome --------------------------------------------------------- #

    def _notify(self, text: str, kind: str = "info") -> None:
        """Show a temporary message. A warning is modal, because the user must see a
        failed purchase. Information goes to the status bar."""
        if kind == "warning":
            QMessageBox.warning(self, "Exalted 1e", text)
        else:
            self.statusBar().showMessage(text, 8000)

    def _pal(self):
        return theme.palette(self._ctx["char"].exalt_type)

    def _apply_chrome(self) -> None:
        pal = self._pal()
        self.setWindowTitle(f"Exalted 1e — {pal.splat_label} Builder")
        qtheme.apply(self, pal)

    # ---- toolbar + shell ------------------------------------------------- #

    def _build_toolbar(self) -> None:
        tb = QToolBar("Actions")
        tb.setMovable(False)
        self.addToolBar(tb)
        # ⚠ Write `&&`. In action text, one `&` is the mnemonic marker of Qt, and Qt
        # removes it from the display. "Finish & Lock" then shows as "Finish  Lock".
        tb.addAction("New", self._confirm_new)
        tb.addAction("Load", self._open_load)
        tb.addAction("Save", self._save)
        tb.addAction("Print", self._export_pdf)
        tb.addAction("Finish && Lock", self._finish)
        tb.addAction("Unlock", self._unlock)
        tb.addSeparator()
        party = tb.addAction("Party", self._party)
        party.setToolTip("The Storyteller's party window — members, adversaries and "
                         "the ST reference screen")

    def _build_shell(self) -> None:
        """The readout bar, the left rail + page stack, and the status strip."""
        ctx, ruleset = self._ctx, self._ruleset

        # readout bar
        self.readout = QLabel("")
        self.readout.setStyleSheet(
            f"color:{qtheme.accent(self._pal())}; font-weight:600; padding:4px 8px;")
        details = QPushButton("≡ details")
        details.setToolTip("Validation issues, the bonus-point breakdown, and the "
                           "post-lock Experience card")
        details.clicked.connect(self._open_popover)
        bar = QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.readout, 1)
        bar.addWidget(details)

        # left rail
        self.rail = QListWidget()
        self.rail.setObjectName("appRail")
        self.rail.setFixedWidth(170)
        for name in _RAIL_TABS:
            self.rail.addItem(QListWidgetItem(_RAIL_LABELS.get(name, name)))

        # ⚠ Create the status strip BEFORE the pages. The constructor of a page can send
        # `on_change`. For example, the Advantages page calculates its issue line while it
        # builds. `_refresh` then writes to both readouts.
        self.status = QLabel("")
        self.status.setStyleSheet(f"color:{qtheme.MUTED}; padding:4px 8px;")

        # pages
        self._pages["Identity"] = IdentityPage(
            ruleset, ctx, notify=self._notify,
            on_theme_change=self._apply_chrome, on_change=self._refresh)
        self._pages["Traits"] = TraitsPage(
            ruleset, ctx, notify=self._notify, on_change=self._refresh)
        self._pages["Gear"] = GearPage(
            ruleset, ctx, notify=self._notify, on_change=self._refresh)
        self._pages["Advantages"] = AdvantagesPage(
            ruleset, ctx, notify=self._notify, on_change=self._refresh)
        self._pages["Charms"] = CharmsPage(
            ruleset, ctx, notify=self._notify, on_change=self._refresh)
        # ⚠ Supply no `on_change` here. Play state changes nothing that the readout bar or
        # the status strip shows. Those are permanent derivations, and decision 0006 keeps
        # play state out of all of them. A hook here invites a later change to that rule.
        self._pages["Play"] = PlayPage(ruleset, ctx, notify=self._notify)
        # ⚠ `on_change` is necessary here. "Magic for Everyone" gives free purchases, and
        # the God-Blooded Inheritance rating changes the bonus-point pool. Thus a change to
        # a rule changes the budget line of the readout bar.
        self._pages["ST"] = StorytellerPage(
            ruleset, ctx, notify=self._notify, on_change=self._refresh)
        # ⚠ `on_change` is necessary here. A delete of a custom Charm that the character
        # owns leaves the id on the sheet as an `unknown-charm` error. The readout bar
        # reports that error.
        self._pages["Custom"] = CustomPage(
            ruleset, ctx, notify=self._notify, on_change=self._refresh)
        self._pages["Sheet"] = SheetPage(ruleset, ctx)

        self.stack = QStackedWidget()
        for name in _RAIL_TABS:
            self.stack.addWidget(self._pages[name])
        self.rail.currentRowChanged.connect(self._on_rail_changed)
        self.rail.setCurrentRow(0)

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)
        lay.addLayout(bar)
        mid = QHBoxLayout()
        mid.setSpacing(8)
        mid.addWidget(self.rail)
        mid.addWidget(self.stack, 1)
        lay.addLayout(mid, 1)
        lay.addWidget(self.status)
        self.setCentralWidget(central)

    def _on_rail_changed(self, row: int) -> None:
        # A page that the shell shows calculates again from the shared character. Thus a
        # change on one tab is current on the next tab. Skip this while `_sync_tabs`
        # controls the rail.
        if self._syncing:
            return
        self.stack.setCurrentIndex(row)
        widget = self.stack.widget(row)
        reload = getattr(widget, "reload", None)
        if reload is not None:
            reload()
        for name, page in self._pages.items():
            if page is widget:
                self._state["tab"] = name
                break

    def _visible_rail_tabs(self) -> set[str]:
        """The rail tabs to show. Input: `view.visible_tabs`. Output: the same list, with
        the "Edit" key changed to Identity and Traits, and with "Combos" removed.

        ⚠ Combos is a SUB-TAB of Charms here. Thus this method discards the answer of the
        shared presenter. Do not change the presenter. `visible_tabs` is correct for the
        webapp, where Combos is a top-level tab. `CharmsPage` reads `has_combos_tab` and
        adds or removes its own page.
        """
        char = self._ctx["char"]
        locked = char.chargen_locked
        combos = viewmod.has_combos_tab(self._ruleset, char)
        vis = set(viewmod.visible_tabs(locked, combos=combos))
        vis.discard("Combos")
        if "Edit" in vis:
            vis.discard("Edit")
            vis |= {"Identity", "Traits"}
        return vis

    def _sync_tabs(self) -> None:
        """Show the rail tabs for the stage of this character. Play appears at the lock. If
        the current tab is no longer visible, move to its replacement."""
        combos = viewmod.has_combos_tab(self._ruleset, self._ctx["char"])
        visible = self._visible_rail_tabs()
        self._syncing = True
        for name in _RAIL_TABS:
            self.rail.item(_RAIL_TABS.index(name)).setHidden(name not in visible)
        # `resolve_tab` uses the old keys. Change the current rail tab to an old key,
        # resolve it, then change the result back. An "Edit" result becomes Identity.
        # ⚠ `resolve_tab` can return "Combos", which is not a rail tab. The
        # `target not in _RAIL_TABS` fallback below catches that. It is necessary.
        old = _RAIL_TO_OLD.get(self._state["tab"], self._state["tab"])
        resolved = viewmod.resolve_tab(old, self._ctx["char"].chargen_locked,
                                       combos=combos)
        target = _OLD_TO_RAIL.get(resolved, resolved)
        if target not in _RAIL_TABS:
            target = next((n for n in _RAIL_TABS if n in visible), "Identity")
        self._state["tab"] = target
        idx = _RAIL_TABS.index(target)
        if self.rail.currentRow() != idx:
            self.rail.setCurrentRow(idx)
        self._syncing = False
        self._reload_current()

    def _reload_current(self) -> None:
        reload = getattr(self.stack.currentWidget(), "reload", None)
        if reload is not None:
            reload()
        self._refresh()

    # ---- readout + status + popover -------------------------------------- #

    def _refresh(self) -> None:
        """The readout bar's budget line + status, and the bottom status strip."""
        ruleset, char = self._ruleset, self._ctx["char"]
        view = viewmod.build_sheet_view(ruleset, char)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        status = "✓ Legal" if not errors else f"✗ {len(errors)} error(s)"
        # After the lock there are no bonus points. Thus the line must not start with " · ".
        self.readout.setText(" · ".join(part for part in (bp, status) if part))
        self.status.setText(
            f"Willpower {view.willpower} · {view.essence_pool_label()} · "
            f"Soak B{view.soak.bashing} / L{view.soak.lethal} / A{view.soak.aggravated}")
        # ⚠ The card of a party member shows DERIVED capacities, for example the health
        # track and the mote maxima. Thus an XP purchase here changes what the card draws.
        # The two windows hold the same Character object. That keeps the DATA in
        # agreement, but it does not repaint the card.
        self._refresh_party()

    def _open_popover(self) -> None:
        """The details popover. It shows the validation issues, the bonus-point breakdown,
        and, after the lock, the Experience card and the ledger.

        ⚠ The body SCROLLS, and the dialog has a minimum width. The content has no limit.
        A character can have twelve validation issues that wrap, and a full XP ledger. At
        its size hint, the dialog is too narrow, and labels that wrap then overlap.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle("Validation & experience")
        dialog.setMinimumSize(560, 420)
        outer = QVBoxLayout(dialog)
        body = QWidget()
        root = QVBoxLayout(body)
        root.setSpacing(4)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        def rebuild() -> None:
            # ⚠ Use `clear_layout`. Never write a teardown loop. `item.widget()` is None
            # for a nested QLayout. Thus a widget-only sweep keeps the labels of the
            # bonus-point ROWS attached, and they paint over the new build. The issues
            # then look like they overlap.
            clear_layout(root)
            ruleset, char = self._ruleset, self._ctx["char"]
            view = viewmod.build_sheet_view(ruleset, char)
            errors = [i for i in view.issues if i.severity == "error"]
            head = QLabel("✓ Legal" if not errors else f"✗ {len(errors)} error(s)")
            head.setStyleSheet("font-weight:700; color:%s;"
                               % ("#15803d" if not errors else "#b91c1c"))
            root.addWidget(head)
            for issue in view.issues:
                if issue.code in ("bonus-points", "xp-summary"):
                    continue
                color = {"error": "#b91c1c", "warning": "#b45309"}.get(
                    issue.severity, "#a8a5a0")
                line = QLabel(f"• {issue.message}")
                line.setWordWrap(True)
                line.setStyleSheet(f"color:{color};")
                root.addWidget(line)
            sep = QLabel("─" * 36)
            sep.setStyleSheet("color:#a8a5a0;")
            root.addWidget(sep)
            # ⚠ Bonus points are a CHARGEN surface only (human's ruling). After the lock
            # there are none to spend, and the readout bar removes the line. A popover
            # that reports "12 / 15 spent" for a locked character disagrees with the bar
            # above it. After the lock, this slot holds the Experience card and its ledger.
            if char.chargen_locked:
                self._xp_section(root, rebuild)
            else:
                bd = validate.bonus_point_breakdown(ruleset, char)
                total = QLabel(f"Bonus Points  {bd.total} / {bd.available} spent")
                total.setStyleSheet("font-weight:600; color:%s;"
                                    % ("#b91c1c" if bd.over_budget else "#15803d"))
                root.addWidget(total)
                for line in bd.lines:
                    row = QHBoxLayout()
                    domain = QLabel(line.domain)
                    pts = QLabel(str(line.points))
                    if not line.points:
                        domain.setStyleSheet("color:#a8a5a0;")
                        pts.setStyleSheet("color:#a8a5a0;")
                    row.addWidget(domain, 1)
                    row.addWidget(pts)
                    root.addLayout(row)
            root.addStretch(1)

        rebuild()
        done = QPushButton("Done")
        done.clicked.connect(dialog.accept)
        outer.addWidget(done)
        dialog.exec()

    def _downtime_dialog(self) -> None:
        """The downtime calculator (p.259). Input: a number of years. Output: the
        maturation XP for those years.

        This is a CALCULATOR that grants XP. It enforces nothing. The 4:3:2:1 split is
        advice, and no code downstream applies it (see `engine.elder`).

        ⚠ The AGE is a calculator field, NOT a character trait (human's ruling).
        `Character.age` does not exist, and age gates nothing. The window holds the age.
        Thus a second award starts at the end of the last award. The character receives
        the XP only.
        """
        state = self._downtime
        dialog = QDialog(self)
        dialog.setWindowTitle("Downtime")
        lay = QVBoxLayout(dialog)
        intro = QLabel("Annual experience for skipped years (Player's Guide p.259). "
                       "The award depends on the age entered, so a downtime that "
                       "crosses 100, 250, 500 or 1,000 years changes rate partway.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{qtheme.MUTED};")
        lay.addWidget(intro)

        row = QHBoxLayout()
        age = QSpinBox()
        age.setObjectName("downtime.age")
        age.setRange(0, 100000)
        age.setValue(state["age"])
        row.addWidget(QLabel("Exalted years so far"))
        row.addWidget(age, 1)
        years = QSpinBox()
        years.setObjectName("downtime.years")
        years.setRange(0, 100000)
        years.setValue(state["years"])
        row.addWidget(QLabel("Years of downtime"))
        row.addWidget(years, 1)
        lay.addLayout(row)

        preview_box = QVBoxLayout()
        lay.addLayout(preview_box)

        def redraw() -> None:
            clear_layout(preview_box)
            award = elder.downtime_award(age.value(), years.value())
            head = QLabel(f"Age {award.from_age} → {award.to_age}")
            head.setStyleSheet("font-weight:600;")
            preview_box.addWidget(head)
            for band in award.bands:
                span = (f"{band.from_age}" if band.years == 1
                        else f"{band.from_age}–{band.to_age}")
                line = QLabel(f"age {span}: {band.years} yr × {band.rate} = "
                              f"{band.experience} XP")
                line.setStyleSheet(f"font-family:monospace; color:{qtheme.MUTED};")
                preview_box.addWidget(line)
            total = QLabel(f"{award.total} XP")
            total.setObjectName("downtime.total")
            total.setStyleSheet("font-size:16pt; font-weight:700; color:%s;"
                                % qtheme.accent(theme.palette(self._ctx["char"].exalt_type)))
            preview_box.addWidget(total)
            if not award.total and years.value():
                # The chart starts at 100 years, and the program does not add rows below
                # that age. Show this message. Without it, a zero reads as a defect.
                note = QLabel("The p.259 chart begins at 100 years of Exaltation — a "
                              "younger character earns no maturation experience from "
                              "it. Ordinary play awards are the Storyteller's.")
                note.setWordWrap(True)
                note.setStyleSheet("color:#c08a3e;")
                preview_box.addWidget(note)
            for label, points in award.split:
                srow = QHBoxLayout()
                srow.addWidget(QLabel(label), 1)
                srow.addWidget(QLabel(str(points)))
                preview_box.addLayout(srow)
            advice = QLabel("The split is what p.259 requires the experience be spent "
                            "on. It is printed as guidance — nothing here enforces it.")
            advice.setWordWrap(True)
            advice.setStyleSheet(f"font-style:italic; color:{qtheme.MUTED};")
            preview_box.addWidget(advice)

        age.valueChanged.connect(redraw)
        years.valueChanged.connect(redraw)
        redraw()

        def grant() -> None:
            award = elder.downtime_award(age.value(), years.value())
            state["age"] = award.to_age
            state["years"] = years.value()
            advancement.add_xp(self._ctx["char"], award.total)
            dialog.accept()
            self._notify(f"Granted {award.total} XP — age is now {award.to_age} "
                         f"(for the next award).")
            self._reload_current()

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        go = QPushButton("Grant")
        go.setObjectName("downtime.grant")
        go.clicked.connect(grant)
        buttons.addWidget(go)
        lay.addLayout(buttons)
        dialog.exec()

    def _xp_section(self, root, rebuild) -> None:
        """The post-lock Experience card + ledger inside the popover."""
        char = self._ctx["char"]
        pal = theme.palette(char.exalt_type)
        head = QLabel("Experience")
        head.setStyleSheet("font-weight:700; color:%s;" % qtheme.accent(pal))
        root.addWidget(head)
        available = advancement.xp_available(char)
        row = QHBoxLayout()
        av = QLabel(str(available))
        av.setStyleSheet("font-weight:bold; font-size:18pt; color:%s;"
                         % ("#15803d" if available >= 0 else "#b91c1c"))
        row.addWidget(av)
        row.addWidget(QLabel("XP available"))
        root.addLayout(row)
        earned = QLabel(f"earned {char.xp_earned} · spent {advancement.xp_spent(char)}")
        earned.setStyleSheet("color:#a8a5a0;")
        root.addWidget(earned)
        row = QHBoxLayout()
        amount = QSpinBox()
        amount.setRange(-999, 9999)
        amount.setValue(5)
        row.addWidget(amount, 1)
        adjust = QPushButton("Adjust XP")
        adjust.clicked.connect(lambda: (self._do_add_xp(amount.value()), rebuild()))
        row.addWidget(adjust)
        root.addLayout(row)
        downtime = QPushButton("Downtime…")
        downtime.setObjectName("xp.downtime")
        downtime.clicked.connect(lambda: (self._downtime_dialog(), rebuild()))
        root.addWidget(downtime)
        rows = viewmod.build_xp_log(self._ruleset, char)
        if rows:
            undo = QPushButton(f"Undo last: {rows[-1].label}")
            undo.clicked.connect(lambda: (self._do_undo(), rebuild()))
            root.addWidget(undo)
        granted, remaining = validate.withheld_charm_credits(self._ruleset, char)
        if granted:
            note = QLabel(f"{remaining} of {granted} withheld Charm(s) in reserve — "
                          f"the next {remaining or 'no'} cost no XP.")
            note.setStyleSheet("font-weight:600; color:%s;" % qtheme.accent(pal))
            note.setWordWrap(True)
            root.addWidget(note)
        if not rows:
            empty = QLabel("No XP spent yet.")
            empty.setStyleSheet("color:#a8a5a0;")
            root.addWidget(empty)
        for r in rows:
            row = QHBoxLayout()
            row.addWidget(QLabel(r.label), 1)
            cost = QLabel(f"{r.cost} XP")
            cost.setStyleSheet("color:#a8a5a0;")
            row.addWidget(cost)
            root.addLayout(row)

    def _do_add_xp(self, amount: int) -> None:
        advancement.add_xp(self._ctx["char"], amount)
        self._refresh()

    def _do_undo(self) -> None:
        try:
            advancement.undo_last(self._ruleset, self._ctx["char"])
        except advancement.AdvancementError as ex:
            self._notify(str(ex), "warning")
            return
        self._reload_current()

    # ---- load / save / new ---------------------------------------------- #

    def _apply_loaded(self, loaded: Character, path: Path | None, source_label: str) -> None:
        imported = custom_content.absorb_definitions(loaded)
        if imported:
            rules_db.reload_custom_layer(self._ruleset)
            self._notify(f"Imported {len(imported)} homebrew definition(s) from this save", "info")
        self._ctx["char"] = loaded
        # ⚠ The loaded character is not the party member that this window pointed at. Clear
        # the pointer. If it stays, a later save goes to a member that the user never
        # edited.
        self._ctx["member"] = None
        if path is not None:
            self._ctx["path"] = path
            self._ctx["dir"] = path.resolve().parent
        else:
            self._ctx["dir"] = persistence.default_save_dir()
            self._ctx["path"] = self._ctx["dir"] / persistence.suggested_filename(loaded)
        self._notify(f"Loaded {loaded.name or source_label}", "info")
        self._state["tab"] = "Sheet"
        self._apply_chrome()
        self._sync_tabs()

    def _open_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Load a character", str(self._ctx["dir"]),
                                              "Character files (*.json);;All files (*)")
        if not path:
            return
        try:
            loaded = persistence.load_character(path, absorb_custom=False)
        except Exception as ex:               # noqa: BLE001 - surface any load error
            self._notify(f"Load failed: {ex}", "warning")
            return
        self._apply_loaded(loaded, Path(path), Path(path).stem)

    def _save(self) -> None:
        default = persistence.suggested_filename(self._ctx["char"])
        path, _ = QFileDialog.getSaveFileName(self, "Save character",
                                              str(self._ctx["dir"] / default),
                                              "Character files (*.json)")
        if not path:
            return
        try:
            persistence.save_character(self._ctx["char"], path)
        except Exception as ex:               # noqa: BLE001 - surface write errors
            self._notify(f"Save failed: {ex}", "warning")
            return
        self._ctx["path"], self._ctx["dir"] = Path(path), Path(path).parent
        self._notify(f"Saved to {path}", "info")

    def _confirm_new(self) -> None:
        answer = QMessageBox.question(self, "Start a new character?",
                                      "Any unsaved changes to the current character "
                                      "will be lost.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._ctx["char"] = Character(id=new_character_id())
        self._ctx["member"] = None            # this window no longer edits a party member
        self._ctx["dir"] = persistence.default_save_dir()
        self._ctx["path"] = self._ctx["dir"] / persistence.suggested_filename(self._ctx["char"])
        self._notify("Started a new character", "info")
        self._state["tab"] = "Identity"
        self._apply_chrome()
        self._sync_tabs()

    # ---- lock / unlock --------------------------------------------------- #

    def _finish(self) -> None:
        char = self._ctx["char"]
        errors = [i for i in validate.validate_chargen(self._ruleset, char)
                  if i.severity == "error"]
        lifecycle.lock_chargen(char, self._ruleset)
        if errors:
            self._notify(f"Locked with {len(errors)} unresolved error(s) — see the Sheet", "warning")
        else:
            self._notify("Chargen finished and locked", "info")
        self._state["tab"] = "Sheet"
        self._apply_chrome()
        self._sync_tabs()

    def _unlock(self) -> None:
        if not self._ctx["char"].chargen_locked:
            self._notify("Chargen is not locked.", "info")
            return
        lifecycle.unlock_chargen(self._ctx["char"])
        self._notify("Chargen unlocked — editable again.", "info")
        self._state["tab"] = "Identity"
        self._apply_chrome()
        self._sync_tabs()

    # ---- print / party --------------------------------------------------- #

    def _export_pdf(self) -> None:
        """Print with the reportlab path in `ui/pdf.py`. The Print button of the webapp
        uses the same path."""
        view = viewmod.build_sheet_view(self._ruleset, self._ctx["char"])
        default = pdf.suggested_filename(view)
        # The paper size is a choice for each export (human's ruling). Ask for it here, as
        # the export dialog of the webapp does.
        dialog = QDialog(self)
        dialog.setWindowTitle("Export character sheet")
        lay = QVBoxLayout(dialog)
        lay.addWidget(QLabel("Paper size:"))
        paper = QComboBox()
        paper.addItems(list(pdf.PAPER_SIZES))
        paper.setCurrentText("A4")
        lay.addWidget(paper)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(dialog.reject)
        go = QPushButton("Export PDF")
        buttons.addWidget(cancel)

        def _do() -> None:
            path, _ = QFileDialog.getSaveFileName(dialog, "Export character sheet",
                                                  str(self._ctx["dir"] / default), "PDF (*.pdf)")
            if not path:
                return
            try:
                data = pdf.build_pdf(view, paper=paper.currentText())
            except Exception as ex:           # noqa: BLE001 - surface render errors
                self._notify(f"Export failed: {ex}", "warning")
                return
            try:
                Path(path).write_bytes(data)
            except Exception as ex:           # noqa: BLE001 - surface write errors
                self._notify(f"Export failed: {ex}", "warning")
                return
            self._notify(f"Sheet written to {path}", "info")
            dialog.accept()

        go.clicked.connect(_do)
        buttons.addWidget(go)
        lay.addLayout(buttons)
        dialog.exec()

    def party_window(self) -> PartyWindow:
        """The Storyteller window. This method creates it on the first call and keeps it.

        ⚠ There is ONE window, and the builder holds it. A new window for each click gives
        each window its own `party_page` over the same roster. A click on a card in the old
        window then marks a health box that nobody sees. The window shares the CONTEXT. It
        does not take a copy. The roster, the member Characters and the adversary catalogue
        are the same objects.
        """
        if self._party_window is None:
            # The template catalogue is not rules data. It takes no part in prerequisite
            # resolution or in link checking. Thus it goes in the context, and this code
            # loads it on the first use. `ui/builder.py` loads it in the same way.
            if not self._ctx.get("adversary_catalog"):
                self._ctx["adversary_catalog"] = rules_db.load_adversary_catalog(_DATA_DIR)
            self._party_window = PartyWindow(
                self._ruleset, self._ctx,
                on_open_member=self._open_member,
                on_close_member=lambda: self._ctx.update(member=None),
                parent=None)
        return self._party_window

    def _party(self) -> None:
        window = self.party_window()
        window.reload()
        window.show()
        window.raise_()
        window.activateWindow()

    def _open_member(self, index: int) -> None:
        """Point THIS window at party member `index`. There is one builder, and it changes
        its target. There is no window for each member (human's ruling).

        ⚠ Take the member by REFERENCE. Never take a copy. `ctx["char"]` becomes the object
        of the party. Thus each edit here appears on the card, and no code synchronises
        them. `ctx["member"]` records the member. Thus a later save goes to that member.
        """
        member = self._ctx["party"].members[index]
        self._ctx["char"] = member.character
        self._ctx["member"] = index
        self._ctx["path"] = self._ctx["dir"] / persistence.suggested_filename(
            member.character)
        self._apply_chrome()
        self._sync_tabs()
        self.show()
        self.raise_()
        self.activateWindow()
        self._notify(f"The builder is now editing {member.character.name or 'this member'}")

    def _refresh_party(self) -> None:
        """Draw the party window again after the builder changes a character that the
        window holds.

        ⚠ Draw it only when it is VISIBLE. The builder keeps the window after a close, and
        a hidden window shows nothing. The window reloads on each open."""
        if self._party_window is not None and self._party_window.isVisible():
            self._party_window.reload()

    def closeEvent(self, event):              # noqa: N802 - Qt override
        """⚠ Close the party window with the builder. A QMainWindow with no parent is a
        top-level window. Without this code, a close of the builder leaves the Storyteller
        window open, and the user has no route back to a builder."""
        if self._party_window is not None:
            self._party_window.close()
        super().closeEvent(event)


def run(ruleset: RuleSet, character: Character, save_path: Path) -> None:
    """Run the native window over a loaded ruleset + character (used by __main__)."""
    app = QApplication.instance() or QApplication([])
    win = MainWindow(ruleset, character, save_path)
    win.show()
    app.exec()
