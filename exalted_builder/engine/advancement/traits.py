"""
engine/advancement/traits.py — the rated-trait transitions: one-dot raises, the
dot-track surface (decision 0013), permanent reductions, Paths, Resonance, and
specialties.
"""

from __future__ import annotations

from .. import costs, derive, elder, merits, paths, validate
from ...models.character import (Character, CollegeRating, CraftRating, PathRating,
                                 Specialty, XpEntry)
from ...models.rules import AbilityName, AttributeName, RuleSet, VirtueName

from ._base import (_DOT_MAX, _WILLPOWER_MAX, AdvancementError, _commit,
                    _ensure_locked, specialty_cap, specialty_count)
from .undo import undo_last


# --------------------------------------------------------------------------- #
# Scaled-trait raises (one dot each)
# --------------------------------------------------------------------------- #

def raise_attribute(ruleset: RuleSet, character: Character, attr: AttributeName) -> XpEntry:
    _ensure_locked(character)
    frm = character.attributes[attr]
    # A Merit or Flaw can move the ceiling of one Attribute, at and after chargen.
    cap = merits.merits_and_flaws_calc(ruleset, character).attribute_caps.get(
        attr.value, _DOT_MAX)
    # p.258: Attributes follow permanent Essence above 5. The HIGHER of this and the
    # Merit ceiling wins: both are permissions.
    cap = max(cap, elder.trait_ceiling(character, ruleset, domain="attribute"))
    # An origin ceiling (CH6 p.230) can only LOWER the cap.
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    origin_attr_cap = b.attribute_caps.get(attr.value)
    if origin_attr_cap:
        cap = min(cap, origin_attr_cap)
    # PG p.177: the Essence gate on Intelligence can only LOWER the cap. ⚠ It applies
    # after the lock too.
    if attr == AttributeName.INTELLIGENCE:
        int_cap = b.intelligence_max_by_essence.get(character.essence_rating, 0)
        if int_cap:
            cap = min(cap, int_cap)
    if frm >= cap:
        raise AdvancementError(f"{attr.value} is already at {cap}.")
    cost = costs.attribute_step(ruleset, character, frm, attr)
    entry = _commit(character, f"attributes.{attr.value}", "", frm, frm + 1, cost)
    character.attributes[attr] = frm + 1
    return entry


def raise_ability(ruleset: RuleSet, character: Character, ability: AbilityName) -> XpEntry:
    _ensure_locked(character)
    frm = character.abilities.get(ability, 0)
    # p.258 caps an elder's Abilities at permanent Essence, the same as Attributes.
    cap = elder.trait_ceiling(character, ruleset, domain="ability")
    if frm >= cap:
        raise AdvancementError(f"{ability.value} is already at {cap}.")
    cost = costs.ability_step(ruleset, character, ability, frm)
    entry = _commit(character, f"abilities.{ability.value}", "", frm, frm + 1, cost)
    character.abilities[ability] = frm + 1
    return entry


def learn_craft(ruleset: RuleSet, character: Character, focus: str) -> XpEntry:
    """Start a new Craft focus at rating 1 (core p.136). Priced as a new Ability
    (ability_step). The focus must be non-empty and not owned."""
    _ensure_locked(character)
    focus = focus.strip()
    if not focus:
        raise AdvancementError("A craft needs a focus (e.g. Smithing).")
    if any(c.focus.casefold() == focus.casefold() for c in character.crafts):
        raise AdvancementError(f"Craft ({focus}) already exists; raise it instead.")
    cost = costs.ability_step(ruleset, character, AbilityName.CRAFT, 0)
    entry = _commit(character, "crafts", focus, 0, 1, cost)
    character.crafts.append(CraftRating(focus=focus, rating=1))
    return entry


def raise_craft(ruleset: RuleSet, character: Character, focus: str) -> XpEntry:
    """Raise an owned Craft focus one dot, scaled as an Ability."""
    _ensure_locked(character)
    cr = next((c for c in character.crafts if c.focus == focus), None)
    if cr is None:
        raise AdvancementError(f"No Craft ({focus}) to raise; learn it first.")
    # A Craft focus is an Ability (core p.136): the elder ceiling applies.
    cap = elder.trait_ceiling(character, ruleset, domain="ability")
    if cr.rating >= cap:
        raise AdvancementError(f"Craft ({focus}) is already at {cap}.")
    cost = costs.ability_step(ruleset, character, AbilityName.CRAFT, cr.rating)
    entry = _commit(character, "crafts", focus, cr.rating, cr.rating + 1, cost)
    cr.rating += 1
    return entry


def learn_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    """Start a new Astrological College at rating 1 (Sidereal, p.265). The id must be
    a real College and not owned."""
    _ensure_locked(character)
    if college_id not in ruleset.colleges:
        raise AdvancementError(f"Unknown college {college_id!r}.")
    if any(c.college_id == college_id for c in character.colleges):
        raise AdvancementError(f"{ruleset.colleges[college_id].name} is already known; raise it instead.")
    cost = costs.college_new_cost(ruleset, character)
    entry = _commit(character, "colleges", college_id, 0, 1, cost)
    character.colleges.append(CollegeRating(college_id=college_id, rating=1))
    return entry


def raise_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    """Raise an owned College one dot (current × 3, p.265).

    ⚠ The elder ceiling does NOT apply: p.258 names Abilities and Attributes only.
    Held at `_DOT_MAX`."""
    _ensure_locked(character)
    cr = next((c for c in character.colleges if c.college_id == college_id), None)
    if cr is None:
        raise AdvancementError(f"No college {college_id!r} to raise; learn it first.")
    if cr.rating >= _DOT_MAX:
        raise AdvancementError(f"{ruleset.colleges[college_id].name} is already at {_DOT_MAX}.")
    cost = costs.college_step(ruleset, character, cr.rating)
    entry = _commit(character, "colleges", college_id, cr.rating, cr.rating + 1, cost)
    cr.rating += 1
    return entry


def raise_virtue(ruleset: RuleSet, character: Character, virtue: VirtueName) -> XpEntry:
    _ensure_locked(character)
    frm = character.virtues[virtue]
    # True Paragon: Virtues to 6.
    mf_cap = merits.merits_and_flaws_calc(ruleset, character).virtue_cap
    cap = mf_cap if mf_cap is not None else _DOT_MAX
    # PG p.177 row 6: Virtues to 6 at Essence 6. A permission: the higher wins.
    virt_cap = (ruleset.budgets_for(character.exalt_type, character.origin,
                                    character.upbringing)
                .virtue_max_by_essence.get(character.essence_rating, 0))
    if virt_cap:
        cap = max(cap, virt_cap)
    if frm >= cap:
        raise AdvancementError(f"{virtue.value} is already at {cap}.")
    cost = costs.virtue_step(ruleset, character, frm, virtue)
    entry = _commit(character, f"virtues.{virtue.value}", "", frm, frm + 1, cost)
    character.virtues[virtue] = frm + 1
    return entry


def raise_willpower(ruleset: RuleSet, character: Character) -> XpEntry:
    """Raise permanent Willpower one dot. Increments the purchased component only."""
    _ensure_locked(character)
    frm = derive.willpower(character, ruleset)
    if frm >= _WILLPOWER_MAX:
        raise AdvancementError(f"Willpower is already at {_WILLPOWER_MAX}.")
    # The origin hard cap (CH6 p.230) binds before the universal 10.
    hard_cap = (ruleset.budgets_for(character.exalt_type, character.origin,
                                    character.upbringing).willpower_hard_cap)
    if hard_cap and frm >= hard_cap:
        raise AdvancementError(f"Willpower is already at {hard_cap} for this origin.")
    cost = costs.willpower_step(ruleset, character, frm)
    entry = _commit(character, "willpower", "", frm, frm + 1, cost)
    character.willpower_purchased += 1
    return entry


def raise_essence(ruleset: RuleSet, character: Character) -> XpEntry:
    _ensure_locked(character)
    frm = character.essence_rating
    # engine.elder gives the Essence ceiling. A Merit `essence_cap_override` applies
    # on top (PG p.114).
    cap, terrestrial_limited = elder.essence_cap(ruleset, character)
    override = merits.merits_and_flaws_calc(ruleset, character).essence_cap_override
    if override is not None:
        cap, terrestrial_limited = override, False
    if frm >= cap:
        if terrestrial_limited:
            raise AdvancementError(
                f"Essence is already at {cap}. Terrestrial Exalts may never raise "
                f"permanent Essence higher without outside energies — a Storyteller "
                f"option (see house rules).")
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters cannot raise "
            f"Essence above {cap}.")
    cost = costs.essence_step(ruleset, character, frm)
    entry = _commit(character, "essence", "", frm, frm + 1, cost)
    character.essence_rating = frm + 1
    return entry


# --------------------------------------------------------------------------- #
# The merged trait surface (decision 0013)
#
# One dot track on both sides of the lock: before it a free setter, after it a
# stepper. These functions route to the `raise_*` functions above and read the log.
# They add no rule and no price.
# ---------------------------------------------------------------------------- #

# Log targets that are dot tracks, mapped to their per-dot raise. Names follow the
# `XpEntry.target` convention. Willpower is absent: it is a number input (decision
# 0005). Crafts and Colleges are absent: they carry a `detail`.
def _step_craft(ruleset: RuleSet, character: Character, focus: str) -> XpEntry:
    """Add one dot to a Craft focus, from 0 or above. 0 -> 1 is a new Ability; above
    it is a scaled raise."""
    known = any(cr.focus == focus for cr in character.crafts)
    return raise_craft(ruleset, character, focus) if known \
        else learn_craft(ruleset, character, focus)


def _step_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    known = any(cr.college_id == college_id for cr in character.colleges)
    return raise_college(ruleset, character, college_id) if known \
        else learn_college(ruleset, character, college_id)


# Callables take (ruleset, character, key, detail). `key` is the part of the target
# after the dot. `detail` names the craft or college.
_DOT_TRACK_RAISES = {
    "attributes": lambda rs, c, key, detail: raise_attribute(rs, c, AttributeName(key)),
    "abilities": lambda rs, c, key, detail: raise_ability(rs, c, AbilityName(key)),
    "virtues": lambda rs, c, key, detail: raise_virtue(rs, c, VirtueName(key)),
    "essence": lambda rs, c, key, detail: raise_essence(rs, c),
    "crafts": lambda rs, c, key, detail: _step_craft(rs, c, detail),
    "colleges": lambda rs, c, key, detail: _step_college(rs, c, detail),
    "paths": lambda rs, c, key, detail: _step_path(rs, c, detail),
}


# The reductions for `lower_to`. A reduction takes no ruleset: it costs nothing and
# only the trait floor gates it. Crafts and Colleges reduce too (human's ruling).
# `lower_college` takes a ruleset for its message only, and is adapted here.
_DOT_TRACK_LOWERS = {
    "attributes": lambda c, key, reason: lower_attribute(c, AttributeName(key), reason),
    "abilities": lambda c, key, reason: lower_ability(c, AbilityName(key), reason),
    "virtues": lambda c, key, reason: lower_virtue(c, VirtueName(key), reason),
    "essence": lambda c, key, reason: lower_essence(c, reason),
    "crafts": lambda c, key, reason: lower_craft(c, key, reason),
    "colleges": lambda c, key, reason: _lower_college_by_id(c, key, reason),
    "paths": lambda c, key, reason: _lower_path_by_id(c, key, reason),
}


def _lower_college_by_id(character: Character, college_id: str, reason: str) -> XpEntry:
    """`lower_college` without the ruleset, which it uses only for a message."""
    return lower_college(None, character, college_id, reason)   # type: ignore[arg-type]


def _dot_track_step(target: str):
    """Return the per-dot raise of a log target, or None if it is not a dot track."""
    domain, _, _key = target.partition(".")
    return _DOT_TRACK_RAISES.get(domain)


def _dot_track_rating(character: Character, target: str, detail: str = "") -> int:
    domain, _, key = target.partition(".")
    if domain == "attributes":
        return character.attributes[AttributeName(key)]
    if domain == "abilities":
        return character.abilities.get(AbilityName(key), 0)
    if domain == "virtues":
        return character.virtues[VirtueName(key)]
    if domain == "crafts":
        return next((cr.rating for cr in character.crafts if cr.focus == detail), 0)
    if domain == "colleges":
        return next((cr.rating for cr in character.colleges
                     if cr.college_id == detail), 0)
    if domain == "paths":
        return next((pr.rating for pr in character.paths
                     if pr.path_id == detail), 0)
    return character.essence_rating


def refundable_depth(character: Character, target: str, detail: str = "") -> int:
    """Return how many rows at the TAIL of the XP log are consecutive raises of this
    target: the dots that `undo_last` can give back now.

    ⚠ NOT the dots bought: undo is LIFO across the whole log (decision 0013). A raise
    under any other purchase returns 0.

    A REDUCTION at the tail stops the count. Direction (`to_rating > from_rating`)
    tells them apart, not cost: a withheld-Charm pick also costs 0.
    """
    depth = 0
    for entry in reversed(character.xp_log):
        if entry.target != target or entry.detail != detail:
            break
        if entry.from_rating is None or entry.to_rating is None:
            break
        if entry.to_rating <= entry.from_rating:      # a reduction, not a purchase
            break
        depth += 1
    return depth


def raise_to(ruleset: RuleSet, character: Character, target: str,
             to_rating: int, detail: str = "") -> list[XpEntry]:
    """Raise a dot-tracked trait to `to_rating`, one logged step per dot, through the
    per-dot `raise_*`.

    **The whole click is validated before any of it commits.** A probe on a deep copy
    runs the same functions. An illegal or unaffordable click raises with the
    character unchanged.

    Downward is not handled here: the dialog chooses undo or reduce. A `to_rating`
    at or below the current one returns [].
    """
    _ensure_locked(character)
    step = _dot_track_step(target)
    if step is None:
        raise AdvancementError(
            f"{target!r} is not a dot-tracked trait; raise it with its own control.")
    _domain, _, key = target.partition(".")
    steps = to_rating - _dot_track_rating(character, target, detail)
    if steps <= 0:
        return []

    # Probe first on a copy.
    probe = character.model_copy(deep=True)
    for _ in range(steps):
        step(ruleset, probe, key, detail)

    return [step(ruleset, character, key, detail) for _ in range(steps)]


def refund_to(ruleset: RuleSet, character: Character, target: str,
              to_rating: int, detail: str = "") -> list[XpEntry]:
    """Give back dots of a trait by UNDOING their purchases. XP comes back and the log
    rows go.

    ⚠ Bounded by `refundable_depth`, as an error: more rows would reverse a different
    purchase.
    """
    _ensure_locked(character)
    if _dot_track_step(target) is None:
        raise AdvancementError(f"{target!r} is not a dot-tracked trait.")
    steps = _dot_track_rating(character, target, detail) - to_rating
    if steps <= 0:
        return []
    depth = refundable_depth(character, target, detail)
    if steps > depth:
        raise AdvancementError(
            f"Only {depth} recent purchase(s) of this trait can be refunded — undo is "
            f"last-in-first-out, so anything bought since must be undone first.")
    return [undo_last(ruleset, character) for _ in range(steps)]


def lower_to(character: Character, target: str, to_rating: int,
             reason: str = "", detail: str = "") -> list[XpEntry]:
    """Reduce a trait (a curse). Free, no refund, one logged reduction per dot.

    Not bounded by what was bought: a curse reaches chargen dots. The floor of each
    trait is the only limit. Probe-validated as `raise_to`.
    """
    _ensure_locked(character)
    domain, _, key = target.partition(".")
    step = _DOT_TRACK_LOWERS.get(domain)
    if step is None:
        raise AdvancementError(f"{target!r} is not a dot-tracked trait.")
    steps = _dot_track_rating(character, target, detail) - to_rating
    if steps <= 0:
        return []

    # Crafts and Colleges use `detail`. The other tracks use the target.
    ident = detail or key
    probe = character.model_copy(deep=True)
    for _ in range(steps):
        step(probe, ident, reason)

    return [step(character, ident, reason) for _ in range(steps)]


# --------------------------------------------------------------------------- #
# Permanent reductions (curses, Charm costs, story effects)
#
# A reduction lowers a permanent trait outside the XP economy: cost 0, logged with
# to_rating < from_rating. `undo_last` reverses it. Only the floor is enforced. The
# `reason` is free text on the row. validate() reports a Charm whose requirement is
# then not met.
# --------------------------------------------------------------------------- #

def _log_reduction(character: Character, target: str, frm: int, to: int, reason: str) -> XpEntry:
    entry = XpEntry(target=target, detail=reason, from_rating=frm, to_rating=to, cost=0)
    character.xp_log.append(entry)
    return entry


def lower_attribute(character: Character, attr: AttributeName, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.attributes[attr]
    if frm <= 1:
        raise AdvancementError(f"{attr.value} is already at 1 (the minimum).")
    character.attributes[attr] = frm - 1
    return _log_reduction(character, f"attributes.{attr.value}", frm, frm - 1, reason)


def lower_ability(character: Character, ability: AbilityName, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.abilities.get(ability, 0)
    if frm <= 0:
        raise AdvancementError(f"{ability.value} is already at 0.")
    character.abilities[ability] = frm - 1
    return _log_reduction(character, f"abilities.{ability.value}", frm, frm - 1, reason)


def lower_virtue(character: Character, virtue: VirtueName, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.virtues[virtue]
    if frm <= 1:
        raise AdvancementError(f"{virtue.value} is already at 1 (the minimum).")
    character.virtues[virtue] = frm - 1
    return _log_reduction(character, f"virtues.{virtue.value}", frm, frm - 1, reason)


def lower_willpower(character: Character, reason: str = "", *,
                    ruleset: RuleSet | None = None) -> XpEntry:
    """Reduce permanent Willpower one dot (a curse). The purchased component can go
    negative (permanent = Virtue component + purchased). The floor is 1."""
    _ensure_locked(character)
    # ⚠ Pass `ruleset` for a character with Weak-Willed or Callous. Else the floor
    # test reads the incorrect number.
    frm = derive.willpower(character, ruleset)
    if frm <= 1:
        raise AdvancementError("Willpower is already at 1 (the minimum).")
    character.willpower_purchased -= 1
    return _log_reduction(character, "willpower", frm, frm - 1, reason)


def lower_craft(character: Character, focus: str, reason: str = "") -> XpEntry:
    """Reduce a per-focus Craft one dot, removing it entirely at 0.

    Not a printed rule (human's ruling): undo is LIFO and cannot always reach a
    mistake. It refunds nothing. `refund_to` refunds XP.
    """
    _ensure_locked(character)
    cr = next((c for c in character.crafts if c.focus == focus), None)
    if cr is None:
        raise AdvancementError(f"No Craft ({focus}) to reduce.")
    frm = cr.rating
    if frm <= 0:
        raise AdvancementError(f"Craft ({focus}) is already at 0.")
    cr.rating = frm - 1
    if cr.rating <= 0:
        # A Craft at 0 is removed.
        character.crafts.remove(cr)
    return _log_reduction(character, "crafts", frm, frm - 1, reason or focus)


def lower_college(ruleset: RuleSet, character: Character, college_id: str,
                  reason: str = "") -> XpEntry:
    """Reduce an Astrological College one dot, removing it at 0. As `lower_craft`."""
    _ensure_locked(character)
    cr = next((c for c in character.colleges if c.college_id == college_id), None)
    if cr is None:
        raise AdvancementError(f"No college {college_id!r} to reduce.")
    frm = cr.rating
    if frm <= 0:
        raise AdvancementError("That college is already at 0.")
    cr.rating = frm - 1
    if cr.rating <= 0:
        character.colleges.remove(cr)
    return _log_reduction(character, "colleges", frm, frm - 1, reason or college_id)


def learn_path(ruleset: RuleSet, character: Character, path_id: str) -> XpEntry:
    """Start a new Dragon-King Path at rating 1 (PG pp.175-177): 7 XP, or 6 for a
    Breed/Favoured Path (p.176). The id must be a real Path and not owned. The
    Essence gate is checked."""
    _ensure_locked(character)
    if path_id not in ruleset.paths:
        raise AdvancementError(f"Unknown path {path_id!r}.")
    if any(p.path_id == path_id for p in character.paths):
        raise AdvancementError(f"{ruleset.paths[path_id].name} is already known; raise it instead.")
    if paths.path_essence_max(ruleset, character) < 1:
        raise AdvancementError(
            f"{ruleset.paths[path_id].name} cannot be learned at Essence "
            f"{character.essence_rating}.")
    cost = costs.path_new_cost(ruleset, character, path_id)
    entry = _commit(character, "paths", path_id, 0, 1, cost)
    character.paths.append(PathRating(path_id=path_id, rating=1))
    return entry


def raise_path(ruleset: RuleSet, character: Character, path_id: str) -> XpEntry:
    """Raise an owned Path one dot (p.176: ×5, ×4 for Breed/Favoured), capped by the
    Essence gate (p.177).

    ⚠ `elder.trait_ceiling` does NOT apply: it covers Abilities and Attributes."""
    _ensure_locked(character)
    pr = next((p for p in character.paths if p.path_id == path_id), None)
    if pr is None:
        raise AdvancementError(f"No path {path_id!r} to raise; learn it first.")
    cap = paths.path_essence_max(ruleset, character)
    if pr.rating >= cap:
        raise AdvancementError(
            f"{ruleset.paths[path_id].name} is already at {cap} (the Essence-"
            f"{character.essence_rating} ceiling).")
    cost = costs.path_step(ruleset, character, path_id, pr.rating)
    entry = _commit(character, "paths", path_id, pr.rating, pr.rating + 1, cost)
    pr.rating += 1
    return entry


def lower_path(ruleset: RuleSet, character: Character, path_id: str,
               reason: str = "") -> XpEntry:
    """Reduce a Path one dot, removing it at 0. As `lower_craft`."""
    _ensure_locked(character)
    pr = next((p for p in character.paths if p.path_id == path_id), None)
    if pr is None:
        raise AdvancementError(f"No path {path_id!r} to reduce.")
    frm = pr.rating
    if frm <= 0:
        raise AdvancementError("That path is already at 0.")
    pr.rating = frm - 1
    if pr.rating <= 0:
        character.paths.remove(pr)
    return _log_reduction(character, "paths", frm, frm - 1, reason or path_id)


def _step_path(ruleset: RuleSet, character: Character, path_id: str) -> XpEntry:
    """Add one dot to a Path, from 0 or above."""
    known = any(p.path_id == path_id for p in character.paths)
    return raise_path(ruleset, character, path_id) if known \
        else learn_path(ruleset, character, path_id)


def _lower_path_by_id(character: Character, path_id: str, reason: str) -> XpEntry:
    """`lower_path` without the ruleset, which it uses only for a message."""
    return lower_path(None, character, path_id, reason)   # type: ignore[arg-type]


def lower_essence(character: Character, reason: str = "") -> XpEntry:
    _ensure_locked(character)
    frm = character.essence_rating
    if frm <= 1:
        raise AdvancementError("Essence is already at 1 (the minimum).")
    character.essence_rating = frm - 1
    return _log_reduction(character, "essence", frm, frm - 1, reason)


# --------------------------------------------------------------------------- #
# Permanent Resonance (Death's Taint, PG p.41)
#
# Gaining a dot is a story event and costs nothing. Shedding a dot costs five XP and a
# Harrowing. Both are logged (decision 0006). The Harrowing is not checked.
# --------------------------------------------------------------------------- #

def gain_permanent_resonance(ruleset: RuleSet, character: Character,
                             reason: str = "") -> XpEntry:
    """Add one dot of permanent Resonance. Free — it is inflicted, not bought."""
    _ensure_locked(character)
    cap = derive.permanent_limit_cap(ruleset, character)
    if not cap:
        raise AdvancementError(
            "This character has no permanent Resonance track.")
    frm = character.limit_permanent
    if frm >= cap:
        raise AdvancementError(
            f"Permanent Resonance may not exceed Essence ({cap}).")
    entry = _commit(character, validate.PERMANENT_RESONANCE_TARGET, reason, frm, frm + 1, 0)
    character.limit_permanent = frm + 1
    return entry


def shed_permanent_resonance(ruleset: RuleSet, character: Character,
                             reason: str = "") -> XpEntry:
    """Remove one dot of permanent Resonance for five experience points."""
    _ensure_locked(character)
    frm = character.limit_permanent
    if frm <= 0:
        raise AdvancementError("Permanent Resonance is already 0.")
    cost = merits.PERMANENT_RESONANCE_SHED_XP
    entry = _commit(character, validate.PERMANENT_RESONANCE_TARGET, reason, frm, frm - 1, cost)
    character.limit_permanent = frm - 1
    return entry


def add_specialty(ruleset: RuleSet, character: Character, ability: AbilityName,
                  name: str) -> XpEntry:
    """Buy one specialty. Always worth 1 — a specialty is not a rated trait.

    A duplicate gives the stack. The cap of 3 counts ROWS in an Ability, not names
    (human's ruling): two Swords and one Parrying fills Melee.
    """
    _ensure_locked(character)
    if not name.strip():
        raise AdvancementError("A specialty needs a name.")
    cap = specialty_cap(ruleset, character, ability)
    if specialty_count(character, ability) >= cap:
        if cap == 3:
            raise AdvancementError(
                f"{ability.value} already has three specialties, which is the maximum.")
        raise AdvancementError(
            f"{ability.value} already has {cap} specialties, which is the maximum "
            "for this ability.")
    cost = costs.specialty_cost(ruleset, character, ability)
    entry = _commit(character, "specialties", f"{ability.value}:{name}", None, None, cost)
    character.specialties.append(Specialty(ability=ability, name=name, rating=1))
    return entry
