"""The size limit of an upload on the hosted server. `server/upload_limit.py`.

⚠ `ui.upload(max_file_size=...)` sets a prop of the Quasar control. The BROWSER
applies it. The upload route of NiceGUI reads each body to its end, thus a client
that posts to the route directly sends any size. Reproduced on a local server: a
300 MB POST to the import control answered 200, and the peak memory of the server
rose by about 300 MB. The container has `mem_limit: 2g`.

PRODUCTION wiring: `tests/_auth_main.py` installs the limit in the order of
`server/main.main`.
"""

from __future__ import annotations

import httpx
import pytest
from nicegui.testing import User
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from exalted_builder.server import upload_limit

pytest.importorskip("bcrypt")

from .test_auth_gate import _sign_up  # noqa: E402

MAIN = "tests/_auth_main.py"
UPLOAD = "/_nicegui/client/abc/upload/12"


def _app(limit: int) -> httpx.AsyncClient:
    """Return a client of a small app with one upload route behind the limit."""

    async def endpoint(request: Request) -> PlainTextResponse:
        body = await request.body()
        return PlainTextResponse(f"read {len(body)}")

    app = Starlette(routes=[Route(UPLOAD, endpoint, methods=["POST"]),
                            Route("/other", endpoint, methods=["POST"])])
    app.add_middleware(upload_limit.UploadLimit, limit=limit)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                             base_url="http://test")


@pytest.mark.asyncio
async def test_a_body_over_the_limit_is_refused_by_its_length() -> None:
    async with _app(1000) as client:
        response = await client.post(UPLOAD, content=b"x" * 1001)
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_a_body_over_the_limit_is_refused_with_no_length() -> None:
    """⚠ A chunked body has no Content-Length. The limit counts the bytes."""

    async def chunks():
        for _ in range(5):
            yield b"x" * 400

    async with _app(1000) as client:
        response = await client.post(UPLOAD, content=chunks())
    assert response.status_code == 413


@pytest.mark.asyncio
async def test_a_body_in_the_limit_reaches_the_route() -> None:
    async with _app(1000) as client:
        response = await client.post(UPLOAD, content=b"x" * 1000)
    assert response.status_code == 200
    assert response.text == "read 1000"


@pytest.mark.asyncio
async def test_a_route_that_is_not_an_upload_has_no_limit() -> None:
    async with _app(1000) as client:
        response = await client.post("/other", content=b"x" * 5000)
    assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_server_refuses_a_large_import(user: User) -> None:
    """The real route of the import control on `/home`, with the real middleware."""
    await _sign_up(user, "Harmonious")
    await user.should_see(marker="home-new")
    (control,) = user.find(marker="home-import").elements
    url = control.props["url"]  # The route that the browser posts to.

    big = b"x" * (upload_limit.MAX_UPLOAD_BYTES + 1)
    response = await user.http_client.post(
        url, files={"file": ("big.json", big, "application/json")})

    assert response.status_code == 413
