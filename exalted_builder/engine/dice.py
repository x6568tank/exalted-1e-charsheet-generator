"""
engine/dice.py — the dumb roller (decision 0019).

In: a dice COUNT the player typed, a target number, a die size, and the two
printed switches. Out: the faces rolled, the success count and a botch flag.
Between them sit exactly two rules off the page — the Rule of Ten and the Rule
of One — both of which are properties of a handful of dice and know nothing
about whose dice they are.

⚠ **What must never enter this signature: a roll.** Decision 0009 barred rolling
entirely, and 0019 reversed it only for a roller that takes a NUMBER. The gap
between a `RollDefinition` (or a `Character`, or a `PoolBreakdown`) and this
function is the whole safety mechanism: a roller that cannot know which roll it
is rolling cannot be asked to add the Charm dice, which is the open-ended job
decision 0008 rejected. Pre-filling the count from a pool row is the SURFACE's
business and legal only under 0019's three conditions — chiefly that the
result's label is the player's free text and never the roll's name.

Also out, and none of it belongs here later: Storyteller modifiers, opposed
rolls or any resolution, and a success-odds display (0009 barred that by name
and 0019 kept the bar).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# The face the Rule of Ten names. It is the literal face and not the die's
# maximum: the page says "rolls a '10'", so a d6's 6 doubles nothing.
TEN = 10

DEFAULT_TARGET_NUMBER = 7
DEFAULT_DIE_FACES = 10

# A guard on the input field, not a rule — nothing printed caps a pool. It is
# high enough that no sheet arithmetic reaches it and low enough that a
# fat-fingered 99999 cannot hang the surface rendering the faces.
MAX_DICE = 100


@dataclass(frozen=True)
class RollResult:
    """One roll's dice and what they came to.

    ⚠ Deliberately carries no name, id or label for the roll. See the module
    docstring: a label the app chose is the app asserting the pool was right.
    """
    faces: tuple[int, ...]
    successes: int
    botch: bool
    target_number: int = DEFAULT_TARGET_NUMBER
    die_faces: int = DEFAULT_DIE_FACES
    doubles_tens: bool = True
    can_botch: bool = True

    @property
    def ones(self) -> int:
        """How many 1s came up — for display only. ⚠ 1s never subtract
        successes (core p.89); that is another edition's convention."""
        return self.faces.count(1)

    @property
    def tens(self) -> int:
        """How many 10s came up, each worth two successes under the Rule of Ten
        unless `doubles_tens` is off."""
        return self.faces.count(TEN)

    @property
    def summary(self) -> str:
        """'3 successes' / '1 success' / 'Failure' / 'Botch' — the outcome in one
        phrase, still naming no roll."""
        if self.botch:
            return "Botch"
        if self.successes == 0:
            return "Failure"
        return f"{self.successes} success" + ("" if self.successes == 1 else "es")


def count_successes(faces, target_number: int = DEFAULT_TARGET_NUMBER, *,
                    doubles_tens: bool = True,
                    can_botch: bool = True) -> tuple[int, bool]:
    """In: the faces of an already-rolled handful. Out: `(successes, botch)`.

    A die at `target_number` or higher is one success, and a 10 is two (the Rule
    of Ten, core p.90) unless `doubles_tens` is off. A botch is no die at target
    or higher AND at least one 1 (the Rule of One, p.89) — one success or more
    and the 1s are ignored entirely.

    ⚠ The two switches default ON because the rules are general; the printed
    exceptions (damage rolls, the Rune) are per-effect and turn both off
    together, and the player sets them because the Storyteller said so. The
    roller cannot work it out — it does not know which roll this is.
    """
    hits = [f for f in faces if f >= target_number]
    successes = len(hits)
    if doubles_tens:
        successes += sum(1 for f in hits if f == TEN)
    botch = can_botch and not hits and 1 in faces
    return successes, botch


def roll(count: int, target_number: int = DEFAULT_TARGET_NUMBER,
         die_faces: int = DEFAULT_DIE_FACES, *, doubles_tens: bool = True,
         can_botch: bool = True,
         rng: random.Random | None = None) -> RollResult:
    """In: how many dice to pick up. Out: a `RollResult` of that many faces,
    counted by `count_successes`.

    `count` may be 0 — a pool can fall below one die — but not negative, and not
    above `MAX_DICE`. `rng` is injectable because a roller that cannot be seeded
    cannot be tested; omitted, it is a fresh `random.Random`.
    """
    if count < 0:
        raise ValueError(f"cannot roll {count} dice")
    if count > MAX_DICE:
        raise ValueError(f"cannot roll more than {MAX_DICE} dice at once")
    if die_faces < 2:
        raise ValueError(f"a die needs at least 2 faces, got {die_faces}")
    source = rng if rng is not None else random.Random()
    faces = tuple(source.randint(1, die_faces) for _ in range(count))
    successes, botch = count_successes(
        faces, target_number, doubles_tens=doubles_tens, can_botch=can_botch)
    return RollResult(
        faces=faces, successes=successes, botch=botch,
        target_number=target_number, die_faces=die_faces,
        doubles_tens=doubles_tens, can_botch=can_botch)
