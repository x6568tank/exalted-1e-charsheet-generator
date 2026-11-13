"""
engine/elder.py — Essence and trait ceilings, and the p.259 downtime calculator.

Player's Guide pp.258-259, as the human ruled. Essence is XP-purchasable. There is
no age chart:

  1. ESSENCE is the ceiling on Abilities and Attributes bought with XP. It binds only
     ABOVE 5: the ceiling is `max(5, Essence)`. `trait_ceiling` is the one read site.
  2. `ExaltDefinition.essence_cap` caps permanent Essence (0 = no printed cap). A
     Terrestrial is held at 7 (p.258) without the ST toggle. `essence_cap` is the one
     read site. `advancement.raise_essence` applies a Merit `essence_cap_override`.
  3. "Exalted cannot raise their Virtues above 5" — no exception.

`downtime_award` is a CALCULATOR for the p.259 downtime awards, not an enforcement: it
totals the XP for skipped years and reports the 4:3:2:1 split. It takes an AGE input
(human's ruling). There is no `Character.age`. The split is not enforced on purchases
(human's ruling).

Training times are out of scope (CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.character import Character
from ..models.rules import RuleSet

# The ordinary ceiling on a rated trait, and the floor of each higher ceiling.
DOT_MAX = 5

# The Essence ceiling for a splat with no printed cap (`essence_cap` 0): the p.258
# chart maximum ("9+").
_ESSENCE_MAX = 9

# p.259, third column: XP per year of downtime, by age band. The chart starts at 100.
# Below 100 this calculator awards 0. Play XP is separate.
_ANNUAL_XP_TABLE: tuple[tuple[int, int], ...] = (
    (1000, 2),
    (500, 3),
    (250, 4),
    (100, 5),
)

# p.259: the 4:3:2:1 split, in the page's order and with the page's labels.
_SPLIT_RATIO: tuple[tuple[str, int], ...] = (
    ("Charms and Combos", 4),
    ("Abilities", 3),
    ("Attributes and Virtues", 2),
    ("Essence", 1),
)

# p.258: the Terrestrial hold. The ST toggle is
# HouseRules.terrestrial_essence_transcendence.
_TERRESTRIAL_CAP = 7

# The ExaltDefinition.tier of the hold. ⚠ Match the tier, never a splat id.
_TERRESTRIAL_TIER = "Terrestrial"


def trait_ceiling(character: Character, ruleset: RuleSet | None = None,
                  domain: str = "ability") -> int:
    """Return the ceiling of one Ability or Attribute: `max(5, permanent Essence)`
    (p.258). Reads the CURRENT Essence. The one read site.

    The origin `ChargenBudgets.attribute_cap` / `ability_cap` (CH6 p.230) wins if
    set. ⚠ Without `ruleset` the override is missing."""
    if ruleset is not None:
        b = ruleset.budgets_for(character.exalt_type, character.origin,
                                character.upbringing)
        override = b.attribute_cap if domain == "attribute" else b.ability_cap
        if override:
            return override
    return max(DOT_MAX, character.essence_rating)


def essence_cap(ruleset: RuleSet, character: Character) -> tuple[int, bool]:
    """Return `(cap, terrestrial_limited)`: the permanent-Essence ceiling.

    `ExaltDefinition.essence_cap` (0 gives `_ESSENCE_MAX`), then the p.258
    Terrestrial-7 hold unless `HouseRules.terrestrial_essence_transcendence` is set.
    `terrestrial_limited` is True if the hold is the binding limit. The caller
    (advancement.raise_essence) applies a Merit `essence_cap_override`."""
    ex = ruleset.exalt_for(character.exalt_type)
    cap = ex.essence_cap or _ESSENCE_MAX
    # The origin ceiling overrides the splat value (CH6 p.230).
    origin_cap = (ruleset.budgets_for(character.exalt_type, character.origin,
                                      character.upbringing).essence_cap)
    if origin_cap:
        cap = origin_cap
    if ex.tier == _TERRESTRIAL_TIER:
        hr = character.house_rules
        if not (hr and hr.terrestrial_essence_transcendence) and cap > _TERRESTRIAL_CAP:
            return _TERRESTRIAL_CAP, True
    return cap, False


@dataclass(frozen=True)
class DowntimeBand:
    """One part of a downtime in one age band, for display."""

    from_age: int
    to_age: int          # inclusive
    rate: int            # experience per year in this band
    years: int

    @property
    def experience(self) -> int:
        return self.rate * self.years


@dataclass(frozen=True)
class DowntimeAward:
    """The p.259 XP for skipped years, and its split. Advice, not enforcement."""

    from_age: int
    to_age: int
    total: int
    bands: tuple[DowntimeBand, ...]
    split: tuple[tuple[str, int], ...]

    # No `years` property: nothing reads it.


def annual_xp_for_age(age: int) -> int:
    """Return the p.259 XP per year of downtime at `age`. 0 below 100."""
    for years, xp in _ANNUAL_XP_TABLE:
        if age >= years:
            return xp
    return 0


def split_downtime_experience(total: int) -> tuple[tuple[str, int], ...]:
    """Return the 4:3:2:1 split of `total`. Each part is floored. The remainder goes
    to the largest category (not from the page), thus the parts sum to `total`."""
    if total <= 0:
        return tuple((label, 0) for label, _ in _SPLIT_RATIO)
    shares = sum(weight for _, weight in _SPLIT_RATIO)
    parts = [(label, total * weight // shares) for label, weight in _SPLIT_RATIO]
    remainder = total - sum(p for _, p in parts)
    if remainder:
        label, first = parts[0]
        parts[0] = (label, first + remainder)
    return tuple(parts)


def downtime_award(from_age: int, years: int) -> DowntimeAward:
    """Return the XP for `years` of downtime from `from_age`.

    Calculated year by year against the age bands (human's ruling): the rate changes
    at 100, 250, 500 and 1,000. The rate of a year is the rate of the age reached in
    that year.
    """
    from_age = max(0, from_age)
    years = max(0, years)
    bands: list[DowntimeBand] = []
    total = 0
    for year in range(years):
        age = from_age + year + 1
        rate = annual_xp_for_age(age)
        total += rate
        # Merge consecutive years at the same rate into one row.
        if bands and bands[-1].rate == rate:
            last = bands[-1]
            bands[-1] = DowntimeBand(last.from_age, age, rate, last.years + 1)
        else:
            bands.append(DowntimeBand(age, age, rate, 1))
    return DowntimeAward(from_age=from_age, to_age=from_age + years, total=total,
                         bands=tuple(bands), split=split_downtime_experience(total))
