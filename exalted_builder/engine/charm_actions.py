"""
engine/charm_actions.py — the Charm, spell and variant-menu purchase dispatchers.

Each function dispatches on the lock: a chargen list edit before it, an
`engine.advancement` purchase after it. Each returns the message the caller should
show, and raises `advancement.AdvancementError` when the purchase is refused. None of
them decides legality — the gates come from `engine.validate`.

This is `engine/thaum_actions.py`'s shape applied to the Charm picker, and for the
same reason: two shells now drive these purchases (`ui/picker.py` and
`qt/charms.py`), and a picker-local copy in each is a rules bug waiting to happen.

⚠ **The raised type is part of the contract.** Both shells catch
`advancement.AdvancementError` to turn a refusal into a notification; a different
exception type here becomes a traceback instead of "prerequisites not met".

**Naming.** `learn_charm` / `learn_spell` share a name with the
`engine.advancement` function they call after the lock. Read `charm_actions.x` as
"the lock-aware x", `advancement.x` as "the XP purchase" — the same split
`thaum_actions` documents.

⚠ **A variant-menu Charm is NOT toggleable and must be refused here.** Ox-Body
Technique and Deadly Beastman Transformation are bought as a PACKAGE (a variant key,
a Gift list) into their own character fields, `ox_body` and `beastman_gifts` — never
by appending the Charm id to `character.charms`. The web picker avoids this by
branching in its detail card before an Add button is ever drawn, which is a guard in
a widget: the Qt picker toggles straight from a node click and had no such branch, so
it would have mis-written the purchase. `variant_menu_reason` is that guard moved
where both shells run it.
"""

from __future__ import annotations

from ..models.character import (BeastmanGiftPurchase, Character, OxBodyPurchase,
                                SubmodulePurchase)
from ..models.rules import RuleSet
from . import advancement, costs, validate


def _refuse(message: str) -> None:
    raise advancement.AdvancementError(message)


def _cap_phrase(charm) -> str:
    """"once per dot of Endurance" — the trait and its unit are per-splat DATA
    (`repeatable_cap_ability`), so no message may hardcode either (Lunar Ox-Body
    counts Stamina, p.132; Deadly Beastman counts Essence, p.124)."""
    trait = validate.repeatable_cap_trait_name(charm)
    unit = validate.repeatable_cap_unit(charm)
    return f"once per {unit} of {trait}" if trait else "its maximum"


def variant_menu_reason(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """Why `charm_id` cannot be learned by an ordinary toggle, or "" when it can.

    The two variant-menu Charms buy into their own fields through `add_ox_body` /
    `add_gift_purchase`; a shell must open its chooser instead of toggling."""
    if charm_id and charm_id == validate.ox_body_charm_id(ruleset, character):
        return ("Ox-Body Technique is bought as a package — choose a health-level "
                "variant from its detail panel.")
    if charm_id and charm_id == validate.gift_charm_id(ruleset, character):
        return ("Deadly Beastman Transformation is bought as a package — choose its "
                "Gifts from its detail panel.")
    return ""


# ---- Charms ------------------------------------------------------------- #

def learn_charm(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """Add one copy of a Charm: an XP purchase after the lock, an append to the
    chargen pick list before it.

    Owned-but-under-cap is a legitimate call on BOTH sides of the lock (the picker's
    "Add another" for a generic repeatable Charm — Mountain Folk Essence Satiation /
    Stone-Still Lungs, CH6 pp.245-246); it is `toggle_charm` that reads a second click
    as a removal."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        _refuse(f"Unknown Charm {charm_id!r}.")
    reason = variant_menu_reason(ruleset, character, charm_id)
    if reason:
        _refuse(reason)
    cap = validate._repeatable_purchase_cap(charm, character)
    if character.chargen_locked:
        # ⚠ The cap is consulted on BOTH sides of the lock. This guard used to be a
        # bare `charm_id in character.charms`, which refused every second copy after
        # the lock — and `advancement.learn_charm` below it has supported exactly that
        # purchase, cap check and page citation included (CH6 pp.245-246), since it was
        # written. A dispatcher guard written for ordinary Charms caught repeatables in
        # its net and made the deliberate support unreachable from either shell.
        if charm_id in character.charms and not cap:
            _refuse(f"{charm.name} is already known — undo the purchase on the "
                    "Edit tab to give it back.")
        if cap and character.charms.count(charm_id) >= cap:
            _refuse(f"{charm.name}: already bought {cap} times — its maximum.")
        cost = costs.charm_cost(ruleset, character, charm)
        advancement.learn_charm(ruleset, character, charm_id)
        return f"Learned {charm.name} — {cost} XP"
    if not validate.meets_charm_requirements(ruleset, character, charm):
        _refuse(f"{charm.name}: prerequisites not met")
    if cap and character.charms.count(charm_id) >= cap:
        _refuse(f"{charm.name}: already bought {cap} times — its maximum.")
    if not cap and charm_id in character.charms:
        _refuse(f"{charm.name} is already known.")
    character.charms.append(charm_id)
    return f"Learned {charm.name}"


def drop_charm(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """Give back one copy of a chargen Charm pick.

    Post-lock this always refuses: a bought Charm is undone from the XP ledger, which
    is what keeps the append-only log and the traits in step (decision 0004)."""
    charm = ruleset.charms.get(charm_id)
    name = charm.name if charm is not None else charm_id
    if charm_id not in character.charms:
        _refuse(f"{name} is not known.")
    if character.chargen_locked:
        _refuse(f"{name} was bought with XP — undo the purchase on the Edit tab "
                "to give it back.")
    blockers = validate.charms_depending_on(ruleset, character, charm_id)
    if blockers:
        _refuse(f"{name}: can't remove — needed by {', '.join(blockers)}")
    character.charms.remove(charm_id)
    return f"Removed {name}"


def toggle_charm(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """The picker's node click: learn an unowned Charm, drop an owned one.

    ⚠ Post-lock this NEVER drops — `learn_charm` refuses an already-known Charm with
    the undo-on-the-Edit-tab message, because a click in a shop is a purchase and a
    second click must not become a refund."""
    if charm_id in character.charms and not character.chargen_locked:
        return drop_charm(ruleset, character, charm_id)
    return learn_charm(ruleset, character, charm_id)


# ---- Spells ------------------------------------------------------------- #

def learn_spell(ruleset: RuleSet, character: Character, spell_id: str) -> str:
    """Add a spell: an XP purchase after the lock, a chargen pick before it. Spells
    share the Charm pool at chargen (core p.100), which the budget accounting handles
    — nothing extra is owed here."""
    spell = ruleset.spells.get(spell_id)
    if spell is None:
        _refuse(f"Unknown spell {spell_id!r}.")
    if character.chargen_locked:
        if spell_id in character.spells:
            _refuse(f"{spell.name} is already known — undo the purchase on the "
                    "Edit tab to give it back.")
        cost = costs.spell_cost(ruleset, character, spell)
        advancement.learn_spell(ruleset, character, spell_id)
        return f"Learned {spell.name} — {cost} XP"
    if spell_id in character.spells:
        _refuse(f"{spell.name} is already known.")
    if not validate.meets_spell_requirements(ruleset, character, spell):
        _refuse(f"{spell.name}: not available")
    character.spells.append(spell_id)
    return f"Learned {spell.name}"


def drop_spell(ruleset: RuleSet, character: Character, spell_id: str) -> str:
    """Give back a chargen spell pick; post-lock, refuse to the XP ledger. No
    dependency guard: nothing in the catalogue takes a spell as a prerequisite (the
    Circle gate is on the Charm, not on the other spells)."""
    spell = ruleset.spells.get(spell_id)
    name = spell.name if spell is not None else spell_id
    if spell_id not in character.spells:
        _refuse(f"{name} is not known.")
    if character.chargen_locked:
        _refuse(f"{name} was bought with XP — undo the purchase on the Edit tab "
                "to give it back.")
    character.spells.remove(spell_id)
    return f"Dropped {name}"


def toggle_spell(ruleset: RuleSet, character: Character, spell_id: str) -> str:
    """The spell list's click. Same post-lock asymmetry as `toggle_charm`."""
    if spell_id in character.spells and not character.chargen_locked:
        return drop_spell(ruleset, character, spell_id)
    return learn_spell(ruleset, character, spell_id)


# ---- Ox-Body Technique (a variant menu, not a toggle) -------------------- #

def add_ox_body(ruleset: RuleSet, character: Character, variant_key: str) -> str:
    """Buy one Ox-Body package. The variant names which health levels it grants; the
    purchase lands in `character.ox_body`, never in `character.charms`."""
    charm = validate.ox_body_charm(ruleset, character)
    if charm is None:
        _refuse("Ox-Body Technique is not in the rule set.")
    variant = next((v for v in charm.variants if v.key == variant_key), None)
    if variant is None:
        _refuse(f"Unknown Ox-Body variant {variant_key!r}.")
    if character.chargen_locked:
        cost = costs.ox_body_cost(ruleset, character)
        advancement.learn_ox_body(ruleset, character, variant_key)
        return f"Bought Ox-Body Technique ({variant.label}) — {cost} XP"
    if len(character.ox_body) >= validate.ox_body_cap(ruleset, character):
        _refuse(f"Ox-Body: already bought {_cap_phrase(charm)}.")
    character.ox_body.append(
        OxBodyPurchase(variant=variant_key, health_levels=list(variant.health_levels)))
    return f"Added Ox-Body Technique ({variant.label})"


def remove_ox_body(character: Character, index: int) -> str:
    """Give back one chargen Ox-Body package by its position in the list."""
    if character.chargen_locked:
        _refuse("That Ox-Body purchase was bought with XP — undo it on the Edit tab.")
    if not 0 <= index < len(character.ox_body):
        _refuse("No such Ox-Body purchase.")
    del character.ox_body[index]
    return "Removed an Ox-Body Technique purchase"


# ---- Deadly Beastman Transformation (a variant menu, multi-pick) --------- #

def add_gift_purchase(ruleset: RuleSet, character: Character, keys: list[str]) -> str:
    """Buy one Deadly Beastman Transformation, granting the Gifts named by `keys`
    (2 on the first purchase, 1 after — p.124). Which Gifts are legal together is the
    chooser's job (`validate.gifts_per_purchase` / the Gift prerequisites); this
    applies the purchase the chooser already assembled."""
    charm = validate.gift_charm(ruleset, character)
    if charm is None:
        _refuse("Deadly Beastman Transformation is not in the rule set.")
    if character.chargen_locked:
        cost = costs.gift_cost(ruleset, character)
        advancement.learn_gift(ruleset, character, keys)
        return (f"Bought Deadly Beastman Transformation ({', '.join(keys)}) — "
                f"{cost} XP")
    if len(character.beastman_gifts) >= validate.gift_purchase_cap(ruleset, character):
        _refuse(f"Deadly Beastman Transformation: already bought {_cap_phrase(charm)}.")
    character.beastman_gifts.append(BeastmanGiftPurchase(gifts=keys))
    return f"Added Deadly Beastman Transformation ({', '.join(keys)})"


def remove_gift_purchase(character: Character, index: int) -> str:
    """Give back one chargen Gift purchase by its position in the list."""
    if character.chargen_locked:
        _refuse("That purchase was bought with XP — undo it on the Edit tab.")
    if not 0 <= index < len(character.beastman_gifts):
        _refuse("No such Deadly Beastman Transformation purchase.")
    del character.beastman_gifts[index]
    return "Removed a Deadly Beastman Transformation purchase"


# ---- Alchemical submodules (p.89) --------------------------------------- #
#
# A submodule permanently upgrades ONE Charm, so it is bought on that Charm's detail
# panel rather than from a catalogue. Dual cost: bonus points at chargen, experience
# after the lock.

def learn_submodule(ruleset: RuleSet, character: Character,
                    charm_id: str, key: str) -> str:
    """Buy one submodule: an XP purchase after the lock, an append to
    `character.submodules` before it (where the bonus-point calc picks it up).

    ⚠ The chargen half checks `validate.submodule_block_reason` — the same gate the
    detail panel greys its button on. Without it a shell that drew the button anyway,
    or one that never asked, could append a submodule whose Essence/Attribute minimum
    the character does not meet."""
    definition = validate.submodule_def(ruleset, charm_id, key)
    if definition is None:
        _refuse(f"No submodule {key!r} on Charm {charm_id!r}.")
    if character.chargen_locked:
        advancement.learn_submodule(ruleset, character, charm_id, key)
        return f"Bought {definition.name} — {definition.xp_cost} XP"
    if validate.owns_submodule(character, charm_id, key):
        _refuse(f"{definition.name} is already owned.")
    reason = validate.submodule_block_reason(ruleset, character, charm_id, key)
    if reason:
        _refuse(f"{definition.name}: {reason}")
    character.submodules.append(SubmodulePurchase(charm_id=charm_id, key=key))
    return f"Added {definition.name}"


def drop_submodule(character: Character, charm_id: str, key: str) -> str:
    """Give back one chargen submodule. Post-lock the only refund is the XP log's
    last-first undo on the Edit tab, exactly as for Charms and Combos."""
    if character.chargen_locked:
        _refuse("That submodule was bought with XP — undo it on the Edit tab.")
    for i in range(len(character.submodules) - 1, -1, -1):
        s = character.submodules[i]
        if s.charm_id == charm_id and s.key == key:
            del character.submodules[i]
            return "Removed a submodule"
    _refuse("No such submodule purchase.")
