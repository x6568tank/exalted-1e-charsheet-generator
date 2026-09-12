"""
ui/saving.py — the save callback that a tab receives.

Each `build_*` tab takes a `save_fn`. It calls `save_fn(character)` and it knows
nothing more. A tab cannot see a file path, thus a tab cannot assume a file
system. A hosted deployment supplies a different callback and no tab changes.

See `docs/plans/hosting-state-model.md` section 3.5.
"""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from pathlib import Path

from nicegui import ui

from .. import persistence
from ..models.character import Character

# The type that every `build_*` tab takes as its third argument.
SaveFn = Callable[[Character], None]

# The auto-save poll interval, in seconds. The exposure to an eviction is one
# interval of edits.
#
# ⚠ This is a debounce. Do not save for each mutation: the dot tracks call their
# refresh for each click.
AUTOSAVE_SECONDS = 5.0


def save_to_path(save_path: Path | str, *, notify: bool = True,
                 custom_dir: Path | None = None) -> SaveFn:
    """Return a save function that writes a character to `save_path`.

    The function writes the file. With `notify`, it also shows a positive
    notification. A write error propagates to the caller.

    Use `notify=False` for a write that the user did not ask for. The auto-save
    timer does, because a toast for each interval hides the real messages.

    `custom_dir` is the homebrew library that the save copies definitions from.
    None is the default library. A hosted session gives its own.

    This is the desktop behaviour. Use it for a run that owns a file system.
    """
    target = Path(save_path)

    def save_fn(character: Character) -> None:
        persistence.save_character(character, target, custom_dir=custom_dir)
        if notify:
            ui.notify(f"Saved to {target}", type="positive")

    return save_fn


def character_digest(character: Character) -> str:
    """Return a digest of the bytes that a save of `character` writes.

    ⚠ The digest sees the serialized fields only. A tracker that is kept beside
    the Character, and not on it, does not change the digest and thus does not
    start an auto-save.
    """
    return hashlib.sha256(character.model_dump_json().encode("utf-8")).hexdigest()


class AutoSave:
    """A write-through auto-save, driven by a poll of the character's digest.

    `poll(character)` writes the character if its digest differs from the last
    written one. It returns True if it wrote. `reset(character)` adopts a
    character and its digest, and writes nothing.

    The caller polls this from a timer. See `AUTOSAVE_SECONDS`.

    ⚠ Do not replace the poll with a hook on a tab's `changed()`. Three of the
    seven tabs define one; the rest call their own refresh. A hook gives auto-save
    in three tabs and silence in four, and no test fails. A poll cannot be wired
    to the incorrect phase, because it is not wired to a phase.

    ⚠ The digest advances on a successful write only. A digest that advances on a
    failed write discards that edit: the next poll reads clean and the change is
    never written again.

    `on_error` receives the text of a write error. It is called one time for each
    run of failures, thus a broken destination does not report for each poll.

    See `docs/plans/hosting-state-model.md` section 3.7.
    """

    def __init__(self, save_fn: SaveFn, character: Character,
                 on_error: Callable[[str], None] | None = None) -> None:
        self._save_fn = save_fn
        self._on_error = on_error
        self._digest = character_digest(character)
        self._failing = False

    def reset(self, character: Character) -> None:
        """Adopt `character` as the saved state. Write nothing.

        ⚠ A Load and a New repoint the character. Without this, the change reads
        as one large difference and the next poll writes the new character back
        over the file that it came from.
        """
        self._digest = character_digest(character)
        self._failing = False

    def poll(self, character: Character) -> bool:
        """Write `character` if it changed since the last successful write.

        Return True if this call wrote the file. Return False if the character is
        unchanged, or if the write failed.

        ⚠ This catches the write error. A timer callback that raises is logged and
        not raised, thus the error is invisible. `on_error` reports it.
        """
        digest = character_digest(character)
        if digest == self._digest:
            return False
        try:
            self._save_fn(character)
        except Exception as ex:                  # noqa: BLE001 - report, never raise
            if not self._failing and self._on_error is not None:
                self._on_error(str(ex))
            self._failing = True
            return False
        self._digest = digest
        self._failing = False
        return True
