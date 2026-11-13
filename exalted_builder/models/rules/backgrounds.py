"""
models/rules/backgrounds.py — the Background models, the trait requirements,
and the Background point limits.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ._base import BackgroundBudgetTier, Source


class BackgroundType(BaseModel):
    """A Background in the catalogue. character.BackgroundEntry holds the rating.

    Availability is an autofill hint only. `exalt_type`: only this splat.
    `excluded_exalt_types`: splats that cannot take it (p.156-157)."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    description: str = ""
    exalt_type: str = ""                          # "" = all splats; else only this one
    excluded_exalt_types: list[str] = Field(default_factory=list)
    # Origins that cannot take this Background (PG p.176), as the origin part of the
    # "E:o:u" key. ⚠ For Savant the value is the modern origin `["Dragon-Kings"]`, not
    # the ancient key. Read by RuleSet.backgrounds_for.
    excluded_origins: list[str] = Field(default_factory=list)
    # The Background belongs to no splat, thus all splats get it (Cult; human's
    # ruling).
    # ⚠ Set it explicitly. Do not derive it. `tests/test_backgrounds_splat.py` checks
    # the flag against the data.
    # The exclusions and `banned_backgrounds` still apply (CH6 p.234).
    universal: bool = False
    # The splat decides which Backgrounds it can take (p.66), not the Background:
    # see `ChargenBudgets.allowed_backgrounds`.
    #
    # The text of each rating. Six entries, indexed by rating: `ladder[0]` is the `x`
    # row. Empty = not transcribed; the sheet shows `description`.
    # ⚠ Text only. The engine does not read a rung. Put a cap or a cost in
    # `BackgroundRule`.
    ladder: tuple[str, ...] = ()

    # The Background id whose ladder this entry uses (human's ruling). The loader
    # copies the rungs onto `ladder`.
    # ⚠ An explicit pointer. Do not fall back to an entry of the same name:
    # Alchemical Artifact and Family have no ladder by design.
    ladder_from: str = ""

    # The page that prints this Background. None when no page is known.
    # ⚠ None, not the default `Source()`. That default names "Core", thus an
    # unsourced row would show a book that does not print it.
    # ⚠ Read site: the public wiki (`ui/wiki_view.background_page`).
    source: Optional[Source] = None

    # ---- Hearthstones (Savant and Sorcerer pp.66-67) ---------------------- #
    # Set on the Manse variants only. `engine.artifacts.grows_hearthstones` is the
    # one read site.
    #
    # S&S p.67: the sum of the stone levels cannot exceed the Manse level (p.66).
    # `BackgroundBudgetTier.max_items` gives a printed count.
    #
    #   `hearthstone_per_dot` — N dots give N x per_dot levels (Mountain Folk CH6: 2).
    #     One stone can use the full allowance.
    #
    #   `hearthstone_tiers` — a printed table with a total and a largest stone.
    #     The tiers win if both are set.
    #
    # ⚠ Demesnes are not modelled (S&S p.66, human's ruling). A row with
    # `BackgroundEntry.is_demesne` set has no stones.
    hearthstone_tiers: tuple[BackgroundBudgetTier, ...] = ()
    hearthstone_per_dot: int = Field(default=0, ge=0)

    @field_validator("ladder")
    @classmethod
    def _ladder_is_empty_or_complete(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        """Refuse a ladder that is not empty and not 6 entries. ⚠ The sheet indexes
        the ladder by rating."""
        if v and len(v) != 6:
            raise ValueError(
                f"ladder must have 6 entries (x + 5 dots), got {len(v)}")
        return v


class TraitRequirement(BaseModel):
    """A trait rating that a Merit or Flaw needs (p.22, p.28).

    `trait` is a NAME. `validate.trait_rating` resolves it across Attributes,
    Abilities, Virtues and Backgrounds, in that order. A name that does not resolve
    reads as 0.
    """
    model_config = ConfigDict(frozen=True)

    trait: str
    rating: int = Field(default=1, ge=0)


class BackgroundPointLimit(BaseModel):
    """A limit on the points of a Merit or Flaw, from a Background rating
    (PG pp.37-38). Validate checks it. engine.merits does not read it.

    `background` matches by lowercased name.
    """
    model_config = ConfigDict(frozen=True)

    background: str
    # "max"   — points may not exceed (rating + offset)
    # "above" — points must exceed (rating + offset)
    mode: str = "max"
    offset: int = 0
    # PG p.38: use the rating of the item `MeritFlawPurchase.artifact_key`, not the
    # sum of the Background.
    per_entry: bool = False
    # "rating": the dots of the item. "acquisition_cost": the points paid for it
    # (PG p.38).
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
