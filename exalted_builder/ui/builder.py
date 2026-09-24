"""
ui/builder.py — the unified Exalted 1e builder app.

Stitches the views over one in-memory Character: an Edit tab (the editable sheet),
a Charms tab (the Cytoscape charm-tree picker), a Combos tab, a Play tab, an ST
Options tab (the table's optional-rule switches) and a Sheet tab (the read-only
viewer). A top bar provides Save, Load, and Finish & Lock.

The tab bar tracks the character's stage, but every tab that edits the character is on
it throughout and changes MODE rather than going read-only or being swapped out: before
the lock they spend the chargen budget, after it they spend experience. Play is the one
locked-only tab. See `visible_tabs`, and decision 0013 for why there is no XP tab.

Only the active tab's content is mounted (a single refreshable area), which keeps
the Cytoscape container visible when it builds and avoids stale hidden canvases.
A single charm_toggle handler is registered here and dispatches to whatever the
picker last handed back, so rebuilding the picker never duplicates handlers.

Run:
    python -m exalted_builder.ui.builder [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from nicegui import app, ui

from .. import custom_content, persistence, rules_db
from ..engine import lifecycle, validate
from ..models.character import Character, new_character_id
from ..models.party import Party
from ..models.rules import RuleSet
from ..server import auth, nav
from ..server.config import storage_secret
from ..server.session import SessionRegistry
from . import advantages
from . import gear as gear_mod
from . import app as sheet_app
from . import combos as combos_mod
from . import custom as custom_mod
from . import editor, pdf, picker, saving, theme
from . import play as play_mod
from . import storyteller as st_mod
from . import view as viewmod
from .assets import cytoscape_head_html
# The tab set and its stage logic moved to view.py (toolkit-free) for the Qt port;
# re-exported here so `builder.visible_tabs` callers (tests included) keep working.
from .view import _TABS, resolve_tab, visible_tabs

# Package-relative so it resolves in a dev checkout and a packaged (PyInstaller)
# build alike: builder.py lives in exalted_builder/ui/, so data is one level up.
_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"


def _native_window():
    """The pywebview window when running as a native desktop app (``--native``),
    else None — in which case the browser upload/download fallback is used."""
    return getattr(app.native, "main_window", None)


def _any_socket_connected(clients) -> bool:
    """True if any of `clients` holds a live browser socket. Pure (testable)."""
    return any(getattr(c, "has_socket_connection", False) for c in clients)


def any_tab_connected() -> bool:
    """True while at least one browser tab still has a live socket to the server.
    The packaged app uses this to decide whether to quit when a tab closes."""
    from nicegui import Client
    return _any_socket_connected(Client.instances.values())


def _dialog_type(kind: str):
    """The pywebview file-dialog selector for ``kind`` ('save'/'open'). Use the
    `FileDialog` IntEnum (pywebview 5+): the legacy `webview.SAVE_DIALOG`/`OPEN_DIALOG`
    module attributes are non-picklable Proxy objects, and NiceGUI forwards the call
    to its window subprocess through a multiprocessing queue — pickling a Proxy fails
    silently (the dialog never opens). The enum members pickle cleanly."""
    import webview
    fd = getattr(webview, "FileDialog", None)
    if fd is not None:
        return fd.SAVE if kind == "save" else fd.OPEN
    return 30 if kind == "save" else 10        # legacy pywebview int constants


class _NullDialog:
    """A no-op stand-in so the native Open path can reuse `do_load`, which closes a
    dialog after loading; the native OS dialog has already closed itself."""
    def close(self) -> None:
        pass


def make_context(character: Character, save_path: Path) -> dict:
    """One browser session's mutable context. The builder ('/') and the GM party
    page ('/gm') of ONE session work on the same objects — see `register_pages`,
    which holds one of these for each session.

    ⚠ The context that a caller gives to `register_pages` is a PROTOTYPE. Each
    session gets a copy of it. See `session_context_factory`.

    `char` is whichever character the builder is currently pointed at; `dir` is the
    folder saves land in (the filename is derived from the character's name at save
    time, so renaming the character renames its file). `party` is the GM roster and
    `member` the index within it that `char` came from, or None when editing a
    standalone character that is not in the party.

    `adversary_catalog` is the Storyteller's template list (rules_db.
    load_adversary_catalog). It sits here rather than on the RuleSet because it is
    not rules — see that function. Defaults to empty so a caller that never loads
    it still gets a working roster, offering blank entries only.

    `home_dir` is the folder this session owns. A character that has no file of its
    own lands there: a new character, and an uploaded one. ⚠ Read this field. Do
    not call `persistence.default_save_dir()` in a handler. That function is
    process-wide, thus it takes a hosted session out of its own directory and into
    one that every session shares. See `session_context_factory`.

    `custom_dir` is the homebrew library of this session. None is the default
    library, which is correct for the desktop only. ⚠ Give this field to each
    call that reads or writes the library. A call with no folder uses the
    default library, and the hosted server refuses that.
    """
    return {"char": character, "path": save_path, "dir": Path(save_path).parent,
            "home_dir": persistence.default_save_dir(), "custom_dir": None,
            "party": Party(id="party.new"), "party_path": None, "member": None,
            "adversary_catalog": {}}


def open_member(ctx: dict, index: int) -> None:
    """Point the builder at party member `index`. The Character is shared by
    reference, not copied, so anything the builder edits mutates the party member
    in place and the card reflects it without any syncing code."""
    member = ctx["party"].members[index]
    ctx["char"] = member.character
    ctx["member"] = index
    ctx["path"] = ctx["dir"] / persistence.suggested_filename(member.character)


def close_member(ctx: dict) -> None:
    """Forget which party member the builder is pointed at. The character object
    itself is left alone — it is still in the party."""
    ctx["member"] = None


def session_context_factory(prototype: dict,
                            ruleset: RuleSet | None = None) -> Callable[[str], dict]:
    """Return a factory that makes one context for each browser session of the
    DESKTOP app.

    The factory takes a session key and returns a copy of `prototype`: a deep
    copy of the Character and of the Party, the prototype's save destination,
    and the SAME adversary catalogue. The catalogue is read-only rules data, thus
    a copy of it costs memory and buys nothing. One user owns the file system,
    thus Save writes the file that the user opened. `custom_dir` is None, the
    default library, and the RuleSet is `ruleset` itself.

    The hosted server does not use this. It has one context for each stored
    character (`server/home.py`) since section 5 piece 4.

    `SessionRegistry` calls this. The factory makes a new context on each call;
    the registry, not the factory, gives one key one context.

    ⚠ Inside one context, `char` can BE a party member's character, by identity.
    `open_member` points it there by reference, and the party card then follows
    the builder's edits with no syncing code. This function keeps that identity.
    A copy of `char` and of `party` that is made separately breaks it, and no
    other test fails. See hosting-state-model.md section 3.6.
    """
    def factory(key: str) -> dict:
        party = prototype["party"].model_copy(deep=True)
        member_of = next(
            (index for index, member in enumerate(prototype["party"].members)
             if member.character is prototype["char"]), None)
        char = (party.members[member_of].character if member_of is not None
                else prototype["char"].model_copy(deep=True))
        return {"char": char, "path": prototype["path"], "dir": prototype["dir"],
                "home_dir": prototype["home_dir"], "custom_dir": None, "ruleset": ruleset,
                "party": party, "party_path": prototype["party_path"],
                "member": prototype["member"],
                "adversary_catalog": prototype["adversary_catalog"]}

    return factory


def session_key() -> str:
    """The id of the browser session of the current request.

    NiceGUI writes this id into the signed session cookie, thus it is the same
    for all tabs of one browser and it survives a navigation. See
    hosting-state-model.md section 3.4: the registry is keyed per browser, not
    per tab.

    ⚠ This raises if `ui.run` receives no `storage_secret`. There is no fallback
    key on purpose. A constant fallback gives every browser one context, which is
    the defect that the registry removes, and no test reports it.
    """
    return app.storage.browser["id"]


def build_app(ruleset: RuleSet, character: Character, save_path: Path,
              *, ctx: dict | None = None, hosted: bool = False,
              home_path: str | None = None,
              on_lock: Callable[[], None] | None = None,
              in_campaign: bool = False,
              campaign_draft: str | None = None,
              top_bar_menu: Callable[[], None] | None = None) -> None:
    """Render the single-character builder. `ctx` is the shared app context; when
    omitted (running this module standalone) a private one is created, so the
    builder still works with no party involved.

    ⚠ `save_path` builds the fallback context and nothing else. It is not the save
    seam. The tabs receive `tab_save`, which reads the CURRENT `ctx["path"]`. This
    function keeps a path because it owns the file dialogs; a tab does not. See
    hosting-state-model.md section 3.5.

    `hosted` says that this session runs on a server and owns a directory there.
    It selects three behaviours, and it is ONE switch on purpose:

      1. The write-through auto-save timer starts.
      2. Save writes to `ctx["path"]` instead of sending a download.
      3. The session owns its destination: the hosted server gives each stored
         character its own file (`server/home.py`), and only it passes True.

    ⚠ Do not separate these. Auto-save with a shared path is N browsers writing
    one file on a timer, last writer wins, with no error. A server-side Save with
    a shared path is the same defect on a button. A deployment that can enable
    one without the others can configure that. See section 3.7.

    ⚠ The default is the desktop. `build_app` is embedded by the per-screen dev
    entry points and by the tests; a default of True makes each of them write.

    `home_path` says that the page shows ONE stored character of the hosted server
    (`server/home.py`). The top bar then has Home in place of Party, New and Load:
    the home page makes and imports characters, and the Party page is hidden until
    P3 (docs/plans/vtt.md 9.3a).

    `on_lock` runs after Finish & Lock. The hosted server shows a locked base on a
    page of its own, thus it saves and goes there.

    `in_campaign` is True for a campaign copy of the hosted server. Then Unlock,
    Adjust XP and Downtime are not built: the Storyteller unlocks and grants XP
    (p3-tables.md section 6, Q5, Q6). The ST Options tab builds no control: the
    Storyteller sets the house rules (section 5, Q2). ⚠ Not built, not hidden: a
    hidden button keeps its handler.

    `campaign_draft` is the name of the campaign for which this draft is made
    (p3-tables.md section 14, step 6b). The page says so, and the ST Options tab
    builds no control: the draft is built under the rules of the campaign.

    `top_bar_menu` draws a control at the left end of the top bar. The hosted
    server draws the button of its site menu there.
    """
    # ⚠ The seven tabs take a callback here and this function takes a path. That
    # asymmetry is deliberate, and it misleads: a caller that passes a save
    # callback gets an `os.PathLike` error from inside NiceGUI, in a page handler,
    # with no reference to this call. Name the mistake instead.
    if callable(save_path):
        raise TypeError(
            "build_app takes a save_path, not a save callback. The tabs take a "
            "callback; this function owns the file dialogs and needs the path. "
            "See hosting-state-model.md section 3.5a.")
    if ctx is None:
        ctx = make_context(character, save_path)
    state: dict = {"tab": "Edit", "select": None, "syncing": False}

    def tab_save(target: Character) -> None:
        """Write `target` to the path that this session points at now.

        The path changes when the user loads a file, starts a new character, or
        saves to a new name. Thus this function reads `ctx` at each call. A
        callback that captured the path would write to the previous file.

        ⚠ The tabs are built with `with_header=False`, thus none of them shows a
        Save button and none of them calls this today. The Save control of the
        app is `save()` below, which adds the file dialogs.
        """
        saving.save_to_path(ctx["path"], custom_dir=ctx["custom_dir"])(target)

    def _quiet_save(target: Character) -> None:
        """Write `target` to the current path and show no notification.

        The auto-save timer calls this. It reads `ctx` at each call, for the same
        reason that `tab_save` does.
        """
        saving.save_to_path(ctx["path"], notify=False,
                            custom_dir=ctx["custom_dir"])(target)

    # Made for each session, and before the handlers that reset it. The digest of
    # a 3 KB character costs 0.015 ms, thus the poll is free.
    auto = saving.AutoSave(
        _quiet_save, ctx["char"],
        on_error=lambda text: ui.notify(f"Auto-save failed: {text}", type="negative"))

    def _pal():
        """The palette for the current character's splat (red for Dragon-Blooded,
        gold for Solar). Re-derived on demand so loading/creating a character of a
        different splat re-themes the whole app."""
        return theme.palette(ctx["char"].exalt_type)

    ui.add_head_html(cytoscape_head_html())
    ui.add_head_html(_pal().head_style())

    if hosted:
        # ⚠ A poll, not a hook on the tabs. Three of the seven tabs define
        # `changed()`; the rest call their own refresh. A hook gives auto-save in
        # three tabs and silence in four, and no test fails. See section 3.7.
        ui.timer(saving.AUTOSAVE_SECONDS, lambda: auto.poll(ctx["char"]))

    # One charm_select handler for the whole app; dispatch to the picker's current
    # select (set whenever the Charms tab builds).
    ui.on("charm_select", lambda e: state["select"](e.args["id"]) if state["select"] else None)

    @ui.refreshable
    def content() -> None:
        char = ctx["char"]
        _apply_chrome()          # keep the header/background in sync with the splat
        _sync_tabs()             # Edit ⇄ XP swap follows the lock
        if state["tab"] == "Edit":
            editor.build_editor(ruleset, char, tab_save, with_header=False,
                                on_theme_change=_apply_chrome, in_campaign=in_campaign)
        elif state["tab"] == "Gear":
            # ⚠ A hosted campaign copy has "library_dir" None: it has no library.
            gear_mod.build_gear(ruleset, char, tab_save, with_header=False,
                                custom_dir=ctx.get("library_dir", ctx["custom_dir"]),
                                library=ctx.get("library_dir", True) is not None,
                                reload_library=ctx.get("reload_library"))
        elif state["tab"] == "Advantages":
            advantages.build_advantages(ruleset, char, tab_save, with_header=False)
        elif state["tab"] == "Charms":
            state["select"] = picker.build_picker(
                ruleset, char, tab_save, with_header=False, register_events=False)
        elif state["tab"] == "Combos":
            combos_mod.build_combos(ruleset, char, tab_save, with_header=False)
        elif state["tab"] == "Play":
            play_mod.build_play(ruleset, char, tab_save, with_header=False)
        elif state["tab"] == "ST":
            st_mod.build_storyteller(
                ruleset, char, tab_save, with_header=False,
                in_campaign=in_campaign or campaign_draft is not None)
        elif state["tab"] == "Custom":
            # Rule-set editing, not character editing: it takes no Character and is
            # the one tab whose edits outlive the open save. It mutates `ruleset` in
            # place, so every other tab sees new homebrew without a restart.
            custom_mod.build_custom(ruleset, custom_dir=ctx["custom_dir"],
                                    with_header=False)
        else:
            sheet_app.render_sheet(viewmod.build_sheet_view(ruleset, char))

    def select_tab(name: str) -> None:
        state["tab"] = name
        content.refresh()

    def _on_tab_change(name: str) -> None:
        # _sync_tabs writes the bar's value itself, which fires this handler back at
        # us; that echo must not re-enter the refresh it came from.
        if not state["syncing"]:
            select_tab(name)

    def _hosted_save() -> None:
        """Write the character to the destination that this session owns.

        Show no dialog. The session does not choose a server directory: the
        factory gave it one, and the auto-save timer already writes there. This
        button makes that write immediate and reports it.

        ⚠ Read `ctx["path"]` at call time. A Load or a New repoints it.
        """
        target = ctx["path"]
        try:
            persistence.save_character(ctx["char"], target,
                                       custom_dir=ctx["custom_dir"])
        except Exception as ex:                     # noqa: BLE001 - surface write errors
            ui.notify(f"Save failed: {ex}", type="negative")
            return
        auto.reset(ctx["char"])
        ui.notify(f"Saved {target.name}", type="positive")

    async def save() -> None:
        """Write the character. There are THREE deployments and each gets its own
        branch:

        hosted -> write to the session's own directory on the server, no dialog.
        native desktop window -> the OS "Save As" dialog (choose folder + name).
        plain browser -> a filename prompt, then a download to the browser.

        ⚠ The two-way version of this was silently wrong for a hosted run: every
        deployment that was not native downloaded, so a hosted Save showed a green
        "Downloading …" toast and left the server untouched. It looks like it
        worked. See hosting-per-instance.md, which records the branch and the
        first, reverted, fix.

        ⚠ That earlier fix read a module-level `_SERVER_SAVE_DIR`, and its own note
        says that was safe ONLY because the deployment was one player per process.
        That is no longer true. The destination here is `ctx["path"]`, which the
        session owns.
        """
        win = _native_window()
        default_name = persistence.suggested_filename(ctx["char"])
        if hosted:
            _hosted_save()
        elif win is not None:
            chosen = await win.create_file_dialog(
                _dialog_type("save"), directory=str(ctx["dir"]), save_filename=default_name)
            if not chosen:                              # cancelled
                return
            target = Path(chosen if isinstance(chosen, str) else chosen[0])
            try:
                persistence.save_character(ctx["char"], target,
                                           custom_dir=ctx["custom_dir"])
            except Exception as ex:                     # noqa: BLE001 - surface write errors
                ui.notify(f"Save failed: {ex}", type="negative")
                return
            ctx["path"], ctx["dir"] = target, target.parent
            ui.notify(f"Saved to {target}", type="positive")
        else:
            _open_browser_save_dialog(default_name)

    def _open_browser_save_dialog(default_name: str) -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Save character").classes("text-lg font-bold")
            ui.label("Downloads to your browser's download folder.").classes("text-sm text-gray-600")
            name_input = ui.input("File name", value=default_name).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Download", icon="download",
                          on_click=lambda: _browser_download(name_input.value, dialog)).props(f"color={_pal().button}")
        dialog.open()

    def _download_copy(filename: str) -> None:
        """Send the character to the browser as `filename`. Do not change `ctx`.

        The hosted "Download a copy" button calls this directly. See
        hosting-state-model.md section 5.1c.
        """
        ui.download.content(persistence.character_to_json(ctx["char"]).encode("utf-8"), filename)
        ui.notify(f"Downloading {filename}", type="positive")

    def _browser_download(name: str, dialog) -> None:
        filename = persistence.normalize_save_filename(name, ctx["char"])
        _download_copy(filename)
        # ⚠ Desktop only. Here the download IS the save, thus it sets the
        # destination. On a hosted run this line moves the auto-save target.
        ctx["path"] = ctx["dir"] / filename
        dialog.close()

    # ---- print / PDF export ----------------------------------------------- #
    # The button lives HERE and not on the Sheet tab on purpose: `render_sheet`
    # takes a SheetView and nothing else — no callbacks — and that purity is what
    # lets the GM party screen and the render tests reuse it. A button inside it
    # would need one.
    def export_pdf() -> None:
        default = pdf.suggested_filename(viewmod.build_sheet_view(ruleset, ctx["char"]))
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Export character sheet").classes("text-lg font-bold")
            ui.label("A print-ready PDF of the Sheet tab.").classes(
                "text-sm text-gray-600")
            # Paper size is a per-export choice (the human's call), not a stored
            # setting — so it is asked here rather than living in HouseRules.
            paper = ui.radio(list(pdf.PAPER_SIZES), value="A4").props("inline")
            name_input = ui.input("File name", value=default).classes("w-96")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("Export PDF", icon="picture_as_pdf",
                          on_click=lambda: _do_export(paper.value, name_input.value,
                                                      dialog)
                          ).props(f"color={_pal().button}")
        dialog.open()

    async def _do_export(paper: str, name: str, dialog) -> None:
        view = viewmod.build_sheet_view(ruleset, ctx["char"])
        try:
            data = pdf.build_pdf(view, paper=paper or "A4")
        except Exception as ex:                     # noqa: BLE001 - surface render errors
            ui.notify(f"Export failed: {ex}", type="negative")
            return
        filename = pdf.normalize_pdf_filename(name, view)
        dialog.close()
        # Same split as save(): the native window gets the OS dialog, a plain
        # browser gets a download.
        win = _native_window()
        if win is None:
            ui.download.content(data, filename)
            ui.notify(f"Downloading {filename}", type="positive")
            return
        chosen = await win.create_file_dialog(
            _dialog_type("save"), directory=str(ctx["dir"]), save_filename=filename)
        if not chosen:                              # cancelled
            return
        target = Path(chosen if isinstance(chosen, str) else chosen[0])
        try:
            target.write_bytes(data)
        except Exception as ex:                     # noqa: BLE001 - surface write errors
            ui.notify(f"Export failed: {ex}", type="negative")
            return
        ui.notify(f"Sheet written to {target}", type="positive")

    def _apply_loaded(loaded: Character, path: Path | None, source_label: str) -> None:
        """Swap in a freshly loaded character. With a real path, future saves land
        beside it; for an uploaded file (no path) they default to the save dir.

        The single funnel for every load, which is why the homebrew import happens
        here: a save from another table carries the definitions of the custom Charms
        it uses, and absorbing them into this machine's library is what makes those
        Charms resolve instead of showing as ⚠ rows. Both load paths pass
        `absorb_custom=False` so the count is still ours to report."""
        imported = custom_content.absorb_definitions(loaded, custom_dir=ctx["custom_dir"])
        if imported:
            rules_db.reload_custom_layer(ruleset, ctx["custom_dir"])
            ui.notify(f"Imported {len(imported)} homebrew definition(s) from this save",
                      type="info")
        ctx["char"] = loaded
        if path is not None:
            ctx["path"] = path
            ctx["dir"] = path.resolve().parent
        else:
            # An upload carries no path. It lands in the folder this session owns.
            ctx["dir"] = ctx["home_dir"]
            ctx["path"] = ctx["dir"] / persistence.suggested_filename(loaded)
        # ⚠ The new character reads as one large difference. Without this reset the
        # next poll writes it straight back over the file it came from.
        auto.reset(loaded)
        ui.notify(f"Loaded {loaded.name or source_label}", type="positive")
        select_tab("Sheet")

    def do_load(path_str: str, dialog) -> None:
        try:
            loaded = persistence.load_character(path_str, absorb_custom=False,
                                                custom_dir=ctx["custom_dir"])
        except Exception as ex:                       # noqa: BLE001 - surface any load error to the user
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded(loaded, Path(path_str), Path(path_str).stem)

    async def _on_upload(e, dialog) -> None:
        # NiceGUI 3.x: the event carries a FileUpload at e.file (was e.content/e.name
        # in 2.x), and reading it is async.
        try:
            loaded = persistence.character_from_json(await e.file.text())
        except Exception as ex:                       # noqa: BLE001 - surface any parse/validation error
            ui.notify(f"Load failed: {ex}", type="negative")
            return
        dialog.close()
        _apply_loaded(loaded, None, e.file.name)

    def new_character(dialog=None) -> None:
        ctx["char"] = Character(id=new_character_id())
        ctx["dir"] = ctx["home_dir"]
        ctx["path"] = ctx["dir"] / persistence.suggested_filename(ctx["char"])
        # ⚠ See the reset in `_apply_loaded`. A blank character is a large
        # difference too, and the timer would write it over the previous save.
        auto.reset(ctx["char"])
        if dialog is not None:
            dialog.close()
        ui.notify("Started a new character", type="positive")
        select_tab("Edit")

    def confirm_new() -> None:
        with ui.dialog() as dialog, ui.card():
            ui.label("Start a new character?").classes("text-lg font-bold")
            ui.label("Any unsaved changes to the current character will be lost.").classes("text-sm")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                ui.button("New character", on_click=lambda: new_character(dialog)).props(f"color={_pal().button}")
        dialog.open()

    def _do_unlock() -> None:
        lifecycle.unlock_chargen(ctx["char"])
        ui.notify("Chargen unlocked — editable again.", type="positive")
        select_tab("Edit")

    def unlock() -> None:
        if not ctx["char"].chargen_locked:
            ui.notify("Chargen is not locked.", type="info")
            return
        warning = viewmod.unlock_warning(ctx["char"])
        if not warning:
            _do_unlock()
            return
        # Ruled 2026-09-12: an Unlock after XP is allowed, with a warning.
        with ui.dialog() as dialog, ui.card().classes(f"w-[30rem] p-4 gap-2 {_pal().card_solid}"):
            ui.label("Unlock a character that has spent XP?").classes("text-base font-bold")
            ui.label(warning).classes("text-sm")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def confirm() -> None:
                    dialog.close()
                    _do_unlock()

                ui.button("Unlock", on_click=confirm, color="negative").mark("unlock-confirm")
        dialog.open()

    async def open_load() -> None:
        """Native desktop window -> the OS "Open" dialog; plain browser -> a dialog
        with a file picker (upload) plus a path field as a fallback."""
        win = _native_window()
        if win is not None:
            chosen = await win.create_file_dialog(
                _dialog_type("open"), directory=str(ctx["dir"]), allow_multiple=False,
                file_types=("Character files (*.json)", "All files (*.*)"))
            if not chosen:                              # cancelled
                return
            path = chosen[0] if isinstance(chosen, (list, tuple)) else chosen
            do_load(path, _NullDialog())
        else:
            _open_browser_load_dialog()

    def _open_browser_load_dialog() -> None:
        with ui.dialog() as dialog, ui.card().classes("gap-2"):
            ui.label("Load a character").classes("text-lg font-bold")
            ui.upload(label="Choose a .character.json file", auto_upload=True,
                      on_upload=lambda e: _on_upload(e, dialog)).classes("w-96")
            # ⚠ Desktop only. On a hosted run the path is a path on the SERVER: a
            # player could open the save of a different account, and the auto-save
            # then writes to it. See tests/test_hosted_save.py.
            if not hosted:
                ui.label("…or load by path:").classes("text-xs text-gray-600 mt-2")
                path_input = ui.input("Path to .character.json", value=str(ctx["path"])) \
                    .classes("w-96").mark("load-by-path")
            with ui.row():
                ui.button("Cancel", on_click=dialog.close).props("flat")
                if not hosted:
                    ui.button("Load path", on_click=lambda: do_load(path_input.value, dialog)
                              ).props(f"color={_pal().button}")
        dialog.open()

    def finish() -> None:
        errors = [i for i in validate.validate_chargen(ruleset, ctx["char"]) if i.severity == "error"]
        lifecycle.lock_chargen(ctx["char"], ruleset)
        if errors:
            ui.notify(f"Locked with {len(errors)} unresolved error(s) — see the Sheet", type="warning")
        else:
            ui.notify("Chargen finished and locked", type="positive")
        if on_lock is not None:
            on_lock()
            return
        select_tab("Sheet")

    # ---- top bar + tabs --------------------------------------------------- #
    def go_to_party() -> None:
        # Leaving the builder for the roster: stop pointing at a member, so a later
        # save/edit here isn't silently attributed to one.
        close_member(ctx)
        ui.navigate.to("/gm")

    def _stage() -> str:
        row = ctx.get("row")
        if row is not None and row.is_copy:
            return "Campaign copy"
        return "Locked" if ctx["char"].chargen_locked else "Draft"

    with ui.header().classes("items-center justify-between px-4 no-wrap") as header_el:
        # The left side says WHICH character this is. With several characters an
        # account cannot tell the pages apart by the splat alone.
        with ui.row().classes("items-center gap-1 no-wrap min-w-0"):
            if top_bar_menu is not None:
                top_bar_menu()
            if home_path is not None:
                ui.button("Home", icon="chevron_left",
                          on_click=lambda: ui.navigate.to(home_path)).props(
                    "flat dense no-caps color=white").mark("top-bar-home")
                ui.label("›").classes("text-white opacity-70")
            title_label = ui.label().classes("text-lg font-bold text-white truncate")
            title_label.bind_text_from(
                ctx, "char", backward=lambda c: c.name or "Unnamed character")
            subtitle_label = ui.label().classes("text-xs text-white opacity-80 ml-2")
        with ui.row().classes("items-center gap-2 no-wrap"):
            if home_path is None:
                # Always present: the party page is where characters are ADDED to a
                # party, so gating this on a non-empty party would make an empty one
                # unreachable — the only way in would be typing the URL.
                ui.button("Party", icon="groups", on_click=go_to_party).props(
                    "flat color=white").mark("top-bar-party").tooltip(
                    "Storyteller view — track the whole party at once")
                ui.button("New", icon="note_add", on_click=confirm_new).props(
                    "flat color=white").mark("top-bar-new")
            # ⚠ The mark is the handle a test clicks. `find("Save")` also matches
            # "Save As" and the dialog buttons, and `find(...).elements` is an
            # unordered set, thus the click would be ambiguous.
            ui.button("Save", icon="save",
                      on_click=save).props("flat color=white").mark("top-bar-save")
            # Only the lock action that applies is shown. `_apply_chrome` switches
            # them, because a lock and an unlock both refresh the content.
            lock_button = ui.button("Finish & Lock", icon="lock", on_click=finish).props(
                "flat color=white").mark("top-bar-lock")
            unlock_button = None if in_campaign else ui.button(
                "Unlock", icon="lock_open", on_click=unlock).props(
                "flat color=white").mark("top-bar-unlock")
            # The file actions that are not Save, in one menu.
            with ui.button(icon="more_vert").props("flat round color=white").tooltip(
                    "More: download, load, print" + (", log out" if hosted else "")):
                with ui.menu():
                    if hosted:
                        # On the desktop, Save is already the download. Section 5.1c.
                        ui.menu_item("Download a copy", on_click=lambda: _download_copy(
                            persistence.suggested_filename(ctx["char"]))
                        ).mark("top-bar-download")
                    if home_path is None:
                        ui.menu_item("Load…", on_click=open_load).mark("top-bar-load")
                    ui.menu_item("Print a PDF sheet…", on_click=export_pdf).mark("top-bar-print")
                    if hosted:
                        ui.separator()
                        # The server registers `/logout`. See server/auth.py.
                        ui.menu_item(nav.logout_label(auth.current_username()),
                                     on_click=lambda: ui.navigate.to("/logout")
                                     ).mark("top-bar-logout")

    def _apply_chrome() -> None:
        """Paint the header bar, title and page background from the current
        character's splat palette. Called on every content refresh, so switching
        tabs after changing the Exalt type re-themes the whole app."""
        pal = _pal()
        header_el.style(f"background:{pal.accent}")
        subtitle_label.set_text(f"{pal.splat_label} · {_stage()}")
        lock_button.set_visibility(not ctx["char"].chargen_locked)
        if unlock_button is not None:
            unlock_button.set_visibility(ctx["char"].chargen_locked)
        ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")
        # A Charm-Slot splat builds Arrays instead of Combos (p.89), so the tab is
        # relabelled for them. Only the LABEL changes — the tab keeps its "Combos"
        # name, so tab state, visibility and resolve_tab are untouched.
        if viewmod.has_combos_tab(ruleset, ctx["char"]):
            tabs["Combos"].props(
                f'label={"Arrays" if viewmod.uses_arrays(ruleset, ctx["char"]) else "Combos"}')

    _ICONS = {"Edit": "edit", "Gear": "inventory_2", "Advantages": "workspace_premium",
              "Charms": "account_tree", "Combos": "bolt",
              "XP": "trending_up", "Play": "casino", "ST": "gavel",
              "Custom": "construction", "Sheet": "description"}
    # Tab names are identifiers (state, visible_tabs, resolve_tab all key off them);
    # where a name reads badly on the bar, the LABEL differs — see Combos/Arrays.
    _LABELS = {"ST": "ST Options"}
    if campaign_draft is not None:
        ui.label(f"For {campaign_draft}: built under its house rules, and sent to its "
                 "Storyteller when you Finish & Lock.").classes(
            f"w-full text-sm px-3 py-1 rounded {_pal().card_soft}").mark(
            "draft-for-campaign")
    with ui.tabs(value="Edit").classes("w-full") as tab_bar:
        tabs = {name: ui.tab(name, label=_LABELS.get(name, name), icon=_ICONS[name])
                for name in _TABS}
    tab_bar.on_value_change(lambda e: _on_tab_change(e.value))

    def _sync_tabs() -> None:
        """Show the tabs this character's stage has (`visible_tabs`); Play appears at
        the lock, Combos disappears for a splat that builds neither. If the tab we are
        on is the one that just disappeared, land on its counterpart rather than
        rendering a tab that is no longer on the bar."""
        locked = ctx["char"].chargen_locked
        combos = viewmod.has_combos_tab(ruleset, ctx["char"])
        for name in _TABS:
            # ⚠ On a hosted character page the homebrew library is on /home: it
            # belongs to the account, not to this character.
            shown = name in visible_tabs(locked, combos=combos) and not (
                name == "Custom" and home_path is not None)
            tabs[name].set_visibility(shown)
        state["tab"] = resolve_tab(state["tab"], locked, combos=combos)
        if tab_bar.value != state["tab"]:
            state["syncing"] = True
            tab_bar.set_value(state["tab"])
            state["syncing"] = False

    content()


def register_pages(ruleset: RuleSet, ctx: dict,
                   key: Callable[[], str] = session_key) -> SessionRegistry:
    """Register the routes of the DESKTOP app: '/' the builder, '/gm' the
    Storyteller's party page. Return the registry of the session contexts.

    The hosted server does not call this. It registers `server/home.py`.

    `ctx` is the PROTOTYPE. Each browser session gets its own copy of it, from
    `session_context_factory`, and the two routes resolve that copy per request.
    Thus "Open in builder" and "back to Party" move between the two pages of ONE
    session without re-loading anything — the party member and the builder's
    character stay one object — and two browsers never share a Character.

    ⚠ Resolve the context in the page BODY. A context in the closure is the
    defect of hosting-state-model.md section 3.1: every browser then edits one
    Character, and every functional test still passes.

    `key` returns the registry key of the current request. The default is the
    browser key.

    ⚠ Each caller of this function must give `ui.run` a `storage_secret`. The
    session key comes from the session cookie, which needs one. See
    `session_key` and server/config.py.

    Both entry points (this module's main() and pack/run_app.py) call this, so the
    route set is declared exactly once.
    """
    # Imported here, not at module scope: ui/gm.py imports this module for the
    # shared context and the file-dialog helpers, so a top-level import would be
    # circular.
    from . import gm as gm_mod

    # The adversary templates, loaded once for whichever entry point got here, so
    # neither main() has to remember to. Left alone if a caller (a test) supplied
    # its own catalogue.
    if not ctx.get("adversary_catalog"):
        ctx["adversary_catalog"] = rules_db.load_adversary_catalog(_DATA_DIR)

    sessions = SessionRegistry(factory=session_context_factory(ctx, ruleset=ruleset))

    @ui.page("/")
    def index() -> None:
        session_ctx = sessions.ctx_for(key())
        build_app(session_ctx["ruleset"], session_ctx["char"], session_ctx["path"],
                  ctx=session_ctx)

    @ui.page("/gm")
    def party_page() -> None:
        session_ctx = sessions.ctx_for(key())
        gm_mod.build_gm(session_ctx["ruleset"], session_ctx)

    return sessions


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    """Load the rule set and the starting character. With a path, open that file;
    with none, start on a blank new character whose save lands next to the
    executable (see persistence.default_save_dir). The bundled example is no longer
    auto-loaded — open it via the path argument or the Load dialog."""
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)
    if character_path:
        path = Path(character_path)
        character = persistence.load_character(path)
        return ruleset, character, path
    character = Character(id=new_character_id())
    path = persistence.default_save_dir() / persistence.suggested_filename(character)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e Solar builder (unified app)")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--native", action="store_true", help="run in a native desktop window")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)
    register_pages(ruleset, make_context(character, path))

    # `storage_secret` signs the session cookie. Without it `app.storage.user`
    # raises, thus the per-session state of hosting-state-model.md section 3.4
    # cannot work. See server/config.py: a deployment sets EXALTED_STORAGE_SECRET,
    # and this process makes a random key if it does not.
    secret = storage_secret()

    if args.native:
        ui.run(title="Exalted 1e — Builder", reload=False, native=True,
               window_size=(1280, 900), storage_secret=secret)
    else:
        ui.run(title="Exalted 1e — Builder", reload=False, show=args.show,
               port=args.port, storage_secret=secret)


if __name__ in {"__main__", "__mp_main__"}:
    main()
