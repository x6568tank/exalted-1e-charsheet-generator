"""
engine/artifacts.py — individually rated artifacts, and the Background that budgets them.

Two printed rules need the rating of ONE artifact, not the summed Artifact
Background:

  * **The Abyssal Artifact Background** (E:Ab p.131) is a BUDGET: a combined rating,
    and on the lower rows a ceiling on one item.
  * **Damaged Artifact** (PG p.38) limits its points to the rating of the artifact
    that it modifies.

Artifacts are in three lists: `Character.artifacts`, weapons and armor.
`artifact_items` is the ONE enumeration of all three. Each rule here reads it.

Nothing here is splat-specific. The p.131 table is the `budget_tiers` data of the
loyal Abyssal Artifact `BackgroundRule`. With no table, each check does nothing.
⚠ `Abyssal:fugitive` must not carry the tiers (p.131).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..models.character import Character
from ..models.rules import BackgroundBudgetTier, BackgroundRule

# The Background of artifacts, matched by lowercased name.
ARTIFACT_BACKGROUND = "artifact"

# The Background of a Hearthstone. See `ArtifactType.background`.
MANSE_BACKGROUND = "manse"

# Item-key prefixes. A key is "<source>:<lowercased name>". A key of a renamed or
# deleted item resolves to nothing.
# The acquisition channel (decision 0017). See `models.character.ArtifactEntry.acquired`.
# Background: pre-game (core p.342). Cash: in play (Manacle and Coin pp.122-125).
# Only the Background channel counts against the budget.
ACQUIRED_BACKGROUND = "background"
ACQUIRED_PURCHASED = "purchased"
# The Legendary Artifact Merit channel (human's ruling). Counts against no budget.
# See `rules.ArtifactType.requires_merit`.
ACQUIRED_LEGENDARY = "legendary"

SOURCE_ARTIFACT = "artifact"
SOURCE_WEAPON = "weapon"
SOURCE_ARMOR = "armor"


class ArtifactItem(BaseModel):
    """One rated artifact that the character owns, from one of the three lists.

    A view, not stored. `key` derives from the name, thus a rename breaks a
    `MeritFlawPurchase.artifact_key`. Validate then reports "no artifact chosen"."""
    key: str
    name: str
    rating: int
    source: str                            # SOURCE_ARTIFACT / _WEAPON / _ARMOR
    acquired: str = ACQUIRED_BACKGROUND    # ACQUIRED_BACKGROUND / _PURCHASED
    # The commitment, from the row that owns it. ⚠ A mote derivation must read
    # `artifact_items`, not the three lists.
    attunement: int = 0
    attuned: bool = False
    attuned_pool: str = "peripheral"
    # The material id, or "". `derive.committed_attunement` reads it (core p.341).
    # ⚠ ALWAYS "" for a standalone `ArtifactEntry`: that model has no material field.
    material: str = ""


def item_key(source: str, name: str) -> str:
    """Return the key of the artifact `name` from `source`."""
    return f"{source}:{name.strip().lower()}"


def artifact_items(character: Character) -> list[ArtifactItem]:
    """Return all rated artifacts of the character in one list.

    Order: standalone artifacts, artifact weapons, artifact armor. Skips mundane
    gear (`artifact_rating` 0) and unnamed rows.
    """
    out: list[ArtifactItem] = []
    for art in character.artifacts:
        if art.name.strip():
            key = item_key(SOURCE_ARTIFACT, art.name)
            # ⚠ If a gear stat line exists, the commitment comes from the gear row
            # (human's ruling). Else a linked daiklave commits its motes two times.
            commitment = stat_line_row(character, key) or art
            out.append(ArtifactItem(
                key=key, name=art.name,
                rating=art.rating, source=SOURCE_ARTIFACT, acquired=art.acquired,
                attunement=commitment.attunement, attuned=commitment.attuned,
                attuned_pool=commitment.attuned_pool,
                material=getattr(commitment, "material", ""),
            ))
    # A gear row that is the stat line of a standalone artifact is the same
    # object: skip it (`Weapon.from_artifact`). Check against the collected keys: an
    # orphaned link counts as its own item.
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
                    acquired=item.acquired, attunement=item.attunement,
                    attuned=item.attuned, attuned_pool=item.attuned_pool,
                    material=item.material,
                ))
    return out


def stat_line_row(character: Character, key: str):
    """Return the `Weapon`/`Armor` row that is the stat line of the artifact `key`.
    Return None if it has none. Returns the FIRST match.
    """
    if not key:
        return None
    for item in (*character.weapons, *character.armor):
        if item.from_artifact == key:
            return item
    return None


def find_item(character: Character, key: str) -> Optional[ArtifactItem]:
    """Return the artifact of `key`, or None if it resolves to nothing."""
    if not key:
        return None
    for item in artifact_items(character):
        if item.key == key:
            return item
    return None


def gear_stat_line(ruleset, name: str):
    """Return `(source, entry)`: the catalogue weapon or armor of the artifact `name`.
    Return None if it is neither. Matches the normalized name.

    ⚠ Only artifact-rated gear matches. Else a mundane row with the same name
    becomes the stat line, and `artifact_items` removes the real artifact.
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
    """Return True if the splat uses the core Artifact Background: one artifact,
    rated no higher than the Background (human's ruling). True for no rule row, or a
    row with no tier table and no multiplier.

    ⚠ The validator and the budget line must both use this predicate.
    """
    return rule is None or (not rule.budget_tiers and rule.rating_per_dot <= 1)


def rule_is_pending_an_origin(ruleset, exalt_type: str, origin: str) -> bool:
    """Return True if the character has no Artifact rule only because the ORIGIN is
    not selected. Then nothing is checked.

    Example: the Mountain Folk have no base budget row, only origin rows.

    ⚠ All three conditions are necessary:

    * an origin is selected: the result of the key order is the answer;
    * the splat has a BASE row: the answer is final. Without this clause the
      `Solar:illuminated` tiers turn off the core default for each ordinary Solar;
    * an origin row has a rule: the character is incomplete.
    """
    if origin or exalt_type in ruleset.budgets:
        return False
    prefix = f"{exalt_type}:"
    return any(key.startswith(prefix) and artifact_rule(budgets) is not None
               for key, budgets in ruleset.budgets.items())


def purchasable_with_artifact(catalog) -> list:
    """Return the catalogue entries that the Artifact Background buys, by name.

    ⚠ A Hearthstone (pp.338-340) comes with the Manse Background. Both Artifact
    surfaces (the name combobox and the catalogue dialog) use this filter, thus a
    stone never counts against the p.131 budget.
    """
    return sorted((a for a in catalog.values()
                   if a.background == ARTIFACT_BACKGROUND and not a.requires_merit),
                  key=lambda a: a.name)


def merit_gated(catalog) -> list:
    """Return the catalogue entries that a MERIT unlocks ("ARTIFACT N/A"), by name.
    ⚠ They must never reach a surface that spends Background dots.
    """
    return sorted((a for a in catalog.values() if a.requires_merit),
                  key=lambda a: a.name)


def held_merit_ids(character: Character) -> set:
    """Return the Merit/Flaw ids that the character holds (decision 0011)."""
    return {p.merit_id for p in character.merits_flaws if p.merit_id}


def purchasable_artifacts(catalog, character: Character) -> list:
    """Return the entries that the character can select: the Artifact entries,
    plus the Merit-gated entries whose Merit is held.

    ⚠ The offer follows the permission. Else the player cannot find an allowed item.
    """
    held = held_merit_ids(character)
    return sorted(purchasable_with_artifact(catalog)
                  + [a for a in merit_gated(catalog) if a.requires_merit in held],
                  key=lambda a: a.name)


def missing_merits(catalog, character: Character) -> list:
    """Return (artifact name, required merit id) for each owned Merit-gated artifact
    whose Merit is not held.

    Uses the NAME against the catalogue, not the player-editable
    `ArtifactEntry.acquired`.
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
    """Return the catalogue entries of the MANSE Background, by name."""
    return sorted((a for a in catalog.values() if a.background == MANSE_BACKGROUND),
                  key=lambda a: a.name)


class HearthstoneAllowance(BaseModel):
    """The Hearthstones that one Manse row at a rating can hold.

    `individual_max` 0 = no ceiling except the combined one. `max_items` 0 = no
    printed count.

    ⚠ Resolved from the BackgroundType: the validator and the picker read the SAME
    numbers."""
    combined_max: int
    individual_max: int = 0
    max_items: int = 0
    tier_name: str = ""


def grows_hearthstones(bg_type) -> bool:
    """Return True if the Background produces Hearthstones. The ONE test.

    ⚠ Never test the NAME. Backgrounds are free text, and the levels differ by splat."""
    return bool(bg_type is not None
                and (bg_type.hearthstone_tiers or bg_type.hearthstone_per_dot))


def hearthstone_allowance(bg_type, rating: int) -> Optional[HearthstoneAllowance]:
    """Return the allowance of `bg_type` at `rating`, or None if it grows no stones.

    Tiers win over the linear rate. A rating with no tier row uses the highest row
    below it. Rating 0 gives a zero allowance, not None."""
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
    # S&S p.66: one stone can use the full allowance, thus `individual_max` stays 0.
    return HearthstoneAllowance(combined_max=total)


def hearthstone_total(bg) -> int:
    """Return the Hearthstone levels on one row: the number that S&S p.67 caps."""
    return sum(stone.rating for stone in bg.hearthstones)


def budgeted_items(character: Character) -> list[ArtifactItem]:
    """Return the artifacts that the Artifact Background paid for: all owned items
    except the cash items (human's ruling).

    The budget uses this list. Damaged Artifact, the sheet and the picker use
    `artifact_items`. Each budget read site must use this function.
    """
    return [i for i in artifact_items(character)
            if i.acquired not in (ACQUIRED_PURCHASED, ACQUIRED_LEGENDARY)]


def purchased_items(character: Character) -> list[ArtifactItem]:
    """Return the artifacts acquired with cash."""
    return [i for i in artifact_items(character)
            if i.acquired == ACQUIRED_PURCHASED]


def combined_rating(character: Character) -> int:
    """Return the total rating that the p.131 budget caps. See `budgeted_items`."""
    return sum(item.rating for item in budgeted_items(character))


def artifact_rule(budgets) -> Optional[BackgroundRule]:
    """Return the Artifact `BackgroundRule` of `budgets`, or None."""
    return budgets.background_rules.get(ARTIFACT_BACKGROUND)


def acquisition_cost(budgets, rating: int) -> int:
    """Return the Artifact Background dots that an artifact of `rating` cost.

    Damaged Artifact (PG p.38) uses this value:

        Solar / core        1 dot buys 1 dot of artifact         cost = rating
        Dragon-Blooded      "twice the dots' worth"              cost = ceil(rating/2)
        Alchemical          "THREE dots of artifacts per dot"    cost = ceil(rating/3)
        Abyssal (loyal)     the p.131 budget table               cost = the cheapest row
                                                                 that permits it

    Measured for each item alone (human's ruling).

    ⚠ The tier `individual_max` applies. This disagrees with the p.38 example (4-dot
    wings at two points): Sound Gear limits one item to 3, thus the answer is three.
    **The table wins (human's ruling).**
    """
    rule = artifact_rule(budgets)
    if rule is None:
        return rating
    if rule.budget_tiers:
        permitted = [t.rating for t in sorted(rule.budget_tiers, key=lambda t: t.rating)
                     if t.combined_max >= rating
                     and (not t.individual_max or t.individual_max >= rating)]
        # No row permits it: return the top row. The budget check reports the excess.
        return permitted[0] if permitted else max(t.rating for t in rule.budget_tiers)
    per = rule.rating_per_dot
    return -(-rating // per)                   # ceiling division


def tier_label(rating: int, tier: BackgroundBudgetTier) -> str:
    """Return the name of a budget row: "Artifact 3 (Well-Equipped)", or "Artifact 3"
    if the row has no name (E:Ab p.131; Cult p.96). ⚠ Format the name here only."""
    return f"Artifact {rating} ({tier.name})" if tier.name else f"Artifact {rating}"


def budget_tier(budgets, rating: int) -> Optional[BackgroundBudgetTier]:
    """Return the Artifact budget row at `rating`, or None if the splat has no table
    or the rating has no row.

    A rating above the top row uses the top row. Rating 0 with no row gives None:
    `budget_issues` reports the mismatch."""
    rule = artifact_rule(budgets)
    if rule is None or not rule.budget_tiers:
        return None
    exact = [t for t in rule.budget_tiers if t.rating == rating]
    if exact:
        return exact[0]
    below = [t for t in rule.budget_tiers if t.rating < rating]
    return max(below, key=lambda t: t.rating) if below else None
