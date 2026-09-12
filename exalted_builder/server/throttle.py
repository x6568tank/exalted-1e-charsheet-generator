"""
server/throttle.py — the rate limit on login attempts, by username.

The human ruled on 2026-09-11: limit by username, not by address. Behind the
tunnel, every request has the address of the tunnel.

The rule: `FREE_ATTEMPTS` failures have no wait. Each failure after them sets a
wait that starts at `FIRST_COOLDOWN` and doubles, to `MAX_COOLDOWN`. A success
clears the name. A name with no failure for `FORGET_AFTER` seconds is cleared.

⚠ `begin` counts the attempt as a failure before the password is checked, and
`succeeded` removes it. A count that waits for the result lets parallel attempts
all pass the check before the first result arrives.

⚠ A player can keep another player's name in its wait by guessing. This is the
cost of the ruling, and the cap limits it.

⚠ The table is in memory. It is empty after a restart, and it is not shared
between processes. The server runs one process; see server/main.py.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import time


@dataclass
class _Record:
    failures: int = 0
    last_failure: float = 0.0
    blocked_until: float = 0.0


@dataclass
class LoginThrottle:
    """The failure counts of the login names.

    `clock` returns seconds. It defaults to `time.monotonic`. `max_names` bounds
    the table; the name with the oldest failure leaves first.
    """

    FREE_ATTEMPTS = 5
    FIRST_COOLDOWN = 30.0
    MAX_COOLDOWN = 900.0
    FORGET_AFTER = 3600.0

    clock: Callable[[], float] = time.monotonic
    max_names: int = 10_000
    _records: dict[str, _Record] = field(default_factory=dict, init=False, repr=False)

    def begin(self, username: str) -> float:
        """Start a login attempt for `username`.

        Return 0.0 if the attempt can go on; the attempt then counts as a failure
        until `succeeded`. Return the seconds to wait if it cannot; a refused
        attempt changes nothing.
        """
        now = self.clock()
        record = self._records.get(username)
        if record is not None and now - record.last_failure > self.FORGET_AFTER:
            record = None
            del self._records[username]
        if record is not None and record.blocked_until > now:
            return record.blocked_until - now

        if record is None:
            record = self._records[username] = _Record(last_failure=now)
            self._prune(protect=username)
        record.failures += 1
        record.last_failure = now
        # The fifth failure sets the first wait, thus the sixth attempt waits.
        extra = record.failures - self.FREE_ATTEMPTS + 1
        if extra > 0:
            wait = min(self.FIRST_COOLDOWN * 2 ** (extra - 1), self.MAX_COOLDOWN)
            record.blocked_until = now + wait
        return 0.0

    def succeeded(self, username: str) -> None:
        """Clear the failures of `username`. Call it after a correct password."""
        self._records.pop(username, None)

    def __len__(self) -> int:
        return len(self._records)

    def _prune(self, *, protect: str) -> None:
        """Remove the names with the oldest failures until the table is in bounds.

        Never remove `protect`. The caller counts a failure on it next.
        """
        while len(self._records) > self.max_names:
            oldest = min((name for name in self._records if name != protect),
                         key=lambda name: self._records[name].last_failure)
            del self._records[oldest]
