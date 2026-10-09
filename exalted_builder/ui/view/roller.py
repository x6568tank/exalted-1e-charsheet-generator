"""
ui/view/roller.py — the dice roller (decision 0019). It rolls a typed dice count
only. ⚠ Read 0019 before you change it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# --------------------------------------------------------------------------- #
# The dumb dice roller (decision 0019)
#
# ⚠ Read 0019 before touching anything below, especially its no-wire rule. The
# roller takes a COUNT the player typed and a LABEL the player wrote; it must
# never learn which roll it is rolling. Nothing here may take a `RollDefinition`,
# a `PoolRow` or a `PoolBreakdown` — the moment a roll's name reaches a result,
# the app is asserting the pool was right, which is what decision 0008 rejected
# and what 0009 was written to prevent. No test can catch that regression.
# --------------------------------------------------------------------------- #

# How many past rolls the transcript keeps. A transcript, not play-state:
# results are never written to the Character (0019) and die with the session.
ROLL_LOG_LENGTH = 12

# What the surface says instead of offering a difficulty or stunt field. 0019
# keeps Storyteller modifiers out: a field for them implies the app could know.
ROLLER_CAVEAT = ("Type the dice you are picking up. Stunt dice, difficulty and "
                 "any Charm effect are the Storyteller's — ask them, this does "
                 "not know.")


@dataclass(frozen=True)
class RollFace:
    """One die as the transcript shows it. `kind` is a rendering class, not a
    rule: 'double' is a 10 under the Rule of Ten, 'one' a 1 that could botch,
    'hit' any other success, 'miss' the rest."""
    value: int
    kind: str


@dataclass(frozen=True)
class RollEntry:
    """One roll in the session transcript.

    ⚠ `label` is the PLAYER's free text and may be empty. It is never filled in
    from a pool row, a Charm or a `RollDefinition` — see the note above.
    """
    label: str
    faces: tuple[RollFace, ...]
    successes: int
    botch: bool
    outcome: str                             # "3 successes" / "Failure" / "Botch"
    detail: str                              # "5 dice · TN 7 · 10s double · can botch"

    @property
    def faces_text(self) -> str:
        """The dice as one line, for a surface with no room to style each face."""
        return " ".join(str(f.value) for f in self.faces)


def new_roller_state() -> dict:
    """The roller's controls, owned by the CALLER for the same reason
    `play.new_pool_state` is: the Play tab is rebuilt on every health-box click,
    and state owned by the roller would wipe the player's typed count and their
    transcript on exactly the click that precedes a roll.

    Both switches default ON because both printed rules are general — the
    exceptions (damage rolls, the Rune) are per-effect and the player turns them
    off because the Storyteller said so.
    """
    from ...engine import dice as dicemod
    return {"count": 1, "label": "",
            "target_number": dicemod.DEFAULT_TARGET_NUMBER,
            "doubles_tens": True, "can_botch": True,
            "log": [],
            # The transcript folds after the newest line. Collapsed by default: a
            # long session's log is the thing being got out of the way, and the
            # roll you just made is the only one you need at a glance.
            "log_open": False}


def roll_detail(count: int, target_number: int, doubles_tens: bool,
                can_botch: bool) -> str:
    """'5 dice · TN 7 · 10s double · can botch' — what was rolled under which
    switches, so a transcript line can still be read an hour later."""
    parts = [f"{count} {'die' if count == 1 else 'dice'}", f"TN {target_number}"]
    parts.append("10s double" if doubles_tens else "10s count once")
    parts.append("can botch" if can_botch else "cannot botch")
    return " · ".join(parts)


def roll_log_split(state: dict) -> tuple[Optional[RollEntry], list[RollEntry]]:
    """In: the roller's state. Out: `(newest, older)` — the roll to keep on
    screen and the ones behind the fold. `newest` is None on an empty log.

    One function so the two shells cannot disagree about which line stays
    visible, which is the whole point of the split.
    """
    log = state.get("log") or []
    return (log[0] if log else None), list(log[1:])


def previous_rolls_label(count: int) -> str:
    """'Previous rolls (3)' — the fold's caption, stating what is hidden. A
    collapsed section with no count reads as an empty one."""
    return f"Previous rolls ({count})"


def roll_dice(state: dict, *, rng=None) -> RollEntry:
    """In: the roller's own `state` (a typed count, a typed label and the two
    switches). Out: a `RollEntry`, also PREPENDED to `state["log"]`, which is
    trimmed to `ROLL_LOG_LENGTH`.

    ⚠ The signature takes no character, ruleset or roll, and must not gain one.
    """
    from ...engine import dice as dicemod
    count = max(0, int(state.get("count") or 0))
    target = int(state.get("target_number") or dicemod.DEFAULT_TARGET_NUMBER)
    doubles = bool(state.get("doubles_tens", True))
    botching = bool(state.get("can_botch", True))
    result = dicemod.roll(count, target, doubles_tens=doubles,
                          can_botch=botching, rng=rng)

    def _kind(face: int) -> str:
        if face == dicemod.TEN and doubles:
            return "double"
        if face >= target:
            return "hit"
        return "one" if face == 1 else "miss"

    entry = RollEntry(
        label=(state.get("label") or "").strip(),
        faces=tuple(RollFace(f, _kind(f)) for f in result.faces),
        successes=result.successes, botch=result.botch,
        outcome=result.summary,
        detail=roll_detail(count, target, doubles, botching))
    log = state.setdefault("log", [])
    log.insert(0, entry)
    del log[ROLL_LOG_LENGTH:]
    return entry
