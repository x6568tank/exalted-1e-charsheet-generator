"""
engine/camp_actions.py — the training-camp, Calling and granted-Charm-package writes.

Input: a RuleSet, a Character and the player's pick. Output: the character is
mutated, and each function returns a REFUSAL STRING when it declined the pick, or
None when it went through. Mechanism: resolve the pick against `engine.camp`'s view
of the package, then rewrite only the part of `character.granted_charms` that pick
owns.

This is `engine/gear_actions.py`'s shape applied to the camp panel, and for the same
reason: two shells drive these writes (`ui/editor.py` and `qt/editor.py`), and a
shell-local copy in each is a rules bug waiting to happen.

⚠ **A refusal is RETURNED, not raised and not notified.** These sit below the UI, so
they cannot call `ui.notify`; and unlike a purchase there is no `AdvancementError`
shape here, because a refused pick is an ordinary outcome rather than an error. The
caller must show the string AND re-render — a refused pick leaves the control showing
something the character does not hold, and the redraw is what snaps it back. Dropping
the string on the floor is how a dropdown comes to look broken.

⚠ **Each write owns exactly one slice of `granted_charms`.** The fixed grants and
every OTHER choice must survive it, which is why each function computes what the old
selection covered and subtracts precisely that rather than clearing the list.
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
    """Resolve one granted-Charm choice, replacing whatever was selected for THAT
    choice and leaving the fixed grants and the other choices alone.

    Returns a refusal string when the option is listed but not selectable. ⚠ Such an
    option is offered on purpose — the rulebook prints it and hiding it would
    misrepresent the page — so this refuses rather than falling through and assigning
    an empty list, which cleared the control and looked like a broken dropdown."""
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
    """Set WHICH Charms a category choice grants, within the already-chosen style.

    The style pick seeds a reachable default; this is how the player changes it.
    Over-picking is REFUSED rather than silently truncated — the package is exactly
    `pick` Charms and quietly dropping one would misreport the grant. Under-picking is
    allowed through so the control can be emptied and refilled; the engine's
    `granted-charm-missing` issue covers the incomplete state."""
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
