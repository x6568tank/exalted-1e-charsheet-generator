"""
engine/validate/budgets.py — chargen point accounting: pools, bonus points, `validate_chargen`.

This module asks if each trait was PAID for. `validate_chargen` gives the answer for
a whole sheet.

  * `attribute_pool_assignment` / `effective_attribute_pools` — the 8/6/4 pools.
    The engine INFERS the category of each pool from the spend. It is not stored.
  * `two_pool_ability_accounting` — the Mountain Folk two-pool Ability budget.
  * `bonus_point_breakdown` — the bonus points of each domain.
  * `unspent_budget_issues` — unallocated free dots, as warnings.
  * `validate_chargen` — all chargen predicates.

⚠ Chargen accounting reads `_base._chargen_source`, NOT the live traits: once locked,
the snapshot is the source (decision 0004). A live trait here makes an XP purchase
look like a chargen overspend.

⚠ Willpower's Virtue component is PINNED at the lock (decision 0005). Raising a
Virtue after creation does not raise Willpower.

⚠ Play-state must never enter this module (decision 0006) — a test enforces it.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel

from ...models.character import Character
from ...models.rules import AbilityName, AttributeName, CharmType, RuleSet, VirtueName
from .. import artifacts, derive, elder, merits
from .. import paths as paths_mod
from ._base import (
    ATTRIBUTE_CATEGORIES,
    Issue,
    _attribute_category,
    _chargen_source,
    ability_rating,
    chargen_house_rules,
    craft_rating,
    effective_budgets,
    thaum_state,
)
from .alchemical import submodule_def
from .artifact_checks import check_artifacts
from .backgrounds import (
    background_dots_budget,
    background_issues,
    background_pool_dots,
    background_pool_spend,
    background_rating,
    background_rule,
    trait_rating,
)
from .castes import (
    _caste_favored,
    _caste_favored_attr_names,
    _caste_favored_attribute_category,
    _caste_favored_attribute_sets,
    caste_favored_abilities,
    splat_has_castes,
)
from .charms import (
    _immaculate_path,
    _mountain_folk_pattern,
    charm_pick_bp_costs,
    charm_pick_count,
    charm_slot_counts,
    charm_slot_usage,
    chargen_charm_picks,
    uses_charm_slots,
)
from .illuminated import (
    calling_abilities,
    camp_min_abilities,
    check_camp_and_calling,
    granted_charm_issues,
)
from .merit_checks import magic_gate_issues, merit_bonus_point_cost, merit_issues
from .spells import chargen_barred_circle
from .thaumaturgy import (
    _thaum_purchases_from,
    thaumaturgy_issues,
    magic_for_everyone_grant,
    thaum_purchase_bp_costs,
    thaumaturgy_chargen_issues,
)
from .traits import heritage_origin_issues


def _ability_slots(abilities: dict, crafts: list):
    """Yield (ability, rating) pairs for chargen accounting. The AbilityName.CRAFT key
    is dropped. Each Craft instance gives its own slot, keyed to CRAFT."""
    for ab, rating in abilities.items():
        if ab == AbilityName.CRAFT:
            continue
        yield ab, rating
    for cr in crafts:
        yield AbilityName.CRAFT, cr.rating


def two_pool_ability_accounting(b, character, abilities, crafts, bp_costs=None):
    """Return the Mountain Folk two-pool Ability accounting (CH6 p.230).

    The free pool (`ability_dots`) pays for ANY Ability up to `ability_cap_pre_bp` (3).
    The favored pool (`ability_favored_dots`) pays for FAVORED Abilities above that,
    up to 5. Other dots cost bonus points at the ordinary or favored rate.

    The player's allocation is not recorded, thus this calculates the cheapest legal
    one: the free pool first, then the favored pool for Favored dots, and overflow on
    the favored pool (1 BP/dot) before the free pool (2 BP/dot).

    Returns `(within, ability_bp)`: pool dots spent, and the bonus-point charge.
    `ability_bp` is 0 if `bp_costs` is None.

    ⚠ The ONE read site for this rule. `bonus_point_breakdown`, the unspent warning
    and the editor readout all call it.
    """
    cap = b.ability_cap_pre_bp
    ceiling = merits.DOT_MAX          # 5 — the chargen ability ceiling (p.230)
    favored_set = set(character.favored_abilities)
    nf_free = nf_above = 0
    fav_free_max = fav_above3 = fav_above_ceiling = 0
    for ab, rating in _ability_slots(abilities, crafts):
        if ab in favored_set:
            fav_free_max += min(rating, cap)
            fav_above3 += max(0, min(rating, ceiling) - cap)
            fav_above_ceiling += max(0, rating - ceiling)
        else:
            nf_free += min(rating, cap)
            nf_above += max(0, rating - cap)
    fav_free = min(max(0, b.ability_dots - nf_free), fav_free_max)
    free_used = nf_free + fav_free
    favored_used = (fav_free_max - fav_free) + fav_above3
    within = free_used + min(favored_used, b.ability_favored_dots)
    if bp_costs is None:
        return within, 0
    ability_bp = (nf_above + max(0, nf_free - b.ability_dots)) * bp_costs.ability
    ability_bp += fav_above_ceiling * bp_costs.ability_favored_caste
    ability_bp += max(0, favored_used - b.ability_favored_dots) * bp_costs.ability_favored_caste
    return within, ability_bp


def _attr_bp_caste_favored(ruleset: RuleSet, character: Character, b, bp_costs,
                            attributes: dict) -> int:
    """Return the Attribute bonus points in caste_favored mode. The pools go in order
    to the caste, favored and other sets. Overspend on the caste and favored sets
    costs `attribute_caste_favored`. The other set costs `attribute`."""
    caste, favored, remaining = _caste_favored_attribute_sets(ruleset, character)
    pools = list(effective_attribute_pools(ruleset, character))

    def spend(group: set) -> int:
        return sum(attributes.get(a, b.attribute_base) - b.attribute_base for a in group)

    cf_rate = bp_costs.attribute_caste_favored
    return (max(0, spend(caste) - pools[0]) * cf_rate
            + max(0, spend(favored) - pools[1]) * cf_rate
            + max(0, spend(remaining) - pools[2]) * bp_costs.attribute)


def unspent_budget_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Return the unallocated free chargen dots, as warnings.

    Covers Attributes, Abilities, Virtues and Backgrounds. Reads the snapshot once
    locked.

    ⚠ WARNINGS, never errors (human's ruling): an unfinished sheet is not illegal.
    The budget arithmetic charges `max(0, spend - budget)` and does not see an
    underspend.

    ⚠ Bonus points are EXCLUDED: unspent BP are not an omission.
    """
    b = effective_budgets(ruleset, character)
    (attributes, abilities, crafts, virtues, backgrounds, _specialties,
     charms, spells, *_rest) = _chargen_source(character)
    issues: list[Issue] = []

    def warn(domain: str, left: int, total: int) -> None:
        if left > 0:
            issues.append(Issue(
                code="unspent-chargen-dots", where=domain.lower(), severity="warning",
                message=f"{left} of {total} free {domain} dots are unspent.",
            ))

    # Attributes: the pools are per GROUP. Count and sum the leftovers of each pool.
    if b.attribute_mode == "caste_favored":
        groups = _caste_favored_attribute_sets(ruleset, character)   # caste/favored/rest
        spends = [sum(attributes.get(a, b.attribute_base) - b.attribute_base for a in g)
                  for g in groups]
        pools = list(effective_attribute_pools(ruleset, character))                              # FIXED order here
    else:
        assignment = attribute_pool_assignment(ruleset, character, b, attributes)
        spends = [spend for _cat, spend, _pool in assignment]
        pools = [pool for _cat, _spend, pool in assignment]
    warn("Attribute", sum(max(0, p - s) for s, p in zip(spends, pools)), sum(pools))

    # Abilities/Virtues/Backgrounds: one pool each. Only dots at or below the pre-BP
    # cap count, as in bonus_point_breakdown. The Mountain Folk shape (CH6 p.230)
    # uses two_pool_ability_accounting.
    if b.ability_favored_dots:
        ability_within, _bp = two_pool_ability_accounting(b, character, abilities, crafts)
        _total = b.ability_dots + b.ability_favored_dots
        warn("Ability", _total - ability_within, _total)
    else:
        ability_within = sum(min(rating, b.ability_cap_pre_bp)
                             for _ab, rating in _ability_slots(abilities, crafts))
        warn("Ability", b.ability_dots - ability_within, b.ability_dots)

    virtue_within = sum(max(0, min(r, b.virtue_cap_pre_bp) - b.virtue_base)
                        for r in virtues.values())
    warn("Virtue", b.virtue_dots - virtue_within, b.virtue_dots)

    bg_within, _above = background_pool_spend(ruleset, character, b, backgrounds)
    warn("Background", background_dots_budget(b, character) - bg_within,
         background_dots_budget(b, character))

    # Fetters: the same arithmetic.
    if b.fetter_dots:
        fetter_within = sum(min(f.rating, b.fetter_cap_pre_bp)
                            for f in character.fetters)
        warn("Fetter", b.fetter_dots - fetter_within, b.fetter_dots)

    # Charms: a pool of PICKS, not dots. Spells share the pool (p.100). The
    # Immaculate path changes its size (DB p.151).
    #
    # ⚠ Both expressions must match `bonus_point_breakdown`. Skipped for the Slot
    # economy. `charm_noun` gives "Arcanoi" for a ghost.
    if b.charm_count and not uses_charm_slots(ruleset, character):
        pool = (b.immaculate_charm_count
                if _immaculate_path(ruleset, charms, character.exalt_type)
                else b.charm_count)
        taken = charm_pick_count(ruleset, character) + sum(
            1 for sid in spells if ruleset.spells.get(sid) is not None)
        left = pool - taken
        if left > 0:
            noun = ruleset.exalt_for(character.exalt_type).charm_noun
            issues.append(Issue(
                code="unspent-chargen-dots", where="charms", severity="warning",
                message=f"{left} of {pool} free {noun} are unspent.",
            ))

    return issues


def optional_favored_ability_open(ruleset: RuleSet, character: Character) -> bool:
    """Return True if the optional Favoured Ability of core p.103 applies: the ORIGIN
    allows it and the Storyteller switched it on. Reads `chargen_house_rules`, thus a
    locked sheet keeps its answer."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return (b.optional_favored_ability
            and chargen_house_rules(character).mortal_favored_ability)


def favored_ability_count(ruleset: RuleSet, character: Character) -> int:
    """Return the Favoured Ability count: the budget count, plus one if the core
    p.103 option applies."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    total = b.favored_count + (1 if optional_favored_ability_open(ruleset, character) else 0)
    # Prodigy: one more per purchase, five maximum (p.21).
    extra = merits.merits_and_flaws_calc(ruleset, character).extra_favored_abilities
    return min(merits.PRODIGY_FAVORED_CAP, total + extra) if extra else total


def mortal_favored_ability_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check the condition of the p.103 option: no Ability can be higher than the
    Favored Ability. Only while the option applies. Exalts have no such ceiling."""
    if not optional_favored_ability_open(ruleset, character):
        return []
    favored = list(character.favored_abilities)
    if not favored:
        return []
    best = max(character.abilities.get(f, 0) for f in favored)
    over = sorted(a for a, r in character.abilities.items()
                  if a not in favored and r > best)
    if not over:
        return []
    return [Issue(
        code="mortal-favored-not-highest", where=a.value,
        message=f"{a.value} ({character.abilities[a]}) is rated above the Favoured "
                f"Ability ({best}); a mortal's Favoured Ability must be equal to or "
                f"greater than every other Ability (core p.103).",
    ) for a in over]


class BonusPointLine(BaseModel):
    """The bonus points of one domain, for the chargen BP log."""
    domain: str
    points: int


class BonusPointBreakdown(BaseModel):
    """The bonus points of each domain. `lines` are in display order, each domain
    present at 0 too. `total` is the sum. `available` is the budget."""
    lines: list[BonusPointLine]
    total: int
    available: int

    @property
    def over_budget(self) -> bool:
        return self.total > self.available


def bonus_point_breakdown(ruleset: RuleSet, character: Character) -> BonusPointBreakdown:
    """Return the bonus points spent in each chargen domain (Exalted 1e pp.104-105).

    For each domain, dots above the free budget or the pre-bonus cap of 3 cost bonus
    points at the RuleSet.bonus_costs rates. The free dots go to the most expensive
    dots first. The one source of the BP totals: validate_chargen checks the ceiling
    with it, and the editor shows it as a log.
    """
    b = effective_budgets(ruleset, character)
    bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin, character.upbringing)
    (attributes, abilities, crafts, virtues, backgrounds, specialties,
     charms, spells, combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, submodules, colleges, thaumaturgy, paths,
     favored_path, elemental_powers, variant_purchases) = _chargen_source(character)

    cf = _caste_favored(ruleset, character)
    cf_set = (cf[0] | cf[1]) if cf is not None else set()
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)
    picks = chargen_charm_picks(ruleset, character)

    # --- Attributes ----------------------------------------------------------- #
    # caste_favored mode (Alchemical, p.60). See _attr_bp_caste_favored.
    if b.attribute_mode == "caste_favored":
        attr_bp = _attr_bp_caste_favored(ruleset, character, b, bp_costs, attributes)
    else:
        # category mode: three category spends matched to the 8/6/4 pools by spend.
        # The rate of a category depends on whether it is the caste's favored one
        # (Lunar, p.93). Ability-caste splats use the flat `attribute` rate.
        attr_bp = sum(
            max(0, spend - pool) * (bp_costs.attribute_caste_favored if cat == caste_attr_category
                                     else bp_costs.attribute)
            for cat, spend, pool in attribute_pool_assignment(ruleset, character, b,
                                                              attributes)
        )

    # Dragon-King breed bonuses (PG pp.167-174) add to the stored value. Each
    # EFFECTIVE dot above 5 costs bonus points at the attribute rate (p.175).
    # Example: stored Dexterity 5 on a Pterok is effective 7: (7 − 5) × 4 = 8 BP.
    caste_def = ruleset.castes.get(character.caste)
    breed_bonuses = (caste_def.breed_traits.attribute_bonuses
                     if caste_def and caste_def.breed_traits else {})
    for aname, bonus in breed_bonuses.items():
        if bonus:
            effective = attributes.get(aname, b.attribute_base) + bonus
            if effective > 5:
                attr_bp += (effective - 5) * bp_costs.attribute

    # --- Abilities: 25 free dots, pre-BP cap 3 -------------------------------- #
    # Four rate tiers. A Calling (p.90) STACKS with Caste/Favoured:
    #   both      1 BP per `calling_ability_favored_caste_dots_per_point` dots (0.5/dot)
    #   cf only   bp_costs.ability_favored_caste                              (1/dot)
    #   calling   bp_costs.calling_ability                                    (1/dot)
    #   neither   bp_costs.ability                                            (2/dot)
    cap = b.ability_cap_pre_bp
    call_set = calling_abilities(ruleset, character)
    per_point = max(1, bp_costs.calling_ability_favored_caste_dots_per_point)

    def _tier(ab) -> str:
        cf, call = ab in cf_set, ab in call_set
        return "both" if (cf and call) else "cf" if cf else "calling" if call else "neither"

    if b.ability_favored_dots:
        # TWO-POOL (Mountain Folk, CH6 p.230). See two_pool_ability_accounting.
        _within, ability_bp = two_pool_ability_accounting(
            b, character, abilities, crafts, bp_costs)
    else:
        within_by_tier = {"both": 0, "cf": 0, "calling": 0, "neither": 0}
        above_by_tier = dict(within_by_tier)
        for ab, rating in _ability_slots(abilities, crafts):
            tier = _tier(ab)
            within_by_tier[tier] += min(rating, cap)
            above_by_tier[tier] += max(0, rating - cap)

        # Overflow is paid cheapest first, by effective rate per dot.
        flat_rate = {"cf": bp_costs.ability_favored_caste,
                     "calling": bp_costs.calling_ability,
                     "neither": bp_costs.ability}
        order = sorted(("cf", "calling", "neither"), key=lambda t: flat_rate[t])
        total_within = sum(within_by_tier.values())
        overflow = max(0, total_within - b.ability_dots)

        paid = dict(above_by_tier)            # above-cap dots always cost BP
        remaining = overflow
        for tier in ["both"] + order:         # 'both' is 0.5/dot, cheapest of all
            take = min(remaining, within_by_tier[tier])
            paid[tier] += take
            remaining -= take
            if not remaining:
                break

        # The 'both' tier rounds UP (human's ruling).
        ability_bp = ((paid["both"] + per_point - 1) // per_point
                      + sum(paid[t] * flat_rate[t] for t in order))

    # --- Backgrounds: N free dots, pre-BP cap 3 (above-3 dot costs 2) --------- #
    # `background_rules` can exempt a Background from the cap and make its upper
    # dots cost more.
    bg_within, above_rates = background_pool_spend(ruleset, character, b, backgrounds,
                                                   bp_costs)
    bg_above_bp = sum(above_rates)
    bg_overflow = max(0, bg_within - background_dots_budget(b, character))
    bg_bp = bg_above_bp + bg_overflow * bp_costs.background

    # --- Virtues: 5 free dots over base 1, pre-BP cap 3 ----------------------- #
    # PG p.74: an ATTUNED Virtue costs 2 BP per dot. Attuned dots use the free pool
    # LAST, thus the discount applies to the most dots.
    favored = merits.merits_and_flaws_calc(ruleset, character).favored_virtues
    v_within = v_above = attuned_within = attuned_above = 0
    for v, rating in virtues.items():
        within = max(0, min(rating, b.virtue_cap_pre_bp) - b.virtue_base)
        above = max(0, rating - b.virtue_cap_pre_bp)
        v_within += within
        v_above += above
        if v.value in favored:
            attuned_within += within
            attuned_above += above
    v_overflow = max(0, v_within - b.virtue_dots)
    # The free pool takes the NON-attuned within-cap dots first. The remainder takes
    # attuned dots. The other attuned dots are priced at the discount.
    free_left = max(0, b.virtue_dots - (v_within - attuned_within))
    attuned_paid = attuned_above + max(0, attuned_within - free_left)
    virtue_bp = (v_above + v_overflow) * bp_costs.virtue - attuned_paid

    # --- Charms & Spells ------------------------------------------------------ #
    if uses_charm_slots(ruleset, character):
        # Slot economy (Alchemical, p.88-89): the character buys SLOTS. BP: extra
        # General Slots at bp_costs.charm, extra Dedicated at charm_favored_caste.
        g, d, bg, bd = charm_slot_counts(ruleset, character)
        charm_bp = (max(0, g - bg) * bp_costs.charm
                    + max(0, d - bd) * bp_costs.charm_favored_caste)
    else:
        # Per-pick economy: one Charm/Spell pool (p.100). The Immaculate path (DB,
        # p.151) changes the pool size and the BP row.
        immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
        free_charm_pool = b.immaculate_charm_count if immaculate else b.charm_count
        occult_cf = AbilityName.OCCULT in cf_set
        # See `charm_pick_bp_costs`. Spells share the pool.
        pick_costs = charm_pick_bp_costs(ruleset, character, picks)
        for sid in spells:
            if ruleset.spells.get(sid) is None:
                continue
            pick_costs.append(merits.adjust_spell_cost(
                ruleset, character,
                bp_costs.charm_favored_caste if occult_cf else bp_costs.charm))
        pick_costs.sort(reverse=True)                # free pool absorbs the dearest picks
        charm_bp = sum(pick_costs[free_charm_pool:])

    # --- Combos: BP = its number of Charms (p.213) --------------------------- #
    combo_bp = sum(len(combo.charm_ids) for combo in combos)

    # --- Arrays: BP = its number of Charms (Alchemical, p.89) ---------------- #
    array_bp = sum(len(array.charm_ids) for array in arrays)

    # --- Submodules: each priced at its own bp_cost (Alchemical, p.89) ------- #
    submodule_bp = sum(
        (d.bp_cost for d in (submodule_def(ruleset, s.charm_id, s.key) for s in submodules)
         if d is not None), 0)

    # --- Specialties: 1 BP/dot; Caste/Favoured get N dots per BP (p.105) ------ #
    cf_spec_dots = sum(s.rating for s in specialties if s.ability in cf_set)
    other_spec_dots = sum(s.rating for s in specialties if s.ability not in cf_set)
    per_point = bp_costs.specialty_favored_caste_dots_per_point
    spec_bp = other_spec_dots * bp_costs.specialty + (cf_spec_dots + per_point - 1) // per_point

    # --- Astrological Colleges (Sidereal): own pool, pre-BP cap 3 ------------- #
    # Own-Maiden Colleges are the cheap dots. The free pool takes the most expensive
    # dots first. Above-cap dots always cost BP.
    college_cap = b.college_cap_pre_bp
    col_cheap_within = col_dear_within = col_above_bp = 0
    for cr in colleges:
        college = ruleset.colleges.get(cr.college_id)
        own = college is not None and college.house == character.caste
        within = min(cr.rating, college_cap)
        above = max(0, cr.rating - college_cap)
        col_above_bp += above * (bp_costs.college_own_house if own else bp_costs.college)
        if own:
            col_cheap_within += within
        else:
            col_dear_within += within
    col_overflow = max(0, (col_cheap_within + col_dear_within) - b.college_dots)
    col_overflow_cheap = min(col_overflow, col_cheap_within)
    college_bp = (col_above_bp
                  + col_overflow_cheap * bp_costs.college_own_house
                  + (col_overflow - col_overflow_cheap) * bp_costs.college)

    # --- Dragon-King Paths (PG p.176): own pool, favoured discount, above-3 ---- #
    # The College shape, with two changes: the cheap dots are FAVOURED Paths (breed
    # element or `favored_path`), and the above-3 rate is DOUBLED.
    path_cap = b.path_cap_pre_bp
    path_cheap_within = path_dear_within = path_above_bp = 0
    for pr in paths:
        # The snapshot value of `favored_path` (decision 0003).
        fav = paths_mod.path_is_favored(ruleset, character, pr.path_id,
                                        favored_path=favored_path)
        within = min(pr.rating, path_cap)
        above = max(0, pr.rating - path_cap)
        path_above_bp += above * (bp_costs.path_breed_above_3 if fav else bp_costs.path_above_3)
        if fav:
            path_cheap_within += within
        else:
            path_dear_within += within
    path_overflow = max(0, (path_cheap_within + path_dear_within) - b.path_dots)
    path_overflow_cheap = min(path_overflow, path_cheap_within)
    path_bp = (path_above_bp
               + path_overflow_cheap * bp_costs.path_breed
               + (path_overflow - path_overflow_cheap) * bp_costs.path)

    # --- Thaumaturgy: every purchase priced individually, no free pool -------- #
    # No free pool (p.113): the sum of the purchase prices. Sciences price at 0 here.
    # See ThaumPurchase.priced.
    thaum_purchases_cg = _thaum_purchases_from(ruleset, thaumaturgy)
    thaum_bp = sum(thaum_purchase_bp_costs(
        ruleset, character, thaum_purchases_cg,
        free_picks=magic_for_everyone_grant(ruleset, character)))

    # --- Fetters (ghosts only, E:Ab p.126-127) -------------------------------- #
    # The Background shape. No Passion line: Passions cost nothing (p.283).
    f_within = sum(min(f.rating, b.fetter_cap_pre_bp) for f in character.fetters)
    f_above = sum(max(0, f.rating - b.fetter_cap_pre_bp) for f in character.fetters)
    f_overflow = max(0, f_within - b.fetter_dots)
    fetter_bp = (f_above + f_overflow) * bp_costs.fetter

    # --- Willpower / Essence -------------------------------------------------- #
    wp_bp = wp_purchased * bp_costs.willpower
    # God-Blooded p.50: `essence_by_rating` prices by the target rating.
    if bp_costs.essence_by_rating and essence in bp_costs.essence_by_rating:
        essence_bp = bp_costs.essence_by_rating[essence]
    else:
        essence_bp = max(0, essence - b.essence_start) * bp_costs.essence

    lines = [
        BonusPointLine(domain="Attributes", points=attr_bp),
        BonusPointLine(domain="Abilities", points=ability_bp),
        BonusPointLine(domain="Backgrounds", points=bg_bp),
        BonusPointLine(domain="Virtues", points=virtue_bp),
        BonusPointLine(domain="Charms & Spells", points=charm_bp),
        BonusPointLine(domain="Combos", points=combo_bp),
    ]
    # Arrays: only for splats that build them (p.89).
    if array_bp or submodule_bp or uses_charm_slots(ruleset, character):
        lines.append(BonusPointLine(domain="Arrays", points=array_bp))
        lines.append(BonusPointLine(domain="Submodules", points=submodule_bp))
    lines += [
        BonusPointLine(domain="Specialties", points=spec_bp),
        BonusPointLine(domain="Willpower", points=wp_bp),
        BonusPointLine(domain="Essence", points=essence_bp),
    ]
    # Colleges: only for splats that have them.
    if b.college_dots > 0 or colleges:
        lines.insert(3, BonusPointLine(domain="Colleges", points=college_bp))
    # Paths: only for splats that have them.
    if b.path_dots > 0 or paths:
        lines.insert(3, BonusPointLine(domain="Paths", points=path_bp))
    # Fetters: only for splats that have them.
    if b.fetter_dots > 0 or character.fetters:
        lines.insert(3, BonusPointLine(domain="Fetters", points=fetter_bp))
    # Thaumaturgy: only after the first purchase.
    if thaumaturgy.arts or thaumaturgy.art_specialties or thaumaturgy.sciences \
            or thaumaturgy.rituals or thaumaturgy.formulas:
        lines.append(BonusPointLine(domain="Thaumaturgy", points=thaum_bp))
    # Elemental Powers (PG p.68): only when held.
    elemental_bp = sum(
        ruleset.elemental_powers[pid].bp_cost
        for pid in elemental_powers if pid in ruleset.elemental_powers)
    if elemental_powers:
        lines.append(BonusPointLine(domain="Elemental Powers", points=elemental_bp))
    # A MERIT is a spend. A FLAW raises `available`. ⚠ Not a negative line: that
    # would let a Flaw pay for an overspend in a different domain. Oathbound points
    # are after the stacking reduction.
    merit_bp = merit_bonus_point_cost(ruleset, character)
    granted = merits.merits_and_flaws_calc(ruleset, character).bonus_point_grant
    if character.merits_flaws or merit_bp:
        lines.append(BonusPointLine(domain="Merits", points=merit_bp))
    total = sum(line.points for line in lines)
    # Inheritance (God-Blooded, p.61): bonus points added by rating.
    inheritance_bp = 0
    if b.inheritance_bonus_points:
        rating = min(merits.inheritance_rating(character),
                     len(b.inheritance_bonus_points) - 1)
        inheritance_bp = b.inheritance_bonus_points[rating]
    return BonusPointBreakdown(lines=lines, total=total,
                               available=b.bonus_points + granted + inheritance_bp)


def attribute_pool_assignment(ruleset: RuleSet, character: Character, b, attributes
                              ) -> list[tuple[str, int, int]]:
    """Return [(category, spend, pool)] for category-mode splats.

    The biggest spend takes the biggest pool.

    ⚠ Thus Diminished Attributes is not a budget delta. The forfeit comes off the
    pool that the category gets, which is known only after the match.

    ⚠ A forfeit can move a category to a smaller pool, and that can cost bonus points
    in a different category (human's ruling).
    """
    forfeits = merits.merits_and_flaws_calc(ruleset, character).forfeited_attribute_dots
    cat_spends = sorted(
        ((cat, sum(attributes[a] - b.attribute_base for a in attrs))
         for cat, attrs in ATTRIBUTE_CATEGORIES.items()),
        key=lambda cs: cs[1], reverse=True,
    )
    pools = sorted(effective_attribute_pools(ruleset, character), reverse=True)
    return [(cat, spend, max(0, pool - forfeits.get(cat, 0)))
            for (cat, spend), pool in zip(cat_spends, pools)]


def _chargen_attribute_range_issues(b, attributes, mf_caps) -> list[Issue]:
    """Check the Attribute ranges. A Merit or Flaw can move the ceiling of one
    Attribute. The floor follows a lower ceiling down."""
    issues: list[Issue] = []
    for name, attr in attributes.items():
        # The origin ceiling (CH6 p.230) is the base. Absent = 5.
        origin_cap = b.attribute_caps.get(name.value, b.attribute_cap or merits.DOT_MAX)
        cap = mf_caps.attribute_caps.get(name.value, origin_cap)
        # ⚠ The floor must follow the ceiling DOWN. Disfigured can set 0. An origin
        # floor (CH6 p.230) raises the floor. Else the range can be "3-0".
        low = min(b.attribute_min or b.attribute_base, cap)
        if not (low <= attr <= cap):
            span = f"exactly {cap}" if low == cap else f"{low}-{cap}"
            issues.append(Issue(
                code="attribute-range", where=name.value,
                message=f"Attribute {name.value} = {attr}; must be {span} at creation.",
            ))
    return issues


def _chargen_caste_favored_attribute_issues(ruleset: RuleSet, character: Character, b, attributes) -> list[Issue]:
    """Check caste_favored Attributes (Alchemical, p.60): the Favoured count, no
    overlap with Caste, and the Caste Attribute minimum."""
    issues: list[Issue] = []
    # --- caste_favored attribute legality (Alchemical, p.60) ------------------ #
    if b.attribute_mode == "caste_favored":
        caste_def = ruleset.castes.get(character.caste)
        caste_attrs = set(caste_def.caste_attributes) if caste_def else set()
        fav_attrs = character.favored_attributes
        if len(set(fav_attrs)) != b.attribute_favored_count:
            issues.append(Issue(
                code="favored-attribute-count",
                message=f"Expected {b.attribute_favored_count} Favored Attributes, "
                        f"found {len(set(fav_attrs))}.",
            ))
        overlap = set(fav_attrs) & caste_attrs
        if overlap:
            issues.append(Issue(
                code="favored-attribute-overlaps-caste",
                message="Favored Attributes may not be Caste Attributes: "
                        f"{sorted(a.value for a in overlap)}.",
            ))
        for a in sorted(caste_attrs, key=lambda x: x.value):
            if attributes.get(a, 0) < b.attribute_caste_min:
                issues.append(Issue(
                    code="caste-attribute-min", where=a.value,
                    message=f"Caste Attribute {a.value} = {attributes.get(a, 0)}; "
                            f"must be at least {b.attribute_caste_min} at creation.",
                ))
    return issues


def _chargen_ability_dot_issues(b, abilities, crafts, cf_set) -> list[Issue]:
    """Ability ranges and the Caste/Favoured dot minimum."""
    issues: list[Issue] = []
    cheap_within = 0
    for ab, rating in _ability_slots(abilities, crafts):
        if not (0 <= rating <= 5):
            issues.append(Issue(
                code="ability-range", where=ab.value,
                message=f"Ability {ab.value} = {rating}; must be 0-5 at creation.",
            ))
        if ab in cf_set:
            cheap_within += min(rating, b.ability_cap_pre_bp)
    if cheap_within < b.ability_min_caste_favored:
        issues.append(Issue(
            code="ability-caste-favored-min",
            message=f"At least {b.ability_min_caste_favored} of the {b.ability_dots} "
                    f"Ability dots must be Caste/Favoured; only {cheap_within} are.",
        ))
    return issues


def _chargen_required_ability_issues(ruleset: RuleSet, character: Character, b, abilities, crafts) -> list[Issue]:
    """Check the Ability floors: DB p.151, Sidereal p.98, the camp (p.89), and the
    group-sum floors."""
    issues: list[Issue] = []
    # Any ONE listed Ability meets a requirement. The budget list and the caste list
    # are combined. A ronin ignores the caste list (p.100).
    caste_def = ruleset.castes.get(character.caste)
    caste_min = ([] if b.ignore_caste_min_abilities
                 else (caste_def.required_min_abilities if caste_def else []))
    # The camp floors (p.89) join the same union.
    camp_min = [] if b.ignore_caste_min_abilities else camp_min_abilities(ruleset, character)
    for req in list(b.required_min_abilities) + list(caste_min) + list(camp_min):
        best = max((abilities.get(ab, 0) for ab in req.abilities), default=0)
        if best < req.rating:
            names = " or ".join(a.value for a in req.abilities)
            issues.append(Issue(
                code="required-min-ability", where=names,
                message=f"This origin requires at least {req.rating} dot(s) in {names}; "
                        f"has {best}.",
            ))
    # Group-sum floors (CH6 p.230). Each Craft focus counts separately.
    caste_groups = ([] if b.ignore_caste_min_abilities
                    else (caste_def.required_min_ability_groups if caste_def else []))
    for req in list(b.required_min_ability_groups) + list(caste_groups):
        total = sum(rating for ab, rating in _ability_slots(abilities, crafts)
                    if ab in req.abilities)
        if total < req.rating:
            names = " + ".join(sorted(a.value for a in req.abilities))
            issues.append(Issue(
                code="required-min-ability-group", where=names,
                message=f"This origin requires at least {req.rating} dot(s) total "
                        f"divided among {names}; has {total}.",
            ))
    return issues


def _chargen_virtue_range_issues(b, virtues, mf_caps) -> list[Issue]:
    """Check the Virtue ranges. A Merit or Flaw can move the ceiling."""
    issues: list[Issue] = []
    virtue_cap = (mf_caps.virtue_cap if mf_caps.virtue_cap is not None
                  else merits.DOT_MAX)
    for v, rating in virtues.items():
        if not (b.virtue_base <= rating <= virtue_cap):
            issues.append(Issue(
                code="virtue-range", where=v.value,
                message=f"Virtue {v.value} = {rating}; must be "
                        f"{b.virtue_base}-{virtue_cap} at creation.",
            ))
    return issues


def _chargen_college_issues(ruleset: RuleSet, character: Character, b, colleges) -> list[Issue]:
    """Check the Colleges (Sidereal, p.98): references, range, and the own-Maiden
    floor."""
    issues: list[Issue] = []
    # Over-budget dots cost bonus points (bonus_point_breakdown). No hard total cap.
    own_house_dots = 0
    for cr in colleges:
        college = ruleset.colleges.get(cr.college_id)
        if college is None:
            issues.append(Issue(
                code="unknown-college", where=cr.college_id,
                message=f"College {cr.college_id} is not in the RuleSet.",
            ))
            continue
        if not (0 <= cr.rating <= 5):
            issues.append(Issue(
                code="college-range", where=cr.college_id,
                message=f"College {college.name} = {cr.rating}; must be 0-5 at creation.",
            ))
        if college.house == character.caste:
            own_house_dots += cr.rating
    if own_house_dots < b.college_min_own_house:
        issues.append(Issue(
            code="college-own-house-min",
            message=f"At least {b.college_min_own_house} College dots must be in the "
                    f"character's Maiden's Colleges; only {own_house_dots} are.",
        ))
    return issues


def _chargen_path_issues(ruleset: RuleSet, character: Character, b, paths, essence: int) -> list[Issue]:
    """Check the Dragon-King Paths (PG pp.175-177): references, range, the Essence
    gate, the Breed/Favoured floor, and the Favoured-Path choice."""
    issues: list[Issue] = []
    # --- Dragon-King Paths (PG p.175-177) ------------------------------------ #
    # ⚠ The Essence gate uses the CHARGEN Essence (snapshot, or live before the
    # lock), never `essence_start`.
    path_max = b.path_max_by_essence.get(essence, 0)
    favored_dots = 0
    for pr in paths:
        path = ruleset.paths.get(pr.path_id)
        if path is None:
            issues.append(Issue(
                code="path-unknown", where=pr.path_id,
                message=f"Path {pr.path_id} is not in the RuleSet.",
            ))
            continue
        if not (0 <= pr.rating <= 6):
            issues.append(Issue(
                code="path-range", where=pr.path_id,
                message=f"Path {path.name} = {pr.rating}; must be 0-6 at creation.",
            ))
        if path_max and pr.rating > path_max:
            issues.append(Issue(
                code="path-essence-cap", where=pr.path_id,
                message=f"{path.name} = {pr.rating}; at Essence {essence} a Dragon King "
                        f"cannot develop a Path above {path_max}.",
            ))
        if paths_mod.path_is_favored(ruleset, character, pr.path_id):
            favored_dots += pr.rating
    if b.path_dots > 0 and favored_dots < b.path_min_breed_favored:
        issues.append(Issue(
            code="path-min-breed-favored",
            message=f"At least {b.path_min_breed_favored} Path dots must be in Breed or "
                    f"Favoured Paths; only {favored_dots} are.",
        ))
    if character.favored_path:
        fp = ruleset.paths.get(character.favored_path)
        if fp is None:
            issues.append(Issue(
                code="favored-path-unknown", where=character.favored_path,
                message=f"Favoured Path {character.favored_path} is not in the RuleSet.",
            ))
        elif fp.element and fp.element == paths_mod.breed_element(ruleset, character):
            issues.append(Issue(
                code="favored-path-is-breed-path", where=character.favored_path,
                message=f"{fp.name} is one of your breed's Paths; the chosen Favoured "
                        "Path must be one of the other eight.",
            ))
    return issues


def _chargen_essence_ceiling_issues(b, attributes, virtues, essence: int) -> list[Issue]:
    """Check the Essence-gated ceilings and the Virtue floors (Dragon-Kings,
    PG p.177)."""
    issues: list[Issue] = []
    # p.177: Intelligence by Essence. elder.trait_ceiling gives the Ability ceiling.
    # Virtue 6 is post-lock only. p.175: the Valor floor.
    int_cap = b.intelligence_max_by_essence.get(essence, 0)
    if int_cap and attributes[AttributeName.INTELLIGENCE] > int_cap:
        issues.append(Issue(
            code="intelligence-essence-cap",
            message=f"Intelligence = {attributes[AttributeName.INTELLIGENCE]}; at "
                    f"Essence {essence} a Dragon King's Intelligence cannot exceed "
                    f"{int_cap}.",
        ))
    virt_cap = b.virtue_max_by_essence.get(essence, 0)
    for vname, rating in virtues.items():
        if virt_cap and rating > virt_cap:
            issues.append(Issue(
                code="virtue-essence-cap", where=vname.value,
                message=f"{vname.value.title()} = {rating}; at Essence {essence} a "
                        f"Dragon King's Virtues cannot exceed {virt_cap}.",
            ))
        need = b.required_virtue_dots.get(vname, 0)
        if need and rating < need:
            issues.append(Issue(
                code="required-virtue-dots", where=vname.value,
                message=f"Dragon Kings must put at least {need} dot in "
                        f"{vname.value.title()}; it is {rating}.",
            ))
    return issues


def _chargen_spell_circle_issues(ruleset: RuleSet, character: Character, spells) -> list[Issue]:
    """Check the spell circle that is barred at creation."""
    issues: list[Issue] = []
    # --- Spells ---------------------------------------------------------------- #
    barred = chargen_barred_circle(ruleset, character)
    for sid in spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        if barred is not None and spell.circle == barred:
            issues.append(Issue(
                code="spell-top-circle-chargen", where=sid,
                message=f"{spell.name}: {spell.circle.value} Circle spells may not "
                        "be taken at character creation.",
            ))
    return issues


def _chargen_charm_issues(ruleset: RuleSet, character: Character, b, charms, spells, ox_body,
                         beastman_gifts, cf_set) -> list[Issue]:
    """Check the chargen Charms: the Slot rules (Alchemical), or the per-pick
    Caste/Favoured minimum and the Immaculate one-tree rule."""
    issues: list[Issue] = []
    if uses_charm_slots(ruleset, character):
        # Slots (p.88-89): non-Caste/Favored Charms go in General Slots only. The
        # installed total cannot exceed the Slots. The installation motes cannot
        # exceed the Personal pool (p.62).
        g, d, _bg, _bd = charm_slot_counts(ruleset, character)
        installed, noncf, install_motes = charm_slot_usage(ruleset, character)
        if installed > g + d:
            issues.append(Issue(
                code="charm-exceeds-slots",
                message=f"{installed} Charms installed but only {g + d} Charm Slots "
                        f"({g} General + {d} Dedicated); buy more Slots or install fewer.",
            ))
        if noncf > g:
            issues.append(Issue(
                code="charm-noncf-exceeds-general-slots",
                message=f"{noncf} non-Caste/Favored Charms need General Slots, but only "
                        f"{g} exist; Dedicated Slots hold only Caste/Favored-Attribute Charms.",
            ))
        pool = derive.charm_installation_pool(ruleset, character)
        if install_motes > pool:
            merged = derive.essence_pool_is_merged(ruleset, character)
            where_from = "the Essence pool is" if merged else "Personal Essence is"
            issues.append(Issue(
                code="charm-installation-over-personal",
                message=f"Installed Charms commit {install_motes} motes, but "
                        f"{where_from} only {pool}; they will not all fit.",
            ))
    else:
        # Per pick. Standard: at least charm_min_caste_favored Caste/Favoured picks.
        # Immaculate (DB, p.151): one element tree, no minimum.
        immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
        # Lookshy, p.68: check the bar first, for the more useful message.
        if b.bar_immaculate_charms_at_chargen:
            barred = [cid for cid in charms
                      if (c := ruleset.charms.get(cid)) is not None and c.immaculate]
            if barred:
                immaculate = False
                issues.append(Issue(
                    code="charm-immaculate-barred-at-chargen",
                    message=(f"{len(barred)} Immaculate Order Charm(s) taken, but this "
                             "origin may not learn the Immaculate Martial Arts before "
                             "play begins (p.68); they may be bought with experience."),
                ))
        occult_cf = AbilityName.OCCULT in cf_set
        # The enumeration of the pricing.
        cf_pick_count = sum(
            1 for p in chargen_charm_picks(ruleset, character)
            if p.counts_toward_pool and p.caste_favored
            and ruleset.charms.get(p.charm_id) is not None
        )
        if occult_cf:
            cf_pick_count += sum(1 for sid in spells if ruleset.spells.get(sid) is not None)

        if immaculate:
            # Each chargen Charm must be an Immaculate Charm of one element. The
            # enlightenment Charms (DB p241-242) are permitted too. Each still costs a
            # pick.
            trees: set[str] = set()
            impure = bool(spells) or bool(ox_body) or bool(beastman_gifts)
            for cid in charms:
                charm = ruleset.charms.get(cid)
                if charm is None:
                    continue
                if charm.category == "martial_arts:enlightenment":
                    continue
                if charm.immaculate and charm.element:
                    trees.add(charm.element)
                else:
                    impure = True
            if impure or len(trees) > 1:
                detail = f" ({'/'.join(sorted(trees))})" if len(trees) > 1 else ""
                issues.append(Issue(
                    code="immaculate-single-tree",
                    message=("An Immaculate martial artist must take all chargen Charms "
                             f"from a single elemental tree{detail}; mixing trees, spells, "
                             "Ox-Body, or non-Immaculate Charms is not allowed on the "
                             "Immaculate path (p.151)."),
                ))
        elif cf_pick_count < b.charm_min_caste_favored:
            issues.append(Issue(
                code="charm-caste-favored-min",
                message=f"At least {b.charm_min_caste_favored} of the {b.charm_count} "
                        f"Charms/Spells must be Caste/Favoured; only {cf_pick_count} "
                        "resolve as such.",
            ))
    return issues


def _chargen_mountain_folk_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check Mountain Folk Patterns: Artisan implies Enlightened, and the
    Enlightened cross-Pattern cap (CH6 pp.230-231, 244)."""
    issues: list[Issue] = []
    # --- Mountain Folk Pattern access (CH6 pp.230-231, 244) ------------------- #
    # Enlightened: no more than three of six chargen Charms from the Patterns of the
    # two other castes. An Unenlightened Artisan is illegal.
    if ruleset.exalt_for(character.exalt_type).id == "Mountain-Folk":
        if character.caste == "artisan" and character.origin == "unenlightened":
            issues.append(Issue(
                code="artisan-must-be-enlightened",
                message="All Artisans are Enlightened (CH6 p.230); an Unenlightened "
                        "character cannot take the Artisan Caste.",
            ))
        own_pattern = character.caste           # worker / warrior / artisan
        # The Unenlightened bar is a LIFETIME rule in charm_matches_splat (p.244).
        # This module checks the chargen-only Enlightened cap.
        cross = 0
        for p in chargen_charm_picks(ruleset, character):
            if not p.counts_toward_pool:
                continue
            charm = ruleset.charms.get(p.charm_id)
            pat = _mountain_folk_pattern(charm) if charm is not None else None
            if pat is None:
                continue
            other_caste = pat in ("worker", "warrior", "artisan") and pat != own_pattern
            if other_caste:
                cross += 1
        if character.origin != "unenlightened" and cross > 3:
            issues.append(Issue(
                code="mountain-folk-pattern-cross-cap",
                message=(f"No more than 3 of the 6 chargen Charms may come from another "
                         f"caste's Pattern; {cross} do (CH6 p.230)."),
            ))
    return issues


def _chargen_martial_arts_form_issues(ruleset: RuleSet, b, charms) -> list[Issue]:
    """Check the p.101 cap on chargen Charms from a Sidereal Martial Arts form."""
    issues: list[Issue] = []
    # A "form" is one of three Sidereal styles (Sidereals pp.184-201).
    #
    # ⚠ Use `ma_tier`, NEVER `open_to_tiers`, which includes all Celestial-open
    # styles. A ronin (cap 0) would then have no Celestial Monkey Charm.
    if b.martial_arts_form_charm_cap is not None:
        n_form = sum(
            1 for cid in charms
            if (c := ruleset.charms.get(cid)) is not None
            and c.ma_tier == "Sidereal")
        if n_form > b.martial_arts_form_charm_cap:
            cap = b.martial_arts_form_charm_cap
            issues.append(Issue(
                code="charm-too-many-martial-arts-forms",
                message=(f"{n_form} Charms are from a Sidereal Martial Arts form; at "
                         f"chargen no more than {cap} may be" +
                         (" (a ronin may take none, p.101)." if cap == 0
                          else f" from such forms (p.101).")),
            ))
    return issues


def _chargen_willpower_issues(b, virtues, wp_total: int) -> list[Issue]:
    """Check the Willpower start cap with its Virtue exception, and the hard origin
    ceiling."""
    issues: list[Issue] = []
    if wp_total > b.willpower_start_cap:
        high_virtues = sum(1 for r in virtues.values() if r >= b.willpower_cap_exception_virtue)
        if high_virtues < b.willpower_cap_exception_count:
            issues.append(Issue(
                code="willpower-start-cap",
                message=(f"Willpower starts at {wp_total}; may not exceed "
                         f"{b.willpower_start_cap} unless at least "
                         f"{b.willpower_cap_exception_count} Virtues are "
                         f">= {b.willpower_cap_exception_virtue}."),
            ))
    # The hard ceiling (CH6 p.230) applies even when the exception applies.
    if b.willpower_hard_cap and wp_total > b.willpower_hard_cap:
        issues.append(Issue(
            code="willpower-hard-cap",
            message=(f"Willpower is {wp_total}; this origin may never exceed "
                     f"{b.willpower_hard_cap}."),
        ))
    return issues


def _chargen_merit_trait_issues(character: Character, mf, virtues, wp_forfeited: int) -> list[Issue]:
    """Check the Willpower and Nature rules of held Merits and Flaws, from
    MeritEffects fields (decision 0011)."""
    issues: list[Issue] = []
    if mf.willpower_virtue_margin is not None:
        ceiling = derive.two_highest_virtues(virtues) + mf.willpower_virtue_margin
        if wp_forfeited > ceiling:
            issues.append(Issue(
                code="callous-willpower-cap",
                message=(f"Willpower starts at {wp_forfeited}; a Flaw held caps it at "
                         f"{ceiling} — no more than {mf.willpower_virtue_margin} above "
                         f"the sum of the two highest Virtues."),
            ))
    if mf.willpower_floor and wp_forfeited < mf.willpower_floor:
        issues.append(Issue(
            code="willpower-below-flaw-floor",
            message=(f"Willpower starts at {wp_forfeited}; a Flaw held floors it at "
                     f"{mf.willpower_floor}."),
        ))
    if mf.barred_natures and character.nature in mf.barred_natures:
        issues.append(Issue(
            code="nature-barred-by-flaw",
            message=f"A Flaw held bars the {character.nature} Nature.",
        ))
    for name in mf.nature_requirement_unmet:
        issues.append(Issue(
            code="merit-nature-required", where=name,
            message=(f"{name} may only be purchased or retained with the Nature it "
                     f"requires; this character's Nature is "
                     f"{character.nature or 'unset'}."),
        ))
    return issues


def _chargen_essence_issues(b, mf, essence) -> list[Issue]:
    """Check Essence: the origin floor, the Flaw ceiling, and the creation cap of 5
    (decision 0014)."""
    issues: list[Issue] = []
    # --- Essence forced by a Flaw --------------------------------------------- #
    # Weak Essence: a chargen ceiling only.
    if mf.essence_start_override is not None and essence > mf.essence_start_override:
        issues.append(Issue(
            code="essence-above-flaw-start",
            message=(f"Essence starts at {essence}; a Flaw held reduces the starting "
                     f"rating to {mf.essence_start_override}."),
        ))

    # --- Essence -------------------------------------------------------------- #
    if essence < b.essence_start:
        issues.append(Issue(
            code="essence-below-start",
            message=f"Essence {essence} is below the starting {b.essence_start}.",
        ))
    # The creation ceiling of 5 for all characters. Above 5 is XP only
    # (advancement.raise_essence).
    #
    # ⚠ Not `essence_start_cap` below, which is an origin rule (p.90).
    if essence > elder.DOT_MAX:
        issues.append(Issue(
            code="essence-above-elder-chargen-cap",
            message=(f"Essence {essence} exceeds 5. No character may leave creation "
                     f"with Essence above 5; raise it with experience after the lock."),
        ))
    if b.essence_start_cap and essence > b.essence_start_cap:
        issues.append(Issue(
            code="essence-above-chargen-cap",
            message=f"Essence {essence} exceeds the creation ceiling of "
                    f"{b.essence_start_cap} for this origin.",
        ))
    return issues


def validate_chargen(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Return all chargen issues, and the bonus-point ceiling (core pp.104-105).

    Checks the live traits before the lock and the ChargenSnapshot after it. One
    `_chargen_*_issues` helper per domain, then the total against
    `bonus_point_breakdown`.

    ⚠ Simplification: the Caste/Favoured minimums (10 of 25 dots, 5 of 10 Charms)
    are checked as NECESSARY conditions, not optimized with the free-dot assignment.

    ⚠ A check that applies on both sides of the lock goes in its domain module,
    called from `validate()`. This function runs at chargen only.
    """
    issues: list[Issue] = []
    b = effective_budgets(ruleset, character)
    (attributes, abilities, crafts, virtues, backgrounds, _specialties,
     charms, spells, _combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, _submodules, colleges, thaumaturgy, paths,
     _favored_path, _elemental_powers, _variant_purchases) = _chargen_source(character)

    # Backgrounds with mechanics (CH2 p.65-69).
    #
    # ⚠ Pass `character`. Else the Attribute-sum cap and the ST toggles are skipped.
    issues += background_issues(b, backgrounds, character)

    # Thaumaturgy: Occult gates and Science ceilings.
    issues += thaumaturgy_issues(ruleset, character, thaumaturgy)
    issues += thaumaturgy_chargen_issues(ruleset, character, thaumaturgy)

    cf = _caste_favored(ruleset, character)
    if cf is None:
        # A splat with no castes (core p.103) does not need a caste.
        if splat_has_castes(ruleset, character.exalt_type):
            issues.append(Issue(
                code="unknown-caste", where=str(character.caste),
                message=f"Caste {character.caste} is not in the RuleSet; "
                        "caste/favoured checks skipped.",
            ))
        # A casteless splat still has a Favoured set (core p.103).
        caste_abilities, favored = set(), set(character.favored_abilities)
        expected = favored_ability_count(ruleset, character)
        if len(favored) != expected:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {expected} Favoured abilities, found {len(favored)}.",
            ))
        for ab in sorted(favored, key=lambda a: a.value):
            # Craft is per focus (core p.136): read through ability_rating.
            if ability_rating(character, ab) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))
        issues += mortal_favored_ability_issues(ruleset, character)
    else:
        caste_abilities, favored = cf
        # Favoured: exactly favored_ability_count, none a Caste Ability, >=1 dot each.
        expected_favored = favored_ability_count(ruleset, character)
        if len(favored) != expected_favored:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {expected_favored} Favoured abilities, "
                        f"found {len(favored)}.",
            ))
        overlap = favored & caste_abilities
        if overlap:
            issues.append(Issue(
                code="favored-overlaps-caste",
                message="Favoured abilities may not be Caste abilities: "
                        f"{sorted(a.value for a in overlap)}.",
            ))
        for ab in sorted(favored, key=lambda a: a.value):
            # Craft is per focus (core p.136): read through ability_rating.
            if ability_rating(character, ab) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))
        # Abilities that must be Favored (Lunar, p.90).
        for ab in b.required_favored:
            if ab not in favored:
                issues.append(Issue(
                    code="required-favored-ability", where=ab.value,
                    message=f"{ab.value} must be a Favored Ability for this splat.",
                ))

    cf_set = caste_abilities | favored

    # --- Range checks --------------------------------------------------------- #
    # A Merit or Flaw can move the ceiling of 5 for one Attribute, from MeritEffects
    # (decision 0011).
    mf_caps = merits.merits_and_flaws_calc(ruleset, character)
    issues += _chargen_attribute_range_issues(b, attributes, mf_caps)

    # Dragon-King breed bonuses (PG pp.167-174) add to the stored value.
    #
    # ⚠ Effective dots above 5 cost bonus points (p.175), in `bonus_point_breakdown`.
    # The range check above applies to the STORED value.
    #
    issues += _chargen_caste_favored_attribute_issues(ruleset, character, b, attributes)
    issues += _chargen_ability_dot_issues(b, abilities, crafts, cf_set)
    issues += _chargen_required_ability_issues(ruleset, character, b, abilities, crafts)
    issues += _chargen_virtue_range_issues(b, virtues, mf_caps)

    issues += _chargen_college_issues(ruleset, character, b, colleges)

    issues += _chargen_path_issues(ruleset, character, b, paths, essence)

    issues += _chargen_essence_ceiling_issues(b, attributes, virtues, essence)

    issues += _chargen_spell_circle_issues(ruleset, character, spells)

    issues += _chargen_charm_issues(ruleset, character, b, charms, spells, ox_body,
                                     beastman_gifts, cf_set)

    issues += _chargen_mountain_folk_issues(ruleset, character)

    issues += _chargen_martial_arts_form_issues(ruleset, b, charms)

    # --- Willpower start-cap -------------------------------------------------- #
    # The Flaw rules below use the same total.
    wp_total = derive.two_highest_virtues(virtues) + wp_purchased
    issues += _chargen_willpower_issues(b, virtues, wp_total)

    # --- Willpower rules imposed by a held Flaw ------------------------------- #
    # Callous (ceiling) and Weak-Willed (floor), from MeritEffects (decision 0011).
    # Callous is the exception to decision 0005 (human's ruling).
    mf = merits.merits_and_flaws_calc(ruleset, character)
    wp_forfeited = max(0, wp_total - mf.forfeited_willpower_dots)
    issues += _chargen_merit_trait_issues(character, mf, virtues, wp_forfeited)

    issues += _chargen_essence_issues(b, mf, essence)

    # A splat that needs a Merit for its pool (God-Blooded): without it, Charms,
    # spells and Essence above the start are illegal.
    issues += magic_gate_issues(ruleset, character)
    issues += heritage_origin_issues(ruleset, character)

    # Unallocated free dots, as warnings.
    issues.extend(unspent_budget_issues(ruleset, character))
    issues.extend(merit_issues(ruleset, character))

    issues.extend(check_camp_and_calling(ruleset, character))
    issues.extend(granted_charm_issues(ruleset, character))

    # --- Bonus-point ceiling (numbers from bonus_point_breakdown) ------------- #
    breakdown = bonus_point_breakdown(ruleset, character)
    if breakdown.over_budget:
        issues.append(Issue(
            code="bonus-points-exceeded",
            message=f"Spends {breakdown.total} bonus points; only {breakdown.available} available.",
        ))
    issues.append(Issue(
        code="bonus-points", severity="info",
        message=f"{breakdown.total} of {breakdown.available} bonus points spent.",
    ))
    return issues


def effective_attribute_pools(ruleset: RuleSet, character: Character) -> tuple[int, int, int]:
    """Return the attribute pools: the budget pools, or the heritage override
    (Half-Caste (6, 5, 4), PG p.47; the p.50 summary is a printing error). The one
    read site."""
    caste = ruleset.castes.get(character.caste)
    heritage = caste.heritage_traits if caste is not None else None
    if heritage is not None and heritage.attribute_pools is not None:
        return tuple(heritage.attribute_pools)
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return tuple(b.attribute_pools)
