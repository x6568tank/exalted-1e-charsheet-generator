"""
models/rules/traits.py — the Merits and Flaws, the Natures, the trait reference
text, the Virtue Flaws, the roll definitions, and the magical materials.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ._base import AbilityName, AttributeName, Source, VirtueName
from .backgrounds import BackgroundPointLimit, TraitRequirement


class MeritFlaw(BaseModel):
    """One purchasable Merit or Flaw.

    ⚠ Deliberately INERT (decision 0011): it carries the printed text, the cost and
    the prerequisites, and NOTHING about what a Merit does. Effects live in
    `engine.merits.merits_and_flaws_calc`, keyed by id, so a new Merit with no
    mechanical effect needs data only. The catalogue spans the general M&F chapter and
    the Thaumaturgy Merits (Player's Guide pp.120-122).

    Shape notes:

      * `cost` is the printed point value. Oathbound Magic has no single cost — it is
        a Flaw whose value depends on the oath sworn — so `cost_options` carries the
        named tiers and `cost` stays 0. A purchase then names its tier.
      * `kind` is "merit" or "flaw". A FLAW's cost is a bonus-point GRANT, not a spend;
        the calc, not this model, decides the sign.
      * `repeatable_by` names the axis a repeatable Merit varies along ("attribute
        group" for The Flow of Essence, which may be taken once per Physical/Social/
        Mental). Empty = take it once.
      * `prerequisites` are other MeritFlaw ids. Non-Merit prerequisites that this
        build cannot yet express (Celestial Travel Permit needs "Celestial Patron of at
        least 2", a Background) go in `prerequisite_note` as printed text, so the
        requirement is shown to the player and simply not machine-checked.
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    # "merit" | "flaw" | "either". A few entries are printed as both — "VARIABLE COST
    # MERIT OR FLAW" (Mutation, Favor) and Eternal Vow's "3-PT. MERIT OR 1-PT. FLAW" —
    # and which side applies is the PLAYER's choice, recorded on the purchase
    # (`MeritFlawPurchase.taken_as`), not fixed by the catalogue.
    kind: str = "merit"
    category: str = ""                     # "Supernatural" / "Social" / ... as printed
    cost: int = 0                          # printed point value; 0 when cost_options is used
    cost_options: dict[str, int] = Field(default_factory=dict)   # named tier -> points
    # Per-splat cost overrides, {exalt_type: {tier: points}}. The general chapter is
    # full of these — "(1- OR 2-PT. MERIT, 1-PT. FOR LUNARS)", "(5-PT. MERIT, 3-PT.
    # FOR EXALTED)" — and they are real mechanical differences, not flavour, so the
    # price a character pays depends on their splat. Inner key "" means the splat has
    # a single fixed price regardless of the tiers the default offers. Empty for a
    # Merit that costs the same for everyone.
    cost_options_by_exalt_type: dict[str, dict[str, int]] = Field(default_factory=dict)
    # The same shape keyed by CASTE id, which outranks the splat override. Only
    # Brigid's Heir needs it ("5-PT. MERIT, 4-PT. FOR TWILIGHT CASTE", p.30) — the one
    # price in 87 entries that keys on caste rather than splat.
    cost_options_by_caste: dict[str, dict[str, int]] = Field(default_factory=dict)
    # Per-SIDE price for a `kind: "either"` entry, {"merit": N, "flaw": N} — Eternal
    # Vow is "3-PT. MERIT OR 1-PT. FLAW" (p.30). Empty when both sides price alike or
    # are variable (Mutation, Favor).
    cost_by_kind: dict[str, int] = Field(default_factory=dict)
    # A Merit whose price the page does not fix at all ("VARIABLE COST MERIT",
    # "VARIABLE POINT FLAW") — the value is agreed with the Storyteller and stored on
    # the PURCHASE, not here. Distinct from cost_options, which is a printed menu.
    variable_cost: bool = False
    # The printed cost line, verbatim. Every entry carries it, because a few qualifiers
    # cannot be modelled at all — a per-CASTE price ("4-PT. FOR TWILIGHT CASTE"), a
    # RELATIVE one ("1-PT. LESS FOR EXALTED") — and dropping them would lose printed
    # rules. The UI shows it, so the Storyteller always sees what the book actually
    # says even where the engine cannot price it.
    cost_note: str = ""
    # Splats this entry is restricted to, as printed ("LUNARS ONLY", "CELESTIAL
    # EXALTED ONLY"). Empty = open to all. Display + validation.
    exalt_types: list[str] = Field(default_factory=list)
    # Splats this entry is CLOSED to, as printed — the negative of `exalt_types`.
    # Prodigy is "not available to Solars, Abyssals or Lunars (who already reach these
    # limits as part of their Exaltation)" and "Alchemical Exalted may not take this
    # Merit at all" (p.21). A restriction is inert data like a cost or a prerequisite,
    # so it belongs here rather than in engine.merits.
    barred_exalt_types: list[str] = Field(default_factory=list)
    # CasteDefinition ids this entry is closed to — the same restriction one level
    # down. Beacon of Power is open to every splat but "Night and Day Caste Exalted
    # may not take this Flaw" (p.41), the two castes whose whole point is concealment.
    # Caste ids are unique across splats, so no splat qualifier is needed.
    barred_castes: list[str] = Field(default_factory=list)
    # Origins this entry is restricted TO — one level down from barred_castes, for a
    # heritage that splits along the origin axis. The Fae-Blooded's "nobles only"
    # (Prince of Chaos, Transcendent Dream Shape) / "commoners only" (Goblin Body),
    # where both are the same caste (fae-blooded) distinguished by origin (human,
    # 2026-08-02). Empty = open to every origin of the caste. Enforced beside
    # barred_castes in both the validation and the picker, so a UI that hides on this
    # can never offer something validation rejects.
    required_origins: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)       # other MeritFlaw ids
    # A floor on the SPLAT's starting Essence, as opposed to a character trait. Weak
    # Essence is "6-PT." and its entire cost is reducing starting Essence to 1, so a
    # splat that already starts at 1 would collect the points for nothing: "Other
    # magical beings may take this Flaw, provided that they normally have a starting
    # Essence of 2" (p.41). 0 = no floor. Read against `ChargenBudgets.essence_start`.
    min_starting_essence: int = 0
    # Splat bars that apply to ONE option of a menu rather than to the whole entry.
    # Prodigy is barred to Solars/Abyssals/Lunars/Alchemicals only for the half that
    # grants a Favored Ability — "not available to Solars, Abyssals or Lunars (who
    # already reach these limits)" — while its +2 "increased aptitude" half is
    # explicitly open to "characters who innately gain Favored Abilities as part of
    # character creation", which is exactly those splats (p.20-21, ruled 2026-07-31).
    # {tier: [exalt_type, ...]}. An entry barred at EVERY tier is barred outright.
    tier_barred_exalt_types: dict[str, list[str]] = Field(default_factory=dict)
    prerequisite_note: str = ""            # printed prereq this build cannot check
    # Rated traits required before this entry may be bought, keyed by TIER — "" is the
    # requirement every tier carries, and a named tier adds its own. Innocuous is why:
    # "Characters must have Appearance 2 in order to purchase this version" applies to
    # the two-point version and not the four-point one.
    #
    # The value is AND-of-OR, the same shape `Charm.prerequisites` uses and for the same
    # reason: Cache is "Resources 4+ OR Salary 2+" (p.25). Every inner list is one OR
    # group; every group must be satisfied.
    trait_prerequisites: dict[str, list[list[TraitRequirement]]] = Field(default_factory=dict)
    # A trait that caps how many TIMES this entry may be taken — Alternative Divination's
    # "characters may not purchase this Merit more times than their Occult rating"
    # (PG p.24). A repeat limit, not a rating floor, so it is its own field. "" = no
    # limit beyond `repeatable_by`.
    max_purchases_from_trait: str = ""
    # A repeat limit that varies by ORIGIN — the Fae-Blooded's Virtue Attunement:
    # "Fae-Blooded born of any of these fae types may only purchase this Merit once.
    # Children of fairy nobles may purchase this Merit up to twice" (PG p.74). {origin:
    # max purchases}; an origin with no entry is uncapped (the page's "once" is the
    # Commoner entry here). Enforced wherever the repeat count is — validate and the
    # post-lock buy path — so a Commoner cannot buy a second copy with XP either.
    max_purchases_by_origin: dict[str, int] = Field(default_factory=dict)
    # Ceilings (or floors) on this entry's point value set by a Background rating —
    # Known Anathema, Damaged Artifact and Debt. Empty for everything else.
    #
    # ⚠ PLURAL because Damaged Artifact prints TWO constraints that measure different
    # things (PG p.38): "may not gain more points from this Flaw than the rating of the
    # artifact it modifies" is per-item, while "characters must have at least one more
    # dot of Artifact than the points obtained" is against the summed Background.
    # Collapsing them into one summed check lets a character with a 4-dot daiklave and
    # 2-dot wings take the full three points against the wings.
    points_limits: tuple[BackgroundPointLimit, ...] = ()
    repeatable_by: str = ""                # "" = once only
    # Whether a purchase of this entry may record STIPULATIONS — Heir Apparent's "add
    # an extra dot to the pool of invested Backgrounds for every major stipulation
    # applied to the Inheritance" (p.24). Inert in exactly the way `repeatable_by` is:
    # it says what a purchase may RECORD, never what the entry does. The UI reads it to
    # decide whether to offer the field, so no id is named outside engine.merits.
    takes_stipulations: bool = False
    # "VARIABLE COST SUPERNATURAL FLAW, THAUMATURGES ONLY" — the Merit is only open to
    # a character who actually holds thaumaturgy. False for everything else.
    thaumaturges_only: bool = False
    description: str = ""
    source: Source = Field(default_factory=Source)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, v: str) -> str:
        if v not in ("merit", "flaw", "either"):
            raise ValueError(f"kind must be merit/flaw/either, got {v!r}")
        return v


class NatureType(BaseModel):
    """A character Nature (Archetype). Narrative only — no mechanical enforcement;
    this is the catalog the editor's Nature dropdown is populated from. The chosen
    value is stored as free text on Character.nature."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""


class AttributeDescription(BaseModel):
    """The reference text for one Attribute (core pp.127-128): the prose, plus the
    printed 1-5 rung ladder keyed by rating.

    `ladder` values carry the printed rung LABEL inline ("Poor: Weakling (dead lift
    80 lbs.)."), because that is how the page reads and the label is worthless apart
    from its text. Display-only — nothing in engine/ reads this."""
    model_config = ConfigDict(frozen=True)

    id: AttributeName
    name: str
    category: str = ""                 # "Physical" / "Social" / "Mental"
    description: str = ""
    ladder: dict[int, str] = Field(default_factory=dict)


class AbilityDescription(BaseModel):
    """The reference text for one Ability (core pp.133-140): the prose, the printed
    sample specialties and the three example feats.

    ⚠ Abilities have NO per-Ability dot ladder in 1e — the rungs are generic and shared
    (`TraitDescriptions.ability_ladder`). What varies per Ability is the difficulty
    tiers: `standard` is 1 success, `challenging` 3, `legendary` 5 (p.132). Linguistics
    prints neither feats nor a specialty LIST — its specialties are a paragraph, which
    is what `specialties_note` holds; both are empty for every other Ability."""
    model_config = ConfigDict(frozen=True)

    id: AbilityName
    name: str
    description: str = ""
    specialties: list[str] = Field(default_factory=list)
    specialties_note: str = ""
    standard: str = ""
    challenging: str = ""
    legendary: str = ""


class VirtueDescription(BaseModel):
    """The reference text for one Virtue (core pp.129-130): the prose, the 1-5 ladder,
    and the two printed lists of what the Virtue aids and what a character must FAIL a
    check against it to do.

    Unlike the Attribute ladder the rungs carry no labels — the page prints bare prose
    per dot, so `ladder` values are that prose verbatim."""
    model_config = ConfigDict(frozen=True)

    id: VirtueName
    name: str
    description: str = ""
    ladder: dict[int, str] = Field(default_factory=dict)
    aids_in: str = ""
    must_fail_check_to: str = ""


class TraitDescriptions(BaseModel):
    """Chapter Four's reference text for the three rated trait families, in one object
    because `ability_ladder` — the generic Novice/Practiced/Competent/Expert/Master
    rungs every Ability shares (p.132) — belongs to no single Ability.

    Purely descriptive: the editor shows it beside the dot tracks so a player can read
    what a rating MEANS. No engine module reads it, and an absent file simply means the
    dot tracks carry no reference text, as they did before."""
    model_config = ConfigDict(frozen=True)

    source: Source = Field(default_factory=Source)
    # Keyed by rating, and unlike the other ladders it starts at 0 — "Unskilled"
    # is a printed rung for Abilities (with its -2 penalty) and has no Attribute or
    # Virtue counterpart.
    ability_ladder: dict[int, str] = Field(default_factory=dict)
    attributes: list[AttributeDescription] = Field(default_factory=list)
    virtues: list[VirtueDescription] = Field(default_factory=list)
    abilities: list[AbilityDescription] = Field(default_factory=list)

    def attribute(self, name: AttributeName) -> AttributeDescription | None:
        """The row for `name`, or None when the file is absent or omits it."""
        return next((a for a in self.attributes if a.id == name), None)

    def ability(self, name: AbilityName) -> AbilityDescription | None:
        """The row for `name`, or None when the file is absent or omits it."""
        return next((a for a in self.abilities if a.id == name), None)

    def virtue(self, name: VirtueName) -> VirtueDescription | None:
        """The row for `name`, or None when the file is absent or omits it."""
        return next((v for v in self.virtues if v.id == name), None)


class VirtueFlawType(BaseModel):
    """One of the book's SAMPLE Virtue Flaws — the Great Curse's named perversions of
    a Virtue (core pp.131-133).

    A catalogue, never a constraint. The book is explicit that these "aren\u2019t the only
    Flaws that an Exalted might develop" and that players should "feel free to work
    together to develop their own", so `Character.virtue_flaw.description` stays free
    text and this list only populates the dropdown beside it — the same contract Nature
    has. `virtue` is which Virtue the Flaw springs from, which is what filters the
    dropdown: a Flaw must belong to a Virtue the character rates 3 or more (p.131), and
    offering a Compassion Flaw to someone who flawed their Valor would be offering an
    illegal pick.

    `limit_break` is the printed Limit Break Condition, kept as its own field rather
    than glued onto the description: it is the half that gets consulted at the table.
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    virtue: VirtueName
    description: str = ""
    limit_break: str = ""                   # the printed Limit Break Condition
    source: str = ""
    notes: str = ""                         # transcription oddities, printed as-is


class PoolKind(str, Enum):
    """What arithmetic a RollDefinition's base term is made of."""
    ATTRIBUTE_ABILITY = "attribute_ability"   # Dexterity + Melee, Wits + Awareness…
    VIRTUE = "virtue"                         # a Virtue check: the Virtue's rating alone
    WILLPOWER = "willpower"                   # a Willpower check: permanent Willpower


class WeaponStat(str, Enum):
    """Which weapon stat, if any, joins the pool. Both are printed as being added
    to the Dexterity + Ability total (core p.327): accuracy "when rolling for
    attacks", defense "when she parries with the weapon"."""
    NONE = "none"
    ACCURACY = "accuracy"
    DEFENSE = "defense"


class RollDefinition(BaseModel):
    """One named roll whose BASE dice pool is trait arithmetic (decision 0016).

    Data, not code: which traits compose a given roll comes off the printed page
    like every other game value, so the roster lives in data/dice_pools.json and
    the engine does nothing but add up what this row names.

    ⚠ This models the BASE pool only. Nothing here describes stunts, difficulty,
    range, multiple-action splitting, or Charm dice — those are Storyteller- or
    play-state-supplied and are out of scope by 0016. `excludes` carries the text
    the surface must show so the number never reads as a final pool.
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: PoolKind = PoolKind.ATTRIBUTE_ABILITY
    category: str = ""                     # UI grouping only: "Combat", "Social"…
    attribute: Optional[AttributeName] = None   # required for ATTRIBUTE_ABILITY
    ability: Optional[AbilityName] = None       # required for ATTRIBUTE_ABILITY
    weapon_stat: WeaponStat = WeaponStat.NONE
    # Armour's mobility penalty is "the number of dice subtracted from the
    # character's dice pools when she tries to do anything requiring agility or
    # physical dexterity. This penalty doesn't normally apply to attack and parry
    # rolls, but does apply to dodge rolls and Athletics rolls for feats that
    # require whole-body agility" (core p.326). So this is a PER-ROLL fact off the
    # page, not a blanket subtraction — attack rolls must not carry it.
    mobility_applies: bool = False
    # Wound penalties apply to essentially every action — p.229's "Order of
    # Modifiers" lists them among the subtractions, and the human confirmed
    # 2026-08-12 that this includes Virtue and Willpower checks. So the default is
    # True and a row opts OUT only where a page says so in as many words: p.233,
    # "wound penalties do not subtract from the character's dice pool for the
    # purposes of this roll" (resisting infection). Do not clear this on a hunch —
    # a silent exemption is a silently inflated pool.
    wound_applies: bool = True
    notes: str = ""
    source: Source = Field(default_factory=Source)

    @model_validator(mode="after")
    def _check_traits(self) -> "RollDefinition":
        if self.kind is PoolKind.ATTRIBUTE_ABILITY:
            if self.attribute is None or self.ability is None:
                raise ValueError(
                    f"roll {self.id!r}: kind 'attribute_ability' needs both "
                    f"`attribute` and `ability`.")
        elif self.attribute is not None or self.ability is not None:
            raise ValueError(
                f"roll {self.id!r}: kind {self.kind.value!r} takes no attribute/ability.")
        if self.weapon_stat is not WeaponStat.NONE and self.kind is not PoolKind.ATTRIBUTE_ABILITY:
            raise ValueError(f"roll {self.id!r}: a weapon stat needs an Attribute + Ability pool.")
        return self


class MagicalMaterial(BaseModel):
    """One of the five magical materials an artifact weapon/armour can be forged
    from (core p.341). Each material resonates with exactly one Exalt type and
    grants its bonus ONLY in the hands of that type — `exalt_type` matches
    Character.exalt_type ("Solar", "Lunar", "Dragon-Blooded", ...). The weapon_*
    deltas are added to the inline weapon's stats when the wielder matches; the
    armor_* deltas do the same for armour (pending the core armour-material page —
    they default to 0). Values come from page images, never from training data."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    exalt_type: str                        # the Exalt the bonus applies for
    weapon_speed: int = 0
    weapon_accuracy: int = 0
    weapon_damage: int = 0
    weapon_defense: int = 0
    # Armour (core p.345-346). Soak deltas are additive; the two negate flags zero
    # out a value rather than add to it (Moonsilver removes mobility penalty,
    # Jade removes fatigue) — these depend on the base, so they can't be a delta.
    armor_soak_lethal: int = 0
    armor_soak_bashing: int = 0
    armor_negate_mobility_penalty: bool = False
    armor_negate_fatigue: bool = False
    notes: str = ""                        # narrative riders (mote drain, damage-roll effects)
