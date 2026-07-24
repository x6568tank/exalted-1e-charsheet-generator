"""
engine/advancement.py — post-lock XP advancement transitions.

The chargen counterpart is engine.lifecycle; this is the *post-lock* layer. Each
`raise_*`/`learn_*`/`add_*` is a transition that mutates the Character: it prices
the advance via engine.costs, checks it is legal and affordable, applies the trait
change, and appends an append-only XpEntry to character.xp_log. `undo_last`
reverses the most recent entry (last-in-first-out, so the log and the traits never
drift out of sync). `validate_xp` (in engine.validate) audits the result.

Not pure — like lifecycle, these are state transitions. Legality that needs the
rules (Charm prerequisites, spell-circle access, Combo composition) is delegated to
engine.validate; the trait caps live here.
"""

from __future__ import annotations

from ..models.character import (
    Array, BeastmanGiftPurchase, Character, CollegeRating, Combo, CraftRating, OxBodyPurchase,
    Specialty, SubmodulePurchase, XpEntry)
from ..models.rules import AbilityName, AttributeName, RuleSet, VirtueName
from . import costs, derive, validate

# Conventional maxima for raises. The 1-5 dot cap is the universal trait cap used
# throughout chargen; Willpower's permanent maximum is 10. (Essence is capped here
# at the core Solar 5; raise this constant if higher-Essence rules are added.)
_DOT_MAX = 5
_WILLPOWER_MAX = 10


class AdvancementError(ValueError):
    """An illegal or unaffordable advance. The UI surfaces the message."""


# --------------------------------------------------------------------------- #
# XP accounting
# --------------------------------------------------------------------------- #

def xp_spent(character: Character) -> int:
    """Total XP committed across the log."""
    return sum(entry.cost for entry in character.xp_log)


def xp_available(character: Character) -> int:
    """Unspent XP: earned minus the log total (may go negative if hand-edited)."""
    return character.xp_earned - xp_spent(character)


def add_xp(character: Character, amount: int) -> None:
    """Adjust earned XP by `amount` (negative to correct an over-grant). Earned
    never drops below zero."""
    character.xp_earned = max(0, character.xp_earned + amount)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _ensure_locked(character: Character) -> None:
    if not character.chargen_locked:
        raise AdvancementError("Lock chargen before spending XP.")


def _commit(character: Character, target: str, detail: str,
            frm: int | None, to: int | None, cost: int) -> XpEntry:
    """Affordability gate + append the log row. Call only after the trait change is
    decided (cost computed) but it is fine to mutate before or after — nothing here
    touches traits."""
    if cost > xp_available(character):
        raise AdvancementError(
            f"Costs {cost} XP; only {xp_available(character)} available.")
    entry = XpEntry(target=target, detail=detail, from_rating=frm, to_rating=to, cost=cost)
    character.xp_log.append(entry)
    return entry


# --------------------------------------------------------------------------- #
# Scaled-trait raises (one dot each)
# --------------------------------------------------------------------------- #

def raise_attribute(ruleset: RuleSet, character: Character, attr: AttributeName) -> XpEntry:
    _ensure_locked(character)
    frm = character.attributes[attr]
    if frm >= _DOT_MAX:
        raise AdvancementError(f"{attr.value} is already at {_DOT_MAX}.")
    cost = costs.attribute_step(ruleset, character, frm, attr)
    entry = _commit(character, f"attributes.{attr.value}", "", frm, frm + 1, cost)
    character.attributes[attr] = frm + 1
    return entry


def raise_ability(ruleset: RuleSet, character: Character, ability: AbilityName) -> XpEntry:
    _ensure_locked(character)
    frm = character.abilities.get(ability, 0)
    if frm >= _DOT_MAX:
        raise AdvancementError(f"{ability.value} is already at {_DOT_MAX}.")
    cost = costs.ability_step(ruleset, character, ability, frm)
    entry = _commit(character, f"abilities.{ability.value}", "", frm, frm + 1, cost)
    character.abilities[ability] = frm + 1
    return entry


def learn_craft(ruleset: RuleSet, character: Character, focus: str) -> XpEntry:
    """Begin a new per-focus Craft Ability at rating 1 (core p.136). Priced as a new
    Ability (the flat 'new ability' cost, with the Caste/Favoured discount baked into
    ability_step). Focus must be non-empty and not already owned."""
    _ensure_locked(character)
    focus = focus.strip()
    if not focus:
        raise AdvancementError("A craft needs a focus (e.g. Smithing).")
    if any(c.focus.casefold() == focus.casefold() for c in character.crafts):
        raise AdvancementError(f"Craft ({focus}) already exists; raise it instead.")
    cost = costs.ability_step(ruleset, character, AbilityName.CRAFT, 0)
    entry = _commit(character, "crafts", focus, 0, 1, cost)
    character.crafts.append(CraftRating(focus=focus, rating=1))
    return entry


def raise_craft(ruleset: RuleSet, character: Character, focus: str) -> XpEntry:
    """Raise an existing per-focus Craft Ability one dot, scaled like any Ability."""
    _ensure_locked(character)
    cr = next((c for c in character.crafts if c.focus == focus), None)
    if cr is None:
        raise AdvancementError(f"No Craft ({focus}) to raise; learn it first.")
    if cr.rating >= _DOT_MAX:
        raise AdvancementError(f"Craft ({focus}) is already at {_DOT_MAX}.")
    cost = costs.ability_step(ruleset, character, AbilityName.CRAFT, cr.rating)
    entry = _commit(character, "crafts", focus, cr.rating, cr.rating + 1, cost)
    cr.rating += 1
    return entry


def learn_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    """Begin a new Astrological College at rating 1 (Sidereal, p.265). Flat new_college
    cost. The id must be a real College and not already owned."""
    _ensure_locked(character)
    if college_id not in ruleset.colleges:
        raise AdvancementError(f"Unknown college {college_id!r}.")
    if any(c.college_id == college_id for c in character.colleges):
        raise AdvancementError(f"{ruleset.colleges[college_id].name} is already known; raise it instead.")
    cost = costs.college_new_cost(ruleset, character)
    entry = _commit(character, "colleges", college_id, 0, 1, cost)
    character.colleges.append(CollegeRating(college_id=college_id, rating=1))
    return entry


def raise_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    """Raise an existing College one dot, scaled (current × 3, p.265)."""
    _ensure_locked(character)
    cr = next((c for c in character.colleges if c.college_id == college_id), None)
    if cr is None:
        raise AdvancementError(f"No college {college_id!r} to raise; learn it first.")
    if cr.rating >= _DOT_MAX:
        raise AdvancementError(f"{ruleset.colleges[college_id].name} is already at {_DOT_MAX}.")
    cost = costs.college_step(ruleset, character, cr.rating)
    entry = _commit(character, "colleges", college_id, cr.rating, cr.rating + 1, cost)
    cr.rating += 1
    return entry


def raise_virtue(ruleset: RuleSet, character: Character, virtue: VirtueName) -> XpEntry:
    _ensure_locked(character)
    frm = character.virtues[virtue]
    if frm >= _DOT_MAX:
        raise AdvancementError(f"{virtue.value} is already at {_DOT_MAX}.")
    cost = costs.virtue_step(ruleset, character, frm)
    entry = _commit(character, f"virtues.{virtue.value}", "", frm, frm + 1, cost)
    character.virtues[virtue] = frm + 1
    return entry


def raise_willpower(ruleset: RuleSet, character: Character) -> XpEntry:
    """Raise permanent Willpower one dot (increments the purchased component; the
    pinned Virtue component is untouched)."""
    _ensure_locked(character)
    frm = derive.willpower(character)
    if frm >= _WILLPOWER_MAX:
        raise AdvancementError(f"Willpower is already at {_WILLPOWER_MAX}.")
    cost = costs.willpower_step(ruleset, character, frm)
    entry = _commit(character, "willpower", "", frm, frm + 1, cost)
    character.willpower_purchased += 1
    return entry


def raise_essence(ruleset: RuleSet, character: Character) -> XpEntry:
    _ensure_locked(character)
    frm = character.essence_rating
    if frm >= _DOT_MAX:
        raise AdvancementError(f"Essence is already at {_DOT_MAX}.")
    cost = costs.essence_step(ruleset, character, frm)
    entry = _commit(character, "essence", "", frm, frm + 1, cost)
    character.essence_rating = frm + 1
    return entry


# --------------------------------------------------------------------------- #
# Permanent reductions (curses, Charm costs, story effects)
#
# A reduction lowers a permanent trait *outside* the XP economy: it refunds NO XP
# (cost 0) and is logged as an append-only row with to_rating < from_rating, so the
# audit prices it at 0 and `undo_last` reverses it like any other row. These are
# story-driven (a curse that saps Strength, a Charm with a permanent cost), so the
# engine enforces only the floor — not any rules reason. The `reason` is free text
# (stored on the row's detail) shown in the ledger. If a reduction drops an Ability
# below a known Charm's requirement, the normal validate() surfaces that — by design.
# --------------------------------------------------------------------------- #

def _log_reduction(character: Character, target: str, frm: int, to: int, reason: str) -> XpEntry:
    entry = XpEntry(target=target, detail=reason, from_rating=frm, to_rating=to, cost=0)
    character.xp_log.append(entry)
    return entry


def lower_attribute(character: Character, attr: AttributeName, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.attributes[attr]
    if frm <= 1:
        raise AdvancementError(f"{attr.value} is already at 1 (the minimum).")
    character.attributes[attr] = frm - 1
    return _log_reduction(character, f"attributes.{attr.value}", frm, frm - 1, reason)


def lower_ability(character: Character, ability: AbilityName, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.abilities.get(ability, 0)
    if frm <= 0:
        raise AdvancementError(f"{ability.value} is already at 0.")
    character.abilities[ability] = frm - 1
    return _log_reduction(character, f"abilities.{ability.value}", frm, frm - 1, reason)


def lower_virtue(character: Character, virtue: VirtueName, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.virtues[virtue]
    if frm <= 1:
        raise AdvancementError(f"{virtue.value} is already at 1 (the minimum).")
    character.virtues[virtue] = frm - 1
    return _log_reduction(character, f"virtues.{virtue.value}", frm, frm - 1, reason)


def lower_willpower(character: Character, reason: str = "") -> XpEntry:
    """Reduce permanent Willpower one dot (a curse). Decrements the purchased
    component, which may go negative — permanent Willpower = pinned Virtue component
    + purchased, so a curse below the Virtue floor is represented as net-negative
    purchased. Floored at a permanent Willpower of 1."""
    _ensure_locked(character)
    frm = derive.willpower(character)
    if frm <= 1:
        raise AdvancementError("Willpower is already at 1 (the minimum).")
    character.willpower_purchased -= 1
    return _log_reduction(character, "willpower", frm, frm - 1, reason)


def lower_essence(character: Character, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.essence_rating
    if frm <= 1:
        raise AdvancementError("Essence is already at 1 (the minimum).")
    character.essence_rating = frm - 1
    return _log_reduction(character, "essence", frm, frm - 1, reason)


# --------------------------------------------------------------------------- #
# New traits
# --------------------------------------------------------------------------- #

def learn_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    _ensure_locked(character)
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if charm_id in character.charms:
        raise AdvancementError(f"{charm.name} is already known.")
    # A Charm-Slot splat (Alchemical) does not learn Charms per-pick: it buys a Slot
    # (buy_charm_slot) or a Panoply Charm (learn_retainer_charm). Route callers there
    # so a Slot is never silently skipped.
    if validate.uses_charm_slots(ruleset, character):
        raise AdvancementError(
            f"{charm.name}: Alchemicals gain Charms by buying a Charm Slot or a "
            f"Panoply (retainer) Charm, not directly.")
    # Another splat's Charm is buyable only by an Eclipse-style caste (p.127), and
    # then at the doubled price costs.charm_cost applies.
    if not validate.charm_learnable_by_splat(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} belongs to another Exalt type ({validate.splat_of(charm)}).")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    cost = costs.charm_cost(ruleset, character, charm)
    # p.90 crossover: an Eclipse/Moonshadow learning an Alchemical Charm gains a
    # General Charm Slot with it. Logged under a distinct target so undo gives the
    # Slot back too.
    grants_slot = validate.crossover_alchemical_charm(ruleset, character, charm)
    entry = _commit(character, "crossover_charms" if grants_slot else "charms",
                    charm_id, None, None, cost)
    character.charms.append(charm_id)
    if grants_slot:
        g, _d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
        character.general_charm_slots = g + 1
    return entry


def learn_spell(ruleset: RuleSet, character: Character, spell_id: str) -> XpEntry:
    _ensure_locked(character)
    spell = ruleset.spells.get(spell_id)
    if spell is None:
        raise AdvancementError(f"Unknown spell {spell_id!r}.")
    if spell_id in character.spells:
        raise AdvancementError(f"{spell.name} is already known.")
    # Post-lock the chargen Solar-Circle bar lifts; only circle access is required.
    if not validate.meets_spell_requirements(ruleset, character, spell, chargen=False):
        raise AdvancementError(f"{spell.name}: no known Charm grants its Circle.")
    cost = costs.spell_cost(ruleset, character, spell)
    entry = _commit(character, "spells", spell_id, None, None, cost)
    character.spells.append(spell_id)
    return entry


# --------------------------------------------------------------------------- #
# Alchemical Charm-Slot economy (post-lock; Autochthonians p.64, p.89)
# --------------------------------------------------------------------------- #

def _require_slot_splat(ruleset: RuleSet, character: Character) -> None:
    if not validate.uses_charm_slots(ruleset, character):
        raise AdvancementError("Charm Slots are an Alchemical mechanic.")


def _installable_charm(ruleset: RuleSet, character: Character, charm_id: str):
    """Shared gate for a Charm the character is about to gain (Slot or Panoply): it
    exists, is not already owned (installed or on retainer), is learnable by the
    splat, and its requirements are met. Returns the Charm."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if charm_id in character.charms or charm_id in character.retainer_charms:
        raise AdvancementError(f"{charm.name} is already owned.")
    if not validate.charm_learnable_by_splat(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} belongs to another Exalt type ({validate.splat_of(charm)}).")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    return charm


def buy_charm_slot(ruleset: RuleSet, character: Character, *, dedicated: bool,
                   charm_id: str) -> XpEntry:
    """Buy one more Charm Slot (p.64): General (12) or Dedicated (10). The Slot comes
    with a free Charm of the player's choice that must fit the Slot — a Dedicated Slot
    holds only a Caste/Favored-Attribute Charm. The Charm is installed (added to
    `charms`); the Slot count is incremented."""
    _ensure_locked(character)
    _require_slot_splat(ruleset, character)
    charm = _installable_charm(ruleset, character, charm_id)
    if dedicated and not validate.charm_fits_dedicated_slot(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} is not keyed to a Caste/Favored Attribute, so it cannot "
            f"fill a Dedicated Slot; buy a General Slot instead.")
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    cost = costs.charm_slot_cost(ruleset, character, dedicated=dedicated)
    kind = "dedicated" if dedicated else "general"
    frm = d if dedicated else g
    entry = _commit(character, f"charm_slots.{kind}", charm_id, frm, frm + 1, cost)
    if dedicated:
        character.dedicated_charm_slots = d + 1
    else:
        character.general_charm_slots = g + 1
    character.charms.append(charm_id)
    return entry


def upgrade_charm_slot(ruleset: RuleSet, character: Character) -> XpEntry:
    """Upgrade one Dedicated Charm Slot to a General Slot (p.64, 2 XP). Requires a
    Dedicated Slot to exist."""
    _ensure_locked(character)
    _require_slot_splat(ruleset, character)
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    if d <= 0:
        raise AdvancementError("No Dedicated Charm Slot to upgrade.")
    cost = costs.charm_slot_upgrade_cost(ruleset, character)
    # Ratings left None: this swaps two counts, not a single-trait change, and a
    # to<from would be misread as a free reduction by the audit.
    entry = _commit(character, "charm_slot_upgrade", "", None, None, cost)
    character.dedicated_charm_slots = d - 1
    character.general_charm_slots = g + 1
    return entry


def learn_retainer_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    """Buy one Panoply (retainer) Charm WITHOUT a Slot. A native Alchemical pays the
    flat 6 XP (p.64); an Eclipse/Moonshadow may instead add an Alchemical Charm to their
    Panoply through the crossover at their caste's flat rate (p.90, 8) as a cheaper
    alternative to a Slot. Either way the Charm is owned but not installed."""
    _ensure_locked(character)
    native = validate.uses_charm_slots(ruleset, character)
    crossover = validate.crossover_panoply_xp(ruleset, character) is not None
    if not native and not crossover:
        raise AdvancementError(
            "Panoply Charms are an Alchemical mechanic (or the Eclipse/Moonshadow "
            "Alchemical crossover, p.90).")
    charm = _installable_charm(ruleset, character, charm_id)
    # A crossover Panoply holds Alchemical Charms specifically (p.90).
    if not native and not validate.splat_uses_charm_slots(ruleset, validate.splat_of(charm)):
        raise AdvancementError(
            f"{charm.name} is not an Alchemical Charm; only Alchemical Charms go on the "
            f"crossover Panoply.")
    cost = costs.retainer_charm_cost(ruleset, character)
    entry = _commit(character, "retainer_charms", charm_id, None, None, cost)
    character.retainer_charms.append(charm_id)
    return entry


def learn_submodule(ruleset: RuleSet, character: Character,
                    charm_id: str, key: str) -> XpEntry:
    """Buy an Alchemical submodule (p.89) post-lock for its `xp_cost`. The parent
    Charm must be known and the submodule's own Essence/Attribute minimums met."""
    _ensure_locked(character)
    definition = validate.submodule_def(ruleset, charm_id, key)
    if definition is None:
        raise AdvancementError(f"No submodule {key!r} on Charm {charm_id!r}.")
    if charm_id not in character.charms:
        raise AdvancementError(f"Charm {charm_id!r} is not known; install it first.")
    if any(s.charm_id == charm_id and s.key == key for s in character.submodules):
        raise AdvancementError(f"Submodule {definition.name} is already owned.")
    if character.essence_rating < definition.min_essence:
        raise AdvancementError(
            f"{definition.name} requires Essence {definition.min_essence}.")
    if definition.min_attribute:
        attr = AttributeName(definition.min_attribute)
        if character.attributes.get(attr, 0) < definition.min_attribute_rating:
            raise AdvancementError(
                f"{definition.name} requires {definition.min_attribute} "
                f"{definition.min_attribute_rating}.")
    entry = _commit(character, "submodules", f"{charm_id}:{key}", None, None,
                    definition.xp_cost)
    character.submodules.append(SubmodulePurchase(charm_id=charm_id, key=key))
    return entry


def add_combo(ruleset: RuleSet, character: Character, name: str,
              charm_ids: list[str]) -> XpEntry:
    _ensure_locked(character)
    combo = Combo(name=name, charm_ids=list(charm_ids))
    problems = [i for i in validate.combo_issues(ruleset, character, combo)
                if i.severity == "error"]
    if problems:
        raise AdvancementError(problems[0].message)
    cost = costs.combo_cost(ruleset, charm_ids)
    entry = _commit(character, "combos", name, None, None, cost)
    character.combos.append(combo)
    return entry


def add_array(ruleset: RuleSet, character: Character, name: str,
              charm_ids: list[str]) -> XpEntry:
    """Buy an Alchemical Array post-lock (p.89) for the sum of its member Charms'
    minimum Attribute ratings. Legality is `validate.array_issues` plus the two
    cross-Array rules `validate_arrays` adds — only a Charm-Slot splat may build
    Arrays, and a Charm may sit in only one — checked here against the Arrays the
    character already holds so a post-lock purchase cannot reuse a linked Charm."""
    _ensure_locked(character)
    if not validate.uses_charm_slots(ruleset, character):
        raise AdvancementError(
            "Only Alchemical Exalted build Arrays (Eclipse and Moonshadow Caste "
            "may not, p.90).")
    array = Array(name=name, charm_ids=list(charm_ids))
    problems = [i for i in validate.array_issues(ruleset, character, array)
                if i.severity == "error"]
    if problems:
        raise AdvancementError(problems[0].message)
    linked = {cid for existing in character.arrays for cid in existing.charm_ids}
    reused = [cid for cid in charm_ids if cid in linked]
    if reused:
        charm = ruleset.charms.get(reused[0])
        raise AdvancementError(
            f"{charm.name if charm else reused[0]} is already linked into another "
            "Array; a Charm may join only one Array unless purchased again.")
    cost = costs.array_cost(ruleset, charm_ids)
    entry = _commit(character, "arrays", name, None, None, cost)
    character.arrays.append(array)
    return entry


def learn_ox_body(ruleset: RuleSet, character: Character, variant_key: str,
                  *, dedicated: bool = False) -> XpEntry:
    """Buy one more Ox-Body Technique with the chosen health-level package (post-lock).
    Gated by the splat's once-per-dot-of-cap-trait limit (Endurance, Stamina for Lunar,
    Essence for Alchemical). Priced as a normal new Charm — EXCEPT for a Charm-Slot
    splat (Alchemical), where every purchase installs the Charm in its own Slot (user
    ruling), so it costs a Slot (General 12 / Dedicated 10) and raises the Slot count.
    `dedicated` chooses the Slot kind and is ignored by non-Slot splats."""
    _ensure_locked(character)
    charm = validate.ox_body_charm(ruleset, character)
    if charm is None:
        raise AdvancementError("Ox-Body Technique is not in the RuleSet.")
    variant = next((v for v in charm.variants if v.key == variant_key), None)
    if variant is None:
        raise AdvancementError(f"Unknown Ox-Body package {variant_key!r}.")
    if character.essence_rating < charm.min_essence:
        raise AdvancementError(
            f"Ox-Body Technique requires Essence {charm.min_essence}.")
    cap = validate.ox_body_cap(ruleset, character)
    if len(character.ox_body) >= cap:
        raise AdvancementError(
            f"Ox-Body Technique may be bought at most once per dot of "
            f"{validate.repeatable_cap_trait_name(charm)} ({cap}).")
    purchase = OxBodyPurchase(variant=variant_key, health_levels=list(variant.health_levels))
    if validate.uses_charm_slots(ruleset, character):
        if dedicated and not validate.charm_fits_dedicated_slot(ruleset, character, charm):
            raise AdvancementError(
                f"{charm.name} is not keyed to a Caste/Favored Attribute; it cannot "
                f"fill a Dedicated Slot.")
        g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
        cost = costs.charm_slot_cost(ruleset, character, dedicated=dedicated)
        kind = "dedicated" if dedicated else "general"
        frm = d if dedicated else g
        entry = _commit(character, f"ox_body_slot.{kind}", variant_key, frm, frm + 1, cost)
        if dedicated:
            character.dedicated_charm_slots = d + 1
        else:
            character.general_charm_slots = g + 1
        character.ox_body.append(purchase)
        return entry
    cost = costs.ox_body_cost(ruleset, character)
    entry = _commit(character, "ox_body", variant_key, None, None, cost)
    character.ox_body.append(purchase)
    return entry


def learn_martial_arts_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    """Learn a Martial Arts Charm through Perfected Lotus Matrix (p.100): a Terrestrial/
    Celestial style, learned "as any other Celestial Exalt", for the flat MA rate (11).
    Stored inside the Matrix — it uses NO Charm Slot — so it is added to `charms` but
    the Slot accounting skips it (validate.charm_occupies_slot)."""
    _ensure_locked(character)
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if not validate.is_martial_arts_charm(charm):
        raise AdvancementError(f"{charm.name} is not a Martial Arts Charm.")
    if not validate.has_perfected_lotus_matrix(character):
        raise AdvancementError(
            "Learning Martial Arts Charms requires Perfected Lotus Matrix installed (p.100).")
    if charm_id in character.charms:
        raise AdvancementError(f"{charm.name} is already known.")
    if not validate.charm_matches_splat(character, charm, ruleset):
        raise AdvancementError(
            f"{charm.name} is not a Terrestrial/Celestial style available through "
            f"Perfected Lotus Matrix.")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    cost = costs.martial_arts_charm_cost(ruleset, character)
    entry = _commit(character, "martial_arts", charm_id, None, None, cost)
    character.charms.append(charm_id)
    return entry


def learn_gift(ruleset: RuleSet, character: Character, gift_keys: list[str]) -> XpEntry:
    """Buy one more purchase of the Gift-granting Charm (Deadly Beastman
    Transformation, p.124-127) with the chosen Gift(s), post-lock. Gated by the
    once-per-point-of-Essence cap; `gift_keys` must match what this purchase
    grants (2 on the first purchase, 1 on each after); each Gift's own
    prerequisites (among the character's already-known Gifts and the rest of
    this same purchase, taken as one atomic set — the rulebook applies a
    purchase's Gifts together, p.124) and repeat cap must hold. Priced as a
    normal new Charm regardless of how many Gifts are chosen."""
    _ensure_locked(character)
    charm = validate.gift_charm(ruleset, character)
    if charm is None:
        raise AdvancementError("Deadly Beastman Transformation is not in the RuleSet.")
    if character.essence_rating < charm.min_essence:
        raise AdvancementError(f"{charm.name} requires Essence {charm.min_essence}.")
    cap = validate.gift_purchase_cap(ruleset, character)
    if len(character.beastman_gifts) >= cap:
        raise AdvancementError(
            f"{charm.name} may be bought at most once per point of Essence ({cap}).")
    expected = validate.gifts_per_purchase(charm, len(character.beastman_gifts))
    if len(gift_keys) != expected:
        raise AdvancementError(
            f"This purchase of {charm.name} grants {expected} Gift(s); "
            f"{len(gift_keys)} were chosen.")
    variants_by_key = {v.key: v for v in charm.variants}
    known = validate.known_gift_keys(character)
    available = set(known) | set(gift_keys)
    counts: dict[str, int] = {}
    for key in known:
        counts[key] = counts.get(key, 0) + 1
    for key in gift_keys:
        variant = variants_by_key.get(key)
        if variant is None:
            raise AdvancementError(f"Unknown Gift {key!r}.")
        if variant.prerequisites and not all(
                any(pid in available for pid in group) for group in variant.prerequisites):
            raise AdvancementError(f"Gift {variant.label!r} needs its prerequisite Gift first.")
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > variant.max_purchases:
            raise AdvancementError(
                f"Gift {variant.label!r} may be taken at most "
                f"{variant.max_purchases} time(s).")
    cost = costs.gift_cost(ruleset, character)
    entry = _commit(character, "beastman_gifts", "|".join(gift_keys), None, None, cost)
    character.beastman_gifts.append(BeastmanGiftPurchase(gifts=list(gift_keys)))
    return entry


def add_specialty(ruleset: RuleSet, character: Character, ability: AbilityName,
                  name: str) -> XpEntry:
    _ensure_locked(character)
    if not name.strip():
        raise AdvancementError("A specialty needs a name.")
    cost = costs.specialty_cost(ruleset, character)
    entry = _commit(character, "specialties", f"{ability.value}:{name}", None, None, cost)
    character.specialties.append(Specialty(ability=ability, name=name, rating=1))
    return entry


# --------------------------------------------------------------------------- #
# Undo (LIFO)
# --------------------------------------------------------------------------- #

def undo_last(ruleset: RuleSet, character: Character) -> XpEntry:
    """Reverse the most recent XP purchase: undo its trait change and drop the log
    row. Last-in-first-out so prerequisites and Combo members are always removed
    after the things that depend on them."""
    if not character.xp_log:
        raise AdvancementError("Nothing to undo.")
    entry = character.xp_log[-1]
    domain, _, key = entry.target.partition(".")

    if domain == "attributes":
        character.attributes[AttributeName(key)] = entry.from_rating
    elif domain == "abilities":
        character.abilities[AbilityName(key)] = entry.from_rating
    elif domain == "crafts":
        for i in range(len(character.crafts) - 1, -1, -1):
            if character.crafts[i].focus == entry.detail:
                if entry.from_rating and entry.from_rating > 0:
                    character.crafts[i].rating = entry.from_rating
                else:                       # was a freshly-learned craft -> remove it
                    del character.crafts[i]
                break
    elif domain == "colleges":
        for i in range(len(character.colleges) - 1, -1, -1):
            if character.colleges[i].college_id == entry.detail:
                if entry.from_rating and entry.from_rating > 0:
                    character.colleges[i].rating = entry.from_rating
                else:                       # was a freshly-learned college -> remove it
                    del character.colleges[i]
                break
    elif domain == "virtues":
        character.virtues[VirtueName(key)] = entry.from_rating
    elif domain == "willpower":
        # Reverse exactly the delta this row applied: a raise (+1) or a reduction (-1).
        character.willpower_purchased -= (entry.to_rating - entry.from_rating)
    elif domain == "essence":
        character.essence_rating = entry.from_rating
    elif domain == "charms":
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "crossover_charms":
        # An Eclipse/Moonshadow Alchemical Charm: drop it AND the General Slot it granted.
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
        character.general_charm_slots = (character.general_charm_slots or 0) - 1
    elif domain == "charm_slots":
        # Reverse a bought Slot: uninstall its bundled Charm and drop the Slot count.
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
        if key == "dedicated":
            character.dedicated_charm_slots = entry.from_rating
        else:
            character.general_charm_slots = entry.from_rating
    elif domain == "charm_slot_upgrade":
        # Reverse a Dedicated->General upgrade: give the Dedicated Slot back.
        character.dedicated_charm_slots = (character.dedicated_charm_slots or 0) + 1
        character.general_charm_slots = (character.general_charm_slots or 0) - 1
    elif domain == "retainer_charms":
        if entry.detail in character.retainer_charms:
            character.retainer_charms.remove(entry.detail)
    elif domain == "spells":
        if entry.detail in character.spells:
            character.spells.remove(entry.detail)
    elif domain == "combos":
        for i in range(len(character.combos) - 1, -1, -1):
            if character.combos[i].name == entry.detail:
                del character.combos[i]
                break
    elif domain == "arrays":
        for i in range(len(character.arrays) - 1, -1, -1):
            if character.arrays[i].name == entry.detail:
                del character.arrays[i]
                break
    elif domain == "specialties":
        ab, _, spec_name = entry.detail.partition(":")
        for i in range(len(character.specialties) - 1, -1, -1):
            s = character.specialties[i]
            if s.ability.value == ab and s.name == spec_name:
                del character.specialties[i]
                break
    elif domain == "ox_body":
        # LIFO: drop the most recent purchase of the undone variant.
        for i in range(len(character.ox_body) - 1, -1, -1):
            if character.ox_body[i].variant == entry.detail:
                del character.ox_body[i]
                break
    elif domain == "ox_body_slot":
        # An Alchemical Ox-Body purchase: drop the purchase AND give back its Slot.
        for i in range(len(character.ox_body) - 1, -1, -1):
            if character.ox_body[i].variant == entry.detail:
                del character.ox_body[i]
                break
        if key == "dedicated":
            character.dedicated_charm_slots = entry.from_rating
        else:
            character.general_charm_slots = entry.from_rating
    elif domain == "martial_arts":
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "beastman_gifts":
        # LIFO: drop the most recent purchase with this exact Gift set.
        for i in range(len(character.beastman_gifts) - 1, -1, -1):
            if "|".join(character.beastman_gifts[i].gifts) == entry.detail:
                del character.beastman_gifts[i]
                break
    elif domain == "submodules":
        for i in range(len(character.submodules) - 1, -1, -1):
            s = character.submodules[i]
            if f"{s.charm_id}:{s.key}" == entry.detail:
                del character.submodules[i]
                break

    character.xp_log.pop()
    return entry


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def _expected_cost(ruleset: RuleSet, character: Character, entry: XpEntry) -> int | None:
    """Recompute what `entry` should have cost from the XP table, or None when it
    cannot be priced (e.g. an id no longer in the rule set)."""
    domain, _, key = entry.target.partition(".")
    frm = entry.from_rating
    # A permanent reduction (curse / Charm cost) is free and refunds no XP.
    if frm is not None and entry.to_rating is not None and entry.to_rating < frm:
        return 0
    if domain == "attributes" and frm is not None:
        attr = AttributeName(key) if key else None
        return costs.attribute_step(ruleset, character, frm, attr)
    if domain == "abilities" and frm is not None:
        return costs.ability_step(ruleset, character, AbilityName(key), frm)
    if domain == "crafts" and frm is not None:
        return costs.ability_step(ruleset, character, AbilityName.CRAFT, frm)
    if domain == "colleges" and frm is not None:
        return (costs.college_new_cost(ruleset, character) if frm <= 0
                else costs.college_step(ruleset, character, frm))
    if domain == "virtues" and frm is not None:
        return costs.virtue_step(ruleset, character, frm)
    if domain == "willpower" and frm is not None:
        return costs.willpower_step(ruleset, character, frm)
    if domain == "essence" and frm is not None:
        return costs.essence_step(ruleset, character, frm)
    if domain in ("charms", "crossover_charms"):
        charm = ruleset.charms.get(entry.detail)
        return costs.charm_cost(ruleset, character, charm) if charm else None
    if domain == "spells":
        spell = ruleset.spells.get(entry.detail)
        return costs.spell_cost(ruleset, character, spell) if spell else None
    if domain == "charm_slots":
        return costs.charm_slot_cost(ruleset, character, dedicated=(key == "dedicated"))
    if domain == "charm_slot_upgrade":
        return costs.charm_slot_upgrade_cost(ruleset, character)
    if domain == "retainer_charms":
        return costs.retainer_charm_cost(ruleset, character)
    if domain == "specialties":
        return costs.specialty_cost(ruleset, character)
    if domain == "combos":
        combo = next((c for c in character.combos if c.name == entry.detail), None)
        return costs.combo_cost(ruleset, combo.charm_ids) if combo else None
    if domain == "arrays":
        array = next((a for a in character.arrays if a.name == entry.detail), None)
        return costs.array_cost(ruleset, array.charm_ids) if array else None
    if domain == "ox_body":
        return costs.ox_body_cost(ruleset, character)
    if domain == "ox_body_slot":
        return costs.charm_slot_cost(ruleset, character, dedicated=(key == "dedicated"))
    if domain == "martial_arts":
        return costs.martial_arts_charm_cost(ruleset, character)
    if domain == "beastman_gifts":
        return costs.gift_cost(ruleset, character)
    if domain == "submodules":
        cid, _, k = entry.detail.partition(":")
        definition = validate.submodule_def(ruleset, cid, k)
        return definition.xp_cost if definition is not None else None
    return None


def validate_xp(ruleset: RuleSet, character: Character) -> list[validate.Issue]:
    """Audit the XP log of a locked character: no overspend, and each row priced at
    the table rate. Pure (returns Issues; mutates nothing). Empty for an unlocked
    character — XP is a post-lock concern."""
    if not character.chargen_locked or character.chargen_snapshot is None:
        return []
    issues: list[validate.Issue] = []
    spent = xp_spent(character)
    if spent > character.xp_earned:
        issues.append(validate.Issue(
            code="xp-overspent",
            message=f"Spent {spent} XP but only {character.xp_earned} earned.",
        ))
    for entry in character.xp_log:
        expected = _expected_cost(ruleset, character, entry)
        if expected is not None and expected != entry.cost:
            issues.append(validate.Issue(
                code="xp-cost-mismatch", where=entry.target,
                message=(f"{entry.target}: logged {entry.cost} XP, "
                         f"table rate is {expected}."),
            ))
    issues.append(validate.Issue(
        code="xp-summary", severity="info",
        message=f"{spent} of {character.xp_earned} XP spent "
                f"({xp_available(character)} available).",
    ))
    return issues
