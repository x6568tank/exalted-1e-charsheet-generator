"""The per-session context registry — tier 2 of `hosting-state-model.md` section 3.4.

This is the piece that makes two browsers edit two characters. `ui/builder.py`
builds one `ctx` in `main()` and both routes close over it, so every connection
shares one `Character` (section 3.1). The registry replaces that one dict with one
dict per session.

⚠ Nothing imports the registry yet. It is deliberately additive: the wiring is a
later step, and `tests/test_session_isolation.py` stays `xfail` until it lands.
These tests prove the registry's own behaviour, NOT that the app is isolated. Do
not delete an xfail marker there on the strength of a green run here.

⚠ The registry holds live `Character` objects, so it can never be JSON, so it can
never be shared between processes. Section 3.4 records the consequence: run one
worker. A test that assumes two registries stay in step is asserting a property
this design does not have.

The tests inject a clock. A sweep test that sleeps buys nothing and costs seconds.
"""

from __future__ import annotations

import pytest

from exalted_builder.server.session import SessionRegistry


class _Clock:
    """A hand-driven clock. `advance` moves it; `__call__` reads it."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _counting_factory() -> tuple[list[str], object]:
    """A factory and the list of keys it was called with. Each call returns a new
    dict, so an implementation that shares one context fails the identity tests."""
    calls: list[str] = []

    def factory(key: str) -> dict:
        calls.append(key)
        return {"char": f"character-for-{key}", "member": None}

    return calls, factory


# --------------------------------------------------------------------------- #
# Identity — the property the whole refactor exists for
# --------------------------------------------------------------------------- #

def test_one_key_gives_one_context_object() -> None:
    """A second request in the same session gets the same object, not a copy. The
    GM handoff repoints `ctx['char']` by reference and then does a full page load,
    so a copy breaks it silently (section 3.2)."""
    calls, factory = _counting_factory()
    registry = SessionRegistry(factory=factory)

    first = registry.ctx_for("session-a")
    second = registry.ctx_for("session-a")

    assert first is second
    assert calls == ["session-a"], "The factory ran twice for one session."


def test_two_keys_give_two_context_objects() -> None:
    """Two sessions get two contexts. This is the defect in section 3.1."""
    calls, factory = _counting_factory()
    registry = SessionRegistry(factory=factory)

    a = registry.ctx_for("session-a")
    b = registry.ctx_for("session-b")

    assert a is not b
    assert a["char"] != b["char"]
    assert calls == ["session-a", "session-b"]


def test_an_edit_in_one_session_does_not_reach_another() -> None:
    """Mutation of one context leaves the other alone. The tabs mutate the
    character in place, so the registry must not share any level of the dict."""
    _, factory = _counting_factory()
    registry = SessionRegistry(factory=factory)

    registry.ctx_for("session-a")["char"] = "renamed"

    assert registry.ctx_for("session-b")["char"] == "character-for-session-b"


# --------------------------------------------------------------------------- #
# Bounds — section 3.4 requires the registry to be bounded
# --------------------------------------------------------------------------- #

def test_an_idle_session_is_swept() -> None:
    """`sweep` removes a session that is idle for longer than `max_idle_seconds`."""
    clock = _Clock()
    _, factory = _counting_factory()
    registry = SessionRegistry(factory=factory, max_idle_seconds=60.0, clock=clock)

    registry.ctx_for("session-a")
    clock.advance(61.0)

    assert registry.sweep() == 1
    assert len(registry) == 0


def test_a_busy_session_is_not_swept() -> None:
    """A read of the context resets its idle time. Without this the sweep evicts
    the session of a player who is typing."""
    clock = _Clock()
    _, factory = _counting_factory()
    registry = SessionRegistry(factory=factory, max_idle_seconds=60.0, clock=clock)

    registry.ctx_for("session-a")
    clock.advance(50.0)
    registry.ctx_for("session-a")
    clock.advance(50.0)

    assert registry.sweep() == 0
    assert len(registry) == 1


def test_the_cap_evicts_the_least_recently_used_session() -> None:
    """A new session above `max_sessions` evicts the oldest use, not the oldest
    creation. `session-a` is created first but used last, so `session-b` goes."""
    clock = _Clock()
    _, factory = _counting_factory()
    registry = SessionRegistry(factory=factory, max_sessions=2, clock=clock)

    registry.ctx_for("session-a")
    clock.advance(1.0)
    registry.ctx_for("session-b")
    clock.advance(1.0)
    registry.ctx_for("session-a")
    clock.advance(1.0)
    registry.ctx_for("session-c")

    assert set(registry.keys()) == {"session-a", "session-c"}


def test_the_cap_never_evicts_the_session_it_just_made() -> None:
    """`ctx_for` returns a context that is IN the registry, at every cap.

    ⚠ The cap of 0 is the discriminator, and it is the only one. Above 0 the new
    session is the most recently used, thus the least-recently-used rule never
    selects it and a defect in the protection cannot show. A cap of 0 is a
    misconfiguration, and it must degrade to one live session, not to a context
    that the caller holds and the registry has already discarded.
    """
    _, factory = _counting_factory()
    registry = SessionRegistry(factory=factory, max_sessions=0)

    ctx = registry.ctx_for("session-a")

    assert list(registry.keys()) == ["session-a"], (
        "The registry returned a context it does not hold. The next request of "
        "this session rebuilds from the factory and the edit is lost."
    )
    assert registry.ctx_for("session-a") is ctx


# --------------------------------------------------------------------------- #
# Rehydration — an evicted session must come back
# --------------------------------------------------------------------------- #

def test_an_evicted_session_rebuilds_from_the_factory() -> None:
    """The next request after an eviction calls the factory again. The session
    continues; it does not error."""
    clock = _Clock()
    calls, factory = _counting_factory()
    registry = SessionRegistry(factory=factory, max_idle_seconds=60.0, clock=clock)

    first = registry.ctx_for("session-a")
    clock.advance(61.0)
    registry.sweep()
    second = registry.ctx_for("session-a")

    assert first is not second
    assert calls == ["session-a", "session-a"]


# --------------------------------------------------------------------------- #
# The eviction hook — the seam the auto-save of section 3.7 needs
# --------------------------------------------------------------------------- #

def test_the_hook_sees_each_evicted_session_once() -> None:
    """`on_evict` takes the key and the context. It runs once for each eviction."""
    clock = _Clock()
    _, factory = _counting_factory()
    seen: list[tuple[str, str]] = []
    registry = SessionRegistry(
        factory=factory, max_idle_seconds=60.0, clock=clock,
        on_evict=lambda key, ctx: seen.append((key, ctx["char"])),
    )

    registry.ctx_for("session-a")
    registry.ctx_for("session-b")
    clock.advance(61.0)
    registry.sweep()

    assert sorted(seen) == [("session-a", "character-for-session-a"),
                            ("session-b", "character-for-session-b")]


def test_a_failed_hook_keeps_the_session(caplog) -> None:
    """⚠ An eviction discards unsaved work. If `on_evict` raises, the registry
    KEEPS the session and re-raises. Memory is the cheaper loss."""
    clock = _Clock()
    _, factory = _counting_factory()

    def failing_hook(key: str, ctx: dict) -> None:
        raise RuntimeError("the save failed")

    registry = SessionRegistry(factory=factory, max_idle_seconds=60.0, clock=clock,
                               on_evict=failing_hook)
    kept = registry.ctx_for("session-a")
    clock.advance(61.0)

    with pytest.raises(RuntimeError, match="the save failed"):
        registry.sweep()

    assert registry.ctx_for("session-a") is kept, (
        "The registry dropped a session whose save failed. That is the data loss "
        "the hook exists to prevent."
    )


def test_discard_removes_one_session_and_runs_the_hook() -> None:
    """`discard` removes a named session. A logout uses it."""
    _, factory = _counting_factory()
    seen: list[str] = []
    registry = SessionRegistry(factory=factory,
                               on_evict=lambda key, ctx: seen.append(key))

    registry.ctx_for("session-a")
    registry.ctx_for("session-b")
    registry.discard("session-a")

    assert list(registry.keys()) == ["session-b"]
    assert seen == ["session-a"]


def test_discard_of_an_unknown_session_does_nothing() -> None:
    """`discard` on a missing key is not an error. Two requests can log out."""
    _, factory = _counting_factory()
    seen: list[str] = []
    registry = SessionRegistry(factory=factory,
                               on_evict=lambda key, ctx: seen.append(key))

    registry.discard("never-existed")

    assert seen == []
