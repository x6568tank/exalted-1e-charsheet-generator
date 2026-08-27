"""
engine/house_rule_actions.py — writing a Storyteller option onto a character.

Input: a Character and a `HouseRules` field name plus the value a control produced.
Output: the field set, with `Character.house_rules` created on first write. Mechanism:
the field name is checked against the model, then the value is coerced to the type the
model declares — because the three control shapes hand back three different things.

Both shells edit these, so the coercion lives here rather than in either one. It is
game data (it re-prices chargen), not presentation.

⚠ **`bool(value)` is right for exactly one of the three shapes.** A checkbox sends a
bool; the M&F-method select sends its stored string, which `bool()` would turn into
True; the Inheritance select sends an option key ("per-character" or "1".."5") that
must land as None or an int.
"""

from __future__ import annotations

from ..models.character import Character, HouseRules


def house_rules(character: Character) -> HouseRules:
    """The character's HouseRules, created on first edit so a character whose table
    uses no optional rules keeps a clean save."""
    if character.house_rules is None:
        character.house_rules = HouseRules()
    return character.house_rules


def set_rule(character: Character, field: str,
             value: bool | str | int | None) -> None:
    """Set one house rule. Pure state; the caller refreshes. Guarded against unknown
    field names so a renamed field fails loudly here rather than silently writing an
    attribute nothing reads."""
    if field not in HouseRules.model_fields:
        raise KeyError(f"{field!r} is not a HouseRules field")
    target = house_rules(character)
    if field == "mf_change_method":
        setattr(target, field, value)
    elif field == "godblooded_inheritance_rating":
        setattr(target, field, None if value == "per-character" else int(value))
    else:
        setattr(target, field, bool(value))
