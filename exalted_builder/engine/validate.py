"""
engine/validate.py — pure legality checks: (RuleSet, Character) -> issues.

Where the models guard *shape* and derive.py computes *values*, this module
guards *rules*: that the traits a character actually holds are legal given the
rulebook. Pure — no I/O, no mutation; it reads the RuleSet and the Character and
returns a list of `Issue`s (empty == legal for the checks run).

Implemented so far:
  * Reference integrity — every Charm/Spell id on the character exists in the set.
  * Charm prerequisites — min essence, min ability, and the AND-of-OR Charm
    prerequisite graph.
  * Spell-circle access — a known Spell requires a known Charm that grants its
    Sorcery circle.

NOT yet implemented: chargen budget predicates (attribute pools, ability dots,
caste/favoured minimums, Charm counts, bonus-point reconciliation) and the XP-log
reconciliation. Those depend on design decisions still open with the rules
authority; see `validate_chargen` placeholder.

All thresholds come from the RuleSet (budgets / cost tables), never hardcoded, so
correcting the data corrects the engine.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from ..models.character import Character, FormulaEntry, RitualEntry, ThaumaturgyState
from ..models.rules import (
    AbilityName,
    AttributeName,
    Charm,
    CharmCountRequirement,
    CharmType,
    RuleSet,
    SpellCircle,
    VirtueName,
)
from . import derive

# Attribute categories and the order Strength/Dexterity/Stamina etc. (core p.104).
# Which category receives which of the 8/6/4 pools is the player's priority and is
# inferred from the spend, not stored — so this is just the membership grouping.
ATTRIBUTE_CATEGORIES: dict[str, tuple[AttributeName, ...]] = {
    "Physical": (AttributeName.STRENGTH, AttributeName.DEXTERITY, AttributeName.STAMINA),
    "Social": (AttributeName.CHARISMA, AttributeName.MANIPULATION, AttributeName.APPEARANCE),
    "Mental": (AttributeName.PERCEPTION, AttributeName.INTELLIGENCE, AttributeName.WITS),
}

# The repeatable Ox-Body-equivalent Charm is per-splat: each ExaltDefinition names
# its own (Solar's is solar.endurance.ox-body-technique). It is bought once per dot
# of its cap trait (Endurance; Stamina for Lunar), each purchase choosing a
# health-level package;
# stored on Character.ox_body, not in Character.charms (so the count is representable).


def ox_body_charm_id(ruleset: RuleSet, character: Character) -> str:
    """The id of this character's splat's repeatable Ox-Body-equivalent Charm (from
    its ExaltDefinition), or '' if the splat defines none."""
    return ruleset.exalt_for(character.exalt_type).ox_body_charm_id


def ox_body_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """The Ox-Body-equivalent Charm object for this character's splat, or None when
    the splat names none or the id is absent from the RuleSet."""
    return ruleset.charms.get(ox_body_charm_id(ruleset, character))


def gift_charm_id(ruleset: RuleSet, character: Character) -> str:
    """The id of this character's splat's repeatable Gift-granting Charm (Deadly
    Beastman Transformation for Lunar, p.124-127), or '' if the splat defines none."""
    return ruleset.exalt_for(character.exalt_type).gift_charm_id


def gift_charm(ruleset: RuleSet, character: Character) -> Charm | None:
    """The Gift-granting Charm object for this character's splat, or None when the
    splat names none or the id is absent from the RuleSet."""
    return ruleset.charms.get(gift_charm_id(ruleset, character))


# --------------------------------------------------------------------------- #
# The canonical Charm-pick enumeration
# --------------------------------------------------------------------------- #

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
    call_charms = calling_charm_ids(ruleset, character)
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
        else:
            costs.append(bp_costs.charm_favored_caste if cf else bp_costs.charm)
    return costs


# --------------------------------------------------------------------------- #
# The canonical Thaumaturgy-purchase enumeration
# --------------------------------------------------------------------------- #

def thaum_state(character: Character) -> ThaumaturgyState:
    """The character's thaumaturgy, or an empty state. `Character.thaumaturgy` is
    Optional so old saves load with None; every consumer wants the same empty
    answer, so it is centralised here rather than None-checked at each site."""
    return character.thaumaturgy or ThaumaturgyState()


class ThaumPurchase(BaseModel):
    """One thaumaturgic thing a character bought, in a shape both currencies price.

    The Charm-pick enumeration's sibling, and for the same reason: four
    heterogeneous purchasables (Arts, Art specialties, Sciences, rituals, formulas)
    live on five different lists, and each of the BP breakdown, the XP audit and the
    UI would otherwise walk all five and special-case each. They are enumerated once
    here and priced once in `thaum_purchase_bp_costs`.

    `level` is the ritual's or formula's level, or the Science's rating; 0 where the
    kind has none. `orientations` is how many regional versions are owned — the
    first is included in the base price and each further one costs a flat point
    (p.124), which is the whole reason a ritual is not a bare id.

    Every kind is priced. Sciences briefly were not — the published cost tables have
    no Science row — but that is a printing error Grabowski cleared up later, and the
    rate came from the rules authority (5/7 BP, 7/rating×6 XP).
    """
    kind: str                  # art | specialty | science | ritual | formula
    key: str                   # catalogue id, or "art_id:name" for a specialty
    label: str                 # display-ready
    level: int = 0
    orientations: int = 1
    narrowed: bool = False


def thaum_purchases(ruleset: RuleSet, character: Character) -> list[ThaumPurchase]:
    """Everything the character has bought in thaumaturgy RIGHT NOW, in sheet order:
    Arts, Art specialties, Sciences, rituals, formulas.

    This is what the UI must consume instead of reading the five `ThaumaturgyState`
    lists. Unresolvable ids are still yielded, with the raw id as the label, so a
    stale save shows the problem rather than dropping a row.
    """
    return _thaum_purchases_from(ruleset, thaum_state(character))


def chargen_thaum_purchases(ruleset: RuleSet, character: Character) -> list[ThaumPurchase]:
    """`thaum_purchases` over the traits chargen accounting reads: the frozen
    snapshot once locked, else the live state."""
    snap = character.chargen_snapshot
    state = (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character)
    return _thaum_purchases_from(ruleset, state)


def thaum_ritual_level(ruleset: RuleSet, entry: RitualEntry) -> int:
    """A ritual entry's level, from the catalogue when it references one and from the
    inline fields when it is custom (rituals are catalogue + custom by decision)."""
    ritual = ruleset.thaum_rituals.get(entry.ritual_id) if entry.ritual_id else None
    return ritual.level if ritual is not None else entry.level


def thaum_formula_level(ruleset: RuleSet, entry: FormulaEntry) -> int:
    formula = ruleset.thaum_formulas.get(entry.formula_id) if entry.formula_id else None
    return formula.level if formula is not None else entry.level


def _thaum_purchases_from(ruleset: RuleSet, state: ThaumaturgyState) -> list[ThaumPurchase]:
    """Build the purchase list from an explicit state, so the same enumeration serves
    both the live character and the chargen snapshot."""
    out: list[ThaumPurchase] = []

    for art_id in state.arts:
        art = ruleset.thaum_arts.get(art_id)
        out.append(ThaumPurchase(kind="art", key=art_id,
                                 label=art.name if art else art_id))

    for spec in state.art_specialties:
        art = ruleset.thaum_arts.get(spec.art_id)
        art_name = art.name if art else spec.art_id
        out.append(ThaumPurchase(
            kind="specialty", key=f"{spec.art_id}:{spec.name}",
            label=f"{art_name} ({spec.name})", narrowed=spec.narrowed))

    for sci in state.sciences:
        if sci.rating <= 0:
            continue
        science = ruleset.thaum_sciences.get(sci.science_id)
        out.append(ThaumPurchase(
            kind="science", key=sci.science_id,
            label=f"{science.name if science else sci.science_id} {sci.rating}",
            level=sci.rating))

    for entry in state.rituals:
        ritual = ruleset.thaum_rituals.get(entry.ritual_id) if entry.ritual_id else None
        name = ritual.name if ritual is not None else (entry.name or entry.ritual_id)
        level = thaum_ritual_level(ruleset, entry)
        out.append(ThaumPurchase(
            kind="ritual", key=entry.ritual_id or entry.name,
            label=_thaum_label(name, level, entry.orientations),
            level=level, orientations=len(entry.orientations)))

    for entry in state.formulas:
        formula = ruleset.thaum_formulas.get(entry.formula_id) if entry.formula_id else None
        name = formula.name if formula is not None else (entry.name or entry.formula_id)
        level = thaum_formula_level(ruleset, entry)
        out.append(ThaumPurchase(
            kind="formula", key=entry.formula_id or entry.name,
            label=_thaum_label(name, level, entry.orientations),
            level=level, orientations=len(entry.orientations)))

    return out


def _thaum_label(name: str, level: int, orientations: list) -> str:
    """`Name (level N; North, Realm)` — orientation is display state as well as
    accounting state, since which versions are owned is what the player reads back."""
    regions = ", ".join(o.value for o in orientations)
    return f"{name} (level {level}; {regions})" if regions else f"{name} (level {level})"


def thaum_purchase_bp_costs(ruleset: RuleSet, character: Character,
                            purchases: list[ThaumPurchase]) -> list[int]:
    """The bonus-point price of each purchase, in purchase order — parallel to
    `purchases`, so the UI can render a priced row per purchase. A Science's figure
    is the whole ladder up to its rating, since chargen holds a rating rather than a
    sequence of purchases."""
    # Deferred import: costs.py imports this module, so a top-level import here would
    # cycle. The thaum_* rate functions depend on nothing in validate, hence safe.
    from . import costs

    out: list[int] = []
    for p in purchases:
        if p.kind == "art":
            out.append(costs.thaum_art_bp(ruleset, character))
        elif p.kind == "specialty":
            out.append(costs.thaum_specialty_bp(ruleset, character, narrowed=p.narrowed))
        elif p.kind == "science":
            out.append(costs.thaum_science_bp(ruleset, character, p.level))
        elif p.kind == "ritual":
            out.append(costs.thaum_ritual_bp(ruleset, character, p.level, p.orientations))
        elif p.kind == "formula":
            out.append(costs.thaum_formula_bp(ruleset, character, p.orientations))
        else:
            out.append(0)
    return out


def thaumaturgy_issues(ruleset: RuleSet, character: Character,
                       state: ThaumaturgyState) -> list["Issue"]:
    """Legality of a thaumaturgic holding. Called from `validate_chargen` against the
    chargen state; safe to call on the live state too.

    The gates the source actually states:
      * Ghosts hold thaumaturgy but may never use it (p.114) — a flag, not a bar, so
        this is an info Issue and never blocks a purchase (rules-authority call 1).
      * The Fair Folk cannot learn it at all (p.114) — `thaumaturgy_usable` False.
      * "a thaumaturge must have an Occult score equal to or higher than the
        ritual's level" (p.148).
      * An Art's `min_occult`, and Summoning's per-aspect minima.
      * A Science may not exceed its own `max_rating` (Alchemy 6, the rest 5).

    Deliberately NOT gated: owning an Art is not required to buy a specialty in it
    (p.116 footnote, stated three times). Do not add that check.
    """
    issues: list[Issue] = []
    occult = ability_rating(character, AbilityName.OCCULT)
    exalt = ruleset.exalt_for(character.exalt_type)
    purchases = _thaum_purchases_from(ruleset, state)

    if not purchases:
        return issues

    if not exalt.thaumaturgy_usable:      # exalt_for never returns None
        issues.append(Issue(
            code="thaum-unusable", where=character.exalt_type,
            message=f"{character.exalt_type} may hold thaumaturgy but can never "
                    "use it (Player's Guide p.114).", severity="info",
        ))

    for art_id in state.arts:
        art = ruleset.thaum_arts.get(art_id)
        if art is None:
            issues.append(Issue(code="unknown-thaum-art", where=art_id,
                                message=f"Art {art_id} is not in the rule set."))
        elif occult < art.min_occult:
            issues.append(Issue(
                code="thaum-art-occult", where=art_id,
                message=f"The Art of {art.name} needs Occult {art.min_occult}; "
                        f"character has {occult}.",
            ))

    for spec in state.art_specialties:
        art = ruleset.thaum_arts.get(spec.art_id)
        if art is None:
            issues.append(Issue(
                code="unknown-thaum-art", where=spec.art_id,
                message=f"Specialty {spec.name!r} names Art {spec.art_id}, "
                        "which is not in the rule set."))
            continue
        # A printed aspect carries its own Occult minimum (Summoning alone). A
        # player-invented specialty matches no aspect and is ungated.
        aspect = next((a for a in art.aspects if a.name.casefold() == spec.name.casefold()),
                      None)
        if aspect is not None and occult < aspect.min_occult:
            issues.append(Issue(
                code="thaum-aspect-occult", where=f"{spec.art_id}:{spec.name}",
                message=f"{art.name} ({aspect.name}) needs Occult "
                        f"{aspect.min_occult}; character has {occult}.",
            ))
        if spec.narrowed and not art.aspect_narrowing:
            issues.append(Issue(
                code="thaum-narrowing-unavailable", where=f"{spec.art_id}:{spec.name}",
                message=f"Only Summoning allows an aspect to be further limited for "
                        f"half cost (p.127); {art.name} does not.",
            ))

    for sci in state.sciences:
        science = ruleset.thaum_sciences.get(sci.science_id)
        if science is None:
            issues.append(Issue(code="unknown-thaum-science", where=sci.science_id,
                                message=f"Science {sci.science_id} is not in the rule set."))
        elif sci.rating > science.max_rating:
            issues.append(Issue(
                code="thaum-science-range", where=sci.science_id,
                message=f"{science.name} is {sci.rating}; its maximum is "
                        f"{science.max_rating}.",
            ))

    for entry in state.rituals:
        if entry.ritual_id and entry.ritual_id not in ruleset.thaum_rituals:
            issues.append(Issue(code="unknown-thaum-ritual", where=entry.ritual_id,
                                message=f"Ritual {entry.ritual_id} is not in the rule set."))
            continue
        level = thaum_ritual_level(ruleset, entry)
        if occult < level:
            name = entry.ritual_id or entry.name
            issues.append(Issue(
                code="thaum-ritual-occult", where=name,
                message=f"A level-{level} ritual needs Occult {level}; "
                        f"character has {occult} (p.148).",
            ))

    for entry in state.formulas:
        if entry.formula_id and entry.formula_id not in ruleset.thaum_formulas:
            issues.append(Issue(
                code="unknown-thaum-formula", where=entry.formula_id,
                message=f"Formula {entry.formula_id} is not in the rule set."))

    return issues


def _repeatable_purchase_cap(charm: Charm, character: Character) -> int:
    """Resolve a repeatable Charm's `repeatable_cap_ability` against the character:
    an Ability, an Attribute, or the special value 'essence' (Deadly Beastman
    Transformation, p.124 — "no more times than he has points of Essence"; Essence
    isn't an Ability or Attribute, so it can't come through the normal lookups).
    0 if the Charm isn't repeatable or the trait name resolves to none of these."""
    if not charm.repeatable_cap_ability:
        return 0
    if charm.repeatable_cap_ability == "essence":
        return character.essence_rating
    try:
        return character.abilities[AbilityName(charm.repeatable_cap_ability)]
    except ValueError:
        pass
    try:
        return character.attributes[AttributeName(charm.repeatable_cap_ability)]
    except ValueError:
        return 0


class Issue(BaseModel):
    """One legality finding. `code` is a stable machine tag; `where` locates the
    offending trait (a Charm/Spell id, an ability name, etc.)."""
    code: str
    message: str
    where: str = ""
    severity: str = "error"        # "error" | "warning"


# --------------------------------------------------------------------------- #
# Reference integrity
# --------------------------------------------------------------------------- #

def check_references(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Every Charm/Spell id the character holds must resolve in the RuleSet.
    Equipment is an inline copy by design and is intentionally not checked."""
    issues: list[Issue] = []
    for cid in character.charms:
        if cid not in ruleset.charms:
            issues.append(Issue(
                code="unknown-charm", where=cid,
                message=f"Character holds unknown Charm id {cid!r}.",
            ))
    for sid in character.spells:
        if sid not in ruleset.spells:
            issues.append(Issue(
                code="unknown-spell", where=sid,
                message=f"Character holds unknown Spell id {sid!r}.",
            ))
    return issues


# --------------------------------------------------------------------------- #
# Charm prerequisites
# --------------------------------------------------------------------------- #

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


def _min_trait_rating(character: Character, charm: Charm) -> tuple[str, int] | None:
    """The (trait name, character's rating) `charm.min_ability` is checked
    against — an Attribute for Lunar's Attribute-keyed Charms (`min_attribute`
    set, p.122), otherwise the Ability `category` resolves to. None if the Charm
    gates on neither (e.g. a `category` like 'sorcery' with no `min_attribute`).

    `min_attribute` takes priority: some categories (e.g. 'melee') are ALSO
    valid AbilityName values, and a Lunar Melee Charm must gate on the Dexterity/
    Strength/etc. `min_attribute` names, never on the character's Melee Ability
    rating — the two happen to collide by name, not by meaning."""
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
    return out


def charm_ability_requirements(charm: Charm) -> list[tuple[str, int]]:
    """Every Ability/Attribute minimum a Charm imposes, as (trait label, rating), for
    display. The primary gate first, then the extras in authored order. Presenters use
    this instead of reading `min_ability` alone, so a multi-gate Charm cannot show only
    half its requirements on the sheet or in the picker."""
    out: list[tuple[str, int]] = []
    if charm.min_attribute:
        out.append((charm.min_attribute, charm.min_ability))
    else:
        ability = _category_ability(charm.category)
        if ability is not None:
            out.append((ability.value, charm.min_ability))
    for req in charm.extra_min_abilities:
        out.append((" or ".join(a.value for a in req.abilities), req.rating))
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


def craft_rating(character: Character) -> int:
    """The effective Craft Ability rating: the highest of the character's per-focus
    Craft instances (core p.136), or 0 if they have none. A Craft Charm's minimum
    Ability is met by the best craft a character possesses."""
    return max((c.rating for c in character.crafts), default=0)


def ability_rating(character: Character, ability: AbilityName) -> int:
    """A character's rating in `ability`, reading Craft from its per-focus instances
    rather than the (unused) AbilityName.CRAFT dot."""
    if ability == AbilityName.CRAFT:
        return craft_rating(character)
    return character.abilities.get(ability, 0)


def _ability_slots(abilities: dict, crafts: list):
    """Yield (ability, rating) pairs for chargen ability accounting. The single
    AbilityName.CRAFT key is dropped and each Craft instance contributes its own
    slot (keyed to CRAFT), so per-focus crafts are budgeted, capped and discounted
    independently like the separate Abilities they are."""
    for ab, rating in abilities.items():
        if ab == AbilityName.CRAFT:
            continue
        yield ab, rating
    for cr in crafts:
        yield AbilityName.CRAFT, cr.rating


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
    return issues


# Dragon-Blooded martial-arts "Enlightenment" gate (DB p241-242). A Terrestrial
# must master both Immaculate enlightenment Charms — Spirit Sight, then Spirit
# Walking — before she may learn the Charms of any Dragon Path. Celestial Exalted
# and Abyssals need no such initiation (the p241 box: Exalted of any type can learn
# the Dragon Paths given a tutor), so the gate is Dragon-Blooded-only; and Five-
# Dragon Style — a mundane DB style, not a Dragon Path — is exempt.
DB_MA_ENLIGHTENMENT_IDS = ("dragonblooded.martial-arts.spirit-sight",
                           "dragonblooded.martial-arts.spirit-walking")
_UNGATED_MA_STYLES = frozenset({"five-dragon", "enlightenment"})


def _is_dragon_path_style(category: str) -> bool:
    """A martial-arts style category that counts as a 'Dragon Path' for the DB
    enlightenment gate — any ``martial_arts:<style>`` except the exempt styles
    (Five-Dragon and the Enlightenment tree itself)."""
    if not category.startswith("martial_arts:"):
        return False
    return category.split(":", 1)[1] not in _UNGATED_MA_STYLES


def db_enlightenment_met(character: Character) -> bool:
    """Whether the Dragon-Blooded Dragon-Path gate is OPEN for this character: always
    True for non-Dragon-Blooded (they need no initiation); for a Dragon-Blooded, True
    only once BOTH Immaculate enlightenment Charms (Spirit Sight + Spirit Walking)
    are known."""
    if character.exalt_type != "Dragon-Blooded":
        return True
    known = set(character.charms)
    return all(cid in known for cid in DB_MA_ENLIGHTENMENT_IDS)


def category_available(ruleset: RuleSet, character: Character, category: str) -> bool:
    """Whether a Charm `category` is open to the character right now — the picker's
    style-dropdown filter. Currently the only gate is the Dragon-Blooded Dragon-Path
    rule (p241): a DB reaches the elemental Dragon styles only after learning both
    enlightenment Charms. Every other category is always available."""
    return not (_is_dragon_path_style(category) and not db_enlightenment_met(character))


def meets_charm_requirements(ruleset: RuleSet, character: Character, charm) -> bool:
    """Whether the character could legally learn `charm` *right now*: min essence,
    min ability (when the category resolves to an ability), every AND-of-OR
    prerequisite group satisfied by an already-known Charm, and — for a Dragon-
    Blooded — the Dragon-Path enlightenment gate (p241). The forward-looking
    counterpart to check_charm_prerequisites; used by the charm-tree picker to
    decide which Charms are currently selectable."""
    if _is_dragon_path_style(charm.category) and not db_enlightenment_met(character):
        return False
    if character.essence_rating < charm.min_essence:
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


# --------------------------------------------------------------------------- #
# Spell-circle access
# --------------------------------------------------------------------------- #

def granted_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """The set of magic circles the character can cast in, taken from the
    `grants_circle` of every known initiation Charm. Track-agnostic (sorcery or,
    later, necromancy) — the circle enum carries the distinction."""
    return {
        ruleset.charms[cid].grants_circle
        for cid in character.charms
        if cid in ruleset.charms and ruleset.charms[cid].grants_circle is not None
    }


def accessible_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """Every magic circle this character can reach — the circle granted by any
    initiation Charm they may learn (their own Exalt type, or an `open_to_all`
    Charm), unioned with circles already granted by known Charms.

    This is what the spell picker should show, and it is deliberately NOT the same
    as the Exalt's nominal `magic_track`: a splat whose Charm trees hold BOTH sorcery
    and necromancy initiations (Abyssals carry Terrestrial/Celestial Sorcery AND the
    three Necromancy circles) reaches both tracks, so its picker must too. Track is a
    display-ordering hint, not an access gate — the gate is the granting Charm."""
    out = granted_circles(ruleset, character)
    for charm in ruleset.charms.values():
        if charm.grants_circle is not None and charm_matches_splat(character, charm, ruleset):
            out.add(charm.grants_circle)
    return out


def chargen_barred_circle(ruleset: RuleSet, character: Character) -> SpellCircle | None:
    """The magic circle barred at character creation for this Exalt type, resolved
    from ExaltDefinition.highest_magic_circle_id (Solars: the Solar Circle, core
    p.100). Empty or unrecognised -> None (nothing barred at creation)."""
    cid = ruleset.exalt_for(character.exalt_type).highest_magic_circle_id
    try:
        return SpellCircle(cid) if cid else None
    except ValueError:
        return None


def meets_spell_requirements(ruleset: RuleSet, character: Character, spell,
                             *, chargen: bool = True) -> bool:
    """Whether the character could learn `spell` right now: a known Charm must grant
    its circle, and at chargen the Exalt type's highest circle is barred (Solars:
    Solar Circle, core p.100). Forward-looking counterpart to check_spell_access."""
    if chargen and spell.circle == chargen_barred_circle(ruleset, character):
        return False
    return spell.circle in granted_circles(ruleset, character)


def check_spell_access(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A known Spell requires a known Charm whose `grants_circle` matches
    the Spell's circle.

    Exact-circle match is correct for 1e (core pp.191): the three initiation
    Charms form a prerequisite chain — Celestial Circle Sorcery requires
    Terrestrial, Solar requires Celestial — so a higher-circle sorcerer always
    also holds the lower Charms (enforced by check_charm_prerequisites) and can
    cast lower-circle spells through them. No separate circle-nesting rule is
    needed here; the prerequisite chain provides it.
    """
    granted = granted_circles(ruleset, character)
    issues: list[Issue] = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        if spell.circle not in granted:
            issues.append(Issue(
                code="spell-circle", where=sid,
                message=(f"{spell.name}: no known Charm grants the "
                         f"{spell.circle.value} circle."),
            ))
    return issues


# --------------------------------------------------------------------------- #
# Combos
# --------------------------------------------------------------------------- #

# Only Charms of instant duration may be Comboed (core p.213). Compared against
# Charm.duration, whose instant value is the model default "Instant".
_COMBO_DURATION = "Instant"

# Castes allowed to mix Ability-based and Attribute-based Charms in one Combo
# (Lunars p.122): Solar Eclipse and Abyssal Moonshadow are "gifted generalists"
# who may cross the two Charm systems; every other caste (including every
# Lunar caste, whose native Charms are ALL Attribute-based already, and any
# other splat's caste) may not. A Lunar combining native Attribute Charms with
# an open_to_tiers Ability-keyed Martial Arts style (e.g. Five-Dragon Style, a
# Celestial-tier style a Lunar can learn) hits this the same as anyone else —
# the sourcebook names only Eclipse/Moonshadow for the crossover, not "any
# Lunar." This checks Combo COMPOSITION legality only; the p.122 dice-pool cap
# for a mixed Combo (2x Essence) is a play-time numeric limit with no home in
# this engine, same as the rest of attack/damage math (see the Combat/attack
# derivation out-of-scope decision).
_MIXED_COMBO_CASTES = {"eclipse", "moonshadow"}


def combo_issues(ruleset: RuleSet, character: Character, combo) -> list[Issue]:
    """Legality findings for a single Combo (core pp.213-214): two or more *known*
    Charms of instant duration, no Charm twice, at most one Simple and at most one
    Extra Action Charm. `where` is the Combo's name. The picker uses this per-Combo;
    validate_combos aggregates it over the character."""
    issues: list[Issue] = []
    known = set(character.charms)
    where = combo.name or "(unnamed combo)"
    if len(combo.charm_ids) < 2:
        issues.append(Issue(
            code="combo-too-small", where=where,
            message=f"Combo {where!r} has {len(combo.charm_ids)} Charm(s); a Combo "
                    "must combine at least two.",
        ))
    seen: set[str] = set()
    simple = extra_action = 0
    has_attribute_charm = has_ability_charm = False
    for cid in combo.charm_ids:
        if cid in seen:
            issues.append(Issue(
                code="combo-duplicate-charm", where=where,
                message=f"Combo {where!r} includes {cid!r} more than once; a Combo "
                        "may not repeat a Charm.",
            ))
            continue
        seen.add(cid)
        if cid not in known:
            issues.append(Issue(
                code="combo-unknown-charm", where=where,
                message=f"Combo {where!r} includes {cid!r}, which the character "
                        "does not know.",
            ))
            continue
        charm = ruleset.charms.get(cid)
        if charm is None:                 # known id absent from the set: check_references reports it
            continue
        if charm.duration != _COMBO_DURATION:
            issues.append(Issue(
                code="combo-non-instant", where=where,
                message=f"Combo {where!r}: {charm.name} has {charm.duration} duration; "
                        "Combos may only contain instant-duration Charms.",
            ))
        if charm.type == CharmType.SIMPLE:
            simple += 1
        elif charm.type == CharmType.EXTRA_ACTION:
            extra_action += 1
        if charm.min_attribute:
            has_attribute_charm = True
        else:
            has_ability_charm = True
    if simple > 1:
        issues.append(Issue(
            code="combo-multiple-simple", where=where,
            message=f"Combo {where!r} has {simple} Simple Charms; a Combo may "
                    "contain at most one.",
        ))
    if extra_action > 1:
        issues.append(Issue(
            code="combo-multiple-extra-action", where=where,
            message=f"Combo {where!r} has {extra_action} Extra Action Charms; a "
                    "Combo may contain at most one.",
        ))
    if (has_attribute_charm and has_ability_charm
            and character.caste not in _MIXED_COMBO_CASTES):
        issues.append(Issue(
            code="combo-mixed-attribute-ability", where=where,
            message=f"Combo {where!r} mixes an Attribute-based Charm with an "
                    "Ability-based Charm; only Solar Eclipse and Abyssal "
                    "Moonshadow Charms may cross the two systems in one Combo.",
        ))
    return issues


def eligible_combo_charms(ruleset: RuleSet, character: Character) -> list[str]:
    """Ids of the character's known Charms that may legally go in a Combo — i.e.
    those of instant duration (core p.213). Order follows the character's Charm
    list. The picker offers these when adding a Charm to a Combo."""
    out: list[str] = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.duration == _COMBO_DURATION:
            out.append(cid)
    return out


def validate_combos(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every Combo the character holds (core pp.213-214). The
    Storyteller veto of specific Combos and the in-play activation rules are out of
    scope here; the bonus-point cost is accounted in validate_chargen. Operates on
    the character's current Charms/Combos (like the other reference checks)."""
    issues: list[Issue] = []
    for combo in character.combos:
        issues += combo_issues(ruleset, character, combo)
    return issues


def background_rule(budgets, name: str):
    """The `BackgroundRule` for the Background called `name` under these budgets, or
    None when it has no mechanics. Backgrounds are free text, so the lookup is by
    lowercased, stripped NAME — not by `BackgroundType.id`."""
    return budgets.background_rules.get(name.strip().lower())


def camp_for(ruleset, character):
    """The character's TrainingCamp, or None. `camp` is only meaningful for an origin
    whose budget sets `requires_camp` (Cult of the Illuminated, p.89), but a stray id
    still resolves here — legality is `check_camp_and_calling`'s job."""
    return ruleset.camps.get(character.camp) if character.camp else None


def calling_for(ruleset, character):
    """The character's Calling, or None."""
    return ruleset.callings.get(character.calling) if character.calling else None


def calling_abilities(ruleset, character) -> set:
    """The Abilities the character's Calling discounts (p.90). NOT Favored Abilities —
    the discount stacks with the Caste/Favoured one, so the two sets stay separate and
    a Calling Ability does NOT count toward the Caste/Favoured dot minimum."""
    calling = calling_for(ruleset, character)
    return set(calling.abilities) if calling else set()


def calling_charm_ids(ruleset, character) -> set:
    """The Charm ids the character's Calling discounts."""
    calling = calling_for(ruleset, character)
    return set(calling.charms) if calling else set()


def is_calling_charm(ruleset, character, charm) -> bool:
    charm_id = getattr(charm, "id", charm)
    return charm_id in calling_charm_ids(ruleset, character)


def camp_min_abilities(ruleset, character) -> list:
    """The Ability floors imposed by the character's training camp (p.89), unioned
    into the chargen minimums exactly as the caste's own are. Suppressed by the same
    `ignore_caste_min_abilities` switch, on the grounds that an origin declaring
    itself free of required Ability scores means all of them."""
    camp = camp_for(ruleset, character)
    return list(camp.required_min_abilities) if camp else []


def granted_charm_ids(ruleset, character) -> list[str]:
    """Every Charm the character holds for free from their camp package (p.90).

    Read off `character.granted_charms`, which is the RESOLVED list (the camp's fixed
    grants plus the player's choices). These are granted, not picked: they must never
    count against the Charm pool or the Caste/Favoured Charm minimum."""
    return list(character.granted_charms)


def check_camp_and_calling(ruleset, character) -> list[Issue]:
    """Camp/Calling legality (Cult of the Illuminated, p.89-93). Data-driven off the
    budget's `requires_camp`/`requires_calling`, so no splat or origin is named here."""
    issues: list[Issue] = []
    budgets = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)

    if budgets.requires_camp:
        camp = camp_for(ruleset, character)
        if camp is None:
            issues.append(Issue(
                code="camp-required",
                message="This origin requires a training camp; none is set."
                        if not character.camp else
                        f"Unknown training camp {character.camp!r}.",
            ))
        elif camp.exalt_type != character.exalt_type or (
                camp.origin and camp.origin != character.origin):
            issues.append(Issue(
                code="camp-wrong-origin", where=camp.id,
                message=f"Training camp {camp.label!r} belongs to "
                        f"{camp.exalt_type}/{camp.origin or 'any'}, not "
                        f"{character.exalt_type}/{character.origin or 'any'}.",
            ))
    elif character.camp:
        issues.append(Issue(
            code="camp-not-supported", where=character.camp,
            message="This origin has no training camps, but one is set.",
        ))

    if budgets.requires_calling:
        calling = calling_for(ruleset, character)
        if calling is None:
            issues.append(Issue(
                code="calling-required",
                message="This origin requires a Calling; none is set."
                        if not character.calling else
                        f"Unknown Calling {character.calling!r}.",
            ))
        # A Calling belongs to ONE camp (p.90-92): the Tabernacle's three are not on
        # offer at Kether Rock.
        elif character.camp and calling.camp and calling.camp != character.camp:
            issues.append(Issue(
                code="calling-wrong-camp", where=calling.id,
                message=f"Calling {calling.label!r} is offered by {calling.camp!r}, "
                        f"not by {character.camp!r}.",
            ))
    elif character.calling:
        issues.append(Issue(
            code="calling-not-supported", where=character.calling,
            message="This origin has no Callings, but one is set.",
        ))

    return issues


def default_camp_and_calling(ruleset, character) -> tuple[str, str, list[str]]:
    """The (camp id, calling id, granted Charm ids) a character of this splat/origin
    should default to — the first camp offered, its first Calling, and that camp's
    automatic grants. All three empty when the origin has no camps.

    Lives here rather than in the editor because "which camp is legal, and what does it
    hand you" is a rules question, and the UI is meant to contain no game logic. It also
    makes the behaviour testable without driving a browser: picking the Illuminated
    origin has to leave the character LEGAL, not merely leave three more dropdowns to
    fill in.

    Keeps a camp/Calling the character already has if it is still valid, so re-running
    this is idempotent and never silently discards a player's choice."""
    camps = ruleset.camps_for(character.exalt_type, character.origin)
    if not camps:
        return "", "", []

    camp = next((c for c in camps if c.id == character.camp), camps[0])
    callings = ruleset.callings_for(camp.id)
    calling = next((c.id for c in callings if c.id == character.calling),
                   callings[0].id if callings else "")

    granted = list(camp.granted_charms)
    if camp.id == character.camp:
        # Same camp: preserve whatever the player already resolved for each choice, and
        # only top up the fixed grants.
        granted = list(dict.fromkeys(granted + list(character.granted_charms)))
    return camp.id, calling, granted


def granted_charm_issues(ruleset, character) -> list[Issue]:
    """Whether `character.granted_charms` is a legal resolution of the camp's free-Charm
    package (p.90): every fixed grant present, each choice resolved, nothing extra, and
    the character meeting each granted Charm's own minima ("As usual, the Solar must
    meet the minimum requirements to gain these Charms")."""
    issues: list[Issue] = []
    camp = camp_for(ruleset, character)
    granted = list(character.granted_charms)

    if camp is None:
        if granted:
            issues.append(Issue(
                code="granted-charm-not-supported",
                message="Granted Charms are set, but the character has no training camp.",
            ))
        return issues

    seen = set()
    for cid in granted:
        if cid not in ruleset.charms:
            issues.append(Issue(code="granted-charm-unknown", where=cid,
                                message=f"Unknown Charm {cid!r} in the camp package."))
        if cid in seen:
            issues.append(Issue(code="granted-charm-duplicate", where=cid,
                                message=f"Charm {cid!r} is granted twice."))
        seen.add(cid)

    remaining = list(granted)
    for cid in camp.granted_charms:
        if cid in remaining:
            remaining.remove(cid)
        else:
            issues.append(Issue(
                code="granted-charm-missing", where=cid,
                message=f"{camp.label} grants {_charm_name(ruleset, cid)} to every "
                        f"graduate; it is not in the character's granted Charms.",
            ))

    for choice in camp.granted_charm_choices:
        if choice.fixed_sets:
            # Exactly one whole printed set, all-or-nothing.
            match = next((grp for grp in choice.fixed_sets
                          if all(c in remaining for c in grp)), None)
            if match is None:
                issues.append(Issue(
                    code="granted-charm-choice-unresolved", where=choice.label,
                    message=f"{camp.label}: {choice.label} — none of the "
                            f"{len(choice.fixed_sets)} options is fully taken.",
                ))
            else:
                for cid in match:
                    remaining.remove(cid)
        elif choice.from_categories:
            # `pick` Charms, all from ONE of the listed categories.
            by_cat: dict[str, list[str]] = {}
            for cid in remaining:
                charm = ruleset.charms.get(cid)
                if charm is not None and charm.category in choice.from_categories:
                    by_cat.setdefault(charm.category, []).append(cid)
            chosen = next((cat for cat, ids in by_cat.items() if len(ids) >= choice.pick), None)
            if chosen is None:
                issues.append(Issue(
                    code="granted-charm-choice-unresolved", where=choice.label,
                    message=f"{camp.label}: {choice.label} — needs {choice.pick} Charm(s) "
                            f"from ONE of {', '.join(choice.from_categories)}.",
                ))
            else:
                if len(by_cat) > 1:
                    issues.append(Issue(
                        code="granted-charm-choice-mixed", where=choice.label,
                        message=f"{camp.label}: {choice.label} — the Charms must all come "
                                f"from ONE style; found "
                                f"{', '.join(sorted(by_cat))}.",
                    ))
                for cid in by_cat[chosen][:choice.pick]:
                    remaining.remove(cid)

    for cid in remaining:
        issues.append(Issue(
            code="granted-charm-extra", where=cid,
            message=f"{_charm_name(ruleset, cid)} is not part of {camp.label}'s package.",
        ))

    # The character must still qualify for what they were given.
    for cid in granted:
        charm = ruleset.charms.get(cid)
        if charm is None:
            continue
        ok, why = _granted_charm_minima_met(ruleset, character, charm)
        if not ok:
            issues.append(Issue(code="granted-charm-minimum", where=cid, message=why))

    return issues


def _charm_name(ruleset, charm_id: str) -> str:
    charm = ruleset.charms.get(charm_id)
    return charm.name if charm is not None else charm_id


def _granted_charm_minima_met(ruleset, character, charm) -> tuple[bool, str]:
    """A granted Charm is exempt from the Charm POOL, not from its own requirements
    (p.90). Prerequisites are deliberately NOT checked: the package hands out Charms
    like Iron Skin Concentration whose own tree the character has not climbed, and the
    page grants them outright."""
    short = charm_ability_shortfalls(character, charm)
    if short:
        label, want, have = short[0]
        return False, (f"{charm.name} is granted by the camp but requires "
                       f"{label} {want}; character has {have}.")
    if character.essence_rating < charm.min_essence:
        return False, (f"{charm.name} is granted by the camp but requires Essence "
                       f"{charm.min_essence}; character has {character.essence_rating}.")
    return True, ""


def background_pool_dots(rule, rating: int) -> int:
    """How many dots of the chargen Background pool a rating of `rating` consumes.
    Ordinarily one per dot; a rule may make the dots above a threshold cost more
    (Alchemical Artifact: dots 4 and 5 cost two pool dots each, CH2 p.65), and may
    grant the first `free_rating` dots outside the pool entirely (the Illuminated
    Solar's Illumination •, p.90 — "in addition" to the nine dots, so it is free
    rather than merely mandatory; contrast Alchemical Class •••, which is mandatory
    and paid for)."""
    if rule is None:
        return rating
    if rule.expensive_above and rating > rule.expensive_above:
        cheap = rule.expensive_above
        paid = cheap + (rating - cheap) * rule.expensive_dot_cost
    else:
        paid = rating
    return max(0, paid - rule.free_rating)


def background_rating(backgrounds, name: str) -> int:
    """The character's rating in the Background called `name` (0 if absent). Sums
    duplicates, since Backgrounds are free text and nothing stops two rows."""
    key = name.strip().lower()
    return sum(bg.rating for bg in backgrounds if bg.name.strip().lower() == key)


def background_issues(budgets, backgrounds) -> list[Issue]:
    """Chargen legality for Backgrounds that carry mechanics (`background_rules`).
    Empty for every splat with none — which is all of them but the Alchemical, whose
    book is the first to give Backgrounds real rules (CH2 p.65-69).

    Two checks: a Background the splat receives automatically may not be below that
    rating (Alchemicals "automatically receive Class ••• during character creation"),
    and a Background gated on another must have it (Backing "requires Class •••+").

    Plus, when the origin restricts WHICH Backgrounds it may take at all
    (`allowed_backgrounds` — the Sidereal ronin, p.100), anything outside that list is
    flagged. Blank rows are skipped: the editor adds an empty row for the player to
    fill in, and an unnamed row is not yet an illegal Background."""
    issues: list[Issue] = []
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
    for name, rule in budgets.background_rules.items():
        rating = background_rating(backgrounds, name)
        if rule.min_rating and rating < rule.min_rating:
            issues.append(Issue(
                code="background-below-minimum", where=name,
                message=f"{name.title()} is automatically {rule.min_rating} at character "
                        f"creation; this character has {rating}.",
            ))
        if rule.requires and rating > 0:
            have = background_rating(backgrounds, rule.requires)
            if have < rule.requires_rating:
                issues.append(Issue(
                    code="background-requires", where=name,
                    message=f"{name.title()} requires {rule.requires.title()} "
                            f"{rule.requires_rating}+; this character has {have}.",
                ))
    return issues


def eligible_array_charms(ruleset: RuleSet, character: Character) -> list[str]:
    """Ids of the character's known Charms that may legally be linked into an Array
    (p.89) — Attribute-based and `arrayable`, which excludes the Ability-based
    supernatural martial arts and the Weaving Engines. Order follows the character's
    Charm list. This is the Array counterpart of `eligible_combo_charms`: it does NOT
    exclude Charms already sitting in an Array (`validate_arrays` reports reuse), so
    the caller decides whether to offer them again."""
    out: list[str] = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.min_attribute and charm.arrayable:
            out.append(cid)
    return out


def array_issues(ruleset: RuleSet, character: Character, array) -> list[Issue]:
    """Legality findings for a single Alchemical Array (p.89): two or more *known*
    Charms, no Charm twice, and every member Attribute-based (supernatural martial
    arts, which are Ability-based, may not join). The instant-duration / one-Simple
    limits are NOT checked here — they bound the integrated Combos an Array grants,
    not the Array itself. `where` is the Array's name."""
    issues: list[Issue] = []
    known = set(character.charms)
    where = array.name or "(unnamed array)"
    if len(array.charm_ids) < 2:
        issues.append(Issue(
            code="array-too-small", where=where,
            message=f"Array {where!r} has {len(array.charm_ids)} Charm(s); an Array "
                    "must link at least two.",
        ))
    seen: set[str] = set()
    for cid in array.charm_ids:
        if cid in seen:
            issues.append(Issue(
                code="array-duplicate-charm", where=where,
                message=f"Array {where!r} includes {cid!r} more than once; link a "
                        "second copy of the Charm into a separate Array instead.",
            ))
            continue
        seen.add(cid)
        if cid not in known:
            issues.append(Issue(
                code="array-unknown-charm", where=where,
                message=f"Array {where!r} includes {cid!r}, which the character "
                        "does not know.",
            ))
            continue
        charm = ruleset.charms.get(cid)
        if charm is None:                 # known id absent from the set: check_references reports it
            continue
        if not charm.min_attribute:
            issues.append(Issue(
                code="array-non-attribute-charm", where=where,
                message=f"Array {where!r}: {charm.name} is not Attribute-based; only "
                        "Attribute-based Charms may be linked into an Array (this "
                        "excludes supernatural martial arts).",
            ))
        elif not charm.arrayable:
            issues.append(Issue(
                code="array-charm-not-arrayable", where=where,
                message=f"Array {where!r}: {charm.name} may not be placed in an Array.",
            ))
    return issues


def validate_arrays(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every Array the character holds (p.89). Adds two cross-Array
    rules to the per-Array checks: only a Charm-Slot splat may build Arrays (p.90 —
    Eclipse/Moonshadow may not), and a Charm may sit in at most one Array unless
    bought again (there is only one copy of each id on the character)."""
    issues: list[Issue] = []
    if not character.arrays:
        return issues
    slots = uses_charm_slots(ruleset, character)
    seen_charms: set[str] = set()
    for array in character.arrays:
        where = array.name or "(unnamed array)"
        if not slots:
            issues.append(Issue(
                code="array-not-supported", where=where,
                message=f"Array {where!r}: only Alchemical Exalted build Arrays "
                        "(Eclipse and Moonshadow Caste may not, p.90).",
            ))
        issues += array_issues(ruleset, character, array)
        for cid in set(array.charm_ids):
            if cid in seen_charms:
                issues.append(Issue(
                    code="array-charm-reused", where=where,
                    message=f"Array {where!r} reuses {cid!r}, already linked into "
                            "another Array; a Charm may join only one Array unless "
                            "purchased again.",
                ))
            seen_charms.add(cid)
    return issues


def submodule_def(ruleset: RuleSet, charm_id: str, key: str):
    """The rules.Submodule with `key` on Charm `charm_id`, or None if either the
    Charm or the key is absent."""
    charm = ruleset.charms.get(charm_id)
    if charm is None:
        return None
    return next((s for s in charm.submodules if s.key == key), None)


def owns_submodule(character: Character, charm_id: str, key: str) -> bool:
    """Whether the character has already purchased this submodule."""
    return any(s.charm_id == charm_id and s.key == key for s in character.submodules)


def submodule_block_reason(ruleset: RuleSet, character: Character,
                           charm_id: str, key: str) -> str:
    """Why this submodule cannot be purchased right now — "" when it can. The same
    gates `validate_submodules` and `advancement.learn_submodule` apply (parent Charm
    installed, own Essence and Attribute minimums), phrased for the picker so the UI
    never re-derives them. Says nothing about affordability: BP and XP are the
    caller's budget question, not a legality one."""
    definition = submodule_def(ruleset, charm_id, key)
    if definition is None:
        return "No such submodule."
    if owns_submodule(character, charm_id, key):
        return "Already purchased."
    if charm_id not in character.charms:
        charm = ruleset.charms.get(charm_id)
        return f"Install {charm.name if charm else charm_id} first."
    if character.essence_rating < definition.min_essence:
        return f"Requires Essence {definition.min_essence}."
    if definition.min_attribute:
        try:
            attr = AttributeName(definition.min_attribute)
        except ValueError:
            return f"Unknown Attribute {definition.min_attribute!r}."
        if character.attributes.get(attr, 0) < definition.min_attribute_rating:
            return (f"Requires {definition.min_attribute.title()} "
                    f"{definition.min_attribute_rating}.")
    return ""


def validate_submodules(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of every purchased submodule (p.89): its parent Charm must exist and
    be known, the key must be a real submodule of that Charm, no submodule bought
    twice, and the character must meet the submodule's own Essence / Attribute
    minimums. Used for both chargen (BP) and post-lock (XP) purchases."""
    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    known = set(character.charms)
    for sub in character.submodules:
        where = f"{sub.charm_id}:{sub.key}"
        pair = (sub.charm_id, sub.key)
        if pair in seen:
            issues.append(Issue(
                code="submodule-duplicate", where=where,
                message=f"Submodule {where!r} is purchased more than once.",
            ))
            continue
        seen.add(pair)
        charm = ruleset.charms.get(sub.charm_id)
        if charm is None:
            issues.append(Issue(
                code="submodule-unknown-charm", where=where,
                message=f"Submodule {where!r} names Charm {sub.charm_id!r}, which is "
                        "not in the rule set.",
            ))
            continue
        definition = submodule_def(ruleset, sub.charm_id, sub.key)
        if definition is None:
            issues.append(Issue(
                code="submodule-unknown", where=where,
                message=f"{charm.name} has no submodule {sub.key!r}.",
            ))
            continue
        if sub.charm_id not in known:
            issues.append(Issue(
                code="submodule-charm-not-known", where=where,
                message=f"Submodule {definition.name}: its Charm {charm.name} is not "
                        "known/installed.",
            ))
        if character.essence_rating < definition.min_essence:
            issues.append(Issue(
                code="submodule-essence", where=where,
                message=f"Submodule {definition.name} requires Essence "
                        f"{definition.min_essence}; has {character.essence_rating}.",
            ))
        if definition.min_attribute:
            try:
                attr = AttributeName(definition.min_attribute)
            except ValueError:
                attr = None
            have = character.attributes.get(attr, 0) if attr is not None else 0
            if have < definition.min_attribute_rating:
                issues.append(Issue(
                    code="submodule-attribute", where=where,
                    message=f"Submodule {definition.name} requires "
                            f"{definition.min_attribute} {definition.min_attribute_rating}; "
                            f"has {have}.",
                ))
    return issues


def array_installation_motes(ruleset: RuleSet, charm_ids) -> int:
    """The combined installation cost of one Array's member Charms (p.89):
    three-fourths of their summed cost, rounded up. Public so the UI can show an
    Array's mote saving using the same arithmetic the chargen check applies."""
    total = sum(ruleset.charms[cid].installation_cost
                for cid in charm_ids if cid in ruleset.charms)
    return (3 * total + 3) // 4              # ceil(3/4 * total)


def _installation_motes(ruleset: RuleSet, charm_ids, arrays) -> int:
    """Total Personal Essence committed to install `charm_ids`, applying the Array
    discount (p.89): a Charm inside an Array contributes to that Array's combined
    installation cost, which is three-fourths of the sum, rounded up; a Charm in no
    Array contributes its own full installation cost."""
    array_of: dict[str, int] = {}
    for i, arr in enumerate(arrays):
        for cid in arr.charm_ids:
            array_of.setdefault(cid, i)      # first Array wins (reuse is flagged elsewhere)
    loose = 0
    grouped: dict[int, list[str]] = {}
    for cid in charm_ids:
        if cid not in ruleset.charms:
            continue
        if cid in array_of:
            grouped.setdefault(array_of[cid], []).append(cid)
        else:
            loose += ruleset.charms[cid].installation_cost
    return loose + sum(array_installation_motes(ruleset, ids)
                       for ids in grouped.values())


# --------------------------------------------------------------------------- #
# Ox-Body Technique (repeatable Charm)
# --------------------------------------------------------------------------- #

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


# --------------------------------------------------------------------------- #
# Deadly Beastman Transformation Gifts (repeatable, multi-pick-per-purchase Charm)
# --------------------------------------------------------------------------- #

def gift_purchase_cap(ruleset: RuleSet, character: Character) -> int:
    """Max purchases of the splat's Gift-granting Charm: Character.essence_rating
    for Deadly Beastman Transformation ("no more times than he has points of
    Essence", p.124). 0 if the splat has no such Charm."""
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


# --------------------------------------------------------------------------- #
# Chargen (not yet implemented — see module docstring)
# --------------------------------------------------------------------------- #

def _caste_favored(ruleset: RuleSet, character: Character) -> tuple[set, set] | None:
    """(caste_abilities, favored_abilities) as sets, or None if the caste is not
    in the RuleSet (caller emits an issue and skips caste-dependent checks). For a
    Lunar caste (caste_attributes set, caste_abilities empty — p.90), the caste
    contributes no Ability discount here; its discount is Attribute-keyed and
    handled separately by `_caste_favored_attribute_category`."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return None
    return set(caste_def.caste_abilities), set(character.favored_abilities)


def _attribute_category(attr: AttributeName) -> str | None:
    """Which of Physical/Social/Mental `attr` belongs to (the reverse lookup of
    ATTRIBUTE_CATEGORIES)."""
    for cat, attrs in ATTRIBUTE_CATEGORIES.items():
        if attr in attrs:
            return cat
    return None


def _caste_favored_attribute_category(ruleset: RuleSet, character: Character) -> str | None:
    """The Attribute category (Physical/Social/Mental) a Lunar's caste favors, or
    None for a caste with no Caste Attributes (every non-Lunar caste, and the
    Lunar Casteless caste, p.108). Full Moon/Changing Moon/No Moon's three Caste
    Attributes are always exactly one whole ATTRIBUTE_CATEGORIES group (p.90-91),
    so the category of any one of them is the caste's favored category."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None or not caste_def.caste_attributes:
        return None
    return _attribute_category(caste_def.caste_attributes[0])


def _caste_favored_attribute_sets(ruleset: RuleSet, character: Character
                                   ) -> tuple[set, set, set]:
    """(caste, favored, remaining) Attribute sets for a caste_favored-mode splat
    (Alchemical, p.60), partitioning all nine Attributes disjointly. Caste
    Attributes come from the caste; Favored are the player's chosen ones with any
    that also happen to be Caste removed (that overlap is illegal and flagged
    separately, but the accounting must not double-count); remaining is everything
    else. An unknown caste yields an empty caste set (validate emits unknown-caste)."""
    caste_def = ruleset.castes.get(character.caste)
    caste = set(caste_def.caste_attributes) if caste_def else set()
    favored = set(character.favored_attributes) - caste
    remaining = set(AttributeName) - caste - favored
    return caste, favored, remaining


def _attr_bp_caste_favored(ruleset: RuleSet, character: Character, b, bp_costs,
                            attributes: dict) -> int:
    """Bonus points spent on Attributes under caste_favored mode: the three pools
    are assigned in FIXED order to the caste / favored / remaining sets, over-spend
    on the caste and favored sets is charged the discounted
    `attribute_caste_favored` rate, and the remaining set the flat `attribute` rate."""
    caste, favored, remaining = _caste_favored_attribute_sets(ruleset, character)
    pools = list(b.attribute_pools)

    def spend(group: set) -> int:
        return sum(attributes.get(a, b.attribute_base) - b.attribute_base for a in group)

    cf_rate = bp_costs.attribute_caste_favored
    return (max(0, spend(caste) - pools[0]) * cf_rate
            + max(0, spend(favored) - pools[1]) * cf_rate
            + max(0, spend(remaining) - pools[2]) * bp_costs.attribute)


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


def caste_attributes(ruleset: RuleSet, character: Character) -> set[AttributeName]:
    """The character's Caste Attributes (Lunar, p.90-91), or an empty set for a
    caste with none (every non-Lunar caste and the Lunar Casteless caste). This is
    the set that earns the Caste-Attribute XP/BP discount, the Attribute parallel
    to `caste_favored_abilities`."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None:
        return set()
    return set(caste_def.caste_attributes)


def _caste_favored_attr_names(ruleset: RuleSet, character: Character) -> set:
    """The set of AttributeName a caste_favored-mode splat (Alchemical) counts as
    Caste-or-Favored for the purpose of Charm keying — the caste's Caste Attributes
    plus the player's Favored Attributes. Empty for category-mode splats (Lunar/
    Solar/...), which is also the discriminator: a non-empty set means caste_favored
    mode, so a Charm's Caste/Favored-ness is a SPECIFIC-attribute match rather than
    the category match category-mode splats use."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    if b.attribute_mode != "caste_favored":
        return set()
    caste_def = ruleset.castes.get(character.caste)
    caste = set(caste_def.caste_attributes) if caste_def else set()
    return caste | set(character.favored_attributes)


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
    install_motes = _installation_motes(ruleset, charms, arrays)
    if ob_charm is not None:
        install_motes += ob_charm.installation_cost * len(ox_body)
    return installed, noncf, install_motes


def caste_favored_abilities(ruleset: RuleSet, character: Character) -> set[AbilityName]:
    """The character's Caste ∪ Favoured abilities — the set that earns the discount
    on Ability/Charm/spell costs. Falls back to just the Favoured set if the caste
    is unknown to the RuleSet. Shared by chargen and XP costing."""
    cf = _caste_favored(ruleset, character)
    if cf is None:
        return set(character.favored_abilities)
    caste_abilities, favored = cf
    return caste_abilities | favored


class BonusPointLine(BaseModel):
    """One domain's bonus-point spend, for the chargen BP-spend log."""
    domain: str
    points: int


class BonusPointBreakdown(BaseModel):
    """Per-domain bonus-point accounting for the creation allocation. `lines` are
    in display order (every domain present, even at 0); `total` is their sum;
    `available` is the budget (15 by default)."""
    lines: list[BonusPointLine]
    total: int
    available: int

    @property
    def over_budget(self) -> bool:
        return self.total > self.available


def _chargen_source(character: Character):
    """The traits chargen accounting reads: the frozen snapshot once locked, else
    the current (pre-lock) traits. Returned as a flat tuple in a fixed order."""
    snap = character.chargen_snapshot
    return (
        snap.attributes if snap else character.attributes,
        snap.abilities if snap else character.abilities,
        snap.crafts if snap else character.crafts,
        snap.virtues if snap else character.virtues,
        snap.backgrounds if snap else character.backgrounds,
        snap.specialties if snap else character.specialties,
        snap.charms if snap else character.charms,
        snap.spells if snap else character.spells,
        snap.combos if snap else character.combos,
        snap.ox_body if snap else character.ox_body,
        snap.essence_rating if snap else character.essence_rating,
        snap.willpower_purchased if snap else character.willpower_purchased,
        snap.beastman_gifts if snap else character.beastman_gifts,
        snap.arrays if snap else character.arrays,
        snap.submodules if snap else character.submodules,
        snap.colleges if snap else character.colleges,
        (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character),
    )


def bonus_point_breakdown(ruleset: RuleSet, character: Character) -> BonusPointBreakdown:
    """Compute the bonus points spent in each chargen domain (Exalted 1e pp.104-105).

    The engine computes the accounting; the player does not tag dots. For each
    domain, dots beyond the free budget — or above the pre-bonus cap of 3 — are
    paid from the 15 bonus points at the rates in RuleSet.bonus_costs. Where a
    domain mixes cheap (Caste/Favoured) and dear dots, the *free* dots are assigned
    to the dearest first, the player-favourable minimum. This is the single source
    of the BP totals; validate_chargen consumes it for the ceiling check, and the
    editor renders it as a spend log.
    """
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin, character.upbringing)
    (attributes, abilities, crafts, virtues, backgrounds, specialties,
     charms, spells, combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, submodules, colleges, thaumaturgy) = _chargen_source(character)

    cf = _caste_favored(ruleset, character)
    cf_set = (cf[0] | cf[1]) if cf is not None else set()
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)
    picks = chargen_charm_picks(ruleset, character)

    # --- Attributes ----------------------------------------------------------- #
    # caste_favored mode (Alchemical, p.60): pools go to the caste / favored /
    # remaining Attribute SETS, not to categories — see _attr_bp_caste_favored.
    if b.attribute_mode == "caste_favored":
        attr_bp = _attr_bp_caste_favored(ruleset, character, b, bp_costs, attributes)
    else:
        # category mode (every other splat): three category spends matched to the
        # 8/6/4 pools. The pool assignment (which category gets which of the sorted
        # pools) is by spend alone; the per-category RATE additionally depends on
        # whether that category is the caste's favored one (Lunar Caste Attributes,
        # p.93 — "4, 3 if a Caste Attribute"). Ability-caste splats have no favored
        # category (caste_attr_category is None), so every category costs the same
        # flat `attribute` rate.
        cat_spends = sorted(
            ((cat, sum(attributes[a] - b.attribute_base for a in attrs))
             for cat, attrs in ATTRIBUTE_CATEGORIES.items()),
            key=lambda cs: cs[1], reverse=True,
        )
        pools = sorted(b.attribute_pools, reverse=True)
        attr_bp = sum(
            max(0, spend - pool) * (bp_costs.attribute_caste_favored if cat == caste_attr_category
                                     else bp_costs.attribute)
            for (cat, spend), pool in zip(cat_spends, pools)
        )

    # --- Abilities: 25 free dots, pre-BP cap 3 -------------------------------- #
    # Four rate tiers, because a Calling (Cult of the Illuminated, p.90) is a discount
    # axis that STACKS with Caste/Favoured rather than replacing it:
    #   both      1 BP per `calling_ability_favored_caste_dots_per_point` dots (0.5/dot)
    #   cf only   bp_costs.ability_favored_caste                              (1/dot)
    #   calling   bp_costs.calling_ability                                    (1/dot)
    #   neither   bp_costs.ability                                            (2/dot)
    # With no Calling the two Calling tiers stay empty and this reduces exactly to the
    # previous two-tier arithmetic, so every other splat is unaffected.
    cap = b.ability_cap_pre_bp
    call_set = calling_abilities(ruleset, character)
    per_point = max(1, bp_costs.calling_ability_favored_caste_dots_per_point)

    def _tier(ab) -> str:
        cf, call = ab in cf_set, ab in call_set
        return "both" if (cf and call) else "cf" if cf else "calling" if call else "neither"

    within_by_tier = {"both": 0, "cf": 0, "calling": 0, "neither": 0}
    above_by_tier = dict(within_by_tier)
    for ab, rating in _ability_slots(abilities, crafts):
        tier = _tier(ab)
        within_by_tier[tier] += min(rating, cap)
        above_by_tier[tier] += max(0, rating - cap)

    # Overflow past the free pool is paid cheapest-first (player-favourable), by
    # EFFECTIVE per-dot rate, so the fractional 'both' tier is spent first.
    flat_rate = {"cf": bp_costs.ability_favored_caste,
                 "calling": bp_costs.calling_ability,
                 "neither": bp_costs.ability}
    order = sorted(("cf", "calling", "neither"), key=lambda t: flat_rate[t])
    total_within = sum(within_by_tier.values())
    overflow = max(0, total_within - b.ability_dots)

    paid = dict(above_by_tier)                # above-cap dots always cost BP
    remaining = overflow
    for tier in ["both"] + order:             # 'both' is 0.5/dot, cheapest of all
        take = min(remaining, within_by_tier[tier])
        paid[tier] += take
        remaining -= take
        if not remaining:
            break

    # The 'both' tier is charged in bulk and rounds UP, matching how specialties
    # already handle a dots-per-point rate (rules-authority call: the page does not
    # say how an odd dot rounds).
    ability_bp = ((paid["both"] + per_point - 1) // per_point
                  + sum(paid[t] * flat_rate[t] for t in order))

    # --- Backgrounds: N free dots, pre-BP cap 3 (above-3 dot costs 2) --------- #
    # `background_rules` (empty for every splat but the Alchemical) can exempt a
    # Background from the cap and make its upper dots cost more than one pool dot each.
    bg_within = bg_above_bp = 0
    for bg in backgrounds:
        rule = background_rule(b, bg.name)
        cap = bg.rating if (rule and rule.cap_pre_bp_exempt) else b.background_cap_pre_bp
        bg_within += background_pool_dots(rule, min(bg.rating, cap))
        above = max(0, bg.rating - cap)
        # A per-Background bonus-point surcharge rides on top of the above-cap rate
        # (Lookshy Breeding, p.66). Dots at or below the cap pay their half of the
        # same surcharge through the pool, via background_pool_dots.
        rate = bp_costs.background_above_3 + (rule.bp_surcharge_per_dot if rule else 0)
        bg_above_bp += above * rate
    bg_overflow = max(0, bg_within - b.background_dots)
    bg_bp = bg_above_bp + bg_overflow * bp_costs.background

    # --- Virtues: 5 free dots over base 1, pre-BP cap 3 ----------------------- #
    v_within = v_above = 0
    for v, rating in virtues.items():
        v_within += max(0, min(rating, b.virtue_cap_pre_bp) - b.virtue_base)
        v_above += max(0, rating - b.virtue_cap_pre_bp)
    v_overflow = max(0, v_within - b.virtue_dots)
    virtue_bp = (v_above + v_overflow) * bp_costs.virtue

    # --- Charms & Spells ------------------------------------------------------ #
    if uses_charm_slots(ruleset, character):
        # Slot economy (Alchemical, p.88-89): you buy SLOTS, not Charm picks — each
        # Slot comes with a free Charm. BP is the cost of slots beyond the free base:
        # extra General slots at bp_costs.charm (6), extra Dedicated at
        # charm_favored_caste (5). The Charms themselves are free.
        g, d, bg, bd = charm_slot_counts(ruleset, character)
        charm_bp = (max(0, g - bg) * bp_costs.charm
                    + max(0, d - bd) * bp_costs.charm_favored_caste)
    else:
        # Per-pick economy (every other splat): one shared Charm/Spell pool (p.100).
        # The Immaculate martial-arts path (DB, p.151) swaps the free pool size and
        # the per-Charm BP row: 5 Immaculate Charms free (vs charm_count), each
        # Immaculate Charm priced from the Immaculate BP row (10/7).
        immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
        free_charm_pool = b.immaculate_charm_count if immaculate else b.charm_count
        occult_cf = AbilityName.OCCULT in cf_set
        # One ladder for every pick, whichever list it lives on — see
        # `charm_pick_bp_costs`. Spells share the pool but are not Charms.
        pick_costs = charm_pick_bp_costs(ruleset, character, picks)
        for sid in spells:
            if ruleset.spells.get(sid) is None:
                continue
            pick_costs.append(bp_costs.charm_favored_caste if occult_cf else bp_costs.charm)
        pick_costs.sort(reverse=True)                # free pool absorbs the dearest picks
        charm_bp = sum(pick_costs[free_charm_pool:])

    # --- Combos: BP = its number of Charms (p.213) --------------------------- #
    combo_bp = sum(len(combo.charm_ids) for combo in combos)

    # --- Arrays: BP = its number of Charms (Alchemical, p.89) ---------------- #
    array_bp = sum(len(array.charm_ids) for array in arrays)

    # --- Submodules: each priced at its own bp_cost (Alchemical, p.89) ------- #
    submodule_bp = sum(
        (d.bp_cost for d in (submodule_def(ruleset, s.charm_id, s.key) for s in submodules)
         if d is not None), 0)

    # --- Specialties: 1 BP/dot; Caste/Favoured get N dots per BP (p.105) ------ #
    cf_spec_dots = sum(s.rating for s in specialties if s.ability in cf_set)
    other_spec_dots = sum(s.rating for s in specialties if s.ability not in cf_set)
    per_point = bp_costs.specialty_favored_caste_dots_per_point
    spec_bp = other_spec_dots * bp_costs.specialty + (cf_spec_dots + per_point - 1) // per_point

    # --- Astrological Colleges (Sidereal): own pool, pre-BP cap 3 ------------- #
    # Same shape as Abilities: own-Maiden Colleges are the cheap dots (6), other
    # houses the dear (8); the free pool absorbs the dearest first, so overflow is
    # paid cheapest-first (player-favourable). Above-cap dots always cost BP.
    college_cap = b.college_cap_pre_bp
    col_cheap_within = col_dear_within = col_above_bp = 0
    for cr in colleges:
        college = ruleset.colleges.get(cr.college_id)
        own = college is not None and college.house == character.caste
        within = min(cr.rating, college_cap)
        above = max(0, cr.rating - college_cap)
        col_above_bp += above * (bp_costs.college_own_house if own else bp_costs.college)
        if own:
            col_cheap_within += within
        else:
            col_dear_within += within
    col_overflow = max(0, (col_cheap_within + col_dear_within) - b.college_dots)
    col_overflow_cheap = min(col_overflow, col_cheap_within)
    college_bp = (col_above_bp
                  + col_overflow_cheap * bp_costs.college_own_house
                  + (col_overflow - col_overflow_cheap) * bp_costs.college)

    # --- Thaumaturgy: every purchase priced individually, no free pool -------- #
    # Unlike every domain above, thaumaturgy has no chargen allowance: "Thaumaturges
    # may spend their bonus points on any combination of these without limitation"
    # (p.113). So the total is simply the sum of the purchase prices — the free-pool
    # arithmetic that shapes the other domains has nothing to absorb here. Sciences
    # price at 0 because the source gives no rate; see ThaumPurchase.priced.
    thaum_bp = sum(thaum_purchase_bp_costs(
        ruleset, character, _thaum_purchases_from(ruleset, thaumaturgy)))

    # --- Willpower / Essence -------------------------------------------------- #
    wp_bp = wp_purchased * bp_costs.willpower
    essence_bp = max(0, essence - b.essence_start) * bp_costs.essence

    lines = [
        BonusPointLine(domain="Attributes", points=attr_bp),
        BonusPointLine(domain="Abilities", points=ability_bp),
        BonusPointLine(domain="Backgrounds", points=bg_bp),
        BonusPointLine(domain="Virtues", points=virtue_bp),
        BonusPointLine(domain="Charms & Spells", points=charm_bp),
        BonusPointLine(domain="Combos", points=combo_bp),
    ]
    # Arrays are an Alchemical-only domain (p.89); show the line only for splats
    # that build them, so every other splat's breakdown is unchanged. array_bp is 0
    # whenever the line is omitted (no arrays), so the total is unaffected either way.
    if array_bp or submodule_bp or uses_charm_slots(ruleset, character):
        lines.append(BonusPointLine(domain="Arrays", points=array_bp))
        lines.append(BonusPointLine(domain="Submodules", points=submodule_bp))
    lines += [
        BonusPointLine(domain="Specialties", points=spec_bp),
        BonusPointLine(domain="Willpower", points=wp_bp),
        BonusPointLine(domain="Essence", points=essence_bp),
    ]
    # Colleges only exist for splats that ship them (Sidereal) — omit the line
    # entirely otherwise so every other splat's breakdown is unchanged.
    if b.college_dots > 0 or colleges:
        lines.insert(3, BonusPointLine(domain="Colleges", points=college_bp))
    # Thaumaturgy is cross-splat but optional for every splat, so the line appears
    # only once a character has bought something — a Solar who never touches it sees
    # the same breakdown as before. thaum_bp is 0 whenever the line is omitted.
    if thaumaturgy.arts or thaumaturgy.art_specialties or thaumaturgy.sciences \
            or thaumaturgy.rituals or thaumaturgy.formulas:
        lines.append(BonusPointLine(domain="Thaumaturgy", points=thaum_bp))
    total = sum(line.points for line in lines)
    return BonusPointBreakdown(lines=lines, total=total, available=b.bonus_points)


def validate_chargen(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Chargen budget predicates and bonus-point reconciliation (Exalted 1e core,
    pp.104-105). Validates the creation allocation: current traits pre-lock, or
    the frozen ChargenSnapshot once locked.

    The per-domain bonus-point arithmetic lives in `bonus_point_breakdown`; this
    function adds the legality predicates (ranges, Caste/Favoured minimums, the
    Willpower start-cap, the Charm/Spell Caste-Favoured minimum) and the final
    budget-ceiling check. One known simplification, flagged for the rules
    authority: the "10 of 25 Ability dots / 5 of 10 Charms must be Caste or
    Favoured" rules are checked as necessary conditions rather than jointly
    optimised with the free-dot assignment; the two only interact in rare
    over-spent builds.
    """
    issues: list[Issue] = []
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    (attributes, abilities, crafts, virtues, backgrounds, _specialties,
     charms, spells, _combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, _submodules, colleges, thaumaturgy) = _chargen_source(character)

    # Backgrounds that carry mechanics (Alchemical Class/Backing, CH2 p.65-69). No-op
    # for every splat whose Backgrounds are purely narrative.
    issues += background_issues(b, backgrounds)

    # Thaumaturgy: Occult gates on Arts, aspects and rituals; per-Science ceilings.
    # No-op for a character who has bought none, which is every character until the
    # feature is used.
    issues += thaumaturgy_issues(ruleset, character, thaumaturgy)

    cf = _caste_favored(ruleset, character)
    if cf is None:
        issues.append(Issue(
            code="unknown-caste", where=str(character.caste),
            message=f"Caste {character.caste} is not in the RuleSet; "
                    "caste/favoured checks skipped.",
        ))
        caste_abilities, favored = set(), set()
    else:
        caste_abilities, favored = cf
        # Favoured: exactly favored_count, all distinct from Caste, >=1 dot each.
        if len(favored) != b.favored_count:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {b.favored_count} Favoured abilities, "
                        f"found {len(favored)}.",
            ))
        overlap = favored & caste_abilities
        if overlap:
            issues.append(Issue(
                code="favored-overlaps-caste",
                message="Favoured abilities may not be Caste abilities: "
                        f"{sorted(a.value for a in overlap)}.",
            ))
        for ab in sorted(favored, key=lambda a: a.value):
            if abilities.get(ab, 0) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))
        # Abilities the origin/splat forces into the Favored set — Lunar Survival
        # (p.90); empty for splats with no such rule.
        for ab in b.required_favored:
            if ab not in favored:
                issues.append(Issue(
                    code="required-favored-ability", where=ab.value,
                    message=f"{ab.value} must be a Favored Ability for this splat.",
                ))

    cf_set = caste_abilities | favored
    caste_attr_category = _caste_favored_attribute_category(ruleset, character)

    # --- Range checks --------------------------------------------------------- #
    for name, attr in attributes.items():
        if not (b.attribute_base <= attr <= 5):
            issues.append(Issue(
                code="attribute-range", where=name.value,
                message=f"Attribute {name.value} = {attr}; must be {b.attribute_base}-5 at creation.",
            ))

    # --- caste_favored attribute legality (Alchemical, p.60) ------------------ #
    # The three attribute pools go to disjoint SETS: 3 Caste Attributes, 3 chosen
    # Favored Attributes (distinct from Caste), and the rest. Each Caste Attribute
    # must reach attribute_caste_min ("none may have a rating lower than 2").
    if b.attribute_mode == "caste_favored":
        caste_def = ruleset.castes.get(character.caste)
        caste_attrs = set(caste_def.caste_attributes) if caste_def else set()
        fav_attrs = character.favored_attributes
        if len(set(fav_attrs)) != b.attribute_favored_count:
            issues.append(Issue(
                code="favored-attribute-count",
                message=f"Expected {b.attribute_favored_count} Favored Attributes, "
                        f"found {len(set(fav_attrs))}.",
            ))
        overlap = set(fav_attrs) & caste_attrs
        if overlap:
            issues.append(Issue(
                code="favored-attribute-overlaps-caste",
                message="Favored Attributes may not be Caste Attributes: "
                        f"{sorted(a.value for a in overlap)}.",
            ))
        for a in sorted(caste_attrs, key=lambda x: x.value):
            if attributes.get(a, 0) < b.attribute_caste_min:
                issues.append(Issue(
                    code="caste-attribute-min", where=a.value,
                    message=f"Caste Attribute {a.value} = {attributes.get(a, 0)}; "
                            f"must be at least {b.attribute_caste_min} at creation.",
                ))
    cheap_within = 0
    for ab, rating in _ability_slots(abilities, crafts):
        if not (0 <= rating <= 5):
            issues.append(Issue(
                code="ability-range", where=ab.value,
                message=f"Ability {ab.value} = {rating}; must be 0-5 at creation.",
            ))
        if ab in cf_set:
            cheap_within += min(rating, b.ability_cap_pre_bp)
    if cheap_within < b.ability_min_caste_favored:
        issues.append(Issue(
            code="ability-caste-favored-min",
            message=f"At least {b.ability_min_caste_favored} of the {b.ability_dots} "
                    f"Ability dots must be Caste/Favoured; only {cheap_within} are.",
        ))
    # Required minimum Abilities — the Dragon-Blooded Dynastic schooling floor
    # (p.151) and the Sidereal per-house floor (p.98). Each requirement is satisfied
    # by any one of its listed Abilities; the budget's (exalt-type-keyed) list is
    # unioned with the caste's own (the Sidereal per-house minimums live on the caste
    # because they differ per house, unlike the DB floor which is aspect-agnostic).
    # A ronin Sidereal keeps a Caste but "has no minimum required Ability scores"
    # (p.100), so that origin suppresses the caste half outright.
    caste_def = ruleset.castes.get(character.caste)
    caste_min = ([] if b.ignore_caste_min_abilities
                 else (caste_def.required_min_abilities if caste_def else []))
    # The training camp's regimen floors (Cult of the Illuminated, p.89) join the
    # union on the same terms as the caste's.
    camp_min = [] if b.ignore_caste_min_abilities else camp_min_abilities(ruleset, character)
    for req in list(b.required_min_abilities) + list(caste_min) + list(camp_min):
        best = max((abilities.get(ab, 0) for ab in req.abilities), default=0)
        if best < req.rating:
            names = " or ".join(a.value for a in req.abilities)
            issues.append(Issue(
                code="required-min-ability", where=names,
                message=f"This origin requires at least {req.rating} dot(s) in {names}; "
                        f"has {best}.",
            ))
    for v, rating in virtues.items():
        if not (b.virtue_base <= rating <= 5):
            issues.append(Issue(
                code="virtue-range", where=v.value,
                message=f"Virtue {v.value} = {rating}; must be {b.virtue_base}-5 at creation.",
            ))

    # --- Astrological Colleges (Sidereal, p.98) ------------------------------- #
    # Reference integrity + range + the "at least N dots in the Colleges of his
    # Maiden" floor. Over-budget/over-cap dots are paid from bonus points (see
    # bonus_point_breakdown), so there is no hard total cap here — same as Backgrounds.
    own_house_dots = 0
    for cr in colleges:
        college = ruleset.colleges.get(cr.college_id)
        if college is None:
            issues.append(Issue(
                code="unknown-college", where=cr.college_id,
                message=f"College {cr.college_id} is not in the RuleSet.",
            ))
            continue
        if not (0 <= cr.rating <= 5):
            issues.append(Issue(
                code="college-range", where=cr.college_id,
                message=f"College {college.name} = {cr.rating}; must be 0-5 at creation.",
            ))
        if college.house == character.caste:
            own_house_dots += cr.rating
    if own_house_dots < b.college_min_own_house:
        issues.append(Issue(
            code="college-own-house-min",
            message=f"At least {b.college_min_own_house} College dots must be in the "
                    f"character's Maiden's Colleges; only {own_house_dots} are.",
        ))

    # --- Charms & Spells ------------------------------------------------------ #
    # The top spell circle is barred at creation for every splat; the Charm legality
    # then splits by economy — the Alchemical Charm Slot rules (p.88-89) or the
    # per-pick Caste/Favoured minimum / Immaculate single-tree rule (every other
    # splat).
    barred = chargen_barred_circle(ruleset, character)
    for sid in spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        if barred is not None and spell.circle == barred:
            issues.append(Issue(
                code="spell-top-circle-chargen", where=sid,
                message=f"{spell.name}: {spell.circle.value} Circle spells may not "
                        "be taken at character creation.",
            ))

    caste_fav_attrs = _caste_favored_attr_names(ruleset, character)
    if uses_charm_slots(ruleset, character):
        # Alchemical Charm Slots (p.88-89): every installed Charm occupies a Slot.
        # non-Caste/Favored Charms may only sit in General Slots; the total installed
        # can't exceed the total Slots; and the committed installation motes can't
        # exceed the Personal Essence pool (p.62 — the Charms must all fit).
        g, d, _bg, _bd = charm_slot_counts(ruleset, character)
        installed, noncf, install_motes = charm_slot_usage(ruleset, character)
        if installed > g + d:
            issues.append(Issue(
                code="charm-exceeds-slots",
                message=f"{installed} Charms installed but only {g + d} Charm Slots "
                        f"({g} General + {d} Dedicated); buy more Slots or install fewer.",
            ))
        if noncf > g:
            issues.append(Issue(
                code="charm-noncf-exceeds-general-slots",
                message=f"{noncf} non-Caste/Favored Charms need General Slots, but only "
                        f"{g} exist; Dedicated Slots hold only Caste/Favored-Attribute Charms.",
            ))
        personal, _peripheral = derive.essence_pools(ruleset, character)
        if install_motes > personal:
            issues.append(Issue(
                code="charm-installation-over-personal",
                message=f"Installed Charms commit {install_motes} motes, but Personal "
                        f"Essence is only {personal}; they will not all fit.",
            ))
    else:
        # Per-pick path. Standard: >=charm_min_caste_favored of the picks are
        # Caste/Favoured. Immaculate (DB, p.151, triggered by any Immaculate Order
        # Charm): all chargen Charms must instead be one elemental tree, minimum waived.
        immaculate = _immaculate_path(ruleset, charms, character.exalt_type)
        # Lookshy, p.68: an origin may forbid the Immaculate path outright at creation.
        # Checked before the path itself, so the character gets the "you may not take
        # these" message rather than the single-elemental-tree one they cannot satisfy.
        if b.bar_immaculate_charms_at_chargen:
            barred = [cid for cid in charms
                      if (c := ruleset.charms.get(cid)) is not None and c.immaculate]
            if barred:
                immaculate = False
                issues.append(Issue(
                    code="charm-immaculate-barred-at-chargen",
                    message=(f"{len(barred)} Immaculate Order Charm(s) taken, but this "
                             "origin may not learn the Immaculate Martial Arts before "
                             "play begins (p.68); they may be bought with experience."),
                ))
        occult_cf = AbilityName.OCCULT in cf_set
        # Same enumeration the pricing reads, so a repeatable or granted list can never
        # again be counted by one of the two and missed by the other.
        cf_pick_count = sum(
            1 for p in chargen_charm_picks(ruleset, character)
            if p.counts_toward_pool and p.caste_favored
            and ruleset.charms.get(p.charm_id) is not None
        )
        if occult_cf:
            cf_pick_count += sum(1 for sid in spells if ruleset.spells.get(sid) is not None)

        if immaculate:
            # Every chargen Charm must be an Immaculate Charm of one shared element;
            # spells, Ox-Body, and ordinary ability Charms are not part of any tree.
            # The Immaculate "Enlightenment" Charms (Spirit Sight / Spirit Walking) ARE
            # part of Immaculate martial arts — the required entry to ANY Dragon Path
            # (DB p241-242) — so they're permitted alongside the single elemental tree.
            # They are NOT exempt from the budget: each still costs a normal Charm pick
            # (priced above), only the single-tree check tolerates them.
            trees: set[str] = set()
            impure = bool(spells) or bool(ox_body) or bool(beastman_gifts)
            for cid in charms:
                charm = ruleset.charms.get(cid)
                if charm is None:
                    continue
                if charm.category == "martial_arts:enlightenment":
                    continue
                if charm.immaculate and charm.element:
                    trees.add(charm.element)
                else:
                    impure = True
            if impure or len(trees) > 1:
                detail = f" ({'/'.join(sorted(trees))})" if len(trees) > 1 else ""
                issues.append(Issue(
                    code="immaculate-single-tree",
                    message=("An Immaculate martial artist must take all chargen Charms "
                             f"from a single elemental tree{detail}; mixing trees, spells, "
                             "Ox-Body, or non-Immaculate Charms is not allowed on the "
                             "Immaculate path (p.151)."),
                ))
        elif cf_pick_count < b.charm_min_caste_favored:
            issues.append(Issue(
                code="charm-caste-favored-min",
                message=f"At least {b.charm_min_caste_favored} of the {b.charm_count} "
                        f"Charms/Spells must be Caste/Favoured; only {cf_pick_count} "
                        "resolve as such.",
            ))

    # --- Sidereal Martial Arts form cap (p.101) ------------------------------ #
    # "no more than 3 [chargen Charms] may be from a Sidereal Martial Arts form;
    # ronin ... none". A "form" is a supernatural SMA style — a martial_arts Charm
    # that is open_to_tiers (Celestial-open); the Violet Bier auspicious tree is not
    # open_to_tiers and is uncapped. None on every other splat = no cap.
    if b.martial_arts_form_charm_cap is not None:
        n_form = sum(
            1 for cid in charms
            if (c := ruleset.charms.get(cid)) is not None
            and c.category.startswith("martial_arts") and c.open_to_tiers)
        if n_form > b.martial_arts_form_charm_cap:
            cap = b.martial_arts_form_charm_cap
            issues.append(Issue(
                code="charm-too-many-martial-arts-forms",
                message=(f"{n_form} Charms are from a Sidereal Martial Arts form; at "
                         f"chargen no more than {cap} may be" +
                         (" (a ronin may take none, p.101)." if cap == 0
                          else f" from such forms (p.101).")),
            ))

    # --- Willpower start-cap -------------------------------------------------- #
    wp_total = derive.two_highest_virtues(virtues) + wp_purchased
    if wp_total > b.willpower_start_cap:
        high_virtues = sum(1 for r in virtues.values() if r >= b.willpower_cap_exception_virtue)
        if high_virtues < b.willpower_cap_exception_count:
            issues.append(Issue(
                code="willpower-start-cap",
                message=(f"Willpower starts at {wp_total}; may not exceed "
                         f"{b.willpower_start_cap} unless at least "
                         f"{b.willpower_cap_exception_count} Virtues are "
                         f">= {b.willpower_cap_exception_virtue}."),
            ))

    # --- Essence -------------------------------------------------------------- #
    if essence < b.essence_start:
        issues.append(Issue(
            code="essence-below-start",
            message=f"Essence {essence} is below the starting {b.essence_start}.",
        ))
    # A hard ceiling AFTER bonus points, where an origin sets one: the Illuminated
    # Solar starts at 3 and may buy higher, but "under no circumstances" begins at 6+
    # (p.90). 0 = no ceiling, which is every other splat.
    if b.essence_start_cap and essence > b.essence_start_cap:
        issues.append(Issue(
            code="essence-above-chargen-cap",
            message=f"Essence {essence} exceeds the creation ceiling of "
                    f"{b.essence_start_cap} for this origin.",
        ))

    issues.extend(check_camp_and_calling(ruleset, character))
    issues.extend(granted_charm_issues(ruleset, character))

    # --- Bonus-point ceiling (numbers from bonus_point_breakdown) ------------- #
    breakdown = bonus_point_breakdown(ruleset, character)
    if breakdown.over_budget:
        issues.append(Issue(
            code="bonus-points-exceeded",
            message=f"Spends {breakdown.total} bonus points; only {breakdown.available} available.",
        ))
    issues.append(Issue(
        code="bonus-points", severity="info",
        message=f"{breakdown.total} of {breakdown.available} bonus points spent.",
    ))
    return issues


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #

def check_exalt_type(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The character's exalt_type must be a known ExaltDefinition. An unknown type
    still derives (essence pools fall back to Solar) but is surfaced here so a
    hand-edited or mis-migrated save is flagged rather than silently mis-priced."""
    if character.exalt_type in ruleset.exalts:
        return []
    return [Issue(
        code="exalt-type-unknown", where=character.exalt_type,
        message=f"Exalt type {character.exalt_type!r} is not defined in the rule set.",
    )]


def check_caste_splat(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The character's caste must belong to the character's own Exalt type — a
    Solar can't be a Dragon-Blooded Aspect and vice versa. An unknown caste is left
    to validate_chargen's 'unknown-caste' finding, so this doesn't double-report."""
    caste_def = ruleset.castes.get(character.caste)
    if caste_def is None or caste_def.exalt_type == character.exalt_type:
        return []
    return [Issue(
        code="caste-wrong-splat", where=character.caste,
        message=f"Caste {caste_def.label!r} belongs to {caste_def.exalt_type}, "
                f"not the character's Exalt type {character.exalt_type!r}.",
    )]


# Lunar Casteless (p.90-91, p.108): unlike Dragon-Blooded Dynastic/Outcaste — an
# origin variant orthogonal to caste — Lunar Casteless is a single condition
# expressed on BOTH fields at once (no Caste Attributes, only 6 Charms, no
# Ability minimums, no Renown). The two must move together: Casteless origin iff
# the Casteless caste, never one without the other.
LUNAR_CASTELESS_CASTE_ID = "casteless"
LUNAR_CASTELESS_ORIGIN = "casteless"


def check_lunar_casteless_consistency(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A Lunar's origin and caste must agree on Casteless-ness. Not gated on caste
    lookup succeeding — an unrecognised caste is `check_caste_splat`'s concern."""
    if character.exalt_type != "Lunar":
        return []
    is_casteless_caste = character.caste == LUNAR_CASTELESS_CASTE_ID
    is_casteless_origin = character.origin == LUNAR_CASTELESS_ORIGIN
    if is_casteless_caste == is_casteless_origin:
        return []
    return [Issue(
        code="lunar-casteless-mismatch", where=character.caste,
        message=("A Lunar's Casteless origin and Casteless caste must match: "
                 f"caste={character.caste!r}, origin={character.origin!r}."),
    )]


def splat_of(charm: Charm) -> str:
    """The Exalt type that can learn `charm` (charm.exalt_type). A tiny accessor so
    the UI/engine don't reach into the field directly and can grow smarter later
    (e.g. cross-splat Martial Arts / sorcery) without a churn of call sites."""
    return charm.exalt_type


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
    given; without one the call degrades to the splat/`open_to_all` answer."""
    if charm.open_to_all or splat_of(charm) == character.exalt_type:
        return True
    if ruleset is not None and charm.open_to_tiers:
        if ruleset.exalt_for(character.exalt_type).tier in charm.open_to_tiers:
            return True
        # Perfected Lotus Matrix (CH3 p.100): an Alchemical with it installed learns
        # Terrestrial/Celestial Martial Arts Charms "in the same manner as any other
        # Celestial Exalted type", so a Celestial-tier MA style becomes available.
        if (is_martial_arts_charm(charm) and "Celestial" in charm.open_to_tiers
                and has_perfected_lotus_matrix(character)):
            return True
    return False


PERFECTED_LOTUS_MATRIX_ID = "alchemical.close-combat.perfected-lotus-matrix"


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


def foreign_charms_open(ruleset: RuleSet, character: Character) -> bool:
    """Whether the character may learn other splats' Charms *right now*. The caste
    must allow it (p.127), and — before the sheet is locked — the Storyteller must
    have permitted it: "Eclipse Caste characters may not start the game knowing the
    Charms of other such beings without Storyteller permission." After lock the rule
    asks only for a willing tutor, which is narrative, so the gate falls away."""
    if foreign_charms_caste(ruleset, character) is None:
        return False
    return character.chargen_locked or character.st_foreign_charms


def is_foreign_charm(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """Whether `charm` is another splat's Charm for this character — i.e. it is only
    reachable via the p.127 generalist rule, not by the ordinary splat/tier match.
    This is what the doubled XP price keys off, so the `open_to_tiers` styles a
    Celestial may learn natively (Hungry Ghost, Five-Dragon) are NOT foreign and
    must not double — hence the ruleset argument."""
    return not charm_matches_splat(character, charm, ruleset)


def charm_learnable_by_splat(ruleset: RuleSet, character: Character, charm: Charm) -> bool:
    """The picker/graph filter and the `charm-wrong-splat` check: `charm` is either
    natively available (charm_matches_splat) or reachable through the caste's
    foreign-Charm privilege. Kept separate from charm_matches_splat so that
    accessible_circles — which asks what the character's OWN splat can initiate —
    keeps its narrower question."""
    if charm_matches_splat(character, charm, ruleset):
        return True
    # A Charm flagged no_foreign_learning is never reachable through the generalist
    # rule (the Alchemical Weaving Engines — CH4, "Non-Alchemicals cannot learn
    # weaving Charms"): only its own splat, caught by the match above, may hold it.
    return foreign_charms_open(ruleset, character) and not charm.no_foreign_learning


def check_splat_consistency(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Every Charm the character holds must belong to the character's own Exalt
    type, unless their caste may learn other splats' Charms (p.127). Spells are
    cross-splat (gated by circle, not splat) and are not checked; unknown Charm ids
    are left to check_references."""
    issues: list[Issue] = []
    permissive = foreign_charms_open(ruleset, character)
    gated = foreign_charms_caste(ruleset, character) is not None and not permissive
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is None or charm_matches_splat(character, charm, ruleset):
            continue
        if charm.no_foreign_learning:
            # Barred from the generalist rule entirely (Weaving Engines, CH4) — the
            # foreign-charm privilege never reaches it, permission or not.
            issues.append(Issue(
                code="charm-wrong-splat", where=cid,
                message=f"Charm {charm.name!r} is {splat_of(charm)} and cannot be "
                        f"learned by another Exalt type even under the generalist "
                        f"rule (CH4: non-Alchemicals cannot learn weaving Charms).",
            ))
            continue
        if permissive:
            continue
        if gated:
            issues.append(Issue(
                code="charm-foreign-no-st-permission", where=cid,
                message=f"Charm {charm.name!r} belongs to another Exalt type "
                        f"({splat_of(charm)}). An Eclipse-style caste may only start "
                        f"play knowing it with Storyteller permission (p.127).",
            ))
            continue
        issues.append(Issue(
            code="charm-wrong-splat", where=cid,
            message=f"Charm {charm.name!r} is {splat_of(charm)}, not the "
                    f"character's Exalt type {character.exalt_type!r}.",
        ))
    return issues


def validate(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Run all *implemented* checks and return the combined issues. Chargen
    predicates are excluded until designed."""
    issues: list[Issue] = []
    issues += check_exalt_type(ruleset, character)
    issues += check_caste_splat(ruleset, character)
    issues += check_lunar_casteless_consistency(ruleset, character)
    issues += check_splat_consistency(ruleset, character)
    issues += check_references(ruleset, character)
    issues += check_charm_prerequisites(ruleset, character)
    issues += check_spell_access(ruleset, character)
    issues += validate_combos(ruleset, character)
    issues += validate_arrays(ruleset, character)
    issues += validate_submodules(ruleset, character)
    issues += check_ox_body(ruleset, character)
    issues += check_beastman_gifts(ruleset, character)
    return issues
