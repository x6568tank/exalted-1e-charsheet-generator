"""The write-through auto-save — `hosting-state-model.md` section 3.7.

The trigger is a dirty hash, polled by a timer. It is NOT a hook on the tabs'
`changed()`.

⚠ Why not `changed()`: only three of the seven tabs define one. The others funnel
through `combos.refresh()` and direct `body.refresh()` / `detail.refresh()` calls.
A hook on `changed()` gives auto-save in three tabs and silence in four, with
every test green — `CLAUDE.md` section 7's house bug. The plan itself carried that
false claim; see section 3.7a.

The hash has two properties that a funnel call does not:

  * It cannot be wired to the wrong phase, because it is not wired to a phase. A
    mutation site added later is covered with no action.
  * It fires when the bytes that would be written differ. A funnel call is a
    lossy proxy: `readout.refresh()` after a FAILED purchase would write a
    byte-identical file.

⚠ It sees only what serializes. `Character.play` is a real field (PlayState), thus
the play tab's spent Willpower, fatigue and health boxes are covered. A tracker
kept BESIDE the Character would not be.

The wiring into the page is `tests/test_character_pages.py`; a correct
mechanism that nothing calls is this project's usual defect.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder import persistence
from exalted_builder.models.character import Character, PlayState
from exalted_builder.ui import saving


def _char(**kw) -> Character:
    kw.setdefault("name", "Auto Save")
    return Character(id="as", caste="dawn", **kw)


class _Recorder:
    """A save function that records the characters it receives."""

    def __init__(self, fail: bool = False) -> None:
        self.saved: list[Character] = []
        self.fail = fail

    def __call__(self, character: Character) -> None:
        if self.fail:
            raise OSError("disk full")
        self.saved.append(character)


# --------------------------------------------------------------------------- #
# The digest
# --------------------------------------------------------------------------- #

def test_two_equal_characters_have_one_digest() -> None:
    assert saving.character_digest(_char()) == saving.character_digest(_char())


def test_a_trait_change_changes_the_digest() -> None:
    char = _char()
    before = saving.character_digest(char)
    char.attributes["strength"] = 3

    assert saving.character_digest(char) != before


def test_a_play_state_change_changes_the_digest() -> None:
    """⚠ The play tab is the one that could have been invisible here. Its tracker
    is `Character.play`, a real field, thus it serializes."""
    char = _char()
    char.play = PlayState()
    before = saving.character_digest(char)
    char.play.willpower_spent = 2

    assert saving.character_digest(char) != before, (
        "The play tab's edits do not reach the digest. Auto-save never fires for "
        "them and the tracker is lost on eviction."
    )


# --------------------------------------------------------------------------- #
# The poll
# --------------------------------------------------------------------------- #

def test_a_clean_character_is_not_written() -> None:
    """⚠ The load-bearing case. A poll that always writes turns the timer into a
    write every interval for every idle session."""
    char = _char()
    recorder = _Recorder()
    auto = saving.AutoSave(recorder, char)

    assert auto.poll(char) is False
    assert recorder.saved == []


def test_a_dirty_character_is_written_once() -> None:
    char = _char()
    recorder = _Recorder()
    auto = saving.AutoSave(recorder, char)

    char.name = "Edited"

    assert auto.poll(char) is True
    assert auto.poll(char) is False, "The second poll wrote an unchanged character."
    assert len(recorder.saved) == 1
    assert recorder.saved[0] is char


def test_each_change_is_written() -> None:
    char = _char()
    recorder = _Recorder()
    auto = saving.AutoSave(recorder, char)

    char.name = "One"
    auto.poll(char)
    char.name = "Two"
    auto.poll(char)

    assert len(recorder.saved) == 2


def test_reset_adopts_a_new_character_without_writing() -> None:
    """⚠ Load and New repoint the character. That reads as one enormous diff, and
    the timer would write the just-loaded file back over itself."""
    recorder = _Recorder()
    auto = saving.AutoSave(recorder, _char())

    loaded = _char(name="Loaded From Disk")
    auto.reset(loaded)

    assert auto.poll(loaded) is False, (
        "The baseline still describes the previous character, thus the first poll "
        "after a Load writes."
    )
    assert recorder.saved == []


def test_a_change_after_a_reset_is_written() -> None:
    """The negative control for the test above. `reset` must not stop the poll."""
    recorder = _Recorder()
    auto = saving.AutoSave(recorder, _char())
    loaded = _char(name="Loaded")
    auto.reset(loaded)

    loaded.name = "Edited After Load"

    assert auto.poll(loaded) is True
    assert len(recorder.saved) == 1


# --------------------------------------------------------------------------- #
# Failure
# --------------------------------------------------------------------------- #

def test_a_failed_write_is_retried() -> None:
    """⚠ The baseline advances on a SUCCESSFUL write only. A baseline that
    advances on failure discards the edit: the next poll reads clean and that
    change is never written again."""
    char = _char()
    recorder = _Recorder(fail=True)
    errors: list[str] = []
    auto = saving.AutoSave(recorder, char, on_error=errors.append)

    char.name = "Edited"
    assert auto.poll(char) is False
    assert len(errors) == 1

    recorder.fail = False
    assert auto.poll(char) is True, "The failed change was not retried."
    assert recorder.saved[0].name == "Edited"


def test_a_write_error_is_reported_once_per_failure_run() -> None:
    """A broken destination must not report on every tick of the timer."""
    char = _char()
    recorder = _Recorder(fail=True)
    errors: list[str] = []
    auto = saving.AutoSave(recorder, char, on_error=errors.append)

    char.name = "One"
    auto.poll(char)
    char.name = "Two"
    auto.poll(char)

    assert len(errors) == 1


def test_a_recovery_reports_again() -> None:
    """The negative control for the test above. The report is suppressed for a
    RUN of failures, not permanently."""
    char = _char()
    recorder = _Recorder(fail=True)
    errors: list[str] = []
    auto = saving.AutoSave(recorder, char, on_error=errors.append)

    char.name = "One"
    auto.poll(char)
    recorder.fail = False
    auto.poll(char)
    recorder.fail = True
    char.name = "Two"
    auto.poll(char)

    assert len(errors) == 2


def test_a_write_error_does_not_escape_the_poll() -> None:
    """The timer calls this. An exception in a NiceGUI timer callback is logged
    and not raised, thus it would be an invisible auto-save."""
    char = _char()
    auto = saving.AutoSave(_Recorder(fail=True), char)
    char.name = "Edited"

    assert auto.poll(char) is False


# --------------------------------------------------------------------------- #
# The destination
# --------------------------------------------------------------------------- #

def test_it_writes_the_file_at_the_current_path(tmp_path: Path) -> None:
    """End to end over a real file, with the real save function."""
    char = _char()
    target = tmp_path / "hero.character.json"
    auto = saving.AutoSave(lambda c: persistence.save_character(c, target), char)

    char.name = "Written By Auto Save"
    auto.poll(char)

    assert persistence.load_character(target).name == "Written By Auto Save"


def test_it_creates_a_missing_session_directory(tmp_path: Path) -> None:
    """A session directory does not exist until its first write."""
    char = _char()
    target = tmp_path / "session-a" / "hero.character.json"
    auto = saving.AutoSave(lambda c: persistence.save_character(c, target), char)

    char.name = "First Write"

    assert auto.poll(char) is True
    assert target.exists()


@pytest.mark.parametrize("interval", [saving.AUTOSAVE_SECONDS])
def test_the_interval_is_a_positive_number(interval) -> None:
    """The exposure to an eviction is one interval. It must be a real debounce and
    not a write per mutation: the dot tracks fire their funnel per click."""
    assert interval >= 1.0
