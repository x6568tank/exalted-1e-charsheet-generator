"""
engine/merits.py — the ONE place Merits & Flaws have mechanical effects.

Merits & Flaws were removed in June 2026 because the old implementation scattered
their effects across every file they touched: a Merit that changed a Charm's cost
edited the cost code, one that granted a pool edited the derivation, and there was no
way to see what any of it did without grepping the tree. **Decision 0011** is that
they come back as a single calculation, and this module is it.

The contract, and the thing to preserve:

  * `rules.MeritFlaw` is INERT DATA — printed text, cost, prerequisites. It says
    nothing about what a Merit does. A Merit with no mechanical effect (most of them)
    needs a data row and nothing else.
  * `merits_and_flaws_calc` maps the Merits a character HOLDS to a `MeritEffects`
    value object. It is the only function that knows any Merit's id.
  * Everything else — validate, derive, costs, advancement, the UI — reads
    `MeritEffects` fields. **No caller anywhere may branch on a Merit id.** If a new
    Merit needs an effect the object cannot express, add a FIELD here; do not add a
    lookup there. That rule is what stops the June situation recurring.

`MeritEffects` is keyed by EFFECT, not by Merit taxonomy, deliberately: the general
M&F chapter is a much broader set (social, physical, supernatural) and will attach new
Merits to existing effects far more often than it invents new ones.

Source: Player's Guide pp.120-122 (the Thaumaturgy Merits). These were authored first
because they are the mortal magic-access set — see docs/status/merits-flaws.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.character import Character
from ..models.rules import MeritFlaw, RuleSet, SpellCircle

# --------------------------------------------------------------------------- #
# The ids this module knows. Nothing outside engine/merits.py may name these.
# --------------------------------------------------------------------------- #

# "Characters may only receive up to 10 extra bonus points from Flaws, regardless of
# the number taken" (PG p.16). The same ceiling governs experience after creation:
# "Characters with more than 10 points of Flaws receive no experience for the excess"
# (p.17). One constant for both.
FLAW_POINT_CAP = 10

ESSENCE_AWARENESS = "thaum.essence-awareness"
ESSENCE_MASTERY = "thaum.essence-mastery"
OATHBOUND_MAGIC = "thaum.oathbound-magic"
HOLY_MIEN = "thaum.holy-mien"
# Holy Mien "grants the character possessing it the Priest Merit at the one-point level
# at no extra cost and reduces the cost of the seven-point level to six bonus points"
# (PG p.121). Priest itself is in the general chapter (p.24), which is why this could
# not be wired until that landed.
PRIEST = "mf.priest"

# Spirit Walking is the second Charm of the Immaculate enlightenment tree and is what
# grants access to CELESTIAL Martial Arts ("before a Dragon-Blooded may walk any Dragon
# Path, she must master this skill"). A mortal can never reach those, so Essence
# Mastery's grant of Terrestrial Martial Arts stops short of it — human, rules
# authority, 2026-07-30, and confirmed as "just the one Charm": its prerequisite,
# Spirit Sight, is legal and simply dead-ends.
#
# The existing tier machinery does NOT catch this: Spirit Walking is `open_to_all`, so
# any splat able to reach Terrestrial MA at all would otherwise be handed it.
SPIRIT_WALKING = "dragonblooded.martial-arts.spirit-walking"


@dataclass(frozen=True)
class MeritEffects:
    """What a character's Merits and Flaws do, as data.

    Every field is a NEUTRAL default for a character holding no Merits, so callers can
    use the result unconditionally rather than testing for its absence.
    """

    # --- Essence ----------------------------------------------------------- #
    # Does the character have access to an Essence pool at all? Mortals have none
    # ("they lack an Essence pool, either Peripheral or Personal", PG p.114) until
    # Essence Awareness unlocks part of it. True for every Exalt, always.
    essence_pool_unlocked: bool = False
    # Is that access UNRESTRICTED? Essence Awareness gives a third of the pool freely
    # and the rest on a Willpower roll; Essence Mastery removes the restriction
    # entirely. We do not roll dice (decision 0009), so the split is narrative and
    # only the distinction between "some access" and "full access" is modelled.
    essence_pool_unrestricted: bool = False
    # Raises ExaltDefinition.essence_cap when set. Essence Mastery is what lets a
    # mortal exceed Essence 1 at all, and 3 is "the limit of human potential —
    # mortals that exceed Essence 3 become gods" (PG p.114). None = no override.
    essence_cap_override: int | None = None

    # --- Magic access ------------------------------------------------------ #
    # Charm categories opened to a character whose splat is otherwise Charmless, and
    # the individual Charms still withheld inside them. Both are consulted by
    # validate.charm_matches_splat; `barred_charm_ids` wins over `open_charm_categories`.
    open_charm_categories: frozenset[str] = frozenset()
    barred_charm_ids: frozenset[str] = frozenset()
    # Withhold the Immaculate Order Charms (the five elemental Dragon styles) from
    # within an opened category. A CLASS of Charms rather than a list of ids, so it
    # is its own flag: Essence Mastery opens Terrestrial Martial Arts, but the
    # Immaculate Dragon Paths are closed to mortals (human, rules authority,
    # 2026-07-30). Consistent with barring Spirit Walking — the Dragon Paths are
    # exactly what Spirit Walking exists to unlock.
    bar_immaculate_charms: bool = False
    # Spell circles granted outright, without the initiating Charm the engine normally
    # requires. Mortals cannot hold Charms, so a Merit-granted circle is the only way
    # they reach sorcery at all.
    granted_circles: frozenset[SpellCircle] = frozenset()

    # --- Points ------------------------------------------------------------ #
    # Bonus points ADDED to the chargen allowance by Flaws, net of Oathbound Magic's
    # same-arena stacking reduction and CLAMPED to FLAW_POINT_CAP.
    bonus_point_grant: int = 0
    # What the Flaws would have granted before the cap, so the UI can say "10 of 13"
    # rather than silently swallowing three points the player thinks they have.
    flaw_points_raw: int = 0

    # --- Cross-Merit effects ----------------------------------------------- #
    # Merits held FREE because another Merit grants them (Holy Mien -> Priest at the
    # one-point level). The character has them whether or not they appear on the
    # sheet, so the UI shows them as granted rather than purchased.
    granted_merits: frozenset[str] = frozenset()
    # Price overrides another Merit imposes, {merit_id: {tier: points}}. Holy Mien
    # drops Priest's seven-point level to six. Consulted by validate.merit_points
    # before any of the entry's own cost shapes.
    merit_cost_overrides: dict[str, dict[str, int]] = field(default_factory=dict)

    # --- Bookkeeping ------------------------------------------------------- #
    # Ids that produced no effect, for the UI to explain rather than silently ignore.
    narrative_only: tuple[str, ...] = ()


def _held(ruleset: RuleSet, character: Character) -> list[tuple[MeritFlaw, object]]:
    """(definition, purchase) for every Merit the character holds that resolves in the
    RuleSet. An unresolvable id is skipped here and reported by validate, matching how
    unknown Charm ids are handled — graceful, never a crash."""
    out = []
    for purchase in character.merits_flaws:
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is not None:
            out.append((definition, purchase))
    return out


def oathbound_bonus_points(character: Character, ruleset: RuleSet) -> int:
    """Bonus points granted by Oathbound Magic, net of the stacking rule.

    PG p.122: "Oaths in a particular area … can be stacked, but each stacked oath past
    the first is reduced in value by the total number of oaths. So, a pair of oaths to
    never initiate violence and to use no bladed weapon would be worth five bonus
    points, rather than six (3 + 3, -1 for an additional oath in the same arena)."

    Read literally against the worked example: within one arena, every oath past the
    first loses (number of oaths in that arena − 1) points. Two oaths → the second
    loses 1 → 3 + 2 = 5. ✓  The reduction floors at zero rather than going negative;
    the page does not contemplate an oath of negative worth.

    Oaths in DIFFERENT arenas do not interact, which is the point of tracking `arena`.
    Purchases with a blank arena are each treated as their own — the conservative
    reading, since the page's reduction only ever applies "in a particular area".
    """
    by_arena: dict[str, list[int]] = {}
    for definition, purchase in _held(ruleset, character):
        if definition.id != OATHBOUND_MAGIC:
            continue
        value = definition.cost_options.get(purchase.tier, 0)
        key = purchase.arena or f"\0{id(purchase)}"      # blank arena = its own bucket
        by_arena.setdefault(key, []).append(value)

    total = 0
    for values in by_arena.values():
        penalty = len(values) - 1                       # 0 for a lone oath
        # Highest-value oath keeps its full worth; the page's example reduces the
        # *additional* oaths, so sort descending and charge the penalty to the rest.
        for i, value in enumerate(sorted(values, reverse=True)):
            total += value if i == 0 else max(0, value - penalty)
    return total


def flaw_points(ruleset: RuleSet, character: Character) -> int:
    """Total bonus points the character's FLAWS are worth, before the cap.

    Every Flaw grants its printed value — "Flaws work in reverse, imposing
    disadvantages in exchange for additional bonus points" (PG p.16) — so this is not
    special to Oathbound Magic; Oathbound is merely the one whose value varies and
    whose same-arena oaths reduce each other, which `oathbound_bonus_points` handles.

    NOTE Oathbound's points ARE counted toward the cap. The page says "regardless of
    the number taken", and an oath is a Flaw. Its own rule that oath points "must be
    tied to the Traits purchased using them" — i.e. they are earmarked rather than
    fungible — is NOT modelled: this build has a single bonus-point pool. Flagged in
    docs/status/merits-flaws.md rather than guessed at.
    """
    total = oathbound_bonus_points(character, ruleset)
    for definition, purchase in _held(ruleset, character):
        from .validate import effective_merit_kind, merit_points   # validate imports merits
        if definition.id == OATHBOUND_MAGIC:
            continue
        if effective_merit_kind(definition, purchase) != "flaw":
            continue
        total += merit_points(definition, purchase, character.exalt_type,
                              character.caste)
    return total


def merits_and_flaws_calc(ruleset: RuleSet, character: Character) -> MeritEffects:
    """The single M&F calculation. See the module docstring for why it is the only one.

    Baseline: a character whose splat HAS an Essence pool already has one — Merits only
    ever add. `ExaltDefinition.essence.personal_essence_coeff` being all-zero is how a
    Charmless, poolless splat is expressed (mortals), so that is what "needs unlocking"
    means, rather than a hardcoded check for the Mortal splat.
    """
    exalt = ruleset.exalt_for(character.exalt_type)
    has_native_pool = bool(exalt.essence.personal_essence_coeff
                           or exalt.essence.personal_willpower_coeff)
    raw_flaw_points = flaw_points(ruleset, character)

    held_ids = {d.id for d, _p in _held(ruleset, character)}
    effects_from: set[str] = set()

    # --- Essence Awareness / Mastery --------------------------------------- #
    awareness = ESSENCE_AWARENESS in held_ids
    mastery = ESSENCE_MASTERY in held_ids
    if awareness or mastery:
        effects_from.update({ESSENCE_AWARENESS, ESSENCE_MASTERY} & held_ids)

    open_categories: frozenset[str] = frozenset()
    barred: frozenset[str] = frozenset()
    circles: frozenset[SpellCircle] = frozenset()
    cap_override: int | None = None
    bar_immaculate = False

    if mastery:
        # "sufficient Essence to … practice Terrestrial Martial Arts" (PG p.121),
        # minus the one Charm that would open the Celestial styles.
        open_categories = frozenset({"martial_arts"})
        barred = frozenset({SPIRIT_WALKING})
        bar_immaculate = True
        # Terrestrial circle only — a mortal never reaches Celestial sorcery
        # (human, rules authority, 2026-07-30).
        circles = frozenset({SpellCircle.TERRESTRIAL})
        # Only meaningful where the splat is capped below 3 to begin with; an Exalt's
        # cap is 0 (uncapped) and must not be LOWERED to 3 by holding this Merit.
        if exalt.essence_cap and exalt.essence_cap < 3:
            cap_override = 3

    # Holy Mien's grant, expressed as effects rather than a branch in the cost code.
    granted_merits: frozenset[str] = frozenset()
    cost_overrides: dict[str, dict[str, int]] = {}
    if HOLY_MIEN in held_ids and PRIEST in ruleset.merits_flaws:
        granted_merits = frozenset({PRIEST})
        cost_overrides = {PRIEST: {"1": 0, "7": 6}}
        effects_from.add(HOLY_MIEN)

    return MeritEffects(
        granted_merits=granted_merits,
        merit_cost_overrides=cost_overrides,
        essence_pool_unlocked=has_native_pool or awareness or mastery,
        essence_pool_unrestricted=has_native_pool or mastery,
        essence_cap_override=cap_override,
        open_charm_categories=open_categories,
        barred_charm_ids=barred,
        bar_immaculate_charms=bar_immaculate,
        granted_circles=circles,
        bonus_point_grant=min(raw_flaw_points, FLAW_POINT_CAP),
        flaw_points_raw=raw_flaw_points,
        narrative_only=tuple(sorted(
            held_ids - effects_from - {OATHBOUND_MAGIC})),
    )
