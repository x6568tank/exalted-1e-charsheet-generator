"""
engine/camp_actions.py — the training-camp, Calling and granted-Charm-package writes.

Input: a RuleSet, a Character and the player's pick. Output: the character is
mutated, and each function returns a REFUSAL STRING when it declined the pick, or
None when it went through. Mechanism: resolve the pick against `engine.camp`'s view
of the package, then rewrite only the part of `character.granted_charms` that pick
owns.

Both shells (`ui/editor.py`, `qt/editor.py`) use these functions.

⚠ **A refusal is RETURNED, not raised and not notified.** The caller must show the
string AND re-render: the redraw resets the control to the held value.

⚠ **Each write owns one part of `granted_charms`.** It removes only what the old
selection of that choice covered. The fixed grants and the other choices stay.
"""

from __future__ import annotations

from typing import Optional

from ..models.character import Character
from ..models.rules import RuleSet
from .camp import build_camp_view


def set_camp(ruleset: RuleSet, character: Character, camp_id: str) -> None:
    """Pick a training camp. The camp determines both the Calling list and the free
    Charm package, so changing it clears any Calling and granted Charms belonging to
    the old one and re-seeds the fixed grants. The player still resolves each choice."""
    character.camp = camp_id
    camp = ruleset.camps.get(camp_id)
    callings = ruleset.callings_for(camp_id)
    if character.calling not in {c.id for c in callings}:
        character.calling = callings[0].id if callings else ""
    character.granted_charms = list(camp.granted_charms) if camp else []


def set_calling(character: Character, calling_id: str) -> None:
    character.calling = calling_id


def set_camp_choice(ruleset: RuleSet, character: Character,
                    choice_index: int, key: str) -> Optional[str]:
    """Resolve one granted-Charm choice. Replace the selection of THAT choice only.

    Returns a refusal string for an option that is listed but not selectable. ⚠ Do
    not fall through and assign an empty list: that clears the control."""
    camp = ruleset.camps.get(character.camp)
    if camp is None or choice_index >= len(camp.granted_charm_choices):
        return None
    cview = build_camp_view(ruleset, character).choices[choice_index]
    picked = next((o for o in cview.options if o.key == key), None)
    if picked is None:
        return None
    if not picked.available:
        return f"{picked.label} is not selectable — {picked.reason}."
    old = next((o.charm_ids for o in cview.options if o.key == cview.chosen_key), [])
    new = list(picked.charm_ids)
    choice = camp.granted_charm_choices[choice_index]
    if choice.from_categories:
        # A category choice takes `pick` Charms from the chosen style. Seed the
        # lowest-requirement ones so the default is as reachable as possible; the
        # player swaps individual Charms afterwards.
        pool = sorted((c for c in ruleset.charms.values() if c.id in new),
                      key=lambda c: (c.min_ability, c.min_essence, c.name))
        new = [c.id for c in pool[:choice.pick]]
    keep = [cid for cid in character.granted_charms if cid not in old]
    character.granted_charms = keep + [cid for cid in new if cid not in keep]
    return None


def set_camp_choice_charms(ruleset: RuleSet, character: Character,
                           choice_index: int, ids: list[str]) -> Optional[str]:
    """Set the Charms of a category choice, in the chosen style.

    Over-picking is REFUSED, not truncated: the package is exactly `pick` Charms.
    Under-picking is allowed: `granted-charm-missing` reports it."""
    camp = ruleset.camps.get(character.camp)
    if camp is None or choice_index >= len(camp.granted_charm_choices):
        return None
    cview = build_camp_view(ruleset, character).choices[choice_index]
    allowed = {o.charm_id for o in cview.charm_options}
    chosen = [cid for cid in ids if cid in allowed]
    if len(chosen) > cview.pick:
        return (f"{cview.label} grants only {cview.pick} Charm(s) — "
                f"deselect one first.")
    # Replace this choice's Charms, leaving the fixed grants and any other choice
    # untouched: drop everything from THIS style, then add the new selection.
    keep = [cid for cid in character.granted_charms if cid not in allowed]
    character.granted_charms = keep + chosen
    return None
