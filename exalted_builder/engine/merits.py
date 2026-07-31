"""
engine/merits.py — the ONE place Merits & Flaws have mechanical effects.

Merits & Flaws were removed in June 2026 because the old implementation scattered
their effects across every file they touched: a Merit that changed a Charm's cost
edited the cost code, one that granted a pool edited the derivation, and there was no
way to see what any of it did without grepping the tree. **Decision 0011** is that
they come back as a single calculation, and this module is it.

The contract, and the thing to preserve:

  * `rules.MeritFlaw` is INERT DATA — printed text, cost, prerequisites. It says
    nothing about what a Merit does. A Merit with no mechanical effect (most of them)
    needs a data row and nothing else.
  * `merits_and_flaws_calc` maps the Merits a character HOLDS to a `MeritEffects`
    value object. It is the only function that knows any Merit's id.
  * Everything else — validate, derive, costs, advancement, the UI — reads
    `MeritEffects` fields. **No caller anywhere may branch on a Merit id.** If a new
    Merit needs an effect the object cannot express, add a FIELD here; do not add a
    lookup there. That rule is what stops the June situation recurring.

`MeritEffects` is keyed by EFFECT, not by Merit taxonomy, deliberately: the general
M&F chapter is a much broader set (social, physical, supernatural) and will attach new
Merits to existing effects far more often than it invents new ones.

Source: Player's Guide pp.120-122 (the Thaumaturgy Merits). These were authored first
because they are the mortal magic-access set — see docs/status/merits-flaws.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..models.character import Character
from ..models.rules import AttributeName, MeritFlaw, RuleSet, SpellCircle

# --------------------------------------------------------------------------- #
# The ids this module knows. Nothing outside engine/merits.py may name these.
# --------------------------------------------------------------------------- #

# "Characters may only receive up to 10 extra bonus points from Flaws, regardless of
# the number taken" (PG p.16). The same ceiling governs experience after creation:
# "Characters with more than 10 points of Flaws receive no experience for the excess"
# (p.17). One constant for both.
FLAW_POINT_CAP = 10

ESSENCE_AWARENESS = "thaum.essence-awareness"
ESSENCE_MASTERY = "thaum.essence-mastery"
OATHBOUND_MAGIC = "thaum.oathbound-magic"
HOLY_MIEN = "thaum.holy-mien"
# Holy Mien "grants the character possessing it the Priest Merit at the one-point level
# at no extra cost and reduces the cost of the seven-point level to six bonus points"
# (PG p.121). Priest itself is in the general chapter (p.24), which is why this could
# not be wired until that landed.
PRIEST = "mf.priest"

# Spirit Walking is the second Charm of the Immaculate enlightenment tree and is what
# grants access to CELESTIAL Martial Arts ("before a Dragon-Blooded may walk any Dragon
# Path, she must master this skill"). A mortal can never reach those, so Essence
# Mastery's grant of Terrestrial Martial Arts stops short of it — human, rules
# authority, 2026-07-30, and confirmed as "just the one Charm": its prerequisite,
# Spirit Sight, is legal and simply dead-ends.
#
# The existing tier machinery does NOT catch this: Spirit Walking is `open_to_all`, so
# any splat able to reach Terrestrial MA at all would otherwise be handed it.
SPIRIT_WALKING = "dragonblooded.martial-arts.spirit-walking"

# The four trait-forfeit Flaws (PG pp.35-36, p.20), and the bonus points each pays per
# dot given up. The rate is what converts a purchase's point value back into dots, so
# the forfeit needs no field of its own on the purchase.
DIMINISHED_ATTRIBUTES = "mf.diminished-attributes"
CALLOUS = "mf.callous"
UNSKILLED = "mf.unskilled"
WEAK_WILLED = "mf.weak-willed"

# Health levels (A2). Large Size at four points grants "one additional -0 health level";
# at six, "one -0 level and one -1 level" (p.20). Small "costs her one -1 health level"
# (p.32). Keyed by tier because the tier IS the printed distinction.
LARGE_SIZE = "mf.large-size"
SMALL = "mf.small"

_LARGE_SIZE_LEVELS: dict[str, tuple[int, ...]] = {"4": (0,), "6": (0, -1)}
_SMALL_REMOVES: tuple[int, ...] = (-1,)

# Trait caps (A3). The universal ceiling on any trait in this build is 5; these are the
# entries that move it for one character.
LEGENDARY_ATTRIBUTE = "mf.legendary-attribute"
TRUE_PARAGON = "mf.true-paragon"
DISFIGURED = "mf.disfigured"
WEAK_ESSENCE = "mf.weak-essence"

DOT_MAX = 5                        # the universal trait cap these entries depart from

# Disfigured: three points "cannot ever have an Appearance rating greater than 1"; four
# points is "an Appearance of 0 that cannot be improved with bonus or experience points"
# (p.33). A cap of 0 expresses the unraisability on its own.
_DISFIGURED_APPEARANCE_CAPS: dict[str, int] = {"3": 1, "4": 0}
# Keyed by AttributeName.value, which is LOWERCASE — the caps dict is looked up with
# that value, so every key written into it must be normalised the same way.
APPEARANCE = "appearance"

# True Paragon raises every Virtue's ceiling to 6 (p.22) and requires the Paragon
# Nature — the exact Nature that Callous bars, which is why one is a required-Nature
# check and the other a barred-Nature one.
TRUE_PARAGON_VIRTUE_CAP = 6

# Weak Essence "reduces the character's starting Essence rating to 1" (p.41).
WEAK_ESSENCE_START = 1
# "If used to represent a new Exalt, the player may choose to withhold up to five Charms
# in reserve (typically until after the character can raise Essence in play). Withheld
# Charms waive their experience cost, though they still require the same training time."
# Read (human, rules authority, 2026-07-30) as banked PICKS rather than Charms named at
# creation: the Flaw exists because a character at Essence 1 cannot choose well, so what
# is held back is the choice itself.
WEAK_ESSENCE_CHARM_CREDITS = 5

_FORFEIT_RATES = {
    DIMINISHED_ATTRIBUTES: 3,      # "three points for every Physical Attribute dot"
    CALLOUS: 2,                    # "two bonus points for every dot of Virtues"
    UNSKILLED: 1,                  # "one bonus point for every dot of Abilities"
    WEAK_WILLED: 1,                # "one bonus point for every dot of permanent Willpower"
}

# Callous "automatically loses this Flaw at no cost" once the character has 9 dots of
# Virtues (p.35). Below that its Willpower ceiling and Nature ban both apply.
CALLOUS_EXPIRY_VIRTUE_DOTS = 9
CALLOUS_WILLPOWER_MARGIN = 1
PARAGON_NATURE = "Paragon"

# Weak-Willed's floors (p.36): "Exalted characters with this Flaw may not begin with a
# Willpower rating lower than 4, unless they are also Callous. UnExalted and Callous
# Exalted characters may have a Willpower score as low as 2."
WEAK_WILLED_FLOOR_EXALTED = 4
WEAK_WILLED_FLOOR_MORTAL = 2

# Essence-pool shape (A5). Two entries that change the pools themselves rather than any
# term feeding them.
LEGENDARY_BREEDING = "mf.legendary-breeding"
BEACON_OF_POWER = "mf.beacon-of-power"

# "her Breeding Background (see E:DB, p. 158) has a rating of 6. This superb ancestry
# adds 6 motes to her Personal Essence pool and 11 motes to her Peripheral Essence pool"
# (p.28). Those two totals are the rating-6 row of the Breeding table — one more step of
# the +1 Personal / +2 Peripheral the printed 0..5 rows already climb — so the Merit is
# modelled as the RATING it says it grants, and the motes come from the table in
# data/exalts.json like every other Breeding rating's do. Requires Breeding 5 to buy,
# which is a trait prerequisite and not yet checked anywhere (see the triage doc).
LEGENDARY_BREEDING_RATING = 6
# Its "Characters must already have Breeding 5 to purchase this Merit" (p.28) is a TRAIT
# prerequisite, which `MeritFlaw.prerequisites` cannot express — that holds Merit ids
# only. It now lives in the catalogue as `MeritFlaw.trait_prerequisites` and is
# evaluated generically, so no constant is needed here and this module learns nothing
# about it. Until 2026-07-31 nothing checked it at all and the Merit paid its full
# rating-6 row to a character with no Breeding whatsoever — an Outcaste, typically.


@dataclass(frozen=True)
class MeritEffects:
    """What a character's Merits and Flaws do, as data.

    Every field is a NEUTRAL default for a character holding no Merits, so callers can
    use the result unconditionally rather than testing for its absence.
    """

    # --- Essence ----------------------------------------------------------- #
    # Does the character have access to an Essence pool at all? Mortals have none
    # ("they lack an Essence pool, either Peripheral or Personal", PG p.114) until
    # Essence Awareness unlocks part of it. True for every Exalt, always.
    essence_pool_unlocked: bool = False
    # Is that access UNRESTRICTED? Essence Awareness gives a third of the pool freely
    # and the rest on a Willpower roll; Essence Mastery removes the restriction
    # entirely. We do not roll dice (decision 0009), so the split is narrative and
    # only the distinction between "some access" and "full access" is modelled.
    essence_pool_unrestricted: bool = False
    # Raises ExaltDefinition.essence_cap when set. Essence Mastery is what lets a
    # mortal exceed Essence 1 at all, and 3 is "the limit of human potential —
    # mortals that exceed Essence 3 become gods" (PG p.114). None = no override.
    essence_cap_override: int | None = None
    # An EFFECTIVE rating for the Background that feeds the Essence pools
    # (EssencePoolSpec.breeding_background — Dragon-Blooded Breeding), replacing the
    # rating the character actually bought. Legendary Breeding's whole effect is
    # "her Breeding Background has a rating of 6"; the motes follow from the table.
    # None = use the purchased rating. Ignored by splats with no such Background.
    breeding_rating_override: int | None = None
    # Beacon of Power: "a single Essence pool equal to the sum of their Personal and
    # Peripheral Essence, all of which is considered Peripheral for the purposes of
    # anima displays" (p.41). Personal becomes 0 and everything sits in Peripheral —
    # the pools are still computed normally, they are just merged afterwards.
    # The anima-display half needs nothing: this build models no anima costs at all.
    essence_single_pool: bool = False

    # --- Magic access ------------------------------------------------------ #
    # Charm categories opened to a character whose splat is otherwise Charmless, and
    # the individual Charms still withheld inside them. Both are consulted by
    # validate.charm_matches_splat; `barred_charm_ids` wins over `open_charm_categories`.
    open_charm_categories: frozenset[str] = frozenset()
    barred_charm_ids: frozenset[str] = frozenset()
    # Withhold the Immaculate Order Charms (the five elemental Dragon styles) from
    # within an opened category. A CLASS of Charms rather than a list of ids, so it
    # is its own flag: Essence Mastery opens Terrestrial Martial Arts, but the
    # Immaculate Dragon Paths are closed to mortals (human, rules authority,
    # 2026-07-30). Consistent with barring Spirit Walking — the Dragon Paths are
    # exactly what Spirit Walking exists to unlock.
    bar_immaculate_charms: bool = False
    # Spell circles granted outright, without the initiating Charm the engine normally
    # requires. Mortals cannot hold Charms, so a Merit-granted circle is the only way
    # they reach sorcery at all.
    granted_circles: frozenset[SpellCircle] = frozenset()

    # --- Points ------------------------------------------------------------ #
    # Bonus points ADDED to the chargen allowance by Flaws, net of Oathbound Magic's
    # same-arena stacking reduction and CLAMPED to FLAW_POINT_CAP.
    bonus_point_grant: int = 0
    # What the Flaws would have granted before the cap, so the UI can say "10 of 13"
    # rather than silently swallowing three points the player thinks they have.
    flaw_points_raw: int = 0

    # --- Trait caps -------------------------------------------------------- #
    # Per-Attribute ceilings that REPLACE the universal 5 for the trait named, keyed by
    # AttributeName.value. Deliberately one field for both directions: Legendary
    # Attribute raises a cap and Disfigured lowers Appearance, and "what may this trait
    # reach" is one question however it is answered. Keyed by EFFECT, not by Merit, per
    # the module docstring. Absent = the universal 5.
    attribute_caps: dict[str, int] = field(default_factory=dict)
    # The ceiling on every Virtue, when a Merit raises it — True Paragon's "may spend
    # bonus or experience points to raise any Virtue to a rating of 6" (p.22). None =
    # the universal 5. Permanent Willpower's own maximum of 10 is untouched by this;
    # the page says so explicitly.
    virtue_cap: int | None = None
    # Essence forced at creation — Weak Essence "reduces the character's starting
    # Essence rating to 1" (p.41). None = the splat's own starting Essence.
    essence_start_override: int | None = None
    # --- Cost repricing (A4) ------------------------------------------------ #
    # Brigid's Heir "doubles the bonus/experience cost and training time of all Charms
    # but halves the corresponding costs and training time for spells" (p.30). Flags
    # rather than multipliers because the Charm half is exempt along the Terrestrial
    # sorcery line — see `adjust_charm_cost`, which is what callers actually use.
    # Training time is not modelled anywhere (it is Storyteller bookkeeping), so only
    # the point costs move.
    charm_cost_doubled: bool = False
    spell_cost_halved: bool = False

    # --- Favored Abilities (A4) --------------------------------------------- #
    # Extra Favored Abilities granted, one per purchase of Prodigy (p.21). Added to the
    # count `validate.favored_ability_count` requires, so the existing favored-count
    # check does the work.
    extra_favored_abilities: int = 0

    # The MOST chargen Charm picks a Flaw lets the character bank for post-lock use,
    # XP-free. A ceiling, not an entitlement: how many were actually withheld is the
    # unspent remainder of the chargen Charm budget, which only validate can count
    # (see `validate.withheld_charm_credits`). 0 = no such Flaw held.
    charm_credits_max: int = 0
    # Display NAMES (never ids) of held entries whose printed Nature requirement is not
    # met — True Paragon is "only characters with the Paragon Nature may purchase or
    # retain this Merit". Names so the UI can report without naming an id.
    nature_requirement_unmet: tuple[str, ...] = ()
    # Display NAMES of held entries whose printed TRAIT prerequisite is not met — a
    # Background rating, as opposed to `MeritFlaw.prerequisites`, which holds only other
    # Merit ids. Same shape as the Nature check above, and for the same reason: the UI
    # must be able to report it without learning which Merit it is.
    trait_requirement_unmet: tuple[str, ...] = ()

    # --- Health track ------------------------------------------------------ #
    # Levels a Merit adds, as (wound penalty, source label) — the label is the Merit's
    # own name, read from the catalogue, so the sheet can say where a level came from
    # exactly as it does for Ox-Body. Large Size is the first non-Charm source of a
    # health level in the build.
    health_levels_granted: tuple[tuple[int, str], ...] = ()
    # Wound penalties a Flaw takes AWAY, one level per entry. Small is the only one.
    # A base level goes before a granted one, matching how a curse already removes.
    health_levels_removed: tuple[int, ...] = ()

    # --- Chargen budget forfeits ------------------------------------------- #
    # Four Flaws buy their bonus points by GIVING UP free chargen dots rather than by
    # imposing a disadvantage: Diminished Attributes (3 BP per Physical Attribute dot),
    # Callous (2 per Virtue dot), Unskilled (1 per Ability dot) and Weak-Willed (1 per
    # permanent Willpower dot). The bonus points themselves need nothing special —
    # every one is priced from the purchase, so `flaw_points` already grants them.
    # These fields are the OTHER half of the bargain: the budget the character no
    # longer has. Expressed as a delta rather than as a rewritten ChargenBudgets so
    # the printed budget stays the one in data/ and the difference is always visible.
    #
    # Dots are derived, not stored: each entry's point value IS its dot count times a
    # fixed rate, so `dots = points // rate` and no new model field is needed.
    forfeited_ability_dots: int = 0
    forfeited_virtue_dots: int = 0
    forfeited_willpower_dots: int = 0
    # {"Physical" | "Social" | "Mental": dots}. Keyed by category because Diminished
    # Attributes is printed as three separate Flaws sharing one entry — the Mental and
    # Social versions "are considered Mental and Social Flaws rather than falling into
    # the Physical category" (p.36) — and the purchase names which in `detail`.
    forfeited_attribute_dots: dict[str, int] = field(default_factory=dict)
    # Callous: "may not begin play with a Willpower rating more than one point higher
    # than the sum of their two highest Virtues" (p.35). None for everyone else, which
    # is NOT the same as 0 — no margin at all would be a real and different rule.
    # This is the one sanctioned exception to decision 0005: the human ruled 2026-07-30
    # that Willpower moves with the Virtues for a Callous character and stays pinned
    # for everybody else.
    willpower_virtue_margin: int | None = None
    # Whether permanent Willpower's Virtue component keeps TRACKING the current Virtues
    # after the lock instead of being the frozen `wp_virtue_component`. True only for
    # Callous, and it is the other half of the ruling above: the margin field alone is
    # a chargen ceiling, which does nothing post-lock, so raising a Virtue on a Callous
    # character left Willpower where it was (found in the 2026-07-31 click-through).
    # Decision 0005 still governs everybody else.
    willpower_tracks_virtues: bool = False
    # A floor under starting permanent Willpower — Weak-Willed's "may not begin with a
    # Willpower rating lower than 4" for the Exalted, 2 for the un-Exalted or Callous.
    # 0 = no floor imposed by any held Flaw.
    willpower_floor: int = 0
    # Natures a held Flaw forbids. Callous bars Paragon (p.35); True Paragon requires
    # it, which is why this is a set of names rather than a Callous-shaped boolean.
    barred_natures: frozenset[str] = frozenset()

    # --- Cross-Merit effects ----------------------------------------------- #
    # Merits held FREE because another Merit grants them (Holy Mien -> Priest at the
    # one-point level). The character has them whether or not they appear on the
    # sheet, so the UI shows them as granted rather than purchased.
    granted_merits: frozenset[str] = frozenset()
    # Price overrides another Merit imposes, {merit_id: {tier: points}}. Holy Mien
    # drops Priest's seven-point level to six. Consulted by validate.merit_points
    # before any of the entry's own cost shapes.
    merit_cost_overrides: dict[str, dict[str, int]] = field(default_factory=dict)

    # --- Bookkeeping ------------------------------------------------------- #
    # Ids that produced no effect, for the UI to explain rather than silently ignore.
    narrative_only: tuple[str, ...] = ()


def _held(ruleset: RuleSet, character: Character) -> list[tuple[MeritFlaw, object]]:
    """(definition, purchase) for every Merit the character holds that resolves in the
    RuleSet. An unresolvable id is skipped here and reported by validate, matching how
    unknown Charm ids are handled — graceful, never a crash."""
    out = []
    for purchase in character.merits_flaws:
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is not None:
            out.append((definition, purchase))
    return out


def oathbound_bonus_points(character: Character, ruleset: RuleSet) -> int:
    """Bonus points granted by Oathbound Magic, net of the stacking rule.

    PG p.122: "Oaths in a particular area … can be stacked, but each stacked oath past
    the first is reduced in value by the total number of oaths. So, a pair of oaths to
    never initiate violence and to use no bladed weapon would be worth five bonus
    points, rather than six (3 + 3, -1 for an additional oath in the same arena)."

    Read literally against the worked example: within one arena, every oath past the
    first loses (number of oaths in that arena − 1) points. Two oaths → the second
    loses 1 → 3 + 2 = 5. ✓  The reduction floors at zero rather than going negative;
    the page does not contemplate an oath of negative worth.

    Oaths in DIFFERENT arenas do not interact, which is the point of tracking `arena`.
    Purchases with a blank arena are each treated as their own — the conservative
    reading, since the page's reduction only ever applies "in a particular area".
    """
    by_arena: dict[str, list[int]] = {}
    for definition, purchase in _held(ruleset, character):
        if definition.id != OATHBOUND_MAGIC:
            continue
        value = definition.cost_options.get(purchase.tier, 0)
        key = purchase.arena or f"\0{id(purchase)}"      # blank arena = its own bucket
        by_arena.setdefault(key, []).append(value)

    total = 0
    for values in by_arena.values():
        penalty = len(values) - 1                       # 0 for a lone oath
        # Highest-value oath keeps its full worth; the page's example reduces the
        # *additional* oaths, so sort descending and charge the penalty to the rest.
        for i, value in enumerate(sorted(values, reverse=True)):
            total += value if i == 0 else max(0, value - penalty)
    return total


def flaw_points(ruleset: RuleSet, character: Character) -> int:
    """Total bonus points the character's FLAWS are worth, before the cap.

    Every Flaw grants its printed value — "Flaws work in reverse, imposing
    disadvantages in exchange for additional bonus points" (PG p.16) — so this is not
    special to Oathbound Magic; Oathbound is merely the one whose value varies and
    whose same-arena oaths reduce each other, which `oathbound_bonus_points` handles.

    NOTE Oathbound's points ARE counted toward the cap. The page says "regardless of
    the number taken", and an oath is a Flaw. Its own rule that oath points "must be
    tied to the Traits purchased using them" — i.e. they are earmarked rather than
    fungible — is NOT modelled: this build has a single bonus-point pool. Flagged in
    docs/status/merits-flaws.md rather than guessed at.
    """
    total = oathbound_bonus_points(character, ruleset)
    for definition, purchase in _held(ruleset, character):
        from .validate import effective_merit_kind, merit_points   # validate imports merits
        if definition.id == OATHBOUND_MAGIC:
            continue
        if effective_merit_kind(definition, purchase) != "flaw":
            continue
        total += merit_points(definition, purchase, character.exalt_type,
                              character.caste)
    return total


def forfeit_rate(definition) -> int | None:
    """Bonus points this entry pays per dot given up, or None if it is not a
    trait-forfeit Flaw at all.

    The ONE thing a caller outside this module may ask about the forfeit Flaws, and it
    exists so the editor can collect DOTS rather than points: the human ruled
    2026-07-31 that the dots are what a player chooses and the payout follows, which is
    also how the page phrases it ("three points for every Physical Attribute dot").
    Returning the rate rather than a set of ids keeps decision 0011 intact — the caller
    still never learns which Merit it is holding, only that this one converts.

    `dots x forfeit_rate(d)` is what belongs in `MeritFlawPurchase.points`; the engine
    reads points and divides back, so nothing downstream changes.
    """
    return _FORFEIT_RATES.get(definition.id)


def forfeit_trait_label(definition) -> str:
    """What a dot of this forfeit BUYS BACK, for the editor's field label. Empty for
    anything that is not a forfeit Flaw. Kept beside the rate so the two cannot drift,
    and phrased as the trait rather than the Flaw so no id leaks into the UI."""
    return {DIMINISHED_ATTRIBUTES: "Attribute", CALLOUS: "Virtue",
            UNSKILLED: "Ability", WEAK_WILLED: "Willpower"}.get(definition.id, "")


def uses_arena(definition) -> bool:
    """Whether `MeritFlawPurchase.arena` means anything for this entry. True only for
    Oathbound Magic, whose same-arena stacking rule (p.122) is the only thing that
    reads it — the editor was showing an "arena (combat, food…)" box beside EVERY
    menu-priced entry, Callous and Large Size included, where it does nothing."""
    return definition.id == OATHBOUND_MAGIC


def detail_choices(definition) -> tuple[str, ...]:
    """The closed set of values `MeritFlawPurchase.detail` may take for this entry, or
    () where the detail is genuinely free text (a note, an oath's wording).

    Two entries structure their detail, and BOTH were broken by being free text:

      * Diminished Attributes — which Attribute category the dots come out of. The page
        prints three versions of one Flaw, the Mental and Social variants being
        "considered Mental and Social Flaws rather than falling into the Physical
        category" (p.36). `_attribute_forfeits` title-cases whatever was typed and
        defaults to Physical, so a typo silently became a fourth category.
      * Legendary Attribute — which Attribute gets the raised ceiling. Read as an
        `AttributeName.value`, so anything else left the Merit inert with no complaint
        at all (reported 2026-07-31).

    Returned as display strings; the caller stores them verbatim. Values are matched
    case-insensitively downstream, which is why the Attribute names may be Title Case
    here while `AttributeName.value` is lower.
    """
    if definition.id == DIMINISHED_ATTRIBUTES:
        return ("Physical", "Mental", "Social")
    if definition.id == LEGENDARY_ATTRIBUTE:
        return tuple(a.value.title() for a in AttributeName)
    return ()


def _trait_rating(character: Character, req) -> int:
    """The character's current rating in the trait a prerequisite names.

    Backgrounds match by NAME, case-insensitively and on the highest instance held: a
    player types those, and the same Background may legitimately appear twice (two
    Manses). An Attribute matches its `AttributeName.value`. An unknown trait reads 0,
    so a mis-authored prerequisite reports rather than silently passing.
    """
    if req.kind == "background":
        return max((b.rating for b in character.backgrounds
                    if b.name.strip().casefold() == req.name.strip().casefold()),
                   default=0)
    for attr, rating in character.attributes.items():
        if attr.value == req.name.strip().casefold():
            return rating
    return 0


def _forfeited_dots(ruleset: RuleSet, character: Character) -> dict[str, int]:
    """{merit_id: dots given up} for each trait-forfeit Flaw the character holds.

    Each of the four pays a FIXED number of bonus points per dot, so the dot count is
    recoverable from the point value the purchase already records — `_FORFEIT_RATES`
    is that conversion. A purchase whose points are not a whole multiple of the rate
    rounds DOWN — the player-unfavourable direction, so a mis-entered value can never
    conjure budget out of nothing.

    That rounding is currently reachable through the DATA, not just through bad input:
    `mf.callous` is authored with a 2..10 tier menu, but its own text prices it at "two
    bonus points for every dot of Virtues", so the odd tiers 3/5/7/9 buy no extra dot
    while still granting their points. Flagged for the human — see
    docs/status/merits-flaws-triage.md — rather than silently re-authored here.
    """
    from .validate import merit_points                    # validate imports merits

    out: dict[str, int] = {}
    for definition, purchase in _held(ruleset, character):
        rate = _FORFEIT_RATES.get(definition.id)
        if rate is None:
            continue
        points = merit_points(definition, purchase, character.exalt_type, character.caste)
        out[definition.id] = out.get(definition.id, 0) + max(0, points) // rate
    return out


def _attribute_forfeits(ruleset: RuleSet, character: Character) -> dict[str, int]:
    """Diminished Attributes' dots, split by the Attribute category they came out of.

    The category is the player's, recorded in `MeritFlawPurchase.detail`, because the
    page prints three versions of one Flaw — Physical, and the Mental and Social
    variants that "are considered Mental and Social Flaws rather than falling into the
    Physical category" (p.36). A purchase with no category recorded defaults to
    Physical, the printed entry's own category, and validate flags the omission.
    """
    from .validate import merit_points

    out: dict[str, int] = {}
    for definition, purchase in _held(ruleset, character):
        if definition.id != DIMINISHED_ATTRIBUTES:
            continue
        points = merit_points(definition, purchase, character.exalt_type, character.caste)
        category = (purchase.detail or "").strip().title() or "Physical"
        out[category] = out.get(category, 0) + max(0, points) // _FORFEIT_RATES[definition.id]
    return out


def merits_and_flaws_calc(ruleset: RuleSet, character: Character) -> MeritEffects:
    """The single M&F calculation. See the module docstring for why it is the only one.

    Baseline: a character whose splat HAS an Essence pool already has one — Merits only
    ever add. `ExaltDefinition.essence.personal_essence_coeff` being all-zero is how a
    Charmless, poolless splat is expressed (mortals), so that is what "needs unlocking"
    means, rather than a hardcoded check for the Mortal splat.
    """
    exalt = ruleset.exalt_for(character.exalt_type)
    has_native_pool = bool(exalt.essence.personal_essence_coeff
                           or exalt.essence.personal_willpower_coeff)
    raw_flaw_points = flaw_points(ruleset, character)

    held_ids = {d.id for d, _p in _held(ruleset, character)}
    effects_from: set[str] = set()

    # --- Essence Awareness / Mastery --------------------------------------- #
    awareness = ESSENCE_AWARENESS in held_ids
    mastery = ESSENCE_MASTERY in held_ids
    if awareness or mastery:
        effects_from.update({ESSENCE_AWARENESS, ESSENCE_MASTERY} & held_ids)

    open_categories: frozenset[str] = frozenset()
    barred: frozenset[str] = frozenset()
    circles: frozenset[SpellCircle] = frozenset()
    cap_override: int | None = None
    bar_immaculate = False

    if mastery:
        # "sufficient Essence to … practice Terrestrial Martial Arts" (PG p.121),
        # minus the one Charm that would open the Celestial styles.
        open_categories = frozenset({"martial_arts"})
        barred = frozenset({SPIRIT_WALKING})
        bar_immaculate = True
        # Terrestrial circle only — a mortal never reaches Celestial sorcery
        # (human, rules authority, 2026-07-30).
        circles = frozenset({SpellCircle.TERRESTRIAL})
        # Only meaningful where the splat is capped below 3 to begin with; an Exalt's
        # cap is 0 (uncapped) and must not be LOWERED to 3 by holding this Merit.
        if exalt.essence_cap and exalt.essence_cap < 3:
            cap_override = 3

    # --- Trait caps -------------------------------------------------------- #
    attribute_caps: dict[str, int] = {}
    virtue_cap: int | None = None
    essence_start_override: int | None = None
    charm_credits_max = 0
    charm_cost_doubled = False
    spell_cost_halved = False
    extra_favored = 0
    nature_unmet: list[str] = []
    trait_unmet: list[str] = []
    breeding_override: int | None = None
    single_pool = False
    for definition, purchase in _held(ruleset, character):
        # Printed TRAIT prerequisites, evaluated from catalogue data so this needs no
        # Merit id at all — the check is the same shape for every entry that grows one.
        # REPORTED, never enforced: the effect still applies, so the sheet stays
        # internally consistent and the Storyteller decides what to do about it.
        for req in definition.trait_prerequisites:
            if req.tier and req.tier != purchase.tier:
                continue                       # gate is on one option of the menu only
            held_rating = _trait_rating(character, req)
            if held_rating < req.minimum:
                trait_unmet.append(
                    f"{definition.name} requires {req.name.title()} {req.minimum}; "
                    f"this character has {held_rating}")
        if definition.id == LEGENDARY_ATTRIBUTE:
            # "a rating one dot higher than the normal limit imposed by their Essence
            # allows ... for mortals and Exalted with Essence 1 to 5, this allows a
            # rating of 6. Exalted with Essence 6 may raise the Attribute to 7" (p.20).
            # So the normal limit is Essence once Essence exceeds 5, and the universal
            # 5 below that. NOTE this does NOT introduce an Essence-scaled cap for
            # anyone else — the base cap stays 5 throughout the build.
            trait = (purchase.detail or "").strip().lower()   # AttributeName.value
            if trait:
                cap = max(DOT_MAX, character.essence_rating) + 1
                attribute_caps[trait] = max(attribute_caps.get(trait, 0), cap)
                effects_from.add(definition.id)
        elif definition.id == DISFIGURED:
            cap = _DISFIGURED_APPEARANCE_CAPS.get(purchase.tier)
            if cap is not None:
                # The LOWEST cap wins where several apply, so a Merit can never undo a
                # Flaw's ceiling by being processed second.
                current = attribute_caps.get(APPEARANCE)
                attribute_caps[APPEARANCE] = cap if current is None else min(current, cap)
                effects_from.add(definition.id)
        elif definition.id == TRUE_PARAGON:
            virtue_cap = TRUE_PARAGON_VIRTUE_CAP
            if character.nature != PARAGON_NATURE:
                nature_unmet.append(definition.name)
            effects_from.add(definition.id)
        elif definition.id == BRIGIDS_HEIR:
            charm_cost_doubled = True
            spell_cost_halved = True
            effects_from.add(definition.id)
        elif definition.id == PRODIGY:
            extra_favored += 1
            effects_from.add(definition.id)
        elif definition.id == WEAK_ESSENCE:
            essence_start_override = WEAK_ESSENCE_START
            charm_credits_max = WEAK_ESSENCE_CHARM_CREDITS
            effects_from.add(definition.id)
        elif definition.id == LEGENDARY_BREEDING:
            # The highest rating wins if this were ever held twice — an effective
            # rating is a ceiling on ancestry, not something that accumulates.
            breeding_override = max(breeding_override or 0, LEGENDARY_BREEDING_RATING)
            effects_from.add(definition.id)
        elif definition.id == BEACON_OF_POWER:
            single_pool = True
            effects_from.add(definition.id)

    # --- Health levels ----------------------------------------------------- #
    granted_levels: list[tuple[int, str]] = []
    removed_levels: list[int] = []
    for definition, purchase in _held(ruleset, character):
        if definition.id == LARGE_SIZE:
            # An unrecognised tier grants nothing rather than guessing which size was
            # meant; validate reports the unrecorded choice separately.
            for penalty in _LARGE_SIZE_LEVELS.get(purchase.tier, ()):
                granted_levels.append((penalty, definition.name))
            effects_from.add(definition.id)
        elif definition.id == SMALL:
            removed_levels.extend(_SMALL_REMOVES)
            effects_from.add(definition.id)

    # --- The trait-forfeit Flaws ------------------------------------------- #
    forfeits = _forfeited_dots(ruleset, character)
    effects_from.update(forfeits.keys() & held_ids)

    callous_dots = forfeits.get(CALLOUS, 0)
    virtue_total = sum(character.virtues.values())
    # Callous falls away at 9 Virtue dots, taking its ceiling and Nature ban with it —
    # but NOT its bonus points, which were spent at creation and are not refunded.
    callous_active = CALLOUS in held_ids and virtue_total < CALLOUS_EXPIRY_VIRTUE_DOTS

    willpower_floor = 0
    if WEAK_WILLED in held_ids:
        willpower_floor = (WEAK_WILLED_FLOOR_MORTAL
                           if (not has_native_pool or CALLOUS in held_ids)
                           else WEAK_WILLED_FLOOR_EXALTED)

    # Holy Mien's grant, expressed as effects rather than a branch in the cost code.
    granted_merits: frozenset[str] = frozenset()
    cost_overrides: dict[str, dict[str, int]] = {}
    if HOLY_MIEN in held_ids and PRIEST in ruleset.merits_flaws:
        granted_merits = frozenset({PRIEST})
        cost_overrides = {PRIEST: {"1": 0, "7": 6}}
        effects_from.add(HOLY_MIEN)

    return MeritEffects(
        attribute_caps=attribute_caps,
        virtue_cap=virtue_cap,
        essence_start_override=essence_start_override,
        charm_credits_max=charm_credits_max,
        charm_cost_doubled=charm_cost_doubled,
        spell_cost_halved=spell_cost_halved,
        extra_favored_abilities=extra_favored,
        nature_requirement_unmet=tuple(nature_unmet),
        trait_requirement_unmet=tuple(trait_unmet),
        health_levels_granted=tuple(granted_levels),
        health_levels_removed=tuple(removed_levels),
        forfeited_ability_dots=forfeits.get(UNSKILLED, 0),
        forfeited_virtue_dots=callous_dots,
        forfeited_willpower_dots=forfeits.get(WEAK_WILLED, 0),
        forfeited_attribute_dots=_attribute_forfeits(ruleset, character),
        willpower_virtue_margin=CALLOUS_WILLPOWER_MARGIN if callous_active else None,
        willpower_tracks_virtues=callous_active,
        willpower_floor=willpower_floor,
        barred_natures=frozenset({PARAGON_NATURE}) if callous_active else frozenset(),
        granted_merits=granted_merits,
        merit_cost_overrides=cost_overrides,
        essence_pool_unlocked=has_native_pool or awareness or mastery,
        essence_pool_unrestricted=has_native_pool or mastery,
        essence_cap_override=cap_override,
        breeding_rating_override=breeding_override,
        essence_single_pool=single_pool,
        open_charm_categories=open_categories,
        barred_charm_ids=barred,
        bar_immaculate_charms=bar_immaculate,
        granted_circles=circles,
        bonus_point_grant=min(raw_flaw_points, FLAW_POINT_CAP),
        flaw_points_raw=raw_flaw_points,
        narrative_only=tuple(sorted(
            held_ids - effects_from - {OATHBOUND_MAGIC})),
    )


# --------------------------------------------------------------------------- #
# Cost adjustment (A4). Brigid's Heir is the only entry that reprices Charms and
# spells, and it does so with a per-Charm exemption, so it cannot be a plain field on
# MeritEffects: the answer depends on WHICH Charm. These functions are the read —
# callers pass a cost and get one back, and still name no Merit id.
# --------------------------------------------------------------------------- #

BRIGIDS_HEIR = "mf.brigid-s-heir"
PRODIGY = "mf.prodigy"

# "may not have more than five Favored Abilities in total" (p.21).
PRODIGY_FAVORED_CAP = 5

# Charms exempt from Brigid's Heir's doubling, per splat. Recomputed rarely and cached
# because the sorcery-line closure walks every Charm's prerequisites.
_BRIGID_EXEMPT_CACHE: dict[tuple[int, str], frozenset[str]] = {}


def _terrestrial_sorcery_line(ruleset: RuleSet, character: Character) -> frozenset[str]:
    """Charm ids exempt from Brigid's Heir: "Ox-Body Technique is exempt from this
    doubling, as is any Charm that includes Terrestrial Circle Sorcery as an ultimate
    prerequisite or leads directly to that Charm" (p.30).

    Found through DATA, not by id: the initiating Charm is the one whose `grants_circle`
    is Terrestrial, so this works for every splat that has sorcery without naming any of
    their Charms. Three groups:

      * the initiating Charm itself,
      * its direct prerequisites — the Charms that "lead directly to" it,
      * everything with it in the transitive prerequisite closure — the Charms that
        "include it as an ultimate prerequisite".

    RULED 2026-07-31 (human, rules authority): the printed text names only the second
    and third groups, so the initiating Charm itself is exempt here BY INFERENCE —
    leaving the one Charm the Merit is *about* at double cost while everything either
    side of it is exempt reads as a drafting slip rather than intent. The human kept
    the inference but holds it lightly ("fine for now, but I don't mind"), so do NOT
    cite it as precedent for any other exemption. Reverting to the literal reading is
    still one token: drop `{tcs_id}` from the union below.
    """
    key = (id(ruleset), character.exalt_type)
    cached = _BRIGID_EXEMPT_CACHE.get(key)
    if cached is not None:
        return cached

    exempt: set[str] = set()
    from .validate import ox_body_charm_id
    ox = ox_body_charm_id(ruleset, character)
    if ox:
        exempt.add(ox)

    tcs_ids = {cid for cid, charm in ruleset.charms.items()
               if charm.grants_circle == SpellCircle.TERRESTRIAL}
    for tcs_id in tcs_ids:
        exempt.add(tcs_id)                                  # by inference — see above
        tcs = ruleset.charms[tcs_id]
        for group in tcs.prerequisites:                     # AND-of-OR: flatten
            exempt.update(group)
    # Downstream: anything whose prerequisite closure reaches an initiating Charm.
    for cid, charm in ruleset.charms.items():
        seen: set[str] = set()
        stack = [p for group in charm.prerequisites for p in group]
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            if pid in tcs_ids:
                exempt.add(cid)
                break
            prereq = ruleset.charms.get(pid)
            if prereq is not None:
                stack.extend(p for group in prereq.prerequisites for p in group)

    result = frozenset(exempt)
    _BRIGID_EXEMPT_CACHE[key] = result
    return result


def adjust_charm_cost(ruleset: RuleSet, character: Character, charm, cost: int) -> int:
    """`cost` after any Merit that reprices Charms. Brigid's Heir "doubles the
    bonus/experience cost ... of all Charms" outside the sorcery line (p.30)."""
    if not merits_and_flaws_calc(ruleset, character).charm_cost_doubled:
        return cost
    if charm is not None and charm.id in _terrestrial_sorcery_line(ruleset, character):
        return cost
    return cost * 2


def adjust_spell_cost(ruleset: RuleSet, character: Character, cost: int) -> int:
    """`cost` after any Merit that reprices spells. Brigid's Heir "halves the
    corresponding costs ... for spells" (p.30).

    ⚠ The page does not say how an odd cost halves. Rounded DOWN, the player-favourable
    direction for a price. No printed cost in the build is currently odd, so this has no
    effect today — flagged for the rules authority against future data.
    """
    if not merits_and_flaws_calc(ruleset, character).spell_cost_halved:
        return cost
    return cost // 2
