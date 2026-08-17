"""
engine/validate/artifact_checks.py — artifact legality and the Artifact budget.

⚠ Named `artifact_checks`, not `artifacts`, deliberately: this module reads
`engine/artifacts.py` throughout as `artifacts.X`, and a sibling called
`validate/artifacts.py` would make every one of those references ambiguous to a
reader and to grep. The rating/soak MECHANICS live in `engine/artifacts.py`; only
the legality checks are here.

Owns `check_artifacts` and its three helpers: the Background-funded budget
(E:Ab p.131), the chargen purchase bar, and the corebook single-artifact default.

⚠ Artifacts have THREE acquisition channels (decision 0017, amended 2026-08-13/14),
and only the first is budgeted:
  1. the **Artifact Background** — pre-game, "to start the game owning" (core p.342);
  2. **cash** in play (M&C pp.122-125), barred at chargen;
  3. the **Legendary Artifact 10-pt Merit** — five plot devices printing
     "(ARTIFACT N/A)", charged to no budget at all.

⚠ ONE ARTIFACT PER BACKGROUND ROW. Two Artifact •• rows are two artifacts, not one
•••• — which is why this reads `background_rows`, never `background_rating`.

⚠ The Merit-gated bar keys on the artifact NAME, not on the player-editable
`acquired` field. `ArtifactType.requires_merit` is DATA precisely so no module here
names a Merit id (decision 0011).
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import RuleSet
from .. import artifacts
from ._base import Issue, effective_budgets
from .backgrounds import background_rating, background_rows


def _purchased_at_chargen_issues(character: Character) -> list[Issue]:
    """Artifacts may not be BOUGHT during character creation (human's ruling
    2026-08-13).

    The corebook defines the Artifact column of every gear table as "the number of dots
    in the Artifact Background the character must spend TO START THE GAME OWNING one of
    these" (p.342; p.345 for armour), so the Background is the pre-game channel and cash
    is the in-play one. Without this, `acquired` would be a hole straight through the
    budget at exactly the phase the budget exists for: a player could mark every artifact
    purchased and start play with a hoard the Background never paid for.

    Post-lock it is silent — buying an artifact with money is the whole point of the
    other channel, and Resources is a hint rather than a validation (core p.325).
    """
    if character.chargen_locked:
        return []
    bought = artifacts.purchased_items(character)
    if not bought:
        return []
    return [Issue(
        code="artifact-purchased-at-chargen", where=item.name,
        message=(f"{item.name} is marked as purchased, but artifacts are bought with "
                 f"cash only in play; at creation the Artifact Background is what "
                 f"buys them (core p.342)."),
    ) for item in bought]


def _missing_merit_issues(ruleset, character: Character) -> list[Issue]:
    """Owning a plot-device artifact without the Merit that is its whole price.

    The Mantle of Brigid and the Sword of Ice (BoTC pp.25-27) print "(ARTIFACT N/A)" —
    no Background buys them, so no budget can catch them, and without this check they
    would be the one thing in the catalogue that is free. The human's ruling
    2026-08-13 is that they cost the Legendary Artifact 10-pt Merit; this is the bar,
    and `artifacts.purchasable_artifacts` is the matching OFFER.

    Runs on BOTH sides of the lock, like every other artifact rule, and for the reason
    the house bug keeps teaching: the Merit can be dropped after creation as easily as
    it can be skipped during it, and a chargen-only check would go quiet exactly then.
    Which Merit is DATA (`ArtifactType.requires_merit`) — no id is named here.
    """
    issues: list[Issue] = []
    for name, merit_id in artifacts.missing_merits(ruleset.artifact_catalog, character):
        merit = ruleset.merits_flaws.get(merit_id)
        label = merit.name if merit is not None else merit_id
        issues.append(Issue(
            code="artifact-missing-merit", where=name,
            message=(f"{name} is a plot device rather than a rated artifact — it is "
                     f"owned through the {label} Merit, which this character does not "
                     f"have."),
        ))
    return issues


def _corebook_artifact_issues(items: list, rows: list[int]) -> list[Issue]:
    """The corebook Artifact Background: ONE artifact per Background ROW, each rated no
    higher than its own row (human's rulings 2026-07-31 and 2026-08-13).

    The rule every splat gets unless its own book prints something else, so this is the
    branch that runs for plain Solars, Lunars, Sidereals, Ghosts, Godblooded and the
    Abyssal renegade.

    ⚠ **Per ROW, not per summed rating.** The first cut read the summed Background and
    demanded exactly one artifact, so a character holding two Artifact •• Backgrounds
    and two daiklaves was told "Artifact 4 permits ONE artifact rated no higher than 4"
    (found in the browser, 2026-08-13). That contradicted an interpretation this build
    had already recorded — `background_best`'s docstring says in as many words that
    "two Artifacts at 2 dots each are two artifacts, not one artifact at 4", which is
    why Damaged Artifact reads the best row rather than the sum. Two rulings, one of
    them months old, and the new code agreed with neither.

    Rows and items are matched largest-first: the biggest artifact must fit the biggest
    row. That is the only assignment that can succeed if any can — a smaller artifact
    fits anywhere a larger one does — so a greedy pass is exact here, not an
    approximation.

    Both findings are ERRORS, not warnings: the corebook ladder carries no "without
    Storyteller permission" clause, which is what made the Abyssal per-item cap a
    warning.
    """
    owned = sorted(items, key=lambda i: i.rating, reverse=True)
    ladder = sorted((r for r in rows if r > 0), reverse=True)
    if not ladder:
        return [Issue(
            code="artifact-without-background", where="Artifact",
            message=f"This character owns {len(owned)} artifact(s) but has no Artifact "
                    f"Background; artifacts are bought with its dots.",
        )] if owned else []

    issues: list[Issue] = []
    for item, row in zip(owned, ladder):
        if item.rating > row:
            issues.append(Issue(
                code="artifact-item-over-background", where=item.name,
                message=f"Artifact {row} permits no artifact rated above {row}; "
                        f"{item.name} is {item.rating}.",
            ))
    if len(owned) > len(ladder):
        allowed = ("one artifact" if len(ladder) == 1
                   else f"{len(ladder)} artifacts, one per Artifact Background")
        issues.append(Issue(
            code="artifact-over-background-dots", where="Artifact",
            message=f"Artifact {'+'.join(str(r) for r in ladder)} permits {allowed} "
                    f"({', '.join('rated up to ' + str(r) for r in ladder)}); this "
                    f"character owns {len(owned)} "
                    f"({', '.join(i.name for i in owned)}).",
        ))
    return issues


def check_artifacts(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The p.131 Artifact BUDGET: combined rating and per-item ceiling, keyed by the
    character's Artifact Background rating (E:Ab p.131).

    Runs on BOTH sides of the lock, following `check_fetters_and_passions` — and for
    the same reason. The budget is keyed to a Background that experience can raise, so
    the ceiling MOVES: a loyal Abyssal who buys Artifact ••• with XP may hold a combined
    7, and one who has an artifact taken away is under budget rather than over. A
    chargen-only check would go quiet exactly when the cap started changing. This is
    also why artifacts are absent from `ChargenSnapshot`, which weapons and armour
    already are.

    Three rules, one per branch: the printed TIER table (loyal Abyssal, Illuminated),
    the MULTIPLIER (DB and Dragon-Kings at two dots per dot, Alchemical at three), and
    otherwise the COREBOOK default — see `_corebook_artifact_issues`. Only the last is
    reachable without a `BackgroundRule` at all, which is why the `rule is None` early
    return above became a fallback rather than an exit. A no-op for anyone owning no
    artifacts, which is most characters.

    The tiered branch's three findings:
      * owning artifacts with no Artifact Background at all,
      * combined rating over the row's `combined_max`,
      * a single item over the row's `individual_max` (the lower rows only). The page
        makes these ST-overridable — "without Storyteller permission" — so they are
        reported as warnings rather than errors; the combined budget is not.
    """
    issues: list[Issue] = []
    # The BUDGET counts what the Artifact Background bought. A purchased artifact is
    # equipment paid for in cash and is charged to nothing here — see
    # `artifacts.budgeted_items` and the ruling in `ArtifactEntry.acquired`. The chargen
    # bar below is what stops that being a free pass at creation.
    issues += _purchased_at_chargen_issues(character)
    # The merit-gated plot devices are charged to no budget at all, so this must run
    # before the `not items` early return below — a character who owns nothing BUT a
    # Mantle of Brigid has an empty budgeted list and still needs the Merit.
    issues += _missing_merit_issues(ruleset, character)
    items = artifacts.budgeted_items(character)
    if not items:
        return issues
    budgets = effective_budgets(ruleset, character)
    rule = artifacts.artifact_rule(budgets)
    rating = background_rating(character.backgrounds, artifacts.ARTIFACT_BACKGROUND)
    # A splat with no Artifact rule at all (plain Solar, Lunar, Sidereal, Ghost,
    # Godblooded, the Abyssal renegade who "uses the Artifact Background found in
    # Chapter Four", p.131) falls back to the COREBOOK rule, which is not "no budget".
    # Human ruling 2026-08-13: the corebook default is ONE artifact, rated no higher
    # than the Background — every rung of the printed ladder describes a single item
    # ("A useful item, a weapon or suit of armor"), and the splats that hand out
    # several (DB, Dragon-Kings, Mountain Folk, Alchemical) are exactly the ones whose
    # own ladder says so. This branch used to `return issues`, which meant a Solar
    # could hold five daiklaves on Artifact 0 in silence.
    if artifacts.uses_corebook_rule(rule):
        # …unless this splat DOES print a rule and the character simply has not reached
        # the row that carries it — a Mountain Folk with no Enlightenment chosen. See
        # `artifacts.splat_prints_its_own_rule`: silence beats the wrong rule.
        if rule is None and artifacts.rule_is_pending_an_origin(
                ruleset, character.exalt_type, character.origin):
            return issues
        return issues + _corebook_artifact_issues(
            items, background_rows(character.backgrounds,
                                   artifacts.ARTIFACT_BACKGROUND))
    if rule.budget_tiers:
        tier = artifacts.budget_tier(budgets, rating)
        if tier is None:
            issues.append(Issue(
                code="artifact-without-background", where="Artifact",
                message=f"This character owns {len(items)} artifact(s) but has no Artifact "
                        f"Background; artifacts are bought with its dots.",
            ))
            return issues
        combined = sum(i.rating for i in items)
        if combined > tier.combined_max:
            issues.append(Issue(
                code="artifact-combined-over-budget", where="Artifact",
                message=f"{artifacts.tier_label(rating, tier)} allows a combined rating "
                        f"no higher than {tier.combined_max}; this character owns "
                        f"{combined}.",
            ))
        if tier.individual_max:
            for item in items:
                if item.rating > tier.individual_max:
                    issues.append(Issue(
                        severity="warning",
                        code="artifact-item-over-cap", where=item.name,
                        message=f"{artifacts.tier_label(rating, tier)} allows no single "
                                f"artifact above {tier.individual_max} without Storyteller "
                                f"permission; {item.name} is {item.rating}.",
                    ))
        return issues
    # The multiplier rule (DB/DK "twice the dots' worth" p.176, Alchemical three):
    # each Background dot buys `rating_per_dot` dots of artifact, capping the combined
    # rating at background × rating_per_dot. This was data-only — never enforced —
    # before this check; a Dragon King with Artifact • and a 3-dot artifact passed
    # silently. rating_per_dot 1 (a rule with no multiplier) is the Solar default and
    # imposes nothing.
    if rule.rating_per_dot > 1:
        combined = artifacts.combined_rating(character)
        if rating == 0:
            issues.append(Issue(
                code="artifact-without-background", where="Artifact",
                message=f"This character owns {len(items)} artifact(s) but has no Artifact "
                        f"Background; artifacts are bought with its dots.",
            ))
        else:
            cap = rating * rule.rating_per_dot
            if combined > cap:
                issues.append(Issue(
                    code="artifact-over-background-dots", where="Artifact",
                    message=f"Artifact {rating} buys {cap} dots of artifacts "
                            f"({rule.rating_per_dot} per dot, p.176); this character "
                            f"owns combined rating {combined}.",
                ))
            # Human ruling 2026-08-05 (via a 1e-experienced source): the doubled rule
            # is "you get (Rating x 2) artifact dots to spread around, with no one
            # artifact having a rating higher than (Background rating)". So a 4-dot
            # artifact needs Artifact 4 even though the doubled budget would fit it.
            # Applies to the doubled rule (DB/DK, rating_per_dot 2); Alchemical's
            # "three dots per dot" is left to the combined cap, whose per-item shape
            # this code does not have a source for.
            if rule.rating_per_dot == 2:
                for item in items:
                    if item.rating > rating:
                        issues.append(Issue(
                            code="artifact-item-over-background", where=item.name,
                            message=f"Artifact {rating} permits no single artifact rated "
                                    f"above {rating} (p.176); {item.name} is "
                                    f"{item.rating}.",
                        ))
                # Human correction 2026-08-05: only ONE artifact may be rated AT the
                # Background rating (the flagship) — the rest are smaller. Artifact 5
                # + [5,5] is two flagships and invalid; Artifact 5 + [4,1] is the
                # intended shape (flagship plus smaller artifacts).
                if sum(1 for i in items if i.rating == rating) > 1:
                    issues.append(Issue(
                        code="artifact-two-flagships", where="Artifact",
                        message=f"Artifact {rating} permits only one artifact rated at "
                                f"{rating}; {sum(1 for i in items if i.rating == rating)} "
                                f"are rated {rating}.",
                    ))
    return issues
