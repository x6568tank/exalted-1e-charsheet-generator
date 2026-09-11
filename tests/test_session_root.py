"""The per-session save root — `hosting-state-model.md` section 3.7.

Each browser session needs its own save destination. `server/config.session_root`
supplies the parent folder, and it has NO default.

⚠ The property that matters most is NEGATIVE: an absent value raises. A fallback
path would give every session one directory, and no functional test would notice
— one browser works perfectly. `test_an_absent_root_raises` is the test that
fails if somebody adds a convenient default.

The destination rule itself is in `tests/test_session_context_factory.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder.server import config


@pytest.fixture(autouse=True)
def _clean_root(monkeypatch):
    """Each test starts with no environment variable."""
    monkeypatch.delenv(config.SESSION_ROOT_ENV, raising=False)


def test_the_environment_variable_is_used(monkeypatch) -> None:
    monkeypatch.setenv(config.SESSION_ROOT_ENV, "/srv/exalted/sessions")

    assert config.session_root() == Path("/srv/exalted/sessions")


def test_surrounding_space_is_removed(monkeypatch) -> None:
    """A value from a `.env` file or a shell export can carry a newline."""
    monkeypatch.setenv(config.SESSION_ROOT_ENV, "  /srv/sessions\n")

    assert config.session_root() == Path("/srv/sessions")


def test_a_user_path_is_expanded(monkeypatch) -> None:
    monkeypatch.setenv(config.SESSION_ROOT_ENV, "~/exalted-sessions")

    root = config.session_root()

    assert "~" not in str(root)
    assert root.is_absolute()


@pytest.mark.parametrize("value", ["", "   ", "\n"])
def test_an_absent_root_raises(monkeypatch, value) -> None:
    """The negative property of this module.

    ⚠ Do not replace this with a default path. One shared directory makes every
    session write one file on the auto-save timer, and nothing reports it.
    """
    monkeypatch.setenv(config.SESSION_ROOT_ENV, value)

    with pytest.raises(RuntimeError, match=config.SESSION_ROOT_ENV):
        config.session_root()


def test_an_unset_variable_raises() -> None:
    """The fixture removed the variable, thus this is the fresh-process case."""
    with pytest.raises(RuntimeError, match=config.SESSION_ROOT_ENV):
        config.session_root()
