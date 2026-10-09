"""
models/rules/castes.py — the caste and the origin models: castes, Godblooded
heritages, Lunar breeds, granted Charm choices, Cult camps and Callings, Sidereal
Colleges, martial-arts styles, and Dragon-King Paths.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import (AbilityGroupMinimum, AbilityMinimum, AbilityName, AttributeName,
                    CharmType, EssencePoolSpec, Source)
from .charms import CharmCost


class GodbloodedHeritage(BaseModel):
    """The heritage-keyed mechanics of one God-Blooded heritage (Player's Guide CH2,
    pp.45-60). Attached to a `CasteDefinition` via `CasteDefinition.heritage_traits`
    — a heritage IS the Godblooded caste slot (`caste_noun: "Heritage"`) — and None on
    every caste of every other splat, so the shared class carries one optional block
    rather than six flat fields (see docs/status/godblooded.md).

    What the five heritages actually differ on (God / Demon / Ghost / Half-Caste / Fae):

    * `unlocked_essence` — the Awakened-Essence pool formula, per-heritage (p.66):
      God/Demon/Ghost = Ess×5 + WP×2 + ΣVirtues; Half-Caste = Ess×5 + ΣVirtues;
      Fae = Ess×8. Mirrors ExaltDefinition.unlocked_essence (the mortal shape), keyed
      by heritage because the formula varies within one splat.
    * `charm_access` — which OTHER splat's Charm catalogue this heritage learns
      "exactly as their parents" (p.47): Ghost-Blooded → ["Ghost"] (the Arcanoi);
      Half-Caste → the parent Exalt's catalogue (`charm_access_parent`); Fae → none.
    * `magic_track` / `magic_track_by_parent` — the ONE magic track this heritage may
      be initiated into, restricting which `grants_circle` Charms it can hold (p.48:
      "Terrestrial Circle Sorcery is available to all the remaining heritages save
      Ghost-Blooded and Abyssal Half-Caste. Conversely, only these heritages may learn
      Shadowlands Circle Necromancy."). "" = no restriction beyond Charm access.
    * `attribute_pools` — the Half-Caste 6/5/4 override (p.47; prose wins over the
      p.50 summary's 6/5/3). None = the splat's 6/4/3.
    * `allowed_backgrounds` — the heritage-gated specialised Backgrounds (p.50), e.g.
      Abyssal Command / Underworld Manse / Whispers for Ghost-Blooded. Lowercased
      NAMEs, matching ChargenBudgets.allowed_backgrounds.
    * `heritage_power` — the per-heritage perception power (p.51-60). Display-only."""
    model_config = ConfigDict(frozen=True)

    unlocked_essence: Optional[EssencePoolSpec] = None
    charm_access: list[str] = Field(default_factory=list)
    # When True, `charm_access` is ignored and the heritage learns the catalogue of the
    # character's PARENT Exalt type instead (Half-Caste, p.47: "The descendents of
    # Exalted learn the Charms of their parents"). The parent rides the `Character.origin` axis (the Origin dropdown);
    # every other heritage leaves this False and uses the static `charm_access` list.
    charm_access_parent: bool = False
    magic_track: str = ""
    # The same restriction keyed by the PARENT Exalt type, for the Half-Caste — whose
    # track is not a property of the heritage but of who their parent was (p.48: only
    # Ghost-Blooded and the ABYSSAL Half-Caste get necromancy; every other parent gets
    # sorcery). Read exactly like `magic_track`, which it overrides when the parent
    # has an entry. Empty for every heritage without a parent axis.
    magic_track_by_parent: dict[str, str] = Field(default_factory=dict)
    attribute_pools: Optional[tuple[int, int, int]] = None
    allowed_backgrounds: list[str] = Field(default_factory=list)
    heritage_power: str = ""
    # The Origin-dropdown choices this heritage offers, when it keys off the origin
    # axis at all. Two heritages do: the Half-Caste's origin is their parent Exalt type
    # (Solar/DB/Lunar/Sidereal/Abyssal, p.47) and the Fae-Blooded's is Noble vs
    # Commoner (the nobility axis p.73-79 gates powers on, human 2026-08-02). Empty
    # for every heritage that leaves Character.origin blank (Ghost-Blooded, and the
    # God/Demon-Blooded until their pages land). The editor renders the Origin
    # dropdown from this, so the options travel with the heritage.
    origin_options: list[str] = Field(default_factory=list)
    # Heritage-level Charm bars, the parallel to ExaltDefinition.barred_charm_ids: a
    # Charm this heritage may never hold even when charm access would reach it. For the
    # Half-Caste this is the "no perfect defense or persistent scene-length defense"
    # list (p.47) plus the Sidereal Maiden-approval Charms — a single list is enough
    # because a Half-Caste can only reach their own parent's catalogue, so a bar from
    # another parent is unreachable anyway. Checked first in both charm gates.
    barred_charm_ids: list[str] = Field(default_factory=list)
    # Whether this heritage may hold its OWN splat's native Charms at all — the mirror
    # of ExaltDefinition.charms_available. The one False heritage is the Fae-Blooded,
    # "The children of the Fair Folk do not use Charms" (p.47), and it is a FLAG, not a
    # deny-list, because a deny-list of today's God-Blooded Arcanoi silently admits the
    # ninth one the day God/Demon-Blooded's spirit Charms are authored. With the flag
    # False the native catalogue is closed wholesale and only the explicit grants
    # survive: the p.234 Terrestrial martial arts, the foreign `charm_access`
    # catalogue. Checked where the native match happens in charm_matches_splat.
    charms_available: bool = True
    # The repeatable Gift-granting Charm for a parent type, and its purchase cap — keyed
    # by `Character.origin` (the parent Exalt type). Only the Lunar parent sets these (a Lunar Half-Caste
    # may take up to TWO alternate forms via Deadly Beastman Transformation, p.47).
    # Empty for every other heritage, which has no gift economy.
    gift_charm_ids: dict[str, str] = Field(default_factory=dict)
    gift_caps: dict[str, int] = Field(default_factory=dict)
    # The repeatable Ox-Body Technique for a parent type, keyed by `Character.origin`.
    # A Half-Caste learns their PARENT's Charms (p.47), and the God-Blooded's own Ox-Body
    # is the SPIRIT/ARCANOS version for the spirit-descended heritages — so a Half-Caste
    # uses their parent Exalt's Ox-Body instead (the splat-level `ox_body_charm_id` stays
    # the God-Blooded one for the ghost-blooded heritage). Empty for every other heritage.
    ox_body_charm_ids: dict[str, str] = Field(default_factory=dict)
    # A heritage's OWN Ox-Body, when it is not the splat-level one: God/Demon-Blooded
    # use the SPIRIT Ox-Body (PG p.83 lists Ox-Body Technique as "(Spirit, Arcanos)";
    # human's ruling 2026-08-07 — copied into the Spirit catalogue, the Arcanos version
    # left to Ghost-Blooded). Checked after `ox_body_charm_ids` and before the splat
    # fallback. Empty on every heritage that keeps the splat-level id.
    ox_body_charm_id: str = ""


class InnateWeapon(BaseModel):
    """One natural weapon a Dragon-King breed attacks with (PG pp.167-174). The four
    fields are the printed table's Spd / Acc / Dmg / Def; `damage_type` carries the
    L/B off the damage column. Display-only — decision 0008 keeps attack derivation
    out, so these never feed a roll."""
    model_config = ConfigDict(frozen=True)

    name: str
    speed: int = 0
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0


class BreedTraits(BaseModel):
    """The breed-keyed mechanics of one Dragon-King breed (PG pp.167-174). Attached
    to a `CasteDefinition` via `CasteDefinition.breed_traits` — a breed IS the
    Dragon-King caste slot (`caste_noun: "Breed"`) — and None on every caste of every
    other splat, exactly the `heritage_traits` pattern.

    * `element` — the breed's element ("air"/"wood"/"fire"/"water"); the two Paths
      whose `Path.element` matches are the breed's auto-favoured Breed Paths.
    * `attribute_bonuses` — free dots ON TOP of the attribute pools (p.167: "The
      Pterok gain +2 to Dexterity and +2 to Perception"). They do not consume the
      pool, and the effective total (pool-spent + bonus) may pass 5, but each
      effective dot above 5 is bought with bonus points at the attribute rate
      (p.175: "Even after these modifiers are applied, Dragon Kings cannot have any
      Attributes higher than 5 without spending bonus or experience points").
      ⚠ Read against the EFFECTIVE value, not the pool spend; charged in
      bonus_point_breakdown.
    * `innate_soak_bashing` / `innate_soak_lethal` — the breed's innate armour
      (Pterok +1B/1L, Raptok +3B/3L, Anklok +6B/6L, Mosok +4B/4L), folded into
      derive.soak. Read together with ExaltDefinition.stamina_adds_to_lethal_soak
      (p.165: Dragon-King Stamina does not add to lethal soak).
    * `bonus_health_levels` — wound-penalty levels the breed adds to the health
      track (Anklok and Mosok get one extra -0 level, p.171/174).
    * `innate_weapons` — the breed's natural weapons with their printed Spd/Acc/Dmg/Def
      (see `InnateWeapon`); display-only (decision 0008 keeps attack derivation out).
    """
    model_config = ConfigDict(frozen=True)

    element: str = ""
    attribute_bonuses: dict[AttributeName, int] = Field(default_factory=dict)
    innate_soak_bashing: int = Field(default=0, ge=0)
    innate_soak_lethal: int = Field(default=0, ge=0)
    bonus_health_levels: list[int] = Field(default_factory=list)
    innate_weapons: list[InnateWeapon] = Field(default_factory=list)


class CasteDefinition(BaseModel):
    """One caste (Solar) / aspect (Dragon-Blooded) / etc. `id` is the stable
    lowercase key it is stored under in RuleSet.castes and on Character.caste
    (e.g. "dawn"); `label` is the display name ("Dawn"); `exalt_type` names the
    splat it belongs to, so a caste can be matched to a character's Exalt type."""
    model_config = ConfigDict(frozen=True)

    id: str                                # stable lowercase key, e.g. "dawn"
    exalt_type: str = "Solar"              # the splat this caste belongs to
    label: str                             # display name, e.g. "Dawn"
    caste_abilities: list[AbilityName] = Field(default_factory=list)  # the fixed caste abilities
    # Lunar castes have Caste ATTRIBUTES instead of Caste Abilities (p.90-91): Full
    # Moon = Strength/Dexterity/Stamina, Changing Moon = Charisma/Manipulation/
    # Appearance, No Moon = Perception/Intelligence/Wits — each set is exactly one
    # of engine.validate.ATTRIBUTE_CATEGORIES. Empty for Ability-caste splats
    # (Solar, Dragon-Blooded, Abyssal). A caste sets caste_abilities OR
    # caste_attributes, never both.
    caste_attributes: list[AttributeName] = Field(default_factory=list)
    # Flat XP discount this caste gets on a new spell whose circle is priced via
    # ExperienceCosts.new_spell_by_circle (Lunar No Moon: 2, p.251 — "12/15, minus 2
    # for a No Moon"). 0 (the default) for every caste that gets no such discount,
    # including the other Lunar castes. Ignored entirely by splats that price spells
    # flatly (they use the Occult-Caste/Favoured discount instead).
    spell_cost_discount: int = 0
    # Per-caste ability floors, unioned with the exalt-type-keyed budget minimums.
    # The Sidereal per-house minimums (p.98) differ by caste, unlike the DB Dynastic
    # floor which is the same for every aspect, so they live here rather than on
    # ChargenBudgets. Empty for every caste with no house-specific floor.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Group-sum floors on this CASTE (the "•• divided among Craft Abilities" half of
    # the Mountain Folk Artisan's College of Divine Enlightenment schooling, CH6
    # p.230) — the parallel of `required_min_abilities`. Empty for every caste whose
    # printed floors are all per-ability (every caste but the Artisan).
    required_min_ability_groups: list[AbilityGroupMinimum] = Field(default_factory=list)
    # The Eclipse Caste generalist rule (core p.127): with a willing tutor, this
    # caste may learn OTHER splats' Charms, at `foreign_charm_xp_multiplier` times
    # the normal experience. False for every other caste, so the ability is data,
    # not a splat check — the Abyssal Moonshadow parallel is a one-line data change.
    # The chargen half of the rule ("may not start the game knowing" them without
    # Storyteller permission) is Character.house_rules.st_foreign_charms.
    foreign_charms: bool = False
    # Only meaningful when foreign_charms is True. p.127: "Such Charms cost double
    # the normal experience to learn (usually 20 points) and use." The *use* half
    # (mote costs) is play-time math and deliberately not modelled.
    foreign_charm_xp_multiplier: int = Field(default=2, ge=1)
    # Alchemical crossover (Autochthonians p.90): an Eclipse/Moonshadow learning an
    # Alchemical Charm gains a General Charm Slot with it (the 20-XP path, priced via
    # foreign_charm_xp_multiplier), but may instead add the Charm to their Panoply
    # (no Slot) for this flat rate. None = the caste has no Alchemical-crossover Panoply
    # rate. Only meaningful alongside foreign_charms.
    foreign_panoply_charm_xp: Optional[int] = None
    description: str = ""                   # a quick flavour blurb for the caste
    anima_powers: str = ""
    # The heritage-keyed mechanics of a God-Blooded heritage (which IS the Godblooded
    # caste slot — `caste_noun: "Heritage"`), or None for every caste of every other
    # splat. ONE optional block rather than six flat fields so the shared class is not
    # widened for a single splat; named `heritage_traits` rather than `godblooded` so
    # the Exalted-God-Blooded crossover can reuse it if ever built. See GodbloodedHeritage.
    heritage_traits: Optional[GodbloodedHeritage] = None
    # The breed-keyed mechanics of a Dragon-King breed (which IS the Dragon-King
    # caste slot — `caste_noun: "Breed"`), or None for every caste of every other
    # splat. The same optional-block pattern as `heritage_traits`. See BreedTraits.
    breed_traits: Optional[BreedTraits] = None


class GrantedCharmChoice(BaseModel):
    """One player choice within a TrainingCamp's free-Charm package.

    The Cult of the Illuminated grants free Charms in three shapes, and a camp lists
    whichever it needs:

    * `from_categories` — "two Charms from ONE of the following four martial arts"
      (p.90). The player picks a single category from the list, then `pick` Charms
      inside it. The single-category restriction is the whole point of this shape.
    * `fixed_sets` — "one of the following pairs of Charms" (p.90). The player takes
      exactly one whole set, verbatim. `pick` is ignored (a set is all-or-nothing).
    * `pool_categories` + `pool_charms` — "three (3) Charms from Ebon Shadow Style,
      Falling Blossom Style, Praying Mantis Style, Snake Style, Tiger Style or
      Ox-Body Technique" (p.96, the Dragon-Blooded package at the Sequestered
      Tabernacle). `pick` Charms from ONE FLAT POOL, in any combination — the
      sentence, unlike the Solar camps', does not say "from one of".

    The pool shape is not `from_categories` with the restriction relaxed, and the two
    must not be merged: it also has to hold a pool that MIXES styles with a named
    Ability Charm (Ox-Body Technique), which a category list cannot express. The pool
    is the union of every Charm in `pool_categories` and every id in `pool_charms`;
    naming the categories rather than enumerating their Charms means a style gaining
    a Charm later widens the package automatically, the way the printed text does.

    A set may offer alternates for one member where a house rule swaps a Charm
    (Spirit Strengthens the Skin replaces Iron Skin Concentration under Exalted
    Power Combat); those are authored as two separate sets, since the choice is the
    player's, not a rules branch the engine should pick."""
    model_config = ConfigDict(frozen=True)
    label: str = ""                                 # display, e.g. "Martial arts style"
    pick: int = Field(default=0, ge=0)              # how many Charms from the chosen category
    from_categories: list[str] = Field(default_factory=list)
    fixed_sets: list[list[str]] = Field(default_factory=list)
    pool_categories: list[str] = Field(default_factory=list)
    pool_charms: list[str] = Field(default_factory=list)

    def pool_charm_ids(self, charms: dict) -> list[str]:
        """Every Charm id this choice's flat pool offers, given the Charm catalogue.
        Empty for the other two shapes, which is what keeps their branches unchanged."""
        if not (self.pool_categories or self.pool_charms):
            return []
        out = [cid for cid, charm in charms.items()
               if charm.category in self.pool_categories]
        out += [cid for cid in self.pool_charms if cid not in out]
        return out


class TrainingCamp(BaseModel):
    """A training camp: an origin-scoped package of chargen requirements attached to
    a character alongside (not instead of) their Caste.

    Introduced for the Cult of the Illuminated (Solar, p.89-93), where an
    Illuminated Solar picks one of two camps — the Sequestered Tabernacle or Kether
    Rock — and that choice sets Ability floors and a free-Charm package. It is a
    THIRD axis beyond splat and caste, which is why it needs its own table rather
    than living on CasteDefinition (any caste may attend either camp) or on
    ChargenBudgets (the budget row is per-origin, and both camps share one origin).

    `origin` scopes the camp to a `Character.origin` value so the camp list a
    character may choose from is data-driven; `exalt_type` scopes it to a splat."""
    model_config = ConfigDict(frozen=True)
    id: str                                         # stable lowercase key
    exalt_type: str = "Solar"
    origin: str = ""                                # Character.origin this camp belongs to
    label: str
    description: str = ""
    # Ability floors this camp's training regimen imposes (p.89). Unioned with the
    # budget's own minimums exactly as CasteDefinition.required_min_abilities is, and
    # AbilityMinimum's OR semantics already express Kether Rock's "either Archery •
    # or Brawl •" with no new machinery.
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # Free Charms every graduate of this camp receives, by id. These do NOT come out
    # of the chargen Charm pool and do NOT count toward the Caste/Favored minimum —
    # they are granted, not picked. The character must still meet each Charm's own
    # minimum Ability/Essence ("As usual, the Solar must meet the minimum
    # requirements to gain these Charms", p.90).
    granted_charms: list[str] = Field(default_factory=list)
    # Player choices layered on top of `granted_charms`, resolved onto
    # Character.granted_charms.
    granted_charm_choices: list[GrantedCharmChoice] = Field(default_factory=list)
    # The page that prints this row. None when no page is known. ⚠ None, not
    # `Source()`, which names "Core". Read site: the public wiki (`ui/wiki_view`).
    source: Optional[Source] = None


class Calling(BaseModel):
    """A Calling: the character's role within their organisation, which discounts a
    named set of Abilities and Charms at BOTH chargen and in play.

    Cult of the Illuminated, p.90 and p.102. Each TrainingCamp offers three. The
    discount stacks with the Caste/Favored discount and is a DISCOUNT AXIS, not a
    second Favored list — a Calling Ability is not thereby Favored, so it does not
    count toward the Caste/Favored dot minimum.

    The rates live on BonusPointCosts/ExperienceCosts (per exalt type), not here, so
    a later organisation with a different discount reuses this table unchanged."""
    model_config = ConfigDict(frozen=True)
    id: str                                         # stable lowercase key
    exalt_type: str = "Solar"
    camp: str = ""                                  # TrainingCamp.id that offers it
    label: str
    description: str = ""
    abilities: list[AbilityName] = Field(default_factory=list)
    # Calling Charms, by id. A Charm here is discounted, never granted.
    charms: list[str] = Field(default_factory=list)
    # Calling Abilities named with a parenthetical focus on the page — Paladin's
    # "Craft (War)" — record the focus so the Craft-as-per-focus-Ability machinery
    # can match the right Craft instance. Keyed by AbilityName value.
    ability_focus: dict[str, str] = Field(default_factory=dict)
    # The page that prints this row. None when no page is known. ⚠ None, not
    # `Source()`, which names "Core". Read site: the public wiki (`ui/wiki_view`).
    source: Optional[Source] = None


class College(BaseModel):
    """One Astrological College (Sidereal, p.220-235) — a rated Advantage bought at
    chargen with its own point pool, distinct from Abilities. `house` is the caste id
    of the Maiden that governs it (journeys/serenity/battles/secrets/endings), so the
    "≥4 dots in the Colleges of his Maiden" rule (p.98) matches `house` to
    Character.caste directly; `house_label` is the printed astrological house name
    (e.g. Serenity's colleges sit in the "House of Leisure"). Sidereal-only today;
    other splats simply ship no colleges.json and never reference one."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    house: str                              # caste id of the governing Maiden
    house_label: str = ""                   # printed astrological house name (display)


class MartialArtsStyle(BaseModel):
    """One martial-arts STYLE — the thing the `martial_arts:<slug>` Charm categories
    have always implied without ever existing as an entity.

    It holds what the page prints ABOVE the Charm list: the style's `Type:` line,
    its prose, and its style-level rules (the "Weapons and Armor" sidebar, and
    oddities like Celestial Monkey's Virtue ceiling).

    ⚠ **`tier` is DISPLAY ONLY. Nothing in engine/ may read it** (a test enforces
    this). It is the same fact the Charms' `open_to_tiers` / `open_to_all` already
    carry, and the moment two descriptions of one rule are both live they disagree —
    the shape decision 0011 exists to prevent. Who may learn a style is decided by
    the CHARM fields, exactly as before; this entity changed no access rule.
    The human's scoping call, 2026-08-14: preamble and Type only.
    """
    model_config = ConfigDict(frozen=True)
    id: str                                 # "style.righteous-devil"
    name: str                               # "Righteous Devil Style", as printed
    category: str                           # "martial_arts:righteous-devil"
    # The printed `Type:` word ("Terrestrial" / "Celestial" / "Sidereal"). A plain
    # str, not an enum: the set of printed values is an observation about the pages
    # read so far, and closing it from memory is what decision 0001 forbids.
    tier: str = ""
    preamble: str = ""                      # the style's prose, as printed
    # Style-level RULES, one entry per printed rule, kept out of `preamble` because
    # a Storyteller needs to find them rather than read past them. [] for a style
    # whose page carries only flavour.
    mechanics: list[str] = Field(default_factory=list)
    source: Source = Field(default_factory=Source)


class PathPower(BaseModel):
    """One dot-level power of a Dragon-King Path (PG pp.177-191). Each Path has
    exactly six, one per dot 1..6; the dot IS the Path rating at which the power is
    gained ("Each Path must be learned in a fixed order" p.177). `cost` is the
    in-play activation cost (CharmCost — use `raw` for the variable-cost powers like
    "1 mote per 1L damage"), `type` reuses CharmType, `text` is the printed prose."""
    model_config = ConfigDict(frozen=True)

    dot: int = Field(ge=1, le=6)
    name: str
    type: CharmType
    cost: CharmCost = Field(default_factory=CharmCost)
    duration: str = "Instant"
    keywords: list[str] = Field(default_factory=list)
    text: str = ""


class Path(BaseModel):
    """One of the ten Dragon-King Paths of Prehuman Mastery (PG pp.177-191) — a
    rated trait (dots 1-6) bought in fixed order, distinct from Abilities and with
    its own chargen pool, BP/XP tables and Essence gate (see docs/status/
    dragon-kings.md and the plan). `element` is the Path's element ("air"/"wood"/
    "fire"/"water"/"earth"); the two Paths whose element matches a breed's
    `BreedTraits.element` are that breed's auto-favoured Breed Paths. `powers` are
    the six dot-level powers, in order."""
    model_config = ConfigDict(frozen=True)

    id: str                                  # stable lowercase key, e.g. "dk.celestial-air"
    name: str                                # e.g. "Celestial Air"
    element: str = ""                        # "air" | "wood" | "fire" | "water" | "earth"
    element_label: str = ""                  # display, e.g. "Air"
    description: str = ""
    powers: list[PathPower] = Field(default_factory=list)
