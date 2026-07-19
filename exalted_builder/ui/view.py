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

from ..engine import advancement, derive, validate
from ..models.character import Armor, Character, Weapon, XpEntry
from ..models.rules import AbilityName, CharmCost, RuleSet, SpellCircle, VirtueName


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


@dataclass
class SpellDetail:
    id: str
    name: str
    circle: str
    cost: str
    description: str
    owned: bool
    available: bool                        # a known Charm grants its Circle


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
    )


def build_charm_graph(ruleset: RuleSet, character: Character, category: str) -> CharmGraph:
    """Assemble the prerequisite graph for one Charm category, tagging each node
    by the character's relationship to it: owned, available (learnable now), or
    locked. Pure — eligibility comes from engine.validate."""
    owned = set(character.charms)
    charms = [c for c in ruleset.charms.values()
              if c.category == category and validate.charm_matches_splat(character, c)]
    charms.sort(key=lambda c: c.id)

    ox_id = validate.ox_body_charm_id(ruleset, character)
    nodes = []
    for c in charms:
        # Ox-Body is repeatable and lives on character.ox_body, not character.charms:
        # it is "owned" once at least one copy is bought, else available per its reqs.
        if c.id and c.id == ox_id:
            state = "owned" if character.ox_body else (
                "available" if validate.meets_charm_requirements(ruleset, character, c) else "locked")
        elif c.id in owned:
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
    if domain in ("willpower", "essence"):
        return f"{domain.title()} {entry.from_rating} → {entry.to_rating}{note}"
    if domain == "charms":
        charm = ruleset.charms.get(entry.detail)
        return f"Charm: {charm.name if charm else entry.detail}"
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
    return entry.target


def build_xp_log(ruleset: RuleSet, character: Character) -> list[XpLogRow]:
    """The XP spend log as display rows, in spend order. Pure presentation; the
    engine owns costs and legality. Only the last row is safe to undo (LIFO)."""
    return [
        XpLogRow(index=i, label=_xp_entry_label(ruleset, character, e),
                 detail=e.target.split(".", 1)[0], cost=e.cost)
        for i, e in enumerate(character.xp_log)
    ]


_CIRCLE_ORDER = {SpellCircle.TERRESTRIAL: 0, SpellCircle.CELESTIAL: 1, SpellCircle.SOLAR: 2}


def build_spell_picker(ruleset: RuleSet, character: Character) -> list[SpellPickRow]:
    """Every Spell in the RuleSet tagged by the character's relationship to it:
    owned, available (a known Charm grants its circle and it isn't a chargen-barred
    Solar spell), or locked with a one-line reason. Ordered by circle then name.
    Pure — eligibility comes from engine.validate."""
    barred = validate.chargen_barred_circle(ruleset, character)
    rows: list[SpellPickRow] = []
    for spell in sorted(ruleset.spells.values(),
                        key=lambda s: (_CIRCLE_ORDER.get(s.circle, 9), s.name)):
        owned = spell.id in character.spells
        available = validate.meets_spell_requirements(ruleset, character, spell)
        reason = ""
        if not owned and not available:
            if spell.circle == barred:
                reason = f"{spell.circle.value} Circle spells can't be taken at creation"
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
    caste_noun: str          # what this splat calls the caste slot ("Caste"/"Aspect")
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
    # Pre-lock, surface chargen budget/legality findings; post-lock, the XP audit.
    if not character.chargen_locked:
        issues += validate.validate_chargen(ruleset, character)
    else:
        issues += advancement.validate_xp(ruleset, character)

    own_caste = ruleset.castes.get(character.caste)
    own_caste_abilities = set(own_caste.caste_abilities) if own_caste else set()
    favored = set(character.favored_abilities)

    attributes = [
        (category, [TraitRow(_label(a.value), character.attributes[a]) for a in members])
        for category, members in validate.ATTRIBUTE_CATEGORIES.items()
    ]

    # Abilities grouped by their ability-caste (Dawn..Eclipse), matching the sheet.
    # Craft is per-focus (core p.136): the single Craft slot expands into one row
    # per craft instance ("Craft (Smithing)"), or a single 0-rated row if none.
    ability_groups: list[tuple[str, list[TraitRow]]] = []
    for group_def in ruleset.castes.values():
        if group_def.exalt_type != character.exalt_type:
            continue
        rows: list[TraitRow] = []
        for a in group_def.caste_abilities:
            cf_flags = dict(caste=a in own_caste_abilities, favored=a in favored)
            if a == AbilityName.CRAFT:
                if character.crafts:
                    rows += [TraitRow(f"Craft ({c.focus})", c.rating, **cf_flags)
                             for c in character.crafts]
                else:
                    rows.append(TraitRow("Craft", 0, **cf_flags))
            else:
                rows.append(TraitRow(_label(a.value), character.abilities.get(a, 0), **cf_flags))
        ability_groups.append((group_def.label, rows))

    virtues = [TraitRow(_label(v.value), character.virtues[v]) for v in VirtueName]

    charms = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm:
            charms.append(CharmRow(charm.name, charm.category, _cost_str(charm.cost)))
        else:
            charms.append(CharmRow(cid, "?", "—"))
    # Repeatable Ox-Body Technique: one row per purchase, labelled by its package.
    ox_charm = validate.ox_body_charm(ruleset, character)
    if ox_charm:
        labels = {v.key: v.label for v in ox_charm.variants}
        for p in character.ox_body:
            charms.append(CharmRow(f"{ox_charm.name} ({labels.get(p.variant, p.variant)})",
                                   ox_charm.category, "—"))
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
        caste=own_caste.label if own_caste else character.caste,
        caste_noun=ruleset.exalt_for(character.exalt_type).caste_noun,
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
        # Effective stats: material bonuses folded in, Exalt-gated (core p.341).
        weapons=[derive.effective_weapon(ruleset, character, w) for w in character.weapons],
        armor=[derive.effective_armor(ruleset, character, a) for a in character.armor],
        virtue_flaw=virtue_flaw,
        experience=character.xp_earned,
        issues=issues,
        chargen_locked=character.chargen_locked,
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
    )
