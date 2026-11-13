"""
engine/refit.py — the Alchemical vat refit: moving Charms between the Charm Slots
and the Panoply (CH2/CH3, p.88-89).

An Alchemical OWNS more Charms than the Slots hold. Installed Charms are in Slots and
commit Personal Essence. The others are in the Panoply, owned but inert. This module
is the one place that moves a Charm between the two.

**Play state, not chargen and not XP.** A refit costs nothing and writes no XP entry.
⚠ Do not use `validate.charm_slot_usage`: it reads the chargen snapshot. This module
calculates the live load. Nothing here feeds chargen validation, the XP audit, or the
permanent derivations.

A refit still respects the Slots: a Charm needs a free Slot of a kind it fits
(Dedicated: Caste/Favored Charms only), and the installation motes must fit the
Personal pool.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.character import Character
from ..models.rules import RuleSet
from . import derive, validate


class RefitError(Exception):
    """A refit that the Slot rules refuse."""


@dataclass
class SlotLoad:
    """The LIVE Slot picture — what is worn right now, as opposed to
    `validate.charm_slot_usage`, which reports the frozen chargen build."""
    general: int          # General Slots the character has
    dedicated: int        # Dedicated Slots the character has
    installed: int        # Slots currently occupied
    noncf: int            # of those, Charms needing a General Slot
    motes: int            # committed installation cost
    personal: int         # the pool those motes come from (merged pool when merged)

    @property
    def total_slots(self) -> int:
        return self.general + self.dedicated

    @property
    def free_slots(self) -> int:
        return self.total_slots - self.installed

    @property
    def free_general(self) -> int:
        return self.general - self.noncf

    @property
    def free_motes(self) -> int:
        return self.personal - self.motes


def supports_refit(ruleset: RuleSet, character: Character) -> bool:
    """Whether this character has a Slot/Panoply to manage at all — a Charm-Slot
    splat, or a non-Alchemical who picked up Alchemical Charms (and with them either
    a crossover Slot or a Panoply entry) through the p.90 generalist rule."""
    if validate.uses_charm_slots(ruleset, character):
        return True
    return bool(character.retainer_charms) or bool(character.general_charm_slots)


def _slot_charms(ruleset: RuleSet, character: Character) -> list[str]:
    """The installed Charm ids that actually occupy a Slot, in character order. PLM
    Martial Arts Charms are installed but Slot-free (they live inside the Matrix), so
    they are not refittable and do not appear."""
    return [cid for cid in character.charms
            if (charm := ruleset.charms.get(cid)) is not None
            and validate.charm_occupies_slot(ruleset, character, charm)]


def slot_load(ruleset: RuleSet, character: Character) -> SlotLoad:
    """The live Slot occupancy and committed Essence. Each Ox-Body purchase occupies a
    Slot too (user ruling: every Alchemical Charm does) and is counted, though it is
    not itself refittable — it lives on `character.ox_body`, not `charms`."""
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    installed = noncf = 0
    for cid in _slot_charms(ruleset, character):
        installed += 1
        if not validate.charm_fits_dedicated_slot(ruleset, character, ruleset.charms[cid]):
            noncf += 1
    ob = validate.ox_body_charm(ruleset, character)
    if ob is not None and character.ox_body:
        installed += len(character.ox_body)
        if not validate.charm_fits_dedicated_slot(ruleset, character, ob):
            noncf += len(character.ox_body)
    motes = validate._installation_motes(
        ruleset, _slot_charms(ruleset, character) + ([ob.id] * len(character.ox_body)
                                                     if ob is not None else []),
        character.arrays)
    return SlotLoad(general=g, dedicated=d, installed=installed, noncf=noncf,
                    motes=motes,
                    personal=derive.charm_installation_pool(ruleset, character))


def install_block_reason(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """Why `charm_id` cannot be installed from the Panoply right now — "" when it can.
    Checks Slot availability (a non-Caste/Favored Charm needs a *General* Slot
    specifically) and the Personal Essence the installation would commit."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        return "Not in the rule set."
    if charm_id in character.charms:
        return "Already installed."
    if charm_id not in character.retainer_charms:
        return "Not in the Panoply."
    load = slot_load(ruleset, character)
    if load.free_slots < 1:
        return f"No free Charm Slot ({load.installed}/{load.total_slots} used)."
    if not validate.charm_fits_dedicated_slot(ruleset, character, charm) \
            and load.free_general < 1:
        return (f"Only Dedicated Slots are free, and they take Caste/Favored "
                f"Charms only ({load.noncf}/{load.general} General used).")
    # Arrays discount the combined cost, so ask for the delta the whole set would move
    # by rather than this Charm's sticker price.
    after = validate._installation_motes(
        ruleset, _slot_charms(ruleset, character) + [charm_id], character.arrays)
    if after > load.personal:
        return (f"Installing commits {after}m of a {load.personal}m Personal pool.")
    return ""


def uninstall_block_reason(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """Return why `charm_id` cannot move to the Panoply, or "" if it can. The Charm
    must be installed in a Slot, and a `permanent_install` Charm (p.141) never comes
    out.

    A prerequisite of an installed Charm is NOT a bar: a Panoply Charm is still owned.
    An uninstall never cascades."""
    charm = ruleset.charms.get(charm_id)
    if charm_id not in character.charms:
        return "Not installed."
    if charm is None:
        return ""
    if not validate.charm_occupies_slot(ruleset, character, charm):
        return (f"Held in the Perfected Lotus Matrix, not a Charm Slot, so it cannot "
                f"move to the Panoply.")
    if charm.permanent_install:
        return "Can never be removed once installed (p.141)."
    return ""


def uninstall(ruleset: RuleSet, character: Character, charm_id: str) -> None:
    """Move an installed Charm into the Panoply."""
    reason = uninstall_block_reason(ruleset, character, charm_id)
    if reason:
        raise RefitError(f"{ruleset.charms[charm_id].name}: {reason}"
                         if charm_id in ruleset.charms else reason)
    character.charms.remove(charm_id)
    if charm_id not in character.retainer_charms:
        character.retainer_charms.append(charm_id)


def install(ruleset: RuleSet, character: Character, charm_id: str) -> None:
    """Move a Panoply Charm into a Charm Slot, if the Slot and Essence rules allow."""
    reason = install_block_reason(ruleset, character, charm_id)
    if reason:
        raise RefitError(reason)
    character.retainer_charms.remove(charm_id)
    character.charms.append(charm_id)
