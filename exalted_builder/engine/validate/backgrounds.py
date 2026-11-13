"""
engine/validate/backgrounds.py — Background legality, dots and ratings.

Owns the Background pool accounting (`background_pool_spend`,
`background_dots_budget`), the per-splat catalogue and permission rules
(`background_catalogue_for`, `background_st_permitted`), the rating caps
(`background_rating_cap`, `effective_background_rating`), `background_issues`, the
Hearthstone allowance (`check_hearthstones`), and the two generic trait readers
`trait_rating` / `unmet_trait_prerequisites` that resolve a prerequisite naming a
Background.

⚠ `catalogue_backgrounds` is what the dropdown OFFERS; `allowed_backgrounds` is HARD
validation. Writing a list into the wrong one makes every free-text Background
illegal for that splat.

⚠ A Background is a MULTI-ROW trait. `background_rating` gives the sum. Read
`background_rows` for the rows and `background_best` for the highest. Two
Artifact •• rows are two artifacts, not one ••••.

⚠ `background_issues` runs on BOTH sides of the lock, with different rules:
`validate_chargen` applies the chargen caps. After the lock only the rules with
`bind_post_lock` apply: the story can add dots that no chargen budget allows.
"""

from __future__ import annotations

from ...models.character import Character, HouseRules
from ...models.rules import AbilityName, AttributeName, RuleSet, VirtueName
from .. import artifacts, merits
from ._base import Issue, _chargen_source, ability_rating, effective_budgets


def background_catalogue_for(ruleset: RuleSet, character: Character) -> list:
    """Return the Background names that the character can select.

    Reads the LIVE house rules, not the snapshot: the flag changes the offer, not the
    price.

    ⚠ The ONE read site for `HouseRules.all_backgrounds_available`.
    """
    hr = character.house_rules or HouseRules()
    rows = ruleset.backgrounds_for(character.exalt_type, character.origin,
                                   all_available=hr.all_backgrounds_available)
    # A `barred` rule hides the Background until its Storyteller toggle lifts it.
    #
    # ⚠ A permission toggle must move the BAR and the OFFER.
    budgets = effective_budgets(ruleset, character)
    hidden = {name for name, rule in budgets.background_rules.items()
              if rule.barred and not background_st_permitted(character, rule)}
    if hidden:
        rows = [bg for bg in rows if bg.name.strip().lower() not in hidden]
    return rows


def background_rule(budgets, name: str):
    """Return the `BackgroundRule` of the Background `name`, or None. The lookup uses
    the lowercased, stripped NAME, not `BackgroundType.id`."""
    return budgets.background_rules.get(name.strip().lower())


def background_pool_dots(rule, rating: int) -> int:
    """Return the chargen pool dots that `rating` uses: one per dot, unless the rule
    changes it.

    `expensive_above`: dots past a threshold cost more (CH2 p.65). `free_rating`: the
    first N dots are outside the pool (p.90).

    ⚠ FREE and MANDATORY are different. Alchemical Class ••• is mandatory and paid,
    thus it has no `free_rating`.
    """
    if rule is None:
        return rating
    if rule.expensive_above and rating > rule.expensive_above:
        cheap = rule.expensive_above
        paid = cheap * rule.dot_cost + (rating - cheap) * rule.expensive_dot_cost
    else:
        paid = rating * rule.dot_cost
    return max(0, paid - rule.free_rating)


def background_rating(backgrounds, name: str) -> int:
    """Return the SUM of all rows named `name`. 0 if absent.

    ⚠ Usually not the correct reader. See `background_rows` and `background_best`.
    """
    key = name.strip().lower()
    return sum(bg.rating for bg in backgrounds if bg.name.strip().lower() == key)


def background_rows(backgrounds, name: str) -> list[int]:
    """Return the ratings of all rows named `name`, for a rule that applies PER ROW.

    ⚠ Do not use the sum or the maximum for such a rule.
    """
    key = name.strip().lower()
    return [bg.rating for bg in backgrounds if bg.name.strip().lower() == key]


def background_best(backgrounds, name: str) -> int:
    """Return the HIGHEST row named `name`, 0 if absent, for a rule on ONE item.

    ⚠ Damaged Artifact (p.37) is singular. The sum lets two 2-dot artifacts meet a
    3-point Flaw.
    """
    key = name.strip().lower()
    return max((bg.rating for bg in backgrounds if bg.name.strip().lower() == key),
               default=0)


def effective_background_rating(ruleset: RuleSet, character: Character,
                                name: str) -> int:
    """Return the effective rating of a Background (Mountain Folk Resources, CH6).
    A splat with neither field gets the stored rating.

    ⚠ `effective_floor` is NOT `effective_bonus` at zero. The one place that reads
    both fields.
    """
    stored = background_best(character.backgrounds, name)
    rule = effective_budgets(ruleset, character).background_rules.get(name.strip().lower())
    if rule is None:
        return stored
    if stored <= 0:
        return max(rule.effective_floor, 0)
    return stored + rule.effective_bonus


def gear_affordability(ruleset: RuleSet, character: Character,
                       resources_cost: int) -> str:
    """Return how gear at `resources_cost` compares with the Resources of the
    character (core p.325):

        * cost LOWER than her Resources — an out-of-pocket expense;
        * cost EQUAL to her Resources — a serious expense: Resources drops by 1;
        * cost GREATER — she cannot afford it.

    Returns "easy" / "serious" / "unaffordable", or "" for gear with no printed cost.

    ⚠ For a PURCHASE only. Never use it to validate what a character OWNS (human's
    ruling): the EQUAL clause itself gives an item above the rating.
    """
    if resources_cost <= 0:
        return ""
    # ⚠ The EFFECTIVE rating, not the stored one (Mountain Folk). It also takes the
    # HIGHEST row, not the sum.
    #
    # ⚠ `ruleset` is REQUIRED here. An optional one would give a silent "you cannot
    # buy that".
    rating = effective_background_rating(ruleset, character, "Resources")
    if resources_cost < rating:
        return "easy"
    return "serious" if resources_cost == rating else "unaffordable"


def trait_rating(character: Character, name: str, backgrounds=None) -> int:
    """Return the rating of the trait `name`, of any kind.

    Order: Attributes, Abilities, Virtues, Backgrounds. Craft resolves through
    `craft_rating`. An unknown name gives 0. No 1e trait name exists in two
    namespaces.
    """
    key = name.strip().lower()
    if not key:
        return 0
    for attr in AttributeName:
        if attr.value == key:
            return character.attributes.get(attr, 0)
    for ab in AbilityName:
        if ab.value == key:
            return ability_rating(character, ab)
    for v in VirtueName:
        if v.value == key:
            return character.virtues.get(v, 0)
    return background_rating(
        character.backgrounds if backgrounds is None else backgrounds, name)


def unmet_trait_prerequisites(character: Character, definition, purchase,
                              backgrounds=None) -> list[list]:
    """Return the OR groups of `definition.trait_prerequisites` that this purchase
    does NOT meet.

    The "" key applies to all tiers. A named tier adds to it. A group is met if ANY
    member is met.
    """
    groups: list[list] = []
    groups += definition.trait_prerequisites.get("", [])
    if purchase.tier:
        groups += definition.trait_prerequisites.get(purchase.tier, [])
    return [g for g in groups
            if not any(trait_rating(character, r.trait, backgrounds) >= r.rating
                       for r in g)]


def background_dots_budget(b, character: Character) -> int:
    """Return the Background-dot budget of the character: `background_dots_by_caste`
    by CasteDefinition.id (CH6 p.230), else `background_dots`. All Background-budget
    readers use it."""
    if b.background_dots_by_caste:
        return b.background_dots_by_caste.get(character.caste, b.background_dots)
    return b.background_dots


def background_pool_spend(ruleset: RuleSet, character: Character, b, backgrounds,
                          bp_costs=None) -> tuple[int, list[int]]:
    """Return (pool dots used, bonus-point rates owed per dot) for the Backgrounds.

    A dot at or below `background_cap_pre_bp` uses a pool dot. A dot above it costs
    `background_above_3`, plus any surcharge (p.66).

    Heir Apparent (p.24) moves above-cap dots into the pool. The waiver goes to the
    most expensive above-cap dots. A waived dot counts as ONE pool dot.

    ⚠ `effective_budgets` adds as many pool dots as are waived here. Change both
    sides together.

    ⚠ The one arithmetic for the unspent warning and `bonus_point_breakdown`.
    """
    if bp_costs is None:
        bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                           character.upbringing)
    within = 0
    above_rates: list[int] = []
    for bg in backgrounds:
        rule = background_rule(b, bg.name)
        cap = bg.rating if (rule and rule.cap_pre_bp_exempt) else b.background_cap_pre_bp
        # The free Inheritance dots (PG p.61, human's ruling) waive the pool cost AND
        # the above-cap bonus points.
        if bg.name.strip().lower() == "inheritance":
            free = merits.inheritance_free_rating(ruleset, character)
            within += max(0, min(bg.rating, cap) - free)
            free_above = max(0, min(bg.rating, free) - cap)
            rate = bp_costs.background_above_3
            above_rates += [rate] * max(0, bg.rating - cap - free_above)
            continue
        # CH6 p.234-235: dots above `bp_above_rating` cost one bonus point each, not
        # a pool dot. Dots at or below it use the normal accounting.
        if rule and rule.bp_above_rating and bg.rating > rule.bp_above_rating:
            pool_rating = min(bg.rating, rule.bp_above_rating)
            within += background_pool_dots(rule, min(pool_rating, cap))
            mid_rate = bp_costs.background_above_3 + rule.bp_surcharge_per_dot
            above_rates += [mid_rate] * max(0, pool_rating - cap)
            above_rates += [1] * (bg.rating - rule.bp_above_rating)
            continue
        within += background_pool_dots(rule, min(bg.rating, cap))
        rate = bp_costs.background_above_3 + (rule.bp_surcharge_per_dot if rule else 0)
        above_rates += [rate] * max(0, bg.rating - cap)

    exempt = merits.merits_and_flaws_calc(ruleset, character).background_cap_exempt_dots
    if exempt:
        above_rates.sort(reverse=True)
        waived = min(exempt, len(above_rates))
        within += waived
        above_rates = above_rates[waived:]
    return within, above_rates


def background_issues(budgets, backgrounds, character=None, *,
                      post_lock=False) -> list[Issue]:
    """Check the Backgrounds that have mechanics (`background_rules`).

    Checks: a granted rating; a required Background; a ceiling (`max_rating`, the
    Attribute sum, or `barred`), unless `st_toggle` permits; the cap of 5 unless a
    rule raises it; and `allowed_backgrounds` (p.100). Skips blank rows.

    ⚠ `character` is OPTIONAL. Without it the answer is NARROWER, with no error.

    `post_lock=True` runs only the `BackgroundRule.bind_post_lock` rules.

    ⚠ The other caps are chargen-only BY DESIGN. Do not make a cap post-lock without
    a ruling.
    """
    issues: list[Issue] = []
    if not post_lock:
        allowed = {n.strip().lower() for n in budgets.allowed_backgrounds}
        if allowed:
            for bg in backgrounds:
                name = bg.name.strip()
                if name and name.lower() not in allowed:
                    issues.append(Issue(
                        code="background-not-allowed", where=name,
                        message=f"{name} is not available to this origin; allowed: "
                                f"{', '.join(sorted(n.title() for n in allowed))}.",
                    ))
        banned = {n.strip().lower() for n in budgets.banned_backgrounds}
        if banned:
            for bg in backgrounds:
                name = bg.name.strip()
                if name and name.lower() in banned:
                    issues.append(Issue(
                        code="background-banned", where=name,
                        message=f"{name.title()} is prohibited for this origin: "
                                f"{', '.join(sorted(n.title() for n in banned))}.",
                    ))
    for name, rule in budgets.background_rules.items():
        if post_lock and not rule.bind_post_lock:
            continue
        rating = background_rating(backgrounds, name)
        if not post_lock and rule.min_rating and rating < rule.min_rating:
            issues.append(Issue(
                code="background-below-minimum", where=name,
                message=f"{name.title()} is automatically {rule.min_rating} at character "
                        f"creation; this character has {rating}.",
            ))
        # The ceiling: `max_rating`, or the Attribute sum (Sidereals pp.106-108). Both
        # are HARD ceilings, lifted by `st_toggle`. The sum needs the character.
        cap = None
        cap_is_attribute_sum = False
        if rule.max_rating_is_attribute_sum and character is not None:
            cap = sum(_chargen_source(character)[0].values())
            cap_is_attribute_sum = True
        elif rule.max_rating:
            cap = rule.max_rating
        if cap and rating > cap and not background_st_permitted(character, rule):
            if cap_is_attribute_sum:
                issues.append(Issue(
                    code="background-above-attribute-cap", where=name,
                    message=f"{name.title()} may not exceed {cap} for this character; "
                            f"this character has {rating}.",
                ))
            else:
                issues.append(Issue(
                    code="background-above-origin-cap", where=name,
                    message=f"{name.title()} may not exceed {cap} for this origin; "
                            f"this character has {rating}.",
                ))
        # A BAR (core p.103), lifted by ST permission. Chargen only.
        if not post_lock and rule.barred and rating > 0 \
                and not background_st_permitted(character, rule):
            issues.append(Issue(
                code="background-barred", where=name,
                message=f"{name.title()} may not be purchased for this origin without "
                        f"Storyteller permission; this character has {rating}.",
            ))
        if not post_lock and rule.requires and rating > 0:
            have = background_rating(backgrounds, rule.requires)
            if have < rule.requires_rating:
                issues.append(Issue(
                    code="background-requires", where=name,
                    message=f"{name.title()} requires {rule.requires.title()} "
                            f"{rule.requires_rating}+; this character has {have}.",
                ))
    # The cap of 5, on both sides of the lock, except where a rule raises it. A
    # TOTAL-cap rule is checked above.
    for bg in backgrounds:
        key = (bg.name or "").strip().lower()
        if not key:
            continue
        rule = budgets.background_rules.get(key)
        governs = rule is not None and (not post_lock or rule.bind_post_lock)
        # ⚠ A rule may RAISE the cap. It may never REMOVE it.
        ceiling = (rule.max_rating if governs and rule.max_rating > merits.DOT_MAX
                   else merits.DOT_MAX)
        # A rule with a literal ceiling already reported this row.
        #
        # ⚠ A TOTAL-cap rule must NOT skip: its check reads the sum, not the row. Each
        # row of Sidereal Connections is capped at 5 too (human's ruling).
        if governs and rule.max_rating:
            continue
        if bg.rating > ceiling:
            issues.append(Issue(
                code="background-above-universal-cap", where=bg.name,
                message=f"{bg.name.title()} may not exceed {merits.DOT_MAX}; "
                        f"this character has {bg.rating}.",
            ))
    return issues


def background_st_permitted(character, rule) -> bool:
    """Return True if the `st_toggle` of `rule` lifts it for `character`.

    The toggle is the PER-CHARACTER `HouseRules` field that `BackgroundRule.st_toggle`
    names. ⚠ The ONE read site: the UI never reads HouseRules by name. No character,
    or an unknown field: False."""
    if character is None or not rule.st_toggle:
        return False
    hr = character.house_rules
    if hr is None:
        return False
    return bool(getattr(hr, rule.st_toggle, False))


def background_rating_cap(budgets, character, name, *, post_lock=False) -> int:
    """Return the highest rating of the Background `name` for THIS character on
    THIS side of the lock. The rating controls take their ceiling from here.

    Layers, most restrictive first:
      * a `barred` rule (rating must be 0), unless its `st_toggle` grants permission;
      * the rule's own `max_rating` ceiling;
      * DOT_MAX, the universal trait cap (5).

    ⚠ The Attribute-sum rule is NOT a layer: it caps a TOTAL (Sidereals
    pp.106-108).

    ⚠ After the lock, only `bind_post_lock` ceilings apply.
    """
    key = (name or "").strip().lower()
    rule = budgets.background_rules.get(key)
    if post_lock and not (rule and rule.bind_post_lock):
        return merits.DOT_MAX
    if rule is None:
        return merits.DOT_MAX
    if rule.barred and not background_st_permitted(character, rule):
        return 0
    if rule.max_rating and not background_st_permitted(character, rule):
        return rule.max_rating
    # Sidereal Connections caps a TOTAL, not a row: the row keeps the universal 5 and
    # `background_issues` checks the summed rating (human's ruling).
    return merits.DOT_MAX


def check_hearthstones(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check the Hearthstones on each Manse row (S&S pp.66-67). p.67 caps the TOTAL
    level. Some ladders also cap the largest stone.

    ⚠ PER ROW, not per character.

    ⚠ Runs on BOTH sides of the lock (human's ruling).

    The allowance comes from `background_catalogue_for`, thus each splat gets its
    own Manse variant. A row whose name matches no entry grows no stones: a stone on
    it is reported.
    """
    by_name = {bg.name.strip().lower(): bg
               for bg in background_catalogue_for(ruleset, character)}
    issues: list[Issue] = []
    for bg in character.backgrounds:
        if not bg.hearthstones:
            continue
        held = artifacts.hearthstone_total(bg)
        where = bg.name or "Background"
        bg_type = by_name.get(bg.name.strip().lower())
        allowance = (None if bg.is_demesne
                     else artifacts.hearthstone_allowance(bg_type, bg.rating))
        if allowance is None:
            issues.append(Issue(
                code="hearthstone-without-manse",
                message=(f"{where} holds {len(bg.hearthstones)} Hearthstone(s) but "
                         f"produces none"
                         + (" — the row is marked as a Demesne" if bg.is_demesne
                            else "")),
                where=where))
            continue
        label = (f"{where} {bg.rating} ({allowance.tier_name})"
                 if allowance.tier_name else f"{where} {bg.rating}")
        if held > allowance.combined_max:
            issues.append(Issue(
                code="hearthstone-over-combined",
                message=(f"{label} allows {allowance.combined_max} level(s) of "
                         f"Hearthstone; {held} held"),
                where=where))
        if allowance.individual_max:
            for stone in bg.hearthstones:
                if stone.rating > allowance.individual_max:
                    issues.append(Issue(
                        code="hearthstone-over-individual",
                        message=(f"{label} allows no Hearthstone above level "
                                 f"{allowance.individual_max}; {stone.name} is level "
                                 f"{stone.rating}"),
                        where=where))
        if allowance.max_items and len(bg.hearthstones) > allowance.max_items:
            issues.append(Issue(
                code="hearthstone-over-count",
                message=(f"{label} allows {allowance.max_items} Hearthstone(s); "
                         f"{len(bg.hearthstones)} held"),
                where=where))
    return issues
