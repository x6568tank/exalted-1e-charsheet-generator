"""
models/rules/gear.py — the equipment catalogue models: goods, armor, weapons, and
artifacts.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import Source


# --------------------------------------------------------------------------- #
# Equipment catalog
# The character stores an inline copy (character.Weapon / .Armor), not a reference
# (decision 0007).
# --------------------------------------------------------------------------- #

class ArmorWeight(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    SUPERHEAVY = "Superheavy"


class GearType(BaseModel):
    """One row of the mundane price tables (Manacle and Coin p.123; core pp.323-324).

    `kind` (human's ruling):

    * `goods` — the character can own it. It goes into `Character.gear`.
    * `service` — upkeep, an event or a rental. A reference price only. Never owned.

    `cash` is the printed jade/silver text ("6 minae 950 dinars"). ⚠ Text only: the
    engine calculates nothing from it (M&C p.122).
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: str = "goods"                    # "goods" (ownable) | "service" (reference)
    category: str = ""                     # the printed table heading
    resources_cost: int = Field(default=0, ge=0)
    cash: str = ""                         # printed jade/silver equivalent, verbatim
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    source: Source = Field(default_factory=Source)


class ArmorType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    weight: ArmorWeight
    soak_lethal: int                       # corebook table is Soak (L/B)
    soak_bashing: int
    mobility_penalty: int = 0
    fatigue: int = 0
    resources_cost: int = Field(default=0, ge=0)   # dots of Resources required to buy
    # 0 = mundane. `artifact_rating`: Artifact dots to start with it. `attunement`:
    # motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    # Rules that the fields cannot hold (Aspect Book: Air p.81).
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    # A shield is a row of this model. `tags: ["shield"]` is the discriminator.
    # RuleSet.shields and .body_armor split on it.
    #
    # The two shield values (p.335). Display only (decision 0008).
    difficulty_melee: int = 0          # +N to hit the bearer hand-to-hand
    difficulty_ranged: int = 0         # +N to hit the bearer with missile fire


class WeaponType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    speed: int = 0                         # melee; modifier to initiative
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0                       # melee
    rate: int = 0
    range: int = Field(default=0, ge=0)    # yards; 0 = melee only (thrown/archery)
    max_strength: int = Field(default=0, ge=0)   # bows: the Strength the bow is built for
    # Minimums to wield without penalty (Str / Dex / Martial Arts; 0 = none).
    min_strength: int = Field(default=0, ge=0)
    min_dexterity: int = Field(default=0, ge=0)
    min_martial_arts: int = Field(default=0, ge=0)
    # 0 = mundane. `artifact_rating`: Artifact dots to start with it. `attunement`:
    # motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    resources_cost: int = Field(default=0, ge=0)
    notes: str = ""                        # special cases (e.g. charge damage)
    tags: list[str] = Field(default_factory=list)
    # The page that prints this row. None when no page is known. ⚠ None, not
    # `Source()`, which names "Core". Read site: the public wiki (`ui/wiki_view`).
    source: Optional[Source] = None


class ArtifactType(BaseModel):
    """One entry of the rated-artifact catalogue (data/artifacts.json).

    It holds the standalone artifacts, and the artifacts that also have a row in
    weapons.json or armor.json. `rating` is the primary printed rating, and the
    default on a pick. `rating_notes` holds a printed range ("• or •••")."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    rating: int = Field(ge=1, le=5)
    rating_notes: str = ""                  # e.g. "• or •••", "• to •••••"
    # Core p.344: motes to commit. Copied onto a new `character.ArtifactEntry`.
    #
    # ⚠ Set a nonzero value for standalone Wonders only. A row that duplicates a
    # weapons.json or armor.json entry keeps 0: the gear row has the value.
    #
    # ⚠ 0 can also mean "not transcribed". The backfill is not done.
    attunement: int = Field(default=0, ge=0)
    description: str = ""                   # short, human-vetted from the source page
    source: str = ""                        # e.g. "MF p.279"
    # Manacle and Coin p.125: the cost in Resources dots (decision 0017). A different
    # scale from `rating` (core p.342). 0 = no printed price.
    resources_cost: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)   # kind: tool/communication/weapon/...
    # The Background that pays for this entry. A Hearthstone (pp.338-340) uses the
    # Manse rating, not the p.131 Artifact budget. Read through
    # `engine.artifacts.purchasable_with_artifact`.
    background: str = "artifact"            # "artifact" | "manse"
    # The Merit id that this entry needs (Book of Three Circles pp.25-27; PG p.24;
    # human's ruling). "" = no Merit.
    #
    # ⚠ The id is data only: no module outside `engine/merits.py` may name a Merit id
    # (decision 0011, and a test greps for it). Read sites:
    # `engine.artifacts.purchasable_with_artifact` (excludes these),
    # `engine.artifacts.purchasable_artifacts` (adds them when the Merit is held) and
    # `engine.validate.check_artifacts`.
    requires_merit: str = ""
