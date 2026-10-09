"""
ui/view/xp_log.py — the rows of the XP log, with a label for each purchase.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...engine import validate
from ...engine.labels import _label
from ...models.character import Character, XpEntry
from ...models.rules import RuleSet


@dataclass
class XpLogRow:
    index: int           # position in character.xp_log
    label: str           # human-readable purchase, e.g. "Melee 2 → 3"
    detail: str          # ability/charm/etc. label without the rating arrows
    cost: int


def _xp_entry_label(ruleset: RuleSet, character: Character, entry: XpEntry) -> str:
    domain, _, key = entry.target.partition(".")
    reduction = (entry.from_rating is not None and entry.to_rating is not None
                 and entry.to_rating < entry.from_rating)
    note = (f"  ↓ {entry.detail}" if entry.detail else "  ↓") if reduction else ""
    if domain in ("attributes", "abilities", "virtues"):
        return f"{_label(key)} {entry.from_rating} → {entry.to_rating}{note}"
    if domain == "crafts":
        return f"Craft ({entry.detail}) {entry.from_rating} → {entry.to_rating}"
    if domain == "colleges":
        college = ruleset.colleges.get(entry.detail)
        return (f"College: {college.name if college else entry.detail} "
                f"{entry.from_rating} → {entry.to_rating}")
    if domain in ("willpower", "essence"):
        return f"{domain.title()} {entry.from_rating} → {entry.to_rating}{note}"
    if domain == "charms":
        charm = ruleset.charms.get(entry.detail)
        return f"Charm: {charm.name if charm else entry.detail}"
    # A Charm redeemed against a Weak Essence credit. Its own target keeps the audit
    # from re-pricing it, but the target has no dot in it, so `domain` was the whole
    # string and the row fell through to the raw "charms_withheld" — the charm's own
    # name never appeared. Keeps the "Charm:" prefix the ordinary rows use so the
    # ledger still sorts and scans as one thing.
    if domain == validate.WITHHELD_CHARM_TARGET:
        charm = ruleset.charms.get(entry.detail)
        return f"Charm: {charm.name if charm else entry.detail} (withheld, no XP)"
    if domain == "spells":
        spell = ruleset.spells.get(entry.detail)
        return f"Spell: {spell.name if spell else entry.detail}"
    if domain == "combos":
        return f"Combo: {entry.detail}"
    if domain == "specialties":
        return f"Specialty: {entry.detail.replace(':', ' — ', 1)}"
    if domain == "ox_body":
        charm = validate.ox_body_charm(ruleset, character)
        label = next((v.label for v in (charm.variants if charm else []) if v.key == entry.detail),
                     entry.detail)
        return f"Ox-Body: {label}"
    if domain == "beastman_gifts":
        charm = validate.gift_charm(ruleset, character)
        labels = {v.key: v.label for v in (charm.variants if charm else [])}
        # advancement.learn_gift logs the purchase's Gift keys joined by '|'
        gifts = ", ".join(labels.get(k, k) for k in entry.detail.split("|") if k)
        return f"{charm.name if charm else 'Beastman Gifts'}: {gifts}"
    if domain == "variant_purchases":
        # detail is "<charm_id>:<key|key>" — advancement.learn_variant_purchase logs
        # the Charm and the versions this purchase took.
        cid, _, keys = entry.detail.partition(":")
        charm = ruleset.charms.get(cid)
        labels = {v.key: v.label for v in (charm.variants if charm else [])}
        taken = ", ".join(labels.get(k, k) for k in keys.split("|") if k)
        name = charm.name if charm else cid
        return f"{name}: {taken}" if taken else f"Charm: {name}"
    # Thaumaturgy (Player's Guide CH3). Names are resolved from the catalogue where
    # there is one and fall back to the logged id, so a custom ritual — or a stale id
    # whose catalogue entry has since gone — still reads as itself rather than
    # vanishing from the ledger.
    if domain == "thaum_arts":
        art = ruleset.thaum_arts.get(entry.detail)
        return f"Art: {art.name if art else entry.detail}"
    if domain == "thaum_specialties":
        art_id, _, name = entry.detail.partition(":")
        art = ruleset.thaum_arts.get(art_id)
        return f"Specialty: {art.name if art else art_id} ({name})"
    if domain == "thaum_sciences":
        science = ruleset.thaum_sciences.get(entry.detail)
        return (f"Science: {science.name if science else entry.detail} "
                f"{entry.from_rating} → {entry.to_rating}")
    if domain in ("thaum_rituals", "thaum_formulas"):
        noun = "Ritual" if domain == "thaum_rituals" else "Formula"
        catalogue = (ruleset.thaum_rituals if domain == "thaum_rituals"
                     else ruleset.thaum_formulas)
        obj = catalogue.get(entry.detail)
        # to_rating carries the level, so the row prices and reads correctly from the
        # log alone (see advancement.learn_thaum_ritual).
        level = f" (level {entry.to_rating})" if entry.to_rating else ""
        return f"{noun}: {obj.name if obj else entry.detail}{level}"
    if domain == "thaum_orientations":
        # detail is "key:Orientation"; a custom name may itself contain a colon, so
        # split from the right — the same reason advancement's undo uses rpartition.
        target, _, orientation = entry.detail.rpartition(":")
        catalogue = ruleset.thaum_rituals if key == "ritual" else ruleset.thaum_formulas
        obj = catalogue.get(target)
        return f"Orientation: {obj.name if obj else target} ({orientation})"
    if domain == "elemental_powers":
        power = ruleset.elemental_powers.get(entry.detail)
        return f"Elemental Power: {power.name if power else entry.detail}"
    if domain == "merits":
        # A buy/gain logs the bare merit_id; a drop logs "-<merit_id>". Strip the
        # leading dash so both resolve to the same catalogue name (and the Undo
        # button names the row it will reverse).
        mid = entry.detail.lstrip("-")
        mf = ruleset.merits_flaws.get(mid)
        name = mf.name if mf else mid
        return f"{name} (removed)" if entry.detail.startswith("-") else name
    return entry.target


def build_xp_log(ruleset: RuleSet, character: Character) -> list[XpLogRow]:
    """The XP spend log as display rows, in spend order. Pure presentation; the
    engine owns costs and legality. Only the last row is safe to undo (LIFO)."""
    return [
        XpLogRow(index=i, label=_xp_entry_label(ruleset, character, e),
                 detail=e.target.split(".", 1)[0], cost=e.cost)
        for i, e in enumerate(character.xp_log)
    ]
