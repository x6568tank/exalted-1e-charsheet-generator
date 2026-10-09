"""
ui/view/augments.py — the Alchemical Augmentation Charms, grouped into one
pop-up for each type.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...engine import validate
from ...models.character import Character
from ...models.rules import RuleSet

from .charm_trees import build_charm_detail


# --- Augmentation grouping (Alchemical) ------------------------------------- #
# The Alchemical "general" category is 9 Transitory + 9 Sustained "Augmentation of
# (Attribute)" Charms — one template keyed per Attribute. They stay 18 distinct ids in
# the data (many other Charms name a SPECIFIC one as a prerequisite), but the picker
# collapses them into two per-type pop-ups so the page isn't 18 disconnected nodes.

_AUGMENT_SPLIT = " Augmentation of "


@dataclass
class AugmentEntry:
    """One Attribute row inside an Augmentation pop-up."""
    attribute: str          # display name, e.g. "Strength"
    charm_id: str
    owned: bool
    available: bool         # requirements met (can install now)
    reason: str             # why it is locked, when not owned and not available


@dataclass
class AugmentGroup:
    title: str              # e.g. "Transitory Augmentation"
    entries: list[AugmentEntry]


def augmentation_category(ruleset: RuleSet, character: Character) -> Optional[str]:
    """The Charm category whose Charms (for this character's splat) are ALL
    '<Type> Augmentation of <Attribute>' templates the picker collapses into
    per-type pop-ups — Alchemical 'general'. None when the splat has no such category,
    so every other splat's picker is untouched."""
    by_cat: dict[str, list] = {}
    for ch in ruleset.charms.values():
        if validate.charm_matches_splat(character, ch, ruleset):
            by_cat.setdefault(ch.category, []).append(ch)
    for cat, charms in by_cat.items():
        if charms and all(_AUGMENT_SPLIT in c.name for c in charms):
            return cat
    return None


def build_augmentation_view(ruleset: RuleSet, character: Character) -> list[AugmentGroup]:
    """The two Augmentation groups (Transitory / Sustained), each with one row per
    Attribute — its install state and, when locked, why. Empty for a non-Alchemical."""
    cat = augmentation_category(ruleset, character)
    if cat is None:
        return []
    groups: dict[str, list[AugmentEntry]] = {}
    order: list[str] = []
    for ch in ruleset.charms.values():
        if ch.category != cat or not validate.charm_matches_splat(character, ch, ruleset):
            continue
        prefix, _, attr = ch.name.partition(_AUGMENT_SPLIT)
        title = f"{prefix} Augmentation"
        detail = build_charm_detail(ruleset, character, ch.id)
        owned = ch.id in character.charms
        available = detail.available if detail else False
        entry = AugmentEntry(
            attribute=attr, charm_id=ch.id, owned=owned, available=available,
            reason="" if owned or available else f"Needs {detail.requirement}" if detail else "Locked")
        if title not in groups:
            groups[title] = []
            order.append(title)
        groups[title].append(entry)
    return [AugmentGroup(title, groups[title]) for title in order]
