"""The login rate limit: `server/throttle.py`.

The human's ruling of 2026-09-11: limit by username. Five attempts are free; then
each failure doubles a cooldown, to a cap. A success clears the name.

⚠ An attempt counts as a failure when it STARTS, and a success clears it. A count
that waits for the bcrypt result lets N parallel attempts all pass the check
before the first one is recorded.
"""

from __future__ import annotations

import pytest

from exalted_builder.server.throttle import LoginThrottle


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def throttle(clock: Clock) -> LoginThrottle:
    return LoginThrottle(clock=clock)


def _fail(throttle: LoginThrottle, name: str, times: int) -> None:
    for _ in range(times):
        assert throttle.begin(name) == 0.0
        # No `succeeded`: the attempt stays a failure.


def test_the_free_attempts_are_not_limited(throttle: LoginThrottle) -> None:
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)


def test_the_attempt_after_the_free_ones_waits(throttle: LoginThrottle) -> None:
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)

    assert throttle.begin("Harmonious") == LoginThrottle.FIRST_COOLDOWN


def test_a_refused_attempt_does_not_extend_the_wait(throttle: LoginThrottle,
                                                    clock: Clock) -> None:
    """A refusal checks no password, thus it is not a guess. Counting it lets a
    player who retries during the wait lock the name for longer and longer."""
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)
    first = throttle.begin("Harmonious")
    clock.now += 1
    second = throttle.begin("Harmonious")

    assert second == first - 1


def test_the_wait_doubles_and_stops_at_the_cap(throttle: LoginThrottle,
                                               clock: Clock) -> None:
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)
    waits = []
    for _ in range(12):
        wait = throttle.begin("Harmonious")
        waits.append(wait)
        clock.now += wait
        assert throttle.begin("Harmonious") == 0.0   # the next guess, a failure

    assert waits[:3] == [LoginThrottle.FIRST_COOLDOWN * n for n in (1, 2, 4)]
    assert max(waits) == LoginThrottle.MAX_COOLDOWN


def test_a_success_clears_the_name(throttle: LoginThrottle, clock: Clock) -> None:
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS - 1)
    assert throttle.begin("Harmonious") == 0.0
    throttle.succeeded("Harmonious")

    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)


def test_one_name_does_not_limit_another(throttle: LoginThrottle) -> None:
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)
    assert throttle.begin("Harmonious") > 0

    assert throttle.begin("Radiant") == 0.0


def test_the_name_is_case_sensitive(throttle: LoginThrottle) -> None:
    """Usernames are case-sensitive, thus "harmonious" is a different account."""
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)

    assert throttle.begin("harmonious") == 0.0


def test_parallel_attempts_are_counted_at_the_start(throttle: LoginThrottle) -> None:
    """🐞 The race. Six attempts start before any result returns. The sixth must
    wait, because the first five are already counted."""
    starts = [throttle.begin("Harmonious") for _ in range(LoginThrottle.FREE_ATTEMPTS + 1)]

    assert starts[-1] > 0


def test_an_old_failure_is_forgotten(throttle: LoginThrottle, clock: Clock) -> None:
    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)
    clock.now += LoginThrottle.FORGET_AFTER + 1

    assert throttle.begin("Harmonious") == 0.0


def test_the_table_is_bounded(clock: Clock) -> None:
    """A bot that tries random names must not grow the table without end."""
    throttle = LoginThrottle(clock=clock, max_names=10)
    for index in range(50):
        throttle.begin(f"name{index}")
        clock.now += 1

    assert len(throttle) <= 10


def test_a_full_table_still_limits_the_new_name(clock: Clock) -> None:
    """🐞 A prune that removes the name it just added counts the failures on a
    record that is not in the table, thus that name is never limited."""
    throttle = LoginThrottle(clock=clock, max_names=3)
    for index in range(3):
        throttle.begin(f"name{index}")
    clock.now += 1

    _fail(throttle, "Harmonious", LoginThrottle.FREE_ATTEMPTS)

    assert throttle.begin("Harmonious") > 0
