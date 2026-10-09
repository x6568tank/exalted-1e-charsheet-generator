"""
engine/advancement/magic.py — the new-magic purchases: Charms, Elemental Powers,
spells, Combos, Arrays, Ox-Body packages, martial-arts Charms, Gifts, and variant
purchases.
"""

from __future__ import annotations

from .. import costs, merits, validate
from ...models.character import (Array, BeastmanGiftPurchase, Character, Combo,
                                 OxBodyPurchase, VariantPurchase, XpEntry)
from ...models.rules import RuleSet

from ._base import AdvancementError, _commit, _ensure_locked


# --------------------------------------------------------------------------- #
# New traits
# --------------------------------------------------------------------------- #

def learn_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    _ensure_locked(character)
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if charm_id in character.charms:
        # A generic repeatable Charm (the Mountain Folk Essence Satiation Method and
        # Stone-Still Lungs, CH6 pp.245-246) may be learned once per purchase, up to
        # its trait cap. Every other Charm is single-pick and re-learning is an error.
        cap = validate._repeatable_purchase_cap(charm, character)
        if not cap or character.charms.count(charm_id) >= cap:
            raise AdvancementError(f"{charm.name} is already known.")
    # A Charm-Slot splat (Alchemical) does not learn Charms per-pick: it buys a Slot
    # (buy_charm_slot) or a Panoply Charm (learn_retainer_charm). Route callers there
    # so a Slot is never silently skipped.
    if validate.uses_charm_slots(ruleset, character):
        raise AdvancementError(
            f"{charm.name}: Alchemicals gain Charms by buying a Charm Slot or a "
            f"Panoply (retainer) Charm, not directly.")
    # A splat barred from Charms outright (mortals, core p.103) is refused first and
    # by name: the generic message below blames the Charm's splat, which reads as
    # nonsense for an `open_to_all` Charm that belongs to no one splat.
    #
    # The bar is not absolute — a Merit reopens part of it (Essence Mastery grants
    # Terrestrial Martial Arts, PG p.121), and chargen already honours that through
    # charm_matches_splat. Ask the same question here rather than the splat flag
    # alone, or a Charm a mortal may legally pick at creation becomes unbuyable the
    # moment they lock.
    if (not validate.charms_available(ruleset, character)
            and not validate.charm_matches_splat(character, charm, ruleset)):
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters cannot "
            f"purchase Charms (core p.103).")
    # A splat whose Essence pool requires unlocking (God-Blooded, PG p.66 — the pool
    # comes from the Awakened Essence Merit) may not purchase Charms until it is:
    # p.49, "Only God-Blooded with the Awakened Essence Merit may purchase or increase
    # magical Traits." The pool unlock IS the gate. Mirrored in validate for chargen.
    if (validate.pool_requires_unlocking(ruleset, character)
            and not merits.merits_and_flaws_calc(
                ruleset, character).essence_pool_unlocked):
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters must hold "
            f"the Awakened Essence Merit to purchase Charms (PG p.49).")
    # A Charm of the character's OWN splat that charm_learnable_by_splat still refuses
    # is a heritage bar (a Fae-Blooded holding a God-Blooded Arcanos, p.47 "do not use
    # Charms"), not a foreign Charm — "belongs to another Exalt type" would be actively
    # misleading for a God-Blooded, the same call the mortal branch above makes.
    if (validate.splat_of(charm) == character.exalt_type
            and not validate.charm_learnable_by_splat(ruleset, character, charm)):
        raise AdvancementError(
            f"{charm.name} belongs to the {character.exalt_type} splat but is barred "
            f"for this character.")
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
    # A chargen pick banked by a Flaw (Weak Essence, p.41) pays for this Charm instead
    # of XP. Logged under its OWN target rather than as a zero-cost `charms` row: the
    # XP audit re-prices every entry from the table, so a 0 filed as `charms` would be
    # reported as a mismatch forever after. The distinct target is also what makes the
    # credits countable — see validate.withheld_charm_credits.
    target = "crossover_charms" if grants_slot else "charms"
    if not grants_slot and cost > 0:
        _granted, remaining = validate.withheld_charm_credits(ruleset, character)
        if remaining > 0:
            target, cost = validate.WITHHELD_CHARM_TARGET, 0
    entry = _commit(character, target, charm_id, None, None, cost)
    character.charms.append(charm_id)
    if grants_slot:
        g, _d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
        character.general_charm_slots = g + 1
    return entry


def learn_elemental_power(ruleset: RuleSet, character: Character, power_id: str) -> XpEntry:
    """Learn an elemental power in play (PG p.68): 14 XP (7 BP doubled). Simpler than
    learn_charm — no splat/foreign/withheld-credit machinery — because the catalogue
    belongs to exactly one origin and the cost table is flat."""
    _ensure_locked(character)
    power = ruleset.elemental_powers.get(power_id)
    if power is None:
        raise AdvancementError(f"Unknown elemental power {power_id!r}.")
    if power_id in character.elemental_powers:
        raise AdvancementError(f"{power.name} is already known.")
    if not validate.elemental_powers_available(ruleset, character):
        raise AdvancementError(
            "Only Elemental-origin God-Blooded may learn elemental powers (PG p.68).")
    if not validate.meets_elemental_power_requirements(ruleset, character, power):
        shortfalls = "; ".join(
            validate.elemental_power_shortfalls(ruleset, character, power))
        raise AdvancementError(f"{power.name}: requirements not met ({shortfalls}).")
    cost = costs.elemental_power_xp(ruleset, character, power)
    entry = _commit(character, "elemental_powers", power_id, None, None, cost)
    character.elemental_powers.append(power_id)
    return entry


def learn_spell(ruleset: RuleSet, character: Character, spell_id: str) -> XpEntry:
    _ensure_locked(character)
    spell = ruleset.spells.get(spell_id)
    if spell is None:
        raise AdvancementError(f"Unknown spell {spell_id!r}.")
    if spell_id in character.spells:
        raise AdvancementError(f"{spell.name} is already known.")
    # The same Merit gate as learn_charm: a God-Blooded may not buy spells without the
    # unlocked pool (p.49). The Spell itself is cross-splat, so the splat check has to
    # live here rather than on any spell.
    if (validate.pool_requires_unlocking(ruleset, character)
            and not merits.merits_and_flaws_calc(
                ruleset, character).essence_pool_unlocked):
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters must hold "
            f"the Awakened Essence Merit to purchase spells (PG p.49).")
    # Post-lock the chargen Solar-Circle bar lifts; only circle access is required.
    if not validate.meets_spell_requirements(ruleset, character, spell, chargen=False):
        raise AdvancementError(f"{spell.name}: no known Charm grants its Circle.")
    cost = costs.spell_cost(ruleset, character, spell)
    entry = _commit(character, "spells", spell_id, None, None, cost)
    character.spells.append(spell_id)
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


def learn_variant_purchase(ruleset: RuleSet, character: Character,
                           charm_id: str, variant_keys: list[str]) -> XpEntry:
    """Buy one more purchase of a generic variant-menu Charm post-lock (Environmental
    Hazard-Resisting Meditation, Zenith p.72-73). Priced as a normal new Charm.

    Gated by the Charm's min essence, its purchase cap, and — when it marks its
    variants unique — the versions already taken."""
    _ensure_locked(character)
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if not validate.is_variant_menu_charm(ruleset, character, charm):
        raise AdvancementError(f"{charm.name} is not a variant-menu Charm.")
    if character.essence_rating < charm.min_essence:
        raise AdvancementError(f"{charm.name} requires Essence {charm.min_essence}.")
    held = validate.variant_purchases_for(character, charm_id)
    cap = validate.variant_purchase_cap(ruleset, character, charm)
    if len(held) >= cap:
        raise AdvancementError(
            f"{charm.name}: already bought {cap} times — its maximum.")
    expected = validate.gifts_per_purchase(charm, len(held))
    if len(variant_keys) != expected:
        raise AdvancementError(
            f"This purchase of {charm.name} grants {expected} version(s); "
            f"{len(variant_keys)} were chosen.")
    by_key = {v.key: v for v in charm.variants}
    known = validate.known_variant_keys(character, charm_id)
    for key in variant_keys:
        if key not in by_key:
            raise AdvancementError(f"Unknown version {key!r}.")
        if charm.variants_unique and key in known:
            raise AdvancementError(
                f"{by_key[key].label} has already been taken.")
    cost = costs.variant_purchase_cost(ruleset, character, charm)
    entry = _commit(character, "variant_purchases",
                    f"{charm_id}:{'|'.join(variant_keys)}", None, None, cost)
    character.variant_purchases.append(
        VariantPurchase(charm_id=charm_id, variants=list(variant_keys)))
    return entry
