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

import pytest

from exalted_builder.server import config, main


@pytest.fixture
def root(tmp_path: Path) -> Path:
    """A session root of this test alone."""
    return tmp_path / "sessions"


# --------------------------------------------------------------------------- #
# The wiring: the entry point passes a root
# --------------------------------------------------------------------------- #


def test_two_sessions_of_the_server_get_two_directories(root: Path) -> None:
    """The dormancy check. `build_server` must hand `register_pages` a root.

    Delete the `session_root=` argument in `server/main.py` and this is the case
    that reddens.
    """
    registry = main.build_server(session_root=root)

    alpha = registry.ctx_for("alpha")
    beta = registry.ctx_for("beta")

    assert alpha["path"].parent != beta["path"].parent, (
        f"Both sessions save under {alpha['path'].parent}. The hosted entry point "
        "passed no session root, thus every browser writes one file on the "
        "auto-save timer."
    )


def test_the_server_saves_inside_the_session_root(root: Path) -> None:
    """The destination comes from the root, not from the prototype."""
    registry = main.build_server(session_root=root)

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


def test_the_session_home_is_the_session_directory(root: Path) -> None:
    """🐞 The handler trap of section 3.7b.

    `new_character` and the upload branch rebuild the destination from
    `ctx["home_dir"]`. A home outside the session directory takes the session back
    out of its own folder on the first click of New.
    """
    registry = main.build_server(session_root=root)

    ctx = registry.ctx_for("alpha")

    assert ctx["home_dir"] == ctx["path"].parent, (
        f"home_dir is {ctx['home_dir']} but the session saves in "
        f"{ctx['path'].parent}. A New character leaves the session directory."
    )


def test_the_server_reads_the_root_from_the_environment(root: Path, monkeypatch) -> None:
    """The whole chain. `build_server` with no argument must call
    `config.session_root`, which reads `EXALTED_SESSION_ROOT`."""
    monkeypatch.setenv(config.SESSION_ROOT_ENV, str(root))

    registry = main.build_server()

    assert registry.ctx_for("alpha")["path"].is_relative_to(root)


def test_the_server_refuses_to_start_without_a_root(monkeypatch) -> None:
    """No default, for section 3.7's reason: one shared directory is the defect."""
    monkeypatch.delenv(config.SESSION_ROOT_ENV, raising=False)

    with pytest.raises(RuntimeError, match=config.SESSION_ROOT_ENV):
        main.build_server()


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
# The exposure guard: there is no auth yet
# --------------------------------------------------------------------------- #


def test_a_public_bind_needs_the_explicit_acknowledgement() -> None:
    """⚠ Auth is piece 3 and is NOT built. `hosting-per-instance.md` records what
    an un-gated hostname costs: the character, the homebrew library and the
    Storyteller screen, open to whoever finds the name.

    Thus a non-loopback bind must be asked for twice. Delete this and the default
    entry point publishes an unauthenticated server.
    """
    with pytest.raises(RuntimeError, match="no authentication"):
        main.check_bind_is_allowed("0.0.0.0", acknowledged=False)


def test_a_loopback_bind_needs_no_acknowledgement() -> None:
    main.check_bind_is_allowed("127.0.0.1", acknowledged=False)
    main.check_bind_is_allowed("localhost", acknowledged=False)


def test_a_public_bind_is_allowed_once_acknowledged() -> None:
    main.check_bind_is_allowed("0.0.0.0", acknowledged=True)


def test_the_default_host_is_loopback() -> None:
    """The default must be the safe one. A default of 0.0.0.0 makes the guard
    above a thing the operator meets after the fact."""
    assert main.DEFAULT_HOST == "127.0.0.1"
