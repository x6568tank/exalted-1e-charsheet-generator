"""
engine/validate/charms.py — Charm legality: who may learn what, and at what cost.

The largest and most cross-referenced of the validation domains, extracted from the
5,791-line `validate.py` on 2026-08-17 (plan: `docs/plans/validate-refactor.md`).
It owns:

  * **Access** — `charm_matches_splat`, `charm_learnable_by_splat`, `meets_charm_
    requirements`, the tier ladder (`tier_rank`/`tier_reaches`, decision 0015), the
    Immaculate paths, foreign Charms, and heritage Charm access.
  * **Prerequisites** — `check_charm_prerequisites` and the AND-of-OR graph, minimum
    Essence/Ability/Attribute, and Charm-count requirements.
  * **Picks and cost** — `charm_picks` and the ONE enumeration of a chargen Charm
    pick (an architecture invariant: there must not be a second).
  * **Slots** — the Alchemical Charm-slot economy (`charm_slot_counts`,
    `uses_charm_slots`, `charm_fits_dedicated_slot`).
  * **The repeatable Charms** — Ox-Body and the Lunar Gifts, which are stored off
    `Character.charms` and so need their own counting.

⚠ Access is decided by the CHARM fields (`open_to_all`, `open_to_tiers`,
`restricted_to`, `immaculate`, `ma_tier`), never by the style catalogue —
`tests/test_martial_arts_styles.py` bars `engine/` from reading
`ruleset.martial_arts_styles` at all, and `Charm.ma_tier` is projected onto the
Charm by the loader precisely so this module never has to.

⚠ `ma_tier` and `open_to_tiers` are DIFFERENT FACTS and conflating them is the bug
the 2026-08-14 access work removed: `open_to_tiers` says who may learn the Charm,
`ma_tier` says whether it is a Sidereal Martial Arts form for the p.101 chargen cap.
Violet Bier of Sorrows is Celestial and is NOT a Sidereal MA form.

Two back-edges to other domains are imported INSIDE their functions rather than at
module scope, because those domains import this one: the Illuminated Calling
(`calling_charm_ids`) and the Alchemical array installation cost
(`_installation_motes`). See the call sites.
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


# The repeatable Ox-Body-equivalent Charm is per-splat: each ExaltDefinition names
# its own (Solar's is solar.endurance.ox-body-technique). It is bought once per dot
# of its cap trait (Endurance; Stamina for Lunar), each purchase choosing a
# health-level package;
# stored on Character.ox_body, not in Character.charms (so the count is representable).


def ox_body_charm_id(ruleset: RuleSet, character: Character) -> str:
    """The id of this character's splat's repeatable Ox-Body-equivalent Charm (from
    its ExaltDefinition), or the heritage's parent-keyed one for a Half-Caste (a
    Half-Caste learns their parent's Charms and uses the parent's Ox-Body, p.47),
    or the heritage's own for God/Demon-Blooded (the SPIRIT Ox-Body — PG p.83 lists
    it as "(Spirit, Arcanos)" and the human ruled 2026-08-07 that the Arcanos
    version is Ghost-Blooded-only), or '' if neither defines one."""
    caste = ruleset.castes.get(character.caste)
    if caste is not None and caste.heritage_traits is not None:
        parent_ox = caste.heritage_traits.ox_body_charm_ids.get(character.origin)
        if parent_ox:
            return parent_ox
        if caste.heritage_traits.ox_body_charm_id:
            return caste.heritage_traits.ox_body_charm_id
    return ruleset.exalt_for(character.exalt_type).ox_body_charm_id


def ox_body_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """The Ox-Body-equivalent Charm object for this character's splat, or None when
    the splat names none or the id is absent from the RuleSet."""
    return ruleset.charms.get(ox_body_charm_id(ruleset, character))


def heritage_gift_spec(ruleset: RuleSet, character: Character):
    """The heritage's parent-keyed Gift-granting Charm (id, purchase-cap) for the
    character's `origin` — the Half-Caste's parent Exalt type. Only the Lunar parent
    sets these: a Lunar Half-Caste may gain up to TWO alternate forms via Deadly
    Beastman Transformation (p.47), so the cap is 2 regardless of Essence. None for
    every heritage without a gift economy, which falls back to the splat's."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return None
    traits = caste.heritage_traits
    if character.origin in traits.gift_charm_ids:
        return (traits.gift_charm_ids[character.origin],
                traits.gift_caps.get(character.origin))
    return None


def gift_charm_id(ruleset: RuleSet, character: Character) -> str:
    """The id of this character's splat's repeatable Gift-granting Charm (Deadly
    Beastman Transformation for Lunar, p.124-127), or the heritage's parent-keyed one
    for a Lunar Half-Caste (p.47), or '' if neither defines one."""
    spec = heritage_gift_spec(ruleset, character)
    if spec is not None:
        return spec[0]
    return ruleset.exalt_for(character.exalt_type).gift_charm_id


def gift_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """The Gift-granting Charm object for this character's splat, or None when the
    splat names none or the id is absent from the RuleSet."""
    return ruleset.charms.get(gift_charm_id(ruleset, character))


class CharmPick(BaseModel):
    """One Charm a character holds, wherever it is stored.

    A repeatable Charm (Ox-Body Technique; Deadly Beastman Transformation) lives on
    its OWN `Character` list rather than in `character.charms`, because N copies must
    be representable. Granted Charms (a Cult of the Illuminated training camp, p.90)
    are a third such list. Every consumer that walked `character.charms` therefore had
    to special-case each list by hand — and four separately failed to when Gifts
    landed. This type is the single enumeration they consume instead, so adding a
    fourth list is one change here rather than a scavenger hunt.

    `counts_toward_pool` is False only for granted Charms: they cost no chargen pick
    and no bonus points. `label` is display-ready and already folds in a repeatable
    purchase's chosen variant(s). `caste_favored` is the Caste/Favoured decision for
    THIS pick, resolved once here — the discount axis both the BP pricing and the
    chargen Caste/Favoured minimum key off, whichever list the pick came from.

    NOTE: this covers what a character HOLDS, plus the one trait of it (Caste/Favoured)
    that does not depend on the accounting being done. The per-pick BP arithmetic is
    `charm_pick_bp_costs`, which consumes this list.
    """
    charm_id: str
    name: str                  # the Charm's own name, or the raw id if unresolved
    label: str                 # display name; includes variant labels for repeatables
    category: str = ""
    source: str = "charms"     # charms | ox_body | beastman_gifts | granted | origin
    counts_toward_pool: bool = True
    caste_favored: bool = False


def charm_picks(ruleset: RuleSet, character: Character) -> list[CharmPick]:
    """Every Charm the character holds RIGHT NOW, in sheet order: plain picks, then one
    entry per repeatable purchase, then Charms granted by a training camp.

    This is the enumeration the UI must use instead of reading `character.charms`,
    `character.ox_body`, `character.beastman_gifts` and `character.granted_charms`
    itself. Unresolvable ids are still yielded (with `name` set to the raw id) so a
    stale save shows the problem rather than silently losing a row.

    Chargen accounting wants `chargen_charm_picks` instead — post-lock, the current
    lists include Charms bought with XP.
    """
    return _charm_picks_from(
        ruleset, character,
        character.charms, character.ox_body, character.beastman_gifts,
        character.granted_charms,
    )


def chargen_charm_picks(ruleset: RuleSet, character: Character) -> list[CharmPick]:
    """`charm_picks` over the traits chargen accounting reads: the frozen snapshot once
    locked, else the current lists. Granted Charms are read live either way — they are
    a property of the training camp, cost nothing, and the snapshot does not hold them.
    """
    src = _chargen_source(character)
    return _charm_picks_from(
        ruleset, character,
        src[6], src[9], src[12], character.granted_charms,
    )


def _charm_picks_from(ruleset: RuleSet, character: Character,
                      charms, ox_body, beastman_gifts, granted) -> list[CharmPick]:
    """Build the pick list from explicit trait lists, so the same enumeration serves
    both the live character and the chargen snapshot."""
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

    for cid in granted:
        charm = ruleset.charms.get(cid)
        picks.append(_pick(cid, charm, f"{charm.name if charm else cid} (granted)",
                           source="granted", counts=False))

    # Charms the ORIGIN hands out unconditionally (Lookshy, p.68). Unlike a training
    # camp's package these are not stored on the Character at all — they follow from
    # the budget row, so they are enumerated here rather than saved, and a character
    # who changes origin simply stops having them. A Charm the character also bought
    # is not listed twice; the bought copy wins, since it is the one that cost a pick.
    held = {p.charm_id for p in picks}
    for cid in origin_granted_charm_ids(ruleset, character):
        if cid in held:
            continue
        charm = ruleset.charms.get(cid)
        picks.append(_pick(cid, charm, f"{charm.name if charm else cid} (origin)",
                           source="origin", counts=False))

    return picks


def origin_granted_charm_ids(ruleset: RuleSet, character: Character) -> list[str]:
    """The Charm ids this character's origin grants free at creation (Lookshy, p.68).
    Empty for every origin that grants none, which is all but one today."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return list(b.granted_charms)


def charm_pick_count(ruleset: RuleSet, character: Character) -> int:
    """How many Charm picks the character has spent from the chargen pool — i.e.
    everything `charm_picks` yields except the free granted ones."""
    return sum(1 for p in charm_picks(ruleset, character) if p.counts_toward_pool)


def charm_pick_bp_costs(ruleset: RuleSet, character: Character,
                        picks: list[CharmPick]) -> list[int]:
    """The bonus-point price of each pool-counting pick in `picks`, in pick order.

    The pricing half of the canonical enumeration: one rate ladder, applied to every
    pick regardless of which `Character` list it came from. Most specific claim about
    the Charm wins —

      Calling         (Cult of the Illuminated, p.90)   4 BP, 3 if Caste/Favoured
      Immaculate      (DB, p.151)                       10 / 7
      Martial Arts    (Sidereal, p.101)                 8 / 6, None → the ordinary rate
      ordinary                                          charm / charm_favored_caste

    Unresolvable ids are priced at nothing and dropped, matching every other consumer.
    Spells share the Charm pool but are not Charms and are priced by their caller.
    """
    bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin, character.upbringing)
    # Deferred to call time, not imported at module scope: `illuminated` imports
    # this module (a Calling grants Charms), so a top-level import is a cycle.
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
            # Other splats leave both Martial Arts fields None and fall back to the
            # ordinary Charm rate, so their MA Charms are byte-identical.
            rate = (bp_costs.martial_arts_charm_favored_caste if cf
                    else bp_costs.martial_arts_charm)
            if rate is None:
                rate = bp_costs.charm_favored_caste if cf else bp_costs.charm
            costs.append(rate)
        elif charm.grants_circle is not None and bp_costs.magic_charm:
            # The sorcery/necromancy INITIATION Charms (God-Blooded, p.50: "Charm/Spell*
            # | 7 (10 for Sorcery or Necro-mancy Charms)"). Flat — the table prints no
            # favoured variant. `magic_charm` 0 (every other splat) falls through to the
            # ordinary rate below.
            costs.append(bp_costs.magic_charm)
        elif bp_costs.charm_cross_pattern and mountain_folk_cross_pattern(
                ruleset, character, charm):
            # A Mountain Folk Charm of another caste's Pattern costs 7 BP (CH6 p.233:
            # "Charms | 5 (7 if part of another caste's Pattern)").
            costs.append(bp_costs.charm_cross_pattern)
        else:
            costs.append(bp_costs.charm_favored_caste if cf else bp_costs.charm)
        # Brigid's Heir doubles the BONUS-point cost as well as the XP one, outside the
        # sorcery line. Applied per pick so the exemption is per Charm.
        costs[-1] = merits.adjust_charm_cost(ruleset, character, charm, costs[-1])
    return costs


def _repeatable_purchase_cap(charm: Charm, character: Character) -> int:
    """Resolve a repeatable Charm's `repeatable_cap_ability` against the character:
    an Ability, an Attribute, or the special value 'essence' (Deadly Beastman
    Transformation, p.124 — "no more times than he has points of Essence"; Essence
    isn't an Ability or Attribute, so it can't come through the normal lookups).
    Or a Virtue, via `repeatable_cap_virtue` (the God-Blooded Ox-Body Technique, PG
    p.83 — "no more times than their Conviction rating"; the same retarget `min_virtue`
    performs for Charm minimums). The Mountain Folk add `repeatable_cap_highest_virtue`
    (their Ox-Body "cannot develop ... more times than their highest Virtue", CH6
    p.245 — the MAX of the four, which no single Virtue name can hold). A FLAT
    `repeatable_cap_max` caps the trait-derived number (the Mountain Folk Satiation /
    Stone-Still "three times", CH6 pp.245-246 — an Essence-5 Jadeborn still buys at
    most three, the third gated on Essence 3). 0 if the Charm isn't repeatable or the
    trait name resolves to none of these."""
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
    """Resolve a Charm `category` to the Ability that gates its minimum. A plain
    ability is itself (e.g. 'melee'); a Martial Arts style uses the convention
    'martial_arts:<style>' (e.g. 'martial_arts:tiger') and resolves to Martial
    Arts. Anything else (e.g. 'sorcery') has no single gating ability -> None."""
    base = category.split(":", 1)[0]      # 'martial_arts:tiger' -> 'martial_arts'
    try:
        return AbilityName(base)
    except ValueError:
        return None


def _mountain_folk_pattern(charm: Charm) -> str | None:
    """The Mountain Folk Pattern a Charm belongs to ('foundation' | 'worker' |
    'warrior' | 'artisan' | 'enlightened'), or None for any non-Mountain-Folk Charm.
    Categories use the `martial_arts:<style>` namespace convention:
    'mountain_folk:<pattern>'. The Pattern is the splat's gating axis — no ability
    prerequisite gates a Jadeborn Charm, only Minimum Essence and Pattern membership
    (CH6 p.244)."""
    if not charm.category.startswith("mountain_folk:"):
        return None
    return charm.category.split(":", 1)[1]


def _mountain_folk_unenlightened_bar(character: Character, charm: Charm) -> bool:
    """True when an Unenlightened Jadeborn may never hold `charm`: "Unenlightened
    characters can only learn the Charms of their own Caste Pattern or the Foundation
    Pattern" (CH6 p.244) is a LIFETIME access rule, not a chargen one — it is read
    here, beside the ghost Spirit-Walking bar in charm_matches_splat and in
    meets_charm_requirements, so both the chargen picker and the XP buy path enforce
    it. (A non-Mountain-Folk Charm is not this bar's business — foreign_charms_barred
    closes those.)"""
    if character.exalt_type != "Mountain-Folk" or character.origin != "unenlightened":
        return False
    pat = _mountain_folk_pattern(charm)
    if pat is None:
        return False
    return pat not in ("foundation", character.caste)


def mountain_folk_cross_pattern(ruleset: RuleSet, character: Character,
                                charm: Charm) -> bool:
    """Whether `charm` is a Mountain Folk Charm from ANOTHER caste's Pattern for
    THIS character — the rule that prices a cross-Pattern Charm at 12 XP / 7 BP
    (CH6 pp.233-237). A Charm of the character's own Caste Pattern, the Foundation
    Pattern or the Enlightened Pattern is NOT 'another caste'. False for every
    non-Mountain-Folk character or Charm, and for every non-caste Pattern."""
    if ruleset.exalt_for(character.exalt_type).id != "Mountain-Folk":
        return False
    pat = _mountain_folk_pattern(charm)
    return pat in ("worker", "warrior", "artisan") and pat != character.caste


def _min_trait_rating(character: Character, charm: Charm) -> tuple[str, int] | None:
    """The (trait name, character's rating) `charm.min_ability` is checked
    against — a Virtue for the ghosts' Virtue-keyed Arcanoi (`min_virtue` set,
    E:Ab p.234), an Attribute for Lunar's Attribute-keyed Charms (`min_attribute`
    set, p.122), otherwise the Ability `category` resolves to. None if the Charm
    gates on none of them (e.g. a `category` like 'sorcery' with no key).

    The named keys take priority over the category, and for the same reason in both
    cases: some categories (e.g. 'melee') are ALSO valid AbilityName values, and a
    Lunar Melee Charm must gate on the Dexterity/Strength/etc. `min_attribute` names,
    never on the character's Melee Ability rating — the two collide by name, not by
    meaning. An Arcanos is keyed the same way against its path's category.

    A Charm sets at most one of the three; the order here is the tiebreak if data ever
    sets two, and it is the order the model documents."""
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
    """Every Ability/Attribute minimum on `charm` the character FAILS, as
    (trait label, required, held).

    THE single place that answers "does this character meet this Charm's trait
    minimums". Covers both the primary `min_ability` (resolved through `category`, or
    through `min_attribute` for the Attribute-keyed splats) and any
    `extra_min_abilities` — the rare Charm the page gates on more than one Ability,
    e.g. Ascendant Battle Visage's "Minimum Brawl 5 / Minimum Endurance 5" (Cult of
    the Illuminated, p.102).

    Every caller that used to compare `_min_trait_rating(...)[1] < charm.min_ability`
    by hand goes through here instead, so adding the second gate could not miss a
    call site — and a third gating axis has exactly one function to change.

    Empty list means every minimum is met."""
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
    """Every Ability/Attribute minimum a Charm imposes, as (trait label, rating), for
    display. The primary gate first, then the extras in authored order. Presenters use
    this instead of reading `min_ability` alone, so a multi-gate Charm cannot show only
    half its requirements on the sheet or in the picker."""
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
    """Which of `charm`'s breadth prerequisites ("any three Lore Charms") are unmet,
    as (requirement, how many the character actually holds).

    The Charm never counts toward its own requirement — otherwise buying it would
    part-satisfy the thing gating it. Counting is by `category`, which is exactly how
    a Charm's Ability is identified everywhere else, so a Craft Charm printed in the
    Air book still counts toward "any three Craft Charms".

    One function for both the retrospective check (`check_charm_prerequisites`) and the
    forward-looking one (`meets_charm_requirements`), so the picker's "selectable" and
    the sheet's "illegal" can never disagree.
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
    """"any 3 Occult Charms" — the display form of a breadth prerequisite."""
    noun = req.label or req.category.replace("_", " ").title()
    return f"any {req.count} {noun} Charm{'s' if req.count != 1 else ''}"


def is_immaculate_charm(charm: Charm) -> bool:
    """True for an Immaculate Order Charm — a Fivefold Dragon Method martial-arts
    Charm (Dragon-Blooded splatbook, ch.6). These are what a DB may take the
    *Immaculate* chargen path with (5 from one elemental tree) in place of the
    standard 7 Dragon-Blooded Charms (p.151). Marked by the data flag Charm.immaculate."""
    return charm.immaculate


def _immaculate_path(ruleset: RuleSet, charm_ids, exalt_type: str) -> bool:
    """Whether a chargen Charm selection puts the character on the Immaculate
    martial-arts path — true when a Dragon-Blooded chooses ANY Immaculate Order
    Charm. On this path the Charm rules change (single elemental tree, 5-Charm
    free pool, Immaculate BP row, no Caste/Favoured minimum). The Immaculate
    *package* is Dragon-Blooded-only: a non-DB learner (e.g. a Solar taking a
    Terrestrial style, which is `open_to_all`) is priced/counted as ordinary
    Martial Arts and never trips this path, so it gates on `exalt_type`."""
    return exalt_type == "Dragon-Blooded" and any(
        (c := ruleset.charms.get(cid)) is not None and c.immaculate
        for cid in charm_ids)


def immaculate_martial_artist(ruleset: RuleSet, character: Character) -> bool:
    """Public form of `_immaculate_path` over the character's chargen Charm source
    (current pre-lock, or the frozen snapshot). Lets the UI show/gate the Immaculate
    path without re-deriving the snapshot selection."""
    charms = _chargen_source(character)[6]     # (…, charms, …) — see _chargen_source
    return _immaculate_path(ruleset, charms, character.exalt_type)


def check_charm_prerequisites(ruleset: RuleSet, character: Character) -> list[Issue]:
    """For each *known* Charm, verify min essence, min ability, and the AND-of-OR
    Charm prerequisite graph against the Charms the character knows. Unknown ids
    are skipped here (reported by check_references)."""
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
    # A generic repeatable Charm (Mountain Folk Essence Satiation Method, Stone-Still
    # Lungs — CH6 pp.245-246) appears once per purchase; cap the copies at the
    # trait-derived purchase cap, on both sides of the lock.
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


# Dragon-Blooded martial-arts "Enlightenment" gate (DB p241-242). A Terrestrial
# must master a PAIR of enlightenment Charms — one opening her perceptions, one
# letting her act on what she perceives — before she may learn the Charms of any
# Dragon Path. Celestial Exalted and Abyssals need no such initiation (the p241 box:
# Exalted of any type can learn the Dragon Paths given a tutor), so the gate is
# Dragon-Blooded-only; and Five-Dragon Style — a mundane DB style, not a Dragon Path
# — is exempt.
#
# There are THREE such pairs, and any ONE of them opens the gate. The Immaculate pair
# is only the best known: PG p.236 says so outright — "The Immaculate Charms Spirit
# Sight and Spirit Walking are just one set of such Charms. There are others" — and
# then prints two more. Requiring the Immaculate pair specifically would make the
# other four Charms buyable but inert, which is this codebase's oldest bug shape.
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
    """A martial-arts style the Dragon-Blooded enlightenment gate applies to.

    The gate is about **Celestial** martial arts, not martial arts in general —
    PG p.236 describes the initiation as what lets "the Terrestrial to, with
    difficulty, grasp the principles and practice of the Celestial martial arts",
    and the five Immaculate Dragon Paths are explicitly Celestial styles (human,
    rules authority, 2026-08-11). So the test is the style's TIER.

    A Dragon-Blooded therefore reaches every TERRESTRIAL style uninitiated — Five
    Dragon, Falling Blossom, Crimson Pentacle Blade — and Jade Mountain, which is a
    Dragon-Blooded style carrying no tier at all.

    Previously this exempted two styles BY NAME and gated everything else, which hid
    every Terrestrial style from an uninitiated Dragon-Blooded. Falling Blossom had
    been invisible to them since it was authored; adding Crimson Pentacle Blade is
    what made the bug visible.
    """
    if not category.startswith("martial_arts:"):
        return False
    for charm in ruleset.charms.values():
        if charm.category == category:
            return "Celestial" in charm.open_to_tiers
    return False


def db_enlightenment_met(character: Character) -> bool:
    """Whether the Dragon-Blooded Dragon-Path gate is OPEN for this character: always
    True for non-Dragon-Blooded (they need no initiation); for a Dragon-Blooded, True
    once she knows BOTH Charms of ANY ONE enlightenment pair — the Immaculate pair,
    the Iris-Bulb pair or the Tiger-and-Bear pair (DB p.241-242, PG pp.236-237)."""
    if character.exalt_type != "Dragon-Blooded":
        return True
    known = set(character.charms)
    return any(all(cid in known for cid in pair)
               for pair in DB_MA_ENLIGHTENMENT_PAIRS)


def category_available(ruleset: RuleSet, character: Character, category: str) -> bool:
    """Whether a Charm `category` is open to the character right now — the picker's
    style-dropdown filter. Currently the only gate is the Dragon-Blooded Dragon-Path
    rule (p241): a DB reaches the elemental Dragon styles only after learning both
    enlightenment Charms. Every other category is always available."""
    return not (_is_dragon_path_style(ruleset, category)
                and not db_enlightenment_met(character))


def meets_charm_requirements(ruleset: RuleSet, character: Character, charm) -> bool:
    """Whether the character could legally learn `charm` *right now*: min essence,
    min ability (when the category resolves to an ability), every AND-of-OR
    prerequisite group satisfied by an already-known Charm, and — for a Dragon-
    Blooded — the Dragon-Path enlightenment gate (p241). The forward-looking
    counterpart to check_charm_prerequisites; used by the charm-tree picker to
    decide which Charms are currently selectable."""
    if _is_dragon_path_style(ruleset, charm.category) and not db_enlightenment_met(character):
        return False
    if _mountain_folk_unenlightened_bar(character, charm):
        # An Unenlightened Jadeborn may only learn their own Caste Pattern or the
        # Foundation Pattern (CH6 p.244) — the forward-looking counterpart of the
        # charm_matches_splat bar, so the picker does not offer it either.
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
    """Names of currently-owned Charms that would lose a prerequisite if `charm_id`
    were dropped — i.e. they list it in an AND-of-OR group with no other owned
    alternative. Empty means the Charm is safe to remove. Used by the picker to
    keep the owned set internally consistent (remove leaves first)."""
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
    """Human name of the trait limiting a repeatable Charm's purchases, for use in
    messages: "Endurance", "Stamina", "Essence". "" if the Charm is absent or not
    repeatable. The trait is per-splat DATA (`repeatable_cap_ability`) — Lunar
    Ox-Body counts Stamina where every other splat counts Endurance (p.132) — so no
    message may hardcode it. Pairs with `_repeatable_purchase_cap`, which resolves
    the same field to a number."""
    name = charm.repeatable_cap_ability if charm else ""
    return name.replace("_", " ").title() if name else ""


def ox_body_cap(ruleset: RuleSet, character: Character) -> int:
    """Maximum number of Ox-Body Technique purchases: once per dot of the Charm's
    `repeatable_cap_ability` (Endurance for Solar/DB/Abyssal; Stamina — an
    Attribute, not an Ability — for Lunar, p.132). 0 if the Charm or its cap
    trait is absent. Used by both the engine and the picker to gate purchases."""
    charm = ox_body_charm(ruleset, character)
    if charm is None:
        return 0
    return _repeatable_purchase_cap(charm, character)


def check_ox_body(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of the character's Ox-Body purchases: at most one per dot of the
    splat's cap trait (core p.170), every chosen package a real variant, and the Charm's
    min essence met. The per-purchase bonus-point/XP cost is accounted elsewhere
    (validate_chargen / costs). Empty when no purchases."""
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
    """Max purchases of the splat's Gift-granting Charm: Character.essence_rating
    for Deadly Beastman Transformation ("no more times than he has points of
    Essence", p.124). 0 if the splat has no such Charm. A heritage that sets its own
    cap (the Lunar Half-Caste's two forms, p.47) wins over the Charm's own trait cap."""
    spec = heritage_gift_spec(ruleset, character)
    if spec is not None and spec[1] is not None:
        return spec[1]
    charm = gift_charm(ruleset, character)
    if charm is None:
        return 0
    return _repeatable_purchase_cap(charm, character)


def gifts_per_purchase(charm: Charm, purchase_index: int) -> int:
    """How many Gifts the purchase at `purchase_index` (0-based) grants:
    `variant_picks_first_purchase` for index 0, `variant_picks_per_purchase` for
    every purchase after (p.124: Deadly Beastman Transformation's first purchase
    grants 2 Gifts, each purchase after grants 1)."""
    return (charm.variant_picks_first_purchase if purchase_index == 0
            else charm.variant_picks_per_purchase)


def known_gift_keys(character: Character) -> list[str]:
    """Every Gift key the character has purchased, across all purchases of the
    Gift-granting Charm, flattened (a Gift bought twice appears twice)."""
    return [g for p in character.beastman_gifts for g in p.gifts]


def check_gift_prerequisites(ruleset: RuleSet, character: Character) -> list[Issue]:
    """AND-of-OR prerequisite legality for known Gifts — the same shape as
    check_charm_prerequisites, but CharmVariant.prerequisites references OTHER
    variant keys of the SAME Charm (p.126-127's own Gift-to-Gift chain, e.g.
    Glue-Foot Climbing needs Spider-Foot Climbing needs Bestial Reflexes-or-
    Lightning Speed), not Charm ids."""
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
    """Legality of the character's Gift-granting Charm purchases: purchases <=
    Essence cap (p.124), each purchase's Gift count matches what that purchase
    grants, every chosen Gift a real variant, no Gift taken past its own
    max_purchases, and Gift prerequisites satisfied. The per-purchase BP/XP cost
    is accounted elsewhere (validate_chargen / costs), same as Ox-Body. Empty
    when no purchases."""
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
    """Whether an Attribute-keyed Charm (Lunar) counts as Caste-favored: its
    `min_attribute`'s category matches the caste's favored category (p.122).
    False for a Charm with no `min_attribute` or for a non-Lunar/Casteless caste."""
    if not charm.min_attribute or caste_attr_category is None:
        return False
    try:
        attr = AttributeName(charm.min_attribute)
    except ValueError:
        return False
    return _attribute_category(attr) == caste_attr_category


def _charm_is_caste_favored(charm: Charm, cf_set: set, caste_attr_category: str | None,
                             caste_fav_attrs: set) -> bool:
    """Whether `charm` counts as Caste/Favoured for its owner — the single decision
    the BP pricing, the chargen minimum, and the slot rule all share. Ability-keyed:
    its category-Ability is in the Caste∪Favoured Ability set. Attribute-keyed: in
    caste_favored mode (Alchemical, `caste_fav_attrs` non-empty) its `min_attribute`
    is literally one of the Caste/Favored Attributes; otherwise (Lunar) its
    Attribute's CATEGORY matches the caste's favored category."""
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
    """Whether `charm` may occupy a Dedicated Charm Slot (p.88): it must be keyed to a
    Caste or Favored Attribute. General Slots hold any Charm, so this is only the
    Dedicated restriction. Bundles the same decision the chargen slot check makes so
    the advancement layer and the UI share one answer."""
    cf_set = caste_favored_abilities(ruleset, character)
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)
    caste_fav_attrs = _caste_favored_attr_names(ruleset, character)
    return _charm_is_caste_favored(charm, cf_set, caste_attr_category, caste_fav_attrs)


def uses_charm_slots(ruleset: RuleSet, character: Character) -> bool:
    """Whether this splat uses the Alchemical Charm Slot system (p.88-89) — has any
    free General/Dedicated Slots in its budget — rather than the per-pick Charm
    economy every other splat uses."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return (b.charm_slots_general + b.charm_slots_dedicated) > 0


def splat_uses_charm_slots(ruleset: RuleSet, splat: str) -> bool:
    """Whether the named splat is a Charm-Slot splat (Alchemical). Splat-level (no
    character), so it can classify OTHER splats' Charms — used to spot an Alchemical
    Charm being learned by a non-Alchemical via the crossover rule."""
    b = ruleset.budgets_for(splat)
    return (b.charm_slots_general + b.charm_slots_dedicated) > 0


def crossover_alchemical_charm(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Whether `character` is a non-Alchemical learning an Alchemical (Slot-splat)
    Charm through the Eclipse/Moonshadow generalist rule — the p.90 crossover, which
    grants a General Charm Slot along with the Charm."""
    return (not uses_charm_slots(ruleset, character)
            and foreign_charms_open(ruleset, character)
            and is_foreign_charm(ruleset, character, charm)
            and splat_uses_charm_slots(ruleset, splat_of(charm)))


def crossover_panoply_xp(ruleset: RuleSet, character: Character) -> Optional[int]:
    """The flat XP an Eclipse-style caste pays to add an Alchemical Charm to its Panoply
    instead of buying a Slot (p.90, 8), or None if the caste has no such crossover
    rate. Requires the generalist rule to be open to this character."""
    if not foreign_charms_open(ruleset, character):
        return None
    caste = ruleset.castes.get(character.caste)
    return caste.foreign_panoply_charm_xp if caste is not None else None


def charm_slot_counts(ruleset: RuleSet, character: Character) -> tuple[int, int, int, int]:
    """(general, dedicated, base_general, base_dedicated) Charm Slot counts. The
    effective counts fall back to the budget's free base when the character hasn't
    initialised them (None); the base pair is what BP accounting charges *beyond*."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    bg, bd = b.charm_slots_general, b.charm_slots_dedicated
    g = character.general_charm_slots if character.general_charm_slots is not None else bg
    d = character.dedicated_charm_slots if character.dedicated_charm_slots is not None else bd
    return g, d, bg, bd


def charm_slot_usage(ruleset: RuleSet, character: Character) -> tuple[int, int, int]:
    """(installed, noncf, install_motes) for a Charm-Slot splat: how many Slots the
    installed Charms occupy, how many of those are non-Caste/Favored (and so need a
    General Slot), and the committed installation motes. Reads the chargen source
    (the frozen snapshot once locked), so it matches the chargen Slot check exactly,
    and is the single computation both that check and the UI readout consume.

    PLM Martial Arts Charms occupy no Slot; each Ox-Body purchase occupies one (it is
    stored on `ox_body`, not `charms`, so it is added explicitly)."""
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
    # Deferred for the same reason as `calling_charm_ids` above — `alchemical`
    # imports this module.
    from . import alchemical
    install_motes = alchemical._installation_motes(ruleset, charms, arrays)
    if ob_charm is not None:
        install_motes += ob_charm.installation_cost * len(ox_body)
    return installed, noncf, install_motes


def splat_of(charm: Charm) -> str:
    """The Exalt type that can learn `charm` (charm.exalt_type). A tiny accessor so
    the UI/engine don't reach into the field directly and can grow smarter later
    (e.g. cross-splat Martial Arts / sorcery) without a churn of call sites."""
    return charm.exalt_type


def charms_available(ruleset: RuleSet, character: Character) -> bool:
    """Whether this character's splat may hold Charms at all. False only for mortals
    (core p.103, "Mortals cannot purchase Charms"). See
    `ExaltDefinition.charms_available` for why this is a flag and not `charm_count: 0`,
    and for how Merits & Flaws are expected to reopen it later."""
    return ruleset.exalt_for(character.exalt_type).charms_available


def charm_restriction_met(character: Character, charm: Charm) -> bool:
    """Whether the character satisfies a style's own named access list.

    `Charm.restricted_to` holds "<Splat>" / "<Splat>:<caste>" entries and the
    character must match ONE. It NARROWS an access the splat/tier test already
    granted — a Celestial style that also names its splats is open to Celestials who
    are on the list and nobody else. Empty (the default) means no extra restriction,
    so every existing Charm is unaffected."""
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
    """Whether the character is under a style's Virtue ceiling (`Charm.max_virtue`).

    The one requirement here that is failed by having MORE of a trait, so it cannot
    be folded into the min_* shortfall machinery."""
    if not charm.max_virtue:
        return True
    return all(v <= charm.max_virtue for v in character.virtues.values())


def charm_matches_splat(character: Character, charm: Charm,
                        ruleset: Optional[RuleSet] = None) -> bool:
    """Whether `charm` is available to the character — the picker/graph filter and
    the `charm-wrong-splat` check. A Charm matches when

      * it belongs to the character's own Exalt type, OR
      * it is flagged `open_to_all` (cross-splat Charms such as the Terrestrial
        Immaculate Dragon martial-arts styles, which any splat may learn), OR
      * the character's Exalt *tier* is listed in `charm.open_to_tiers` — the
        Celestial-only styles (Hungry Ghost, Five-Dragon).

    The tier test needs the splat table, so it only applies when `ruleset` is
    given; without one the call degrades to the splat/`open_to_all` answer.

    A splat that may not hold Charms at all (mortals, core p.103) matches NOTHING,
    and that test comes first — `open_to_all` would otherwise hand a mortal the eight
    cross-splat Charms whose minimums an Essence-1 character can actually meet. A
    Merit can reopen part of that (Essence Mastery grants Terrestrial Martial Arts),
    which is asked of engine.merits and never decided here."""
    # Virtual rows are never learnable, whatever else would reach them. They are the
    # Dragon-King Path powers projected into the charm catalogue so Combos and the
    # sheet can name them (rules_db._virtual_path_charms); the real Path state is the
    # rated track, and no Charm path buys a Path dot. First, above every grant below,
    # so a later branch can never talk past it.
    if charm.virtual:
        return False
    # A style that names who may learn it (PG p.249). Narrowing only, and above the
    # grants below so no later branch can talk past it.
    if not charm_restriction_met(character, charm):
        return False
    # A Charm this splat may never hold, whatever else permits it (ghosts and Spirit
    # Walking). First, and above every grant below — including the splat's own Charms —
    # because a bar a later branch can talk past is not a bar. The HERITAGE bar (the
    # Half-Caste's perfect/persistent defense ban) sits beside the splat-level one, so
    # the two cannot disagree about ordering.
    if ruleset is not None and charm.id in ruleset.exalt_for(character.exalt_type).barred_charm_ids:
        return False
    # An Unenlightened Jadeborn may only learn their own Caste Pattern or the
    # Foundation Pattern (CH6 p.244) — a LIFETIME access bar, placed beside the ghost
    # Spirit-Walking bar so neither the chargen picker nor the XP buy path can talk
    # past it.
    if _mountain_folk_unenlightened_bar(character, charm):
        return False
    if ruleset is not None and charm.id in heritage_barred_charm_ids(ruleset, character):
        return False
    # …and the heritage's magic TRACK, which bars the other discipline's initiation
    # Charms (p.48). Same position, for the same reason.
    if ruleset is not None and heritage_bars_initiation(ruleset, character, charm):
        return False
    if ruleset is not None and not charms_available(ruleset, character):
        eff = merits.merits_and_flaws_calc(ruleset, character)
        if charm.id in eff.barred_charm_ids:
            return False
        if eff.bar_immaculate_charms and is_immaculate_charm(charm):
            return False
        # A Merit opens a whole CATEGORY; `martial_arts:<style>` categories match on
        # their prefix so one grant covers every Terrestrial style.
        root = charm.category.split(":", 1)[0]
        if root not in eff.open_charm_categories:
            return False
        # Within an opened category the ordinary splat/tier rules still apply — the
        # Merit grants access to Terrestrial styles, not to every splat's Charms.
        return charm.open_to_all or "Terrestrial" in charm.open_to_tiers
    # A splat barred from other people's Charms (the dead, E:Ab p.126: "Ghosts may not
    # learn Exalted Charms"). Checked BEFORE `open_to_all`, which would otherwise hand
    # them the cross-splat Terrestrial styles — the same ordering trap the mortal bar
    # above documents. Their own Arcanoi are unaffected.
    if ruleset is not None and ruleset.exalt_for(character.exalt_type).foreign_charms_barred:
        # ...gated on the heritage allowing native Charms at all: a Fae-Blooded's
        # "do not use Charms" (p.47) closes the God-Blooded's own Arcanoi wholesale
        # (heritage_charms_available False) rather than deny-listing today's eight —
        # a list a ninth Charm, authored for a later heritage, would silently outrun.
        if (splat_of(charm) == character.exalt_type
                and heritage_charms_available(ruleset, character)):
            return True
        # …the heritage's borrowed catalogue (God-Blooded, PG p.47): a Ghost-Blooded
        # learns the Ghost Arcanoi "exactly as their parents". Still a NATIVE match —
        # this sits inside the foreign-bar, so it is not the p.127 generalist privilege
        # and is not restated separately in charm_learnable_by_splat's foreign branch.
        if splat_of(charm) in heritage_charm_access(ruleset, character):
            return True
        # …with one printed exception: the Terrestrial supernatural martial arts
        # (PG p.234). Same shape as the mortal Essence Mastery branch above, and for
        # the same reason — a `martial_arts:<style>` category matches on its prefix so
        # one rule covers every Terrestrial style.
        return (ruleset.exalt_for(character.exalt_type).terrestrial_martial_arts
                and is_terrestrial_martial_arts(charm))
    # An Alchemical is a CELESTIAL Exalt (human, 2026-08-11) but reaches NO martial
    # arts at all — Terrestrial or Celestial — without Perfected Lotus Matrix installed
    # (CH3 p.100: with it she learns them "in the same manner as any other Celestial
    # Exalted type"). The tier says what she could reach; PLM says whether she may.
    #
    # This sits ABOVE `open_to_all`, because the Terrestrial styles are open_to_all and
    # would otherwise be granted before any tier reasoning ran — the same ordering trap
    # the mortal and ghost bars above document. Her own Charms are unaffected: no
    # Alchemical Charm lives in a `martial_arts:` category, PLM included.
    if (character.exalt_type == "Alchemical" and is_martial_arts_charm(charm)
            and not has_perfected_lotus_matrix(character)):
        return False
    # A Lunar may NEVER learn Sidereal martial arts (PG p.235, in the LUNAR MARTIAL
    # ARTISTS section: "They may not learn Sidereal martial arts under any
    # circumstances"). "They" is the Lunar Exalted specifically — the sentence sits
    # inside that section — so this is a LUNAR bar and not a Celestial-tier one:
    # Solars and Abyssals reach the Sidereal styles by tier exactly as before.
    #
    # Above the grants below, because the three Sidereal styles carry
    # `open_to_tiers: ["Celestial"]` and a Lunar reaches Celestial, so the tier
    # branch would otherwise hand them over.
    if character.exalt_type == "Lunar" and charm.ma_tier == "Sidereal":
        return False
    if charm.open_to_all or splat_of(charm) == character.exalt_type:
        return True
    if ruleset is not None and charm.open_to_tiers:
        if tier_reaches(ruleset.exalt_for(character.exalt_type).tier,
                        charm.open_to_tiers):
            return True
    # A TERRESTRIAL who has been initiated reaches the CELESTIAL martial arts
    # (PG pp.235-236: "It is possible for the Terrestrial Exalted to practice
    # Celestial martial arts. Indeed, many Terrestrials do"). The initiation is the
    # enlightenment Charm pair — any one of the three, which `db_enlightenment_met`
    # already decides and `category_available` already uses as a GATE.
    #
    # ⚠ The gate was never a grant. A Dragon-Blood reached her own Dragon Paths by
    # SPLAT OWNERSHIP, so the gate only ever narrowed that; an initiated DB was still
    # refused Celestial Monkey, which has carried `open_to_tiers: ["Celestial"]` all
    # along. This branch is the missing half. It grants nothing to an UNINITIATED
    # Terrestrial, and nothing at all above Celestial — a Dragon-Blood never reaches
    # Solar-tier or Sidereal material, which decision 0015's "never reaches up" and
    # the Lunar-style bars above both preserve.
    # ⚠ Gated on the SPLAT, not on the tier. Four splats are Terrestrial-tier
    # (Dragon-Blooded, Dragon-Kings, God-Blooded, Mountain-Folk) and
    # `db_enlightenment_met` returns True for every non-Dragon-Blood — so a tier test
    # would hand the other three every Celestial style for free, having met no
    # initiation at all. PG p.235 also bars one of them outright: "Dragon Kings ...
    # can never master anything other than Terrestrial styles designed specifically
    # for Dragon Kings." The printed passage says "the Dragon-Blood must also have
    # her perceptions opened", and the initiation pairs are Dragon-Blooded Charms, so
    # Dragon-Blooded is the correct and faithful scope.
    if (charm.ma_tier == "Celestial"
            and character.exalt_type == "Dragon-Blooded"
            and db_enlightenment_met(character)):
        return True
    return False


PERFECTED_LOTUS_MATRIX_ID = "alchemical.close-combat.perfected-lotus-matrix"


# The Exalt power hierarchy, low to high (human, rules authority, 2026-08-11):
# Terrestrial = the Dragon-Blooded alone; Celestial = Lunars, Sidereals, Abyssals and
# Alchemicals; Solar = the Solar Exalted, above all. A splat reaches its own tier AND
# EVERY TIER BELOW IT — a Solar may learn Celestial and Terrestrial martial arts, a
# Celestial may learn Terrestrial, a Terrestrial reaches only Terrestrial. Nothing
# reaches UP: Lunars and Sidereals cannot touch Solar-tier material.
#
# Before 2026-08-11 the tier test was exact string equality, so "Celestial or below"
# was inexpressible and Solar had to be MISLABELLED `tier: "Celestial"` to reach
# Celestial martial arts at all — which in turn left Alchemicals matching nothing and
# needing a hardcoded Perfected Lotus Matrix special case.
TIER_ORDER = ("Terrestrial", "Celestial", "Solar")


def tier_rank(tier: str) -> int:
    """Position of `tier` in the Exalt hierarchy, or -1 for a tier outside it
    (Mortal, Ghost — those splats reach nothing by rank and are gated elsewhere)."""
    return TIER_ORDER.index(tier) if tier in TIER_ORDER else -1


def tier_reaches(character_tier: str, charm_tiers: list[str]) -> bool:
    """Whether a splat of `character_tier` may reach a Charm marked `charm_tiers`.

    True when the character's rank is at least the LOWEST tier the Charm names, so a
    Solar reaches a Celestial style and a Dragon-Blooded does not."""
    mine = tier_rank(character_tier)
    if mine < 0:
        return False
    ranks = [tier_rank(t) for t in charm_tiers if tier_rank(t) >= 0]
    return bool(ranks) and mine >= min(ranks)


def is_martial_arts_charm(charm: Charm) -> bool:
    """Whether `charm` is a Martial Arts style Charm (its category is a
    `martial_arts:*` tree), as opposed to an ordinary Ability/Attribute Charm."""
    return charm.category.startswith("martial_arts")


def has_perfected_lotus_matrix(character: Character) -> bool:
    """Whether the Alchemical has Perfected Lotus Matrix installed (CH3 p.100) — the
    Charm that lets her learn Terrestrial/Celestial Martial Arts Charms. Removing it
    revokes access to the MA Charms stored inside it."""
    return PERFECTED_LOTUS_MATRIX_ID in character.charms


def charm_occupies_slot(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Whether an installed Charm consumes a Charm Slot. Every Alchemical Charm does
    (user ruling: including each Ox-Body / Strain Resistant Chassis purchase) EXCEPT
    the Martial Arts Charms learned through Perfected Lotus Matrix, which are stored
    inside that Charm rather than in a Slot (CH3 p.100)."""
    return not (is_martial_arts_charm(charm) and splat_of(charm) != character.exalt_type)


def foreign_charms_caste(ruleset: RuleSet, character: Character):
    """The character's CasteDefinition when that caste may learn other splats'
    Charms (the Eclipse generalist rule, core p.127), else None. Data-driven via
    `CasteDefinition.foreign_charms` — no caste or splat is named in code."""
    caste = ruleset.castes.get(character.caste)
    return caste if caste is not None and caste.foreign_charms else None


def heritage_charm_access(ruleset: RuleSet, character: Character) -> frozenset[str]:
    """The exalt_types whose Charm catalogues the character's heritage may learn
    natively — the God-Blooded "learn the Charms of their magical parents, exactly
    as their parents" (PG p.47). A Ghost-Blooded's heritage borrows the Ghost Arcanoi
    catalogue; the Half-Caste heritage borrows its parent EXALT type, which rides the
    `origin` axis (the Origin dropdown, human 2026-08-02). Read off the caste's
    `heritage_traits`: the static `charm_access` list, or `character.origin` when
    `charm_access_parent` is set (empty when no parent chosen). Empty for every
    non-God-Blooded caste. One read site, so adding a heritage's catalogue is a data
    edit."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return frozenset()
    if caste.heritage_traits.charm_access_parent:
        return frozenset({character.origin}) if character.origin else frozenset()
    return frozenset(caste.heritage_traits.charm_access)


def heritage_charms_available(ruleset: RuleSet, character: Character) -> bool:
    """Whether this heritage may hold its OWN splat's native Charms
    (`GodbloodedHeritage.charms_available`). The one False heritage is the Fae-Blooded,
    "The children of the Fair Folk do not use Charms" (p.47) — the whole native
    catalogue is closed, not the eight Arcanoi individually, so a Charm authored for a
    later heritage (God/Demon-Blooded's spirit Charms) cannot silently become legal
    here. The gate sits at the native match in charm_matches_splat, the one site it can
    be walked past: the foreign `charm_access` catalogue and the p.234 Terrestrial arts
    are separate grants and survive it."""
    if ruleset is None:
        return True
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return True
    return caste.heritage_traits.charms_available


def heritage_barred_charm_ids(ruleset: RuleSet, character: Character) -> frozenset[str]:
    """Charm ids this heritage may never hold (`GodbloodedHeritage.barred_charm_ids`) —
    the Half-Caste's "may not master any Charms that provide a perfect defense or
    persistent scene-length defense" list plus the Sidereal Maiden-approval Charms
    (p.47). Empty for every non-God-Blooded caste. Checked FIRST in both charm gates,
    exactly like `ExaltDefinition.barred_charm_ids`, so a bar a later grant branch can
    talk past is not a bar."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return frozenset()
    return frozenset(caste.heritage_traits.barred_charm_ids)


def heritage_magic_track(ruleset: RuleSet, character: Character) -> str:
    """The ONE magic track this heritage may be initiated into ("sorcery" /
    "necromancy"), "" for no restriction, or "none" for a heritage that may initiate
    into NOTHING. PG p.48: "Terrestrial Circle Sorcery is available to all the
    remaining heritages save Ghost-Blooded and Abyssal Half-Caste. Conversely, only
    these heritages may learn Shadowlands Circle Necromancy." — and the Fae-Blooded,
    whose magic is glamour Merits rather than spells: "All God-Blooded with the
    Awakened Essence Merit APART FROM Fae-Blooded may also learn to cast spells."
    "none" is the third state the Phase C machinery needs; "" would mean no restriction,
    which is the OPPOSITE for a Fae-Blooded (that trap is why the sentinel exists).

    Read off the caste's `heritage_traits`: the parent-keyed map wins where the parent
    has an entry (the Half-Caste's track follows their PARENT, not their heritage),
    otherwise the scalar. Empty for every non-God-Blooded caste."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None:
        return ""
    traits = caste.heritage_traits
    return traits.magic_track_by_parent.get(character.origin) or traits.magic_track


def heritage_bars_initiation(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Whether the heritage's magic track bars this Charm — true only for an
    INITIATION Charm (one with `grants_circle`) whose circle belongs to the other
    track. A heritage with no track restriction bars nothing, and an ordinary Charm is
    never touched: this restricts which magic a heritage may unlock, not which Charms
    it may hold.

    Charm ACCESS alone does not express the rule. A Ghost-Blooded happens to land on
    necromancy because the Ghost catalogue holds no sorcery, but an Abyssal Half-Caste
    borrows a catalogue holding BOTH and would otherwise reach Terrestrial Sorcery,
    and a Solar Half-Caste's catalogue holds Shadowlands Circle Necromancy."""
    if charm.grants_circle is None:
        return False
    track = heritage_magic_track(ruleset, character)
    if track == "none":
        # The Fae-Blooded: no spell initiation at all, Awakened Essence or not (p.48).
        return True
    if not track:
        return False
    allowed = TRACK_CIRCLES.get(track, ())
    # God-Blooded are limited to the FIRST circle of their track (p.48: "Greater
    # circles of sorcery and necromancy lie beyond the purview of the God-Blooded").
    # This is the real bar — the Essence-3 cap was never enough, because the
    # splat-access gate does not consult min_essence, so a Celestial/Solar (or
    # Labyrinth/Void) initiation was OFFERED even though the buy path would refuse.
    return charm.grants_circle not in allowed[:1]


def foreign_charms_permitted(character: Character) -> bool:
    """The stored Storyteller permission alone, ignoring caste and lock state — what
    the chargen checkbox reflects. `foreign_charms_open` is the question the engine
    actually asks; this is just the flag, and lives here so no caller has to know it
    moved onto HouseRules."""
    return character.house_rules is not None and character.house_rules.st_foreign_charms


def foreign_charms_open(ruleset: RuleSet, character: Character) -> bool:
    """Whether the character may learn other splats' Charms *right now*. The caste
    must allow it (p.127), and — before the sheet is locked — the Storyteller must
    have permitted it: "Eclipse Caste characters may not start the game knowing the
    Charms of other such beings without Storyteller permission." After lock the rule
    asks only for a willing tutor, which is narrative, so the gate falls away."""
    if foreign_charms_caste(ruleset, character) is None:
        return False
    return character.chargen_locked or foreign_charms_permitted(character)


def is_foreign_charm(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Whether `charm` is another splat's Charm for this character — i.e. it is only
    reachable via the p.127 generalist rule, not by the ordinary splat/tier match.
    This is what the doubled XP price keys off, so the `open_to_tiers` styles a
    Celestial may learn natively (Hungry Ghost, Five-Dragon) are NOT foreign and
    must not double — hence the ruleset argument."""
    return not charm_matches_splat(character, charm, ruleset)


def is_terrestrial_martial_arts(charm: Charm) -> bool:
    """A Terrestrial-tier supernatural martial-arts Charm — the class of Charm the
    otherwise-Charmless and the otherwise-barred are repeatedly allowed to reach
    (mortals via Essence Mastery, ghosts via PG p.234). One definition, so the two
    routes cannot drift apart."""
    return (charm.category.split(":", 1)[0] == "martial_arts"
            and (charm.open_to_all or "Terrestrial" in charm.open_to_tiers))


def charm_learnable_by_splat(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """The picker/graph filter and the `charm-wrong-splat` check: `charm` is either
    natively available (charm_matches_splat) or reachable through the caste's
    foreign-Charm privilege. Kept separate from charm_matches_splat so that
    accessible_circles — which asks what the character's OWN splat can initiate —
    keeps its narrower question."""
    # The per-splat Charm bar, restated at this entry point rather than left to
    # charm_matches_splat. This function does not merely delegate — it falls THROUGH a
    # False answer into two further grants, so a bar checked only in the callee is one
    # this route walks straight past. Same shape as the bug preflight caught here on
    # 2026-08-01, one grant earlier.
    if charm.id in ruleset.exalt_for(character.exalt_type).barred_charm_ids:
        return False
    # The heritage-level bar is restated at THIS entry point too — the generalist
    # privilege below is a second route to the same permission, and a bar on only one
    # of two routes is the build's most-repeated bug.
    if charm.id in heritage_barred_charm_ids(ruleset, character):
        return False
    if heritage_bars_initiation(ruleset, character, charm):
        return False
    if charm_matches_splat(character, charm, ruleset):
        return True
    # A splat barred from other people's Charms outright (the dead, E:Ab p.126) is
    # refused HERE as well, not only in charm_matches_splat. The generalist privilege
    # below is a second route to the same permission, and a bar enforced on only one
    # of two routes is this build's most-repeated bug — a ghost given the Eclipse
    # privilege by a house rule would otherwise walk straight past p.126.
    if ruleset.exalt_for(character.exalt_type).foreign_charms_barred:
        return (splat_of(charm) in heritage_charm_access(ruleset, character)
                or (ruleset.exalt_for(character.exalt_type).terrestrial_martial_arts
                    and is_terrestrial_martial_arts(charm)))
    # A Charm flagged no_foreign_learning is never reachable through the generalist
    # rule (the Alchemical Weaving Engines — CH4, "Non-Alchemicals cannot learn
    # weaving Charms"): only its own splat, caught by the match above, may hold it.
    return foreign_charms_open(ruleset, character) and not charm.no_foreign_learning
