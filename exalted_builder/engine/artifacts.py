"""
engine/artifacts.py — individually rated artifacts, and the Background that budgets them.

Two printed rules need to point at ONE artifact rather than at the character's summed
Artifact Background, and neither could be expressed before this module existed:

  * **The Abyssal Artifact Background** (E:Ab p.131) is a BUDGET, not a cost curve.
    Its dots buy a pool of combined artifact rating plus, on the lower rows, a ceiling
    on any single item. Both halves need the individual ratings.
  * **Damaged Artifact** (PG p.38) limits its points to "the rating of the artifact it
    modifies". Checked against the summed Background, a character with a 4-dot daiklave
    and a 2-dot pair of wings could take the full three-point Flaw against the wings,
    because 4 + 2 − 1 ≥ 3.

The awkward part is that artifacts live in three places. Weapons and armour have
carried `artifact_rating` since long before this module, and re-entering a daiklave in
`Character.artifacts` would double-count it — so `artifact_items` is the ONE enumeration
that folds all three into a single keyed list, and every rule here reads that rather
than any one field. It is the same shape as `validate.charm_picks`: one enumeration, so
counting, pricing and display cannot disagree.

Nothing in this module is splat-specific. The p.131 table is DATA — the `budget_tiers`
rows on the loyal Abyssal's Artifact `BackgroundRule` — so a splat that prints no such
table gets an empty tuple and every check below becomes a no-op. That matters for
`Abyssal:fugitive` in particular: p.131 says renegades "use the Artifact Background
found in Chapter Four: Traits of the main Exalted rulebook", so the tiers must be absent
from that budget row rather than special-cased here.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..models.character import Character
from ..models.rules import BackgroundBudgetTier, BackgroundRule

# The Background that governs artifacts. Backgrounds are free text throughout this
# build, so it is matched by lowercased name like every other Background lookup.
ARTIFACT_BACKGROUND = "artifact"

# Item-key prefixes. A key is "<source>:<lowercased name>" — stable across a save,
# readable in a JSON file, and resolvable to nothing (gracefully) when the item it
# names has been renamed or deleted.
SOURCE_ARTIFACT = "artifact"
SOURCE_WEAPON = "weapon"
SOURCE_ARMOR = "armor"


class ArtifactItem(BaseModel):
    """One rated artifact the character owns, from any of the three places they live.

    A view, never stored: `key` is derived from the name, so renaming an artifact
    changes its key and any `MeritFlawPurchase.artifact_key` pointing at it stops
    resolving. That is deliberate and matches the soft-reference treatment Backgrounds
    already get — a dangling key reads as "no artifact chosen" and is reported, rather
    than silently attaching the Flaw to whatever item took the old name."""
    key: str
    name: str
    rating: int
    source: str                            # SOURCE_ARTIFACT / _WEAPON / _ARMOR


def item_key(source: str, name: str) -> str:
    """The stable key for an artifact of `source` called `name`."""
    return f"{source}:{name.strip().lower()}"


def artifact_items(character: Character) -> list[ArtifactItem]:
    """Every individually rated artifact the character owns, folded into one list.

    Standalone artifacts first (the book's own example — the tattered wings of the
    raptor — is neither weapon nor armour), then artifact weapons, then artifact
    armour. Mundane gear is skipped: `artifact_rating` 0 is the mundane default on
    both models, not a zero-dot artifact.

    Unnamed rows are skipped rather than keyed as "artifact:" — the editor adds a blank
    row for the player to fill in, and a blank row is not yet an artifact.
    """
    out: list[ArtifactItem] = []
    for art in character.artifacts:
        if art.name.strip():
            out.append(ArtifactItem(
                key=item_key(SOURCE_ARTIFACT, art.name), name=art.name,
                rating=art.rating, source=SOURCE_ARTIFACT,
            ))
    for source, gear in ((SOURCE_WEAPON, character.weapons),
                         (SOURCE_ARMOR, character.armor)):
        for item in gear:
            if item.artifact_rating > 0 and item.name.strip():
                out.append(ArtifactItem(
                    key=item_key(source, item.name), name=item.name,
                    rating=item.artifact_rating, source=source,
                ))
    return out


def find_item(character: Character, key: str) -> Optional[ArtifactItem]:
    """The artifact `key` names, or None when it resolves to nothing — a renamed or
    deleted item, or a purchase that has never chosen one."""
    if not key:
        return None
    for item in artifact_items(character):
        if item.key == key:
            return item
    return None


def combined_rating(character: Character) -> int:
    """Total artifact rating owned, which is what the p.131 budget caps."""
    return sum(item.rating for item in artifact_items(character))


def artifact_rule(budgets) -> Optional[BackgroundRule]:
    """The `BackgroundRule` governing Artifact under these budgets, or None. Split out
    so the UI can ask "does this character's splat budget artifacts?" without
    duplicating the lookup key."""
    return budgets.background_rules.get(ARTIFACT_BACKGROUND)


def acquisition_cost(budgets, rating: int) -> int:
    """What an artifact of `rating` COST to obtain, in Artifact Background dots.

    This is what Damaged Artifact's second clause measures against — "the number of
    Background and/or bonus points spent obtaining the artifact" (PG p.38) — and it is
    not the same number as the artifact's rating for every splat, which is the whole
    reason the clause exists. The Background's own text prints two multipliers, and the
    loyal Abyssal prints a table:

        Solar / core        1 dot buys 1 dot of artifact         cost = rating
        Dragon-Blooded      "twice the dots' worth"              cost = ceil(rating/2)
        Alchemical          "THREE dots of artifacts per dot"    cost = ceil(rating/3)
        Abyssal (loyal)     the p.131 budget table               cost = the cheapest row
                                                                 that permits it

    Measured PER ITEM IN ISOLATION — the cheapest Artifact rating that would permit this
    artifact on its own, ignoring anything else the character owns (human, rules
    authority, 2026-08-02). Nothing printed apportions a shared budget across the items
    inside it, and owning a ring alongside a daiklave does not make the daiklave dearer.

    ⚠ The tiers' `individual_max` IS respected here, which makes this disagree with the
    book's own worked example. p.38 prices the 4-dot tattered wings at two Abyssal
    Background points, reading only the combined maximum (Sound Gear allows a combined
    5); but Sound Gear also allows "none individually above Artifact 3", so 4-dot wings
    actually need Well-Equipped, and the answer is three. The example disregards its own
    table. **The human ruled 2026-08-02 that the table wins.**
    """
    rule = artifact_rule(budgets)
    if rule is None:
        return rating
    if rule.budget_tiers:
        permitted = [t.rating for t in sorted(rule.budget_tiers, key=lambda t: t.rating)
                     if t.combined_max >= rating
                     and (not t.individual_max or t.individual_max >= rating)]
        # Nothing permits it — the artifact is over even the top row. It still cost the
        # top row to get as close as the table allows; the budget check reports the
        # excess separately rather than this returning a number no dot count can reach.
        return permitted[0] if permitted else max(t.rating for t in rule.budget_tiers)
    per = rule.rating_per_dot
    return -(-rating // per)                   # ceiling division


def tier_label(rating: int, tier: BackgroundBudgetTier) -> str:
    """How a budget row is named back to the player: "Artifact 3 (Well-Equipped)", or
    plain "Artifact 3" where the printed table names no rows.

    A `BackgroundBudgetTier.name` is optional and the second table to arrive had none:
    the loyal Abyssal's five rows are labelled (E:Ab p.131), the Cult of the
    Illuminated's are bare dot rows (Cult p.96). Interpolating the empty name gave
    "Artifact 3 ()" in the budget Issues and a trailing comma in the panel header, so
    both read it through here rather than formatting the name themselves."""
    return f"Artifact {rating} ({tier.name})" if tier.name else f"Artifact {rating}"


def budget_tier(budgets, rating: int) -> Optional[BackgroundBudgetTier]:
    """The budget row for Artifact at `rating` dots, or None when this splat prints no
    budget table (every splat but the loyal Abyssal) or the rating has no row.

    An Artifact rating ABOVE the highest printed row takes that row — the table stops
    at five because Backgrounds do, so there is nothing above it to fall off. A rating
    of 0 with no explicit row is None: owning no Artifact Background is not a budget of
    zero to be reported against, it is the ordinary case of owning no artifacts, and
    `budget_issues` reports the mismatch itself."""
    rule = artifact_rule(budgets)
    if rule is None or not rule.budget_tiers:
        return None
    exact = [t for t in rule.budget_tiers if t.rating == rating]
    if exact:
        return exact[0]
    below = [t for t in rule.budget_tiers if t.rating < rating]
    return max(below, key=lambda t: t.rating) if below else None
