"""
engine/gear_actions.py — the equipment mutators: what owning, buying and granting do.

Input: a ruleset, a character and either a list name, a row index or a shop key.
Output: the character's four owned-lists mutated in place, and a message the caller
may show. Mechanism: each function maps one player action onto one or more of
`character.weapons` / `.armor` / `.gear` / `.artifacts`, applying the acquisition and
linking rules that decide what the Artifact budget will later count.

Both shells (`ui/gear.py` and `qt/gear.py`) call these functions. Do not copy the
logic into a widget.

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
    """Return the PLAYER's fields of `old`, kept across a catalogue re-pick.

    ⚠ The complement of `_catalogue_stats`, not a hand-written list: a re-pick
    REPLACES the row, and an unlisted field is lost. Two fields decide the Artifact
    budget:

    * `from_artifact`: without it the linked daiklave counts two times
      (`artifacts.artifact_items`).
    * `acquired` (decision 0017): without it a cash artifact counts against the p.131
      budget.
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
    """Delete one owned row. A delete is a sale: core p.145 gives no sale rate, and
    no Resources drop applies (human's ruling)."""
    rows = getattr(character, list_name)
    if 0 <= index < len(rows):
        del rows[index]


def remove_artifact(character: Character, index: int) -> None:
    """Delete one artifact. Keep the gear row that it granted: the orphan then counts
    as its own artifact (`artifacts.artifact_items`).
    """
    if 0 <= index < len(character.artifacts):
        del character.artifacts[index]


# ---- picking a catalogue entry into an existing row --------------------- #

def set_weapon(ruleset: RuleSet, character: Character, index: int, name: str) -> None:
    """Set weapon row `index` to the catalogue entry `name`, or to free text.

    A catalogue pick REPLACES the row. The player's fields are kept (see
    `_owned_fields`).
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
    """Set armor row `index` to the catalogue entry `name`, or to free text."""
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
    """Add the gear stat line of a new artifact. Return True if a row was added.

    ⚠ The row gets `from_artifact`, thus the budget counts the pair one time (human's
    ruling). Does nothing if the artifact has no gear half, or if the row exists.

    ⚠ The row copies the `acquired` of the artifact. If the artifact is deleted, the
    orphan keeps the correct channel.
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
    rows.append(model(**_catalogue_stats(entry, model), from_artifact=key,
                      acquired=_channel_of(character, key)))
    return True


def _channel_of(character: Character, key: str) -> str:
    """Return the `acquired` of the artifact `key`, or the model default. Reads the
    character: each caller adds the artifact first.
    """
    for art in character.artifacts:
        if artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, art.name) == key:
            return art.acquired
    return artifactsmod.ACQUIRED_BACKGROUND


def acquisition_for(entry) -> str:
    """Return the `acquired` of a catalogue artifact picked through the Background
    channel. A Merit-gated entry gets the Legendary channel (decision 0017).
    """
    return (artifactsmod.ACQUIRED_LEGENDARY if entry.requires_merit
            else artifactsmod.ACQUIRED_BACKGROUND)


def set_acquired(character: Character, index: int, channel: str) -> None:
    """Set the `acquired` of artifact `index`, and of its granted stat line.

    ⚠ The stat line must change too. Else an orphaned row keeps the old channel.
    """
    rows = character.artifacts
    if not (0 <= index < len(rows)):
        return
    rows[index].acquired = channel or artifactsmod.ACQUIRED_BACKGROUND
    key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, rows[index].name)
    for owned in (*character.weapons, *character.armor):
        if owned.from_artifact == key:
            owned.acquired = rows[index].acquired


def add_artifact(ruleset: RuleSet, character: Character,
                 name: Optional[str] = None) -> int:
    """Add one artifact: the catalogue entry `name`, or a blank row if `name` is None
    or unknown. Return its index. A catalogue pick sets the rating, the channel and
    the gear half. Free text gives a rating-1 row.
    """
    entry = None
    if name:
        entry = next((a for a in artifactsmod.purchasable_artifacts(
            ruleset.artifact_catalog, character) if a.name == name), None)
    if entry is None:
        character.artifacts.append(ArtifactEntry(name=name or "", rating=1))
    else:
        character.artifacts.append(ArtifactEntry(
            name=entry.name, rating=entry.rating, attunement=entry.attunement,
            acquired=acquisition_for(entry)))
        grant_gear(ruleset, character, entry.name)
    return len(character.artifacts) - 1


def set_artifact(ruleset: RuleSet, character: Character, index: int,
                 name: str) -> bool:
    """Rename artifact row `index`. Return True if a catalogue entry was applied.
    A catalogue pick sets the rating and the channel and grants the stat line, as in
    the dialog. Free text keeps the rating.
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
    rows[index].attunement = entry.attunement
    if entry.requires_merit:
        # Through `set_acquired`: `grant_gear` does nothing if the row exists.
        set_acquired(character, index, artifactsmod.ACQUIRED_LEGENDARY)
    grant_gear(ruleset, character, entry.name)
    return True


# ---- the shop ------------------------------------------------------------ #

def buy(ruleset: RuleSet, character: Character, key: str) -> str:
    """Apply one Buy-dialog row key. Return the message for the shell.

    The key prefix (`weapon:` / `armor:` / `goods:` / `artifact:` / `custom:`) selects
    one of four lists (human's ruling).

    ⚠ Nothing is deducted. The Resources cost is a hint (core p.325).
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
        # Cash: not charged to the Artifact Background (M&C pp.122-125). Post-lock
        # only.
        character.artifacts.append(ArtifactEntry(
            name=entry.name, rating=entry.rating, attunement=entry.attunement,
            acquired=artifactsmod.ACQUIRED_PURCHASED))
        grant_gear(ruleset, character, entry.name)
    else:
        return ""
    return f"Added {name}."


# ---- the custom library -------------------------------------------------- #

def library_payload(kind: str, item) -> dict:
    """Return one owned row as a library row in the `data/` shape.

    One mapping per kind: an owned row has ownership fields (`quantity`,
    `from_artifact`) that do not go into a catalogue. `custom_content.save_gear_row`
    writes the result.

    ⚠ `attuned`/`attuned_pool` must stay excluded: they are ownership state.
    `attunement` is included.
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
            # ⚠ `weight` is REQUIRED by ArmorType and an owned row has none. It gets a
            # default, and the caller tells the player.
            "weight": "Light",
            "soak_lethal": item.soak_lethal, "soak_bashing": item.soak_bashing,
            "mobility_penalty": item.mobility_penalty, "fatigue": item.fatigue,
            "artifact_rating": item.artifact_rating,
            "attunement": item.attunement, "resources_cost": item.resources_cost}
    if kind == "gear":
        return base | {"kind": "goods", "category": "Your library",
                       "resources_cost": item.resources_cost, "notes": item.note}
    return base | {"rating": item.rating, "attunement": item.attunement,
                   "description": item.note}


def reserved_ids(ruleset: RuleSet) -> set[str]:
    """Return all ids of the BOOK. A library row cannot use one. The same rule as
    `_load_custom_layer`, checked at save time."""
    return (set(ruleset.weapon_catalog) | set(ruleset.armor_catalog)
            | set(ruleset.gear_catalog) | set(ruleset.artifact_catalog))
