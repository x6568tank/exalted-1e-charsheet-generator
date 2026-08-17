"""
engine/validate/traits.py — reference integrity, splat consistency and trait shape.

The checks that ask whether the character's own record is coherent, rather than whether
a purchase was affordable: reference integrity (`check_references`), caste/splat
agreement, specialties, the Ghost Fetters and Passions, and the Godblooded heritage
origin.

⚠ Equipment is an inline copy by design (decision 0007) and is deliberately NOT
reference-checked.

⚠ A specialty is an INSTANCE, not a rated trait: the same one is taken again rather
than raised, capped at 3 per Ability — two Swords plus one Parrying fills Melee.

⚠ Passions are a LIVE DERIVATION of the Virtues on both sides of the lock, per-Virtue,
never bought with BP or XP (E:Ab p.283).

⚠ These run on BOTH sides of the lock. A reference can rot after creation — a
hand-edited save, a custom Charm deleted from the library — so none may become
chargen-only.
"""

from __future__ import annotations

from ...models.character import Character
from ...models.rules import AbilityName, RuleSet
from .. import derive
from ._base import Issue, ability_rating, craft_rating
from .castes import splat_has_castes
from .charms import (
    charm_learnable_by_splat,
    charm_matches_splat,
    charms_available,
    foreign_charms_caste,
    foreign_charms_open,
    heritage_charms_available,
    splat_of,
)


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


# Permanent Resonance (Death's Taint) moves on the XP ledger like a curse, but with its
# own prices in each direction — free to gain, five to shed — so it needs a target the
# audit can recognise. `_expected_cost` must test this BEFORE its general "a reduction
# is free" rule, which would otherwise price the shed at 0 and report a mismatch on
# every later validation.
PERMANENT_RESONANCE_TARGET = "limit_permanent"


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
    """The two ghost-only rated traits (E:Ab p.126-127, p.283). Empty for every other
    splat, whose lists and Fetter budget are both empty.

    ⚠ Both rules run on BOTH sides of the lock, because both keep moving:

      * the Fetter ceiling is "Willpower + Essence" — a ghost who buys Willpower may
        hold more, and one cursed down to a lower Willpower is now over the cap;
      * the Passion pool tracks the Virtues forever (p.283: "There is no other way for
        these Traits to increase"), so an XP Virtue raise opens a dot to distribute and
        leaving it undistributed is a live finding.
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
