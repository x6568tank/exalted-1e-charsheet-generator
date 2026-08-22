"""
engine/gear_actions.py — the equipment mutators: what owning, buying and granting do.

Input: a ruleset, a character and either a list name, a row index or a shop key.
Output: the character's four owned-lists mutated in place, and a message the caller
may show. Mechanism: each function maps one player action onto one or more of
`character.weapons` / `.armor` / `.gear` / `.artifacts`, applying the acquisition and
linking rules that decide what the Artifact budget will later count.

This is `engine/thaum_actions.py` and `engine/charm_actions.py`'s shape applied to the
Gear tab, for the same reason: two shells now drive these edits (`ui/gear.py` and
`qt/gear.py`), and a widget-local copy in each is a rules bug waiting to happen. The
milestone-2 question — "does this surface need an engine dispatcher extracted?" — was
asked of Gear before it was ported and the answer was yes, unlike Advantages.

⚠ Nothing here validates. `engine.validate` owns the budget; these functions only make
the character say truthfully what it owns and how it came by it.
"""

from __future__ import annotations

from typing import Optional

from ..models.character import (Armor, ArtifactEntry, Character, GearEntry, Weapon)
from ..models.rules import RuleSet
from . import artifacts as artifactsmod


ROW_FACTORIES = {"weapons": lambda: Weapon(name=""),
                 "armor": lambda: Armor(name=""),
                 "gear": lambda: GearEntry(name="")}


def _catalogue_stats(entry, owned_type) -> dict:
    """The catalogue entry's fields that an OWNED row also has — its printed stats."""
    shared = set(type(entry).model_fields) & set(owned_type.model_fields)
    return {name: getattr(entry, name) for name in shared}


def _owned_fields(old, entry) -> dict:
    """The fields that are the PLAYER's, carried across a catalogue re-pick.

    ⚠ Derived as the complement of `_catalogue_stats` rather than listed by hand,
    because a re-pick REPLACES the row and every field not named here is silently
    discarded. Two of the four decide what the Artifact budget charges:

    * `from_artifact` links a granted stat line back to its artifact, so the pair is
      counted once (`artifacts.artifact_items`). Dropping it charges the daiklave twice.
    * `acquired` records the channel (decision 0017). Dropping it turns a cash-bought
      artifact weapon back into a Background-funded one, so re-picking its own name from
      the row's dropdown charges the p.131 budget for something Resources paid for.

    The second was live in `ui/gear.py` until 2026-08-21 — the hand-written copy list
    carried `from_artifact` because a comment warned about it, and never knew `acquired`
    existed. That is why this is computed, not written out.
    """
    mine = set(type(old).model_fields) - set(type(entry).model_fields)
    return {name: getattr(old, name) for name in mine}


# ---- adding and removing rows ------------------------------------------- #

def add_row(character: Character, list_name: str) -> int:
    """Append a blank row to one of the three typed equipment lists; return its index."""
    rows = getattr(character, list_name)
    rows.append(ROW_FACTORIES[list_name]())
    return len(rows) - 1


def remove_row(character: Character, list_name: str, index: int) -> None:
    """Delete one owned row. Deleting IS selling — core p.145 prints no rate for a sale
    and the buy-side dot drop is not applied automatically either (human's ruling,
    2026-08-13), so there is no separate sell action to dispatch."""
    rows = getattr(character, list_name)
    if 0 <= index < len(rows):
        del rows[index]


def remove_artifact(character: Character, index: int) -> None:
    """Delete one artifact, LEAVING BEHIND any gear row it granted.

    The row may have been edited, and deleting a player's equipment to tidy up a link
    is not this function's business; the orphan counts as an artifact in its own right
    again (`artifacts.artifact_items`), which is visible rather than free.
    """
    if 0 <= index < len(character.artifacts):
        del character.artifacts[index]


# ---- picking a catalogue entry into an existing row --------------------- #

def set_weapon(ruleset: RuleSet, character: Character, index: int, name: str) -> None:
    """Point weapon row `index` at catalogue entry `name`, or rename it to free text.

    A catalogue pick REPLACES the row with a copy of the entry, so the player's own
    fields are carried across explicitly — see `_catalogue_stats`.
    """
    rows = character.weapons
    if not (0 <= index < len(rows)):
        return
    entry = next((w for w in ruleset.weapon_catalog.values() if w.name == name), None)
    if entry is None:
        rows[index].name = name or ""
        return
    old = rows[index]
    rows[index] = Weapon(**_catalogue_stats(entry, Weapon),
                         **_owned_fields(old, entry))


def set_armor(ruleset: RuleSet, character: Character, index: int, name: str) -> None:
    """Point armour row `index` at catalogue entry `name`, or rename it to free text."""
    rows = character.armor
    if not (0 <= index < len(rows)):
        return
    entry = next((a for a in ruleset.armor_catalog.values() if a.name == name), None)
    if entry is None:
        rows[index].name = name or ""
        return
    old = rows[index]
    rows[index] = Armor(**_catalogue_stats(entry, Armor),
                        **_owned_fields(old, entry))


# ---- artifacts ----------------------------------------------------------- #

def grant_gear(ruleset: RuleSet, character: Character, artifact_name: str) -> bool:
    """Give a newly picked artifact its stat line on the equipment surface. True when a
    row was added.

    ⚠ Owning "Daiklave" as an artifact and separately adding a "Daiklave" weapon to
    swing it counts the same object twice, which the corebook one-artifact rule turns
    into a false error (human's call, 2026-08-13). So the artifact grants the row and
    stamps `from_artifact` on it, and the budget counts the pair once.

    Silent when the artifact has no gear half (the large majority do not), and when the
    row is already there — picking the same artifact twice must not breed daiklaves.
    """
    found = artifactsmod.gear_stat_line(ruleset, artifact_name)
    if found is None:
        return False
    source, entry = found
    key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, artifact_name)
    weapon = source == artifactsmod.SOURCE_WEAPON
    rows = character.weapons if weapon else character.armor
    if any(row.from_artifact == key for row in rows):
        return False
    model = Weapon if weapon else Armor
    rows.append(model(**_catalogue_stats(entry, model), from_artifact=key))
    return True


def acquisition_for(entry) -> str:
    """How a catalogue artifact picked at the Background channel was come by.

    A merit-gated plot device is charged to no budget — the Legendary Artifact Merit
    was its price (decision 0017's third channel) — and the stamp comes from the
    CATALOGUE at pick time rather than from a menu, so the player never has to know the
    channel exists.
    """
    return (artifactsmod.ACQUIRED_LEGENDARY if entry.requires_merit
            else artifactsmod.ACQUIRED_BACKGROUND)


def add_artifact(ruleset: RuleSet, character: Character,
                 name: Optional[str] = None) -> int:
    """Add one artifact — a catalogue entry by `name`, or a blank row when `name` is
    None or matches nothing. Returns its index.

    A catalogue pick brings its rating, its acquisition channel and its gear half;
    free text is a rating-1 row the player fills in.
    """
    entry = None
    if name:
        entry = next((a for a in artifactsmod.purchasable_artifacts(
            ruleset.artifact_catalog, character) if a.name == name), None)
    if entry is None:
        character.artifacts.append(ArtifactEntry(name=name or "", rating=1))
    else:
        character.artifacts.append(ArtifactEntry(
            name=entry.name, rating=entry.rating, acquired=acquisition_for(entry)))
        grant_gear(ruleset, character, entry.name)
    return len(character.artifacts) - 1


def set_artifact(ruleset: RuleSet, character: Character, index: int,
                 name: str) -> bool:
    """Rename artifact row `index`, autofilling from the catalogue when `name` is one.
    True when a catalogue entry was applied.

    A catalogue pick sets the rating and the acquisition channel and grants the stat
    line — choosing an artifact HERE is the same act as choosing one in the dialog.
    Any other value is free text that renames and preserves the rating.
    """
    rows = character.artifacts
    if not (0 <= index < len(rows)):
        return False
    entry = next((a for a in artifactsmod.purchasable_artifacts(
        ruleset.artifact_catalog, character) if a.name == name), None)
    if entry is None:
        rows[index].name = name or ""
        return False
    rows[index].name = entry.name
    rows[index].rating = entry.rating
    if entry.requires_merit:
        rows[index].acquired = artifactsmod.ACQUIRED_LEGENDARY
    grant_gear(ruleset, character, entry.name)
    return True


# ---- the shop ------------------------------------------------------------ #

def buy(ruleset: RuleSet, character: Character, key: str) -> str:
    """Act on one Buy-dialog row key; return the message a shell may show.

    The key carries the kind (`weapon:` / `armor:` / `goods:` / `artifact:` /
    `custom:`) precisely so ONE dialog can append to four differently typed lists —
    the unification that let the four per-panel shops go (human, 2026-08-13).

    ⚠ Nothing is deducted. The Resources cost is a hint, not a currency (core p.325).
    """
    if not key:
        return ""
    kind, _, name = key.partition(":")
    if kind == "custom":
        # "Custom <kind>" — a blank row of that kind, for something no catalogue holds.
        if name == "artifacts":
            add_artifact(ruleset, character)
        else:
            add_row(character, name)
        return "Added a blank row."
    if kind == "weapon":
        set_weapon(ruleset, character, add_row(character, "weapons"), name)
    elif kind == "armor":
        set_armor(ruleset, character, add_row(character, "armor"), name)
    elif kind == "goods":
        entry = ruleset.gear_catalog.get(name)
        character.gear.append(
            GearEntry(name=entry.name, resources_cost=entry.resources_cost)
            if entry is not None else GearEntry(name=""))
        name = entry.name if entry is not None else name
    elif kind == "artifact":
        entry = next((a for a in ruleset.artifact_catalog.values()
                      if a.name == name), None)
        if entry is None:
            return ""
        # Bought with cash, so NOT charged to the Artifact Background — decision 0017's
        # in-play channel (M&C pp.122-125), which is why the shop only offers artifacts
        # post-lock.
        character.artifacts.append(ArtifactEntry(
            name=entry.name, rating=entry.rating,
            acquired=artifactsmod.ACQUIRED_PURCHASED))
        grant_gear(ruleset, character, entry.name)
    else:
        return ""
    return f"Added {name}."


# ---- the custom library -------------------------------------------------- #

def library_payload(kind: str, item) -> dict:
    """One owned row, as a library row of the shape `data/` uses.

    The four kinds have four models, so this is four small mappings rather than a
    generic dump — a `Weapon` is not a `WeaponType` (the character's copy has
    `quantity` and `from_artifact`, which are facts about ownership, not about the
    design) and shipping the difference into the library would put ownership state in a
    catalogue. A codec half, not a presenter: `custom_content.save_gear_row` writes it
    and the loader reads it back as catalogue content.
    """
    from .. import custom_content as customs

    base = {"id": customs.make_id(item.name), "name": item.name}
    if kind == "weapons":
        return base | {
            "speed": item.speed, "accuracy": item.accuracy, "damage": item.damage,
            "damage_type": item.damage_type, "defense": item.defense,
            "rate": item.rate, "range": item.range,
            "min_strength": item.min_strength, "min_dexterity": item.min_dexterity,
            "min_martial_arts": item.min_martial_arts,
            "max_strength": item.max_strength,
            "artifact_rating": item.artifact_rating,
            "attunement": item.attunement, "resources_cost": item.resources_cost,
            "notes": item.notes}
    if kind == "armor":
        return base | {
            # ⚠ `weight` is REQUIRED by ArmorType and a character's armour row does not
            # carry one, so it is defaulted and SAID OUT LOUD in the caller's notify
            # rather than guessed silently. The player edits the library file if it
            # matters; nothing in the engine reads armour weight today.
            "weight": "Light",
            "soak_lethal": item.soak_lethal, "soak_bashing": item.soak_bashing,
            "mobility_penalty": item.mobility_penalty, "fatigue": item.fatigue,
            "artifact_rating": item.artifact_rating,
            "attunement": item.attunement, "resources_cost": item.resources_cost}
    if kind == "gear":
        return base | {"kind": "goods", "category": "Your library",
                       "resources_cost": item.resources_cost, "notes": item.note}
    return base | {"rating": item.rating, "description": item.note}


def reserved_ids(ruleset: RuleSet) -> set[str]:
    """Every id the BOOK uses, so a library row can never shadow printed content — the
    same rule `_load_custom_layer` enforces on load, checked at save time so the user
    hears about it while they can still rename the thing."""
    return (set(ruleset.weapon_catalog) | set(ruleset.armor_catalog)
            | set(ruleset.gear_catalog) | set(ruleset.artifact_catalog))
