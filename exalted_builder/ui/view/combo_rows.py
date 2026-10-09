"""
ui/view/combo_rows.py — the Combos tab: the Combo rows, the Alchemical Arrays,
and the Submodule rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...engine import costs, validate
from ...models.character import Character
from ...models.rules import RuleSet


@dataclass
class ComboCharmRow:
    id: str
    name: str
    type: str            # Simple / Supplemental / Reflexive / Extra Action
    category: str


@dataclass
class ComboRow:
    index: int           # position in character.combos (the edit handle)
    name: str
    members: list[ComboCharmRow]
    cost: int            # bonus points = number of member Charms
    issues: list[str]    # this Combo's legality messages (empty == legal)


@dataclass
class ComboView:
    combos: list[ComboRow]
    addable: list[ComboCharmRow]   # known, instant-duration Charms (Combo-eligible)
    total_cost: int                # bonus points spent on all Combos


def _combo_charm_row(ruleset: RuleSet, cid: str) -> ComboCharmRow:
    charm = ruleset.charms.get(cid)
    if charm is None:
        return ComboCharmRow(id=cid, name=cid, type="?", category="?")
    return ComboCharmRow(id=cid, name=charm.name, type=charm.type.value, category=charm.category)


def build_combo_view(ruleset: RuleSet, character: Character) -> ComboView:
    """Presenter for the Combos editor: each Combo with its member Charms, BP cost
    (= number of Charms), and its own legality messages; plus the pool of known
    instant-duration Charms eligible to add. Pure — legality from engine.validate."""
    combos = []
    for i, combo in enumerate(character.combos):
        members = [_combo_charm_row(ruleset, cid) for cid in combo.charm_ids]
        issues = [iss.message for iss in validate.combo_issues(ruleset, character, combo)]
        combos.append(ComboRow(index=i, name=combo.name, members=members,
                               cost=len(combo.charm_ids), issues=issues))
    addable = [_combo_charm_row(ruleset, cid)
               for cid in validate.eligible_combo_charms(ruleset, character)]
    return ComboView(combos=combos, addable=addable,
                     total_cost=sum(c.cost for c in combos))


@dataclass
class ArrayCharmRow:
    id: str
    name: str
    attribute: str       # the Attribute the Charm is keyed to (Charm.min_attribute)
    rating: int          # its minimum rating — this Charm's share of the XP price
    install: int         # installation cost, in committed Personal motes


@dataclass
class ArrayRow:
    index: int           # position in character.arrays (the edit handle)
    name: str
    members: list[ArrayCharmRow]
    cost: int            # bonus points = number of member Charms
    xp_cost: int         # XP = sum of member minimum Attribute ratings
    install_loose: int   # motes to install the members separately
    install_arrayed: int # motes with the Array's three-fourths discount
    issues: list[str]    # this Array's legality messages (empty == legal)

    @property
    def install_saving(self) -> int:
        return self.install_loose - self.install_arrayed


@dataclass
class ArrayView:
    arrays: list[ArrayRow]
    addable: list[ArrayCharmRow]   # known, Attribute-based, arrayable Charms
    total_cost: int                # bonus points spent on all Arrays


def _array_charm_row(ruleset: RuleSet, cid: str) -> ArrayCharmRow:
    charm = ruleset.charms.get(cid)
    if charm is None:
        return ArrayCharmRow(id=cid, name=cid, attribute="?", rating=0, install=0)
    return ArrayCharmRow(id=cid, name=charm.name, attribute=charm.min_attribute or "—",
                         rating=charm.min_ability, install=charm.installation_cost)


def build_array_view(ruleset: RuleSet, character: Character) -> ArrayView:
    """Presenter for the Arrays editor (p.89), the Alchemical analogue of
    `build_combo_view`: each Array with its member Charms, its BP cost (= number of
    Charms) and XP price (= Σ minimum Attribute ratings), the installation motes it
    saves, and its own legality messages; plus the pool of known Attribute-based
    Charms eligible to link. Pure — legality and mote arithmetic from engine."""
    arrays = []
    for i, array in enumerate(character.arrays):
        members = [_array_charm_row(ruleset, cid) for cid in array.charm_ids]
        issues = [iss.message for iss in validate.array_issues(ruleset, character, array)]
        arrays.append(ArrayRow(
            index=i, name=array.name, members=members,
            cost=len(array.charm_ids),
            xp_cost=costs.array_cost(ruleset, array.charm_ids),
            install_loose=sum(m.install for m in members),
            install_arrayed=validate.array_installation_motes(ruleset, array.charm_ids),
            issues=issues))
    addable = [_array_charm_row(ruleset, cid)
               for cid in validate.eligible_array_charms(ruleset, character)]
    return ArrayView(arrays=arrays, addable=addable,
                     total_cost=sum(a.cost for a in arrays))


@dataclass
class SubmoduleRow:
    """One purchasable upgrade to a Charm (p.89), for the picker's detail card."""
    charm_id: str
    key: str
    name: str
    description: str
    bp_cost: int
    xp_cost: int
    requirement: str     # "Essence 3 · Wits 3", or "" when it gates on nothing extra
    owned: bool
    block_reason: str    # "" when purchasable; why not otherwise

    @property
    def available(self) -> bool:
        return not self.owned and not self.block_reason


def build_submodule_rows(ruleset: RuleSet, character: Character,
                         charm_id: str) -> list[SubmoduleRow]:
    """Every submodule offered by `charm_id`, with its dual price (BP at chargen OR
    XP post-lock), its own minima, and whether it is owned or blocked. Empty for a
    Charm with no submodules, which is most of them. Pure — legality from the engine."""
    charm = ruleset.charms.get(charm_id)
    if charm is None or not charm.submodules:
        return []
    rows = []
    for sub in charm.submodules:
        gates = []
        if sub.min_essence > 1:
            gates.append(f"Essence {sub.min_essence}")
        if sub.min_attribute and sub.min_attribute_rating:
            gates.append(f"{sub.min_attribute.title()} {sub.min_attribute_rating}")
        rows.append(SubmoduleRow(
            charm_id=charm_id, key=sub.key, name=sub.name, description=sub.description,
            bp_cost=sub.bp_cost, xp_cost=sub.xp_cost, requirement=" · ".join(gates),
            owned=validate.owns_submodule(character, charm_id, sub.key),
            block_reason=validate.submodule_block_reason(
                ruleset, character, charm_id, sub.key)))
    return rows


def uses_arrays(ruleset: RuleSet, character: Character) -> bool:
    """Whether this character builds Arrays rather than Combos — i.e. is a Charm-Slot
    splat (Alchemical). The Combos tab renders one or the other on this flag, so it is
    the single place the UI decides which of the two systems a splat has."""
    return validate.uses_charm_slots(ruleset, character)


def has_combos_tab(ruleset: RuleSet, character: Character) -> bool:
    """Whether this character gets the Combos tab at all.

    A splat barred from Combos outright (the dead — E:Ab p.234, "The dead may never
    learn Combos") has nothing to put on it, and an empty tab that answers every
    attempt with a validation error is worse than no tab. Arrays keep it: a Charm-Slot
    splat has no Combos either, but it builds Arrays on the same tab (`uses_arrays`),
    so the tab has content.
    """
    return (ruleset.exalt_for(character.exalt_type).combos_available
            or uses_arrays(ruleset, character))
