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

from typing import Optional

from pydantic import BaseModel

from ..models.character import Character
from ..models.rules import (
    AbilityName,
    AttributeName,
    Charm,
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

# The repeatable Ox-Body-equivalent Charm is per-splat: each ExaltDefinition names
# its own (Solar's is solar.endurance.ox-body-technique). It is bought once per dot
# of its cap trait (Endurance; Stamina for Lunar), each purchase choosing a
# health-level package;
# stored on Character.ox_body, not in Character.charms (so the count is representable).


def ox_body_charm_id(ruleset: RuleSet, character: Character) -> str:
    """The id of this character's splat's repeatable Ox-Body-equivalent Charm (from
    its ExaltDefinition), or '' if the splat defines none."""
    return ruleset.exalt_for(character.exalt_type).ox_body_charm_id


def ox_body_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """The Ox-Body-equivalent Charm object for this character's splat, or None when
    the splat names none or the id is absent from the RuleSet."""
    return ruleset.charms.get(ox_body_charm_id(ruleset, character))


def gift_charm_id(ruleset: RuleSet, character: Character) -> str:
    """The id of this character's splat's repeatable Gift-granting Charm (Deadly
    Beastman Transformation for Lunar, p.124-127), or '' if the splat defines none."""
    return ruleset.exalt_for(character.exalt_type).gift_charm_id


def gift_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """The Gift-granting Charm object for this character's splat, or None when the
    splat names none or the id is absent from the RuleSet."""
    return ruleset.charms.get(gift_charm_id(ruleset, character))


def _repeatable_purchase_cap(charm: Charm, character: Character) -> int:
    """Resolve a repeatable Charm's `repeatable_cap_ability` against the character:
    an Ability, an Attribute, or the special value 'essence' (Deadly Beastman
    Transformation, p.124 — "no more times than he has points of Essence"; Essence
    isn't an Ability or Attribute, so it can't come through the normal lookups).
    0 if the Charm isn't repeatable or the trait name resolves to none of these."""
    if not charm.repeatable_cap_ability:
        return 0
    if charm.repeatable_cap_ability == "essence":
        return character.essence_rating
    try:
        return character.abilities[AbilityName(charm.repeatable_cap_ability)]
    except ValueError:
        pass
    try:
        return character.attributes[AttributeName(charm.repeatable_cap_ability)]
    except ValueError:
        return 0


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


def _min_trait_rating(character: Character, charm: Charm) -> tuple[str, int] | None:
    """The (trait name, character's rating) `charm.min_ability` is checked
    against — an Attribute for Lunar's Attribute-keyed Charms (`min_attribute`
    set, p.122), otherwise the Ability `category` resolves to. None if the Charm
    gates on neither (e.g. a `category` like 'sorcery' with no `min_attribute`).

    `min_attribute` takes priority: some categories (e.g. 'melee') are ALSO
    valid AbilityName values, and a Lunar Melee Charm must gate on the Dexterity/
    Strength/etc. `min_attribute` names, never on the character's Melee Ability
    rating — the two happen to collide by name, not by meaning."""
    if charm.min_attribute:
        try:
            attr = AttributeName(charm.min_attribute)
        except ValueError:
            return None
        return attr.value, character.attributes.get(attr, 0)
    ability = _category_ability(charm.category)
    if ability is None:
        return None
    return ability.value, ability_rating(character, ability)


def is_immaculate_charm(charm: Charm) -> bool:
    """True for an Immaculate Order Charm — a Fivefold Dragon Method martial-arts
    Charm (Dragon-Blooded splatbook, ch.6). These are what a DB may take the
    *Immaculate* chargen path with (5 from one elemental tree) in place of the
    standard 7 Dragon-Blooded Charms (p.151). Marked by the data flag Charm.immaculate."""
    return charm.immaculate


def _immaculate_path(ruleset: RuleSet, charm_ids, exalt_type: str) -> bool:
    """Whether a chargen Charm selection puts the character on the Immaculate
    martial-arts path — true when a Dragon-Blooded chooses ANY Immaculate Order
    Charm. On this path the Charm rules change (single elemental tree, 5-Charm
    free pool, Immaculate BP row, no Caste/Favoured minimum). The Immaculate
    *package* is Dragon-Blooded-only: a non-DB learner (e.g. a Solar taking a
    Terrestrial style, which is `open_to_all`) is priced/counted as ordinary
    Martial Arts and never trips this path, so it gates on `exalt_type`."""
    return exalt_type == "Dragon-Blooded" and any(
        (c := ruleset.charms.get(cid)) is not None and c.immaculate
        for cid in charm_ids)


def immaculate_martial_artist(ruleset: RuleSet, character: Character) -> bool:
    """Public form of `_immaculate_path` over the character's chargen Charm source
    (current pre-lock, or the frozen snapshot). Lets the UI show/gate the Immaculate
    path without re-deriving the snapshot selection."""
    charms = _chargen_source(character)[6]     # (…, charms, …) — see _chargen_source
    return _immaculate_path(ruleset, charms, character.exalt_type)


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

        trait = _min_trait_rating(character, charm)
        if trait is not None:
            trait_name, rating = trait
            if rating < charm.min_ability:
                issues.append(Issue(
                    code="charm-min-ability", where=cid,
                    message=(f"{charm.name}: requires {trait_name} "
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


# Dragon-Blooded martial-arts "Enlightenment" gate (DB p241-242). A Terrestrial
# must master both Immaculate enlightenment Charms — Spirit Sight, then Spirit
# Walking — before she may learn the Charms of any Dragon Path. Celestial Exalted
# and Abyssals need no such initiation (the p241 box: Exalted of any type can learn
# the Dragon Paths given a tutor), so the gate is Dragon-Blooded-only; and Five-
# Dragon Style — a mundane DB style, not a Dragon Path — is exempt.
DB_MA_ENLIGHTENMENT_IDS = ("dragonblooded.martial-arts.spirit-sight",
                           "dragonblooded.martial-arts.spirit-walking")
_UNGATED_MA_STYLES = frozenset({"five-dragon", "enlightenment"})


def _is_dragon_path_style(category: str) -> bool:
    """A martial-arts style category that counts as a 'Dragon Path' for the DB
    enlightenment gate — any ``martial_arts:<style>`` except the exempt styles
    (Five-Dragon and the Enlightenment tree itself)."""
    if not category.startswith("martial_arts:"):
        return False
    return category.split(":", 1)[1] not in _UNGATED_MA_STYLES


def db_enlightenment_met(character: Character) -> bool:
    """Whether the Dragon-Blooded Dragon-Path gate is OPEN for this character: always
    True for non-Dragon-Blooded (they need no initiation); for a Dragon-Blooded, True
    only once BOTH Immaculate enlightenment Charms (Spirit Sight + Spirit Walking)
    are known."""
    if character.exalt_type != "Dragon-Blooded":
        return True
    known = set(character.charms)
    return all(cid in known for cid in DB_MA_ENLIGHTENMENT_IDS)


def category_available(ruleset: RuleSet, character: Character, category: str) -> bool:
    """Whether a Charm `category` is open to the character right now — the picker's
    style-dropdown filter. Currently the only gate is the Dragon-Blooded Dragon-Path
    rule (p241): a DB reaches the elemental Dragon styles only after learning both
    enlightenment Charms. Every other category is always available."""
    return not (_is_dragon_path_style(category) and not db_enlightenment_met(character))


def meets_charm_requirements(ruleset: RuleSet, character: Character, charm) -> bool:
    """Whether the character could legally learn `charm` *right now*: min essence,
    min ability (when the category resolves to an ability), every AND-of-OR
    prerequisite group satisfied by an already-known Charm, and — for a Dragon-
    Blooded — the Dragon-Path enlightenment gate (p241). The forward-looking
    counterpart to check_charm_prerequisites; used by the charm-tree picker to
    decide which Charms are currently selectable."""
    if _is_dragon_path_style(charm.category) and not db_enlightenment_met(character):
        return False
    if character.essence_rating < charm.min_essence:
        return False
    trait = _min_trait_rating(character, charm)
    if trait is not None and trait[1] < charm.min_ability:
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

def granted_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """The set of magic circles the character can cast in, taken from the
    `grants_circle` of every known initiation Charm. Track-agnostic (sorcery or,
    later, necromancy) — the circle enum carries the distinction."""
    return {
        ruleset.charms[cid].grants_circle
        for cid in character.charms
        if cid in ruleset.charms and ruleset.charms[cid].grants_circle is not None
    }


def accessible_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """Every magic circle this character can reach — the circle granted by any
    initiation Charm they may learn (their own Exalt type, or an `open_to_all`
    Charm), unioned with circles already granted by known Charms.

    This is what the spell picker should show, and it is deliberately NOT the same
    as the Exalt's nominal `magic_track`: a splat whose Charm trees hold BOTH sorcery
    and necromancy initiations (Abyssals carry Terrestrial/Celestial Sorcery AND the
    three Necromancy circles) reaches both tracks, so its picker must too. Track is a
    display-ordering hint, not an access gate — the gate is the granting Charm."""
    out = granted_circles(ruleset, character)
    for charm in ruleset.charms.values():
        if charm.grants_circle is not None and charm_matches_splat(character, charm, ruleset):
            out.add(charm.grants_circle)
    return out


def chargen_barred_circle(ruleset: RuleSet, character: Character) -> SpellCircle | None:
    """The magic circle barred at character creation for this Exalt type, resolved
    from ExaltDefinition.highest_magic_circle_id (Solars: the Solar Circle, core
    p.100). Empty or unrecognised -> None (nothing barred at creation)."""
    cid = ruleset.exalt_for(character.exalt_type).highest_magic_circle_id
    try:
        return SpellCircle(cid) if cid else None
    except ValueError:
        return None


def meets_spell_requirements(ruleset: RuleSet, character: Character, spell,
                             *, chargen: bool = True) -> bool:
    """Whether the character could learn `spell` right now: a known Charm must grant
    its circle, and at chargen the Exalt type's highest circle is barred (Solars:
    Solar Circle, core p.100). Forward-looking counterpart to check_spell_access."""
    if chargen and spell.circle == chargen_barred_circle(ruleset, character):
        return False
    return spell.circle in granted_circles(ruleset, character)


def check_spell_access(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A known Spell requires a known Charm whose `grants_circle` matches
    the Spell's circle.

    Exact-circle match is correct for 1e (core pp.191): the three initiation
    Charms form a prerequisite chain — Celestial Circle Sorcery requires
    Terrestrial, Solar requires Celestial — so a higher-circle sorcerer always
    also holds the lower Charms (enforced by check_charm_prerequisites) and can
    cast lower-circle spells through them. No separate circle-nesting rule is
    needed here; the prerequisite chain provides it.
    """
    granted = granted_circles(ruleset, character)
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

# Castes allowed to mix Ability-based and Attribute-based Charms in one Combo
# (Lunars p.122): Solar Eclipse and Abyssal Moonshadow are "gifted generalists"
# who may cross the two Charm systems; every other caste (including every
# Lunar caste, whose native Charms are ALL Attribute-based already, and any
# other splat's caste) may not. A Lunar combining native Attribute Charms with
# an open_to_tiers Ability-keyed Martial Arts style (e.g. Five-Dragon Style, a
# Celestial-tier style a Lunar can learn) hits this the same as anyone else —
# the sourcebook names only Eclipse/Moonshadow for the crossover, not "any
# Lunar." This checks Combo COMPOSITION legality only; the p.122 dice-pool cap
# for a mixed Combo (2x Essence) is a play-time numeric limit with no home in
# this engine, same as the rest of attack/damage math (see the Combat/attack
# derivation out-of-scope decision).
_MIXED_COMBO_CASTES = {"eclipse", "moonshadow"}


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
    has_attribute_charm = has_ability_charm = False
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
        if charm.min_attribute:
            has_attribute_charm = True
        else:
            has_ability_charm = True
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
    if (has_attribute_charm and has_ability_charm
            and character.caste not in _MIXED_COMBO_CASTES):
        issues.append(Issue(
            code="combo-mixed-attribute-ability", where=where,
            message=f"Combo {where!r} mixes an Attribute-based Charm with an "
                    "Ability-based Charm; only Solar Eclipse and Abyssal "
                    "Moonshadow Charms may cross the two systems in one Combo.",
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

def repeatable_cap_trait_name(charm: Optional[Charm]) -> str:
    """Human name of the trait limiting a repeatable Charm's purchases, for use in
    messages: "Endurance", "Stamina", "Essence". "" if the Charm is absent or not
    repeatable. The trait is per-splat DATA (`repeatable_cap_ability`) — Lunar
    Ox-Body counts Stamina where every other splat counts Endurance (p.132) — so no
    message may hardcode it. Pairs with `_repeatable_purchase_cap`, which resolves
    the same field to a number."""
    name = charm.repeatable_cap_ability if charm else ""
    return name.replace("_", " ").title() if name else ""


def ox_body_cap(ruleset: RuleSet, character: Character) -> int:
    """Maximum number of Ox-Body Technique purchases: once per dot of the Charm's
    `repeatable_cap_ability` (Endurance for Solar/DB/Abyssal; Stamina — an
    Attribute, not an Ability — for Lunar, p.132). 0 if the Charm or its cap
    trait is absent. Used by both the engine and the picker to gate purchases."""
    charm = ox_body_charm(ruleset, character)
    if charm is None:
        return 0
    return _repeatable_purchase_cap(charm, character)


def check_ox_body(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of the character's Ox-Body purchases: at most one per dot of the
    splat's cap trait (core p.170), every chosen package a real variant, and the Charm's
    min essence met. The per-purchase bonus-point/XP cost is accounted elsewhere
    (validate_chargen / costs). Empty when no purchases."""
    issues: list[Issue] = []
    purchases = character.ox_body
    if not purchases:
        return issues
    oid = ox_body_charm_id(ruleset, character)
    charm = ox_body_charm(ruleset, character)
    if charm is None:
        issues.append(Issue(
            code="ox-body-unknown", where=oid,
            message="Character has Ox-Body purchases but the Charm is not in the RuleSet.",
        ))
        return issues
    cap = ox_body_cap(ruleset, character)
    if len(purchases) > cap:
        issues.append(Issue(
            code="ox-body-over-cap", where=oid,
            message=(f"Ox-Body Technique bought {len(purchases)} times; it may be "
                     f"bought at most once per dot of "
                     f"{repeatable_cap_trait_name(charm)} ({cap})."),
        ))
    if character.essence_rating < charm.min_essence:
        issues.append(Issue(
            code="ox-body-min-essence", where=oid,
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
# Deadly Beastman Transformation Gifts (repeatable, multi-pick-per-purchase Charm)
# --------------------------------------------------------------------------- #

def gift_purchase_cap(ruleset: RuleSet, character: Character) -> int:
    """Max purchases of the splat's Gift-granting Charm: Character.essence_rating
    for Deadly Beastman Transformation ("no more times than he has points of
    Essence", p.124). 0 if the splat has no such Charm."""
    charm = gift_charm(ruleset, character)
    if charm is None:
        return 0
    return _repeatable_purchase_cap(charm, character)


def gifts_per_purchase(charm: Charm, purchase_index: int) -> int:
    """How many Gifts the purchase at `purchase_index` (0-based) grants:
    `variant_picks_first_purchase` for index 0, `variant_picks_per_purchase` for
    every purchase after (p.124: Deadly Beastman Transformation's first purchase
    grants 2 Gifts, each purchase after grants 1)."""
    return (charm.variant_picks_first_purchase if purchase_index == 0
            else charm.variant_picks_per_purchase)


def known_gift_keys(character: Character) -> list[str]:
    """Every Gift key the character has purchased, across all purchases of the
    Gift-granting Charm, flattened (a Gift bought twice appears twice)."""
    return [g for p in character.beastman_gifts for g in p.gifts]


def check_gift_prerequisites(ruleset: RuleSet, character: Character) -> list[Issue]:
    """AND-of-OR prerequisite legality for known Gifts — the same shape as
    check_charm_prerequisites, but CharmVariant.prerequisites references OTHER
    variant keys of the SAME Charm (p.126-127's own Gift-to-Gift chain, e.g.
    Glue-Foot Climbing needs Spider-Foot Climbing needs Bestial Reflexes-or-
    Lightning Speed), not Charm ids."""
    issues: list[Issue] = []
    charm = gift_charm(ruleset, character)
    if charm is None:
        return issues
    variants_by_key = {v.key: v for v in charm.variants}
    known = set(known_gift_keys(character))
    for key in known:
        variant = variants_by_key.get(key)
        if variant is None:
            continue          # reported separately as beastman-gift-bad-variant
        for group in variant.prerequisites:
            if not any(pid in known for pid in group):
                issues.append(Issue(
                    code="gift-prerequisite-missing", where=key,
                    message=f"Gift {key!r} requires one of {sorted(group)!r}, "
                            "none of which is known.",
                ))
    return issues


def check_beastman_gifts(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of the character's Gift-granting Charm purchases: purchases <=
    Essence cap (p.124), each purchase's Gift count matches what that purchase
    grants, every chosen Gift a real variant, no Gift taken past its own
    max_purchases, and Gift prerequisites satisfied. The per-purchase BP/XP cost
    is accounted elsewhere (validate_chargen / costs), same as Ox-Body. Empty
    when no purchases."""
    issues: list[Issue] = []
    purchases = character.beastman_gifts
    if not purchases:
        return issues
    gid = gift_charm_id(ruleset, character)
    charm = gift_charm(ruleset, character)
    if charm is None:
        issues.append(Issue(
            code="beastman-gift-unknown-charm", where=gid,
            message="Character has Beastman Gift purchases but the Charm is not "
                    "in the RuleSet.",
        ))
        return issues
    cap = gift_purchase_cap(ruleset, character)
    if len(purchases) > cap:
        issues.append(Issue(
            code="beastman-gift-over-cap", where=gid,
            message=(f"{charm.name} bought {len(purchases)} times; it may be "
                     f"bought at most once per point of Essence ({cap})."),
        ))
    if character.essence_rating < charm.min_essence:
        issues.append(Issue(
            code="beastman-gift-min-essence", where=gid,
            message=(f"{charm.name} requires Essence {charm.min_essence}, "
                     f"character has {character.essence_rating}."),
        ))
    valid_keys = {v.key for v in charm.variants}
    for i, p in enumerate(purchases):
        expected = gifts_per_purchase(charm, i)
        if len(p.gifts) != expected:
            issues.append(Issue(
                code="beastman-gift-wrong-count", where=gid,
                message=(f"Purchase {i + 1} of {charm.name} grants {expected} "
                         f"Gift(s), but {len(p.gifts)} were chosen."),
            ))
        for key in p.gifts:
            if key not in valid_keys:
                issues.append(Issue(
                    code="beastman-gift-bad-variant", where=key,
                    message=f"{charm.name}: unknown Gift {key!r}.",
                ))
    counts: dict[str, int] = {}
    for key in known_gift_keys(character):
        counts[key] = counts.get(key, 0) + 1
    for key, n in counts.items():
        variant = next((v for v in charm.variants if v.key == key), None)
        if variant is not None and n > variant.max_purchases:
            issues.append(Issue(
                code="beastman-gift-over-repeat-cap", where=key,
                message=(f"Gift {key!r} taken {n} times; it may be taken at most "
                         f"{variant.max_purchases} time(s)."),
            ))
    issues += check_gift_prerequisites(ruleset, character)
    return issues


# --------------------------------------------------------------------------- #
# Chargen (not yet implemented — see module docstring)
# --------------------------------------------------------------------------- #

def _caste_favored(ruleset: RuleSet, character: Character) -> tuple[set, set] | None:
    """(caste_abilities, favored_abilities) as sets, or None if the caste is not
    in the RuleSet (caller emits an issue and skips caste-dependent checks). For a
    Lunar caste (caste_attributes set, caste_abilities empty — p.90), the caste
    contributes no Ability discount here; its discount is Attribute-keyed and
    handled separately by `_caste_favored_attribute_category`."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return None
    return set(caste_def.caste_abilities), set(character.favored_abilities)


def _attribute_category(attr: AttributeName) -> str | None:
    """Which of Physical/Social/Mental `attr` belongs to (the reverse lookup of
    ATTRIBUTE_CATEGORIES)."""
    for cat, attrs in ATTRIBUTE_CATEGORIES.items():
        if attr in attrs:
            return cat
    return None


def _caste_favored_attribute_category(ruleset: RuleSet, character: Character) -> str | None:
    """The Attribute category (Physical/Social/Mental) a Lunar's caste favors, or
    None for a caste with no Caste Attributes (every non-Lunar caste, and the
    Lunar Casteless caste, p.108). Full Moon/Changing Moon/No Moon's three Caste
    Attributes are always exactly one whole ATTRIBUTE_CATEGORIES group (p.90-91),
    so the category of any one of them is the caste's favored category."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None or not caste_def.caste_attributes:
        return None
    return _attribute_category(caste_def.caste_attributes[0])


def _ox_body_caste_favored(ruleset: RuleSet, character: Character,
                            cf_set: set, caste_attr_category: str | None) -> bool:
    """Whether the character's splat's Ox-Body-equivalent Charm counts as
    Caste/Favoured — same rule as any other Charm (category-Ability membership
    for Solar/DB/Abyssal's Endurance-keyed Charm, Attribute-category match for
    Lunar's Stamina-keyed one), just resolved once here instead of re-deriving
    `ox_body_charm` at each call site."""
    charm = ox_body_charm(ruleset, character)
    if charm is None:
        return False
    ability = _category_ability(charm.category)
    if ability is not None and ability in cf_set:
        return True
    return _charm_attribute_caste_favored(charm, caste_attr_category)


def _gift_caste_favored(ruleset: RuleSet, character: Character,
                         cf_set: set, caste_attr_category: str | None) -> bool:
    """Whether the character's splat's Gift-granting Charm counts as Caste/
    Favoured — same rule as _ox_body_caste_favored, just against gift_charm."""
    charm = gift_charm(ruleset, character)
    if charm is None:
        return False
    ability = _category_ability(charm.category)
    if ability is not None and ability in cf_set:
        return True
    return _charm_attribute_caste_favored(charm, caste_attr_category)


def _charm_attribute_caste_favored(charm: Charm, caste_attr_category: str | None) -> bool:
    """Whether an Attribute-keyed Charm (Lunar) counts as Caste-favored: its
    `min_attribute`'s category matches the caste's favored category (p.122).
    False for a Charm with no `min_attribute` or for a non-Lunar/Casteless caste."""
    if not charm.min_attribute or caste_attr_category is None:
        return False
    try:
        attr = AttributeName(charm.min_attribute)
    except ValueError:
        return False
    return _attribute_category(attr) == caste_attr_category


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
        snap.beastman_gifts if snap else character.beastman_gifts,
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
    b = ruleset.budgets_for(character.exalt_type, character.origin)
    bp_costs = ruleset.bonus_costs_for(character.exalt_type)
    (attributes, abilities, crafts, virtues, backgrounds, specialties,
     charms, spells, combos, ox_body, essence, wp_purchased,
     beastman_gifts) = _chargen_source(character)

    cf = _caste_favored(ruleset, character)
    cf_set = (cf[0] | cf[1]) if cf is not None else set()
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)

    # --- Attributes: three category spends matched to the 8/6/4 pools --------- #
    # The pool assignment (which category gets which of the sorted pools) is by
    # spend alone, same as before; the per-category RATE additionally depends on
    # whether that category is the caste's favored one (Lunar Caste Attributes,
    # p.93 — "4, 3 if a Caste Attribute"). Ability-caste splats have no favored
    # category (caste_attr_category is None), so every category costs the same
    # flat `attribute` rate, unchanged from before this was added.
    cat_spends = sorted(
        ((cat, sum(attributes[a] - b.attribute_base for a in attrs))
         for cat, attrs in ATTRIBUTE_CATEGORIES.items()),
        key=lambda cs: cs[1], reverse=True,
    )
    pools = sorted(b.attribute_pools, reverse=True)
    attr_bp = sum(
        max(0, spend - pool) * (bp_costs.attribute_caste_favored if cat == caste_attr_category
                                 else bp_costs.attribute)
        for (cat, spend), pool in zip(cat_spends, pools)
    )

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

    # --- Charms & Spells: one shared pool (p.100) ----------------------------- #
    # The Immaculate martial-arts path (DB, p.151) swaps the free pool size and the
    # per-Charm BP row: 5 Immaculate Charms free (vs charm_count), each Immaculate
    # Charm priced from the Immaculate BP row (10/7) rather than the ordinary one.
    immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
    free_charm_pool = b.immaculate_charm_count if immaculate else b.charm_count
    occult_cf = AbilityName.OCCULT in cf_set
    pick_costs: list[int] = []
    for cid in charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ability = _category_ability(charm.category)
        is_cf = ((ability is not None and ability in cf_set)
                 or _charm_attribute_caste_favored(charm, caste_attr_category))
        if charm.immaculate:
            pick_costs.append(bp_costs.immaculate_charm_favored_caste if is_cf
                              else bp_costs.immaculate_charm)
        else:
            pick_costs.append(bp_costs.charm_favored_caste if is_cf else bp_costs.charm)
    for sid in spells:
        if ruleset.spells.get(sid) is None:
            continue
        pick_costs.append(bp_costs.charm_favored_caste if occult_cf else bp_costs.charm)
    ox_body_cf = _ox_body_caste_favored(ruleset, character, cf_set, caste_attr_category)
    for _ in ox_body:
        pick_costs.append(bp_costs.charm_favored_caste if ox_body_cf else bp_costs.charm)
    gift_cf = _gift_caste_favored(ruleset, character, cf_set, caste_attr_category)
    for _ in beastman_gifts:
        pick_costs.append(bp_costs.charm_favored_caste if gift_cf else bp_costs.charm)
    pick_costs.sort(reverse=True)                # free pool absorbs the dearest picks
    charm_bp = sum(pick_costs[free_charm_pool:])

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
    b = ruleset.budgets_for(character.exalt_type, character.origin)
    (attributes, abilities, crafts, virtues, _backgrounds, _specialties,
     charms, spells, _combos, ox_body, essence, wp_purchased,
     beastman_gifts) = _chargen_source(character)

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
        # Abilities the origin/splat forces into the Favored set — Lunar Survival
        # (p.90); empty for splats with no such rule.
        for ab in b.required_favored:
            if ab not in favored:
                issues.append(Issue(
                    code="required-favored-ability", where=ab.value,
                    message=f"{ab.value} must be a Favored Ability for this splat.",
                ))

    cf_set = caste_abilities | favored
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)

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
    # Required minimum Abilities — the Dragon-Blooded Dynastic schooling floor
    # (p.151). Each requirement is satisfied by any one of its listed Abilities.
    for req in b.required_min_abilities:
        best = max((abilities.get(ab, 0) for ab in req.abilities), default=0)
        if best < req.rating:
            names = " or ".join(a.value for a in req.abilities)
            issues.append(Issue(
                code="required-min-ability", where=names,
                message=f"This origin requires at least {req.rating} dot(s) in {names}; "
                        f"has {best}.",
            ))
    for v, rating in virtues.items():
        if not (b.virtue_base <= rating <= 5):
            issues.append(Issue(
                code="virtue-range", where=v.value,
                message=f"Virtue {v.value} = {rating}; must be {b.virtue_base}-5 at creation.",
            ))

    # --- Charms & Spells: top circle barred at creation, plus one of two paths -- #
    # Standard path: >=charm_min_caste_favored of the picks are Caste/Favoured.
    # Immaculate path (DB, p.151, triggered by any Immaculate Order Charm): all
    # chargen Charms must instead be a single elemental tree, and the Caste/Favoured
    # minimum is waived.
    immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
    occult_cf = AbilityName.OCCULT in cf_set
    barred = chargen_barred_circle(ruleset, character)
    cf_pick_count = 0
    for cid in charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ability = _category_ability(charm.category)
        if ((ability is not None and ability in cf_set)
                or _charm_attribute_caste_favored(charm, caste_attr_category)):
            cf_pick_count += 1
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
        if occult_cf:
            cf_pick_count += 1
    if _ox_body_caste_favored(ruleset, character, cf_set, caste_attr_category):
        cf_pick_count += len(ox_body)
    if _gift_caste_favored(ruleset, character, cf_set, caste_attr_category):
        cf_pick_count += len(beastman_gifts)

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

def check_exalt_type(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The character's exalt_type must be a known ExaltDefinition. An unknown type
    still derives (essence pools fall back to Solar) but is surfaced here so a
    hand-edited or mis-migrated save is flagged rather than silently mis-priced."""
    if character.exalt_type in ruleset.exalts:
        return []
    return [Issue(
        code="exalt-type-unknown", where=character.exalt_type,
        message=f"Exalt type {character.exalt_type!r} is not defined in the rule set.",
    )]


def check_caste_splat(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The character's caste must belong to the character's own Exalt type — a
    Solar can't be a Dragon-Blooded Aspect and vice versa. An unknown caste is left
    to validate_chargen's 'unknown-caste' finding, so this doesn't double-report."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None or caste_def.exalt_type == character.exalt_type:
        return []
    return [Issue(
        code="caste-wrong-splat", where=character.caste,
        message=f"Caste {caste_def.label!r} belongs to {caste_def.exalt_type}, "
                f"not the character's Exalt type {character.exalt_type!r}.",
    )]


# Lunar Casteless (p.90-91, p.108): unlike Dragon-Blooded Dynastic/Outcaste — an
# origin variant orthogonal to caste — Lunar Casteless is a single condition
# expressed on BOTH fields at once (no Caste Attributes, only 6 Charms, no
# Ability minimums, no Renown). The two must move together: Casteless origin iff
# the Casteless caste, never one without the other.
LUNAR_CASTELESS_CASTE_ID = "casteless"
LUNAR_CASTELESS_ORIGIN = "casteless"


def check_lunar_casteless_consistency(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A Lunar's origin and caste must agree on Casteless-ness. Not gated on caste
    lookup succeeding — an unrecognised caste is `check_caste_splat`'s concern."""
    if character.exalt_type != "Lunar":
        return []
    is_casteless_caste = character.caste == LUNAR_CASTELESS_CASTE_ID
    is_casteless_origin = character.origin == LUNAR_CASTELESS_ORIGIN
    if is_casteless_caste == is_casteless_origin:
        return []
    return [Issue(
        code="lunar-casteless-mismatch", where=character.caste,
        message=("A Lunar's Casteless origin and Casteless caste must match: "
                 f"caste={character.caste!r}, origin={character.origin!r}."),
    )]


def splat_of(charm: Charm) -> str:
    """The Exalt type that can learn `charm` (charm.exalt_type). A tiny accessor so
    the UI/engine don't reach into the field directly and can grow smarter later
    (e.g. cross-splat Martial Arts / sorcery) without a churn of call sites."""
    return charm.exalt_type


def charm_matches_splat(character: Character, charm: Charm,
                        ruleset: Optional[RuleSet] = None) -> bool:
    """Whether `charm` is available to the character — the picker/graph filter and
    the `charm-wrong-splat` check. A Charm matches when

      * it belongs to the character's own Exalt type, OR
      * it is flagged `open_to_all` (cross-splat Charms such as the Terrestrial
        Immaculate Dragon martial-arts styles, which any splat may learn), OR
      * the character's Exalt *tier* is listed in `charm.open_to_tiers` — the
        Celestial-only styles (Hungry Ghost, Five-Dragon).

    The tier test needs the splat table, so it only applies when `ruleset` is
    given; without one the call degrades to the splat/`open_to_all` answer."""
    if charm.open_to_all or splat_of(charm) == character.exalt_type:
        return True
    if ruleset is not None and charm.open_to_tiers:
        return ruleset.exalt_for(character.exalt_type).tier in charm.open_to_tiers
    return False


def foreign_charms_caste(ruleset: RuleSet, character: Character):
    """The character's CasteDefinition when that caste may learn other splats'
    Charms (the Eclipse generalist rule, core p.127), else None. Data-driven via
    `CasteDefinition.foreign_charms` — no caste or splat is named in code."""
    caste = ruleset.castes.get(character.caste)
    return caste if caste is not None and caste.foreign_charms else None


def foreign_charms_open(ruleset: RuleSet, character: Character) -> bool:
    """Whether the character may learn other splats' Charms *right now*. The caste
    must allow it (p.127), and — before the sheet is locked — the Storyteller must
    have permitted it: "Eclipse Caste characters may not start the game knowing the
    Charms of other such beings without Storyteller permission." After lock the rule
    asks only for a willing tutor, which is narrative, so the gate falls away."""
    if foreign_charms_caste(ruleset, character) is None:
        return False
    return character.chargen_locked or character.st_foreign_charms


def is_foreign_charm(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Whether `charm` is another splat's Charm for this character — i.e. it is only
    reachable via the p.127 generalist rule, not by the ordinary splat/tier match.
    This is what the doubled XP price keys off, so the `open_to_tiers` styles a
    Celestial may learn natively (Hungry Ghost, Five-Dragon) are NOT foreign and
    must not double — hence the ruleset argument."""
    return not charm_matches_splat(character, charm, ruleset)


def charm_learnable_by_splat(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """The picker/graph filter and the `charm-wrong-splat` check: `charm` is either
    natively available (charm_matches_splat) or reachable through the caste's
    foreign-Charm privilege. Kept separate from charm_matches_splat so that
    accessible_circles — which asks what the character's OWN splat can initiate —
    keeps its narrower question."""
    return (charm_matches_splat(character, charm, ruleset)
            or foreign_charms_open(ruleset, character))


def check_splat_consistency(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Every Charm the character holds must belong to the character's own Exalt
    type, unless their caste may learn other splats' Charms (p.127). Spells are
    cross-splat (gated by circle, not splat) and are not checked; unknown Charm ids
    are left to check_references."""
    issues: list[Issue] = []
    permissive = foreign_charms_open(ruleset, character)
    gated = foreign_charms_caste(ruleset, character) is not None and not permissive
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is None or charm_matches_splat(character, charm, ruleset):
            continue
        if permissive:
            continue
        if gated:
            issues.append(Issue(
                code="charm-foreign-no-st-permission", where=cid,
                message=f"Charm {charm.name!r} belongs to another Exalt type "
                        f"({splat_of(charm)}). An Eclipse-style caste may only start "
                        f"play knowing it with Storyteller permission (p.127).",
            ))
            continue
        issues.append(Issue(
            code="charm-wrong-splat", where=cid,
            message=f"Charm {charm.name!r} is {splat_of(charm)}, not the "
                    f"character's Exalt type {character.exalt_type!r}.",
        ))
    return issues


def validate(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Run all *implemented* checks and return the combined issues. Chargen
    predicates are excluded until designed."""
    issues: list[Issue] = []
    issues += check_exalt_type(ruleset, character)
    issues += check_caste_splat(ruleset, character)
    issues += check_lunar_casteless_consistency(ruleset, character)
    issues += check_splat_consistency(ruleset, character)
    issues += check_references(ruleset, character)
    issues += check_charm_prerequisites(ruleset, character)
    issues += check_spell_access(ruleset, character)
    issues += validate_combos(ruleset, character)
    issues += check_ox_body(ruleset, character)
    issues += check_beastman_gifts(ruleset, character)
    return issues
