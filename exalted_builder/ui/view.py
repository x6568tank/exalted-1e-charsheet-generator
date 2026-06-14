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

from dataclasses import dataclass
from typing import Optional

from ..engine import derive, validate
from ..models.character import Armor, Character, Weapon
from ..models.rules import AbilityName, Caste, CharmCost, RuleSet, SpellCircle, VirtueName


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


@dataclass
class SpellRow:
    name: str
    circle: str
    cost: str


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


@dataclass
class CharmNode:
    id: str
    label: str
    state: str          # 'owned' | 'available' | 'locked'
    min_ability: int
    min_essence: int


@dataclass
class CharmGraph:
    category: str
    nodes: list[CharmNode]
    edges: list[tuple[str, str]]   # (prerequisite_id, charm_id)
    roots: list[str]               # charm ids with no prerequisites


@dataclass
class CharmDetail:
    id: str
    name: str
    description: str
    type: str
    cost: str
    requirement: str                       # e.g. "Martial Arts 4, Essence 2"
    prerequisite_groups: list[list[str]]   # charm names; inner list = an OR group
    owned: bool
    available: bool                        # learnable right now


def build_charm_detail(ruleset: RuleSet, character: Character, charm_id: str) -> Optional[CharmDetail]:
    """Display detail for a single Charm: its requirements (gating ability + min
    essence), prerequisite Charms by name, and the character's relationship to it.
    Pure; eligibility comes from engine.validate."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        return None
    ability = validate._category_ability(charm.category)
    reqs = []
    if ability is not None and charm.min_ability:
        reqs.append(f"{_label(ability.value)} {charm.min_ability}")
    reqs.append(f"Essence {charm.min_essence}")
    groups = [[ruleset.charms[r].name if r in ruleset.charms else r for r in group]
              for group in charm.prerequisites]
    return CharmDetail(
        id=charm.id,
        name=charm.name,
        description=charm.description,
        type=charm.type.value,
        cost=_cost_str(charm.cost),
        requirement=", ".join(reqs),
        prerequisite_groups=groups,
        owned=charm_id in character.charms,
        available=validate.meets_charm_requirements(ruleset, character, charm),
    )


def build_charm_graph(ruleset: RuleSet, character: Character, category: str) -> CharmGraph:
    """Assemble the prerequisite graph for one Charm category, tagging each node
    by the character's relationship to it: owned, available (learnable now), or
    locked. Pure — eligibility comes from engine.validate."""
    owned = set(character.charms)
    charms = [c for c in ruleset.charms.values() if c.category == category]
    charms.sort(key=lambda c: c.id)

    nodes = []
    for c in charms:
        if c.id in owned:
            state = "owned"
        elif validate.meets_charm_requirements(ruleset, character, c):
            state = "available"
        else:
            state = "locked"
        nodes.append(CharmNode(c.id, c.name, state, c.min_ability, c.min_essence))

    ids = {c.id for c in charms}
    edges = [(req, c.id) for c in charms for group in c.prerequisites
             for req in group if req in ids]
    roots = [c.id for c in charms if not c.prerequisites]
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


_CIRCLE_ORDER = {SpellCircle.TERRESTRIAL: 0, SpellCircle.CELESTIAL: 1, SpellCircle.SOLAR: 2}


def build_spell_picker(ruleset: RuleSet, character: Character) -> list[SpellPickRow]:
    """Every Spell in the RuleSet tagged by the character's relationship to it:
    owned, available (a known Charm grants its circle and it isn't a chargen-barred
    Solar spell), or locked with a one-line reason. Ordered by circle then name.
    Pure — eligibility comes from engine.validate."""
    rows: list[SpellPickRow] = []
    for spell in sorted(ruleset.spells.values(),
                        key=lambda s: (_CIRCLE_ORDER.get(s.circle, 9), s.name)):
        owned = spell.id in character.spells
        available = validate.meets_spell_requirements(ruleset, character, spell)
        reason = ""
        if not owned and not available:
            if spell.circle == SpellCircle.SOLAR:
                reason = "Solar Circle spells can't be taken at creation"
            else:
                reason = f"needs a Charm granting the {spell.circle.value} Circle"
        rows.append(SpellPickRow(
            id=spell.id, name=spell.name, circle=spell.circle.value,
            cost=_cost_str(spell.cost), description=spell.description,
            owned=owned, available=available, reason=reason,
        ))
    return rows


@dataclass
class SheetView:
    # identity / concept
    name: str
    player: str
    caste: str
    exalt_type: str
    concept: str
    nature: str
    anima: str
    essence_rating: int
    # traits
    attributes: list[tuple[str, list[TraitRow]]]      # (category, rows), ordered
    ability_groups: list[tuple[str, list[TraitRow]]]  # (ability-caste, rows), Dawn..Eclipse
    virtues: list[TraitRow]
    # derived
    willpower: int
    essence_personal: int
    essence_peripheral: int
    soak: derive.SoakView
    health: list[str]                                 # formatted level labels
    # advantages / gear
    backgrounds: list[tuple[str, int, str]]           # (name, rating, note)
    specialties: list[tuple[str, str, int]]           # (ability label, name, rating)
    charms: list[CharmRow]
    spells: list[SpellRow]
    weapons: list[Weapon]
    armor: list[Armor]
    # status / misc
    virtue_flaw: Optional[str]
    merits_flaws: list[tuple[str, int, bool]]   # (name, points, is_flaw)
    experience: int
    issues: list[validate.Issue]
    chargen_locked: bool


def _label(value: str) -> str:
    """'martial_arts' -> 'Martial Arts'."""
    return value.replace("_", " ").title()


def _cost_str(cost: CharmCost) -> str:
    if cost.raw:
        return cost.raw
    parts = []
    if cost.motes:
        parts.append(f"{cost.motes}m")
    if cost.willpower:
        parts.append(f"{cost.willpower}wp")
    if cost.health:
        parts.append(f"{cost.health}hl")
    return ", ".join(parts) if parts else "—"


def _health_label(hl: derive.HealthLevelView) -> str:
    if hl.incapacitated:
        base = "Incap"
    elif hl.penalty == 0:
        base = "-0"
    else:
        base = str(hl.penalty)
    return f"{base} ★" if hl.source else base   # ★ marks a Charm-granted level


def build_sheet_view(ruleset: RuleSet, character: Character) -> SheetView:
    d = derive.derive(ruleset, character)

    issues = list(validate.validate(ruleset, character))
    # Pre-lock, also surface chargen budget/legality findings.
    if not character.chargen_locked:
        issues += validate.validate_chargen(ruleset, character)

    own_caste = ruleset.castes.get(character.caste)
    own_caste_abilities = set(own_caste.caste_abilities) if own_caste else set()
    favored = set(character.favored_abilities)

    attributes = [
        (category, [TraitRow(_label(a.value), character.attributes[a]) for a in members])
        for category, members in validate.ATTRIBUTE_CATEGORIES.items()
    ]

    # Abilities grouped by their ability-caste (Dawn..Eclipse), matching the sheet.
    ability_groups: list[tuple[str, list[TraitRow]]] = []
    for caste in Caste:
        group_def = ruleset.castes.get(caste)
        if group_def is None:
            continue
        rows = [
            TraitRow(_label(a.value), character.abilities.get(a, 0),
                     caste=a in own_caste_abilities, favored=a in favored)
            for a in group_def.caste_abilities
        ]
        ability_groups.append((caste.value, rows))

    virtues = [TraitRow(_label(v.value), character.virtues[v]) for v in VirtueName]

    charms = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm:
            charms.append(CharmRow(charm.name, charm.category, _cost_str(charm.cost)))
        else:
            charms.append(CharmRow(cid, "?", "—"))
    spells = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell:
            spells.append(SpellRow(spell.name, spell.circle.value, _cost_str(spell.cost)))
        else:
            spells.append(SpellRow(sid, "?", "—"))

    virtue_flaw = None
    if character.virtue_flaw:
        vf = character.virtue_flaw
        virtue_flaw = f"{_label(vf.virtue.value)}: {vf.description}" if vf.description else _label(vf.virtue.value)

    return SheetView(
        name=character.name or "(unnamed)",
        player=character.player,
        caste=character.caste.value,
        exalt_type=character.exalt_type,
        concept=character.concept,
        nature=character.nature,
        anima=character.anima,
        essence_rating=character.essence_rating,
        attributes=attributes,
        ability_groups=ability_groups,
        virtues=virtues,
        willpower=d.willpower,
        essence_personal=d.essence_personal,
        essence_peripheral=d.essence_peripheral,
        soak=d.soak,
        health=[_health_label(hl) for hl in d.health_levels],
        backgrounds=[(b.name, b.rating, b.note) for b in character.backgrounds],
        specialties=[(_label(s.ability.value), s.name, s.rating) for s in character.specialties],
        charms=charms,
        spells=spells,
        weapons=list(character.weapons),
        armor=list(character.armor),
        virtue_flaw=virtue_flaw,
        merits_flaws=[(mf.name, mf.points, mf.is_flaw) for mf in character.merits_flaws],
        experience=character.xp_earned,
        issues=issues,
        chargen_locked=character.chargen_locked,
    )
