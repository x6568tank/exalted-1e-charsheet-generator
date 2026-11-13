"""
models/rules/ruleset.py — the RuleSet: the complete rulebook as one immutable
object, and the Storyteller reference screen.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from .backgrounds import BackgroundType
from .budgets import (SOLAR_EXALT, BonusPointCosts, ChargenBudgets, ExaltDefinition,
                      ExperienceCosts, _keyed_row)
from .castes import (Calling, CasteDefinition, College, MartialArtsStyle, Path,
                     TrainingCamp)
from .charms import Charm, ElementalPower, Spell
from .gear import ArmorType, ArtifactType, GearType, WeaponType
from .thaumaturgy import (ThaumaturgicArt, ThaumaturgicFormula, ThaumaturgicRitual,
                          ThaumaturgicScience)
from .traits import (MagicalMaterial, MeritFlaw, NatureType, RollDefinition,
                     TraitDescriptions, VirtueFlawType)


# --------------------------------------------------------------------------- #
# Storyteller reference screen
#
# The rules tables of the Storyteller screen (p.2-3 of the screen PDF), for display
# in the GM party page. The engine does not read them.
# --------------------------------------------------------------------------- #

class RefTable(BaseModel):
    """One titled table: `columns` over `rows`. `note` is a footnote. A table with no
    `columns` shows as a list of rows."""
    title: str
    columns: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)
    note: str = ""


class RefGroup(BaseModel):
    """A named panel of related tables (e.g. "Combat")."""
    title: str
    tables: list[RefTable] = Field(default_factory=list)


class StScreen(BaseModel):
    """The whole Storyteller reference screen: named groups of tables."""
    title: str = "Storyteller Reference"
    groups: list[RefGroup] = Field(default_factory=list)


class RuleSet(BaseModel):
    """The rulebook in memory. Charms and spells are indexed by id.

    The cost and budget tables are keyed by Exalt type. The "default" key holds the
    common values. The `*_for(exalt_type)` accessors use "default" for an absent key.
    They take strings: this module does not import Character."""
    exalts: dict[str, ExaltDefinition] = Field(
        default_factory=lambda: {SOLAR_EXALT.id: SOLAR_EXALT})
    castes: dict[str, CasteDefinition]     # keyed by CasteDefinition.id
    charms: dict[str, Charm]
    spells: dict[str, Spell] = Field(default_factory=dict)
    armor_catalog: dict[str, ArmorType] = Field(default_factory=dict)
    # M&C p.123. See GearType.
    gear_catalog: dict[str, GearType] = Field(default_factory=dict)
    weapon_catalog: dict[str, WeaponType] = Field(default_factory=dict)
    artifact_catalog: dict[str, ArtifactType] = Field(default_factory=dict)
    background_catalog: dict[str, BackgroundType] = Field(default_factory=dict)
    nature_catalog: dict[str, NatureType] = Field(default_factory=dict)
    # Core pp.131-133, keyed by id.
    virtue_flaw_catalog: dict[str, VirtueFlawType] = Field(default_factory=dict)
    material_catalog: dict[str, MagicalMaterial] = Field(default_factory=dict)
    colleges: dict[str, College] = Field(default_factory=dict)   # Astrological Colleges (Sidereal)
    # Keyed by MartialArtsStyle.id. ⚠ Nothing in engine/ reads this. The Charm fields
    # decide access.
    martial_arts_styles: dict[str, MartialArtsStyle] = Field(default_factory=dict)
    # Decision 0016, keyed by RollDefinition.id.
    roll_catalog: dict[str, RollDefinition] = Field(default_factory=dict)
    # PG pp.177-191, keyed by Path.id. The powers are also virtual rows in `charms`
    # (rules_db.load_ruleset).
    paths: dict[str, Path] = Field(default_factory=dict)
    # Decision 0011. engine.merits gives the effects.
    merits_flaws: dict[str, MeritFlaw] = Field(default_factory=dict)
    # Core p.296, GoD p.56, PG p.68.
    elemental_powers: dict[str, ElementalPower] = Field(default_factory=dict)
    # Player's Guide CH3. Not keyed by exalt_type.
    thaum_arts: dict[str, ThaumaturgicArt] = Field(default_factory=dict)
    thaum_sciences: dict[str, ThaumaturgicScience] = Field(default_factory=dict)
    thaum_rituals: dict[str, ThaumaturgicRitual] = Field(default_factory=dict)
    thaum_formulas: dict[str, ThaumaturgicFormula] = Field(default_factory=dict)
    camps: dict[str, TrainingCamp] = Field(default_factory=dict)  # Training camps (Illuminated Solar)
    callings: dict[str, Calling] = Field(default_factory=dict)    # Callings (Illuminated Solar)
    bonus_costs: dict[str, BonusPointCosts] = Field(
        default_factory=lambda: {"default": BonusPointCosts()})
    xp_costs: dict[str, ExperienceCosts] = Field(
        default_factory=lambda: {"default": ExperienceCosts()})
    budgets: dict[str, ChargenBudgets] = Field(
        default_factory=lambda: {"default": ChargenBudgets()})
    # data/st_screen.json. None if absent.
    st_screen: Optional[StScreen] = None
    # data/trait_descriptions.json. None if absent.
    trait_descriptions: Optional[TraitDescriptions] = None
    # The errors of the custom library (custom_content.py), one string per dropped
    # row. Not fatal: the UI shows them as a warning (decision 0012).
    custom_problems: list[str] = Field(default_factory=list)

    # Shields and helms are rows of armor_catalog, by tag (see ArmorType).
    def body_armor(self) -> list[ArmorType]:
        """Return the armor rows that are not a shield and not a helm."""
        return [a for a in self.armor_catalog.values()
                if "shield" not in a.tags and "helm" not in a.tags]

    def shields(self) -> list[ArmorType]:
        """Return the shields (p.335)."""
        return [a for a in self.armor_catalog.values() if "shield" in a.tags]

    def helms(self) -> list[ArmorType]:
        """Return the helms (core pp.334-335). They have no game effect."""
        return [a for a in self.armor_catalog.values() if "helm" in a.tags]

    def exalt_for(self, exalt_type: str) -> ExaltDefinition:
        """Return the ExaltDefinition of `exalt_type`. Return Solar for an unknown
        type: engine.validate.check_exalt_type reports it."""
        return self.exalts.get(exalt_type) or self.exalts.get("Solar") or SOLAR_EXALT

    def bonus_costs_for(self, exalt_type: str, origin: str = "",
                        upbringing: str = "") -> BonusPointCosts:
        """Return the bonus-point rates of `exalt_type`, by the `budgets_for` key
        order (origin rates: p.160, p.133)."""
        return _keyed_row(self.bonus_costs, exalt_type, origin, upbringing,
                          self.bonus_costs["default"])

    def xp_costs_for(self, exalt_type: str) -> ExperienceCosts:
        return self.xp_costs.get(exalt_type, self.xp_costs["default"])

    def catalogue_backgrounds_for(self, exalt_type: str, origin: str = "",
                                  upbringing: str = "") -> set[str]:
        """Return the lowercased Backgrounds that the book of this splat/origin lists:
        the dropdown list. Empty = use the `exalt_type` filter.

        Not `ChargenBudgets.allowed_backgrounds`, which is HARD validation.

        ⚠ Returns the first NON-EMPTY list of `E:o:u` -> `E:o` -> `E`, not the most
        specific row. Else an origin row with no list opens all Backgrounds (p.66).
        """
        for key in ([f"{exalt_type}:{origin}:{upbringing}"] if origin and upbringing else []) \
                + ([f"{exalt_type}:{origin}"] if origin else []) + [exalt_type]:
            row = self.budgets.get(key)
            if row is not None and row.catalogue_backgrounds:
                # Entries are lowercased NAMES, or `background.*` IDS. Ids are kept
                # as written.
                return {n.strip() if n.strip().startswith("background.")
                        else n.strip().lower()
                        for n in row.catalogue_backgrounds}
        return set()

    def backgrounds_for(self, exalt_type: str, origin: str = "", *,
                        upbringing: str = "", all_available: bool = False) -> list[BackgroundType]:
        """Return the Backgrounds that the dropdown shows for `exalt_type`, in
        catalogue order.

        Filters: `exalt_type` on the Background; `excluded_exalt_types`;
        `excluded_origins` against the budget key (⚠ Savant excludes the modern key
        `"Dragon-Kings"`, not `"Dragon-Kings:ancient"`); `origins`; universal entries
        pass.

        `all_available` (p.66) lifts the splat and origin filters. ⚠ It does not lift
        `banned_backgrounds` (CH6 p.234). Pass `HouseRules.all_backgrounds_available`,
        not a literal."""
        key = f"{exalt_type}:{origin}" if (origin and f"{exalt_type}:{origin}" in self.budgets) else exalt_type
        # The list of the splat, if transcribed. It narrows the dropdown only.
        offered = self.catalogue_backgrounds_for(exalt_type, origin, upbringing)
        out: list[BackgroundType] = []
        for bg in self.background_catalog.values():
            if not all_available:
                # The list gives the names. The splat tag gives the copy of a name
                # that exists two times. With no list, the tag is the only filter.
                # A universal Background is in no list.
                if offered:
                    if not bg.universal and not (
                            bg.id in offered
                            or bg.name.strip().lower() in offered):
                        continue
                    # An id entry selects the copy. The splat tag must not refuse it.
                    if bg.id in offered:
                        out.append(bg)
                        continue
                if bg.exalt_type and bg.exalt_type != exalt_type:
                    continue
                # The exclusion lists always apply (PG p.176).
                if exalt_type in bg.excluded_exalt_types:
                    continue
                if key in bg.excluded_origins:
                    continue
            out.append(bg)
        # A copy of the splat replaces the untagged copy of the same name.
        # ⚠ Else a name shows two times when the tag is the only filter. Not
        # applied under `all_available`.
        if not all_available:
            owned = {bg.name.strip().lower() for bg in out if bg.exalt_type}
            out = [bg for bg in out
                   if bg.exalt_type or bg.name.strip().lower() not in owned]
        # Remove a banned Background (CH6 p.234).
        banned = {n.strip().lower()
                  for n in self.budgets_for(exalt_type, origin).banned_backgrounds}
        if banned:
            out = [bg for bg in out if bg.name.strip().lower() not in banned]
        return out

    def camps_for(self, exalt_type: str, origin: str = "") -> list[TrainingCamp]:
        """Return the training camps of this splat/origin, in table order. Empty =
        the UI shows no picker."""
        return [c for c in self.camps.values()
                if c.exalt_type == exalt_type and (not c.origin or c.origin == origin)]

    def callings_for(self, camp_id: str) -> list[Calling]:
        """Return the Callings of one camp, in table order."""
        return [c for c in self.callings.values() if c.camp == camp_id]

    def budgets_for(self, exalt_type: str, origin: str = "",
                    upbringing: str = "") -> ChargenBudgets:
        """Return the chargen budget of `exalt_type`, for `origin` and `upbringing`.
        The most specific row wins (`_keyed_row`)."""
        return _keyed_row(self.budgets, exalt_type, origin, upbringing,
                          self.budgets["default"])
