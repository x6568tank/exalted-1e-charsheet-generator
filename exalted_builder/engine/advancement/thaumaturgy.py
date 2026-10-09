"""
engine/advancement/thaumaturgy.py — the Thaumaturgy purchases (Player's Guide
CH3): Arts, specialties, Sciences, Rituals, Formulas, and Orientations.
"""

from __future__ import annotations

from .. import costs
from ...models.character import (ArtSpecialty, Character, FormulaEntry, RitualEntry,
                                 ScienceRating, ThaumaturgyState, XpEntry)
from ...models.rules import Orientation, RuleSet

from ._base import AdvancementError, _commit, _ensure_locked


# --------------------------------------------------------------------------- #
# Thaumaturgy (Player's Guide CH3)
# --------------------------------------------------------------------------- #
# Cross-splat: every splat but the Fair Folk may buy these, so nothing here keys off
# exalt_type beyond the cost multiplier baked into engine.costs.

def _thaum(character: Character) -> ThaumaturgyState:
    """The character's ThaumaturgyState, creating it on first purchase. Character.
    thaumaturgy stays None for anyone who never buys any, so old saves round-trip."""
    if character.thaumaturgy is None:
        character.thaumaturgy = ThaumaturgyState()
    return character.thaumaturgy


def learn_thaum_art(ruleset: RuleSet, character: Character, art_id: str) -> XpEntry:
    """Train in an Art (+2 dice to its attempts). Occult minimums are a validate
    concern, matching how Charm minimums are handled."""
    _ensure_locked(character)
    if art_id not in ruleset.thaum_arts:
        raise AdvancementError(f"Unknown thaumaturgic Art {art_id!r}.")
    state = _thaum(character)
    if art_id in state.arts:
        raise AdvancementError(f"{art_id} is already trained.")
    cost = costs.thaum_art_xp(ruleset, character)
    entry = _commit(character, "thaum_arts", art_id, None, None, cost)
    state.arts.append(art_id)
    return entry


def add_thaum_specialty(ruleset: RuleSet, character: Character, art_id: str,
                        name: str, *, narrowed: bool = False) -> XpEntry:
    """Buy a specialty in an Art — including a printed aspect, which IS a general
    specialty (p.126). Owning the Art is explicitly NOT required (p.116), so this
    checks only that the Art exists; `narrowed` halves the cost and is Summoning's
    alone, which validate enforces."""
    _ensure_locked(character)
    name = name.strip()
    if not name:
        raise AdvancementError("A specialty needs a name.")
    if art_id not in ruleset.thaum_arts:
        raise AdvancementError(f"Unknown thaumaturgic Art {art_id!r}.")
    state = _thaum(character)
    if any(s.art_id == art_id and s.name.casefold() == name.casefold()
           for s in state.art_specialties):
        raise AdvancementError(f"Specialty {name!r} in {art_id} is already known.")
    cost = costs.thaum_specialty_xp(ruleset, character, narrowed=narrowed)
    entry = _commit(character, "thaum_specialties", f"{art_id}:{name}", None, None, cost)
    state.art_specialties.append(ArtSpecialty(art_id=art_id, name=name, narrowed=narrowed))
    return entry


def raise_thaum_science(ruleset: RuleSet, character: Character, science_id: str) -> XpEntry:
    """Raise a Science by one dot: 7 XP for the first, then current rating × 6.

    The ceiling is the Science's OWN `max_rating` rather than the usual _DOT_MAX. All
    four Sciences stop at 5 — Alchemy's printed six-dot rung is a typo for five (human,
    2026-07-30) — so this reads as a plain 5 today. Kept per-Science because the ceiling
    is rules data, not an engine constant.
    """
    _ensure_locked(character)
    science = ruleset.thaum_sciences.get(science_id)
    if science is None:
        raise AdvancementError(f"Unknown thaumaturgic Science {science_id!r}.")
    state = _thaum(character)
    held = next((s for s in state.sciences if s.science_id == science_id), None)
    frm = held.rating if held is not None else 0
    if frm >= science.max_rating:
        raise AdvancementError(
            f"{science.name} is already at {science.max_rating}, its maximum.")
    cost = costs.thaum_science_step_xp(ruleset, character, frm)
    entry = _commit(character, f"thaum_sciences.{science_id}", science_id, frm, frm + 1, cost)
    if held is None:
        state.sciences.append(ScienceRating(science_id=science_id, rating=1))
    else:
        held.rating = frm + 1
    return entry


def learn_thaum_ritual(ruleset: RuleSet, character: Character, ritual_id: str = "", *,
                       name: str = "", level: int = 1,
                       orientation: Orientation = Orientation.REALM) -> XpEntry:
    """Learn a ritual in ONE regional version. Catalogue (`ritual_id`) or custom
    (`name` + `level`) — the book expects STs to write more.

    Exactly one orientation is bought here; further versions go through
    `add_thaum_orientation`, so no log row is ever ambiguous between the two.
    """
    _ensure_locked(character)
    if ritual_id:
        ritual = ruleset.thaum_rituals.get(ritual_id)
        if ritual is None:
            raise AdvancementError(f"Unknown ritual {ritual_id!r}.")
        key, level = ritual_id, ritual.level
    else:
        key = name.strip()
        if not key:
            raise AdvancementError("A custom ritual needs a name.")
    state = _thaum(character)
    if any((r.ritual_id or r.name) == key for r in state.rituals):
        raise AdvancementError(f"Ritual {key!r} is already known; "
                               "buy another orientation of it instead.")
    cost = costs.thaum_ritual_xp(ruleset, character, level, 1)
    # to_rating carries the level so the audit can re-price the row from the log
    # alone, even if the catalogue entry later changes or the ritual was custom.
    entry = _commit(character, "thaum_rituals", key, None, level, cost)
    state.rituals.append(RitualEntry(
        ritual_id=ritual_id, name="" if ritual_id else key,
        level=level, orientations=[orientation]))
    return entry


def learn_thaum_formula(ruleset: RuleSet, character: Character, formula_id: str = "", *,
                        name: str = "", science_id: str = "", level: int = 1,
                        orientation: Orientation = Orientation.REALM) -> XpEntry:
    """Learn a formula or procedure in ONE regional version. Flat 1 XP whatever its
    level — the cheapest purchasable in thaumaturgy."""
    _ensure_locked(character)
    if formula_id:
        formula = ruleset.thaum_formulas.get(formula_id)
        if formula is None:
            raise AdvancementError(f"Unknown formula {formula_id!r}.")
        key, level, science_id = formula_id, formula.level, formula.science_id
    else:
        key = name.strip()
        if not key:
            raise AdvancementError("A custom formula needs a name.")
    state = _thaum(character)
    if any((f.formula_id or f.name) == key for f in state.formulas):
        raise AdvancementError(f"Formula {key!r} is already known; "
                               "buy another orientation of it instead.")
    cost = costs.thaum_formula_xp(ruleset, character, 1)
    entry = _commit(character, "thaum_formulas", key, None, level, cost)
    state.formulas.append(FormulaEntry(
        formula_id=formula_id, name="" if formula_id else key,
        science_id=science_id, level=level, orientations=[orientation]))
    return entry


def add_thaum_orientation(ruleset: RuleSet, character: Character, kind: str,
                          key: str, orientation: Orientation) -> XpEntry:
    """Learn a further regional version of a ritual or formula already known — a flat
    1 point whichever it is (p.124). `kind` is "ritual" or "formula"; `key` is the id,
    or the name for a custom entry."""
    _ensure_locked(character)
    if kind not in ("ritual", "formula"):
        raise AdvancementError(f"kind must be 'ritual' or 'formula', not {kind!r}.")
    state = _thaum(character)
    entries = state.rituals if kind == "ritual" else state.formulas
    target = next((e for e in entries
                   if ((e.ritual_id if kind == "ritual" else e.formula_id) or e.name) == key),
                  None)
    if target is None:
        raise AdvancementError(f"No known {kind} {key!r} to add an orientation to.")
    if orientation in target.orientations:
        raise AdvancementError(
            f"{key} is already known in its {orientation.value} version.")
    cost = costs.thaum_orientation_xp(ruleset, character)
    entry = _commit(character, f"thaum_orientations.{kind}",
                    f"{key}:{orientation.value}", None, None, cost)
    target.orientations.append(orientation)
    return entry
