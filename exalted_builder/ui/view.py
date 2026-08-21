"""
ui/view.py — the presenter: assemble a display-ready view model from a RuleSet
and Character.

This is the seam between the engine and the rendering layer. It calls the engine
(derive, validate), resolves Charm/Spell ids to names, groups abilities by their
ability-caste (as the one-page sheet does), and shapes everything into plain
dataclasses the UI can render directly. It contains NO game logic of its own and
imports NO UI toolkit, so it is unit-testable on its own and the NiceGUI layer
(ui/app.py) stays a thin renderer.
"""

from __future__ import annotations

from dataclasses import dataclass, field, field as dc_field
from typing import Optional, Sequence

from .. import custom_content
from ..engine import (advancement, adversaries as advmod,
                      artifacts as artifactsmod, costs, derive, elder,
                      merits as meritsmod, paths as engine_paths, validate)
from ..models.adversary import Adversary
from ..models.character import Armor, Character, HouseRules, Weapon, XpEntry
from ..models.rules import (DAMAGE_LABELS, AbilityName, AttributeName, BackgroundType,
                            CharmCost, Damage, PoolKind, RuleSet, SpellCircle,
                            TRACK_CIRCLES, VirtueName, circle_kind)


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


# --------------------------------------------------------------------------- #
# Gear stat lines — ONE format string per kind, for both the character's own gear
# and a catalogue entry.
#
# ⚠ ONE definition, used by the row readout and by the catalogue dialog alike. Two
# copies drift on details no test looks at — the spacing before "Mob" differed while
# one docstring claimed the two matched.
#
# Duck-typed on purpose: `Weapon`/`Armor` (a character's item, usually passed through
# `derive.effective_*` so the material bonus is folded in) and `WeaponType`/`ArmorType`
# (a catalogue row) carry the same stat field names, and the caller decides which it
# has. `material` is the wielder-dependent tag, which a pre-pick catalogue row has no
# character to compute — hence a parameter rather than a lookup in here.
# --------------------------------------------------------------------------- #

def weapon_stat_line(weapon, *, material: str = "") -> str:
    """One-line weapon stat readout: `Acc+2 Dmg+5L Def+0 Spd+0  ◈ Orichalcum`."""
    tag = f"  ◈ {material}" if material else ""
    return (f"Acc{weapon.accuracy:+d} Dmg{weapon.damage:+d}{weapon.damage_type} "
            f"Def{weapon.defense:+d} Spd{weapon.speed:+d}{tag}")


def armor_stat_line(armor, *, material: str = "") -> str:
    """One-line armour stat readout: `Soak 3L/4B  Mob-1 Ftg1  ◈ Moonsilver`."""
    tag = f"  ◈ {material}" if material else ""
    return (f"Soak {armor.soak_lethal}L/{armor.soak_bashing}B  "
            f"Mob{armor.mobility_penalty:+d} Ftg{armor.fatigue}{tag}")


@dataclass
class InventoryRow:
    """One thing the character owns, whatever list it is stored in.

    The INVENTORY is a VIEW, not a storage shape (human's model, 2026-08-13: "your
    inventory, which is Everything, but you can filter it down to certain types of
    goods, some of which would overlap"). The three lists stay typed and separate —
    a weapon carries accuracy and rate, armour carries soak and fatigue, goods carry
    neither, and collapsing them would mean a save migration plus rewriting every index
    into `character.weapons` (the dice-pool sidebar's, for one) to buy nothing.

    `kinds` is a SET because the categories genuinely overlap: an artifact daiklave is a
    weapon AND an artifact, a shield is armour, an arrow is a weapon and ammunition. A
    filter picks rows whose kinds INTERSECT what it asks for, so the same row can appear
    under two filters and be one object underneath.
    """
    name: str
    kinds: tuple[str, ...]                 # "weapon" / "armor" / "artifact" / "goods" …
    detail: str = ""                       # the stat line, or the price, or ""
    quantity: int = 1
    resources_cost: int = 0
    artifact_rating: int = 0
    acquired: str = ""                     # only meaningful for artifacts
    index: int = 0                         # position in its OWN list
    list_name: str = ""                    # which list that is — the edit route back
    # An artifact and the gear row `grant_gear` stamped for it are ONE OBJECT and get
    # ONE row (the human, 2026-08-13: two peer rows for one daiklave "feels odd, and a
    # little obtuse"). The artifact owns the row; its stat line rides in `detail` and
    # its editor is reached through this SECOND route back. Empty for every unmerged
    # row, which is the large majority.
    #
    # ⚠ Display-only. The typed lists are untouched, so `character.weapons` keeps its
    # positional indices — the dice-pool sidebar reads them.
    linked_list_name: str = ""
    linked_index: int = 0


INVENTORY_FILTERS = ("all", "weapon", "armor", "artifact", "goods",
                     "ammunition")


def inventory_rows(ruleset: RuleSet, character: Character) -> list[InventoryRow]:
    """Everything the character owns, from all four lists, in one list of rows.

    Pure and presentation-only: it computes no rule and validates nothing. The artifact
    kind is taken from `engine.artifacts.artifact_items` rather than from
    `artifact_rating` directly, so a gear row that is the STAT LINE of a standalone
    artifact is not tagged as a second artifact — the same dedup the budget uses, read
    from the same place, so the inventory and the budget cannot disagree about what is
    an artifact.
    """
    owned = {i.key: i for i in artifactsmod.artifact_items(character)}
    # A character's `Weapon` carries no tags (decision 0007: inline copies), so
    # ammunition is recovered from the catalogue by name — the same recovery, with the
    # same failure direction, as the dice-pool sidebar's.
    ammo = _ammunition_indices(ruleset, character)

    def _art(source: str, name: str):
        return owned.get(artifactsmod.item_key(source, name))

    # Which standalone artifact each granted gear row belongs to, as
    # `(list_name, gear index) -> artifact index`. Resolved against the artifacts
    # actually present rather than trusting the stored key, so an ORPHANED link (the
    # artifact renamed or deleted) leaves the gear row standing on its own line instead
    # of merging into nothing and vanishing — the same failure direction
    # `artifact_items` picked for the same link.
    art_index = {}
    for idx, art in enumerate(character.artifacts):
        if art.name.strip():
            art_index.setdefault(
                artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, art.name), idx)
    merged: dict[int, tuple[str, int]] = {}          # artifact idx -> (list, gear idx)
    for list_name, gear in (("weapons", character.weapons), ("armor", character.armor)):
        for idx, item in enumerate(gear):
            target = art_index.get(item.from_artifact)
            if item.from_artifact and target is not None and target not in merged:
                merged[target] = (list_name, idx)
    merged_gear = {v for v in merged.values()}

    rows: list[InventoryRow] = []
    for idx, w in enumerate(character.weapons):
        if ("weapons", idx) in merged_gear:
            continue          # shown on its artifact's row, as one object
        item = _art(artifactsmod.SOURCE_WEAPON, w.name)
        kinds = ["weapon"]
        if item is not None:
            kinds.append("artifact")
        if idx in ammo:
            kinds.append("ammunition")
        rows.append(InventoryRow(
            name=w.name or "(unnamed)", kinds=tuple(kinds),
            detail=weapon_stat_line(w), quantity=w.quantity,
            resources_cost=w.resources_cost, artifact_rating=w.artifact_rating,
            acquired=w.acquired if item is not None else "",
            index=idx, list_name="weapons"))
    for idx, a in enumerate(character.armor):
        if ("armor", idx) in merged_gear:
            continue
        item = _art(artifactsmod.SOURCE_ARMOR, a.name)
        kinds = ["armor"] + (["artifact"] if item is not None else [])
        rows.append(InventoryRow(
            name=a.name or "(unnamed)", kinds=tuple(kinds),
            detail=armor_stat_line(a), resources_cost=a.resources_cost,
            artifact_rating=a.artifact_rating,
            acquired=a.acquired if item is not None else "",
            index=idx, list_name="armor"))
    for idx, art in enumerate(character.artifacts):
        kinds, detail, link = ["artifact"], art.note, ("", 0)
        if idx in merged:
            list_name, gear_idx = merged[idx]
            gear = getattr(character, list_name)[gear_idx]
            # The STAT LINE is what the merged row shows, because that is the half a
            # player is looking for on a weapon they own — the artifact's own note is
            # prose and lives in its editor. `kinds` gains the gear's kind so the row
            # still answers to the Weapons/Armor filter: merging two rows must not cost
            # the object a filter it used to appear under.
            kinds.append("weapon" if list_name == "weapons" else "armor")
            detail = (weapon_stat_line(gear) if list_name == "weapons"
                      else armor_stat_line(gear))
            link = (list_name, gear_idx)
        rows.append(InventoryRow(
            name=art.name or "(unnamed)", kinds=tuple(kinds),
            detail=detail, artifact_rating=art.rating, acquired=art.acquired,
            index=idx, list_name="artifacts",
            linked_list_name=link[0], linked_index=link[1]))
    for idx, g in enumerate(character.gear):
        rows.append(InventoryRow(
            name=g.name or "(unnamed)", kinds=("goods",), detail=g.note,
            quantity=g.quantity, resources_cost=g.resources_cost,
            index=idx, list_name="gear"))
    return rows


def filter_inventory(rows: list[InventoryRow], kind: str) -> list[InventoryRow]:
    """The rows matching one filter — `"all"`, or any kind. Overlapping by design: an
    artifact daiklave answers to both `weapon` and `artifact`."""
    if kind == "all":
        return list(rows)
    return [r for r in rows if kind in r.kinds]


def inventory_counts(rows: list[InventoryRow]) -> dict[str, int]:
    """How many rows each filter would show — for the filter labels, so a player can
    see that a tab is empty before clicking it. Sums to MORE than the row count when
    anything overlaps, which is correct and is why the filters are not a partition."""
    return {k: len(filter_inventory(rows, k)) for k in INVENTORY_FILTERS}


def build_charm_detail(ruleset: RuleSet, character: Character, charm_id: str) -> Optional[CharmDetail]:
    """Display detail for a single Charm: its requirements (gating ability + min
    essence), prerequisite Charms by name, and the character's relationship to it.
    Pure; eligibility comes from engine.validate."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        return None
    # Every trait minimum, not just the primary one: a Charm may gate on more than one
    # Ability (Ascendant Battle Visage needs Brawl 5 AND Endurance 5, p.102), and the
    # engine owns the list so the card cannot show half the requirements.
    reqs = [f"{_label(name)} {rating}"
            for name, rating in validate.charm_ability_requirements(charm) if rating]
    reqs.append(f"Essence {charm.min_essence}")
    groups = [[ruleset.charms[r].name if r in ruleset.charms else r for r in group]
              for group in charm.prerequisites]
    # A breadth prerequisite ("any 3 Occult Charms") names no id, so it cannot be a
    # group of Charm names — it rides as its own single-entry group, which is how the
    # card already renders "one of these" lines. Without this the five Aspect-Book
    # Charms that have ONLY a breadth prerequisite would show none at all.
    groups += [[validate.charm_count_requirement_label(req)]
               for req in charm.prerequisite_counts]
    return CharmDetail(
        id=charm.id,
        name=charm.name,
        description=_charm_description(charm),
        type=charm.type.value,
        cost=_cost_str(charm.cost),
        duration=charm.duration,
        requirement=", ".join(reqs),
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


_TABS = ("Edit", "Gear", "Advantages", "Charms", "Combos", "Play", "ST",
         "Custom", "Sheet")


def visible_tabs(locked: bool, *, combos: bool = True) -> tuple[str, ...]:
    """The tabs for a character at this stage of its life.

    **Edit is on the bar on BOTH sides of the lock** (decision 0013), as are Charms,
    Combos and Advantages. The dot tracks change MODE rather than being replaced: free
    setters pre-lock, steppers that spend XP post-lock.

    ⚠ There is no XP tab, and splitting one back out is how these traits come to be
    implemented twice and disagree — a hardcoded trait ceiling on a separate XP surface
    makes Legendary Attribute unbuyable there while chargen honours it. Everything an
    XP tab would hold lives beside the thing it acts on: traits on the dot tracks, the
    ledger and Adjust XP in Edit's sticky column, permanent Resonance and the
    withheld-Charm note beside their traits, Crafts/Colleges/Specialties/equipment on
    the panels that already exist here.

    Play is locked-only. The tracker overlays spent motes, marked health and Willpower
    onto capacities derived from the finished character, and every one of those moves
    while chargen is still open — a half-built character's track is a set of boxes that
    change under the player. It is also the tab most likely to mislead: play-state is
    validation-isolated (decision 0006) and never enters chargen, so marks made before
    the lock silently mean nothing to the point accounting.
    """
    hidden = {"Play"} if not locked else set()
    # A splat that may never learn Combos and builds no Arrays either (ghosts, E:Ab
    # p.234) loses the tab rather than being given an empty one that refuses every
    # attempt. Asked of `view.has_combos_tab` by the caller, so the rule lives with
    # the engine and this stays a pure function of two booleans.
    if not combos:
        hidden.add("Combos")
    return tuple(t for t in _TABS if t not in hidden)


def resolve_tab(name: str, locked: bool, *, combos: bool = True) -> str:
    """`name`, or a sensible landing tab when locking/unlocking just hid it.

    Edit survives the lock now, so it is the answer in both directions — a player who
    locks while editing traits stays where they were, looking at the same dots, which
    is the point of the merge.
    """
    if name in visible_tabs(locked, combos=combos):
        return name
    return "Edit"


# Presentation-only: intra-splat chargen origins to offer per Exalt type, and their
# display labels. The origin *value* drives ruleset.budgets_for (keyed "<exalt>" for
# the first/default origin and "<exalt>:<origin>" for the rest); all the budget
# numbers live in chargen_budgets.json — this map is just which choices to show.
_SPLAT_ORIGINS: dict[str, dict[str, str]] = {
    # A Solar trained by the Cult of the Illuminated has a different initiation
    # entirely (p.89): 30 Abilities, 9 Backgrounds, 8 Charms, Essence 3, plus a
    # training camp and a Calling. "standard" has no `Solar:standard` budget row, so
    # it falls back to the plain "Solar" row — the same trick "dynastic" and "loyal"
    # use below.
    "Solar": {"standard": "Standard", "illuminated": "Cult of the Illuminated"},
    # The Outcaste book adds four Dragon-Blooded origins on top of the core two. Each
    # varies by UPBRINGING as well — see _ORIGIN_UPBRINGINGS below, which is the second
    # dropdown; the origin decides Backgrounds/Charms/Virtues, the upbringing decides
    # the Ability budget and its minimums.
    "Dragon-Blooded": {
        "dynastic": "Dynastic", "outcaste": "Outcaste",
        "lookshy": "Lookshy (Seventh Legion)",
        "forest-witch": "Forest Witch",
        "lost-egg": "Lost Egg",
        "pirate": "Pirate (Eos and Ossissa)",
        # Cult p.96: a Dragon-Blooded trained by the Cult of the Illuminated is
        # generated as a standard outcaste with four exceptions (30 Abilities, 7
        # Backgrounds, the Cult's Backgrounds, and a training camp). Unlike the
        # Solar Cult origin there is no Calling — the page never gives them one.
        "illuminated": "Cult of the Illuminated",
    },
    # Abyssal Backgrounds depend on standing with the Deathlord: 13 dots for a loyal
    # deathknight, 5 for a fugitive/renegade (p.122). First key is the default
    # (plain "Abyssal" budget row); "fugitive" maps to "Abyssal:fugitive".
    "Abyssal": {"loyal": "Loyal Deathknight", "fugitive": "Fugitive"},
    # Unlike the above two, Lunar "casteless" is coupled to the Caste field itself,
    # not independent of it (engine.validate.check_lunar_casteless_consistency) — the
    # editor doesn't yet auto-sync the Caste dropdown when this is picked, so choosing
    # "Casteless" here also requires setting Caste to Casteless, or validation flags it.
    "Lunar": {"society": "Society (Silver Pact)", "casteless": "Casteless"},
    # A ronin Sidereal evaded the Celestial Hierarchy entirely (p.100): 25 abilities,
    # 7 backgrounds from a fixed list, 8 Charms with no Sidereal Martial Arts, no
    # Colleges and no Ability minimums. Independent of the Caste field (a ronin still
    # has a Caste), unlike Lunar's casteless.
    "Sidereal": {"hierarchy": "Celestial Hierarchy", "ronin": "Ronin"},
    # Core p.103 draws one line through the mortal rules: a heroic mortal gets 6/4/3
    # Attributes and 22 Ability dots, an ordinary one 4/3/3 and 16. Everything else on
    # the page (5 Backgrounds, no Charms, Essence 1, 21 bonus points) is shared, which
    # is why this is an origin and not two splats. "heroic" is the default and so has
    # no `Mortal:heroic` row — it falls back to the plain "Mortal" row, the same trick
    # "dynastic" and "loyal" use above.
    "Mortal": {"heroic": "Heroic Mortal", "ordinary": "Ordinary Mortal"},
    # E:Ab p.126 and its "THE MUNDANE DEAD" sidebar: the heroic dead get 6/4/3
    # Attributes, 22 Ability dots, six Arcanoi and 21 bonus points; the mundane dead
    # 4/3/3, 16, two and 15. Everything else (Virtues, Essence 2, Fetters, the Essence
    # pool) is shared, which is why this is an origin and not two splats — the same
    # shape the mortal line above takes.
    #
    # Unlike every origin above it, "heroic" is NOT a bare default: ghosts also carry
    # an UPBRINGING, and `_keyed_row` only consults the ":origin:upbringing" key when
    # the origin is non-empty. See _ORIGIN_UPBRINGINGS.
    "Ghost": {"heroic": "Heroic Dead", "mundane": "Mundane Dead"},
    # The God-Blooded Half-Caste heritage (p.47): "learn the Charms of their parents",
    # where the parent's Exalt type IS the origin. Only the Half-Caste heritage uses it —
    # the origin select is gated on heritage_traits.charm_access_parent, so a Ghost-
    # Blooded never sees these. The values are the Exalt type strings themselves, so
    # validate.heritage_charm_access returns character.origin directly.
    # The God-Blooded have no entry HERE — their origin is HERITAGE-keyed
    # (`GodbloodedHeritage.origin_options`: the Half-Caste's five parents, the
    # Fae-Blooded's Noble/Commoner), read by `_origin_options` from the data.
    # The Dragon-Kings (PG p.159-160): two origins with different budgets, Path pools,
    # Backgrounds and mandatory abilities. "modern" has no `Dragon-Kings:modern` budget
    # row, so it falls back to the plain "Dragon-Kings" row — the dynastic trick.
    "Dragon-Kings": {"modern": "Modern", "ancient": "Ancient"},
    # The Mountain Folk (CH6 pp.230-231): Enlightenment is the origin axis, and it
    # rewrites nearly every chargen number — 16/13/10 vs 8/4/3 Attributes, a two-pool
    # Ability budget, per-caste Background dots, trait ceilings, Essence and
    # Willpower caps. "enlightened" HAS a `Mountain-Folk:enlightened` row (unlike the
    # dynastic trick above), so it is the default explicitly.
    "Mountain-Folk": {"enlightened": "Enlightened", "unenlightened": "Unenlightened"},
}

# The second axis, keyed by "<exalt_type>:<origin>". Only origins that HAVE variants
# appear here, and the first key of each is the origin's own default (it has no
# ":<upbringing>" budget row, so it falls back to the origin row — the same trick the
# origins above use against the splat row). The Outcaste book is the only source of
# these so far; every other splat has no entry and so gets no second dropdown.
_ORIGIN_UPBRINGINGS: dict[str, dict[str, str]] = {
    # p.68: a Lookshy Terrestrial who was not raised there trades the 35 Ability dots
    # and the Lookshy minimums for 25/10, but keeps the 13 Backgrounds and 6 Charms.
    "Dragon-Blooded:lookshy": {
        "": "Born in Lookshy", "foreign": "Raised elsewhere"},
    # p.132: an ex-Dynast keeps the Realm schooling; other outcastes get 25 dots; one
    # raised by Oreithyia also buys Virtues and Essence cheaper (p.133).
    "Dragon-Blooded:forest-witch": {
        "": "Ex-Dynast", "outcaste": "Outcaste", "oreithyia": "Raised by Oreithyia"},
    # p.159: three Realm cases plus the Threshold, which is the only one that drops
    # the Aspect/Favored minimum to 10.
    "Dragon-Blooded:lost-egg": {
        "": "Realm, lower-class birth",
        "graduate": "Pasiap's Stair / Cloister of Wisdom",
        "patrician": "Patrician-born",
        "threshold": "Threshold outcaste"},
    # p.96: Dynast or born outcaste; both need Sail.
    "Dragon-Blooded:pirate": {"": "Dynast", "outcaste": "Born outcaste"},
    # E:Ab p.126: where the ghost is FROM decides the Background pool — "Ghosts from
    # areas that uphold the Immaculate Philosophy have five (5) dots to spend on
    # Backgrounds, while those from areas with active ancestor worship have eight (8)",
    # and an Immaculate-region ghost may not buy Ancestor Cult or Grave Goods above •.
    # Independent of heroic/mundane, so both origins carry it.
    "Ghost:heroic": {"": "Ancestor-worshipping region",
                     "immaculate": "Immaculate-dominated region"},
    "Ghost:mundane": {"": "Ancestor-worshipping region",
                      "immaculate": "Immaculate-dominated region"},
}


def _heritage_uses_origin(ruleset: RuleSet, character) -> bool:
    """Whether the character's heritage keys off the origin axis. Two God-Blooded
    heritages do: the Half-Caste's parent Exalt type (p.47) and the Fae-Blooded's
    Noble/Commoner (p.73-79). `GodbloodedHeritage.origin_options` is the single source
    — the editor renders the Origin dropdown from it."""
    cd = ruleset.castes.get(character.caste)
    return bool(cd is not None and cd.heritage_traits is not None
                and cd.heritage_traits.origin_options)


def _origin_options(ruleset: RuleSet, character) -> dict[str, str]:
    """The Origin dropdown options for this character: the splat's origins, EXCEPT
    the God-Blooded, whose origin is their HERITAGE's own axis — the Half-Caste's
    parent Exalt type, the Fae-Blooded's Noble/Commoner — and appears only for that
    heritage (a Ghost-Blooded never sees a meaningless Solar origin). Every other
    splat's origins are unconditional, so they render exactly as before."""
    if character.exalt_type == "God-Blooded":
        cd = ruleset.castes.get(character.caste)
        opts = cd.heritage_traits.origin_options if (
            cd is not None and cd.heritage_traits is not None) else []
        return {o: o for o in opts} if opts else {}
    return _SPLAT_ORIGINS.get(character.exalt_type, {})


def upbringing_options(exalt_type: str, origin: str) -> dict[str, str]:
    """The upbringing choices for this splat/origin, or {} when it has none (which is
    every splat but the Outcaste-book Dragon-Blooded). The UI renders the second
    dropdown only when this is non-empty, so no other splat grows a control."""
    return _ORIGIN_UPBRINGINGS.get(f"{exalt_type}:{origin}", {})


@dataclass
class XpLogRow:
    index: int           # position in character.xp_log
    label: str           # human-readable purchase, e.g. "Melee 2 → 3"
    detail: str          # ability/charm/etc. label without the rating arrows
    cost: int


def _xp_entry_label(ruleset: RuleSet, character: Character, entry: XpEntry) -> str:
    domain, _, key = entry.target.partition(".")
    reduction = (entry.from_rating is not None and entry.to_rating is not None
                 and entry.to_rating < entry.from_rating)
    note = (f"  ↓ {entry.detail}" if entry.detail else "  ↓") if reduction else ""
    if domain in ("attributes", "abilities", "virtues"):
        return f"{_label(key)} {entry.from_rating} → {entry.to_rating}{note}"
    if domain == "crafts":
        return f"Craft ({entry.detail}) {entry.from_rating} → {entry.to_rating}"
    if domain == "colleges":
        college = ruleset.colleges.get(entry.detail)
        return (f"College: {college.name if college else entry.detail} "
                f"{entry.from_rating} → {entry.to_rating}")
    if domain in ("willpower", "essence"):
        return f"{domain.title()} {entry.from_rating} → {entry.to_rating}{note}"
    if domain == "charms":
        charm = ruleset.charms.get(entry.detail)
        return f"Charm: {charm.name if charm else entry.detail}"
    # A Charm redeemed against a Weak Essence credit. Its own target keeps the audit
    # from re-pricing it, but the target has no dot in it, so `domain` was the whole
    # string and the row fell through to the raw "charms_withheld" — the charm's own
    # name never appeared. Keeps the "Charm:" prefix the ordinary rows use so the
    # ledger still sorts and scans as one thing.
    if domain == validate.WITHHELD_CHARM_TARGET:
        charm = ruleset.charms.get(entry.detail)
        return f"Charm: {charm.name if charm else entry.detail} (withheld, no XP)"
    if domain == "spells":
        spell = ruleset.spells.get(entry.detail)
        return f"Spell: {spell.name if spell else entry.detail}"
    if domain == "combos":
        return f"Combo: {entry.detail}"
    if domain == "specialties":
        return f"Specialty: {entry.detail.replace(':', ' — ', 1)}"
    if domain == "ox_body":
        charm = validate.ox_body_charm(ruleset, character)
        label = next((v.label for v in (charm.variants if charm else []) if v.key == entry.detail),
                     entry.detail)
        return f"Ox-Body: {label}"
    if domain == "beastman_gifts":
        charm = validate.gift_charm(ruleset, character)
        labels = {v.key: v.label for v in (charm.variants if charm else [])}
        # advancement.learn_gift logs the purchase's Gift keys joined by '|'
        gifts = ", ".join(labels.get(k, k) for k in entry.detail.split("|") if k)
        return f"{charm.name if charm else 'Beastman Gifts'}: {gifts}"
    # Thaumaturgy (Player's Guide CH3). Names are resolved from the catalogue where
    # there is one and fall back to the logged id, so a custom ritual — or a stale id
    # whose catalogue entry has since gone — still reads as itself rather than
    # vanishing from the ledger.
    if domain == "thaum_arts":
        art = ruleset.thaum_arts.get(entry.detail)
        return f"Art: {art.name if art else entry.detail}"
    if domain == "thaum_specialties":
        art_id, _, name = entry.detail.partition(":")
        art = ruleset.thaum_arts.get(art_id)
        return f"Specialty: {art.name if art else art_id} ({name})"
    if domain == "thaum_sciences":
        science = ruleset.thaum_sciences.get(entry.detail)
        return (f"Science: {science.name if science else entry.detail} "
                f"{entry.from_rating} → {entry.to_rating}")
    if domain in ("thaum_rituals", "thaum_formulas"):
        noun = "Ritual" if domain == "thaum_rituals" else "Formula"
        catalogue = (ruleset.thaum_rituals if domain == "thaum_rituals"
                     else ruleset.thaum_formulas)
        obj = catalogue.get(entry.detail)
        # to_rating carries the level, so the row prices and reads correctly from the
        # log alone (see advancement.learn_thaum_ritual).
        level = f" (level {entry.to_rating})" if entry.to_rating else ""
        return f"{noun}: {obj.name if obj else entry.detail}{level}"
    if domain == "thaum_orientations":
        # detail is "key:Orientation"; a custom name may itself contain a colon, so
        # split from the right — the same reason advancement's undo uses rpartition.
        target, _, orientation = entry.detail.rpartition(":")
        catalogue = ruleset.thaum_rituals if key == "ritual" else ruleset.thaum_formulas
        obj = catalogue.get(target)
        return f"Orientation: {obj.name if obj else target} ({orientation})"
    if domain == "elemental_powers":
        power = ruleset.elemental_powers.get(entry.detail)
        return f"Elemental Power: {power.name if power else entry.detail}"
    if domain == "merits":
        # A buy/gain logs the bare merit_id; a drop logs "-<merit_id>". Strip the
        # leading dash so both resolve to the same catalogue name (and the Undo
        # button names the row it will reverse).
        mid = entry.detail.lstrip("-")
        mf = ruleset.merits_flaws.get(mid)
        name = mf.name if mf else mid
        return f"{name} (removed)" if entry.detail.startswith("-") else name
    return entry.target


def build_xp_log(ruleset: RuleSet, character: Character) -> list[XpLogRow]:
    """The XP spend log as display rows, in spend order. Pure presentation; the
    engine owns costs and legality. Only the last row is safe to undo (LIFO)."""
    return [
        XpLogRow(index=i, label=_xp_entry_label(ruleset, character, e),
                 detail=e.target.split(".", 1)[0], cost=e.cost)
        for i, e in enumerate(character.xp_log)
    ]


# Global circle order for display: the two tracks laid end to end in TRACK_CIRCLES
# order (sorcery Terrestrial→Solar, then necromancy Shadowlands→Void). A picker may
# now show circles from BOTH tracks (Abyssals reach sorcery and necromancy), so the
# index must be global rather than per-track.
CIRCLE_DISPLAY_ORDER = tuple(c for circles in TRACK_CIRCLES.values() for c in circles)
_CIRCLE_ORDER = {c: i for i, c in enumerate(CIRCLE_DISPLAY_ORDER)}


def build_spell_picker(ruleset: RuleSet, character: Character) -> list[SpellPickRow]:
    """Every Spell of a circle the character can reach, tagged by the character's
    relationship to it: owned, available (a known Charm grants its circle and it
    isn't a chargen-barred top-circle spell), or locked with a one-line reason.
    Circles the character cannot reach at all (no learnable initiation Charm grants
    them) are omitted, so a plain Solar sees only Sorcery while an Abyssal — whose
    Occult tree holds both sorcery and necromancy initiations — sees both. Ordered
    by circle then name. Pure — eligibility comes from engine.validate."""
    reachable = validate.accessible_circles(ruleset, character)
    # The top circle is barred at *creation* only (core p.100). Once chargen is
    # locked the character is in play and may buy it with experience.
    chargen = not character.chargen_locked
    barred = validate.chargen_barred_circle(ruleset, character) if chargen else None
    rows: list[SpellPickRow] = []
    for spell in sorted(ruleset.spells.values(),
                        key=lambda s: (_CIRCLE_ORDER.get(s.circle, 9), s.name)):
        if spell.circle not in reachable:
            continue
        owned = spell.id in character.spells
        available = validate.meets_spell_requirements(ruleset, character, spell,
                                                      chargen=chargen)
        reason = ""
        if not owned and not available:
            if spell.circle == barred:
                reason = f"{spell.circle.value} Circle spells can't be taken at creation"
            else:
                reason = f"needs a Charm granting the {spell.circle.value} Circle"
        rows.append(SpellPickRow(
            id=spell.id, name=spell.name, circle=spell.circle.value,
            cost=_cost_str(spell.cost), description=spell.description,
            owned=owned, available=available, reason=reason, custom=spell.custom,
        ))
    return rows


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
#
# Four genuinely different mechanical shapes — a binary Art, a rated Science, a
# levelled ritual, a flat-rate formula — so four row types rather than one flat
# list that would fight all four (see docs/status/thaumaturgy.md).
#
# Every price here is the LIST price of one purchase, in whichever currency the
# character is currently spending. It is deliberately not the amount that will be
# charged: under "Magic for Everyone" the engine zeroes the dearest eligible
# purchases collectively, an assignment no single row can know about. The panel
# shows list prices and reads the actual total off `bonus_point_breakdown`, which
# is the one place the free grant is applied.
# --------------------------------------------------------------------------- #

@dataclass
class ThaumSpecialtyRow:
    """A specialty of an Art — a printed aspect or a player-invented one. Both are
    the same purchase at the same rate (p.126); `printed` only says which of the two
    a row came from, which matters for the free grant and for the Occult gate."""
    art_id: str
    name: str
    description: str
    min_occult: int
    printed: bool
    owned: bool
    narrowed: bool
    available: bool
    reason: str
    price: int


@dataclass
class ThaumArtRow:
    id: str
    name: str
    min_occult: int
    roll: str
    cost_text: str          # display, e.g. "3 motes per attempt"
    description: str
    owned: bool
    available: bool
    reason: str
    price: int
    allows_narrowing: bool  # Summoning alone (p.127)
    specialties: list[ThaumSpecialtyRow] = field(default_factory=list)


@dataclass
class ThaumScienceLevelRow:
    rating: int
    description: str        # "" where the book prints no rung (Alchemy 5)


@dataclass
class ThaumScienceRow:
    id: str
    name: str
    roll: str
    cost_text: str
    time: str
    duration: str
    description: str
    rating: int
    max_rating: int
    next_price: int         # to buy the NEXT dot; 0 when none may be bought
    can_raise: bool
    reason: str
    levels: list[ThaumScienceLevelRow] = field(default_factory=list)


@dataclass
class ThaumEntryRow:
    """A ritual or a formula: both are learned once and then owned in one or more
    regional orientations, at a flat point per extra (p.124)."""
    key: str                # catalogue id, or the name for a custom entry
    name: str
    kind: str               # 'ritual' | 'formula'
    level: int
    custom: bool
    owned: bool
    available: bool
    reason: str
    price: int              # to learn it in its first orientation
    orientation_price: int  # to add one further regional version
    orientations: list[str] = field(default_factory=list)   # owned, display strings
    detail: list[tuple[str, str]] = field(default_factory=list)   # (label, value)
    description: str = ""


@dataclass
class ThaumOwnedRow:
    """One line of "what this character has bought", straight off the engine's
    canonical enumeration and priced by it — including the free-grant zeroes, which
    is why this is not recomputed from the rows above."""
    kind: str
    key: str
    label: str
    cost: int
    free: bool


@dataclass
class ThaumPickerView:
    currency: str           # 'BP' | 'XP'
    usable: bool            # False for a splat that may hold but never use it
    usable_note: str
    occult: int
    free_picks: int         # "Magic for Everyone" allowance, 0 when off
    free_note: str
    arts: list[ThaumArtRow] = field(default_factory=list)
    sciences: list[ThaumScienceRow] = field(default_factory=list)
    rituals: list[ThaumEntryRow] = field(default_factory=list)
    formulas: list[ThaumEntryRow] = field(default_factory=list)
    owned: list[ThaumOwnedRow] = field(default_factory=list)
    total: int = 0


@dataclass
class ElementalPowerRow:
    """One elemental power as the picker renders it (Core p.296 / GoD p.56, PG p.68).
    `activation` and `description` are descriptive text (decision 0008); `requires`
    is the human-readable prerequisite line (Merits + Essence)."""
    id: str
    name: str
    price: int              # bp_cost chargen, bp_cost * 2 in play
    activation: str
    description: str
    requires: str
    owned: bool
    available: bool
    reason: str             # why it's locked, for the button tooltip


@dataclass
class ElementalPowerView:
    currency: str           # 'BP' | 'XP'
    total: int              # total cost of owned powers
    powers: list[ElementalPowerRow] = field(default_factory=list)
    owned: list[ElementalPowerRow] = field(default_factory=list)


def build_elemental_power_picker(ruleset: RuleSet, character: Character) -> ElementalPowerView:
    """The elemental-powers page as display rows. Pure: every gate comes from
    engine.validate and every price from engine.costs.

    Prices switch currency at the lock like every other picker — before it a purchase
    costs bonus points, after it experience (PG p.68, "learned in play for a number of
    experience points equal to double its bonus point value")."""
    in_play = character.chargen_locked
    currency = "XP" if in_play else "BP"
    held = set(character.elemental_powers)
    rows: list[ElementalPowerRow] = []
    for power in sorted(ruleset.elemental_powers.values(), key=lambda p: p.name):
        reason = "; ".join(validate.elemental_power_shortfalls(
            ruleset, character, power))
        names = [ruleset.merits_flaws[mid].name
                 for mid in power.required_merits
                 if (mid in ruleset.merits_flaws)]
        requires = ", ".join(names + [f"Essence {power.min_essence}"])
        price = (costs.elemental_power_xp(ruleset, character, power) if in_play
                 else power.bp_cost)
        rows.append(ElementalPowerRow(
            id=power.id, name=power.name, price=price,
            activation=power.activation, description=power.description,
            requires=requires, owned=power.id in held,
            available=not reason, reason=reason,
        ))
    owned = [r for r in rows if r.owned]
    # Summed off the rows so the total is in the SAME currency they are priced in —
    # bonus points before the lock, XP (double, PG p.68) after it. Re-summing bp_cost
    # here would label a BP total "XP" post-lock.
    total = sum(r.price for r in owned)
    return ElementalPowerView(currency=currency, total=total,
                              powers=rows, owned=owned)


def _thaum_specialty_rows(ruleset: RuleSet, character: Character, art,
                          state, price: int) -> list[ThaumSpecialtyRow]:
    """Every printed aspect of `art`, then any player-invented specialty the
    character already holds in it. Held ones are matched case-insensitively against
    the printed list so a specialty typed as "ghosts" does not show up twice."""
    held = {s.name.casefold(): s for s in state.art_specialties if s.art_id == art.id}
    rows: list[ThaumSpecialtyRow] = []
    for aspect in art.aspects:
        owned = held.get(aspect.name.casefold())
        reason = validate.thaum_aspect_locked_reason(
            ruleset, character, art.id, aspect.name)
        rows.append(ThaumSpecialtyRow(
            art_id=art.id, name=aspect.name, description=aspect.description,
            min_occult=aspect.min_occult, printed=True, owned=owned is not None,
            narrowed=bool(owned and owned.narrowed),
            available=not reason, reason=reason, price=price))
    printed = {a.name.casefold() for a in art.aspects}
    for spec in state.art_specialties:
        if spec.art_id != art.id or spec.name.casefold() in printed:
            continue
        rows.append(ThaumSpecialtyRow(
            art_id=art.id, name=spec.name, description="", min_occult=0,
            printed=False, owned=True, narrowed=spec.narrowed,
            available=True, reason="", price=price))
    return rows


def _thaum_entry_detail(obj, kind: str) -> list[tuple[str, str]]:
    """The labelled display lines of a catalogue ritual or formula. Rituals print no
    stat block at all (everything is prose), so most of their fields are empty and
    simply do not render — see docs/status/thaumaturgy.md."""
    if kind == "ritual":
        pairs = [("Roll", obj.roll), ("Cost", obj.cost), ("Materials", obj.resources)]
    else:
        materials = obj.materials_raw or (
            f"Resources {obj.materials_resources}" if obj.materials_resources else "")
        pairs = [("Roll", obj.roll),
                 ("Difficulty", str(obj.difficulty) if obj.difficulty else ""),
                 ("Materials", materials),
                 ("Effects", obj.effects), ("Addiction", obj.addiction)]
    return [(label, value) for label, value in pairs if value]


def build_thaum_picker(ruleset: RuleSet, character: Character) -> ThaumPickerView:
    """The whole thaumaturgy page as display rows. Pure: every gate comes from
    engine.validate and every price from engine.costs.

    Prices switch currency at the lock, the same way the Charm picker does — before
    it a purchase costs bonus points, after it experience.
    """
    state = validate.thaum_state(character)
    chargen = not character.chargen_locked
    in_play = character.chargen_locked
    exalt = ruleset.exalt_for(character.exalt_type)

    art_price = (costs.thaum_art_xp(ruleset, character) if in_play
                 else costs.thaum_art_bp(ruleset, character))
    spec_price = (costs.thaum_specialty_xp(ruleset, character) if in_play
                  else costs.thaum_specialty_bp(ruleset, character))
    orient_price = (costs.thaum_orientation_xp(ruleset, character) if in_play
                    else costs.thaum_orientation_bp(ruleset, character))

    arts: list[ThaumArtRow] = []
    for art in sorted(ruleset.thaum_arts.values(), key=lambda a: a.name):
        reason = validate.thaum_art_locked_reason(ruleset, character, art.id)
        arts.append(ThaumArtRow(
            id=art.id, name=art.name, min_occult=art.min_occult, roll=art.roll,
            cost_text=art.cost, description=art.description,
            owned=art.id in state.arts, available=not reason, reason=reason,
            price=art_price, allows_narrowing=art.aspect_narrowing,
            specialties=_thaum_specialty_rows(ruleset, character, art, state, spec_price),
        ))

    sciences: list[ThaumScienceRow] = []
    for science in sorted(ruleset.thaum_sciences.values(), key=lambda s: s.name):
        held = next((s for s in state.sciences if s.science_id == science.id), None)
        rating = held.rating if held is not None else 0
        reason = validate.thaum_science_raise_reason(
            ruleset, character, science.id, chargen=chargen)
        step = (costs.thaum_science_step_xp(ruleset, character, rating) if in_play
                else costs.thaum_science_step_bp(ruleset, character, rating))
        # The ladder is rendered from 1..max_rating rather than from `levels`, so
        # Alchemy's undescribed five-dot rung shows as an empty rung instead of
        # silently pulling the six-dot text down into the gap.
        sciences.append(ThaumScienceRow(
            id=science.id, name=science.name, roll=science.roll,
            cost_text=science.cost, time=science.time, duration=science.duration,
            description=science.description, rating=rating,
            max_rating=science.max_rating, next_price=0 if reason else step,
            can_raise=not reason, reason=reason,
            levels=[ThaumScienceLevelRow(
                rating=r,
                description=(science.level(r).description if science.level(r) else ""))
                for r in range(1, science.max_rating + 1)],
        ))

    def _entry_rows(catalogue: dict, held: list, kind: str) -> list[ThaumEntryRow]:
        by_key = {}
        for entry in held:
            key = (entry.ritual_id if kind == "ritual" else entry.formula_id) or entry.name
            by_key[key] = entry
        rows: list[ThaumEntryRow] = []
        for obj in sorted(catalogue.values(), key=lambda o: (o.level, o.name)):
            entry = by_key.pop(obj.id, None)
            price = (costs.thaum_ritual_xp(ruleset, character, obj.level, 1) if in_play
                     else costs.thaum_ritual_bp(ruleset, character, obj.level, 1)) \
                if kind == "ritual" else (
                    costs.thaum_formula_xp(ruleset, character, 1) if in_play
                    else costs.thaum_formula_bp(ruleset, character, 1))
            # Formulas carry no purchase gate: the source states one for Arts,
            # aspects and rituals only, and inventing a Science-rating requirement
            # here would be a rule we do not have. Do not add one.
            reason = (validate.thaum_ritual_locked_reason(
                ruleset, character, obj.level, chargen=chargen)
                if kind == "ritual" else "")
            rows.append(ThaumEntryRow(
                key=obj.id, name=obj.name, kind=kind, level=obj.level, custom=False,
                owned=entry is not None, available=not reason, reason=reason,
                price=price, orientation_price=orient_price,
                orientations=[o.value for o in entry.orientations] if entry else [],
                detail=_thaum_entry_detail(obj, kind),
                # A formula has no prose block — its content is the labelled
                # Effects/Addiction lines, which are already in `detail`.
                description=obj.description if kind == "ritual" else "",
            ))
        # Whatever is left in by_key is custom — authored by the player, or a stale
        # id no longer in the catalogue. Either way it is shown, never dropped.
        for key, entry in by_key.items():
            rows.append(ThaumEntryRow(
                key=key, name=entry.name or key, kind=kind, level=entry.level,
                custom=True, owned=True, available=True, reason="",
                price=0, orientation_price=orient_price,
                orientations=[o.value for o in entry.orientations],
                description=entry.description,
            ))
        return rows

    purchases = validate.thaum_purchases(ruleset, character)
    free = validate.magic_for_everyone_grant(ruleset, character)
    # Priced through the engine's own function so the free-grant assignment shown
    # here is the same one the bonus-point breakdown charges for.
    prices = validate.thaum_purchase_bp_costs(ruleset, character, purchases,
                                              free_picks=free)
    owned = [ThaumOwnedRow(kind=p.kind, key=p.key, label=p.label, cost=c,
                           free=c == 0 and validate.magic_for_everyone_eligible(ruleset, p))
             for p, c in zip(purchases, prices)]

    free_note = ""
    if free:
        free_note = (f"Magic for Everyone: {free} free purchase(s) from Occult "
                     f"{validate.ability_rating(character, AbilityName.OCCULT)} — "
                     "rituals, formulas or printed aspects up to level 3. Applied to "
                     "the dearest eligible purchases; Arts and Sciences are never free.")

    return ThaumPickerView(
        currency="XP" if in_play else "BP",
        usable=exalt.thaumaturgy_usable,
        usable_note=("" if exalt.thaumaturgy_usable else
                     f"{character.exalt_type} may hold thaumaturgy but can never use "
                     "it (p.114) — the knowledge is kept, and can still be taught."),
        occult=validate.ability_rating(character, AbilityName.OCCULT),
        free_picks=free, free_note=free_note,
        arts=arts, sciences=sciences,
        rituals=_entry_rows(ruleset.thaum_rituals, state.rituals, "ritual"),
        formulas=_entry_rows(ruleset.thaum_formulas, state.formulas, "formula"),
        owned=owned, total=sum(prices),
    )


# --------------------------------------------------------------------------- #
# Storyteller options (Character.house_rules)
#
# The model marks TABLE-WIDE vs PER-CHARACTER in comments only — a deliberate
# choice (human, 2026-07-29) to keep HouseRules one flat model. The tab still has
# to *show* that split, so the machine-readable version lives here, in the
# presenter, rather than being pushed back into the model. A future party-wide
# "apply to all" control should read `scope` from here too.
# --------------------------------------------------------------------------- #

@dataclass
class HouseRuleRow:
    field: str
    label: str
    scope: str              # 'table' | 'character'
    citation: str
    description: str
    # bool for a plain toggle; a str for a multiple-choice rule, whose `options` maps
    # stored value -> label. `options` empty means it renders as a checkbox. The
    # Inheritance-rating row is an int (1-5) on the model, shown in the select as its
    # option key (a str), with "per-character" standing in for None.
    value: bool | str | int | None
    options: dict[str, str] = dc_field(default_factory=dict)
    note: str = ""          # why it currently does nothing, when it doesn't


# (field, label, scope, citation, description) — ordered as the tab renders them.
_HOUSE_RULES = [
    ("magic_for_everyone", "Magic for Everyone", "table", "Player's Guide p.115",
     "Every starting character gets one free ritual, formula or printed aspect per "
     "two dots of Occult (level 3 or lower). Arts and Sciences are never free."),
    ("restrict_chargen_ritual_level", "Cap starting rituals at level 3", "table",
     "Player's Guide p.113",
     "Starting characters may not buy rituals above level 3. Independent of the "
     "Science cap — the book offers them as 'and/or'."),
    ("restrict_chargen_science_rating", "Cap starting Sciences at 3 dots", "table",
     "Player's Guide p.113",
     "Starting characters may not buy a Science above three dots. Experience is "
     "unaffected: a Science raised past 3 in play stays legal."),
    ("st_foreign_charms", "May start play knowing foreign Charms", "character",
     "Exalted p.127",
     "Storyteller permission for THIS character to begin play already knowing "
     "another Exalt type's Charms. After chargen the rule asks only for a willing "
     "tutor, so this stops mattering once the sheet is locked."),
    ("mortal_favored_ability", "Heroic mortal may pick a Favored Ability", "character",
     "Exalted p.103",
     "Grants one Favored Ability, discount included. The price is a ceiling: no other "
     "Ability may be rated above it. Only affects splats with no castes."),
    ("st_celestial_manse_over_three", "Sidereal may hold Celestial Manse above 3 dots",
     "character", "Sidereals p.106",
     "Storyteller permission for THIS Sidereal to own a Celestial Manse above three "
     "dots — 'Characters cannot buy above Celestial Manse ••• without special "
     "Storyteller permission'. The ceiling binds on both sides of the lock, and this "
     "lifts it for one character only."),
    ("st_mortal_artifact_manse", "Mortal may hold Artifact and Manse", "character",
     "Exalted p.103",
     "Storyteller permission for THIS mortal to take the Artifact or Manse Background "
     "— 'may not purchase the Artifacts or Manse Backgrounds without Storyteller "
     "permission; if a mortal has control over one of these, it's a plot device'. "
     "Chargen only: there is no post-lock purchase to bar."),
    ("terrestrial_essence_transcendence", "Terrestrial may pass Essence 7", "character",
     "Player's Guide p.258",
     "Terrestrial Exalts are held at Essence 7 without 'outside energies' — dietary "
     "and meditational regimens, powerful Hearthstones and the like. None of that is "
     "on the sheet, so this is the Storyteller asserting it happened."),
    ("all_backgrounds_available", "Open every Background to every splat", "table",
     "The Outcaste p.66",
     "By default a character is offered the Backgrounds her own book prints — "
     "Arsenal belongs to Lookshy, Sifu to the Sidereals. The books ask for this "
     "switch in so many words: Storytellers 'may wish to introduce them in other "
     "games where they are appropriate'. Does not lift a splat's own prohibitions, "
     "such as the Great Geas barring the Mountain Folk a Cult."),
    ("mf_change_method", "Merits & Flaws after character creation", "table",
     "Player's Guide p.17",
     "How a Merit or Flaw gained or lost in play is accounted for. The book offers "
     "three methods and lets the Storyteller pick, or combine them per situation."),
    ("godblooded_inheritance_rating", "God-Blooded Inheritance rating", "table",
     "Player's Guide p.61",
     "How many dots of the Inheritance Background the table's God-Blooded hold. The "
     "book leaves the rating to the Storyteller — 'assigns a consistent rating to set "
     "the series' power level' — and the rating sets each God-Blooded's bonus-point "
     "pool and Flaw capacity. Per character: each uses their own Inheritance dots."),
]

# Multiple-choice house rules: field -> {stored value: label}. Everything absent here
# is a plain boolean toggle.
_HOUSE_RULE_OPTIONS: dict[str, dict[str, str]] = {
    "mf_change_method": {
        "experience": "Experience — pay/receive twice the point value (default)",
        "backgrounds": "Like Backgrounds — changes cost and reward nothing",
        "swap": "Equal-value swap — a lost Trait is replaced, a gained one erodes another",
    },
    # Keys are the select's option values; "per-character" maps to None on the model
    # (each God-Blooded uses their own Inheritance dots). The p.61 dot names are the
    # labels — Thin blood through Divine.
    "godblooded_inheritance_rating": {
        "per-character": "Per character — each uses their own Inheritance dots",
        "1": "1 • Thin blood",
        "2": "2 •• Good blood",
        "3": "3 ••• Notable ancestry",
        "4": "4 •••• Impeccable scion",
        "5": "5 ••••• Divine",
    },
}


def build_house_rules(ruleset: RuleSet, character: Character) -> list[HouseRuleRow]:
    """The Storyteller-options rows for this character, with any that cannot bite
    annotated rather than hidden — an ST looking for a toggle should find it and be
    told why it is inert, not wonder where it went."""
    rules = character.house_rules or HouseRules()
    rows: list[HouseRuleRow] = []
    for fld, label, scope, citation, description in _HOUSE_RULES:
        note = ""
        if fld == "st_foreign_charms":
            if validate.foreign_charms_caste(ruleset, character) is None:
                note = (f"No effect: only a caste with the generalist privilege "
                        f"(Eclipse, Moonshadow) can learn foreign Charms, and "
                        f"{character.caste or 'this caste'} is not one.")
            elif character.chargen_locked:
                note = ("No longer applies: chargen is locked, so a willing tutor "
                        "is the only remaining gate.")
        elif fld == "mortal_favored_ability":
            b = ruleset.budgets_for(character.exalt_type, character.origin,
                                    character.upbringing)
            if not b.optional_favored_ability:
                note = ("No effect: core p.103 offers this to HEROIC mortals only, "
                        f"and this character is {character.exalt_type}"
                        f"{'/' + character.origin if character.origin else ''}.")
            elif getattr(rules, fld):
                note = "Granting 1 Favored Ability, which must stay the highest-rated."
        elif fld == "st_celestial_manse_over_three":
            if character.exalt_type != "Sidereal":
                note = (f"No effect: the Celestial Manse ≤3 ceiling is a Sidereal rule "
                        f"(Sidereals p.106), and this character is {character.exalt_type}.")
            elif getattr(rules, fld):
                note = "Permission granted: this Sidereal may hold Celestial Manse above 3 dots."
        elif fld == "st_mortal_artifact_manse":
            if character.exalt_type != "Mortal":
                note = (f"No effect: core p.103 bars MORTALS from Artifact and Manse, "
                        f"and this character is {character.exalt_type}.")
            elif getattr(rules, fld):
                note = "Permission granted: this mortal may take Artifact and Manse Backgrounds."
        elif fld == "terrestrial_essence_transcendence":
            if ruleset.exalt_for(character.exalt_type).tier != "Terrestrial":
                note = (f"No effect: the Essence 7 ceiling is a Terrestrial rule, and "
                        f"{ruleset.exalt_for(character.exalt_type).label} are not "
                        f"Terrestrial.")
            elif character.essence_rating < 7:
                note = ("Nothing to lift yet: Essence is below the Terrestrial "
                        "ceiling of 7. The toggle matters once it reaches 7.")
        elif fld == "all_backgrounds_available":
            # Say what the toggle is actually worth to THIS character, in names.
            # A count is the honest measure: the ST wants to know whether flipping
            # it changes anything before they flip it.
            own = len(ruleset.backgrounds_for(character.exalt_type, character.origin))
            everything = len(ruleset.backgrounds_for(
                character.exalt_type, character.origin, all_available=True))
            if getattr(rules, fld):
                note = (f"Offering all {everything} Backgrounds, up from the "
                        f"{own} this character's own books print.")
            else:
                note = (f"Offering the {own} Backgrounds this character's own books "
                        f"print; {everything - own} more exist in other splats' books.")
        elif fld == "magic_for_everyone" and getattr(rules, fld):
            grant = validate.magic_for_everyone_grant(ruleset, character)
            note = (f"Currently granting {grant} free purchase(s)." if grant else
                    "Granting nothing yet: the allowance is Occult ÷ 2, rounded down.")
        elif fld == "godblooded_inheritance_rating":
            b = ruleset.budgets_for(character.exalt_type, character.origin,
                                    character.upbringing)
            if not b.inheritance_bonus_points:
                note = (f"No effect: Inheritance bonus points are a God-Blooded rule, "
                        f"and this character is {character.exalt_type}.")
            elif getattr(rules, fld) is not None:
                rating = getattr(rules, fld)
                # The ST's pick is how many Inheritance DOTS are FREE, not the rating
                # itself (human 2026-08-02) — the bonus points always follow the sheet.
                note = (f"Setting the first {rating} dot(s) of Inheritance free for "
                        f"every God-Blooded: no pool dots, no above-cap bonus points. "
                        f"The bonus points and Flaw capacity still follow each "
                        f"character's own sheet rating.")
        value = getattr(rules, fld)
        if fld == "godblooded_inheritance_rating":
            # The select's option keys are the strings "1".."5" plus a sentinel for
            # None, so an int rating must become its key (and None its sentinel) or
            # the select's build-time value check fails.
            value = "per-character" if value is None else str(value)
        rows.append(HouseRuleRow(field=fld, label=label, scope=scope,
                                 citation=citation, description=description,
                                 value=value,
                                 options=dict(_HOUSE_RULE_OPTIONS.get(fld, {})),
                                 note=note))
    return rows


@dataclass
class SheetView:
    # identity / concept
    name: str
    player: str
    caste: str
    caste_noun: str          # what this splat calls the caste slot ("Caste"/"Aspect")
    exalt_type: str
    concept: str
    nature: str
    anima: str
    # free-fill biography (human 2026-08-21) — (label, value) pairs, empty ones dropped
    biography: list[tuple[str, str]]
    # Lunar Form Library (narrative only — see models.character.AnimalForm)
    totem: str
    animal_forms: list[tuple[str, str]]               # (animal, notes)
    essence_rating: int
    # traits
    attributes: list[tuple[str, list[TraitRow]]]      # (category, rows), ordered
    ability_groups: list[tuple[str, list[TraitRow]]]  # (ability-caste, rows), Dawn..Eclipse
    virtues: list[TraitRow]
    # derived
    willpower: int
    essence_personal: int
    essence_peripheral: int
    # Personal is 0 by RULE, not by arithmetic (Beacon of Power) — read it through
    # `essence_pool_label`, which is what both the sheet and the editor display.
    essence_single_pool: bool
    # Motes drawable without a Willpower roll (Essence Awareness), or None when the
    # whole pool is. Also read through `essence_pool_label`.
    essence_free: Optional[int]
    soak: derive.SoakView
    health: list[str]                                 # formatted level labels
    # advantages / gear
    backgrounds: list[tuple[str, int, str]]           # (name, rating, note)
    # Individually rated artifacts (E:Ab p.131), as (name, rating, note, damaged) —
    # every one the character owns, folded from the standalone list AND from artifact
    # weapons and armour, so the sheet's combined total matches the one the budget
    # check reads. `damaged` is points of Damaged Artifact against that item, 0 for
    # sound ones. Empty for the many characters who own none, which drops the panel.
    artifacts: list[tuple[str, int, str, int]]
    # (name, printed cost with sign, detail, "merit"|"flaw"|"either", tooltip) — the
    # sign carries the direction so a Flaw never reads as something the character paid
    # for. The tooltip is the printed cost line plus the rules text: the sheet has no
    # room to show it inline, but a Merit whose text you cannot read is just a word.
    merits_flaws: list[tuple[str, str, str, str, str]]
    # Astrological Colleges (Sidereal, p.98). (name, rating, house_label, own_house)
    # — `own_house` marks a College of the character's own Maiden, the ones the
    # chargen floor counts. Empty for every splat that ships no colleges.
    colleges: list[tuple[str, int, str, bool]]
    # Thaumaturgy (Player's Guide CH3) as (section, item labels) — Arts, Specialties,
    # Sciences, Rituals, Formulas. Cross-splat, so this may be non-empty on any
    # character; empty (and the panel absent) for anyone who bought none.
    thaumaturgy: list[tuple[str, list[str]]]
    thaumaturgy_note: str                             # "" unless the splat may not use it
    specialties: list[tuple[str, str, int]]           # (ability label, name, rating)
    charms: list[CharmRow]
    # The same charm holdings grouped by subsystem — (label, rows) for "Charms",
    # "Arcanoi" (Ghost), "Gifts" (Lunar), "Ox-Body Technique" — so the sheet can head
    # each panel the way the picker's tabs do instead of one undifferentiated list.
    # `charms` above stays the flat concatenation (the GM party view and tests read it).
    charm_sections: list[tuple[str, list[CharmRow]]]
    # Dragon-King Paths of Prehuman Mastery — one row per owned Path, rated 1-6, with
    # the powers its dots grant. Empty for every splat that ships no paths.
    paths: list[PathRow]
    # Combos the character holds — (name, resolved member names, cost = member count).
    # Empty for characters with none; the sheet renders the panel only when non-empty.
    combos: list[tuple[str, list[str], int]]
    spells: list[SpellRow]
    weapons: list[Weapon]
    armor: list[Armor]
    # status / misc
    virtue_flaw: Optional[str]
    experience: int
    issues: list[validate.Issue]
    chargen_locked: bool
    # The XP ledger, as HISTORY. `app.render_sheet` takes only this dataclass — no
    # ruleset, no character, no callbacks — and the GM party screen and the render
    # tests depend on that purity, so the sheet's copy of the ledger is a printout and
    # the live one (Adjust XP, Undo) stays on the Edit tab where the buying happens.
    # Empty pre-lock: there is nothing spent yet and a chargen sheet should not imply
    # otherwise. See decision 0013.
    xp_earned: int = 0
    xp_spent: int = 0
    xp_available: int = 0
    xp_log: list[XpLogRow] = field(default_factory=list)
    # --- Ghosts only (E:Ab p.126-127) --------------------------------------- #
    # Empty for every other splat, which is what keeps the panels off their sheets.
    fetters: list[tuple[str, int, str]] = field(default_factory=list)   # name, rating, note
    fetter_cap: int = 0                               # Willpower + Essence (p.127)
    # (virtue, name, rating) — each Passion belongs to the Virtue whose pool it draws on.
    passions: list[tuple[str, str, int]] = field(default_factory=list)
    # (virtue, distributed, pool) per Virtue. DERIVED from the CURRENT Virtues on both
    # sides of the lock, never snapshotted: p.283 says Passions rise whenever the
    # Virtues do, so a sheet that froze this would go stale the first time a locked
    # ghost bought a Virtue.
    passion_pools: list[tuple[str, int, int]] = field(default_factory=list)
    # Dragon-King breed innate weapons (PG pp.167-174) as (name, speed, accuracy,
    # damage, damage_type, defense) — the printed Spd/Acc/Dmg/Def table. Display-only,
    # decision 0008 keeps attack derivation out. Empty for every splat whose caste has
    # no `breed_traits`, which drops the section from their sheet.
    breed_weapons: list[tuple[str, int, int, int, str, int]] = field(default_factory=list)
    # Elemental Powers (PG p.68) — the Charm-like learnable powers of an
    # Elemental-origin God-Blooded, as CharmRow-shaped rows (category = the power's
    # class). They also get their own headed section inside `charm_sections`, so the
    # Charms & Sorcery band heads them like Arcanoi/Gifts. Empty for every splat that
    # ships no powers, which drops the section from their sheet. Kept off the flat
    # `charms` concatenation — tests and the GM party view read that and pin its count.
    elemental_powers: list[CharmRow] = field(default_factory=list)

    def essence_pool_label(self) -> str:
        """The Essence pools as one line. A merged pool is named as one rather than
        shown as "Personal 0", which reads as a character with no Essence at all, and
        a partly-unlocked one says how much of it is reachable without a Willpower
        roll — a mortal with Essence Awareness owns the whole pool but may only draw
        on a third of it freely, and a bare total would overstate what he can spend."""
        if self.essence_single_pool:
            base = f"Single pool {self.essence_peripheral} (all Peripheral)"
        else:
            base = (f"Personal {self.essence_personal}"
                    f"  ·  Peripheral {self.essence_peripheral}")
        if self.essence_free is None:
            return base
        return f"{base}  ·  {self.essence_free} without a Willpower roll"


def _label(value: str) -> str:
    """'martial_arts' -> 'Martial Arts'."""
    return value.replace("_", " ").title()


# The DEFAULT Ability grouping, for splats whose Abilities are not divided along
# caste lines: War / Life / Wisdom, as printed on the canonical 1e Lunar character
# sheet (images/Lunar/character sheet.png). This is a sheet-layout convention, not
# a rule — nothing mechanical keys off which of the three an Ability sits in, so it
# lives here in the presenter rather than in data/. Splats that DO have ability
# castes (Solar, Dragon-Blooded, Abyssal) override it with their caste grouping.
DEFAULT_ABILITY_GROUPS: tuple[tuple[str, tuple[AbilityName, ...]], ...] = (
    ("War", (AbilityName.ARCHERY, AbilityName.ATHLETICS, AbilityName.AWARENESS,
             AbilityName.BRAWL, AbilityName.DODGE, AbilityName.ENDURANCE,
             AbilityName.MARTIAL_ARTS, AbilityName.MELEE, AbilityName.RESISTANCE,
             AbilityName.THROWN)),
    ("Life", (AbilityName.CRAFT, AbilityName.LARCENY, AbilityName.LINGUISTICS,
              AbilityName.PERFORMANCE, AbilityName.PRESENCE, AbilityName.RIDE,
              AbilityName.SAIL, AbilityName.SOCIALIZE, AbilityName.STEALTH,
              AbilityName.SURVIVAL)),
    ("Wisdom", (AbilityName.BUREAUCRACY, AbilityName.INVESTIGATION, AbilityName.LORE,
                AbilityName.MEDICINE, AbilityName.OCCULT)),
)


def repeatable_cap_trait(charm) -> tuple[str, str]:
    """`(trait label, unit noun)` naming what limits a repeatable Charm's purchases,
    e.g. ("Endurance", "dot") or ("Essence", "point"). ("", "") if not repeatable.

    Never hardcode the trait in UI copy: it varies by splat even for the SAME Charm.
    Ox-Body caps on Endurance for Solar/Dragon-Blooded/Abyssal but on **Stamina** for
    Lunar (The Lunars p.132, "once per dot of human-form Stamina"), and Deadly
    Beastman Transformation caps on Essence (p.124), which is neither an Ability nor
    an Attribute. This mirrors engine.validate._repeatable_purchase_cap, which
    resolves the same field to the actual number."""
    name = getattr(charm, "repeatable_cap_ability", "") if charm else ""
    if not name:
        return ("", "")
    # Essence is rated in points; Abilities and Attributes in dots.
    return ("Essence", "point") if name == "essence" else (_label(name), "dot")


def merit_rows(ruleset: RuleSet, character: Character
               ) -> list[tuple[str, str, str, str, str]]:
    """The Merits & Flaws block for a sheet. An unresolvable id is SHOWN with a warning
    marker rather than dropped — the same graceful treatment unknown Charm ids get,
    since a save opened without its data set should say so, not quietly shrink."""
    rows: list[tuple[str, str, str, str, str]] = []
    for mp in character.merits_flaws:
        # A player-authored "Custom" row (2026-08-10): display-only, no mechanical
        # effect — render it by its name rather than as a missing-data warning. The
        # discriminator is the EMPTY merit_id, not custom_name's truthiness: the name
        # is player-editable and may be blanked, but the row must still read as custom
        # (see the chargen-row comment in ui/advantages.py).
        if not mp.merit_id:
            rows.append((mp.custom_name or "Custom", "", mp.detail, "merit",
                         "Custom — no printed effect."))
            continue
        definition = ruleset.merits_flaws.get(mp.merit_id)
        if definition is None:
            rows.append((f"⚠ {mp.merit_id}", "?", mp.detail, "merit",
                         "Not in the rule set — the data that defined it is missing."))
            continue
        points = (definition.cost_options.get(mp.tier, 0)
                  if definition.cost_options else definition.cost)
        sign = "−" if definition.kind == "merit" else "+"
        name = definition.name + (f" ({mp.tier})" if mp.tier else "")
        detail = " · ".join(x for x in (mp.arena, mp.detail) if x)
        tooltip = " ".join(x for x in (definition.cost_note, definition.description) if x)
        rows.append((name, f"{sign}{points}", detail, definition.kind, tooltip))
    return rows


def ability_group_defs(ruleset: RuleSet, exalt_type: str) -> list[tuple[str, list[AbilityName]]]:
    """How to lay the Ability roster out in columns, for the sheet and the editor.

    Ability-caste splats (Solar, Dragon-Blooded, Abyssal) group by caste, which is
    how their character sheets print. Lunars have no Caste Abilities at all and
    "Abilities are not divided along caste lines" (The Lunars p.90), so their
    castes carry `caste_attributes` instead and grouping by caste yields NOTHING.
    Those splats fall back to `DEFAULT_ABILITY_GROUPS` (War / Life / Wisdom).

    A splat whose castes list only PART of the roster falls back the same way. The
    Dragon-Kings' four breeds each name three BREED abilities (12 total), but a DK
    buys 25 dots across all 25 abilities (PG CH4) — grouping by breed would drop the
    other 13 from the sheet and editor entirely. Solar/DB/Abyssal castes partition
    the whole roster (5 × 5 = 25), so they keep their caste columns; the breed
    abilities are still marked ● by the caste markers, exactly as a caste ability is."""
    groups = [(cd.label, list(cd.caste_abilities)) for cd in ruleset.castes.values()
              if cd.exalt_type == exalt_type and cd.caste_abilities]
    if groups and {a for _, abilities in groups for a in abilities} >= set(AbilityName):
        return groups
    return [(label, list(abilities)) for label, abilities in DEFAULT_ABILITY_GROUPS]


@dataclass(frozen=True)
class CampChoiceOption:
    """One option within a camp's grant choice.

    `available` is False when the option cannot actually be taken — which for this book
    means a martial-arts style the page offers but whose Charms `data/` cannot yet
    supply `pick` of. All four of the Tabernacle's styles are authored as of 2026-07-25,
    so nothing trips this today; it stays because the next book to offer a style before
    its Charms exist will. Such an option is still LISTED, because the rulebook offers
    it and hiding it would misrepresent the page — but the UI must refuse to select it
    rather than assign nothing and silently blank the control."""
    key: str
    label: str
    charm_ids: list[str]
    available: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CampCharmOption:
    """One Charm selectable inside an already-chosen category option.

    The Tabernacle's package is "two Charms from ONE of four martial arts" (p.90) —
    choosing the STYLE is only half the choice, and the player picks WHICH Charms.
    `meets_minimums` is False when the character does not yet meet the Charm's own trait
    minimums; the page requires those ("must meet the minimum requirements", p.90) and
    `validate.granted_charm_issues` raises `granted-charm-minimum` for a violation, so
    the option is still offered but flagged. Charm PREREQUISITES are deliberately not
    considered — the package hands out Charms whose tree the character has not climbed."""
    charm_id: str
    label: str
    meets_minimums: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CampChoiceView:
    """One player choice inside a training camp's free-Charm package, flattened for the
    UI. For a fixed-set choice each option is a whole printed pair; for a category choice
    each option is one style and `pick` says how many Charms to take from it.

    A category choice is TWO controls, not one: `options`/`chosen_key` pick the style,
    then `charm_options`/`chosen_charm_ids` pick which `pick` of that style's Charms are
    granted. `charm_options` is empty until a style is chosen, and always empty for a
    fixed-set choice (there the printed pair IS the grant — no sub-choice).

    A flat-pool choice (GrantedCharmChoice.pool_categories/pool_charms) is the mirror
    image: `options` is EMPTY and `charm_options` holds the whole pool from the start,
    so the editor renders one control instead of two."""
    label: str
    pick: int
    is_category_choice: bool
    options: list[CampChoiceOption]
    chosen_key: str = ""
    charm_options: list[CampCharmOption] = field(default_factory=list)
    chosen_charm_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CampView:
    """Everything the editor needs to render the camp/Calling panel. Empty/None for
    every character whose origin has no camps, which is how the panel stays hidden."""
    camp_options: list[tuple[str, str]]          # (id, label)
    camp_id: str
    camp_label: str
    camp_description: str
    minimums: list[str]                          # e.g. "Melee 2", "Archery or Brawl 1"
    granted_fixed: list[tuple[str, str]]         # (charm id, name) — always received
    choices: list[CampChoiceView]
    calling_options: list[tuple[str, str]]       # (id, label) for the CHOSEN camp
    calling_id: str
    calling_label: str
    calling_description: str
    calling_abilities: list[str]                 # display labels, ★-marked by the UI
    calling_charms: list[tuple[str, str]]        # (charm id, name)


def requires_camp(ruleset: RuleSet, character: Character) -> bool:
    """Whether this character's origin uses training camps (Cult of the Illuminated).
    Budget-driven, so no splat or origin is named in the UI."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return b.requires_camp or b.requires_calling


def build_camp_view(ruleset: RuleSet, character: Character) -> Optional[CampView]:
    """The camp/Calling panel, or None when the origin has no camps."""
    if not requires_camp(ruleset, character):
        return None

    camps = ruleset.camps_for(character.exalt_type, character.origin)
    camp = validate.camp_for(ruleset, character)
    calling = validate.calling_for(ruleset, character)
    # `camp_for` resolves the stored id against the WHOLE camp table, so a camp
    # belonging to another splat's Cult resolves fine and would be handed to the
    # select as a value that is not one of its options — which `ui.select` raises on
    # at BUILD time, taking the rest of the tab down with it. Clamp to something
    # offered; the engine still reports `camp-wrong-origin` in the issue panel, which
    # is where a mismatch belongs. Unreachable until Cult Dragon-Blooded shipped
    # (2026-08-12) — with one splat owning every camp, the value was always an option.
    # Only a MISMATCH is clamped. A character with no camp chosen yet keeps the empty
    # select it has always had — filling it in here would show a camp the character
    # does not actually hold.
    if camps and character.camp and camp not in camps:
        camp = camps[0]
    if calling is not None and camp is not None and \
            calling not in ruleset.callings_for(camp.id):
        calling = None

    minimums: list[str] = []
    granted_fixed: list[tuple[str, str]] = []
    choices: list[CampChoiceView] = []
    if camp is not None:
        for req in camp.required_min_abilities:
            names = " or ".join(_label(a.value) for a in req.abilities)
            minimums.append(f"{names} {req.rating}")
        granted_fixed = [(cid, _charm_name(ruleset, cid)) for cid in camp.granted_charms]

        held = set(character.granted_charms)
        for choice in camp.granted_charm_choices:
            options: list[CampChoiceOption] = []
            chosen = ""
            if choice.fixed_sets:
                for group in choice.fixed_sets:
                    key = "|".join(group)
                    label = " + ".join(_charm_name(ruleset, c) for c in group)
                    missing = [c for c in group if c not in ruleset.charms]
                    options.append(CampChoiceOption(
                        key=key, label=label, charm_ids=list(group),
                        available=not missing,
                        reason="" if not missing else "Charm not in data"))
                    if all(c in held for c in group):
                        chosen = key
            else:
                for cat in choice.from_categories:
                    ids = [c.id for c in ruleset.charms.values() if c.category == cat]
                    ok = len(ids) >= choice.pick
                    if ok:
                        reason = ""
                    elif not ids:
                        reason = "no Charms authored yet"
                    else:
                        reason = f"only {len(ids)} Charm(s) authored, needs {choice.pick}"
                    options.append(CampChoiceOption(
                        key=cat, label=_style_label(cat, ruleset), charm_ids=ids,
                        available=ok, reason=reason))
                    if ids and any(c in held for c in ids):
                        chosen = cat
            # A flat-pool choice reaches here with `options` still empty, and that is
            # what tells the editor to render only the Charm multi-select: the shape
            # has no style step, and a select over nothing would be an empty dropdown
            # the player can neither use nor dismiss.
            #
            # Choosing the style is only half a category choice — the page grants
            # "two Charms from ONE of four martial arts" (p.90), so the player also
            # picks WHICH. Offer the chosen style's whole roster, flagging any Charm
            # whose own trait minimums the character does not meet (still selectable:
            # validate.granted_charm_issues reports it as granted-charm-minimum, and
            # raising the trait later clears it).
            charm_options: list[CampCharmOption] = []
            chosen_charm_ids: list[str] = []
            pool: list[str] = []
            if chosen and choice.from_categories:
                pool = next((o.charm_ids for o in options if o.key == chosen), [])
            elif not choice.fixed_sets and not choice.from_categories:
                # The flat pool is offered whole and immediately — there is no style
                # to choose first, so this control is the entire choice.
                pool = choice.pool_charm_ids(ruleset.charms)
            if pool:
                for cid in sorted(pool, key=lambda i: _charm_name(ruleset, i)):
                    charm = ruleset.charms.get(cid)
                    short = validate.charm_ability_shortfalls(character, charm) if charm else []
                    reason = ("needs " + ", ".join(f"{_label(t)} {req}"
                                                   for t, req, _ in short)
                              if short else "")
                    charm_options.append(CampCharmOption(
                        charm_id=cid, label=_charm_name(ruleset, cid),
                        meets_minimums=not short, reason=reason))
                chosen_charm_ids = [c for c in pool if c in held]

            choices.append(CampChoiceView(
                label=choice.label, pick=choice.pick,
                is_category_choice=bool(choice.from_categories),
                options=options, chosen_key=chosen,
                charm_options=charm_options, chosen_charm_ids=chosen_charm_ids))

    return CampView(
        camp_options=[(c.id, c.label) for c in camps],
        camp_id=camp.id if camp else "",
        camp_label=camp.label if camp else "",
        camp_description=camp.description if camp else "",
        minimums=minimums,
        granted_fixed=granted_fixed,
        choices=choices,
        calling_options=[(c.id, c.label) for c in ruleset.callings_for(camp.id)] if camp else [],
        calling_id=calling.id if calling else "",
        calling_label=calling.label if calling else "",
        calling_description=calling.description if calling else "",
        calling_abilities=[_label(a.value) for a in calling.abilities] if calling else [],
        calling_charms=[(cid, _charm_name(ruleset, cid)) for cid in calling.charms]
                       if calling else [],
    )


def _charm_name(ruleset: RuleSet, charm_id: str) -> str:
    charm = ruleset.charms.get(charm_id)
    return charm.name if charm is not None else charm_id


def _style_label(category: str, ruleset=None) -> str:
    """"martial_arts:ebon-shadow" -> "Ebon Shadow Style".

    The AUTHORED name wins when the style catalogue has one, because the slug is
    not always the printed name: `martial_arts:praying-mantis` is printed "Mantis
    Style" (Caste Book: Eclipse p.73). Without this the same style is called two
    things on two surfaces. The slug remains the fallback — homebrew styles are
    minted at runtime and have no catalogue entry (decision 0012).
    """
    if ruleset is not None:
        for style in getattr(ruleset, "martial_arts_styles", {}).values():
            if style.category == category:
                return style.name
    slug = category.split(":", 1)[-1]
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-")) + " Style"


@dataclass
class StyleView:
    """The style-level text above a martial-arts Charm tree — the preamble the
    `martial_arts:<slug>` categories always implied (docs/plans/martial-arts-
    styles.md). Presentation only: `tier` is the printed `Type:` word and NOTHING
    reads it to decide access, which is still the Charms' business."""
    name: str
    tier: str                 # printed "Type:" — DISPLAY ONLY
    preamble: str
    mechanics: list[str]
    source_label: str         # "Player's Guide p.239", "" when unattributed

    @property
    def heading(self) -> str:
        """The panel's title. `tier` is optional — most books print no `Type:` line
        — so interpolating it unconditionally yields "Air Dragon Style — " with a
        dangling separator.

        Derived HERE rather than inline in `ui/picker.py` for two reasons: CLAUDE.md
        asks for derived state in the presenter so the Qt port carries it over, and
        it gives the tier-less case a home that can be unit-tested with a synthetic
        StyleView. That second reason is load-bearing — every style in the catalogue
        now has a tier, so there is no real subject left to point a render test at,
        and a control with no subject silently stops testing anything.
        """
        return f"{self.name} — {self.tier}" if self.tier else self.name


def style_for_category(ruleset: RuleSet, category: str) -> Optional[StyleView]:
    """The authored style for a `martial_arts:*` category, or None.

    None is an ordinary answer, not an error: a category with no authored style
    (`martial_arts:enlightenment`, which is the Dragon-Path initiation tree rather
    than a style) returns None, and a homebrew style has no page to have a preamble
    from. A caller must render nothing rather than an empty panel.

    ⚠ A returned StyleView can still have an EMPTY `tier` or an empty `preamble` —
    only the Player's Guide prints both. Callers must treat each field as optional
    rather than assuming a non-None style is a fully populated one.
    """
    if not category or not category.startswith("martial_arts:"):
        return None
    for style in ruleset.martial_arts_styles.values():
        if style.category != category:
            continue
        src = style.source
        label = f"{src.book} p.{src.page}" if src and src.book and src.page else ""
        return StyleView(name=style.name, tier=style.tier, preamble=style.preamble,
                         mechanics=list(style.mechanics), source_label=label)
    return None


def calling_ability_marks(ruleset: RuleSet, character: Character) -> set:
    """The Ability names the Calling discounts, for the editor's ✦ marks. A separate
    set from the Caste/Favoured one on purpose: an Ability can be both, and the two
    discounts stack (p.90)."""
    return validate.calling_abilities(ruleset, character)


def is_calling_charm(ruleset: RuleSet, character: Character, charm_id: str) -> bool:
    """Whether the picker should mark this Charm as a discounted Calling Charm."""
    return charm_id in validate.calling_charm_ids(ruleset, character)


def granted_charm_rows(ruleset: RuleSet, character: Character) -> list[CharmRow]:
    """The camp's free Charms, as sheet rows. Kept separate from the picked Charms so
    the sheet can label them "granted" — they cost no BP and no XP."""
    rows: list[CharmRow] = []
    for cid in character.granted_charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        rows.append(CharmRow(
            name=charm.name, category=_label(charm.category.split(":")[-1]),
            cost=_cost_str(charm.cost), duration=charm.duration,
            description=_charm_description(charm)))
    return rows


def uses_caste_favored_attributes(ruleset: RuleSet, character: Character) -> bool:
    """Whether this splat allocates Attributes to Caste/Favored/remaining SETS
    (Alchemical, p.60) rather than prioritising Physical/Social/Mental categories.
    The editor uses it to switch the Attribute panel between the two layouts."""
    return ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing).attribute_mode == "caste_favored"


def attribute_budget_summary(ruleset: RuleSet, character: Character) -> Optional[str]:
    """A one-line set-based Attribute budget readout for a caste_favored-mode splat
    ('Caste 9 (min 2 each) · Favored 6 · Other 4'), or None for category-mode splats
    (whose panel header shows the prioritised pools instead)."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    if b.attribute_mode != "caste_favored":
        return None
    caste, favored, other = b.attribute_pools
    return (f"Caste {caste} (min {b.attribute_caste_min} each) · "
            f"Favored {favored} · Other {other}")


@dataclass
class SlotBudget:
    """Alchemical Charm-Slot occupancy, for the picker/sheet readout. `installed`
    Charms occupy Slots (each Ox-Body purchase counts; PLM Martial Arts Charms do
    not); `noncf` of them are non-Caste/Favored and so need a General Slot; committed
    installation `motes` must fit the `personal` Essence pool (p.62)."""
    general: int
    dedicated: int
    installed: int
    noncf: int
    motes: int
    personal: int

    @property
    def over_slots(self) -> bool:
        return self.installed > self.general + self.dedicated

    @property
    def over_general(self) -> bool:
        return self.noncf > self.general

    @property
    def over_personal(self) -> bool:
        return self.motes > self.personal


def charm_slot_budget(ruleset: RuleSet, character: Character) -> Optional[SlotBudget]:
    """The Charm-Slot occupancy for a slot-splat (Alchemical), or None for the per-pick
    splats. Everything comes from the engine — the same `charm_slot_usage` the chargen
    check consumes — so the readout can never disagree with validation."""
    if not validate.uses_charm_slots(ruleset, character):
        return None
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    installed, noncf, motes = validate.charm_slot_usage(ruleset, character)
    personal, _peripheral = derive.essence_pools(ruleset, character)
    return SlotBudget(g, d, installed, noncf, motes, personal)


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


def _artifact_rows(ruleset: RuleSet, character: Character
                   ) -> list[tuple[str, int, str, int]]:
    """Every rated artifact for the sheet, as (name, rating, source label, damage).

    Reads `engine.artifacts.artifact_items` rather than `character.artifacts` so an
    artifact daiklave appears here as well as in the weapons table — the p.131 budget
    counts it, so a sheet that omitted it would disagree with the validator about what
    the character owns.

    The damage figure comes from `MeritEffects`, not from any Merit id: this module
    may not name one (decision 0011).
    """
    damaged = meritsmod.merits_and_flaws_calc(ruleset, character).damaged_artifacts
    return [(i.name, i.rating,
             "" if i.source == artifactsmod.SOURCE_ARTIFACT else i.source,
             damaged.get(i.key, 0))
            for i in artifactsmod.artifact_items(character)]


def _health_label(hl: derive.HealthLevelView) -> str:
    if hl.incapacitated:
        base = "Incap"
    elif hl.penalty == 0:
        base = "-0"
    else:
        base = str(hl.penalty)
    return f"{base} ★" if hl.source else base   # ★ marks a Charm-granted level


# The book prints the zero rung as "x"; "○" reads as an empty dot beside the filled
# ones and does not collide with the em dashes the ladder text itself uses.
_DOTS = ["○", "•", "••", "•••", "••••", "•••••"]


def background_rung(catalog: Sequence[BackgroundType], name: str, rating: int) -> str:
    """What the book says this RATING of this Background gets you — the one rung of
    `BackgroundType.ladder` the character actually holds, rendered "••• Three major
    contacts and…".

    `catalog` is the character's OWN filtered catalogue (`RuleSet.backgrounds_for`),
    not the whole `background_catalog`, and that is load-bearing rather than
    convenience: several Background NAMES belong to two splats with different printed
    text — a Dragon-Blooded's Connections is not a Sidereal's (Sidereals p.106), and
    Celestial Manse / Salary / Savant are printed for both the Dragon-Kings (PG p.176)
    and the Sidereals. `BackgroundEntry` stores a name, not an id, so a search over
    every splat's entries would hand a Sidereal the Dragon-King's rungs. Searching
    only what this character can actually take makes the name unambiguous.

    Backgrounds are free text, so an unknown name, an untranscribed ladder and a
    rating off the 0-5 scale all return "" and the caller simply shows nothing."""
    bg = next((b for b in catalog if b.name == name), None)
    if bg is None or not bg.ladder or not 0 <= rating < len(bg.ladder):
        return ""
    return f"{_DOTS[rating]} {bg.ladder[rating]}"


def background_ladder(catalog: Sequence[BackgroundType], name: str) -> list[tuple[str, str]]:
    """The WHOLE printed ladder as (dots, text) pairs, for the catalogue dialog's
    full-description panel — where the reader is choosing a rating rather than
    holding one. Same splat-filtered `catalog` as `background_rung`, for the same
    duplicate-name reason. Empty for a Background whose ladder is not transcribed."""
    bg = next((b for b in catalog if b.name == name), None)
    return [(_DOTS[i], text) for i, text in enumerate(bg.ladder)] if bg else []


def college_rows(ruleset: RuleSet, character: Character) -> list[tuple[str, int, str, bool]]:
    """The character's Astrological Colleges as (name, rating, house_label, own_house),
    ordered own-Maiden first then by name — the chargen floor counts only the own-house
    dots (Sidereal, p.98), so those are what a reader checks first. A College id no
    longer in the RuleSet still renders, showing its raw id, rather than vanishing."""
    rows = []
    for cr in character.colleges:
        college = ruleset.colleges.get(cr.college_id)
        if college is None:
            rows.append((cr.college_id, cr.rating, "?", False))
        else:
            rows.append((college.name, cr.rating, college.house_label,
                         college.house == character.caste))
    return sorted(rows, key=lambda r: (not r[3], r[0]))


# The sheet's section order, and the ThaumPurchase.kind each draws from. Sections with
# nothing in them are dropped, so a character with only a couple of formulas gets one
# short line rather than five headings and four dashes.
_THAUM_SECTIONS = [("Arts", "art"), ("Specialties", "specialty"),
                   ("Sciences", "science"), ("Rituals", "ritual"),
                   ("Formulas", "formula")]


def thaumaturgy_rows(ruleset: RuleSet, character: Character) -> list[tuple[str, list[str]]]:
    """The character's thaumaturgy grouped for the sheet, from the engine's canonical
    enumeration — so a purchase can never appear on the picker and be missing here."""
    purchases = validate.thaum_purchases(ruleset, character)
    out = []
    for label, kind in _THAUM_SECTIONS:
        items = [p.label for p in purchases if p.kind == kind]
        if items:
            out.append((label, items))
    return out


def build_sheet_view(ruleset: RuleSet, character: Character) -> SheetView:
    d = derive.derive(ruleset, character)

    issues = list(validate.validate(ruleset, character))
    # Pre-lock, surface chargen budget/legality findings; post-lock, the XP audit.
    if not character.chargen_locked:
        issues += validate.validate_chargen(ruleset, character)
    else:
        issues += advancement.validate_xp(ruleset, character)

    own_caste = ruleset.castes.get(character.caste)
    own_caste_abilities = set(own_caste.caste_abilities) if own_caste else set()
    favored = set(character.favored_abilities)

    # Dragon-King breed attribute bonuses (PG pp.167-174): the breed grants free dots
    # ON TOP of the pool, so the sheet shows the EFFECTIVE value (stored + bonus) with
    # the bonus called out — a Pterok's Dexterity reads as its real 5, not the 3 it
    # cost to buy. Stored values stay what pools and validation read; this is display
    # only, and a no-op for every splat whose caste has no breed_traits.
    _breed_traits = own_caste.breed_traits if own_caste else None
    _breed_bonus = _breed_traits.attribute_bonuses if _breed_traits else {}

    def _attribute_row(a: AttributeName) -> TraitRow:
        bonus = _breed_bonus.get(a, 0)
        if bonus:
            return TraitRow(f"{_label(a.value)} (+{bonus} breed)",
                            character.attributes[a] + bonus)
        return TraitRow(_label(a.value), character.attributes[a])

    attributes = [
        (category, [_attribute_row(a) for a in members])
        for category, members in validate.ATTRIBUTE_CATEGORIES.items()
    ]

    # Abilities grouped by their ability-caste (Dawn..Eclipse), matching the sheet.
    # Craft is per-focus (core p.136): the single Craft slot expands into one row
    # per craft instance ("Craft (Smithing)"), or a single 0-rated row if none.
    ability_groups: list[tuple[str, list[TraitRow]]] = []
    for group_label, group_abilities in ability_group_defs(ruleset, character.exalt_type):
        rows: list[TraitRow] = []
        for a in group_abilities:
            cf_flags = dict(caste=a in own_caste_abilities, favored=a in favored)
            if a == AbilityName.CRAFT:
                if character.crafts:
                    rows += [TraitRow(f"Craft ({c.focus})", c.rating, **cf_flags)
                             for c in character.crafts]
                else:
                    rows.append(TraitRow("Craft", 0, **cf_flags))
            else:
                rows.append(TraitRow(_label(a.value), character.abilities.get(a, 0), **cf_flags))
        ability_groups.append((group_label, rows))

    virtues = [TraitRow(_label(v.value), character.virtues[v]) for v in VirtueName]

    # One row per Charm the character holds, from the single engine enumeration —
    # the sheet must NOT walk character.charms / .ox_body / .beastman_gifts /
    # .granted_charms itself. `charm_picks` already labels repeatable purchases with
    # their chosen variant(s) and tags granted Charms "(granted)".
    charms = []
    _sections: dict[str, list[CharmRow]] = {}

    def _section_label(pick, charm) -> str:
        """Which subsystem panel a charm pick belongs on — the same distinctions the
        picker's tabs draw. Gifts are the Lunar DBT list, Ox-Body its own repeatable
        purchase, Arcanoi are the Ghost/God-Blooded Virtue-keyed Charms (identified by
        `min_virtue` AND a non-Spirit exalt_type, exactly as the picker does — the
        spirit Charms are Virtue-keyed too but are a different class, not Arcanoi);
        everything else is an ordinary Charm."""
        if pick.source == "beastman_gifts":
            return "Gifts"
        if pick.source == "ox_body":
            return "Ox-Body Technique"
        if charm is not None and charm.min_virtue and charm.exalt_type != "Spirit":
            return "Arcanoi"
        return "Charms"

    for pick in validate.charm_picks(ruleset, character):
        charm = ruleset.charms.get(pick.charm_id)
        if charm is None:
            row = CharmRow(pick.label, "?", "—", "—", missing=True)
            charms.append(row)
            _sections.setdefault("Charms", []).append(row)
            continue
        # A repeatable purchase shows the Charm's own text rather than the
        # prerequisite-annotated one, and Ox-Body has no per-purchase activation cost.
        if pick.source in ("ox_body", "beastman_gifts"):
            cost = "—" if pick.source == "ox_body" else _cost_str(charm.cost)
            description = charm.description
        else:
            cost = _cost_str(charm.cost)
            description = _charm_description(charm)
        row = CharmRow(pick.label, charm.category, cost, charm.duration,
                       description, custom=charm.custom)
        charms.append(row)
        _sections.setdefault(_section_label(pick, charm), []).append(row)
    # Elemental Powers (PG p.68): the Charm-like learnable powers of an
    # Elemental-origin God-Blooded, their own headed section in the Charms & Sorcery
    # band exactly like Arcanoi/Gifts. Missing ids render as lost rows, mirroring the
    # missing-Charm handling above — a deleted custom power must not vanish silently.
    elemental_powers = []
    for pid in character.elemental_powers:
        power = ruleset.elemental_powers.get(pid)
        if power is None:
            elemental_powers.append(CharmRow(pid, "?", "—", "—", missing=True))
            continue
        elemental_powers.append(CharmRow(
            power.name, "Elemental Powers", "", "", power.description))
    if elemental_powers:
        _sections["Elemental Powers"] = elemental_powers
    # A character who holds no Charm of any kind still gets a "Charms (0)" panel —
    # the sheet has always said so, and the render tests pin it. Sections only appear
    # when they have rows (an empty Arcanoi panel must not sit on every sheet).
    charm_sections = list(_sections.items()) or [("Charms", [])]

    # Dragon-King Paths (PG pp.175-191): the rated-track truth, not the virtual Charm
    # projection. Only owned Paths appear; each lists the powers its rating grants.
    paths = []
    for path in ruleset.paths.values():
        rating = next((p.rating for p in character.paths if p.path_id == path.id), 0)
        if rating <= 0:
            continue
        if path.element and path.element == engine_paths.breed_element(ruleset, character):
            fav = "★"
        elif path.id == character.favored_path:
            fav = "✚"
        else:
            fav = ""
        paths.append(PathRow(
            name=path.name, element_label=path.element_label, favored=fav, rating=rating,
            powers=[PathPowerRow(p.dot, p.name, _cost_str(p.cost), p.type.value,
                                 p.duration, p.text)
                    for p in path.powers[:rating]],
        ))

    # Combos — member names resolve through ruleset.charms, which includes the
    # Dragon-King Path powers' virtual rows, so a DK Combo's members read as their
    # power names.
    combos = []
    for combo in character.combos:
        members = []
        for cid in combo.charm_ids:
            ch = ruleset.charms.get(cid)
            members.append(ch.name if ch else cid)
        combos.append((combo.name, members, len(combo.charm_ids)))
    spells = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            # Mirrors the missing-Charm row above: a spell whose definition has gone
            # (a deleted custom spell) must show as lost, not quietly vanish off the
            # sheet leaving the character looking like it never knew it.
            spells.append(SpellRow(sid, "?", "—", missing=True))
            continue
        spells.append(SpellRow(spell.name, spell.circle.value, _cost_str(spell.cost),
                               spell.description, custom=spell.custom))

    virtue_flaw = None
    if character.virtue_flaw:
        vf = character.virtue_flaw
        virtue_flaw = f"{_label(vf.virtue.value)}: {vf.description}" if vf.description else _label(vf.virtue.value)

    return SheetView(
        name=character.name or "(unnamed)",
        player=character.player,
        caste=own_caste.label if own_caste else character.caste,
        caste_noun=ruleset.exalt_for(character.exalt_type).caste_noun,
        exalt_type=character.exalt_type,
        concept=character.concept,
        nature=character.nature,
        anima=character.anima,
        biography=[(label, value) for label, value in (
            ("Sex", character.sex), ("Age", character.age),
            ("Eyes", character.eye_color), ("Hair", character.hair_color),
            ("Skin", character.skin_color), ("Height", character.height),
            ("Weight", character.weight), ("Description", character.description),
            ("Backstory", character.backstory), ("Notes", character.notes))
            if value],
        totem=character.totem,
        animal_forms=[(f.name, f.notes) for f in character.animal_forms],
        essence_rating=character.essence_rating,
        attributes=attributes,
        ability_groups=ability_groups,
        virtues=virtues,
        willpower=d.willpower,
        essence_personal=d.essence_personal,
        essence_peripheral=d.essence_peripheral,
        essence_single_pool=d.essence_single_pool,
        essence_free=d.essence_free,
        soak=d.soak,
        health=[_health_label(hl) for hl in d.health_levels],
        backgrounds=[(b.name, b.rating, b.note) for b in character.backgrounds],
        artifacts=_artifact_rows(ruleset, character),
        fetters=[(f.name, f.rating, f.note) for f in character.fetters],
        fetter_cap=(derive.fetter_cap(character, ruleset) if character.fetters else 0),
        passions=[(p.virtue.value.title(), p.name, p.rating)
                  for p in character.passions],
        passion_pools=([(v.value.title(),
                         derive.passion_pool(character)[v]
                         - derive.passion_dots_unspent(character)[v],
                         derive.passion_pool(character)[v])
                        for v in VirtueName if derive.passion_pool(character)[v]]
                       if character.passions else []),
        merits_flaws=merit_rows(ruleset, character),
        colleges=college_rows(ruleset, character),
        thaumaturgy=thaumaturgy_rows(ruleset, character),
        # The dead hold thaumaturgy but may never use it (p.114) — a note on the sheet,
        # not a bar, so the knowledge still reads as theirs.
        thaumaturgy_note=("" if ruleset.exalt_for(character.exalt_type).thaumaturgy_usable
                          else f"{character.exalt_type} may hold thaumaturgy but can "
                               "never use it (p.114)."),
        specialties=[(_label(s.ability.value), s.name, s.rating) for s in character.specialties],
        charms=charms,
        charm_sections=charm_sections,
        paths=paths,
        breed_weapons=[(w.name, w.speed, w.accuracy, w.damage, w.damage_type, w.defense)
                       for w in _breed_traits.innate_weapons] if _breed_traits else [],
        combos=combos,
        spells=spells,
        elemental_powers=elemental_powers,
        # Effective stats: material bonuses folded in, Exalt-gated (core p.341).
        weapons=[derive.effective_weapon(ruleset, character, w) for w in character.weapons],
        armor=[derive.effective_armor(ruleset, character, a) for a in character.armor],
        virtue_flaw=virtue_flaw,
        experience=character.xp_earned,
        issues=issues,
        chargen_locked=character.chargen_locked,
        xp_earned=character.xp_earned,
        xp_spent=advancement.xp_spent(character),
        xp_available=advancement.xp_available(character),
        # Pre-lock the log is empty by construction, but say so explicitly: a chargen
        # sheet showing an "Experience" section with nothing in it reads as a bug.
        xp_log=build_xp_log(ruleset, character) if character.chargen_locked else [],
    )


# --------------------------------------------------------------------------- #
# Play-state capacities (the in-play tracker reads these; nothing flows back) #
# --------------------------------------------------------------------------- #

@dataclass
class PlayHealthBox:
    label: str            # "-0", "-1", "Incap", with " ★" for a bonus/charm level
    incapacitated: bool


@dataclass
class PlayView:
    """The capacities the Play tab overlays its fill-state onto, all derived from
    the permanent character — the box count/labels of the health track and the
    mote/Willpower maxima. The tracker stores only the fill marks (Character.play)."""
    health_boxes: list[PlayHealthBox]
    personal_max: int
    peripheral_max: int
    willpower_max: int
    # The two pools merged into one (Beacon of Power). Carried rather than inferred
    # from `personal_max == 0`, which cannot tell "merged by rule" from "this splat
    # has no Personal pool" — the same distinction `essence_single_pool` draws for
    # the sheet. ⚠ Without it the tracker renders a Personal box reading 0/0, which
    # looks like a bug rather than a rule.
    single_pool: bool = False
    # Motes of that maximum drawable without a Willpower roll (Essence Awareness),
    # or None when all of them are. The tracker still counts spending against the
    # FULL maximum — the restricted two thirds are spendable, just not freely — so
    # this is a marker on the track, never a second cap. The roll is the table's to
    # make (decision 0009); the tracker only says where the line falls.
    free_max: Optional[int] = None
    # The fatigue-roll difficulty of each worn piece, "Buff Jacket 1" (core p.332:
    # the roll is Stamina + Endurance "with a difficulty equal to the armor's fatigue
    # value"). Read through effective_armor, so jade shows no difficulty at all for a
    # Dragon-Blooded — "jade-alloy armor has no fatigue value" (p.345). A difficulty
    # is not a dice-pool term, so it is reference text beside the counter, never a
    # line in a pool.
    fatigue_difficulties: list[str] = dc_field(default_factory=list)


def build_play_view(ruleset: RuleSet, character: Character) -> PlayView:
    """Capacities for the in-play tracker. Pure read of the engine derivations —
    the health track shape, the Essence pools, and permanent Willpower."""
    d = derive.derive(ruleset, character)
    return PlayView(
        health_boxes=[PlayHealthBox(_health_label(hl), hl.incapacitated)
                      for hl in d.health_levels],
        personal_max=d.essence_personal,
        peripheral_max=d.essence_peripheral,
        willpower_max=d.willpower,
        single_pool=d.essence_single_pool,
        free_max=d.essence_free,
        fatigue_difficulties=[
            f"{a.name or 'Armour'} {eff.fatigue}"
            for a, eff in ((a, derive.effective_armor(ruleset, character, a))
                           for a in character.armor)
            if eff.fatigue],
    )


# --------------------------------------------------------------------------- #
# The dice-pool calculator (decision 0016)
#
# A BASE pool, never a final one. Everything derived lives here so the widget
# module only lays out what this returns — including the exclusions text, which is
# not decoration: it is the mitigation 0016 accepted for 0008's objection that a
# static combat number "looks authoritative and is wrong the moment a Charm fires".
# --------------------------------------------------------------------------- #

@dataclass
class PoolChoicesView:
    """Everything the calculator's controls can offer for one selected roll —
    which of them are relevant is a property of the RollDefinition, so the widget
    module never has to know that (say) a Virtue check takes no weapon."""
    needs_weapon: bool
    needs_virtue: bool
    weapons: list[str]                       # inline weapon names, in owned order
    virtues: list[str]                       # display labels
    specialties: list[str]                   # "Swords (+2 dice)" for the ones that apply
    takes_mobility: bool                     # this roll carries the armour penalty
    mobility_lines: list[str]                # what would be subtracted, for the toggle label
    takes_wound: bool                        # False where a page exempts the roll (p.233)
    wound_exempt_note: str = ""              # why, when it does not
    fatigue_points: int = 0                  # accumulated armour fatigue, as a positive count


@dataclass
class PoolView:
    """One computed base pool, ready to render."""
    roll_name: str
    lines: list[tuple[str, int]]             # (label, signed value), in order
    total: int
    summary: str                             # "Dexterity 4 + Melee 3 … = 9"
    excludes: list[str]
    notes: str = ""
    wound_label: str = ""                    # "-2", "Incapacitated", or ""
    below_one: bool = False                  # penalties took it under a single die


def pool_roll_options(ruleset: RuleSet) -> list[tuple[str, str]]:
    """(id, label) for every shipped roll, grouped by category in the label so one
    flat select reads as a grouped one. Empty when no dice_pools.json shipped."""
    rows = sorted(ruleset.roll_catalog.values(), key=lambda r: (r.category, r.name))
    return [(r.id, f"{r.category} · {r.name}" if r.category else r.name) for r in rows]


def build_pool_choices(ruleset: RuleSet, character: Character,
                       roll) -> PoolChoicesView:
    from ..engine import pools as poolsmod
    return PoolChoicesView(
        needs_weapon=roll.weapon_stat.value != "none",
        needs_virtue=roll.kind.value == "virtue",
        weapons=[w.name or "(unnamed)" for w in character.weapons],
        virtues=[v.value.title() for v in VirtueName],
        # One entry per NAME, already summed across instances — see SpecialtyOption.
        specialties=[f"{s.name} (+{s.dice} {'die' if s.dice == 1 else 'dice'})"
                     for s in poolsmod.specialties_for(character, roll)],
        takes_mobility=roll.mobility_applies,
        mobility_lines=[f"{name} -{points}" for name, points
                        in poolsmod.mobility_penalty(ruleset, character)],
        takes_wound=roll.wound_applies,
        wound_exempt_note=("" if roll.wound_applies else
                           "Wound penalties do not subtract from this roll (p.233)."),
        fatigue_points=-poolsmod.fatigue_penalty(character),
    )


def build_pool_view(ruleset: RuleSet, character: Character, roll, *,
                    weapon_index: Optional[int] = None,
                    virtue: Optional[VirtueName] = None,
                    specialty_index: Optional[int] = None,
                    include_mobility: bool = True,
                    include_wound: bool = True,
                    include_fatigue: bool = True) -> PoolView:
    """Compute the base pool for `roll` with the calculator's current selections.

    The wound and fatigue penalties are read HERE — the visible play-state reads,
    handed to the engine as plain integers (decision 0006; see engine/pools.py).
    `include_wound` / `include_fatigue` are the toggles, so switching one off is a
    presentation choice that never has to reach into Character.play.

    ⚠ `include_wound=True` is a REQUEST, not a guarantee: a roll whose row is
    exempt (p.233) drops the line inside the engine. Read the returned lines, never
    the flag, to know what is in the total.
    """
    from ..engine import pools as poolsmod
    penalty, wound_label = poolsmod.wound_penalty(ruleset, character)
    fatigue = poolsmod.fatigue_penalty(character)
    weapon = (character.weapons[weapon_index]
              if weapon_index is not None and 0 <= weapon_index < len(character.weapons)
              else None)
    applicable = poolsmod.specialties_for(character, roll)
    specialty = (applicable[specialty_index]
                 if specialty_index is not None and 0 <= specialty_index < len(applicable)
                 else None)
    bd = poolsmod.base_pool(
        ruleset, character, roll,
        weapon=weapon, virtue=virtue, specialty=specialty,
        include_mobility=include_mobility,
        wound_penalty=penalty if include_wound else 0,
        fatigue_penalty=fatigue if include_fatigue else 0)
    return PoolView(
        roll_name=bd.roll,
        lines=[(ln.label, ln.value) for ln in bd.lines],
        total=bd.total,
        summary=bd.summary,
        excludes=list(bd.excludes),
        notes=bd.notes,
        wound_label=wound_label,
        below_one=bd.below_one,
    )


@dataclass
class PoolRow:
    """One roll in the sidebar list: a name, its arithmetic on one line, and the
    total. `compact` is a BREAKDOWN, not a caption — a row that showed only `total`
    would be the bare number decision 0016 forbids."""
    name: str
    compact: str                             # "+4 dex +3 melee +2 acc -1 wnd -2 ftg"
    total: int
    below_one: bool = False
    note: str = ""                           # a printed rider worth one short line


@dataclass
class PoolSidebarView:
    """Everything the dice-pool sidebar renders: the shared controls at the top, the
    grouped roll list in the middle, and the standing exclusions at the bottom."""
    # (index into character.weapons, display name). PAIRS rather than a bare list
    # because the list is now FILTERED — ammunition is excluded — and a filtered list
    # whose position was used as the index would attack with the wrong weapon.
    weapons: list[tuple[int, str]]
    groups: list[tuple[str, list[PoolRow]]]  # (category, rows), in catalogue order
    excludes: list[str]
    wound_label: str = ""                    # "-1", "Incapacitated", or ""
    fatigue_points: int = 0
    mobility_lines: list[str] = dc_field(default_factory=list)
    any_below_one: bool = False
    # Ammunition the character carries, same (index, name) shape. Only populated when
    # the chosen weapon is one that fires it.
    arrows: list[tuple[int, str]] = dc_field(default_factory=list)
    # The chosen arrow's printed damage line — REFERENCE, never a pool term. An arrow
    # changes what the shot does, not what you roll to hit (core p.330 gives arrows a
    # base damage and a soak clause and no accuracy at all), and decision 0008 keeps
    # damage out of this build entirely. Shown beside the Archery rows so the player
    # can see which arrow is nocked without it touching a single die.
    arrow_note: str = ""


def _ammunition_indices(ruleset: RuleSet, character: Character) -> set[int]:
    """Positions in `character.weapons` holding ammunition rather than a weapon.

    The character's `Weapon` is an inline copy carrying no tags (decision 0007), so the
    kind is recovered by matching the name back to the catalogue — the same recovery
    `pools.weapon_abilities` does, and with the same failure direction: a homebrew name
    matches nothing and is treated as a weapon, because a custom weapon that silently
    stopped being attackable-with would be the worse bug."""
    ammo = {w.name for w in ruleset.weapon_catalog.values() if "ammunition" in w.tags}
    return {i for i, w in enumerate(character.weapons) if w.name in ammo}


def _fires_ammunition(ruleset: RuleSet, weapon: Optional[Weapon]) -> bool:
    """Whether this weapon takes arrows — an Archery weapon that is not itself ammo."""
    if weapon is None:
        return False
    entry = next((w for w in ruleset.weapon_catalog.values() if w.name == weapon.name),
                 None)
    return entry is not None and "archery" in entry.tags and "ammunition" not in entry.tags


def clamp_pool_selection(state: dict, sidebar: PoolSidebarView) -> None:
    """Drop a weapon/arrow choice that no longer names a row, in place.

    `state` OUTLIVES the weapon list it indexes: the Play tab's sidebar is rebuilt on
    every play-state change, and between two builds the player can delete a weapon on
    the equipment surface. A `ui.select` whose value is not among its options raises at
    BUILD time and takes the whole tab down with it, siblings included
    (`docs/adding-a-splat.md` trap #3).

    Clearing rather than remapping is deliberate: the list renumbers when a row is
    deleted, so the index that survives names a DIFFERENT weapon than the one chosen.

    ⚠ A PURE function so it can be tested without the browser harness. Driving this
    through a delete-and-rebuild is untestable in a full-suite run: a `@ui.page` route
    builds once per session and `user.client.elements` accumulates across every route
    the session has opened, so "the last select labelled X" — and `user.find(marker=
    ...)` with it — can belong to another page entirely. Such a test passes alone and
    fails in the suite, firing its trigger at somebody else's widget.
    """
    for key, rows in (("weapon", sidebar.weapons), ("arrow", sidebar.arrows)):
        if state.get(key) not in {i for i, _ in rows}:
            state[key] = None


def build_pool_sidebar(ruleset: RuleSet, character: Character, *,
                       weapon_index: Optional[int] = None,
                       arrow_index: Optional[int] = None,
                       include_mobility: bool = True,
                       include_wound: bool = True,
                       include_fatigue: bool = True) -> PoolSidebarView:
    """Every roll the catalogue knows, computed at once for the sidebar.

    Two rolls expand into several rows, because in a LIST there is nothing to pick
    from — the choice has to be visible as separate lines:

    * a Virtue check becomes one row per Virtue;
    * a roll whose Ability carries specialties gets one extra row per specialty
      NAME, since a specialty applies only to its own facet (p.134) and folding it
      into the base row would claim dice the character does not always have.
    """
    from ..engine import pools as poolsmod
    penalty, wound_label = poolsmod.wound_penalty(ruleset, character)
    fatigue = poolsmod.fatigue_penalty(character)
    weapon = (character.weapons[weapon_index]
              if weapon_index is not None and 0 <= weapon_index < len(character.weapons)
              else None)

    def _row(roll, name: str, **kw) -> PoolRow:
        # The weapon joins only the rolls it is actually used with — a daiklave
        # lends nothing to an Archery pool. Unknown (homebrew) weapons apply
        # everywhere, which is the safe direction.
        wp = weapon if (weapon is not None
                        and poolsmod.weapon_applies(ruleset, weapon, roll)) else None
        bd = poolsmod.base_pool(
            ruleset, character, roll, weapon=wp,
            include_mobility=include_mobility,
            wound_penalty=penalty if include_wound else 0,
            fatigue_penalty=fatigue if include_fatigue else 0, **kw)
        return PoolRow(name=name, compact=bd.compact, total=bd.total,
                       below_one=bd.below_one, note=bd.notes)

    groups: dict[str, list[PoolRow]] = {}
    for roll in sorted(ruleset.roll_catalog.values(),
                       key=lambda r: (r.category, r.name)):
        rows = groups.setdefault(roll.category or "Other", [])
        if roll.kind is PoolKind.VIRTUE:
            rows += [_row(roll, f"{roll.name} — {v.value.title()}", virtue=v)
                     for v in VirtueName]
            continue
        rows.append(_row(roll, roll.name))
        for spec in poolsmod.specialties_for(character, roll):
            rows.append(_row(roll, f"{roll.name} · {spec.name}", specialty=spec))

    ammo_idx = _ammunition_indices(ruleset, character)
    arrows: list[tuple[int, str]] = []
    arrow_note = ""
    if _fires_ammunition(ruleset, weapon):
        arrows = [(i, character.weapons[i].name or "(unnamed)") for i in sorted(ammo_idx)]
        if arrow_index is not None and arrow_index in ammo_idx:
            arrow = character.weapons[arrow_index]
            sign = "+" if arrow.damage >= 0 else ""
            arrow_note = (f"{arrow.name}: Strength {sign}{arrow.damage}"
                          f"{arrow.damage_type or 'L'} base damage"
                          + (f" — {arrow.notes}" if arrow.notes else ""))

    return PoolSidebarView(
        weapons=[(i, w.name or "(unnamed)") for i, w in enumerate(character.weapons)
                 if i not in ammo_idx],
        arrows=arrows,
        arrow_note=arrow_note,
        groups=list(groups.items()),
        excludes=list(poolsmod.EXCLUDES),
        wound_label=wound_label,
        fatigue_points=-fatigue,
        mobility_lines=[f"{name} -{points}" for name, points
                        in poolsmod.mobility_penalty(ruleset, character)],
        any_below_one=any(r.below_one for rows in groups.values() for r in rows),
    )


def pool_trait_options() -> tuple[dict[str, str], dict[str, str]]:
    """(attributes, abilities) as {enum value: label} for the custom-pool selects.
    The full nine and the full 25 — a custom pool is for whatever the table is
    doing, so nothing is filtered by caste, favouring or rating."""
    return ({a.value: _label(a.value) for a in AttributeName},
            {a.value: _label(a.value) for a in AbilityName})


def pool_mobility_lines(ruleset: RuleSet, character: Character) -> list[str]:
    """"Buff Jacket -1" per worn piece, for a surface that needs to know whether the
    armour-mobility question arises at all. Same read `build_pool_sidebar` does."""
    from ..engine import pools as poolsmod
    return [f"{name} -{points}"
            for name, points in poolsmod.mobility_penalty(ruleset, character)]


def build_custom_pool(ruleset: RuleSet, character: Character,
                      attribute: AttributeName, ability: AbilityName, *,
                      agility_based: bool = False,
                      include_mobility: bool = True,
                      include_wound: bool = True,
                      include_fatigue: bool = True) -> list[PoolRow]:
    """The player's own Attribute + Ability pool, plus one row per applicable
    specialty (same reasoning as the preset rows — p.134 scopes a specialty to its
    own facet, so it cannot be folded into the base row).

    `agility_based` is the player's answer to p.332's discretionary clause, not a
    guess: the mobility penalty applies to dodge and whole-body Athletics feats by
    the printed rule, and to anything else "the Storyteller deems becomes more
    difficult in 20 or more pounds of protective gear".
    """
    from ..engine import pools as poolsmod
    penalty, _ = poolsmod.wound_penalty(ruleset, character)
    fatigue = poolsmod.fatigue_penalty(character)
    roll = poolsmod.custom_roll(attribute, ability, mobility_applies=agility_based)

    def _row(name: str, **kw) -> PoolRow:
        bd = poolsmod.base_pool(
            ruleset, character, roll,
            include_mobility=include_mobility,
            wound_penalty=penalty if include_wound else 0,
            fatigue_penalty=fatigue if include_fatigue else 0, **kw)
        return PoolRow(name=name, compact=bd.compact, total=bd.total,
                       below_one=bd.below_one)

    rows = [_row(roll.name)]
    rows += [_row(f"{roll.name} · {s.name}", specialty=s)
             for s in poolsmod.specialties_for(character, roll)]
    return rows


@dataclass
class PartyCardView:
    """One character as the GM's party page shows them: the same play capacities
    the Play tab uses, plus the few permanent numbers worth having on the table
    at a glance. `dodge` is the stored Ability rating, NOT a dice pool — combat
    derivation is deliberately not implemented, so the card must not invent one."""
    name: str
    exalt_type: str
    caste_label: str
    caste_noun: str          # what this splat calls the caste slot ("Caste"/"Aspect")
    essence_rating: int
    dodge: int
    soak: derive.SoakView
    play: PlayView
    chargen_locked: bool

    @property
    def identity_line(self) -> str:
        """'Fire Aspect · Dragon-Blooded' — the sub-heading under the name. A
        party is often mixed, so each card states its own splat vocabulary."""
        return f"{self.caste_label} {self.caste_noun} · {self.exalt_type}"


def build_party_card_view(ruleset: RuleSet, character: Character) -> PartyCardView:
    """The compact card for one party member. Composes build_play_view rather
    than re-deriving the capacities, so a card and the Play tab can never
    disagree about the same character."""
    caste = ruleset.castes.get(character.caste)
    return PartyCardView(
        name=character.name or "(unnamed)",
        exalt_type=character.exalt_type,
        caste_label=caste.label if caste else character.caste,
        caste_noun=ruleset.exalt_for(character.exalt_type).caste_noun,
        essence_rating=character.essence_rating,
        dodge=character.abilities.get(AbilityName.DODGE, 0),
        soak=derive.derive(ruleset, character).soak,
        play=build_play_view(ruleset, character),
        chargen_locked=character.chargen_locked,
    )


# --------------------------------------------------------------------------- #
# Custom content (the /custom authoring page)
#
# The page is a JSON editor with dropdowns, so everything here is shape-shuffling
# between a flat form dict and a Charm/Spell payload — no game logic, and no
# writing: custom_content owns the filesystem, models own validity.
#
# It lives in view.py with the other presenters so it can be tested without
# NiceGUI, which matters more here than for most panels: the form is where a typo
# turns into an unloadable library.
# --------------------------------------------------------------------------- #

# The health-cost damage types, for the form's dropdown. "" is "the source does not
# say", which is how every printed Charm with a health cost reads.
HEALTH_TYPE_OPTIONS = {"": "unspecified"} | {
    d.value: DAMAGE_LABELS[d] for d in Damage}

# The one field that is a free-text escape hatch rather than a dropdown. Seeded
# from what the shipped data actually uses, most common first, and a combobox so
# anything else can still be typed.
CHARM_DURATIONS = ["Instant", "One scene", "One turn", "One day", "One hour",
                   "Indefinite", "Permanent", "Varies", "Special", "N/A"]

# `keywords` is deliberately omitted: EVERY shipped Charm leaves it empty, so a
# control for it would be clutter.


@dataclass
class CustomRow:
    """One row in the library list on the left of the authoring page."""
    id: str
    name: str
    kind: str                  # "charm" | "spell"
    detail: str                # category/circle, for the list's second line
    valid: bool                # False = in the library but rejected by the loader
    problem: str = ""          # why it was rejected, when it was


# Sentinel category: the page swaps in a style-name box and writes
# martial_arts:<slug>. Not a storable value — never reaches a payload.
NEW_STYLE = "__new_style__"


def _style_categories(ruleset: RuleSet) -> list[str]:
    """Every Martial Arts style category present in the rule set, custom included."""
    return sorted({c.category for c in ruleset.charms.values()
                   if c.category.startswith("martial_arts:")})


def custom_category_options(ruleset: RuleSet) -> dict[str, str]:
    """The category dropdown: every Ability, then every known Martial Arts style,
    then the sentinel that creates a NEW style. Keys are the stored `category`
    strings, values the labels."""
    opts = {a.value: _label(a.value) for a in AbilityName}
    opts.update({cat: _style_label(cat, ruleset) for cat in _style_categories(ruleset)})
    opts["sorcery"] = "Sorcery (no gating Ability)"
    opts[NEW_STYLE] = "New Martial Arts style…"
    return opts



def charm_element_options(ruleset: RuleSet) -> dict[str, str]:
    """The elemental-tree dropdown, read from the data rather than hardcoded so a
    splat with a different elemental axis needs no change here."""
    elements = sorted({c.element for c in ruleset.charms.values() if c.element})
    return {"": "no elemental tree"} | {e: e for e in elements}


def charm_tier_options(ruleset: RuleSet) -> dict[str, str]:
    """The Exalt tiers a Charm may be opened to (`open_to_tiers`), from the splat
    definitions — "Celestial" on the cross-tier Martial Arts styles."""
    return {t: t for t in sorted({e.tier for e in ruleset.exalts.values() if e.tier})}


def extra_req_trait_options(kind: str) -> dict[str, str]:
    """The trait dropdown for one extra-requirement row: Abilities or Attributes.
    Both are OR-lists, so the control is a multi-select either way."""
    names = AttributeName if kind == "attribute" else AbilityName
    return {t.value: _label(t.value) for t in names}


def custom_charm_form(row: Optional[dict] = None) -> dict:
    """The form state for a Charm: blank for a new one, or filled from a library
    row for an edit. Flat and JSON-safe so the page can bind straight to it."""
    row = row or {}
    cost = row.get("cost") or {}
    source = row.get("source") or {}
    groups = row.get("prerequisites") or []
    # AND-of-OR collapses to two shapes the form can express: every group a single
    # id ("all of these"), or one group of several ("any one of these"). Anything
    # more complex was hand-authored and is left to the JSON pane, which is why the
    # mode is reported rather than guessed at save time.
    any_of = len(groups) == 1 and len(groups[0]) > 1
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "category": row.get("category", AbilityName.MELEE.value),
        "style_name": "",
        "exalt_type": row.get("exalt_type", "Solar"),
        "type": row.get("type", "Supplemental"),
        "min_ability": row.get("min_ability", 1),
        "min_essence": row.get("min_essence", 1),
        "motes": cost.get("motes", 0),
        "willpower": cost.get("willpower", 0),
        "health": cost.get("health", 0),
        "health_type": cost.get("health_type") or "",
        "committed": bool(cost.get("committed", False)),
        "cost_raw": cost.get("raw", ""),
        "duration": row.get("duration", "Instant"),
        "extra_reqs": ([{"kind": "ability", "traits": list(r.get("abilities") or []),
                         "rating": r.get("rating", 1)}
                        for r in (row.get("extra_min_abilities") or [])]
                       + [{"kind": "attribute", "traits": list(r.get("attributes") or []),
                           "rating": r.get("rating", 1)}
                          for r in (row.get("extra_min_attributes") or [])]),
        "prerequisites": [g[0] for g in groups] if not any_of else list(groups[0]),
        "prereq_mode": "any" if any_of else "all",
        "grants_circle": row.get("grants_circle") or "",
        # --- advanced: splat mechanics, behind the form's collapsed section ---
        "element": row.get("element", ""),
        "immaculate": bool(row.get("immaculate", False)),
        "open_to_all": bool(row.get("open_to_all", False)),
        "open_to_tiers": list(row.get("open_to_tiers") or []),
        "min_attribute": row.get("min_attribute", ""),
        "no_foreign_learning": bool(row.get("no_foreign_learning", False)),
        "installation_cost": row.get("installation_cost", 0),
        "arrayable": bool(row.get("arrayable", True)),
        "permanent_install": bool(row.get("permanent_install", False)),
        "permanent_clarity": row.get("permanent_clarity", 0),
        "breadth_reqs": [{"category": r.get("category", ""), "count": r.get("count", 1),
                          "label": r.get("label", "")}
                         for r in (row.get("prerequisite_counts") or [])],
        "description": row.get("description", ""),
        "book": source.get("book", "Homebrew"),
        "page": source.get("page") or None,
    }


def custom_charm_payload(form: dict) -> dict:
    """Form state -> a Charm payload for custom_content.save_charm. Drops empty
    optional fields rather than storing zeros and "", so a hand-read library file
    stays as short as the Charm actually is."""
    category = form.get("category") or ""
    if category == NEW_STYLE:
        category = custom_content.style_category(form.get("style_name", ""))
    ids = [i for i in (form.get("prerequisites") or []) if i]
    prerequisites = ([list(ids)] if form.get("prereq_mode") == "any" and len(ids) > 1
                     else [[i] for i in ids])
    cost = {k: int(form.get(k) or 0) for k in ("motes", "willpower", "health")}
    cost = {k: v for k, v in cost.items() if v}
    # Only meaningful alongside a health cost: naming a damage type for a Charm that
    # spends no health levels would be stored and then never read.
    if cost.get("health") and form.get("health_type"):
        cost["health_type"] = form["health_type"]
    if form.get("committed"):
        cost["committed"] = True
    if (form.get("cost_raw") or "").strip():
        cost["raw"] = form["cost_raw"].strip()

    payload = {
        "id": form.get("id") or "",
        "name": (form.get("name") or "").strip(),
        "category": category,
        "exalt_type": form.get("exalt_type") or "Solar",
        "type": form.get("type") or "Supplemental",
        "min_ability": int(form.get("min_ability") or 0),
        "min_essence": int(form.get("min_essence") or 1),
        "duration": form.get("duration") or "Instant",
        "description": (form.get("description") or "").strip(),
        "source": {"book": (form.get("book") or "Homebrew").strip(),
                   "page": form.get("page") or None},
    }
    if cost:
        payload["cost"] = cost
    if prerequisites:
        payload["prerequisites"] = prerequisites
    if form.get("grants_circle"):
        payload["grants_circle"] = form["grants_circle"]
    # Extra trait minimums. One control in the form, two typed lists in the payload:
    # the engine budgets Abilities and Attributes differently and the models keep them
    # apart. A row with no traits picked is dropped rather than stored empty.
    extra_abilities, extra_attributes = [], []
    for req in form.get("extra_reqs") or []:
        traits = [t for t in (req.get("traits") or []) if t]
        rating = int(req.get("rating") or 1)
        if not traits:
            continue
        if req.get("kind") == "attribute":
            extra_attributes.append({"attributes": traits, "rating": rating})
        else:
            extra_abilities.append({"abilities": traits, "rating": rating})
    if extra_abilities:
        payload["extra_min_abilities"] = extra_abilities
    if extra_attributes:
        payload["extra_min_attributes"] = extra_attributes

    # Breadth prerequisites ("any three Lore Charms") — a COUNT over a category,
    # which the id-based `prerequisites` cannot express.
    breadth = [{"category": r["category"], "count": int(r.get("count") or 1)}
               | ({"label": r["label"]} if (r.get("label") or "").strip() else {})
               for r in (form.get("breadth_reqs") or []) if (r.get("category") or "")]
    if breadth:
        payload["prerequisite_counts"] = breadth

    # Advanced splat mechanics. Each is written only when it differs from the model
    # default, so an ordinary homebrew Charm's JSON stays short and readable.
    for key in ("element", "min_attribute"):
        if (form.get(key) or "").strip():
            payload[key] = form[key].strip()
    for key in ("immaculate", "open_to_all", "no_foreign_learning", "permanent_install"):
        if form.get(key):
            payload[key] = True
    if form.get("open_to_tiers"):
        payload["open_to_tiers"] = list(form["open_to_tiers"])
    for key in ("installation_cost", "permanent_clarity"):
        if int(form.get(key) or 0):
            payload[key] = int(form[key])
    # `arrayable` defaults TRUE, so only the False case is worth storing.
    if not form.get("arrayable", True):
        payload["arrayable"] = False
    return payload


def custom_spell_form(row: Optional[dict] = None) -> dict:
    row = row or {}
    cost = row.get("cost") or {}
    source = row.get("source") or {}
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "circle": row.get("circle", SpellCircle.TERRESTRIAL.value),
        "motes": cost.get("motes", 0),
        "willpower": cost.get("willpower", 0),
        "cost_raw": cost.get("raw", ""),
        "description": row.get("description", ""),
        "book": source.get("book", "Homebrew"),
        "page": source.get("page") or None,
    }


def custom_spell_payload(form: dict) -> dict:
    cost = {k: int(form.get(k) or 0) for k in ("motes", "willpower")}
    cost = {k: v for k, v in cost.items() if v}
    if (form.get("cost_raw") or "").strip():
        cost["raw"] = form["cost_raw"].strip()
    payload = {
        "id": form.get("id") or "",
        "name": (form.get("name") or "").strip(),
        "circle": form.get("circle") or SpellCircle.TERRESTRIAL.value,
        "description": (form.get("description") or "").strip(),
        "source": {"book": (form.get("book") or "Homebrew").strip(),
                   "page": form.get("page") or None},
    }
    if cost:
        payload["cost"] = cost
    return payload


def build_custom_library(ruleset: RuleSet, charm_rows: list[dict],
                         spell_rows: list[dict]) -> list[CustomRow]:
    """The library list: every row ON DISK, whether or not it loaded.

    Taking the rows as arguments keeps this pure — the page reads the disk. A row
    the loader rejected still appears, marked invalid with the loader's reason, so
    the only copy of a broken Charm is not invisible in the one screen that could
    fix it.
    """
    problems = {p: p for p in ruleset.custom_problems}

    def _problem_for(row_id: str) -> str:
        return next((p for p in problems if f"{row_id!r}" in p), "")

    out: list[CustomRow] = []
    for row in charm_rows:
        rid = row.get("id", "")
        loaded = ruleset.charms.get(rid)
        out.append(CustomRow(
            id=rid, name=row.get("name") or rid, kind="charm",
            detail=(_style_label(loaded.category, ruleset) if loaded and loaded.category.startswith("martial_arts:")
                    else _label(loaded.category) if loaded
                    else row.get("category", "?")),
            valid=loaded is not None and loaded.custom,
            problem=_problem_for(rid)))
    for row in spell_rows:
        rid = row.get("id", "")
        loaded = ruleset.spells.get(rid)
        out.append(CustomRow(
            id=rid, name=row.get("name") or rid, kind="spell",
            detail=f"{loaded.circle.value} Circle" if loaded else row.get("circle", "?"),
            valid=loaded is not None and loaded.custom,
            problem=_problem_for(rid)))
    return out


# --------------------------------------------------------------------------- #
# Adversary card presentation
#
# Moved verbatim out of `ui/adversaries.py` 2026-08-10 (the engine module was
# aliased `adv` there and is `advmod` here — the only edit). Display composition,
# not rules: every number comes from `engine.adversaries`, this just words it.
#
# Their siblings `trait_line` / `attack_line` did NOT come here despite also being
# model-to-text: those are half of a round-tripped edit-field codec and live with
# their parsers in `engine/adversaries.py`. See the note above them there.
# --------------------------------------------------------------------------- #

def summary_line(ruleset: RuleSet, a: Adversary) -> str:
    """The one-line stat readout under the name: initiative, dodge, soak.

    Reads through the engine so the armour's mobility penalty and soak land here
    the same way they would anywhere else."""
    lethal, bashing = advmod.soak(ruleset, a)
    dodge = advmod.dodge_after_armor(ruleset, a)
    bits = []
    if a.base_initiative is not None:
        bits.append(f"Init {a.base_initiative}")
    # An extra's single pool replaces every Attribute + Ability roll it makes, so
    # it belongs on the stat line rather than buried among the traits.
    if a.combat_pool is not None:
        bits.append(f"Pool {a.combat_pool}")
    bits.append(f"Dodge {dodge}" if dodge is not None else "No dodge")
    bits.append(f"Soak {lethal}L/{bashing}B")
    if a.essence:
        bits.append(f"Essence {a.essence}")
    if a.cost_to_materialize:
        bits.append(f"Materialize {a.cost_to_materialize}")
    if a.cost_to_dematerialize:
        bits.append(f"Dematerialize {a.cost_to_dematerialize}")
    # The shield's contribution the dodge pool cannot show: the book prints this
    # on the statblocks themselves ("+1 difficulty to attack"), and nothing here
    # resolves an attack, so the Storyteller applies it.
    melee, ranged = advmod.attack_difficulty(ruleset, a)
    if melee or ranged:
        bits.append(f"+{melee}/+{ranged} difficulty to hit (melee/ranged)")
    return "  ·  ".join(bits)


def trait_map_line(values: dict[str, int], order: list[str]) -> str:
    """"Str 4  Dex 2  Sta 4" — the printed Attributes/Virtues, abbreviated to fit
    a card. Absent keys are skipped, never shown as 0 (a beast prints three of the
    nine, and the book means absent, not zero)."""
    return "  ".join(f"{k[:3].title()} {values[k]}" for k in order if k in values)
