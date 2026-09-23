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
        raise AccountError(
            "A username has 3 to 32 characters: letters, digits, '.', '_' or '-'.")
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


def _hash(password: str) -> str:
    """Return the bcrypt hash of `password`, at `BCRYPT_ROUNDS`."""
    bcrypt = _bcrypt()
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=BCRYPT_ROUNDS)).decode("ascii")


def create_user(path: Path, username: str, password: str) -> int:
    """Make an account and return its id.

    Remove the surrounding whitespace of `username`, not of `password`. Raise
    `AccountError` if the pair fails `check_new_account`, or if the name exists.
    """
    username = normalise_username(username)
    check_new_account(username, password)
    digest = _hash(password)
    try:
        with closing(connect(path)) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, digest))
            return int(cursor.lastrowid)
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
    return None if row is None else str(row[0])


def set_password(path: Path, username: str, password: str) -> None:
    """Replace the password of account `username`.

    Raise `AccountError` if the account does not exist, or if `password` fails
    `check_password`. The operator command `server/users.py` calls this.
    """
    username = normalise_username(username)
    check_password(password)
    digest = _hash(password)
    with closing(connect(path)) as connection, connection:
        cursor = connection.execute(
            "UPDATE users SET password_hash = ? WHERE username = ?", (digest, username))
    if cursor.rowcount != 1:
        raise AccountError(f"There is no account named {username!r}.")


def list_users(path: Path) -> list[tuple[int, str, str]]:
    """Return the id, the username and the creation time of each account, by id."""
    with closing(connect(path)) as connection:
        rows = connection.execute(
            "SELECT id, username, created_at FROM users ORDER BY id").fetchall()
    return [(int(user_id), str(name), str(created)) for user_id, name, created in rows]
