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

from enum import Enum
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


class CraftRating(BaseModel):
    """One Craft Ability instance. In 1e (core p.136) Craft is taken per focus —
    "characters who wish to master multiple crafts must take this Ability multiple
    times" — so each craft (Smithing, Genesis, ...) is its own independently rated
    Ability, NOT a specialty. The single AbilityName.CRAFT dot in `abilities` is
    unused; the engine reads craft ratings from this list."""
    focus: str                             # the specific craft, e.g. "Smithing"
    rating: int = Field(ge=0, le=5)


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
    # Magical material (rules.MagicalMaterial id; "" = mundane). Its stat bonus is
    # applied by engine.derive only when the wielder's Exalt type matches.
    material: str = ""
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
    material: str = ""                     # magical material id; "" = mundane


class VirtueFlaw(BaseModel):
    virtue: VirtueName
    description: str = ""


class OxBodyPurchase(BaseModel):
    """One purchase of the repeatable Ox-Body Technique. `variant` is the chosen
    package's key (rules.CharmVariant.key); `health_levels` is that package's wound
    levels copied inline (like equipment) so engine.derive needs no RuleSet."""
    variant: str
    health_levels: list[int] = Field(default_factory=list)


class HealthLevel(BaseModel):
    """An adjustment to the health track. Normally a *bonus* level granted by a
    Charm (e.g. Ox-Body Technique); with `removed=True` it instead *removes* a
    level of that penalty (e.g. a curse that leaves a character less hale than
    normal). The base -0/-1/-1/-2/-2/-4/Incap track is a rules constant, derived
    not stored. Marked damage is play-state and intentionally out of scope."""
    penalty: int                           # 0, -1, -2, -4 ...
    source_charm: str = ""
    removed: bool = False                  # True = a curse removing a level of this penalty


class XpEntry(BaseModel):
    """One post-lock purchase. The engine verifies `cost` against the XP table and
    that the implied delta is reflected in current state."""
    target: str                            # "abilities.melee", "essence", "charms", ...
    detail: str = ""                       # charm/spell id for 'new' purchases
    from_rating: Optional[int] = None
    to_rating: Optional[int] = None
    cost: int
    training_complete: bool = True         # dormant hook for the parked training-time rule


class ChargenSnapshot(BaseModel):
    """Frozen at lock; the baseline the XP log is measured against."""
    attributes: dict[AttributeName, int]
    abilities: dict[AbilityName, int]
    crafts: list[CraftRating] = Field(default_factory=list)
    virtues: dict[VirtueName, int]
    specialties: list[Specialty]
    backgrounds: list[BackgroundEntry]
    charms: list[str]
    spells: list[str]
    combos: list[Combo] = Field(default_factory=list)
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)
    essence_rating: int
    willpower_purchased: int
    wp_virtue_component: int               # two highest Virtues AT LOCK; never recomputed


class Damage(str, Enum):
    """A mark in a health-track box. The 1e shorthand: '/' bashing, 'x' lethal,
    '*' aggravated. (Empty boxes are None.)"""
    BASHING = "/"
    LETHAL = "x"
    AGGRAVATED = "*"


class PlayState(BaseModel):
    """Ephemeral *play-state* — current motes/Willpower spent, marked health damage,
    and Limit. This is a deliberately separate layer from the permanent character:
    it is NOT read by chargen validation, the XP audit, or the permanent-value
    derivations (those only flow capacities OUT to here). It is a dumb manual
    tracker — no auto mote-accounting, no damage-wrapping rules, no auto-healing —
    so the ST stays in control. Old saves load with `Character.play` None.

    `health` is a list of marks aligned positionally to engine.derive.health_track;
    it is normalised to the track length at render time (Ox-Body bought later just
    extends it). Motes are a simple spent count against the derived pool maxima;
    `willpower_spent` counts spent boxes out of permanent Willpower; `limit` is a
    bare 0..10 counter (Limit Break at 10)."""
    health: list[Optional[Damage]] = Field(default_factory=list)
    motes_personal_spent: int = Field(default=0, ge=0)
    motes_peripheral_spent: int = Field(default=0, ge=0)
    willpower_spent: int = Field(default=0, ge=0)
    limit: int = Field(default=0, ge=0, le=10)


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
    # Craft is per-focus (core p.136): each entry is its own rated Ability. The
    # AbilityName.CRAFT key in `abilities` is unused — read craft from here.
    crafts: list[CraftRating] = Field(default_factory=list)
    favored_abilities: list[AbilityName] = Field(default_factory=list)
    specialties: list[Specialty] = Field(default_factory=list)

    virtues: dict[VirtueName, int] = Field(
        default_factory=lambda: {v: 1 for v in VirtueName}
    )
    virtue_flaw: Optional[VirtueFlaw] = None

    # Purchased Willpower dots, net of permanent penalties. Non-negative in normal
    # play, but may go negative post-lock when a curse reduces permanent Willpower
    # below the pinned Virtue component (permanent WP = component + purchased; see
    # engine.advancement.lower_willpower). The engine floors permanent WP at 1.
    willpower_purchased: int = 0
    # Frozen at lock so post-creation Virtue gains can't raise Willpower; None pre-lock.
    wp_virtue_component: Optional[int] = None

    backgrounds: list[BackgroundEntry] = Field(default_factory=list)
    charms: list[str] = Field(default_factory=list)           # Charm ids into the RuleSet
    combos: list[Combo] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)           # Spell ids into the RuleSet
    # Repeatable Ox-Body Technique: one record per purchase (it is therefore NOT in
    # `charms`). Each carries the chosen variant + its inline health levels.
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)

    weapons: list[Weapon] = Field(default_factory=list)
    armor: list[Armor] = Field(default_factory=list)
    health_bonus_levels: list[HealthLevel] = Field(default_factory=list)

    # --- lifecycle / accounting ---
    chargen_locked: bool = False
    chargen_snapshot: Optional[ChargenSnapshot] = None
    xp_earned: int = Field(default=0, ge=0)
    xp_log: list[XpEntry] = Field(default_factory=list)

    # --- play-state (separate layer; never enters chargen/XP validation) ---
    play: Optional[PlayState] = None
