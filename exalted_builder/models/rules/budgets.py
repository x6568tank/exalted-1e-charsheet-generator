"""
models/rules/budgets.py — the cost tables and the chargen budgets: bonus point
costs, XP costs, Background rules, Essence pool formulas, and the Exalt definitions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._base import (AbilityGroupMinimum, AbilityMinimum, AbilityName,
                    BackgroundBudgetTier, EssencePoolSpec, SpellCircle, VirtueName)


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
    # The Mountain Folk surcharge for a chargen Charm from ANOTHER caste's Pattern
    # (CH6 p.233 BP table: "Charms | 5 (7 if part of another caste's Pattern)"). 0 =
    # no such surcharge, which is every splat but the Mountain Folk. Mirrors
    # ExperienceCosts.new_charm_cross_pattern.
    charm_cross_pattern: int = 0
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
    # The Mountain Folk Superior Craftsmanship rates (CH6 p.237): "may purchase or
    # improve Craft Abilities and specialties for half the usual experience cost ...
    # (rounded up). This discount supersedes and replaces the normal discount
    # awarded to Favored Abilities." A Craft Ability raises at `craft` (current
    # rating — half the usual current×2) and a Craft specialty costs
    # `craft_specialty` (2 — half of 3 rounded up). None / 0 = the ordinary rates,
    # which is every splat but the Mountain Folk.
    craft: Optional[LinearCost] = None
    craft_specialty: int = 0
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
    # The Mountain Folk surcharge for a New Charm from ANOTHER caste's Pattern (CH6
    # p.233: "10 (12 if part of another Caste Pattern)"). 0 = no such surcharge,
    # which is every splat but the Mountain Folk. Mirrors
    # BonusPointCosts.charm_cross_pattern.
    new_charm_cross_pattern: int = 0
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
    # Whether this rule binds on BOTH sides of the lock. The default (False) is
    # chargen-only: Backgrounds change through the story, not by purchase, so nothing
    # checks them after the lock. Exactly two rules bind post-lock, both by human
    # ruling (the ONLY ones in the build): Sidereal Celestial Manse ≤3 (Sidereals
    # p.106, "cannot buy above
    # Celestial Manse ••• without special Storyteller permission") and Mountain Folk
    # Artifact ≤10 (CH6 p.234-235; the ceiling itself is the human's call — the book
    # prints no upper bound). `background_issues` runs post-lock (from
    # `validate.validate`) and applies ONLY the rules flagged here, so every other
    # splat's caps keep behaving exactly as they do today.
    bind_post_lock: bool = False
    # The EFFECTIVE rating this Background delivers, where a splat's book separates what
    # you buy from what it is worth. Mountain Folk Resources (CH6): "an effective
    # Resources rating equal to the number of dots invested in this Background + 2, but
    # cannot have more than three actual dots" — so `max_rating: 3` with
    # `effective_bonus: 2`, and Artifact ••• is a stored 3 worth 5.
    #
    # `effective_floor` is the same page's other half, and the half that is easy to
    # miss: "Characters LACKING this Background may still live comfortably with a
    # standard of living equivalent to Resources •• for the Enlightened and Resources •
    # for the Unenlightened." A floor is not a bonus — it applies at zero dots, where
    # `effective_bonus` must NOT (0 + 2 would give an unbought Background the same worth
    # as one dot bought). Keyed per origin, which the budget rows already are.
    #
    # Read through `validate.effective_background_rating`, the ONE read site. Nothing
    # else may add these — a consumer that reads `BackgroundEntry.rating` raw gets the
    # STORED number, which for a Mountain Folk is two dots short of the truth.
    effective_bonus: int = Field(default=0, ge=0)
    effective_floor: int = Field(default=0, ge=0)
    # A ceiling expressed as a TRAIT TOTAL rather than a literal: when true, the rating
    # may not exceed the sum of the character's Attributes (Sidereal Connections,
    # Sidereals pp.106-108: "cannot manage more points of Connections than the sum of
    # your character's Physical, Social and Mental Attributes combined"). The DATA names
    # what is summed; the engine never hardcodes "Attributes" or the 27 a default
    # chargen spread happens to sum to. Requires the character (the attribute sum), so
    # `background_issues` skips it when called without one — the silent-fallback shape
    # the merits-flaws precedent uses. Chargen only, like `max_rating`.
    max_rating_is_attribute_sum: bool = False
    # A BAR rather than a ceiling: this origin may not take the Background AT ALL
    # (rating must be 0) until `st_toggle` is set. Mortals and core p.103: "may not
    # purchase the Artifacts or Manse Backgrounds without Storyteller permission; if a
    # mortal has control over one of these, it's a plot device, not an object for him
    # to use." Distinct from `banned_backgrounds`, which is unconditional — this lifts
    # with ST permission. Chargen only.
    barred: bool = False
    # The PER-CHARACTER `HouseRules` field that, when True, lifts this rule for THIS
    # character ("Storyteller permission"). Read through
    # `validate.background_st_permitted`, the ONE read site, so no caller (UI included)
    # reaches into HouseRules for a name. Empty = no toggle, the rule binds
    # unconditionally. R2's Celestial Manse ceiling and R3's mortal bar each name their
    # toggle here.
    st_toggle: str = ""
    # Dots ABOVE this rating are bought one bonus point each, NOT from the Background
    # pool — the Mountain Folk Artifact ("with each dot beyond 5 costing one bonus
    # point and granting an additional dot of total artifacts", CH6 p.234-235).
    # 0 = no such threshold, which is every Background but the Mountain Folk Artifact.
    # Dots at or below it still go through the normal pool accounting (`cap_pre_bp_exempt`
    # keeps the MF's dots in the pool). Distinct from `bp_surcharge_per_dot`, which is
    # an EXTRA on top of `background_above_3` for above-cap dots; this is a flat
    # one-point price above a named rating, and the two compose differently.
    bp_above_rating: int = Field(default=0, ge=0)


class ChargenBudgets(BaseModel):
    # attributes: 8/6/4 across the three prioritized categories; all start at 1.
    # Which category gets which pool is derived from the per-category spend, not stored.
    attribute_pools: tuple[int, int, int] = (8, 6, 4)
    attribute_base: int = 1
    # A per-ATTRIBUTE floor the pools must be spent up to, on top of
    # `attribute_base`. Enlightened Mountain Folk (CH6 p.230): "no Attribute can have
    # a rating ... lower than three (3) dots" — combined with the base-1 start, that
    # means at least two of the pool must reach every one of the nine Attributes.
    # 0 = no floor, which is every other splat.
    attribute_min: int = 0
    # A per-ORIGIN Attribute ceiling on BOTH sides of the lock, overriding the
    # universal 5 / essence-derived ceiling. Enlightened Mountain Folk (CH6 p.230):
    # "no Attribute can have a rating higher than seven (7) dots". 0 = inherit the
    # normal ceiling, which is every splat but the Enlightened Mountain Folk.
    attribute_cap: int = 0
    # Per-ATTRIBUTE ceilings for this origin, on both sides of the lock — the
    # Unenlightened Mountain Folk's Intelligence bar (CH6 p.230: "cannot have an
    # Intelligence rating above two (2) dots or any other Attribute above five (5)").
    # Keyed by AttributeName value; an attribute absent here falls back to
    # `attribute_cap` or the normal ceiling. Empty = no named caps, which is every
    # splat but the Unenlightened Mountain Folk.
    attribute_caps: dict[str, int] = Field(default_factory=dict)
    # A per-ORIGIN Ability ceiling on both sides of the lock, overriding the
    # universal 5 / essence-derived ceiling. Enlightened Mountain Folk (CH6 p.230):
    # "can increase Abilities as high as six dots with bonus points". 0 = inherit
    # the normal ceiling, which is every splat but the Enlightened Mountain Folk.
    ability_cap: int = 0
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
    # Group-sum floors, the "•• divided among Craft Abilities" half of the Mountain
    # Folk Artisan schooling (CH6 p.230) — the parallel of required_min_abilities,
    # which is per-ability OR. Empty for every splat without a "divided among" floor
    # (all but the Mountain Folk Artisan).
    required_min_ability_groups: list[AbilityGroupMinimum] = Field(default_factory=list)

    # Abilities that MUST be among the character's Favored set (not just dotted) —
    # the Lunar rule that Survival is always Favored (p.90). Empty for splats with
    # no such forced inclusion (Solar, Dragon-Blooded, Abyssal).
    required_favored: list[AbilityName] = Field(default_factory=list)

    ability_dots: int = 25
    ability_min_caste_favored: int = 10    # >= 10 of the 25 on caste/favored abilities
    # The two-pool Ability budget (Mountain Folk, CH6 p.230): `ability_favored_dots`
    # is a SEPARATE pool spent only on Favored Abilities (a minimum of one dot in
    # each), and `ability_dots` then becomes the additional/free pool spent on any
    # Ability, capped per Ability at `ability_cap_pre_bp`. 0 = the one-pool shape
    # (Solar: 25 total, >= ability_min_caste_favored on caste/favored) every other
    # splat uses. Enlightened MF: 10 favored + 25 free; Unenlightened: 14 favored + 8.
    ability_favored_dots: int = 0
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
    # Background dots by CASTE, for a splat whose aristocrat caste gets a richer
    # budget than its undercastes (Mountain Folk, CH6 p.230: Artisans 13, Enlightened
    # undercastes 10, Unenlightened 6). Keyed by CasteDefinition.id; a caste absent
    # from the map falls back to `background_dots`. Empty = every splat where the
    # budget does not vary by caste.
    background_dots_by_caste: dict[str, int] = Field(default_factory=dict)
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
    # The Backgrounds this splat/origin's own book ENUMERATES — the list that decides
    # what the dropdown OFFERS. Empty = the book has not been transcribed, and the
    # catalogue falls back to the per-Background `exalt_type` tag. Read through
    # `RuleSet.catalogue_backgrounds_for`.
    #
    # Entries are lowercased NAMES ("allies"), or an exact id ("background.whispers")
    # where a name is not enough. Use an id in two cases:
    #   * the name exists twice and this splat wants a particular copy — a Sidereal's
    #     Connections is not a Dragon-Blooded's;
    #   * the Background is TAGGED for another splat but this book grants it anyway.
    #     The God-Blooded chapter (PG p.50) is the case: twelve of its twenty-five are
    #     printed in other splats' books and cross-referenced, and no `exalt_type`
    #     string can say "Abyssal and God-Blooded". An id bypasses the tag; a name
    #     does not.
    #
    # ⚠ NOT the same field as `allowed_backgrounds` above, and the distinction is the
    # whole reason this exists rather than reusing it:
    #
    #   allowed_backgrounds     HARD VALIDATION. A name outside it is an ERROR
    #                           (`background-not-allowed`). Opt-in for the one or two
    #                           origins whose book forbids the rest outright — the
    #                           Sidereal ronin (p.100), the Illuminated Solar.
    #   catalogue_backgrounds   OFFERED LIST. A name outside it is simply not in the
    #                           dropdown. Backgrounds stay soft free text: a player who
    #                           types one in anyway is still legal, and the Storyteller's
    #                           `all_backgrounds_available` reveals the rest.
    #
    # Reusing the first for the second would have made every free-text Background
    # ILLEGAL for every splat whose list got transcribed — which is exactly what the
    # suite caught when this was first written as one field.
    catalogue_backgrounds: list[str] = Field(default_factory=list)
    # Backgrounds this origin may NOT take AT ALL, as lowercased NAMEs — the named
    # complement of `allowed_backgrounds`, for the one or two bans a book prints on
    # an otherwise-open list. Mountain Folk: Cult is "explicitly prohibited" by the
    # Great Geas (CH6 p.234). Empty = no named bans, which is every splat but the
    # Mountain Folk.
    banned_backgrounds: list[str] = Field(default_factory=list)
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
    # A per-ORIGIN ceiling on post-lock Essence, overriding ExaltDefinition.essence_cap
    # for this origin only. Enlightened Mountain Folk cap at 5 (splat-wide, on the
    # ExaltDefinition row); the Unenlightened row caps at 3 ("cannot have an Essence
    # rating above 3", CH6 p.230). 0 = inherit the splat-wide cap, which is every
    # other origin.
    essence_cap: int = 0
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
    # A HARD ceiling on Willpower that binds after the lock as well (bonus points
    # and XP cannot buy past it), unlike `willpower_start_cap` which only binds at
    # creation. Unenlightened Mountain Folk (CH6 p.230): "cannot ever have a
    # permanent Willpower above 6". 0 = no hard cap, which is every other splat.
    willpower_hard_cap: int = 0

    @field_validator("attribute_mode")
    @classmethod
    def _check_attribute_mode(cls, v: str) -> str:
        if v not in ("category", "caste_favored"):
            raise ValueError(
                f"attribute_mode must be category/caste_favored, got {v!r}")
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
    # ⚠ It is the DEFAULT, not the whole story: the right Merits reopen Terrestrial
    # Martial Arts (all but Spirit Walking) and Terrestrial Sorcery, so it is read
    # through `engine.merits.merits_and_flaws_calc` (decision 0011).
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
    # 2026-07-30 — the printed Merit text does not itself state the 3). ⚠
    # `merits_and_flaws_calc` RAISES this 1 to 3 rather than removing it.
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
    # What this splat calls the things it spends its Charm pool on, PLURAL: a ghost
    # buys "Arcanoi", not Charms (E:Ab p.126). Presentation only, exactly like
    # `caste_noun` above — the underlying pool, its budget row (`charm_count`) and
    # the single `charm_picks` enumeration are unchanged, and a splat that never
    # sets it reads "Charms". Used by the chargen unspent-picks warning and by the
    # picker's readout, so the two cannot disagree about what to call the pool.
    charm_noun: str = "Charms"
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
    # Arts on the sheet, flagged unusable, and can still teach. True everywhere else.
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
    # ⚠ The SECOND source of a merged pool; the first is the Beacon of Power Merit,
    # reachable only through `merits_and_flaws_calc`. Both are OR'd into the one read
    # site, `derive.essence_pool_is_merged`. Two sources, one consumer — adding a
    # third source here must not add a third read.
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
