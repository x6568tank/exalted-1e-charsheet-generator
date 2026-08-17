"""
engine/validate/__init__.py — pure legality checks: (RuleSet, Character) -> issues.

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

from collections import Counter
from typing import Optional

from pydantic import BaseModel

from ...models.character import (
    Character, FormulaEntry, HouseRules, RitualEntry, ThaumaturgyState)
from ...models.rules import (
    AbilityName,
    AttributeName,
    Charm,
    CharmCountRequirement,
    CharmType,
    RuleSet,
    SpellCircle,
    TRACK_CIRCLES,
    VirtueName,
)
from .. import artifacts, derive, elder, merits
from .. import paths as paths_mod   # aliased: `paths` is the local PathRating list in chargen accounting

# Re-exported, not defined here. `validate.X` is the ONE public path to every name
# in this package (the human's call, 2026-08-17) — 1,465 call sites across
# `engine/`, `ui/` and `tests/` reach these through `validate.`, and a domain module
# is an implementation detail, not a second front door. When a rule moves out of
# this file, it gains a line here and every caller keeps working unchanged.
from ._base import (           # noqa: F401 — re-exported for callers
    ATTRIBUTE_CATEGORIES,
    Issue,
    _attribute_category,
    _chargen_source,
    ability_rating,
    craft_rating,
    thaum_state,
)
from .castes import (          # noqa: F401 — re-exported for callers
    _caste_favored,
    _caste_favored_attr_names,
    _caste_favored_attribute_category,
    _caste_favored_attribute_sets,
    caste_attributes,
    caste_favored_abilities,
    splat_has_castes,
)
from .charms import (          # noqa: F401 — re-exported for callers
    DB_MA_ENLIGHTENMENT_PAIRS,
    PERFECTED_LOTUS_MATRIX_ID,
    TIER_ORDER,
    CharmPick,
    _category_ability,
    _charm_attribute_caste_favored,
    _charm_is_caste_favored,
    _charm_name,
    _charm_picks_from,
    _immaculate_path,
    _is_dragon_path_style,
    _min_trait_rating,
    _mountain_folk_pattern,
    _mountain_folk_unenlightened_bar,
    _repeatable_purchase_cap,
    category_available,
    charm_ability_requirements,
    charm_ability_shortfalls,
    charm_count_requirement_label,
    charm_count_shortfalls,
    charm_fits_dedicated_slot,
    charm_learnable_by_splat,
    charm_matches_splat,
    charm_occupies_slot,
    charm_pick_bp_costs,
    charm_pick_count,
    charm_picks,
    charm_restriction_met,
    charm_slot_counts,
    charm_slot_usage,
    charm_virtue_cap_met,
    chargen_charm_picks,
    charms_available,
    charms_depending_on,
    check_beastman_gifts,
    check_charm_prerequisites,
    check_gift_prerequisites,
    check_ox_body,
    crossover_alchemical_charm,
    crossover_panoply_xp,
    db_enlightenment_met,
    foreign_charms_caste,
    foreign_charms_open,
    foreign_charms_permitted,
    gift_charm,
    gift_charm_id,
    gift_purchase_cap,
    gifts_per_purchase,
    has_perfected_lotus_matrix,
    heritage_barred_charm_ids,
    heritage_bars_initiation,
    heritage_charm_access,
    heritage_charms_available,
    heritage_gift_spec,
    heritage_magic_track,
    immaculate_martial_artist,
    is_foreign_charm,
    is_immaculate_charm,
    is_martial_arts_charm,
    is_terrestrial_martial_arts,
    known_gift_keys,
    meets_charm_requirements,
    mountain_folk_cross_pattern,
    origin_granted_charm_ids,
    ox_body_cap,
    ox_body_charm,
    ox_body_charm_id,
    repeatable_cap_trait_name,
    splat_of,
    splat_uses_charm_slots,
    tier_rank,
    tier_reaches,
    uses_charm_slots,
)


# The repeatable Ox-Body-equivalent Charm is per-splat: each ExaltDefinition names
# its own (Solar's is solar.endurance.ox-body-technique). It is bought once per dot
# of its cap trait (Endurance; Stamina for Lunar), each purchase choosing a
# health-level package;
# stored on Character.ox_body, not in Character.charms (so the count is representable).












# --------------------------------------------------------------------------- #
# The canonical Charm-pick enumeration
# --------------------------------------------------------------------------- #















# --------------------------------------------------------------------------- #
# The canonical Thaumaturgy-purchase enumeration
# --------------------------------------------------------------------------- #

# "Magic for Everyone" (p.115) covers "rituals, formulas or procedures of no more
# than level 3". Not in a cost table — it is a limit on an optional grant rather
# than a rate, so it has no natural home in costs_bonus.json.
_MAGIC_FOR_EVERYONE_MAX_LEVEL = 3

# The two optional ST chargen restrictions of p.113: "no more than three-dot rituals
# and/or the third level of knowledge in any Science". Off unless the table turns
# them on -- see HouseRules.restrict_chargen_*.
_ST_CHARGEN_RITUAL_CAP = 3
_ST_CHARGEN_SCIENCE_CAP = 3



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


def chargen_house_rules(character: Character) -> HouseRules:
    """The table toggles chargen accounting reads: the frozen snapshot once locked,
    else the live setting, else the all-off default.

    Kept as its own accessor rather than an 18th element of `_chargen_source` — that
    tuple is trait state, and this is a setting about how trait state is priced.
    """
    snap = character.chargen_snapshot
    if snap is not None:
        return snap.house_rules or HouseRules()
    return character.house_rules or HouseRules()


def background_catalogue_for(ruleset: RuleSet, character: Character) -> list:
    """The Background names this character may actually pick from — the ONE read site
    for `HouseRules.all_backgrounds_available`, so no UI module has to know the flag
    exists and the answer cannot differ between the two places Backgrounds are chosen
    (the row dropdown and the catalogue dialog).

    Reads the LIVE house rules rather than `chargen_house_rules`'s frozen snapshot: a
    locked character keeps her Backgrounds either way, and a table that later opens
    the catalogue should be able to add one in play. This flag changes which names are
    OFFERED, never how a dot is priced, which is what the snapshot exists to protect.
    """
    hr = character.house_rules or HouseRules()
    rows = ruleset.backgrounds_for(character.exalt_type, character.origin,
                                   all_available=hr.all_backgrounds_available)
    # A `barred` rule hides the Background until its Storyteller toggle lifts it, the
    # same treatment `backgrounds_for` gives `banned_backgrounds`: the dropdown never
    # offers a name the sheet cannot legally hold. The BAR and the OFFER are separate
    # mechanisms and the toggle has to move both — the browser found exactly that
    # (2026-08-12), with a mortal granted permission and still unable to find Artifact
    # or Manse in the catalogue, because the bar lifted and the offer list did not.
    budgets = effective_budgets(ruleset, character)
    hidden = {name for name, rule in budgets.background_rules.items()
              if rule.barred and not background_st_permitted(character, rule)}
    if hidden:
        rows = [bg for bg in rows if bg.name.strip().lower() not in hidden]
    return rows


def magic_for_everyone_grant(ruleset: RuleSet, character: Character) -> int:
    """How many thaumaturgy purchases this character gets FREE at creation under the
    optional "Magic for Everyone" rule (p.115): "one ritual, one formula or procedure
    or knowledge of one aspect for every two dots in Occult".

    0 unless the table has switched the rule on. Occult is read from the chargen
    source, so the allowance is fixed at creation — **raising Occult with XP does not
    earn more free picks** (rules-authority call, human 2026-07-29). Post-lock that
    happens for free: the snapshot holds chargen Occult.
    """
    if not chargen_house_rules(character).magic_for_everyone:
        return 0
    abilities, crafts = _chargen_source(character)[1], _chargen_source(character)[2]
    occult = abilities.get(AbilityName.OCCULT, 0)
    return occult // 2


def magic_for_everyone_eligible(ruleset: RuleSet, purchase: ThaumPurchase) -> bool:
    """Whether `purchase` is the kind of thing the free grant may cover.

    The rule is explicit about its own limits: "rituals, formulas or procedures of no
    more than level 3, and only specialties in Arts, not the Arts themselves (so a
    non-thaumaturge could chose to learn how to ward off ghosts, but not the Art of
    Warding)". So Arts and Sciences are never free.

    "knowledge of one aspect" means a PRINTED aspect, so a player-invented narrower
    specialty is not eligible — it is not one of the things the book enumerates.
    (The sidebar's parenthetical "along with any appropriate specialties" is
    deliberately unimplemented: the rules authority could not determine what it
    means, human 2026-07-29. Do not guess at it.)
    """
    if purchase.kind in ("art", "science"):
        return False
    if purchase.kind == "specialty":
        art_id, _, name = purchase.key.partition(":")
        art = ruleset.thaum_arts.get(art_id)
        return art is not None and any(
            a.name.casefold() == name.casefold() for a in art.aspects)
    return purchase.level <= _MAGIC_FOR_EVERYONE_MAX_LEVEL


def thaum_purchase_bp_costs(ruleset: RuleSet, character: Character,
                            purchases: list[ThaumPurchase],
                            free_picks: int = 0) -> list[int]:
    """The bonus-point price of each purchase, in purchase order — parallel to
    `purchases`, so the UI can render a priced row per purchase. A Science's figure
    is the whole ladder up to its rating, since chargen holds a rating rather than a
    sequence of purchases.

    `free_picks` is the "Magic for Everyone" allowance. It zeroes that many ELIGIBLE
    purchases, dearest first — the player-favourable assignment this module already
    uses everywhere a free pool meets mixed rates. The player does not tag which
    purchases were free; the engine computes it, per the standing decision that
    current state is canonical and the accounting is derived.
    """
    # Deferred import: costs.py imports this module, so a top-level import here would
    # cycle. The thaum_* rate functions depend on nothing in validate, hence safe.
    from .. import costs

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

    if free_picks > 0:
        eligible = [i for i, p in enumerate(purchases)
                    if magic_for_everyone_eligible(ruleset, p)]
        for i in sorted(eligible, key=lambda i: out[i], reverse=True)[:free_picks]:
            out[i] = 0
    return out


# --------------------------------------------------------------------------- #
# Per-purchase gates.
#
# `thaumaturgy_issues` below answers "is what this character HOLDS legal"; a picker
# needs the forward-looking twin, "may they buy this ONE thing right now, and if not
# why". Both questions share one implementation here so the UI can grey a row out
# for exactly the reason the validator would later complain about — the reason
# strings ARE the issue messages, which is why the issue builders below call these
# rather than wording the same gate twice.
#
# `chargen=True` adds the two optional p.113 creation-only restrictions, mirroring
# `meets_spell_requirements(..., chargen=...)`. They are not part of the holding's
# legality once play starts, so they never appear when chargen=False.
# --------------------------------------------------------------------------- #

def thaum_art_locked_reason(ruleset: RuleSet, character: Character, art_id: str) -> str:
    """Why the Art `art_id` may not be trained right now, or "" if it may be."""
    art = ruleset.thaum_arts.get(art_id)
    if art is None:
        return f"Art {art_id} is not in the rule set."
    occult = ability_rating(character, AbilityName.OCCULT)
    if occult < art.min_occult:
        return (f"The Art of {art.name} needs Occult {art.min_occult}; "
                f"character has {occult}.")
    return ""


def thaum_aspect_locked_reason(ruleset: RuleSet, character: Character,
                               art_id: str, aspect_name: str) -> str:
    """Why this specialty may not be bought, or "" if it may be.

    Owning the parent Art is NOT a requirement and must never become one (p.116
    footnote, stated three times). Only a PRINTED aspect can be gated at all: a
    player-invented specialty matches no aspect and is therefore always open.
    """
    art = ruleset.thaum_arts.get(art_id)
    if art is None:
        return f"Art {art_id} is not in the rule set."
    aspect = next((a for a in art.aspects
                   if a.name.casefold() == aspect_name.casefold()), None)
    if aspect is None:
        return ""
    occult = ability_rating(character, AbilityName.OCCULT)
    if occult < aspect.min_occult:
        return (f"{art.name} ({aspect.name}) needs Occult "
                f"{aspect.min_occult}; character has {occult}.")
    return ""


def thaum_ritual_locked_reason(ruleset: RuleSet, character: Character, level: int,
                               *, chargen: bool = False) -> str:
    """Why a level-`level` ritual may not be learned, or "" if it may be. Level is
    passed rather than an id so a custom ritual is gated identically to a catalogue
    one — the Occult rule is stated about the level, not the entry (p.148)."""
    occult = ability_rating(character, AbilityName.OCCULT)
    if occult < level:
        return (f"A level-{level} ritual needs Occult {level}; "
                f"character has {occult} (p.148).")
    if (chargen and level > _ST_CHARGEN_RITUAL_CAP
            and chargen_house_rules(character).restrict_chargen_ritual_level):
        return (f"This table restricts starting characters to rituals of "
                f"level {_ST_CHARGEN_RITUAL_CAP} or lower (p.113); this "
                f"one is level {level}.")
    return ""


def thaum_science_raise_reason(ruleset: RuleSet, character: Character,
                               science_id: str, *, chargen: bool = False) -> str:
    """Why this Science may not gain its NEXT dot, or "" if it may.

    The forward-looking counterpart of the `max_rating` check in
    `thaumaturgy_issues`: that one asks whether a held rating is in range, this asks
    whether one more dot is buyable. The ceiling is the Science's OWN `max_rating`
    (Alchemy 6), never the project's usual 5 — see rules.ScienceLevel.
    """
    science = ruleset.thaum_sciences.get(science_id)
    if science is None:
        return f"Science {science_id} is not in the rule set."
    held = next((s for s in thaum_state(character).sciences
                 if s.science_id == science_id), None)
    rating = held.rating if held is not None else 0
    if rating >= science.max_rating:
        return f"{science.name} is already at {science.max_rating}, its maximum."
    if (chargen and rating >= _ST_CHARGEN_SCIENCE_CAP
            and chargen_house_rules(character).restrict_chargen_science_rating):
        return (f"This table restricts starting characters to "
                f"{_ST_CHARGEN_SCIENCE_CAP} dots in any Science (p.113).")
    return ""


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

    # Announced BEFORE the no-purchases early return: under "Magic for Everyone" the
    # allowance applies to every starting character, so the one who has bought no
    # thaumaturgy at all is exactly the one who needs telling it is there. Silent at
    # Occult 0-1, where the allowance is zero, and in every game without the toggle.
    grant = magic_for_everyone_grant(ruleset, character)
    if grant:
        issues.append(Issue(
            code="magic-for-everyone-grant", severity="info",
            message=f"Magic for Everyone: {grant} free ritual(s), formula(s) or "
                    f"printed aspect(s) at creation, from Occult {occult}. "
                    f"Rituals and formulas are limited to level "
                    f"{_MAGIC_FOR_EVERYONE_MAX_LEVEL}; Arts and Sciences are never free.",
        ))

    if not purchases:
        return issues

    if not exalt.thaumaturgy_usable:      # exalt_for never returns None
        issues.append(Issue(
            code="thaum-unusable", where=character.exalt_type,
            message=f"{character.exalt_type} may hold thaumaturgy but can never "
                    "use it (Player's Guide p.114).", severity="info",
        ))

    for art_id in state.arts:
        if art_id not in ruleset.thaum_arts:
            issues.append(Issue(code="unknown-thaum-art", where=art_id,
                                message=f"Art {art_id} is not in the rule set."))
            continue
        reason = thaum_art_locked_reason(ruleset, character, art_id)
        if reason:
            issues.append(Issue(code="thaum-art-occult", where=art_id, message=reason))

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
        reason = thaum_aspect_locked_reason(ruleset, character, spec.art_id, spec.name)
        if reason:
            issues.append(Issue(
                code="thaum-aspect-occult", where=f"{spec.art_id}:{spec.name}",
                message=reason))
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
        # chargen=False: the p.113 cap is a creation-time restriction and belongs to
        # thaumaturgy_chargen_issues, which reports it with its own code.
        reason = thaum_ritual_locked_reason(ruleset, character, level)
        if reason:
            issues.append(Issue(
                code="thaum-ritual-occult", where=entry.ritual_id or entry.name,
                message=reason))

    for entry in state.formulas:
        if entry.formula_id and entry.formula_id not in ruleset.thaum_formulas:
            issues.append(Issue(
                code="unknown-thaum-formula", where=entry.formula_id,
                message=f"Formula {entry.formula_id} is not in the rule set."))

    return issues


def thaumaturgy_chargen_issues(ruleset: RuleSet, character: Character,
                               state: ThaumaturgyState) -> list["Issue"]:
    """The two OPTIONAL chargen restrictions of p.113, each switched on separately:
    "Storytellers may choose to restrict starting characters to no more than
    three-dot rituals and/or the third level of knowledge in any Science."

    Separate from `thaumaturgy_issues` because these are creation-time only — they
    cap what may be BOUGHT at chargen, not what may ever be known. A character who
    legitimately raises a Science past 3 with XP must not start failing this check,
    so it is only ever called with the chargen state, from `validate_chargen`.
    """
    issues: list[Issue] = []
    rules = chargen_house_rules(character)

    if rules.restrict_chargen_ritual_level:
        for entry in state.rituals:
            level = thaum_ritual_level(ruleset, entry)
            if level > _ST_CHARGEN_RITUAL_CAP:
                issues.append(Issue(
                    code="thaum-ritual-chargen-cap", where=entry.ritual_id or entry.name,
                    message=f"This table restricts starting characters to rituals of "
                            f"level {_ST_CHARGEN_RITUAL_CAP} or lower (p.113); this "
                            f"one is level {level}.",
                ))

    if rules.restrict_chargen_science_rating:
        for sci in state.sciences:
            if sci.rating > _ST_CHARGEN_SCIENCE_CAP:
                science = ruleset.thaum_sciences.get(sci.science_id)
                issues.append(Issue(
                    code="thaum-science-chargen-cap", where=sci.science_id,
                    message=f"This table restricts starting characters to "
                            f"{_ST_CHARGEN_SCIENCE_CAP} dots in any Science (p.113); "
                            f"{science.name if science else sci.science_id} is "
                            f"{sci.rating}.",
                ))
    return issues






# --------------------------------------------------------------------------- #
# Reference integrity
# --------------------------------------------------------------------------- #

def check_references(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Every Charm/Spell/Elemental-Power id the character holds must resolve in the
    RuleSet. Equipment is an inline copy by design and is intentionally not checked.

    Charms live on four lists, and all four are checked: an unresolvable id in the
    Alchemical's Panoply (`retainer_charms`) or in a camp's `granted_charms` is the
    same defect as one in `charms` — most likely a custom Charm deleted from the
    library, or a save opened without the library that defined it (see
    custom_content.py). Elemental Powers are the same class of defect: a renamed or
    deleted power id must surface an `elemental-power-unknown` issue rather than a
    bare "?" row on the sheet with nothing behind it."""
    issues: list[Issue] = []
    charm_lists = (
        ("", character.charms),
        (" (in the Panoply)", character.retainer_charms),
        (" (granted by a training camp)", character.granted_charms),
    )
    for note, ids in charm_lists:
        for cid in ids:
            if cid not in ruleset.charms:
                issues.append(Issue(
                    code="unknown-charm", where=cid,
                    message=f"Character holds unknown Charm id {cid!r}{note}.",
                ))
    for sid in character.spells:
        if sid not in ruleset.spells:
            issues.append(Issue(
                code="unknown-spell", where=sid,
                message=f"Character holds unknown Spell id {sid!r}.",
            ))
    for pid in character.elemental_powers:
        if pid not in ruleset.elemental_powers:
            issues.append(Issue(
                code="elemental-power-unknown", where=pid,
                message=f"Character holds unknown Elemental Power id {pid!r}.",
            ))
    return issues


# --------------------------------------------------------------------------- #
# Charm prerequisites
# --------------------------------------------------------------------------- #





























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


def two_pool_ability_accounting(b, character, abilities, crafts, bp_costs=None):
    """The Mountain Folk two-pool Ability accounting (CH6 p.230), and the ONE read
    site for it — `bonus_point_breakdown`, the unspent warning and the editor's
    "N / M dots spent" readout all call this, so they cannot disagree.

    The free pool (`ability_dots`) funds ANY Ability's dots up to `ability_cap_pre_bp`
    (3); the favored pool (`ability_favored_dots`) funds FAVORED Abilities' dots above
    that and up to the chargen ability ceiling (5 — "can increase Abilities as high as
    six dots with bonus points", so the sixth dot is bonus points). Dots neither pool
    covers are bonus points at the existing tier rates: the ordinary rate for a
    non-Favored Ability's 4th dot, the favored rate for a Favored Ability's 6th.

    Allocation between the pools is the player's choice and is not recorded, so this
    computes the PLAYER-FAVOURABLE one — the cheapest legal assignment, the same
    principle `background_pool_spend` uses for Heir Apparent's waived dots: the free
    pool is spent first (it is free up to its budget), a Favored Ability's remaining
    dots ride the favored pool, and the favored pool is overflowed (1 BP/dot) rather
    than the free pool (2 BP/dot) when both run out.

    Returns `(within, ability_bp)`: `within` is how many pool dots are spent (counted
    against the combined `ability_dots + ability_favored_dots` budget); `ability_bp`
    is the bonus-point charge (0 when `bp_costs` is None, which is what the unspent
    warning and the editor readout pass)."""
    cap = b.ability_cap_pre_bp
    ceiling = merits.DOT_MAX          # 5 — the chargen ability ceiling (p.230)
    favored_set = set(character.favored_abilities)
    nf_free = nf_above = 0
    fav_free_max = fav_above3 = fav_above_ceiling = 0
    for ab, rating in _ability_slots(abilities, crafts):
        if ab in favored_set:
            fav_free_max += min(rating, cap)
            fav_above3 += max(0, min(rating, ceiling) - cap)
            fav_above_ceiling += max(0, rating - ceiling)
        else:
            nf_free += min(rating, cap)
            nf_above += max(0, rating - cap)
    fav_free = min(max(0, b.ability_dots - nf_free), fav_free_max)
    free_used = nf_free + fav_free
    favored_used = (fav_free_max - fav_free) + fav_above3
    within = free_used + min(favored_used, b.ability_favored_dots)
    if bp_costs is None:
        return within, 0
    ability_bp = (nf_above + max(0, nf_free - b.ability_dots)) * bp_costs.ability
    ability_bp += fav_above_ceiling * bp_costs.ability_favored_caste
    ability_bp += max(0, favored_used - b.ability_favored_dots) * bp_costs.ability_favored_caste
    return within, ability_bp














# --------------------------------------------------------------------------- #
# Spell-circle access
# --------------------------------------------------------------------------- #

def granted_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """The set of magic circles the character can cast in, taken from the
    `grants_circle` of every known initiation Charm PLUS any circle a Merit grants
    outright. Track-agnostic (sorcery or, later, necromancy) — the circle enum
    carries the distinction.

    The Merit half is not a convenience: a splat that may hold no Charms at all
    (mortals) can never satisfy the Charm half, so Essence Mastery's Terrestrial
    sorcery would be permanently unreachable without it. This is the function the
    *gates* use (meets_spell_requirements, check_spell_access), which is why the
    grant has to land here and not only in accessible_circles."""
    out = {
        ruleset.charms[cid].grants_circle
        for cid in character.charms
        if cid in ruleset.charms and ruleset.charms[cid].grants_circle is not None
    }
    out |= set(merits.merits_and_flaws_calc(ruleset, character).granted_circles)
    return out


def accessible_circles(ruleset: RuleSet, character: Character) -> set[SpellCircle]:
    """Every magic circle this character can reach — the circle granted by any
    initiation Charm they may learn (their own Exalt type, or an `open_to_all`
    Charm), unioned with circles already granted by known Charms.

    This is what the spell picker should show, and it is deliberately NOT the same
    as the Exalt's nominal `magic_track`: a splat whose Charm trees hold BOTH sorcery
    and necromancy initiations (Abyssals carry Terrestrial/Celestial Sorcery AND the
    three Necromancy circles) reaches both tracks, so its picker must too. Track is a
    display-ordering hint, not an access gate — the gate is the granting Charm."""
    # Merit-granted circles (mortals + Essence Mastery, capped at Terrestrial) arrive
    # through granted_circles, which is where the gates read them too. See engine.merits.
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
    if spell.id in ruleset.exalt_for(character.exalt_type).barred_spell_ids:
        return False
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
    barred = ruleset.exalt_for(character.exalt_type).barred_spell_ids
    issues: list[Issue] = []
    for sid in character.spells:
        spell = ruleset.spells.get(sid)
        if spell is None:
            continue
        # The splat-level spell bar, restated here as well as in
        # meets_spell_requirements: the picker route and the already-held route are
        # two ways to the same permission, and a bar on only one of them is this
        # build's most-repeated bug.
        if sid in barred:
            issues.append(Issue(
                code="spell-barred", where=sid,
                message=(f"{spell.name}: {ruleset.exalt_for(character.exalt_type).label} "
                         f"may never learn this spell."),
            ))
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
    # The Dragon-King Path powers are Combo members (p.177 "Dragon Kings may purchase
    # and use Combos normally") — their virtual Charm rows resolve via ruleset.charms
    # in the loop below, so the only change is folding them into the "known" set.
    known = set(character.charms) | set(paths_mod.path_power_ids(ruleset, character))
    where = combo.name or "(unnamed combo)"
    # A splat barred from Combos outright (the dead — E:Ab p.234, "The dead may never
    # learn Combos and so may never use more than one Charm per turn"). Reported first
    # and alone: every other finding below is about how this Combo is BUILT, which is
    # noise for a character who may not have one at all.
    if not ruleset.exalt_for(character.exalt_type).combos_available:
        return [Issue(
            code="combo-splat-barred", where=where,
            message=(f"{ruleset.exalt_for(character.exalt_type).label} characters may "
                     f"never learn Combos (E:Ab p.234)."),
        )]
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
    list, then the Dragon-King Path powers (owned dots projected into virtual Charm
    rows; only instant-duration powers are Combo-legal, p.177). The picker offers
    these when adding a Charm to a Combo."""
    out: list[str] = []
    for cid in character.charms:
        charm = ruleset.charms.get(cid)
        if charm is not None and charm.duration == _COMBO_DURATION:
            out.append(cid)
    for cid in paths_mod.path_power_ids(ruleset, character):
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
        else:
            # A flat pool: `pick` Charms from anywhere in it, in any combination
            # (Cult p.96, the Dragon-Blooded Tabernacle package). No cross-style
            # complaint is possible here — mixing IS the shape — so the only failure
            # is the wrong COUNT, and an over-count leaves the surplus in `remaining`
            # to be reported as granted-charm-extra like any other stray id.
            pool = set(choice.pool_charm_ids(ruleset.charms))
            taken = [cid for cid in remaining if cid in pool]
            if len(taken) < choice.pick:
                issues.append(Issue(
                    code="granted-charm-choice-unresolved", where=choice.label,
                    message=f"{camp.label}: {choice.label} — needs {choice.pick} "
                            f"Charm(s) from the package's list; {len(taken)} taken.",
                ))
            for cid in taken[:choice.pick]:
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
        paid = cheap * rule.dot_cost + (rating - cheap) * rule.expensive_dot_cost
    else:
        paid = rating * rule.dot_cost
    return max(0, paid - rule.free_rating)


def background_rating(backgrounds, name: str) -> int:
    """The character's rating in the Background called `name` (0 if absent). Sums
    duplicates, since Backgrounds are free text and nothing stops two rows."""
    key = name.strip().lower()
    return sum(bg.rating for bg in backgrounds if bg.name.strip().lower() == key)


def background_rows(backgrounds, name: str) -> list[int]:
    """Every INSTANCE of the Background called `name`, as a list of ratings.

    The third way to read a repeated Background, beside `background_rating` (the sum)
    and `background_best` (the largest). A possession Background is held per possession
    — "two Artifacts at 2 dots each are two artifacts, not one artifact at 4" — so a
    rule that allows one thing PER ROW needs the rows themselves, not either summary.
    """
    key = name.strip().lower()
    return [bg.rating for bg in backgrounds if bg.name.strip().lower() == key]


def background_best(backgrounds, name: str) -> int:
    """The HIGHEST single instance of the Background called `name` (0 if absent).

    Backgrounds that name a specific possession are held per possession — two Artifacts
    at 2 dots each are two artifacts, not one artifact at 4 — so a rule that measures
    ONE of them must not read the sum. Damaged Artifact is the case: "may not gain more
    points from this Flaw than the rating of the artifact it modifies" (p.37), singular.
    Two 2-dot artifacts satisfied a 3-point Damaged Artifact until 2026-07-31.
    """
    key = name.strip().lower()
    return max((bg.rating for bg in backgrounds if bg.name.strip().lower() == key),
               default=0)


def effective_background_rating(ruleset: RuleSet, character: Character,
                                name: str) -> int:
    """What a Background is WORTH to this character, which is not always what is stored.

    Mountain Folk Resources is the case that needs it (CH6): "an effective Resources
    rating equal to the number of dots invested in this Background + 2, but cannot have
    more than three actual dots", plus a floor for characters who never bought it at all
    — Resources •• Enlightened, • Unenlightened. So a stored 3 is worth 5, and a stored
    0 is worth 2.

    ⚠ The floor is NOT a bonus applied to zero. Adding `effective_bonus` at 0 dots would
    make an unbought Background worth as much as one bought dot, which is a different
    (and wrong) rule. They are separate fields and this is the only place both are read.

    Every splat that prints neither field gets the stored rating unchanged, so this is
    safe to call for any Background on any character.
    """
    stored = background_best(character.backgrounds, name)
    rule = effective_budgets(ruleset, character).background_rules.get(name.strip().lower())
    if rule is None:
        return stored
    if stored <= 0:
        return max(rule.effective_floor, 0)
    return stored + rule.effective_bonus


def gear_affordability(ruleset: RuleSet, character: Character,
                       resources_cost: int) -> str:
    """How a piece of gear priced at `resources_cost` sits against this character's
    Resources — core p.325, "The Resources System", the whole rule:

        * cost LOWER than her Resources — an out-of-pocket expense; "within reason,
          the character can purchase as many of the items as she wants";
        * cost EQUAL to her Resources — "a serious expense. When she buys it, she
          lowers her Resources rating by 1 until it is increased through roleplaying";
        * cost GREATER — "too expensive for her, and she cannot afford to buy it".

    Returns "easy" / "serious" / "unaffordable", or "" for gear with no printed cost
    (56 of the 122 catalogue rows have none, and a missing price is not a free item).

    ⚠ This answers a PURCHASE, and is deliberately NOT a validation of what a character
    OWNS — no caller may turn it into one (human's ruling 2026-08-12). The printed rule
    contradicts an ownership invariant in its own middle clause: buying at cost EQUAL
    drops Resources by one, so the book's own outcome is a character holding a 3-cost
    item at Resources 2. Loot and gifts break it the same way — nothing says a
    character may not be GIVEN a daiklave. A static "no item above your rating" check
    would flag both as errors.
    """
    if resources_cost <= 0:
        return ""
    # The EFFECTIVE rating, not the stored one — a Mountain Folk's Resources is worth
    # her dots + 2 and is capped at 3 actual dots, so reading the row raw made every
    # item above Resources ••• unaffordable to the richest Jadeborn in Creation (found
    # in the browser, 2026-08-13). `effective_background_rating` also takes the HIGHEST
    # single row rather than the sum: Resources is one lifestyle rating, and two rows of
    # 2 is a character who wrote it down twice, not a character with 4.
    #
    # ⚠ `ruleset` is REQUIRED here, unlike the optional-ruleset shape `derive.soak` and
    # friends use. That shape trades a TypeError for a silently wrong answer, and this
    # function's wrong answer is "you cannot buy that" — invisible, and exactly the bug
    # being fixed. A caller with no RuleSet has no business pricing gear.
    rating = effective_background_rating(ruleset, character, "Resources")
    if resources_cost < rating:
        return "easy"
    return "serious" if resources_cost == rating else "unaffordable"


def trait_rating(character: Character, name: str, backgrounds=None) -> int:
    """The character's rating in the trait called `name`, whatever kind of trait it is.

    Merit prerequisites (cluster 7) name traits across four namespaces — Appearance is
    an Attribute, Occult an Ability, Manse and Breeding and Celestial Patron are
    Backgrounds — and the printed text gives only a name. So this resolves by name in
    a fixed order: Attributes, Abilities, Virtues, then Backgrounds.

    An unresolvable name reads as 0 rather than raising, the same graceful handling
    unresolvable Charm and Background references already get. The order matters only if
    a name ever collides across namespaces; none of the 1e trait names does.

    Craft resolves through `craft_rating` (the best of the per-focus instances), since
    the single AbilityName.CRAFT dot is unused.
    """
    key = name.strip().lower()
    if not key:
        return 0
    for attr in AttributeName:
        if attr.value == key:
            return character.attributes.get(attr, 0)
    for ab in AbilityName:
        if ab.value == key:
            return ability_rating(character, ab)
    for v in VirtueName:
        if v.value == key:
            return character.virtues.get(v, 0)
    return background_rating(
        character.backgrounds if backgrounds is None else backgrounds, name)


def unmet_trait_prerequisites(character: Character, definition, purchase,
                              backgrounds=None) -> list[list]:
    """The OR groups of `definition.trait_prerequisites` this purchase does NOT satisfy.

    Empty for the great majority, which require no rated trait. The "" key holds the
    requirements every tier carries; a named tier adds its own on top (Innocuous' two-
    point version needs Appearance 2, its four-point version needs nothing).

    A group is satisfied when ANY member of it is met — Cache's "Resources 4+ or
    Salary 2+" — matching the AND-of-OR shape Charm prerequisites already use.
    """
    groups: list[list] = []
    groups += definition.trait_prerequisites.get("", [])
    if purchase.tier:
        groups += definition.trait_prerequisites.get(purchase.tier, [])
    return [g for g in groups
            if not any(trait_rating(character, r.trait, backgrounds) >= r.rating
                       for r in g)]


def background_dots_budget(b, character: Character) -> int:
    """The Background-dot budget for THIS character, honouring a per-caste override
    (Mountain Folk, CH6 p.230: Artisans 13, Enlightened undercastes 10, Unenlightened
    6). `background_dots_by_caste` keys on CasteDefinition.id; a caste absent from the
    map falls back to `background_dots`. Every Background-budget consumer reads this,
    so the warning and the overflow arithmetic can never disagree."""
    if b.background_dots_by_caste:
        return b.background_dots_by_caste.get(character.caste, b.background_dots)
    return b.background_dots


def background_pool_spend(ruleset: RuleSet, character: Character, b, backgrounds,
                          bp_costs=None) -> tuple[int, list[int]]:
    """(pool dots consumed, per-dot bonus-point rates still owed) for the character's
    Backgrounds. The single arithmetic both the unspent-dot warning and
    `bonus_point_breakdown` read, so the two can never disagree about what "spent from
    the pool" means.

    Ordinarily a dot at or below `background_cap_pre_bp` consumes a pool dot and a dot
    above it is paid in bonus points at `background_above_3` (plus any per-Background
    surcharge — Lookshy Breeding, p.66).

    Heir Apparent (A6, p.24) moves some of the second group into the first: its
    inherited dots "may raise a Background above a rating of three", so that many
    above-cap dots are paid out of the ENLARGED pool the Merit granted instead of out
    of bonus points. They are not free — `effective_budgets` added exactly as many pool
    dots as are waived here, so the character pays for them once, through the pool.

    Which Background received the inheritance is the player's choice and is not
    recorded, so the waiver goes to the DEAREST above-cap dots the character actually
    has: the player-favourable reading, matching how free dots are already assigned.
    A waived dot counts as ONE pool dot rather than going back through
    `background_pool_dots`, whose expensive-upper-dot rules are Alchemical-only.
    """
    if bp_costs is None:
        bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin,
                                           character.upbringing)
    within = 0
    above_rates: list[int] = []
    for bg in backgrounds:
        rule = background_rule(b, bg.name)
        cap = bg.rating if (rule and rule.cap_pre_bp_exempt) else b.background_cap_pre_bp
        # The God-Blooded Inheritance Background's FREE dots — the ST's series option
        # (PG p.61, human 2026-08-02) — waive BOTH the pool cost and the above-cap
        # bonus points: a free dot that sits above the cap must not appear in
        # above_rates either, or "Inheritance 4 with the ST option at 4" still charges
        # the two points for the fourth dot, which is exactly the complaint.
        if bg.name.strip().lower() == "inheritance":
            free = merits.inheritance_free_rating(ruleset, character)
            within += max(0, min(bg.rating, cap) - free)
            free_above = max(0, min(bg.rating, free) - cap)
            rate = bp_costs.background_above_3
            above_rates += [rate] * max(0, bg.rating - cap - free_above)
            continue
        # Dots ABOVE `bp_above_rating` are bought one bonus point each, NOT from the
        # Background pool (Mountain Folk Artifact, CH6 p.234-235: "with each dot
        # beyond 5 costing one bonus point"). The dots at or below it go through the
        # normal accounting below — `cap_pre_bp_exempt` keeps the MF's dots in the
        # pool — and any of those that still sit above the pre-BP cap owe the ordinary
        # above-cap rate (none for the MF, whose exempt cap is its own rating).
        if rule and rule.bp_above_rating and bg.rating > rule.bp_above_rating:
            pool_rating = min(bg.rating, rule.bp_above_rating)
            within += background_pool_dots(rule, min(pool_rating, cap))
            mid_rate = bp_costs.background_above_3 + rule.bp_surcharge_per_dot
            above_rates += [mid_rate] * max(0, pool_rating - cap)
            above_rates += [1] * (bg.rating - rule.bp_above_rating)
            continue
        within += background_pool_dots(rule, min(bg.rating, cap))
        rate = bp_costs.background_above_3 + (rule.bp_surcharge_per_dot if rule else 0)
        above_rates += [rate] * max(0, bg.rating - cap)

    exempt = merits.merits_and_flaws_calc(ruleset, character).background_cap_exempt_dots
    if exempt:
        above_rates.sort(reverse=True)
        waived = min(exempt, len(above_rates))
        within += waived
        above_rates = above_rates[waived:]
    return within, above_rates


def background_issues(budgets, backgrounds, character=None, *,
                      post_lock=False) -> list[Issue]:
    """Legality for Backgrounds that carry mechanics (`background_rules`). Empty for
    every splat with none — which is all of them but the Alchemical and the handful of
    rules this brief adds.

    `character` is OPTIONAL, the silent-fallback shape the merits-flaws precedent uses
    (`derive.soak`, `lifecycle.lock_chargen`): a rule that needs the character — the
    Attribute-sum ceiling (Sidereal Connections) or a PER-CHARACTER `st_toggle` — is
    skipped (or reads as no permission) when called without one, rather than
    TypeErroring at every call site.

    `post_lock` runs the subset that binds on BOTH sides of the lock. `background_issues`
    is called post-lock from `validate.validate`, and ONLY rules with
    `BackgroundRule.bind_post_lock` are applied there — exactly the Sidereal Celestial
    Manse ≤3 and Mountain Folk Artifact ≤10 (2026-08-12 rulings). Every other cap in
    the build is chargen-only by design, because Backgrounds change through the story,
    not by purchase; the allowed/banned lists, minimums, prerequisites and the mortal
    bar all stay chargen-side.

    The checks: a Background the splat receives automatically may not be below that
    rating; a Background gated on another must have it; a hard ceiling — a literal
    `max_rating`, the Attribute-sum ceiling, or a `barred` prohibition (rating must be
    0) — may not be passed, each unless its `st_toggle` grants permission; the
    universal trait cap (5) holds every Background on BOTH sides of the lock unless a
    rule explicitly raises it; and, when the origin restricts WHICH Backgrounds it may
    take at all (`allowed_backgrounds` — the Sidereal ronin, p.100), anything outside
    that list is flagged. Blank rows are skipped: the editor adds an empty row for the
    player to fill in, and an unnamed row is not yet an illegal Background.
    """
    issues: list[Issue] = []
    if not post_lock:
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
        banned = {n.strip().lower() for n in budgets.banned_backgrounds}
        if banned:
            for bg in backgrounds:
                name = bg.name.strip()
                if name and name.lower() in banned:
                    issues.append(Issue(
                        code="background-banned", where=name,
                        message=f"{name.title()} is prohibited for this origin: "
                                f"{', '.join(sorted(n.title() for n in banned))}.",
                    ))
    for name, rule in budgets.background_rules.items():
        if post_lock and not rule.bind_post_lock:
            continue
        rating = background_rating(backgrounds, name)
        if not post_lock and rule.min_rating and rating < rule.min_rating:
            issues.append(Issue(
                code="background-below-minimum", where=name,
                message=f"{name.title()} is automatically {rule.min_rating} at character "
                        f"creation; this character has {rating}.",
            ))
        # The ceiling: a literal `max_rating`, or the Attribute-sum cap (Sidereal
        # Connections, Sidereals pp.106-108). Both are HARD ceilings — an error rather
        # than the bonus-point surcharge a soft cap produces — and both lift when the
        # rule's `st_toggle` grants permission. The Attribute-sum variant needs the
        # character; called without one it is skipped, the silent fallback.
        cap = None
        cap_is_attribute_sum = False
        if rule.max_rating_is_attribute_sum and character is not None:
            cap = sum(_chargen_source(character)[0].values())
            cap_is_attribute_sum = True
        elif rule.max_rating:
            cap = rule.max_rating
        if cap and rating > cap and not background_st_permitted(character, rule):
            if cap_is_attribute_sum:
                issues.append(Issue(
                    code="background-above-attribute-cap", where=name,
                    message=f"{name.title()} may not exceed {cap} for this character; "
                            f"this character has {rating}.",
                ))
            else:
                issues.append(Issue(
                    code="background-above-origin-cap", where=name,
                    message=f"{name.title()} may not exceed {cap} for this origin; "
                            f"this character has {rating}.",
                ))
        # A BAR (rating must be 0) — mortals and Artifact/Manse, core p.103 — lifted
        # by ST permission. Chargen only: there is no post-lock purchase to bar.
        if not post_lock and rule.barred and rating > 0 \
                and not background_st_permitted(character, rule):
            issues.append(Issue(
                code="background-barred", where=name,
                message=f"{name.title()} may not be purchased for this origin without "
                        f"Storyteller permission; this character has {rating}.",
            ))
        if not post_lock and rule.requires and rating > 0:
            have = background_rating(backgrounds, rule.requires)
            if have < rule.requires_rating:
                issues.append(Issue(
                    code="background-requires", where=name,
                    message=f"{name.title()} requires {rule.requires.title()} "
                            f"{rule.requires_rating}+; this character has {have}.",
                ))
    # The universal trait cap (5), enforced here now that `BackgroundEntry.rating` no
    # longer carries it structurally — a hand-edited or older save could otherwise hold
    # an Artifact 10 with no rule to flag it. Every Background is held to it on BOTH
    # sides of the lock, EXCEPT where a rule explicitly raises it (Mountain Folk
    # Artifact ≤10, whose higher ceiling the loop above enforces). A rule that caps
    # LOWER (Backing ≤2) is chargen-only and falls away post-lock, so post-lock only
    # this cap holds it. A rule that caps a TOTAL (Sidereal Connections) is skipped
    # here — its own check above reads the summed rating against the attribute total.
    for bg in backgrounds:
        key = (bg.name or "").strip().lower()
        if not key:
            continue
        rule = budgets.background_rules.get(key)
        governs = rule is not None and (not post_lock or rule.bind_post_lock)
        # A rule may RAISE the universal cap; it may never REMOVE it. The earlier
        # version skipped this check whenever a rule merely EXISTED, which let the
        # rules that state no maximum at all — Alchemical Class (`min_rating`),
        # Alchemical Backing (`requires`), Illuminated Illumination (`min_rating`) —
        # lose the cap at chargen while keeping it post-lock.
        ceiling = (rule.max_rating if governs and rule.max_rating > merits.DOT_MAX
                   else merits.DOT_MAX)
        # Where the rule states its own LITERAL ceiling, that check has already spoken
        # (an above-origin-cap issue) and saying it twice for one row is noise.
        #
        # A TOTAL-cap rule is different and must NOT skip: `max_rating_is_attribute_sum`
        # reads `background_rating`, which SUMS every row sharing the name, so it has
        # nothing to say about one row. Sidereal Connections is capped at 5 per row like
        # every other Background (human's ruling 2026-08-12) while its printed total
        # binds across rows — two ceilings measuring two different things.
        if governs and rule.max_rating:
            continue
        if bg.rating > ceiling:
            issues.append(Issue(
                code="background-above-universal-cap", where=bg.name,
                message=f"{bg.name.title()} may not exceed {merits.DOT_MAX}; "
                        f"this character has {bg.rating}.",
            ))
    return issues


def background_st_permitted(character, rule) -> bool:
    """Whether THIS rule's Storyteller toggle lifts it for `character`.

    The toggle is the PER-CHARACTER `HouseRules` field named by `BackgroundRule.st_toggle`
    — R2's Sidereal Celestial Manse ≤3 and R3's mortal Artifact/Manse bar, both "without
    Storyteller permission". ONE read site, the `validate.foreign_charms_permitted`
    pattern: the UI never reaches into HouseRules for a name. `character` is optional —
    called without one, no permission, the rule binds. A toggle the field names but a
    HouseRules version lacks reads as False (graceful, like any dangling reference)."""
    if character is None or not rule.st_toggle:
        return False
    hr = character.house_rules
    if hr is None:
        return False
    return bool(getattr(hr, rule.st_toggle, False))


def background_rating_cap(budgets, character, name, *, post_lock=False) -> int:
    """The highest rating the Background `name` may be set to for THIS character on
    THIS side of the lock — the single engine-side answer the rating controls take
    their ceiling from (ui/advantages.py hardcoded 5 in both until 2026-08-12, which
    made the Mountain Folk Artifact lift unrecordable).

    A rating above this errors in `background_issues`; a control that offered more
    would be the cap you can click past, which is not a ceiling. Layers, most
    restrictive first:
      * a `barred` rule (rating must be 0), unless its `st_toggle` grants permission;
      * the rule's own `max_rating` ceiling;
      * DOT_MAX, the universal trait cap (5).

    The Attribute-sum rule (Sidereal Connections) is deliberately NOT a layer here: it
    caps a TOTAL ("the total number of dots in Connections may not exceed" the sum,
    Sidereals pp.106-108), so the per-row control keeps the universal ceiling and
    `background_issues` enforces the total against the summed rating.

    Post-lock only the `bind_post_lock` rules' ceilings apply. Backgrounds are free
    story edits in play, so a chargen-only cap must NOT clamp the play control: a
    locked Unenlightened Mountain Folk can be given Backing 4 by the story even though
    he could not buy it at creation, and a mortal can be granted an artifact.
    """
    key = (name or "").strip().lower()
    rule = budgets.background_rules.get(key)
    if post_lock and not (rule and rule.bind_post_lock):
        return merits.DOT_MAX
    if rule is None:
        return merits.DOT_MAX
    if rule.barred and not background_st_permitted(character, rule):
        return 0
    if rule.max_rating and not background_st_permitted(character, rule):
        return rule.max_rating
    # The Attribute-sum rule (Sidereal Connections) is a TOTAL cap, not a per-row one:
    # the printed rule says "the total number of dots in Connections may not exceed"
    # the sum, and `background_rating` already sums duplicate rows for the check. The
    # row keeps the universal 5 like every other Background (human's ruling
    # 2026-08-12) and the total is `background_issues`' job — a row must never offer
    # the whole attribute sum as pips.
    return merits.DOT_MAX


def check_hearthstones(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The Hearthstone allowance on every Manse Background row (Savant and Sorcerer
    pp.66-67).

    The governing sentence is p.67: "The sum of the levels of all the Hearthstones
    produced can never exceed the level of the Manse." A Manse may be built to yield
    several stones rather than one (p.66), so the rule caps the TOTAL and not the count,
    and the Dragon-Blooded and Abyssal ladders add a ceiling on the largest single stone
    on top of that.

    PER ROW, not per character: two Manse rows are two Manses with two separate
    allowances, and summing them would let a Manse • and a Manse ••••• between them
    carry a level-5 stone on the wrong one.

    Runs on BOTH sides of the lock, following `check_artifacts` for the same reason it
    does — the allowance is keyed to a Background the story can raise or take away, so
    a chargen-only check would fall silent exactly when the cap started moving. That is
    also the human's ruling for this rule specifically (2026-08-12).

    The allowance comes from the BackgroundType, resolved through
    `background_catalogue_for` so a splat sees its OWN Manse variant — the six variants
    print six different allowances, and matching on the bare name would hand a
    Dragon-Blooded the corebook's linear one. A row whose name matches no catalogue
    entry (Backgrounds are free text) grows no stones, which is reported rather than
    ignored: it is the only way a stone can end up stranded on a row that cannot hold
    it, by renaming the row or flipping it to a Demesne after the fact.
    """
    by_name = {bg.name.strip().lower(): bg
               for bg in background_catalogue_for(ruleset, character)}
    issues: list[Issue] = []
    for bg in character.backgrounds:
        if not bg.hearthstones:
            continue
        held = artifacts.hearthstone_total(bg)
        where = bg.name or "Background"
        bg_type = by_name.get(bg.name.strip().lower())
        allowance = (None if bg.is_demesne
                     else artifacts.hearthstone_allowance(bg_type, bg.rating))
        if allowance is None:
            issues.append(Issue(
                code="hearthstone-without-manse",
                message=(f"{where} holds {len(bg.hearthstones)} Hearthstone(s) but "
                         f"produces none"
                         + (" — the row is marked as a Demesne" if bg.is_demesne
                            else "")),
                where=where))
            continue
        label = (f"{where} {bg.rating} ({allowance.tier_name})"
                 if allowance.tier_name else f"{where} {bg.rating}")
        if held > allowance.combined_max:
            issues.append(Issue(
                code="hearthstone-over-combined",
                message=(f"{label} allows {allowance.combined_max} level(s) of "
                         f"Hearthstone; {held} held"),
                where=where))
        if allowance.individual_max:
            for stone in bg.hearthstones:
                if stone.rating > allowance.individual_max:
                    issues.append(Issue(
                        code="hearthstone-over-individual",
                        message=(f"{label} allows no Hearthstone above level "
                                 f"{allowance.individual_max}; {stone.name} is level "
                                 f"{stone.rating}"),
                        where=where))
        if allowance.max_items and len(bg.hearthstones) > allowance.max_items:
            issues.append(Issue(
                code="hearthstone-over-count",
                message=(f"{label} allows {allowance.max_items} Hearthstone(s); "
                         f"{len(bg.hearthstones)} held"),
                where=where))
    return issues


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







# --------------------------------------------------------------------------- #
# Deadly Beastman Transformation Gifts (repeatable, multi-pick-per-purchase Charm)
# --------------------------------------------------------------------------- #











# --------------------------------------------------------------------------- #
# Chargen (not yet implemented — see module docstring)
# --------------------------------------------------------------------------- #











def _attr_bp_caste_favored(ruleset: RuleSet, character: Character, b, bp_costs,
                            attributes: dict) -> int:
    """Bonus points spent on Attributes under caste_favored mode: the three pools
    are assigned in FIXED order to the caste / favored / remaining sets, over-spend
    on the caste and favored sets is charged the discounted
    `attribute_caste_favored` rate, and the remaining set the flat `attribute` rate."""
    caste, favored, remaining = _caste_favored_attribute_sets(ruleset, character)
    pools = list(effective_attribute_pools(ruleset, character))

    def spend(group: set) -> int:
        return sum(attributes.get(a, b.attribute_base) - b.attribute_base for a in group)

    cf_rate = bp_costs.attribute_caste_favored
    return (max(0, spend(caste) - pools[0]) * cf_rate
            + max(0, spend(favored) - pools[1]) * cf_rate
            + max(0, spend(remaining) - pools[2]) * bp_costs.attribute)


























def unspent_budget_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Free chargen dots the character has NOT allocated, as non-blocking warnings.

    The engine's budget arithmetic is otherwise entirely one-sided: every domain
    computes `max(0, spend - budget)`, charges the overflow to bonus points and errors
    only if THAT exceeds the allowance. Nothing ever noticed a character who spent too
    LITTLE, so a completely blank sheet reported "✓ Legal" — visible on a mortal, whose
    lack of caste rules leaves nothing else to report, but true of every splat.

    Warnings, not errors (rules-authority call, 2026-07-30): an unfinished sheet is
    incomplete, not illegal, and the UI already treats severity="warning" as
    non-blocking. Covers Attributes, Abilities, Virtues and **Backgrounds**; bonus
    points are deliberately EXCLUDED — "BP are bonus for a reason", and a concept may
    legitimately not want them. Reads the frozen snapshot once locked, like all the
    other chargen accounting, so a locked sheet's warnings never drift.
    """
    b = effective_budgets(ruleset, character)
    (attributes, abilities, crafts, virtues, backgrounds, _specialties,
     charms, spells, *_rest) = _chargen_source(character)
    issues: list[Issue] = []

    def warn(domain: str, left: int, total: int) -> None:
        if left > 0:
            issues.append(Issue(
                code="unspent-chargen-dots", where=domain.lower(), severity="warning",
                message=f"{left} of {total} free {domain} dots are unspent.",
            ))

    # Attributes: pools are per-GROUP, so leftovers are counted per pool and summed —
    # spending all 13 in one category leaves the other two pools unspent, and both
    # that and the resulting overspend are worth saying.
    if b.attribute_mode == "caste_favored":
        groups = _caste_favored_attribute_sets(ruleset, character)   # caste/favored/rest
        spends = [sum(attributes.get(a, b.attribute_base) - b.attribute_base for a in g)
                  for g in groups]
        pools = list(effective_attribute_pools(ruleset, character))                              # FIXED order here
    else:
        assignment = attribute_pool_assignment(ruleset, character, b, attributes)
        spends = [spend for _cat, spend, _pool in assignment]
        pools = [pool for _cat, _spend, pool in assignment]
    warn("Attribute", sum(max(0, p - s) for s, p in zip(spends, pools)), sum(pools))

    # Abilities/Virtues/Backgrounds: one flat pool each, and only dots at or below the
    # pre-BP cap count toward it — the same `within` arithmetic bonus_point_breakdown
    # uses, so the two can never disagree about what "spent from the pool" means. The
    # two-pool Mountain Folk shape (CH6 p.230) asks two_pool_ability_accounting, the
    # single read site, so the warning and the billing cannot drift.
    if b.ability_favored_dots:
        ability_within, _bp = two_pool_ability_accounting(b, character, abilities, crafts)
        _total = b.ability_dots + b.ability_favored_dots
        warn("Ability", _total - ability_within, _total)
    else:
        ability_within = sum(min(rating, b.ability_cap_pre_bp)
                             for _ab, rating in _ability_slots(abilities, crafts))
        warn("Ability", b.ability_dots - ability_within, b.ability_dots)

    virtue_within = sum(max(0, min(r, b.virtue_cap_pre_bp) - b.virtue_base)
                        for r in virtues.values())
    warn("Virtue", b.virtue_dots - virtue_within, b.virtue_dots)

    bg_within, _above = background_pool_spend(ruleset, character, b, backgrounds)
    warn("Background", background_dots_budget(b, character) - bg_within,
         background_dots_budget(b, character))

    # Fetters, for the splats that have them. Same arithmetic as the pools above.
    if b.fetter_dots:
        fetter_within = sum(min(f.rating, b.fetter_cap_pre_bp)
                            for f in character.fetters)
        warn("Fetter", b.fetter_dots - fetter_within, b.fetter_dots)

    # Charms — the one chargen pool counted in PICKS rather than dots, which is why
    # it does not go through `warn`. A heroic ghost gets six Arcanoi and nothing said
    # so: every other domain warned about its leftovers and this one never did, so a
    # sheet with no magic at all still read as merely "incomplete elsewhere".
    #
    # The pool is shared with Spells (p.100) and the Immaculate path swaps its size
    # (DB p.151), both exactly as `bonus_point_breakdown` prices it — same two
    # expressions, so the warning and the billing cannot drift. Skipped for the slot
    # economy: an Alchemical buys Slots, not picks, and the picker already shows slot
    # occupancy. `charm_noun` makes the message say Arcanoi to a ghost.
    if b.charm_count and not uses_charm_slots(ruleset, character):
        pool = (b.immaculate_charm_count
                if _immaculate_path(ruleset, charms, character.exalt_type)
                else b.charm_count)
        taken = charm_pick_count(ruleset, character) + sum(
            1 for sid in spells if ruleset.spells.get(sid) is not None)
        left = pool - taken
        if left > 0:
            noun = ruleset.exalt_for(character.exalt_type).charm_noun
            issues.append(Issue(
                code="unspent-chargen-dots", where="charms", severity="warning",
                message=f"{left} of {pool} free {noun} are unspent.",
            ))

    return issues


def optional_favored_ability_open(ruleset: RuleSet, character: Character) -> bool:
    """Whether core p.103's optional Favoured Ability is actually in play: the ORIGIN
    must allow it and the Storyteller must have switched it on. Both halves matter —
    the page offers it to "heroic mortals" only, so an ordinary mortal does not get one
    however the table's toggle is set, and an Exalt's origin never allows it at all.

    Reads the house rules through `chargen_house_rules`, so a locked sheet keeps the
    answer it was built with even if the table later changes its mind."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return (b.optional_favored_ability
            and chargen_house_rules(character).mortal_favored_ability)


def favored_ability_count(ruleset: RuleSet, character: Character) -> int:
    """How many Favoured Abilities this character must pick — the budget's count, plus
    the one core p.103's optional rule grants a heroic mortal when it is in play."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    total = b.favored_count + (1 if optional_favored_ability_open(ruleset, character) else 0)
    # Prodigy grants "one additional Favored Ability for every time this Merit is
    # purchased", but "characters may not have more than five Favored Abilities in
    # total" (p.21) — which is exactly why the Merit is closed to the splats already at
    # that limit.
    extra = merits.merits_and_flaws_calc(ruleset, character).extra_favored_abilities
    return min(merits.PRODIGY_FAVORED_CAP, total + extra) if extra else total


def mortal_favored_ability_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The price of p.103's optional Favoured Ability: "the character can never have
    any other Ability rated higher than his Favored Ability. The Favored Ability must
    be equal to or greater than every other skill he possesses."

    Only meaningful while the rule is actually in play — an Exalt's Favoured Abilities
    carry no such ceiling ("Exalted do not suffer from this restriction")."""
    if not optional_favored_ability_open(ruleset, character):
        return []
    favored = list(character.favored_abilities)
    if not favored:
        return []
    best = max(character.abilities.get(f, 0) for f in favored)
    over = sorted(a for a, r in character.abilities.items()
                  if a not in favored and r > best)
    if not over:
        return []
    return [Issue(
        code="mortal-favored-not-highest", where=a.value,
        message=f"{a.value} ({character.abilities[a]}) is rated above the Favoured "
                f"Ability ({best}); a mortal's Favoured Ability must be equal to or "
                f"greater than every other Ability (core p.103).",
    ) for a in over]


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
    b = effective_budgets(ruleset, character)
    bp_costs = ruleset.bonus_costs_for(character.exalt_type, character.origin, character.upbringing)
    (attributes, abilities, crafts, virtues, backgrounds, specialties,
     charms, spells, combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, submodules, colleges, thaumaturgy, paths,
     favored_path, elemental_powers) = _chargen_source(character)

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
        attr_bp = sum(
            max(0, spend - pool) * (bp_costs.attribute_caste_favored if cat == caste_attr_category
                                     else bp_costs.attribute)
            for cat, spend, pool in attribute_pool_assignment(ruleset, character, b,
                                                              attributes)
        )

    # Dragon-King breed attribute bonuses (PG pp.167-174): the breed's free dots
    # stack ON TOP of the stored value, but each EFFECTIVE dot above 5 must be
    # bought with bonus points at the attribute rate (p.175: "Even after these
    # modifiers are applied, Dragon Kings cannot have any Attributes higher than 5
    # without spending bonus or experience points"). The 2026-08-06 "free past 5"
    # reading was a misunderstanding and is reversed; this charge plus the stored-5
    # range check in validate_chargen is the whole attribute rule. A Pterok's
    # stored Dexterity 5 reads as an effective 7 that costs (7 − 5) × 4 = 8 BP.
    caste_def = ruleset.castes.get(character.caste)
    breed_bonuses = (caste_def.breed_traits.attribute_bonuses
                     if caste_def and caste_def.breed_traits else {})
    for aname, bonus in breed_bonuses.items():
        if bonus:
            effective = attributes.get(aname, b.attribute_base) + bonus
            if effective > 5:
                attr_bp += (effective - 5) * bp_costs.attribute

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

    if b.ability_favored_dots:
        # TWO-POOL (Mountain Folk, CH6 p.230): the favored pool funds a Favored
        # Ability's dots beyond the free-pool cap, allocated player-favourably — see
        # two_pool_ability_accounting, the ONE read site this, the unspent warning and
        # the editor readout all share.
        _within, ability_bp = two_pool_ability_accounting(
            b, character, abilities, crafts, bp_costs)
    else:
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

        paid = dict(above_by_tier)            # above-cap dots always cost BP
        remaining = overflow
        for tier in ["both"] + order:         # 'both' is 0.5/dot, cheapest of all
            take = min(remaining, within_by_tier[tier])
            paid[tier] += take
            remaining -= take
            if not remaining:
                break

        # The 'both' tier is charged in bulk and rounds UP, matching how specialties
        # already handle a dots-per-point rate (rules-authority call: the page does
        # not say how an odd dot rounds).
        ability_bp = ((paid["both"] + per_point - 1) // per_point
                      + sum(paid[t] * flat_rate[t] for t in order))

    # --- Backgrounds: N free dots, pre-BP cap 3 (above-3 dot costs 2) --------- #
    # `background_rules` (empty for every splat but the Alchemical) can exempt a
    # Background from the cap and make its upper dots cost more than one pool dot each.
    bg_within, above_rates = background_pool_spend(ruleset, character, b, backgrounds,
                                                   bp_costs)
    bg_above_bp = sum(above_rates)
    bg_overflow = max(0, bg_within - background_dots_budget(b, character))
    bg_bp = bg_above_bp + bg_overflow * bp_costs.background

    # --- Virtues: 5 free dots over base 1, pre-BP cap 3 ----------------------- #
    # A Fae-Blooded's ATTUNED Virtue (Virtue Attunement, PG p.74) is priced at two
    # bonus points per dot instead of the splat's three. Attuned dots draw on the free
    # pool LAST (the player-favourable reading), so the discount lands on as many of
    # their priced dots as possible: the pool absorbs the non-attuned dots first, and
    # every attuned dot it cannot then hide is priced at the discounted rate.
    favored = merits.merits_and_flaws_calc(ruleset, character).favored_virtues
    v_within = v_above = attuned_within = attuned_above = 0
    for v, rating in virtues.items():
        within = max(0, min(rating, b.virtue_cap_pre_bp) - b.virtue_base)
        above = max(0, rating - b.virtue_cap_pre_bp)
        v_within += within
        v_above += above
        if v.value in favored:
            attuned_within += within
            attuned_above += above
    v_overflow = max(0, v_within - b.virtue_dots)
    # The free pool goes to the NON-attuned within-cap dots first; whatever is left
    # then hides attuned dots, and the remaining attuned ones are priced (and get
    # the discount): min(attuned_within, v_overflow) of the attuned within-cap dots.
    # The free_left bookkeeping keeps that exact when the non-attuned dots do not
    # themselves fill the pool.
    free_left = max(0, b.virtue_dots - (v_within - attuned_within))
    attuned_paid = attuned_above + max(0, attuned_within - free_left)
    virtue_bp = (v_above + v_overflow) * bp_costs.virtue - attuned_paid

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
            pick_costs.append(merits.adjust_spell_cost(
                ruleset, character,
                bp_costs.charm_favored_caste if occult_cf else bp_costs.charm))
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

    # --- Dragon-King Paths (PG p.176): own pool, favoured discount, above-3 ---- #
    # The same within/above/overflow shape as Colleges, with two DK differences: the
    # cheap/dear split is per-dot FAVOURED (a Path is favoured by breed element or by
    # `favored_path`, not by house), and the above-3 rate is DOUBLED ("Path | 5 (10
    # if the Path is being raised above 3)", "Breed Path | 4 (8 if raised above 3)").
    # Unused for every splat with `path_dots` 0, which is every non-Dragon-King.
    path_cap = b.path_cap_pre_bp
    path_cheap_within = path_dear_within = path_above_bp = 0
    for pr in paths:
        # The snapshot's favoured Path, not the live character's: once locked, the
        # snapshot is the chargen accounting source (decision 0003), and the choice
        # must not re-price creation if `character.favored_path` ever drifts.
        fav = paths_mod.path_is_favored(ruleset, character, pr.path_id,
                                        favored_path=favored_path)
        within = min(pr.rating, path_cap)
        above = max(0, pr.rating - path_cap)
        path_above_bp += above * (bp_costs.path_breed_above_3 if fav else bp_costs.path_above_3)
        if fav:
            path_cheap_within += within
        else:
            path_dear_within += within
    path_overflow = max(0, (path_cheap_within + path_dear_within) - b.path_dots)
    path_overflow_cheap = min(path_overflow, path_cheap_within)
    path_bp = (path_above_bp
               + path_overflow_cheap * bp_costs.path_breed
               + (path_overflow - path_overflow_cheap) * bp_costs.path)

    # --- Thaumaturgy: every purchase priced individually, no free pool -------- #
    # Unlike every domain above, thaumaturgy has no chargen allowance: "Thaumaturges
    # may spend their bonus points on any combination of these without limitation"
    # (p.113). So the total is simply the sum of the purchase prices — the free-pool
    # arithmetic that shapes the other domains has nothing to absorb here. Sciences
    # price at 0 because the source gives no rate; see ThaumPurchase.priced.
    thaum_purchases_cg = _thaum_purchases_from(ruleset, thaumaturgy)
    thaum_bp = sum(thaum_purchase_bp_costs(
        ruleset, character, thaum_purchases_cg,
        free_picks=magic_for_everyone_grant(ruleset, character)))

    # --- Fetters (ghosts only, E:Ab p.126-127) -------------------------------- #
    # Same `within`/`above` shape as Backgrounds: dots at or below the pre-BP cap come
    # out of the pool, dots above it are bonus points, and pool overflow is bonus
    # points too. 0 for every other splat, whose fetter list is empty and whose
    # `fetter_dots` budget is 0.
    #
    # There is deliberately no Passion line. Passions are derived from the Virtues and
    # cost nothing at any point (p.283) — see models.character.PassionEntry.
    f_within = sum(min(f.rating, b.fetter_cap_pre_bp) for f in character.fetters)
    f_above = sum(max(0, f.rating - b.fetter_cap_pre_bp) for f in character.fetters)
    f_overflow = max(0, f_within - b.fetter_dots)
    fetter_bp = (f_above + f_overflow) * bp_costs.fetter

    # --- Willpower / Essence -------------------------------------------------- #
    wp_bp = wp_purchased * bp_costs.willpower
    # Essence is usually linear (dot × rate); a splat whose BP table prices it by
    # DESTINATION instead (God-Blooded, p.50: Essence 2* = 5, Essence 3** = 15) sets
    # `essence_by_rating` and the exact-rating price wins.
    if bp_costs.essence_by_rating and essence in bp_costs.essence_by_rating:
        essence_bp = bp_costs.essence_by_rating[essence]
    else:
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
    # Paths, on the same terms: only for splats that have them (Dragon-Kings).
    if b.path_dots > 0 or paths:
        lines.insert(3, BonusPointLine(domain="Paths", points=path_bp))
    # Fetters, on the same terms: only for splats that have them (ghosts), so every
    # other breakdown is byte-identical to before.
    if b.fetter_dots > 0 or character.fetters:
        lines.insert(3, BonusPointLine(domain="Fetters", points=fetter_bp))
    # Thaumaturgy is cross-splat but optional for every splat, so the line appears
    # only once a character has bought something — a Solar who never touches it sees
    # the same breakdown as before. thaum_bp is 0 whenever the line is omitted.
    if thaumaturgy.arts or thaumaturgy.art_specialties or thaumaturgy.sciences \
            or thaumaturgy.rituals or thaumaturgy.formulas:
        lines.append(BonusPointLine(domain="Thaumaturgy", points=thaum_bp))
    # Elemental Powers (PG p.68), on the same terms: one flat line once held, and
    # absent entirely for every other origin/splat so their breakdowns are unchanged.
    elemental_bp = sum(
        ruleset.elemental_powers[pid].bp_cost
        for pid in elemental_powers if pid in ruleset.elemental_powers)
    if elemental_powers:
        lines.append(BonusPointLine(domain="Elemental Powers", points=elemental_bp))
    # Merits & Flaws. A MERIT is a spend at its printed point value; a FLAW is a
    # GRANT that raises the allowance rather than reducing the spend, which is why it
    # lands on `available` and not as a negative line — a negative line would let a
    # Flaw silently pay for an overspend elsewhere in the same total. Oathbound
    # Magic's grant is already net of its same-arena stacking reduction.
    merit_bp = merit_bonus_point_cost(ruleset, character)
    granted = merits.merits_and_flaws_calc(ruleset, character).bonus_point_grant
    if character.merits_flaws or merit_bp:
        lines.append(BonusPointLine(domain="Merits", points=merit_bp))
    total = sum(line.points for line in lines)
    # Inheritance (God-Blooded, p.61): the Background's rating adds bonus points on
    # top of the budget's flat pool — Thin blood +6 … Divine +30. Indexed by rating,
    # empty for every other splat (the term is then 0).
    inheritance_bp = 0
    if b.inheritance_bonus_points:
        rating = min(merits.inheritance_rating(character),
                     len(b.inheritance_bonus_points) - 1)
        inheritance_bp = b.inheritance_bonus_points[rating]
    return BonusPointBreakdown(lines=lines, total=total,
                               available=b.bonus_points + granted + inheritance_bp)


def elemental_powers_available(ruleset: RuleSet, character: Character) -> bool:
    """Whether the elemental-powers catalogue is open to this character at all — the
    Elemental-origin God-Blooded gate (PG p.68, "descendents of elementals draw on the
    innate powers of their heritage"). The UI reads this to decide whether the picker
    page exists; every requirement check starts from it too.

    The gate is CASTE-level, not just splat-and-origin: the retired Merit's printed
    restriction barred every heritage but god-blooded (`barred_castes`), and "Elemental"
    is only an origin option on the god-blooded row — so a hand-edited save with
    `caste="demon-blooded"` + `origin="Elemental"` must NOT open the catalogue. `origin`
    alone is not enough; a stray origin string could pass it."""
    return (character.exalt_type == "God-Blooded"
            and character.caste == "god-blooded"
            and character.origin == "Elemental")


def legal_elemental_powers(ruleset: RuleSet, character: Character) -> list[str]:
    """The Elemental Powers a heritage change leaves the character able to hold.
    The catalogue belongs to the Elemental origin alone (see elemental_powers_available),
    so any structural switch away from it orphans every held power — the picker tab
    vanishes, the BP breakdown keeps charging, and validation errors with no UI path to
    remove them. The editor reads this after a heritage/caste/origin switch and drops
    whatever it no longer authorizes (the same shape as default_camp_and_calling: the
    engine decides, the UI applies)."""
    return list(character.elemental_powers) if elemental_powers_available(ruleset, character) else []


def meets_elemental_power_requirements(ruleset: RuleSet, character: Character, power) -> bool:
    """Whether the character could legally learn `power` right now: Elemental origin,
    min Essence, and every Merit in `required_merits` held. The forward-looking
    counterpart of elemental_power_issues, used by the picker to decide which powers
    are selectable. Ownership is excluded exactly as meets_charm_requirements excludes
    it — the caller checks "already owned" separately."""
    if not elemental_powers_available(ruleset, character):
        return False
    if character.essence_rating < power.min_essence:
        return False
    held = merits.merit_ids_held(character)
    return all(mid in held for mid in power.required_merits)


def elemental_power_shortfalls(ruleset: RuleSet, character: Character, power) -> list[str]:
    """Human-readable reasons `power` is not learnable right now; empty when it is.
    Used by the picker for the button tooltip."""
    out = []
    if not elemental_powers_available(ruleset, character):
        out.append("only Elemental-origin God-Blooded may learn elemental powers")
    if character.essence_rating < power.min_essence:
        out.append(f"requires Essence {power.min_essence}")
    held = merits.merit_ids_held(character)
    for mid in power.required_merits:
        if mid not in held:
            definition = ruleset.merits_flaws.get(mid)
            out.append(f"requires the {definition.name if definition else mid} Merit")
    return out


def elemental_power_issues(ruleset: RuleSet, character: Character,
                           power_ids: list[str]) -> list[Issue]:
    """Legality of the character's elemental powers (PG p.68): an unknown id, an
    origin that bars them, Essence below minimum, or a missing required Merit.
    Mirrors merit_issues — structural only, and what a power DOES is descriptive
    text, not modelled mechanics (decision 0008)."""
    issues: list[Issue] = []
    for pid in power_ids:
        power = ruleset.elemental_powers.get(pid)
        if power is None:
            # Unknown ids are check_references' job (the same split as unknown-charm /
            # unknown-spell): this function only reports legality for RESOLVED powers,
            # so a deleted/renamed power surfaces exactly one issue.
            continue
        if not elemental_powers_available(ruleset, character):
            issues.append(Issue(
                code="elemental-power-wrong-origin", where=pid,
                message=f"{power.name} is restricted to Elemental-origin God-Blooded; "
                        f"this character is a {character.origin or 'blank'} "
                        f"{character.exalt_type}.",
            ))
        if character.essence_rating < power.min_essence:
            issues.append(Issue(
                code="elemental-power-low-essence", where=pid,
                message=f"{power.name} requires Essence {power.min_essence}; "
                        f"this character has Essence {character.essence_rating}.",
            ))
        held = merits.merit_ids_held(character)
        for mid in power.required_merits:
            if mid not in held:
                definition = ruleset.merits_flaws.get(mid)
                issues.append(Issue(
                    code="elemental-power-missing-merit", where=pid,
                    message=f"{power.name} requires the "
                            f"{definition.name if definition else mid} Merit.",
                ))
    return issues


def merit_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Legality of the character's Merits & Flaws (Player's Guide pp.120-122).

    Structural only — an unknown id, a missing prerequisite, a variable-cost entry
    with no valid tier, a repeat of a non-repeatable Merit, or a thaumaturges-only
    entry on a character who holds no thaumaturgy. What a Merit DOES is never checked
    here; that is engine.merits' job (decision 0011)."""
    issues: list[Issue] = []
    held: dict[str, int] = {}
    # "THAUMATURGES ONLY" asks whether the character holds any thaumaturgy at all;
    # read through the snapshot so a locked sheet keeps the answer it was built with.
    snap = character.chargen_snapshot
    thaum = (snap.thaumaturgy or ThaumaturgyState()) if snap else thaum_state(character)
    has_thaum = bool(thaum.arts or thaum.sciences or thaum.rituals or thaum.formulas
                     or thaum.art_specialties)
    # Read through the snapshot for the same reason: a purchase whose legality depends
    # on a Background rating must keep the answer the locked sheet was built with.
    backgrounds = snap.backgrounds if snap else character.backgrounds

    for purchase in character.merits_flaws:
        # A player-authored "Custom" row (2026-08-10) has no catalogue entry by
        # design — display-only, no mechanical effect. Nothing about it is checkable
        # here, so it is skipped entirely rather than reported as merit-unknown. The
        # discriminator is the EMPTY merit_id (set at creation, never edited by the
        # name input) — not custom_name, which the player can blank and must not
        # turn back into a merit-unknown error.
        if not purchase.merit_id:
            continue
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is None:
            issues.append(Issue(
                code="merit-unknown", where=purchase.merit_id,
                message=f"Merit {purchase.merit_id!r} is not in the rule set.",
            ))
            continue
        held[definition.id] = held.get(definition.id, 0) + 1

        if purchase.tier and exalt_type_barred_from_tier(definition, character.exalt_type,
                                                         purchase.tier):
            issues.append(Issue(
                code="merit-barred-splat-tier", where=definition.id,
                message=(f"{definition.name} at {purchase.tier!r} is not available to "
                         f"{character.exalt_type}; open options are "
                         f"{', '.join(merit_tiers_available(definition, character.exalt_type, character.caste))}."),
            ))
        # Against the menu THIS character prices on, not the generic one — a Sidereal
        # recording Lucky at 4 would otherwise pass validation and be worth 0 points.
        own_options = merit_cost_options(definition, character.exalt_type, character.caste)
        if definition.cost_options and purchase.tier not in own_options:
            issues.append(Issue(
                code="merit-bad-tier", where=definition.id,
                message=f"{definition.name} needs one of "
                        f"{sorted(own_options)}; got {purchase.tier!r}.",
            ))
        if definition.kind == "either" and purchase.taken_as not in ("merit", "flaw"):
            issues.append(Issue(
                code="merit-side-unchosen", where=definition.id,
                message=f"{definition.name} is printed as a Merit OR a Flaw "
                        f"{definition.cost_note}; record which side was taken.",
            ))
        if definition.exalt_types and character.exalt_type not in definition.exalt_types:
            issues.append(Issue(
                code="merit-wrong-splat", where=definition.id,
                message=f"{definition.name} is restricted to "
                        f"{', '.join(definition.exalt_types)}; this character is "
                        f"{character.exalt_type}.",
            ))
        if character.exalt_type in definition.barred_exalt_types:
            issues.append(Issue(
                code="merit-barred-splat", where=definition.id,
                message=f"{definition.name} is not available to "
                        f"{', '.join(definition.barred_exalt_types)}.",
            ))
        if character.caste in definition.barred_castes:
            caste = ruleset.castes.get(character.caste)
            issues.append(Issue(
                code="merit-barred-caste", where=definition.id,
                message=f"{definition.name} is not available to the "
                        f"{caste.label if caste else character.caste} caste.",
            ))
        if definition.required_origins and character.origin not in definition.required_origins:
            issues.append(Issue(
                code="merit-wrong-origin", where=definition.id,
                message=f"{definition.name} is restricted to "
                        f"{', '.join(definition.required_origins)}; this character "
                        f"is a {character.origin or 'blank'} {character.caste}.",
            ))
        for limit in definition.points_limits:
            points = merit_points(definition, purchase, character.exalt_type,
                                  character.caste)
            if limit.per_entry:
                # The limit measures ONE named artifact, not the character's holdings.
                # An unresolved key is reported rather than defaulted: choosing the
                # best artifact on the character's behalf would make an illegal
                # purchase legal without anyone deciding to.
                item = artifacts.find_item(character, purchase.artifact_key)
                if item is None:
                    issues.append(Issue(
                        code="merit-artifact-unchosen", where=definition.id,
                        message=f"{definition.name} must name which artifact it "
                                f"modifies; its point limit is the rating of that "
                                f"artifact.",
                    ))
                    continue
                if limit.measure == "acquisition_cost":
                    budgets = effective_budgets(ruleset, character)
                    have = artifacts.acquisition_cost(budgets, item.rating)
                    shown = f"the {have} Background point(s) {item.name} cost"
                else:
                    have, shown = item.rating, f"{item.name} {item.rating}"
            else:
                have = background_best(backgrounds, limit.background)
                shown = f"{limit.background} {have}"
            rating = have + limit.offset
            if limit.mode == "max" and points > rating:
                issues.append(Issue(
                    code="merit-points-above-background", where=definition.id,
                    message=f"{definition.name} may not be worth more than "
                            f"{max(0, rating)} point(s) at {shown}; "
                            f"this purchase is worth {points}.",
                ))
            elif limit.mode == "above" and points <= rating:
                issues.append(Issue(
                    code="merit-points-below-background", where=definition.id,
                    message=f"{definition.name} must exceed {shown}; "
                            f"this purchase is worth {points}.",
                ))
        for group in unmet_trait_prerequisites(character, definition, purchase,
                                               backgrounds):
            want = " or ".join(f"{r.trait} {r.rating}" for r in group)
            issues.append(Issue(
                code="merit-trait-prerequisite", where=definition.id,
                message=f"{definition.name} requires {want}.",
            ))
        # A structured `detail` (which Attribute category a forfeit comes from, which
        # Attribute Legendary Attribute raises) is a CLOSED set. Unset or off-list, the
        # effect silently does not happen — Legendary Attribute grants no cap at all,
        # and a forfeit falls back to Physical. Reported rather than defaulted.
        choices = merits.detail_choices(definition)
        if choices and purchase.detail.strip().title() not in choices:
            issues.append(Issue(
                code="merit-detail-unchosen", where=definition.id,
                message=(f"{definition.name} must name which of "
                         f"{', '.join(choices)} it applies to; got "
                         f"{purchase.detail or '(nothing)'!r}."),
            ))
        if definition.min_starting_essence:
            start = effective_budgets(ruleset, character).essence_start
            if start < definition.min_starting_essence:
                issues.append(Issue(
                    code="merit-starting-essence", where=definition.id,
                    message=(f"{definition.name} is only open to characters whose splat "
                             f"starts at Essence {definition.min_starting_essence} or "
                             f"more; {character.exalt_type} starts at {start}, so the "
                             f"Flaw would cost nothing and still pay its points."),
                ))
        if definition.thaumaturges_only and not has_thaum:
            issues.append(Issue(
                code="merit-thaumaturges-only", where=definition.id,
                message=f"{definition.name} is open to thaumaturges only; this "
                        f"character holds no Arts, Sciences, rituals or formulas.",
            ))

    for mid, count in held.items():
        definition = ruleset.merits_flaws[mid]
        if count > 1 and not definition.repeatable_by:
            issues.append(Issue(
                code="merit-repeated", where=mid,
                message=f"{definition.name} may only be taken once; found {count}.",
            ))
        # A repeatable entry may still be capped by a trait — "characters may not
        # purchase this Merit more times than their Occult rating" (p.17).
        if definition.max_purchases_from_trait:
            limit = trait_rating(character, definition.max_purchases_from_trait,
                                 backgrounds)
            if count > limit:
                issues.append(Issue(
                    code="merit-repeats-above-trait", where=mid,
                    message=f"{definition.name} may not be taken more times than "
                            f"{definition.max_purchases_from_trait} "
                            f"({limit}); found {count}.",
                ))
        # ...or by origin — Virtue Attunement is once for a commoner Fae-Blooded,
        # twice for a noble (PG p.74). An origin with no entry in the map is uncapped.
        if character.origin in definition.max_purchases_by_origin:
            limit = definition.max_purchases_by_origin[character.origin]
            if count > limit:
                issues.append(Issue(
                    code="merit-repeats-above-origin", where=mid,
                    message=f"{definition.name} may be taken at most {limit} time(s) "
                            f"as a {character.origin}; found {count}.",
                ))
        for pid in definition.prerequisites:
            if pid not in held:
                name = ruleset.merits_flaws[pid].name if pid in ruleset.merits_flaws else pid
                issues.append(Issue(
                    code="merit-prerequisite", where=mid,
                    message=f"{definition.name} requires {name}.",
                ))

    # Backgrounds a held entry caps or forbids (A6 — Innocuous' veiled tier, p.22).
    # Asked of engine.merits, so no Merit id is named here.
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if effects.background_caps or effects.barred_backgrounds:
        for bg in backgrounds:
            key = bg.name.strip().lower()
            if not key or bg.rating <= 0:
                continue
            if key in effects.barred_backgrounds:
                issues.append(Issue(
                    code="background-barred-by-merit", where=bg.name,
                    message=f"{bg.name} is closed to this character by a Merit or "
                            f"Flaw they hold.",
                ))
            cap = effects.background_caps.get(key)
            if cap is not None and bg.rating > cap:
                issues.append(Issue(
                    code="background-above-merit-cap", where=bg.name,
                    message=f"{bg.name} may not exceed {cap} for this character "
                            f"(a Merit or Flaw they hold caps it); rating is "
                            f"{bg.rating}.",
                ))
    return issues


def merit_bonus_point_cost(ruleset: RuleSet, character: Character) -> int:
    """Bonus points SPENT on Merits. Flaws cost nothing to take — their point value is
    a grant, accounted separately (see `MeritEffects.bonus_point_grant`), so only
    `kind == "merit"` rows are charged here.

    Every cost shape is resolved by `merit_points`, including the per-splat prices the
    general chapter is full of — hence passing the character's Exalt type."""
    total = 0
    # A Merit whose price another Merit changes (Holy Mien -> Priest). Asked of
    # engine.merits, so no Merit id is ever named here.
    overrides = merits.merits_and_flaws_calc(ruleset, character).merit_cost_overrides
    for purchase in character.merits_flaws:
        definition = ruleset.merits_flaws.get(purchase.merit_id)
        if definition is None:
            continue
        if effective_merit_kind(definition, purchase) != "merit":
            continue
        override = overrides.get(definition.id)
        if override is not None and purchase.tier in override:
            total += override[purchase.tier]
            continue
        total += merit_points(definition, purchase, character.exalt_type,
                              character.caste)
    return total


def effective_merit_kind(definition, purchase) -> str:
    """Whether THIS purchase counts as a Merit or a Flaw.

    Fixed by the catalogue for the single-sided majority. A `kind: "either"` entry —
    Mutation, Favor, Eternal Vow, each printed as "MERIT OR FLAW" — is the player's
    choice, recorded on the purchase. An either-entry with no choice recorded defaults
    to "merit" here so pricing never crashes; validate reports the missing choice
    separately rather than letting it pass unnoticed."""
    if definition.kind != "either":
        return definition.kind
    return purchase.taken_as if purchase.taken_as in ("merit", "flaw") else "merit"


def merit_cost_options(definition, exalt_type: str = "", caste: str = "") -> dict[str, int]:
    """The menu this character actually prices against — the ONE resolution order, so a
    dropdown can never offer an option the pricer will not honour.

    Caste outranks splat outranks the generic table, exactly as `merit_points` reads
    them. Lucky is why this is not just `definition.cost_options`: it is "1- TO 5-PT.
    MERIT, 1- TO 3-PT. FOR SIDEREALS", and reading the generic table offered a Sidereal
    a 4- and 5-point option that priced at 0 — visible in the dropdown, worth nothing.
    """
    by_caste = definition.cost_options_by_caste.get(caste or "")
    if by_caste:
        return dict(by_caste)
    by_splat = definition.cost_options_by_exalt_type.get(exalt_type or "")
    if by_splat:
        return dict(by_splat)
    return dict(definition.cost_options)


def merit_tiers_available(definition, exalt_type: str, caste: str = "") -> tuple[str, ...]:
    """The options of a menu-priced entry this splat may actually choose.

    Two things narrow the menu. `tier_barred_exalt_types` is Prodigy's, barred to four
    splats for the half that grants a Favored Ability while its "increased aptitude"
    half stays open to exactly those splats. `merit_cost_options` is Lucky's, where the
    splat gets a SHORTER menu rather than a differently-priced one. Returns () for an
    entry with no menu at all — callers should treat that as "no tier to choose", not
    as "nothing available".
    """
    return tuple(t for t in merit_cost_options(definition, exalt_type, caste)
                 if exalt_type not in definition.tier_barred_exalt_types.get(t, ()))


def exalt_type_barred_from_tier(definition, exalt_type: str, tier: str) -> bool:
    """Whether this splat is barred from one named option of a menu-priced entry."""
    return exalt_type in definition.tier_barred_exalt_types.get(tier, ())


def merit_available_to(definition, exalt_type: str, caste: str = "", *,
                       origin: str = "", starting_essence: int | None = None) -> bool:
    """Whether the catalogue opens this entry to this character at all.

    The printed restrictions only — splat allow-list, splat bar, caste bar, origin
    gate — which are inert catalogue DATA rather than effects, so no Merit id is named
    and `engine.merits` is not consulted. Prerequisites, tiers and "thaumaturges only"
    are NOT checked here: those depend on the rest of the sheet and change as it is
    built, so hiding an entry for them would make the dropdown flicker.

    Shares its three conditions with the `merit-wrong-splat` / `merit-barred-splat` /
    `merit-barred-caste` issues above, so a UI that filters on this can never offer
    something validation would immediately reject.
    """
    if definition.exalt_types and exalt_type not in definition.exalt_types:
        return False
    if exalt_type in definition.barred_exalt_types:
        return False
    if caste and caste in definition.barred_castes:
        return False
    if definition.required_origins and origin not in definition.required_origins:
        return False
    # A splat-level floor on starting Essence. Optional because not every caller has
    # the budgets to hand; when it is not supplied the entry is NOT hidden, so a
    # missing argument can only ever be permissive — validation still reports it.
    if (starting_essence is not None and definition.min_starting_essence
            and starting_essence < definition.min_starting_essence):
        return False
    # Barred at every option of its own menu = barred outright. Derived rather than
    # duplicated, so a per-tier bar can never disagree with the whole-entry one.
    if definition.cost_options and not merit_tiers_available(definition, exalt_type):
        return False
    return True


def attribute_pool_assignment(ruleset: RuleSet, character: Character, b, attributes
                              ) -> list[tuple[str, int, int]]:
    """[(category, spend, pool)] for category-mode splats — which of the 8/6/4 pools
    each Attribute category gets, and how many dots were spent against it.

    The pools are matched to categories BY SPEND, not declared: the biggest spend takes
    the biggest pool. That is why Diminished Attributes cannot be applied as a budget
    delta the way Callous and Unskilled are — the forfeit has to come off the pool its
    category actually receives, which is only known once the matching is done. So the
    matching happens first, on the character's real spends, and the forfeit is taken
    off the pool afterwards.

    A consequence the human accepted explicitly (2026-07-30): forfeiting dots lowers a
    category's spend, which can drop it to a smaller pool, and that reshuffle can cost
    bonus points elsewhere. "If BP need be consumed because of how the pools change,
    then that's what happens."
    """
    forfeits = merits.merits_and_flaws_calc(ruleset, character).forfeited_attribute_dots
    cat_spends = sorted(
        ((cat, sum(attributes[a] - b.attribute_base for a in attrs))
         for cat, attrs in ATTRIBUTE_CATEGORIES.items()),
        key=lambda cs: cs[1], reverse=True,
    )
    pools = sorted(effective_attribute_pools(ruleset, character), reverse=True)
    return [(cat, spend, max(0, pool - forfeits.get(cat, 0)))
            for (cat, spend), pool in zip(cat_spends, pools)]


WITHHELD_CHARM_TARGET = "charms_withheld"

# Permanent Resonance (Death's Taint) moves on the XP ledger like a curse, but with its
# own prices in each direction — free to gain, five to shed — so it needs a target the
# audit can recognise. `_expected_cost` must test this BEFORE its general "a reduction
# is free" rule, which would otherwise price the shed at 0 and report a mismatch on
# every later validation.
PERMANENT_RESONANCE_TARGET = "limit_permanent"


def withheld_charm_credits(ruleset: RuleSet, character: Character) -> tuple[int, int]:
    """(granted, remaining) chargen Charm picks banked for XP-free use after the lock.

    Weak Essence lets a new Exalt "withhold up to five Charms in reserve … Withheld
    Charms waive their experience cost" (p.41), because a character pinned at Essence 1
    cannot qualify for enough Charms to spend a full chargen budget.

    NOTHING new is stored. How many were withheld is the unspent remainder of the
    chargen Charm budget — the snapshot already records what was taken — capped by the
    Flaw's own ceiling:

        granted = min(charm_credits_max, charm_count − picks taken)

    which is the human's rule ("keep the free Charms at 5; if more than five Charms are
    selected during chargen, subtract the number over") stated so it holds for any
    splat's budget rather than only Solar's 10. Banking can never yield MORE Charms than
    the character's ordinary budget: it defers picks, it does not add them.

    Redemptions are counted straight off the append-only XP log, so the pair always
    reconciles with what was actually spent.
    """
    ceiling = merits.merits_and_flaws_calc(ruleset, character).charm_credits_max
    if not ceiling:
        return 0, 0
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    taken = len(chargen_charm_picks(ruleset, character))
    granted = max(0, min(ceiling, b.charm_count - taken))
    redeemed = sum(1 for e in character.xp_log if e.target == WITHHELD_CHARM_TARGET)
    return granted, max(0, granted - redeemed)


def effective_budgets(ruleset: RuleSet, character: Character):
    """The character's chargen budgets, reduced by any trait-forfeit Flaw they hold.

    Four Flaws (PG pp.35-36) pay bonus points for free chargen dots GIVEN UP rather
    than for a disadvantage suffered — Callous trades Virtue dots, Unskilled Ability
    dots, Weak-Willed permanent Willpower, Diminished Attributes Attribute dots. The
    human's framing (2026-07-30) is that this is a budget delta and nothing more: a
    Callous character who sold two Virtue dots has a Virtue budget of 3 rather than 5,
    and every existing over-spend check then does the real work unchanged.

    The printed budget stays the one in `data/`; this returns a COPY. Callers that want
    to show the player what they gave up can diff the two.

    Diminished Attributes is deliberately NOT applied here: `attribute_pools` are
    matched to categories by spend rather than declared, so the forfeit has to be taken
    off the pool that its category actually receives, at the point the two are zipped.
    `MeritEffects.forfeited_attribute_dots` carries it; nothing consumes it yet.

    A budget may also be ENLARGED the same way (A6): Heir Apparent's inheritance adds
    Background dots. Same delta, opposite sign — that symmetry is why it belongs here
    rather than anywhere the Background pool is read.
    """
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    effects = merits.merits_and_flaws_calc(ruleset, character)
    if not (effects.forfeited_ability_dots or effects.forfeited_virtue_dots
            or effects.bonus_background_dots):
        return b
    return b.model_copy(update={
        "ability_dots": max(0, b.ability_dots - effects.forfeited_ability_dots),
        "virtue_dots": max(0, b.virtue_dots - effects.forfeited_virtue_dots),
        "background_dots": b.background_dots + effects.bonus_background_dots,
    })


def merit_points(definition, purchase, exalt_type: str = "", caste: str = "") -> int:
    if definition.variable_cost:
        return max(0, purchase.points)
    # A two-sided entry may price each side differently (Eternal Vow: 3 as a Merit,
    # 1 as a Flaw), and that outranks every other shape.
    if definition.cost_by_kind:
        side = effective_merit_kind(definition, purchase)
        if side in definition.cost_by_kind:
            return definition.cost_by_kind[side]
    options = merit_cost_options(definition, exalt_type, caste)
    if options:
        return options.get(purchase.tier, options.get("", 0))
    return definition.cost


def pool_requires_unlocking(ruleset: RuleSet, character: Character) -> bool:
    """Whether the splat's Essence pool exists only after a Merit unlocks it — the
    God-Blooded's (Awakened Essence, PG p.66; the per-heritage formula sits on the
    caste's heritage_traits, not on the ExaltDefinition) and the mortal's (Essence
    Awareness / Essence Mastery). True exactly when the splat has no NATIVE pool and
    some unlocked spec exists to replace the empty one. One read site, shared by the
    chargen gate (magic_gate_issues) and the advancement-side refusals, so the two
    cannot disagree about which splats are gated."""
    exalt = ruleset.exalt_for(character.exalt_type)
    if exalt.essence.personal_essence_coeff or exalt.essence.personal_willpower_coeff:
        return False                       # a native pool needs no unlocking
    caste = ruleset.castes.get(character.caste)
    if caste is not None and caste.heritage_traits is not None \
            and caste.heritage_traits.unlocked_essence is not None:
        return True
    return exalt.unlocked_essence is not None


def magic_gate_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A splat whose Essence pool must be UNLOCKED (see `pool_requires_unlocking` —
    the God-Blooded's pool comes from the Awakened Essence Merit, PG p.66) may not
    hold Charms, spells, or Essence above its start until the pool is unlocked:
    p.49, "Only God-Blooded with the Awakened Essence Merit may purchase or increase
    magical Traits."

    Mortals are deliberately skipped (`charms_available` False) — their bars already
    live in charm_matches_splat and essence_start_cap, and this would double-report
    the same Charm. God-Blooded hold Charms freely once unlocked (charms_available
    True), so this gate is what stops an Awakened-Essence-less build from keeping the
    seven-BP Charms. Mirrors the advancement-side refusal in learn_charm/learn_spell."""
    exalt = ruleset.exalt_for(character.exalt_type)
    if not pool_requires_unlocking(ruleset, character) or not exalt.charms_available:
        return []
    if merits.merits_and_flaws_calc(ruleset, character).essence_pool_unlocked:
        return []
    b = ruleset.budgets_for(character.exalt_type, character.origin,
                            character.upbringing)
    issues: list[Issue] = []
    if list(charm_picks(ruleset, character)):
        issues.append(Issue(
            code="magic-requires-awakened-essence", where="charms",
            message=f"{exalt.label} may not purchase Charms without the Awakened "
                    "Essence Merit (PG p.49).",
        ))
    if character.spells:
        issues.append(Issue(
            code="magic-requires-awakened-essence", where="spells",
            message=f"{exalt.label} may not learn spells without the Awakened Essence "
                    "Merit (PG p.49).",
        ))
    if character.essence_rating > b.essence_start:
        issues.append(Issue(
            code="magic-requires-awakened-essence", where="essence",
            message="Essence above the starting rating requires the Awakened Essence "
                    "Merit (PG p.48).",
        ))
    return issues


def heritage_origin_issues(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A heritage that keys off the origin axis must actually choose one of its
    options, and the value must BE one of them. Two heritages key off it: the
    Half-Caste's parent Exalt type (p.47: "learn the Charms of their parents") and
    the Fae-Blooded's Noble/Commoner (the nobility axis the powers on pp.73-79 gate
    on, human 2026-08-02). Without one the heritage is half-formed — a Half-Caste
    with no parent learns nothing, a Fae-Blooded with no nobility cannot be gated.
    A value from ANOTHER heritage is just as broken (a Fae-Blooded carrying a
    "Solar" parent), and is reported distinctly so the stale choice is visible
    rather than merely fatal in the editor."""
    caste = ruleset.castes.get(character.caste)
    if caste is None or caste.heritage_traits is None \
            or not caste.heritage_traits.origin_options:
        return []
    options = list(caste.heritage_traits.origin_options)
    if character.origin in options:
        return []
    if not character.origin:
        return [Issue(
            code="heritage-requires-origin", where="origin",
            message=f"A {caste.label} must choose an origin "
                    f"({', '.join(options)}).",
        )]
    return [Issue(
        code="heritage-foreign-origin", where="origin",
        message=f"{character.origin!r} is not a {caste.label} origin; "
                f"choose one of {', '.join(options)}.",
    )]


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
    b = effective_budgets(ruleset, character)
    (attributes, abilities, crafts, virtues, backgrounds, _specialties,
     charms, spells, _combos, ox_body, essence, wp_purchased,
     beastman_gifts, arrays, _submodules, colleges, thaumaturgy, paths,
     _favored_path, _elemental_powers) = _chargen_source(character)

    # Backgrounds that carry mechanics (Alchemical Class/Backing, CH2 p.65-69). No-op
    # for every splat whose Backgrounds are purely narrative. The character goes in —
    # the Attribute-sum cap (Sidereal Connections) and the PER-CHARACTER ST toggles
    # both read it, and an omitted character silently skips them (the house bug).
    issues += background_issues(b, backgrounds, character)

    # Thaumaturgy: Occult gates on Arts, aspects and rituals; per-Science ceilings.
    # No-op for a character who has bought none, which is every character until the
    # feature is used.
    issues += thaumaturgy_issues(ruleset, character, thaumaturgy)
    issues += thaumaturgy_chargen_issues(ruleset, character, thaumaturgy)

    cf = _caste_favored(ruleset, character)
    if cf is None:
        # A splat with NO castes in the RuleSet is casteless BY DESIGN, not
        # mis-configured: mortals "do not select a caste" (core p.103). Only report a
        # missing caste for a splat that actually has some to choose from, or every
        # mortal sheet carries a permanent spurious error.
        if splat_has_castes(ruleset, character.exalt_type):
            issues.append(Issue(
                code="unknown-caste", where=str(character.caste),
                message=f"Caste {character.caste} is not in the RuleSet; "
                        "caste/favoured checks skipped.",
            ))
        # A casteless splat still HAS a Favoured set — normally empty, but core p.103's
        # optional rule gives a heroic mortal one. Carry it through rather than
        # discarding it, or the count below can never be checked for them.
        caste_abilities, favored = set(), set(character.favored_abilities)
        expected = favored_ability_count(ruleset, character)
        if len(favored) != expected:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {expected} Favoured abilities, found {len(favored)}.",
            ))
        for ab in sorted(favored, key=lambda a: a.value):
            # Craft is per-focus (core p.136): a character with any Craft focus has
            # Craft dots, so read through ability_rating, not the flat abilities map.
            if ability_rating(character, ab) < 1:
                issues.append(Issue(
                    code="favored-needs-dot", where=ab.value,
                    message=f"Favoured ability {ab.value} must have at least 1 dot.",
                ))
        issues += mortal_favored_ability_issues(ruleset, character)
    else:
        caste_abilities, favored = cf
        # Favoured: exactly favored_ability_count, all distinct from Caste, >=1 dot
        # each. The count is not b.favored_count directly because Prodigy grants extra
        # Favoured Abilities to the splats not already at the five-Ability limit.
        expected_favored = favored_ability_count(ruleset, character)
        if len(favored) != expected_favored:
            issues.append(Issue(
                code="favored-count",
                message=f"Expected {expected_favored} Favoured abilities, "
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
            # Craft is per-focus (core p.136): a character with any Craft focus has
            # Craft dots, so read through ability_rating, not the flat abilities map.
            if ability_rating(character, ab) < 1:
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
    # The universal ceiling is 5; a Merit or Flaw may move it for one named Attribute
    # (Legendary Attribute raises, Disfigured lowers Appearance). Read from
    # MeritEffects rather than branching on an entry, per decision 0011.
    mf_caps = merits.merits_and_flaws_calc(ruleset, character)
    for name, attr in attributes.items():
        # The origin's own ceiling (Enlightened Mountain Folk 7; the Unenlightened's
        # Intelligence 2, CH6 p.230) is the DEFAULT the Merit machinery raises or
        # lowers from — an absent origin cap is the universal 5.
        origin_cap = b.attribute_caps.get(name.value, b.attribute_cap or merits.DOT_MAX)
        cap = mf_caps.attribute_caps.get(name.value, origin_cap)
        # A Flaw's ceiling can sit BELOW the normal chargen floor — Disfigured at four
        # points is "an Appearance of 0", and the free dot every Attribute starts with
        # is exactly what it takes away. So the floor follows the ceiling down. An
        # origin's FLOOR (Enlightened Mountain Folk: "no Attribute ... lower than
        # three", CH6 p.230) raises it — but must still follow a Flaw-lowered ceiling
        # below itself, or a Disfigured Enlightened Jadeborn gets an unsatisfiable
        # "3-0" range.
        low = min(b.attribute_min or b.attribute_base, cap)
        if not (low <= attr <= cap):
            span = f"exactly {cap}" if low == cap else f"{low}-{cap}"
            issues.append(Issue(
                code="attribute-range", where=name.value,
                message=f"Attribute {name.value} = {attr}; must be {span} at creation.",
            ))

    # Dragon-King breed attribute bonuses (PG pp.167-174): free dots ON TOP of the
    # stored value — they do not consume the pools, and the EFFECTIVE total may pass
    # 5 (a Pterok's stored Dexterity 5 reads as an effective 7), but each effective
    # dot above 5 is bought with bonus points at the attribute rate, charged in
    # bonus_point_breakdown. p.175's "cannot have any Attributes higher than 5
    # without spending bonus or experience points" is read against the effective
    # value — the 2026-08-06 "free past 5" reading was a misunderstanding and is
    # reversed. The stored 5-ceiling (the range check above) is the trait cap Essence
    # (max(5, Essence)); at chargen Essence 2/3/5 that is 5, so no stored dot above 5
    # exists here to gate. Past 5 is the post-lock XP path at Essence 6 (see
    # raise_attribute), and effective past 5 is BP-bought, not free.
    #
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
    # Group-sum floors — the Mountain Folk Artisan's "•• divided among Craft
    # Abilities" (CH6 p.230), where the SUM over a set of Abilities (each per-focus
    # Craft counting separately, via _ability_slots) must reach the rating. Distinct
    # from the per-ability OR floors above.
    caste_groups = ([] if b.ignore_caste_min_abilities
                    else (caste_def.required_min_ability_groups if caste_def else []))
    for req in list(b.required_min_ability_groups) + list(caste_groups):
        total = sum(rating for ab, rating in _ability_slots(abilities, crafts)
                    if ab in req.abilities)
        if total < req.rating:
            names = " + ".join(sorted(a.value for a in req.abilities))
            issues.append(Issue(
                code="required-min-ability-group", where=names,
                message=f"This origin requires at least {req.rating} dot(s) total "
                        f"divided among {names}; has {total}.",
            ))
    virtue_cap = (mf_caps.virtue_cap if mf_caps.virtue_cap is not None
                  else merits.DOT_MAX)
    for v, rating in virtues.items():
        if not (b.virtue_base <= rating <= virtue_cap):
            issues.append(Issue(
                code="virtue-range", where=v.value,
                message=f"Virtue {v.value} = {rating}; must be "
                        f"{b.virtue_base}-{virtue_cap} at creation.",
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

    # --- Dragon-King Paths (PG p.175-177): reference, favour, Essence gate ----- #
    # Paths are a rated Advantage with their own pool. A Dragon King may not start a
    # Path above the pre-BP cap, must put `path_min_breed_favored` dots in Breed or
    # Favoured Paths ("at least 3 must be from Favored or Breed Paths"), may not
    # exceed the Essence gate, and the chosen Favoured Path must not already be one
    # of the breed's two. The gate resolves against the CHARGEN Essence (snapshot or
    # live pre-lock), never `essence_start` — a BP-bought Essence raise lifts it.
    path_max = b.path_max_by_essence.get(essence, 0)
    favored_dots = 0
    for pr in paths:
        path = ruleset.paths.get(pr.path_id)
        if path is None:
            issues.append(Issue(
                code="path-unknown", where=pr.path_id,
                message=f"Path {pr.path_id} is not in the RuleSet.",
            ))
            continue
        if not (0 <= pr.rating <= 6):
            issues.append(Issue(
                code="path-range", where=pr.path_id,
                message=f"Path {path.name} = {pr.rating}; must be 0-6 at creation.",
            ))
        if path_max and pr.rating > path_max:
            issues.append(Issue(
                code="path-essence-cap", where=pr.path_id,
                message=f"{path.name} = {pr.rating}; at Essence {essence} a Dragon King "
                        f"cannot develop a Path above {path_max}.",
            ))
        if paths_mod.path_is_favored(ruleset, character, pr.path_id):
            favored_dots += pr.rating
    if b.path_dots > 0 and favored_dots < b.path_min_breed_favored:
        issues.append(Issue(
            code="path-min-breed-favored",
            message=f"At least {b.path_min_breed_favored} Path dots must be in Breed or "
                    f"Favoured Paths; only {favored_dots} are.",
        ))
    if character.favored_path:
        fp = ruleset.paths.get(character.favored_path)
        if fp is None:
            issues.append(Issue(
                code="favored-path-unknown", where=character.favored_path,
                message=f"Favoured Path {character.favored_path} is not in the RuleSet.",
            ))
        elif fp.element and fp.element == paths_mod.breed_element(ruleset, character):
            issues.append(Issue(
                code="favored-path-is-breed-path", where=character.favored_path,
                message=f"{fp.name} is one of your breed's Paths; the chosen Favoured "
                        "Path must be one of the other eight.",
            ))

    # --- Essence-gated trait ceilings + required Virtues (Dragon-Kings) ------- #
    # p.177 "Maximum Intelligence and Path Level": Intelligence caps at 1/3/5/6 by
    # Essence (binds at chargen: modern Essence 2 → Int ≤ 3), and row 6 lets a Dragon
    # King raise Abilities, Virtues and Paths to 6. The Ability half is already
    # delivered post-lock by elder.trait_ceiling and needs no chargen check; Virtue-6 is
    # a post-lock unlock (row 6 only), and the ≥1-Valor floor ("at least 1 of which
    # must be put into Valor", p.175) is a required-virtue floor. All no-op for every
    # splat that authors none of these tables.
    int_cap = b.intelligence_max_by_essence.get(essence, 0)
    if int_cap and attributes[AttributeName.INTELLIGENCE] > int_cap:
        issues.append(Issue(
            code="intelligence-essence-cap",
            message=f"Intelligence = {attributes[AttributeName.INTELLIGENCE]}; at "
                    f"Essence {essence} a Dragon King's Intelligence cannot exceed "
                    f"{int_cap}.",
        ))
    virt_cap = b.virtue_max_by_essence.get(essence, 0)
    for vname, rating in virtues.items():
        if virt_cap and rating > virt_cap:
            issues.append(Issue(
                code="virtue-essence-cap", where=vname.value,
                message=f"{vname.value.title()} = {rating}; at Essence {essence} a "
                        f"Dragon King's Virtues cannot exceed {virt_cap}.",
            ))
        need = b.required_virtue_dots.get(vname, 0)
        if need and rating < need:
            issues.append(Issue(
                code="required-virtue-dots", where=vname.value,
                message=f"Dragon Kings must put at least {need} dot in "
                        f"{vname.value.title()}; it is {rating}.",
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

    # --- Mountain Folk Pattern access (CH6 pp.230-231, 244) ------------------- #
    # Jadeborn Charms live in five Patterns (Foundation / Worker / Warrior / Artisan /
    # Enlightened). Unenlightened "can only learn the Charms of their own Caste Pattern
    # or the Foundation Pattern"; Enlightened receive six Charms "no more than three of
    # which may come from the Pattern of another caste". An Enlightened character may
    # learn ANY Pattern (Foundation + Enlightened + own-caste don't count toward the
    # three); only the two OTHER castes' Patterns do. Also the origin/caste coupling:
    # "All of the Artisan Caste are Enlightened" — an Unenlightened Artisan is illegal.
    if ruleset.exalt_for(character.exalt_type).id == "Mountain-Folk":
        if character.caste == "artisan" and character.origin == "unenlightened":
            issues.append(Issue(
                code="artisan-must-be-enlightened",
                message="All Artisans are Enlightened (CH6 p.230); an Unenlightened "
                        "character cannot take the Artisan Caste.",
            ))
        own_pattern = character.caste           # worker / warrior / artisan
        # The Unenlightened bar (own Caste Pattern + Foundation only) is a LIFETIME
        # rule — p.244 states it as ACCESS, not chargen — so it lives in
        # charm_matches_splat / meets_charm_requirements, where both phases read it
        # (an Unenlightened character holding a cross-Pattern Charm is caught as a
        # charm-wrong-splat at chargen). What stays here is the chargen-only half:
        # the Enlightened "no more than three of the six" cap, which counts chargen
        # picks and cannot be expressed as a per-Charm access bar.
        cross = 0
        for p in chargen_charm_picks(ruleset, character):
            if not p.counts_toward_pool:
                continue
            charm = ruleset.charms.get(p.charm_id)
            pat = _mountain_folk_pattern(charm) if charm is not None else None
            if pat is None:
                continue
            other_caste = pat in ("worker", "warrior", "artisan") and pat != own_pattern
            if other_caste:
                cross += 1
        if character.origin != "unenlightened" and cross > 3:
            issues.append(Issue(
                code="mountain-folk-pattern-cross-cap",
                message=(f"No more than 3 of the 6 chargen Charms may come from another "
                         f"caste's Pattern; {cross} do (CH6 p.230)."),
            ))

    # --- Sidereal Martial Arts form cap (p.101) ------------------------------ #
    # "no more than 3 [chargen Charms] may be from a Sidereal Martial Arts form;
    # ronin ... none". A "form" is a SIDEREAL martial-arts style — the three secret
    # styles of Sidereals pp.184-201. The Violet Bier auspicious tree is a lesser
    # (Celestial) style and is uncapped. None on every other splat = no cap.
    #
    # ⚠ This used to test `c.open_to_tiers`, i.e. "any Celestial-open martial-arts
    # Charm", as a proxy for "is a Sidereal MA form". The proxy was wrong and got
    # worse as the catalogue grew: it matched 140 Charms across TWELVE styles when
    # only 41 across three are Sidereal MA, so the five Immaculate Dragon Paths,
    # Celestial Monkey, Dreaming Pearl, Righteous Devil and Hungry Ghost all counted
    # against this cap — and a ronin, whose cap is 0, could not take a single
    # Celestial Monkey Charm. `ma_tier` names the style KIND directly.
    if b.martial_arts_form_charm_cap is not None:
        n_form = sum(
            1 for cid in charms
            if (c := ruleset.charms.get(cid)) is not None
            and c.ma_tier == "Sidereal")
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
    # A HARD ceiling binds even when the exception clause would let it go higher —
    # Unenlightened Mountain Folk "can never have a permanent Willpower above 6"
    # (CH6 p.230), whatever their Virtues. The exception clause above is superseded:
    # with two Virtues at 4+ an Unenlightened sheet would read 8 and the start-cap
    # check would pass, but the hard cap still binds.
    if b.willpower_hard_cap and wp_total > b.willpower_hard_cap:
        issues.append(Issue(
            code="willpower-hard-cap",
            message=(f"Willpower is {wp_total}; this origin may never exceed "
                     f"{b.willpower_hard_cap}."),
        ))

    # --- Willpower rules imposed by a held Flaw ------------------------------- #
    # Callous ceilings Willpower just above the Virtues it let the player sell off, and
    # Weak-Willed floors what its own forfeit may reach. Both read MeritEffects fields
    # rather than naming a Flaw (decision 0011). The Callous ceiling is the sanctioned
    # exception to decision 0005 — the human ruled that Willpower moves with the Virtues
    # for a Callous character, and stays pinned at lock for everyone else.
    mf = merits.merits_and_flaws_calc(ruleset, character)
    wp_forfeited = max(0, wp_total - mf.forfeited_willpower_dots)
    if mf.willpower_virtue_margin is not None:
        ceiling = derive.two_highest_virtues(virtues) + mf.willpower_virtue_margin
        if wp_forfeited > ceiling:
            issues.append(Issue(
                code="callous-willpower-cap",
                message=(f"Willpower starts at {wp_forfeited}; a Flaw held caps it at "
                         f"{ceiling} — no more than {mf.willpower_virtue_margin} above "
                         f"the sum of the two highest Virtues."),
            ))
    if mf.willpower_floor and wp_forfeited < mf.willpower_floor:
        issues.append(Issue(
            code="willpower-below-flaw-floor",
            message=(f"Willpower starts at {wp_forfeited}; a Flaw held floors it at "
                     f"{mf.willpower_floor}."),
        ))
    if mf.barred_natures and character.nature in mf.barred_natures:
        issues.append(Issue(
            code="nature-barred-by-flaw",
            message=f"A Flaw held bars the {character.nature} Nature.",
        ))
    for name in mf.nature_requirement_unmet:
        issues.append(Issue(
            code="merit-nature-required", where=name,
            message=(f"{name} may only be purchased or retained with the Nature it "
                     f"requires; this character's Nature is "
                     f"{character.nature or 'unset'}."),
        ))

    # --- Essence forced by a Flaw --------------------------------------------- #
    # Weak Essence "reduces the character's starting Essence rating to 1", which is a
    # ceiling on creation, not on later advancement — the Flaw exists precisely so the
    # character can raise Essence in play.
    if mf.essence_start_override is not None and essence > mf.essence_start_override:
        issues.append(Issue(
            code="essence-above-flaw-start",
            message=(f"Essence starts at {essence}; a Flaw held reduces the starting "
                     f"rating to {mf.essence_start_override}."),
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
    # The universal creation ceiling, under every splat's own: no character may leave
    # creation with Essence above 5 — Essence is XP-purchasable past it only after the
    # lock (see advancement.raise_essence). Separate from `essence_start_cap` below,
    # which is a narrower origin rule — this one holds even for a splat that sets no
    # origin ceiling at all.
    if essence > elder.DOT_MAX:
        issues.append(Issue(
            code="essence-above-elder-chargen-cap",
            message=(f"Essence {essence} exceeds 5. No character may leave creation "
                     f"with Essence above 5; raise it with experience after the lock."),
        ))
    if b.essence_start_cap and essence > b.essence_start_cap:
        issues.append(Issue(
            code="essence-above-chargen-cap",
            message=f"Essence {essence} exceeds the creation ceiling of "
                    f"{b.essence_start_cap} for this origin.",
        ))

    # A Merit-gated splat's magical purchases require the pool unlocked (God-Blooded
    # + Awakened Essence); otherwise Charms, spells and Essence above start are all
    # illegal together, and each reports on its own domain.
    issues += magic_gate_issues(ruleset, character)
    issues += heritage_origin_issues(ruleset, character)

    # Unallocated free dots — warnings, so they never block, but "✓ Legal" no longer
    # claims a blank sheet is finished.
    issues.extend(unspent_budget_issues(ruleset, character))
    issues.extend(merit_issues(ruleset, character))

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





































def effective_attribute_pools(ruleset: RuleSet, character: Character) -> tuple[int, int, int]:
    """The character's attribute pools — the budget's, unless the heritage overrides
    them. The Half-Caste heritage sets `attribute_pools` to (6, 5, 4) (PG p.47 prose;
    the p.50 summary's 6/5/3 is a printing error), where every other heritage keeps
    the God-Blooded 6/4/3. One read site so a heritage override cannot land in some
    of the six attribute-pool readers and not the rest."""
    caste = ruleset.castes.get(character.caste)
    heritage = caste.heritage_traits if caste is not None else None
    if heritage is not None and heritage.attribute_pools is not None:
        return tuple(heritage.attribute_pools)
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return tuple(b.attribute_pools)












def check_splat_consistency(ruleset: RuleSet, character: Character) -> list[Issue]:
    """Every Charm the character holds must belong to the character's own Exalt
    type, unless their caste may learn other splats' Charms (p.127). Spells are
    cross-splat (gated by circle, not splat) and are not checked; unknown Charm ids
    are left to check_references."""
    issues: list[Issue] = []
    # A splat barred from Charms outright gets its own finding: "wrong splat" would be
    # actively misleading for a mortal holding an `open_to_all` Charm, which belongs to
    # no splat in particular and is refused for a different reason entirely.
    if not charms_available(ruleset, character):
        # ...but the bar is not absolute: a Merit reopens part of it (Essence Mastery
        # grants Terrestrial Martial Arts), and charm_matches_splat is the one place
        # that knows which part. Anything it still refuses is reported; anything it
        # allows is a legal pick and must not be flagged, at chargen or in play.
        return [Issue(
            code="charms-not-available", where=cid,
            message=f"{ruleset.exalt_for(character.exalt_type).label} characters "
                    f"cannot purchase Charms (core p.103); remove {cid!r}.",
        ) for cid in character.charms
            if cid in ruleset.charms          # unknown ids: check_references' job
            and not charm_matches_splat(character, ruleset.charms[cid], ruleset)]
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
        if splat_of(charm) == character.exalt_type:
            # The Charm belongs to the character's OWN splat yet charm_matches_splat
            # refused it — a heritage bar (a God-Blooded holding a God-Blooded Arcanos,
            # p.47 "do not use Charms"), not a splat mismatch. "Wrong splat" would be
            # actively misleading, the same call the mortal branch above makes. Checked
            # before the ST foreign-charm privilege: the toggle waives the p.127
            # generalist rule, not a bar on the character's own catalogue.
            issues.append(Issue(
                code="charm-wrong-splat", where=cid,
                message=f"Charm {charm.name!r} belongs to the character's own "
                        f"{character.exalt_type} splat but is barred for this "
                        f"character; remove {cid!r}.",
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


def check_specialties(ruleset: RuleSet, character: Character) -> list[Issue]:
    """A specialty is an instance, not a rated trait (human, rules authority,
    2026-07-31): "you don't raise specialties, you just take the same one multiple
    times, and you can only have 3 specialties per ability".

    Both halves need checking HERE and not only in `advancement.add_specialty`,
    because chargen writes the list directly from the editor — an advancement guard
    alone would leave the whole pre-lock path unchecked, which is the mis-placed-rule
    shape this project keeps hitting.
    """
    from collections import Counter
    from .. import advancement as adv
    issues: list[Issue] = []
    counts = Counter(s.ability for s in character.specialties)
    for ability, n in sorted(counts.items(), key=lambda kv: kv[0].value):
        cap = adv.specialty_cap(ruleset, character, ability)
        if n > cap:
            issues.append(Issue(
                code="specialty-cap", where=ability.value,
                message=(f"{ability.value.title()} has {n} specialties; the maximum is "
                         f"{cap} per Ability."),
            ))
    for spec in character.specialties:
        if spec.rating > 1:
            issues.append(Issue(
                code="specialty-rating", where=f"{spec.ability.value}:{spec.name}",
                message=(f"{spec.name} ({spec.ability.value}) is rated {spec.rating}. "
                         f"Specialties are not raised — take the same one again "
                         f"instead, up to {adv.SPECIALTIES_PER_ABILITY} per Ability."),
            ))
    return issues


def check_fetters_and_passions(ruleset: RuleSet, character: Character) -> list[Issue]:
    """The two ghost-only rated traits (E:Ab p.126-127, p.283).

    Runs on BOTH sides of the lock, deliberately, because both rules do:

      * the Fetter ceiling is "Willpower + Essence", which MOVES — a ghost who buys
        Willpower may hold more Fetters, and one cursed down to a lower Willpower is
        over the cap and has to be told. A chargen-only check would have gone quiet at
        exactly the moment the cap started changing.
      * the Passion pool tracks the Virtues forever (p.283: "There is no other way for
        these Traits to increase"), so raising a Virtue with experience opens a dot to
        distribute and leaving it undistributed is a live finding, not a chargen one.

    Empty for every splat but the ghosts, whose lists are empty and whose Fetter budget
    is 0 — the check costs nothing for anyone else.
    """
    issues: list[Issue] = []
    if not character.fetters and not character.passions:
        return issues

    # --- Fetters: the hard cap ------------------------------------------------ #
    spent = derive.fetter_dots_spent(character)
    cap = derive.fetter_cap(character, ruleset)
    if spent > cap:
        issues.append(Issue(
            severity="error", code="fetter-over-cap", where="Fetters",
            message=(f"{spent} dots of Fetters exceeds the cap of {cap} "
                     f"(Willpower + Essence, p.127)."),
        ))

    # --- Passions: distribution against the live per-Virtue pool -------------- #
    # Reported per Virtue rather than in aggregate: the pools do not pool. A ghost
    # with Compassion 3 and Valor 1 who has put four dots into Compassion Passions is
    # over on one and under on the other, and one net-zero number would hide both.
    unspent = derive.passion_dots_unspent(character)
    for virtue, left in unspent.items():
        if left < 0:
            issues.append(Issue(
                severity="error", code="passion-over-pool", where=virtue.value.title(),
                message=(f"{-left} more dot(s) of {virtue.value.title()} Passions than "
                         f"{virtue.value.title()} allows — the pool is that Virtue's "
                         f"rating (p.126)."),
            ))
        elif left > 0:
            issues.append(Issue(
                severity="warning", code="passion-undistributed",
                where=virtue.value.title(),
                message=(f"{left} dot(s) of {virtue.value.title()} Passions still to "
                         f"distribute."),
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
    issues += check_specialties(ruleset, character)
    issues += check_fetters_and_passions(ruleset, character)
    issues += check_artifacts(ruleset, character)
    issues += check_hearthstones(ruleset, character)
    # The Background rules that bind on BOTH sides of the lock — `bind_post_lock` in
    # the data, exactly the Sidereal Celestial Manse ≤3 and Mountain Folk Artifact ≤10
    # (2026-08-12 rulings). Chargen-only caps stay in `validate_chargen`; Backgrounds
    # change through the story, so a locked Unenlightened Mountain Folk may be given
    # Backing 4 and nothing may object, and a locked Sidereal must still be held to
    # Manse ••• unless the ST lifts it. Reads the LIVE backgrounds, which are the
    # truth post-lock — the snapshot is for the XP audit, and Backgrounds have no XP.
    if character.chargen_locked:
        issues += background_issues(effective_budgets(ruleset, character),
                                    character.backgrounds, character, post_lock=True)
    # Elemental Powers legality runs on BOTH sides of the lock, like every other
    # trait check here — the powers are bought in play as well as at creation, and a
    # chargen-only read would go dead the moment the character locks (the house bug).
    # `character.elemental_powers` is the LIVE list: at lock it still holds the
    # chargen picks, and in play learn_elemental_power appends to it, so the snapshot
    # (which only ever holds chargen picks) is the wrong resolution here.
    issues += elemental_power_issues(ruleset, character, character.elemental_powers)
    return issues
