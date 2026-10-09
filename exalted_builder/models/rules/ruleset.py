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
# A purely presentational block of rules tables (the tri-fold GM screen, p.2-3 of
# `images/exaltedscreen-20050917.pdf`), rendered read-only in the GM party page.
# It carries NO game logic and is never referenced by id, keyed, or consumed by the
# engine — it is display text, the digital equivalent of a printed screen. Modeled
# as generic tables so any rules table drops in without a bespoke shape.
# --------------------------------------------------------------------------- #

class RefTable(BaseModel):
    """One titled reference table: a header row (`columns`) over `rows`, each row a
    list of cells matching the columns. `note` is an optional footnote below it.
    A `columns`-less table renders as a bare list of rows (e.g. a step sequence)."""
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
    """The whole rulebook in memory. Charms and spells are indexed by id for
    O(1) prerequisite resolution and load-time link-checking.

    The cost/budget tables are keyed by Exalt type so different splats can carry
    different chargen budgets / XP costs. The shared baseline lives under the
    "default" key; a splat that differs adds an entry under its own exalt_type and
    the `*_for(exalt_type)` accessors fall back to "default" otherwise. (This module
    knows nothing about Character, so the accessors take the exalt_type string, not
    a Character.)"""
    exalts: dict[str, ExaltDefinition] = Field(
        default_factory=lambda: {SOLAR_EXALT.id: SOLAR_EXALT})
    castes: dict[str, CasteDefinition]     # keyed by CasteDefinition.id
    charms: dict[str, Charm]
    spells: dict[str, Spell] = Field(default_factory=dict)
    armor_catalog: dict[str, ArmorType] = Field(default_factory=dict)
    # The mundane price tables (M&C p.123). Ownable `goods` feed the
    # inventory; `service` rows are a reference price list — see GearType.
    gear_catalog: dict[str, GearType] = Field(default_factory=dict)
    weapon_catalog: dict[str, WeaponType] = Field(default_factory=dict)
    artifact_catalog: dict[str, ArtifactType] = Field(default_factory=dict)
    background_catalog: dict[str, BackgroundType] = Field(default_factory=dict)
    nature_catalog: dict[str, NatureType] = Field(default_factory=dict)
    # The sample Virtue Flaws (core pp.131-133), keyed by id. Empty for a ruleset
    # without the file — the flaw stays free text, which is what it was before.
    virtue_flaw_catalog: dict[str, VirtueFlawType] = Field(default_factory=dict)
    material_catalog: dict[str, MagicalMaterial] = Field(default_factory=dict)
    colleges: dict[str, College] = Field(default_factory=dict)   # Astrological Colleges (Sidereal)
    # Martial-arts styles, keyed by MartialArtsStyle.id. The preamble the
    # `martial_arts:<slug>` categories always implied. Cross-splat and inert:
    # ⚠ nothing in engine/ reads this — access is still decided by the CHARM fields
    # (see MartialArtsStyle). Empty when the file is absent, which simply means the
    # picker shows a style tree with no preamble above it, as it always did.
    martial_arts_styles: dict[str, MartialArtsStyle] = Field(default_factory=dict)
    # Named base dice pools (decision 0016), keyed by RollDefinition.id. Cross-splat
    # — every character rolls Dexterity + Melee the same way. Empty when the file is
    # absent, which simply means the pool calculator offers no presets.
    roll_catalog: dict[str, RollDefinition] = Field(default_factory=dict)
    # Dragon-King Paths of Prehuman Mastery (PG pp.177-191), keyed by Path.id. The
    # 60 dot-level powers are ALSO projected into `charms` as virtual rows (see
    # rules_db.load_ruleset) so Combos and the sheet can name them; `paths` is the
    # rated-track truth the real state (Character.paths) lives against. Empty for
    # every splat that ships no paths.json.
    paths: dict[str, Path] = Field(default_factory=dict)
    # Merits & Flaws. Cross-splat like thaumaturgy, and inert data: what a Merit DOES
    # lives in engine.merits, never here (decision 0011). Empty when the file is absent.
    merits_flaws: dict[str, MeritFlaw] = Field(default_factory=dict)
    # Elemental Powers (Core p.296 + GoD p.56, PG p.68), the learnable Charm-like
    # catalogue for Elemental-origin God-Blooded. Empty when the file is absent.
    elemental_powers: dict[str, ElementalPower] = Field(default_factory=dict)
    # Thaumaturgy (Player's Guide CH3). Cross-splat, not keyed by exalt_type:
    # any character may hold these. Empty when data/thaumaturgy*.json is absent.
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
    # Optional read-only GM reference screen (data/st_screen.json). None when absent.
    st_screen: Optional[StScreen] = None
    # Chapter Four's descriptive text for Attributes, Abilities and Virtues
    # (data/trait_descriptions.json). None when absent — the editor then shows the dot
    # tracks with no reference text beside them.
    trait_descriptions: Optional[TraitDescriptions] = None
    # Everything wrong with the user's custom library (custom_content.py), one string
    # per dropped row. Book-data problems are fatal and never reach here — these are
    # non-fatal by design, so the UI shows them as a warning and the app still runs.
    custom_problems: list[str] = Field(default_factory=list)

    # Shields live in armor_catalog tagged "shield" (see ArmorType). These two
    # split it so a caller never has to know the tag string, and so "the armour
    # list" and "the shield list" are one source of truth with two views.
    def body_armor(self) -> list[ArmorType]:
        """Armour proper — everything in the catalogue that is neither a shield nor a
        helm. Both of those are armour ROWS (a character's armour is a list, so worn
        gear needs no second slot), and both are excluded here for the same reason: an
        adversary's "what armour is this NPC wearing" list wants suits, not accessories."""
        return [a for a in self.armor_catalog.values()
                if "shield" not in a.tags and "helm" not in a.tags]

    def shields(self) -> list[ArmorType]:
        """The shields. p.335 describes three; all are mundane."""
        return [a for a in self.armor_catalog.values() if "shield" in a.tags]

    def helms(self) -> list[ArmorType]:
        """The helms (core pp.334-335). Three are printed and the book states outright
        that "all helms are considered mechanically identical" — they are a substitute
        for a striking hair style, carrying no soak, no mobility penalty and no fatigue.
        They are in the catalogue so a character can record what she is wearing, not
        because they do anything."""
        return [a for a in self.armor_catalog.values() if "helm" in a.tags]

    def exalt_for(self, exalt_type: str) -> ExaltDefinition:
        """The ExaltDefinition for `exalt_type`, falling back to Solar if the type
        is unknown (engine.validate.check_exalt_type surfaces the bad value as an
        Issue separately, so derivation still produces a number instead of crashing)."""
        return self.exalts.get(exalt_type) or self.exalts.get("Solar") or SOLAR_EXALT

    def bonus_costs_for(self, exalt_type: str, origin: str = "",
                        upbringing: str = "") -> BonusPointCosts:
        """The bonus-point rates for `exalt_type`, specialised by origin/upbringing on
        the same cascade as `budgets_for`. Nearly every splat prints one table for the
        whole splat, but the Outcaste book's Lost Eggs pay 2/3 per Background dot
        rather than 1/2 (p.160) and a Forest Witch raised by Oreithyia buys Virtues at
        2 and Essence at 8 (p.133) — an origin-level difference in the RATES, not the
        budgets, so it needs its own keyed row."""
        return _keyed_row(self.bonus_costs, exalt_type, origin, upbringing,
                          self.bonus_costs["default"])

    def xp_costs_for(self, exalt_type: str) -> ExperienceCosts:
        return self.xp_costs.get(exalt_type, self.xp_costs["default"])

    def catalogue_backgrounds_for(self, exalt_type: str, origin: str = "",
                                  upbringing: str = "") -> set[str]:
        """The Backgrounds this splat/origin's own book enumerates, lowercased — what
        the dropdown OFFERS. Empty = the book has not been transcribed, and the
        catalogue falls back to the per-Background `exalt_type` filter.

        Not to be confused with `ChargenBudgets.allowed_backgrounds`, which is the
        HARD validation list; see the field comment there.

        ⚠ Walks the `E:o:u` -> `E:o` -> `E` cascade for the first NON-EMPTY list,
        rather than taking the most specific row the way `budgets_for` does. Budget
        rows REPLACE wholesale, so an origin row that does not restate its splat's
        Background list — most of the 30-odd rows — would read as "unrestricted" and
        silently reopen the whole catalogue. Inheriting means an origin authors a list
        only where its book prints a DIFFERENT one (Lookshy p.66 does; the pirates
        do not).
        """
        for key in ([f"{exalt_type}:{origin}:{upbringing}"] if origin and upbringing else []) \
                + ([f"{exalt_type}:{origin}"] if origin else []) + [exalt_type]:
            row = self.budgets.get(key)
            if row is not None and row.catalogue_backgrounds:
                # Entries are lowercased NAMES, or exact `background.*` IDS where a
                # name would be ambiguous. Ids are preserved verbatim (they are
                # already lowercase) so `backgrounds_for` can tell the two apart.
                return {n.strip() if n.strip().startswith("background.")
                        else n.strip().lower()
                        for n in row.catalogue_backgrounds}
        return set()

    def backgrounds_for(self, exalt_type: str, origin: str = "", *,
                        upbringing: str = "", all_available: bool = False) -> list[BackgroundType]:
        """The Backgrounds a character of `exalt_type` may pick from (the editor's
        autofill list). A splat-restricted Background (`exalt_type` set) shows only
        for that splat; a Background listing `exalt_type` in `excluded_exalt_types`
        is hidden from it (DB bar Contacts/Influence/Followers). A Background listing
        the character's effective budget cascade key in `excluded_origins` is hidden
        from that ORIGIN — the ancient-only Savant excludes the modern key
        `"Dragon-Kings"`, never `"Dragon-Kings:ancient"` (barring the ancient row
        would bar the wrong half); one carrying a non-empty `origins` shows ONLY to
        the keys it lists (Lookshy's Arsenal). Universal ones (no restriction) show
        for everyone. Order follows the catalog's insertion order.

        `all_available` is the Storyteller's override, and the books ask for it in so
        many words — the Outcaste's own new-Backgrounds heading (p.66) says
        "Storytellers may wish to introduce them in other games where they are
        appropriate but are under no compulsion to allow characters to take them
        unless the game is about Lookshy Dragon-Blooded." It lifts the SPLAT and
        ORIGIN filters, which are questions of which book a Background came from.
        It deliberately does NOT lift `banned_backgrounds`: those are in-fiction
        prohibitions on a splat that CAN see the Background — the Great Geas forbids
        a Mountain Folk a Cult (CH6 p.234) — not a matter of which book is in play.
        Callers pass `HouseRules.all_backgrounds_available`, never a literal."""
        key = f"{exalt_type}:{origin}" if (origin and f"{exalt_type}:{origin}" in self.budgets) else exalt_type
        # The splat's own enumerated list, when its book has been transcribed. This
        # narrows what is OFFERED; it never makes a typed-in name illegal.
        offered = self.catalogue_backgrounds_for(exalt_type, origin, upbringing)
        out: list[BackgroundType] = []
        for bg in self.background_catalog.values():
            if not all_available:
                # The allow-list answers WHICH NAMES; the splat tag answers WHICH
                # VERSION of a name, and both are needed. Four names are printed
                # twice with different rules — a Dragon-Blooded's Connections is not
                # a Sidereal's — so a name-keyed list alone admits both copies and
                # the dropdown shows "Connections" twice. Where a splat has no
                # transcribed summary the tag is also the whole filter, which is
                # what every splat used before the summaries were read.
                # A universal Background sits outside the per-splat lists entirely —
                # no book enumerates it because no splat owns it.
                if offered:
                    if not bg.universal and not (
                            bg.id in offered
                            or bg.name.strip().lower() in offered):
                        continue
                    # A list entry naming this Background BY ID has already picked
                    # which copy it means, so the splat tag must not then veto it.
                    # That is how the God-Blooded get the twelve Backgrounds their
                    # own chapter grants them out of other splats' books (Whispers
                    # from E:Ab, Renown from E:L, Salary from E:S…): the copies are
                    # tagged for the splat that PRINTED them, and no `exalt_type`
                    # string can say "Abyssal and God-Blooded".
                    if bg.id in offered:
                        out.append(bg)
                        continue
                if bg.exalt_type and bg.exalt_type != exalt_type:
                    continue
                # The two exclusion lists apply EITHER WAY. They are explicit printed
                # bars on a named Background, and a summary that happens to list one
                # does not repeal them — the ancient-only Savant (PG p.176) must stay
                # shut to a modern Dragon King even though both origins inherit the
                # same allow-list.
                if exalt_type in bg.excluded_exalt_types:
                    continue
                if key in bg.excluded_origins:
                    continue
            out.append(bg)
        # A splat's OWN copy of a name displaces the untagged one. ⚠ Both survive the
        # filters above whenever the tag is doing the whole job — a splat with no
        # transcribed summary, or one whose list is keyed by origin and the origin is
        # blank (a save written before the axis existed) — which puts every name in the
        # dropdown twice. Not applied under `all_available`: the Storyteller asked for
        # every book's version, and there the five Artifacts are the point.
        if not all_available:
            owned = {bg.name.strip().lower() for bg in out if bg.exalt_type}
            out = [bg for bg in out
                   if bg.exalt_type or bg.name.strip().lower() not in owned]
        # A Background this origin is BARRED from entirely is not even offered —
        # the Mountain Folk may not take Cult (CH6 p.234: "This Background is
        # explicitly prohibited"). Filtering here (rather than relying on the
        # engine flag) means the dropdown never shows a name the sheet cannot hold.
        banned = {n.strip().lower()
                  for n in self.budgets_for(exalt_type, origin).banned_backgrounds}
        if banned:
            out = [bg for bg in out if bg.name.strip().lower() not in banned]
        return out

    def camps_for(self, exalt_type: str, origin: str = "") -> list[TrainingCamp]:
        """The training camps a character of this splat/origin may attend, in table
        order. Empty for every splat with no camps, which is how the UI decides
        whether to render the picker at all."""
        return [c for c in self.camps.values()
                if c.exalt_type == exalt_type and (not c.origin or c.origin == origin)]

    def callings_for(self, camp_id: str) -> list[Calling]:
        """The Callings offered by one camp, in table order."""
        return [c for c in self.callings.values() if c.camp == camp_id]

    def budgets_for(self, exalt_type: str, origin: str = "",
                    upbringing: str = "") -> ChargenBudgets:
        """The chargen budget for `exalt_type`, optionally specialised by `origin`
        (an intra-splat variant such as Dragon-Blooded Dynastic vs Outcaste) and then
        by `upbringing` (how that origin raised the character — Outcaste book, see
        Character.upbringing). Most specific row wins; see `_keyed_row`.
        (Character-free: takes strings, not a Character, so this module never imports
        the character model.)"""
        return _keyed_row(self.budgets, exalt_type, origin, upbringing,
                          self.budgets["default"])
