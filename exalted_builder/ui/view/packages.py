"""
ui/view/packages.py — the variant-menu packages (Ox-Body Technique, Deadly
Beastman Transformation): the menu and the selection prune.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ...engine import costs, validate
from ...models.character import Character
from ...models.rules import RuleSet

from .sheet import repeatable_cap_trait


# --- Variant-menu packages (Ox-Body, Deadly Beastman Transformation) -------- #
# Both Charms are bought as a PACKAGE into their own character field rather than by
# appending an id to `character.charms` — `engine.charm_actions.variant_menu_reason`
# refuses the ordinary toggle, and this is what a shell shows instead. One presenter
# for both, because the two shells' choosers had already drifted once (the web
# picker's chooser was the only one there was).

@dataclass
class PackagePick:
    """One selectable entry on a package menu: an Ox-Body health-level variant, or
    one Deadly Beastman Gift."""
    key: str
    label: str
    description: str
    max_purchases: int      # >1 for a Gift the book lets you take twice
    taken: int              # copies already held (Gifts only; always 0 for Ox-Body)
    reason: str             # why it can't be picked right now; "" when it can


@dataclass
class PackageHeld:
    """One package already bought, by its position in the character's list."""
    index: int
    label: str              # the labels of that package's picks, joined


@dataclass
class PackageMenu:
    """Everything a shell needs to draw one variant-menu Charm's chooser."""
    kind: str               # "ox_body" | "gift" | "variant"
    charm_id: str
    name: str
    description: str
    bought: int
    cap: int
    cap_trait: str          # per-splat DATA — Endurance, Stamina or Essence
    cap_unit: str           # "dot" | "point"
    needed: int             # picks this purchase grants (Gifts: 2 first, then 1)
    price: int              # XP each post-lock; 0 in chargen
    held: list[PackageHeld]
    picks: list[PackagePick]
    note: str               # book rider, when the page prints one
    # Each version may be taken at most once (rules.Charm.variants_unique).
    unique_versions: bool = False

    @property
    def cap_phrase(self) -> str:
        """What actually limits the purchases, as a phrase.

        ⚠ Not always the trait. A menu whose versions are unique runs out of VERSIONS
        first whenever the version count is the tighter bound — Environmental
        Hazard-Resisting Meditation needs Resistance 5 to learn at all, so its four
        versions always bind and "once per dot of Resistance" is simply untrue there.
        Composed here so no shell reassembles it from `cap_trait`/`cap_unit`."""
        if self.unique_versions and self.cap >= len(self.picks):
            return f"one of each of its {len(self.picks)} versions"
        if not self.cap_trait:
            return "its maximum"
        return f"once per {self.cap_unit} of {self.cap_trait}"


def package_menu_kind(ruleset: RuleSet, character: Character, charm_id: str) -> str:
    """"ox_body", "gift", "variant", or "" when `charm_id` is an ordinary toggleable
    Charm.

    ⚠ The discriminator is the character's OWN package-Charm ids and the Charm's
    `variants` list, not the name or the category: which Charm fills the Ox-Body and
    Gift roles is per-splat data (a heritage points at its parent's copy), and no
    widget can edit any of it.

    "variant" is the generic case — every other Charm carrying variants, stored on
    `character.variant_purchases` keyed by charm_id."""
    if not charm_id:
        return ""
    if charm_id == validate.ox_body_charm_id(ruleset, character):
        return "ox_body"
    if charm_id == validate.gift_charm_id(ruleset, character):
        return "gift"
    if validate.is_variant_menu_charm(ruleset, character, ruleset.charms.get(charm_id)):
        return "variant"
    return ""


def _gift_pick_reason(labels: dict[str, str], taken: dict[str, int],
                      held: set[str], variant) -> str:
    """Why Gift `variant` can't be picked given `held` as the Gifts in hand; "" when
    it can. `held` includes the pending selection, because a Gift chosen in the SAME
    purchase satisfies a prerequisite (p.124)."""
    if variant.max_purchases - taken.get(variant.key, 0) <= 0:
        return ("Already taken" if variant.max_purchases == 1
                else f"Taken {taken.get(variant.key, 0)}/{variant.max_purchases}")
    for group in variant.prerequisites:
        if not any(g in held for g in group):
            return "Requires " + " or ".join(labels.get(g, g) for g in group)
    return ""


def build_package_menu(ruleset: RuleSet, character: Character, charm_id: str,
                       selection: Sequence[str] = ()) -> Optional[PackageMenu]:
    """The chooser for one variant-menu Charm, or None when `charm_id` is not one (or
    its Charm is missing from the rule set).

    `selection` is the picks staged in the shell but not yet bought: each Gift row's
    `reason` is computed against the held Gifts PLUS that selection, so a chain can be
    assembled inside one purchase. A staged pick is judged WITHOUT itself, or it would
    read as its own prerequisite.

    ⚠ Ox-Body's `max_purchases` is 1 and means nothing here — a repeat purchase picks
    a variant again, same or different (`CharmVariant`), so the taken/max rule is
    applied to Gifts ONLY."""
    kind = package_menu_kind(ruleset, character, charm_id)
    if not kind:
        return None
    is_gift = kind == "gift"
    charm = (validate.gift_charm(ruleset, character) if is_gift
             else ruleset.charms.get(charm_id) if kind == "variant"
             else validate.ox_body_charm(ruleset, character))
    if charm is None:
        return None
    labels = {v.key: v.label for v in charm.variants}
    cap_trait, cap_unit = repeatable_cap_trait(charm)
    if is_gift:
        purchases = character.beastman_gifts
        held = [PackageHeld(i, ", ".join(labels.get(k, k) for k in p.gifts))
                for i, p in enumerate(purchases)]
        cap = validate.gift_purchase_cap(ruleset, character)
        needed = validate.gifts_per_purchase(charm, len(purchases))
        price = costs.gift_cost(ruleset, character) if character.chargen_locked else 0
        known = validate.known_gift_keys(character)
        taken: dict[str, int] = {}
        for k in known:
            taken[k] = taken.get(k, 0) + 1
        in_hand = set(known) | set(selection)
        picks = [
            PackagePick(v.key, v.label, v.description, v.max_purchases,
                        taken.get(v.key, 0),
                        _gift_pick_reason(labels, taken,
                                          in_hand - ({v.key} if v.key in selection else set()),
                                          v))
            for v in charm.variants]
        # p.126 heads the list "Sample Gifts … these are not the only possible gifts":
        # the roster is illustrative and anything else is a Storyteller call, so say
        # so rather than implying the listed ones are the whole rule.
        note = ("Sample Gifts (p.126-127) — the book's list is not exhaustive; "
                "anything else is a Storyteller call.")
    elif kind == "variant":
        # The generic menu. Its versions may be marked unique (`variants_unique`), in
        # which case one already taken is offered with a reason rather than hidden —
        # the player should see the whole printed list and why a row is closed.
        purchases = validate.variant_purchases_for(character, charm_id)
        held = [PackageHeld(i, ", ".join(labels.get(k, k) for k in p.variants))
                for i, p in enumerate(purchases)]
        cap = validate.variant_purchase_cap(ruleset, character, charm)
        needed = validate.gifts_per_purchase(charm, len(purchases))
        price = (costs.variant_purchase_cost(ruleset, character, charm)
                 if character.chargen_locked else 0)
        known = set(validate.known_variant_keys(character, charm_id))
        picks = [PackagePick(v.key, v.label, v.description, v.max_purchases,
                             1 if v.key in known else 0,
                             "Already taken" if charm.variants_unique
                             and v.key in known else "")
                 for v in charm.variants]
        note = ""
    else:
        purchases = character.ox_body
        held = [PackageHeld(i, labels.get(p.variant, p.variant))
                for i, p in enumerate(purchases)]
        cap = validate.ox_body_cap(ruleset, character)
        needed = 1
        price = costs.ox_body_cost(ruleset, character) if character.chargen_locked else 0
        picks = [PackagePick(v.key, v.label, v.description, v.max_purchases, 0, "")
                 for v in charm.variants]
        note = ""
    return PackageMenu(
        kind=kind, charm_id=charm_id, name=charm.name, description=charm.description,
        bought=len(purchases), cap=cap, cap_trait=cap_trait, cap_unit=cap_unit,
        needed=needed, price=price, held=held, picks=picks, note=note,
        unique_versions=charm.variants_unique)


def prune_package_selection(ruleset: RuleSet, character: Character, charm_id: str,
                            selection: Sequence[str]) -> list[str]:
    """`selection` with every pick whose prerequisites it no longer satisfies dropped,
    repeatedly until it settles.

    Unchecking a Gift must drop anything selected that depended on it — otherwise the
    chooser could confirm a chain whose root is gone. Order is preserved, so the
    cascade is stable."""
    kept = list(selection)
    changed = True
    while changed:
        changed = False
        menu = build_package_menu(ruleset, character, charm_id, kept)
        if menu is None:
            return kept
        blocked = {p.key for p in menu.picks if p.reason}
        for key in list(kept):
            if key in blocked:
                kept.remove(key)
                changed = True
    return kept
