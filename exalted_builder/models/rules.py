"""
models/rules.py — the rulebook as data.

These models define the *shape* of static game data: Charms, spells, caste
definitions, and the cost/budget tables. They are loaded once from data/*.json
at startup and treated as immutable at runtime.

Structural validation lives here (an enum is an enum, a coefficient is a
number). Game-legality validation does NOT — it lives in engine.validate,
because legality depends on a *character* and these rules considered together.
This module therefore knows nothing about any Character.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# --------------------------------------------------------------------------- #
# Fixed vocabularies
# --------------------------------------------------------------------------- #

class AttributeName(str, Enum):
    STRENGTH = "strength"
    DEXTERITY = "dexterity"
    STAMINA = "stamina"
    CHARISMA = "charisma"
    MANIPULATION = "manipulation"
    APPEARANCE = "appearance"
    PERCEPTION = "perception"
    INTELLIGENCE = "intelligence"
    WITS = "wits"


class AbilityName(str, Enum):
    # Dawn
    ARCHERY = "archery"
    BRAWL = "brawl"
    MARTIAL_ARTS = "martial_arts"
    MELEE = "melee"
    THROWN = "thrown"
    # Zenith
    ENDURANCE = "endurance"
    PERFORMANCE = "performance"
    PRESENCE = "presence"
    RESISTANCE = "resistance"
    SURVIVAL = "survival"
    # Twilight
    CRAFT = "craft"
    INVESTIGATION = "investigation"
    LORE = "lore"
    MEDICINE = "medicine"
    OCCULT = "occult"
    # Night
    ATHLETICS = "athletics"
    AWARENESS = "awareness"
    DODGE = "dodge"
    LARCENY = "larceny"
    STEALTH = "stealth"
    # Eclipse
    BUREAUCRACY = "bureaucracy"
    LINGUISTICS = "linguistics"
    RIDE = "ride"
    SAIL = "sail"
    SOCIALIZE = "socialize"


class VirtueName(str, Enum):
    COMPASSION = "compassion"
    CONVICTION = "conviction"
    TEMPERANCE = "temperance"
    VALOR = "valor"


class CharmType(str, Enum):
    REFLEXIVE = "Reflexive"
    SUPPLEMENTAL = "Supplemental"
    SIMPLE = "Simple"
    EXTRA_ACTION = "Extra Action"
    PERMANENT = "Permanent"
    SPECIAL = "Special"        # e.g. Ox-Body Technique (repeatable, permanent effect)


class SpellCircle(str, Enum):
    # Sorcery circles — ascend earth->Heaven (core p.191).
    TERRESTRIAL = "Terrestrial"
    CELESTIAL = "Celestial"
    SOLAR = "Solar"
    # Necromancy circles — the death-magic mirror of sorcery (Abyssal p.223). They
    # DESCEND in the fiction (toward Oblivion) but grow in power Shadowlands->
    # Labyrinth->Void, so they are ordered low-to-high power like the sorcery ones.
    SHADOWLANDS = "Shadowlands"
    LABYRINTH = "Labyrinth"
    VOID = "Void"
    # Alchemical weaving protocols — the Machine God's sorcery-analogue (Autochthonians
    # CH4). Man-Machine ~ Terrestrial Circle, God-Machine ~ Celestial Circle in power.
    # Gated ONLY by which Weaving Engine Charm is installed, exactly as the sorcery/
    # necromancy circles are gated by their initiation Charms.
    MAN_MACHINE = "Man-Machine"
    GOD_MACHINE = "God-Machine"


class CircleKind(str, Enum):
    """Which of the magic disciplines a circle belongs to. Matches
    ExaltDefinition.magic_track. The tracks never cross-grant: a known Sorcery Charm
    unlocks only sorcery circles, a Weaving Engine only weaving circles, etc.
    (Abyssal p.223; Autochthonians CH4 — "Non-Alchemicals cannot learn weaving")."""
    SORCERY = "sorcery"
    NECROMANCY = "necromancy"
    WEAVING = "weaving"


# The three circles of each magic track, ordered ascending in power. Keyed by the
# magic_track string on ExaltDefinition, so a splat's picker shows the right columns
# (Solars: Sorcery; Abyssals: Necromancy). The engine's circle-access logic is
# track-agnostic (exact-match + the initiation-Charm prerequisite chain) — this table
# is for presentation and track membership, not access.
TRACK_CIRCLES: dict[str, tuple["SpellCircle", ...]] = {
    CircleKind.SORCERY.value: (SpellCircle.TERRESTRIAL, SpellCircle.CELESTIAL, SpellCircle.SOLAR),
    CircleKind.NECROMANCY.value: (SpellCircle.SHADOWLANDS, SpellCircle.LABYRINTH, SpellCircle.VOID),
    CircleKind.WEAVING.value: (SpellCircle.MAN_MACHINE, SpellCircle.GOD_MACHINE),
}


def circle_kind(circle: "SpellCircle") -> str:
    """The magic track ('sorcery' | 'necromancy') a circle belongs to."""
    for kind, circles in TRACK_CIRCLES.items():
        if circle in circles:
            return kind
    return CircleKind.SORCERY.value


# --------------------------------------------------------------------------- #
# Charms & spells
# --------------------------------------------------------------------------- #

class Source(BaseModel):
    book: str = "Exalted 1e Core"
    page: Optional[int] = None


class Damage(str, Enum):
    """A mark in a health-track box. The 1e shorthand: '/' bashing, 'x' lethal,
    '*' aggravated. (Empty boxes are None.)

    Shared vocabulary: the character marks damage in its health track, and a Charm
    cost may name which KIND of health level it spends. It lives here, with the other
    enums character.py already imports, rather than in a module of its own.
    """
    BASHING = "/"
    LETHAL = "x"
    AGGRAVATED = "*"


# Display names, for anywhere the shorthand glyph alone would not read.
DAMAGE_LABELS = {
    Damage.BASHING: "bashing",
    Damage.LETHAL: "lethal",
    Damage.AGGRAVATED: "aggravated",
}


class CharmCost(BaseModel):
    """Activation cost paid in play. Distinct from the XP/BP cost to *learn* the
    Charm, which is character-relative and computed in engine.costs."""
    motes: int = Field(default=0, ge=0)
    willpower: int = Field(default=0, ge=0)
    health: int = Field(default=0, ge=0)   # health levels spent by the Charm
    # WHICH kind of health level `health` spends. None means the page does not say —
    # which is the case for every one of the 52 printed Charms with a health cost, so
    # it is the default and renders exactly as before. Set it only where a source
    # names the type, or on homebrew where the author decides.
    health_type: Optional[Damage] = None
    committed: bool = False                # committed motes reduce the pool until released
    raw: str = ""                          # display string; authoritative for variable costs


class CharmVariant(BaseModel):
    """One selectable package for a repeatable Charm. Ox-Body Technique: each
    purchase picks exactly one variant, `health_levels` are the wound-penalty
    levels it grants (e.g. [0] or [-1, -2, -2]), no prerequisites, `max_purchases`
    is always 1 (repeat purchases just pick a variant again, whether same or
    different). Deadly Beastman Transformation's Gifts (Lunar, p.126-127) are the
    second use of this shape: `health_levels` stays empty, `prerequisites` is an
    AND-of-OR over OTHER variant `key`s of the SAME Charm (mirrors Charm.
    prerequisites but scoped to this Charm's own variant menu, e.g. Glue-Foot
    Climbing needs Spider-Foot Climbing needs Bestial Reflexes-or-Lightning
    Speed), and `max_purchases` is 2 for the handful of Gifts that explicitly
    permit taking them twice (Bestial Reflexes, Enhanced Senses)."""
    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    health_levels: list[int] = Field(default_factory=list)
    prerequisites: list[list[str]] = Field(default_factory=list)
    max_purchases: int = 1
    description: str = ""


class AbilityMinimum(BaseModel):
    """A required minimum in one of a set of Abilities (OR semantics): the character
    must have at least `rating` in AT LEAST ONE of `abilities`. A single-element list
    is a specific-ability floor. Used for the Dragon-Blooded Dynastic schooling
    minimums (p.151) and the Sidereal per-house minimums (p.98) — these are a floor
    spent from the pool, NOT free extra dots."""
    model_config = ConfigDict(frozen=True)
    abilities: list[AbilityName]
    rating: int = Field(ge=1)


class AttributeMinimum(BaseModel):
    """The Attribute mirror of AbilityMinimum: the character must have at least
    `rating` in AT LEAST ONE of `attributes` (OR semantics; a single-element list is a
    specific-Attribute floor).

    Its own type rather than a widened AbilityMinimum, because AbilityMinimum is also
    the Dragon-Blooded/Sidereal chargen schooling minimum — those consumers budget
    ABILITY dots and must not be handed an Attribute.

    Distinct from `Charm.min_attribute`, which RETARGETS the primary `min_ability`
    gate at an Attribute for the Attribute-keyed splats (Lunar, p.122) and therefore
    feeds pricing and the Caste/Favoured discount. These are pure additional
    requirements and feed neither, exactly like `extra_min_abilities`.
    """
    model_config = ConfigDict(frozen=True)
    attributes: list[AttributeName]
    rating: int = Field(ge=1)


class Submodule(BaseModel):
    """One purchasable upgrade to a single Alchemical Charm (p.89). A submodule
    permanently improves its parent Charm; the character has access to it whenever
    that Charm is installed. Dual cost: `bp_cost` bonus points at chargen OR
    `xp_cost` experience post-lock (the page prints both, e.g. "2 bonus points or 6
    experience points"). May carry its own minimum Essence and/or a minimum
    Attribute gate (e.g. the omnidextrous submodule "requires Wits 3+")."""
    model_config = ConfigDict(frozen=True)
    key: str                               # stable within the parent Charm
    name: str
    bp_cost: int = Field(default=0, ge=0)
    xp_cost: int = Field(default=0, ge=0)
    min_essence: int = Field(default=1, ge=1)
    min_attribute: str = ""                # optional extra Attribute gate (AttributeName value)
    min_attribute_rating: int = Field(default=0, ge=0)
    description: str = ""


class CharmCountRequirement(BaseModel):
    """"Any three Lore Charms" — a breadth prerequisite, counting Charms the character
    holds in a `category` rather than naming ids (see `Charm.prerequisite_counts`).

    The Charm requiring it is never counted toward its own requirement. `label` is an
    optional display override for the category noun; when empty the presenters use the
    category itself, which reads correctly for every Ability ("any 3 Occult Charms").
    """
    model_config = ConfigDict(frozen=True)

    category: str
    count: int = Field(default=1, ge=1)
    label: str = ""


class Charm(BaseModel):
    model_config = ConfigDict(frozen=True)  # rules data is immutable at runtime

    id: str
    name: str
    category: str                          # an AbilityName value, a Martial Arts style, or "sorcery"
    exalt_type: str = "Solar"              # the splat that can learn it; filters the picker
    # The elemental tree a Charm belongs to, for splats that organise Charms by
    # element (Dragon-Blooded: "Air"/"Earth"/"Fire"/"Water"/"Wood"). "" for splats
    # with no elemental axis (Solar). Authored from the page's element headings; it
    # groups the DB picker and drives the Immaculate "one elemental tree" constraint.
    element: str = ""
    # An Immaculate Order Charm — a Fivefold Dragon Method martial-arts Charm
    # (Dragon-Blooded splatbook, ch.6). These are the Charms a DB may take the
    # *Immaculate* chargen path with (5 from one elemental tree, p.151) instead of
    # the standard 7 Dragon-Blooded Charms; they also cost the Immaculate BP row.
    # False for ordinary ability Charms (all Solar Charms). Set together with
    # `element` on each Immaculate martial-arts Charm.
    immaculate: bool = False
    # A Charm learnable by ANY splat, not just `exalt_type`'s owners. Set on the
    # Terrestrial (Immaculate Dragon) martial-arts styles: nothing in 1e bars a
    # Solar from learning Terrestrial Martial Arts (it just needs a trainer). For a
    # non-DB learner such a Charm is priced/counted as an ordinary Martial Arts
    # Charm — the Immaculate chargen *package* stays Dragon-Blooded-only (see
    # engine.validate._immaculate_path, which also gates on exalt_type).
    open_to_all: bool = False
    # Exalt *tiers* that may learn this Charm on top of `exalt_type` — the middle
    # ground between one splat and `open_to_all`. Matched against
    # ExaltDefinition.tier ("Terrestrial"/"Celestial"). Set ["Celestial"] on the
    # Hungry Ghost Style (Abyssal) and Five-Dragon Style (Dragon-Blooded), which any
    # Celestial Exalt may learn; adding Lunars/Sidereals as Celestial splats grants
    # them these styles with no data or code change. Like `open_to_all`, a Charm
    # learned this way is an ordinary Martial Arts Charm for the learner.
    open_to_tiers: list[str] = Field(default_factory=list)
    type: CharmType
    min_ability: int = Field(default=0, ge=0)
    # For splats whose Charms are Attribute-keyed rather than Ability-keyed (Lunar,
    # p.122): the AttributeName value `min_ability` is the required rating in. ""
    # (default) means the Charm gates on `category`'s Ability as usual. A Charm
    # should set at most one of min_attribute / an Ability-resolving category.
    min_attribute: str = ""
    # For splats whose Charms are VIRTUE-keyed (ghosts, E:Ab p.234-253 — every one of
    # the 56 Arcanoi prints exactly one "Minimum Compassion/Conviction/Temperance/
    # Valor" alongside its Minimum Essence, and none prints an Ability at all). The
    # VirtueName value `min_ability` is the required rating in, exactly as
    # `min_attribute` works — the third and last of the three keyings.
    #
    # Reusing `min_ability` as the rating rather than adding a fourth number is
    # deliberate, and is the same trade `min_attribute` made: everything downstream
    # (pricing, the picker's tree layout, Combo cost) already keys off `min_ability`,
    # so a Charm keyed a new way costs nothing to price. The field is misnamed for
    # this case and correctly named for the common one.
    #
    # A Charm sets AT MOST ONE of min_virtue / min_attribute / an Ability-resolving
    # category. `validate._min_trait_rating` resolves them in that order.
    min_virtue: str = ""
    min_essence: int = Field(default=1, ge=1)
    # ADDITIONAL Ability minimums beyond `min_ability`, for the rare Charm the page
    # gates on more than one Ability. Ascendant Battle Visage (Cult of the Illuminated,
    # p.102) is the first: "Minimum Brawl: 5 / Minimum Endurance: 5".
    #
    # `min_ability` stays the PRIMARY gate — the one derived from `category` — because
    # everything downstream keys off it: the Caste/Favoured and Calling discounts, XP
    # and BP pricing, Combo cost, and the picker's tree layout. These extras are pure
    # REQUIREMENT checks and deliberately feed none of that: a Brawl Charm that also
    # needs Endurance 5 must not become cheaper for a character whose Caste Ability is
    # Endurance.
    #
    # Reuses AbilityMinimum, so each entry is an independent AND whose inner list is an
    # OR ("Brawl 5 AND Endurance 5", or hypothetically "AND (Melee 3 OR Thrown 3)").
    # Empty for all but a handful of Charms.
    extra_min_abilities: list[AbilityMinimum] = Field(default_factory=list)
    # ADDITIONAL Attribute minimums, the same shape over Attributes ("Stamina 3 AND
    # (Wits 4 OR Perception 4)"). Empty for every printed Charm in the build — no 1e
    # page gates a Charm on more than one Attribute — and added for homebrew, which
    # freely wants combinations the books never printed. Enforced and displayed
    # through the same two functions as extra_min_abilities, so it cannot drift.
    extra_min_attributes: list[AttributeMinimum] = Field(default_factory=list)
    # Alchemical Charms only (p.88-91): the Personal Essence committed to *install*
    # the Charm in a Charm Slot (distinct from `cost`, the activation cost paid in
    # play). Committed for as long as the Charm is installed, so the sum over a
    # character's installed Charms is capped by the Personal pool — enforced at
    # chargen for Alchemicals. 0 for every non-Alchemical Charm.
    installation_cost: int = Field(default=0, ge=0)
    # Repeatable Charms (Ox-Body Technique; Deadly Beastman Transformation, Lunar
    # p.124-127): may be bought once per dot of this Ability/Attribute (the cap),
    # each purchase choosing from `variants`. The special value "essence" caps on
    # Character.essence_rating instead (Deadly Beastman Transformation: "no more
    # times than he has points of Essence", p.124 — Essence isn't an Ability or
    # Attribute, so it can't resolve through the normal AbilityName/AttributeName
    # lookup validate.py otherwise uses). None = not repeatable.
    repeatable_cap_ability: Optional[str] = None
    # The God-Blooded Ox-Body Technique (PG p.83) caps on CONVICTION: "Characters
    # cannot purchase this Charm more times than their Conviction rating" — a Virtue,
    # which `repeatable_cap_ability` cannot express (Ability/Attribute/"essence" only).
    # Mirrors the `min_virtue` retarget pattern: the VirtueName value, else None.
    repeatable_cap_virtue: Optional[str] = None
    variants: list[CharmVariant] = Field(default_factory=list)
    # How many variants a single purchase selects. Ox-Body: always 1 (the default
    # for both fields below). Deadly Beastman Transformation (p.124): the FIRST
    # purchase grants 2 Gifts, every purchase after grants 1.
    variant_picks_first_purchase: int = 1
    variant_picks_per_purchase: int = 1
    # AND-of-ORs: the character must satisfy every inner group; a group is
    # satisfied if ANY of its ids is known. A flat list of single-id groups is
    # the common "all of these required" case.
    prerequisites: list[list[str]] = Field(default_factory=list)
    # BREADTH prerequisites: "any three Lore Charms" (Aspect Book: Air/Earth, five
    # Charms). A COUNT over a category, which `prerequisites` cannot express — it is
    # AND-of-OR over ids, and encoding "3 of 11" as three groups each listing all
    # eleven would be satisfied three times over by a single owned Charm. Every entry
    # is an independent AND, like extra_min_abilities. Empty for all but a handful.
    prerequisite_counts: list[CharmCountRequirement] = Field(default_factory=list)
    cost: CharmCost = Field(default_factory=CharmCost)
    duration: str = "Instant"
    keywords: list[str] = Field(default_factory=list)
    # Set on the circle-initiation Charms (e.g. Terrestrial/Celestial/Solar Circle
    # Sorcery). Lets engine.validate gate known spells on a known initiation Charm of
    # their circle. Track-agnostic: a necromancy initiation Charm sets it the same way.
    grants_circle: Optional[SpellCircle] = None
    # Charms that even the Eclipse/Moonshadow generalist rule (p.127) may NOT reach.
    # The Alchemical Weaving Engines set this: Autochthonians CH4 states outright that
    # "Non-Alchemicals cannot learn weaving Charms", so a foreign learner must never
    # acquire an engine (and thereby its Man-/God-Machine circle). Default False —
    # ordinary foreign-learnable Charms are unaffected.
    no_foreign_learning: bool = False
    # Alchemical Charms only (p.89): the upgrades available for this Charm. Empty
    # for every other splat's Charms and for Alchemical Charms with no listed
    # submodule (most of them, per the book).
    submodules: list[Submodule] = Field(default_factory=list)
    # False bars this Charm from Alchemical Arrays (p.159) — the Auxiliary Essence
    # Storage Unit and the Man-/God-Machine Weaving Engines say so explicitly. True
    # for every ordinary Charm (Arrays otherwise accept any Attribute-based Charm).
    arrayable: bool = True
    # True bars this Charm from ever being uninstalled once worn (CH3 p.141: an
    # Alchemical "cannot ever remove" either Weaving Engine). The vat refit refuses to
    # move it to the Panoply. Default False — an ordinary Charm is freely refittable.
    permanent_install: bool = False
    # Dots of PERMANENT Clarity gained by installing this Charm (CH2 p.69). Six
    # Alchemical Charms grant one each; 0 for every other Charm. Derived, not tracked:
    # removing the Charm removes the dots (p.70), which falls out of reading this off
    # the character's installed Charms.
    permanent_clarity: int = Field(default=0, ge=0)
    description: str = ""
    source: Source = Field(default_factory=Source)
    # NOT authored — stamped by the loader on rows that came from the user's custom
    # library rather than from `data/` (see custom_content.py). The engine treats a
    # custom Charm as an ordinary Charm of its category in every respect; the flag
    # exists so the UI can badge it as non-canon (human's call 2026-07-29: homebrew
    # must be easily distinguishable from printed Charms) and so the authoring page
    # knows which rows it is allowed to edit or delete.
    custom: bool = False
    # Stamped by the loader on rows GENERATED from another data shape rather than
    # authored — the Dragon-King Path powers: each dot-level power of a Path
    # (`Path.powers`) becomes a virtual Charm row so the Combo machinery and the
    # sheet have names/types/durations for them, while the real Path state stays the
    # rated track on Character.paths. The picker hides virtual rows (they are not
    # purchasable); every OTHER read site must decide explicitly whether to skip or
    # include them (see the load_ruleset inventory in the Dragon-Kings plan).
    virtual: bool = False


class Spell(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    circle: SpellCircle
    cost: CharmCost = Field(default_factory=CharmCost)
    description: str = ""
    source: Source = Field(default_factory=Source)
    # Stamped by the loader, exactly as Charm.custom is — see that field.
    custom: bool = False



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
      Half-Caste → the parent Exalt's catalogue (later phase); Fae → none.
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
      pool, and the effective total (pool-spent + bonus) is capped at 5 at chargen
      unless bonus/experience points were spent on that attribute (human ruling
      2026-08-05; the book says "Even after these modifiers are applied, Dragon Kings
      cannot have any Attributes higher than 5 without spending bonus or experience
      points").
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

    The Cult of the Illuminated grants free Charms in two shapes (p.90), so this
    covers both and a camp lists whichever it needs:

    * `from_categories` — "two Charms from ONE of the following four martial arts".
      The player picks a single category from the list, then `pick` Charms inside it.
    * `fixed_sets` — "one of the following pairs of Charms". The player takes exactly
      one whole set, verbatim. `pick` is ignored (a set is all-or-nothing).

    A set may offer alternates for one member where a house rule swaps a Charm
    (Spirit Strengthens the Skin replaces Iron Skin Concentration under Exalted
    Power Combat); those are authored as two separate sets, since the choice is the
    player's, not a rules branch the engine should pick."""
    model_config = ConfigDict(frozen=True)
    label: str = ""                                 # display, e.g. "Martial arts style"
    pick: int = Field(default=0, ge=0)              # how many Charms from the chosen category
    from_categories: list[str] = Field(default_factory=list)
    fixed_sets: list[list[str]] = Field(default_factory=list)


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


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
#
# Thaumaturgy is NOT a splat and NOT an origin: it is an orthogonal capability
# layer. p.114 — the Exalted learn it "without any difficulty", the Wyld-tainted
# "with no restraint", Dragon Kings can, spirits pay double, the Fair Folk not at
# all, and the dead retain what they learned but may never use it (see
# ExaltDefinition.thaumaturgy_usable). It therefore keys off nothing; any
# character may hold it.
#
# Four branches, four different mechanical shapes (p.113):
#   Arts       - BINARY. Trained = +2 dice. Specialties +1 die each, max two
#                applied to a roll. Buyable WITHOUT the parent Art.
#   Sciences   - RATED, with printed per-dot descriptions.
#   Rituals    - LEVELLED 1-5, gated only on Occult >= level.
#   Formulas   - rote recipes for a Science, cheapest of all.
#
# Everything the chapter says about RESOLVING these (ward Strength/Durability,
# the banishment table, summoning difficulties, internal-alchemy failure, the
# four ways to pay a cost) is dice resolution and deliberately OUT OF SCOPE, the
# same call as combat derivation. `roll`/`cost`/`time` below are display strings
# the engine never parses.
# --------------------------------------------------------------------------- #

class Orientation(str, Enum):
    """The regional version of a ritual or formula (p.124). Every ritual and
    formula has one. Casting one from a foreign orientation costs +1 difficulty at
    one region away and +2 at two, with prep time x2/x5 — all of which is dice
    resolution and out of scope. What IS in scope is that a thaumaturge may learn
    several versions of the same spell, each extra costing a flat 1 point, so a
    character's holding is (id, {orientations}) and never a bare id."""
    NORTH = "North"
    SOUTH = "South"
    EAST = "East"
    WEST = "West"
    REALM = "Realm"


class ThaumaturgicAspect(BaseModel):
    """One sub-field of an Art — Summoning's "ghosts", Warding's "the Wyld".

    **An aspect IS a printed general specialty.** The source uses both words for
    one thing: the stat block heads the list "Aspects:", while the prose (p.126)
    says "each field of study is further subdivided into a number of specialties"
    and "Each art lists a number of specialties". The worked example settles it by
    using a printed aspect as its middle term — "mastering the Art (Warding, +2),
    a general specialty in the Art (Fair Folk, +1) and a relevant specialty (Local
    Fair Folk, +1)" — and "Fair Folk" is an item on Warding's Aspects line.

    So: buying an aspect is buying a specialty, at the Art Specialty rate, and a
    player-invented narrower specialty stacks on top for another +1. At most TWO
    specialties apply to any one roll, so the ceiling is +4 (Art +2, general +1,
    narrow +1).

    **No Art is required to buy one** (p.126, and the BP-table footnote): "A
    thaumaturge does not need to buy a field of study in order to purchase a
    specialty in that field, and many do not." Never add a prerequisite.

    `min_occult` is 0 for most: only Summoning gates its aspects individually
    (Beasts/Mortals •, Demons/Elementals ••, Ghosts/Spirits •••, p.126-129).
    Warding, Exorcism and Astrology print aspect lists with no per-aspect gate, so
    0 means "no gate beyond the parent Art's own min_occult"."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    min_occult: int = Field(default=0, ge=0)
    description: str = ""


class ThaumaturgicArt(BaseModel):
    """One Art (p.126-135). Binary, not rated: training grants a flat +2 dice.

    `aspects` is the printed general-specialty menu — see ThaumaturgicAspect; an
    aspect and a specialty are the same purchase. `specialties` is a spare slot for
    any Art that ever prints a specialty list SEPARATE from its Aspects line; none
    of the four do, so it is empty everywhere today. Player-invented specialties
    are free text on the character (the Backgrounds precedent), because the book
    explicitly invites them: "a character could choose to buy a specialty of 'Local
    Fair Folk' for the Art of Warding" (p.126)."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    min_occult: int = Field(default=1, ge=0)
    roll: str = ""                          # display, e.g. "Charisma + Occult"
    cost: str = ""                          # display, e.g. "3 motes per attempt"
    aspects: list[ThaumaturgicAspect] = Field(default_factory=list)
    specialties: list[str] = Field(default_factory=list)   # suggested, not exhaustive
    # Summoning only (p.127): further limiting an aspect ("Summoning (War Gods)")
    # halves that aspect's cost. No other Art prints the option.
    aspect_narrowing: bool = False
    description: str = ""
    source: Source = Field(default_factory=Source)


class ScienceLevel(BaseModel):
    """One printed dot-rung of a Science. Keyed by `rating` rather than held in a
    positional list BECAUSE THE LADDER IS SPARSE: Alchemy prints • •• ••• •••• and
    then ••••••, with no five-dot rung, yet two printed formulas require Alchemy
    ••••• and the stated rule is that a formula's required level equals its
    difficulty (p.143). Rating 5 is thus reachable and purchasable with no
    description. Never renumber the six-dot entry down to close the gap."""
    model_config = ConfigDict(frozen=True)
    rating: int = Field(ge=1)
    description: str = ""


class ThaumaturgicScience(BaseModel):
    """One Science: Alchemy, Enchantment, Geomancy or Weather Working (p.136-148).
    The only rated branch of thaumaturgy.

    `max_rating` is per-Science and is 6 for Alchemy — see ScienceLevel. Do not
    assume the project's usual <=5 rating bound applies here; that bound is a
    convention that holds because chargen rarely exceeds 5, not an invariant."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    roll: str = ""                          # display, e.g. "Dexterity + Occult"
    cost: str = ""                          # display, e.g. "3 motes per level of effect"
    time: str = ""                          # display, e.g. "one day per dot of effect"
    duration: str = ""                      # display
    max_rating: int = Field(default=5, ge=1)
    levels: list[ScienceLevel] = Field(default_factory=list)   # sparse; keyed by rating
    description: str = ""
    source: Source = Field(default_factory=Source)

    def level(self, rating: int) -> Optional[ScienceLevel]:
        """The printed rung at `rating`, or None where the book prints none
        (Alchemy 5). A missing rung is legal, not a data error."""
        return next((lv for lv in self.levels if lv.rating == rating), None)


class ThaumaturgicRitual(BaseModel):
    """One ritual (p.148-150). Levelled 1-5; "the only normal restriction on
    purchasing a ritual is that a thaumaturge must have an Occult score equal to
    or higher than the ritual's level".

    The chapter prints exactly five, and the book expects more to be written
    (p.148: "there are few constant rules, but there are guidelines"), so the
    catalogue is a seed and the character may also carry custom rituals inline —
    the editable-custom-weapons precedent.

    Rituals have NO stat block in the source: the heading is the name with its dot
    rating inline and everything else is prose. `cost`/`roll`/`difficulty` are
    therefore best-effort display strings pulled out of that prose, and
    `description` remains authoritative."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    level: int = Field(ge=1, le=5)
    cost: str = ""                          # display, e.g. "1 mote or one Willpower"
    roll: str = ""                          # display; many rituals print none
    resources: str = ""                     # display, e.g. "Resources 2" for components
    description: str = ""
    source: Source = Field(default_factory=Source)


class ThaumaturgicFormula(BaseModel):
    """One formula or procedure — a rote recipe belonging to a Science (p.138-142).
    Unlike rituals these DO have a labelled stat block: Name / Alchemy / Roll /
    Difficulty / Cost of Materials / Effects / Addiction.

    `materials_raw` wins when set, because one printed formula costs "Equal to
    poison cost" rather than a number of Resources dots."""
    model_config = ConfigDict(frozen=True)
    id: str
    name: str
    science_id: str                         # the Science it belongs to, e.g. "alchemy"
    # The Science rating required. NOT bounded at 5: Alchemy reaches 6.
    level: int = Field(ge=1)
    roll: str = ""                          # display, normally "Intelligence + Occult"
    difficulty: Optional[int] = None
    materials_resources: Optional[int] = None
    materials_raw: str = ""                 # authoritative when set
    effects: str = ""
    addiction: str = ""
    source: Source = Field(default_factory=Source)


# --------------------------------------------------------------------------- #
# Equipment catalog
#
# Catalog entries are autofill sources for the corebook gear tables. The
# character stores a *resolved inline copy* (see character.Weapon / .Armor),
# not a reference, because equipment frequently varies per character (artifacts,
# masterwork, enchantment) in a way Charms and spells never do.
# --------------------------------------------------------------------------- #

class ArmorWeight(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    SUPERHEAVY = "Superheavy"


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
    # Artifact armour (0 = mundane). artifact_rating is the dots of Artifact
    # Background needed to start with it; attunement is the motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    # Everything the fields above cannot hold — WeaponType has carried this since the
    # castebooks (Strength-relative damage, odd rates); armour needed it once the
    # Most Terrifying Armor of the Air Dragon landed with a Strength bonus column and
    # flight rules (Aspect Book: Air p.81). The asymmetry was an oversight: a `notes`
    # key in armor.json was silently DROPPED on load before this.
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    # SHIELDS ride on this model rather than getting one of their own. They are
    # worn equipment with a mobility penalty and no soak, and a character's armour
    # is already a LIST, so a shield is simply another row — no second slot, no
    # second catalogue, and characters get shields for free. `tags: ["shield"]` is
    # the discriminator; RuleSet.shields / .body_armor split on it.
    #
    # These two are the only shield-specific numbers, 0 on every real armour: the
    # p.335 shields differ on them (a buckler "does nothing to protect the
    # character from missile fire", a tower shield raises ranged difficulty by 2).
    # Display only — decision 0008 keeps attack resolution out of this build.
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
    # Artifact weapons (0 = mundane). artifact_rating is the dots of Artifact
    # Background needed to start with it; attunement is the motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    resources_cost: int = Field(default=0, ge=0)
    notes: str = ""                        # special cases (e.g. charge damage)
    tags: list[str] = Field(default_factory=list)


class BackgroundType(BaseModel):
    """A purchasable Background. The catalog of names a character may pick from;
    the per-character rating/descriptor lives on character.BackgroundEntry.

    Availability is a UI autofill hint (backgrounds are free text, never hard-
    validated): `exalt_type`, when set, restricts the Background to that one splat
    (Dragon-Blooded Breeding/Connections); `excluded_exalt_types` lists splats that
    may NOT take an otherwise-universal Background (the DB splatbook, oddly, bars
    Dragon-Blooded from Contacts/Influence/Followers, p.156-157)."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    exalt_type: str = ""                          # "" = all splats; else only this one
    excluded_exalt_types: list[str] = Field(default_factory=list)
    # Origins of the owning splat that may NOT take this Background, matching the
    # origin half of the "E:o:u" budget cascade. Used for the ancient-only Savant
    # (PG p.176: "Only ancient Dragon Kings may possess this Background at character
    # creation"): the value is the MODERN/default origin, i.e. `["Dragon-Kings"]`,
    # NOT the ancient key — excluding the ancient row would bar the wrong half. Read
    # by RuleSet.backgrounds_for as a soft autofill filter (backgrounds are free
    # text, never hard-validated).
    excluded_origins: list[str] = Field(default_factory=list)


class TraitRequirement(BaseModel):
    """A rated trait a Merit or Flaw requires before it may be bought (cluster 7 of the
    M&F triage) — "Characters must have Appearance 2 in order to purchase this version"
    (Innocuous, p.22), "must already have Breeding 5" (Legendary Breeding, p.28).

    `trait` is a NAME, not an id, and is resolved across Attributes, Abilities, Virtues
    and Backgrounds in that order by `validate.trait_rating`. That is not laziness: the
    six entries that want this span all four namespaces (Appearance, Occult, Manse,
    Resources, Salary, Breeding, Celestial Patron), and Backgrounds are free text with
    no id to reference in the first place. A name that resolves nowhere reads as 0 and
    the requirement simply fails, which is the graceful-unresolvable-reference rule the
    rest of the build already follows.
    """
    model_config = ConfigDict(frozen=True)

    trait: str
    rating: int = Field(default=1, ge=0)


class BackgroundPointLimit(BaseModel):
    """A printed rule tying how many POINTS a Merit or Flaw may be worth to a
    Background the character holds (A6, PG pp.37-38). Three of the general chapter's
    entries say the same thing in different words:

      * Known Anathema — "may not generally take more points of this Flaw than their
        rating in Influence" (`background="Influence"`, `mode="max"`),
      * Damaged Artifact — "must have at least one more dot of Artifact than the points
        obtained with this Flaw" (`background="Artifact"`, `mode="max"`, `offset=-1`),
      * Debt — "provided the former exceeds the latter" (`background="Resources"`,
        `mode="above"`).

    Inert catalogue data, exactly like `barred_exalt_types` and `barred_castes`: a
    printed restriction on what may be BOUGHT, not something the entry does. Validate
    checks it; engine.merits never sees it.

    Backgrounds are free text, so `background` is matched by lowercased name.
    """
    model_config = ConfigDict(frozen=True)

    background: str
    # "max"   — points may not exceed (rating + offset)
    # "above" — points must exceed (rating + offset)
    mode: str = "max"
    offset: int = 0
    # Read the rating of ONE named item rather than the character's summed Background.
    # Damaged Artifact only, whose limit is "the rating of the artifact it modifies"
    # (PG p.38): a character with a 4-dot and a 2-dot artifact may take three points of
    # the Flaw against the daiklave and one against the wings, never three against the
    # wings — which is what the summed reading permitted. The item is named by
    # `MeritFlawPurchase.artifact_key`; `background` still identifies which Background
    # governs, so a per-entry limit stays self-describing in the catalogue.
    per_entry: bool = False
    # WHAT to measure on that entry. "rating" is the item's own dots; "acquisition_cost"
    # is what it cost to obtain — Damaged Artifact caps its points at BOTH ("may not
    # gain more points from this Flaw than the rating of the artifact it modifies OR the
    # number of Background and/or bonus points spent obtaining the artifact, whichever
    # is less", PG p.38). The two diverge for any splat whose Artifact Background buys
    # more than one dot of artifact per dot spent.
    measure: str = "rating"

    @field_validator("measure")
    @classmethod
    def _check_measure(cls, v: str) -> str:
        if v not in ("rating", "acquisition_cost"):
            raise ValueError(
                f"measure must be 'rating' or 'acquisition_cost', got {v!r}")
        return v

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v not in ("max", "above"):
            raise ValueError(f"mode must be 'max' or 'above', got {v!r}")
        return v


class MeritFlaw(BaseModel):
    """One purchasable Merit or Flaw.

    Merits & Flaws were ripped out in June 2026 because the old implementation
    scattered mechanical effects across every file they touched. Decision 0011 is that
    they come back as ONE centralized calculation, and this entity is deliberately
    INERT: it carries the printed text, the cost and the prerequisites, and NOTHING
    about what a Merit does. Effects live in `engine.merits.merits_and_flaws_calc`,
    keyed by id. A new Merit with no mechanical effect therefore needs data only.

    The Thaumaturgy Merits (Player's Guide pp.120-122) are authored first because they
    are the mortal unlock set and were already in hand; the general M&F chapter drops
    into the same file. Shape notes for that:

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
    # (p.17). A repeat limit, not a rating floor, so it is its own field. "" = no limit
    # beyond `repeatable_by`.
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
    # PLURAL because Damaged Artifact prints TWO constraints and they measure different
    # things (PG p.38): "may not gain more points from this Flaw than the rating of the
    # artifact it modifies" is per-item, while "characters must have at least one more
    # dot of Artifact than the points obtained" is against the summed Background. They
    # were collapsed into one summed check with offset -1, which let a character with a
    # 4-dot daiklave and 2-dot wings take the full three points against the wings.
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


# --------------------------------------------------------------------------- #
# Cost tables
# --------------------------------------------------------------------------- #

class LinearCost(BaseModel):
    """cost = current * coeff + offset. The XP increase costs are all of this
    form; the favored/caste ability discount is just offset = -1."""
    coeff: int
    offset: int = 0

    def at(self, current: int) -> int:
        return current * self.coeff + self.offset


class BonusPointCosts(BaseModel):
    """Flat per-purchase BP costs (chargen). background_above_3 applies when the
    dot being bought raises the Background above 3."""
    attribute: int = 4
    # Discount for a Caste ATTRIBUTE (Lunar, p.93 — "4 (3 if a Caste Attribute)").
    # Unused by Ability-caste splats, whose CasteDefinition.caste_attributes is
    # empty so no attribute ever qualifies; defaults equal to `attribute` so it's
    # a no-op until a splat's data row overrides it.
    attribute_caste_favored: int = 4
    ability: int = 2
    ability_favored_caste: int = 1
    background: int = 1
    background_above_3: int = 2
    specialty: int = 1
    # p.105: a specialty dot costs 1 BP, but in a Favoured/Caste Ability you get
    # this many dots per 1 BP ("2 per 1"). Cost is thus dots / this, rounded up.
    specialty_favored_caste_dots_per_point: int = 2
    # --- Thaumaturgy (Player's Guide BP table, p.116) ------------------------ #
    # Cross-splat, so these sit on the shared default row rather than a splat row.
    # An Art Specialty and a printed Art *aspect* are the same purchase — see
    # models.rules.ThaumaturgicAspect.
    thaum_art: int = 5
    thaum_art_specialty: int = 2
    # "Ritual | 2 + 1 per level of Ritual" — so a level-3 ritual is 5 BP.
    thaum_ritual_base: int = 2
    thaum_ritual_per_level: int = 1
    thaum_formula: int = 1
    # Each ADDITIONAL regional version of a ritual or formula already known
    # (p.124): "additional versions for other orientations cost only a single
    # experience or bonus point to learn".
    thaum_extra_orientation: int = 1
    # Sciences: 5 for the first dot, 7 for each dot after.
    #
    # NOT from the printed tables — the published BP and XP tables have no Science
    # row at all, which is a PRINTING ERROR Grabowski cleared up afterwards. Supplied
    # by the rules authority (human, 2026-07-29) from that clarification. Flagged
    # because it is the one rate here with no page behind it; if it is ever
    # contradicted by a printed source, the source wins.
    thaum_science_first_dot: int = 5
    thaum_science_additional_dot: int = 7
    virtue: int = 3
    # Bonus points per dot of Fetter (E:Ab p.127 BP table: "Fetter | 3"). Only ghosts
    # have Fetters at all; the value is inert for every other splat. Passions have no
    # row on that table and none here — see ChargenBudgets.fetter_dots for why the
    # omission is the printed rule rather than a gap.
    fetter: int = 3
    willpower: int = 2
    essence: int = 7
    # Flat per-step Essence prices keyed by the TARGET rating, overriding `essence`
    # for the steps listed — the exact BP mirror of ExperienceCosts.essence_by_rating.
    # The God-Blooded table (p.50) prices Essence by destination: Essence 2* = 5,
    # Essence 3** = 15 (the starred footnotes are the Awakened-Essence / Essence-2
    # gates, enforced in validate). Empty for every splat whose Essence is linear.
    essence_by_rating: dict[int, int] = Field(default_factory=dict)
    charm: int = 5
    charm_favored_caste: int = 4
    # The sorcery/necromancy INITIATION Charms — those whose `grants_circle` is set —
    # cost a distinct rate for the God-Blooded (p.50: "Charm/Spell* | 7 (10 for
    # Sorcery or Necro-mancy Charms)"). 0 = every other splat, whose circle-granting
    # Charms keep the ordinary `charm` rate.
    magic_charm: int = 0
    # Immaculate Order Charms (Dragon-Blooded, p.153) cost more than ordinary DB
    # Charms. Unused by splats without an Immaculate package (Solar); the discount
    # applies when the Charm's Ability is Favoured/Caste, same as `charm`.
    immaculate_charm: int = 10
    immaculate_charm_favored_caste: int = 7
    # Sidereal Martial Arts Charms cost a distinct BP rate (8/6, p.101 summary),
    # differing from the ordinary Charm 7/5. Applies to ALL Martial Arts for a
    # Sidereal (there is no Solar-only Martial Arts they cannot learn). None on
    # every other splat, falling back to `charm`/`charm_favored_caste` so their MA
    # Charms are unchanged. Immaculate MA Charms keep the immaculate rate (that
    # branch is checked first).
    martial_arts_charm: Optional[int] = None
    martial_arts_charm_favored_caste: Optional[int] = None
    # Astrological Colleges (Sidereal, p.100-101): 8 BP per dot, 6 if the College is
    # one of the character's own Maiden's. Unused by splats without colleges.
    college: int = 8
    college_own_house: int = 6
    # Dragon-King Paths (PG p.176 BP table): "Path | 5 (10 if the Path is being
    # raised above 3)" and "Breed Path | 4 (8 if raised above 3)". `path_breed` is
    # the discount rate for a Breed or Favoured Path (the breed's two element Paths
    # plus the one the player chooses). 0 for every splat without Paths, which is
    # every splat except the Dragon-Kings (guarded by ChargenBudgets.path_dots > 0).
    path: int = 0
    path_breed: int = 0
    path_above_3: int = 0
    path_breed_above_3: int = 0
    # Calling discounts (Cult of the Illuminated, p.90 and the p.93 table). A Calling
    # is a DISCOUNT AXIS layered on top of Caste/Favoured, not a second Favored list,
    # so these rates replace `ability`/`charm` for a trait named by the character's
    # Calling and STACK with the Caste/Favoured discount. Defaults equal the
    # undiscounted rates, so a splat with no Callings is unaffected.
    calling_ability: int = 2                        # BP/dot: Calling but not Caste/Favoured
    # Calling AND Caste/Favoured: "1 point per 2 dots" (p.90). Expressed as dots-per-
    # point rather than a rate because it is a fractional cost; rounds UP, matching
    # `specialty_favored_caste_dots_per_point` (rules-authority call, 2026-07-24 —
    # the page does not say how an odd dot rounds).
    calling_ability_favored_caste_dots_per_point: int = 1
    calling_charm: int = 5                          # BP: Calling but not Caste/Favoured
    calling_charm_favored_caste: int = 4            # BP: Calling AND Caste/Favoured


class ExperienceCosts(BaseModel):
    # rating-scaled increases
    attribute: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    # Discount for raising a Caste ATTRIBUTE (Lunar, p.251 — "current rating x 4,
    # minus 1 if a Caste Attribute"). Defaults equal to `attribute` so it's a no-op
    # until a splat's data row overrides it; only splats with Caste Attributes
    # (Lunar) ever have an Attribute qualify. Mirrors BonusPointCosts.attribute_caste_favored.
    attribute_caste_favored: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4))
    # Alchemical (Autochthonians p.64): a Caste- or Favored-Attribute costs
    # (current rating x 4) - 1. Only caste_favored-mode splats have Caste/Favored
    # ATTRIBUTES, so this rate is inert for every category-mode splat (their
    # caste-favored attribute SET is empty — validate._caste_favored_attr_names).
    attribute_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=4, offset=-1))
    ability: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    ability_favored_caste: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2, offset=-1))
    essence: LinearCost = Field(default_factory=lambda: LinearCost(coeff=8))
    # Flat per-step Essence prices, keyed by the TARGET rating, overriding `essence`
    # for the steps listed. The mortal table (PG p.115) prices Essence by destination
    # rather than by a coefficient — "Essence 2* | 20", "Essence 3** | 40" — and stops
    # at 3, which is why ExaltDefinition.essence_cap tops out there for a mortal with
    # the Essence Mastery Merit. Empty for every splat whose Essence is linear.
    # Both starred footnotes ("must already have Essence Mastery"; "must already have
    # Essence 2") are prerequisites, NOT prices, and are enforced elsewhere.
    essence_by_rating: dict[int, int] = Field(default_factory=dict)
    virtue: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))   # does NOT raise Willpower
    # --- Fetters and Passions (ghosts only, E:Ab p.283) --------------------- #
    # Inert for every other splat, which holds no Fetters to price. Raising a Fetter is
    # an ordinary linear cost; the other three are operations no other splat has.
    fetter: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))
    new_fetter: int = 20
    # "New Fetter (Relentless Hunter) | 15" — a discount conditional on the character
    # KNOWING a particular Arcanos, which no other cost in this build is. The Charm is
    # named as data rather than in code, the same way `ox_body_charm_id` and
    # `gift_charm_id` are; "" disables the discount entirely.
    new_fetter_discounted: int = 0
    new_fetter_discount_charm_id: str = ""
    # p.283 "Special": a ghost may move a Passion's or a Fetter's FOCUS without
    # changing its rating. Shifting a Passion "decreases a Passion by one dot [and] in
    # turn … increases an existing Passion by one dot or creates a new one-dot Passion"
    # — a transfer, not a purchase, which is why it has its own flat price and why the
    # total may not move.
    shift_passion: int = 20
    shift_fetter: int = 10
    willpower: LinearCost = Field(default_factory=lambda: LinearCost(coeff=2))
    # flat "new trait" costs
    new_ability: int = 3
    new_specialty: int = 3
    # --- Thaumaturgy (Player's Guide XP table, p.115) ------------------------ #
    # Note the asymmetry with the BP table: an Art costs 5 either way, but an Art
    # Specialty is 2 BP and 3 XP. Do not "tidy" them into agreement.
    # "New Merit (mystical only) | cost in bonus points x2" (PG p.115). A multiplier
    # rather than a table, because the BP value is already on the MeritFlaw row.
    new_merit_bp_multiplier: int = 2
    thaum_new_art: int = 5
    thaum_new_art_specialty: int = 3
    # "Ritual | 3, +1 per level of the ritual" — a level-3 ritual is 6 XP.
    thaum_ritual_base: int = 3
    thaum_ritual_per_level: int = 1
    thaum_formula: int = 1
    thaum_extra_orientation: int = 1
    # Sciences: 7 flat for the first dot, then current rating × 6 — the same
    # "new trait flat, raises scale" shape as every other rated trait here.
    # Same provenance caveat as the BP side: the printed tables omit Sciences
    # entirely (a printing error), and these come from the Grabowski clarification
    # via the rules authority, not from a page.
    thaum_new_science: int = 7
    thaum_science: LinearCost = Field(default_factory=lambda: LinearCost(coeff=6))
    # Astrological Colleges (Sidereal, p.265): a new College costs 5; raising one
    # scales at current rating × 3. Unused by splats without colleges.
    new_college: int = 5
    college: LinearCost = Field(default_factory=lambda: LinearCost(coeff=3))
    # Dragon-King Paths (PG p.176 XP table): "New Path | 7", "New Favored or Breed
    # Path | 6", "Path | current rating x 5", "Favored or Breed Path | current
    # rating x 4". 0/inert for every splat without Paths (guarded by
    # ChargenBudgets.path_dots > 0).
    new_path: int = 0
    new_path_breed: int = 0
    path: LinearCost = Field(default_factory=lambda: LinearCost(coeff=0))
    path_breed: LinearCost = Field(default_factory=lambda: LinearCost(coeff=0))
    new_charm: int = 10
    new_charm_favored_caste: int = 8
    # Immaculate Order Charms (Dragon-Blooded, p.292 — "15, 12 if Favored"). Only
    # consulted for a Charm whose `immaculate` flag is set (Dragon-Blooded only);
    # defaults equal to the ordinary new_charm costs so it's a no-op for every splat
    # without an Immaculate package. Mirrors BonusPointCosts.immaculate_charm.
    new_immaculate_charm: int = 10
    new_immaculate_charm_favored_caste: int = 8
    new_spell: int = 10
    new_spell_occult_favored_caste: int = 8
    # The sorcery/necromancy INITIATION Charms for the God-Blooded (p.49): Terrestrial
    # Circle Sorcery / Shadowlands Circle Necromancy cost 25 XP, "training time
    # measured in weeks rather than days". Keyed off `grants_circle`, so no charm id is
    # named in code. 0 = every other splat, whose circle-granting Charms keep the
    # ordinary new_charm rate.
    new_magic_charm: int = 0
    # Per-circle spell costs (Lunar, p.251 — Terrestrial 12, Celestial 15). When a
    # spell's circle is in this map the map wins and the discount becomes the
    # learner's CASTE discount (CasteDefinition.spell_cost_discount), NOT the
    # Occult-Caste/Favoured discount above — that is the whole point of a splat that
    # prices spells this way (a No Moon Lunar's −2, p.251; Occult-favoured has no
    # effect for such a splat). Empty (every other splat) => the flat new_spell path.
    new_spell_by_circle: dict[SpellCircle, int] = Field(default_factory=dict)
    foreign_charm: int = 20                # spirit Charms / other Exalt types; Eclipse only (gated in engine)
    # Per-circle spell-cost override, keyed by SpellCircle value. When a spell's
    # circle is present, it wins over the flat new_spell rate (and ignores the Occult
    # discount). Alchemical weaving protocols price this way — Man-Machine 12,
    # God-Machine 14 (Autochthonians p.64). Empty for every sorcery/necromancy splat.
    spell_cost_by_circle: dict[str, int] = Field(default_factory=dict)
    # Alchemical Charm-Slot economy (p.64). A bought Slot comes with one free Charm;
    # you pay for the SLOT, not the Charm. `new_charm` here is the flat Panoply
    # (retainer) Charm cost (6) — a Charm bought WITHOUT a Slot.
    new_charm_slot_general: int = 12
    new_charm_slot_dedicated: int = 10
    charm_slot_upgrade: int = 2            # upgrade one Dedicated Slot to General
    # Martial Arts Charm XP rate. Alchemical (11, via Perfected Lotus Matrix) and
    # Sidereal (12/10 — a distinct rate applying to ALL Martial Arts, p.265) set it;
    # None elsewhere, falling back to `new_charm`/`new_charm_favored_caste` so other
    # splats' MA Charms are unchanged.
    new_martial_arts_charm: Optional[int] = None
    new_martial_arts_charm_favored_caste: Optional[int] = None
    # Calling discounts (Cult of the Illuminated, p.102). SUBTRACTED from the computed
    # cost and explicitly stacking with the Caste/Favoured discount: "Any purchase of a
    # Calling Ability after character creation receives a 1 experience point discount.
    # This bonus stacks with the benefit of Favored or Caste Abilities." Deltas rather
    # than rates for exactly that reason. 0 = no Callings, i.e. every other splat.
    calling_ability_discount: int = 0
    calling_charm_discount: int = 0


class BackgroundBudgetTier(BaseModel):
    """One row of a Background that BUYS A BUDGET rather than rating a trait directly
    (`BackgroundRule.budget_tiers`).

    The Abyssal Artifact Background (E:Ab p.131) is the first of these and the reason
    the shape exists: its dots do not describe how good your artifact is, they buy a
    pool of combined artifact rating plus a ceiling on any single item —

        •     Trinkets            combined ≤ 3
        ••    Sound Gear          combined ≤ 5,  none individually above 3
        •••   Well-Equipped       combined ≤ 7,  none individually above 4
        ••••  Supremely Appointed combined ≤ 10, no individual ceiling
        ••••• Divine Regalia      combined ≤ 13, no individual ceiling

    `individual_max` is 0 for "no ceiling" — the two top rows print no limit "other
    than it cannot be N/A", and an N/A artifact has no rating to record in the first
    place (see character.ArtifactEntry). The one-dot row prints no individual cap
    either, because a combined maximum of 3 already is one.

    The per-item ceilings are ST-overridable in the text ("without Storyteller
    permission"); they are reported as ordinary chargen issues, which is how every
    other soft printed limit in this build behaves."""
    model_config = ConfigDict(frozen=True)

    rating: int = Field(ge=0, le=5)        # dots of the owning Background
    name: str = ""                         # the printed label ("Well-Equipped")
    combined_max: int = Field(default=0, ge=0)
    individual_max: int = Field(default=0, ge=0)   # 0 = no per-item ceiling


class BackgroundRule(BaseModel):
    """Mechanical rules attached to ONE Background for ONE splat (see
    `ChargenBudgets.background_rules`).

    Backgrounds are otherwise deliberately soft in this project — free text, an
    autofill catalog, never hard-validated. The Alchemical is the first splat whose
    book gives Backgrounds actual chargen mechanics (CH2 p.65-69), so this is the
    narrow, opt-in exception: a Background with no rule behaves exactly as before.

    `expensive_above`/`expensive_dot_cost` model a Background whose upper dots cost
    more than one dot of the chargen pool each (Alchemical Artifact: "the fourth and
    fifth dot still cost two (2) dots each"). `cap_pre_bp_exempt` lets a Background
    exceed `background_cap_pre_bp` without bonus points ("only Artifact may be higher
    than 3 without bonus points"). `min_rating` is a rating the splat receives
    automatically ("Alchemical Exalted automatically receive Class ••• during
    character creation"). `requires`/`requires_rating` gate one Background on another
    (Backing "requires Class •••+ as a prerequisite")."""
    model_config = ConfigDict(frozen=True)

    cap_pre_bp_exempt: bool = False
    # Pool dots consumed by EVERY dot of this Background. 1 for all but the ghosts'
    # Whispers (E:Ab p.151), which costs "twice the cost … The first 3 dots cost 2
    # Background or bonus points each".
    #
    # Distinct from `expensive_above`/`expensive_dot_cost`, which make only the dots
    # ABOVE a threshold dearer. That pair cannot express "all of them": its threshold
    # is also its disabled sentinel, so `expensive_above: 0` means "no expensive dots"
    # rather than "expensive from the first". The two compose — a Background could be
    # 2/dot up to a threshold and 3/dot beyond it — though nothing printed needs that.
    dot_cost: int = Field(default=1, ge=1)
    expensive_above: int = 0               # 0 = no threshold; see dot_cost
    expensive_dot_cost: int = Field(default=1, ge=1)
    min_rating: int = Field(default=0, ge=0)
    # Dots granted FREE, i.e. on top of the pool rather than out of it. Distinct from
    # min_rating, which is a floor the character must reach by SPENDING pool dots
    # (Alchemical Class •••, CH2 p.61). The Illuminated Solar "begins with
    # Illumination • for free" IN ADDITION to nine Background dots (p.90), so the
    # first dot costs nothing and dots above it cost one each.
    free_rating: int = Field(default=0, ge=0)
    # EXTRA bonus points per dot bought above `background_cap_pre_bp`, on top of
    # `BonusPointCosts.background_above_3`. The pool-side twin of this surcharge is
    # `expensive_above`/`expensive_dot_cost` — one rule, two payment routes, which is
    # exactly how Lookshy Breeding reads (p.66): "each level beyond [2] costs an
    # additional Background OR bonus point (on top of the extra cost to buy
    # Backgrounds above 3)". With expensive_above 2 / expensive_dot_cost 2 and
    # bp_surcharge_per_dot 1, a fully bonus-point-bought Breeding reproduces the
    # page's own totals: 1, 2, 4, 7, 10.
    bp_surcharge_per_dot: int = Field(default=0, ge=0)
    requires: str = ""                     # another Background's NAME, lowercased
    requires_rating: int = Field(default=0, ge=0)
    # A hard ceiling this ORIGIN/UPBRINGING puts on the Background, which bonus points
    # cannot buy past — unlike `background_cap_pre_bp`, which they can. E:Ab p.126:
    # "ghosts from Immaculate dominated areas cannot buy Ancestor Cult or Grave Goods
    # above •", a consequence of living where the Order suppresses ancestor worship.
    # 0 = no ceiling, which is every other Background in the build.
    max_rating: int = Field(default=0, ge=0)
    # Rows of a Background that buys a BUDGET of rated items rather than rating one
    # trait — see BackgroundBudgetTier. Empty for every Background but the loyal
    # Abyssal's Artifact, and empty is what makes the check a no-op everywhere else:
    # the core rulebook's Artifact Background has no budget table, which is exactly why
    # `Abyssal:fugitive` ("Renegade Abyssals use the Artifact Background found in
    # Chapter Four: Traits of the main Exalted rulebook", p.131) must NOT carry these.
    budget_tiers: tuple[BackgroundBudgetTier, ...] = ()
    # How much RATING of the thing this Background buys arrives per dot bought — the
    # other shape a budgeting Background takes, and the simpler one. The Artifact
    # Background's own text carries two: "Dragon-Blooded receive twice the dots' worth
    # of artifacts" (2) and "Alchemicals receive THREE dots of artifacts per dot
    # bought" (3). 1 is the core rulebook's one-for-one and every other Background.
    #
    # Read by `engine.artifacts.acquisition_cost`, which is what Damaged Artifact's
    # "the number of Background and/or bonus points spent obtaining the artifact"
    # measures against. Mutually exclusive with `budget_tiers` in practice: a splat
    # prints one shape or the other, and the tiers win where both appear.
    rating_per_dot: int = Field(default=1, ge=1)


class ChargenBudgets(BaseModel):
    # attributes: 8/6/4 across the three prioritized categories; all start at 1.
    # Which category gets which pool is derived from the per-category spend, not stored.
    attribute_pools: tuple[int, int, int] = (8, 6, 4)
    attribute_base: int = 1
    # How the three attribute_pools are allocated:
    #   "category"      — the default for every prior splat: the pools are matched to
    #                     the three prioritized categories (Physical/Social/Mental) by
    #                     spend, and each category's caste-favoredness (Lunar) only
    #                     affects the over-spend RATE.
    #   "caste_favored" — Alchemical (p.60): the pools are NOT category pools. They are
    #                     assigned in FIXED order to three disjoint attribute SETS —
    #                     the caste's Caste Attributes (pools[0]), the player's chosen
    #                     Favored Attributes (pools[1]), and the remaining attributes
    #                     (pools[2]). Caste and Favored attributes share the discounted
    #                     over-spend rate (bonus_costs.attribute_caste_favored).
    attribute_mode: str = "category"
    # caste_favored mode only: how many Favored Attributes the player selects (3 for
    # Alchemical), and the minimum rating each Caste Attribute must reach ("none may
    # have a rating lower than 2", p.60). 0 = not applicable (every category-mode splat).
    attribute_favored_count: int = 0
    attribute_caste_min: int = 0

    # Required minimum Abilities the character must meet (a floor spent from the
    # pool, not free extras). Dragon-Blooded Dynastic schooling (p.151); empty for
    # splats/origins with no such floor (Solar, DB Outcaste).
    required_min_abilities: list[AbilityMinimum] = Field(default_factory=list)

    # Abilities that MUST be among the character's Favored set (not just dotted) —
    # the Lunar rule that Survival is always Favored (p.90). Empty for splats with
    # no such forced inclusion (Solar, Dragon-Blooded, Abyssal).
    required_favored: list[AbilityName] = Field(default_factory=list)

    ability_dots: int = 25
    ability_min_caste_favored: int = 10    # >= 10 of the 25 on caste/favored abilities
    ability_cap_pre_bp: int = 3
    favored_count: int = 5                 # >= 1 dot required in each favored ability
    # May this origin take core p.103's optional Favored Ability, if the Storyteller
    # switches it on (HouseRules.mortal_favored_ability)? True ONLY for the heroic
    # mortal row: the page offers it to "heroic mortals", not to ordinary ones, which
    # is why it is an origin-keyed budget flag and not a splat-wide property. The house
    # rule alone is not enough — both this and the toggle must be set.
    optional_favored_ability: bool = False

    background_dots: int = 7
    background_cap_pre_bp: int = 3
    # Per-Background mechanical rules, keyed by the Background's NAME lowercased
    # (character.BackgroundEntry.name is free text, not an id, so this cannot key on
    # BackgroundType.id). Empty for every splat whose Backgrounds are purely narrative
    # — which was ALL of them until the Alchemical (CH2 p.65-69) introduced the first
    # Backgrounds with real mechanics. Per-splat because the rules modify otherwise
    # universal Backgrounds: Artifact is ordinary for a Solar and heavily reworked for
    # an Alchemical, so the mechanics cannot live on the shared BackgroundType.
    background_rules: dict[str, BackgroundRule] = Field(default_factory=dict)
    # Backgrounds this origin may take AT ALL, as lowercased NAMEs (matching
    # background_rules' keying). Empty = unrestricted, which is every splat except the
    # Sidereal ronin, who are "limited to the Backgrounds of Acquaintances, Allies,
    # Artifact, Backing, Connections, Familiar, Manse and Resources" (p.100). This is
    # the ONLY hard Background validation in the project — Backgrounds are otherwise
    # deliberately soft free text — so it is opt-in per origin and checked by name.
    # The same paragraph's "no Backing from or Connections with any of the Sidereal
    # factions or Celestial Bureaus" is narrative and is NOT modelled.
    allowed_backgrounds: list[str] = Field(default_factory=list)
    # Suppress the CASTE's own required_min_abilities for this origin. The ronin
    # "have no minimum required Ability scores" (p.100), but a ronin still HAS a
    # Caste, so the per-house floor on CasteDefinition would otherwise still apply.
    # The budget's own required_min_abilities list is simply empty for such a row.
    ignore_caste_min_abilities: bool = False

    # Astrological Colleges (Sidereal, p.98) — a rated Advantage with its OWN point
    # pool, separate from Abilities and Backgrounds. `college_dots` 0 (the default)
    # means the splat has no colleges (every non-Sidereal). `college_min_own_house`
    # is how many of those dots must be in the character's Maiden's Colleges.
    college_dots: int = 0
    college_min_own_house: int = 0
    college_cap_pre_bp: int = 3

    # Dragon-King Paths (PG p.175-177) — a rated Advantage with its OWN point pool,
    # separate from Abilities and Backgrounds, exactly the College shape. `path_dots`
    # 0 (the default) means the splat has no Paths (every non-Dragon-King).
    # `path_min_breed_favored` is how many of those dots must be in Breed or Favoured
    # Paths ("at least 3 must be from Favored or Breed Paths" for a modern DK, 5 for
    # an ancient); `path_cap_pre_bp` is the per-Path chargen cap ("none may be higher
    # than 3 without spending bonus points"). `path_max_by_essence` is the Essence
    # gate (p.177: Paths cap at 1/3/5/6 at Essence 1/2/3-5/6) — resolved against the
    # character's CURRENT Essence rating, never `essence_start`.
    path_dots: int = 0
    path_min_breed_favored: int = 0
    path_cap_pre_bp: int = 3
    path_max_by_essence: dict[int, int] = Field(default_factory=dict)
    # The p.177 "Maximum Intelligence and Path Level" column's OTHER half: the same
    # Essence-gated ceiling over Intelligence (max 1/3/5/6), resolved against current
    # Essence. `ability_max_by_essence` is deliberately ABSENT — Abilities-to-6 at
    # Essence 6 is already delivered by the `elder.trait_ceiling` mechanism.
    # `virtue_max_by_essence` (row 6 unlocks 6) exists because the elder machinery
    # never covers Virtues — Dragon-Kings are the first splat with a Virtue above 5.
    intelligence_max_by_essence: dict[int, int] = Field(default_factory=dict)
    virtue_max_by_essence: dict[int, int] = Field(default_factory=dict)
    # Virtue floors spent from `virtue_dots` (the dragon-kings must put at least one
    # of their five Virtue dots into Valor, p.175). Empty for every other splat.
    required_virtue_dots: dict[VirtueName, int] = Field(default_factory=dict)

    virtue_dots: int = 5                   # spent over a base of 1 each
    virtue_base: int = 1
    virtue_cap_pre_bp: int = 3

    # Fetters — the anchors that hold a ghost to the world (E:Ab p.126, "All players'
    # ghosts start with 5 dots worth of Fetters. No Fetter can be higher than 3 without
    # the expenditure of bonus points"). 0 for every other splat, which is what keeps
    # the panel off their sheets.
    #
    # There is NO `passion_dots` twin. Passions are not a budget: "Choose a number of
    # dots of Passions for each Virtue equal to the number of dots the character has in
    # that Virtue" (p.126), and p.283 closes it — "Ghosts increase their Passions when
    # they increase their Virtues. There is no other way for these Traits to increase."
    # They are DERIVED from the Virtues, so they are a derivation, not a pool.
    fetter_dots: int = 0
    fetter_cap_pre_bp: int = 3

    charm_count: int = 10
    charm_min_caste_favored: int = 5
    # Sidereal, p.101: "no more than 3 [chargen Charms] may be from a Sidereal Martial
    # Arts form; ronin ... none from Sidereal Martial Arts". A "form" is a supernatural
    # SMA style — a martial_arts Charm that is `open_to_tiers` (Celestial-open); the
    # Violet Bier of Sorrows auspicious tree is NOT open_to_tiers and is uncapped. None
    # = no cap (every other splat). 0 = barred (the Sidereal ronin).
    martial_arts_form_charm_cap: Optional[int] = None
    # Charm Slot system (Alchemical, p.88-89): instead of pricing Charms per pick,
    # the character has a fixed number of General Slots (hold any Charm) and
    # Dedicated Slots (hold only a Caste/Favored-Attribute Charm); every Slot comes
    # with one free Charm. These are the FREE (chargen) slot counts. When either is
    # > 0 the splat is slot-based: charm accounting switches from per-pick to
    # per-slot (extra General/Dedicated slots cost bonus_costs.charm/charm_favored_caste),
    # and the caste-favored charm rule becomes "non-Caste/Favored Charms must fit
    # the General Slots". 0/0 (every other splat) keeps the per-pick model.
    charm_slots_general: int = 0
    charm_slots_dedicated: int = 0
    # The alternative Immaculate chargen path (Dragon-Blooded, p.151): a character
    # learning Immaculate martial arts takes this many Charms instead of charm_count,
    # all from a single elemental tree, and the charm_min_caste_favored rule is
    # waived. Only reachable when the character selects Immaculate Order Charms, so it
    # never affects splats without them (Solar).
    immaculate_charm_count: int = 5
    # Charms this origin hands out FREE at creation: no Charm pick, no bonus points
    # (Lookshy, p.68 — "all Lookshy Dragon-Blooded have the Charms Wind-Carried Word
    # Technique and Elemental Bolt Attack, at no cost"). Distinct from a training
    # camp's package (rules.TrainingCamp), which the PLAYER chooses from and which the
    # engine validates as choices; these are fixed and unconditional, so they are a
    # property of the budget row. Empty for every origin that grants nothing.
    granted_charms: list[str] = Field(default_factory=list)
    # Does this origin forbid Immaculate Order Charms at creation? Lookshy, p.68:
    # "Lookshy Dragon-Blooded may not learn the Immaculate Martial Arts before play
    # begins" — a chargen-only bar (the same page points a player who wants them at
    # the Dynastic rules), so it never touches the XP economy. Keys off Charm.immaculate
    # rather than a category list, because that flag already IS "an Immaculate Charm".
    bar_immaculate_charms_at_chargen: bool = False

    essence_start: int = 2
    # Hard ceiling on Essence at the END of character creation, i.e. after bonus
    # points. Cult of the Illuminated (p.90): an Illuminated Solar starts at Essence
    # 3 and "under no circumstances may begin with an Essence of six (6) or higher",
    # so 5. 0 = no ceiling beyond whatever the BP budget can afford, which is every
    # other splat authored so far.
    essence_start_cap: int = 0
    # This origin requires the character to pick a TrainingCamp / Calling (see
    # rules.TrainingCamp). False for every splat without them, which is all of them
    # except the Illuminated Solar.
    requires_camp: bool = False
    requires_calling: bool = False
    bonus_points: int = 15
    # God-Blooded Inheritance (Player's Guide p.61): the Inheritance Background's
    # rating adds to the bonus-point pool — • Thin blood +6, •• Good +12, ••• Notable
    # +18, •••• Impeccable +24, ••••• Divine +30. Indexed by the Inheritance rating
    # (0..5); empty for every other splat, which has no such Background and keeps the
    # flat `bonus_points` above. Read by validate.bonus_point_breakdown.
    inheritance_bonus_points: list[int] = Field(default_factory=list)
    # The Flaw-point cap per Inheritance rating (p.61: 10 / 15 / 15 / 20 / 20). Read
    # by engine.merits.merits_and_flaws_calc instead of its FLAW_POINT_CAP constant
    # when the splat authors it. Index 0 is 0 — a character with no Inheritance is not
    # really a God-Blood (p.61) and, by human ruling, must take at least one dot.
    inheritance_flaw_cap: list[int] = Field(default_factory=list)

    willpower_start_cap: int = 8           # may not start above this...
    willpower_cap_exception_virtue: int = 4   # ...unless at least
    willpower_cap_exception_count: int = 2    # this many Virtues are >= 4

    @field_validator("attribute_mode")
    @classmethod
    def _check_attribute_mode(cls, v: str) -> str:
        if v not in ("category", "caste_favored"):
            raise ValueError(
                f"attribute_mode must be category/caste_favored, got {v!r}")
        return v


class EssencePoolSpec(BaseModel):
    """Per-splat motes formula as data, so derive.essence_pools is a lookup, not a
    branch. personal = essence*personal_essence_coeff + willpower*personal_willpower_coeff;
    peripheral = essence*peripheral_essence_coeff + willpower*peripheral_willpower_coeff
    + the Virtue term selected by `peripheral_virtue_mode`.

      * Solar (core p.104):      3 / 7, virtue_mode "all"          (Ess×3+WP; Ess×7+WP+ΣVirtues)
      * Dragon-Blooded (p.150-152): 1 / 4, virtue_mode "two_highest",
        plus a Breeding-Background term added to BOTH pools (see below).
      * Lunar (p.91):            1 / 4, personal_willpower_coeff 2, virtue_mode
        "highest" with peripheral_virtue_coeff 4 (Ess+WP×2; Ess×4+WP×2+highestVirtue×4).

    `peripheral_virtue_mode`: "all" adds ΣVirtues (all four, Solar), "two_highest"
    adds the sum of the two highest Virtues (Dragon-Blooded), "highest" adds only
    the single highest Virtue (Lunar — scaled by `peripheral_virtue_coeff`, since
    Lunar's term is ×4 rather than the ×1 every other splat uses), "none" adds
    nothing.

    Some splats add a flat, Background-derived bonus to both pools that plain
    coefficients can't express — the Dragon-Blooded Breeding Background (p.158-159).
    `breeding_background` names that Background; `breeding_personal`/`breeding_peripheral`
    are per-rating bonus tables indexed by the Background's rating (0..5, plus a
    rating-6 row a Merit can reach — see engine.merits.LEGENDARY_BREEDING). Empty
    tables (Solar) mean no such term. If a splat needs a term none of this can express,
    STOP and ask for the page."""
    model_config = ConfigDict(frozen=True)
    personal_essence_coeff: int
    personal_willpower_coeff: int = 1
    peripheral_essence_coeff: int
    peripheral_willpower_coeff: int = 1
    peripheral_virtue_mode: str = "all"     # "all" | "two_highest" | "highest" | "none"
    peripheral_virtue_coeff: int = 1        # multiplies the selected Virtue term (Lunar: 4)
    # Optional Background-derived additive term (DB Breeding, p.158-159).
    breeding_background: str = ""            # Background name whose rating indexes the tables
    breeding_personal: list[int] = Field(default_factory=list)     # index by rating 0..6
    breeding_peripheral: list[int] = Field(default_factory=list)
    # A Virtue term on the PERSONAL pool. Every Exalt splat's personal pool is
    # Essence/Willpower only, so these default to inert. They exist for the unlocked
    # mortal (PG p.114), whose single pool is
    #   Essence + Willpower + Conviction + (highest Virtue x 2)
    # — a NAMED Virtue added flat alongside a scaled highest-Virtue term, which
    # nothing else in this spec could express. `personal_named_virtue` is a
    # VirtueName value ("conviction"); "" adds nothing.
    personal_virtue_mode: str = "none"       # same vocabulary as peripheral_virtue_mode
    personal_virtue_coeff: int = 1
    personal_named_virtue: str = ""
    personal_named_virtue_coeff: int = 1
    # Additional named Virtues added flat, the same shape as the single
    # `personal_named_virtue`. The Dragon-Kings (PG p.177) are the first consumer:
    # their single pool is Essence x 4 + Willpower x 2 + Conviction + Valor — TWO
    # specific named Virtues, which no virtue_mode can express ("two_highest" is the
    # two highest, not Conviction+Valor specifically). `_named_virtue_term` sums the
    # single + the list, so the mortal's existing single-named-virtue formula is
    # unchanged (the list defaults empty).
    personal_named_virtues: list[str] = Field(default_factory=list)

    @field_validator("peripheral_virtue_mode", "personal_virtue_mode")
    @classmethod
    def _check_virtue_mode(cls, v: str) -> str:
        if v not in ("all", "two_highest", "highest", "none"):
            raise ValueError(
                f"peripheral_virtue_mode must be all/two_highest/highest/none, got {v!r}")
        return v


class ExaltDefinition(BaseModel):
    """One Exalt type as data. `id` matches Character.exalt_type ("Solar","Abyssal").
    Holds the splat's essence formula, its magic track (sorcery vs necromancy — see
    SpellCircle), the circle barred at character creation, and the id of its
    repeatable Ox-Body-equivalent Charm. Values come from the page, never memory."""
    model_config = ConfigDict(frozen=True)
    id: str
    label: str
    essence: EssencePoolSpec
    magic_track: str = "sorcery"            # "sorcery" | "necromancy"
    # The circle this splat may NOT begin play knowing — withheld at chargen (Solars:
    # "Solar", core p.100). This is the chargen bar, NOT the splat's reachable ceiling:
    # set it "" (nothing barred) for a splat whose entry circle is also its cap, e.g.
    # Dragon-Blooded (Terrestrial only) — barring their one circle would bar all their
    # sorcery at creation. Read only by validate.chargen_barred_circle.
    highest_magic_circle_id: str = ""       # e.g. "Solar"; "" = nothing barred at chargen
    ox_body_charm_id: str = ""              # the splat's repeatable health-level Charm
    # The splat's repeatable multi-variant-pick Charm, if it has one (Lunar:
    # Deadly Beastman Transformation, p.124-127 — see Charm.variant_picks_*).
    # "" for every splat without one (everyone but Lunar today).
    gift_charm_id: str = ""
    # Does this splat keep a Form Library — a Totem plus the animal shapes it can
    # wear (the "Totem" field on the 1e Lunar sheet)? Purely narrative bookkeeping,
    # never validated or priced; this flag only decides whether the UI offers the
    # page at all. True for Lunar; a later shapeshifting splat can opt in as data.
    form_library: bool = False
    # Does this splat use Clarity in place of Limit (CH2 p.69-71)? True for Alchemical,
    # who took no part in the Great Curse and so have no Limit at all. Decides whether
    # the tracker shows Clarity or Limit; the permanent half is derived in
    # engine.derive.clarity, the temporary half tracked on PlayState.
    clarity: bool = False
    # What this splat calls its Limit track. Sidereals call the Great Curse's meter
    # "Paradox" (p.253) — a pure RENAME, identical 0-10 mechanic, so it is a label and
    # not a second code path. Ignored entirely when `clarity` is True (the Alchemical
    # has no Limit at all to rename). Presentation only.
    limit_label: str = "Limit"
    # Does this splat have a Virtue Flaw — the named Virtue whose failure triggers a
    # Limit Break? True for Solar, Abyssal and Lunar. False for Dragon-Blooded,
    # Sidereal and Alchemical (human, rules authority, 2026-07-30), and false for
    # mortals, who take no part in the Great Curse (core p.103: mortals "do not have
    # a Virtue Flaw or suffer from Limit Breaks"). Independent of `limit_label` and
    # `clarity`: the Sidereal still HAS a Limit track called Paradox, it just has no
    # flawed Virtue naming it. Decides whether the editor offers the panel at all.
    has_virtue_flaw: bool = True
    # May this splat hold Charms AT ALL? False only for mortals — "Mortals cannot
    # purchase Charms" (core p.103), a flat bar, not a budget of zero. It has to be
    # its own flag because `charm_count: 0` merely grants none at creation: the eight
    # `open_to_all` Charms with min_essence 1 would still be purchasable with bonus
    # points, and p.103 spends bonus points "on any Traits except Charms and Essence".
    # When Merits & Flaws land this becomes the DEFAULT rather than the whole story —
    # the right Merits reopen Terrestrial Martial Arts (all but Spirit Walking) and
    # Terrestrial Sorcery, so expect this to be read through merits_and_flaws_calc
    # rather than deleted. See CLAUDE.md's Merits & Flaws TODO.
    charms_available: bool = True
    # Hard ceiling on Essence for the whole of the character's life, XP included — as
    # opposed to ChargenBudgets.essence_start_cap, which only binds until the sheet is
    # locked. 0 = no printed cap, which engine.elder resolves to 9 (the p.258 chart's
    # max) — so a new splat row that OMITS the field silently inherits 9: author it
    # explicitly. A Terrestrial is further held at 7 by the same module. Chargen Essence
    # is separately held at 5 (see validate's `essence-above-elder-chargen-cap`) — this
    # field is the post-lock ceiling.
    # 1 for mortals: Player's Guide p.11, "Mortal characters have an Essence of 1, but
    # no way to gain access to their Essence pool." The way UP is the Essence Mastery
    # Merit (5-pt Supernatural, PG p.121), which "unlock[s] her Essence pool completely"
    # and after which a mortal may buy Essence to 3 with XP (human, rules authority,
    # 2026-07-30 — the printed Merit text does not itself state the 3). So when Merits &
    # Flaws land, merits_and_flaws_calc raises this 1 to 3 rather than removing it.
    essence_cap: int = 0
    # The Essence formula that applies once a Merit has UNLOCKED the pool, for a splat
    # whose default `essence` spec is empty because it has no pool at all. Mortals
    # (PG p.114): "Mortals who manage to unlock their Essence gain an Essence pool
    # equal to (Essence + Willpower + Conviction + [highest Virtue x 2])" — one pool,
    # not a personal/peripheral pair, so the peripheral coefficients stay zero. None
    # for every splat whose pool needs no unlocking, which is every Exalt.
    # Selected by engine.derive.essence_pools via engine.merits, never by splat name.
    unlocked_essence: Optional[EssencePoolSpec] = None
    # What this splat calls its caste slot in the UI: Solars have "Caste", the
    # Dragon-Blooded have "Aspect". Presentation only — the underlying field is
    # still Character.caste keyed to RuleSet.castes.
    caste_noun: str = "Caste"
    # Which tier of Exalt this splat is: "Celestial" (Solar, Lunar, Sidereal,
    # Abyssal) or "Terrestrial" (Dragon-Blooded). Read only by
    # validate.charm_matches_splat, against Charm.open_to_tiers, to open a
    # tier-wide Martial Arts style to splats other than the one that authored it.
    tier: str = "Celestial"
    # May this splat USE the thaumaturgy it knows? False only for the dead
    # (Player's Guide p.114): "although the dead retain knowledge of what they
    # learned in Creation, they are forever barred from using that knowledge …
    # The dead who knew magic in life can act as tutors for thaumaturges,
    # however." So this bars USE, not purchase or possession — a ghost keeps its
    # Arts on the sheet, flagged unusable, and can still teach. True everywhere
    # else; the Ghost splat sets it False when it lands.
    thaumaturgy_usable: bool = True
    # Multiplier on the BP/XP cost of any Art, Science, ritual or formula. 2 for
    # spirits (p.114: "Spirits may use thaumaturgy, but they pay twice the normal
    # experience (or bonus) points"). No playable spirit splat exists yet — this
    # is authored and wired but exercised by nothing.
    thaumaturgy_cost_multiplier: int = Field(default=1, ge=1)
    # Does this splat have ONE Essence pool rather than a Personal/Peripheral pair?
    # True for ghosts (E:Ab p.126): "Ghosts do not have separate Personal and
    # Peripheral Essence pools, instead having a single Essence pool that serves all
    # of the character's needs."
    #
    # The merge itself already existed for Beacon of Power, a MERIT — so it was
    # reachable only through `merits_and_flaws_calc`. A splat whose pool is merged by
    # its own nature cannot express that as a Merit, hence a second, splat-level
    # source OR'd into the same one read site (`derive.essence_pool_is_merged`). Two
    # sources, one consumer: adding a third here must not add a third read.
    single_essence_pool: bool = False
    # May this splat learn Charms belonging to ANYONE ELSE — including the
    # `open_to_all` Terrestrial martial-arts styles every other splat may pick up?
    # False for the dead: "Ghosts may not learn Exalted Charms" (E:Ab p.126), a flat
    # clause with no Merit or Background reopening it.
    #
    # Distinct from `charms_available`, which bars Charms ENTIRELY (mortals): a ghost
    # has a full Charm economy of its own in the Arcanoi and is barred only from other
    # people's. Without this the `open_to_all` styles reach them, because open_to_all
    # is checked before the splat comparison.
    foreign_charms_barred: bool = False
    # ONE exception to `foreign_charms_barred`: the supernatural martial arts. PG p.234
    # — "Ghosts may learn supernatural martial-arts techniques as well. Like
    # thaumaturges and God-Blooded, they can learn only Terrestrial styles."
    #
    # UNCONDITIONAL, and that is the point: p.234's main text grants this to every
    # ghost at a penalty price (`new_martial_arts_charm`), and the Fighter in Life
    # Merit only makes some of them cheaper and reachable at creation. Modelling the
    # access itself as the Merit's would have barred it from every ghost without one.
    terrestrial_martial_arts: bool = False
    # Individual Charms this splat may never hold, by id, even when the rules above
    # would otherwise reach them. Ghosts are barred from Spirit Walking (human, rules
    # authority, 2026-08-01) — the Charm that opens the Immaculate Dragon Paths, and
    # the same one the Essence Mastery Merit withholds from mortals for the same
    # reason.
    #
    # DATA rather than code, so barring a Charm from a splat is a JSON edit and no
    # module has to name a Charm id to do it. Checked FIRST in charm_matches_splat, so
    # it outranks every grant — a bar that any later branch can talk past is not a bar.
    barred_charm_ids: list[str] = Field(default_factory=list)
    # Spell ids this splat may never learn, whatever Circle it has been initiated
    # into — the spell-side parallel to `barred_charm_ids`, and read in the same
    # two-routes-or-it-is-not-a-bar way (meets_spell_requirements AND
    # check_spell_access). The God-Blooded, PG p.48: "No God-Blood can learn spells
    # to summon and bind elementals or demons, as the workings of these spells are
    # designed to operate in conjunction with certain privileges of the Exalted."
    # Circle access alone cannot express that — the bar names individual spells
    # inside Circles the splat legitimately holds. Empty for every other splat.
    barred_spell_ids: list[str] = Field(default_factory=list)
    # May this splat learn Combos at all? False for the dead (E:Ab p.234): "The dead
    # may never learn Combos and so may never use more than one Charm per turn."
    #
    # A flat bar, not a budget of zero — the same distinction `charms_available`
    # draws. Ghosts hold Arcanoi freely; it is only their COMBINATION that is barred,
    # so this cannot be expressed by withholding Charms.
    combos_available: bool = True
    # Does this splat's natural Stamina add half its rating to LETHAL soak, the
    # Exalt rule ("magical beings soak lethal with Stamina//2")? False only for the
    # Dragon-Kings (PG p.165 physiology sidebar: "unlike Exalts, their Stamina does
    # not assist them in soaking lethal damage… their bashing soak equals [their
    # Stamina + their innate armor] and their lethal soak equals their innate
    # armor"). Read by derive.soak, which is also where the breed's innate armour
    # (CasteDefinition.breed_traits) is folded in. This field is the data-driven
    # replacement for the retired `exalt_type != "Mortal"` string compare.
    stamina_adds_to_lethal_soak: bool = True


# The canonical Solar definition — the existing hardcoded formula moved into data
# (the values are the verified core-p.104 Solar pools, not new rules). Used as the
# default when no exalts.json is loaded and as the fallback for an unknown exalt_type.
def _keyed_row(table: dict, exalt_type: str, origin: str, upbringing: str, default):
    """Look a per-splat table up on the splat / origin / upbringing cascade, most
    specific first: `"E:o:u"` -> `"E:o"` -> `"E"` -> `default`.

    One helper for both `budgets_for` and `bonus_costs_for` so the two can never
    disagree about which row wins. The cascade is what lets an upbringing row carry
    ONLY its differences: the three Lost Egg upbringings share one `Dragon-Blooded:
    lost-egg` bonus-point row, and an origin with no upbringing variants authors no
    `:u` rows at all.
    """
    if origin and upbringing:
        row = table.get(f"{exalt_type}:{origin}:{upbringing}")
        if row is not None:
            return row
    if origin:
        row = table.get(f"{exalt_type}:{origin}")
        if row is not None:
            return row
    return table.get(exalt_type, default)


SOLAR_EXALT = ExaltDefinition(
    id="Solar",
    label="Solar Exalted",
    essence=EssencePoolSpec(personal_essence_coeff=3, peripheral_essence_coeff=7,
                            peripheral_virtue_mode="all"),
    magic_track="sorcery",
    highest_magic_circle_id="Solar",
    ox_body_charm_id="solar.endurance.ox-body-technique",
)


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
    weapon_catalog: dict[str, WeaponType] = Field(default_factory=dict)
    background_catalog: dict[str, BackgroundType] = Field(default_factory=dict)
    nature_catalog: dict[str, NatureType] = Field(default_factory=dict)
    material_catalog: dict[str, MagicalMaterial] = Field(default_factory=dict)
    colleges: dict[str, College] = Field(default_factory=dict)   # Astrological Colleges (Sidereal)
    # Dragon-King Paths of Prehuman Mastery (PG pp.177-191), keyed by Path.id. The
    # 60 dot-level powers are ALSO projected into `charms` as virtual rows (see
    # rules_db.load_ruleset) so Combos and the sheet can name them; `paths` is the
    # rated-track truth the real state (Character.paths) lives against. Empty for
    # every splat that ships no paths.json.
    paths: dict[str, Path] = Field(default_factory=dict)
    # Merits & Flaws. Cross-splat like thaumaturgy, and inert data: what a Merit DOES
    # lives in engine.merits, never here (decision 0011). Empty when the file is absent.
    merits_flaws: dict[str, MeritFlaw] = Field(default_factory=dict)
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
    # Everything wrong with the user's custom library (custom_content.py), one string
    # per dropped row. Book-data problems are fatal and never reach here — these are
    # non-fatal by design, so the UI shows them as a warning and the app still runs.
    custom_problems: list[str] = Field(default_factory=list)

    # Shields live in armor_catalog tagged "shield" (see ArmorType). These two
    # split it so a caller never has to know the tag string, and so "the armour
    # list" and "the shield list" are one source of truth with two views.
    def body_armor(self) -> list[ArmorType]:
        """Armour proper — everything in the catalogue that is not a shield."""
        return [a for a in self.armor_catalog.values() if "shield" not in a.tags]

    def shields(self) -> list[ArmorType]:
        """The shields. p.335 describes three; all are mundane."""
        return [a for a in self.armor_catalog.values() if "shield" in a.tags]

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

    def backgrounds_for(self, exalt_type: str, origin: str = "") -> list[BackgroundType]:
        """The Backgrounds a character of `exalt_type` may pick from (the editor's
        autofill list). A splat-restricted Background (`exalt_type` set) shows only
        for that splat; a Background listing `exalt_type` in `excluded_exalt_types`
        is hidden from it (DB bar Contacts/Influence/Followers). A Background listing
        the character's effective budget cascade key in `excluded_origins` is hidden
        from that ORIGIN — the ancient-only Savant excludes the modern key
        `"Dragon-Kings"`, never `"Dragon-Kings:ancient"` (barring the ancient row
        would bar the wrong half). Universal ones (no restriction) show for everyone.
        Order follows the catalog's insertion order."""
        key = f"{exalt_type}:{origin}" if (origin and f"{exalt_type}:{origin}" in self.budgets) else exalt_type
        out: list[BackgroundType] = []
        for bg in self.background_catalog.values():
            if bg.exalt_type and bg.exalt_type != exalt_type:
                continue
            if exalt_type in bg.excluded_exalt_types:
                continue
            if key in bg.excluded_origins:
                continue
            out.append(bg)
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
