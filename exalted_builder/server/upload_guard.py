"""
server/upload_guard.py — the size limit on the upload requests of NiceGUI.

`ui.upload(max_file_size=...)` sets a prop that only the browser applies. The
upload route of NiceGUI spools each body to disk with no limit. This middleware
refuses a body over `MAX_UPLOAD_REQUEST_BYTES` before a route reads it.
"""

from __future__ import annotations

import re

# The largest file limit of an upload control is 12 MB (the board). The rest is
# room for the multipart form around the file.
MAX_UPLOAD_REQUEST_BYTES = 13 * 1024 * 1024

# The route of each `ui.upload`: /_nicegui/client/<client id>/upload/<element id>.
_UPLOAD_PATH = re.compile(r"^/_nicegui/client/[^/]+/upload/[^/]+/?$")


class UploadGuard:
    """An ASGI middleware. Limit the body of each POST to an upload route.

    Refuse a declared length over the limit with 413, before the route runs.
    Count the body of each other upload as it arrives. When the count passes the
    limit, give the route `http.disconnect`. ⚠ Count also when the length header
    is present: a client can declare a false length.
    """

    def __init__(self, app, limit: int = MAX_UPLOAD_REQUEST_BYTES) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send) -> None:
        if (scope["type"] != "http" or scope.get("method") != "POST"
                or not _UPLOAD_PATH.match(scope.get("path", ""))):
            await self.app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self.limit:
            await _refuse(send)
            return
        count = 0

        async def counted():
            nonlocal count
            message = await receive()
            if message["type"] == "http.request":
                count += len(message.get("body", b""))
                if count > self.limit:
                    return {"type": "http.disconnect"}
            return message

        await self.app(scope, counted, send)


def _content_length(scope) -> int | None:
    """Return the Content-Length of `scope`, or None if it is absent or not a number."""
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _refuse(send) -> None:
    await send({"type": "http.response.start", "status": 413,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
    await send({"type": "http.response.body", "body": b"The upload is too large."})
