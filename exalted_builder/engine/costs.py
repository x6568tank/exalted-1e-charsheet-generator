"""
engine/costs.py — experience-point cost of a single post-lock advance (pure).

Every number comes from RuleSet.xp_costs (ExperienceCosts), never hardcoded, so
correcting the table corrects the engine. The scaled traits cost
`current rating × N` — you pay on the rating you are *leaving* (the 1e advancement
table; see CLAUDE.md), so each function takes `from_rating`. New Charms, spells and
specialties are flat; a new Combo costs the sum of its member Charms' minimum
Ability values (core p.213).

These are pure `(RuleSet, …) -> int` functions: the advancement transitions in
engine.advancement call them, and the UI shows them as a price before buying.
"""

from __future__ import annotations

from typing import Optional

from ..models.character import Character, MeritFlawPurchase
from ..models.rules import AbilityName, AttributeName, Charm, RuleSet, VirtueName
from . import merits, paths, validate

# A trait's first dot (an Ability bought from 0) has no `from_rating` to scale; it
# is the flat new_ability cost. Attributes/Virtues never start below 1, so they are
# always scaled.


def attribute_step(ruleset: RuleSet, character: Character, from_rating: int,
                   attr: AttributeName | None = None) -> int:
    """XP to raise an Attribute one dot. Two independent discount axes, checked in
    order because a caste_favored-mode splat also has `caste_attributes` populated:

    * caste_favored mode (Alchemical, p.64) — a Caste- or Favored-Attribute takes the
      `attribute_favored_caste` rate, matching a SPECIFIC Attribute.
    * Caste Attributes (Lunar, p.251 — `(x4)-1`) — the `attribute_caste_favored` rate.

    Every other splat (and every non-favored Attribute) pays the flat rate. `attr` is
    optional so call sites that don't pass it keep the flat rate — correct for them,
    since only these two splats override the Attribute rate at all."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if attr is not None:
        if attr in validate._caste_favored_attr_names(ruleset, character):
            return xp.attribute_favored_caste.at(from_rating)
        if attr in validate.caste_attributes(ruleset, character):
            return xp.attribute_caste_favored.at(from_rating)
    return xp.attribute.at(from_rating)


def ability_step(ruleset: RuleSet, character: Character, ability: AbilityName,
                 from_rating: int) -> int:
    """XP to raise an Ability one dot. Going 0 -> 1 is the flat 'new ability' cost;
    above that it scales, with the Caste/Favoured discount when applicable."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if ability == AbilityName.CRAFT and xp.craft is not None:
        # Superior Craftsmanship (Mountain Folk, CH6 p.237): Craft Abilities and
        # specialties cost HALF the usual experience (rounded up), and the discount
        # "supersedes and replaces the normal discount awarded to Favored Abilities"
        # — so the favored rate does not apply on top. The initial purchase is half
        # of the flat new-ability cost (3 → 2).
        if from_rating <= 0:
            return max(1, (xp.new_ability + 1) // 2)
        total = xp.craft.at(from_rating)
    elif from_rating <= 0:
        return xp.new_ability
    else:
        favored = ability in validate.caste_favored_abilities(ruleset, character)
        cost = xp.ability_favored_caste if favored else xp.ability
        total = cost.at(from_rating)
    # A Calling Ability is 1 XP cheaper, and the page is explicit that this "stacks
    # with the benefit of Favored or Caste Abilities" (p.102) — hence a subtraction
    # applied after the rate, not a third rate. 0 for every splat without Callings.
    if ability in validate.calling_abilities(ruleset, character):
        total -= xp.calling_ability_discount
    # Prodigy's "increased aptitude": "(current rating x 2) - 2". Another subtraction
    # after the rate, so it stacks with the two above exactly as the Calling discount
    # does — and, like it, only ever reduces. Read as a field, never by Merit id.
    total -= merits.merits_and_flaws_calc(ruleset, character).ability_xp_discount.get(
        ability.value, 0)
    return max(0, total)


def virtue_step(ruleset: RuleSet, character: Character, from_rating: int,
                virtue: Optional[VirtueName] = None) -> int:
    """XP to raise a Virtue one dot. (Does not raise Willpower — that is pinned at
    lock; see derive.willpower.)

    A Fae-Blooded's ATTUNED Virtue (Virtue Attunement, PG p.74) is priced "for a cost
    of ... (current rating x 2) experience points" instead of the splat's (current x 3).
    Which Virtues are attuned is the Merit effect (`MeritEffects.favored_virtues`,
    read by field, never by id); the x2 rate is the page's own, so it is stated here
    once rather than threaded through a second cost table."""
    if (virtue is not None
            and virtue.value in merits.merits_and_flaws_calc(
                ruleset, character).favored_virtues):
        return from_rating * 2
    return ruleset.xp_costs_for(character.exalt_type).virtue.at(from_rating)


def willpower_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise permanent Willpower one dot, scaled on the current rating."""
    return ruleset.xp_costs_for(character.exalt_type).willpower.at(from_rating)


def essence_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise Essence one dot, scaled on the current rating — unless the splat
    prices that step flat by destination (the mortal table, PG p.115), in which case
    the per-rating entry wins. See XpCosts.essence_by_rating."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    flat = xp.essence_by_rating.get(from_rating + 1)
    return flat if flat is not None else xp.essence.at(from_rating)


def merit_cost(ruleset: RuleSet, character: Character, merit, tier: str = "",
               *, taken_as: str = "", points: int = 0) -> int:
    """XP to buy a Merit after creation: its bonus-point value doubled (PG p.115,
    "New Merit (mystical only) | cost in bonus points x2").

    The bonus-point value is whatever `validate.merit_points` says it is, so the XP
    path and the chargen path can never disagree about a price. That matters for the
    shapes a bare `merit.cost` cannot express: a per-tier menu, a per-splat or
    per-caste rate, a variable cost agreed at the table (`points`), and a two-sided
    entry priced differently on each side (`taken_as` — Eternal Vow is 3 as a Merit
    and 1 as a Flaw, and reading `merit.cost` would price both at 0)."""
    bp = validate.merit_points(
        merit, MeritFlawPurchase(merit_id=merit.id, tier=tier, taken_as=taken_as,
                                 points=points),
        character.exalt_type, character.caste)
    return bp * ruleset.xp_costs_for(character.exalt_type).new_merit_bp_multiplier


def elemental_power_xp(ruleset: RuleSet, character: Character, power) -> int:
    """XP to learn an elemental power in play: its bonus-point value doubled (PG
    p.68, "learned in play for a number of experience points equal to double its
    bonus point value"). Deliberately priced through `bp_cost * new_merit_bp_multiplier`
    — the same "double BP" rule that prices post-lock Merits — NOT through the
    God-Blooded new-Charm rate: the page says double BP, and the powers' 7-BP value
    makes that 14, where the Charm rate would be 15."""
    return power.bp_cost * ruleset.xp_costs_for(character.exalt_type).new_merit_bp_multiplier


def specialty_cost(ruleset: RuleSet, character: Character,
                   ability: AbilityName | None = None) -> int:
    """XP for one new specialty dot (flat). A Mountain Folk Craft specialty costs 2
    (CH6 p.233) instead of the usual 3 — the Superior Craftsmanship half-price
    (p.237) — when the specialty's Ability is named as Craft; None keeps the
    ordinary rate for the display sites that do not know the Ability."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if ability == AbilityName.CRAFT and xp.craft_specialty:
        return xp.craft_specialty
    return xp.new_specialty


def college_new_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for a new Astrological College (Sidereal, p.265): flat new_college (5)."""
    return ruleset.xp_costs_for(character.exalt_type).new_college


def college_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise a College one dot, scaled on the current rating (p.265: ×3)."""
    return ruleset.xp_costs_for(character.exalt_type).college.at(from_rating)


def path_new_cost(ruleset: RuleSet, character: Character, path_id: str) -> int:
    """XP for a new Dragon-King Path at rating 1 (PG p.176): flat new_path (7), or
    new_path_breed (6) when the Path is one of the character's Breed or Favoured
    Paths (the breed's two element Paths plus the one the player chose)."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_path_breed if paths.path_is_favored(ruleset, character, path_id) \
        else xp.new_path


def path_step(ruleset: RuleSet, character: Character, path_id: str,
              from_rating: int) -> int:
    """XP to raise a Path one dot, scaled on the current rating (p.176: ×5, or ×4
    for a Breed/Favoured Path)."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    rate = xp.path_breed if paths.path_is_favored(ruleset, character, path_id) \
        else xp.path
    return rate.at(from_rating)


def _fighter_in_life_covers(ruleset: RuleSet, character: Character,
                            charm: Charm) -> bool:
    """Whether this Terrestrial Martial Arts Charm falls inside the character's Fighter
    in Life allowance (PG p.234).

    The Merit grants a COUNT, and the page does not say which Charms it applies to, so
    it covers the cheapest reading for the player: the first N such Charms bought. A
    Charm already held is counted, so buying the (N+1)th pays the penalty rate.

    No Merit id is named here (decision 0011) — the count is a `MeritEffects` field.
    Charms are counted through `validate.charm_picks`, never off `character.charms`.
    """
    picks = merits.merits_and_flaws_calc(ruleset, character).terrestrial_ma_picks
    if not picks:
        return False
    held = sum(1 for pick in validate.charm_picks(ruleset, character)
               if (c := ruleset.charms.get(pick.charm_id)) is not None
               and validate.is_terrestrial_martial_arts(c)
               and pick.charm_id != charm.id)
    return held < picks


def charm_cost(ruleset: RuleSet, character: Character, charm: Charm) -> int:
    """XP to learn a Charm: discounted when its gating Ability is Caste/Favoured
    (Ability-keyed Charms), or when its gating Attribute's category matches the
    caste's favored Attribute category (Lunar's Attribute-keyed Charms, p.122 —
    the same collision `validate._min_trait_rating` warns about: 'melee' is both
    a category string and a valid AbilityName, so a Lunar Melee Charm's discount
    must come from `min_attribute`, never from category-as-Ability).

    A Charm belonging to ANOTHER splat — reachable only through the Eclipse-style
    caste privilege (p.127) — then costs double ("usually 20 points"). The Caste/
    Favoured discount is applied FIRST and the multiplier last, per the rules
    authority's call: a foreign Charm gets full C/F treatment, then doubles."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    if charm.min_attribute:
        caste_attr_category = validate._caste_favored_attribute_category(ruleset, character)
        favored = validate._charm_attribute_caste_favored(charm, caste_attr_category)
    else:
        ability = validate._category_ability(charm.category)
        favored = ability is not None and ability in validate.caste_favored_abilities(ruleset, character)
    # A splat whose martial-arts access is the PG p.234 exception (ghosts) prices every
    # Terrestrial style off that page, and this branch comes first — ahead of the
    # Immaculate rate below, which is Dragon-Blooded's own (p.292) and has no meaning
    # for a ghost. ⚠ The ORDER is the rule: reversed, a ghost learning an Immaculate
    # Dragon Path is charged a DB rate its own cost row does not even author.
    if (ruleset.exalt_for(character.exalt_type).terrestrial_martial_arts
            and validate.is_terrestrial_martial_arts(charm)):
        if _fighter_in_life_covers(ruleset, character, charm):
            # "the cost of developing a regular Arcanos (14 experience points)".
            cost = xp.new_charm_favored_caste if favored else xp.new_charm
        else:
            # "the same cost per Charm that they would pay for inventing a new
            # Arcanos (20 experience points)" — the penalty every ghost otherwise pays.
            cost = (xp.new_martial_arts_charm
                    if xp.new_martial_arts_charm is not None else xp.new_charm)
    # Immaculate Order Charms (Dragon-Blooded) have their own, higher rate (p.292).
    elif validate.is_immaculate_charm(charm):
        cost = xp.new_immaculate_charm_favored_caste if favored else xp.new_immaculate_charm
    elif charm.category.startswith("martial_arts"):
        # Sidereal Martial Arts is a distinct rate (12/10, p.265); other splats leave
        # both MA fields None and fall back to the ordinary new_charm rate. For ghosts
        # it is the p.234 penalty rate (20) — see _fighter_in_life_covers above.
        if favored:
            cost = xp.new_martial_arts_charm_favored_caste
            if cost is None:
                cost = xp.new_charm_favored_caste
        else:
            cost = xp.new_martial_arts_charm if xp.new_martial_arts_charm is not None else xp.new_charm
    elif charm.grants_circle is not None and xp.new_magic_charm:
        # The sorcery/necromancy INITIATION Charms for the God-Blooded (p.49): 25 XP,
        # "regardless of whether the character favors the Trait", with training time
        # measured in weeks rather than days. Flat — no favoured variant is printed.
        # `new_magic_charm` 0 (every other splat) falls through to the ordinary rate.
        cost = xp.new_magic_charm
    elif xp.new_charm_cross_pattern and validate.mountain_folk_cross_pattern(
            ruleset, character, charm):
        # A Mountain Folk Charm of another caste's Pattern costs 12 XP (CH6 p.233:
        # "10 (12 if part of another Caste Pattern)"). Favoured never applies — no
        # Jadeborn Charm is Caste/Favoured (Patterns replace that axis).
        cost = xp.new_charm_cross_pattern
    else:
        cost = xp.new_charm_favored_caste if favored else xp.new_charm
    # A Calling Charm is 2 XP cheaper, stacking with Caste/Favoured (p.102): "a
    # Calling Charm costs 8 experience points, or 6 if Favored or Caste". Applied
    # BEFORE the foreign-Charm multiplier, consistent with the existing rule that the
    # discount lands first and the doubling last.
    if validate.is_calling_charm(ruleset, character, charm):
        cost = max(0, cost - xp.calling_charm_discount)
    # An Eclipse/Moonshadow learning another splat's Charm pays a multiple (p.90).
    caste = validate.foreign_charms_caste(ruleset, character)
    if caste is not None and validate.is_foreign_charm(ruleset, character, charm):
        cost *= caste.foreign_charm_xp_multiplier
    # A Merit may reprice Charms wholesale (Brigid's Heir). Applied LAST, consistent
    # with the existing rule that discounts land first and multipliers last.
    return merits.adjust_charm_cost(ruleset, character, charm, cost)


def spell_cost(ruleset: RuleSet, character: Character, spell=None) -> int:
    """XP to learn a spell. Three pricing policies, chosen by the splat's data:

    - **Flat per-circle** (Alchemical, p.64): a circle listed in `spell_cost_by_circle`
      prices at that rate — Man-Machine 12, God-Machine 14 — with no Occult discount.
    - **Discounted per-circle** (Lunar, p.251): when the splat's `new_spell_by_circle`
      maps the spell's circle, that base applies, reduced by the learner's *caste*
      discount (`CasteDefinition.spell_cost_discount` — a No Moon's −2). The
      Occult-Caste/Favoured discount does NOT apply to such a splat.
    - **Flat** (Solar/DB/Abyssal, core p.100/191): the flat `new_spell`, discounted to
      `new_spell_occult_favored_caste` when Occult is Caste/Favoured.

    `spell` is optional only so a caller with no spell in hand still gets the flat
    price; both per-circle policies need the spell to read its circle."""
    xp = ruleset.xp_costs_for(character.exalt_type)

    def _adjust(cost: int) -> int:
        # A Merit may reprice spells wholesale (Brigid's Heir halves them). Every
        # policy below routes through here so none of the three can be missed.
        return merits.adjust_spell_cost(ruleset, character, cost)

    if spell is not None:
        by_circle = xp.spell_cost_by_circle.get(spell.circle.value)
        if by_circle is not None:
            return _adjust(by_circle)
        if spell.circle in xp.new_spell_by_circle:
            base = xp.new_spell_by_circle[spell.circle]
            caste_def = ruleset.castes.get(character.caste)
            discount = caste_def.spell_cost_discount if caste_def else 0
            return _adjust(base - discount)
    favored = AbilityName.OCCULT in validate.caste_favored_abilities(ruleset, character)
    return _adjust(xp.new_spell_occult_favored_caste if favored else xp.new_spell)


def charm_slot_cost(ruleset: RuleSet, character: Character, *, dedicated: bool) -> int:
    """XP to buy one more Alchemical Charm Slot (p.64) — Dedicated is cheaper (10)
    than General (12). The Slot comes with one free Charm; you pay only for the Slot."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_charm_slot_dedicated if dedicated else xp.new_charm_slot_general


def charm_slot_upgrade_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to upgrade one Dedicated Charm Slot to a General one (p.64)."""
    return ruleset.xp_costs_for(character.exalt_type).charm_slot_upgrade


def retainer_charm_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for one Panoply (retainer) Charm bought WITHOUT a Slot. A native Alchemical
    pays the flat table rate (p.64, 6); an Eclipse/Moonshadow adding an Alchemical Charm
    to their Panoply through the crossover pays their caste's flat rate (p.90, 8). No
    Caste/Favored discount applies either way."""
    if validate.uses_charm_slots(ruleset, character):
        return ruleset.xp_costs_for(character.exalt_type).new_charm
    crossover = validate.crossover_panoply_xp(ruleset, character)
    if crossover is not None:
        return crossover
    return ruleset.xp_costs_for(character.exalt_type).new_charm


def martial_arts_charm_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for one Martial Arts Charm learned through Perfected Lotus Matrix (p.100,
    flat 11). MA Charms are stored inside the Matrix and use no Charm Slot."""
    xp = ruleset.xp_costs_for(character.exalt_type)
    return xp.new_martial_arts_charm if xp.new_martial_arts_charm is not None else xp.new_charm


def ox_body_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to buy one more Ox-Body Technique: priced as a normal new Charm (the
    variant chosen does not change the cost). 0 if the Charm is absent."""
    charm = validate.ox_body_charm(ruleset, character)
    return charm_cost(ruleset, character, charm) if charm else 0


def gift_cost(ruleset: RuleSet, character: Character) -> int:
    """XP to buy one more purchase of the Gift-granting Charm (Deadly Beastman
    Transformation): priced as a normal new Charm, regardless of how many Gifts
    this purchase grants — they come bundled with the purchase, not priced
    individually (p.124). 0 if the Charm is absent."""
    charm = validate.gift_charm(ruleset, character)
    return charm_cost(ruleset, character, charm) if charm else 0


def combo_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """XP for a new Combo: the sum of its member Charms' minimum Ability values
    (core p.213). Unknown ids contribute nothing (reference checks flag them)."""
    return sum(ruleset.charms[cid].min_ability for cid in charm_ids if cid in ruleset.charms)


def array_cost(ruleset: RuleSet, charm_ids: list[str]) -> int:
    """XP for a new Alchemical Array: the sum of its member Charms' minimum
    Attribute ratings (p.89). Arithmetically identical to `combo_cost` because
    `Charm.min_ability` stores the required *rating* for both keyings — the
    Attribute a Charm gates on is named by `min_attribute`, not rated by it — but
    it is a different rule on a different page, so it gets its own name rather
    than callers reaching for the Combo function."""
    return combo_cost(ruleset, charm_ids)


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
#
# Four purchasable kinds, priced off one ladder, in both currencies. The BP and
# XP tables (p.116 / p.115) agree on Art (5) and Formula (1) but NOT on Art
# Specialty (2 BP vs 3 XP) or Ritual base (2 vs 3); they are separate rows for
# that reason and must not be collapsed.
#
# `multiplier` is ExaltDefinition.thaumaturgy_cost_multiplier — 2 for spirits
# ("Spirits may use thaumaturgy, but they pay twice the normal experience (or
# bonus) points when learning or improving any Art, Science or ritual", p.114).
# No playable spirit splat exists yet, so it is 1 everywhere today.
# --------------------------------------------------------------------------- #

def _thaum_multiplier(ruleset: RuleSet, character: Character) -> int:
    return ruleset.exalt_for(character.exalt_type).thaumaturgy_cost_multiplier


def thaum_art_bp(ruleset: RuleSet, character: Character) -> int:
    """BP for training in an Art: +2 dice to attempts with it (p.126)."""
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    return costs.thaum_art * _thaum_multiplier(ruleset, character)


def thaum_art_xp(ruleset: RuleSet, character: Character) -> int:
    return (ruleset.xp_costs_for(character.exalt_type).thaum_new_art
            * _thaum_multiplier(ruleset, character))


def thaum_specialty_bp(ruleset: RuleSet, character: Character, *,
                       narrowed: bool = False) -> int:
    """BP for one Art specialty — which includes buying a printed *aspect*, since
    an aspect IS a general specialty (see models.rules.ThaumaturgicAspect).

    `narrowed` is Summoning's option alone (p.127): further limiting an aspect
    ("Summoning (War Gods)") "halves the cost of the aspect". Rounded UP, so the
    2-BP specialty becomes 1 rather than 0 — a free purchase is not a thing the
    book offers, and rounding down would make narrowing strictly dominant.
    """
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    base = costs.thaum_art_specialty
    if narrowed:
        base = -(-base // 2)
    return base * _thaum_multiplier(ruleset, character)


def thaum_specialty_xp(ruleset: RuleSet, character: Character, *,
                       narrowed: bool = False) -> int:
    base = ruleset.xp_costs_for(character.exalt_type).thaum_new_art_specialty
    if narrowed:
        base = -(-base // 2)
    return base * _thaum_multiplier(ruleset, character)


def thaum_ritual_bp(ruleset: RuleSet, character: Character, level: int,
                    orientations: int = 1) -> int:
    """BP for a ritual: "2 + 1 per level of Ritual" (p.116), plus a flat 1 for each
    regional version beyond the first (p.124)."""
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    base = costs.thaum_ritual_base + costs.thaum_ritual_per_level * level
    extra = costs.thaum_extra_orientation * max(0, orientations - 1)
    return (base + extra) * _thaum_multiplier(ruleset, character)


def thaum_ritual_xp(ruleset: RuleSet, character: Character, level: int,
                    orientations: int = 1) -> int:
    """XP for a ritual: "3, +1 per level of the ritual" (p.115). Note the base
    differs from the BP table's 2."""
    costs = ruleset.xp_costs_for(character.exalt_type)
    base = costs.thaum_ritual_base + costs.thaum_ritual_per_level * level
    extra = costs.thaum_extra_orientation * max(0, orientations - 1)
    return (base + extra) * _thaum_multiplier(ruleset, character)


def thaum_formula_bp(ruleset: RuleSet, character: Character,
                     orientations: int = 1) -> int:
    """BP for a formula or procedure: 1, plus 1 per extra regional version."""
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    total = costs.thaum_formula + costs.thaum_extra_orientation * max(0, orientations - 1)
    return total * _thaum_multiplier(ruleset, character)


def thaum_formula_xp(ruleset: RuleSet, character: Character,
                     orientations: int = 1) -> int:
    costs = ruleset.xp_costs_for(character.exalt_type)
    total = costs.thaum_formula + costs.thaum_extra_orientation * max(0, orientations - 1)
    return total * _thaum_multiplier(ruleset, character)


def thaum_orientation_bp(ruleset: RuleSet, character: Character) -> int:
    """BP for ONE further regional version of a ritual or formula already known
    (p.124). Flat, and the same for both kinds: "to completely master all versions of
    a given spell would cost four bonus points, in addition to the normal cost".

    Kept separate from `thaum_ritual_bp`/`thaum_formula_bp` so an extra orientation is
    its own logged purchase. That is what keeps the append-only XP log unambiguous —
    a row can only mean "learned it" or "learned another version of it", never both.
    """
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    return costs.thaum_extra_orientation * _thaum_multiplier(ruleset, character)


def thaum_orientation_xp(ruleset: RuleSet, character: Character) -> int:
    return (ruleset.xp_costs_for(character.exalt_type).thaum_extra_orientation
            * _thaum_multiplier(ruleset, character))


def thaum_science_step_bp(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """BP to raise a Science by ONE dot from `from_rating`: 5 for the first, 7 after.

    Provenance: the published cost tables omit Sciences entirely — a printing error,
    clarified by Grabowski afterwards and supplied by the rules authority (human,
    2026-07-29). See models.rules.BonusPointCosts.thaum_science_first_dot.
    """
    costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                    character.upbringing)
    rate = (costs.thaum_science_first_dot if from_rating <= 0
            else costs.thaum_science_additional_dot)
    return rate * _thaum_multiplier(ruleset, character)


def thaum_science_bp(ruleset: RuleSet, character: Character, rating: int) -> int:
    """Total BP to buy a Science up to `rating` from nothing — the chargen figure,
    since chargen holds a rating rather than a sequence of purchases. Flat per dot,
    so this is a sum rather than a closed form only to keep the two functions
    obviously consistent."""
    return sum(thaum_science_step_bp(ruleset, character, r) for r in range(max(0, rating)))


def thaum_science_step_xp(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise a Science by ONE dot: 7 flat for the first, then current × 6 —
    the ordinary "new trait flat, raises scale" shape. Same provenance caveat as
    `thaum_science_step_bp`."""
    costs = ruleset.xp_costs_for(character.exalt_type)
    step = (costs.thaum_new_science if from_rating <= 0
            else costs.thaum_science.at(from_rating))
    return step * _thaum_multiplier(ruleset, character)


def fetter_step(ruleset: RuleSet, character: Character, from_rating: int) -> int:
    """XP to raise one Fetter a dot (E:Ab p.283: "Fetter | current rating x 3")."""
    return ruleset.xp_costs_for(character.exalt_type).fetter.at(from_rating)


def new_fetter_cost(ruleset: RuleSet, character: Character) -> int:
    """XP for a brand-new Fetter — 20, or 15 for a character who knows the Arcanos the
    table names (p.283: "New Fetter (Relentless Hunter) | 15").

    The Charm is named by DATA (`ExperienceCosts.new_fetter_discount_charm_id`) and
    never spelled out here, so a printing that attaches the discount to a different
    Arcanos is a data edit. Asked of `validate.charm_picks` rather than
    `character.charms` directly: Charms live on four lists and reading one of them is
    how four call sites each missed Gifts the day Gifts landed.
    """
    xp = ruleset.xp_costs_for(character.exalt_type)
    cid = xp.new_fetter_discount_charm_id
    if cid and xp.new_fetter_discounted:
        if any(pick.charm_id == cid for pick in validate.charm_picks(ruleset, character)):
            return xp.new_fetter_discounted
    return xp.new_fetter
