"""The account management of `server/db.py`: email, password change, login epochs
and the tombstone delete. `docs/plans/account-management.md`."""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

pytest.importorskip("bcrypt")

from exalted_builder.server import db  # noqa: E402

PASSWORD = "correct horse"
NEW_PASSWORD = "battery staple"


@pytest.fixture
def store(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(db, "BCRYPT_ROUNDS", 4)
    monkeypatch.setattr(db, "_dummy_hash", None)
    path = tmp_path / "exalted.db"
    db.init_db(path)
    return path


# ---- email ----------------------------------------------------------------- #


def test_an_account_has_no_email_until_one_is_set(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    assert db.email_for(store, user_id) is None

    db.set_email(store, user_id, "  jade@example.com ")
    assert db.email_for(store, user_id) == "jade@example.com"


def test_an_empty_email_removes_it(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.set_email(store, user_id, "jade@example.com")

    db.set_email(store, user_id, "")
    assert db.email_for(store, user_id) is None


@pytest.mark.parametrize("bad", ["jade", "jade@", "@example.com", "ja de@example.com",
                                 "a@b@c.com", "x" * 250 + "@example.com"])
def test_a_malformed_email_is_refused(store: Path, bad: str) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    with pytest.raises(db.AccountError):
        db.set_email(store, user_id, bad)
    assert db.email_for(store, user_id) is None


def test_signup_can_record_an_email(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD, email="jade@example.com")
    assert db.email_for(store, user_id) == "jade@example.com"


def test_a_malformed_signup_email_makes_no_account(store: Path) -> None:
    with pytest.raises(db.AccountError):
        db.create_user(store, "Harmonious", PASSWORD, email="not an email")
    assert db.list_users(store) == []


def test_list_users_shows_the_email(store: Path) -> None:
    first = db.create_user(store, "Harmonious", PASSWORD, email="jade@example.com")
    second = db.create_user(store, "Peleps", PASSWORD)
    rows = db.list_users(store)
    assert [(r[0], r[1], r[3]) for r in rows] == [
        (first, "Harmonious", "jade@example.com"), (second, "Peleps", None)]


# ---- password change -------------------------------------------------------- #


def test_a_player_changes_the_password_with_the_current_one(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)

    db.change_password(store, user_id, PASSWORD, NEW_PASSWORD)

    assert db.authenticate(store, "Harmonious", NEW_PASSWORD) == user_id
    assert db.authenticate(store, "Harmonious", PASSWORD) is None


def test_a_wrong_current_password_changes_nothing(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    with pytest.raises(db.AccountError):
        db.change_password(store, user_id, "wrong horse", NEW_PASSWORD)
    assert db.authenticate(store, "Harmonious", PASSWORD) == user_id


def test_a_short_new_password_is_refused(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    with pytest.raises(db.AccountError):
        db.change_password(store, user_id, PASSWORD, "short")


def test_check_password_for_confirms_the_owner(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    assert db.password_matches(store, user_id, PASSWORD)
    assert not db.password_matches(store, user_id, "wrong horse")


# ---- login epochs ------------------------------------------------------------ #


def test_a_new_account_is_at_epoch_zero(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    assert db.login_epoch(store, user_id) == 0


def test_raising_the_epoch_moves_it_and_returns_it(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    assert db.raise_login_epoch(store, user_id) == 1
    assert db.raise_login_epoch(store, user_id) == 2
    assert db.login_epoch(store, user_id) == 2


def test_the_epochs_of_two_accounts_are_separate(store: Path) -> None:
    first = db.create_user(store, "Harmonious", PASSWORD)
    second = db.create_user(store, "Peleps", PASSWORD)
    db.raise_login_epoch(store, first)
    assert db.login_epoch(store, second) == 0


def test_a_password_change_raises_the_epoch(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.change_password(store, user_id, PASSWORD, NEW_PASSWORD)
    assert db.login_epoch(store, user_id) == 1


def test_an_operator_reset_raises_the_epoch(store: Path) -> None:
    """Closes the limit of section 5.1d: a reset did not end the logins."""
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.set_password(store, "Harmonious", NEW_PASSWORD)
    assert db.login_epoch(store, user_id) == 1


# ---- the tombstone delete ------------------------------------------------------ #


def test_a_deleted_account_cannot_log_in_and_frees_its_name(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD, email="jade@example.com")

    db.tombstone_user(store, user_id)

    assert db.authenticate(store, "Harmonious", PASSWORD) is None
    assert db.username_for(store, user_id) is None
    assert db.email_for(store, user_id) is None
    assert db.create_user(store, "Harmonious", PASSWORD) != user_id


def test_a_deleted_id_is_never_given_again(store: Path) -> None:
    """⚠ `users.id` has no AUTOINCREMENT. Without the tombstone row, the newest
    deleted id goes to the next signup, with its log lines and notes files."""
    db.create_user(store, "Harmonious", PASSWORD)
    newest = db.create_user(store, "Peleps", PASSWORD)

    db.tombstone_user(store, newest)
    later = db.create_user(store, "Mnemon", PASSWORD)

    assert later > newest


def test_a_deleted_account_is_not_listed(store: Path) -> None:
    kept = db.create_user(store, "Harmonious", PASSWORD)
    gone = db.create_user(store, "Peleps", PASSWORD)
    db.tombstone_user(store, gone)
    assert [row[0] for row in db.list_users(store)] == [kept]


def test_the_placeholder_name_cannot_log_in(store: Path) -> None:
    """⚠ A crafted socket message can type any text. The placeholder must not reach
    bcrypt with the blanked hash: bcrypt raises on it."""
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.tombstone_user(store, user_id)
    with sqlite3.connect(store) as connection:
        (placeholder,) = connection.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()

    assert db.authenticate(store, placeholder, "") is None
    assert db.authenticate(store, placeholder, PASSWORD) is None


def test_a_deleted_account_ends_its_logins(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.tombstone_user(store, user_id)
    assert db.login_epoch(store, user_id) >= 1


def test_the_new_tables_reach_an_existing_database(tmp_path: Path) -> None:
    """The live server has a database from before these tables. `init_db` must add
    them with no migration."""
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, "
            "password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')))")
    db.init_db(path)
    with sqlite3.connect(path) as connection:
        names = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"user_emails", "login_epochs"} <= names


# ---- rename ---------------------------------------------------------------------- #


def test_a_rename_moves_the_login_to_the_new_name(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)

    assert db.rename_user(store, user_id, PASSWORD, " Radiant ") == "Radiant"

    assert db.username_for(store, user_id) == "Radiant"
    assert db.authenticate(store, "Radiant", PASSWORD) == user_id
    assert db.authenticate(store, "Harmonious", PASSWORD) is None


def test_a_rename_frees_the_old_name(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.rename_user(store, user_id, PASSWORD, "Radiant")
    assert db.create_user(store, "Harmonious", PASSWORD) != user_id


def test_a_taken_name_is_refused(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    db.create_user(store, "Radiant", PASSWORD)
    with pytest.raises(db.AccountError, match="taken"):
        db.rename_user(store, user_id, PASSWORD, "Radiant")
    assert db.username_for(store, user_id) == "Harmonious"


def test_a_malformed_name_is_refused(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    with pytest.raises(db.AccountError):
        db.rename_user(store, user_id, PASSWORD, "deleted:1")
    assert db.username_for(store, user_id) == "Harmonious"


def test_a_rename_needs_the_password(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)
    with pytest.raises(db.AccountError, match="password"):
        db.rename_user(store, user_id, "wrong horse", "Radiant")
    assert db.username_for(store, user_id) == "Harmonious"


def test_a_change_of_case_is_a_rename(store: Path) -> None:
    """Usernames are case-sensitive (the human, 2026-09-11)."""
    user_id = db.create_user(store, "harmonious", PASSWORD)
    db.rename_user(store, user_id, PASSWORD, "Harmonious")
    assert db.username_for(store, user_id) == "Harmonious"
