"""
ui/saving.py — the save callback that a tab receives.

Each `build_*` tab takes a `save_fn`. It calls `save_fn(character)` and it knows
nothing more. A tab cannot see a file path, thus a tab cannot assume a file
system. A hosted deployment supplies a different callback and no tab changes.

See `docs/plans/hosting-state-model.md` section 3.5.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from nicegui import ui

from .. import persistence
from ..models.character import Character

# The type that every `build_*` tab takes as its third argument.
SaveFn = Callable[[Character], None]


def save_to_path(save_path: Path | str) -> SaveFn:
    """Return a save function that writes a character to `save_path`.

    The function writes the file, then it shows a positive notification. A write
    error propagates to the caller.

    This is the desktop behaviour. Use it for a run that owns a file system.
    """
    target = Path(save_path)

    def save_fn(character: Character) -> None:
        persistence.save_character(character, target)
        ui.notify(f"Saved to {target}", type="positive")

    return save_fn
