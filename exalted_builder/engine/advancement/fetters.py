"""
engine/advancement/fetters.py — the ghost Fetters and Passions (Exalted: The
Abyssals p.283): raise, add, and shift.
"""

from __future__ import annotations

from typing import Optional

from .. import costs, derive
from ...models.character import Character, FetterEntry, PassionEntry, XpEntry
from ...models.rules import RuleSet, VirtueName

from ._base import _DOT_MAX, AdvancementError, _commit, _ensure_locked


# --------------------------------------------------------------------------- #
# Fetters and Passions (ghosts — Exalted: The Abyssals p.283)
#
# Four operations, two of which have no analogue anywhere else in the build: a
# "shift" moves a trait's FOCUS without changing any rating, so it is priced flat and
# the totals do not move. Passions are never bought — their dots come from the
# Virtues (p.283) — so `raise_passion` deliberately does not exist.
# --------------------------------------------------------------------------- #

def _fetter_index(character: Character, name: str) -> int:
    for i, f in enumerate(character.fetters):
        if f.name == name:
            return i
    raise AdvancementError(f"No Fetter named {name!r}.")


def _fetter_headroom(ruleset: RuleSet, character: Character) -> int:
    """Dots of Fetter still allowed by the p.127 cap (Willpower + Essence). Asked
    before every purchase that adds a dot, because the cap binds in play — it is not a
    chargen-only rule."""
    return derive.fetter_cap(character, ruleset) - derive.fetter_dots_spent(character)


def raise_fetter(ruleset: RuleSet, character: Character, name: str) -> XpEntry:
    """Raise one Fetter a dot for `current x 3` (p.283)."""
    _ensure_locked(character)
    idx = _fetter_index(character, name)
    frm = character.fetters[idx].rating
    if frm >= _DOT_MAX:
        raise AdvancementError(f"{name} is already at {_DOT_MAX}.")
    if _fetter_headroom(ruleset, character) < 1:
        raise AdvancementError(
            f"Fetters are at the cap of {derive.fetter_cap(character, ruleset)} dots "
            f"(Willpower + Essence, p.127).")
    cost = costs.fetter_step(ruleset, character, frm)
    entry = _commit(character, "fetters", name, frm, frm + 1, cost)
    character.fetters[idx].rating = frm + 1
    return entry


def add_fetter(ruleset: RuleSet, character: Character, name: str,
               note: str = "") -> XpEntry:
    """Form a new one-dot Fetter — 20 XP, or 15 for a ghost who knows the Arcanos the
    table names (p.283). The discount is data, not a hardcoded id; see
    `costs.new_fetter_cost`."""
    _ensure_locked(character)
    if not name.strip():
        raise AdvancementError("A Fetter needs a name.")
    if any(f.name == name for f in character.fetters):
        raise AdvancementError(f"{name} is already a Fetter.")
    if _fetter_headroom(ruleset, character) < 1:
        raise AdvancementError(
            f"Fetters are at the cap of {derive.fetter_cap(character, ruleset)} dots "
            f"(Willpower + Essence, p.127).")
    cost = costs.new_fetter_cost(ruleset, character)
    entry = _commit(character, "new_fetters", name, None, 1, cost)
    character.fetters.append(FetterEntry(name=name, rating=1, note=note))
    return entry


def shift_fetter(ruleset: RuleSet, character: Character, name: str,
                 to_name: str) -> XpEntry:
    """Move a Fetter's focus (p.283, "Shift Fetter | 10"). The RATING does not change —
    only what the ghost is anchored to — so this touches no pool and no cap."""
    _ensure_locked(character)
    idx = _fetter_index(character, name)
    if not to_name.strip():
        raise AdvancementError("A Fetter needs a name.")
    if any(f.name == to_name for f in character.fetters):
        raise AdvancementError(f"{to_name} is already a Fetter.")
    cost = ruleset.xp_costs_for(character.exalt_type).shift_fetter
    entry = _commit(character, "shift_fetters", f"{name}>{to_name}", None, None, cost)
    character.fetters[idx].name = to_name
    return entry


def shift_passion(ruleset: RuleSet, character: Character, frm: str, to: str,
                  to_virtue: Optional[VirtueName] = None) -> XpEntry:
    """Move one dot from one Passion to another (p.283, "Shift Passion | 20").

    "This decreases a Passion by one dot. In turn, it increases an existing Passion by
    one dot or creates a new one-dot Passion." So the TOTAL never moves — which is what
    keeps this consistent with p.283's other half, that Passions rise only when the
    Virtues do. A Passion emptied to zero is removed rather than left as a 0-dot row.

    `to_virtue` names the Virtue the destination Passion belongs to when it is being
    created; it defaults to the source's, since the pools are per-Virtue and a shift
    across Virtues would move a dot between two pools that the Virtues, not the player,
    are supposed to size. Passing one explicitly is allowed — the page does not forbid
    it — and `validate.check_fetters_and_passions` reports the result either way.
    """
    _ensure_locked(character)
    src = next((p for p in character.passions if p.name == frm), None)
    if src is None:
        raise AdvancementError(f"No Passion named {frm!r}.")
    if src.rating < 1:
        raise AdvancementError(f"{frm} has no dots to shift.")
    if not to.strip():
        raise AdvancementError("A Passion needs a name.")
    dst = next((p for p in character.passions if p.name == to), None)
    if dst is not None and dst.rating >= _DOT_MAX:
        raise AdvancementError(f"{to} is already at {_DOT_MAX}.")
    cost = ruleset.xp_costs_for(character.exalt_type).shift_passion
    entry = _commit(character, "shift_passions", f"{frm}>{to}", None, None, cost)
    src.rating -= 1
    if dst is None:
        character.passions.append(
            PassionEntry(name=to, virtue=to_virtue or src.virtue, rating=1))
    else:
        dst.rating += 1
    if src.rating == 0:
        character.passions.remove(src)
    return entry
