"""The hosted entry point: `server/main.py`.

`build_server` must give the character pages of `server/home.py` its session
root, its database and a BOOK ruleset, and `main` must install the gate, the
quota and the homebrew switch before the server runs. The pages themselves are
`tests/test_character_pages.py`.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from exalted_builder import custom_content, persistence
from exalted_builder.models.character import Character
from exalted_builder.server import auth, characters, config, db, main


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A session root of this test alone."""
    return tmp_path / "sessions"


@pytest.fixture
def database(tmp_path: Path) -> Path:
    """An account database of this test alone."""
    return tmp_path / "accounts" / "exalted.db"


# --------------------------------------------------------------------------- #
# The wiring: the entry point passes a root
# --------------------------------------------------------------------------- #


def _character_ctx(registry, database: Path, root: Path, user_id: int) -> dict:
    """Make account `user_id` and one character of it. Return the character's context.

    The account row goes in by SQL: this file does not need bcrypt."""
    with db.connect(database) as connection:
        connection.execute(
            "INSERT OR IGNORE INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            (user_id, f"user{user_id}"))
    row = characters.CharacterStore(db_path=database, root=root).create(
        user_id, Character(id="x", name=f"Hero {user_id}"))
    return registry.ctx_for(row.id)


def test_two_accounts_of_the_server_get_two_folders(root: Path, database: Path) -> None:
    """The dormancy check. `build_server` must hand the pages its root, and each
    account must get its own folder below it."""
    registry = main.build_server(session_root=root, db_path=database)

    alpha = _character_ctx(registry, database, root, 1)
    beta = _character_ctx(registry, database, root, 2)

    assert alpha["home_dir"] != beta["home_dir"], (
        f"Both accounts save under {alpha['home_dir']}. Every account then writes "
        "one folder, under one quota.")
    assert alpha["path"].parent != beta["path"].parent


def test_the_server_saves_inside_the_session_root(root: Path, database: Path) -> None:
    registry = main.build_server(session_root=root, db_path=database)

    ctx = _character_ctx(registry, database, root, 1)

    assert ctx["path"].is_relative_to(ctx["home_dir"])
    assert ctx["home_dir"] == root / "user-1", (
        f"The account folder is {ctx['home_dir']}, not {root / 'user-1'}. The quota "
        "counts the first folder below the root.")


def test_the_hosted_builder_does_not_load_the_default_library(
        root: Path, database: Path, tmp_path: Path, monkeypatch) -> None:
    """Section 5.3: each account has its own library, and there is no library of
    the process. A Charm in the default library must reach no character.

    ⚠ The switch is the discriminator. A build_server that calls
    `load_app_ruleset` reads the default library, and the switch makes that raise.
    The ruleset assertion alone does not find it: each account reloads its own
    library, and the reload removes each custom row first, thus an account hides
    the default library by accident. That is the second type of the house bug."""
    default = tmp_path / "default-library"
    (default / "charms").mkdir(parents=True)
    (default / "charms" / "x.json").write_text(
        '[{"id": "custom.process-wide", "name": "Process Wide", "category": "melee",'
        ' "type": "Supplemental"}]')
    monkeypatch.setenv(custom_content.CUSTOM_DIR_ENV, str(default))

    custom_content.require_explicit_dir(True)
    try:
        registry = main.build_server(session_root=root, db_path=database)
        ruleset = _character_ctx(registry, database, root, 1)["ruleset"]
    finally:
        custom_content.require_explicit_dir(False)

    assert "custom.process-wide" not in ruleset.charms
    assert "melee" in {c.category for c in ruleset.charms.values()}   # the book is there


def test_the_server_reads_the_root_from_the_environment(root: Path, database: Path,
                                                        monkeypatch) -> None:
    """The whole chain. `build_server` with no argument must call
    `config.session_root`, which reads `EXALTED_SESSION_ROOT`."""
    monkeypatch.setenv(config.SESSION_ROOT_ENV, str(root))
    monkeypatch.setenv(config.DB_PATH_ENV, str(database))

    registry = main.build_server()

    assert _character_ctx(registry, database, root, 1)["path"].is_relative_to(root)


def test_the_server_refuses_to_start_without_a_root(monkeypatch) -> None:
    """No default, for section 3.7's reason: one shared directory is the defect."""
    monkeypatch.delenv(config.SESSION_ROOT_ENV, raising=False)

    with pytest.raises(RuntimeError, match=config.SESSION_ROOT_ENV):
        main.build_server()


def test_the_server_refuses_to_start_without_a_database(root: Path, monkeypatch) -> None:
    """No default. A default path in the working directory makes a second account
    store when the server starts from a second directory."""
    monkeypatch.delenv(config.DB_PATH_ENV, raising=False)

    with pytest.raises(RuntimeError, match=config.DB_PATH_ENV):
        main.build_server(session_root=root)


def test_the_server_makes_the_account_database(root: Path, database: Path) -> None:
    main.build_server(session_root=root, db_path=database)

    assert database.exists()


# --------------------------------------------------------------------------- #
# The secret: the hosted path may not take the desktop's random fallback
# --------------------------------------------------------------------------- #


def test_the_hosted_secret_raises_when_the_environment_gives_none(monkeypatch) -> None:
    """⚠ `config.storage_secret` returns a RANDOM key when the environment gives
    none. That is correct for the desktop and wrong for a server: the key changes
    at each restart, thus every session cookie becomes invalid, thus every browser
    gets a new session directory and its auto-saved character is orphaned. Nothing
    reports that — the server starts and looks healthy.
    """
    monkeypatch.delenv(config.STORAGE_SECRET_ENV, raising=False)
    config.reset_ephemeral_secret()

    assert config.storage_secret(), "The desktop fallback must stay."

    with pytest.raises(RuntimeError, match=config.STORAGE_SECRET_ENV):
        config.required_storage_secret()


def test_the_hosted_secret_returns_the_configured_value(monkeypatch) -> None:
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "  a-real-secret  ")

    assert config.required_storage_secret() == "a-real-secret"


def test_the_hosted_secret_rejects_the_desktop_fallback(monkeypatch) -> None:
    """An empty value is not a value. It must raise, not fall through to random."""
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "   ")

    with pytest.raises(RuntimeError, match=config.STORAGE_SECRET_ENV):
        config.required_storage_secret()


# --------------------------------------------------------------------------- #
# The gate: `main` installs it
# --------------------------------------------------------------------------- #


def test_main_installs_the_gate_and_the_quota_before_the_server_runs(root: Path, database: Path,
                                                       monkeypatch) -> None:
    """⚠ `build_server` does not install the gate, thus `main` must. A `main` that
    omits the call serves each route to any visitor, and each case of
    `test_auth_gate.py` still passes, because its main file installs the gate.

    The order matters too. `ui.run` adds the session middleware outside the gate
    only if the gate is there first. See `auth.AuthGate`.

    The quota is the same shape: a correct check that `main` does not install is
    no limit. `test_folder_quota.py` tests the check.
    """
    calls: list[str] = []
    guards: list = []
    monkeypatch.setattr(auth, "install_gate", lambda: calls.append("gate"))
    monkeypatch.setattr(persistence, "set_write_guard",
                        lambda guard: (calls.append("quota"), guards.append(guard)))
    monkeypatch.setattr(custom_content, "require_explicit_dir",
                        lambda on: calls.append(f"library={on}"))
    run_kwargs: dict = {}
    monkeypatch.setattr(main.ui, "run", lambda *args, **kwargs: (
        calls.append("run"), run_kwargs.update(kwargs)))
    monkeypatch.setattr(sys, "argv", ["exalted-server"])
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "a-real-secret")
    monkeypatch.setenv(config.SESSION_ROOT_ENV, str(root))
    monkeypatch.setenv(config.DB_PATH_ENV, str(database))

    main.main()

    assert calls == ["gate", "quota", "library=True", "run"], (
        f"main made the calls {calls}. It must install the gate and the quota, "
        "switch off the default homebrew library, then run.")
    assert guards[0].root == root, "The quota guards a folder that is not the root."
    assert guards[0].limit == 10 * 1024 * 1024
    assert guards[0].db_path == database, (
        "The quota has no account database. An open page of a deleted account "
        "then writes its files again.")
    assert run_kwargs.get("session_middleware_kwargs") is main.SESSION_COOKIE, (
        "main does not pass the session cookie settings to ui.run. The cookie is "
        "then not Secure and a sibling subdomain can set it.")


def test_the_session_cookie_is_secure_and_host_only() -> None:
    """The human's ruling, 2026-09-11: the cookie is HTTPS-only.

    ⚠ The `__Host-` prefix is what stops a sibling subdomain (the operator runs
    several) from planting a session id. The browser enforces it only with Secure,
    path "/" and no domain; with a domain, the browser drops the cookie.
    """
    cookie = main.SESSION_COOKIE

    assert cookie["session_cookie"].startswith("__Host-")
    assert cookie["https_only"] is True
    assert cookie["path"] == "/"
    assert "domain" not in cookie


def test_the_default_host_is_loopback() -> None:
    """The safe default stays. An operator that serves a network passes `--host`."""
    assert main.DEFAULT_HOST == "127.0.0.1"
