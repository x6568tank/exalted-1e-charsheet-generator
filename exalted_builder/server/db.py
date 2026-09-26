"""
server/db.py — the SQLite store of the hosted server. It holds the user accounts.

Section 5 piece 3 of `docs/plans/hosting-state-model.md`. Piece 4 adds the
`characters` table to this file and to this database.

⚠ Store a bcrypt hash only. Never store, log or return a password.

⚠ bcrypt reads 72 bytes of a password and no more. Version 5 of the library raises
on a longer password. `create_user` refuses one, and `authenticate` rejects one.
Thus two passwords with one 72-byte prefix can never both exist.

⚠ bcrypt is imported at the call, not at module scope. Thus the desktop builds and
the tests that do not use accounts run without the `[server]` extra.
"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
import re
import sqlite3

# The work factor of each new hash. 12 is the default of the library. A test
# lowers it through the module object, because a full hash costs a quarter second.
BCRYPT_ROUNDS = 12

# The limits of a username. The characters are safe in a path and in a URL.
USERNAME_PATTERN = re.compile(r"[A-Za-z0-9_.-]{3,32}")
USERNAME_RULE = "3 to 32 characters: letters, digits, '.', '_' or '-'."

# The limits of an email. The check refuses a typing error, not each bad address:
# the operator sends mail to it by hand. See docs/plans/account-management.md.
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
MAX_EMAIL_LENGTH = 254

# The username of a deleted account: `DELETED_PREFIX` + the id. ⚠ It can never match
# `USERNAME_PATTERN`, thus the real name is free and the row can never log in.
DELETED_PREFIX = "deleted:"

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

# Usernames are case-sensitive: "Gil" and "gil" are two accounts, and a login must
# give the case of the signup. The human ruled this on 2026-09-11.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- The characters of each account. Section 5 piece 4; docs/plans/vtt.md 9.3a.
-- The character is a file. This row holds what the file cannot: the owner, the
-- copy flag, the base of a copy, and the table of a copy (P3, NULL until then).
-- A delete of a base keeps its copies and clears their base_id (ruled 2026-09-12).
CREATE TABLE IF NOT EXISTS characters (
    id TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_copy INTEGER NOT NULL DEFAULT 0,
    base_id TEXT REFERENCES characters(id) ON DELETE SET NULL,
    table_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS characters_owner ON characters(owner_id);

-- The campaigns (P3). docs/plans/p3-tables.md section 2.1; server/tables.py.
-- ⚠ characters.table_id has no foreign key: SQLite cannot add one to an existing
-- column. TableStore clears the column itself.
CREATE TABLE IF NOT EXISTS tables (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    storyteller_id INTEGER NOT NULL REFERENCES users(id),
    join_code TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- An approved member. The Storyteller is not a row here: tables.storyteller_id
-- holds that role.
CREATE TABLE IF NOT EXISTS memberships (
    table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (table_id, user_id)
);

-- A request that waits for the Storyteller. base_id NULL is a request to watch.
CREATE TABLE IF NOT EXISTS join_requests (
    id INTEGER PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    base_id TEXT REFERENCES characters(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS characters_table ON characters(table_id);

-- A draft that its owner makes for a campaign (p3-tables.md section 14, step 6b).
-- The draft is an ordinary character with no table_id. Its lock sends a join
-- request, and deletes this row. The page cannot edit this row.
-- The email of an account, if the player gives one. docs/plans/account-management.md.
-- ⚠ New tables, not new columns: `CREATE TABLE IF NOT EXISTS` reaches the live
-- database at the next start, and a new column needs a migration.
CREATE TABLE IF NOT EXISTS user_emails (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    email TEXT NOT NULL
);
-- The login epoch of an account. A login records it; a raise ends each older login.
-- No row is epoch 0.
CREATE TABLE IF NOT EXISTS login_epochs (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    epoch INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign_drafts (
    character_id TEXT PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
    table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE
);
"""


class AccountError(ValueError):
    """A signup that the store refuses. The message is safe to show to the user."""


def _bcrypt():
    """Return the bcrypt module. Raise `RuntimeError` if the `[server]` extra is absent."""
    try:
        import bcrypt
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "The hosted server needs bcrypt. Install the [server] extra.") from exc
    return bcrypt


def connect(path: Path) -> sqlite3.Connection:
    """Open the database at `path` and return the connection.

    Set a busy timeout on each connection. The WAL mode is a property of the file,
    and `init_db` sets it.
    """
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(path: Path) -> None:
    """Make the database at `path` if it is absent, and make each table that is absent.

    Set the WAL mode. Section 5.4: without it, one writer blocks every reader.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as connection, connection:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.executescript(SCHEMA)


def normalise_username(username: str) -> str:
    """Return `username` with the surrounding whitespace removed."""
    return username.strip()


def check_new_account(username: str, password: str) -> None:
    """Raise `AccountError` if `username` or `password` cannot make an account."""
    if not USERNAME_PATTERN.fullmatch(username):
        raise AccountError(f"A username has {USERNAME_RULE}")
    check_password(password)


def check_password(password: str) -> None:
    """Raise `AccountError` if `password` is too short or too long.

    There is no rule on the character types. The human ruled this on 2026-09-11.
    """
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(
            f"A password has at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise AccountError(
            f"A password has at most {MAX_PASSWORD_BYTES} bytes.")


def check_email(email: str) -> str:
    """Return `email` without its surrounding whitespace. Return "" for no email.

    Raise `AccountError` if the email is malformed.
    """
    email = email.strip()
    if email and (len(email) > MAX_EMAIL_LENGTH or not EMAIL_PATTERN.fullmatch(email)):
        raise AccountError("That email address is not valid.")
    return email


def _hash(password: str) -> str:
    """Return the bcrypt hash of `password`, at `BCRYPT_ROUNDS`."""
    bcrypt = _bcrypt()
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def create_user(path: Path, username: str, password: str, *, email: str = "") -> int:
    """Make an account and return its id. Record `email` if it is not empty.

    Remove the surrounding whitespace of `username`, not of `password`. Raise
    `AccountError` if the pair fails `check_new_account`, if `email` fails
    `check_email`, or if the name exists.
    """
    username = normalise_username(username)
    check_new_account(username, password)
    email = check_email(email)
    digest = _hash(password)
    try:
        with closing(connect(path)) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, digest))
            user_id = int(cursor.lastrowid)
            if email:
                connection.execute(
                    "INSERT INTO user_emails (user_id, email) VALUES (?, ?)",
                    (user_id, email))
            return user_id
    except sqlite3.IntegrityError as exc:
        raise AccountError("That username is taken.") from exc


# A hash to compare against when the username is unknown. Made at the first call.
# Thus an unknown name costs the same time as a wrong password.
_dummy_hash: bytes | None = None


def _hash_for_timing() -> bytes:
    global _dummy_hash  # noqa: PLW0603
    if _dummy_hash is None:
        bcrypt = _bcrypt()
        _dummy_hash = bcrypt.hashpw(b"not a password",
                                    bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return _dummy_hash


def authenticate(path: Path, username: str, password: str) -> int | None:
    """Return the id of the account if `password` is its password. Return None in
    all other cases.

    ⚠ Do a bcrypt comparison also for an unknown name. A fast refusal tells a
    caller which names exist.
    """
    username = normalise_username(username)
    encoded = password.encode("utf-8")
    bcrypt = _bcrypt()
    row = None
    # ⚠ A name outside the pattern is unknown. The placeholder of a deleted account
    # is outside it, and its blanked hash makes bcrypt raise.
    if USERNAME_PATTERN.fullmatch(username):
        with closing(connect(path)) as connection:
            row = connection.execute(
                "SELECT id, password_hash FROM users WHERE username = ?",
                (username,)).fetchone()
    if row is None or len(encoded) > MAX_PASSWORD_BYTES:
        bcrypt.checkpw(b"not a password", _hash_for_timing())
        return None
    user_id, digest = row
    if bcrypt.checkpw(encoded, digest.encode("ascii")):
        return int(user_id)
    return None


def username_for(path: Path, user_id: int) -> str | None:
    """Return the username of account `user_id`, or None if it does not exist."""
    with closing(connect(path)) as connection:
        row = connection.execute(
            "SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or str(row[0]).startswith(DELETED_PREFIX):
        return None
    return str(row[0])


def set_password(path: Path, username: str, password: str) -> None:
    """Replace the password of account `username`.

    Raise `AccountError` if the account does not exist, or if `password` fails
    `check_password`. The operator command `server/users.py` calls this.
    """
    username = normalise_username(username)
    check_password(password)
    digest = _hash(password)
    with closing(connect(path)) as connection, connection:
        found = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if found is None or not USERNAME_PATTERN.fullmatch(username):
            raise AccountError(f"There is no account named {username!r}.")
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (digest, found[0]))
        _raise_epoch(connection, int(found[0]))


def list_users(path: Path) -> list[tuple[int, str, str, str | None]]:
    """Return the id, the username, the creation time and the email of each account,
    by id. Do not include a deleted account."""
    with closing(connect(path)) as connection:
        rows = connection.execute(
            "SELECT users.id, username, created_at, email FROM users "
            "LEFT JOIN user_emails ON user_emails.user_id = users.id "
            "WHERE substr(username, 1, ?) != ? ORDER BY users.id",
            (len(DELETED_PREFIX), DELETED_PREFIX)).fetchall()
    return [(int(user_id), str(name), str(created), email)
            for user_id, name, created, email in rows]


def user_id_for(path: Path, username: str) -> int | None:
    """Return the id of the account `username`, or None if it does not exist."""
    username = normalise_username(username)
    if not USERNAME_PATTERN.fullmatch(username):
        return None
    with closing(connect(path)) as connection:
        row = connection.execute(
            "SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    return None if row is None else int(row[0])


def email_for(path: Path, user_id: int) -> str | None:
    """Return the email of account `user_id`, or None if it has none."""
    with closing(connect(path)) as connection:
        row = connection.execute(
            "SELECT email FROM user_emails WHERE user_id = ?", (user_id,)).fetchone()
    return None if row is None else str(row[0])


def set_email(path: Path, user_id: int, email: str) -> None:
    """Record `email` for account `user_id`. An empty `email` removes it.

    Raise `AccountError` if `email` fails `check_email`.
    """
    email = check_email(email)
    with closing(connect(path)) as connection, connection:
        if email:
            connection.execute(
                "INSERT INTO user_emails (user_id, email) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET email = excluded.email",
                (user_id, email))
        else:
            connection.execute("DELETE FROM user_emails WHERE user_id = ?", (user_id,))


def password_matches(path: Path, user_id: int, password: str) -> bool:
    """Return True if `password` is the password of account `user_id`."""
    username = username_for(path, user_id)
    return username is not None and authenticate(path, username, password) == user_id


def change_password(path: Path, user_id: int, current: str, new: str) -> None:
    """Replace the password of account `user_id`, and raise its login epoch.

    Raise `AccountError` if `current` is not its password, or if `new` fails
    `check_password`.
    """
    check_password(new)
    if not password_matches(path, user_id, current):
        raise AccountError("The current password is wrong.")
    digest = _hash(new)
    with closing(connect(path)) as connection, connection:
        connection.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?", (digest, user_id))
        _raise_epoch(connection, user_id)


def login_epoch(path: Path, user_id: int) -> int:
    """Return the login epoch of account `user_id`. No row is epoch 0."""
    with closing(connect(path)) as connection:
        row = connection.execute(
            "SELECT epoch FROM login_epochs WHERE user_id = ?", (user_id,)).fetchone()
    return 0 if row is None else int(row[0])


def raise_login_epoch(path: Path, user_id: int) -> int:
    """Raise the login epoch of account `user_id` by 1. Return the new epoch.

    Each login that recorded an older epoch ends. See `auth.current_user_id`.
    """
    with closing(connect(path)) as connection, connection:
        return _raise_epoch(connection, user_id)


def _raise_epoch(connection: sqlite3.Connection, user_id: int) -> int:
    connection.execute(
        "INSERT INTO login_epochs (user_id, epoch) VALUES (?, 1) "
        "ON CONFLICT(user_id) DO UPDATE SET epoch = epoch + 1", (user_id,))
    (epoch,) = connection.execute(
        "SELECT epoch FROM login_epochs WHERE user_id = ?", (user_id,)).fetchone()
    return int(epoch)


def tombstone_user(path: Path, user_id: int) -> None:
    """Make account `user_id` a deleted account. Keep its row.

    Replace the username with the placeholder, blank the hash, remove the email and
    raise the login epoch. ⚠ Keep the row: `users.id` has no AUTOINCREMENT, thus a
    removed newest row gives its id to the next signup. The caller removes the
    characters, the campaigns and the folder first. See `server/accounts.py`.
    """
    with closing(connect(path)) as connection, connection:
        connection.execute(
            "UPDATE users SET username = ?, password_hash = '' WHERE id = ?",
            (f"{DELETED_PREFIX}{user_id}", user_id))
        connection.execute("DELETE FROM user_emails WHERE user_id = ?", (user_id,))
        _raise_epoch(connection, user_id)
