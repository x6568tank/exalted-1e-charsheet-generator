"""The account store of the hosted server: `server/db.py`.

Section 5 piece 3 of `docs/plans/hosting-state-model.md`.

⚠ The hash is bcrypt at a low work factor here. `db.BCRYPT_ROUNDS` is patched
through the module object, not by a dotted string; see
`test_engine_seam.py::test_no_test_patches_by_dotted_string`.
"""

from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

pytest.importorskip("bcrypt")

from exalted_builder.server import db  # noqa: E402

PASSWORD = "correct horse"


@pytest.fixture
def store(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(db, "BCRYPT_ROUNDS", 4)
    monkeypatch.setattr(db, "_dummy_hash", None)
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    return path


def test_a_new_account_authenticates(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)

    assert db.authenticate(store, "Harmonious", PASSWORD) == user_id


def test_a_wrong_password_does_not_authenticate(store: Path) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    assert db.authenticate(store, "Harmonious", "wrong horse") is None


def test_an_unknown_name_does_not_authenticate(store: Path) -> None:
    assert db.authenticate(store, "Nobody", PASSWORD) is None


def test_the_password_is_not_stored(store: Path) -> None:
    """The column holds a bcrypt hash, never the text."""
    db.create_user(store, "Harmonious", PASSWORD)

    with sqlite3.connect(store) as connection:
        (stored,) = connection.execute("SELECT password_hash FROM users").fetchone()

    assert PASSWORD not in stored
    assert stored.startswith("$2"), f"{stored!r} is not a bcrypt hash."


def test_usernames_are_case_sensitive(store: Path) -> None:
    """The human's ruling, 2026-09-11. "Gil" and "gil" are two accounts, and a
    login must give the case of the signup."""
    upper = db.create_user(store, "Harmonious", PASSWORD)
    lower = db.create_user(store, "harmonious", "another password")

    assert upper != lower
    assert db.authenticate(store, "Harmonious", PASSWORD) == upper
    assert db.authenticate(store, "HARMONIOUS", PASSWORD) is None


def test_a_name_that_exists_is_refused(store: Path) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    with pytest.raises(db.AccountError, match="taken"):
        db.create_user(store, "Harmonious", "another password")


def test_whitespace_around_the_name_is_removed(store: Path) -> None:
    user_id = db.create_user(store, "  Harmonious ", PASSWORD)

    assert db.username_for(store, user_id) == "Harmonious"
    assert db.authenticate(store, "Harmonious", PASSWORD) == user_id


def test_whitespace_in_the_password_is_kept(store: Path) -> None:
    """The name is trimmed; the password is not. A trimmed password is a
    different password from the one the player typed."""
    db.create_user(store, "Harmonious", " " + PASSWORD)

    assert db.authenticate(store, "Harmonious", PASSWORD) is None


@pytest.mark.parametrize("username", ["ab", "a" * 33, "has space", "../up", "semi;colon"])
def test_a_bad_username_is_refused(store: Path, username: str) -> None:
    with pytest.raises(db.AccountError, match="username"):
        db.create_user(store, username, PASSWORD)


def test_a_short_password_is_refused(store: Path) -> None:
    with pytest.raises(db.AccountError, match="at least"):
        db.create_user(store, "Harmonious", "short")


def test_a_password_past_the_bcrypt_limit_is_refused(store: Path) -> None:
    """⚠ bcrypt reads 72 bytes. A longer password would share its hash with every
    password of the same prefix, thus the store refuses it."""
    with pytest.raises(db.AccountError, match="at most"):
        db.create_user(store, "Harmonious", "x" * 73)


def test_a_multibyte_password_is_measured_in_bytes(store: Path) -> None:
    """25 characters of three bytes each is 75 bytes. A character count lets it
    through."""
    with pytest.raises(db.AccountError, match="at most"):
        db.create_user(store, "Harmonious", "日" * 25)


def test_a_long_password_at_login_is_rejected_not_raised(store: Path) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    assert db.authenticate(store, "Harmonious", PASSWORD + "x" * 80) is None


def test_the_database_is_in_wal_mode(store: Path) -> None:
    """Section 5.4. Without WAL, one writer blocks each reader."""
    with sqlite3.connect(store) as connection:
        (mode,) = connection.execute("PRAGMA journal_mode").fetchone()

    assert mode == "wal"


def test_init_is_repeatable(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)

    db.init_db(store)

    assert db.authenticate(store, "Harmonious", PASSWORD) == user_id


def test_a_password_needs_no_character_types(store: Path) -> None:
    """The human's ruling, 2026-09-11: eight characters, no complexity rule."""
    assert db.create_user(store, "Harmonious", "aaaaaaaa")


# --------------------------------------------------------------------------- #
# The operator: reset and list
# --------------------------------------------------------------------------- #


def test_a_reset_replaces_the_password(store: Path) -> None:
    user_id = db.create_user(store, "Harmonious", PASSWORD)

    db.set_password(store, "Harmonious", "a new password")

    assert db.authenticate(store, "Harmonious", PASSWORD) is None
    assert db.authenticate(store, "Harmonious", "a new password") == user_id


def test_a_reset_of_an_unknown_name_is_refused(store: Path) -> None:
    with pytest.raises(db.AccountError, match="no account"):
        db.set_password(store, "Nobody", "a new password")


def test_a_reset_touches_one_account(store: Path) -> None:
    """⚠ The UPDATE has a WHERE. A reset that drops it gives every account the
    new password, and a check of the reset account alone passes."""
    db.create_user(store, "Harmonious", PASSWORD)
    other = db.create_user(store, "Radiant", PASSWORD)

    db.set_password(store, "Harmonious", "a new password")

    assert db.authenticate(store, "Radiant", PASSWORD) == other


def test_a_reset_keeps_the_password_limits(store: Path) -> None:
    db.create_user(store, "Harmonious", PASSWORD)

    with pytest.raises(db.AccountError, match="at least"):
        db.set_password(store, "Harmonious", "short")


def test_the_accounts_are_listed_by_id(store: Path) -> None:
    first = db.create_user(store, "Radiant", PASSWORD)
    second = db.create_user(store, "Harmonious", PASSWORD)

    listed = [(user_id, name) for user_id, name, _ in db.list_users(store)]

    assert listed == [(first, "Radiant"), (second, "Harmonious")]
