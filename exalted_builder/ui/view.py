"""
ui/view.py — the presenter: assemble a display-ready view model from a RuleSet
and Character.

This is the seam between the engine and the rendering layer. It calls the engine
(derive, validate), resolves Charm/Spell ids to names, and shapes everything into
plain dataclasses the UI can render directly. It contains NO game logic of its
own and imports NO UI toolkit, so it is unit-testable on its own and the NiceGUI
layer (ui/app.py) stays a thin renderer.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..engine import derive, validate
from ..models.character import Armor, Character, Weapon
from ..models.rules import AbilityName, RuleSet, VirtueName


@dataclass
class TraitRow:
    label: str
    value: int
    caste: bool = False
    favored: bool = False


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
    attributes: list[tuple[str, list[TraitRow]]]   # (category name, rows), ordered
    abilities: list[TraitRow]                      # all 25, caste-grouped enum order
    virtues: list[TraitRow]
    # derived
    willpower: int
    essence_personal: int
    essence_peripheral: int
    soak: derive.SoakView
    health: list[str]                              # formatted level labels
    # advantages / gear
    backgrounds: list[tuple[str, int, str]]        # (name, rating, note)
    specialties: list[tuple[str, str, int]]        # (ability label, name, rating)
    charms: list[tuple[str, str]]                  # (name, category)
    spells: list[tuple[str, str]]                  # (name, circle)
    weapons: list[Weapon]
    armor: list[Armor]
    # status
    issues: list[validate.Issue]
    chargen_locked: bool


def _label(value: str) -> str:
    """'martial_arts' -> 'Martial Arts'."""
    return value.replace("_", " ").title()


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

    caste_def = ruleset.castes.get(character.caste)
    caste_abilities = set(caste_def.caste_abilities) if caste_def else set()
    favored = set(character.favored_abilities)

    attributes = [
        (category, [TraitRow(_label(a.value), character.attributes[a]) for a in members])
        for category, members in validate.ATTRIBUTE_CATEGORIES.items()
    ]
    abilities = [
        TraitRow(_label(a.value), character.abilities.get(a, 0),
                 caste=a in caste_abilities, favored=a in favored)
        for a in AbilityName
    ]
    virtues = [TraitRow(_label(v.value), character.virtues[v]) for v in VirtueName]

    charms = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        charms.append((charm.name, charm.category) if charm else (cid, "?"))
    spells = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        spells.append((spell.name, spell.circle.value) if spell else (sid, "?"))

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
        abilities=abilities,
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
        issues=issues,
        chargen_locked=character.chargen_locked,
    )
