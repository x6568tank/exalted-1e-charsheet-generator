"""
engine/combo_actions.py — the Combo and Array edit dispatchers.

Input: a RuleSet, a Character and an index or Charm id. Output: the character's
`combos` / `arrays` list mutated, and the message the caller should show. Mechanism:
each function dispatches on the lock — a chargen list edit before it, a refusal after
it, because a bought Combo is priced and logged as a whole (`advancement.add_combo`)
and taking one back is an XP undo, not a list edit.

⚠ **The two systems are MUTUALLY EXCLUSIVE per splat, and neither is the default.**
A Charm-Slot splat (Alchemical, p.89-90) builds Arrays *instead of* Combos, and a splat
that builds neither has no surface at all — the dead may never learn Combos (E:Ab
p.234). `view.uses_arrays` is the one place that decides which, and `view.has_combos_tab`
whether there is one; nothing here re-derives it from a splat name.

⚠ **Module-level, never closures inside a widget builder.** These were closures in
`ui/combos.py` until 2026-08-27, which is why the native shell could not reach them —
the same reason `thaum_actions` and `house_rule_actions` exist. They mutate a save, so
they must be reachable from tests without driving a browser.

This is game logic and imports no `nicegui`, so it does not belong in the UI layer
(CLAUDE.md: "don't leak game logic into the UI"). `ui/combos.py` re-exports every
public name.
"""

from __future__ import annotations

from ..models.character import Array, Character, Combo
from ..models.rules import RuleSet
from . import advancement


def _refuse(message: str) -> None:
    """⚠ The raised TYPE is part of the contract: both shells catch
    `advancement.AdvancementError` to turn a refusal into a notification, so a
    different exception here becomes a traceback instead of a message."""
    raise advancement.AdvancementError(message)


def _locked(character: Character, noun: str) -> None:
    _refuse(f"A bought {noun} is fixed — undo the purchase in the Experience card "
            f"to take it back.")


# ---- Combos (core pp.213-214) -------------------------------------------- #

def add_combo(character: Character, name: str = "") -> str:
    """Start an empty Combo at chargen. ⚠ Empty is a legal WORKING state and priced at
    zero — `validate.combo_issues` reports the too-few-Charms problem, so the builder
    does not need to refuse the first click."""
    if character.chargen_locked:
        _refuse("In play a Combo is bought whole — compose it and buy it in one go.")
    label = name.strip() or f"Combo {len(character.combos) + 1}"
    character.combos.append(Combo(name=label, charm_ids=[]))
    return f"Added {label}"


def remove_combo(character: Character, index: int) -> str:
    if character.chargen_locked:
        _locked(character, "Combo")
    if not 0 <= index < len(character.combos):
        _refuse("No such Combo.")
    name = character.combos[index].name
    del character.combos[index]
    return f"Removed {name}"


def add_combo_member(character: Character, index: int, charm_id: str) -> str:
    """Put one Charm in a Combo. Legality is NOT decided here: `validate.combo_issues`
    reports an illegal set (two Simples, a non-instant duration) as an issue on the row,
    so a half-built Combo can be looked at rather than refused mid-assembly."""
    if character.chargen_locked:
        _locked(character, "Combo")
    if not (charm_id and 0 <= index < len(character.combos)):
        _refuse("No such Combo.")
    ids = character.combos[index].charm_ids
    if charm_id not in ids:
        ids.append(charm_id)
    return ""


def remove_combo_member(character: Character, index: int, charm_id: str) -> str:
    if character.chargen_locked:
        _locked(character, "Combo")
    if not 0 <= index < len(character.combos):
        _refuse("No such Combo.")
    ids = character.combos[index].charm_ids
    if charm_id in ids:
        ids.remove(charm_id)
    return ""


def rename_combo(character: Character, index: int, name: str) -> None:
    """Rename in place. No message and no lock check by design — a rename fires on every
    keystroke, so a refusal here would notify per character typed; the caller does not
    offer the control post-lock."""
    if 0 <= index < len(character.combos):
        character.combos[index].name = name


# ---- Arrays (Alchemical, p.89) ------------------------------------------- #

def add_array(character: Character, name: str = "") -> str:
    if character.chargen_locked:
        _refuse("In play an Array is bought whole — compose it and buy it in one go.")
    label = name.strip() or f"Array {len(character.arrays) + 1}"
    character.arrays.append(Array(name=label, charm_ids=[]))
    return f"Added {label}"


def remove_array(character: Character, index: int) -> str:
    if character.chargen_locked:
        _locked(character, "Array")
    if not 0 <= index < len(character.arrays):
        _refuse("No such Array.")
    name = character.arrays[index].name
    del character.arrays[index]
    return f"Removed {name}"


def add_array_member(character: Character, index: int, charm_id: str) -> str:
    if character.chargen_locked:
        _locked(character, "Array")
    if not (charm_id and 0 <= index < len(character.arrays)):
        _refuse("No such Array.")
    ids = character.arrays[index].charm_ids
    if charm_id not in ids:
        ids.append(charm_id)
    return ""


def remove_array_member(character: Character, index: int, charm_id: str) -> str:
    if character.chargen_locked:
        _locked(character, "Array")
    if not 0 <= index < len(character.arrays):
        _refuse("No such Array.")
    ids = character.arrays[index].charm_ids
    if charm_id in ids:
        ids.remove(charm_id)
    return ""


def rename_array(character: Character, index: int, name: str) -> None:
    """See `rename_combo` for why this neither refuses nor reports."""
    if 0 <= index < len(character.arrays):
        character.arrays[index].name = name


def linked_array_charms(character: Character) -> set[str]:
    """Every Charm already sitting in an Array.

    ⚠ A Charm may join only ONE Array (p.90), so an add-picker must exclude every
    linked Charm and not merely the ones in the Array being edited. The engine refuses
    a reuse either way, so offering one would only produce a rejection.
    """
    return {cid for array in character.arrays for cid in array.charm_ids}
