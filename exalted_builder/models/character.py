"""
models/character.py — the save file.

Holds a character's *current, canonical* trait values plus the audit structures
the engine uses to validate them:

  * pre-lock  : current traits are validated against ChargenBudgets.
  * lock      : freeze the Willpower virtue-component (post-creation Virtue gains
                must NOT raise Willpower) and snapshot traits as the XP baseline.
  * post-lock : edits are mirrored by append-only XpEntry rows; the engine checks
                current state against snapshot + log and that each cost is correct.

Only structural invariants are enforced here (non-negative ratings, valid enums,
rating <= 5). Game legality lives in engine.validate, which needs the RuleSet —
deliberately not imported here, so the engine stays the single source of rules.

Note on serialization: enum-keyed dicts (attributes/abilities/virtues) round-trip
through JSON using the enum *string values* as keys, e.g. {"strength": 3}.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .rules import AbilityName, AttributeName, Caste, VirtueName


# --------------------------------------------------------------------------- #
# Sub-records
# --------------------------------------------------------------------------- #

class Specialty(BaseModel):
    ability: AbilityName
    name: str
    rating: int = Field(ge=1, le=3)        # cap of three per ability enforced in engine


class BackgroundEntry(BaseModel):
    name: str                              # open-ended: "Artifact", "Manse", "Resources"...
    rating: int = Field(ge=0, le=5)
    note: str = ""                         # the specific descriptor


class Combo(BaseModel):
    name: str
    charm_ids: list[str] = Field(default_factory=list)
    willpower_cost: int = Field(default=1, ge=0)


class Weapon(BaseModel):
    """Inline copy of a weapon the character owns. Mirrors rules.WeaponType so the
    catalog can autofill it; artifact/ranged fields default to mundane-melee."""
    name: str
    speed: int = 0
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0
    rate: int = 0
    range: int = Field(default=0, ge=0)    # yards; 0 = melee only
    max_strength: int = Field(default=0, ge=0)
    min_strength: int = Field(default=0, ge=0)
    min_dexterity: int = Field(default=0, ge=0)
    min_martial_arts: int = Field(default=0, ge=0)
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    resources_cost: int = Field(default=0, ge=0)
    notes: str = ""


class Armor(BaseModel):
    """Inline copy of armour the character owns. Mirrors rules.ArmorType."""
    name: str
    soak_lethal: int = 0                   # soak is computed per damage type in engine.derive
    soak_bashing: int = 0
    mobility_penalty: int = 0
    fatigue: int = 0
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    resources_cost: int = Field(default=0, ge=0)


class VirtueFlaw(BaseModel):
    virtue: VirtueName
    description: str = ""


class HealthLevel(BaseModel):
    """A bonus health level granted by a Charm (e.g. Ox-Body Technique). The base
    -0/-1/-1/-2/-2/-4/Incap track is a rules constant and is derived, not stored.
    Marked damage is play-state and is intentionally out of scope."""
    penalty: int                           # 0, -1, -2, -4 ...
    source_charm: str = ""


class XpEntry(BaseModel):
    """One post-lock purchase. The engine verifies `cost` against the XP table and
    that the implied delta is reflected in current state."""
    target: str                            # "abilities.melee", "essence", "charms", ...
    detail: str = ""                       # charm/spell id for 'new' purchases
    from_rating: Optional[int] = None
    to_rating: Optional[int] = None
    cost: int = Field(ge=0)
    training_complete: bool = True         # dormant hook for the parked training-time rule


class ChargenSnapshot(BaseModel):
    """Frozen at lock; the baseline the XP log is measured against."""
    attributes: dict[AttributeName, int]
    abilities: dict[AbilityName, int]
    virtues: dict[VirtueName, int]
    specialties: list[Specialty]
    backgrounds: list[BackgroundEntry]
    charms: list[str]
    spells: list[str]
    essence_rating: int
    willpower_purchased: int
    wp_virtue_component: int               # two highest Virtues AT LOCK; never recomputed


# --------------------------------------------------------------------------- #
# The character
# --------------------------------------------------------------------------- #

class Character(BaseModel):
    # --- identity / concept ---
    id: str
    name: str = ""
    player: str = ""
    edition: str = "1e"
    exalt_type: str = "Solar"
    caste: Caste = Caste.DAWN
    concept: str = ""
    nature: str = ""
    anima: str = ""

    # --- current, canonical traits ---
    essence_rating: int = Field(default=2, ge=1)
    attributes: dict[AttributeName, int] = Field(
        default_factory=lambda: {a: 1 for a in AttributeName}
    )
    abilities: dict[AbilityName, int] = Field(
        default_factory=lambda: {a: 0 for a in AbilityName}
    )
    favored_abilities: list[AbilityName] = Field(default_factory=list)
    specialties: list[Specialty] = Field(default_factory=list)

    virtues: dict[VirtueName, int] = Field(
        default_factory=lambda: {v: 1 for v in VirtueName}
    )
    virtue_flaw: Optional[VirtueFlaw] = None

    willpower_purchased: int = Field(default=0, ge=0)
    # Frozen at lock so post-creation Virtue gains can't raise Willpower; None pre-lock.
    wp_virtue_component: Optional[int] = None

    backgrounds: list[BackgroundEntry] = Field(default_factory=list)
    charms: list[str] = Field(default_factory=list)           # Charm ids into the RuleSet
    combos: list[Combo] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)           # Spell ids into the RuleSet

    weapons: list[Weapon] = Field(default_factory=list)
    armor: list[Armor] = Field(default_factory=list)
    health_bonus_levels: list[HealthLevel] = Field(default_factory=list)

    # --- lifecycle / accounting ---
    chargen_locked: bool = False
    chargen_snapshot: Optional[ChargenSnapshot] = None
    xp_earned: int = Field(default=0, ge=0)
    xp_log: list[XpEntry] = Field(default_factory=list)
