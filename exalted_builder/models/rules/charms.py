"""
models/rules/charms.py — the Charm and spell models: the cost, the variants, the
prerequisites, Submodules, and Elemental Powers.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import (AbilityMinimum, AttributeMinimum, CharmType, Damage, Source,
                    SpellCircle)


# --------------------------------------------------------------------------- #
# Charms & spells
# --------------------------------------------------------------------------- #


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
    # ⚠ NOT homebrew-only, despite having no printed consumer when it was created:
    # Stolen Wax Discipline (E:Ab p.237, "5 motes, one lethal health level") became
    # the first on 2026-08-01. Do not remove it as dead homebrew scaffolding.
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


class ElementalPower(BaseModel):
    """One of the nine learnable elemental powers (PG p.68, CH2 - Godblooded.md).

    Core p.296 prints seven (Aegis, Coarse Skin, Dragon's Suspire, Element's Domain,
    Enshroud, Mobility, Rejuvenation); Games of Divinity p.56 adds Consume Element and
    Plague of Menaces as the only two of its powers "learned" by descendants of
    elementals. They are a Charm-like catalogue for Elemental-origin God-Blooded only,
    bought at `bp_cost` bonus points chargen or `bp_cost * 2` XP in play ("learned in
    play for a number of experience points equal to double its bonus point value").
    `required_merits` names Merit ids (e.g. `mf.elemental-dominion`); every power
    requires that chain, and Rejuvenation additionally requires `mf.primal-restoration`.

    `activation` and `description` are descriptive only — decision 0008 keeps combat
    effects as text. Training time (p.68's "takes a number of days equal to the bonus
    point cost") is NOT built (standing 2026-07-30 ruling)."""
    model_config = ConfigDict(frozen=True)
    id: str                                  # namespaced `elemental.<slug>`
    name: str
    bp_cost: int = Field(default=7, ge=0)
    min_essence: int = Field(default=2, ge=1)
    required_merits: list[str] = Field(default_factory=list)
    activation: str = ""
    description: str = ""
    source: Source = Field(default_factory=Source)


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
    # The martial-arts TIER of the style this Charm belongs to ("Terrestrial" /
    # "Celestial" / "Sidereal"), "" for a non-martial-arts Charm or a style whose
    # page prints no tier.
    #
    # ⚠ NOT AUTHORED IN THE CHARM FILES. `rules_db` projects it from the style
    # catalogue at load time, so `MartialArtsStyle.tier` stays the single authored
    # copy and cannot drift from this one. Setting it in a charms JSON is a mistake
    # — the loader overwrites it.
    #
    # ⚠ Ask `ma_tier` what KIND of style a Charm belongs to; ask `open_to_tiers` who
    # may learn it. They are NOT interchangeable — `open_to_tiers` is far wider, so
    # using it for the p.101 Sidereal chargen cap counts every Celestial-open style
    # where only the three Sidereal ones qualify. See docs/status/martial-arts-styles.md.
    ma_tier: str = ""
    # A style whose OWN text names who may learn it, narrower than any tier. Entries
    # are "<Splat>" or "<Splat>:<caste>", and the character must satisfy ONE of them.
    # Dreaming Pearl Courtesan (PG p.249): "it can be mastered only by the Solar
    # Exalted and Moonshadow Caste Abyssals" -> ["Solar", "Abyssal:moonshadow"].
    # This narrows access; it never widens it, so a Charm still has to pass the
    # ordinary splat/tier test first.
    restricted_to: list[str] = Field(default_factory=list)
    # A cap the LEARNER must stay under, not a minimum they must reach — the only
    # requirement in the build that a character can fail by being too good. Celestial
    # Monkey (PG p.246): "those who would grow in the wisdom of the Celestial Monkey
    # can not have any Virtue rating higher than 3". 0 means no cap.
    max_virtue: int = Field(default=0, ge=0)
    type: CharmType
    min_ability: int = Field(default=0, ge=0)
    # For splats whose Charms are Attribute-keyed rather than Ability-keyed (Lunar,
    # p.122): the AttributeName value `min_ability` is the required rating in. ""
    # (default) means the Charm gates on `category`'s Ability as usual. A Charm
    # should set at most one of min_attribute / an Ability-resolving category.
    min_attribute: str = ""
    # For splats whose Charms are VIRTUE-keyed (ghosts, E:Ab p.234-253 — every Arcanos
    # prints exactly one "Minimum Compassion/Conviction/Temperance/Valor" alongside
    # its Minimum Essence, and none prints an Ability at all). The
    # VirtueName value `min_ability` is the required rating in, exactly as
    # `min_attribute` works — the third and last of the three keyings.
    #
    # ⚠ `min_ability` holds the RATING here, as it does for `min_attribute` —
    # everything downstream (pricing, the picker's tree layout, Combo cost) keys off
    # it, so a Charm keyed a new way costs nothing to price. The field name is wrong
    # for this case and right for the common one.
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
    # The Mountain Folk Ox-Body Technique caps on the character's HIGHEST Virtue
    # (CH6 p.245: "Jadeborn cannot develop Ox-Body Technique more times than their
    # highest Virtue") — not a named Virtue, so `repeatable_cap_virtue` cannot hold
    # it. It is its own bool, mirroring the `repeatable_cap_virtue` retarget pattern
    # (the "highest" is the MAX of the four, which no single Virtue name can hold).
    # False for every other splat's Ox-Body.
    repeatable_cap_highest_virtue: bool = False
    # A FLAT ceiling on a repeatable Charm's purchases, no trait resolution — the
    # Mountain Folk Essence Satiation Method and Stone-Still Lungs are both "three
    # times" (CH6 pp.245-246), with the THIRD purchase gated on Essence 3. That gate
    # is `repeatable_cap_ability: "essence"`; `repeatable_cap_max` then holds the
    # printed "three" so an Essence-5 Jadeborn cannot buy five. Resolved as
    # `min(trait_cap, repeatable_cap_max)` in validate._repeatable_purchase_cap. 0 =
    # no flat cap, which is every other repeatable Charm.
    repeatable_cap_max: int = Field(default=0, ge=0)
    variants: list[CharmVariant] = Field(default_factory=list)
    # How many variants a single purchase selects. Ox-Body: always 1 (the default
    # for both fields below). Deadly Beastman Transformation (p.124): the FIRST
    # purchase grants 2 Gifts, every purchase after grants 1.
    variant_picks_first_purchase: int = 1
    variant_picks_per_purchase: int = 1
    # Each variant may be taken AT MOST ONCE, so the purchase cap is additionally
    # bounded by how many variants there are. Environmental Hazard-Resisting
    # Meditation (Caste Book: Zenith p.72-73) prints exactly this — "until she has
    # purchased all four versions", alongside the separate Resistance-dots cap — and
    # is the only Charm with it today. False for Ox-Body, whose whole point is taking
    # the same health-level package again.
    variants_unique: bool = False
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
