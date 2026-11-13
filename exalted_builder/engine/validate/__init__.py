"""
engine/validate/__init__.py — the validation roll-up and the package's public surface.

Pure legality checks: (RuleSet, Character) -> list[Issue]. Where the models guard
*shape* and `derive.py` computes *values*, this package guards *rules* — that the
traits a character holds are legal given the rulebook. No I/O, no mutation; an empty
list means legal for the checks run.

This module holds two things:

  * **`validate()`** — the post-lock roll-up. Each `check_*` in the package must be
    reachable from it, from `validate_chargen` (in `budgets.py`) or from
    `validate_xp` (in `engine/advancement/audit.py`).
    `tests/test_validator_rollup.py` asserts it: a checker dropped from the roll-up
    still passes its own unit tests and stops running.
  * **the facade** — `validate.X` is the ONE public path to each name in the
    package. A rule that moves to a domain module gets a re-export line here.

The rules themselves live in the domain modules, in dependency order:

    _base        Issue, the shared trait readers, effective_budgets
    castes       caste/favoured membership
    charms       access, prerequisites, picks, slots, Ox-Body and Gifts
    backgrounds  pool accounting, catalogues, rating caps, hearthstones
    spells       Sorcery/Necromancy circle access
    combos       Combo legality
    thaumaturgy  Arts, Sciences, Rituals, Formulas (cross-splat, not a splat)
    illuminated  Cult Camps and Callings
    alchemical   Arrays, Submodules, installation motes
    elemental    Dragon-Blooded Elemental Powers
    artifact_checks  the three acquisition channels and the Artifact budget
    merit_checks     Merit legality, cost, and the mortal magic gate
    traits       reference integrity, splat consistency, specialties, Ghost Fetters
    budgets      the chargen point accounting and `validate_chargen`

All thresholds come from the RuleSet (budgets / cost tables), never from code.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import RuleSet

# Re-exported, not defined here. `validate.X` is the ONE public path to each name in
# this package (human's ruling). A domain module is not a second public path. A name
# that moves to a domain module gets a line here.
from ._base import (           # noqa: F401 — re-exported for callers
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
from .alchemical import (      # noqa: F401 — re-exported for callers
    _installation_motes,
    array_installation_motes,
    array_issues,
    eligible_array_charms,
    owns_submodule,
    submodule_block_reason,
    submodule_def,
    validate_arrays,
    validate_submodules,
)
from .combos import (          # noqa: F401 — re-exported for callers
    _COMBO_DURATION,
    _MIXED_COMBO_CASTES,
    combo_issues,
    eligible_combo_charms,
    validate_combos,
)
from .elemental import (       # noqa: F401 — re-exported for callers
    elemental_power_issues,
    elemental_power_shortfalls,
    elemental_powers_available,
    legal_elemental_powers,
    meets_elemental_power_requirements,
)
from .illuminated import (     # noqa: F401 — re-exported for callers
    _granted_charm_minima_met,
    calling_abilities,
    calling_charm_ids,
    calling_for,
    camp_for,
    camp_min_abilities,
    check_camp_and_calling,
    default_camp_and_calling,
    granted_charm_ids,
    granted_charm_issues,
    is_calling_charm,
)
from .spells import (          # noqa: F401 — re-exported for callers
    accessible_circles,
    chargen_barred_circle,
    check_spell_access,
    granted_circles,
    meets_spell_requirements,
)
from .thaumaturgy import (     # noqa: F401 — re-exported for callers
    _MAGIC_FOR_EVERYONE_MAX_LEVEL,
    _ST_CHARGEN_RITUAL_CAP,
    _ST_CHARGEN_SCIENCE_CAP,
    ThaumPurchase,
    _thaum_label,
    _thaum_purchases_from,
    chargen_thaum_purchases,
    magic_for_everyone_eligible,
    magic_for_everyone_grant,
    thaum_art_locked_reason,
    thaum_aspect_locked_reason,
    thaum_formula_level,
    thaum_purchase_bp_costs,
    thaum_purchases,
    thaum_ritual_level,
    thaum_ritual_locked_reason,
    thaum_science_raise_reason,
    thaumaturgy_chargen_issues,
    thaumaturgy_issues,
)
from .budgets import (         # noqa: F401 — re-exported for callers
    BonusPointBreakdown,
    BonusPointLine,
    _ability_slots,
    _attr_bp_caste_favored,
    attribute_pool_assignment,
    bonus_point_breakdown,
    effective_attribute_pools,
    favored_ability_count,
    mortal_favored_ability_issues,
    optional_favored_ability_open,
    two_pool_ability_accounting,
    unspent_budget_issues,
    validate_chargen,
)
from .traits import (          # noqa: F401 — re-exported for callers
    LUNAR_CASTELESS_CASTE_ID,
    LUNAR_CASTELESS_ORIGIN,
    PERMANENT_RESONANCE_TARGET,
    check_caste_splat,
    check_exalt_type,
    check_fetters_and_passions,
    check_lunar_casteless_consistency,
    check_references,
    check_specialties,
    check_splat_consistency,
    heritage_origin_issues,
)
from .artifact_checks import (  # noqa: F401 — re-exported for callers
    _corebook_artifact_issues,
    _missing_merit_issues,
    _purchased_at_chargen_issues,
    check_artifacts,
)
from .backgrounds import (     # noqa: F401 — re-exported for callers
    background_best,
    background_catalogue_for,
    background_dots_budget,
    background_issues,
    background_pool_dots,
    background_pool_spend,
    background_rating,
    background_rating_cap,
    background_rows,
    background_rule,
    background_st_permitted,
    check_hearthstones,
    effective_background_rating,
    gear_affordability,
    trait_rating,
    unmet_trait_prerequisites,
)
from .merit_checks import (    # noqa: F401 — re-exported for callers
    DRIFT_CODES,
    WITHHELD_CHARM_TARGET,
    effective_merit_kind,
    exalt_type_barred_from_tier,
    magic_gate_issues,
    merit_available_to,
    merit_bonus_point_cost,
    merit_cost_options,
    merit_issues,
    merit_points,
    merit_tiers_available,
    pool_requires_unlocking,
    withheld_charm_credits,
)
from .castes import (          # noqa: F401 — re-exported for callers
    _caste_favored,
    _caste_favored_attr_names,
    _caste_favored_attribute_category,
    _caste_favored_attribute_sets,
    caste_attributes,
    caste_favored_abilities,
    splat_has_castes,
)
from .charms import (          # noqa: F401 — re-exported for callers
    DB_MA_ENLIGHTENMENT_PAIRS,
    PERFECTED_LOTUS_MATRIX_ID,
    TIER_ORDER,
    CharmPick,
    _category_ability,
    _charm_attribute_caste_favored,
    _charm_is_caste_favored,
    _charm_name,
    _charm_picks_from,
    _immaculate_path,
    _is_dragon_path_style,
    _min_trait_rating,
    _mountain_folk_pattern,
    _mountain_folk_unenlightened_bar,
    _repeatable_purchase_cap,
    category_available,
    charm_ability_requirements,
    charm_ability_shortfalls,
    charm_count_requirement_label,
    charm_count_shortfalls,
    charm_fits_dedicated_slot,
    charm_learnable_by_splat,
    charm_matches_splat,
    charm_occupies_slot,
    charm_pick_bp_costs,
    charm_pick_count,
    charm_picks,
    charm_restriction_met,
    charm_slot_counts,
    charm_slot_usage,
    charm_virtue_cap_met,
    chargen_charm_picks,
    charms_available,
    charms_depending_on,
    check_beastman_gifts,
    check_charm_prerequisites,
    check_gift_prerequisites,
    check_ox_body,
    check_variant_purchases,
    crossover_alchemical_charm,
    crossover_panoply_xp,
    db_enlightenment_met,
    foreign_charms_caste,
    foreign_charms_open,
    foreign_charms_permitted,
    gift_charm,
    gift_charm_id,
    is_variant_menu_charm,
    known_variant_keys,
    variant_purchase_cap,
    variant_purchases_for,
    gift_purchase_cap,
    gifts_per_purchase,
    has_perfected_lotus_matrix,
    heritage_barred_charm_ids,
    heritage_bars_initiation,
    heritage_charm_access,
    heritage_charms_available,
    heritage_gift_spec,
    heritage_magic_track,
    immaculate_martial_artist,
    is_foreign_charm,
    is_immaculate_charm,
    is_martial_arts_charm,
    is_terrestrial_martial_arts,
    known_gift_keys,
    meets_charm_requirements,
    mountain_folk_cross_pattern,
    origin_granted_charm_ids,
    ox_body_cap,
    ox_body_charm,
    ox_body_charm_id,
    repeatable_cap_trait_name,
    repeatable_cap_unit,
    splat_of,
    splat_uses_charm_slots,
    tier_rank,
    tier_reaches,
    uses_charm_slots,
)


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #


def validate(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Run every check that binds on both sides of the lock and return the combined
    issues. The chargen-only predicates are `validate_chargen`'s (in `budgets.py`);
    the XP audit is `advancement.validate_xp`'s.

    ⚠ Every `check_*` in the package must be reachable from one of those three —
    `tests/test_validator_rollup.py` asserts it. A checker dropped from this list
    keeps passing its own unit tests and silently stops running.
    """
    issues: list[Issue] = []
    issues += check_exalt_type(ruleset, character)
    issues += check_caste_splat(ruleset, character)
    issues += check_lunar_casteless_consistency(ruleset, character)
    issues += check_splat_consistency(ruleset, character)
    issues += check_references(ruleset, character)
    issues += check_charm_prerequisites(ruleset, character)
    issues += check_spell_access(ruleset, character)
    issues += validate_combos(ruleset, character)
    issues += validate_arrays(ruleset, character)
    issues += validate_submodules(ruleset, character)
    issues += check_ox_body(ruleset, character)
    issues += check_beastman_gifts(ruleset, character)
    issues += check_variant_purchases(ruleset, character)
    issues += check_specialties(ruleset, character)
    issues += check_fetters_and_passions(ruleset, character)
    issues += check_artifacts(ruleset, character)
    issues += check_hearthstones(ruleset, character)
    # The Background rules with `bind_post_lock` (human's rulings). The other caps are
    # in `validate_chargen`: the story changes Backgrounds. Reads the LIVE
    # Backgrounds: Backgrounds have no XP, thus the snapshot does not apply.
    if character.chargen_locked:
        issues += background_issues(effective_budgets(ruleset, character),
                                    character.backgrounds, character, post_lock=True)
        # The Merit gates that measure something the story can change after the
        # purchase — an artifact lost, a Background dropped, a trait cursed down.
        # Warnings, not errors: the story can make this state (human's ruling). The
        # frozen-choice gates stay chargen-only.
        issues += merit_issues(ruleset, character, post_lock=True)
    # Elemental Powers on BOTH sides of the lock (the house bug). Reads the LIVE
    # `character.elemental_powers`: the snapshot has only the chargen picks.
    issues += elemental_power_issues(ruleset, character, character.elemental_powers)
    return issues
