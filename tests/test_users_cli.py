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


# ---- the email (docs/plans/account-management.md, 2026-09-26) ---------------- #


def test_list_prints_the_email(store: Path, capsys) -> None:
    db.create_user(store, "Harmonious", PASSWORD, email="jade@example.com")
    db.create_user(store, "Radiant", PASSWORD)

    users.main(["list"])

    lines = capsys.readouterr().out.splitlines()
    assert any("Harmonious" in line and "jade@example.com" in line for line in lines)
    assert any("Radiant" in line and "(no email)" in line for line in lines)


def test_reset_names_the_address_before_it_asks(store: Path, capsys) -> None:
    """⚠ The operator sends the new password TO THIS ADDRESS, not to the sender of
    the request. The address shows before the prompt, thus the operator can stop."""
    db.create_user(store, "Harmonious", PASSWORD, email="jade@example.com")
    seen = []

    def ask(prompt: str) -> str:
        seen.append(capsys.readouterr().out)
        return "new password"

    users.main(["reset", "Harmonious"], ask=ask)

    assert "jade@example.com" in seen[0]


def test_reset_warns_when_there_is_no_email(store: Path, capsys) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    users.main(["reset", "Harmonious"], ask=_answers("new password", "new password"))

    assert "no email" in capsys.readouterr().out


def test_reset_ends_the_logins(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    users.main(["reset", "Harmonious"], ask=_answers("new password", "new password"))
    assert db.login_epoch(store, user_id) == 1


# ---- delete ------------------------------------------------------------------ #


@pytest.fixture
def root(tmp_path: Path, monkeypatch) -> Path:
    folder = tmp_path / "sessions"
    monkeypatch.setenv(config.SESSION_ROOT_ENV, str(folder))
    return folder


def test_delete_asks_for_the_name_again_and_deletes(store: Path, root: Path, capsys) -> None:
    from exalted_builder.server.characters import CharacterStore
    from exalted_builder.models.character import Character

    user_id = db.create_user(store, "Harmonious", PASSWORD)
    characters = CharacterStore(db_path=store, root=root)
    characters.create(user_id, Character(id="x", name="Ashes"))

    status = users.main(["delete", "Harmonious"], confirm=_answers("Harmonious"))

    assert status == 0
    assert db.user_id_for(store, "Harmonious") is None
    assert characters.list_for(user_id) == []
    assert not characters.account_dir(user_id).exists()


def test_delete_with_a_wrong_answer_changes_nothing(store: Path, root: Path, capsys) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    status = users.main(["delete", "Harmonious"], confirm=_answers("harmonious"))

    assert status == 1
    assert db.user_id_for(store, "Harmonious") is not None
    assert "Nothing changed" in capsys.readouterr().err


def test_delete_names_the_campaigns_it_deletes(store: Path, root: Path, capsys) -> None:
    from exalted_builder.server.tables import TableStore

    user_id = db.create_user(store, "Harmonious", PASSWORD)
    TableStore(db_path=store, root=root).create(user_id, "The Scarlet Gambit")
    seen = []

    def ask(prompt: str) -> str:
        seen.append(capsys.readouterr().out)
        return "no"

    users.main(["delete", "Harmonious"], confirm=ask)

    assert "The Scarlet Gambit" in seen[0]


def test_delete_of_an_unknown_name_is_reported(store: Path, root: Path, capsys) -> None:
    assert users.main(["delete", "Nobody"], confirm=_answers("Nobody")) == 1
