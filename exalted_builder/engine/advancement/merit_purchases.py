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


def _merit_purchase_gates(ruleset: RuleSet, character: Character, definition,
                          tier: str, points: int, taken_as: str) -> None:
    """Raise AdvancementError if this character may not take `definition` right now.

    The gates `validate.merit_issues` applies at chargen that a POST-LOCK purchase
    must also respect. They are re-asked here rather than shared with that function
    because the two differ in kind: this refuses a purchase, that reports a holding.

    ⚠ Test the buy path, not the effect. Every gate below was implemented, ran at
    chargen, and did nothing when a Merit was bought with XP — the house bug, found
    by preflight 2026-08-17.
    """
    # The tier menu THIS character prices on, not the generic one: a tier printed for
    # another splat otherwise passes and then prices at nothing.
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
    # Point limits keyed to a Background or a named artifact (Damaged Artifact,
    # Known Anathema, Debt). Measured LIVE — the purchase is happening now.
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
    _merit_purchase_gates(ruleset, character, definition, tier, points, taken_as)

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


def gain_merit_or_flaw(ruleset: RuleSet, character: Character, merit_id: str,
                       *, tier: str = "", detail: str = "", arena: str = "",
                       taken_as: str = "", points: int = 0) -> XpEntry:
    """Take on one catalogue entry in play, whichever side of the transaction it is.

    Input: the entry's id plus whatever the row records (tier, points, detail, arena,
    and `taken_as` for a two-sided entry). Output: the `XpEntry` `buy_merit` or
    `gain_flaw` logged. Mechanism: the ENTRY decides the direction — a Flaw pays the
    character, a Merit charges her — so the side is read off the definition and only a
    `kind: "either"` entry consults `taken_as`.

    ⚠ Every shell needs this branch, and it is a rules decision, not layout: which of
    the two engine calls runs is what makes the XP positive or negative. Both refusals
    (no entry, and a two-sided entry with no side picked) are raised here so no widget
    has to restate them."""
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
