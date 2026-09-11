"""
server/session.py — one application context for each browser session.

**The defect this removes.** `ui/builder.py:register_pages` builds one `ctx` in
`main()`. Both routes close over it, thus every browser edits one `Character`.
`docs/plans/hosting-state-model.md` section 3.1 records this. Section 3.4 gives the
design: a registry that holds the live context, keyed by the session.

The contract:

  * `ctx_for(key)` returns the SAME dict for the same key. The GM handoff repoints
    `ctx["char"]` by reference and then loads a new page. A copy breaks it, and no
    test outside this file fails.
  * Two keys get two dicts. The factory makes each one.
  * The registry is bounded. It evicts by idle time and by count.
  * An evicted session rebuilds from the factory on its next request.

⚠ This module imports no web toolkit and no database. The caller supplies the key
and the factory. Auth maps a cookie to a user; this module does not.

⚠ The registry holds live `Character` objects. Thus it can never be JSON, thus it
can never move between processes. Run one worker. Section 3.4 gives the evidence:
Redis makes every NiceGUI store serialized, so it is not an alternative.

⚠ This class is not thread-safe. It is safe under one asyncio event loop, because
no method of it awaits. Do not add an `await` to a mutating method.

⚠ Eviction discards work that is not saved. `on_evict` is the seam for the
debounced auto-save of section 3.7. A deployment that supplies no hook loses the
edits of an idle session.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
import time

# One hour idle, and 200 live sessions. Both are memory settings, not rules.
# A context holds one Character and one Party, thus the cost of a session is small
# but not zero.
_DEFAULT_MAX_IDLE_SECONDS = 3600.0
_DEFAULT_MAX_SESSIONS = 200


@dataclass
class _Entry:
    """One live context and the time of its last use."""

    ctx: dict
    last_used: float


@dataclass
class SessionRegistry:
    """The live contexts of all browser sessions.

    `factory` takes a session key and returns a new context dict. The registry
    calls it on the first request of a session, and again after an eviction.

    `max_idle_seconds` and `max_sessions` bound the registry. `sweep` applies the
    first; a new session applies the second.

    `on_evict` takes the key and the context of a session that leaves the
    registry. Supply the auto-save here.

    `clock` returns seconds. It defaults to `time.monotonic`. A test supplies its
    own, because a sweep test that sleeps costs seconds and buys nothing.

    ⚠ Instantiate this once for each process, in the wiring layer. A module-level
    instance shares state between tests.
    """

    factory: Callable[[str], dict]
    max_idle_seconds: float = _DEFAULT_MAX_IDLE_SECONDS
    max_sessions: int = _DEFAULT_MAX_SESSIONS
    on_evict: Callable[[str, dict], None] | None = None
    clock: Callable[[], float] = time.monotonic
    _entries: dict[str, _Entry] = field(default_factory=dict, init=False, repr=False)

    # ----------------------------------------------------------------- #
    # Read
    # ----------------------------------------------------------------- #

    def ctx_for(self, key: str) -> dict:
        """Return the context of session `key`, and record the use.

        Build the context from the factory if the session has none. Apply the
        count bound after the insert, and never to the new session.
        """
        entry = self._entries.get(key)
        if entry is None:
            entry = _Entry(ctx=self.factory(key), last_used=self.clock())
            self._entries[key] = entry
            self._apply_cap(protect=key)
        else:
            entry.last_used = self.clock()
        return entry.ctx

    def keys(self) -> list[str]:
        """The keys of the live sessions, in insertion order."""
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, key: object) -> bool:
        return key in self._entries

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    # ----------------------------------------------------------------- #
    # Eviction
    # ----------------------------------------------------------------- #

    def sweep(self) -> int:
        """Evict each session that is idle for more than `max_idle_seconds`.

        Return the number of evicted sessions. ⚠ Stop and re-raise if `on_evict`
        fails, and keep that session. See `_evict`.
        """
        cutoff = self.clock() - self.max_idle_seconds
        stale = [key for key, entry in self._entries.items() if entry.last_used < cutoff]
        for key in stale:
            self._evict(key)
        return len(stale)

    def discard(self, key: str) -> None:
        """Evict session `key`. Do nothing if the session is not in the registry.

        A logout calls this.
        """
        if key in self._entries:
            self._evict(key)

    def clear(self) -> None:
        """Evict all sessions. A shutdown calls this, to run the hook on each."""
        for key in self.keys():
            self._evict(key)

    # ----------------------------------------------------------------- #
    # Internals
    # ----------------------------------------------------------------- #

    def _evict(self, key: str) -> None:
        """Remove session `key` and run `on_evict`.

        ⚠ Put the session back and re-raise if the hook fails. An eviction
        discards work that is not saved, thus a failed save must not also lose the
        context. Memory is the cheaper loss.
        """
        entry = self._entries.pop(key)
        if self.on_evict is None:
            return
        try:
            self.on_evict(key, entry.ctx)
        except BaseException:
            self._entries[key] = entry
            raise

    def _apply_cap(self, *, protect: str) -> None:
        """Evict the least recently used sessions until the count is in bounds.

        Never evict `protect`. The caller is about to return that context.
        """
        while len(self._entries) > self.max_sessions:
            candidates = [key for key in self._entries if key != protect]
            if not candidates:
                return
            oldest = min(candidates, key=lambda key: self._entries[key].last_used)
            self._evict(oldest)
