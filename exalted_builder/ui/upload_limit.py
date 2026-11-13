"""
ui/upload_limit.py — the size check that an upload handler does before it reads.

`ui.upload(max_file_size=...)` is a prop that only the browser applies. A request
that a program makes skips it. Thus each handler checks the size again.
"""

from __future__ import annotations


def too_large(file, limit: int) -> str | None:
    """Return the refusal text if `file` has more than `limit` bytes. Else return None.

    `file` is the `FileUpload` of an upload event. ⚠ Call this before `read` or
    `text`. A read puts the whole file in memory.
    """
    size = file.size()
    if size <= limit:
        return None
    return (f"That file is {size / 2**20:.1f} MB. "
            f"The limit for an upload is {limit / 2**20:.2g} MB.")
