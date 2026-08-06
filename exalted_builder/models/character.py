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

from pydantic import BaseModel, Field, field_validator, model_validator

from .rules import (AbilityName, AttributeName, Damage, Orientation,
                    VirtueName)


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


class ArtifactEntry(BaseModel):
    """One individually rated artifact the character owns (E:Ab p.131).

    Exists because the Artifact Background is a BUDGET, not a cost curve: the Abyssal
    table caps both the COMBINED rating of everything owned and the rating of any
    SINGLE item, and neither can be checked against a `BackgroundEntry`, which carries
    one summed number. It is also what Damaged Artifact points at — the Flaw's printed
    limit is "the rating of the artifact it modifies", per-item, not the total.

    ⚠ This list is for artifacts that are NEITHER a weapon NOR armour — the book's own
    worked example is the tattered wings of the raptor. Weapons and armour already
    carry `artifact_rating` and are folded in by `engine.artifacts.artifact_items`;
    re-entering a daiklave here would double-count it against the budget.

    `rating` is the artifact's own dots (1-5), not the Background's. N/A artifacts are
    unrepresentable on purpose: the p.131 table's only universal rule is that an item
    "cannot be N/A", so there is no rating to record for one."""
    name: str
    rating: int = Field(ge=1, le=5)
    note: str = ""


class FetterEntry(BaseModel):
    """One Fetter — a person, place or object anchoring a ghost to the world
    (Exalted: The Abyssals p.126). Ghosts only; every other splat's list is empty.

    Shaped like `BackgroundEntry` because it behaves like one: an open-ended NAME the
    player writes, rated 0-5, spent out of a chargen pool and raisable afterwards. It
    is a separate model rather than a Background because it has its own pool, its own
    bonus-point and experience rates, and a hard cap no Background has — "A ghost can
    never have more dots of Fetters than his Willpower + Essence" (p.127, restated in
    the p.283 footnote)."""
    name: str                              # "my widowed wife", "the sword I died on"
    rating: int = Field(ge=0, le=5)
    note: str = ""


class PassionEntry(BaseModel):
    """One Passion — a driving emotional attachment, each belonging to a VIRTUE
    (E:Ab p.126: "Choose a number of dots of Passions for each Virtue equal to the
    number of dots the character has in that Virtue").

    ⚠ A Passion is NOT bought, at creation or afterwards. Its dots are DERIVED from
    the owning Virtue and merely distributed by the player: p.283 — "Ghosts increase
    their Passions when they increase their Virtues. There is no other way for these
    Traits to increase." Confirmed by the human (rules authority, 2026-08-01) to hold
    on BOTH sides of the lock: buy a Virtue dot with experience and one more Passion
    dot of that Virtue becomes available to distribute.

    So there is no `passion` row in the bonus-point or experience tables, and none in
    `BonusPointCosts`/`ExperienceCosts` either. The only experience operation is Shift
    Passion (p.283, 20 XP), which moves a dot BETWEEN Passions of the same Virtue and
    leaves the total where the Virtues put it.

    `virtue` is which Virtue's pool this Passion draws on — the pools are per-Virtue,
    not one aggregate, so Compassion 3 buys three dots of Compassion Passions and
    nothing else."""
    name: str                              # "avenge my murder", "see my son crowned"
    virtue: VirtueName
    rating: int = Field(ge=0, le=5)
    note: str = ""


class MeritFlawPurchase(BaseModel):
    """One Merit or Flaw the character holds, referencing rules.MeritFlaw by id.

    Deliberately thin. What the Merit DOES is decided in one place —
    `engine.merits.merits_and_flaws_calc` — never stored here (decision 0011).

    `tier` names the option for a variable-cost entry (Oathbound Magic: "minor",
    "moderate", "major", "legendary"); "" for the fixed-cost majority. `detail` is the
    player's free text — the Attribute group a repeatable Merit was taken for, or the
    wording of an oath and the Traits it bought, which the page requires be recorded.
    `arena` groups oaths for the stacking rule ("combat", "sex", "eating"): oaths in
    one arena past the first lose value, so the calc needs to know which share one.
    """
    merit_id: str
    tier: str = ""
    detail: str = ""
    arena: str = ""
    # Agreed point value for a `variable_cost` entry, whose price the page leaves to
    # the table ("VARIABLE COST MERIT"). Ignored for every printed-cost entry, which
    # prices from its MeritFlaw row instead — never trust this over the catalogue.
    points: int = 0
    # Which side of a `kind: "either"` entry was taken ("merit" or "flaw"). Ignored
    # for the single-sided majority; "" on an either-entry defaults to merit and is
    # flagged by validate, so the choice is never silently made for the player.
    taken_as: str = ""
    # Major conditions attached to an inheritance — Heir Apparent's "add an extra dot
    # to the pool of invested Backgrounds for every major stipulation applied to the
    # Inheritance, up to a maximum of three conditions" (PG p.24). A COUNT, because the
    # dots follow from the number and the wording is the player's business (`detail`).
    # Unlike the trait-forfeit Flaws, this cannot be recovered from the point value —
    # stipulations cost nothing, so they leave no trace in the price. 0 for every other
    # entry; the printed maximum is clamped in engine.merits, not here, so an old save
    # with a stray value loads rather than failing.
    stipulations: int = Field(default=0, ge=0)
    # Which artifact this Flaw modifies, for a `points_limited_by.per_entry` entry —
    # Damaged Artifact, whose printed limit is "the rating of the artifact it modifies"
    # rather than the character's summed Artifact Background. The value is an
    # `engine.artifacts` item KEY ("artifact:tattered wings", "weapon:grand daiklave"),
    # so it can name a standalone artifact, a weapon or a suit of armour alike.
    #
    # "" on every other entry, and on a Damaged Artifact whose owner has not yet chosen
    # — which validate reports rather than defaulting, because picking the character's
    # best artifact for them would silently make an illegal purchase legal.
    artifact_key: str = ""


class CraftRating(BaseModel):
    """One Craft Ability instance. In 1e (core p.136) Craft is taken per focus —
    "characters who wish to master multiple crafts must take this Ability multiple
    times" — so each craft (Smithing, Genesis, ...) is its own independently rated
    Ability, NOT a specialty. The single AbilityName.CRAFT dot in `abilities` is
    unused; the engine reads craft ratings from this list."""
    focus: str                             # the specific craft, e.g. "Smithing"
    rating: int = Field(ge=0, le=5)


class CollegeRating(BaseModel):
    """One Astrological College instance on a character (Sidereal, p.98). `college_id`
    references a RuleSet College by id; `rating` is its dots. Colleges are a rated
    Advantage with their own chargen pool, so — like backgrounds and per-focus crafts
    — they live as a list rather than a single dot on a fixed trait."""
    college_id: str
    rating: int = Field(ge=0, le=5)


class PathRating(BaseModel):
    """One Dragon-King Path instance on a character (PG pp.175-177). `path_id`
    references a RuleSet Path by id; `rating` is its dots (1-6). A Path is a rated
    Advantage with its own chargen pool and an Essence gate (max rating 1/3/5/6 at
    Essence 1/2/3-5/6, p.177), so it lives as a list exactly like CollegeRating.
    The dot-level POWERS the rating grants are display data on the Path; the engine
    also projects them into the charm catalogue as virtual rows so Combos can name
    them (see rules_db.load_ruleset) — the rating here is the truth."""
    path_id: str
    rating: int = Field(ge=0, le=6)


# --------------------------------------------------------------------------- #
# Thaumaturgy holdings (Player's Guide CH3). See models/rules.py for the
# catalogue side and docs/status/thaumaturgy.md for the design.
# --------------------------------------------------------------------------- #

class ArtSpecialty(BaseModel):
    """+1 die in a narrow corner of an Art; at most two apply to any one roll.

    `art_id` may name an Art the character does NOT own — this is explicitly legal
    and stated three times in the source ("You do not have to buy the relevant Art
    in order to buy a specialty in that Art", p.116). Do not add a prerequisite.

    `name` is free text: the book invites player-invented specialties, so the
    catalogue's `specialties` list is an autofill source, never a hard reference —
    the same call already made for Backgrounds.

    `narrowed` is Summoning's special rule (p.127): "a thaumaturge may choose to
    further limit one or more of their summoning aspects … This halves the cost of
    the aspect and should be noted on the character sheet." It is a player choice
    made about a purchase, not a separate purchase and not inferable from the name,
    so it is stored — the book asks for it on the sheet explicitly. The engine
    refuses it on Arts whose `aspect_narrowing` is False, which is all but
    Summoning."""
    art_id: str
    name: str
    narrowed: bool = False


class ScienceRating(BaseModel):
    """One Science at a rating. Not bounded here: the per-Science ceiling is
    `ThaumaturgicScience.max_rating`, enforced in engine.validate, which has the
    RuleSet. Every Science currently stops at 5 — Alchemy's printed six-dot rung was a
    typo for five (human, 2026-07-30) — but the ceiling stays per-Science data rather
    than a constant, so a future Science may differ without a model change."""
    science_id: str
    rating: int = Field(ge=0)


class RitualEntry(BaseModel):
    """A ritual the character knows, in one or more regional versions.

    Catalogue + custom: `ritual_id` references a RuleSet ritual, OR is empty and
    the inline `name`/`level`/`description` describe a user-authored one (the
    editable-custom-weapons precedent — the book expects STs to write more).

    `orientations` is the crux and the reason this is not a bare id list. Each
    extra regional version costs a flat 1 point on top of the ritual's own cost
    (p.124), so ownership is (id, {orientations}) and the cost function needs the
    set. Retrofitting this later would leave the append-only XP log ambiguous:
    "bought ritual X" could mean the ritual or a further orientation of it, at
    different prices, with no way to re-price history."""
    ritual_id: str = ""                    # "" => custom, described inline below
    name: str = ""                         # custom only; catalogue entries read the RuleSet
    level: int = Field(default=1, ge=1, le=5)   # custom only
    description: str = ""                  # custom only
    orientations: list[Orientation] = Field(default_factory=lambda: [Orientation.REALM])

    @field_validator("orientations")
    @classmethod
    def _at_least_one_orientation(cls, v: list[Orientation]) -> list[Orientation]:
        # Every ritual has an orientation; knowing none is not a state that exists.
        # De-duplicate, since paying twice for the same region is meaningless.
        if not v:
            return [Orientation.REALM]
        return list(dict.fromkeys(v))


class FormulaEntry(BaseModel):
    """A formula or procedure the character knows. Same orientation rule as
    RitualEntry; formulas are the cheapest purchasable in thaumaturgy (1 point).

    `level` is unbounded above for the same reason as ScienceRating: the ceiling is
    per-Science rules data, not a model constant."""
    formula_id: str = ""                   # "" => custom, described inline below
    name: str = ""                         # custom only
    science_id: str = ""                   # custom only
    level: int = Field(default=1, ge=1)    # custom only
    description: str = ""                  # custom only
    orientations: list[Orientation] = Field(default_factory=lambda: [Orientation.REALM])

    @field_validator("orientations")
    @classmethod
    def _at_least_one_orientation(cls, v: list[Orientation]) -> list[Orientation]:
        if not v:
            return [Orientation.REALM]
        return list(dict.fromkeys(v))


class ThaumaturgyState(BaseModel):
    """Everything a character knows of thaumaturgy. Optional on Character, so old
    saves load with it None — the PlayState precedent.

    Deliberately NOT keyed to a splat: thaumaturgy is a cross-splat capability
    layer (p.114). Whether a character may USE what it holds is a property of the
    splat, read from ExaltDefinition.thaumaturgy_usable — the dead keep their Arts
    and may still teach, but may never cast."""
    arts: list[str] = Field(default_factory=list)              # trained Art ids: +2 dice
    art_specialties: list[ArtSpecialty] = Field(default_factory=list)
    sciences: list[ScienceRating] = Field(default_factory=list)
    rituals: list[RitualEntry] = Field(default_factory=list)
    formulas: list[FormulaEntry] = Field(default_factory=list)


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


class HouseRules(BaseModel):
    """Optional rules the table has switched on — ST choices, not character traits
    and not rulebook data.

    They live on the Character rather than the RuleSet because the RuleSet is the
    rulebook: static, shared and read-only. A table's choices are neither, and they
    have to travel with a save file for its accounting to still add up on another
    machine. `Character.play` set the precedent for an optional sub-document; this is
    the same shape, and old saves load with `house_rules` None.

    A container from the outset even though it holds one flag, because the next such
    toggle should not need a new field on Character. Anything that changes chargen
    ACCOUNTING belongs here and must also be frozen into the ChargenSnapshot, or
    flipping it post-lock would retroactively re-price a locked character.

    Each field below is marked TABLE-WIDE or PER-CHARACTER. Everything here is stored
    per-character because HouseRules lives on the Character, but the distinction is
    real: a TABLE-WIDE rule is one the ST turned on for the whole series and should
    hold for every character in it, while a PER-CHARACTER one is permission granted to
    this character alone. **A party-wide "apply to all" control may only touch the
    TABLE-WIDE fields.** Nothing enforces this yet — it is a note for whoever builds
    that control.
    """
    # TABLE-WIDE. "Magic for Everyone" (Player's Guide p.115): every starting
    # character begins with one ritual, formula or printed aspect per two dots of
    # Occult, free. Optional but recommended, and if used the book is explicit that
    # it applies to ALL starting characters — hence table-wide.
    magic_for_everyone: bool = False

    # TABLE-WIDE. The two chargen restrictions of Player's Guide p.113: "Storytellers
    # may choose to restrict starting characters to no more than three-dot rituals
    # and/or the third level of knowledge in any Science." The "and/or" is why these
    # are two independent flags rather than one. Both are creation-time only — they
    # cap what may be bought at chargen, not what may ever be learned.
    restrict_chargen_ritual_level: bool = False
    restrict_chargen_science_rating: bool = False

    # PER-CHARACTER. Storyteller permission for THIS character to start play knowing
    # another splat's Charms — the chargen half of the Eclipse/Moonshadow generalist
    # rule (core p.127): "Eclipse Caste characters may not start the game knowing the
    # Charms of other such beings without Storyteller permission." Post-lock the rule
    # needs only a willing tutor, which is narrative, so this gates chargen picks
    # only. Meaningless unless the caste sets CasteDefinition.foreign_charms.
    st_foreign_charms: bool = False

    # PER-CHARACTER. The optional rule of core p.103: "If the Storyteller agrees to
    # it, heroic mortals may choose one Ability as a Favored Ability, complete with
    # the discount." Permission for one character, not a series-wide switch, so it is
    # per-character despite reading like a table rule.
    #
    # It is NOT a free discount: the same paragraph attaches a constraint — "the
    # character can never have any other Ability rated higher than his Favored
    # Ability. The Favored Ability must be equal to or greater than every other skill
    # he possesses." That ceiling is the price of the discount and is validated
    # (mortal-favored-not-highest); the Exalted are exempt, which is flavour here
    # because only a mortal can turn this flag on in the first place.
    mortal_favored_ability: bool = False

    # TABLE-WIDE. How Merits & Flaws change AFTER character creation (Player's Guide
    # p.17, "Gaining and Losing Merits and Flaws"). The book gives three methods and
    # says the Storyteller "may use any of these three methods or a combination":
    #
    #   "experience" (DEFAULT) — the thorough one. Losing a Merit or gaining a Flaw
    #       pays the character twice its bonus-point value in XP; gaining a Merit or
    #       losing a Flaw charges the same. An unpayable charge becomes a DEBT that
    #       garnishes all further XP until cleared. Flaws past 10 points earn nothing.
    #   "backgrounds" — M&F "change with the plot and events but do not cost or reward
    #       players after character creation".
    #   "swap" — a lost Trait is eventually replaced by another of equal value, and a
    #       gained one erodes another.
    #
    # NOTE the last two are mechanically IDENTICAL to this engine: neither moves any
    # experience. They are kept as separate values because they oblige the Storyteller
    # to different things at the table, and a sheet should record which was chosen —
    # not because the engine does anything different. Do not "simplify" them into one.
    mf_change_method: str = "experience"

    # PER-CHARACTER. Storyteller permission for a TERRESTRIAL Exalt to pass the
    # Essence 7 ceiling of Player's Guide p.258: "Terrestrial Exalts may never raise
    # their permanent Essence above 7 without resorting to the use of outside energies
    # such as complex dietary and meditational regimens, powerful Hearthstones and
    # other, similar effects."
    #
    # A flag rather than a derivation because none of those things is on the sheet —
    # a Hearthstone Background dot does not tell the engine a regimen is in progress,
    # and the book's "and other, similar effects" is open-ended. So it is the ST
    # asserting the fiction happened, granted to one character, not the series.
    #
    # Post-lock only in effect (nothing can reach Essence 7 at chargen), so unlike the
    # accounting toggles above it changes no chargen price and is harmless in the
    # snapshot. Ignored entirely for any splat whose ExaltDefinition.tier is not
    # "Terrestrial".
    terrestrial_essence_transcendence: bool = False

    # TABLE-WIDE. How many dots of the God-Blooded Inheritance Background are FREE
    # (Player's Guide p.61). The same paragraph that lists the bonus points — Thin
    # blood +6 BP / 10 Flaws up to Divine +30 / 20 — makes the Storyteller the
    # arbiter: "the Storyteller assigns a consistent rating to set the series' power
    # level." The ST's pick (1-5) is how many Inheritance dots a God-Blooded is charged
    # nothing for (no Background-pool dots, no above-cap bonus points). It does NOT set
    # the rating itself: the character still takes the dots on their sheet and gets the
    # printed bonus points for THAT rating (human 2026-08-02). When unset (None) the
    # budget's own `free_rating` governs. An accounting toggle, so it freezes into the
    # ChargenSnapshot at lock like the rest.
    godblooded_inheritance_rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("mf_change_method")
    @classmethod
    def _check_mf_method(cls, v: str) -> str:
        if v not in ("experience", "backgrounds", "swap"):
            raise ValueError(
                f"mf_change_method must be experience/backgrounds/swap, got {v!r}")
        return v


class ChargenSnapshot(BaseModel):
    """Frozen at lock; the baseline the XP log is measured against."""
    attributes: dict[AttributeName, int]
    abilities: dict[AbilityName, int]
    crafts: list[CraftRating] = Field(default_factory=list)
    colleges: list[CollegeRating] = Field(default_factory=list)
    paths: list[PathRating] = Field(default_factory=list)
    favored_path: str = ""
    virtues: dict[VirtueName, int]
    specialties: list[Specialty]
    backgrounds: list[BackgroundEntry]
    # ⚠ Artifacts are deliberately NOT frozen here, for the same reason Passions are
    # not (below) and weapons and armour never were: the p.131 budget is keyed to the
    # Artifact Background, which experience can RAISE, so the ceiling moves after the
    # lock and a snapshot would pin it to what the character started with. It is
    # checked live on both sides instead — see engine.validate.check_artifacts, which
    # follows the Fetter-cap precedent.
    # Fetters are frozen like any other bought trait. Passions are NOT — they are a
    # live derivation of the Virtues on both sides of the lock (p.283), so freezing
    # them would be the decision-0005 Willpower treatment applied to a rule that
    # explicitly does not work that way. Only the DISTRIBUTION is the player's, and
    # the XP audit re-derives the pool rather than comparing against a snapshot.
    fetters: list[FetterEntry] = Field(default_factory=list)
    merits_flaws: list[MeritFlawPurchase] = Field(default_factory=list)
    charms: list[str]
    spells: list[str]
    combos: list[Combo] = Field(default_factory=list)
    arrays: list[Array] = Field(default_factory=list)
    submodules: list[SubmodulePurchase] = Field(default_factory=list)
    ox_body: list[OxBodyPurchase] = Field(default_factory=list)
    beastman_gifts: list[BeastmanGiftPurchase] = Field(default_factory=list)
    # Thaumaturgy bought at chargen. None (not an empty state) for a character who
    # never touched it, so "locked before thaumaturgy existed" and "locked with
    # none bought" stay distinguishable in the XP audit.
    thaumaturgy: Optional[ThaumaturgyState] = None
    # Frozen so a post-lock toggle cannot retroactively re-price a locked chargen.
    house_rules: Optional[HouseRules] = None
    essence_rating: int
    willpower_purchased: int
    wp_virtue_component: int               # two highest Virtues AT LOCK; never recomputed


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
    # A FOURTH axis, under `origin`: how the character was RAISED. The Outcaste book's
    # four Dragon-Blooded origins each print two or three upbringings whose Ability
    # budgets and required minimums differ while everything else about the origin
    # holds — a Lookshy Terrestrial not raised in Lookshy gets 25 Ability dots
    # instead of 35 (p.68), a patrician-born Lost Egg 30 instead of 25 (p.159), a
    # Forest Witch raised by Oreithyia cheaper Virtues and Essence (p.133). It is a
    # separate axis and not more origins because the origin still decides Backgrounds,
    # Charms, Virtues and the Charm grants. "" = the origin's default upbringing, which
    # is every origin's own home-raised case and every splat that has no variants.
    upbringing: str = ""
    # Cult of the Illuminated (Solar, p.89-93). A THIRD axis beyond splat and caste:
    # `camp` is a rules.TrainingCamp id (which Ability floors and free Charms apply),
    # `calling` is a rules.Calling id (which Abilities/Charms are discounted). Both ""
    # for every character whose origin does not require them — see
    # ChargenBudgets.requires_camp / .requires_calling, which is what the engine
    # keys off, so nothing here names a splat.
    camp: str = ""
    calling: str = ""
    # Charms received FREE from the camp's package (p.90), resolved: the camp's fixed
    # grants plus whatever the player chose for each GrantedCharmChoice. Kept OUT of
    # `charms` for the same reason ox_body and beastman_gifts are — anything that
    # enumerates picks must not count these against the Charm pool or the Caste/
    # Favored minimum, because they are granted rather than picked.
    granted_charms: list[str] = Field(default_factory=list)
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
    # PERMANENT Resonance — the Abyssal Curse's lasting half, which exists only for a
    # character holding Death's Taint (PG p.41): "Whenever the character's Resonance
    # pool exceeds a rating of 10, her pool resets to zero, and she gains a point of
    # permanent Resonance."
    #
    # This is a PERMANENT trait, not play-state, and it lives here for the reason
    # decision 0006 gives in its own last bullet: "permanent trait *reductions* (curses)
    # are a different thing and live on the XP ledger, not here". It is bought at
    # chargen (out of the Flaw's price), gained in play as a story event, shed for five
    # experience points, and capped at Essence — only the second of those is play-state.
    # Its TEMPORARY counterpart is PlayState.limit, which is correctly ephemeral.
    #
    # Post-lock movement in either direction goes through engine.advancement so the
    # ledger records it, exactly as a curse does. 0 for every character without the Flaw.
    limit_permanent: int = Field(default=0, ge=0)
    attributes: dict[AttributeName, int] = Field(
        default_factory=lambda: {a: 1 for a in AttributeName}
    )
    abilities: dict[AbilityName, int] = Field(
        default_factory=lambda: {a: 0 for a in AbilityName}
    )
    # Craft is per-focus (core p.136): each entry is its own rated Ability. The
    # AbilityName.CRAFT key in `abilities` is unused — read craft from here.
    crafts: list[CraftRating] = Field(default_factory=list)
    # Astrological Colleges (Sidereal, p.98): a rated Advantage with its own chargen
    # pool; each entry references a RuleSet College by id. Empty for non-Sidereals.
    colleges: list[CollegeRating] = Field(default_factory=list)
    # Dragon-King Paths (PG p.175-177): a rated Advantage with its own chargen pool,
    # exactly the College shape. Each entry references a RuleSet Path by id. Empty
    # for non-Dragon-Kings. The ONE player-chosen Favoured Path rides beside them —
    # the two Breed Paths are auto-favoured by `Path.element == breed element`, and
    # this is the third (any of the other eight Paths, human ruling 2026-08-05).
    paths: list[PathRating] = Field(default_factory=list)
    favored_path: str = ""
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
    # Individually rated artifacts that are neither weapon nor armour (E:Ab p.131).
    # Bought with the Artifact Background rather than out of a pool of their own, so
    # there is no BP or XP row for them — what they cost is the Background dots, which
    # the existing rows already price. See ArtifactEntry.
    artifacts: list[ArtifactEntry] = Field(default_factory=list)
    # Ghosts only (E:Ab p.126-127). Fetters are bought out of their own chargen pool
    # and with their own BP/XP rates; Passions are DERIVED from the Virtues and only
    # distributed here — see PassionEntry for why neither cost table has a row for
    # them. Empty for every other splat, which is what keeps the panels off their
    # sheets.
    fetters: list[FetterEntry] = Field(default_factory=list)
    passions: list[PassionEntry] = Field(default_factory=list)
    # Merits & Flaws (decision 0011). Effects are computed in engine.merits from these
    # ids and never stored; an empty list is every character who has bought none.
    merits_flaws: list[MeritFlawPurchase] = Field(default_factory=list)
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

    # Thaumaturgy (Player's Guide CH3) — a cross-splat capability layer, available
    # to every splat, keyed to none. None on a character that has never taken any,
    # so old saves load unchanged (the PlayState precedent).
    thaumaturgy: Optional[ThaumaturgyState] = None

    weapons: list[Weapon] = Field(default_factory=list)
    armor: list[Armor] = Field(default_factory=list)
    health_bonus_levels: list[HealthLevel] = Field(default_factory=list)

    # --- lifecycle / accounting ---
    chargen_locked: bool = False
    chargen_snapshot: Optional[ChargenSnapshot] = None
    xp_earned: int = Field(default=0, ge=0)
    xp_log: list[XpEntry] = Field(default_factory=list)

    # --- Storyteller options (see HouseRules; frozen into the snapshot at lock) ---
    house_rules: Optional[HouseRules] = None

    # --- play-state (separate layer; never enters chargen/XP validation) ---
    play: Optional[PlayState] = None

    # --- homebrew this character depends on (see custom_content.py) ------------
    # Definitions of the CUSTOM Charms/spells this character references, carried
    # inside the save so it survives being handed to someone whose machine has no
    # copy of the author's library. Keyed "charms"/"spells".
    #
    # Deliberately OPAQUE dicts, not Charm/Spell models: those are rules data, and
    # this module must not grow a dependency on the rules catalogue (see the module
    # docstring). They are parsed and validated at the edge — custom_content writes
    # them and rules_db loads them — so a save carrying a malformed row still loads
    # as a Character, and the row is reported rather than fatal.
    #
    # Populated on save and absorbed into the library on load; nothing in the engine
    # reads it, and an id that is in here but not in the RuleSet is still an
    # `unknown-charm` error like any other.
    custom_definitions: dict[str, list[dict]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _migrate_legacy_st_foreign_charms(cls, data: object) -> object:
        """Lift a pre-HouseRules top-level `st_foreign_charms` into `house_rules`.

        The flag moved when the Storyteller options were gathered into one place. It
        was a saved field, so without this every already-created Eclipse and
        Moonshadow would silently lose its permission on load and its foreign Charms
        would start failing validation. An explicit `house_rules` in the same payload
        wins — a new save is authoritative over a legacy key.
        """
        if not isinstance(data, dict) or "st_foreign_charms" not in data:
            return data
        data = dict(data)
        legacy = data.pop("st_foreign_charms")
        existing = data.get("house_rules")
        if isinstance(existing, HouseRules):
            existing = existing.model_dump()
        if existing is None:
            existing = {}
        if isinstance(existing, dict):
            existing.setdefault("st_foreign_charms", legacy)
            data["house_rules"] = existing
        return data

    @field_validator("caste", mode="before")
    @classmethod
    def _migrate_legacy_caste(cls, v: object) -> object:
        """Map a pre-Phase-2 capitalised Solar caste ("Dawn") to its id ("dawn").
        Any other value passes through untouched."""
        return _LEGACY_CASTE_IDS.get(v, v) if isinstance(v, str) else v
