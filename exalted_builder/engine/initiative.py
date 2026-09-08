"""
engine/initiative.py — the initiative RATING (core p.227).

In: a RuleSet, a Character and the weapon they are wielding. Out: an
`InitiativeRating` — Dexterity + Wits + that weapon's Speed, itemised, plus the
standing note that the table adds **1d10 each turn** to get the turn's total.

⚠ **A RATING, not a pool and not a roll.** Decision 0019 lifted 0016's exclusion
of initiative on the express condition that it is never authored as a row in
`data/dice_pools.json`: a pool row renders a total in DICE, and the dumb roller
sits on the same tab, so a rating that looked like a pool would be picked up as a
handful of dice. It is a rating plus ONE d10. Nothing here rolls.

⚠ Weapon Speed is a FLAT modifier, not dice (p.326: "added to or subtracted from
the character's initiative total"). The sign is stored in the data — Daiklave +3,
Grand Daiklave -3, Sledge -6 — so no caller flips it.

**The two adjustments to Speed, both through code that already owned them:**

* the magical material (p.341: orichalcum +1 for Solars, jade +3 for the
  Dragon-Blooded, none from moonsilver/starmetal/soulsteel), via
  `derive.effective_weapon`, which also carries the Exalt-type gate and the Merit
  that refuses the bonus outright;
* the weapon's unmet minimums, one off Speed per dot short, via
  `pools.weapon_minimum_shortfall`, which owns that citation.

**What does NOT reach the rating** — the human's ruling, 2026-09-08, with their
citations. Each is on `EXCLUDES` so the surface states it:

* **Charms.** Nothing is modelled; Speardancer Concentration (PG) adding Essence
  to Initiative for the turn is the example of what a player must add themselves.
  Same open-ended job decision 0008 refused.
* **Armour mobility and encumbrance.** p.332 scopes mobility to rolls needing
  agility or physical dexterity — dodge, Athletics — and a rating is not such a
  roll. ⚠ The human's reading of scope, NOT an explicit exclusion in the text: it
  is a ruling, and reversing it is theirs.
* **Armour fatigue.** "-1 to all actions" (p.332) is unqualified, but the core
  initiative rules make no such adjustment, so neither does this. The Storyteller's.
* **Wound penalties.** They apply to initiative only under **Power Combat**
  (Player's Guide), which this build does not implement. ⚠ Adopting Power Combat
  redefines Speed wholesale — it becomes a function of reach and weapons gain a
  Rate stat — so every weapon value in `data/` changes with it. That is not "add a
  wound line here".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..models.character import Character, Weapon
from ..models.rules import AttributeName, RuleSet
from . import derive
from .pools import PoolLine, weapon_minimum_shortfall

# Shown with every rating. The 0008 mitigation in data form, exactly as
# `pools.EXCLUDES` is: a surface that renders `total` must also render these.
EXCLUDES: tuple[str, ...] = (
    "Charm effects (Speardancer Concentration adds Essence for the turn).",
    "Armour mobility and encumbrance — agility rolls only (p.332).",
    "Armour fatigue — \"-1 to all actions\" (p.332); the core is silent on "
    "initiative. Ask the ST.",
    "Wound penalties — Power Combat only (Player's Guide), not implemented.",
)

TURN_NOTE = "Add 1d10 each turn for that turn's total (p.227)."

TIE_BREAK = ("Ties break on the higher Dexterity + Wits; still tied, roll off "
             "(p.227).")


@dataclass(frozen=True)
class InitiativeRating:
    """A rating, itemised. `total` is the sum of `lines` and nothing else, so the
    breakdown can always be checked against the number it produced.

    ⚠ Deliberately NOT a `PoolBreakdown`: that type means dice, and this number is
    not dice. The separate type is what stops a surface rendering a rating in the
    pool list, where the roller beside it invites picking it up as a handful.

    ⚠ `total` is NOT clamped. A Sledge (-6) in weak hands is a negative rating and
    nothing printed floors it — the same reasoning `PoolBreakdown.below_one`
    carries. Report it honestly; what happens next is the Storyteller's.
    """
    lines: tuple[PoolLine, ...]
    total: int
    excludes: tuple[str, ...] = EXCLUDES
    turn_note: str = TURN_NOTE
    tie_break: str = TIE_BREAK

    @property
    def summary(self) -> str:
        """'Dexterity 4 + Wits 2 + Daiklave (speed) 3 = 9' — the arithmetic on one
        line, for a surface with no room for the itemised list."""
        parts = [f"{ln.label} {ln.value:+d}" for ln in self.lines]
        return f"{' '.join(parts).lstrip('+').strip()} = {self.total}"

    @property
    def compact(self) -> str:
        """'+4 dex +2 wits +3 spd' — the same arithmetic abbreviated, WITHOUT the
        total, for a caller that prints the number separately."""
        return " ".join(f"{ln.value:+d} {ln.short or ln.label.lower()}"
                        for ln in self.lines)


def initiative(ruleset: RuleSet, character: Character, *,
               weapon: Optional[Weapon] = None) -> InitiativeRating:
    """In: the character and the weapon in hand (None = unarmed). Out: their
    initiative rating, itemised.

    Dexterity + Wits (p.227), then — when a weapon is wielded — its Speed after
    the magical-material bonus, and a negative line for any dots it is short of
    its own minimums. Unarmed, the two Attributes are the whole rating.

    A Speed of 0 still gets its line: most swords are +0, and a player who cannot
    see the weapon counted cannot tell it from the weapon they failed to choose.
    """
    lines: list[PoolLine] = [
        PoolLine("Dexterity", character.attributes[AttributeName.DEXTERITY],
                 short="dex"),
        PoolLine("Wits", character.attributes[AttributeName.WITS], short="wits"),
    ]

    if weapon is not None:
        # Through `effective_weapon`, never `weapon.speed`: the material bonus is
        # gated on the wielder's Exalt type AND on a Merit that can refuse it, and
        # both gates live in that function (p.341).
        eff = derive.effective_weapon(ruleset, character, weapon)
        name = weapon.name or "Weapon"
        lines.append(PoolLine(f"{name} (speed)", eff.speed, short="spd"))
        shortfall = weapon_minimum_shortfall(character, weapon)
        if shortfall:
            lines.append(PoolLine(
                f"{name} (minimums not met)", -shortfall,
                "one off Speed per dot short of the weapon's minima (p.327)",
                short="min"))

    return InitiativeRating(lines=tuple(lines),
                            total=sum(ln.value for ln in lines))
