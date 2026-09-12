"""The Save button must write server-side on a hosted run.

`builder.save()` branched two ways: a native window gets the OS dialog, and
EVERYTHING ELSE downloads to the browser. That was correct while "plain browser"
meant *the process is yours, on your own machine* — a download was the only place
a file could go. A hosted run breaks the assumption: the browser is remote, and
there IS a canonical server-side home.

⚠ **The failure shape is why this file exists.** A hosted Save showed the player a
green *"Downloading …"* toast and left the volume untouched. **It looks like it
worked.** `docs/plans/hosting-per-instance.md` records the branch, the fix, and
that the fix was reverted in full.

⚠ Assert on the WRITTEN FILE, not on a flag being set. The reverted version's own
note says so: a flag that is set is "the single read site in the phase that wrote
it" and proves nothing about whether Save persists.

⚠ Read `test_the_desktop_branch_downloads_and_writes_nothing` as the control. It
is what shows these cases can tell the two branches apart.
"""

import pytest
from nicegui.testing import User

from exalted_builder import persistence
from exalted_builder.ui import builder

from . import _hosted_save_state as state

MAIN = "tests/_hosted_save_main.py"

# The text of the browser download dialog. It must appear on the desktop branch
# and never on the hosted one.
DOWNLOAD_PROMPT = "Downloads to your browser's download folder."


def _hosted_ctx() -> dict:
    """The live context of the one hosted session, read out of the registry."""
    keys = state.REGISTRY.keys()
    assert keys, "No session reached the registry. The page did not resolve a context."
    return state.REGISTRY.ctx_for(keys[-1])


# --------------------------------------------------------------------------- #
# The hosted branch
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_save_writes_the_session_file(create_user) -> None:
    """🐞 The defect. Save on a hosted run must put bytes on the server."""
    user = create_user()
    await user.open("/")
    await user.should_see("Identity")

    ctx = _hosted_ctx()
    ctx["char"].name = "HostedSaveName"
    target = ctx["path"]
    assert not target.exists(), "The session file exists before Save was clicked."

    user.find("top-bar-save").click()
    await user.should_see("Saved")

    assert target.exists(), (
        f"Save wrote nothing to {target}. The hosted branch fell through to the "
        "browser download, which shows a green toast over an empty volume."
    )
    assert persistence.load_character(target).name == "HostedSaveName"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_save_does_not_also_offer_a_download(create_user) -> None:
    """The hosted branch must not ALSO reach the filename prompt.

    ⚠ **`should_not_see` alone cannot test this, and the first version of this
    case passed against the defect.** It returns on the first attempt at which the
    text is absent, so it races the async click handler: the dialog had not opened
    yet, the check found nothing, and the case went green while `save()` still had
    the two-way branch.

    The `should_see` below is what removes the race. It waits for the hosted
    branch to finish, and only then is the absence of the prompt meaningful.
    ⚠ Keep the two lines in this order.
    """
    user = create_user()
    await user.open("/")
    await user.should_see("Identity")

    user.find("top-bar-save").click()
    await user.should_see("Saved")          # settles the handler; do not remove

    await user.should_not_see(DOWNLOAD_PROMPT)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_save_stays_inside_the_session_directory(create_user) -> None:
    """Save must not become a second way out of the session's own folder.

    The New handler already did exactly that by recomputing the destination from a
    process-wide default. See `tests/test_session_destinations.py`.
    """
    user = create_user()
    await user.open("/")
    await user.should_see("Identity")

    user.find("top-bar-save").click()
    await user.should_see("Saved")

    written = [p for p in state.ROOT.rglob("*.character.json")]

    assert written, f"Nothing was written under {state.ROOT}."
    for path in written:
        assert path.is_relative_to(state.ROOT)


# --------------------------------------------------------------------------- #
# The SECOND site, which the plan never named
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_party_save_writes_the_file(create_user) -> None:
    """🐞 `gm.save_party()` carried the identical two-way branch, and `/gm` is a
    hosted route.

    ⚠ **This is the house bug.** Every document described the defect as
    *"`builder.save()`'s two-way branch"*, singular. Fixing only that leaves a
    hosted Storyteller clicking "Save party" and getting a download, with the
    server keeping nothing — the same failure, one page over, and `vtt.md`'s trap
    list would have read as closed.

    Found by grepping `_native_window` rather than by reading the plan.
    """
    user = create_user()
    await user.open("/gm")
    await user.should_see("Save party")

    user.find("gm-save-party").click()
    await user.should_see("Saved party")

    written = list(state.ROOT.rglob("*.party.json"))

    assert written, (
        f"Nothing was written under {state.ROOT}. The party Save fell through to "
        "the browser download, so a hosted Storyteller's roster is not on the "
        "server."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_party_save_does_not_also_offer_a_download(create_user) -> None:
    """⚠ The `should_see` settles the async handler. See
    `test_hosted_save_does_not_also_offer_a_download` for why absence alone lies.
    """
    user = create_user()
    await user.open("/gm")
    await user.should_see("Save party")

    user.find("gm-save-party").click()
    await user.should_see("Saved party")        # settles the handler; do not remove

    await user.should_not_see(DOWNLOAD_PROMPT)


# --------------------------------------------------------------------------- #
# The control: the desktop branch is unchanged
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_desktop_branch_downloads_and_writes_nothing(create_user) -> None:
    """THE CONTROL for this file.

    A run with no hosted flag keeps the browser download: the filename prompt
    opens and no file appears. Without this case, the hosted assertions above pass
    against a Save that writes a file on EVERY deployment, which would be a
    different bug — a remote browser silently writing onto the server operator's
    disk.
    """
    user = create_user()
    await user.open("/desktop")
    await user.should_see("Identity")

    user.find("top-bar-save").click()

    await user.should_see(DOWNLOAD_PROMPT)
    assert not state.DESKTOP_DIR.exists() or not list(state.DESKTOP_DIR.glob("*.json")), (
        f"The desktop branch wrote into {state.DESKTOP_DIR}. Save must still offer "
        "a download when the run is not hosted."
    )


# --------------------------------------------------------------------------- #
# "Download a copy" — section 5.1c
# --------------------------------------------------------------------------- #
#
# ⚠ THE TRAP. The desktop download helpers set `ctx["path"]` and
# `ctx["party_path"]` from the downloaded filename. On a hosted run that moves the
# destination of the auto-save timer. These cases assert that `ctx` is UNCHANGED.
# A case that asserts only that a download happened passes with the trap present.


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_download_gives_the_character(create_user) -> None:
    """The hosted character download delivers the current character."""
    user = create_user()
    await user.open("/")
    await user.should_see("Identity")

    ctx = _hosted_ctx()
    ctx["char"].name = "DownloadedName"

    user.find("top-bar-download").click()
    response = await user.download.next()

    assert persistence.character_from_json(response.text).name == "DownloadedName"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_download_does_not_move_the_save_destination(create_user) -> None:
    """🐞 The trap. A download must leave `ctx["path"]` and `ctx["dir"]` alone.

    ⚠ The name edit is what makes this case discriminate. The desktop helper sets
    `ctx["path"]` to a name derived from the character. Without an edit, that name
    is the one already in `ctx["path"]`, and a repoint is invisible.
    """
    user = create_user()
    await user.open("/")
    await user.should_see("Identity")

    ctx = _hosted_ctx()
    ctx["char"].name = "RenamedBeforeDownload"
    path_before, dir_before = ctx["path"], ctx["dir"]
    assert persistence.suggested_filename(ctx["char"]) != path_before.name, (
        "The fixture cannot see a repoint: the downloaded name equals the "
        "current destination."
    )

    user.find("top-bar-download").click()
    await user.download.next()

    assert ctx["path"] == path_before, (
        f"The download moved the save destination from {path_before} to "
        f"{ctx['path']}. The auto-save timer now writes to a name from a download."
    )
    assert ctx["dir"] == dir_before
    written = list(dir_before.glob("*.json")) if dir_before.exists() else []
    assert written in ([], [path_before]), (
        f"The download wrote a file into the session directory: {written}."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_party_download_gives_the_party(create_user) -> None:
    """The SECOND site. A hosted Storyteller can take the party bundle out."""
    user = create_user()
    await user.open("/gm")
    await user.should_see("Save party")

    ctx = _hosted_ctx()
    ctx["party"].name = "DownloadedParty"

    user.find("gm-download-party").click()
    response = await user.download.next()

    assert persistence.party_from_json(response.text).name == "DownloadedParty"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_hosted_party_download_does_not_move_the_save_destination(
        create_user) -> None:
    """🐞 The trap at the second site. `ctx["party_path"]` must not change.

    ⚠ It starts as None, and the desktop helper sets it to a path. Thus a repoint
    is visible here with no edit.
    """
    user = create_user()
    await user.open("/gm")
    await user.should_see("Save party")

    ctx = _hosted_ctx()
    party_path_before, path_before = ctx["party_path"], ctx["path"]

    user.find("gm-download-party").click()
    await user.download.next()

    assert ctx["party_path"] == party_path_before, (
        f"The party download set the party save destination to "
        f"{ctx['party_path']}. The next Save party writes to a download name."
    )
    assert ctx["path"] == path_before


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_download_buttons_are_present_hosted(create_user) -> None:
    """The gate, first direction. Without this case, the absence cases below pass
    against a button that never renders.

    Log out takes the same hosted bit. The server registers `/logout`; this main
    file does not, and the button needs only to render here."""
    user = create_user()
    await user.open("/")
    await user.should_see(marker="top-bar-download")
    await user.should_see(marker="top-bar-logout")

    await user.open("/gm")
    await user.should_see(marker="gm-download-party")
    await user.should_see(marker="gm-logout")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_download_buttons_are_absent_on_the_desktop(create_user) -> None:
    """The gate, second direction. On the desktop, Save is already the download.

    ⚠ The `should_see` of the Save mark comes first. It shows that the header
    rendered, thus the absence of the download mark is meaningful.
    """
    user = create_user()
    await user.open("/desktop")
    await user.should_see(marker="top-bar-save")
    await user.should_not_see(marker="top-bar-download")
    await user.should_not_see(marker="top-bar-logout")

    await user.open("/desktop-gm")
    await user.should_see(marker="gm-save-party")
    await user.should_not_see(marker="gm-download-party")
    await user.should_not_see(marker="gm-logout")


# --------------------------------------------------------------------------- #
# Load by path — the server's file system is not the player's
# --------------------------------------------------------------------------- #
#
# 🐞 Found 2026-09-12, live on the deployed server. Each browser Load dialog had a
# path field. On a hosted run a player could type the save path of a different
# account: the builder opened that character and pointed the auto-save at the
# file, thus the player could read and overwrite it. The field showed the
# player's own server path as its default, which gave the folder names.
#
# ⚠ Each case settles on the upload control first. It shows that the dialog
# rendered, thus the absence of the path field is meaningful.

_PATH_DIALOGS = [
    # (route, button mark, text the dialog shows)
    ("/", "top-bar-load", "Choose a .character.json file"),
    ("/gm", "gm-load-party", "Choose a .party.json file"),
    ("/gm", "gm-add-character", "Choose a .character.json file"),
]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("route,button,upload_text", _PATH_DIALOGS)
async def test_a_hosted_load_dialog_takes_no_server_path(
        create_user, route, button, upload_text) -> None:
    user = create_user()
    await user.open(route)
    user.find(button).click()
    await user.should_see(upload_text)
    await user.should_not_see(marker="load-by-path")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("route,button,upload_text", _PATH_DIALOGS)
async def test_the_desktop_load_dialog_keeps_its_path_field(
        create_user, route, button, upload_text) -> None:
    """The control. Without it, the hosted cases pass against a mark that is on
    no element."""
    user = create_user()
    await user.open({"/": "/desktop", "/gm": "/desktop-gm"}[route])
    user.find(button).click()
    await user.should_see(upload_text)
    await user.should_see(marker="load-by-path")


# --------------------------------------------------------------------------- #
# The one-switch rule
# --------------------------------------------------------------------------- #


def test_build_app_has_one_hosted_switch_and_it_defaults_off() -> None:
    """⚠ Destination isolation, auto-save and server-side Save are ONE bit.

    A deployment that could enable them separately could configure the hazardous
    pair that section 3.7 names — a timer over a shared path — and now a second
    one: a Save that writes server-side to a destination every session shares.

    ⚠ A separate `auto_save` parameter must NOT come back. That is what this case
    is for.
    """
    import inspect

    parameters = inspect.signature(builder.build_app).parameters

    assert "hosted" in parameters, (
        "build_app lost its `hosted` switch. Destination isolation, auto-save and "
        "server-side Save all read it."
    )
    assert parameters["hosted"].default is False, (
        "The default must be the desktop. A default of True makes every embedding "
        "of build_app write server-side."
    )
    assert "auto_save" not in parameters, (
        "`auto_save` is back as its own parameter. It can then disagree with the "
        "hosted flag, which is the configurable hazard the single switch removes."
    )
