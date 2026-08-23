"""
engine/validate/budgets.py — chargen point accounting: pools, bonus points, `validate_chargen`.

The other half of the package. Where the domain modules ask "may this character hold
this trait", this module asks "was it PAID for" — and `validate_chargen` is the
roll-up that answers it for a whole sheet.

  * `attribute_pool_assignment` / `effective_attribute_pools` — the 8/6/4 pools.
    Which category receives which pool is the player's priority and is INFERRED
    from the spend, never stored.
  * `two_pool_ability_accounting` — the Mountain Folk two-pool Ability budget.
  * `bonus_point_breakdown` — what each domain's bonus points went on.
  * `unspent_budget_issues` — free dots left on the table, reported as warnings.
  * `validate_chargen` — every chargen predicate, and the roll-up test's second root.

⚠ Chargen accounting reads `_base._chargen_source`, NOT the live traits: once locked,
the frozen snapshot is the truth (decision 0004). Reading a live trait here makes an
XP purchase look like a chargen overspend.

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
    """Yield (ability, rating) pairs for chargen ability accounting. The single
    AbilityName.CRAFT key is dropped and each Craft instance contributes its own
    slot (keyed to CRAFT), so per-focus crafts are budgeted, capped and discounted
    independently like the separate Abilities they are."""
    for ab, rating in abilities.items():
        if ab == AbilityName.CRAFT:
            continue
        yield ab, rating
    for cr in crafts:
        yield AbilityName.CRAFT, cr.rating


def two_pool_ability_accounting(b, character, abilities, crafts, bp_costs=None):
    """The Mountain Folk two-pool Ability accounting (CH6 p.230).

    The free pool (`ability_dots`) funds ANY Ability up to `ability_cap_pre_bp` (3); the
    favored pool (`ability_favored_dots`) funds FAVORED Abilities above that up to the
    chargen ceiling of 5. Dots neither pool covers are bonus points at the ordinary or
    favored tier rate.

    Allocation between the pools is the player's and is not recorded, so this computes
    the cheapest legal assignment: spend the free pool first, ride a Favored Ability's
    remaining dots on the favored pool, and overflow the favored pool (1 BP/dot) rather
    than the free one (2 BP/dot).

    Returns `(within, ability_bp)` — pool dots spent against the combined budget, and
    the bonus-point charge. `ability_bp` is 0 when `bp_costs` is None.

    ⚠ The ONE read site for this rule. `bonus_point_breakdown`, the unspent warning and
    the editor's "N / M dots spent" readout all call it; a second implementation drifts
    from the others silently.
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
    """Bonus points spent on Attributes under caste_favored mode: the three pools
    are assigned in FIXED order to the caste / favored / remaining sets, over-spend
    on the caste and favored sets is charged the discounted
    `attribute_caste_favored` rate, and the remaining set the flat `attribute` rate."""
    caste, favored, remaining = _caste_favored_attribute_sets(ruleset, character)
    pools = list(effective_attribute_pools(ruleset, character))

    def spend(group: set) -> int:
        return sum(attributes.get(a, b.attribute_base) - b.attribute_base for a in group)

    cf_rate = bp_costs.attribute_caste_favored
    return (max(0, spend(caste) - pools[0]) * cf_rate
            + max(0, spend(favored) - pools[1]) * cf_rate
            + max(0, spend(remaining) - pools[2]) * bp_costs.attribute)


def unspent_budget_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Free chargen dots the character has NOT allocated, as non-blocking warnings.

    Covers Attributes, Abilities, Virtues and Backgrounds. Reads the frozen snapshot
    once locked, like the rest of the chargen accounting.

    ⚠ WARNINGS, never errors (human's ruling): an unfinished sheet is incomplete, not
    illegal, and the UI treats severity="warning" as non-blocking. The rest of the
    engine's budget arithmetic is one-sided — every domain charges `max(0, spend -
    budget)` to bonus points and never notices a character who spent too LITTLE, which
    is why a blank sheet read "✓ Legal" without this.

    ⚠ Bonus points are deliberately EXCLUDED: unspent BP are not an omission, and a
    concept may legitimately not want them.
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

    # Attributes: pools are per-GROUP, so leftovers are counted per pool and summed —
    # spending all 13 in one category leaves the other two pools unspent, and both
    # that and the resulting overspend are worth saying.
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

    # Abilities/Virtues/Backgrounds: one flat pool each, and only dots at or below the
    # pre-BP cap count toward it — the same `within` arithmetic bonus_point_breakdown
    # uses, so the two can never disagree about what "spent from the pool" means. The
    # two-pool Mountain Folk shape (CH6 p.230) asks two_pool_ability_accounting, the
    # single read site, so the warning and the billing cannot drift.
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

    # Fetters, for the splats that have them. Same arithmetic as the pools above.
    if b.fetter_dots:
        fetter_within = sum(min(f.rating, b.fetter_cap_pre_bp)
                            for f in character.fetters)
        warn("Fetter", b.fetter_dots - fetter_within, b.fetter_dots)

    # Charms — the one chargen pool counted in PICKS rather than dots, so it does not
    # go through `warn`. The pool is shared with Spells (p.100) and the Immaculate path
    # swaps its size (DB p.151).
    #
    # ⚠ Both expressions must match `bonus_point_breakdown`'s, or the warning and the
    # billing drift. Skipped for the slot economy: an Alchemical buys Slots, not picks.
    # `charm_noun` makes the message say Arcanoi to a ghost.
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
    """Whether core p.103's optional Favoured Ability is actually in play: the ORIGIN
    must allow it and the Storyteller must have switched it on. Both halves matter —
    the page offers it to "heroic mortals" only, so an ordinary mortal does not get one
    however the table's toggle is set, and an Exalt's origin never allows it at all.

    Reads the house rules through `chargen_house_rules`, so a locked sheet keeps the
    answer it was built with even if the table later changes its mind."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return (b.optional_favored_ability
            and chargen_house_rules(character).mortal_favored_ability)


def favored_ability_count(ruleset: RuleSet, character: Character) -> int:
    """How many Favoured Abilities this character must pick — the budget's count, plus
    the one core p.103's optional rule grants a heroic mortal when it is in play."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    total = b.favored_count + (1 if optional_favored_ability_open(ruleset, character) else 0)
    # Prodigy grants "one additional Favored Ability for every time this Merit is
    # purchased", but "characters may not have more than five Favored Abilities in
    # total" (p.21) — which is exactly why the Merit is closed to the splats already at
    # that limit.
    extra = merits.merits_and_flaws_calc(ruleset, character).extra_favored_abilities
    return min(merits.PRODIGY_FAVORED_CAP, total + extra) if extra else total


def mortal_favored_ability_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The price of p.103's optional Favoured Ability: "the character can never have
    any other Ability rated higher than his Favored Ability. The Favored Ability must
    be equal to or greater than every other skill he possesses."

    Only meaningful while the rule is actually in play — an Exalt's Favoured Abilities
    carry no such ceiling ("Exalted do not suffer from this restriction")."""
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
    """One domain's bonus-point spend, for the chargen BP-spend log."""
    domain: str
    points: int


class BonusPointBreakdown(BaseModel):
    """Per-domain bonus-point accounting for the creation allocation. `lines` are
    in display order (every domain present, even at 0); `total` is their sum;
    `available` is the budget (15 by default)."""
    lines: list[BonusPointLine]
    total: int
    available: int

    @property
    def over_budget(self) -> bool:
        return self.total > self.available


def bonus_point_breakdown(ruleset: RuleSet, character: Character) -> BonusPointBreakdown:
    """Compute the bonus points spent in each chargen domain (Exalted 1e pp.104-105).

    The engine computes the accounting; the player does not tag dots. For each
    domain, dots beyond the free budget — or above the pre-bonus cap of 3 — are
    paid from the 15 bonus points at the rates in RuleSet.bonus_costs. Where a
    domain mixes cheap (Caste/Favoured) and dear dots, the *free* dots are assigned
    to the dearest first, the player-favourable minimum. This is the single source
    of the BP totals; validate_chargen consumes it for the ceiling check, and the
    editor renders it as a spend log.
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
    # caste_favored mode (Alchemical, p.60): pools go to the caste / favored /
    # remaining Attribute SETS, not to categories — see _attr_bp_caste_favored.
    if b.attribute_mode == "caste_favored":
        attr_bp = _attr_bp_caste_favored(ruleset, character, b, bp_costs, attributes)
    else:
        # category mode (every other splat): three category spends matched to the
        # 8/6/4 pools. The pool assignment (which category gets which of the sorted
        # pools) is by spend alone; the per-category RATE additionally depends on
        # whether that category is the caste's favored one (Lunar Caste Attributes,
        # p.93 — "4, 3 if a Caste Attribute"). Ability-caste splats have no favored
        # category (caste_attr_category is None), so every category costs the same
        # flat `attribute` rate.
        attr_bp = sum(
            max(0, spend - pool) * (bp_costs.attribute_caste_favored if cat == caste_attr_category
                                     else bp_costs.attribute)
            for cat, spend, pool in attribute_pool_assignment(ruleset, character, b,
                                                              attributes)
        )

    # Dragon-King breed attribute bonuses (PG pp.167-174): the breed's free dots
    # stack ON TOP of the stored value, but each EFFECTIVE dot above 5 must be
    # bought with bonus points at the attribute rate (p.175: "Even after these
    # modifiers are applied, Dragon Kings cannot have any Attributes higher than 5
    # without spending bonus or experience points"). The 2026-08-06 "free past 5"
    # reading was a misunderstanding and is reversed; this charge plus the stored-5
    # range check in validate_chargen is the whole attribute rule. A Pterok's
    # stored Dexterity 5 reads as an effective 7 that costs (7 − 5) × 4 = 8 BP.
    caste_def = ruleset.castes.get(character.caste)
    breed_bonuses = (caste_def.breed_traits.attribute_bonuses
                     if caste_def and caste_def.breed_traits else {})
    for aname, bonus in breed_bonuses.items():
        if bonus:
            effective = attributes.get(aname, b.attribute_base) + bonus
            if effective > 5:
                attr_bp += (effective - 5) * bp_costs.attribute

    # --- Abilities: 25 free dots, pre-BP cap 3 -------------------------------- #
    # Four rate tiers, because a Calling (Cult of the Illuminated, p.90) STACKS with
    # Caste/Favoured rather than replacing it:
    #   both      1 BP per `calling_ability_favored_caste_dots_per_point` dots (0.5/dot)
    #   cf only   bp_costs.ability_favored_caste                              (1/dot)
    #   calling   bp_costs.calling_ability                                    (1/dot)
    #   neither   bp_costs.ability                                            (2/dot)
    # With no Calling the two Calling tiers stay empty, reducing to two-tier pricing.
    cap = b.ability_cap_pre_bp
    call_set = calling_abilities(ruleset, character)
    per_point = max(1, bp_costs.calling_ability_favored_caste_dots_per_point)

    def _tier(ab) -> str:
        cf, call = ab in cf_set, ab in call_set
        return "both" if (cf and call) else "cf" if cf else "calling" if call else "neither"

    if b.ability_favored_dots:
        # TWO-POOL (Mountain Folk, CH6 p.230): the favored pool funds a Favored
        # Ability's dots beyond the free-pool cap, allocated player-favourably — see
        # two_pool_ability_accounting, the ONE read site this, the unspent warning and
        # the editor readout all share.
        _within, ability_bp = two_pool_ability_accounting(
            b, character, abilities, crafts, bp_costs)
    else:
        within_by_tier = {"both": 0, "cf": 0, "calling": 0, "neither": 0}
        above_by_tier = dict(within_by_tier)
        for ab, rating in _ability_slots(abilities, crafts):
            tier = _tier(ab)
            within_by_tier[tier] += min(rating, cap)
            above_by_tier[tier] += max(0, rating - cap)

        # Overflow past the free pool is paid cheapest-first (player-favourable), by
        # EFFECTIVE per-dot rate, so the fractional 'both' tier is spent first.
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

        # The 'both' tier is charged in bulk and rounds UP, matching how specialties
        # already handle a dots-per-point rate (rules-authority call: the page does
        # not say how an odd dot rounds).
        ability_bp = ((paid["both"] + per_point - 1) // per_point
                      + sum(paid[t] * flat_rate[t] for t in order))

    # --- Backgrounds: N free dots, pre-BP cap 3 (above-3 dot costs 2) --------- #
    # `background_rules` (empty for every splat but the Alchemical) can exempt a
    # Background from the cap and make its upper dots cost more than one pool dot each.
    bg_within, above_rates = background_pool_spend(ruleset, character, b, backgrounds,
                                                   bp_costs)
    bg_above_bp = sum(above_rates)
    bg_overflow = max(0, bg_within - background_dots_budget(b, character))
    bg_bp = bg_above_bp + bg_overflow * bp_costs.background

    # --- Virtues: 5 free dots over base 1, pre-BP cap 3 ----------------------- #
    # A Fae-Blooded's ATTUNED Virtue (Virtue Attunement, PG p.74) is priced at two
    # bonus points per dot instead of the splat's three. Attuned dots draw on the free
    # pool LAST (the player-favourable reading), so the discount lands on as many of
    # their priced dots as possible: the pool absorbs the non-attuned dots first, and
    # every attuned dot it cannot then hide is priced at the discounted rate.
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
    # The free pool goes to the NON-attuned within-cap dots first; whatever is left
    # then hides attuned dots, and the remaining attuned ones are priced (and get
    # the discount): min(attuned_within, v_overflow) of the attuned within-cap dots.
    # The free_left bookkeeping keeps that exact when the non-attuned dots do not
    # themselves fill the pool.
    free_left = max(0, b.virtue_dots - (v_within - attuned_within))
    attuned_paid = attuned_above + max(0, attuned_within - free_left)
    virtue_bp = (v_above + v_overflow) * bp_costs.virtue - attuned_paid

    # --- Charms & Spells ------------------------------------------------------ #
    if uses_charm_slots(ruleset, character):
        # Slot economy (Alchemical, p.88-89): you buy SLOTS, not Charm picks — each
        # Slot comes with a free Charm. BP is the cost of slots beyond the free base:
        # extra General slots at bp_costs.charm (6), extra Dedicated at
        # charm_favored_caste (5). The Charms themselves are free.
        g, d, bg, bd = charm_slot_counts(ruleset, character)
        charm_bp = (max(0, g - bg) * bp_costs.charm
                    + max(0, d - bd) * bp_costs.charm_favored_caste)
    else:
        # Per-pick economy (every other splat): one shared Charm/Spell pool (p.100).
        # The Immaculate martial-arts path (DB, p.151) swaps the free pool size and
        # the per-Charm BP row: 5 Immaculate Charms free (vs charm_count), each
        # Immaculate Charm priced from the Immaculate BP row (10/7).
        immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
        free_charm_pool = b.immaculate_charm_count if immaculate else b.charm_count
        occult_cf = AbilityName.OCCULT in cf_set
        # One ladder for every pick, whichever list it lives on — see
        # `charm_pick_bp_costs`. Spells share the pool but are not Charms.
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
    # Same shape as Abilities: own-Maiden Colleges are the cheap dots (6), other
    # houses the dear (8); the free pool absorbs the dearest first, so overflow is
    # paid cheapest-first (player-favourable). Above-cap dots always cost BP.
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
    # The same within/above/overflow shape as Colleges, with two DK differences: the
    # cheap/dear split is per-dot FAVOURED (a Path is favoured by breed element or by
    # `favored_path`, not by house), and the above-3 rate is DOUBLED ("Path | 5 (10
    # if the Path is being raised above 3)", "Breed Path | 4 (8 if raised above 3)").
    # Unused for every splat with `path_dots` 0, which is every non-Dragon-King.
    path_cap = b.path_cap_pre_bp
    path_cheap_within = path_dear_within = path_above_bp = 0
    for pr in paths:
        # The snapshot's favoured Path, not the live character's: once locked, the
        # snapshot is the chargen accounting source (decision 0003), and the choice
        # must not re-price creation if `character.favored_path` ever drifts.
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
    # Unlike every domain above, thaumaturgy has no chargen allowance: "Thaumaturges
    # may spend their bonus points on any combination of these without limitation"
    # (p.113). So the total is simply the sum of the purchase prices — the free-pool
    # arithmetic that shapes the other domains has nothing to absorb here. Sciences
    # price at 0 because the source gives no rate; see ThaumPurchase.priced.
    thaum_purchases_cg = _thaum_purchases_from(ruleset, thaumaturgy)
    thaum_bp = sum(thaum_purchase_bp_costs(
        ruleset, character, thaum_purchases_cg,
        free_picks=magic_for_everyone_grant(ruleset, character)))

    # --- Fetters (ghosts only, E:Ab p.126-127) -------------------------------- #
    # Same `within`/`above` shape as Backgrounds: dots at or below the pre-BP cap come
    # from the pool, dots above it and any pool overflow are bonus points. 0 for every
    # other splat, whose fetter list and `fetter_dots` budget are both empty.
    #
    # There is deliberately no Passion line. Passions are derived from the Virtues and
    # cost nothing at any point (p.283) — see models.character.PassionEntry.
    f_within = sum(min(f.rating, b.fetter_cap_pre_bp) for f in character.fetters)
    f_above = sum(max(0, f.rating - b.fetter_cap_pre_bp) for f in character.fetters)
    f_overflow = max(0, f_within - b.fetter_dots)
    fetter_bp = (f_above + f_overflow) * bp_costs.fetter

    # --- Willpower / Essence -------------------------------------------------- #
    wp_bp = wp_purchased * bp_costs.willpower
    # Essence is usually linear (dot × rate); a splat whose BP table prices it by
    # DESTINATION instead (God-Blooded, p.50: Essence 2* = 5, Essence 3** = 15) sets
    # `essence_by_rating` and the exact-rating price wins.
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
    # Arrays are an Alchemical-only domain (p.89); show the line only for splats
    # that build them, so every other splat's breakdown is unchanged. array_bp is 0
    # whenever the line is omitted (no arrays), so the total is unaffected either way.
    if array_bp or submodule_bp or uses_charm_slots(ruleset, character):
        lines.append(BonusPointLine(domain="Arrays", points=array_bp))
        lines.append(BonusPointLine(domain="Submodules", points=submodule_bp))
    lines += [
        BonusPointLine(domain="Specialties", points=spec_bp),
        BonusPointLine(domain="Willpower", points=wp_bp),
        BonusPointLine(domain="Essence", points=essence_bp),
    ]
    # Colleges only exist for splats that ship them (Sidereal) — omit the line
    # entirely otherwise so every other splat's breakdown is unchanged.
    if b.college_dots > 0 or colleges:
        lines.insert(3, BonusPointLine(domain="Colleges", points=college_bp))
    # Paths, on the same terms: only for splats that have them (Dragon-Kings).
    if b.path_dots > 0 or paths:
        lines.insert(3, BonusPointLine(domain="Paths", points=path_bp))
    # Fetters, on the same terms: only for splats that have them (ghosts), so every
    # other breakdown is byte-identical to before.
    if b.fetter_dots > 0 or character.fetters:
        lines.insert(3, BonusPointLine(domain="Fetters", points=fetter_bp))
    # Thaumaturgy is cross-splat but optional for every splat, so the line appears
    # only once a character has bought something — a Solar who never touches it sees
    # the same breakdown as before. thaum_bp is 0 whenever the line is omitted.
    if thaumaturgy.arts or thaumaturgy.art_specialties or thaumaturgy.sciences \
            or thaumaturgy.rituals or thaumaturgy.formulas:
        lines.append(BonusPointLine(domain="Thaumaturgy", points=thaum_bp))
    # Elemental Powers (PG p.68), on the same terms: one flat line once held, and
    # absent entirely for every other origin/splat so their breakdowns are unchanged.
    elemental_bp = sum(
        ruleset.elemental_powers[pid].bp_cost
        for pid in elemental_powers if pid in ruleset.elemental_powers)
    if elemental_powers:
        lines.append(BonusPointLine(domain="Elemental Powers", points=elemental_bp))
    # Merits & Flaws. A MERIT is a spend at its printed point value; a FLAW is a
    # GRANT that raises the allowance rather than reducing the spend, which is why it
    # lands on `available` and not as a negative line — a negative line would let a
    # Flaw silently pay for an overspend elsewhere in the same total. Oathbound
    # Magic's grant is already net of its same-arena stacking reduction.
    merit_bp = merit_bonus_point_cost(ruleset, character)
    granted = merits.merits_and_flaws_calc(ruleset, character).bonus_point_grant
    if character.merits_flaws or merit_bp:
        lines.append(BonusPointLine(domain="Merits", points=merit_bp))
    total = sum(line.points for line in lines)
    # Inheritance (God-Blooded, p.61): the Background's rating adds bonus points on
    # top of the budget's flat pool — Thin blood +6 … Divine +30. Indexed by rating,
    # empty for every other splat (the term is then 0).
    inheritance_bp = 0
    if b.inheritance_bonus_points:
        rating = min(merits.inheritance_rating(character),
                     len(b.inheritance_bonus_points) - 1)
        inheritance_bp = b.inheritance_bonus_points[rating]
    return BonusPointBreakdown(lines=lines, total=total,
                               available=b.bonus_points + granted + inheritance_bp)


def attribute_pool_assignment(ruleset: RuleSet, character: Character, b, attributes
                              ) -> list[tuple[str, int, int]]:
    """[(category, spend, pool)] for category-mode splats — which of the 8/6/4 pools
    each Attribute category receives, and the dots spent against it.

    Pools are matched to categories BY SPEND rather than declared: the biggest spend
    takes the biggest pool.

    ⚠ That is why Diminished Attributes cannot be a budget delta the way Callous and
    Unskilled are. The forfeit must come off the pool its category ACTUALLY receives,
    which is only known after matching — so matching runs first, on the real spends,
    and the forfeit comes off afterwards.

    ⚠ Accepted consequence (human's ruling): forfeiting dots lowers a category's spend,
    which can drop it to a smaller pool, and the reshuffle can cost bonus points
    elsewhere.
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
    """Attribute ranges. The ceiling is the origin's, which a Merit or Flaw may move
    for one named Attribute; the floor follows a Flaw-lowered ceiling down."""
    issues: list[Issue] = []
    for name, attr in attributes.items():
        # The origin's own ceiling (Enlightened Mountain Folk 7, the Unenlightened's
        # Intelligence 2, CH6 p.230) is the DEFAULT a Merit raises or lowers from; an
        # absent origin cap is the universal 5.
        origin_cap = b.attribute_caps.get(name.value, b.attribute_cap or merits.DOT_MAX)
        cap = mf_caps.attribute_caps.get(name.value, origin_cap)
        # ⚠ The floor must follow the ceiling DOWN. A Flaw's ceiling can sit below the
        # normal chargen floor (Disfigured at four points is "an Appearance of 0",
        # taking away the free dot every Attribute starts with), and an origin FLOOR
        # (Enlightened Mountain Folk's "no Attribute ... lower than three", CH6 p.230)
        # raises it — so a Disfigured Enlightened Jadeborn would otherwise be given an
        # unsatisfiable "3-0" range.
        low = min(b.attribute_min or b.attribute_base, cap)
        if not (low <= attr <= cap):
            span = f"exactly {cap}" if low == cap else f"{low}-{cap}"
            issues.append(Issue(
                code="attribute-range", where=name.value,
                message=f"Attribute {name.value} = {attr}; must be {span} at creation.",
            ))
    return issues


def _chargen_caste_favored_attribute_issues(ruleset: RuleSet, character: Character, b, attributes) -> list[Issue]:
    """caste_favored-mode Attribute legality (Alchemical, p.60): the Favoured count,
    the Caste/Favoured disjointness, and the Caste Attribute minimum."""
    issues: list[Issue] = []
    # --- caste_favored attribute legality (Alchemical, p.60) ------------------ #
    # The three attribute pools go to disjoint SETS: 3 Caste Attributes, 3 chosen
    # Favored Attributes (distinct from Caste), and the rest. Each Caste Attribute
    # must reach attribute_caste_min ("none may have a rating lower than 2").
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
    """The required-minimum Ability floors: the DB Dynastic schooling floor (p.151),
    the Sidereal per-house floor (p.98), the Illuminated camp regimen (p.89), and
    the group-sum floors where a rating is divided among a set of Abilities."""
    issues: list[Issue] = []
    # Each requirement is satisfied by any ONE of its listed Abilities. The budget's
    # exalt-type-keyed list is unioned with the caste's own, because the Sidereal
    # per-house minimums differ per house while the DB floor is aspect-agnostic.
    # A ronin Sidereal keeps a Caste but "has no minimum required Ability scores"
    # (p.100), so that origin suppresses the caste half outright.
    caste_def = ruleset.castes.get(character.caste)
    caste_min = ([] if b.ignore_caste_min_abilities
                 else (caste_def.required_min_abilities if caste_def else []))
    # The training camp's regimen floors (Cult of the Illuminated, p.89) join the
    # union on the same terms as the caste's.
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
    # Group-sum floors — the Mountain Folk Artisan's "•• divided among Craft
    # Abilities" (CH6 p.230), where the SUM over a set of Abilities (each per-focus
    # Craft counting separately, via _ability_slots) must reach the rating. Distinct
    # from the per-ability OR floors above.
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
    """Virtue ranges, with the ceiling a Merit or Flaw may move."""
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
    """Astrological Colleges (Sidereal, p.98): reference integrity, range, and the
    floor on dots in the character's own Maiden's Colleges."""
    issues: list[Issue] = []
    # --- Astrological Colleges (Sidereal, p.98) ------------------------------- #
    # Reference integrity + range + the "at least N dots in the Colleges of his
    # Maiden" floor. Over-budget/over-cap dots are paid from bonus points (see
    # bonus_point_breakdown), so there is no hard total cap here — same as Backgrounds.
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
    """Dragon-King Paths: reference integrity, range, the Essence gate, the Breed/
    Favoured dot floor, and the Favoured-Path choice (PG pp.175-177)."""
    issues: list[Issue] = []
    # --- Dragon-King Paths (PG p.175-177): reference, favour, Essence gate ----- #
    # Paths are a rated Advantage with their own pool. A Dragon King may not start a
    # Path above the pre-BP cap, must put `path_min_breed_favored` dots in Breed or
    # Favoured Paths ("at least 3 must be from Favored or Breed Paths"), may not
    # exceed the Essence gate, and the chosen Favoured Path must not already be one
    # of the breed's two. The gate resolves against the CHARGEN Essence (snapshot or
    # live pre-lock), never `essence_start` — a BP-bought Essence raise lifts it.
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
    """Essence-gated trait ceilings and required Virtue floors (Dragon-Kings,
    PG p.177). No-op for every splat that authors none of these tables."""
    issues: list[Issue] = []
    # --- Essence-gated trait ceilings + required Virtues (Dragon-Kings) ------- #
    # p.177 "Maximum Intelligence and Path Level": Intelligence caps at 1/3/5/6 by
    # Essence (binds at chargen: modern Essence 2 → Int ≤ 3), and row 6 lets a Dragon
    # King raise Abilities, Virtues and Paths to 6. The Ability half is already
    # delivered post-lock by elder.trait_ceiling and needs no chargen check; Virtue-6 is
    # a post-lock unlock (row 6 only), and the ≥1-Valor floor ("at least 1 of which
    # must be put into Valor", p.175) is a required-virtue floor. All no-op for every
    # splat that authors none of these tables.
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
    """The top spell circle is barred at creation for every splat."""
    issues: list[Issue] = []
    # --- Charms & Spells ------------------------------------------------------ #
    # The top spell circle is barred at creation for every splat; the Charm legality
    # then splits by economy — the Alchemical Charm Slot rules (p.88-89) or the
    # per-pick Caste/Favoured minimum / Immaculate single-tree rule (every other
    # splat).
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
    """Charm legality at creation, which splits by economy: the Alchemical Charm Slot
    rules, or the per-pick Caste/Favoured minimum and the Immaculate single-tree
    rule for every other splat."""
    issues: list[Issue] = []
    if uses_charm_slots(ruleset, character):
        # Alchemical Charm Slots (p.88-89): every installed Charm occupies a Slot.
        # non-Caste/Favored Charms may only sit in General Slots; the total installed
        # can't exceed the total Slots; and the committed installation motes can't
        # exceed the Personal Essence pool (p.62 — the Charms must all fit).
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
        personal, _peripheral = derive.essence_pools(ruleset, character)
        if install_motes > personal:
            issues.append(Issue(
                code="charm-installation-over-personal",
                message=f"Installed Charms commit {install_motes} motes, but Personal "
                        f"Essence is only {personal}; they will not all fit.",
            ))
    else:
        # Per-pick path. Standard: >=charm_min_caste_favored of the picks are
        # Caste/Favoured. Immaculate (DB, p.151, triggered by any Immaculate Order
        # Charm): all chargen Charms must instead be one elemental tree, minimum waived.
        immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
        # Lookshy, p.68: an origin may forbid the Immaculate path outright at creation.
        # Checked before the path itself, so the character gets the "you may not take
        # these" message rather than the single-elemental-tree one they cannot satisfy.
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
        # Same enumeration the pricing reads, so a repeatable or granted list can never
        # again be counted by one of the two and missed by the other.
        cf_pick_count = sum(
            1 for p in chargen_charm_picks(ruleset, character)
            if p.counts_toward_pool and p.caste_favored
            and ruleset.charms.get(p.charm_id) is not None
        )
        if occult_cf:
            cf_pick_count += sum(1 for sid in spells if ruleset.spells.get(sid) is not None)

        if immaculate:
            # Every chargen Charm must be an Immaculate Charm of one shared element;
            # spells, Ox-Body, and ordinary ability Charms are not part of any tree.
            # The Immaculate "Enlightenment" Charms (Spirit Sight / Spirit Walking) ARE
            # part of Immaculate martial arts — the required entry to ANY Dragon Path
            # (DB p241-242) — so they're permitted alongside the single elemental tree.
            # They are NOT exempt from the budget: each still costs a normal Charm pick
            # (priced above), only the single-tree check tolerates them.
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
    """Mountain Folk Pattern access: the Artisan/Enlightened coupling and the
    Enlightened cross-Pattern cap on chargen picks (CH6 pp.230-231, 244)."""
    issues: list[Issue] = []
    # --- Mountain Folk Pattern access (CH6 pp.230-231, 244) ------------------- #
    # Jadeborn Charms live in five Patterns (Foundation / Worker / Warrior / Artisan /
    # Enlightened). Unenlightened "can only learn the Charms of their own Caste Pattern
    # or the Foundation Pattern"; Enlightened receive six Charms "no more than three of
    # which may come from the Pattern of another caste". An Enlightened character may
    # learn ANY Pattern (Foundation + Enlightened + own-caste don't count toward the
    # three); only the two OTHER castes' Patterns do. Also the origin/caste coupling:
    # "All of the Artisan Caste are Enlightened" — an Unenlightened Artisan is illegal.
    if ruleset.exalt_for(character.exalt_type).id == "Mountain-Folk":
        if character.caste == "artisan" and character.origin == "unenlightened":
            issues.append(Issue(
                code="artisan-must-be-enlightened",
                message="All Artisans are Enlightened (CH6 p.230); an Unenlightened "
                        "character cannot take the Artisan Caste.",
            ))
        own_pattern = character.caste           # worker / warrior / artisan
        # The Unenlightened bar (own Caste Pattern + Foundation only) is a LIFETIME
        # rule — p.244 states it as ACCESS, not chargen — so it lives in
        # charm_matches_splat / meets_charm_requirements, where both phases read it
        # (an Unenlightened character holding a cross-Pattern Charm is caught as a
        # charm-wrong-splat at chargen). What stays here is the chargen-only half:
        # the Enlightened "no more than three of the six" cap, which counts chargen
        # picks and cannot be expressed as a per-Charm access bar.
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
    """The p.101 cap on chargen Charms drawn from a Sidereal Martial Arts form."""
    issues: list[Issue] = []
    # --- Sidereal Martial Arts form cap (p.101) ------------------------------ #
    # "no more than 3 [chargen Charms] may be from a Sidereal Martial Arts form;
    # ronin ... none". A "form" is one of the three secret Sidereal styles
    # (Sidereals pp.184-201). No cap on any other splat.
    #
    # ⚠ Keyed on `ma_tier`, NEVER on `open_to_tiers`. The latter means "who may learn
    # this", and as a proxy it sweeps in every Celestial-open style when only the
    # three Sidereal ones qualify — Violet Bier, the Immaculate Dragon Paths and
    # Celestial Monkey all count, and a ronin (cap 0) can then learn no Celestial
    # Monkey Charm at all.
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
    """The Willpower start-cap and its two-high-Virtues exception, plus any hard
    origin ceiling that supersedes the exception."""
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
    # A HARD ceiling binds even when the exception clause would let it go higher —
    # Unenlightened Mountain Folk "can never have a permanent Willpower above 6"
    # (CH6 p.230), whatever their Virtues. The exception clause above is superseded:
    # with two Virtues at 4+ an Unenlightened sheet would read 8 and the start-cap
    # check would pass, but the hard cap still binds.
    if b.willpower_hard_cap and wp_total > b.willpower_hard_cap:
        issues.append(Issue(
            code="willpower-hard-cap",
            message=(f"Willpower is {wp_total}; this origin may never exceed "
                     f"{b.willpower_hard_cap}."),
        ))
    return issues


def _chargen_merit_trait_issues(character: Character, mf, virtues, wp_forfeited: int) -> list[Issue]:
    """Willpower ceilings/floors and Nature restrictions imposed by a held Merit or
    Flaw. Reads MeritEffects fields only — no Merit id is named (decision 0011)."""
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
    """Essence: the origin floor, the Flaw-forced ceiling, and the universal creation
    cap of 5 (decision 0014 — past 5 is the post-lock XP path)."""
    issues: list[Issue] = []
    # --- Essence forced by a Flaw --------------------------------------------- #
    # Weak Essence "reduces the character's starting Essence rating to 1", which is a
    # ceiling on creation, not on later advancement — the Flaw exists precisely so the
    # character can raise Essence in play.
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
    # The UNIVERSAL creation ceiling: no character leaves creation with Essence above 5,
    # which is XP-purchasable only after the lock (advancement.raise_essence).
    #
    # ⚠ Distinct from `essence_start_cap` below, a narrower per-origin rule (the
    # Illuminated Solar starts at 3 and may buy up, but "under no circumstances" begins
    # at 6+, p.90). This one binds even for a splat that sets no origin ceiling.
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
    """Every chargen legality predicate, plus the bonus-point ceiling (core pp.104-105).

    Validates the creation allocation — live traits pre-lock, the frozen
    ChargenSnapshot once locked. Delegates one section per printed domain to the
    `_chargen_*_issues` helpers above, then reconciles the total against
    `bonus_point_breakdown`.

    ⚠ Known simplification, flagged to the rules authority: the "10 of 25 Ability dots
    / 5 of 10 Charms must be Caste or Favoured" rules are checked as NECESSARY
    conditions, not jointly optimised with the free-dot assignment. The two interact
    only in rare over-spent builds.

    ⚠ A section that binds on both sides of the lock does NOT belong here — it belongs
    in its domain module, reached from `validate()`. This function runs at chargen only.
    """
    issues: list[Issue] = []
    b = effective_budgets(ruleset, character)
    (attributes, abilities, crafts, virtues, backgrounds, _specialties,
     charms, spells, _combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, _submodules, colleges, thaumaturgy, paths,
     _favored_path, _elemental_powers, _variant_purchases) = _chargen_source(character)

    # Backgrounds that carry mechanics (Alchemical Class/Backing, CH2 p.65-69). No-op
    # for every splat whose Backgrounds are purely narrative.
    #
    # ⚠ `character` must be passed. The Attribute-sum cap (Sidereal Connections) and the
    # per-character ST toggles all read it, and omitting it skips them silently.
    issues += background_issues(b, backgrounds, character)

    # Thaumaturgy: Occult gates on Arts, aspects and rituals; per-Science ceilings.
    # No-op for a character who has bought none, which is every character until the
    # feature is used.
    issues += thaumaturgy_issues(ruleset, character, thaumaturgy)
    issues += thaumaturgy_chargen_issues(ruleset, character, thaumaturgy)

    cf = _caste_favored(ruleset, character)
    if cf is None:
        # A splat with NO castes in the RuleSet is casteless BY DESIGN, not
        # mis-configured: mortals "do not select a caste" (core p.103). Only report a
        # missing caste for a splat that actually has some to choose from, or every
        # mortal sheet carries a permanent spurious error.
        if splat_has_castes(ruleset, character.exalt_type):
            issues.append(Issue(
                code="unknown-caste", where=str(character.caste),
                message=f"Caste {character.caste} is not in the RuleSet; "
                        "caste/favoured checks skipped.",
            ))
        # A casteless splat still HAS a Favoured set — normally empty, but core p.103's
        # optional rule gives a heroic mortal one. Carry it through rather than
        # discarding it, or the count below can never be checked for them.
        caste_abilities, favored = set(), set(character.favored_abilities)
        expected = favored_ability_count(ruleset, character)
        if len(favored) != expected:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {expected} Favoured abilities, found {len(favored)}.",
            ))
        for ab in sorted(favored, key=lambda a: a.value):
            # Craft is per-focus (core p.136): a character with any Craft focus has
            # Craft dots, so read through ability_rating, not the flat abilities map.
            if ability_rating(character, ab) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))
        issues += mortal_favored_ability_issues(ruleset, character)
    else:
        caste_abilities, favored = cf
        # Favoured: exactly favored_ability_count, all distinct from Caste, >=1 dot
        # each. The count is not b.favored_count directly because Prodigy grants extra
        # Favoured Abilities to the splats not already at the five-Ability limit.
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
            # Craft is per-focus (core p.136): a character with any Craft focus has
            # Craft dots, so read through ability_rating, not the flat abilities map.
            if ability_rating(character, ab) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))
        # Abilities the origin/splat forces into the Favored set — Lunar Survival
        # (p.90); empty for splats with no such rule.
        for ab in b.required_favored:
            if ab not in favored:
                issues.append(Issue(
                    code="required-favored-ability", where=ab.value,
                    message=f"{ab.value} must be a Favored Ability for this splat.",
                ))

    cf_set = caste_abilities | favored

    # --- Range checks --------------------------------------------------------- #
    # The universal ceiling is 5; a Merit or Flaw may move it for one named Attribute
    # (Legendary Attribute raises, Disfigured lowers Appearance). Read from
    # MeritEffects rather than branching on an entry, per decision 0011. Shared by the
    # Attribute and Virtue range checks below.
    mf_caps = merits.merits_and_flaws_calc(ruleset, character)
    issues += _chargen_attribute_range_issues(b, attributes, mf_caps)

    # Dragon-King breed attribute bonuses (PG pp.167-174) are free dots ON TOP of the
    # stored value: they consume no pool, and the EFFECTIVE total may pass 5 (a Pterok's
    # stored Dexterity 5 reads as 7).
    #
    # ⚠ Effective dots above 5 are NOT free — each is BP-bought at the attribute rate,
    # charged in `bonus_point_breakdown`, per p.175's "cannot have any Attributes higher
    # than 5 without spending bonus or experience points". The STORED ceiling is the
    # separate thing the range check above enforces.
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
    # Bound here rather than in the helper: the Flaw-imposed Willpower rules below
    # measure against the same total.
    wp_total = derive.two_highest_virtues(virtues) + wp_purchased
    issues += _chargen_willpower_issues(b, virtues, wp_total)

    # --- Willpower rules imposed by a held Flaw ------------------------------- #
    # Callous ceilings Willpower just above the Virtues it let the player sell off, and
    # Weak-Willed floors what its own forfeit may reach. Both read MeritEffects fields
    # rather than naming a Flaw (decision 0011). The Callous ceiling is the sanctioned
    # exception to decision 0005 — the human ruled that Willpower moves with the Virtues
    # for a Callous character, and stays pinned at lock for everyone else.
    mf = merits.merits_and_flaws_calc(ruleset, character)
    wp_forfeited = max(0, wp_total - mf.forfeited_willpower_dots)
    issues += _chargen_merit_trait_issues(character, mf, virtues, wp_forfeited)

    issues += _chargen_essence_issues(b, mf, essence)

    # A Merit-gated splat's magical purchases require the pool unlocked (God-Blooded
    # + Awakened Essence); otherwise Charms, spells and Essence above start are all
    # illegal together, and each reports on its own domain.
    issues += magic_gate_issues(ruleset, character)
    issues += heritage_origin_issues(ruleset, character)

    # Unallocated free dots — warnings, so they never block, but "✓ Legal" no longer
    # claims a blank sheet is finished.
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
    """The character's attribute pools — the budget's, unless the heritage overrides
    them. The Half-Caste heritage sets `attribute_pools` to (6, 5, 4) (PG p.47 prose;
    the p.50 summary's 6/5/3 is a printing error), where every other heritage keeps
    the God-Blooded 6/4/3. One read site so a heritage override cannot land in some
    of the six attribute-pool readers and not the rest."""
    caste = ruleset.castes.get(character.caste)
    heritage = caste.heritage_traits if caste is not None else None
    if heritage is not None and heritage.attribute_pools is not None:
        return tuple(heritage.attribute_pools)
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return tuple(b.attribute_pools)
