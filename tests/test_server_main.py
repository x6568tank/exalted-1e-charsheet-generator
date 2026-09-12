"""The hosted entry point supplies the session root.

Section 3 of `docs/plans/hosting-state-model.md` built per-session destinations and
write-through auto-save. Nothing reached them: all three production callers of
`register_pages` are desktop and pass no root. `server/main.py` is the caller that
turns them on, and this file is the discriminator for that.

⚠ The property here is NOT "the factory isolates". That is
`tests/test_session_context_factory.py`, and `tests/test_session_destinations.py`
proves the pages use it. Both pass with `server/main.py` absent or with its
`session_root` argument deleted. This file fails in that case, and only this file.

⚠ The prototype path must stay OUTSIDE the root. A prototype inside the root makes
`is_relative_to(root)` pass whether or not the session was isolated.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

from exalted_builder import persistence
from exalted_builder.server import auth, config, main


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


def test_two_sessions_of_the_server_get_two_directories(root: Path, database: Path) -> None:
    """The dormancy check. `build_server` must hand `register_pages` a root.

    Delete the `session_root=` argument in `server/main.py` and this is the case
    that reddens.
    """
    registry = main.build_server(session_root=root, db_path=database)

    alpha = registry.ctx_for("alpha")
    beta = registry.ctx_for("beta")

    assert alpha["path"].parent != beta["path"].parent, (
        f"Both sessions save under {alpha['path'].parent}. The hosted entry point "
        "passed no session root, thus every browser writes one file on the "
        "auto-save timer."
    )


def test_the_server_saves_inside_the_session_root(root: Path, database: Path) -> None:
    """The destination comes from the root, not from the prototype."""
    registry = main.build_server(session_root=root, db_path=database)

    path = registry.ctx_for("alpha")["path"]

    assert path.is_relative_to(root), (
        f"The session saves to {path}, which is outside {root}."
    )


def test_the_prototype_path_is_outside_the_root(root: Path) -> None:
    """The negative control for the case above.

    ⚠ Without this, `is_relative_to(root)` proves nothing: a prototype that already
    lives in the root satisfies it with no isolation at all.
    """
    proto = main.prototype_context(root)

    assert not proto["path"].is_relative_to(root), (
        f"The prototype path {proto['path']} is inside {root}. The isolation "
        "assertions above then pass whether or not the session was isolated."
    )


def test_the_session_home_is_the_session_directory(root: Path, database: Path) -> None:
    """🐞 The handler trap of section 3.7b.

    `new_character` and the upload branch rebuild the destination from
    `ctx["home_dir"]`. A home outside the session directory takes the session back
    out of its own folder on the first click of New.
    """
    registry = main.build_server(session_root=root, db_path=database)

    ctx = registry.ctx_for("alpha")

    assert ctx["home_dir"] == ctx["path"].parent, (
        f"home_dir is {ctx['home_dir']} but the session saves in "
        f"{ctx['path'].parent}. A New character leaves the session directory."
    )


def test_the_server_reads_the_root_from_the_environment(root: Path, database: Path,
                                                        monkeypatch) -> None:
    """The whole chain. `build_server` with no argument must call
    `config.session_root`, which reads `EXALTED_SESSION_ROOT`."""
    monkeypatch.setenv(config.SESSION_ROOT_ENV, str(root))
    monkeypatch.setenv(config.DB_PATH_ENV, str(database))

    registry = main.build_server()

    assert registry.ctx_for("alpha")["path"].is_relative_to(root)


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
    run_kwargs: dict = {}
    monkeypatch.setattr(main.ui, "run", lambda *args, **kwargs: (
        calls.append("run"), run_kwargs.update(kwargs)))
    monkeypatch.setattr(sys, "argv", ["exalted-server"])
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "a-real-secret")
    monkeypatch.setenv(config.SESSION_ROOT_ENV, str(root))
    monkeypatch.setenv(config.DB_PATH_ENV, str(database))

    main.main()

    assert calls == ["gate", "quota", "run"], (
        f"main made the calls {calls}. It must install the gate and the quota, "
        "then run.")
    assert guards[0].root == root, "The quota guards a folder that is not the root."
    assert guards[0].limit == 10 * 1024 * 1024
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
