"""
engine/validate/merit_checks.py — Merit & Flaw legality, cost, and the magic gate.

`merit_issues` (prerequisites, tiers, caps, point limits), `merit_bonus_point_cost` and
the cost helpers, plus `magic_gate_issues` and `pool_requires_unlocking` — the rules by
which a mortal reaches magic at all, which arrive through Merits and so live here.

⚠ No function here may name a Merit id (decision 0011). Every branch reads a
`MeritEffects` field or a `MeritFlaw` data field; a rule that seems to need an id
belongs in `engine/merits.py` with a new `MeritEffects` field instead.

⚠ Named `merit_checks`, not `merits`, for that rule's sake as much as readability:
decision 0011's containment test used to exempt the BASENAME `merits.py`, so a second
file of that name would have exempted itself from the only enforcement the rule has.
The test now keys on the path.

⚠ `withheld_charm_credits` ships without its printed counterweight — Weak Essence's
withheld Charms "still require the same training time", and training times are not
modelled. The XP waiver is deliberately one-sided.
"""

from __future__ import annotations

from ...models.character import Character, ThaumaturgyState
from ...models.rules import RuleSet
from .. import artifacts, merits
from ._base import Issue, ability_rating, effective_budgets, thaum_state
from .backgrounds import background_best, trait_rating, unmet_trait_prerequisites
from .charms import chargen_charm_picks, charm_picks


# The gates that measure something which can CHANGE after the purchase — an artifact
# lost, a Background dropped, a trait cursed down. These re-run post-lock as warnings;
# every other gate here measures a frozen chargen choice and does not.
DRIFT_CODES = frozenset({
    "merit-artifact-unchosen",
    "merit-points-above-background",
    "merit-points-below-background",
    "merit-trait-prerequisite",
    "merit-repeats-above-trait",
})


def merit_issues(ruleset: RuleSet, character: Character, *,
                 post_lock: bool = False) -> list[Issue]:
    """Legality of the character's Merits & Flaws (Player's Guide pp.120-122).

    Structural only — an unknown id, a missing prerequisite, a variable-cost entry
    with no valid tier, a repeat of a non-repeatable Merit, or a thaumaturges-only
    entry on a character who holds no thaumaturgy. What a Merit DOES is never checked
    here; that is engine.merits' job (decision 0011).

    `post_lock=True` returns only the `DRIFT_CODES` subset, downgraded to warnings —
    the same shape `background_issues(post_lock=True)` uses. Human's ruling
    2026-08-17: a character holding a benefit they no longer qualify for should be
    told, but the story can legitimately create the state, so it is not an error.

    ⚠ Post-lock the gates read LIVE traits, not the snapshot. The snapshot holds the
    values as they were AT the lock, so a snapshot read would re-check what was
    already checked and never fire — the check would exist and do nothing.

    ⚠ The frozen-choice gates (splat, caste, origin, tier) are deliberately NOT in
    `DRIFT_CODES`. They cannot drift, so re-running them is noise.
    """
    issues: list[Issue] = []
    held: dict[str, int] = {}
    # "THAUMATURGES ONLY" asks whether the character holds any thaumaturgy at all.
    # Read through the snapshot at chargen so a locked sheet keeps the answer it was
    # built with; LIVE post-lock, where the question is what is true NOW.
    snap = None if post_lock else character.chargen_snapshot
    thaum = (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character)
    has_thaum = bool(thaum.arts or thaum.sciences or thaum.rituals or thaum.formulas
                     or thaum.art_specialties)
    backgrounds = snap.backgrounds if snap else character.backgrounds

    for purchase in character.merits_flaws:
        # A player-authored "Custom" row (2026-08-10) has no catalogue entry by
        # design — display-only, no mechanical effect. Nothing about it is checkable
        # here, so it is skipped entirely rather than reported as merit-unknown. The
        # discriminator is the EMPTY merit_id (set at creation, never edited by the
        # name input) — not custom_name, which the player can blank and must not
        # turn back into a merit-unknown error.
        if not purchase.merit_id:
            continue
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is None:
            issues.append(Issue(
                code="merit-unknown", where=purchase.merit_id,
                message=f"Merit {purchase.merit_id!r} is not in the rule set.",
            ))
            continue
        held[definition.id] = held.get(definition.id, 0) + 1

        if purchase.tier and exalt_type_barred_from_tier(definition, character.exalt_type,
                                                         purchase.tier):
            issues.append(Issue(
                code="merit-barred-splat-tier", where=definition.id,
                message=(f"{definition.name} at {purchase.tier!r} is not available to "
                         f"{character.exalt_type}; open options are "
                         f"{', '.join(merit_tiers_available(definition, character.exalt_type, character.caste))}."),
            ))
        # Against the menu THIS character prices on, not the generic one — a Sidereal
        # recording Lucky at 4 would otherwise pass validation and be worth 0 points.
        own_options = merit_cost_options(definition, character.exalt_type, character.caste)
        if definition.cost_options and purchase.tier not in own_options:
            issues.append(Issue(
                code="merit-bad-tier", where=definition.id,
                message=f"{definition.name} needs one of "
                        f"{sorted(own_options)}; got {purchase.tier!r}.",
            ))
        if definition.kind == "either" and purchase.taken_as not in ("merit", "flaw"):
            issues.append(Issue(
                code="merit-side-unchosen", where=definition.id,
                message=f"{definition.name} is printed as a Merit OR a Flaw "
                        f"{definition.cost_note}; record which side was taken.",
            ))
        if definition.exalt_types and character.exalt_type not in definition.exalt_types:
            issues.append(Issue(
                code="merit-wrong-splat", where=definition.id,
                message=f"{definition.name} is restricted to "
                        f"{', '.join(definition.exalt_types)}; this character is "
                        f"{character.exalt_type}.",
            ))
        if character.exalt_type in definition.barred_exalt_types:
            issues.append(Issue(
                code="merit-barred-splat", where=definition.id,
                message=f"{definition.name} is not available to "
                        f"{', '.join(definition.barred_exalt_types)}.",
            ))
        if character.caste in definition.barred_castes:
            caste = ruleset.castes.get(character.caste)
            issues.append(Issue(
                code="merit-barred-caste", where=definition.id,
                message=f"{definition.name} is not available to the "
                        f"{caste.label if caste else character.caste} caste.",
            ))
        if definition.required_origins and character.origin not in definition.required_origins:
            issues.append(Issue(
                code="merit-wrong-origin", where=definition.id,
                message=f"{definition.name} is restricted to "
                        f"{', '.join(definition.required_origins)}; this character "
                        f"is a {character.origin or 'blank'} {character.caste}.",
            ))
        for limit in definition.points_limits:
            points = merit_points(definition, purchase, character.exalt_type,
                                  character.caste)
            if limit.per_entry:
                # The limit measures ONE named artifact, not the character's holdings.
                # An unresolved key is reported rather than defaulted: choosing the
                # best artifact on the character's behalf would make an illegal
                # purchase legal without anyone deciding to.
                item = artifacts.find_item(character, purchase.artifact_key)
                if item is None:
                    issues.append(Issue(
                        code="merit-artifact-unchosen", where=definition.id,
                        message=f"{definition.name} must name which artifact it "
                                f"modifies; its point limit is the rating of that "
                                f"artifact.",
                    ))
                    continue
                if limit.measure == "acquisition_cost":
                    budgets = effective_budgets(ruleset, character)
                    have = artifacts.acquisition_cost(budgets, item.rating)
                    shown = f"the {have} Background point(s) {item.name} cost"
                else:
                    have, shown = item.rating, f"{item.name} {item.rating}"
            else:
                have = background_best(backgrounds, limit.background)
                shown = f"{limit.background} {have}"
            rating = have + limit.offset
            if limit.mode == "max" and points > rating:
                issues.append(Issue(
                    code="merit-points-above-background", where=definition.id,
                    message=f"{definition.name} may not be worth more than "
                            f"{max(0, rating)} point(s) at {shown}; "
                            f"this purchase is worth {points}.",
                ))
            elif limit.mode == "above" and points <= rating:
                issues.append(Issue(
                    code="merit-points-below-background", where=definition.id,
                    message=f"{definition.name} must exceed {shown}; "
                            f"this purchase is worth {points}.",
                ))
        for group in unmet_trait_prerequisites(character, definition, purchase,
                                               backgrounds):
            want = " or ".join(f"{r.trait} {r.rating}" for r in group)
            issues.append(Issue(
                code="merit-trait-prerequisite", where=definition.id,
                message=f"{definition.name} requires {want}.",
            ))
        # A structured `detail` (which Attribute category a forfeit comes from, which
        # Attribute Legendary Attribute raises) is a CLOSED set. Unset or off-list, the
        # effect silently does not happen — Legendary Attribute grants no cap at all,
        # and a forfeit falls back to Physical. Reported rather than defaulted.
        choices = merits.detail_choices(definition)
        if choices and purchase.detail.strip().title() not in choices:
            issues.append(Issue(
                code="merit-detail-unchosen", where=definition.id,
                message=(f"{definition.name} must name which of "
                         f"{', '.join(choices)} it applies to; got "
                         f"{purchase.detail or '(nothing)'!r}."),
            ))
        if definition.min_starting_essence:
            start = effective_budgets(ruleset, character).essence_start
            if start < definition.min_starting_essence:
                issues.append(Issue(
                    code="merit-starting-essence", where=definition.id,
                    message=(f"{definition.name} is only open to characters whose splat "
                             f"starts at Essence {definition.min_starting_essence} or "
                             f"more; {character.exalt_type} starts at {start}, so the "
                             f"Flaw would cost nothing and still pay its points."),
                ))
        if definition.thaumaturges_only and not has_thaum:
            issues.append(Issue(
                code="merit-thaumaturges-only", where=definition.id,
                message=f"{definition.name} is open to thaumaturges only; this "
                        f"character holds no Arts, Sciences, rituals or formulas.",
            ))

    for mid, count in held.items():
        definition = ruleset.merits_flaws[mid]
        if count > 1 and not definition.repeatable_by:
            issues.append(Issue(
                code="merit-repeated", where=mid,
                message=f"{definition.name} may only be taken once; found {count}.",
            ))
        # A repeatable entry may still be capped by a trait — "characters may not
        # purchase this Merit more times than their Occult rating" (PG p.24).
        if definition.max_purchases_from_trait:
            limit = trait_rating(character, definition.max_purchases_from_trait,
                                 backgrounds)
            if count > limit:
                issues.append(Issue(
                    code="merit-repeats-above-trait", where=mid,
                    message=f"{definition.name} may not be taken more times than "
                            f"{definition.max_purchases_from_trait} "
                            f"({limit}); found {count}.",
                ))
        # ...or by origin — Virtue Attunement is once for a commoner Fae-Blooded,
        # twice for a noble (PG p.74). An origin with no entry in the map is uncapped.
        if character.origin in definition.max_purchases_by_origin:
            limit = definition.max_purchases_by_origin[character.origin]
            if count > limit:
                issues.append(Issue(
                    code="merit-repeats-above-origin", where=mid,
                    message=f"{definition.name} may be taken at most {limit} time(s) "
                            f"as a {character.origin}; found {count}.",
                ))
        for pid in definition.prerequisites:
            if pid not in held:
                name = ruleset.merits_flaws[pid].name if pid in ruleset.merits_flaws else pid
                issues.append(Issue(
                    code="merit-prerequisite", where=mid,
                    message=f"{definition.name} requires {name}.",
                ))

    # Backgrounds a held entry caps or forbids (A6 — Innocuous' veiled tier, p.22).
    # Asked of engine.merits, so no Merit id is named here.
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if effects.background_caps or effects.barred_backgrounds:
        for bg in backgrounds:
            key = bg.name.strip().lower()
            if not key or bg.rating <= 0:
                continue
            if key in effects.barred_backgrounds:
                issues.append(Issue(
                    code="background-barred-by-merit", where=bg.name,
                    message=f"{bg.name} is closed to this character by a Merit or "
                            f"Flaw they hold.",
                ))
            cap = effects.background_caps.get(key)
            if cap is not None and bg.rating > cap:
                issues.append(Issue(
                    code="background-above-merit-cap", where=bg.name,
                    message=f"{bg.name} may not exceed {cap} for this character "
                            f"(a Merit or Flaw they hold caps it); rating is "
                            f"{bg.rating}.",
                ))
    if post_lock:
        return [i.model_copy(update={"severity": "warning"})
                for i in issues if i.code in DRIFT_CODES]
    return issues


def merit_bonus_point_cost(ruleset: RuleSet, character: Character) -> int:
    """Bonus points SPENT on Merits. Flaws cost nothing to take — their point value is
    a grant, accounted separately (see `MeritEffects.bonus_point_grant`), so only
    `kind == "merit"` rows are charged here.

    Every cost shape is resolved by `merit_points`, including the per-splat prices the
    general chapter is full of — hence passing the character's Exalt type."""
    total = 0
    # A Merit whose price another Merit changes (Holy Mien -> Priest). Asked of
    # engine.merits, so no Merit id is ever named here.
    overrides = merits.merits_and_flaws_calc(ruleset, character).merit_cost_overrides
    for purchase in character.merits_flaws:
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is None:
            continue
        if effective_merit_kind(definition, purchase) != "merit":
            continue
        override = overrides.get(definition.id)
        if override is not None and purchase.tier in override:
            total += override[purchase.tier]
            continue
        total += merit_points(definition, purchase, character.exalt_type,
                              character.caste)
    return total


def effective_merit_kind(definition, purchase) -> str:
    """Whether THIS purchase counts as a Merit or a Flaw.

    Fixed by the catalogue for the single-sided majority. A `kind: "either"` entry —
    Mutation, Favor, Eternal Vow, each printed as "MERIT OR FLAW" — is the player's
    choice, recorded on the purchase. An either-entry with no choice recorded defaults
    to "merit" here so pricing never crashes; validate reports the missing choice
    separately rather than letting it pass unnoticed."""
    if definition.kind != "either":
        return definition.kind
    return purchase.taken_as if purchase.taken_as in ("merit", "flaw") else "merit"


def merit_cost_options(definition, exalt_type: str = "", caste: str = "") -> dict[str, int]:
    """The menu this character actually prices against — the ONE resolution order, so a
    dropdown can never offer an option the pricer will not honour.

    Caste outranks splat outranks the generic table, exactly as `merit_points` reads
    them. Lucky is why this is not just `definition.cost_options`: it is "1- TO 5-PT.
    MERIT, 1- TO 3-PT. FOR SIDEREALS", and reading the generic table offered a Sidereal
    a 4- and 5-point option that priced at 0 — visible in the dropdown, worth nothing.
    """
    by_caste = definition.cost_options_by_caste.get(caste or "")
    if by_caste:
        return dict(by_caste)
    by_splat = definition.cost_options_by_exalt_type.get(exalt_type or "")
    if by_splat:
        return dict(by_splat)
    return dict(definition.cost_options)


def merit_tiers_available(definition, exalt_type: str, caste: str = "") -> tuple[str, ...]:
    """The options of a menu-priced entry this splat may actually choose.

    Two things narrow the menu. `tier_barred_exalt_types` is Prodigy's, barred to four
    splats for the half that grants a Favored Ability while its "increased aptitude"
    half stays open to exactly those splats. `merit_cost_options` is Lucky's, where the
    splat gets a SHORTER menu rather than a differently-priced one. Returns () for an
    entry with no menu at all — callers should treat that as "no tier to choose", not
    as "nothing available".
    """
    return tuple(t for t in merit_cost_options(definition, exalt_type, caste)
                 if exalt_type not in definition.tier_barred_exalt_types.get(t, ()))


def exalt_type_barred_from_tier(definition, exalt_type: str, tier: str) -> bool:
    """Whether this splat is barred from one named option of a menu-priced entry."""
    return exalt_type in definition.tier_barred_exalt_types.get(tier, ())


def merit_available_to(definition, exalt_type: str, caste: str = "", *,
                       origin: str = "", starting_essence: int | None = None) -> bool:
    """Whether the catalogue opens this entry to this character at all.

    The printed restrictions only — splat allow-list, splat bar, caste bar, origin
    gate — which are inert catalogue DATA rather than effects, so no Merit id is named
    and `engine.merits` is not consulted. Prerequisites, tiers and "thaumaturges only"
    are NOT checked here: those depend on the rest of the sheet and change as it is
    built, so hiding an entry for them would make the dropdown flicker.

    Shares its three conditions with the `merit-wrong-splat` / `merit-barred-splat` /
    `merit-barred-caste` issues above, so a UI that filters on this can never offer
    something validation would immediately reject.
    """
    if definition.exalt_types and exalt_type not in definition.exalt_types:
        return False
    if exalt_type in definition.barred_exalt_types:
        return False
    if caste and caste in definition.barred_castes:
        return False
    if definition.required_origins and origin not in definition.required_origins:
        return False
    # A splat-level floor on starting Essence. Optional because not every caller has
    # the budgets to hand; when it is not supplied the entry is NOT hidden, so a
    # missing argument can only ever be permissive — validation still reports it.
    if (starting_essence is not None and definition.min_starting_essence
            and starting_essence < definition.min_starting_essence):
        return False
    # Barred at every option of its own menu = barred outright. Derived rather than
    # duplicated, so a per-tier bar can never disagree with the whole-entry one.
    if definition.cost_options and not merit_tiers_available(definition, exalt_type):
        return False
    return True


WITHHELD_CHARM_TARGET = "charms_withheld"


def withheld_charm_credits(ruleset: RuleSet, character: Character) -> tuple[int, int]:
    """(granted, remaining) chargen Charm picks banked for XP-free use after the lock.

    Weak Essence lets a new Exalt "withhold up to five Charms in reserve … Withheld
    Charms waive their experience cost" (p.41), since a character pinned at Essence 1
    cannot qualify for enough Charms to spend a full budget.

        granted = min(charm_credits_max, charm_count − picks taken)

    stated against the splat's own budget rather than Solar's 10. Redemptions are
    counted off the append-only XP log, so the pair reconciles with what was spent.

    ⚠ NOTHING new is stored — how many were withheld is derived from the unspent
    remainder, which the snapshot already records.

    ⚠ Banking defers picks, it never adds them: this cannot yield more Charms than the
    ordinary budget.
    """
    ceiling = merits.merits_and_flaws_calc(ruleset, character).charm_credits_max
    if not ceiling:
        return 0, 0
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    taken = len(chargen_charm_picks(ruleset, character))
    granted = max(0, min(ceiling, b.charm_count - taken))
    redeemed = sum(1 for e in character.xp_log if e.target == WITHHELD_CHARM_TARGET)
    return granted, max(0, granted - redeemed)


def merit_points(definition, purchase, exalt_type: str = "", caste: str = "") -> int:
    if definition.variable_cost:
        return max(0, purchase.points)
    # A two-sided entry may price each side differently (Eternal Vow: 3 as a Merit,
    # 1 as a Flaw), and that outranks every other shape.
    if definition.cost_by_kind:
        side = effective_merit_kind(definition, purchase)
        if side in definition.cost_by_kind:
            return definition.cost_by_kind[side]
    options = merit_cost_options(definition, exalt_type, caste)
    if options:
        return options.get(purchase.tier, options.get("", 0))
    return definition.cost


def pool_requires_unlocking(ruleset: RuleSet, character: Character) -> bool:
    """Whether the splat's Essence pool exists only after a Merit unlocks it — the
    God-Blooded's (Awakened Essence, PG p.66; the per-heritage formula sits on the
    caste's heritage_traits, not on the ExaltDefinition) and the mortal's (Essence
    Awareness / Essence Mastery). True exactly when the splat has no NATIVE pool and
    some unlocked spec exists to replace the empty one. One read site, shared by the
    chargen gate (magic_gate_issues) and the advancement-side refusals, so the two
    cannot disagree about which splats are gated."""
    exalt = ruleset.exalt_for(character.exalt_type)
    if exalt.essence.personal_essence_coeff or exalt.essence.personal_willpower_coeff:
        return False                       # a native pool needs no unlocking
    caste = ruleset.castes.get(character.caste)
    if caste is not None and caste.heritage_traits is not None \
            and caste.heritage_traits.unlocked_essence is not None:
        return True
    return exalt.unlocked_essence is not None


def magic_gate_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A splat whose Essence pool must be UNLOCKED (see `pool_requires_unlocking` —
    the God-Blooded's pool comes from the Awakened Essence Merit, PG p.66) may not
    hold Charms, spells, or Essence above its start until the pool is unlocked:
    p.49, "Only God-Blooded with the Awakened Essence Merit may purchase or increase
    magical Traits."

    Mortals are deliberately skipped (`charms_available` False) — their bars already
    live in charm_matches_splat and essence_start_cap, and this would double-report
    the same Charm. God-Blooded hold Charms freely once unlocked (charms_available
    True), so this gate is what stops an Awakened-Essence-less build from keeping the
    seven-BP Charms. Mirrors the advancement-side refusal in learn_charm/learn_spell."""
    exalt = ruleset.exalt_for(character.exalt_type)
    if not pool_requires_unlocking(ruleset, character) or not exalt.charms_available:
        return []
    if merits.merits_and_flaws_calc(ruleset, character).essence_pool_unlocked:
        return []
    b = ruleset.budgets_for(character.exalt_type, character.origin,
                            character.upbringing)
    issues: list[Issue] = []
    if list(charm_picks(ruleset, character)):
        issues.append(Issue(
            code="magic-requires-awakened-essence", where="charms",
            message=f"{exalt.label} may not purchase Charms without the Awakened "
                    "Essence Merit (PG p.49).",
        ))
    if character.spells:
        issues.append(Issue(
            code="magic-requires-awakened-essence", where="spells",
            message=f"{exalt.label} may not learn spells without the Awakened Essence "
                    "Merit (PG p.49).",
        ))
    if character.essence_rating > b.essence_start:
        issues.append(Issue(
            code="magic-requires-awakened-essence", where="essence",
            message="Essence above the starting rating requires the Awakened Essence "
                    "Merit (PG p.48).",
        ))
    return issues
