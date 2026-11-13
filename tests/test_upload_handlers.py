"""Each upload handler checks the file size before it reads: `ui/upload_check.py`.

`ui.upload(max_file_size=...)` is a browser-side prop.
`server/upload_limit.py` limits the request; these tests cover the handlers.

PRODUCTION wiring: `tests/_auth_main.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from nicegui.elements.upload_files import FileUpload
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder.server import chrome  # noqa: E402

from .test_auth_gate import _sign_up  # noqa: E402
from .test_table_board_view import _ask  # noqa: E402
from .test_table_view import _campaign  # noqa: E402

MAIN = "tests/_auth_main.py"


@dataclass
class _Huge(FileUpload):
    """A file over every limit. A read fails the test: the check must come first."""

    def size(self) -> int:
        return 50 * 2**20

    async def read(self) -> bytes:
        raise AssertionError("The handler read the file before the size check.")

    async def text(self, encoding: str = "utf-8") -> str:
        return (await self.read()).decode(encoding)

    def iterate(self, *, chunk_size: int = 2**20):
        raise AssertionError("The handler read the file before the size check.")

    async def save(self, path) -> None:
        raise AssertionError("The handler saved the file before the size check.")


async def _send_huge(user: User, marker: str) -> None:
    (upload,) = [e for e in user.client.elements.values()
                 if marker in getattr(e, "_markers", [])]
    with user.client:
        await upload.handle_uploads([_Huge(name="huge.bin", content_type="x")])


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_character_import_checks_the_size_first(user: User, caplog) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")

    await _send_huge(user, "home-import")

    await user.should_see("The limit for an upload is 2 MB.")
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_homebrew_import_checks_the_size_first(user: User, caplog) -> None:
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    user.find("Homebrew").click()
    await user.should_see(marker="custom-import")

    await _send_huge(user, "custom-import-upload")

    await user.should_see("The limit for an upload is 2 MB.")
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_background_upload_checks_the_size_first(create_user, caplog) -> None:
    st, _, table, _ = await _campaign(create_user, "Ashes of Dawn")
    await st.open(chrome.table_url(table.id))
    await st.should_see(marker="board-st-menu")

    await _send_huge(st, "board-upload")

    await st.should_see("The limit for an upload is 12 MB.")
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_token_image_upload_checks_the_size_first(create_user, caplog) -> None:
    _, _, table, [(player, _, _)] = await _campaign(create_user, "Ashes of Dawn")
    await player.open(chrome.table_url(table.id))
    await player.should_see(marker="board-stage")
    await _ask(player, {"kind": "token", "x": 1, "y": 2})

    await _send_huge(player, "board-token-upload")

    await player.should_see("The limit for an upload is 12 MB.")
    assert not [r for r in caplog.records if r.levelname == "ERROR"]
