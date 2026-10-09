"""
models/rules/__init__.py — the rulebook as data. This file is the public surface of
the package.

These models define the *shape* of static game data: Charms, spells, caste
definitions, and the cost/budget tables. They are loaded once from data/*.json
at startup and treated as immutable at runtime.

Structural validation lives here (an enum is an enum, a coefficient is a
number). Game-legality validation does NOT — it lives in engine.validate,
because legality depends on a *character* and these rules considered together.
This package therefore knows nothing about any Character.

The domain modules, in dependency order (a module imports only modules above it):

    _base        the fixed vocabularies and the shared small models
    charms       Charms, spells, Submodules, Elemental Powers
    castes       castes, heritages, breeds, camps, Callings, Colleges, styles, Paths
    thaumaturgy  Arts, Sciences, Rituals, Formulas
    gear         the equipment catalogue
    backgrounds  Backgrounds, trait requirements, point limits
    traits       Merits and Flaws, Natures, trait text, rolls, materials
    budgets      the cost tables, the chargen budgets, the Exalt definitions
    ruleset      the RuleSet and the Storyteller screen
"""

from __future__ import annotations

# Re-exported, not defined here. `rules.X` is the ONE public path to every
# name. A domain module is an implementation detail, not a second front door.
# tests/test_package_facades.py fails if a caller reads a name that is not here.
#
# ⚠ A monkeypatch on this module does not reach the domain modules. Patch the
# module that defines the name AND each module that reads it.
from ._base import (           # noqa: F401 — re-exported for callers
    AbilityGroupMinimum,
    AbilityMinimum,
    AbilityName,
    AttributeMinimum,
    AttributeName,
    BackgroundBudgetTier,
    CharmType,
    CircleKind,
    DAMAGE_LABELS,
    Damage,
    EssencePoolSpec,
    Source,
    SpellCircle,
    TRACK_CIRCLES,
    VirtueName,
    circle_kind,
)
from .backgrounds import (     # noqa: F401 — re-exported for callers
    BackgroundPointLimit,
    BackgroundType,
    TraitRequirement,
)
from .budgets import (         # noqa: F401 — re-exported for callers
    BackgroundRule,
    BonusPointCosts,
    ChargenBudgets,
    ExaltDefinition,
    ExperienceCosts,
    LinearCost,
    SOLAR_EXALT,
)
from .castes import (          # noqa: F401 — re-exported for callers
    BreedTraits,
    Calling,
    CasteDefinition,
    College,
    GodbloodedHeritage,
    GrantedCharmChoice,
    InnateWeapon,
    MartialArtsStyle,
    Path,
    PathPower,
    TrainingCamp,
)
from .charms import (          # noqa: F401 — re-exported for callers
    Charm,
    CharmCost,
    CharmCountRequirement,
    CharmVariant,
    ElementalPower,
    Spell,
    Submodule,
)
from .gear import (            # noqa: F401 — re-exported for callers
    ArmorType,
    ArmorWeight,
    ArtifactType,
    GearType,
    WeaponType,
)
from .ruleset import (         # noqa: F401 — re-exported for callers
    RefGroup,
    RefTable,
    RuleSet,
    StScreen,
)
from .thaumaturgy import (     # noqa: F401 — re-exported for callers
    Orientation,
    ScienceLevel,
    ThaumaturgicArt,
    ThaumaturgicAspect,
    ThaumaturgicFormula,
    ThaumaturgicRitual,
    ThaumaturgicScience,
)
from .traits import (          # noqa: F401 — re-exported for callers
    AbilityDescription,
    AttributeDescription,
    MagicalMaterial,
    MeritFlaw,
    NatureType,
    PoolKind,
    RollDefinition,
    TraitDescriptions,
    VirtueDescription,
    VirtueFlawType,
    WeaponStat,
)

