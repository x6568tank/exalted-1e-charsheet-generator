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
    # A Merit or Flaw may move the ceiling for one named Attribute — Legendary
    # Attribute explicitly applies "during character creation or after it".
    cap = merits.merits_and_flaws_calc(ruleset, character).attribute_caps.get(
        attr.value, _DOT_MAX)
    # An elder's Attributes follow permanent Essence up past 5 (p.258). Whichever
    # ceiling is HIGHER wins: both are permissions, and neither is written as a limit
    # on the other, so a Legendary Attribute never holds an elder down and vice versa.
    cap = max(cap, elder.trait_ceiling(character, ruleset, domain="attribute"))
    # A per-ORIGIN Attribute ceiling (the Unenlightened Mountain Folk's Intelligence
    # 2, CH6 p.230) is a CEILING on one named Attribute that can only LOWER the cap,
    # like the Dragon-King Essence gate just below.
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    origin_attr_cap = b.attribute_caps.get(attr.value)
    if origin_attr_cap:
        cap = min(cap, origin_attr_cap)
    # The Dragon-King Essence gate (PG p.177 "Maximum Intelligence and Path Level")
    # is a CEILING on Intelligence specifically — 1/3/5/6 at Essence 1/2/3-5/6 — so
    # unlike the permission ceilings above, it can only LOWER the cap, and it binds
    # post-lock too (the chargen check alone would let XP raise Intelligence past it).
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
    """Begin a new per-focus Craft Ability at rating 1 (core p.136). Priced as a new
    Ability (the flat 'new ability' cost, with the Caste/Favoured discount baked into
    ability_step). Focus must be non-empty and not already owned."""
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
    """Raise an existing per-focus Craft Ability one dot, scaled like any Ability."""
    _ensure_locked(character)
    cr = next((c for c in character.crafts if c.focus == focus), None)
    if cr is None:
        raise AdvancementError(f"No Craft ({focus}) to raise; learn it first.")
    # A per-focus Craft IS an Ability (core p.136), so the elder ceiling reaches it.
    cap = elder.trait_ceiling(character, ruleset, domain="ability")
    if cr.rating >= cap:
        raise AdvancementError(f"Craft ({focus}) is already at {cap}.")
    cost = costs.ability_step(ruleset, character, AbilityName.CRAFT, cr.rating)
    entry = _commit(character, "crafts", focus, cr.rating, cr.rating + 1, cost)
    cr.rating += 1
    return entry


def learn_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    """Begin a new Astrological College at rating 1 (Sidereal, p.265). Flat new_college
    cost. The id must be a real College and not already owned."""
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
    """Raise an existing College one dot, scaled (current × 3, p.265).

    NOT lifted by the elder ceiling: p.258 names "Abilities and Attributes", and a
    College is neither — it is a rated Advantage with its own chargen pool. Held at
    `_DOT_MAX` deliberately; do not "fix" it without a page saying otherwise."""
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
    # True Paragon lets Virtues be raised to 6 "with bonus or experience points".
    mf_cap = merits.merits_and_flaws_calc(ruleset, character).virtue_cap
    cap = mf_cap if mf_cap is not None else _DOT_MAX
    # The Dragon-King Essence-gated Virtue ceiling (PG p.177 row 6: at Essence 6 a
    # Dragon King may raise Virtues to 6). A PERMISSION like the Merit's — the
    # higher wins — because below Essence 6 the table is 5 (the default) and only
    # row 6 exceeds it. Without this, `_DOT_MAX` (5) would make the Essence-6
    # Virtue-6 unlock unreachable.
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
    """Raise permanent Willpower one dot (increments the purchased component; the
    pinned Virtue component is untouched)."""
    _ensure_locked(character)
    frm = derive.willpower(character, ruleset)
    if frm >= _WILLPOWER_MAX:
        raise AdvancementError(f"Willpower is already at {_WILLPOWER_MAX}.")
    # An origin's HARD cap binds tighter than the universal 10 — Unenlightened
    # Mountain Folk "can never have a permanent Willpower above 6" (CH6 p.230).
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
    # The permanent-Essence ceiling is the splat's `essence_cap` (0 → the flat 9,
    # p.258's chart max), then the p.258 Terrestrial-7 hold. Asked of engine.elder,
    # never decided here. A Merit can override it — Essence Mastery takes a mortal
    # from 1 to 3, "the limit of human potential" (PG p.114) — so the override is
    # applied on top, and it names no Terrestrial hold.
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
# One dot track serves both sides of the lock: pre-lock a free setter, post-lock a
# stepper. These two functions are what the post-lock half needs and the per-dot
# `raise_*` above cannot express on their own. Neither adds a rule or a price — they
# route to the functions above and read the log.
# --------------------------------------------------------------------------- #

# Log targets that ARE dot tracks in the editor, mapped to their per-dot raise. The
# names match the `XpEntry.target` convention `undo_last` already partitions on, so
# the UI names a trait the same way everywhere. Willpower is deliberately absent: it
# is a number input, not a track, because decision 0005 pins its Virtue component and
# only `willpower_purchased` moves. Crafts and Colleges are absent because they carry
# a `detail` (the focus / college id) and are their own controls.
def _step_craft(ruleset: RuleSet, character: Character, focus: str) -> XpEntry:
    """One dot of a per-focus Craft, whichever side of 0 it starts on. A dot track
    spans "not owned" and "owned at 1" as one gesture, but the engine prices those
    differently (a new Ability vs a scaled raise), so the split lives here rather
    than in the UI."""
    known = any(cr.focus == focus for cr in character.crafts)
    return raise_craft(ruleset, character, focus) if known \
        else learn_craft(ruleset, character, focus)


def _step_college(ruleset: RuleSet, character: Character, college_id: str) -> XpEntry:
    known = any(cr.college_id == college_id for cr in character.colleges)
    return raise_college(ruleset, character, college_id) if known \
        else learn_college(ruleset, character, college_id)


# Callables take (ruleset, character, key, detail): `key` is the part of the target
# after the dot (an Attribute/Ability/Virtue name), `detail` the XpEntry detail that
# identifies WHICH craft or college. Most targets use one or the other, never both.
_DOT_TRACK_RAISES = {
    "attributes": lambda rs, c, key, detail: raise_attribute(rs, c, AttributeName(key)),
    "abilities": lambda rs, c, key, detail: raise_ability(rs, c, AbilityName(key)),
    "virtues": lambda rs, c, key, detail: raise_virtue(rs, c, VirtueName(key)),
    "essence": lambda rs, c, key, detail: raise_essence(rs, c),
    "crafts": lambda rs, c, key, detail: _step_craft(rs, c, detail),
    "colleges": lambda rs, c, key, detail: _step_college(rs, c, detail),
    "paths": lambda rs, c, key, detail: _step_path(rs, c, detail),
}


# The same four targets going down, for `lower_to`. Reductions take no ruleset (they
# are priced at nothing and gated only by each trait's floor), which is why this is a
# separate table rather than a direction flag on the one above.
# Crafts and Colleges reduce too (human, 2026-07-31) — a usability escape hatch rather
# than a printed rule, because undo is LIFO and cannot always reach a misclick. Their
# lowerers need no ruleset either, so the whole table keeps one signature; `lower_college`
# takes one only for its error message and is adapted here.
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
    """The per-dot raise for a log target, or None if that target is not a dot track."""
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
    """How many rows at the TAIL of the XP log are consecutive *raises* of exactly
    this target — i.e. how many dots of it `undo_last` could give back right now.

    This is what greys the downward-click dialog's undo branch and caps its count. It
    is emphatically NOT "how many dots of this trait were bought": undo is LIFO across
    the whole log, so a raise buried under any other purchase is unreachable until
    that purchase is unwound, and this returns 0 for it. Reading it as a per-trait
    refund allowance is the misreading decision 0013 warns about.

    A REDUCTION at the tail stops the count. It shares the log with purchases but is
    not one — it refunded nothing, so there is nothing above it to refund. Direction
    (`to_rating > from_rating`) is what distinguishes them, not cost: a withheld-Charm
    pick (Weak Essence) is a genuine purchase that also costs 0.
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
    """Raise a dot-tracked trait to `to_rating`, one logged step per dot.

    The stepper behind an upward click on a post-lock dot track. Every step goes
    through the ordinary per-dot `raise_*`, so each dot is priced from the live rating
    (the escalating `current x N`) and gated by the same caps — no pricing or rule
    lives here.

    **The whole click is validated before any of it commits.** A probe run against a
    deep copy spends the identical functions, so an unaffordable or illegal click
    raises with the character untouched rather than landing halfway up the track with
    the XP gone. That is the failure mode this exists to prevent, and it is why the
    UI can offer a multi-dot click at all.

    Downward is not handled here — it is the dialog's job to choose between undo and
    reduce, and silently refunding here would make that choice. A `to_rating` at or
    below the current one returns [] and changes nothing.
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

    # Probe first: same functions, throwaway character. Anything illegal or
    # unaffordable raises here, before the real character has been touched.
    probe = character.model_copy(deep=True)
    for _ in range(steps):
        step(ruleset, probe, key, detail)

    return [step(ruleset, character, key, detail) for _ in range(steps)]


def refund_to(ruleset: RuleSet, character: Character, target: str,
              to_rating: int, detail: str = "") -> list[XpEntry]:
    """Give back dots of a trait by UNDOING the purchases that bought them — the
    dialog's refund branch. XP comes back; the log rows go away.

    Bounded by `refundable_depth`, and that bound is a hard error rather than a
    truncation: undo is LIFO across the whole log, so unwinding more rows than this
    trait owns at the tail would silently reverse somebody else's purchase. A caller
    that wants to go further is asking for a reduction, not a refund.
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
    """Reduce a trait by `curse` — the dialog's other branch. Free, refunds nothing,
    one logged reduction per dot.

    Unlike `refund_to` this is NOT bounded by what was bought: a curse reaches chargen
    dots too, and goes below the snapshot. The only floor is each trait's own.
    Probe-validated like `raise_to`, so a click that runs past the floor is refused
    whole rather than lowering as far as it can.
    """
    _ensure_locked(character)
    domain, _, key = target.partition(".")
    step = _DOT_TRACK_LOWERS.get(domain)
    if step is None:
        raise AdvancementError(f"{target!r} is not a dot-tracked trait.")
    steps = _dot_track_rating(character, target, detail) - to_rating
    if steps <= 0:
        return []

    # Crafts and Colleges carry their identity in `detail`, not in the target; every
    # other dot track is the other way round. One of the two is always empty.
    ident = detail or key
    probe = character.model_copy(deep=True)
    for _ in range(steps):
        step(probe, ident, reason)

    return [step(character, ident, reason) for _ in range(steps)]


# --------------------------------------------------------------------------- #
# Permanent reductions (curses, Charm costs, story effects)
#
# A reduction lowers a permanent trait *outside* the XP economy: it refunds NO XP
# (cost 0) and is logged as an append-only row with to_rating < from_rating, so the
# audit prices it at 0 and `undo_last` reverses it like any other row. These are
# story-driven (a curse that saps Strength, a Charm with a permanent cost), so the
# engine enforces only the floor — not any rules reason. The `reason` is free text
# (stored on the row's detail) shown in the ledger. If a reduction drops an Ability
# below a known Charm's requirement, the normal validate() surfaces that — by design.
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
    """Reduce permanent Willpower one dot (a curse). Decrements the purchased
    component, which may go negative — permanent Willpower = pinned Virtue component
    + purchased, so a curse below the Virtue floor is represented as net-negative
    purchased. Floored at a permanent Willpower of 1."""
    _ensure_locked(character)
    # `ruleset` is optional to match its `lower_*` siblings, but OMITTING IT IS A BUG
    # for any character holding a Flaw that moves Willpower — Weak-Willed sells dots,
    # Callous keeps tracking the Virtues. Without it the "already at 1" guard tests the
    # wrong number and the ledger records a reduction that never happened.
    frm = derive.willpower(character, ruleset)
    if frm <= 1:
        raise AdvancementError("Willpower is already at 1 (the minimum).")
    character.willpower_purchased -= 1
    return _log_reduction(character, "willpower", frm, frm - 1, reason)


def lower_craft(character: Character, focus: str, reason: str = "") -> XpEntry:
    """Reduce a per-focus Craft one dot, removing it entirely at 0.

    Not a printed rule but a usability one (human, rules authority, 2026-07-31): undo
    is LIFO and so cannot always reach a mistake, and "a misclick can always happen".
    Like every reduction it refunds nothing — this is an escape hatch, not a refund
    path, and `refund_to` remains the way to get experience back.
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
        # A Craft IS its focus; rating 0 is not a state it has (learn_craft starts it
        # at 1), so the row goes rather than lingering as an empty Ability.
        character.crafts.remove(cr)
    return _log_reduction(character, "crafts", frm, frm - 1, reason or focus)


def lower_college(ruleset: RuleSet, character: Character, college_id: str,
                  reason: str = "") -> XpEntry:
    """Reduce an Astrological College one dot, removing it entirely at 0. Same
    reasoning as `lower_craft`."""
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
    """Begin a new Dragon-King Path at rating 1 (PG pp.175-177). Flat cost — 7 XP, or
    6 for a Breed/Favoured Path (p.176). The id must be a real Path and not already
    owned. The Essence gate (max rating 1 at Essence 1) never binds the first dot for
    a playable Dragon King (they start at Essence 2+), but is checked for the same
    reason every other gate is."""
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
    """Raise an existing Path one dot, scaled on the current rating (p.176: ×5, ×4
    for a Breed/Favoured Path). Capped by the Essence gate (p.177: a Path may not
    exceed 1/3/5/6 at Essence 1/2/3-5/6) — which is also the Path's whole ceiling,
    since Essence 6 is the life cap and admits Path 6. Deliberately NOT lifted by the
    trait ceiling: `elder.trait_ceiling` raises Abilities and Attributes, and a Path
    is a rated Advantage with its own gate."""
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
    """Reduce a Path one dot, removing it entirely at 0. Same reasoning as
    `lower_craft`/`lower_college` (a usability escape hatch, not a printed rule)."""
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
    """One dot of a Path, whichever side of 0 it starts on (the dot-track split)."""
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
# The Abyssal Curse's lasting half moves in BOTH directions, and the two directions
# have different prices, which is why it needs its own pair of functions rather than
# riding the curse path:
#
#   * GAINING a dot is a story event — "whenever the character's Resonance pool exceeds
#     a rating of 10 … she gains a point of permanent Resonance" — and costs nothing.
#   * SHEDDING one costs five experience points and a Harrowing.
#
# Both are logged, so the ledger is the audit trail for a permanent trait exactly as
# decision 0006 requires. The Harrowing itself is a story requirement no engine can
# check; see `XpEntry.training_complete` for the class of rule it belongs to.
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

    "You don't raise specialties, you just take the same one multiple times, and you
    can only have 3 specialties per ability" (human, rules authority, 2026-07-31):
    Melee with two Swords and one Parrying is legal and full. So duplicates are the
    stacking mechanism, and the cap counts ROWS in an Ability, not distinct names.
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
