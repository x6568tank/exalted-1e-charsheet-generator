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

# The Background a Hearthstone comes with. A stone is a rated object like any other in
# `data/artifacts.json`, but its dots are the MANSE's rating, not Artifact dots — see
# `ArtifactType.background`.
MANSE_BACKGROUND = "manse"

# Item-key prefixes. A key is "<source>:<lowercased name>" — stable across a save,
# readable in a JSON file, and resolvable to nothing (gracefully) when the item it
# names has been renamed or deleted.
# How an item was acquired — see `models.character.ArtifactEntry.acquired`. The
# Background is the pre-game channel ("to start the game owning", core p.342); cash is
# the in-play one (Manacle and Coin pp.122-125). Only the first is charged to the
# budget.
ACQUIRED_BACKGROUND = "background"
ACQUIRED_PURCHASED = "purchased"
# The third channel (human's ruling 2026-08-13): a plot-device artifact that prints
# "(ARTIFACT N/A)" and is paid for with the Legendary Artifact 10-pt Merit rather than
# with dots of anything. Charged to no budget, exactly like a purchased item, but for
# the opposite reason — not "you bought it with money" but "there is no rating to
# charge". See `rules.ArtifactType.requires_merit`.
ACQUIRED_LEGENDARY = "legendary"

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
    acquired: str = ACQUIRED_BACKGROUND    # ACQUIRED_BACKGROUND / _PURCHASED


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
                rating=art.rating, source=SOURCE_ARTIFACT, acquired=art.acquired,
            ))
    # A gear row that is the stat line of a standalone artifact is the SAME OBJECT, and
    # counting it again would charge the budget twice for one daiklave — see
    # `Weapon.from_artifact`. Resolved against the keys just collected rather than
    # trusting the stored flag: an orphaned link (the artifact renamed or deleted) makes
    # the gear count on its own, so the failure mode is a visible artifact rather than a
    # free one. Same graceful-unresolvable-id contract `find_item` gives its callers.
    owned = {item.key for item in out}
    for source, gear in ((SOURCE_WEAPON, character.weapons),
                         (SOURCE_ARMOR, character.armor)):
        for item in gear:
            if item.artifact_rating > 0 and item.name.strip():
                if item.from_artifact and item.from_artifact in owned:
                    continue
                out.append(ArtifactItem(
                    key=item_key(source, item.name), name=item.name,
                    rating=item.artifact_rating, source=source,
                    acquired=item.acquired,
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


def gear_stat_line(ruleset, name: str):
    """The catalogue weapon or armour that IS this artifact, as `(source, entry)`, or
    None when the artifact is neither.

    Twenty of the 222 catalogue artifacts are also gear rows — Daiklave, Grand Daiklave,
    Myrmidon Carapace — because an artifact entry describes what a thing IS and a gear
    row carries what it DOES, and a daiklave needs both. Matched on the normalised name,
    which is the same soft reference `item_key` already uses; a catalogue whose two
    halves disagree about a name simply grants nothing, rather than guessing.

    Only artifact-rated gear qualifies. A mundane row sharing a name with an artifact
    would otherwise be granted as that artifact's stat line and then excluded from the
    budget by `artifact_items` — a mundane hatchet quietly cancelling a real one.
    """
    want = name.strip().lower()
    if not want:
        return None
    for source, catalog in ((SOURCE_WEAPON, ruleset.weapon_catalog),
                            (SOURCE_ARMOR, ruleset.armor_catalog)):
        for entry in catalog.values():
            if entry.name.strip().lower() == want and entry.artifact_rating > 0:
                return source, entry
    return None


def uses_corebook_rule(rule) -> bool:
    """Whether this splat gets the COREBOOK Artifact Background — one artifact, rated
    no higher than the Background (human ruling 2026-08-13).

    True when the splat's book alters nothing: no rule row at all (plain Solar, Lunar,
    Sidereal, Ghost, Godblooded, the Abyssal renegade), or a row that prints neither a
    tier table nor a multiplier. One predicate rather than two copies of the condition,
    because the validator and the on-screen budget line have to agree about which rule
    is running — a header that says nothing while the validator raises an error is the
    shape that has bitten this area before.
    """
    return rule is None or (not rule.budget_tiers and rule.rating_per_dot <= 1)


def rule_is_pending_an_origin(ruleset, exalt_type: str, origin: str) -> bool:
    """Whether this character resolves to no Artifact rule only because they have not
    chosen an ORIGIN yet — in which case nothing should be judged.

    The guard on the corebook fallback, and it exists because of the Mountain Folk:
    theirs is the one splat with NO base budget row, only `Mountain-Folk:enlightened`
    and `:unenlightened`, both carrying the doubled rule. A Mountain Folk who has not
    yet chosen an Enlightenment — a fresh character, or a save written before the axis
    — resolves to no rule at all, and handing them the corebook's one-artifact limit
    would enforce a rule their own book overrides.

    All three conditions are load-bearing, and the middle one is the one that bit:

    * an origin already chosen means the cascade RESOLVED, and whatever it found (rule
      or no rule) is this character's answer;
    * a splat with a BASE row has also resolved — a plain Solar is a finished thing,
      not a half-built Illuminated one. Without this clause `Solar:illuminated`'s tier
      table counted as "the splat prints a rule" and switched the corebook default off
      for every ordinary Solar, which is the whole feature;
    * and only then does an origin row carrying a rule mean the character is
      mid-build.

    Applying the wrong rule is worse than applying none, which is why this is silence
    rather than a best guess. It is separate from `uses_corebook_rule` because that one
    answers a question about the SPLAT and this one about the CHARACTER.
    """
    if origin or exalt_type in ruleset.budgets:
        return False
    prefix = f"{exalt_type}:"
    return any(key.startswith(prefix) and artifact_rule(budgets) is not None
               for key, budgets in ruleset.budgets.items())


def purchasable_with_artifact(catalog) -> list:
    """The catalogue entries the Artifact Background actually buys, sorted by name.

    `data/artifacts.json` is the catalogue of RATED OBJECTS, which since the corebook
    Hearthstones (pp.338-340) landed is not the same set as the objects Artifact dots
    pay for: a Hearthstone's rating is the rating of the Manse that grew it, and it
    arrives with the Manse Background. Both surfaces that spend Artifact dots — the
    artifact row's name combobox and its catalogue dialog — filter through here, so a
    stone can never be picked into `Character.artifacts` and charged against the p.131
    budget. `ArtifactType.background` defaults to "artifact", so every entry authored
    before the field existed keeps its old behaviour.
    """
    return sorted((a for a in catalog.values()
                   if a.background == ARTIFACT_BACKGROUND and not a.requires_merit),
                  key=lambda a: a.name)


def merit_gated(catalog) -> list:
    """The catalogue entries a MERIT unlocks rather than a Background — the plot
    devices printed "(ARTIFACT N/A)". Sorted by name, like its sibling above.

    Kept apart from `purchasable_with_artifact` for the reason the Hearthstones were:
    an entry no Background pays for must never reach a surface that spends Background
    dots, or picking it charges a budget for something that budget never bought.
    """
    return sorted((a for a in catalog.values() if a.requires_merit),
                  key=lambda a: a.name)


def held_merit_ids(character: Character) -> set:
    """The Merit/Flaw ids this character holds. Generic by construction — no module
    outside `engine/merits.py` may NAME a Merit id (decision 0011), so the gating field
    lives in data and every comparison here is against whatever it happens to say."""
    return {p.merit_id for p in character.merits_flaws if p.merit_id}


def purchasable_artifacts(catalog, character: Character) -> list:
    """What this character may actually pick: everything the Artifact Background buys,
    plus the merit-gated entries whose Merit she already holds.

    The offer moves with the permission — a Merit the character does not hold hides its
    artifact, and taking the Merit reveals it. Backgrounds taught this: a permission
    toggle that moves the BAR but not the OFFER leaves the player unable to find the
    thing she was just allowed, which is worse than no toggle at all.
    """
    held = held_merit_ids(character)
    return sorted(purchasable_with_artifact(catalog)
                  + [a for a in merit_gated(catalog) if a.requires_merit in held],
                  key=lambda a: a.name)


def missing_merits(catalog, character: Character) -> list:
    """(artifact name, required merit id) for every owned artifact whose catalogue entry
    is merit-gated and whose Merit the character does not hold.

    Keys on the NAME against the catalogue rather than on `ArtifactEntry.acquired`,
    which is player-editable: a discriminator anything on the screen can write is not a
    discriminator (the catalogue-dialog lesson). Renaming the row IS how you disclaim
    the artifact, and that is fine — the row then names something else.
    """
    held = held_merit_ids(character)
    by_name = {a.name.casefold(): a for a in catalog.values() if a.requires_merit}
    out = []
    for art in character.artifacts:
        entry = by_name.get((art.name or "").casefold())
        if entry is not None and entry.requires_merit not in held:
            out.append((entry.name, entry.requires_merit))
    return out


def hearthstones(catalog) -> list:
    """The catalogue entries the MANSE Background brings, sorted by name — the other
    half of `purchasable_with_artifact`."""
    return sorted((a for a in catalog.values() if a.background == MANSE_BACKGROUND),
                  key=lambda a: a.name)


class HearthstoneAllowance(BaseModel):
    """What one Manse Background row at a given rating may hold in Hearthstones.

    `individual_max` 0 means "no ceiling beyond the combined one", matching
    `BackgroundBudgetTier`; `max_items` 0 means the page states no count. Resolved from
    the BackgroundType so both the validator and the picker read the same numbers —
    the picker greys the stones this says are too large, and greying a stone the
    validator would have accepted (or the reverse) is the failure mode that split
    control from rule here in the first place."""
    combined_max: int
    individual_max: int = 0
    max_items: int = 0
    tier_name: str = ""


def grows_hearthstones(bg_type) -> bool:
    """Whether this Background produces Hearthstones at all — the ONE test, replacing
    the `"manse" in name.lower()` substring the first cut used.

    The substring was not merely inelegant: it is a free-text NAME, so a row typed
    "Manse (destroyed)" grew stones and a Sidereal row renamed by its table stopped,
    and it could say nothing about HOW MANY levels the row carries, which differs per
    splat. A Background that authors neither field grows nothing, so every non-Manse
    entry in the catalogue is unaffected without being listed anywhere."""
    return bool(bg_type is not None
                and (bg_type.hearthstone_tiers or bg_type.hearthstone_per_dot))


def hearthstone_allowance(bg_type, rating: int) -> Optional[HearthstoneAllowance]:
    """The allowance for `bg_type` at `rating` dots, or None when this Background grows
    no stones.

    Tiers win over the linear rate where a Background authors both (nothing does). A
    rating with no exact tier row takes the highest row BELOW it — the same treatment
    `budget_tier` gives the Artifact table, and for the same reason: the printed tables
    stop at five because Backgrounds do, so there is nothing above the top row to fall
    off. A rating below every row (i.e. 0) yields a zero allowance rather than None:
    owning Manse 0 is owning no Manse, and a stone on it is a real finding, not an
    absent rule."""
    if not grows_hearthstones(bg_type):
        return None
    if bg_type.hearthstone_tiers:
        at_or_below = [t for t in bg_type.hearthstone_tiers if t.rating <= rating]
        if not at_or_below:
            return HearthstoneAllowance(combined_max=0)
        tier = max(at_or_below, key=lambda t: t.rating)
        return HearthstoneAllowance(combined_max=tier.combined_max,
                                    individual_max=tier.individual_max,
                                    max_items=tier.max_items, tier_name=tier.name)
    total = rating * bg_type.hearthstone_per_dot
    # A linear Manse may put its whole allowance into one stone (S&S p.66: a Manse
    # "either produces a single Hearthstone at the same level as the Manse or multiple
    # Hearthstones that, combined, are equal in level"), so the individual ceiling is
    # the combined one and is left at 0 rather than restated.
    return HearthstoneAllowance(combined_max=total)


def hearthstone_total(bg) -> int:
    """Levels of Hearthstone held on one Background row — the number S&S p.67 caps."""
    return sum(stone.rating for stone in bg.hearthstones)


def budgeted_items(character: Character) -> list[ArtifactItem]:
    """The artifacts the Artifact Background actually PAID FOR — everything owned,
    minus what was bought with cash (human's ruling 2026-08-13).

    Split from `artifact_items` rather than replacing it, because the two questions are
    different and only one of them is about money. The BUDGET asks what the Background
    bought; Damaged Artifact, the sheet and the picker ask what the character OWNS, and
    a purchased daiklave can be damaged, wielded and displayed like any other. Every
    budget read site goes through here; nothing else should.
    """
    return [i for i in artifact_items(character)
            if i.acquired not in (ACQUIRED_PURCHASED, ACQUIRED_LEGENDARY)]


def purchased_items(character: Character) -> list[ArtifactItem]:
    """The other half — artifacts acquired with cash rather than Background dots."""
    return [i for i in artifact_items(character)
            if i.acquired == ACQUIRED_PURCHASED]


def combined_rating(character: Character) -> int:
    """Total artifact rating the Background is charged for, which is what the p.131
    budget caps. Purchased artifacts are excluded — see `budgeted_items`."""
    return sum(item.rating for item in budgeted_items(character))


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
