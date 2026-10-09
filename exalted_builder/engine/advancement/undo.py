"""
engine/advancement/undo.py — `undo_last`: it reverses the most recent XP log row
(last in, first out).
"""

from __future__ import annotations

from .. import validate
from ...models.character import Character, PassionEntry, ThaumaturgyState, XpEntry
from ...models.rules import AbilityName, AttributeName, Orientation, RuleSet, VirtueName

from ._base import AdvancementError


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
    elif domain == validate.PERMANENT_RESONANCE_TARGET:
        character.limit_permanent = entry.from_rating
    elif domain == validate.WITHHELD_CHARM_TARGET:
        # Removing the row restores the credit, since credits are counted from the log.
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "fetters":
        for f in character.fetters:
            if f.name == entry.detail:
                f.rating = entry.from_rating
                break
    elif domain == "new_fetters":
        character.fetters = [f for f in character.fetters if f.name != entry.detail]
    elif domain == "shift_fetters":
        # `detail` is "old>new"; a shift changed only the NAME, so undo renames back.
        was, _, now = entry.detail.partition(">")
        for f in character.fetters:
            if f.name == now:
                f.name = was
                break
    elif domain == "shift_passions":
        # Move the dot back. The destination may have been created by the shift, in
        # which case undoing it removes the row again rather than leaving a 0-dot one.
        was, _, now = entry.detail.partition(">")
        dst = next((x for x in character.passions if x.name == now), None)
        src = next((x for x in character.passions if x.name == was), None)
        if dst is not None:
            dst.rating -= 1
            if src is None:
                character.passions.append(
                    PassionEntry(name=was, virtue=dst.virtue, rating=1))
            else:
                src.rating += 1
            if dst.rating == 0:
                character.passions.remove(dst)
    elif domain == "charms":
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "elemental_powers":
        if entry.detail in character.elemental_powers:
            character.elemental_powers.remove(entry.detail)
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
    elif domain == "merits":
        if entry.removed_purchase is not None:
            # A DROP reversed: re-add the exact purchase the row removed. LIFO — no
            # later row can exist, so appending restores the held state as it was.
            character.merits_flaws.append(entry.removed_purchase)
        elif entry.detail.startswith("-"):
            # A drop logged before the row carried `removed_purchase` (an older save):
            # the removed purchase cannot be reconstructed. Refuse rather than pop the
            # row and strand the Merit's XP.
            raise AdvancementError(
                "Cannot undo a Merit/Flaw removal from an older save.")
        else:
            # A buy or gain reversed: drop the LAST matching purchase. LIFO — a
            # repeatable Merit held twice must undo one copy, and the logged one is
            # the newest.
            for i in range(len(character.merits_flaws) - 1, -1, -1):
                if character.merits_flaws[i].merit_id == entry.detail:
                    del character.merits_flaws[i]
                    break
    elif domain == "beastman_gifts":
        # LIFO: drop the most recent purchase with this exact Gift set.
        for i in range(len(character.beastman_gifts) - 1, -1, -1):
            if "|".join(character.beastman_gifts[i].gifts) == entry.detail:
                del character.beastman_gifts[i]
                break
    elif domain == "variant_purchases":
        # detail is "<charm_id>:<key|key>"; a charm id holds no colon, so partition
        # from the left. LIFO: drop the most recent purchase that matches exactly.
        cid, _, keys = entry.detail.partition(":")
        for i in range(len(character.variant_purchases) - 1, -1, -1):
            vp = character.variant_purchases[i]
            if vp.charm_id == cid and "|".join(vp.variants) == keys:
                del character.variant_purchases[i]
                break
    elif domain == "submodules":
        for i in range(len(character.submodules) - 1, -1, -1):
            s = character.submodules[i]
            if f"{s.charm_id}:{s.key}" == entry.detail:
                del character.submodules[i]
                break
    elif domain.startswith("thaum_") and character.thaumaturgy is not None:
        _undo_thaum(character.thaumaturgy, domain, key, entry.detail, entry.from_rating)

    character.xp_log.pop()
    return entry


def _undo_thaum(state: ThaumaturgyState, domain: str, key: str, detail: str,
                entry_from: int | None = None) -> None:
    """Reverse one thaumaturgy purchase. Split out because the five kinds live on five
    lists; LIFO ordering is `undo_last`'s job, so this only has to find and drop."""
    if domain == "thaum_arts":
        if detail in state.arts:
            state.arts.remove(detail)
    elif domain == "thaum_specialties":
        art_id, _, name = detail.partition(":")
        for i in range(len(state.art_specialties) - 1, -1, -1):
            s = state.art_specialties[i]
            if s.art_id == art_id and s.name == name:
                del state.art_specialties[i]
                break
    elif domain == "thaum_sciences":
        for i in range(len(state.sciences) - 1, -1, -1):
            if state.sciences[i].science_id == detail:
                if entry_from and entry_from > 0:
                    state.sciences[i].rating = entry_from
                else:                       # was a freshly-learned Science -> remove it
                    del state.sciences[i]
                break
    elif domain == "thaum_rituals":
        for i in range(len(state.rituals) - 1, -1, -1):
            if (state.rituals[i].ritual_id or state.rituals[i].name) == detail:
                del state.rituals[i]
                break
    elif domain == "thaum_formulas":
        for i in range(len(state.formulas) - 1, -1, -1):
            if (state.formulas[i].formula_id or state.formulas[i].name) == detail:
                del state.formulas[i]
                break
    elif domain == "thaum_orientations":
        # detail is "<key>:<Orientation>"; rsplit because a custom name may contain ':'.
        entry_key, _, region = detail.rpartition(":")
        entries = state.rituals if key == "ritual" else state.formulas
        for e in entries:
            if ((e.ritual_id if key == "ritual" else e.formula_id) or e.name) != entry_key:
                continue
            orientation = Orientation(region)
            # Never strip the last orientation: an entry with none is not a state the
            # model allows, and the base purchase paid for one.
            if orientation in e.orientations and len(e.orientations) > 1:
                e.orientations.remove(orientation)
            break
