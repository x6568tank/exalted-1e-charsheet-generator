"""The operator command: `python -m exalted_builder.server.users`.

The human's ruling of 2026-09-11: a player with a forgotten password writes to the
admin address, and the operator resets it. There is no reset by email.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("bcrypt")

from exalted_builder.server import config, db, users  # noqa: E402

PASSWORD = "correct horse"


@pytest.fixture
def store(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(db, "BCRYPT_ROUNDS", 4)
    monkeypatch.setattr(db, "_dummy_hash", None)
    path = tmp_path / "exalted.db"
    db.init_db(path)
    monkeypatch.setenv(config.DB_PATH_ENV, str(path))
    return path


def _answers(*values: str):
    queue = list(values)
    return lambda prompt: queue.pop(0)


def test_reset_sets_the_new_password(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)

    status = users.main(["reset", "Harmonious"], ask=_answers("new password", "new password"))

    assert status == 0
    assert db.authenticate(store, "Harmonious", "new password") == user_id


def test_two_different_answers_change_nothing(store: Path, capsys) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    status = users.main(["reset", "Harmonious"], ask=_answers("new password", "typo"))

    assert status == 1
    assert "different" in capsys.readouterr().err
    assert db.authenticate(store, "Harmonious", PASSWORD) is not None


def test_an_unknown_name_is_reported(store: Path, capsys) -> None:
    status = users.main(["reset", "Nobody"], ask=_answers("new password", "new password"))

    assert status == 1
    assert "no account" in capsys.readouterr().err


def test_a_short_password_is_reported(store: Path, capsys) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    status = users.main(["reset", "Harmonious"], ask=_answers("short", "short"))

    assert status == 1
    assert "at least" in capsys.readouterr().err


def test_list_prints_each_account(store: Path, capsys) -> None:
    db.create_user(store, "Harmonious", PASSWORD)
    db.create_user(store, "Radiant", PASSWORD)

    assert users.main(["list"]) == 0

    out = capsys.readouterr().out
    assert "Harmonious" in out and "Radiant" in out
    assert PASSWORD not in out and "$2" not in out, "The listing shows a secret."


def test_a_missing_database_is_reported_not_made(tmp_path: Path, monkeypatch, capsys) -> None:
    """A mistyped path must not make an empty second store."""
    path = tmp_path / "nowhere.db"
    monkeypatch.setenv(config.DB_PATH_ENV, str(path))

    assert users.main(["list"]) == 1
    assert not path.exists()
