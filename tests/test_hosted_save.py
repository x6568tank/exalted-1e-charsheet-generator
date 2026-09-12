"""The desktop side of the hosted Save, and the one-switch rule.

`builder.save()` has three branches: hosted writes to the server, a native window
gets the OS dialog, and a plain browser downloads. The hosted cases are in
`tests/test_character_pages.py`, on the production pages of `server/home.py`.
This file holds their CONTROL: the desktop still downloads and writes nothing.
Without it, the hosted cases pass against a Save that writes a file on EVERY
deployment, which is a different bug — a remote browser writing onto the disk
of the server operator.

⚠ The history of the defect is in `docs/plans/hosting-per-instance.md`: a hosted
Save showed a green "Downloading …" toast and left the volume untouched.
"""

import pytest
from nicegui.testing import User

from exalted_builder.ui import builder

from . import _hosted_save_state as state

MAIN = "tests/_hosted_save_main.py"

# The text of the browser download dialog. It must appear on the desktop branch
# and never on the hosted one.
DOWNLOAD_PROMPT = "Downloads to your browser's download folder."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_desktop_branch_downloads_and_writes_nothing(create_user) -> None:
    """THE CONTROL for this file.

    A run with no hosted flag keeps the browser download: the filename prompt
    opens and no file appears. Without this case, the hosted cases of
    `test_character_pages.py` pass against a Save that writes a file on EVERY
    deployment.
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


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_download_buttons_are_absent_on_the_desktop(create_user) -> None:
    """On the desktop, Save is already the download, and there is no login.

    ⚠ The `should_see` of the Save mark comes first. It shows that the header
    rendered, thus the absence of the download mark is meaningful.
    """
    user = create_user()
    await user.open("/desktop")
    await user.should_see(marker="top-bar-save")
    await user.should_not_see(marker="top-bar-download")
    await user.should_not_see(marker="top-bar-logout")


# The desktop load dialogs keep their path field. On the server a path from the
# browser is a path on the SERVER (closed 2026-09-12, `beda3ec`); the hosted pages
# have no Load at all, and `test_character_pages.py` asserts that.
_PATH_DIALOGS = [
    # (route, button mark, text the dialog shows)
    ("/desktop", "top-bar-load", "Choose a .character.json file"),
    ("/desktop-gm", "gm-load-party", "Choose a .party.json file"),
    ("/desktop-gm", "gm-add-character", "Choose a .character.json file"),
]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
@pytest.mark.parametrize("route,button,upload_text", _PATH_DIALOGS)
async def test_the_desktop_load_dialog_keeps_its_path_field(
        create_user, route, button, upload_text) -> None:
    """The desktop keeps the path field. It also shows that the `load-by-path`
    mark is on a real element, thus the hosted absence is meaningful."""
    user = create_user()
    await user.open(route)
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
