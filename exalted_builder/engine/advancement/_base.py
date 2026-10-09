"""
engine/advancement/_base.py — the XP ledger: the spent, available, and debt totals,
the XP award, the commit of a log row, and the specialty cap.

This module is the bottom of the package. It imports no sibling module.
"""

from __future__ import annotations

from ...models.character import Character, XpEntry
from ...models.rules import AbilityName, RuleSet


# Conventional maxima for raises. The 1-5 dot cap is the universal trait cap used
# throughout chargen; Willpower's permanent maximum is 10.
#
# It is a FLOOR under the elder ceilings rather than the last word: age lifts Essence
# past it and Essence lifts Abilities and Attributes past it (Player's Guide pp.258-259).
# Every such raise asks engine.elder — the constant itself never moves.
_DOT_MAX = 5
_WILLPOWER_MAX = 10

# "You can only have 3 specialties per ability" (human, rules authority, 2026-07-31).
# Counts ROWS, not distinct names — two Swords and one Parrying fills Melee.
SPECIALTIES_PER_ABILITY = 3


def specialty_cap(ruleset: RuleSet, character: Character, ability: AbilityName) -> int:
    """Specialty-row cap for one Ability. The Mountain Folk may have up to five
    Specialties in any Craft (CH6 p.230: "Jadeborn can have up to five Specialties in
    any Craft, but they cannot purchase the same specialty more than three times");
    every other Ability of every splat caps at three (the 2026-07-31 ruling)."""
    if ability == AbilityName.CRAFT and ruleset.exalt_for(character.exalt_type).id == "Mountain-Folk":
        return 5
    return SPECIALTIES_PER_ABILITY


def specialty_count(character: Character, ability: AbilityName) -> int:
    """How many specialty rows this Ability holds. Duplicated names each count: taking
    the same specialty twice is how a specialty stacks, since it has no rating to
    raise."""
    return sum(1 for s in character.specialties if s.ability == ability)


class AdvancementError(ValueError):
    """An illegal or unaffordable advance. The UI surfaces the message."""


# --------------------------------------------------------------------------- #
# XP accounting
# --------------------------------------------------------------------------- #

def xp_spent(character: Character) -> int:
    """Total XP committed across the log."""
    return sum(entry.cost for entry in character.xp_log)


def xp_available(character: Character) -> int:
    """Unspent XP: earned minus the log total. Goes NEGATIVE when a Merit change was
    taken on credit (see `xp_debt`) or after a hand-edit."""
    return character.xp_earned - xp_spent(character)


def xp_debt(character: Character) -> int:
    """Outstanding balance owed on a Merit change the character could not afford —
    Player's Guide p.17: "she pays whatever she has available and must allocate all
    further experience to the remaining balance until it is paid in full."

    ⚠ DERIVED, never stored, and that is load-bearing. Storing the balance and paying
    it down inside `add_xp` silently DESTROYS experience: the log then records only the
    affordable part and the rest is never counted as spent. Logging the FULL cost and
    letting `xp_available` go negative makes the debt self-evident, self-clearing as XP
    is earned, and impossible to lose."""
    return max(0, -xp_available(character))


def add_xp(character: Character, amount: int) -> None:
    """Adjust earned XP by `amount` (negative to correct an over-grant). Earned
    never drops below zero. Any outstanding debt clears automatically, because it is
    derived from the same two numbers."""
    character.xp_earned = max(0, character.xp_earned + amount)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _ensure_locked(character: Character) -> None:
    if not character.chargen_locked:
        raise AdvancementError("Lock chargen before spending XP.")


def _commit(character: Character, target: str, detail: str,
            frm: int | None, to: int | None, cost: int) -> XpEntry:
    """Affordability gate + append the log row. Call only after the trait change is
    decided (cost computed) but it is fine to mutate before or after — nothing here
    touches traits."""
    if cost > xp_available(character):
        raise AdvancementError(
            f"Costs {cost} XP; only {xp_available(character)} available.")
    entry = XpEntry(target=target, detail=detail, from_rating=frm, to_rating=to, cost=cost)
    character.xp_log.append(entry)
    return entry
