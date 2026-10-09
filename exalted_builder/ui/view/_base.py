"""
ui/view/_base.py — the row types and the formatters that more than one presenter
module uses.

This module is the bottom of the package. It imports no sibling module.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...engine import derive
from ...models.rules import DAMAGE_LABELS, CharmCost, SpellCircle, circle_kind


@dataclass
class TraitRow:
    label: str
    value: int
    caste: bool = False
    favored: bool = False


@dataclass
class CharmRow:
    name: str
    category: str
    cost: str
    duration: str = ""
    description: str = ""
    # Homebrew from the user's custom library rather than a printed Charm. The sheet
    # badges it: the human's requirement is that custom content stay easily
    # distinguishable from canon (2026-07-29).
    custom: bool = False
    # The id does not resolve in the RuleSet at all — a deleted custom Charm, or a
    # save opened on a machine without the library that defined it. The row is still
    # rendered (never silently dropped) so the loss is visible; engine.validate
    # reports it as an `unknown-charm` error separately.
    missing: bool = False


@dataclass
class SpellRow:
    name: str
    circle: str
    cost: str
    description: str = ""
    custom: bool = False                   # see CharmRow.custom
    missing: bool = False                  # see CharmRow.missing


@dataclass
class PathPowerRow:
    """One dot-level power of a Dragon-King Path, as the sheet shows it (PG pp.177-191)."""
    dot: int
    name: str
    cost: str
    type: str
    duration: str
    text: str


@dataclass
class PathRow:
    """One Dragon-King Path on the sheet, with the powers its rating grants."""
    name: str
    element_label: str
    favored: str              # "" | "★" (breed) | "✚" (the player's choice)
    rating: int
    powers: list[PathPowerRow]


@dataclass
class SpellPickRow:
    id: str
    name: str
    circle: str
    cost: str
    description: str
    owned: bool
    available: bool        # learnable right now (circle granted, not Solar at chargen)
    reason: str            # why it is locked, when neither owned nor available
    custom: bool = False   # see CharmRow.custom


@dataclass
class CharmNode:
    id: str
    label: str
    state: str          # 'owned' | 'available' | 'locked'
    min_ability: int
    min_essence: int
    external: bool = False   # a prerequisite drawn in from ANOTHER category
    # A breadth prerequisite ("any 3 Occult Charms", Aspect Books) has no source node
    # to draw an edge FROM — the requirement is a count over a category, not an id. It
    # rides as a badge on the node instead, so a capstone Charm does not silently read
    # as an entry-level root just because nothing points at it.
    count_requirement: str = ""
    custom: bool = False     # homebrew from the user's library — see CharmRow.custom


@dataclass
class CharmGraph:
    category: str
    nodes: list[CharmNode]
    edges: list[tuple[str, str]]   # (prerequisite_id, charm_id)
    roots: list[str]               # charm ids with no prerequisite inside the graph


@dataclass
class CharmDetail:
    id: str
    name: str
    description: str
    type: str
    cost: str
    duration: str
    requirement: str                       # e.g. "Martial Arts 4, Essence 2"
    prerequisite_groups: list[list[str]]   # charm names; inner list = an OR group
    owned: bool
    available: bool                        # learnable right now
    # Another Exalt type's Charm, reachable only through the Eclipse-style caste
    # privilege (p.127) and priced at double. "" for an ordinary native Charm — the
    # cross-tier styles a Celestial may learn natively are NOT foreign.
    foreign_splat: str = ""
    custom: bool = False                   # see CharmRow.custom


def source_label(source) -> str:
    """Return "<book> p.<page>" for a `Source`. Return "" if the book or the page is
    absent."""
    return f"{source.book} p.{source.page}" if source and source.book and source.page else ""
# Casting time by circle: the turns spent shaping Essence before a spell of that
# circle takes effect — 1/2/3 for the low/mid/top circle of each track. Sorcery is
# core p.216 (Terrestrial 1, Celestial 2, Solar 3); necromancy casting times "parallel
# sorcery" (Abyssal p.223), so Shadowlands 1, Labyrinth 2, Void 3. Shown as descriptive
# flavour on the circle-granting initiation Charm (which unlocks that circle's spells),
# NOT on each spell — some spells (rituals, summonings) state their own longer casting
# time. Flavour text, NOT a play mechanic (actual play is out of scope).
_SHAPING_TURNS = {SpellCircle.TERRESTRIAL: 1, SpellCircle.CELESTIAL: 2, SpellCircle.SOLAR: 3,
                  SpellCircle.SHADOWLANDS: 1, SpellCircle.LABYRINTH: 2, SpellCircle.VOID: 3}
def _charm_description(charm) -> str:
    """The Charm's description, with the per-circle casting time appended when the
    Charm grants a magic circle (the Sorcery or Necromancy Circle initiation Charms).
    Other Charms are returned unchanged."""
    turns = _SHAPING_TURNS.get(charm.grants_circle) if charm.grants_circle else None
    if not turns:
        return charm.description
    page = "p.216" if circle_kind(charm.grants_circle) == "sorcery" else "p.223"
    note = (f"{charm.grants_circle.value} Circle spells require {turns} "
            f"turn{'s' if turns > 1 else ''} of shaping the Essence before taking "
            f"effect ({page}).")
    return f"{charm.description} {note}".strip()
def _cost_str(cost: CharmCost) -> str:
    if cost.raw:
        return cost.raw
    parts = []
    if cost.motes:
        parts.append(f"{cost.motes}m")
    if cost.willpower:
        parts.append(f"{cost.willpower}wp")
    if cost.health:
        # The damage type is named only where a source (or a homebrew author) says
        # so; unset renders "1hl" exactly as before, which is every printed Charm.
        kind = DAMAGE_LABELS.get(cost.health_type, "") if cost.health_type else ""
        parts.append(f"{cost.health}hl {kind}".strip())
    return ", ".join(parts) if parts else "—"
def _health_label(hl: derive.HealthLevelView) -> str:
    if hl.incapacitated:
        base = "Incap"
    elif hl.penalty == 0:
        base = "-0"
    else:
        base = str(hl.penalty)
    return f"{base} ★" if hl.source else base   # ★ marks a Charm-granted level
