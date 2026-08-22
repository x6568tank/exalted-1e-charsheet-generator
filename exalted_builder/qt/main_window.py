"""exalted_builder/qt/main_window.py — the native builder window (decision 0018).

The shell is the master-detail the human approved in spikes/qt_edit: a left RAIL of
app tabs (Identity / Traits / Gear / Advantages / Charms / Play / ST Options /
Custom / Sheet) beside a stack of pages, a top toolbar (New / Load / Save /
Print / Finish & Lock / Unlock / Party), a readout bar whose "≡ details" opens a
popover with validation + bonus-points + the post-lock Experience card, and a bottom
status strip (Willpower · pools · Soak).

The Identity/Traits split: the old monolithic Edit tab became two pages
(qt/editor.py). Rail visibility follows view.visible_tabs with the old "Edit" key
mapped to showing both; a page's reload() runs whenever it is shown, so a structural
change on Identity is fresh when Traits opens.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QToolBar, QVBoxLayout, QWidget,
)

from exalted_builder import custom_content, persistence, rules_db
from exalted_builder.engine import advancement, elder, lifecycle, validate
from exalted_builder.models.character import Character
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
from .play import PlayPage
from .sheet import SheetPage

# The rail's tabs: the app's viewmod._TABS with the "Edit" tab split into Identity +
# Traits (the human-approved spike layout).
# ⚠ "Combos" is NOT here. It is a SUB-TAB of Charms in the native shell (2026-08-21,
# the human's call), because a Combo is assembled out of Charms the character already
# owns and the two were a rail apart. The webapp keeps its top-level Combos tab, so
# `viewmod.visible_tabs` still names one and `_visible_rail_tabs` drops it — the
# show/hide rule itself moved inward to `CharmsPage`.
_RAIL_TABS = ("Identity", "Traits", "Gear", "Advantages", "Charms",
              "Play", "ST", "Custom", "Sheet")
_RAIL_LABELS = {t: t for t in _RAIL_TABS}
_RAIL_LABELS["ST"] = "ST Options"
# Old tab keys ("Edit") ↔ rail keys. Everything else maps 1:1.
_OLD_TO_RAIL = {"Edit": "Identity"}
_RAIL_TO_OLD = {v: k for k, v in _OLD_TO_RAIL.items()}


def make_context(character: Character, save_path: Path) -> dict:
    """The app's shared, mutable context: the character being edited, where it saves,
    and the (unused-this-milestone) party slot. Mirrors ui/builder.make_context — the
    native shell must not import the NiceGUI module to get it."""
    return {"char": character, "path": Path(save_path), "dir": Path(save_path).parent,
            "party": Party(id="party.new"), "party_path": None, "member": None,
            "adversary_catalog": {}}


class _PlaceholderPage(QWidget):
    """A tab whose module is not ported yet. Says so plainly rather than rendering an
    empty pane — the NiceGUI webapp still ships the surface."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color:#6b7280; font-size:12pt; padding:40px;")
        lay.addWidget(label)
        lay.addStretch(1)


class MainWindow(QMainWindow):
    """The native builder: toolbar + readout bar, a left rail of app tabs, and a
    bottom status strip over the shared character context."""

    def __init__(self, ruleset: RuleSet, character: Character, save_path: Path,
                 *, ctx: dict | None = None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx if ctx is not None else make_context(character, save_path)
        self._state = {"tab": "Identity"}
        # ⚠ A CALCULATOR field, not a character trait — `Character.age` is gone
        # and age gates nothing (human, 2026-08-06). Kept on the window so a
        # second downtime award is priced from where the last one ended.
        self._downtime = {"age": 0, "years": 0}
        self._syncing = False
        self._pages: dict[str, QWidget] = {}

        self.resize(1280, 880)
        self._build_toolbar()
        self._build_shell()
        self.statusBar().showMessage("")
        self._apply_chrome()
        self._sync_tabs()

    # ---- chrome --------------------------------------------------------- #

    def _notify(self, text: str, kind: str = "info") -> None:
        """A transient message. Warnings are modal (a failed purchase needs to be
        seen); info rides the status bar."""
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
        # `&&` — a single `&` in action text is Qt's mnemonic marker and is swallowed
        # from the display ("Finish & Lock" would render "Finish  Lock").
        tb.addAction("New", self._confirm_new)
        tb.addAction("Load", self._open_load)
        tb.addAction("Save", self._save)
        tb.addAction("Print", self._export_pdf)
        tb.addAction("Finish && Lock", self._finish)
        tb.addAction("Unlock", self._unlock)
        tb.addSeparator()
        party = tb.addAction("Party", self._party)
        party.setToolTip("The Storyteller party screen is not part of this milestone.")

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

        # status strip — created BEFORE the pages, because a page's constructor may
        # already fire `on_change` (the Advantages page derives its issue line as it
        # builds) and `_refresh` writes to both readouts.
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
        # ⚠ No `on_change`: play-state moves nothing the shell's readout bar or status
        # strip shows — those are permanent derivations, and decision 0006 keeps
        # play-state out of every one of them. A hook wired here would be a dormant
        # invitation to change that.
        self._pages["Play"] = PlayPage(ruleset, ctx, notify=self._notify)
        self._pages["ST"] = _PlaceholderPage(
            "The ST Options tab is still on the webapp.")
        self._pages["Custom"] = _PlaceholderPage(
            "The Custom (homebrew) tab is still on the webapp.")
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
        # A freshly-shown page re-derives from the shared character, so a change made
        # on one tab is fresh on the next. Skip while _sync_tabs is driving the rail.
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
        """The rail tabs to show: view.visible_tabs with the old "Edit" key mapped to
        showing both Identity and Traits, and "Combos" dropped.

        ⚠ Combos is a Charms SUB-TAB here, so the shared presenter's answer about it is
        deliberately discarded rather than the presenter changed — `visible_tabs` is
        still exactly right for the webapp, where Combos is top-level. `CharmsPage`
        asks `has_combos_tab` itself and adds or drops its own page.
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
        """Show the rail tabs this character's stage has; Play appears at the lock. If
        the tab we are on just disappeared, land on its counterpart."""
        combos = viewmod.has_combos_tab(self._ruleset, self._ctx["char"])
        visible = self._visible_rail_tabs()
        self._syncing = True
        for name in _RAIL_TABS:
            self.rail.item(_RAIL_TABS.index(name)).setHidden(name not in visible)
        # resolve_tab speaks the old keys; map the current rail tab to old, resolve,
        # map back (an "Edit" answer lands on Identity). ⚠ It can still answer "Combos",
        # which is no longer a rail tab — the `target not in _RAIL_TABS` fallback below
        # is what catches that, and it is load-bearing now rather than defensive.
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
        # Post-lock there are no bonus points, so the line must not open on " · ".
        self.readout.setText(" · ".join(part for part in (bp, status) if part))
        self.status.setText(
            f"Willpower {view.willpower} · {view.essence_pool_label()} · "
            f"Soak B{view.soak.bashing} / L{view.soak.lethal} / A{view.soak.aggravated}")

    def _open_popover(self) -> None:
        """The click-to-open details: validation issues, the bonus-point breakdown,
        and (post-lock) the Experience card + ledger.

        The body SCROLLS and the dialog has a floor width, because the content is
        unbounded — a character can carry a dozen word-wrapped validation issues plus a
        full XP ledger. Sized to its hint it came up too narrow, and word-wrapped labels
        in a too-narrow dialog wrap into each other (human, 2026-08-22).
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
            # ⚠ `clear_layout`, never a hand-written loop: `item.widget()` is None for a
            # nested QLayout, so a widget-only sweep leaves the bonus-point ROWS' labels
            # parented and painting over the new build. That is what made the issues
            # look like they clipped into each other.
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
            # ⚠ Bonus points are a CHARGEN surface only (human, 2026-08-22). There are
            # none to spend after the lock, which is why the readout bar already drops
            # the line there — a popover still reporting "12 / 15 spent" for a locked
            # character disagreed with the bar above it. Post-lock this slot is the
            # Experience card and its ledger instead.
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
        """The p.259 downtime calculator: years of skipped time to maturation XP.

        A CALCULATOR that grants, never an enforcement — the 4:3:2:1 split prints as
        advice and nothing downstream polices it (see engine.elder).

        ⚠ The AGE is a calculator field, NOT a character trait (human's ruling
        2026-08-06: `Character.age` is gone and age gates nothing). It lives on the
        window so a second award is priced from where the last one ended; the character
        itself only ever receives the XP.
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
                # The chart starts at 100 years and the build never invents the rows
                # below it. Say so, or a zero reads as a bug.
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
        self._ctx["char"] = Character(id="char.new")
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
        """Print via reportlab ui/pdf.py — the shipped PDF path, shared with the
        webapp's Print button (the plan: printing was resolved without Qt)."""
        view = viewmod.build_sheet_view(self._ruleset, self._ctx["char"])
        default = pdf.suggested_filename(view)
        # Paper size is a per-export choice (the human's call), asked here like the
        # webapp's export dialog.
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

    def _party(self) -> None:
        self._notify("The Storyteller party screen is not part of this milestone.", "info")


def run(ruleset: RuleSet, character: Character, save_path: Path) -> None:
    """Run the native window over a loaded ruleset + character (used by __main__)."""
    app = QApplication.instance() or QApplication([])
    win = MainWindow(ruleset, character, save_path)
    win.show()
    app.exec()
