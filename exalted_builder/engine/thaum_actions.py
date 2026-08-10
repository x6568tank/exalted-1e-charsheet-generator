"""
engine/thaum_actions.py — the thaumaturgy purchase dispatchers.

Each function here dispatches on the lock: a chargen list edit before it, an
`engine.advancement` purchase after it. Each returns the message the caller should
show, and raises `advancement.AdvancementError` when the purchase is refused. None of
them decides legality — the gates come from `engine.validate`.

⚠ **The raised type is part of the contract.** `ui/picker.py` catches
`advancement.AdvancementError` to turn a refusal into a notification; a different
exception type here becomes a traceback in the browser instead of "Already trained in
that Art." Keep `_refuse` raising exactly that.

**Naming.** Several of these share a name with the `engine.advancement` function they
call after the lock (`raise_thaum_science`, `add_thaum_orientation`). That is why this
is its own module rather than more of `advancement.py`: the dispatcher and the priced
purchase are two different things and cannot both be `advancement.raise_thaum_science`.
Read `thaum_actions.x` as "the lock-aware x", `advancement.x` as "the XP purchase".

Moved verbatim out of `ui/picker.py` 2026-08-10 — it is game logic and never imported
`nicegui`, so it did not belong in the UI layer (CLAUDE.md: "don't leak game logic into
the UI"). `picker.py` re-exports every public name, so existing call sites are
unchanged. The move was behaviour-preserving: no edits beyond this docstring.

They were module-level rather than closures inside `build_picker` on the `ui/play.py`
precedent, and that reasoning still holds here: these are the functions that actually
mutate a save, and a bug in one silently corrupts a character's point accounting, so
they must be reachable from tests without driving a browser (several buy buttons
legitimately share a label, which makes click-testing them individually impossible).
"""

from __future__ import annotations

from ..models.character import (ArtSpecialty, Character, FormulaEntry, RitualEntry,
                                ScienceRating, ThaumaturgyState)
from ..models.rules import Orientation, RuleSet
from . import advancement, costs, validate


def thaum_state_of(character: Character) -> ThaumaturgyState:
    """The character's ThaumaturgyState, created on first purchase so a character who
    never buys any thaumaturgy keeps `thaumaturgy` None in their save."""
    if character.thaumaturgy is None:
        character.thaumaturgy = ThaumaturgyState()
    return character.thaumaturgy


def _refuse(message: str) -> None:
    raise advancement.AdvancementError(message)


def _entry_list(character: Character, kind: str) -> list:
    st = thaum_state_of(character)
    return st.rituals if kind == "ritual" else st.formulas


def _entry_key(entry, kind: str) -> str:
    return (entry.ritual_id if kind == "ritual" else entry.formula_id) or entry.name


def find_thaum_entry(character: Character, kind: str, key: str):
    return next((e for e in _entry_list(character, kind)
                 if _entry_key(e, kind) == key), None)


def buy_thaum_art(ruleset: RuleSet, character: Character, art_id: str) -> str:
    reason = validate.thaum_art_locked_reason(ruleset, character, art_id)
    if reason:
        _refuse(reason)
    st = thaum_state_of(character)
    if art_id in st.arts:
        _refuse("Already trained in that Art.")
    name = ruleset.thaum_arts[art_id].name
    if character.chargen_locked:
        advancement.learn_thaum_art(ruleset, character, art_id)
        return f"Learned the Art of {name} — {costs.thaum_art_xp(ruleset, character)} XP"
    st.arts.append(art_id)
    return f"Trained in the Art of {name}"


def drop_thaum_art(ruleset: RuleSet, character: Character, art_id: str) -> str:
    st = thaum_state_of(character)
    if art_id not in st.arts:
        _refuse("That Art is not trained.")
    st.arts.remove(art_id)
    return f"Dropped the Art of {ruleset.thaum_arts[art_id].name}"


def buy_thaum_specialty(ruleset: RuleSet, character: Character, art_id: str,
                        name: str, *, narrowed: bool = False) -> str:
    """Buy a specialty — a printed aspect or a player-invented one, which are the same
    purchase at the same rate (p.126). Owning the parent Art is NOT required and must
    never become a condition here (p.116, stated three times)."""
    name = (name or "").strip()
    if not name:
        _refuse("A specialty needs a name.")
    reason = validate.thaum_aspect_locked_reason(ruleset, character, art_id, name)
    if reason:
        _refuse(reason)
    st = thaum_state_of(character)
    if any(s.art_id == art_id and s.name.casefold() == name.casefold()
           for s in st.art_specialties):
        _refuse(f"{name} is already known.")
    if character.chargen_locked:
        advancement.add_thaum_specialty(ruleset, character, art_id, name,
                                        narrowed=narrowed)
        return (f"Learned the {name} specialty — "
                f"{costs.thaum_specialty_xp(ruleset, character, narrowed=narrowed)} XP")
    st.art_specialties.append(
        ArtSpecialty(art_id=art_id, name=name, narrowed=narrowed))
    return f"Added the {name} specialty"


def drop_thaum_specialty(character: Character, art_id: str, name: str) -> str:
    st = thaum_state_of(character)
    held = next((s for s in st.art_specialties if s.art_id == art_id
                 and s.name.casefold() == name.casefold()), None)
    if held is None:
        _refuse(f"{name} is not known.")
    st.art_specialties.remove(held)
    return f"Dropped the {name} specialty"


def raise_thaum_science(ruleset: RuleSet, character: Character, science_id: str) -> str:
    reason = validate.thaum_science_raise_reason(
        ruleset, character, science_id, chargen=not character.chargen_locked)
    if reason:
        _refuse(reason)
    st = thaum_state_of(character)
    held = next((s for s in st.sciences if s.science_id == science_id), None)
    frm = held.rating if held is not None else 0
    name = ruleset.thaum_sciences[science_id].name
    if character.chargen_locked:
        cost = costs.thaum_science_step_xp(ruleset, character, frm)
        advancement.raise_thaum_science(ruleset, character, science_id)
        return f"{name} {frm} → {frm + 1} — {cost} XP"
    if held is None:
        st.sciences.append(ScienceRating(science_id=science_id, rating=1))
    else:
        held.rating = frm + 1
    return f"{name} {frm} → {frm + 1}"


def lower_thaum_science(ruleset: RuleSet, character: Character, science_id: str) -> str:
    st = thaum_state_of(character)
    held = next((s for s in st.sciences if s.science_id == science_id), None)
    if held is None or held.rating <= 0:
        _refuse("That Science is not held.")
    held.rating -= 1
    if held.rating <= 0:                 # a 0-dot Science is not held at all
        st.sciences.remove(held)
    return f"{ruleset.thaum_sciences[science_id].name} lowered"


def buy_thaum_entry(ruleset: RuleSet, character: Character, kind: str, key: str,
                    orientation: Orientation) -> str:
    """Learn a catalogue ritual or formula in one regional version."""
    catalogue = ruleset.thaum_rituals if kind == "ritual" else ruleset.thaum_formulas
    obj = catalogue.get(key)
    if obj is None:
        _refuse(f"Unknown {kind} {key!r}.")
    if find_thaum_entry(character, kind, key) is not None:
        _refuse(f"{obj.name} is already known — buy another orientation of it instead.")
    if kind == "ritual":
        reason = validate.thaum_ritual_locked_reason(
            ruleset, character, obj.level, chargen=not character.chargen_locked)
        if reason:
            _refuse(reason)
    if character.chargen_locked:
        learn = (advancement.learn_thaum_ritual if kind == "ritual"
                 else advancement.learn_thaum_formula)
        entry = learn(ruleset, character, key, orientation=orientation)
        return f"Learned {obj.name} ({orientation.value}) — {entry.cost} XP"
    if kind == "ritual":
        _entry_list(character, kind).append(RitualEntry(
            ritual_id=key, level=obj.level, orientations=[orientation]))
    else:
        _entry_list(character, kind).append(FormulaEntry(
            formula_id=key, science_id=obj.science_id, level=obj.level,
            orientations=[orientation]))
    return f"Learned {obj.name} ({orientation.value})"


def drop_thaum_entry(character: Character, kind: str, key: str) -> str:
    target = find_thaum_entry(character, kind, key)
    if target is None:
        _refuse(f"No known {kind} {key!r}.")
    _entry_list(character, kind).remove(target)
    return f"Dropped {key}"


def add_thaum_orientation(ruleset: RuleSet, character: Character, kind: str,
                          key: str, orientation: Orientation) -> str:
    """A further regional version of something already known — a flat point each
    (p.124), and its own logged purchase so the XP log stays unambiguous."""
    target = find_thaum_entry(character, kind, key)
    if target is None:
        _refuse(f"No known {kind} {key!r} to add an orientation to.")
    if orientation in target.orientations:
        _refuse(f"Already known in its {orientation.value} version.")
    if character.chargen_locked:
        cost = costs.thaum_orientation_xp(ruleset, character)
        advancement.add_thaum_orientation(ruleset, character, kind, key, orientation)
        return f"Added the {orientation.value} version — {cost} XP"
    target.orientations.append(orientation)
    return f"Added the {orientation.value} version"


def buy_custom_ritual(ruleset: RuleSet, character: Character, name: str, level: int,
                      orientation: Orientation) -> str:
    """Author a ritual the catalogue does not hold. The book prints five and plainly
    expects more to be written (p.148), so the catalogue is a seed — the
    editable-custom-weapons precedent."""
    name = (name or "").strip()
    if not name:
        _refuse("A custom ritual needs a name.")
    level = int(level or 1)
    reason = validate.thaum_ritual_locked_reason(
        ruleset, character, level, chargen=not character.chargen_locked)
    if reason:
        _refuse(reason)
    if find_thaum_entry(character, "ritual", name) is not None:
        _refuse(f"{name} is already known.")
    if character.chargen_locked:
        entry = advancement.learn_thaum_ritual(
            ruleset, character, name=name, level=level, orientation=orientation)
        return f"Learned {name} (level {level}) — {entry.cost} XP"
    _entry_list(character, "ritual").append(
        RitualEntry(name=name, level=level, orientations=[orientation]))
    return f"Learned {name} (level {level})"
