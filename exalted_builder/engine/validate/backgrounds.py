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

⚠ A Background is a MULTI-ROW trait. `background_rating` sums nothing — read
`background_rows` for the individual rows and `background_best` for the highest.
Two Artifact •• rows are two artifacts, not one •••• (2026-07-31).

⚠ `background_issues` runs on BOTH sides of the lock, but with different rules: the
chargen caps are enforced by `validate_chargen`, while only the rules flagged
`bind_post_lock` in the data re-run once locked. Backgrounds change through play, so
a locked character may legitimately gain dots no chargen budget would have allowed.
"""

from __future__ import annotations

from ...models.character import Character, HouseRules
from ...models.rules import AbilityName, AttributeName, RuleSet, VirtueName
from .. import artifacts, merits
from ._base import Issue, _chargen_source, ability_rating, effective_budgets


def background_catalogue_for(ruleset: RuleSet, character: Character) -> list:
    """The Background names this character may pick from.

    Reads the LIVE house rules, not the frozen snapshot: the flag changes which names
    are OFFERED, never how a dot is priced, and a table that opens the catalogue mid-play
    should be able to add one.

    ⚠ The ONE read site for `HouseRules.all_backgrounds_available`, so the row dropdown
    and the catalogue dialog cannot offer different lists.
    """
    hr = character.house_rules or HouseRules()
    rows = ruleset.backgrounds_for(character.exalt_type, character.origin,
                                   all_available=hr.all_backgrounds_available)
    # A `barred` rule hides the Background until its Storyteller toggle lifts it, so the
    # dropdown never offers a name the sheet cannot legally hold.
    #
    # ⚠ The BAR and the OFFER are separate mechanisms and a permission toggle must move
    # BOTH. Lifting only the bar leaves a mortal granted Artifact unable to find it in
    # the catalogue — worse than no toggle at all.
    budgets = effective_budgets(ruleset, character)
    hidden = {name for name, rule in budgets.background_rules.items()
              if rule.barred and not background_st_permitted(character, rule)}
    if hidden:
        rows = [bg for bg in rows if bg.name.strip().lower() not in hidden]
    return rows


def background_rule(budgets, name: str):
    """The `BackgroundRule` for the Background called `name` under these budgets, or
    None when it has no mechanics. Backgrounds are free text, so the lookup is by
    lowercased, stripped NAME — not by `BackgroundType.id`."""
    return budgets.background_rules.get(name.strip().lower())


def background_pool_dots(rule, rating: int) -> int:
    """How many chargen pool dots a rating of `rating` consumes — one per dot, unless
    the rule says otherwise.

    `expensive_above` makes dots past a threshold cost more (Alchemical Artifact: dots 4
    and 5 cost two pool dots each, CH2 p.65). `free_rating` puts the first N dots outside
    the pool entirely (the Illuminated Solar's Illumination •, p.90 — "in addition" to
    the nine dots).

    ⚠ FREE and MANDATORY are different: Alchemical Class ••• is mandatory and still paid
    for, so it sets no `free_rating`.
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
    """The SUM of every row named `name`, 0 if absent.

    ⚠ Rarely the right reader. A possession Background is held per row — see
    `background_rows` and `background_best`.
    """
    key = name.strip().lower()
    return sum(bg.rating for bg in backgrounds if bg.name.strip().lower() == key)


def background_rows(backgrounds, name: str) -> list[int]:
    """Every row named `name`, as a list of ratings — for a rule that permits one thing
    PER ROW.

    ⚠ Two Artifacts at 2 dots each are two artifacts, not one artifact at 4. A rule
    counting rows must not read `background_rating`'s sum or `background_best`'s max.
    """
    key = name.strip().lower()
    return [bg.rating for bg in backgrounds if bg.name.strip().lower() == key]


def background_best(backgrounds, name: str) -> int:
    """The HIGHEST single row named `name`, 0 if absent — for a rule measuring ONE
    possession.

    ⚠ Damaged Artifact is the case: "may not gain more points from this Flaw than the
    rating of the artifact it modifies" (p.37), SINGULAR. Reading the sum lets two 2-dot
    artifacts satisfy a 3-point Flaw.
    """
    key = name.strip().lower()
    return max((bg.rating for bg in backgrounds if bg.name.strip().lower() == key),
               default=0)


def effective_background_rating(ruleset: RuleSet, character: Character,
                                name: str) -> int:
    """What a Background is WORTH to this character, which is not always what is stored.

    Mountain Folk Resources is the case (CH6): "an effective Resources rating equal to
    the number of dots invested in this Background + 2, but cannot have more than three
    actual dots", plus a floor for a character who never bought it — so a stored 3 is
    worth 5 and a stored 0 is worth 2. A splat printing neither field gets the stored
    rating unchanged, so this is safe to call for any Background.

    ⚠ `effective_floor` is NOT `effective_bonus` applied to zero. Adding the bonus at 0
    dots would make an unbought Background worth as much as one bought dot — a different
    and wrong rule. Two fields, and this is the only place both are read.
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
    """How a piece of gear priced at `resources_cost` sits against this character's
    Resources — core p.325, "The Resources System", the whole rule:

        * cost LOWER than her Resources — an out-of-pocket expense; "within reason,
          the character can purchase as many of the items as she wants";
        * cost EQUAL to her Resources — "a serious expense. When she buys it, she
          lowers her Resources rating by 1 until it is increased through roleplaying";
        * cost GREATER — "too expensive for her, and she cannot afford to buy it".

    Returns "easy" / "serious" / "unaffordable", or "" for gear with no printed cost
    (many catalogue rows have none, and a missing price is not a free item).

    ⚠ Answers a PURCHASE, and must never become a validation of what a character OWNS
    (human's ruling). The printed rule contradicts an ownership invariant in its own
    middle clause — buying at cost EQUAL drops Resources by one, so the book's own
    outcome is a character holding a 3-cost item at Resources 2. Loot and gifts break it
    the same way. A static "no item above your rating" check flags both as errors.
    """
    if resources_cost <= 0:
        return ""
    # ⚠ The EFFECTIVE rating, never the stored one. A Mountain Folk's Resources is worth
    # her dots + 2 and is capped at 3 actual dots, so reading the row raw makes every
    # item above Resources ••• unaffordable to the richest Jadeborn in Creation.
    # `effective_background_rating` also takes the HIGHEST
    # single row rather than the sum: Resources is one lifestyle rating, and two rows of
    # 2 is a character who wrote it down twice, not a character with 4.
    #
    # ⚠ `ruleset` is REQUIRED here, unlike the optional-ruleset shape `derive.soak` and
    # friends use. That shape trades a TypeError for a silently wrong answer, and this
    # function's wrong answer is "you cannot buy that" — invisible, and exactly the bug
    # being fixed. A caller with no RuleSet has no business pricing gear.
    rating = effective_background_rating(ruleset, character, "Resources")
    if resources_cost < rating:
        return "easy"
    return "serious" if resources_cost == rating else "unaffordable"


def trait_rating(character: Character, name: str, backgrounds=None) -> int:
    """The character's rating in the trait called `name`, whatever kind of trait it is.

    A Merit prerequisite names a trait across four namespaces — Appearance is an
    Attribute, Occult an Ability, Manse a Background — and the printed text gives only
    the name, so this resolves in a fixed order: Attributes, Abilities, Virtues, then
    Backgrounds. Craft resolves through `craft_rating`, the single AbilityName.CRAFT dot
    being unused.

    ⚠ An unresolvable name reads as 0 rather than raising, matching how unresolvable
    Charm and Background references are handled. The order matters only if a name
    collides across namespaces; no 1e trait name does.
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
    """The OR groups of `definition.trait_prerequisites` this purchase does NOT satisfy.

    Empty for the great majority, which require no rated trait. The "" key holds the
    requirements every tier carries; a named tier adds its own on top (Innocuous' two-
    point version needs Appearance 2, its four-point version needs nothing).

    A group is satisfied when ANY member of it is met — Cache's "Resources 4+ or
    Salary 2+" — matching the AND-of-OR shape Charm prerequisites already use.
    """
    groups: list[list] = []
    groups += definition.trait_prerequisites.get("", [])
    if purchase.tier:
        groups += definition.trait_prerequisites.get(purchase.tier, [])
    return [g for g in groups
            if not any(trait_rating(character, r.trait, backgrounds) >= r.rating
                       for r in g)]


def background_dots_budget(b, character: Character) -> int:
    """The Background-dot budget for THIS character, honouring a per-caste override
    (Mountain Folk, CH6 p.230: Artisans 13, Enlightened undercastes 10, Unenlightened
    6). `background_dots_by_caste` keys on CasteDefinition.id; a caste absent from the
    map falls back to `background_dots`. Every Background-budget consumer reads this,
    so the warning and the overflow arithmetic can never disagree."""
    if b.background_dots_by_caste:
        return b.background_dots_by_caste.get(character.caste, b.background_dots)
    return b.background_dots


def background_pool_spend(ruleset: RuleSet, character: Character, b, backgrounds,
                          bp_costs=None) -> tuple[int, list[int]]:
    """(pool dots consumed, per-dot bonus-point rates still owed) for the character's
    Backgrounds.

    A dot at or below `background_cap_pre_bp` consumes a pool dot; a dot above it is
    paid in bonus points at `background_above_3`, plus any per-Background surcharge
    (Lookshy Breeding, p.66).

    Heir Apparent (p.24) moves some above-cap dots into the pool group: its inherited
    dots "may raise a Background above a rating of three". Which Background received the
    inheritance is not recorded, so the waiver goes to the DEAREST above-cap dots — the
    player-favourable reading. A waived dot counts as ONE pool dot, not through
    `background_pool_dots`, whose expensive-upper-dot rules are Alchemical-only.

    ⚠ Waived dots are not FREE: `effective_budgets` adds exactly as many pool dots as
    are waived here, so the character pays once, through the pool. Changing one side
    without the other double-charges or double-credits.

    ⚠ The single arithmetic behind both the unspent-dot warning and
    `bonus_point_breakdown`. A second copy disagrees about what "spent from the pool"
    means.
    """
    if bp_costs is None:
        bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                           character.upbringing)
    within = 0
    above_rates: list[int] = []
    for bg in backgrounds:
        rule = background_rule(b, bg.name)
        cap = bg.rating if (rule and rule.cap_pre_bp_exempt) else b.background_cap_pre_bp
        # The God-Blooded Inheritance Background's FREE dots — the ST's series option
        # (PG p.61, human 2026-08-02) — waive BOTH the pool cost and the above-cap
        # bonus points: a free dot that sits above the cap must not appear in
        # above_rates either, or "Inheritance 4 with the ST option at 4" still charges
        # the two points for the fourth dot, which is exactly the complaint.
        if bg.name.strip().lower() == "inheritance":
            free = merits.inheritance_free_rating(ruleset, character)
            within += max(0, min(bg.rating, cap) - free)
            free_above = max(0, min(bg.rating, free) - cap)
            rate = bp_costs.background_above_3
            above_rates += [rate] * max(0, bg.rating - cap - free_above)
            continue
        # Dots ABOVE `bp_above_rating` are bought one bonus point each, NOT from the
        # Background pool (Mountain Folk Artifact, CH6 p.234-235: "with each dot
        # beyond 5 costing one bonus point"). The dots at or below it go through the
        # normal accounting below — `cap_pre_bp_exempt` keeps the MF's dots in the
        # pool — and any of those that still sit above the pre-BP cap owe the ordinary
        # above-cap rate (none for the MF, whose exempt cap is its own rating).
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
    """Legality for Backgrounds that carry mechanics (`background_rules`); empty for a
    splat with none.

    The checks: an automatically-granted Background may not sit below its rating; a
    Background gated on another must have it; a ceiling may not be passed — a literal
    `max_rating`, the Attribute-sum ceiling, or a `barred` prohibition (rating 0) —
    each unless its `st_toggle` grants permission; the universal trait cap of 5 holds
    unless a rule raises it; and where an origin restricts WHICH Backgrounds may be
    taken (`allowed_backgrounds`, the Sidereal ronin p.100), anything outside is
    flagged. Blank rows are skipped — the editor adds an empty row to fill in.

    `character` is OPTIONAL, following `derive.soak` and `lifecycle.lock_chargen`: a
    rule needing it is skipped, or reads as no permission, rather than raising.
    ⚠ Every omission is therefore a silently NARROWER answer, not an error.

    `post_lock=True` runs only rules flagged `BackgroundRule.bind_post_lock` — the
    Sidereal Celestial Manse ≤3 and Mountain Folk Artifact ≤10 (2026-08-12 rulings).

    ⚠ Every other cap is chargen-only BY DESIGN, because Backgrounds change through the
    story rather than by purchase. A locked character may legitimately be given dots no
    chargen budget allowed, so do not promote a cap here without a ruling.
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
        # The ceiling: a literal `max_rating`, or the Attribute-sum cap (Sidereal
        # Connections, Sidereals pp.106-108). Both are HARD ceilings — an error rather
        # than the bonus-point surcharge a soft cap produces — and both lift when the
        # rule's `st_toggle` grants permission. The Attribute-sum variant needs the
        # character; called without one it is skipped, the silent fallback.
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
        # A BAR (rating must be 0) — mortals and Artifact/Manse, core p.103 — lifted
        # by ST permission. Chargen only: there is no post-lock purchase to bar.
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
    # The universal trait cap (5), enforced here now that `BackgroundEntry.rating` no
    # longer carries it structurally — a hand-edited or older save could otherwise hold
    # an Artifact 10 with no rule to flag it. Every Background is held to it on BOTH
    # sides of the lock, EXCEPT where a rule explicitly raises it (Mountain Folk
    # Artifact ≤10, whose higher ceiling the loop above enforces). A rule that caps
    # LOWER (Backing ≤2) is chargen-only and falls away post-lock, so post-lock only
    # this cap holds it. A rule that caps a TOTAL (Sidereal Connections) is skipped
    # here — its own check above reads the summed rating against the attribute total.
    for bg in backgrounds:
        key = (bg.name or "").strip().lower()
        if not key:
            continue
        rule = budgets.background_rules.get(key)
        governs = rule is not None and (not post_lock or rule.bind_post_lock)
        # A rule may RAISE the universal cap; it may never REMOVE it. The earlier
        # version skipped this check whenever a rule merely EXISTED, which let the
        # rules that state no maximum at all — Alchemical Class (`min_rating`),
        # Alchemical Backing (`requires`), Illuminated Illumination (`min_rating`) —
        # lose the cap at chargen while keeping it post-lock.
        ceiling = (rule.max_rating if governs and rule.max_rating > merits.DOT_MAX
                   else merits.DOT_MAX)
        # Where the rule states its own LITERAL ceiling, that check has already spoken
        # (an above-origin-cap issue) and saying it twice for one row is noise.
        #
        # A TOTAL-cap rule is different and must NOT skip: `max_rating_is_attribute_sum`
        # reads `background_rating`, which SUMS every row sharing the name, so it has
        # nothing to say about one row. Sidereal Connections is capped at 5 per row like
        # every other Background (human's ruling 2026-08-12) while its printed total
        # binds across rows — two ceilings measuring two different things.
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
    """Whether THIS rule's Storyteller toggle lifts it for `character`.

    The toggle is the PER-CHARACTER `HouseRules` field named by `BackgroundRule.st_toggle`
    — R2's Sidereal Celestial Manse ≤3 and R3's mortal Artifact/Manse bar, both "without
    Storyteller permission". ONE read site, the `validate.foreign_charms_permitted`
    pattern: the UI never reaches into HouseRules for a name. `character` is optional —
    called without one, no permission, the rule binds. A toggle the field names but a
    HouseRules version lacks reads as False (graceful, like any dangling reference)."""
    if character is None or not rule.st_toggle:
        return False
    hr = character.house_rules
    if hr is None:
        return False
    return bool(getattr(hr, rule.st_toggle, False))


def background_rating_cap(budgets, character, name, *, post_lock=False) -> int:
    """The highest rating the Background `name` may be set to for THIS character on
    THIS side of the lock — the single engine-side answer the rating controls take
    their ceiling from (ui/advantages.py hardcoded 5 in both until 2026-08-12, which
    made the Mountain Folk Artifact lift unrecordable).

    A rating above this errors in `background_issues`; a control that offered more
    would be the cap you can click past, which is not a ceiling. Layers, most
    restrictive first:
      * a `barred` rule (rating must be 0), unless its `st_toggle` grants permission;
      * the rule's own `max_rating` ceiling;
      * DOT_MAX, the universal trait cap (5).

    ⚠ The Attribute-sum rule (Sidereal Connections) is NOT a layer here. It caps a
    TOTAL (Sidereals pp.106-108), so the per-row control keeps the universal ceiling and
    `background_issues` enforces the total — a row must never offer the whole attribute
    sum as pips.

    ⚠ Post-lock, only `bind_post_lock` ceilings apply. A chargen-only cap must NOT clamp
    the play control: the story may give a locked Unenlightened Mountain Folk Backing 4,
    or grant a mortal an artifact.
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
    """The Hearthstone allowance on every Manse Background row (S&S pp.66-67).

    p.67: "The sum of the levels of all the Hearthstones produced can never exceed the
    level of the Manse." A Manse may yield several stones rather than one (p.66), so the
    rule caps the TOTAL level, not the count; the Dragon-Blooded and Abyssal ladders add
    a ceiling on the largest single stone as well.

    ⚠ PER ROW, not per character. Two Manse rows are two Manses with separate
    allowances; summing them lets a Manse • and a Manse ••••• between them carry a
    level-5 stone on the wrong one.

    ⚠ Runs on BOTH sides of the lock (human's ruling). The allowance is keyed to a
    Background the story can raise or take away, so a chargen-only check falls silent
    exactly when the cap starts moving.

    The allowance comes from the BackgroundType, resolved through
    `background_catalogue_for` so a splat sees its OWN Manse variant — the six variants
    print six different allowances, and matching on the bare name would hand a
    Dragon-Blooded the corebook's linear one. A row whose name matches no catalogue
    entry (Backgrounds are free text) grows no stones, which is reported rather than
    ignored: it is the only way a stone can end up stranded on a row that cannot hold
    it, by renaming the row or flipping it to a Demesne after the fact.
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
