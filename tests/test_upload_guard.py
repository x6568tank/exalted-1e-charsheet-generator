"""The size limit on upload requests: `server/upload_guard.py`.

Server review finding 4. `ui.upload(max_file_size=...)` is a browser-side prop. The
upload route of NiceGUI spools each body to disk with no limit, and the handlers
read the whole file. The guard refuses a large body before any route reads it.
"""

from __future__ import annotations

import asyncio

import pytest
from nicegui import app
from nicegui.testing import User

from exalted_builder.server import upload_guard
from exalted_builder.server.upload_guard import MAX_UPLOAD_REQUEST_BYTES, UploadGuard

UPLOAD = "/_nicegui/client/abc123/upload/42"
LIMIT = MAX_UPLOAD_REQUEST_BYTES


def _scope(path: str = UPLOAD, method: str = "POST",
           length: int | None = None) -> dict:
    headers = [] if length is None else [(b"content-length", str(length).encode())]
    return {"type": "http", "method": method, "path": path, "headers": headers}


class _App:
    """An ASGI app that reads the whole body, as the upload route does."""

    def __init__(self) -> None:
        self.called = False
        self.read = 0
        self.disconnected = False

    async def __call__(self, scope, receive, send) -> None:
        self.called = True
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                self.disconnected = True
                return
            self.read += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})


def _run(scope: dict, chunks: list[int]) -> tuple[_App, list[dict]]:
    app, sent = _App(), []
    queue = [{"type": "http.request", "body": b"x" * n, "more_body": i < len(chunks) - 1}
             for i, n in enumerate(chunks)]

    async def receive():
        return queue.pop(0) if queue else {"type": "http.disconnect"}

    async def send(message):
        sent.append(message)

    asyncio.run(UploadGuard(app)(scope, receive, send))
    return app, sent


def test_the_limit_takes_the_largest_upload_with_room_for_the_form() -> None:
    from exalted_builder.server.table_board_view import MAX_UPLOAD_BYTES
    assert MAX_UPLOAD_BYTES < LIMIT <= MAX_UPLOAD_BYTES + 2 * 2**20


def test_a_declared_length_over_the_limit_is_refused_before_the_route() -> None:
    app, sent = _run(_scope(length=LIMIT + 1), [10])

    assert not app.called
    assert sent[0]["status"] == 413


def test_a_chunked_body_over_the_limit_stops_the_route() -> None:
    """A body with no length header is counted as it arrives."""
    chunk = 2**20
    app, _ = _run(_scope(), [chunk] * (LIMIT // chunk + 2))

    assert app.disconnected
    assert app.read <= LIMIT


def test_a_false_small_length_does_not_pass_a_large_body() -> None:
    chunk = 2**20
    app, _ = _run(_scope(length=10), [chunk] * (LIMIT // chunk + 2))

    assert app.disconnected


def test_an_upload_in_the_limit_passes() -> None:
    app, sent = _run(_scope(length=LIMIT), [LIMIT // 2, LIMIT // 2])

    assert app.read == LIMIT // 2 * 2 and not app.disconnected
    assert sent[0]["status"] == 200


@pytest.mark.parametrize("scope", [
    _scope(path="/home", length=LIMIT + 1),
    _scope(method="GET", length=LIMIT + 1),
])
def test_other_requests_pass_untouched(scope: dict) -> None:
    app, sent = _run(scope, [LIMIT + 1])

    assert app.read == LIMIT + 1
    assert sent[0]["status"] == 200


# --------------------------------------------------------------------------- #
# The production wiring
# --------------------------------------------------------------------------- #

pytest.importorskip("bcrypt")

from .test_auth_gate import _sign_up  # noqa: E402

MAIN = "tests/_auth_main.py"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_server_refuses_a_large_upload_request(user: User) -> None:
    """⚠ The guard works only if `install_gate` installs it."""
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    (upload,) = user.find(marker="home-import").elements
    url = upload.props["url"]

    response = await user.http_client.post(
        url, content=b"x" * (LIMIT + 1),
        headers={"content-type": "multipart/form-data; boundary=x"})

    assert response.status_code == 413
    assert upload_guard.UploadGuard in [m.cls for m in app.user_middleware]


# --------------------------------------------------------------------------- #
# Each handler checks the size before it reads
# --------------------------------------------------------------------------- #

from dataclasses import dataclass  # noqa: E402

from nicegui.elements.upload_files import FileUpload  # noqa: E402

from exalted_builder.server import chrome  # noqa: E402

from .test_table_board_view import _ask  # noqa: E402
from .test_table_view import _campaign  # noqa: E402


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
