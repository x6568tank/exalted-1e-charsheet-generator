"""
engine/elder.py — the ONE place age moves a trait ceiling (Player's Guide pp.258-259).

An elder Exalt is not a splat and not an origin: it is an axis on a character already
built, the same way Thaumaturgy is a capability layer rather than a character type. All
it does is raise ceilings, so it is one small calculation with one entry point,
`elder_caps`, following the containment shape decision 0011 set for Merits & Flaws.

The rule, in the order it actually resolves (p.258, "Essence and Maximums"):

  1. AGE alone lets permanent Essence pass 5, per the chart on p.259 — 100 years for
     Essence 6, 250 for 7, 500 for 8, 1,000 for 9.
  2. ESSENCE in turn is the ceiling on Abilities and Attributes: "Abilities and
     Attributes may not be raised above the level of the character's permanent Essence
     through the use of experience points."
  3. "Exalted cannot raise their Virtues above 5" — no elder exception, ever.

Two rulings from the human (rules authority, 2026-07-31), because the printed text is
ambiguous and this build never guesses:

  * Rule 2 binds ONLY ABOVE 5. Read literally it would cap an Essence 2 Solar's Melee
    at 2, which is nonsense at any age — so the ceiling is `max(5, Essence)`, i.e. it
    never LOWERS the ordinary maximum, it only follows Essence upward past it.
  * AGE IS NOT A CHARGEN CHOICE. A character may never leave creation with Essence
    above 5 (see validate's `essence-above-elder-chargen-cap`), so nothing here can
    bind before the lock. `Character.age` is post-lock-editable and greyed until then.

Training times are the one part of p.258 deliberately absent. The page calculates them
"using the same formulas as is usual for that Exalt type" and gates the elder ceilings
behind them; this build does not model the passage of in-game time (CLAUDE.md), so the
age chart is the whole gate here. That is a known, accepted incompleteness.

NOT modelled, for want of a rule rather than by choice: what a character does with the
downtime experience of p.259. The annual awards and their 4:3:2:1 split are a
Storyteller's downtime bookkeeping across skipped decades, not a sheet calculation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.character import Character
from ..models.rules import RuleSet

# The ordinary ceiling on any rated trait, and the floor under every elder ceiling —
# `_DOT_MAX` in engine.advancement, which is where the rest of the build reads it.
DOT_MAX = 5

# p.259's chart, richest row first so the first match wins. "Age" is years of EXALTED
# existence, not years lived. The printed max for 1,000 years is "9+"; it ships as a
# flat 9 because the build never invents a number the page does not give, and the "+"
# names no value. A character who should exceed it is the Storyteller's business.
_AGE_TABLE: tuple[tuple[int, int], ...] = (
    (1000, 9),
    (500, 8),
    (250, 7),
    (100, 6),
)

# p.258: "Terrestrial Exalts may never raise their permanent Essence above 7 without
# resorting to the use of outside energies". None of those energies is on the sheet, so
# the escape is an ST toggle — HouseRules.terrestrial_essence_transcendence.
_TERRESTRIAL_CAP = 7

# The value of ExaltDefinition.tier the clause above applies to. Matched on the tier,
# never on a splat id: a second Terrestrial splat must inherit this without a code edit.
_TERRESTRIAL_TIER = "Terrestrial"


@dataclass(frozen=True)
class ElderCaps:
    """What age has unlocked for one character. Both fields are floored at `DOT_MAX`,
    so a young character gets the ordinary ceilings and no caller needs to special-case
    the elder rules out."""

    # Ceiling on permanent Essence from AGE alone. Splat and Merit ceilings are
    # narrower and are applied by the caller (engine.advancement.raise_essence), which
    # already owns both — this object must not duplicate that logic.
    essence: int

    # Ceiling on any one Ability or Attribute: `max(5, permanent Essence)`. Reads the
    # character's CURRENT Essence, not `essence`, because it is the rating actually
    # bought that lifts traits, not the rating age would permit.
    trait: int

    # True when `essence` is the Terrestrial 7 holding the character below what age
    # alone would have allowed — the one case where the ST can lift the ceiling by
    # granting HouseRules.terrestrial_essence_transcendence. Exists so the error the
    # player sees names the rule that actually stopped them, rather than their age.
    terrestrial_limited: bool = False

    @property
    def is_elder(self) -> bool:
        """True once age has moved anything — the UI's cue to show the elder ceilings
        at all, so an ordinary character's sheet is unchanged."""
        return self.essence > DOT_MAX or self.trait > DOT_MAX


def essence_cap_for_age(age: int) -> int:
    """The p.259 chart: years of Exalted existence → the highest permanent Essence age
    permits. `DOT_MAX` below 100 years, which is every ordinary character."""
    for years, cap in _AGE_TABLE:
        if age >= years:
            return cap
    return DOT_MAX


def elder_caps(ruleset: RuleSet, character: Character) -> ElderCaps:
    """The one entry point. Safe on any character: age 0 returns the ordinary 5/5."""
    essence = essence_cap_for_age(character.age)
    terrestrial_limited = False

    # The Terrestrial clause. Applied after the age chart rather than inside it because
    # it is a ceiling on the RESULT — a 1,000-year-old Dragon-Blood is held at 7, not
    # advanced to 9 and then clipped by a different rule elsewhere.
    if ruleset.exalt_for(character.exalt_type).tier == _TERRESTRIAL_TIER:
        hr = character.house_rules
        if not (hr and hr.terrestrial_essence_transcendence) and essence > _TERRESTRIAL_CAP:
            essence = _TERRESTRIAL_CAP
            terrestrial_limited = True

    return ElderCaps(
        essence=essence,
        trait=max(DOT_MAX, character.essence_rating),
        terrestrial_limited=terrestrial_limited,
    )
