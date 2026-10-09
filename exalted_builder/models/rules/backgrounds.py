"""
models/rules/backgrounds.py — the Background models, the trait requirements,
and the Background point limits.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._base import BackgroundBudgetTier, Source


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
    # A Background that belongs to NO splat in particular, and is therefore offered to
    # every splat regardless of what that splat's own book enumerates. Cult is the case
    # that named the field: it is printed in Games of Divinity, which is not a splat
    # book, so no character-creation summary anywhere lists it.
    #
    # Human's ruling, 2026-08-11: "Cult is universal, as are any other backgrounds not
    # in specific splats if such exist."
    #
    # ⚠ Marked explicitly, never derived from "tagged by nobody, listed by nobody": the
    # derived version fails non-locally — the day one splat's book turns out to list
    # Cult, Cult silently disappears from every OTHER splat.
    # `tests/test_backgrounds_splat.py` checks the flag against the data BOTH ways, so
    # it cannot rot: a universal Background must appear in no splat's list, and a
    # Background with no splat tag that no list names must be marked universal.
    #
    # Still subject to `excluded_exalt_types`, `excluded_origins` and the budget's
    # `banned_backgrounds` — universal means "belongs to no one book", not "unbannable".
    # The Great Geas still forbids a Mountain Folk a Cult (CH6 p.234).
    universal: bool = False
    # NOTE there is deliberately NO per-Background allow-list of splats or origins.
    # Which Backgrounds a splat may take is a property of the SPLAT, not of the
    # Background: every book's character-creation summary enumerates its own list
    # (Ghosts CH3 names eleven, Lookshy's p.66 summary fifteen), and that list is the
    # answer. It lives on `ChargenBudgets.allowed_backgrounds` and is read through
    # `RuleSet.allowed_backgrounds_for`. `exalt_type` / `excluded_exalt_types` above
    # remain the FALLBACK for a splat whose summary has not been transcribed yet.
    # The printed dot-by-dot ladder — what each RATING of this Background actually
    # gets you ("•• Two allies or one significant one"). Six entries when present,
    # indexed by rating: `ladder[0]` is the book's `x` row (None) and `ladder[1..5]`
    # the five dots. Empty means the ladder has not been transcribed yet, and the
    # sheet falls back to `description` alone — so an untranscribed Background
    # degrades to what it displayed before rather than rendering a blank rung.
    #
    # This is TEXT, not mechanics: nothing in the engine reads a rung. The numeric
    # rules a ladder happens to state (a cap, a cost, a prerequisite) belong in the
    # per-splat `BackgroundRule`, which is where the engine looks — a rung that says
    # "you cannot buy above three" does not enforce itself, and authoring one as if
    # it did is exactly the writer-with-no-reader bug this project keeps hitting.
    ladder: tuple[str, ...] = ()

    # An exact Background id to BORROW the ladder from, for a splat whose own book
    # prints the Background as prose with no dot-by-dot breakdown (the ten Mountain
    # Folk copies — human's ruling 2026-08-12: "it's prose only, but you should
    # probably make them point to the Solar backgrounds, just makes life easier").
    # The borrowed rungs are copied onto `ladder` ONCE, by the loader, so every reader
    # downstream sees an ordinary ladder and nothing has to know this field exists.
    #
    # ⚠ Deliberately a per-entry POINTER and never a blanket "fall back to the untagged
    # entry of the same name": Alchemical Artifact and Family have no ladder ON PURPOSE
    # (their books print none / print a random table instead), and a same-name fallback
    # would silently hand Alchemical Artifact the Solar Artifact ladder — a splat whose
    # Artifact Background is heavily reworked. An opt-in cannot do that by accident.
    ladder_from: str = ""

    # The page that prints this Background. None when no page is known.
    # ⚠ None, not the default `Source()`. That default names "Core", thus an
    # unsourced row would show a book that does not print it.
    # ⚠ Read site: the public wiki (`ui/wiki_view.background_page`).
    source: Optional[Source] = None

    # ---- Hearthstones (Savant and Sorcerer pp.66-67) ---------------------- #
    # What this Background's dots let the character actually HOLD in Hearthstones.
    # Set on the six Manse variants and nothing else; a Background that leaves both
    # fields at their defaults grows no stones and gets no picker, which is how the
    # UI decides — `engine.artifacts.grows_hearthstones` is the ONE read site, so the
    # old "is the name 'manse'?" substring test is gone. That test could not have
    # expressed these numbers anyway: they differ per splat.
    #
    # The governing rule is S&S p.67: "The sum of the levels of all the Hearthstones
    # produced can never exceed the level of the Manse." A Manse may be designed to
    # produce several stones instead of one (p.66, "Multiple Hearthstones by Design"),
    # so the cap is on the TOTAL, never on the count — except where a page prints a
    # count, which is `BackgroundBudgetTier.max_items`.
    #
    # Two shapes, because the books print two:
    #
    #   `hearthstone_per_dot` — a linear Background, where N dots carry N × per_dot
    #     levels of stone. The core Manse ladder is "Level N Manse" and the Sidereal
    #     and Dragon-King Celestial Manse ladders are "Produces a level N Hearthstone",
    #     so both are 1. The Mountain Folk Manse prints no ladder at all, only prose:
    #     "Each dot in this Background provides two dots worth of Manses" (CH6), so 2.
    #     A single stone may be the whole allowance, so the individual ceiling is the
    #     combined one.
    #
    #   `hearthstone_tiers` — an irregular printed table, which is what the
    #     Dragon-Blooded and Abyssal Underworld ladders are: their rungs name a
    #     combined level total AND the largest single stone, and the totals (2/3/6/8/10)
    #     are not a multiple of anything. Tiers WIN where both are set.
    #
    # ⚠ DEMESNES ARE NOT MODELLED HERE, deliberately (human's ruling 2026-08-12). Every
    # Manse ladder doubles as the Demesne ladder at one rung higher, and S&S p.66 gives
    # Demesne stones their own rule (always one level BELOW the Demesne, and they decay
    # once removed). Rather than model that, `BackgroundEntry.is_demesne` marks the row
    # as a Demesne and it simply grows no stones — the book calls them accidental and
    # rapidly useless, and the toggle is the whole of the support they get.
    hearthstone_tiers: tuple[BackgroundBudgetTier, ...] = ()
    hearthstone_per_dot: int = Field(default=0, ge=0)

    @field_validator("ladder")
    @classmethod
    def _ladder_is_empty_or_complete(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        """A partial ladder is worse than none: the sheet indexes it by rating, so
        four rungs would render the wrong text for a rating rather than no text."""
        if v and len(v) != 6:
            raise ValueError(
                f"ladder must have 6 entries (x + 5 dots), got {len(v)}")
        return v


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
