"""
ui/view/charm_trees.py — the Charm and spell detail cards, and the Charm tree
graph of one category.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...engine import validate
from ...engine.labels import _label
from ...models.character import Character
from ...models.rules import RuleSet

from ._base import CharmDetail, CharmGraph, CharmNode, _charm_description, _cost_str


def charm_requirements(ruleset: RuleSet, charm) -> tuple[str, list[list[str]]]:
    """Return the requirement line and the prerequisite groups of `charm`.

    The requirement line gives each trait minimum and the Essence minimum, for
    example "Martial Arts 4, Essence 2". Each prerequisite group is a list of Charm
    names, and one name in a group satisfies it. A breadth prerequisite is a group
    of one label. The result does not use a character.
    """
    # Every trait minimum, not just the primary one: a Charm may gate on more than one
    # Ability (Ascendant Battle Visage needs Brawl 5 AND Endurance 5, p.102), and the
    # engine owns the list so the card cannot show half the requirements.
    reqs = [f"{_label(name)} {rating}"
            for name, rating in validate.charm_ability_requirements(charm) if rating]
    reqs.append(f"Essence {charm.min_essence}")
    groups = [[name for name, _ in group] for group in charm_prerequisite_links(ruleset, charm)]
    return ", ".join(reqs), groups


def charm_prerequisite_links(ruleset: RuleSet, charm) -> list[list[tuple[str, Optional[str]]]]:
    """Return the prerequisite groups of `charm` as (name, charm id) pairs.

    The id is None for a Charm that the ruleset does not contain, and for a breadth
    prerequisite. One pair in a group satisfies the group.
    """
    groups = [[(ruleset.charms[r].name, r) if r in ruleset.charms else (r, None)
               for r in group]
              for group in charm.prerequisites]
    # A breadth prerequisite ("any 3 Occult Charms") names no id, so it cannot be a
    # group of Charm names — it rides as its own single-entry group, which is how the
    # card already renders "one of these" lines. Without this the five Aspect-Book
    # Charms that have ONLY a breadth prerequisite would show none at all.
    groups += [[(validate.charm_count_requirement_label(req), None)]
               for req in charm.prerequisite_counts]
    return groups


def build_charm_detail(ruleset: RuleSet, character: Character, charm_id: str) -> Optional[CharmDetail]:
    """Display detail for a single Charm: its requirements (gating ability + min
    essence), prerequisite Charms by name, and the character's relationship to it.
    Pure; eligibility comes from engine.validate."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        return None
    requirement, groups = charm_requirements(ruleset, charm)
    return CharmDetail(
        id=charm.id,
        name=charm.name,
        description=_charm_description(charm),
        type=charm.type.value,
        cost=_cost_str(charm.cost),
        duration=charm.duration,
        requirement=requirement,
        prerequisite_groups=groups,
        owned=charm_id in character.charms,
        available=validate.meets_charm_requirements(ruleset, character, charm),
        foreign_splat=(validate.splat_of(charm)
                       if validate.is_foreign_charm(ruleset, character, charm) else ""),
        custom=charm.custom,
    )


@dataclass
class SpellDetail:
    id: str
    name: str
    circle: str
    cost: str
    description: str
    owned: bool
    available: bool                        # a known Charm grants its Circle
    custom: bool = False                   # see CharmRow.custom


def build_spell_detail(ruleset: RuleSet, character: Character, spell_id: str) -> Optional[SpellDetail]:
    """Display detail for a single spell: its Circle, casting cost, description, and
    the character's relationship to it. Pure; eligibility comes from engine.validate
    (post-chargen rules — the chargen Solar bar does not apply here)."""
    spell = ruleset.spells.get(spell_id)
    if spell is None:
        return None
    return SpellDetail(
        id=spell.id,
        name=spell.name,
        circle=spell.circle.value,
        cost=_cost_str(spell.cost),
        description=spell.description,
        owned=spell_id in character.spells,
        available=validate.meets_spell_requirements(ruleset, character, spell, chargen=False),
        custom=spell.custom,
    )


def charm_on_splat_page(ruleset: RuleSet, character: Character, charm,
                        splat: str = "") -> bool:
    """Whether `charm` belongs on the picker page for `splat` — the filter behind the
    picker's Splat dropdown (core p.127, the Eclipse generalist rule).

    `""` or the character's own Exalt type means the NATIVE page: exactly what
    validate.charm_matches_splat allows, cross-tier styles included, so every splat's
    existing pages are untouched. Any other value is a foreign page, which exists only
    while the caste privilege is open and lists that splat's own Charms minus anything
    already on the native page — otherwise a Celestial's Hungry Ghost Style, which is
    nominally Abyssal, would appear on two pages at once."""
    native = validate.charm_matches_splat(character, charm, ruleset)
    if not splat or splat == character.exalt_type:
        return native
    if not validate.foreign_charms_open(ruleset, character):
        return False
    return charm.exalt_type == splat and not native


# The sub-tree key for Charms in a Virtue-split category that carry no Virtue of
# their own. Not a VirtueName, so it can never collide with a real sub-key.
UNKEYED_SUBTREE = "general"


def virtue_split(ruleset: RuleSet, category: str) -> list[str]:
    """Sub-category keys for a data category whose Charms span several Virtues.

    The spirit Charms are the one such category: all but one sit under
    'spirit_templates', each keyed to one of the four Virtues via `min_virtue`.
    The picker presents them as four trees ('spirit_templates:compassion', ...)
    so the Virtue structure is visible. For a spirit Charm the Virtue IS the
    path.

    Ghost Arcanoi deliberately never split, even where a path spans several
    Virtues. For a ghost Arcanos the Virtue is a per-entry GATE, not an
    organizing axis -- the book prints each art as one tree and its chains cross
    Virtues freely (Soul Anchor, Temperance 2, roots the whole Conviction-keyed
    body of Chains of the Ancient Monarchs). ⚠ A multi-Virtue path put through the
    general rule below mis-splits into sparse per-Virtue trees with cross-tree
    prereq edges; the E:Ab paths are single-Virtue and hide this, the Book of Bone
    and Ebony ones do not. They render as one tree per art. Anything not
    Virtue-keyed returns [].

    A split category may also hold Charms that are NOT Virtue-keyed: the one such
    spirit Charm is Terrestrial Circle Sorcery, whose printed minimums are
    Essence 3 and Occult 5 and no Virtue at all (PG p.48). Those go in a final
    ':general' sub-tree, because a per-Virtue split alone would drop them out of
    every tree and out of the picker entirely -- present in the data, unbuyable
    in the UI, which is exactly the dead-field shape this codebase keeps hitting.
    Splitting a category is therefore only safe if it accounts for every Charm
    in it."""
    charms = [c for c in ruleset.charms.values() if c.category == category]
    if any(c.exalt_type == "Ghost" for c in charms):
        return []
    virtues = {c.min_virtue for c in charms if c.min_virtue}
    if len(virtues) < 2:
        return []
    keys = [f"{category}:{v}" for v in sorted(virtues)]
    if any(not c.min_virtue for c in charms):
        keys.append(f"{category}:{UNKEYED_SUBTREE}")
    return keys


def build_charm_graph(ruleset: RuleSet, character: Character, category: str,
                      splat: str = "") -> CharmGraph:
    """Assemble the prerequisite graph for one Charm category, tagging each node
    by the character's relationship to it: owned, available (learnable now), or
    locked. Pure — eligibility comes from engine.validate.

    Prerequisites that live in OTHER categories are drawn in too, transitively, and
    flagged `external`. Without them a cross-tree tree has no visible root and its
    branches fall apart into disconnected nodes — Lunar Body Enhancement is three
    separate trees all hanging off Shapeshifting's Shaping the Ideal Form, and the
    sourcebook's own diagrams draw those foreign prerequisites inside the box for
    exactly this reason.

    `splat` selects which Exalt type's page the category belongs to; "" is the
    character's own. Category names collide across splats ("melee" exists for three
    of them), so the pair (category, splat) — not the category alone — identifies a
    tree. External prerequisites are pulled in by id and are NOT re-filtered: a
    foreign tree's prerequisites are its own splat's Charms by construction."""
    owned = set(character.charms)
    base, sep, virtue = category.partition(":")
    # A composite key like 'spirit_templates:compassion' (from virtue_split)
    # selects one Virtue's sub-tree of a category whose Charms span several
    # Virtues: the data category is `base`, restricted to `min_virtue == virtue`.
    # The martial-arts keys ('martial_arts:snake') are NOT composites -- the full
    # string IS the data category, and since no bare 'martial_arts' category
    # exists this guard keeps them on the direct-equality path.
    base_is_category = bool(sep) and any(
        c.category == base for c in ruleset.charms.values())
    if base_is_category:
        # ':general' selects the Charms of a split category that carry no Virtue --
        # see virtue_split, which only emits that key when such Charms exist.
        def _in_subtree(c) -> bool:
            return not c.min_virtue if virtue == UNKEYED_SUBTREE else c.min_virtue == virtue
        in_category = [c for c in ruleset.charms.values()
                       if c.category == base and _in_subtree(c)
                       and charm_on_splat_page(ruleset, character, c, splat)]
    else:
        in_category = [c for c in ruleset.charms.values()
                       if c.category == category and charm_on_splat_page(ruleset, character, c, splat)]
    category_ids = {c.id for c in in_category}

    external_ids: set[str] = set()
    frontier = [req for c in in_category for group in c.prerequisites for req in group]
    while frontier:
        req = frontier.pop()
        if req in category_ids or req in external_ids:
            continue
        prereq = ruleset.charms.get(req)
        if prereq is None:
            continue
        external_ids.add(req)
        frontier.extend(r for group in prereq.prerequisites for r in group)

    charms = in_category + [ruleset.charms[i] for i in external_ids]
    charms.sort(key=lambda c: c.id)

    ox_id = validate.ox_body_charm_id(ruleset, character)
    gift_id = validate.gift_charm_id(ruleset, character)
    nodes = []
    for c in charms:
        # Ox-Body is repeatable and lives on character.ox_body, not character.charms:
        # it is "owned" once at least one copy is bought, else available per its reqs.
        # The Gift-granting Charm (Deadly Beastman Transformation) is the same shape,
        # tracked on character.beastman_gifts.
        if c.id and c.id in (ox_id, gift_id):
            purchases = character.ox_body if c.id == ox_id else character.beastman_gifts
            state = "owned" if purchases else (
                "available" if validate.meets_charm_requirements(ruleset, character, c) else "locked")
        elif c.id in owned:
            state = "owned"
        elif validate.meets_charm_requirements(ruleset, character, c):
            state = "available"
        else:
            state = "locked"
        nodes.append(CharmNode(
            c.id, c.name, state, c.min_ability, c.min_essence,
            external=c.id in external_ids,
            count_requirement=", ".join(
                validate.charm_count_requirement_label(r) for r in c.prerequisite_counts),
            custom=c.custom))

    ids = {c.id for c in charms}
    edges = [(req, c.id) for c in charms for group in c.prerequisites
             for req in group if req in ids]
    # A node is a layout root when nothing inside the graph points at it — not merely
    # when it has no prerequisites at all, which would orphan every cross-tree branch.
    has_parent = {t for _, t in edges}
    roots = [c.id for c in charms if c.id not in has_parent]
    return CharmGraph(category=category, nodes=nodes, edges=edges, roots=roots)
