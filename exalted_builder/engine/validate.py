"""
engine/validate.py — pure legality checks: (RuleSet, Character) -> issues.

Where the models guard *shape* and derive.py computes *values*, this module
guards *rules*: that the traits a character actually holds are legal given the
rulebook. Pure — no I/O, no mutation; it reads the RuleSet and the Character and
returns a list of `Issue`s (empty == legal for the checks run).

Implemented so far:
  * Reference integrity — every Charm/Spell id on the character exists in the set.
  * Charm prerequisites — min essence, min ability, and the AND-of-OR Charm
    prerequisite graph.
  * Spell-circle access — a known Spell requires a known Charm that grants its
    Sorcery circle.

NOT yet implemented: chargen budget predicates (attribute pools, ability dots,
caste/favoured minimums, Charm counts, bonus-point reconciliation) and the XP-log
reconciliation. Those depend on design decisions still open with the rules
authority; see `validate_chargen` placeholder.

All thresholds come from the RuleSet (budgets / cost tables), never hardcoded, so
correcting the data corrects the engine.
"""

from __future__ import annotations

from pydantic import BaseModel

from ..models.character import Character
from ..models.rules import (
    AbilityName,
    AttributeName,
    CharmType,
    RuleSet,
    SpellCircle,
    VirtueName,
)
from . import derive

# Attribute categories and the order Strength/Dexterity/Stamina etc. (core p.104).
# Which category receives which of the 8/6/4 pools is the player's priority and is
# inferred from the spend, not stored — so this is just the membership grouping.
ATTRIBUTE_CATEGORIES: dict[str, tuple[AttributeName, ...]] = {
    "Physical": (AttributeName.STRENGTH, AttributeName.DEXTERITY, AttributeName.STAMINA),
    "Social": (AttributeName.CHARISMA, AttributeName.MANIPULATION, AttributeName.APPEARANCE),
    "Mental": (AttributeName.PERCEPTION, AttributeName.INTELLIGENCE, AttributeName.WITS),
}


class Issue(BaseModel):
    """One legality finding. `code` is a stable machine tag; `where` locates the
    offending trait (a Charm/Spell id, an ability name, etc.)."""
    code: str
    message: str
    where: str = ""
    severity: str = "error"        # "error" | "warning"


# --------------------------------------------------------------------------- #
# Reference integrity
# --------------------------------------------------------------------------- #

def check_references(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Every Charm/Spell id the character holds must resolve in the RuleSet.
    Equipment is an inline copy by design and is intentionally not checked."""
    issues: list[Issue] = []
    for cid in character.charms:
        if cid not in ruleset.charms:
            issues.append(Issue(
                code="unknown-charm", where=cid,
                message=f"Character holds unknown Charm id {cid!r}.",
            ))
    for sid in character.spells:
        if sid not in ruleset.spells:
            issues.append(Issue(
                code="unknown-spell", where=sid,
                message=f"Character holds unknown Spell id {sid!r}.",
            ))
    return issues


# --------------------------------------------------------------------------- #
# Charm prerequisites
# --------------------------------------------------------------------------- #

def _category_ability(category: str) -> AbilityName | None:
    """Resolve a Charm `category` to the Ability that gates its minimum. A plain
    ability is itself (e.g. 'melee'); a Martial Arts style uses the convention
    'martial_arts:<style>' (e.g. 'martial_arts:tiger') and resolves to Martial
    Arts. Anything else (e.g. 'sorcery') has no single gating ability -> None."""
    base = category.split(":", 1)[0]      # 'martial_arts:tiger' -> 'martial_arts'
    try:
        return AbilityName(base)
    except ValueError:
        return None


def check_charm_prerequisites(ruleset: RuleSet, character: Character) -> list[Issue]:
    """For each *known* Charm, verify min essence, min ability, and the AND-of-OR
    Charm prerequisite graph against the Charms the character knows. Unknown ids
    are skipped here (reported by check_references)."""
    issues: list[Issue] = []
    known = set(character.charms)
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue

        if character.essence_rating < charm.min_essence:
            issues.append(Issue(
                code="charm-min-essence", where=cid,
                message=(f"{charm.name}: requires Essence {charm.min_essence}, "
                         f"character has {character.essence_rating}."),
            ))

        ability = _category_ability(charm.category)
        if ability is not None:
            rating = character.abilities.get(ability, 0)
            if rating < charm.min_ability:
                issues.append(Issue(
                    code="charm-min-ability", where=cid,
                    message=(f"{charm.name}: requires {ability.value} "
                             f"{charm.min_ability}, character has {rating}."),
                ))

        # AND-of-OR: every inner group must be satisfied by at least one known id.
        for group in charm.prerequisites:
            if not any(req in known for req in group):
                needed = " or ".join(
                    ruleset.charms[r].name if r in ruleset.charms else r for r in group)
                issues.append(Issue(
                    code="charm-prerequisite", where=cid,
                    message=f"{charm.name}: unmet prerequisite — needs {needed}.",
                ))
    return issues


def meets_charm_requirements(ruleset: RuleSet, character: Character, charm) -> bool:
    """Whether the character could legally learn `charm` *right now*: min essence,
    min ability (when the category resolves to an ability), and every AND-of-OR
    prerequisite group satisfied by an already-known Charm. The forward-looking
    counterpart to check_charm_prerequisites; used by the charm-tree picker to
    decide which Charms are currently selectable."""
    if character.essence_rating < charm.min_essence:
        return False
    ability = _category_ability(charm.category)
    if ability is not None and character.abilities.get(ability, 0) < charm.min_ability:
        return False
    known = set(character.charms)
    return all(any(req in known for req in group) for group in charm.prerequisites)


def charms_depending_on(ruleset: RuleSet, character: Character, charm_id: str) -> list[str]:
    """Names of currently-owned Charms that would lose a prerequisite if `charm_id`
    were dropped — i.e. they list it in an AND-of-OR group with no other owned
    alternative. Empty means the Charm is safe to remove. Used by the picker to
    keep the owned set internally consistent (remove leaves first)."""
    remaining = set(character.charms) - {charm_id}
    blockers = []
    for oid in character.charms:
        if oid == charm_id:
            continue
        charm = ruleset.charms.get(oid)
        if charm is None:
            continue
        if any(charm_id in group and not any(r in remaining for r in group)
               for group in charm.prerequisites):
            blockers.append(charm.name)
    return blockers


# --------------------------------------------------------------------------- #
# Spell-circle access
# --------------------------------------------------------------------------- #

def granted_sorcery_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """The set of Sorcery circles the character can cast in, taken from the
    `grants_sorcery_circle` of every known initiation Charm."""
    return {
        ruleset.charms[cid].grants_sorcery_circle
        for cid in character.charms
        if cid in ruleset.charms and ruleset.charms[cid].grants_sorcery_circle is not None
    }


def meets_spell_requirements(ruleset: RuleSet, character: Character, spell,
                             *, chargen: bool = True) -> bool:
    """Whether the character could learn `spell` right now: a known Charm must grant
    its circle, and at chargen the Solar Circle is barred (core p.100). The
    forward-looking counterpart to check_spell_access; used by the spell picker."""
    if chargen and spell.circle == SpellCircle.SOLAR:
        return False
    return spell.circle in granted_sorcery_circles(ruleset, character)


def check_spell_access(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A known Spell requires a known Charm whose `grants_sorcery_circle` matches
    the Spell's circle.

    Exact-circle match is correct for 1e (core pp.191): the three initiation
    Charms form a prerequisite chain — Celestial Circle Sorcery requires
    Terrestrial, Solar requires Celestial — so a higher-circle sorcerer always
    also holds the lower Charms (enforced by check_charm_prerequisites) and can
    cast lower-circle spells through them. No separate circle-nesting rule is
    needed here; the prerequisite chain provides it.
    """
    granted = granted_sorcery_circles(ruleset, character)
    issues: list[Issue] = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        if spell.circle not in granted:
            issues.append(Issue(
                code="spell-circle", where=sid,
                message=(f"{spell.name}: no known Charm grants the "
                         f"{spell.circle.value} circle."),
            ))
    return issues


# --------------------------------------------------------------------------- #
# Combos
# --------------------------------------------------------------------------- #

# Only Charms of instant duration may be Comboed (core p.213). Compared against
# Charm.duration, whose instant value is the model default "Instant".
_COMBO_DURATION = "Instant"


def combo_issues(ruleset: RuleSet, character: Character, combo) -> list[Issue]:
    """Legality findings for a single Combo (core pp.213-214): two or more *known*
    Charms of instant duration, no Charm twice, at most one Simple and at most one
    Extra Action Charm. `where` is the Combo's name. The picker uses this per-Combo;
    validate_combos aggregates it over the character."""
    issues: list[Issue] = []
    known = set(character.charms)
    where = combo.name or "(unnamed combo)"
    if len(combo.charm_ids) < 2:
        issues.append(Issue(
            code="combo-too-small", where=where,
            message=f"Combo {where!r} has {len(combo.charm_ids)} Charm(s); a Combo "
                    "must combine at least two.",
        ))
    seen: set[str] = set()
    simple = extra_action = 0
    for cid in combo.charm_ids:
        if cid in seen:
            issues.append(Issue(
                code="combo-duplicate-charm", where=where,
                message=f"Combo {where!r} includes {cid!r} more than once; a Combo "
                        "may not repeat a Charm.",
            ))
            continue
        seen.add(cid)
        if cid not in known:
            issues.append(Issue(
                code="combo-unknown-charm", where=where,
                message=f"Combo {where!r} includes {cid!r}, which the character "
                        "does not know.",
            ))
            continue
        charm = ruleset.charms.get(cid)
        if charm is None:                 # known id absent from the set: check_references reports it
            continue
        if charm.duration != _COMBO_DURATION:
            issues.append(Issue(
                code="combo-non-instant", where=where,
                message=f"Combo {where!r}: {charm.name} has {charm.duration} duration; "
                        "Combos may only contain instant-duration Charms.",
            ))
        if charm.type == CharmType.SIMPLE:
            simple += 1
        elif charm.type == CharmType.EXTRA_ACTION:
            extra_action += 1
    if simple > 1:
        issues.append(Issue(
            code="combo-multiple-simple", where=where,
            message=f"Combo {where!r} has {simple} Simple Charms; a Combo may "
                    "contain at most one.",
        ))
    if extra_action > 1:
        issues.append(Issue(
            code="combo-multiple-extra-action", where=where,
            message=f"Combo {where!r} has {extra_action} Extra Action Charms; a "
                    "Combo may contain at most one.",
        ))
    return issues


def eligible_combo_charms(ruleset: RuleSet, character: Character) -> list[str]:
    """Ids of the character's known Charms that may legally go in a Combo — i.e.
    those of instant duration (core p.213). Order follows the character's Charm
    list. The picker offers these when adding a Charm to a Combo."""
    out: list[str] = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.duration == _COMBO_DURATION:
            out.append(cid)
    return out


def validate_combos(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every Combo the character holds (core pp.213-214). The
    Storyteller veto of specific Combos and the in-play activation rules are out of
    scope here; the bonus-point cost is accounted in validate_chargen. Operates on
    the character's current Charms/Combos (like the other reference checks)."""
    issues: list[Issue] = []
    for combo in character.combos:
        issues += combo_issues(ruleset, character, combo)
    return issues


# --------------------------------------------------------------------------- #
# Chargen (not yet implemented — see module docstring)
# --------------------------------------------------------------------------- #

def _caste_favored(ruleset: RuleSet, character: Character) -> tuple[set, set] | None:
    """(caste_abilities, favored_abilities) as sets, or None if the caste is not
    in the RuleSet (caller emits an issue and skips caste-dependent checks)."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return None
    return set(caste_def.caste_abilities), set(character.favored_abilities)


def caste_favored_abilities(ruleset: RuleSet, character: Character) -> set[AbilityName]:
    """The character's Caste ∪ Favoured abilities — the set that earns the discount
    on Ability/Charm/spell costs. Falls back to just the Favoured set if the caste
    is unknown to the RuleSet. Shared by chargen and XP costing."""
    cf = _caste_favored(ruleset, character)
    if cf is None:
        return set(character.favored_abilities)
    caste_abilities, favored = cf
    return caste_abilities | favored


def validate_chargen(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Chargen budget predicates and bonus-point accounting (Exalted 1e core,
    pp.104-105). Validates the creation allocation: current traits pre-lock, or
    the frozen ChargenSnapshot once locked.

    Bonus-point accounting (the engine computes it; the player does not tag dots).
    For each domain, dots beyond the free budget — or above the pre-bonus cap of 3
    — are paid from the 15 bonus points at the rates in RuleSet.bonus_costs, and
    the total must not exceed the budget. Where a domain has cheap (Caste/Favoured)
    and dear dots, the *free* dots are assigned to the dearest first, i.e. the
    player-favourable minimum. One known simplification, flagged for the rules
    authority: the "10 of 25 Ability dots / 5 of 10 Charms must be Caste or
    Favoured" rules are checked as necessary conditions (enough Caste/Favoured
    dots exist) rather than jointly optimised with the free-dot assignment; the
    two only interact in rare over-spent builds.

    Specialties honour the p.105 Caste/Favoured discount (N dots per BP); see the
    Specialties block for the one accounting choice it entails.
    """
    issues: list[Issue] = []
    b = ruleset.budgets
    bp_costs = ruleset.bonus_costs

    # Source of truth: the frozen snapshot once locked, else current traits.
    snap = character.chargen_snapshot
    attributes = snap.attributes if snap else character.attributes
    abilities = snap.abilities if snap else character.abilities
    virtues = snap.virtues if snap else character.virtues
    backgrounds = snap.backgrounds if snap else character.backgrounds
    specialties = snap.specialties if snap else character.specialties
    charms = snap.charms if snap else character.charms
    spells = snap.spells if snap else character.spells
    combos = snap.combos if snap else character.combos
    essence = snap.essence_rating if snap else character.essence_rating
    wp_purchased = snap.willpower_purchased if snap else character.willpower_purchased

    cf = _caste_favored(ruleset, character)
    if cf is None:
        issues.append(Issue(
            code="unknown-caste", where=str(character.caste),
            message=f"Caste {character.caste} is not in the RuleSet; "
                    "caste/favoured checks skipped.",
        ))
        caste_abilities, favored = set(), set()
    else:
        caste_abilities, favored = cf
        # Favoured: exactly favored_count, all distinct from Caste, >=1 dot each.
        if len(favored) != b.favored_count:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {b.favored_count} Favoured abilities, "
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
            if abilities.get(ab, 0) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))

    cf_set = caste_abilities | favored
    total_bp = 0

    # --- Attributes: three category spends matched to the 8/6/4 pools --------- #
    for name, attr in attributes.items():
        if not (1 <= attr <= 5):
            issues.append(Issue(
                code="attribute-range", where=name.value,
                message=f"Attribute {name.value} = {attr}; must be 1-5 at creation.",
            ))
    spends = sorted(
        (sum(attributes[a] - b.attribute_base for a in attrs)
         for attrs in ATTRIBUTE_CATEGORIES.values()),
        reverse=True,
    )
    pools = sorted(b.attribute_pools, reverse=True)
    attr_overflow = sum(max(0, s - p) for s, p in zip(spends, pools))
    total_bp += attr_overflow * bp_costs.attribute

    # --- Abilities: 25 free dots, pre-BP cap 3, >=10 Caste/Favoured ----------- #
    cap = b.ability_cap_pre_bp
    cheap_within = dear_within = above_bp = 0
    for ab, rating in abilities.items():
        if not (0 <= rating <= 5):
            issues.append(Issue(
                code="ability-range", where=ab.value,
                message=f"Ability {ab.value} = {rating}; must be 0-5 at creation.",
            ))
        within = min(rating, cap)
        above = max(0, rating - cap)
        rate = bp_costs.ability_favored_caste if ab in cf_set else bp_costs.ability
        above_bp += above * rate
        if ab in cf_set:
            cheap_within += within
        else:
            dear_within += within
    if cheap_within < b.ability_min_caste_favored:
        issues.append(Issue(
            code="ability-caste-favored-min",
            message=f"At least {b.ability_min_caste_favored} of the {b.ability_dots} "
                    f"Ability dots must be Caste/Favoured; only {cheap_within} are.",
        ))
    overflow = max(0, (cheap_within + dear_within) - b.ability_dots)
    overflow_cheap = min(overflow, cheap_within)         # cheapest dots paid first
    ability_bp = (above_bp
                  + overflow_cheap * bp_costs.ability_favored_caste
                  + (overflow - overflow_cheap) * bp_costs.ability)
    total_bp += ability_bp

    # --- Backgrounds: 7 free dots, pre-BP cap 3 (above-3 dot costs 2) --------- #
    bg_within = bg_above_bp = 0
    for bg in backgrounds:
        bg_within += min(bg.rating, b.background_cap_pre_bp)
        bg_above_bp += max(0, bg.rating - b.background_cap_pre_bp) * bp_costs.background_above_3
    bg_overflow = max(0, bg_within - b.background_dots)
    total_bp += bg_above_bp + bg_overflow * bp_costs.background

    # --- Virtues: 5 free dots over base 1, pre-BP cap 3 ----------------------- #
    v_within = v_above = 0
    for v, rating in virtues.items():
        if not (1 <= rating <= 5):
            issues.append(Issue(
                code="virtue-range", where=v.value,
                message=f"Virtue {v.value} = {rating}; must be 1-5 at creation.",
            ))
        v_within += max(0, min(rating, b.virtue_cap_pre_bp) - b.virtue_base)
        v_above += max(0, rating - b.virtue_cap_pre_bp)
    v_overflow = max(0, v_within - b.virtue_dots)
    total_bp += (v_above + v_overflow) * bp_costs.virtue

    # --- Charms & Spells: one shared pool of 10, >=5 Caste/Favoured ----------- #
    # p.100: a spell may be taken in place of a Charm pick (1:1), costs the same as
    # a Charm in bonus points, and gets the Caste/Favoured discount when Occult is
    # Caste/Favoured. So Charms and spells share the free pool and the BP rates; a
    # spell counts as a Caste/Favoured pick iff Occult is Caste/Favoured. Solar
    # Circle spells may not be taken at creation at all.
    occult_cf = AbilityName.OCCULT in cf_set
    cf_pick_count = 0          # Charms + spells that count as Caste/Favoured
    for cid in charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ability = _category_ability(charm.category)   # resolves 'martial_arts:<style>' too
        if ability is not None and ability in cf_set:
            cf_pick_count += 1
    for sid in spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        if spell.circle == SpellCircle.SOLAR:
            issues.append(Issue(
                code="spell-solar-circle-chargen", where=sid,
                message=f"{spell.name}: Solar Circle spells may not be taken at "
                        "character creation.",
            ))
        if occult_cf:
            cf_pick_count += 1
    if cf_pick_count < b.charm_min_caste_favored:
        issues.append(Issue(
            code="charm-caste-favored-min",
            message=f"At least {b.charm_min_caste_favored} of the {b.charm_count} "
                    f"Charms/Spells must be Caste/Favoured; only {cf_pick_count} "
                    "resolve as such.",
        ))
    pick_extra = max(0, len(charms) + len(spells) - b.charm_count)
    extra_cheap = min(pick_extra, cf_pick_count)         # cheapest picks paid first
    total_bp += (extra_cheap * bp_costs.charm_favored_caste
                 + (pick_extra - extra_cheap) * bp_costs.charm)

    # --- Combos: starting with a Combo costs BP = its number of Charms (p.213) - #
    # Legality (instant duration, one Simple/Extra Action, etc.) is checked in
    # validate_combos; here we only account the bonus-point cost.
    total_bp += sum(len(combo.charm_ids) for combo in combos)

    # --- Specialties: 1 BP/dot; Caste/Favoured get N dots per BP (p.105) ------ #
    # Caste/Favoured dots are pooled before the round-up, the player-favourable
    # reading of "2 per 1" (two separate 1-dot specialties cost 1 BP together, not
    # 1 each). This pooling is the one accounting choice here worth confirming.
    cf_spec_dots = sum(s.rating for s in specialties if s.ability in cf_set)
    other_spec_dots = sum(s.rating for s in specialties if s.ability not in cf_set)
    per_point = bp_costs.specialty_favored_caste_dots_per_point
    cf_spec_bp = (cf_spec_dots + per_point - 1) // per_point   # round up
    total_bp += other_spec_dots * bp_costs.specialty + cf_spec_bp

    # --- Willpower: purchased dots, plus the start-cap rule -------------------- #
    total_bp += wp_purchased * bp_costs.willpower
    wp_total = derive.two_highest_virtues(virtues) + wp_purchased
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

    # --- Essence -------------------------------------------------------------- #
    if essence < b.essence_start:
        issues.append(Issue(
            code="essence-below-start",
            message=f"Essence {essence} is below the starting {b.essence_start}.",
        ))
    total_bp += max(0, essence - b.essence_start) * bp_costs.essence

    # --- Merits & Flaws: Merits cost BP; Flaws grant BP (capped) -------------- #
    total_bp += sum(mf.points for mf in character.merits_flaws if not mf.is_flaw)
    flaw_points = sum(mf.points for mf in character.merits_flaws if mf.is_flaw)
    flaw_credit = min(flaw_points, b.bonus_points_flaw_cap)
    available = b.bonus_points + flaw_credit
    if flaw_points > b.bonus_points_flaw_cap:
        issues.append(Issue(
            code="flaw-credit-capped", severity="warning",
            message=(f"Flaws are worth {flaw_points} points but only "
                     f"{b.bonus_points_flaw_cap} extra bonus points may be gained from Flaws."),
        ))

    # --- Bonus-point ceiling -------------------------------------------------- #
    if total_bp > available:
        issues.append(Issue(
            code="bonus-points-exceeded",
            message=f"Spends {total_bp} bonus points; only {available} available.",
        ))
    flaw_note = f" (15 + {flaw_credit} from Flaws)" if flaw_credit else ""
    issues.append(Issue(
        code="bonus-points", severity="info",
        message=f"{total_bp} of {available} bonus points spent{flaw_note}.",
    ))
    return issues


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #

def validate(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Run all *implemented* checks and return the combined issues. Chargen
    predicates are excluded until designed."""
    issues: list[Issue] = []
    issues += check_references(ruleset, character)
    issues += check_charm_prerequisites(ruleset, character)
    issues += check_spell_access(ruleset, character)
    issues += validate_combos(ruleset, character)
    return issues
