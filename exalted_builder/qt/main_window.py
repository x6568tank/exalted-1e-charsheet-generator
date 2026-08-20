"""exalted_builder/qt/main_window.py — the native builder window (decision 0018).

The Qt shell mirrors ui/builder.py's composite: a toolbar (New / Load / Save / Print /
Finish & Lock / Unlock / Party) over a tab bar whose pages are persistent widgets —
Edit and Sheet and Charms are the ported pages; Gear, Advantages, Combos, Play, ST and
Custom are placeholders until their modules are ported. All pages read the character
from a shared context dict, and reload() (or the engine's lock/unlock) re-derives them
from the untouched engine / models / ui.view layers.

Tab visibility and the current tab follow view.visible_tabs / view.resolve_tab on both
sides of the lock; a page's reload() runs whenever it is shown, so a change made on one
tab is fresh on the next.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QLabel, QMainWindow,
    QMessageBox, QPushButton, QTabWidget, QToolBar, QVBoxLayout, QWidget,
)

from exalted_builder import custom_content, persistence, rules_db
from exalted_builder.engine import lifecycle, validate
from exalted_builder.models.character import Character
from exalted_builder.models.party import Party
from exalted_builder.models.rules import RuleSet
from exalted_builder.ui import pdf, theme
from exalted_builder.ui import view as viewmod

from . import theme as qtheme
from .charms import CharmsPage
from .editor import EditPage
from .sheet import SheetPage

_TABS = viewmod._TABS

# Tab names are identifiers (state, visible_tabs, resolve_tab all key off them);
# where a name reads badly on the bar, the LABEL differs — see Combos/Arrays.
_LABELS = {t: t for t in _TABS}
_LABELS["ST"] = "ST Options"


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
    """The native builder: toolbar + tab bar over the shared character context."""

    def __init__(self, ruleset: RuleSet, character: Character, save_path: Path,
                 *, ctx: dict | None = None, parent=None):
        super().__init__(parent)
        self._ruleset = ruleset
        self._ctx = ctx if ctx is not None else make_context(character, save_path)
        self._state = {"tab": "Edit"}
        self._syncing = False
        self._pages: dict[str, QWidget] = {}

        self.resize(1280, 880)
        self._build_toolbar()
        self._build_tabs()
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

    # ---- toolbar + tabs ------------------------------------------------- #

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

    def _build_tabs(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        ctx, ruleset = self._ctx, self._ruleset
        self._pages["Edit"] = EditPage(ruleset, ctx, notify=self._notify,
                                       on_theme_change=self._apply_chrome)
        self._pages["Gear"] = _PlaceholderPage(
            "The Gear tab is still on the webapp — this milestone ports Edit, Charms and Sheet.")
        self._pages["Advantages"] = _PlaceholderPage(
            "The Advantages tab is still on the webapp — this milestone ports Edit, Charms and Sheet.")
        self._pages["Charms"] = CharmsPage(ruleset, ctx, notify=self._notify)
        self._pages["Combos"] = _PlaceholderPage(
            "The Combos tab is still on the webapp — this milestone ports Edit, Charms and Sheet.")
        self._pages["Play"] = _PlaceholderPage(
            "The Play tab is still on the webapp — this milestone ports Edit, Charms and Sheet.")
        self._pages["ST"] = _PlaceholderPage(
            "The ST Options tab is still on the webapp — this milestone ports Edit, Charms and Sheet.")
        self._pages["Custom"] = _PlaceholderPage(
            "The Custom (homebrew) tab is still on the webapp — this milestone ports Edit, Charms and Sheet.")
        self._pages["Sheet"] = SheetPage(ruleset, ctx)
        # Signals blocked during construction: addTab sets the current index to 0,
        # which would fire currentChanged and reload the first page before the other
        # tabs exist (and again on the redundant reload the constructor already ran).
        self.tabs.blockSignals(True)
        for name in _TABS:
            self.tabs.addTab(self._pages[name], _LABELS.get(name, name))
        self.tabs.blockSignals(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self.tabs)

    def _on_tab_changed(self, index: int) -> None:
        widget = self.tabs.widget(index)
        # A freshly-shown page re-derives from the shared character, so a change made
        # on one tab is fresh on the next. Skip while _sync_tabs is driving the bar.
        if not self._syncing:
            reload = getattr(widget, "reload", None)
            if reload is not None:
                reload()
            # The internal name (not the label) is what resolve_tab keys off:
            # "ST Options" → "ST", "Arrays" → "Combos".
            for name, page in self._pages.items():
                if page is widget:
                    self._state["tab"] = name
                    break

    def _sync_tabs(self) -> None:
        """Show the tabs this character's stage has (view.visible_tabs); Play appears
        at the lock, Combos disappears for a splat that builds neither. If the tab we
        are on is the one that just disappeared, land on its counterpart."""
        char = self._ctx["char"]
        locked = char.chargen_locked
        combos = viewmod.has_combos_tab(self._ruleset, char)
        self._syncing = True
        for name in _TABS:
            self.tabs.setTabVisible(_TABS.index(name),
                                    name in viewmod.visible_tabs(locked, combos=combos))
        # Relabel the Combos tab for a Charm-Slot splat (Alchemical builds Arrays).
        if combos:
            label = "Arrays" if viewmod.uses_arrays(self._ruleset, char) else "Combos"
            self.tabs.setTabText(_TABS.index("Combos"), label)
        self._state["tab"] = viewmod.resolve_tab(self._state["tab"], locked, combos=combos)
        idx = _TABS.index(self._state["tab"])
        if self.tabs.currentIndex() != idx:
            self.tabs.setCurrentIndex(idx)
        self._syncing = False
        self._reload_current()

    def _reload_current(self) -> None:
        reload = getattr(self.tabs.currentWidget(), "reload", None)
        if reload is not None:
            reload()

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
        self._state["tab"] = "Edit"
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
        self._state["tab"] = "Edit"
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
