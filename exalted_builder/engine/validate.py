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

# The one repeatable Charm in 1e core. Bought once per dot of Endurance, each
# purchase choosing a health-level package; stored on Character.ox_body, not in
# Character.charms (so the count is representable).
OX_BODY_ID = "solar.endurance.ox-body-technique"


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


def craft_rating(character: Character) -> int:
    """The effective Craft Ability rating: the highest of the character's per-focus
    Craft instances (core p.136), or 0 if they have none. A Craft Charm's minimum
    Ability is met by the best craft a character possesses."""
    return max((c.rating for c in character.crafts), default=0)


def ability_rating(character: Character, ability: AbilityName) -> int:
    """A character's rating in `ability`, reading Craft from its per-focus instances
    rather than the (unused) AbilityName.CRAFT dot."""
    if ability == AbilityName.CRAFT:
        return craft_rating(character)
    return character.abilities.get(ability, 0)


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
            rating = ability_rating(character, ability)
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
    if ability is not None and ability_rating(character, ability) < charm.min_ability:
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
# Ox-Body Technique (repeatable Charm)
# --------------------------------------------------------------------------- #

def ox_body_cap(ruleset: RuleSet, character: Character) -> int:
    """Maximum number of Ox-Body Technique purchases: once per dot of the Charm's
    `repeatable_cap_ability` (Endurance). 0 if the Charm or its cap ability is
    absent. Used by both the engine and the picker to gate purchases."""
    charm = ruleset.charms.get(OX_BODY_ID)
    if charm is None or not charm.repeatable_cap_ability:
        return 0
    try:
        cap_ability = AbilityName(charm.repeatable_cap_ability)
    except ValueError:
        return 0
    return character.abilities.get(cap_ability, 0)


def check_ox_body(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of the character's Ox-Body purchases: at most one per dot of
    Endurance (core p.170), every chosen package a real variant, and the Charm's
    min essence met. The per-purchase bonus-point/XP cost is accounted elsewhere
    (validate_chargen / costs). Empty when no purchases."""
    issues: list[Issue] = []
    purchases = character.ox_body
    if not purchases:
        return issues
    charm = ruleset.charms.get(OX_BODY_ID)
    if charm is None:
        issues.append(Issue(
            code="ox-body-unknown", where=OX_BODY_ID,
            message="Character has Ox-Body purchases but the Charm is not in the RuleSet.",
        ))
        return issues
    cap = ox_body_cap(ruleset, character)
    if len(purchases) > cap:
        issues.append(Issue(
            code="ox-body-over-cap", where=OX_BODY_ID,
            message=(f"Ox-Body Technique bought {len(purchases)} times; it may be "
                     f"bought at most once per dot of Endurance ({cap})."),
        ))
    if character.essence_rating < charm.min_essence:
        issues.append(Issue(
            code="ox-body-min-essence", where=OX_BODY_ID,
            message=(f"Ox-Body Technique requires Essence {charm.min_essence}, "
                     f"character has {character.essence_rating}."),
        ))
    valid_keys = {v.key for v in charm.variants}
    for p in purchases:
        if p.variant not in valid_keys:
            issues.append(Issue(
                code="ox-body-bad-variant", where=p.variant,
                message=f"Ox-Body Technique: unknown health-level package {p.variant!r}.",
            ))
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


def _chargen_source(character: Character):
    """The traits chargen accounting reads: the frozen snapshot once locked, else
    the current (pre-lock) traits. Returned as a flat tuple in a fixed order."""
    snap = character.chargen_snapshot
    return (
        snap.attributes if snap else character.attributes,
        snap.abilities if snap else character.abilities,
        snap.crafts if snap else character.crafts,
        snap.virtues if snap else character.virtues,
        snap.backgrounds if snap else character.backgrounds,
        snap.specialties if snap else character.specialties,
        snap.charms if snap else character.charms,
        snap.spells if snap else character.spells,
        snap.combos if snap else character.combos,
        snap.ox_body if snap else character.ox_body,
        snap.essence_rating if snap else character.essence_rating,
        snap.willpower_purchased if snap else character.willpower_purchased,
    )


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
    b = ruleset.budgets
    bp_costs = ruleset.bonus_costs
    (attributes, abilities, crafts, virtues, backgrounds, specialties,
     charms, spells, combos, ox_body, essence, wp_purchased) = _chargen_source(character)

    cf = _caste_favored(ruleset, character)
    cf_set = (cf[0] | cf[1]) if cf is not None else set()

    # --- Attributes: three category spends matched to the 8/6/4 pools --------- #
    spends = sorted(
        (sum(attributes[a] - b.attribute_base for a in attrs)
         for attrs in ATTRIBUTE_CATEGORIES.values()),
        reverse=True,
    )
    pools = sorted(b.attribute_pools, reverse=True)
    attr_bp = sum(max(0, s - p) for s, p in zip(spends, pools)) * bp_costs.attribute

    # --- Abilities: 25 free dots, pre-BP cap 3 -------------------------------- #
    cap = b.ability_cap_pre_bp
    cheap_within = dear_within = above_bp = 0
    for ab, rating in _ability_slots(abilities, crafts):
        within = min(rating, cap)
        above = max(0, rating - cap)
        rate = bp_costs.ability_favored_caste if ab in cf_set else bp_costs.ability
        above_bp += above * rate
        if ab in cf_set:
            cheap_within += within
        else:
            dear_within += within
    overflow = max(0, (cheap_within + dear_within) - b.ability_dots)
    overflow_cheap = min(overflow, cheap_within)         # cheapest dots paid first
    ability_bp = (above_bp
                  + overflow_cheap * bp_costs.ability_favored_caste
                  + (overflow - overflow_cheap) * bp_costs.ability)

    # --- Backgrounds: 7 free dots, pre-BP cap 3 (above-3 dot costs 2) --------- #
    bg_within = bg_above_bp = 0
    for bg in backgrounds:
        bg_within += min(bg.rating, b.background_cap_pre_bp)
        bg_above_bp += max(0, bg.rating - b.background_cap_pre_bp) * bp_costs.background_above_3
    bg_overflow = max(0, bg_within - b.background_dots)
    bg_bp = bg_above_bp + bg_overflow * bp_costs.background

    # --- Virtues: 5 free dots over base 1, pre-BP cap 3 ----------------------- #
    v_within = v_above = 0
    for v, rating in virtues.items():
        v_within += max(0, min(rating, b.virtue_cap_pre_bp) - b.virtue_base)
        v_above += max(0, rating - b.virtue_cap_pre_bp)
    v_overflow = max(0, v_within - b.virtue_dots)
    virtue_bp = (v_above + v_overflow) * bp_costs.virtue

    # --- Charms & Spells: one shared pool of 10 (p.100) ----------------------- #
    occult_cf = AbilityName.OCCULT in cf_set
    pick_costs: list[int] = []
    for cid in charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ability = _category_ability(charm.category)
        is_cf = ability is not None and ability in cf_set
        pick_costs.append(bp_costs.charm_favored_caste if is_cf else bp_costs.charm)
    for sid in spells:
        if ruleset.spells.get(sid) is None:
            continue
        pick_costs.append(bp_costs.charm_favored_caste if occult_cf else bp_costs.charm)
    ox_body_cf = AbilityName.ENDURANCE in cf_set
    for _ in ox_body:
        pick_costs.append(bp_costs.charm_favored_caste if ox_body_cf else bp_costs.charm)
    pick_costs.sort(reverse=True)                # free pool absorbs the dearest picks
    charm_bp = sum(pick_costs[b.charm_count:])

    # --- Combos: BP = its number of Charms (p.213) --------------------------- #
    combo_bp = sum(len(combo.charm_ids) for combo in combos)

    # --- Specialties: 1 BP/dot; Caste/Favoured get N dots per BP (p.105) ------ #
    cf_spec_dots = sum(s.rating for s in specialties if s.ability in cf_set)
    other_spec_dots = sum(s.rating for s in specialties if s.ability not in cf_set)
    per_point = bp_costs.specialty_favored_caste_dots_per_point
    spec_bp = other_spec_dots * bp_costs.specialty + (cf_spec_dots + per_point - 1) // per_point

    # --- Willpower / Essence -------------------------------------------------- #
    wp_bp = wp_purchased * bp_costs.willpower
    essence_bp = max(0, essence - b.essence_start) * bp_costs.essence

    lines = [
        BonusPointLine(domain="Attributes", points=attr_bp),
        BonusPointLine(domain="Abilities", points=ability_bp),
        BonusPointLine(domain="Backgrounds", points=bg_bp),
        BonusPointLine(domain="Virtues", points=virtue_bp),
        BonusPointLine(domain="Charms & Spells", points=charm_bp),
        BonusPointLine(domain="Combos", points=combo_bp),
        BonusPointLine(domain="Specialties", points=spec_bp),
        BonusPointLine(domain="Willpower", points=wp_bp),
        BonusPointLine(domain="Essence", points=essence_bp),
    ]
    total = sum(line.points for line in lines)
    return BonusPointBreakdown(lines=lines, total=total, available=b.bonus_points)


def validate_chargen(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Chargen budget predicates and bonus-point reconciliation (Exalted 1e core,
    pp.104-105). Validates the creation allocation: current traits pre-lock, or
    the frozen ChargenSnapshot once locked.

    The per-domain bonus-point arithmetic lives in `bonus_point_breakdown`; this
    function adds the legality predicates (ranges, Caste/Favoured minimums, the
    Willpower start-cap, the Charm/Spell Caste-Favoured minimum) and the final
    budget-ceiling check. One known simplification, flagged for the rules
    authority: the "10 of 25 Ability dots / 5 of 10 Charms must be Caste or
    Favoured" rules are checked as necessary conditions rather than jointly
    optimised with the free-dot assignment; the two only interact in rare
    over-spent builds.
    """
    issues: list[Issue] = []
    b = ruleset.budgets
    (attributes, abilities, crafts, virtues, _backgrounds, _specialties,
     charms, spells, _combos, ox_body, essence, wp_purchased) = _chargen_source(character)

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

    # --- Range checks --------------------------------------------------------- #
    for name, attr in attributes.items():
        if not (b.attribute_base <= attr <= 5):
            issues.append(Issue(
                code="attribute-range", where=name.value,
                message=f"Attribute {name.value} = {attr}; must be {b.attribute_base}-5 at creation.",
            ))
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
    for v, rating in virtues.items():
        if not (b.virtue_base <= rating <= 5):
            issues.append(Issue(
                code="virtue-range", where=v.value,
                message=f"Virtue {v.value} = {rating}; must be {b.virtue_base}-5 at creation.",
            ))

    # --- Charms & Spells: >=5 Caste/Favoured; Solar Circle barred at creation - #
    occult_cf = AbilityName.OCCULT in cf_set
    cf_pick_count = 0
    for cid in charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ability = _category_ability(charm.category)
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
    if AbilityName.ENDURANCE in cf_set:
        cf_pick_count += len(ox_body)
    if cf_pick_count < b.charm_min_caste_favored:
        issues.append(Issue(
            code="charm-caste-favored-min",
            message=f"At least {b.charm_min_caste_favored} of the {b.charm_count} "
                    f"Charms/Spells must be Caste/Favoured; only {cf_pick_count} "
                    "resolve as such.",
        ))

    # --- Willpower start-cap -------------------------------------------------- #
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
    issues += check_ox_body(ruleset, character)
    return issues
