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

from pydantic import BaseModel, Field, field_validator

from .rules import AbilityName, AttributeName, VirtueName


# Legacy saves stored the caste as its capitalised display name ("Dawn"); the
# caste is now referenced by its stable lowercase id ("dawn"). Map the old Solar
# values forward on load so pre-Phase-2 saves keep working.
_LEGACY_CASTE_IDS = {
    "Dawn": "dawn", "Zenith": "zenith", "Twilight": "twilight",
    "Night": "night", "Eclipse": "eclipse",
}


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


class Array(BaseModel):
    """An Alchemical Array (p.89) — the Chosen of Autochthon's analogue of a Combo.
    Links Attribute-based Charms into a permanent pattern. Cost: 1 bonus point per
    Charm at chargen, or experience equal to the sum of the Charms' minimum Attribute
    ratings. Unlike a Combo, ANY Attribute-based Charms may be linked (the instant-
    duration / one-Simple / one-Extra-Action limits constrain the *integrated
    Combos* an Array grants, not the Array itself); supernatural martial arts
    (Ability-based) may NOT join. An Array reduces its Charms' combined installation
    cost to three-fourths, rounded up (engine.validate applies this), and it grants
    every legal integrated Combo of its member Charms for 1 Willpower. Only splats
    that use the Charm Slot system build Arrays (Eclipse/Moonshadow may not, p.90)."""
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


class BeastmanGiftPurchase(BaseModel):
    """One purchase of the repeatable Deadly Beastman Transformation Charm
    (Lunar, p.124-127). `gifts` are the Gift variant keys (rules.CharmVariant.key
    on that Charm) chosen with this purchase — 2 on the first purchase, 1 on each
    purchase after (rules.Charm.variant_picks_first_purchase/
    variant_picks_per_purchase). The +Attribute points each purchase also grants
    are intentionally NOT tracked here: they only apply while the Lunar is
    actually in hybrid form, the same transient, play-time-only territory as
    combat/attack derivation, which this engine deliberately does not model."""
    gifts: list[str] = Field(default_factory=list)


class SubmodulePurchase(BaseModel):
    """One purchased Alchemical submodule (p.89) — the `key` of a rules.Submodule on
    the Charm named by `charm_id`. Bought with bonus points at chargen or experience
    post-lock; the parent Charm must be known. There is no rating — a submodule is
    owned or not."""
    charm_id: str
    key: str


class AnimalForm(BaseModel):
    """One shape in a Lunar's Form Library — an animal whose heart's blood they have
    taken and can wear. Deliberately FREE-FORM and unvalidated: it is a narrative
    record, not a rated trait. There is no catalogue of animals to reference, no
    cost, no cap checked here, and it never enters chargen validation or the XP
    audit — same isolation as the play-state tracker, for the same reason."""
    name: str = ""
    notes: str = ""       # habitat, stats the ST assigned, when/where it was taken


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
    arrays: list[Array] = Field(default_factory=list)
    submodules: list[SubmodulePurchase] = Field(default_factory=list)
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)
    beastman_gifts: list[BeastmanGiftPurchase] = Field(default_factory=list)
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
    bare 0..10 counter (Limit Break at 10).

    `renown` is Lunar-only (p.112-115): four Storyteller-adjudicated 0-100 scores
    (Succor/Mettle/Cunning/Glory, one per Virtue), gained and lost through GM-called
    Virtue checks during play — nothing like a dotted/XP-priced trait, so it lives
    here rather than in chargen/advancement. `face` (0-10, "Urrach-ya" to
    "Shahan-ya") is likewise entirely Storyteller-adjudicated: total Renown sets a
    floor, but rank also requires freeform GM-judged feats (p.113) this tracker
    does not and should not try to check. Both are meaningless (left at their
    defaults) for non-Lunar characters and for Casteless Lunars, who may not
    possess Renown (p.108) — this is not enforced here; it's the ST's call."""
    health: list[Optional[Damage]] = Field(default_factory=list)
    motes_personal_spent: int = Field(default=0, ge=0)
    motes_peripheral_spent: int = Field(default=0, ge=0)
    willpower_spent: int = Field(default=0, ge=0)
    limit: int = Field(default=0, ge=0, le=10)
    # Alchemical-only (CH2 p.69-71): the TEMPORARY half of Clarity, the Alchemical
    # replacement for Limit. Storyteller-adjudicated exactly as Limit is — gained by
    # suppressing Virtues or going without human contact, shed by Compassion rolls and
    # channelled Virtues — so it is tracked, not computed. The PERMANENT half is
    # derived (Essence above 5 + installed Charms) and deliberately NOT stored here;
    # see engine.derive.clarity. Unlike Limit, Clarity never "breaks" or resets at 10.
    clarity_temporary: int = Field(default=0, ge=0, le=10)
    renown: dict[str, int] = Field(
        default_factory=lambda: {"succor": 0, "mettle": 0, "cunning": 0, "glory": 0})
    face: int = Field(default=0, ge=0, le=10)

    @field_validator("renown")
    @classmethod
    def _check_renown_range(cls, v: dict[str, int]) -> dict[str, int]:
        for k, rating in v.items():
            if not (0 <= rating <= 100):
                raise ValueError(f"renown[{k!r}] = {rating}; must be 0-100.")
        return v


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
    caste: str = "dawn"                     # CasteDefinition.id into ruleset.castes
    # Intra-splat origin variant, when a splat's chargen budget depends on more than
    # its Exalt type. Dragon-Blooded: "dynastic" (Realm-raised: 35 ability dots + the
    # schooling minimums) vs "outcaste" (25 dots, no minimums), p.150-151. "" = the
    # splat's default budget (Solar ignores this). Lunar: "casteless" is a coupled
    # pair with `caste` (see engine.validate.check_lunar_casteless_consistency) —
    # unlike Dragon-Blooded, it's one condition on two fields, not an independent axis.
    origin: str = ""
    concept: str = ""
    nature: str = ""
    anima: str = ""
    # Lunar Form Library (the "Totem" field on the 1e Lunar sheet). Narrative only —
    # see AnimalForm. Empty/unused for every other splat; old saves load with both
    # at their defaults.
    totem: str = ""
    animal_forms: list[AnimalForm] = Field(default_factory=list)

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
    # The player-chosen Favored ATTRIBUTES — used only by splats whose attribute
    # budget is partitioned by caste/favored attribute set rather than by category
    # (Alchemical, p.60: 3 Favored Attributes drawing on the 6-dot secondary pool,
    # distinct from the caste's Caste Attributes). Empty for every category-budget
    # splat (Solar, Dragon-Blooded, Abyssal, Lunar), whose attributes are budgeted
    # by prioritized category and never read this field.
    favored_attributes: list[AttributeName] = Field(default_factory=list)
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
    # Alchemical Panoply (p.89): Charms the character OWNS but has NOT installed in a
    # Charm Slot — bought post-lock for the flat "New Charm" XP cost, or via the Vats
    # Background. They occupy no Slot and are not installed; a Vat refit swaps them in
    # and out (refit itself is play-time, not modelled). Empty for every non-slot
    # splat. Kept OUT of `charms` (which is the installed set the Slot rules count).
    retainer_charms: list[str] = Field(default_factory=list)
    combos: list[Combo] = Field(default_factory=list)
    # Alchemical Arrays (p.89) — see the Array model. Empty for every other splat.
    arrays: list[Array] = Field(default_factory=list)
    # Alchemical submodules (p.89) — per-Charm upgrades. Empty for every other splat.
    submodules: list[SubmodulePurchase] = Field(default_factory=list)
    spells: list[str] = Field(default_factory=list)           # Spell ids into the RuleSet
    # Repeatable Ox-Body Technique: one record per purchase (it is therefore NOT in
    # `charms`). Each carries the chosen variant + its inline health levels.
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)
    # Alchemical Charm Slots (p.88-89): the character's TOTAL General / Dedicated
    # slot counts, base free slots plus any bought with BP/XP (each bought slot
    # comes with a free Charm). None = uninitialised, treated as the splat's free
    # base from ChargenBudgets — so an untouched Alchemical has the base 4/4 and a
    # non-slot splat simply never reads these. Dedicated slots may hold only a
    # Charm keyed to a Caste or Favored Attribute; General slots hold any.
    general_charm_slots: Optional[int] = None
    dedicated_charm_slots: Optional[int] = None
    # Repeatable Deadly Beastman Transformation (Lunar only, p.124-127): one record
    # per purchase, each carrying the Gift(s) chosen with that purchase. Also NOT
    # in `charms`, same reasoning as ox_body.
    beastman_gifts: list[BeastmanGiftPurchase] = Field(default_factory=list)

    weapons: list[Weapon] = Field(default_factory=list)
    armor: list[Armor] = Field(default_factory=list)
    health_bonus_levels: list[HealthLevel] = Field(default_factory=list)

    # Storyteller permission to START play knowing another splat's Charms — the
    # chargen half of the Eclipse generalist rule (core p.127). Post-lock the rule
    # needs only a willing tutor, which is narrative, so this gates chargen picks
    # only. Meaningless unless the caste sets CasteDefinition.foreign_charms.
    st_foreign_charms: bool = False

    # --- lifecycle / accounting ---
    chargen_locked: bool = False
    chargen_snapshot: Optional[ChargenSnapshot] = None
    xp_earned: int = Field(default=0, ge=0)
    xp_log: list[XpEntry] = Field(default_factory=list)

    # --- play-state (separate layer; never enters chargen/XP validation) ---
    play: Optional[PlayState] = None

    @field_validator("caste", mode="before")
    @classmethod
    def _migrate_legacy_caste(cls, v: object) -> object:
        """Map a pre-Phase-2 capitalised Solar caste ("Dawn") to its id ("dawn").
        Any other value passes through untouched."""
        return _LEGACY_CASTE_IDS.get(v, v) if isinstance(v, str) else v
