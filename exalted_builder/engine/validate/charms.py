"""
engine/validate/charms.py — Charm legality: who may learn what, and at what cost.

Access (`charm_matches_splat`, `charm_learnable_by_splat`, `meets_charm_requirements`,
the tier ladder, the Immaculate paths, foreign and heritage access), prerequisites
(`check_charm_prerequisites` and the AND-of-OR graph), the chargen pick enumeration
and its pricing, the Alchemical slot economy, and the repeatable Charms (Ox-Body and
the Lunar Gifts, stored off `Character.charms` and counted separately).

⚠ `charm_picks` is the ONE enumeration of a chargen Charm pick. Do not add a second
one: the pricing reads this one.

⚠ The CHARM fields decide access (`open_to_all`, `open_to_tiers`, `restricted_to`,
`immaculate`, `ma_tier`), NEVER the style catalogue.
`tests/test_martial_arts_styles.py` bars `engine/` from reading
`ruleset.martial_arts_styles`. The loader copies `Charm.ma_tier` from the style.

⚠ `ma_tier` and `open_to_tiers` are DIFFERENT FACTS. `open_to_tiers` gives who can
learn the Charm. `ma_tier` gives if it is a Sidereal Martial Arts form, for the p.101
chargen cap only. Violet Bier of Sorrows is Celestial and is NOT a Sidereal MA form.

⚠ Tiers are RANKED. A character reaches their own tier and each tier below, never
a tier above (decision 0015).

Two imports are inside the functions that need them, because those modules import
this one: `illuminated.calling_charm_ids` and `alchemical._installation_motes`.
"""

from __future__ import annotations

from collections import Counter
from typing import Optional

from pydantic import BaseModel

from ...models.character import Character
from ...models.rules import (
    AbilityName,
    AttributeName,
    Charm,
    CharmCountRequirement,
    CharmType,
    RuleSet,
    TRACK_CIRCLES,
    VirtueName,
)
from .. import derive, elder, merits
from ._base import Issue, _attribute_category, ability_rating, _chargen_source
from .castes import (
    _caste_favored_attr_names,
    _caste_favored_attribute_category,
    caste_favored_abilities,
)


# Each ExaltDefinition names its Ox-Body Charm. One purchase per dot of its cap
# trait. Stored on Character.ox_body, not in Character.charms.


def ox_body_charm_id(ruleset: RuleSet, character: Character) -> str:
    """Return the Ox-Body Charm id of the character: the parent-keyed id for a
    Half-Caste (p.47), the heritage id for God/Demon-Blooded (PG p.83, human's
    ruling), else the splat id. Return '' if none."""
    caste = ruleset.castes.get(character.caste)
    if caste is not None and caste.heritage_traits is not None:
        parent_ox = caste.heritage_traits.ox_body_charm_ids.get(character.origin)
        if parent_ox:
            return parent_ox
        if caste.heritage_traits.ox_body_charm_id:
            return caste.heritage_traits.ox_body_charm_id
    return ruleset.exalt_for(character.exalt_type).ox_body_charm_id


def ox_body_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """Return the Ox-Body Charm of the character, or None."""
    return ruleset.charms.get(ox_body_charm_id(ruleset, character))


def heritage_gift_spec(ruleset: RuleSet, character: Character):
    """Return (id, purchase cap) of the parent-keyed Gift Charm for the character
    `origin`. Only the Lunar parent sets it (p.47): cap 2. None = use the splat."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return None
    traits = caste.heritage_traits
    if character.origin in traits.gift_charm_ids:
        return (traits.gift_charm_ids[character.origin],
                traits.gift_caps.get(character.origin))
    return None


def gift_charm_id(ruleset: RuleSet, character: Character) -> str:
    """Return the Gift Charm id (Lunar, p.124-127), or the parent-keyed id for a
    Lunar Half-Caste (p.47). Return '' if none."""
    spec = heritage_gift_spec(ruleset, character)
    if spec is not None:
        return spec[0]
    return ruleset.exalt_for(character.exalt_type).gift_charm_id


def gift_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """Return the Gift Charm of the character, or None."""
    return ruleset.charms.get(gift_charm_id(ruleset, character))


def is_variant_menu_charm(ruleset: RuleSet, character: Character, charm) -> bool:
    """Return True if `charm` is stored on `character.variant_purchases`: it has
    variants and is not the Ox-Body or Gift Charm of the character.

    ⚠ The discriminator is `Charm.variants`, which no widget can edit."""
    if charm is None or not charm.variants:
        return False
    return charm.id not in (ox_body_charm_id(ruleset, character),
                            gift_charm_id(ruleset, character))


def variant_purchase_cap(ruleset: RuleSet, character: Character, charm) -> int:
    """Return the maximum purchases of a variant-menu Charm: the trait cap, and the
    variant count if `variants_unique` is set (Zenith p.72-73)."""
    if charm is None:
        return 0
    cap = _repeatable_purchase_cap(charm, character)
    if charm.variants_unique:
        cap = min(cap, len(charm.variants)) if cap else len(charm.variants)
    return cap


def variant_purchases_for(character: Character, charm_id: str):
    """Return the purchases of ONE variant-menu Charm, in buy order."""
    return [p for p in character.variant_purchases if p.charm_id == charm_id]


def known_variant_keys(character: Character, charm_id: str) -> list[str]:
    """Return all variant keys taken for `charm_id`, in buy order."""
    return [k for p in variant_purchases_for(character, charm_id) for k in p.variants]


def check_variant_purchases(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check the variant-menu purchases: the Charm exists and has variants, each key
    is a real variant, the minimums are met, the cap holds, and no unique variant
    repeats."""
    issues: list[Issue] = []
    by_charm: dict[str, list] = {}
    for p in character.variant_purchases:
        by_charm.setdefault(p.charm_id, []).append(p)
    for charm_id, purchases in by_charm.items():
        charm = ruleset.charms.get(charm_id)
        if charm is None:
            issues.append(Issue(code="variant-charm-unknown", severity="error",
                                message=f"Unknown Charm {charm_id!r} in variant purchases."))
            continue
        if not is_variant_menu_charm(ruleset, character, charm):
            issues.append(Issue(
                code="variant-charm-not-a-menu", severity="error",
                message=f"{charm.name} is not a variant-menu Charm for this character."))
            continue
        keys = {v.key for v in charm.variants}
        seen: set[str] = set()
        for p in purchases:
            for k in p.variants:
                if k not in keys:
                    issues.append(Issue(
                        code="variant-unknown", severity="error",
                        message=f"{charm.name}: unknown version {k!r}."))
                elif charm.variants_unique and k in seen:
                    labels = {v.key: v.label for v in charm.variants}
                    issues.append(Issue(
                        code="variant-repeated", severity="error",
                        message=f"{charm.name}: {labels.get(k, k)} taken more than once."))
                seen.add(k)
        cap = variant_purchase_cap(ruleset, character, charm)
        if len(purchases) > cap:
            issues.append(Issue(
                code="variant-over-cap", severity="error",
                message=f"{charm.name}: {len(purchases)} purchases, maximum {cap}."))
        if character.essence_rating < charm.min_essence:
            issues.append(Issue(
                code="variant-essence", severity="error",
                message=f"{charm.name} requires Essence {charm.min_essence}."))
    return issues


class CharmPick(BaseModel):
    """One Charm that a character holds, from the list that stores it.

    The lists: `charms`, the repeatables (`ox_body`, `beastman_gifts`,
    `variant_purchases`) and `granted_charms` (p.90). Read this type. Do not walk
    the lists.

    `counts_toward_pool` is False only for granted Charms. `label` includes the
    variants of a repeatable. `caste_favored` is the discount axis of the BP price
    and of the chargen minimum.

    ⚠ Holdings only. `charm_pick_bp_costs` does the BP arithmetic. Do not add
    accounting here.
    """
    charm_id: str
    name: str                  # the Charm's own name, or the raw id if unresolved
    label: str                 # display name; includes variant labels for repeatables
    category: str = ""
    source: str = "charms"     # charms | ox_body | beastman_gifts | variant_purchases
                               #        | granted | origin
    counts_toward_pool: bool = True
    caste_favored: bool = False


def charm_picks(ruleset: RuleSet, character: Character) -> list[CharmPick]:
    """Return all Charms that the character holds NOW, in sheet order: plain picks,
    one entry per repeatable purchase, then granted Charms. An unknown id is returned
    with `name` set to the id.

    ⚠ Chargen accounting must use `chargen_charm_picks`: after the lock these lists
    include XP purchases.
    """
    return _charm_picks_from(
        ruleset, character,
        character.charms, character.ox_body, character.beastman_gifts,
        character.granted_charms, character.variant_purchases,
    )


def chargen_charm_picks(ruleset: RuleSet, character: Character) -> list[CharmPick]:
    """Return `charm_picks` over the chargen traits: the snapshot when locked, else
    the live lists. Granted Charms are always live: the snapshot does not hold them.
    """
    src = _chargen_source(character)
    return _charm_picks_from(
        ruleset, character,
        src[6], src[9], src[12], character.granted_charms, src[20],
    )


def _charm_picks_from(ruleset: RuleSet, character: Character,
                      charms, ox_body, beastman_gifts, granted,
                      variant_purchases=()) -> list[CharmPick]:
    """Return the pick list from explicit trait lists (live or snapshot)."""
    cf_set = caste_favored_abilities(ruleset, character)
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)
    caste_fav_attrs = _caste_favored_attr_names(ruleset, character)

    def _pick(cid, charm, label, *, source, counts=True) -> CharmPick:
        return CharmPick(
            charm_id=cid,
            name=charm.name if charm else cid,
            label=label,
            category=charm.category if charm else "",
            source=source, counts_toward_pool=counts,
            caste_favored=bool(charm) and _charm_is_caste_favored(
                charm, cf_set, caste_attr_category, caste_fav_attrs),
        )

    picks: list[CharmPick] = []

    for cid in charms:
        charm = ruleset.charms.get(cid)
        picks.append(_pick(cid, charm, charm.name if charm else cid, source="charms"))

    ox = ox_body_charm(ruleset, character)
    if ox is not None:
        labels = {v.key: v.label for v in ox.variants}
        for p in ox_body:
            picks.append(_pick(
                ox.id, ox, f"{ox.name} ({labels.get(p.variant, p.variant)})",
                source="ox_body"))

    gift = gift_charm(ruleset, character)
    if gift is not None:
        labels = {v.key: v.label for v in gift.variants}
        for p in beastman_gifts:
            taken = ", ".join(labels.get(k, k) for k in p.gifts)
            picks.append(_pick(gift.id, gift, f"{gift.name} ({taken})",
                               source="beastman_gifts"))

    # Generic variant-menu Charms (Zenith p.72-73).
    for p in variant_purchases:
        charm = ruleset.charms.get(p.charm_id)
        if charm is None:
            picks.append(_pick(p.charm_id, None, p.charm_id,
                               source="variant_purchases"))
            continue
        labels = {v.key: v.label for v in charm.variants}
        taken = ", ".join(labels.get(k, k) for k in p.variants)
        picks.append(_pick(charm.id, charm, f"{charm.name} ({taken})" if taken
                           else charm.name, source="variant_purchases"))

    for cid in granted:
        charm = ruleset.charms.get(cid)
        picks.append(_pick(cid, charm, f"{charm.name if charm else cid} (granted)",
                           source="granted", counts=False))

    # Charms that the ORIGIN grants (Lookshy, p.68). Derived from the budget row, not
    # stored. A Charm that the character also bought is listed one time: the bought
    # copy.
    held = {p.charm_id for p in picks}
    for cid in origin_granted_charm_ids(ruleset, character):
        if cid in held:
            continue
        charm = ruleset.charms.get(cid)
        picks.append(_pick(cid, charm, f"{charm.name if charm else cid} (origin)",
                           source="origin", counts=False))

    return picks


def origin_granted_charm_ids(ruleset: RuleSet, character: Character) -> list[str]:
    """Return the Charm ids that the origin grants free at creation (Lookshy, p.68)."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return list(b.granted_charms)


def charm_pick_count(ruleset: RuleSet, character: Character) -> int:
    """Return the spent chargen Charm picks: `charm_picks` minus granted Charms."""
    return sum(1 for p in charm_picks(ruleset, character) if p.counts_toward_pool)


def charm_pick_bp_costs(ruleset: RuleSet, character: Character,
                        picks: list[CharmPick]) -> list[int]:
    """Return the bonus-point price of each pool-counting pick in `picks`, in order.

    The most specific rate wins:

      Calling         (Cult of the Illuminated, p.90)   4 BP, 3 if Caste/Favoured
      Immaculate      (DB, p.151)                       10 / 7
      Martial Arts    (Sidereal, p.101)                 8 / 6, None → the ordinary rate
      ordinary                                          charm / charm_favored_caste

    An unknown id is not priced. ⚠ Spells share the Charm pool. The caller prices
    them.
    """
    bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin, character.upbringing)
    # Local import: `illuminated` imports this module.
    from . import illuminated
    call_charms = illuminated.calling_charm_ids(ruleset, character)
    costs: list[int] = []
    for pick in picks:
        if not pick.counts_toward_pool:
            continue
        charm = ruleset.charms.get(pick.charm_id)
        if charm is None:
            continue
        cf = pick.caste_favored
        if pick.charm_id in call_charms:
            costs.append(bp_costs.calling_charm_favored_caste if cf
                         else bp_costs.calling_charm)
        elif charm.immaculate:
            costs.append(bp_costs.immaculate_charm_favored_caste if cf
                         else bp_costs.immaculate_charm)
        elif charm.category.startswith("martial_arts"):
            # None on other splats: the ordinary Charm rate applies.
            rate = (bp_costs.martial_arts_charm_favored_caste if cf
                    else bp_costs.martial_arts_charm)
            if rate is None:
                rate = bp_costs.charm_favored_caste if cf else bp_costs.charm
            costs.append(rate)
        elif charm.grants_circle is not None and bp_costs.magic_charm:
            # God-Blooded p.50: the initiation Charms. Flat. 0 = the ordinary rate.
            costs.append(bp_costs.magic_charm)
        elif bp_costs.charm_cross_pattern and mountain_folk_cross_pattern(
                ruleset, character, charm):
            # CH6 p.233: a Charm of another caste's Pattern.
            costs.append(bp_costs.charm_cross_pattern)
        else:
            costs.append(bp_costs.charm_favored_caste if cf else bp_costs.charm)
        # Brigid's Heir doubles the BP cost too, except on the sorcery line. Per pick.
        costs[-1] = merits.adjust_charm_cost(ruleset, character, charm, costs[-1])
    return costs


def _repeatable_purchase_cap(charm: Charm, character: Character) -> int:
    """Return the maximum purchases of a repeatable Charm. Return 0 if it is not
    repeatable or the cap trait does not resolve.

    The cap fields, in order:

      repeatable_cap_highest_virtue   the highest Virtue (CH6 p.245)
      repeatable_cap_virtue           a named Virtue (PG p.83)
      repeatable_cap_ability          an Ability, an Attribute, or 'essence' (p.124)
      repeatable_cap_max              a FLAT ceiling over the result
                                      (CH6 pp.245-246)
    """
    cap = 0
    if charm.repeatable_cap_highest_virtue:
        cap = max(character.virtues.values())
    elif charm.repeatable_cap_ability or charm.repeatable_cap_virtue:
        if charm.repeatable_cap_ability == "essence":
            cap = character.essence_rating
        elif charm.repeatable_cap_virtue:
            try:
                cap = character.virtues[VirtueName(charm.repeatable_cap_virtue)]
            except ValueError:
                return 0
        else:
            try:
                cap = character.abilities[AbilityName(charm.repeatable_cap_ability)]
            except ValueError:
                try:
                    cap = character.attributes[AttributeName(charm.repeatable_cap_ability)]
                except ValueError:
                    return 0
    if charm.repeatable_cap_max and cap:
        cap = min(cap, charm.repeatable_cap_max)
    return cap


def _category_ability(category: str) -> AbilityName | None:
    """Return the Ability that gates the minimum of `category`. 'melee' gives Melee.
    'martial_arts:<style>' gives Martial Arts. Other categories ('sorcery') give
    None."""
    base = category.split(":", 1)[0]      # 'martial_arts:tiger' -> 'martial_arts'
    try:
        return AbilityName(base)
    except ValueError:
        return None


def _mountain_folk_pattern(charm: Charm) -> str | None:
    """Return the Mountain Folk Pattern of a Charm ('foundation' | 'worker' |
    'warrior' | 'artisan' | 'enlightened') from the 'mountain_folk:<pattern>'
    category, or None (CH6 p.244)."""
    if not charm.category.startswith("mountain_folk:"):
        return None
    return charm.category.split(":", 1)[1]


def _mountain_folk_unenlightened_bar(character: Character, charm: Charm) -> bool:
    """Return True if an Unenlightened Jadeborn can never hold `charm`: it is
    outside their Caste Pattern and the Foundation Pattern (CH6 p.244).

    ⚠ A LIFETIME rule. Both `charm_matches_splat` and `meets_charm_requirements`
    read it. `foreign_charms_barred` handles non-Mountain-Folk Charms.
    """
    if character.exalt_type != "Mountain-Folk" or character.origin != "unenlightened":
        return False
    pat = _mountain_folk_pattern(charm)
    if pat is None:
        return False
    return pat not in ("foundation", character.caste)


def mountain_folk_cross_pattern(ruleset: RuleSet, character: Character,
                                charm: Charm) -> bool:
    """Return True if `charm` is from ANOTHER caste's Pattern for this character
    (12 XP / 7 BP, CH6 pp.233-237). The Foundation, Enlightened and own Caste
    Patterns are not another caste."""
    if ruleset.exalt_for(character.exalt_type).id != "Mountain-Folk":
        return False
    pat = _mountain_folk_pattern(charm)
    return pat in ("worker", "warrior", "artisan") and pat != character.caste


def _min_trait_rating(character: Character, charm: Charm) -> tuple[str, int] | None:
    """Return (trait name, rating) for `charm.min_ability`, or None if no trait.

    Order (a Charm sets one; the order breaks a tie):

      min_virtue      a Virtue    (ghost Arcanoi, E:Ab p.234)
      min_attribute   an Attribute (Lunar Attribute-keyed Charms, p.122)
      category        the Ability the category names

    ⚠ The named keys MUST come first: 'melee' is also an AbilityName, thus a Lunar
    Melee Charm on Dexterity would be checked against Melee.
    """
    if charm.min_virtue:
        try:
            virtue = VirtueName(charm.min_virtue)
        except ValueError:
            return None
        return virtue.value, character.virtues.get(virtue, 0)
    if charm.min_attribute:
        try:
            attr = AttributeName(charm.min_attribute)
        except ValueError:
            return None
        return attr.value, character.attributes.get(attr, 0)
    ability = _category_ability(charm.category)
    if ability is None:
        return None
    return ability.value, ability_rating(character, ability)


def charm_ability_shortfalls(character: Character, charm: Charm) -> list[tuple[str, int, int]]:
    """Return each trait minimum of `charm` that the character FAILS, as (trait
    label, required, held). Empty = all met.

    Covers `min_ability` and `extra_min_abilities` / `extra_min_attributes`
    (Cult of the Illuminated, p.102). Each extra is OR over its traits.

    ⚠ THE one place for this question. Do not compare
    `_min_trait_rating(...)[1] < charm.min_ability` directly: that misses the extras.
    """
    out: list[tuple[str, int, int]] = []
    trait = _min_trait_rating(character, charm)
    if trait is not None:
        label, held = trait
        if held < charm.min_ability:
            out.append((label, charm.min_ability, held))
    for req in charm.extra_min_abilities:
        # AbilityMinimum is OR over its `abilities`, so the best of them counts.
        best = max((ability_rating(character, ab) for ab in req.abilities), default=0)
        if best < req.rating:
            out.append((" or ".join(a.value for a in req.abilities), req.rating, best))
    for req in charm.extra_min_attributes:
        best = max((character.attributes.get(at, 0) for at in req.attributes), default=0)
        if best < req.rating:
            out.append((" or ".join(a.value for a in req.attributes), req.rating, best))
    return out


def charm_ability_requirements(charm: Charm) -> list[tuple[str, int]]:
    """Return each Ability/Attribute minimum of a Charm, as (trait label, rating),
    for display. The primary gate first. ⚠ Presenters must use this, not
    `min_ability` alone."""
    out: list[tuple[str, int]] = []
    if charm.min_virtue:
        out.append((charm.min_virtue, charm.min_ability))
    elif charm.min_attribute:
        out.append((charm.min_attribute, charm.min_ability))
    else:
        ability = _category_ability(charm.category)
        if ability is not None:
            out.append((ability.value, charm.min_ability))
    for req in charm.extra_min_abilities:
        out.append((" or ".join(a.value for a in req.abilities), req.rating))
    for req in charm.extra_min_attributes:
        out.append((" or ".join(a.value for a in req.attributes), req.rating))
    return out


def charm_count_shortfalls(ruleset: RuleSet, held_ids, charm: Charm
                           ) -> list[tuple[CharmCountRequirement, int]]:
    """Return the unmet count prerequisites of `charm`, as (requirement, held).
    Counts by `category`.

    ⚠ The Charm never counts toward its OWN requirement.

    ⚠ `check_charm_prerequisites` and `meets_charm_requirements` both use this, thus
    the picker and the sheet agree. Do not fork it.
    """
    if not charm.prerequisite_counts:
        return []
    out = []
    for req in charm.prerequisite_counts:
        have = sum(1 for cid in held_ids
                   if cid != charm.id
                   and (c := ruleset.charms.get(cid)) is not None
                   and c.category == req.category)
        if have < req.count:
            out.append((req, have))
    return out


def charm_count_requirement_label(req: CharmCountRequirement) -> str:
    """Return the display text of a count prerequisite: "any 3 Occult Charms"."""
    noun = req.label or req.category.replace("_", " ").title()
    return f"any {req.count} {noun} Charm{'s' if req.count != 1 else ''}"


def is_immaculate_charm(charm: Charm) -> bool:
    """Return `Charm.immaculate`: an Immaculate Order Charm (Dragon-Blooded ch.6),
    for the Immaculate chargen path (p.151)."""
    return charm.immaculate


def _immaculate_path(ruleset: RuleSet, charm_ids, exalt_type: str) -> bool:
    """Return True if a Dragon-Blooded holds an Immaculate Order Charm in this
    selection. The path changes the rules: one element tree, a 5-Charm pool, the
    Immaculate BP row, and no Caste/Favoured minimum.

    ⚠ Tests `exalt_type`: the package is Dragon-Blooded only. A Solar with an
    `open_to_all` Terrestrial style pays the ordinary Martial Arts rate.
    """
    return exalt_type == "Dragon-Blooded" and any(
        (c := ruleset.charms.get(cid)) is not None and c.immaculate
        for cid in charm_ids)


def immaculate_martial_artist(ruleset: RuleSet, character: Character) -> bool:
    """Return `_immaculate_path` over the chargen Charm source (live, or the
    snapshot)."""
    charms = _chargen_source(character)[6]     # (…, charms, …) — see _chargen_source
    return _immaculate_path(ruleset, charms, character.exalt_type)


def check_charm_prerequisites(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check each known Charm: min essence, min ability, and the AND-of-OR
    prerequisites. Skips an unknown id (check_references reports it)."""
    issues: list[Issue] = []
    known = set(character.charms)
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue

        if character.essence_rating < charm.min_essence:
            issues.append(Issue(
                code="charm-min-essence", where=cid,
                message=(f"{charm.name}: requires Essence {charm.min_essence}, "
                         f"character has {character.essence_rating}."),
            ))

        if not charm_virtue_cap_met(character, charm):
            over = sorted(n.value if hasattr(n, "value") else str(n)
                          for n, v in character.virtues.items() if v > charm.max_virtue)
            issues.append(Issue(
                code="charm-max-virtue", where=cid,
                message=(f"{charm.name}: no Virtue may exceed {charm.max_virtue}; "
                         f"{', '.join(over)} too high."),
            ))

        for trait_name, want, held in charm_ability_shortfalls(character, charm):
            issues.append(Issue(
                code="charm-min-ability", where=cid,
                message=(f"{charm.name}: requires {trait_name} "
                         f"{want}, character has {held}."),
            ))

        # AND-of-OR: every inner group must be satisfied by at least one known id.
        for group in charm.prerequisites:
            if not any(req in known for req in group):
                needed = " or ".join(
                    ruleset.charms[r].name if r in ruleset.charms else r for r in group)
                issues.append(Issue(
                    code="charm-prerequisite", where=cid,
                    message=f"{charm.name}: unmet prerequisite — needs {needed}.",
                ))

        # Breadth prerequisites: "any three Lore Charms" (Aspect Books).
        for req, have in charm_count_shortfalls(ruleset, known, charm):
            issues.append(Issue(
                code="charm-prerequisite-count", where=cid,
                message=(f"{charm.name}: unmet prerequisite — needs "
                         f"{charm_count_requirement_label(req)}, character has {have}."),
            ))
    # A generic repeatable Charm (CH6 pp.245-246): cap the copies, on both sides of
    # the lock.
    for cid, n in Counter(character.charms).items():
        if n < 2:
            continue
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        cap = _repeatable_purchase_cap(charm, character)
        if cap and n > cap:
            issues.append(Issue(
                code="repeatable-charm-over-cap", where=cid,
                message=(f"{charm.name} bought {n} times; it may be bought at most "
                         f"{cap} times."),
            ))
    return issues


# The Dragon-Blooded enlightenment gate (DB p241-242): a Dragon-Blooded needs one
# PAIR of enlightenment Charms before a Dragon Path Charm. Other splats need no pair
# (p241).
#
# ⚠ THREE pairs. Any ONE pair opens the gate (PG p.236).
DB_MA_ENLIGHTENMENT_PAIRS = (
    # Immaculate (DB p.241-242)
    ("dragonblooded.martial-arts.spirit-sight",
     "dragonblooded.martial-arts.spirit-walking"),
    # Iris-Bulb — the Shogunate mandarins' initiation (PG p.236)
    ("dragonblooded.martial-arts.walker-among-irises-perception",
     "dragonblooded.martial-arts.iris-bulb-discourse"),
    # Tiger-and-Bear — used on elite military units (PG p.237)
    ("dragonblooded.martial-arts.tiger-and-bear-awareness",
     "dragonblooded.martial-arts.tiger-and-bear-unity"),
)


def _is_dragon_path_style(ruleset: RuleSet, category: str) -> bool:
    """Return True if the enlightenment gate applies to this style category: a
    **Celestial** style (PG p.236; human's ruling), from any Charm of the category.

    ⚠ Use the tier, never a name list. An uninitiated Dragon-Blooded reaches each
    TERRESTRIAL style and Jade Mountain (no tier).
    """
    if not category.startswith("martial_arts:"):
        return False
    for charm in ruleset.charms.values():
        if charm.category == category:
            return "Celestial" in charm.open_to_tiers
    return False


def db_enlightenment_met(character: Character) -> bool:
    """Return True if the enlightenment gate is OPEN: a Dragon-Blooded knows both
    Charms of one pair (DB p.241-242, PG pp.236-237).

    ⚠ Also True for each NON-Dragon-Blooded. Safe as a BAR, dangerous as a GRANT:
    scope a grant (PG p.235) to the splat, not to this predicate.
    """
    if character.exalt_type != "Dragon-Blooded":
        return True
    known = set(character.charms)
    return any(all(cid in known for cid in pair)
               for pair in DB_MA_ENLIGHTENMENT_PAIRS)


def category_available(ruleset: RuleSet, character: Character, category: str) -> bool:
    """Return True if the picker can show the style `category` now. The only gate
    is the Dragon-Blooded Dragon-Path rule (p241)."""
    return not (_is_dragon_path_style(ruleset, category)
                and not db_enlightenment_met(character))


def meets_charm_requirements(ruleset: RuleSet, character: Character, charm) -> bool:
    """Return True if the character can learn `charm` now: min essence, min ability,
    each AND-of-OR group, and for a Dragon-Blooded the enlightenment gate (p241).
    The forward-looking form of check_charm_prerequisites. The picker uses it."""
    if _is_dragon_path_style(ruleset, charm.category) and not db_enlightenment_met(character):
        return False
    if _mountain_folk_unenlightened_bar(character, charm):
        # CH6 p.244: the forward-looking form of the charm_matches_splat bar.
        return False
    if character.essence_rating < charm.min_essence:
        return False
    if not charm_virtue_cap_met(character, charm):
        return False
    if charm_ability_shortfalls(character, charm):
        return False
    known = set(character.charms)
    if charm_count_shortfalls(ruleset, known, charm):
        return False
    return all(any(req in known for req in group) for group in charm.prerequisites)


def charms_depending_on(ruleset: RuleSet, character: Character, charm_id: str) -> list[str]:
    """Return the names of owned Charms that lose a prerequisite if `charm_id` is
    removed. Empty = safe to remove."""
    remaining = set(character.charms) - {charm_id}
    blockers = []
    for oid in character.charms:
        if oid == charm_id:
            continue
        charm = ruleset.charms.get(oid)
        if charm is None:
            continue
        if any(charm_id in group and not any(r in remaining for r in group)
               for group in charm.prerequisites):
            blockers.append(charm.name)
    return blockers


def _charm_name(ruleset, charm_id: str) -> str:
    charm = ruleset.charms.get(charm_id)
    return charm.name if charm is not None else charm_id


def repeatable_cap_trait_name(charm: Optional[Charm]) -> str:
    """Return the name of the cap trait of a repeatable Charm, for messages:
    "Endurance", "Stamina", "Essence". "" if absent or not repeatable. Data
    (`repeatable_cap_ability`, p.132): do not hardcode it."""
    name = charm.repeatable_cap_ability if charm else ""
    return name.replace("_", " ").title() if name else ""


def repeatable_cap_unit(charm: Optional[Charm]) -> str:
    """Return the unit of the cap trait: "point" for Essence, "dot" otherwise. ""
    if `repeatable_cap_trait_name` gives ""."""
    name = charm.repeatable_cap_ability if charm else ""
    if not name:
        return ""
    return "point" if name == "essence" else "dot"


def ox_body_cap(ruleset: RuleSet, character: Character) -> int:
    """Return the maximum Ox-Body purchases: one per dot of `repeatable_cap_ability`
    (Stamina for Lunar, p.132). 0 if absent."""
    charm = ox_body_charm(ruleset, character)
    if charm is None:
        return 0
    return _repeatable_purchase_cap(charm, character)


def check_ox_body(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check the Ox-Body purchases: one per dot of the cap trait at most (core
    p.170), each package a real variant, min essence met. Costs are elsewhere."""
    issues: list[Issue] = []
    purchases = character.ox_body
    if not purchases:
        return issues
    oid = ox_body_charm_id(ruleset, character)
    charm = ox_body_charm(ruleset, character)
    if charm is None:
        issues.append(Issue(
            code="ox-body-unknown", where=oid,
            message="Character has Ox-Body purchases but the Charm is not in the RuleSet.",
        ))
        return issues
    cap = ox_body_cap(ruleset, character)
    if len(purchases) > cap:
        issues.append(Issue(
            code="ox-body-over-cap", where=oid,
            message=(f"Ox-Body Technique bought {len(purchases)} times; it may be "
                     f"bought at most once per dot of "
                     f"{repeatable_cap_trait_name(charm)} ({cap})."),
        ))
    if character.essence_rating < charm.min_essence:
        issues.append(Issue(
            code="ox-body-min-essence", where=oid,
            message=(f"Ox-Body Technique requires Essence {charm.min_essence}, "
                     f"character has {character.essence_rating}."),
        ))
    valid_keys = {v.key for v in charm.variants}
    for p in purchases:
        if p.variant not in valid_keys:
            issues.append(Issue(
                code="ox-body-bad-variant", where=p.variant,
                message=f"Ox-Body Technique: unknown health-level package {p.variant!r}.",
            ))
    return issues


def gift_purchase_cap(ruleset: RuleSet, character: Character) -> int:
    """Return the maximum Gift Charm purchases: Essence (p.124). 0 if none. A
    heritage cap (p.47) wins."""
    spec = heritage_gift_spec(ruleset, character)
    if spec is not None and spec[1] is not None:
        return spec[1]
    charm = gift_charm(ruleset, character)
    if charm is None:
        return 0
    return _repeatable_purchase_cap(charm, character)


def gifts_per_purchase(charm: Charm, purchase_index: int) -> int:
    """Return the Gifts of the purchase at `purchase_index` (0-based):
    `variant_picks_first_purchase` for 0, else `variant_picks_per_purchase` (p.124)."""
    return (charm.variant_picks_first_purchase if purchase_index == 0
            else charm.variant_picks_per_purchase)


def known_gift_keys(character: Character) -> list[str]:
    """Return all purchased Gift keys, flattened. A Gift bought two times is listed
    two times."""
    return [g for p in character.beastman_gifts for g in p.gifts]


def check_gift_prerequisites(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check the Gift prerequisites. `CharmVariant.prerequisites` names other
    variant keys of the SAME Charm (p.126-127), not Charm ids."""
    issues: list[Issue] = []
    charm = gift_charm(ruleset, character)
    if charm is None:
        return issues
    variants_by_key = {v.key: v for v in charm.variants}
    known = set(known_gift_keys(character))
    for key in known:
        variant = variants_by_key.get(key)
        if variant is None:
            continue          # reported separately as beastman-gift-bad-variant
        for group in variant.prerequisites:
            if not any(pid in known for pid in group):
                issues.append(Issue(
                    code="gift-prerequisite-missing", where=key,
                    message=f"Gift {key!r} requires one of {sorted(group)!r}, "
                            "none of which is known.",
                ))
    return issues


def check_beastman_gifts(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Check the Gift Charm purchases: count <= Essence (p.124), the Gift count of
    each purchase, each Gift a real variant, `max_purchases`, and the
    prerequisites. Costs are elsewhere."""
    issues: list[Issue] = []
    purchases = character.beastman_gifts
    if not purchases:
        return issues
    gid = gift_charm_id(ruleset, character)
    charm = gift_charm(ruleset, character)
    if charm is None:
        issues.append(Issue(
            code="beastman-gift-unknown-charm", where=gid,
            message="Character has Beastman Gift purchases but the Charm is not "
                    "in the RuleSet.",
        ))
        return issues
    cap = gift_purchase_cap(ruleset, character)
    if len(purchases) > cap:
        issues.append(Issue(
            code="beastman-gift-over-cap", where=gid,
            message=(f"{charm.name} bought {len(purchases)} times; it may be "
                     f"bought at most once per point of Essence ({cap})."),
        ))
    if character.essence_rating < charm.min_essence:
        issues.append(Issue(
            code="beastman-gift-min-essence", where=gid,
            message=(f"{charm.name} requires Essence {charm.min_essence}, "
                     f"character has {character.essence_rating}."),
        ))
    valid_keys = {v.key for v in charm.variants}
    for i, p in enumerate(purchases):
        expected = gifts_per_purchase(charm, i)
        if len(p.gifts) != expected:
            issues.append(Issue(
                code="beastman-gift-wrong-count", where=gid,
                message=(f"Purchase {i + 1} of {charm.name} grants {expected} "
                         f"Gift(s), but {len(p.gifts)} were chosen."),
            ))
        for key in p.gifts:
            if key not in valid_keys:
                issues.append(Issue(
                    code="beastman-gift-bad-variant", where=key,
                    message=f"{charm.name}: unknown Gift {key!r}.",
                ))
    counts: dict[str, int] = {}
    for key in known_gift_keys(character):
        counts[key] = counts.get(key, 0) + 1
    for key, n in counts.items():
        variant = next((v for v in charm.variants if v.key == key), None)
        if variant is not None and n > variant.max_purchases:
            issues.append(Issue(
                code="beastman-gift-over-repeat-cap", where=key,
                message=(f"Gift {key!r} taken {n} times; it may be taken at most "
                         f"{variant.max_purchases} time(s)."),
            ))
    issues += check_gift_prerequisites(ruleset, character)
    return issues


def _charm_attribute_caste_favored(charm: Charm, caste_attr_category: str | None) -> bool:
    """Return True if the `min_attribute` category of an Attribute-keyed (Lunar)
    Charm is the favored category of the caste (p.122)."""
    if not charm.min_attribute or caste_attr_category is None:
        return False
    try:
        attr = AttributeName(charm.min_attribute)
    except ValueError:
        return False
    return _attribute_category(attr) == caste_attr_category


def _charm_is_caste_favored(charm: Charm, cf_set: set, caste_attr_category: str | None,
                             caste_fav_attrs: set) -> bool:
    """Return True if `charm` is Caste/Favoured for the character. The BP price,
    the chargen minimum and the Slot rule all use this.

    Ability-keyed: the category Ability is Caste or Favoured. Attribute-keyed:
    `caste_favored` mode (Alchemical) tests the Attribute; else (Lunar) the
    Attribute category."""
    ability = _category_ability(charm.category)
    if ability is not None and ability in cf_set:
        return True
    if charm.min_attribute:
        if caste_fav_attrs:
            try:
                return AttributeName(charm.min_attribute) in caste_fav_attrs
            except ValueError:
                return False
        return _charm_attribute_caste_favored(charm, caste_attr_category)
    return False


def charm_fits_dedicated_slot(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Return True if `charm` can go in a Dedicated Slot (p.88): it is keyed to a
    Caste or Favored Attribute."""
    cf_set = caste_favored_abilities(ruleset, character)
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)
    caste_fav_attrs = _caste_favored_attr_names(ruleset, character)
    return _charm_is_caste_favored(charm, cf_set, caste_attr_category, caste_fav_attrs)


def uses_charm_slots(ruleset: RuleSet, character: Character) -> bool:
    """Return True if the splat uses Charm Slots (p.88-89): the budget has free
    Slots."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return (b.charm_slots_general + b.charm_slots_dedicated) > 0


def splat_uses_charm_slots(ruleset: RuleSet, splat: str) -> bool:
    """Return True if the splat `splat` uses Charm Slots. No character needed."""
    b = ruleset.budgets_for(splat)
    return (b.charm_slots_general + b.charm_slots_dedicated) > 0


def crossover_alchemical_charm(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Return True if a non-Alchemical learns an Alchemical Charm through the p.90
    crossover, which grants a General Slot."""
    return (not uses_charm_slots(ruleset, character)
            and foreign_charms_open(ruleset, character)
            and is_foreign_charm(ruleset, character, charm)
            and splat_uses_charm_slots(ruleset, splat_of(charm)))


def crossover_panoply_xp(ruleset: RuleSet, character: Character) -> Optional[int]:
    """Return the flat XP to add an Alchemical Charm to the Panoply with no Slot
    (p.90, 8), or None. The generalist rule must be open."""
    if not foreign_charms_open(ruleset, character):
        return None
    caste = ruleset.castes.get(character.caste)
    return caste.foreign_panoply_charm_xp if caste is not None else None


def charm_slot_counts(ruleset: RuleSet, character: Character) -> tuple[int, int, int, int]:
    """Return (general, dedicated, base_general, base_dedicated) Slot counts. None
    gives the free base. BP accounting charges above the base."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    bg, bd = b.charm_slots_general, b.charm_slots_dedicated
    g = character.general_charm_slots if character.general_charm_slots is not None else bg
    d = character.dedicated_charm_slots if character.dedicated_charm_slots is not None else bd
    return g, d, bg, bd


def charm_slot_usage(ruleset: RuleSet, character: Character) -> tuple[int, int, int]:
    """Return (installed, noncf, install_motes) for a Slot splat, from the chargen
    source. The chargen Slot check and the UI both use it.

    PLM Martial Arts Charms use no Slot. Each Ox-Body purchase uses one."""
    src = _chargen_source(character)
    charms, ox_body, arrays = src[6], src[9], src[13]
    cf_set = caste_favored_abilities(ruleset, character)
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)
    caste_fav_attrs = _caste_favored_attr_names(ruleset, character)
    installed = noncf = 0
    for cid in charms:
        charm = ruleset.charms.get(cid)
        if charm is None or not charm_occupies_slot(ruleset, character, charm):
            continue
        installed += 1
        if not _charm_is_caste_favored(charm, cf_set, caste_attr_category, caste_fav_attrs):
            noncf += 1
    ob_charm = ox_body_charm(ruleset, character)
    if ob_charm is not None and ox_body:
        installed += len(ox_body)
        if not _charm_is_caste_favored(ob_charm, cf_set, caste_attr_category, caste_fav_attrs):
            noncf += len(ox_body)
    # Local import: `alchemical` imports this module.
    from . import alchemical
    install_motes = alchemical._installation_motes(ruleset, charms, arrays)
    if ob_charm is not None:
        install_motes += ob_charm.installation_cost * len(ox_body)
    return installed, noncf, install_motes


def splat_of(charm: Charm) -> str:
    """Return `charm.exalt_type`."""
    return charm.exalt_type


def charms_available(ruleset: RuleSet, character: Character) -> bool:
    """Return False if the splat cannot hold Charms (core p.103). See
    `ExaltDefinition.charms_available`."""
    return ruleset.exalt_for(character.exalt_type).charms_available


def charm_restriction_met(character: Character, charm: Charm) -> bool:
    """Return True if the character matches `Charm.restricted_to`
    ("<Splat>" / "<Splat>:<caste>"). It narrows access only. Empty = no restriction."""
    if not charm.restricted_to:
        return True
    for entry in charm.restricted_to:
        splat, _, caste = entry.partition(":")
        if character.exalt_type != splat:
            continue
        if not caste or (character.caste or "").lower() == caste.lower():
            return True
    return False


def charm_virtue_cap_met(character: Character, charm: Charm) -> bool:
    """Return True if no Virtue is above `Charm.max_virtue`."""
    if not charm.max_virtue:
        return True
    return all(v <= charm.max_virtue for v in character.virtues.values())


def charm_matches_splat(character: Character, charm: Charm,
                        ruleset: Optional[RuleSet] = None) -> bool:
    """Return True if `charm` is available to the character: the picker filter and
    the `charm-wrong-splat` check. A Charm matches if

      * it belongs to the character's own Exalt type, OR
      * it is flagged `open_to_all`, OR
      * the character's Exalt TIER reaches `charm.open_to_tiers`.

    ⚠ The tier test needs `ruleset`. Without it the answer is narrower, with no error.

    ⚠ A splat with no Charms (core p.103) matches NOTHING, and that test comes first.
    `engine.merits` decides what a Merit opens.
    """
    # ⚠ Virtual rows (Path powers, rules_db._virtual_path_charms) are never
    # learnable. Checked first.
    if charm.virtual:
        return False
    # PG p.249: narrowing only. Above the grants.
    if not charm_restriction_met(character, charm):
        return False
    # ⚠ Charms barred to the splat and to the heritage. Above all grants.
    if ruleset is not None and charm.id in ruleset.exalt_for(character.exalt_type).barred_charm_ids:
        return False
    # CH6 p.244: a LIFETIME bar.
    if _mountain_folk_unenlightened_bar(character, charm):
        return False
    if ruleset is not None and charm.id in heritage_barred_charm_ids(ruleset, character):
        return False
    # The heritage magic TRACK (p.48).
    if ruleset is not None and heritage_bars_initiation(ruleset, character, charm):
        return False
    if ruleset is not None and not charms_available(ruleset, character):
        eff = merits.merits_and_flaws_calc(ruleset, character)
        if charm.id in eff.barred_charm_ids:
            return False
        if eff.bar_immaculate_charms and is_immaculate_charm(charm):
            return False
        # A Merit opens a CATEGORY. `martial_arts:<style>` matches on the prefix.
        root = charm.category.split(":", 1)[0]
        if root not in eff.open_charm_categories:
            return False
        # The ordinary splat/tier rules still apply in the category.
        return charm.open_to_all or "Terrestrial" in charm.open_to_tiers
    # E:Ab p.126: other splats' Charms are barred. ⚠ Check before `open_to_all`.
    if ruleset is not None and ruleset.exalt_for(character.exalt_type).foreign_charms_barred:
        # p.47: the heritage can hold native Charms.
        if (splat_of(charm) == character.exalt_type
                and heritage_charms_available(ruleset, character)):
            return True
        # PG p.47: the borrowed catalogue of the heritage. A NATIVE match.
        if splat_of(charm) in heritage_charm_access(ruleset, character):
            return True
        # PG p.234: Terrestrial martial arts, by the `martial_arts:` prefix.
        return (ruleset.exalt_for(character.exalt_type).terrestrial_martial_arts
                and is_terrestrial_martial_arts(charm))
    # CH3 p.100: an Alchemical needs Perfected Lotus Matrix for any martial arts.
    # ⚠ Check before `open_to_all`.
    if (character.exalt_type == "Alchemical" and is_martial_arts_charm(charm)
            and not has_perfected_lotus_matrix(character)):
        return False
    # PG p.235: a Lunar can never learn Sidereal martial arts. A LUNAR bar, not a
    # Celestial-tier bar. ⚠ Above the tier grant: the Sidereal styles are
    # `open_to_tiers: ["Celestial"]`.
    if character.exalt_type == "Lunar" and charm.ma_tier == "Sidereal":
        return False
    if charm.open_to_all or splat_of(charm) == character.exalt_type:
        return True
    if ruleset is not None and charm.open_to_tiers:
        if tier_reaches(ruleset.exalt_for(character.exalt_type).tier,
                        charm.open_to_tiers):
            return True
    # PG pp.235-236: an INITIATED Terrestrial reaches Celestial martial arts. Never
    # higher (decision 0015).
    #
    # ⚠ Test the SPLAT, not the tier. `db_enlightenment_met` is True for each
    # non-Dragon-Blood. PG p.235 bars Dragon Kings.
    if (charm.ma_tier == "Celestial"
            and character.exalt_type == "Dragon-Blooded"
            and db_enlightenment_met(character)):
        return True
    return False


PERFECTED_LOTUS_MATRIX_ID = "alchemical.close-combat.perfected-lotus-matrix"


# The Exalt tiers, low to high (human's ruling; decision 0015). A splat reaches its
# own tier and each tier below.
#
# ⚠ Never an equality test. Else Solar cannot reach Celestial martial arts.
TIER_ORDER = ("Terrestrial", "Celestial", "Solar")


def tier_rank(tier: str) -> int:
    """Return the rank of `tier`, or -1 for a tier outside the order (Mortal,
    Ghost)."""
    return TIER_ORDER.index(tier) if tier in TIER_ORDER else -1


def tier_reaches(character_tier: str, charm_tiers: list[str]) -> bool:
    """Return True if the rank of `character_tier` is at least the LOWEST tier in
    `charm_tiers`."""
    mine = tier_rank(character_tier)
    if mine < 0:
        return False
    ranks = [tier_rank(t) for t in charm_tiers if tier_rank(t) >= 0]
    return bool(ranks) and mine >= min(ranks)


def is_martial_arts_charm(charm: Charm) -> bool:
    """Return True if the category of `charm` is a `martial_arts:*` tree."""
    return charm.category.startswith("martial_arts")


def has_perfected_lotus_matrix(character: Character) -> bool:
    """Return True if Perfected Lotus Matrix is installed (CH3 p.100)."""
    return PERFECTED_LOTUS_MATRIX_ID in character.charms


def charm_occupies_slot(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Return True if an installed Charm uses a Slot. All Alchemical Charms do,
    including each Ox-Body purchase (human's ruling), except PLM Martial Arts Charms
    (CH3 p.100)."""
    return not (is_martial_arts_charm(charm) and splat_of(charm) != character.exalt_type)


def foreign_charms_caste(ruleset: RuleSet, character: Character):
    """Return the CasteDefinition if `CasteDefinition.foreign_charms` is set (core
    p.127), else None."""
    caste = ruleset.castes.get(character.caste)
    return caste if caste is not None and caste.foreign_charms else None


def heritage_charm_access(ruleset: RuleSet, character: Character) -> frozenset[str]:
    """Return the exalt_types whose Charms the heritage learns natively (PG p.47).
    `charm_access`, or `character.origin` if `charm_access_parent` is set. Empty for
    non-God-Blooded castes.
    """
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return frozenset()
    if caste.heritage_traits.charm_access_parent:
        return frozenset({character.origin}) if character.origin else frozenset()
    return frozenset(caste.heritage_traits.charm_access)


def heritage_charms_available(ruleset: RuleSet, character: Character) -> bool:
    """Return `GodbloodedHeritage.charms_available` (p.47). The gate is at the
    native match in charm_matches_splat. The `charm_access` catalogue and the p.234
    martial arts still apply."""
    if ruleset is None:
        return True
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return True
    return caste.heritage_traits.charms_available


def heritage_barred_charm_ids(ruleset: RuleSet, character: Character) -> frozenset[str]:
    """Return `GodbloodedHeritage.barred_charm_ids` (p.47). ⚠ Both Charm gates check
    it first."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return frozenset()
    return frozenset(caste.heritage_traits.barred_charm_ids)


def heritage_magic_track(ruleset: RuleSet, character: Character) -> str:
    """Return the magic track of the heritage (PG p.48):

      "sorcery" / "necromancy"   that track only
      ""                         no restriction
      "none"                     no initiation at all (Fae-Blooded)

    ⚠ "none" and "" are OPPOSITES.

    The parent-keyed map wins where the parent has an entry. "" for non-God-Blooded
    castes.
    """
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return ""
    traits = caste.heritage_traits
    return traits.magic_track_by_parent.get(character.origin) or traits.magic_track


def heritage_bars_initiation(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Return True if the heritage track bars this INITIATION Charm (`grants_circle`
    of the other track). Ordinary Charms are not affected.

    ⚠ Charm access alone is not enough: an Abyssal Half-Caste borrows a catalogue
    with both tracks."""
    if charm.grants_circle is None:
        return False
    track = heritage_magic_track(ruleset, character)
    if track == "none":
        # Fae-Blooded: no initiation (p.48).
        return True
    if not track:
        return False
    allowed = TRACK_CIRCLES.get(track, ())
        # p.48: the FIRST circle of the track only. ⚠ The access gate does not read
        # min_essence, thus the Essence cap alone does not bar a higher circle.
    return charm.grants_circle not in allowed[:1]


def foreign_charms_permitted(character: Character) -> bool:
    """Return the stored Storyteller permission only (the chargen checkbox).
    `foreign_charms_open` is the engine question."""
    return character.house_rules is not None and character.house_rules.st_foreign_charms


def foreign_charms_open(ruleset: RuleSet, character: Character) -> bool:
    """Return True if the character can learn other splats' Charms now. The caste
    must allow it (p.127). Before the lock the Storyteller must permit it."""
    if foreign_charms_caste(ruleset, character) is None:
        return False
    return character.chargen_locked or foreign_charms_permitted(character)


def is_foreign_charm(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Return True if `charm` is reachable only through the p.127 generalist rule.
    The doubled XP price uses it. ⚠ `open_to_tiers` styles are native, not
    foreign."""
    return not charm_matches_splat(character, charm, ruleset)


def is_terrestrial_martial_arts(charm: Charm) -> bool:
    """Return True for a Terrestrial martial-arts Charm (Essence Mastery; PG p.234)."""
    return (charm.category.split(":", 1)[0] == "martial_arts"
            and (charm.open_to_all or "Terrestrial" in charm.open_to_tiers))


def charm_learnable_by_splat(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Return True if `charm` is native (charm_matches_splat) or reachable through
    the foreign-Charm privilege of the caste. The picker filter and the
    `charm-wrong-splat` check. accessible_circles uses the narrower
    charm_matches_splat."""
    # ⚠ The splat bar again: this function continues past a False answer into two
    # more grants. A bar on one route only is the most frequent defect here.
    if charm.id in ruleset.exalt_for(character.exalt_type).barred_charm_ids:
        return False
    # ⚠ The heritage bar again, for the same reason.
    if charm.id in heritage_barred_charm_ids(ruleset, character):
        return False
    if heritage_bars_initiation(ruleset, character, charm):
        return False
    if charm_matches_splat(character, charm, ruleset):
        return True
    # ⚠ E:Ab p.126 again, for the same reason.
    if ruleset.exalt_for(character.exalt_type).foreign_charms_barred:
        return (splat_of(charm) in heritage_charm_access(ruleset, character)
                or (ruleset.exalt_for(character.exalt_type).terrestrial_martial_arts
                    and is_terrestrial_martial_arts(charm)))
    # CH4: `no_foreign_learning` Charms are never reachable through the generalist
    # rule.
    return foreign_charms_open(ruleset, character) and not charm.no_foreign_learning
