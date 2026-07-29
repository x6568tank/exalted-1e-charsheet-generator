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

from dataclasses import dataclass, field
from typing import Optional

from ..engine import advancement, costs, derive, validate
from ..models.character import Armor, Character, Weapon, XpEntry
from ..models.rules import (AbilityName, CharmCost, RuleSet, SpellCircle,
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


@dataclass
class SpellRow:
    name: str
    circle: str
    cost: str
    description: str = ""


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
    external: bool = False   # a prerequisite drawn in from ANOTHER category
    # A breadth prerequisite ("any 3 Occult Charms", Aspect Books) has no source node
    # to draw an edge FROM — the requirement is a count over a category, not an id. It
    # rides as a badge on the node instead, so a capstone Charm does not silently read
    # as an entry-level root just because nothing points at it.
    count_requirement: str = ""


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
                validate.charm_count_requirement_label(r) for r in c.prerequisite_counts)))

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
    soak: derive.SoakView
    health: list[str]                                 # formatted level labels
    # advantages / gear
    backgrounds: list[tuple[str, int, str]]           # (name, rating, note)
    # Astrological Colleges (Sidereal, p.98). (name, rating, house_label, own_house)
    # — `own_house` marks a College of the character's own Maiden, the ones the
    # chargen floor counts. Empty for every splat that ships no colleges.
    colleges: list[tuple[str, int, str, bool]]
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


def ability_group_defs(ruleset: RuleSet, exalt_type: str) -> list[tuple[str, list[AbilityName]]]:
    """How to lay the Ability roster out in columns, for the sheet and the editor.

    Ability-caste splats (Solar, Dragon-Blooded, Abyssal) group by caste, which is
    how their character sheets print. Lunars have no Caste Abilities at all and
    "Abilities are not divided along caste lines" (The Lunars p.90), so their
    castes carry `caste_attributes` instead and grouping by caste yields NOTHING.
    Those splats fall back to `DEFAULT_ABILITY_GROUPS` (War / Life / Wisdom)."""
    groups = [(cd.label, list(cd.caste_abilities)) for cd in ruleset.castes.values()
              if cd.exalt_type == exalt_type and cd.caste_abilities]
    if groups:
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
    fixed-set choice (there the printed pair IS the grant — no sub-choice)."""
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
                        key=cat, label=_style_label(cat), charm_ids=ids,
                        available=ok, reason=reason))
                    if ids and any(c in held for c in ids):
                        chosen = cat
            # Choosing the style is only half a category choice — the page grants
            # "two Charms from ONE of four martial arts" (p.90), so the player also
            # picks WHICH. Offer the chosen style's whole roster, flagging any Charm
            # whose own trait minimums the character does not meet (still selectable:
            # validate.granted_charm_issues reports it as granted-charm-minimum, and
            # raising the trait later clears it).
            charm_options: list[CampCharmOption] = []
            chosen_charm_ids: list[str] = []
            if chosen and choice.from_categories:
                pool = next((o.charm_ids for o in options if o.key == chosen), [])
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


def _style_label(category: str) -> str:
    """"martial_arts:ebon-shadow" -> "Ebon Shadow Style"."""
    slug = category.split(":", 1)[-1]
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-")) + " Style"


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
# the data (82 other Charms name a SPECIFIC one as a prerequisite), but the picker
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
    for pick in validate.charm_picks(ruleset, character):
        charm = ruleset.charms.get(pick.charm_id)
        if charm is None:
            charms.append(CharmRow(pick.label, "?", "—", "—"))
            continue
        # A repeatable purchase shows the Charm's own text rather than the
        # prerequisite-annotated one, and Ox-Body has no per-purchase activation cost.
        if pick.source in ("ox_body", "beastman_gifts"):
            cost = "—" if pick.source == "ox_body" else _cost_str(charm.cost)
            description = charm.description
        else:
            cost = _cost_str(charm.cost)
            description = _charm_description(charm)
        charms.append(CharmRow(pick.label, charm.category, cost, charm.duration,
                               description))
    spells = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell:
            spells.append(SpellRow(spell.name, spell.circle.value, _cost_str(spell.cost),
                                   spell.description))
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
        totem=character.totem,
        animal_forms=[(f.name, f.notes) for f in character.animal_forms],
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
        colleges=college_rows(ruleset, character),
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
