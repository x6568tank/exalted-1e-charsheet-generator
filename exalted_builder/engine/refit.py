"""
engine/refit.py — the Alchemical vat refit: moving Charms between the Charm Slots
and the Panoply (CH2/CH3, p.88-89).

An Alchemical OWNS more Charms than they can wear. Installed Charms sit in Charm
Slots and commit Personal Essence; the rest sit "on retainer" in the character's
Panoply, owned but inert, until the Exalt returns to a vat and is refitted. This
module is the one place that move happens, in both directions.

**This is play-state, not chargen and not XP.** A refit spends no bonus points and
no experience — the Charms are already paid for; only *which* of them are worn
changes. It therefore writes no XP entry, and `validate.charm_slot_usage` (which
reads the frozen chargen snapshot once locked) is deliberately NOT consulted here:
that function answers "was this character legally built?", while a refit asks "what
is worn right now?". The two must not be confused, so this module computes the live
load itself. Nothing here feeds chargen validation, the XP audit, or the permanent
derivations — the same isolation play-state and the Lunar Form Library have.

What a refit still respects, because those are the mechanical point of Slots:
a Charm needs a free Slot of a kind it fits (Dedicated Slots take only Caste/Favored
Charms), and the committed installation motes must fit the Personal Essence pool.
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
    """Why `charm_id` cannot be moved to the Panoply — "" when it can. Shedding load
    never breaks a Slot or Essence rule, so the only bars are structural: the Charm
    must be installed and occupy a Slot, and a `permanent_install` Charm (either
    Weaving Engine, p.141) can never come out once worn.

    Note what is deliberately NOT a bar: a Charm that other installed Charms name as a
    prerequisite. A Panoply Charm is still OWNED, and a prerequisite must be owned, not
    worn — so uninstalling never cascades. (The pre-lock picker's `charms_depending_on`
    guard is a different case: there the Charm is being unlearned outright.)"""
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
