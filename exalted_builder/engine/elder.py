"""
engine/elder.py — Essence and trait ceilings, and the p.259 downtime calculator.

Human ruling 2026-08-06 (simplifying the shipped elder-age axis): Essence is
XP-purchasable, and the age-chart gate is gone. What survives of Player's Guide
pp.258-259:

  1. ESSENCE is the ceiling on Abilities and Attributes: "Abilities and Attributes
     may not be raised above the level of the character's permanent Essence through
     the use of experience points." Read (as ever) as binding only ABOVE 5 — the
     ceiling is `max(5, Essence)`, so it never lowers the ordinary maximum, it only
     follows Essence upward past it. `trait_ceiling` is the one read site.
  2. A splat's permanent Essence is capped by its own `ExaltDefinition.essence_cap`
     (0 = no printed cap; the six Exalts set 9, the p.258 chart's printed max), and
     the p.258 Terrestrial-7 hold caps a Terrestrial at 7 without the ST's "outside
     energies". `essence_cap` is the one read site; a Merit's `essence_cap_override`
     is applied by `advancement.raise_essence`, which owns the Merit read.
  3. "Exalted cannot raise their Virtues above 5" — no exception, ever.

The p.259 downtime awards stay, as of 2026-08-01 — a CALCULATOR (`downtime_award`),
not an enforcement: it totals the annual experience for a stretch of skipped years and
reports the 4:3:2:1 split the page mandates; granting it and policing how it is spent
stay the Storyteller's. The chart is keyed on years of Exalted existence, so the
calculator takes an AGE INPUT — but it is a pure calculator field (human ruling
2026-08-06); there is no `Character.age` and age gates nothing. Earmarking ledger rows
by category was considered and rejected (human's call): it would touch every purchase
in the build to enforce a rule the page itself frames as an injunction to
Storytellers.

Training times are the one part of p.258 deliberately absent, unchanged from before:
this build does not model the passage of in-game time (CLAUDE.md).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.character import Character
from ..models.rules import RuleSet

# The ordinary ceiling on any rated trait, and the floor under every higher ceiling —
# `_DOT_MAX` in engine.advancement, which is where the rest of the build reads it.
DOT_MAX = 5

# The flat permanent-Essence ceiling for a splat with no printed cap (`essence_cap`
# 0 in the data). This is the p.258 chart's printed max ("9+" for 1,000 years) taken
# as a flat number once the age chart is gone — the build never invents a value the
# page does not give, and a character who should exceed it is the Storyteller's
# business. The six Exalts set `essence_cap` to this.
_ESSENCE_MAX = 9

# The third column of the SAME p.259 chart: experience per year of downtime, by the age
# band the character is in. It falls as the character ages — an old Exalt learns less
# from another quiet year than a young one does.
#
# The chart starts at 100. Below that it prints NOTHING, and this build does not invent
# a number the page does not give, so a year lived under 100 years of Exaltation awards
# zero here. That is a floor on what this calculator claims, not a claim that a young
# Exalt learns nothing: ordinary play XP is the rest, and the Storyteller grants it.
_ANNUAL_XP_TABLE: tuple[tuple[int, int], ...] = (
    (1000, 2),
    (500, 3),
    (250, 4),
    (100, 5),
)

# "broken down according to a 4:3:2:1 ratio among categories of Charms and Combos,
# Abilities, Attributes and Virtues, and Essence" (p.259). Order is the page's, and the
# labels are the page's own groupings — Attributes and Virtues share one share.
_SPLIT_RATIO: tuple[tuple[str, int], ...] = (
    ("Charms and Combos", 4),
    ("Abilities", 3),
    ("Attributes and Virtues", 2),
    ("Essence", 1),
)

# p.258: "Terrestrial Exalts may never raise their permanent Essence above 7 without
# resorting to the use of outside energies". None of those energies is on the sheet, so
# the escape is an ST toggle — HouseRules.terrestrial_essence_transcendence.
_TERRESTRIAL_CAP = 7

# The value of ExaltDefinition.tier the clause above applies to. Matched on the tier,
# never on a splat id: a second Terrestrial splat must inherit this without a code edit.
_TERRESTRIAL_TIER = "Terrestrial"


def trait_ceiling(character: Character) -> int:
    """Ceiling on any one Ability or Attribute: `max(5, permanent Essence)` (p.258
    "Essence and Maximums", read as binding only above 5). Reads the character's
    CURRENT Essence, so a splat that can raise Essence past 5 — every Exalt to 9, a
    Dragon King to 6 — lifts its traits the same way. The one read site; every raise
    and every dot-track ceiling goes through it."""
    return max(DOT_MAX, character.essence_rating)


def essence_cap(ruleset: RuleSet, character: Character) -> tuple[int, bool]:
    """`(cap, terrestrial_limited)` — the permanent-Essence ceiling for the whole of
    the character's life: the splat's `ExaltDefinition.essence_cap` (0 = no printed
    cap, so `_ESSENCE_MAX`), then the p.258 Terrestrial-7 hold — "Terrestrial Exalts
    may never raise their permanent Essence above 7 without outside energies" — unless
    the ST lifts it via `HouseRules.terrestrial_essence_transcendence`. `terrestrial_
    limited` is True exactly when that hold is the binding constraint, so the error the
    player sees can name the rule that stopped them. A Merit's `essence_cap_override`
    is applied by the caller (advancement.raise_essence), which owns the Merit read."""
    ex = ruleset.exalt_for(character.exalt_type)
    cap = ex.essence_cap or _ESSENCE_MAX
    if ex.tier == _TERRESTRIAL_TIER:
        hr = character.house_rules
        if not (hr and hr.terrestrial_essence_transcendence) and cap > _TERRESTRIAL_CAP:
            return _TERRESTRIAL_CAP, True
    return cap, False


@dataclass(frozen=True)
class DowntimeBand:
    """One stretch of a downtime spent inside a single age band — the working shown, so
    a Storyteller can see WHY 40 years paid 150 and not 200."""

    from_age: int
    to_age: int          # inclusive
    rate: int            # experience per year in this band
    years: int

    @property
    def experience(self) -> int:
        return self.rate * self.years


@dataclass(frozen=True)
class DowntimeAward:
    """The p.259 annual experience for a stretch of skipped years, and the split it must
    be spent across. ADVICE, not enforcement: nothing in this build refuses a purchase
    for overrunning a category, because the page frames the split as an injunction to
    Storytellers and earmarking every ledger row would touch the whole advancement
    system to police it."""

    from_age: int
    to_age: int
    total: int
    bands: tuple[DowntimeBand, ...]
    split: tuple[tuple[str, int], ...]

    # No `years` property. `to_age - from_age` is the span and the UI prints both ends;
    # a derived field nothing reads is this build's most-repeated bug, and the audit
    # script cannot see it here because these field names are too generic to grep.


def annual_xp_for_age(age: int) -> int:
    """p.259's third column: experience awarded per year of downtime at this age. Zero
    below 100 years, which is where the chart begins — see `_ANNUAL_XP_TABLE`."""
    for years, xp in _ANNUAL_XP_TABLE:
        if age >= years:
            return xp
    return 0


def split_downtime_experience(total: int) -> tuple[tuple[str, int], ...]:
    """The 4:3:2:1 split. The page's shortcut is "divide the lump sum by 10 and then
    multiply by 4, 3, 2 and 1", which only divides cleanly on a multiple of 10 — so the
    parts are floored and the remainder goes to the largest category. That last step is
    OURS, not the page's; it exists so the four numbers always sum back to the lump
    rather than quietly losing experience the Storyteller granted."""
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
    """Total the annual experience for `years` of downtime beginning at `from_age`.

    Walked YEAR BY YEAR against the age bands rather than applied as one flat rate
    (human's ruling, 2026-08-01): a downtime that crosses 100, 250, 500 or 1,000 changes
    rate partway, and the page describes the award as "a year-by-year stream of
    individual incidents". A flat rate at either end of the stretch would over- or
    under-pay a character who spent most of it in the other band.

    The rate for a given year is the one for the age REACHED in that year, so the year a
    character turns 100 is the first that pays 5.
    """
    from_age = max(0, from_age)
    years = max(0, years)
    bands: list[DowntimeBand] = []
    total = 0
    for year in range(years):
        age = from_age + year + 1
        rate = annual_xp_for_age(age)
        total += rate
        # Coalesce consecutive years at the same rate into one row — a 400-year downtime
        # must not print 400 lines to say it crossed two bands.
        if bands and bands[-1].rate == rate:
            last = bands[-1]
            bands[-1] = DowntimeBand(last.from_age, age, rate, last.years + 1)
        else:
            bands.append(DowntimeBand(age, age, rate, 1))
    return DowntimeAward(from_age=from_age, to_age=from_age + years, total=total,
                         bands=tuple(bands), split=split_downtime_experience(total))
