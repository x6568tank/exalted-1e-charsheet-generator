"""The session-cookie secret — `hosting-state-model.md` section 3.4, Constraint 3.

`app.storage.user` raises `RuntimeError` without a `storage_secret`, so tier 1 of the
session design cannot work until each `ui.run` call passes one.

⚠ The property that matters most is NEGATIVE: there is no default secret. A known
secret lets a client forge a session cookie, and no functional test would notice —
the app works perfectly with a secret everybody knows. `test_the_fallback_is_random`
is the one that would fail if somebody adds a convenient constant.
"""

from __future__ import annotations

import pytest

from exalted_builder.server import config


@pytest.fixture(autouse=True)
def _clean_secret(monkeypatch):
    """Each test starts with no environment variable and no cached key."""
    monkeypatch.delenv(config.STORAGE_SECRET_ENV, raising=False)
    config.reset_ephemeral_secret()
    yield
    config.reset_ephemeral_secret()


def test_the_environment_variable_wins(monkeypatch) -> None:
    """A configured secret is used as it is. A hosted deployment sets this, so its
    cookies survive a restart."""
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "a-configured-secret")

    assert config.storage_secret() == "a-configured-secret"


def test_surrounding_space_is_removed(monkeypatch) -> None:
    """A secret from a `.env` file or a shell export can carry a newline."""
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "  padded-secret\n")

    assert config.storage_secret() == "padded-secret"


def test_an_empty_variable_is_the_same_as_none(monkeypatch) -> None:
    """`EXALTED_STORAGE_SECRET=` must not make the cookie key an empty string."""
    monkeypatch.setenv(config.STORAGE_SECRET_ENV, "   ")

    assert config.storage_secret() not in ("", "   ")
    assert len(config.storage_secret()) >= 32


def test_the_fallback_is_stable_within_one_process() -> None:
    """Two calls give one key. A key that changes makes every open session invalid,
    and the user is logged out in the middle of an edit."""
    assert config.storage_secret() == config.storage_secret()


def test_the_fallback_is_random() -> None:
    """⚠ THE DISCRIMINATOR. Two processes must not agree on a key that nobody set.

    A hard-coded default passes every other test in this file and every functional
    test of the application, because the application works correctly with a secret
    that the whole world knows. This test is the only thing that fails.
    """
    first = config.storage_secret()
    config.reset_ephemeral_secret()
    second = config.storage_secret()

    assert first != second, (
        "The fallback secret is a constant. Anybody who reads the source can forge "
        "a session cookie for any deployment that does not set the environment "
        "variable."
    )


def test_the_fallback_is_long_enough() -> None:
    """A short key is guessable. `secrets.token_urlsafe(32)` gives about 43
    characters."""
    assert len(config.storage_secret()) >= 32


# --------------------------------------------------------------------------- #
# The integration check — Constraint 3 of section 3.4
# --------------------------------------------------------------------------- #

MAIN = "tests/_storage_secret_main.py"


@pytest.mark.nicegui_main_file(MAIN)
async def test_tier_one_storage_works_with_the_production_secret(user) -> None:
    """⚠ Passing the argument is not the same as tier 1 working.

    `app.storage.user` raises `RuntimeError` when the secret is absent, and the
    page catches that and prints it. The test reads which of the two happened.
    `tests/_storage_secret_main.py` calls the real `storage_secret()` helper.
    """
    await user.open("/")

    await user.should_see("TIER ONE OK: written")
