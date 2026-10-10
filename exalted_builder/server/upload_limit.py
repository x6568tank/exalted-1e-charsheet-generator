"""
server/upload_limit.py — the size limit of an upload body, on the server.

`ui.upload(max_file_size=...)` sets a prop of the Quasar control. The browser
applies it, and the server does not. The upload route of NiceGUI reads each body
to its end. Thus a client that posts to the route directly sends any size, and
the handler reads all of it into memory.

`UploadLimit` is an ASGI middleware. It refuses an upload body that is larger
than its limit with 413. It reads `Content-Length` first. It also counts the
bytes, because a chunked body has no `Content-Length`.

⚠ The limit is one value for each upload route. It must be at least the largest
`max_file_size` of a control, plus the multipart overhead. The handlers keep their
own smaller limits.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nicegui import app

# The largest control is the board image: 12 MB (`table_board_view.MAX_UPLOAD_BYTES`).
# The extra MB is for the multipart headers.
MAX_UPLOAD_BYTES = 13 * 1024 * 1024

# The upload route of NiceGUI: /_nicegui/client/<client id>/upload/<element id>.
_PREFIX = "/_nicegui/client/"
_PART = "/upload/"


class _TooLarge(Exception):
    pass


def is_upload(scope: Scope) -> bool:
    """Return True if `scope` is a POST to an upload route of NiceGUI."""
    path = scope.get("path", "")
    return (scope.get("type") == "http" and scope.get("method") == "POST"
            and path.startswith(_PREFIX) and _PART in path)


class UploadLimit:
    """Refuse an upload body of more than `limit` bytes with 413."""

    def __init__(self, app: ASGIApp, limit: int = MAX_UPLOAD_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not is_upload(scope):
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    if int(value) > self.limit:
                        await _refuse(send)
                        return
                except ValueError:
                    await _refuse(send, 400)
                    return

        received = 0
        started = False

        async def counted() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    raise _TooLarge
            return message

        async def tracked(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted, tracked)
        except _TooLarge:
            # ⚠ The route reads the whole form before it answers, thus no answer
            # has started. Check it all the same: a second start is an error.
            if not started:
                await _refuse(send)


async def _refuse(send: Send, status: int = 413) -> None:
    body = b"Upload too large." if status == 413 else b"Bad request."
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"text/plain"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


def install_upload_limit() -> None:
    """Add `UploadLimit` to the NiceGUI app. Do nothing if it is there."""
    if not any(middleware.cls is UploadLimit for middleware in app.user_middleware):
        app.add_middleware(UploadLimit)
