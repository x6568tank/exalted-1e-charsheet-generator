"""
engine/advancement/merit_purchases.py — the Merit and Flaw changes after the
lock (Player's Guide p.17): purchase, gain, and removal.
"""

from __future__ import annotations

from .. import costs, merits, validate
from ...models.character import Character, MeritFlawPurchase, XpEntry
from ...models.rules import RuleSet

from ._base import AdvancementError, _ensure_locked


def mf_change_method(character: Character) -> str:
    """Return the Player's Guide p.17 method of the table. Only "experience" moves XP."""
    return (character.house_rules.mf_change_method
            if character.house_rules is not None else "experience")


def merit_change_xp(ruleset: RuleSet, character: Character, merit, tier: str = "",
                    *, taken_as: str = "", points: int = 0) -> int:
    """Return the XP of a M&F change under the experience method (PG p.17): positive
    to gain a Merit or lose a Flaw, negative to lose a Merit or gain a Flaw, 2x the
    bonus-point value. 0 under the other two methods."""
    if mf_change_method(character) != "experience":
        return 0
    return costs.merit_cost(ruleset, character, merit, tier,
                            taken_as=taken_as, points=points)


def _pay_or_owe(character: Character, target: str, detail: str, cost: int) -> XpEntry:
    """Commit a Merit change. An unaffordable change goes into debt (p.17); `_commit`
    refuses instead. The full cost is logged. `xp_available` goes negative and
    `xp_debt` reports it.
    """
    entry = XpEntry(target=target, detail=detail, from_rating=None, to_rating=None,
                    cost=cost)
    character.xp_log.append(entry)
    return entry


def _merit_purchase_gates(ruleset: RuleSet, character: Character, definition,
                          tier: str, points: int, taken_as: str) -> None:
    """Raise AdvancementError if this character may not take `definition` right now.

    The chargen gates of `validate.merit_issues` that an XP purchase must also meet.
    Not shared: this refuses a purchase, that reports a holding.

    ⚠ Test the buy path, not the effect. A gate that runs at chargen only does
    nothing on an XP purchase (the house bug, type 1).
    """
    # The tier menu of THIS character, not the generic one.
    own_options = validate.merit_cost_options(definition, character.exalt_type,
                                              character.caste)
    if definition.cost_options and tier not in own_options:
        raise AdvancementError(
            f"{definition.name} needs one of {sorted(own_options)}.")
    if tier and validate.exalt_type_barred_from_tier(definition,
                                                     character.exalt_type, tier):
        raise AdvancementError(
            f"{definition.name} at {tier!r} is not available to "
            f"{character.exalt_type}.")
    if definition.thaumaturges_only:
        thaum = validate.thaum_state(character)
        if not (thaum.arts or thaum.sciences or thaum.rituals or thaum.formulas
                or thaum.art_specialties):
            raise AdvancementError(
                f"{definition.name} is open to thaumaturges only; this character "
                f"holds no Arts, Sciences, rituals or formulas.")
    purchase = MeritFlawPurchase(merit_id=definition.id, tier=tier,
                                 taken_as=taken_as, points=points)
    for group in validate.unmet_trait_prerequisites(character, definition, purchase,
                                                    character.backgrounds):
        want = " or ".join(f"{r.trait} {r.rating}" for r in group)
        raise AdvancementError(f"{definition.name} requires {want}.")
    # Point limits from a Background or an artifact, measured LIVE.
    value = validate.merit_points(definition, purchase, character.exalt_type,
                                  character.caste)
    for limit in definition.points_limits:
        if limit.per_entry:
            continue        # needs an artifact_key the buy path does not carry yet
        have = validate.background_best(character.backgrounds, limit.background)
        rating = have + limit.offset
        if limit.mode == "max" and value > rating:
            raise AdvancementError(
                f"{definition.name} may not be worth more than {max(0, rating)} "
                f"point(s) at {limit.background} {have}; this is worth {value}.")
        if limit.mode == "above" and value <= rating:
            raise AdvancementError(
                f"{definition.name} must exceed {limit.background} {have}; "
                f"this is worth {value}.")
    # A repeatable entry capped by a trait ("no more times than their Occult").
    if definition.max_purchases_from_trait:
        cap = validate.trait_rating(character, definition.max_purchases_from_trait,
                                    character.backgrounds)
        held = [p.merit_id for p in character.merits_flaws].count(definition.id)
        if held >= cap:
            raise AdvancementError(
                f"{definition.name} may not be taken more times than "
                f"{definition.max_purchases_from_trait} ({cap}).")


def buy_merit(ruleset: RuleSet, character: Character, merit_id: str,
              *, tier: str = "", detail: str = "", arena: str = "",
              taken_as: str = "", points: int = 0) -> XpEntry:
    """Gain a Merit after creation: 2x its bonus-point value under the experience
    method (PG p.17, p.115), else 0.

    A Flaw is gained with `gain_flaw`. A `kind: "either"` entry comes here only with
    `taken_as="merit"`: the side decides charge or pay, thus it is never defaulted.
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
    # The origin repeat cap (PG p.74) applies on the buy path too.
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
    _merit_purchase_gates(ruleset, character, definition, tier, points, taken_as)

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
    """Take a Flaw in play. Under the experience method this PAYS 2x its value (a
    negative-cost row), else 0.

    An either-entry needs `taken_as="flaw"`. The Flaw cap (p.16, p.17) applies to the
    total, below.
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
    _merit_purchase_gates(ruleset, character, definition, tier, points, taken_as)

    award = merit_change_xp(ruleset, character, definition, tier,
                            taken_as=taken_as, points=points)
    # PG p.17: no XP for Flaw points above 10, measured against the Flaws ALREADY held.
    # A Flaw across the cap pays for its legal part only.
    if award:
        already = merits.flaw_points(ruleset, character)
        room = max(0, merits.FLAW_POINT_CAP - already)
        # Use the value of this purchase: its side, tier and agreed points.
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


def gain_merit_or_flaw(ruleset: RuleSet, character: Character, merit_id: str,
                       *, tier: str = "", detail: str = "", arena: str = "",
                       taken_as: str = "", points: int = 0) -> XpEntry:
    """Take one catalogue entry in play, Merit or Flaw. Returns the `XpEntry` of
    `buy_merit` or `gain_flaw`.

    The entry decides the direction. Only a `kind: "either"` entry reads `taken_as`.

    ⚠ A rules decision, not layout: each shell must call this. Both refusals (no
    entry, no side for a two-sided entry) are raised here."""
    definition = ruleset.merits_flaws.get(merit_id)
    if definition is None:
        raise AdvancementError("Pick a Merit or Flaw first.")
    side = definition.kind
    if side == "either":
        side = taken_as
        if side not in ("merit", "flaw"):
            raise AdvancementError(
                f"{definition.name} is a Merit OR a Flaw — pick which side.")
    call = gain_flaw if side == "flaw" else buy_merit
    return call(ruleset, character, merit_id, tier=tier, detail=detail, arena=arena,
                taken_as=taken_as, points=points)


def drop_merit(ruleset: RuleSet, character: Character, index: int) -> XpEntry | None:
    """Lose a Merit, or buy off a Flaw (PG p.17). Losing a MERIT pays the character
    two times its value. Losing a FLAW charges it. Returns None for a player-authored
    Custom row: its removal is a plain delete with no XP value."""
    _ensure_locked(character)
    if not 0 <= index < len(character.merits_flaws):
        raise AdvancementError(f"No Merit at index {index}.")
    purchase = character.merits_flaws[index]
    # A player-authored "Custom" row has no XP value: a drop is a plain removal.
    # ⚠ The discriminator is the EMPTY merit_id, not custom_name.
    #
    # ⚠ Log NOTHING: `undo_last` has no merits branch, thus a cost-0 row would use up
    # the player's NEXT undo on a no-op.
    if not purchase.merit_id:
        del character.merits_flaws[index]
        return None
    definition = ruleset.merits_flaws.get(purchase.merit_id)
    if definition is None:
        raise AdvancementError(f"Unknown Merit {purchase.merit_id!r}.")
    # Remove the dependants first: a Merit that requires it, and an elemental power
    # whose `required_merits` names it (Core p.296 / GoD p.56, PG p.68).
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
    # The SIDE of this purchase, not the catalogue `kind`.
    if validate.effective_merit_kind(definition, purchase) == "merit":
        entry = _commit_award(character, "merits", f"-{purchase.merit_id}", -value)
    else:
        entry = _pay_or_owe(character, "merits", f"-{purchase.merit_id}", value)
    # A copy of the removed purchase on the log row, for `undo_last`.
    entry.removed_purchase = purchase.model_copy(deep=True)
    del character.merits_flaws[index]
    return entry


def _commit_award(character: Character, target: str, detail: str, cost: int) -> XpEntry:
    """Append a log row that PAYS the character (negative cost). No affordability
    check."""
    entry = XpEntry(target=target, detail=detail, from_rating=None, to_rating=None,
                    cost=cost)
    character.xp_log.append(entry)
    return entry
