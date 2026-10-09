"""
ui/view/inventory.py — the gear presenters: the stat lines, the inventory, the
artifacts header, and the Buy shop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...engine import artifacts as artifactsmod, validate
from ...models.character import Character
from ...models.rules import RuleSet

from .dice_pools import _ammunition_indices


# --------------------------------------------------------------------------- #
# Gear stat lines — ONE format string per kind, for both the character's own gear
# and a catalogue entry.
#
# ⚠ ONE definition, used by the row readout and by the catalogue dialog alike. Two
# copies drift on details no test looks at — the spacing before "Mob" differed while
# one docstring claimed the two matched.
#
# Duck-typed on purpose: `Weapon`/`Armor` (a character's item, usually passed through
# `derive.effective_*` so the material bonus is folded in) and `WeaponType`/`ArmorType`
# (a catalogue row) carry the same stat field names, and the caller decides which it
# has. `material` is the wielder-dependent tag, which a pre-pick catalogue row has no
# character to compute — hence a parameter rather than a lookup in here.
# --------------------------------------------------------------------------- #

def weapon_stat_line(weapon, *, material: str = "") -> str:
    """One-line weapon stat readout: `Acc+2 Dmg+5L Def+0 Spd+0  ◈ Orichalcum`."""
    tag = f"  ◈ {material}" if material else ""
    return (f"Acc{weapon.accuracy:+d} Dmg{weapon.damage:+d}{weapon.damage_type} "
            f"Def{weapon.defense:+d} Spd{weapon.speed:+d}{tag}")


def armor_stat_line(armor, *, material: str = "") -> str:
    """One-line armour stat readout: `Soak 3L/4B  Mob-1 Ftg1  ◈ Moonsilver`."""
    tag = f"  ◈ {material}" if material else ""
    return (f"Soak {armor.soak_lethal}L/{armor.soak_bashing}B  "
            f"Mob{armor.mobility_penalty:+d} Ftg{armor.fatigue}{tag}")


@dataclass
class InventoryRow:
    """One thing the character owns, whatever list it is stored in.

    The INVENTORY is a VIEW, not a storage shape (human's model, 2026-08-13: "your
    inventory, which is Everything, but you can filter it down to certain types of
    goods, some of which would overlap"). The three lists stay typed and separate —
    a weapon carries accuracy and rate, armour carries soak and fatigue, goods carry
    neither, and collapsing them would mean a save migration plus rewriting every index
    into `character.weapons` (the dice-pool sidebar's, for one) to buy nothing.

    `kinds` is a SET because the categories genuinely overlap: an artifact daiklave is a
    weapon AND an artifact, a shield is armour, an arrow is a weapon and ammunition. A
    filter picks rows whose kinds INTERSECT what it asks for, so the same row can appear
    under two filters and be one object underneath.
    """
    name: str
    kinds: tuple[str, ...]                 # "weapon" / "armor" / "artifact" / "goods" …
    detail: str = ""                       # the stat line, or the price, or ""
    quantity: int = 1
    resources_cost: int = 0
    artifact_rating: int = 0
    acquired: str = ""                     # only meaningful for artifacts
    index: int = 0                         # position in its OWN list
    list_name: str = ""                    # which list that is — the edit route back
    # An artifact and the gear row `grant_gear` stamped for it are ONE OBJECT and get
    # ONE row (the human, 2026-08-13: two peer rows for one daiklave "feels odd, and a
    # little obtuse"). The artifact owns the row; its stat line rides in `detail` and
    # its editor is reached through this SECOND route back. Empty for every unmerged
    # row, which is the large majority.
    #
    # ⚠ Display-only. The typed lists are untouched, so `character.weapons` keeps its
    # positional indices — the dice-pool sidebar reads them.
    linked_list_name: str = ""
    linked_index: int = 0


INVENTORY_FILTERS = ("all", "weapon", "armor", "artifact", "goods",
                     "ammunition")


def inventory_rows(ruleset: RuleSet, character: Character) -> list[InventoryRow]:
    """Everything the character owns, from all four lists, in one list of rows.

    Pure and presentation-only: it computes no rule and validates nothing. The artifact
    kind is taken from `engine.artifacts.artifact_items` rather than from
    `artifact_rating` directly, so a gear row that is the STAT LINE of a standalone
    artifact is not tagged as a second artifact — the same dedup the budget uses, read
    from the same place, so the inventory and the budget cannot disagree about what is
    an artifact.
    """
    owned = {i.key: i for i in artifactsmod.artifact_items(character)}
    # A character's `Weapon` carries no tags (decision 0007: inline copies), so
    # ammunition is recovered from the catalogue by name — the same recovery, with the
    # same failure direction, as the dice-pool sidebar's.
    ammo = _ammunition_indices(ruleset, character)

    def _art(source: str, name: str):
        return owned.get(artifactsmod.item_key(source, name))

    # Which standalone artifact each granted gear row belongs to, as
    # `(list_name, gear index) -> artifact index`. Resolved against the artifacts
    # actually present rather than trusting the stored key, so an ORPHANED link (the
    # artifact renamed or deleted) leaves the gear row standing on its own line instead
    # of merging into nothing and vanishing — the same failure direction
    # `artifact_items` picked for the same link.
    art_index = {}
    for idx, art in enumerate(character.artifacts):
        if art.name.strip():
            art_index.setdefault(
                artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, art.name), idx)
    merged: dict[int, tuple[str, int]] = {}          # artifact idx -> (list, gear idx)
    for list_name, gear in (("weapons", character.weapons), ("armor", character.armor)):
        for idx, item in enumerate(gear):
            target = art_index.get(item.from_artifact)
            if item.from_artifact and target is not None and target not in merged:
                merged[target] = (list_name, idx)
    merged_gear = {v for v in merged.values()}

    rows: list[InventoryRow] = []
    for idx, w in enumerate(character.weapons):
        if ("weapons", idx) in merged_gear:
            continue          # shown on its artifact's row, as one object
        item = _art(artifactsmod.SOURCE_WEAPON, w.name)
        kinds = ["weapon"]
        if item is not None:
            kinds.append("artifact")
        if idx in ammo:
            kinds.append("ammunition")
        rows.append(InventoryRow(
            name=w.name or "(unnamed)", kinds=tuple(kinds),
            detail=weapon_stat_line(w), quantity=w.quantity,
            resources_cost=w.resources_cost, artifact_rating=w.artifact_rating,
            acquired=w.acquired if item is not None else "",
            index=idx, list_name="weapons"))
    for idx, a in enumerate(character.armor):
        if ("armor", idx) in merged_gear:
            continue
        item = _art(artifactsmod.SOURCE_ARMOR, a.name)
        kinds = ["armor"] + (["artifact"] if item is not None else [])
        rows.append(InventoryRow(
            name=a.name or "(unnamed)", kinds=tuple(kinds),
            detail=armor_stat_line(a), resources_cost=a.resources_cost,
            artifact_rating=a.artifact_rating,
            acquired=a.acquired if item is not None else "",
            index=idx, list_name="armor"))
    for idx, art in enumerate(character.artifacts):
        kinds, detail, link = ["artifact"], art.note, ("", 0)
        if idx in merged:
            list_name, gear_idx = merged[idx]
            gear = getattr(character, list_name)[gear_idx]
            # The STAT LINE is what the merged row shows, because that is the half a
            # player is looking for on a weapon they own — the artifact's own note is
            # prose and lives in its editor. `kinds` gains the gear's kind so the row
            # still answers to the Weapons/Armor filter: merging two rows must not cost
            # the object a filter it used to appear under.
            kinds.append("weapon" if list_name == "weapons" else "armor")
            detail = (weapon_stat_line(gear) if list_name == "weapons"
                      else armor_stat_line(gear))
            link = (list_name, gear_idx)
        rows.append(InventoryRow(
            name=art.name or "(unnamed)", kinds=tuple(kinds),
            detail=detail, artifact_rating=art.rating, acquired=art.acquired,
            index=idx, list_name="artifacts",
            linked_list_name=link[0], linked_index=link[1]))
    for idx, g in enumerate(character.gear):
        rows.append(InventoryRow(
            name=g.name or "(unnamed)", kinds=("goods",), detail=g.note,
            quantity=g.quantity, resources_cost=g.resources_cost,
            index=idx, list_name="gear"))
    return rows


def filter_inventory(rows: list[InventoryRow], kind: str) -> list[InventoryRow]:
    """The rows matching one filter — `"all"`, or any kind. Overlapping by design: an
    artifact daiklave answers to both `weapon` and `artifact`."""
    if kind == "all":
        return list(rows)
    return [r for r in rows if kind in r.kinds]


def inventory_counts(rows: list[InventoryRow]) -> dict[str, int]:
    """How many rows each filter would show — for the filter labels, so a player can
    see that a tab is empty before clicking it. Sums to MORE than the row count when
    anything overlaps, which is correct and is why the filters are not a partition."""
    return {k: len(filter_inventory(rows, k)) for k in INVENTORY_FILTERS}


def inventory_filter_label(kind: str, count: int) -> str:
    """One filter chip's caption. `"all"` is spelled "Everything" — a chip reading
    "All (6)" beside a heading reading "Inventory (6)" says the same thing twice."""
    return ("Everything" if kind == "all" else kind.capitalize()) + f" ({count})"


def inventory_heading(rows: list[InventoryRow], counts: dict[str, int],
                      active: str) -> str:
    """The inventory panel's title, naming the ACTIVE filter as well as the total.

    ⚠ EVERY state names its filter, including "all". Without it the only evidence of a
    filter click is rows disappearing, which reads as loss rather than as a view — and a
    heading reading "Inventory (6)" when unfiltered is a strict PREFIX of the filtered
    one, so nothing matching on it, a test or a player's glance, can tell the two apart.
    """
    shown = "Everything" if active == "all" else active.capitalize()
    return f"Inventory ({len(rows)}) · showing {shown} ({counts.get(active, 0)})"


def inventory_row_tags(row: InventoryRow) -> list[str]:
    """The little kind chips beside one inventory row.

    Weapon/armour/ammunition are dropped — the stat line beside them already says which
    it is, so the chip is noise.

    ⚠ A plot device has NO rating to print. Its dots are a placeholder the model's 1-5
    bound demands and its page prints "(ARTIFACT N/A)"; showing "Artifact •••••" here
    would be the one place in the build that states the fiction as a fact.
    """
    tags = []
    for kind in row.kinds:
        if kind in ("weapon", "armor", "ammunition"):
            continue
        if kind != "artifact":
            tags.append(kind.capitalize())
        elif row.acquired == artifactsmod.ACQUIRED_LEGENDARY:
            tags.append("Artifact N/A · by Merit")
        else:
            tags.append("Artifact " + "•" * row.artifact_rating
                        + (" · bought" if row.acquired == artifactsmod.ACQUIRED_PURCHASED
                           else ""))
    return tags


# --------------------------------------------------------------------------- #
# The artifacts budget header
# --------------------------------------------------------------------------- #

def artifacts_header(ruleset: RuleSet, character: Character) -> str:
    """The artifacts panel's title, stating the budget rule and where this character
    stands against it.

    ⚠ It counts the BUDGET's items, not everything owned: a purchased artifact is
    charged to nothing, so counting it here would print a number the validator does not
    agree with — the header and the rule must tell the same story. What is left out is
    said out loud by `artifacts_bought_note`.
    """
    items = artifactsmod.budgeted_items(character)
    rule = artifactsmod.artifact_rule(validate.effective_budgets(ruleset, character))
    rating = sum(bg.rating for bg in character.backgrounds
                 if bg.name.strip().lower() == artifactsmod.ARTIFACT_BACKGROUND)
    if artifactsmod.uses_corebook_rule(rule):
        # The corebook rule (ruling 2026-08-13) governs most splats, and until it was
        # enforced this header said the bare word "Artifacts" — so the first a player
        # heard of the one-artifact limit was a validation error after they had picked
        # two. The line states the rule whether or not they are over it.
        #
        # ONE PER ROW: a character may hold the Artifact Background more than once, and
        # two Artifact •• rows are two artifacts (`validate.background_rows`). The
        # header counts ROWS, not their sum — printing "/1" beside two rows is what made
        # the browser read the validator's error as arbitrary.
        rows = sorted((r for r in validate.background_rows(
            character.backgrounds, artifactsmod.ARTIFACT_BACKGROUND) if r > 0),
            reverse=True)
        if not rows:
            return f"Artifacts ({len(items)} — no Artifact Background)"
        allowance = " + ".join(f"up to {r}" for r in rows)
        return (f"Artifacts ({len(items)}/{len(rows)} — Artifact "
                f"{'+'.join(str(r) for r in rows)}, {allowance})")
    if rule is not None and rule.budget_tiers:
        tier = artifactsmod.budget_tier(
            validate.effective_budgets(ruleset, character), rating)
        combined = sum(i.rating for i in items)
        if tier is None:
            return f"Artifacts ({combined} combined — no Artifact Background)"
        # The row name is optional — the Cult of the Illuminated's table (p.96) prints
        # bare dot rows where the Abyssal's names each one, and a blank left a trailing
        # comma inside the parenthesis.
        named = f", {tier.name}" if tier.name else ""
        return (f"Artifacts ({combined}/{tier.combined_max} combined — "
                f"Artifact {rating}{named})")
    return "Artifacts"


def artifacts_bought_note(character: Character) -> str:
    """The cash-bought artifacts the header above deliberately does not count, or "".

    Said out loud, because the alternative is a header whose count is lower than the
    visible list for no stated reason.
    """
    bought = artifactsmod.purchased_items(character)
    if not bought:
        return ""
    return (f"+ {len(bought)} bought with Resources, not charged to the Background")


def artifacts_also_counted(character: Character) -> str:
    """The artifact weapons and armour that count against the same budget but are
    edited as equipment, or "". Listed so the combined total above is accounted for
    rather than looking wrong."""
    gear = [i for i in artifactsmod.artifact_items(character)
            if i.source != artifactsmod.SOURCE_ARTIFACT]
    if not gear:
        return ""
    return ("Also counted, from equipment: "
            + ", ".join(f"{i.name} ({i.rating})" for i in gear))


# --------------------------------------------------------------------------- #
# The Buy shop — one priced list over four catalogues
# --------------------------------------------------------------------------- #

def catalog_weapon_summary(weapon_type) -> str:
    """One-line stat summary for a catalogue weapon — the SAME line the equipment row
    shows, minus the material tag (that needs a wielder; the dialog is pre-pick)."""
    return weapon_stat_line(weapon_type)


def catalog_armor_summary(armor_type) -> str:
    """One-line stat summary for a catalogue armour — see `catalog_weapon_summary`."""
    return armor_stat_line(armor_type)


# Core p.325 prices gear in Resources dots rather than money, so the shop says what a
# row would COST this character before she picks it. Presentation only: the three cases
# come from `validate.gear_affordability`, which owns the rule.
_AFFORDABILITY_NOTE = {
    "easy": "within your means",
    "serious": "a serious expense (buying it drops Resources by 1)",
    "unaffordable": "beyond your Resources",
}


def gear_cost_note(resources_cost: int, affordability: str) -> str:
    """The Resources clause appended to a gear row's summary, e.g.
    "Resources ●●● — beyond your Resources". Empty for gear with no printed cost."""
    if not resources_cost or not affordability:
        return ""
    return (f"Resources {'●' * resources_cost}"
            f" — {_AFFORDABILITY_NOTE.get(affordability, '')}".rstrip(" —"))


@dataclass(frozen=True)
class ShopRow:
    """One buyable thing, as the Buy dialog shows it.

    ⚠ `key` carries the KIND (`weapon:` / `armor:` / `goods:` / `artifact:`) so one
    dialog can append to four differently typed lists — `engine.gear_actions.buy` reads
    it back. `group` is the filter chip and is the bare kind word: folding the rating
    into it ("Artifact •••") would make one chip per rating.

    `tags` rides along rather than an icon, because the two shells draw from different
    icon sets. Whether a row is dimmed comes from `affordability`, not from a flag —
    the shop states a price, it never refuses a purchase (core p.325).
    """
    key: str
    name: str
    group: str
    summary: str
    full: Optional[str]
    tags: tuple[str, ...]
    affordability: str


def shop_rows(ruleset: RuleSet, character: Character) -> list[ShopRow]:
    """Everything a book prices for this character, plus their own library.

    ⚠ Services are NEVER offered — they are a reference price list, not inventory
    (human's ruling 2026-08-13), and the ruling holds at the OFFER, not just in the data.

    ⚠ Artifacts appear only POST-LOCK (decision 0017): the Artifact Background is the
    pre-game channel ("to start the game owning", core p.342) and cash is the in-play
    one. A shop that offered them at chargen would be the hole that decision closes.
    """
    rows: list[ShopRow] = []

    def add(key, name, group, cost, summary, full=None, tags=()):
        afford = validate.gear_affordability(ruleset, character, cost)
        note = gear_cost_note(cost, afford)
        bits = [group] + [x for x in (summary, note) if x]
        # Your own library rows sit in the same list as the books', because that is the
        # point of a library — but they say which they are. The loader tags them
        # (`rules_db._merge_custom_gear`); nothing here decides it.
        if "custom" in tags:
            bits.insert(0, "★ yours")
        rows.append(ShopRow(key=key, name=name, group=group, summary=" · ".join(bits),
                            full=full, tags=tuple(tags), affordability=afford))

    for w in sorted(ruleset.weapon_catalog.values(), key=lambda x: x.name):
        add(f"weapon:{w.name}", w.name, "Weapon", w.resources_cost,
            catalog_weapon_summary(w), tags=w.tags)
    for a in sorted(ruleset.armor_catalog.values(), key=lambda x: x.name):
        add(f"armor:{a.name}", a.name, "Armour", a.resources_cost,
            catalog_armor_summary(a), tags=a.tags)
    for g in sorted(ruleset.gear_catalog.values(), key=lambda x: x.name):
        if g.kind != "goods":
            continue
        add(f"goods:{g.id}", g.name, "Goods", g.resources_cost, g.category,
            g.notes or None, tags=g.tags)
    if character.chargen_locked:
        for art in sorted(artifactsmod.purchasable_with_artifact(
                ruleset.artifact_catalog), key=lambda x: x.name):
            if not art.resources_cost:
                continue
            add(f"artifact:{art.name}", art.name, "Artifact", art.resources_cost,
                "•" * art.rating, art.description, tags=art.tags)
    return rows


def shop_custom_kinds(character: Character) -> dict[str, str]:
    """The "Custom …" rows the shop offers, keyed by the list a blank row lands in.

    Making a thing and buying a thing are ONE surface: these are what let the four
    per-panel Add buttons be deleted, because a shop CAN know which list a blank row
    belongs in once you say which kind you are making. Artifacts are absent at chargen
    for the same reason they are absent from the shop above — decision 0017.
    """
    kinds = {"weapons": "Custom weapon", "armor": "Custom armour",
             "gear": "Custom goods"}
    if character.chargen_locked:
        kinds["artifacts"] = "Custom artifact"
    return kinds


def service_rows(ruleset: RuleSet, character: Character) -> list[tuple]:
    """The services price list, as `(category, name, dots, cash, notes, affordable)`
    ordered by category then name.

    ⚠ `GearType.cash` — the printed jade and silver equivalents — is the whole point of
    this panel and its only read site. A name and a dot column alone is a PRICE list
    showing no prices, which is the house bug; what makes a reference panel worth its
    space is the information you cannot get anywhere else. Nothing computes from it:
    M&C p.122 says outright the Resources ladder is not linear.
    """
    services = [g for g in ruleset.gear_catalog.values() if g.kind == "service"]
    return [(g.category, g.name, g.resources_cost, g.cash, g.notes,
             validate.gear_affordability(ruleset, character, g.resources_cost)
             != "unaffordable")
            for g in sorted(services, key=lambda g: (g.category, g.name))]
