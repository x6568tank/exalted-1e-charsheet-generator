"""
engine/advancement.py — post-lock XP advancement transitions.

The chargen counterpart is engine.lifecycle; this is the *post-lock* layer. Each
`raise_*`/`learn_*`/`add_*` is a transition that mutates the Character: it prices
the advance via engine.costs, checks it is legal and affordable, applies the trait
change, and appends an append-only XpEntry to character.xp_log. `undo_last`
reverses the most recent entry (last-in-first-out, so the log and the traits never
drift out of sync). `validate_xp` (in engine.validate) audits the result.

Not pure — like lifecycle, these are state transitions. Legality that needs the
rules (Charm prerequisites, spell-circle access, Combo composition) is delegated to
engine.validate; the trait caps live here.
"""

from __future__ import annotations

from typing import Optional

from ..models.character import (
    Array, ArtSpecialty, BeastmanGiftPurchase, Character, CollegeRating, Combo, CraftRating,
    FetterEntry, FormulaEntry, MeritFlawPurchase, OxBodyPurchase, PassionEntry, PathRating,
    RitualEntry, ScienceRating, Specialty, SubmodulePurchase, ThaumaturgyState, XpEntry)
from ..models.rules import AbilityName, AttributeName, Orientation, RuleSet, VirtueName
from . import costs, derive, elder, merits, paths, validate

# Conventional maxima for raises. The 1-5 dot cap is the universal trait cap used
# throughout chargen; Willpower's permanent maximum is 10.
#
# It is a FLOOR under the elder ceilings rather than the last word: age lifts Essence
# past it and Essence lifts Abilities and Attributes past it (Player's Guide pp.258-259).
# Every such raise asks engine.elder — the constant itself never moves.
_DOT_MAX = 5
_WILLPOWER_MAX = 10

# "You can only have 3 specialties per ability" (human, rules authority, 2026-07-31).
# Counts ROWS, not distinct names — two Swords and one Parrying fills Melee.
SPECIALTIES_PER_ABILITY = 3


def specialty_cap(ruleset: RuleSet, character: Character, ability: AbilityName) -> int:
    """Specialty-row cap for one Ability. The Mountain Folk may have up to five
    Specialties in any Craft (CH6 p.230: "Jadeborn can have up to five Specialties in
    any Craft, but they cannot purchase the same specialty more than three times");
    every other Ability of every splat caps at three (the 2026-07-31 ruling)."""
    if ability == AbilityName.CRAFT and ruleset.exalt_for(character.exalt_type).id == "Mountain-Folk":
        return 5
    return SPECIALTIES_PER_ABILITY


def specialty_count(character: Character, ability: AbilityName) -> int:
    """How many specialty rows this Ability holds. Duplicated names each count: taking
    the same specialty twice is how a specialty stacks, since it has no rating to
    raise."""
    return sum(1 for s in character.specialties if s.ability == ability)


class AdvancementError(ValueError):
    """An illegal or unaffordable advance. The UI surfaces the message."""


# --------------------------------------------------------------------------- #
# XP accounting
# --------------------------------------------------------------------------- #

def xp_spent(character: Character) -> int:
    """Total XP committed across the log."""
    return sum(entry.cost for entry in character.xp_log)


def xp_available(character: Character) -> int:
    """Unspent XP: earned minus the log total. Goes NEGATIVE when a Merit change was
    taken on credit (see `xp_debt`) or after a hand-edit."""
    return character.xp_earned - xp_spent(character)


def xp_debt(character: Character) -> int:
    """Outstanding balance owed on a Merit change the character could not afford —
    Player's Guide p.17: "she pays whatever she has available and must allocate all
    further experience to the remaining balance until it is paid in full."

    DERIVED, not stored, and that is load-bearing. An earlier cut stored the balance
    and paid it down inside `add_xp`, which silently destroyed experience: the log
    recorded only the part that was affordable, so the rest was never counted as
    spent at all. Logging the FULL cost and letting `xp_available` go negative makes
    the debt self-evident, self-clearing as XP is earned, and impossible to lose."""
    return max(0, -xp_available(character))


def add_xp(character: Character, amount: int) -> None:
    """Adjust earned XP by `amount` (negative to correct an over-grant). Earned
    never drops below zero. Any outstanding debt clears automatically, because it is
    derived from the same two numbers."""
    character.xp_earned = max(0, character.xp_earned + amount)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

def _ensure_locked(character: Character) -> None:
    if not character.chargen_locked:
        raise AdvancementError("Lock chargen before spending XP.")


def _commit(character: Character, target: str, detail: str,
            frm: int | None, to: int | None, cost: int) -> XpEntry:
    """Affordability gate + append the log row. Call only after the trait change is
    decided (cost computed) but it is fine to mutate before or after — nothing here
    touches traits."""
    if cost > xp_available(character):
        raise AdvancementError(
            f"Costs {cost} XP; only {xp_available(character)} available.")
    entry = XpEntry(target=target, detail=detail, from_rating=frm, to_rating=to, cost=cost)
    character.xp_log.append(entry)
    return entry


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
    # wrong number and the ledger records a reduction that never happened. Same class
    # as the `raise_willpower` omission fixed earlier.
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


# --------------------------------------------------------------------------- #
# New traits
# --------------------------------------------------------------------------- #

def learn_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    _ensure_locked(character)
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if charm_id in character.charms:
        # A generic repeatable Charm (the Mountain Folk Essence Satiation Method and
        # Stone-Still Lungs, CH6 pp.245-246) may be learned once per purchase, up to
        # its trait cap. Every other Charm is single-pick and re-learning is an error.
        cap = validate._repeatable_purchase_cap(charm, character)
        if not cap or character.charms.count(charm_id) >= cap:
            raise AdvancementError(f"{charm.name} is already known.")
    # A Charm-Slot splat (Alchemical) does not learn Charms per-pick: it buys a Slot
    # (buy_charm_slot) or a Panoply Charm (learn_retainer_charm). Route callers there
    # so a Slot is never silently skipped.
    if validate.uses_charm_slots(ruleset, character):
        raise AdvancementError(
            f"{charm.name}: Alchemicals gain Charms by buying a Charm Slot or a "
            f"Panoply (retainer) Charm, not directly.")
    # A splat barred from Charms outright (mortals, core p.103) is refused first and
    # by name: the generic message below blames the Charm's splat, which reads as
    # nonsense for an `open_to_all` Charm that belongs to no one splat.
    #
    # The bar is not absolute — a Merit reopens part of it (Essence Mastery grants
    # Terrestrial Martial Arts, PG p.121), and chargen already honours that through
    # charm_matches_splat. Ask the same question here rather than the splat flag
    # alone, or a Charm a mortal may legally pick at creation becomes unbuyable the
    # moment they lock.
    if (not validate.charms_available(ruleset, character)
            and not validate.charm_matches_splat(character, charm, ruleset)):
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters cannot "
            f"purchase Charms (core p.103).")
    # A splat whose Essence pool requires unlocking (God-Blooded, PG p.66 — the pool
    # comes from the Awakened Essence Merit) may not purchase Charms until it is:
    # p.49, "Only God-Blooded with the Awakened Essence Merit may purchase or increase
    # magical Traits." The pool unlock IS the gate. Mirrored in validate for chargen.
    if (validate.pool_requires_unlocking(ruleset, character)
            and not merits.merits_and_flaws_calc(
                ruleset, character).essence_pool_unlocked):
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters must hold "
            f"the Awakened Essence Merit to purchase Charms (PG p.49).")
    # A Charm of the character's OWN splat that charm_learnable_by_splat still refuses
    # is a heritage bar (a Fae-Blooded holding a God-Blooded Arcanos, p.47 "do not use
    # Charms"), not a foreign Charm — "belongs to another Exalt type" would be actively
    # misleading for a God-Blooded, the same call the mortal branch above makes.
    if (validate.splat_of(charm) == character.exalt_type
            and not validate.charm_learnable_by_splat(ruleset, character, charm)):
        raise AdvancementError(
            f"{charm.name} belongs to the {character.exalt_type} splat but is barred "
            f"for this character.")
    # Another splat's Charm is buyable only by an Eclipse-style caste (p.127), and
    # then at the doubled price costs.charm_cost applies.
    if not validate.charm_learnable_by_splat(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} belongs to another Exalt type ({validate.splat_of(charm)}).")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    cost = costs.charm_cost(ruleset, character, charm)
    # p.90 crossover: an Eclipse/Moonshadow learning an Alchemical Charm gains a
    # General Charm Slot with it. Logged under a distinct target so undo gives the
    # Slot back too.
    grants_slot = validate.crossover_alchemical_charm(ruleset, character, charm)
    # A chargen pick banked by a Flaw (Weak Essence, p.41) pays for this Charm instead
    # of XP. Logged under its OWN target rather than as a zero-cost `charms` row: the
    # XP audit re-prices every entry from the table, so a 0 filed as `charms` would be
    # reported as a mismatch forever after. The distinct target is also what makes the
    # credits countable — see validate.withheld_charm_credits.
    target = "crossover_charms" if grants_slot else "charms"
    if not grants_slot and cost > 0:
        _granted, remaining = validate.withheld_charm_credits(ruleset, character)
        if remaining > 0:
            target, cost = validate.WITHHELD_CHARM_TARGET, 0
    entry = _commit(character, target, charm_id, None, None, cost)
    character.charms.append(charm_id)
    if grants_slot:
        g, _d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
        character.general_charm_slots = g + 1
    return entry


def learn_elemental_power(ruleset: RuleSet, character: Character, power_id: str) -> XpEntry:
    """Learn an elemental power in play (PG p.68): 14 XP (7 BP doubled). Simpler than
    learn_charm — no splat/foreign/withheld-credit machinery — because the catalogue
    belongs to exactly one origin and the cost table is flat."""
    _ensure_locked(character)
    power = ruleset.elemental_powers.get(power_id)
    if power is None:
        raise AdvancementError(f"Unknown elemental power {power_id!r}.")
    if power_id in character.elemental_powers:
        raise AdvancementError(f"{power.name} is already known.")
    if not validate.elemental_powers_available(ruleset, character):
        raise AdvancementError(
            "Only Elemental-origin God-Blooded may learn elemental powers (PG p.68).")
    if not validate.meets_elemental_power_requirements(ruleset, character, power):
        shortfalls = "; ".join(
            validate.elemental_power_shortfalls(ruleset, character, power))
        raise AdvancementError(f"{power.name}: requirements not met ({shortfalls}).")
    cost = costs.elemental_power_xp(ruleset, character, power)
    entry = _commit(character, "elemental_powers", power_id, None, None, cost)
    character.elemental_powers.append(power_id)
    return entry


def learn_spell(ruleset: RuleSet, character: Character, spell_id: str) -> XpEntry:
    _ensure_locked(character)
    spell = ruleset.spells.get(spell_id)
    if spell is None:
        raise AdvancementError(f"Unknown spell {spell_id!r}.")
    if spell_id in character.spells:
        raise AdvancementError(f"{spell.name} is already known.")
    # The same Merit gate as learn_charm: a God-Blooded may not buy spells without the
    # unlocked pool (p.49). The Spell itself is cross-splat, so the splat check has to
    # live here rather than on any spell.
    if (validate.pool_requires_unlocking(ruleset, character)
            and not merits.merits_and_flaws_calc(
                ruleset, character).essence_pool_unlocked):
        raise AdvancementError(
            f"{ruleset.exalt_for(character.exalt_type).label} characters must hold "
            f"the Awakened Essence Merit to purchase spells (PG p.49).")
    # Post-lock the chargen Solar-Circle bar lifts; only circle access is required.
    if not validate.meets_spell_requirements(ruleset, character, spell, chargen=False):
        raise AdvancementError(f"{spell.name}: no known Charm grants its Circle.")
    cost = costs.spell_cost(ruleset, character, spell)
    entry = _commit(character, "spells", spell_id, None, None, cost)
    character.spells.append(spell_id)
    return entry


# --------------------------------------------------------------------------- #
# Alchemical Charm-Slot economy (post-lock; Autochthonians p.64, p.89)
# --------------------------------------------------------------------------- #

def _require_slot_splat(ruleset: RuleSet, character: Character) -> None:
    if not validate.uses_charm_slots(ruleset, character):
        raise AdvancementError("Charm Slots are an Alchemical mechanic.")


def _installable_charm(ruleset: RuleSet, character: Character, charm_id: str):
    """Shared gate for a Charm the character is about to gain (Slot or Panoply): it
    exists, is not already owned (installed or on retainer), is learnable by the
    splat, and its requirements are met. Returns the Charm."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if charm_id in character.charms or charm_id in character.retainer_charms:
        raise AdvancementError(f"{charm.name} is already owned.")
    if not validate.charm_learnable_by_splat(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} belongs to another Exalt type ({validate.splat_of(charm)}).")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    return charm


def buy_charm_slot(ruleset: RuleSet, character: Character, *, dedicated: bool,
                   charm_id: str) -> XpEntry:
    """Buy one more Charm Slot (p.64): General (12) or Dedicated (10). The Slot comes
    with a free Charm of the player's choice that must fit the Slot — a Dedicated Slot
    holds only a Caste/Favored-Attribute Charm. The Charm is installed (added to
    `charms`); the Slot count is incremented."""
    _ensure_locked(character)
    _require_slot_splat(ruleset, character)
    charm = _installable_charm(ruleset, character, charm_id)
    if dedicated and not validate.charm_fits_dedicated_slot(ruleset, character, charm):
        raise AdvancementError(
            f"{charm.name} is not keyed to a Caste/Favored Attribute, so it cannot "
            f"fill a Dedicated Slot; buy a General Slot instead.")
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    cost = costs.charm_slot_cost(ruleset, character, dedicated=dedicated)
    kind = "dedicated" if dedicated else "general"
    frm = d if dedicated else g
    entry = _commit(character, f"charm_slots.{kind}", charm_id, frm, frm + 1, cost)
    if dedicated:
        character.dedicated_charm_slots = d + 1
    else:
        character.general_charm_slots = g + 1
    character.charms.append(charm_id)
    return entry


def upgrade_charm_slot(ruleset: RuleSet, character: Character) -> XpEntry:
    """Upgrade one Dedicated Charm Slot to a General Slot (p.64, 2 XP). Requires a
    Dedicated Slot to exist."""
    _ensure_locked(character)
    _require_slot_splat(ruleset, character)
    g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
    if d <= 0:
        raise AdvancementError("No Dedicated Charm Slot to upgrade.")
    cost = costs.charm_slot_upgrade_cost(ruleset, character)
    # Ratings left None: this swaps two counts, not a single-trait change, and a
    # to<from would be misread as a free reduction by the audit.
    entry = _commit(character, "charm_slot_upgrade", "", None, None, cost)
    character.dedicated_charm_slots = d - 1
    character.general_charm_slots = g + 1
    return entry


def learn_retainer_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    """Buy one Panoply (retainer) Charm WITHOUT a Slot. A native Alchemical pays the
    flat 6 XP (p.64); an Eclipse/Moonshadow may instead add an Alchemical Charm to their
    Panoply through the crossover at their caste's flat rate (p.90, 8) as a cheaper
    alternative to a Slot. Either way the Charm is owned but not installed."""
    _ensure_locked(character)
    native = validate.uses_charm_slots(ruleset, character)
    crossover = validate.crossover_panoply_xp(ruleset, character) is not None
    if not native and not crossover:
        raise AdvancementError(
            "Panoply Charms are an Alchemical mechanic (or the Eclipse/Moonshadow "
            "Alchemical crossover, p.90).")
    charm = _installable_charm(ruleset, character, charm_id)
    # A crossover Panoply holds Alchemical Charms specifically (p.90).
    if not native and not validate.splat_uses_charm_slots(ruleset, validate.splat_of(charm)):
        raise AdvancementError(
            f"{charm.name} is not an Alchemical Charm; only Alchemical Charms go on the "
            f"crossover Panoply.")
    cost = costs.retainer_charm_cost(ruleset, character)
    entry = _commit(character, "retainer_charms", charm_id, None, None, cost)
    character.retainer_charms.append(charm_id)
    return entry


def learn_submodule(ruleset: RuleSet, character: Character,
                    charm_id: str, key: str) -> XpEntry:
    """Buy an Alchemical submodule (p.89) post-lock for its `xp_cost`. The parent
    Charm must be known and the submodule's own Essence/Attribute minimums met."""
    _ensure_locked(character)
    definition = validate.submodule_def(ruleset, charm_id, key)
    if definition is None:
        raise AdvancementError(f"No submodule {key!r} on Charm {charm_id!r}.")
    if charm_id not in character.charms:
        raise AdvancementError(f"Charm {charm_id!r} is not known; install it first.")
    if any(s.charm_id == charm_id and s.key == key for s in character.submodules):
        raise AdvancementError(f"Submodule {definition.name} is already owned.")
    if character.essence_rating < definition.min_essence:
        raise AdvancementError(
            f"{definition.name} requires Essence {definition.min_essence}.")
    if definition.min_attribute:
        attr = AttributeName(definition.min_attribute)
        if character.attributes.get(attr, 0) < definition.min_attribute_rating:
            raise AdvancementError(
                f"{definition.name} requires {definition.min_attribute} "
                f"{definition.min_attribute_rating}.")
    entry = _commit(character, "submodules", f"{charm_id}:{key}", None, None,
                    definition.xp_cost)
    character.submodules.append(SubmodulePurchase(charm_id=charm_id, key=key))
    return entry


def add_combo(ruleset: RuleSet, character: Character, name: str,
              charm_ids: list[str]) -> XpEntry:
    _ensure_locked(character)
    combo = Combo(name=name, charm_ids=list(charm_ids))
    problems = [i for i in validate.combo_issues(ruleset, character, combo)
                if i.severity == "error"]
    if problems:
        raise AdvancementError(problems[0].message)
    cost = costs.combo_cost(ruleset, charm_ids)
    entry = _commit(character, "combos", name, None, None, cost)
    character.combos.append(combo)
    return entry


def add_array(ruleset: RuleSet, character: Character, name: str,
              charm_ids: list[str]) -> XpEntry:
    """Buy an Alchemical Array post-lock (p.89) for the sum of its member Charms'
    minimum Attribute ratings. Legality is `validate.array_issues` plus the two
    cross-Array rules `validate_arrays` adds — only a Charm-Slot splat may build
    Arrays, and a Charm may sit in only one — checked here against the Arrays the
    character already holds so a post-lock purchase cannot reuse a linked Charm."""
    _ensure_locked(character)
    if not validate.uses_charm_slots(ruleset, character):
        raise AdvancementError(
            "Only Alchemical Exalted build Arrays (Eclipse and Moonshadow Caste "
            "may not, p.90).")
    array = Array(name=name, charm_ids=list(charm_ids))
    problems = [i for i in validate.array_issues(ruleset, character, array)
                if i.severity == "error"]
    if problems:
        raise AdvancementError(problems[0].message)
    linked = {cid for existing in character.arrays for cid in existing.charm_ids}
    reused = [cid for cid in charm_ids if cid in linked]
    if reused:
        charm = ruleset.charms.get(reused[0])
        raise AdvancementError(
            f"{charm.name if charm else reused[0]} is already linked into another "
            "Array; a Charm may join only one Array unless purchased again.")
    cost = costs.array_cost(ruleset, charm_ids)
    entry = _commit(character, "arrays", name, None, None, cost)
    character.arrays.append(array)
    return entry


def learn_ox_body(ruleset: RuleSet, character: Character, variant_key: str,
                  *, dedicated: bool = False) -> XpEntry:
    """Buy one more Ox-Body Technique with the chosen health-level package (post-lock).
    Gated by the splat's once-per-dot-of-cap-trait limit (Endurance, Stamina for Lunar,
    Essence for Alchemical). Priced as a normal new Charm — EXCEPT for a Charm-Slot
    splat (Alchemical), where every purchase installs the Charm in its own Slot (user
    ruling), so it costs a Slot (General 12 / Dedicated 10) and raises the Slot count.
    `dedicated` chooses the Slot kind and is ignored by non-Slot splats."""
    _ensure_locked(character)
    charm = validate.ox_body_charm(ruleset, character)
    if charm is None:
        raise AdvancementError("Ox-Body Technique is not in the RuleSet.")
    variant = next((v for v in charm.variants if v.key == variant_key), None)
    if variant is None:
        raise AdvancementError(f"Unknown Ox-Body package {variant_key!r}.")
    if character.essence_rating < charm.min_essence:
        raise AdvancementError(
            f"Ox-Body Technique requires Essence {charm.min_essence}.")
    cap = validate.ox_body_cap(ruleset, character)
    if len(character.ox_body) >= cap:
        raise AdvancementError(
            f"Ox-Body Technique may be bought at most once per dot of "
            f"{validate.repeatable_cap_trait_name(charm)} ({cap}).")
    purchase = OxBodyPurchase(variant=variant_key, health_levels=list(variant.health_levels))
    if validate.uses_charm_slots(ruleset, character):
        if dedicated and not validate.charm_fits_dedicated_slot(ruleset, character, charm):
            raise AdvancementError(
                f"{charm.name} is not keyed to a Caste/Favored Attribute; it cannot "
                f"fill a Dedicated Slot.")
        g, d, _bg, _bd = validate.charm_slot_counts(ruleset, character)
        cost = costs.charm_slot_cost(ruleset, character, dedicated=dedicated)
        kind = "dedicated" if dedicated else "general"
        frm = d if dedicated else g
        entry = _commit(character, f"ox_body_slot.{kind}", variant_key, frm, frm + 1, cost)
        if dedicated:
            character.dedicated_charm_slots = d + 1
        else:
            character.general_charm_slots = g + 1
        character.ox_body.append(purchase)
        return entry
    cost = costs.ox_body_cost(ruleset, character)
    entry = _commit(character, "ox_body", variant_key, None, None, cost)
    character.ox_body.append(purchase)
    return entry


def learn_martial_arts_charm(ruleset: RuleSet, character: Character, charm_id: str) -> XpEntry:
    """Learn a Martial Arts Charm through Perfected Lotus Matrix (p.100): a Terrestrial/
    Celestial style, learned "as any other Celestial Exalt", for the flat MA rate (11).
    Stored inside the Matrix — it uses NO Charm Slot — so it is added to `charms` but
    the Slot accounting skips it (validate.charm_occupies_slot)."""
    _ensure_locked(character)
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        raise AdvancementError(f"Unknown Charm {charm_id!r}.")
    if not validate.is_martial_arts_charm(charm):
        raise AdvancementError(f"{charm.name} is not a Martial Arts Charm.")
    if not validate.has_perfected_lotus_matrix(character):
        raise AdvancementError(
            "Learning Martial Arts Charms requires Perfected Lotus Matrix installed (p.100).")
    if charm_id in character.charms:
        raise AdvancementError(f"{charm.name} is already known.")
    if not validate.charm_matches_splat(character, charm, ruleset):
        raise AdvancementError(
            f"{charm.name} is not a Terrestrial/Celestial style available through "
            f"Perfected Lotus Matrix.")
    if not validate.meets_charm_requirements(ruleset, character, charm):
        raise AdvancementError(f"{charm.name}: requirements not met.")
    cost = costs.martial_arts_charm_cost(ruleset, character)
    entry = _commit(character, "martial_arts", charm_id, None, None, cost)
    character.charms.append(charm_id)
    return entry


def learn_gift(ruleset: RuleSet, character: Character, gift_keys: list[str]) -> XpEntry:
    """Buy one more purchase of the Gift-granting Charm (Deadly Beastman
    Transformation, p.124-127) with the chosen Gift(s), post-lock. Gated by the
    once-per-point-of-Essence cap; `gift_keys` must match what this purchase
    grants (2 on the first purchase, 1 on each after); each Gift's own
    prerequisites (among the character's already-known Gifts and the rest of
    this same purchase, taken as one atomic set — the rulebook applies a
    purchase's Gifts together, p.124) and repeat cap must hold. Priced as a
    normal new Charm regardless of how many Gifts are chosen."""
    _ensure_locked(character)
    charm = validate.gift_charm(ruleset, character)
    if charm is None:
        raise AdvancementError("Deadly Beastman Transformation is not in the RuleSet.")
    if character.essence_rating < charm.min_essence:
        raise AdvancementError(f"{charm.name} requires Essence {charm.min_essence}.")
    cap = validate.gift_purchase_cap(ruleset, character)
    if len(character.beastman_gifts) >= cap:
        raise AdvancementError(
            f"{charm.name} may be bought at most once per point of Essence ({cap}).")
    expected = validate.gifts_per_purchase(charm, len(character.beastman_gifts))
    if len(gift_keys) != expected:
        raise AdvancementError(
            f"This purchase of {charm.name} grants {expected} Gift(s); "
            f"{len(gift_keys)} were chosen.")
    variants_by_key = {v.key: v for v in charm.variants}
    known = validate.known_gift_keys(character)
    available = set(known) | set(gift_keys)
    counts: dict[str, int] = {}
    for key in known:
        counts[key] = counts.get(key, 0) + 1
    for key in gift_keys:
        variant = variants_by_key.get(key)
        if variant is None:
            raise AdvancementError(f"Unknown Gift {key!r}.")
        if variant.prerequisites and not all(
                any(pid in available for pid in group) for group in variant.prerequisites):
            raise AdvancementError(f"Gift {variant.label!r} needs its prerequisite Gift first.")
        counts[key] = counts.get(key, 0) + 1
        if counts[key] > variant.max_purchases:
            raise AdvancementError(
                f"Gift {variant.label!r} may be taken at most "
                f"{variant.max_purchases} time(s).")
    cost = costs.gift_cost(ruleset, character)
    entry = _commit(character, "beastman_gifts", "|".join(gift_keys), None, None, cost)
    character.beastman_gifts.append(BeastmanGiftPurchase(gifts=list(gift_keys)))
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
    four Sciences currently stop at 5 — Alchemy's printed six-dot rung turned out to be
    a typo for five (human, 2026-07-30) — so this reads as a plain 5 today. Kept
    per-Science because the ceiling is rules data, not an engine constant.
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


# --------------------------------------------------------------------------- #
# Undo (LIFO)
# --------------------------------------------------------------------------- #

def undo_last(ruleset: RuleSet, character: Character) -> XpEntry:
    """Reverse the most recent XP purchase: undo its trait change and drop the log
    row. Last-in-first-out so prerequisites and Combo members are always removed
    after the things that depend on them."""
    if not character.xp_log:
        raise AdvancementError("Nothing to undo.")
    entry = character.xp_log[-1]
    domain, _, key = entry.target.partition(".")

    if domain == "attributes":
        character.attributes[AttributeName(key)] = entry.from_rating
    elif domain == "abilities":
        character.abilities[AbilityName(key)] = entry.from_rating
    elif domain == "crafts":
        for i in range(len(character.crafts) - 1, -1, -1):
            if character.crafts[i].focus == entry.detail:
                if entry.from_rating and entry.from_rating > 0:
                    character.crafts[i].rating = entry.from_rating
                else:                       # was a freshly-learned craft -> remove it
                    del character.crafts[i]
                break
    elif domain == "colleges":
        for i in range(len(character.colleges) - 1, -1, -1):
            if character.colleges[i].college_id == entry.detail:
                if entry.from_rating and entry.from_rating > 0:
                    character.colleges[i].rating = entry.from_rating
                else:                       # was a freshly-learned college -> remove it
                    del character.colleges[i]
                break
    elif domain == "virtues":
        character.virtues[VirtueName(key)] = entry.from_rating
    elif domain == "willpower":
        # Reverse exactly the delta this row applied: a raise (+1) or a reduction (-1).
        character.willpower_purchased -= (entry.to_rating - entry.from_rating)
    elif domain == "essence":
        character.essence_rating = entry.from_rating
    elif domain == validate.PERMANENT_RESONANCE_TARGET:
        character.limit_permanent = entry.from_rating
    elif domain == validate.WITHHELD_CHARM_TARGET:
        # Removing the row restores the credit, since credits are counted from the log.
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "fetters":
        for f in character.fetters:
            if f.name == entry.detail:
                f.rating = entry.from_rating
                break
    elif domain == "new_fetters":
        character.fetters = [f for f in character.fetters if f.name != entry.detail]
    elif domain == "shift_fetters":
        # `detail` is "old>new"; a shift changed only the NAME, so undo renames back.
        was, _, now = entry.detail.partition(">")
        for f in character.fetters:
            if f.name == now:
                f.name = was
                break
    elif domain == "shift_passions":
        # Move the dot back. The destination may have been created by the shift, in
        # which case undoing it removes the row again rather than leaving a 0-dot one.
        was, _, now = entry.detail.partition(">")
        dst = next((x for x in character.passions if x.name == now), None)
        src = next((x for x in character.passions if x.name == was), None)
        if dst is not None:
            dst.rating -= 1
            if src is None:
                character.passions.append(
                    PassionEntry(name=was, virtue=dst.virtue, rating=1))
            else:
                src.rating += 1
            if dst.rating == 0:
                character.passions.remove(dst)
    elif domain == "charms":
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "elemental_powers":
        if entry.detail in character.elemental_powers:
            character.elemental_powers.remove(entry.detail)
    elif domain == "crossover_charms":
        # An Eclipse/Moonshadow Alchemical Charm: drop it AND the General Slot it granted.
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
        character.general_charm_slots = (character.general_charm_slots or 0) - 1
    elif domain == "charm_slots":
        # Reverse a bought Slot: uninstall its bundled Charm and drop the Slot count.
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
        if key == "dedicated":
            character.dedicated_charm_slots = entry.from_rating
        else:
            character.general_charm_slots = entry.from_rating
    elif domain == "charm_slot_upgrade":
        # Reverse a Dedicated->General upgrade: give the Dedicated Slot back.
        character.dedicated_charm_slots = (character.dedicated_charm_slots or 0) + 1
        character.general_charm_slots = (character.general_charm_slots or 0) - 1
    elif domain == "retainer_charms":
        if entry.detail in character.retainer_charms:
            character.retainer_charms.remove(entry.detail)
    elif domain == "spells":
        if entry.detail in character.spells:
            character.spells.remove(entry.detail)
    elif domain == "combos":
        for i in range(len(character.combos) - 1, -1, -1):
            if character.combos[i].name == entry.detail:
                del character.combos[i]
                break
    elif domain == "arrays":
        for i in range(len(character.arrays) - 1, -1, -1):
            if character.arrays[i].name == entry.detail:
                del character.arrays[i]
                break
    elif domain == "specialties":
        ab, _, spec_name = entry.detail.partition(":")
        for i in range(len(character.specialties) - 1, -1, -1):
            s = character.specialties[i]
            if s.ability.value == ab and s.name == spec_name:
                del character.specialties[i]
                break
    elif domain == "ox_body":
        # LIFO: drop the most recent purchase of the undone variant.
        for i in range(len(character.ox_body) - 1, -1, -1):
            if character.ox_body[i].variant == entry.detail:
                del character.ox_body[i]
                break
    elif domain == "ox_body_slot":
        # An Alchemical Ox-Body purchase: drop the purchase AND give back its Slot.
        for i in range(len(character.ox_body) - 1, -1, -1):
            if character.ox_body[i].variant == entry.detail:
                del character.ox_body[i]
                break
        if key == "dedicated":
            character.dedicated_charm_slots = entry.from_rating
        else:
            character.general_charm_slots = entry.from_rating
    elif domain == "martial_arts":
        if entry.detail in character.charms:
            character.charms.remove(entry.detail)
    elif domain == "merits":
        if entry.removed_purchase is not None:
            # A DROP reversed: re-add the exact purchase the row removed. LIFO — no
            # later row can exist, so appending restores the held state as it was.
            character.merits_flaws.append(entry.removed_purchase)
        elif entry.detail.startswith("-"):
            # A drop logged before the row carried `removed_purchase` (an older save):
            # the removed purchase cannot be reconstructed. Refuse rather than pop the
            # row and strand the Merit's XP.
            raise AdvancementError(
                "Cannot undo a Merit/Flaw removal from an older save.")
        else:
            # A buy or gain reversed: drop the LAST matching purchase. LIFO — a
            # repeatable Merit held twice must undo one copy, and the logged one is
            # the newest.
            for i in range(len(character.merits_flaws) - 1, -1, -1):
                if character.merits_flaws[i].merit_id == entry.detail:
                    del character.merits_flaws[i]
                    break
    elif domain == "beastman_gifts":
        # LIFO: drop the most recent purchase with this exact Gift set.
        for i in range(len(character.beastman_gifts) - 1, -1, -1):
            if "|".join(character.beastman_gifts[i].gifts) == entry.detail:
                del character.beastman_gifts[i]
                break
    elif domain == "submodules":
        for i in range(len(character.submodules) - 1, -1, -1):
            s = character.submodules[i]
            if f"{s.charm_id}:{s.key}" == entry.detail:
                del character.submodules[i]
                break
    elif domain.startswith("thaum_") and character.thaumaturgy is not None:
        _undo_thaum(character.thaumaturgy, domain, key, entry.detail, entry.from_rating)

    character.xp_log.pop()
    return entry


def _undo_thaum(state: ThaumaturgyState, domain: str, key: str, detail: str,
                entry_from: int | None = None) -> None:
    """Reverse one thaumaturgy purchase. Split out because the five kinds live on five
    lists; LIFO ordering is `undo_last`'s job, so this only has to find and drop."""
    if domain == "thaum_arts":
        if detail in state.arts:
            state.arts.remove(detail)
    elif domain == "thaum_specialties":
        art_id, _, name = detail.partition(":")
        for i in range(len(state.art_specialties) - 1, -1, -1):
            s = state.art_specialties[i]
            if s.art_id == art_id and s.name == name:
                del state.art_specialties[i]
                break
    elif domain == "thaum_sciences":
        for i in range(len(state.sciences) - 1, -1, -1):
            if state.sciences[i].science_id == detail:
                if entry_from and entry_from > 0:
                    state.sciences[i].rating = entry_from
                else:                       # was a freshly-learned Science -> remove it
                    del state.sciences[i]
                break
    elif domain == "thaum_rituals":
        for i in range(len(state.rituals) - 1, -1, -1):
            if (state.rituals[i].ritual_id or state.rituals[i].name) == detail:
                del state.rituals[i]
                break
    elif domain == "thaum_formulas":
        for i in range(len(state.formulas) - 1, -1, -1):
            if (state.formulas[i].formula_id or state.formulas[i].name) == detail:
                del state.formulas[i]
                break
    elif domain == "thaum_orientations":
        # detail is "<key>:<Orientation>"; rsplit because a custom name may contain ':'.
        entry_key, _, region = detail.rpartition(":")
        entries = state.rituals if key == "ritual" else state.formulas
        for e in entries:
            if ((e.ritual_id if key == "ritual" else e.formula_id) or e.name) != entry_key:
                continue
            orientation = Orientation(region)
            # Never strip the last orientation: an entry with none is not a state the
            # model allows, and the base purchase paid for one.
            if orientation in e.orientations and len(e.orientations) > 1:
                e.orientations.remove(orientation)
            break


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #

def _expected_cost(ruleset: RuleSet, character: Character, entry: XpEntry) -> int | None:
    """Recompute what `entry` should have cost from the XP table, or None when it
    cannot be priced (e.g. an id no longer in the rule set)."""
    domain, _, key = entry.target.partition(".")
    frm = entry.from_rating
    # Permanent Resonance is priced per DIRECTION and must be tested before the generic
    # reduction rule below, which would otherwise make the five-point shed free.
    if domain == validate.PERMANENT_RESONANCE_TARGET:
        if frm is not None and entry.to_rating is not None and entry.to_rating < frm:
            return merits.PERMANENT_RESONANCE_SHED_XP      # shed: five XP and a Harrowing
        return 0                                          # gained: inflicted, not bought
    # A permanent reduction (curse / Charm cost) is free and refunds no XP.
    if frm is not None and entry.to_rating is not None and entry.to_rating < frm:
        return 0
    if domain == "attributes" and frm is not None:
        attr = AttributeName(key) if key else None
        return costs.attribute_step(ruleset, character, frm, attr)
    if domain == "abilities" and frm is not None:
        return costs.ability_step(ruleset, character, AbilityName(key), frm)
    if domain == "crafts" and frm is not None:
        return costs.ability_step(ruleset, character, AbilityName.CRAFT, frm)
    if domain == "colleges" and frm is not None:
        return (costs.college_new_cost(ruleset, character) if frm <= 0
                else costs.college_step(ruleset, character, frm))
    if domain == "virtues" and frm is not None:
        return costs.virtue_step(ruleset, character, frm,
                                 VirtueName(key) if key else None)
    if domain == "willpower" and frm is not None:
        return costs.willpower_step(ruleset, character, frm)
    if domain == "essence" and frm is not None:
        return costs.essence_step(ruleset, character, frm)
    if domain == validate.WITHHELD_CHARM_TARGET:
        # Paid with a banked chargen pick, not XP. Free by rule, so the table rate must
        # not be re-applied here.
        return 0
    if domain in ("charms", "crossover_charms"):
        charm = ruleset.charms.get(entry.detail)
        return costs.charm_cost(ruleset, character, charm) if charm else None
    if domain == "elemental_powers":
        power = ruleset.elemental_powers.get(entry.detail)
        return costs.elemental_power_xp(ruleset, character, power) if power else None
    if domain == "spells":
        spell = ruleset.spells.get(entry.detail)
        return costs.spell_cost(ruleset, character, spell) if spell else None
    if domain == "charm_slots":
        return costs.charm_slot_cost(ruleset, character, dedicated=(key == "dedicated"))
    if domain == "charm_slot_upgrade":
        return costs.charm_slot_upgrade_cost(ruleset, character)
    if domain == "retainer_charms":
        return costs.retainer_charm_cost(ruleset, character)
    if domain == "specialties":
        return costs.specialty_cost(ruleset, character)
    if domain == "combos":
        combo = next((c for c in character.combos if c.name == entry.detail), None)
        return costs.combo_cost(ruleset, combo.charm_ids) if combo else None
    if domain == "arrays":
        array = next((a for a in character.arrays if a.name == entry.detail), None)
        return costs.array_cost(ruleset, array.charm_ids) if array else None
    if domain == "ox_body":
        return costs.ox_body_cost(ruleset, character)
    if domain == "ox_body_slot":
        return costs.charm_slot_cost(ruleset, character, dedicated=(key == "dedicated"))
    if domain == "martial_arts":
        return costs.martial_arts_charm_cost(ruleset, character)
    if domain == "beastman_gifts":
        return costs.gift_cost(ruleset, character)
    if domain == "submodules":
        cid, _, k = entry.detail.partition(":")
        definition = validate.submodule_def(ruleset, cid, k)
        return definition.xp_cost if definition is not None else None
    if domain == "thaum_arts":
        return costs.thaum_art_xp(ruleset, character)
    if domain == "thaum_specialties":
        # `narrowed` halves the price and cannot change after purchase, so reading it
        # back off the character re-prices the row exactly.
        art_id, _, name = entry.detail.partition(":")
        state = validate.thaum_state(character)
        spec = next((s for s in state.art_specialties
                     if s.art_id == art_id and s.name == name), None)
        return costs.thaum_specialty_xp(ruleset, character,
                                        narrowed=bool(spec and spec.narrowed))
    if domain == "thaum_sciences" and frm is not None:
        return costs.thaum_science_step_xp(ruleset, character, frm)
    if domain == "thaum_rituals" and entry.to_rating is not None:
        # Level rides on the log row, so a custom ritual (absent from the catalogue)
        # and a catalogue one re-price identically. One orientation per row by
        # construction — extra versions are their own rows.
        return costs.thaum_ritual_xp(ruleset, character, entry.to_rating, 1)
    if domain == "thaum_formulas":
        return costs.thaum_formula_xp(ruleset, character, 1)
    if domain == "thaum_orientations":
        return costs.thaum_orientation_xp(ruleset, character)
    return None


def validate_xp(ruleset: RuleSet, character: Character) -> list[validate.Issue]:
    """Audit the XP log of a locked character: no overspend, and each row priced at
    the table rate. Pure (returns Issues; mutates nothing). Empty for an unlocked
    character — XP is a post-lock concern."""
    if not character.chargen_locked or character.chargen_snapshot is None:
        return []
    issues: list[validate.Issue] = []
    spent = xp_spent(character)
    if spent > character.xp_earned:
        issues.append(validate.Issue(
            code="xp-overspent",
            message=f"Spent {spent} XP but only {character.xp_earned} earned.",
        ))
    for entry in character.xp_log:
        expected = _expected_cost(ruleset, character, entry)
        if expected is not None and expected != entry.cost:
            issues.append(validate.Issue(
                code="xp-cost-mismatch", where=entry.target,
                message=(f"{entry.target}: logged {entry.cost} XP, "
                         f"table rate is {expected}."),
            ))
    issues.append(validate.Issue(
        code="xp-summary", severity="info",
        message=f"{spent} of {character.xp_earned} XP spent "
                f"({xp_available(character)} available).",
    ))
    return issues


def mf_change_method(character: Character) -> str:
    """Which Player's Guide p.17 method governs post-creation M&F changes for this
    character's table. Only "experience" moves any XP."""
    return (character.house_rules.mf_change_method
            if character.house_rules is not None else "experience")


def merit_change_xp(ruleset: RuleSet, character: Character, merit, tier: str = "",
                    *, taken_as: str = "", points: int = 0) -> int:
    """XP a post-creation M&F change costs (positive) or pays (negative), under the
    experience method: "If a character loses a Merit or gains a Flaw, she receives a
    number of experience points equal to twice its bonus point value. If a character
    gains a Merit or loses a Flaw, she must pay a like number" (PG p.17).

    Returns 0 under the other two methods, which "do not cost or reward players after
    character creation"."""
    if mf_change_method(character) != "experience":
        return 0
    return costs.merit_cost(ruleset, character, merit, tier,
                            taken_as=taken_as, points=points)


def _pay_or_owe(character: Character, target: str, detail: str, cost: int) -> XpEntry:
    """Commit a Merit change, allowing it to go into debt rather than refusing.

    Distinct from `_commit`, which REFUSES an unaffordable purchase. A Merit change is
    not always the player's choice — a Flaw healed by someone else's Charm charges her
    whether or not she can pay — so p.17 provides for a running balance instead. The
    full cost is logged; `xp_available` goes negative and `xp_debt` reports it.
    """
    entry = XpEntry(target=target, detail=detail, from_rating=None, to_rating=None,
                    cost=cost)
    character.xp_log.append(entry)
    return entry


def buy_merit(ruleset: RuleSet, character: Character, merit_id: str,
              *, tier: str = "", detail: str = "", arena: str = "",
              taken_as: str = "", points: int = 0) -> XpEntry:
    """Gain a Merit after creation. Under the experience method this costs twice its
    bonus-point value (PG p.17, and the same rate the mortal table gives on p.115);
    under the other two methods it costs nothing, because they "do not cost or reward
    players after character creation".

    Flaws are not bought — a Flaw is GAINED (see `gain_flaw`), which pays the
    character rather than charging her.

    A `kind: "either"` entry (Mutation, Favor, Eternal Vow) may come through here, but
    only when `taken_as="merit"` records that side as the player's choice: the side is
    what decides whether this charges or pays, so it may never be defaulted here.
    """
    _ensure_locked(character)
    definition = ruleset.merits_flaws.get(merit_id)
    if definition is None:
        raise AdvancementError(f"Unknown Merit {merit_id!r}.")
    if definition.kind == "either" and taken_as != "merit":
        raise AdvancementError(
            f"{definition.name} is printed as a Merit OR a Flaw "
            f"{definition.cost_note}; say which side is being taken.")
    if definition.kind == "flaw":
        raise AdvancementError(
            f"{definition.name} is a Flaw; gaining a Flaw pays the character "
            f"(gain_flaw), it is not bought.")
    held = [p.merit_id for p in character.merits_flaws]
    if merit_id in held and not definition.repeatable_by:
        raise AdvancementError(f"{definition.name} is already held.")
    # An origin-keyed repeat cap (Virtue Attunement: once for a commoner Fae-Blooded,
    # twice for a noble, PG p.74) must hold on the buy path too, or a Commoner could
    # buy a second copy with XP past what validate refuses.
    if character.origin in definition.max_purchases_by_origin:
        limit = definition.max_purchases_by_origin[character.origin]
        if held.count(merit_id) >= limit:
            raise AdvancementError(
                f"{definition.name} may be taken at most {limit} time(s) "
                f"as a {character.origin}.")
    for pid in definition.prerequisites:
        if pid not in held:
            name = ruleset.merits_flaws[pid].name if pid in ruleset.merits_flaws else pid
            raise AdvancementError(f"{definition.name} requires {name}.")
    if definition.cost_options and tier not in definition.cost_options:
        raise AdvancementError(
            f"{definition.name} needs one of {sorted(definition.cost_options)}.")

    cost = merit_change_xp(ruleset, character, definition, tier,
                           taken_as=taken_as, points=points)
    entry = _pay_or_owe(character, "merits", merit_id, cost)
    character.merits_flaws.append(
        MeritFlawPurchase(merit_id=merit_id, tier=tier, detail=detail, arena=arena,
                          points=points,
                          taken_as=taken_as if definition.kind == "either" else ""))
    return entry


def gain_flaw(ruleset: RuleSet, character: Character, merit_id: str,
              *, tier: str = "", detail: str = "", arena: str = "",
              taken_as: str = "", points: int = 0) -> XpEntry:
    """Take on a Flaw in play. Under the experience method this PAYS the character
    twice its point value (a negative-cost log row); under the others it pays nothing.

    The p.16 cap is deliberately NOT applied here — "characters with more than 10
    points of Flaws receive no experience for the excess" is a total across all Flaws,
    so it is enforced by engine.merits against the whole sheet, not per purchase.

    As with `buy_merit`, a `kind: "either"` entry is admitted only when `taken_as`
    records the choice explicitly — here, `"flaw"`.
    """
    _ensure_locked(character)
    definition = ruleset.merits_flaws.get(merit_id)
    if definition is None:
        raise AdvancementError(f"Unknown Flaw {merit_id!r}.")
    if definition.kind == "either" and taken_as != "flaw":
        raise AdvancementError(
            f"{definition.name} is printed as a Merit OR a Flaw "
            f"{definition.cost_note}; say which side is being taken.")
    if definition.kind == "merit":
        raise AdvancementError(f"{definition.name} is a Merit; buy it instead.")
    if definition.cost_options and tier not in definition.cost_options:
        raise AdvancementError(
            f"{definition.name} needs one of {sorted(definition.cost_options)}.")

    award = merit_change_xp(ruleset, character, definition, tier,
                            taken_as=taken_as, points=points)
    # "Characters with more than 10 points of Flaws receive no experience for the
    # excess" (PG p.17) — the same ceiling as chargen. Measured against the Flaws
    # ALREADY held, so a Flaw that straddles the cap pays for its legal part only.
    if award:
        already = merits.flaw_points(ruleset, character)
        room = max(0, merits.FLAW_POINT_CAP - already)
        # The point value being measured against the cap has to be the one this
        # purchase actually carries — its side, its tier, its agreed points — or a
        # two-sided or variable-cost Flaw is capped against a number it never had.
        value = validate.merit_points(
            definition,
            MeritFlawPurchase(merit_id=merit_id, tier=tier, taken_as=taken_as,
                              points=points),
            character.exalt_type, character.caste)
        if value > room:
            award = award * room // max(1, value)
    entry = _commit_award(character, "merits", merit_id, -award)
    character.merits_flaws.append(
        MeritFlawPurchase(merit_id=merit_id, tier=tier, detail=detail, arena=arena,
                          points=points,
                          taken_as=taken_as if definition.kind == "either" else ""))
    return entry


def drop_merit(ruleset: RuleSet, character: Character, index: int) -> XpEntry | None:
    """Lose a Merit, or buy off a Flaw. Mirrors the two above: losing a MERIT pays the
    character twice its value, losing a FLAW charges it (PG p.17). Returns None for a
    player-authored Custom row, whose removal is a plain delete with no XP value."""
    _ensure_locked(character)
    if not 0 <= index < len(character.merits_flaws):
        raise AdvancementError(f"No Merit at index {index}.")
    purchase = character.merits_flaws[index]
    # A player-authored "Custom" row (2026-08-10): display-only, no mechanical
    # effect and no XP value — dropping it is a plain removal, not a transaction.
    # The discriminator is the EMPTY merit_id (never edited by the name input), not
    # custom_name's truthiness — a blanked name must still drop as custom.
    #
    # Returns None and logs NOTHING: there is no XP to refund, and `undo_last` has no
    # merits branch (pre-existing — real drops share the gap), so a cost-0 ledger row
    # would sit on the LIFO stack and silently burn the player's NEXT undo on a no-op
    # instead of reversing their last real purchase. A plain removal has no undoable
    # side effect, so there is no entry to record.
    if not purchase.merit_id:
        del character.merits_flaws[index]
        return None
    definition = ruleset.merits_flaws.get(purchase.merit_id)
    if definition is None:
        raise AdvancementError(f"Unknown Merit {purchase.merit_id!r}.")
    # Anything that depends on it must go first, or the sheet is left inconsistent.
    # Both directions: a Merit that names it as a prerequisite, and an elemental power
    # whose `required_merits` names it (Core p.296 / GoD p.56, PG p.68 — Elemental
    # Dominion gates every power, Primal Restoration gates Rejuvenation).
    dependents = [d.name for d in ruleset.merits_flaws.values()
                  if definition.id in d.prerequisites
                  and any(p.merit_id == d.id for p in character.merits_flaws)]
    dependents += [p.name for pid in character.elemental_powers
                   if (p := ruleset.elemental_powers.get(pid)) is not None
                   and definition.id in p.required_merits]
    if dependents:
        raise AdvancementError(
            f"{definition.name} is a prerequisite of {', '.join(sorted(dependents))}.")

    value = merit_change_xp(ruleset, character, definition, purchase.tier,
                           taken_as=purchase.taken_as, points=purchase.points)
    # The SIDE this purchase was taken on, not the catalogue's `kind` — buying off a
    # two-sided entry held as a Flaw must charge, not pay.
    if validate.effective_merit_kind(definition, purchase) == "merit":
        entry = _commit_award(character, "merits", f"-{purchase.merit_id}", -value)
    else:
        entry = _pay_or_owe(character, "merits", f"-{purchase.merit_id}", value)
    # Carry the removed purchase on the log row so `undo_last` can re-add it exactly
    # (tier/taken_as/points/arena/detail are not recoverable from the id alone). A
    # snapshot: the row owns its copy even though the live one is about to be deleted.
    entry.removed_purchase = purchase.model_copy(deep=True)
    del character.merits_flaws[index]
    return entry


def _commit_award(character: Character, target: str, detail: str, cost: int) -> XpEntry:
    """Append a log row that PAYS the character (negative cost) with no affordability
    check — there is nothing to afford. Kept separate from `_commit` so the ordinary
    purchase path keeps its gate."""
    entry = XpEntry(target=target, detail=detail, from_rating=None, to_rating=None,
                    cost=cost)
    character.xp_log.append(entry)
    return entry


# --------------------------------------------------------------------------- #
# Fetters and Passions (ghosts — Exalted: The Abyssals p.283)
#
# Four operations, two of which have no analogue anywhere else in the build: a
# "shift" moves a trait's FOCUS without changing any rating, so it is priced flat and
# the totals do not move. Passions are never bought — their dots come from the
# Virtues (p.283) — so `raise_passion` deliberately does not exist.
# --------------------------------------------------------------------------- #

def _fetter_index(character: Character, name: str) -> int:
    for i, f in enumerate(character.fetters):
        if f.name == name:
            return i
    raise AdvancementError(f"No Fetter named {name!r}.")


def _fetter_headroom(ruleset: RuleSet, character: Character) -> int:
    """Dots of Fetter still allowed by the p.127 cap (Willpower + Essence). Asked
    before every purchase that adds a dot, because the cap binds in play — it is not a
    chargen-only rule."""
    return derive.fetter_cap(character, ruleset) - derive.fetter_dots_spent(character)


def raise_fetter(ruleset: RuleSet, character: Character, name: str) -> XpEntry:
    """Raise one Fetter a dot for `current x 3` (p.283)."""
    _ensure_locked(character)
    idx = _fetter_index(character, name)
    frm = character.fetters[idx].rating
    if frm >= _DOT_MAX:
        raise AdvancementError(f"{name} is already at {_DOT_MAX}.")
    if _fetter_headroom(ruleset, character) < 1:
        raise AdvancementError(
            f"Fetters are at the cap of {derive.fetter_cap(character, ruleset)} dots "
            f"(Willpower + Essence, p.127).")
    cost = costs.fetter_step(ruleset, character, frm)
    entry = _commit(character, "fetters", name, frm, frm + 1, cost)
    character.fetters[idx].rating = frm + 1
    return entry


def add_fetter(ruleset: RuleSet, character: Character, name: str,
               note: str = "") -> XpEntry:
    """Form a new one-dot Fetter — 20 XP, or 15 for a ghost who knows the Arcanos the
    table names (p.283). The discount is data, not a hardcoded id; see
    `costs.new_fetter_cost`."""
    _ensure_locked(character)
    if not name.strip():
        raise AdvancementError("A Fetter needs a name.")
    if any(f.name == name for f in character.fetters):
        raise AdvancementError(f"{name} is already a Fetter.")
    if _fetter_headroom(ruleset, character) < 1:
        raise AdvancementError(
            f"Fetters are at the cap of {derive.fetter_cap(character, ruleset)} dots "
            f"(Willpower + Essence, p.127).")
    cost = costs.new_fetter_cost(ruleset, character)
    entry = _commit(character, "new_fetters", name, None, 1, cost)
    character.fetters.append(FetterEntry(name=name, rating=1, note=note))
    return entry


def shift_fetter(ruleset: RuleSet, character: Character, name: str,
                 to_name: str) -> XpEntry:
    """Move a Fetter's focus (p.283, "Shift Fetter | 10"). The RATING does not change —
    only what the ghost is anchored to — so this touches no pool and no cap."""
    _ensure_locked(character)
    idx = _fetter_index(character, name)
    if not to_name.strip():
        raise AdvancementError("A Fetter needs a name.")
    if any(f.name == to_name for f in character.fetters):
        raise AdvancementError(f"{to_name} is already a Fetter.")
    cost = ruleset.xp_costs_for(character.exalt_type).shift_fetter
    entry = _commit(character, "shift_fetters", f"{name}>{to_name}", None, None, cost)
    character.fetters[idx].name = to_name
    return entry


def shift_passion(ruleset: RuleSet, character: Character, frm: str, to: str,
                  to_virtue: Optional[VirtueName] = None) -> XpEntry:
    """Move one dot from one Passion to another (p.283, "Shift Passion | 20").

    "This decreases a Passion by one dot. In turn, it increases an existing Passion by
    one dot or creates a new one-dot Passion." So the TOTAL never moves — which is what
    keeps this consistent with p.283's other half, that Passions rise only when the
    Virtues do. A Passion emptied to zero is removed rather than left as a 0-dot row.

    `to_virtue` names the Virtue the destination Passion belongs to when it is being
    created; it defaults to the source's, since the pools are per-Virtue and a shift
    across Virtues would move a dot between two pools that the Virtues, not the player,
    are supposed to size. Passing one explicitly is allowed — the page does not forbid
    it — and `validate.check_fetters_and_passions` reports the result either way.
    """
    _ensure_locked(character)
    src = next((p for p in character.passions if p.name == frm), None)
    if src is None:
        raise AdvancementError(f"No Passion named {frm!r}.")
    if src.rating < 1:
        raise AdvancementError(f"{frm} has no dots to shift.")
    if not to.strip():
        raise AdvancementError("A Passion needs a name.")
    dst = next((p for p in character.passions if p.name == to), None)
    if dst is not None and dst.rating >= _DOT_MAX:
        raise AdvancementError(f"{to} is already at {_DOT_MAX}.")
    cost = ruleset.xp_costs_for(character.exalt_type).shift_passion
    entry = _commit(character, "shift_passions", f"{frm}>{to}", None, None, cost)
    src.rating -= 1
    if dst is None:
        character.passions.append(
            PassionEntry(name=to, virtue=to_virtue or src.virtue, rating=1))
    else:
        dst.rating += 1
    if src.rating == 0:
        character.passions.remove(src)
    return entry
