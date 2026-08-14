"""
rules_db.py — load the rulebook from data/ into an immutable RuleSet.

Responsibilities:
  * read the JSON data files into the pydantic rules models;
  * index Charms and Spells by id (duplicate ids are an error);
  * link-check referential integrity at load time, so a typo in a prerequisite
    or an unreachable spell circle fails loudly HERE rather than mid-derivation.

Errors are accumulated and raised together, not one at a time — when you're
hand-entering hundreds of Charms you want to see every broken reference in one
pass, not fix-rerun-fix.

Optional tables (bonus/xp costs, chargen budgets) fall back to the model
defaults when their files are absent, so the loader runs on a partial data set.

A SECOND, optional data source sits on top: the user's custom library (see
custom_content.py), merged by `load_app_ruleset`. It uses the same file shapes and
the same loaders, but its failures are non-fatal — reported on
`RuleSet.custom_problems` rather than raised — because homebrew must never be able
to stop the app from starting. `load_ruleset` alone loads the book only.

Expected layout:
    data/
      castes.json            array of CasteDefinition
      charms/*.json          each an array of Charm
      spells.json            array of Spell           (optional)
      armor.json             array of ArmorType       (optional)
      gear.json              array of GearType        (optional)
      weapons.json           array of WeaponType      (optional)
      natures.json           array of NatureType      (optional)
      virtue_flaws.json      array of VirtueFlawType  (optional)
      costs_bonus.json       BonusPointCosts object   (optional -> defaults)
      costs_xp.json          ExperienceCosts object   (optional -> defaults)
      chargen_budgets.json   ChargenBudgets object    (optional -> defaults)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from . import custom_content
from .models.adversary import Adversary
from .models.rules import (
    AttributeName,
    ArmorType,
    GearType,
    ArtifactType,
    BackgroundType,
    BonusPointCosts,
    CasteDefinition,
    ChargenBudgets,
    Charm,
    College,
    MartialArtsStyle,
    TrainingCamp,
    Calling,
    ElementalPower,
    ExaltDefinition,
    ExperienceCosts,
    MagicalMaterial,
    RollDefinition,
    MeritFlaw,
    # Alias: `pathlib.Path` is already imported above, and the Dragon-King Path
    # catalogue class collides with it. models.rules.py itself has no pathlib import,
    # so the class is named `Path` there and aliased at every consumer that uses
    # pathlib too — this is the only one today.
    Path as DragonKingPath,
    SOLAR_EXALT,
    NatureType,
    VirtueFlawType,
    RuleSet,
    Spell,
    StScreen,
    ThaumaturgicArt,
    ThaumaturgicFormula,
    ThaumaturgicRitual,
    ThaumaturgicScience,
    WeaponType,
)

M = TypeVar("M", bound=BaseModel)


class RuleDataError(Exception):
    """Raised when the data files are structurally or referentially invalid.
    Carries the full list of problems so the whole set can be fixed in one pass."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        joined = "\n  - ".join(problems)
        super().__init__(f"{len(problems)} rule-data problem(s):\n  - {joined}")


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_object(path: Path, model: Type[M], problems: list[str]) -> M | None:
    """Load a single optional JSON object into `model`. Missing file -> None; a
    parse/validation error is recorded and returns None (the feature it powers is
    optional, so a bad file degrades gracefully rather than sinking the load)."""
    if not path.exists():
        return None
    try:
        raw = _read_json(path)
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: invalid JSON ({exc})")
        return None
    try:
        return model(**raw)
    except ValidationError as exc:
        problems.append(f"{path.name}: {exc.errors()[0]['msg']}")
        return None


def _load_array(path: Path, model: Type[M], problems: list[str]) -> list[M]:
    """Load a JSON array of `model`. Missing file -> empty list. Per-row
    validation failures are collected rather than raised."""
    if not path.exists():
        return []
    try:
        rows = _read_json(path)
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: invalid JSON ({exc})")
        return []
    if not isinstance(rows, list):
        problems.append(f"{path.name}: expected a JSON array, got {type(rows).__name__}")
        return []
    out: list[M] = []
    for i, row in enumerate(rows):
        try:
            out.append(model(**row))
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first["loc"])
            problems.append(f"{path.name}[{i}]: {loc}: {first['msg']}")
    return out


def _load_single(path: Path, model: Type[M], problems: list[str]) -> M:
    """Load a single-object table, or fall back to the model's baked-in defaults."""
    if not path.exists():
        return model()  # type: ignore[call-arg]
    try:
        return model(**_read_json(path))
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: invalid JSON ({exc})")
    except ValidationError as exc:
        problems.append(f"{path.name}: {exc.errors()[0]['msg']}")
    return model()  # type: ignore[call-arg]


def _load_keyed_table(path: Path, model: Type[M], problems: list[str]) -> dict[str, M]:
    """Load a per-Exalt-type cost/budget table keyed by exalt_type, e.g.
    ``{"default": {...}, "Abyssal": {...}}``. Absent -> ``{"default": model()}``.
    A legacy bare single-object file (the old shape) is wrapped under "default" —
    detected because every concrete table model has at least one non-dict scalar
    field, so a real keyed map (all values are dicts) is distinguishable. A
    "default" entry is always guaranteed (the accessors fall back to it)."""
    if not path.exists():
        return {"default": model()}  # type: ignore[call-arg]
    try:
        raw = _read_json(path)
    except json.JSONDecodeError as exc:
        problems.append(f"{path.name}: invalid JSON ({exc})")
        return {"default": model()}  # type: ignore[call-arg]
    keyed = isinstance(raw, dict) and bool(raw) and all(isinstance(v, dict) for v in raw.values())
    try:
        tables = ({k: model(**v) for k, v in raw.items()} if keyed
                  else {"default": model(**raw)})
    except ValidationError as exc:
        problems.append(f"{path.name}: {exc.errors()[0]['msg']}")
        return {"default": model()}  # type: ignore[call-arg]
    tables.setdefault("default", model())  # type: ignore[call-arg]
    return tables


def _check_martial_arts_styles(styles: dict, charms: dict, problems: list[str]) -> None:
    """Link-check the style catalogue against the Charms, BOTH WAYS.

    A style whose `category` no Charm uses is a typo in the slug — it would load
    clean and simply never appear. A printed Charm in a `martial_arts:*` category
    with no style is the gap this entity exists to close, and naming it here is how
    Phase 2 knows what is left to author.

    ⚠ Custom styles are exempt. `custom_content.py` mints `martial_arts:<slug>`
    for user-authored styles at runtime, and there is no page to write a preamble
    from — decision 0012 makes homebrew errors non-fatal, and reporting one here
    would put a permanent "problem" on the load of anyone with a homebrew style.
    A category is exempt when EVERY Charm in it is custom.
    """
    used: dict[str, list] = {}
    for charm in charms.values():
        category = getattr(charm, "category", "")
        if isinstance(category, str) and category.startswith("martial_arts:"):
            used.setdefault(category, []).append(charm)

    for style in styles.values():
        if style.category not in used:
            problems.append(
                f"martial arts style '{style.id}' has category '{style.category}', "
                "which no Charm uses (slug typo?)")

    # NB the reverse direction — a Charm category with no style — is deliberately
    # NOT a `problem`. Styles are authored in batches (docs/plans/martial-arts-
    # styles.md), so an unauthored preamble is a WORKLIST ENTRY, not a data error;
    # raising on it would stop the app from starting for the eighteen styles Phase 2
    # has not reached yet. It is reported by `unauthored_martial_arts_styles`, which
    # a test pins so the list can only ever shrink.


def _project_style_tier_onto_charms(styles: dict, charms: dict) -> None:
    """Copy each style's `tier` onto its Charms as `Charm.ma_tier`, in place.

    **The style stays the single AUTHORED copy.** `engine/` needs to know what kind
    of style a Charm belongs to — the p.101 Sidereal chargen cap and the PG p.235
    Terrestrial-initiation grant both turn on it — but a test bars `engine/` from
    reading the style catalogue, and duplicating the tier into 232 charm JSON rows
    would be the two-live-descriptions shape decision 0011 exists to prevent.
    Projecting at load time gives the engine a Charm-level field to read while
    leaving exactly one place to author it.

    A style with a blank `tier` leaves its Charms blank, and so does a category with
    no style entry (`martial_arts:enlightenment`, and every homebrew style). Blank
    means "no tier is printed for this", never "Terrestrial" — every consumer must
    treat it as unknown rather than defaulting it, because 46 of the 232 martial-arts
    Charms are in that state.
    """
    by_category = {s.category: s.tier for s in styles.values() if s.tier}
    for cid, charm in list(charms.items()):
        tier = by_category.get(getattr(charm, "category", ""), "")
        if tier and getattr(charm, "ma_tier", "") != tier:
            charms[cid] = charm.model_copy(update={"ma_tier": tier})


def unauthored_martial_arts_styles(ruleset) -> list[str]:
    """The `martial_arts:*` categories that have printed Charms but no style entry
    — i.e. the styles whose preamble is still unauthored. Sorted, so a test can pin
    it and Phase 2 can print it.

    Custom (homebrew) styles are excluded: there is no page to author a preamble
    from, so they are not work anyone is going to do.
    """
    used: dict[str, list] = {}
    for charm in ruleset.charms.values():
        category = getattr(charm, "category", "")
        if isinstance(category, str) and category.startswith("martial_arts:"):
            used.setdefault(category, []).append(charm)
    described = {s.category for s in ruleset.martial_arts_styles.values()}
    return sorted(
        category for category, rows in used.items()
        if category not in described
        and not all(getattr(c, "custom", False) for c in rows))


def _resolve_borrowed_ladders(backgrounds: dict, problems: list[str]) -> None:
    """Copy each `ladder_from` pointer's rungs onto the borrowing Background, in place.

    Resolved ONCE here rather than at the read sites, because the read sites are handed
    a SPLAT-FILTERED catalogue: a Mountain Folk list does not contain the Solar entry it
    borrows from, so a lookup there would find nothing and silently render no rung — the
    house bug, with the mechanism present and pointed at the wrong collection. After this
    runs, `ladder` is an ordinary transcribed ladder to every reader.

    Chains are not followed: a pointer must aim at an entry that carries its own printed
    ladder, so the text on screen is always one hop from the book that printed it.

    Rewrites the dict's VALUES rather than the entries: rules models are frozen, and the
    replacement copy is what every later reader is handed."""
    for bg in list(backgrounds.values()):
        if not bg.ladder_from:
            continue
        if bg.ladder:
            problems.append(
                f"background {bg.id}: has both a ladder and ladder_from={bg.ladder_from}")
            continue
        src = backgrounds.get(bg.ladder_from)
        if src is None:
            problems.append(
                f"background {bg.id}: ladder_from points at unknown id {bg.ladder_from}")
        elif src.ladder_from:
            problems.append(
                f"background {bg.id}: ladder_from={bg.ladder_from} itself borrows "
                f"its ladder; point at the entry that carries the printed one")
        elif not src.ladder:
            problems.append(
                f"background {bg.id}: ladder_from={bg.ladder_from} has no ladder")
        else:
            backgrounds[bg.id] = bg.model_copy(update={"ladder": src.ladder})


def _index(items: list[M], key: str, kind: str, problems: list[str]) -> dict:
    out: dict = {}
    for it in items:
        k = getattr(it, key)
        if k in out:
            problems.append(f"duplicate {kind} id: {k}")
        out[k] = it
    return out


# The Essence gate on Path rating (PG p.177 "Maximum Intelligence and Path Level"):
# dot 1 needs Essence 1, dots 2-3 Essence 2, dots 4-5 Essence 3, dot 6 Essence 6.
# Mirrors ChargenBudgets.path_max_by_essence; this table is what the VIRTUAL Charm
# rows carry so the Combo/sheet display agrees with the rated-track gate.
_PATH_DOT_ESSENCE_GATE = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 6}


def _virtual_path_charms(paths: list[DragonKingPath]) -> list[Charm]:
    """Project each PathPower into a virtual Charm row (Charm.virtual=True) so the
    Combo machinery and the sheet can name a Path power's type/duration/cost. Not
    purchasable — the picker hides virtual rows, and the rated-track truth lives on
    Character.paths. `prerequisites` chain the dots in fixed order ("each Path must
    be learned in a fixed order", p.177); `min_essence` encodes the Essence gate."""
    out: list[Charm] = []
    for path in paths:
        for power in path.powers:
            pid = f"dk.path.{path.id}.dot{power.dot}"
            out.append(Charm(
                id=pid,
                name=power.name,
                category=f"path:{path.id}",
                exalt_type="Dragon-Kings",
                type=power.type,
                min_essence=_PATH_DOT_ESSENCE_GATE.get(power.dot, 6),
                prerequisites=(
                    [[f"dk.path.{path.id}.dot{power.dot - 1}"]]
                    if power.dot > 1 else []
                ),
                cost=power.cost,
                duration=power.duration,
                keywords=power.keywords,
                description=power.text,
                virtual=True,
            ))
    return out


def _check_prereqs(charms: dict[str, Charm], problems: list[str]) -> None:
    for ch in charms.values():
        for group in ch.prerequisites:
            for pid in group:
                if pid not in charms:
                    problems.append(f"charm '{ch.id}' references unknown prerequisite '{pid}'")


def _check_elemental_powers(powers: dict, merits: dict, problems: list[str]) -> None:
    """Referential checks for the Elemental Powers catalogue (Core p.296 + GoD p.56,
    PG p.68). Each power's `required_merits` names Merit ids and must resolve —
    dropping Elemental Dominion or Primal Restoration would otherwise orphan held
    powers, and a typo would silently make a power permanently unbuyable."""
    for p in powers.values():
        for mid in p.required_merits:
            if mid not in merits:
                problems.append(
                    f"elemental power '{p.id}' references unknown required merit '{mid}'")


def _check_merits_flaws(merits: dict, problems: list[str]) -> None:
    """Referential and structural checks for Merits & Flaws.

    Prerequisites are Merit ids and must resolve — the same rule Charms follow. A
    printed prerequisite this build cannot express belongs in `prerequisite_note`
    instead, which is free text and deliberately unchecked.

    A variable-cost entry must actually offer options, and a fixed-cost one must not
    offer both: `cost` and `cost_options` are alternatives, and a row carrying both
    would silently price by whichever the calc happened to read first."""
    for m in merits.values():
        for pid in m.prerequisites:
            if pid not in merits:
                problems.append(
                    f"merit '{m.id}' references unknown prerequisite '{pid}'")
        if m.cost and m.cost_options:
            problems.append(
                f"merit '{m.id}' sets both cost and cost_options; use one")
        # A trait prerequisite is looked up by NAME at validation time, across four
        # namespaces, and a name that matches nothing simply reads 0 — so a typo would
        # not error, it would make the entry permanently unbuyable. Backgrounds are soft
        # references by design (a character may name one the catalogue has never heard
        # of) and Abilities include per-focus Crafts, so the NAME is deliberately not
        # checked here. The tier key is: it must be one of the entry's own options.
        for tier in m.trait_prerequisites:
            if tier and tier not in m.cost_options:
                problems.append(
                    f"merit '{m.id}' scopes a trait prerequisite to tier '{tier}', "
                    f"which is not one of its cost options {sorted(m.cost_options)}")
        # A variable-cost entry ("VARIABLE COST MERIT") prices from the purchase, so
        # it is the one shape that legitimately carries no printed number.
        if not any((m.cost, m.cost_options, m.variable_cost, m.cost_by_kind)):
            problems.append(
                f"merit '{m.id}' has no cost shape (cost / cost_options / "
                f"variable_cost / cost_by_kind)")
        # cost_by_kind prices the two sides of an "either" entry; it is meaningless
        # on a single-sided one and would silently never be read.
        if m.cost_by_kind and m.kind != "either":
            problems.append(
                f"merit '{m.id}' sets cost_by_kind but its kind is {m.kind!r}")
        if m.kind == "either" and not (m.cost_by_kind or m.variable_cost):
            problems.append(
                f"merit '{m.id}' is kind 'either' but prices neither side")
        if m.variable_cost and (m.cost or m.cost_options):
            problems.append(
                f"merit '{m.id}' is variable_cost but also carries a printed price")
        for splat, opts in m.cost_options_by_exalt_type.items():
            if not opts:
                problems.append(
                    f"merit '{m.id}' has an empty cost override for {splat!r}")


def _check_thaumaturgy(arts, sciences, formulas, problems: list[str]) -> None:
    """Referential and structural checks for thaumaturgy.

    Aspect ids must be globally unique because the character stores an ArtSpecialty
    by (art_id, free-text name) and the UI resolves aspects by id across Arts.

    A formula must belong to a real Science and must not require a rating that
    Science cannot reach. NOTE that a formula may legitimately sit at a rating with NO
    printed ScienceLevel, so a missing rung is never an error — that tolerance was
    written for Alchemy, whose printed ladder skipped five while two of its formulas
    required it. That anomaly is gone (the printed 6 was a typo for 5, human
    2026-07-30), but the tolerance stays: it costs nothing and the next book may do the
    same thing."""
    seen_aspects: dict[str, str] = {}
    for art in arts.values():
        for aspect in art.aspects:
            if aspect.id in seen_aspects:
                problems.append(
                    f"thaumaturgic art {art.id!r}: aspect id {aspect.id!r} already used by "
                    f"art {seen_aspects[aspect.id]!r}")
            seen_aspects[aspect.id] = art.id

    for science in sciences.values():
        for lv in science.levels:
            if lv.rating > science.max_rating:
                problems.append(
                    f"thaumaturgic science {science.id!r}: level {lv.rating} exceeds its "
                    f"max_rating of {science.max_rating}")

    for formula in formulas.values():
        science = sciences.get(formula.science_id)
        if science is None:
            problems.append(
                f"thaumaturgic formula {formula.id!r}: unknown science {formula.science_id!r}")
        elif formula.level > science.max_rating:
            problems.append(
                f"thaumaturgic formula {formula.id!r}: requires {science.name} {formula.level}, "
                f"above that Science's max_rating of {science.max_rating}")


def _check_charm_references(exalts, castes, charms, spells, problems: list[str]) -> None:
    """Every Charm or Spell id named by an ExaltDefinition or a CasteDefinition's
    `heritage_traits` must exist. These are the quietest dangling ids in the build:
    a `barred_charm_ids`/`barred_spell_ids` entry that resolves to nothing BARS
    NOTHING — the bar reads as satisfied and the Charm or Spell stays learnable — and
    a heritage's parent-keyed Ox-Body/Gift id that misses silently drops that parent's
    repeatable-purchase cap. None of it raises, and none of it is visible to a test
    asserting the field's contents, so the check has to live at load.

    `ExaltDefinition.ox_body_charm_id`/`gift_charm_id` are deliberately NOT checked
    here: the loader's own synthetic fixtures name splat Charms outside their
    miniature catalogues, and the two are already exercised through real characters."""
    for exalt in exalts.values():
        for cid in exalt.barred_charm_ids:
            if cid not in charms:
                problems.append(f"exalt {exalt.id!r}: barred charm {cid!r} does not exist")
        for sid in exalt.barred_spell_ids:
            if sid not in spells:
                problems.append(f"exalt {exalt.id!r}: barred spell {sid!r} does not exist")
    for caste in castes.values():
        heritage = getattr(caste, "heritage_traits", None)
        if heritage is None:
            continue
        for cid in heritage.barred_charm_ids:
            if cid not in charms:
                problems.append(f"caste {caste.id!r}: barred charm {cid!r} does not exist")
        # The parent-keyed maps (Half-Caste, PG p.47) — same silent failure, keyed by
        # the parent Exalt type rather than named once.
        for field in ("ox_body_charm_ids", "gift_charm_ids"):
            for parent, cid in getattr(heritage, field, {}).items():
                if cid not in charms:
                    problems.append(
                        f"caste {caste.id!r}: {field}[{parent!r}] {cid!r} does not exist")
        # The heritage's own single Ox-Body (God/Demon-Blooded -> the spirit copy).
        cid = heritage.ox_body_charm_id or ""
        if cid and cid not in charms:
            problems.append(f"caste {caste.id!r}: ox_body_charm_id {cid!r} does not exist")


def _check_camps_and_callings(camps, callings, charms, problems: list[str]) -> None:
    """Every Charm a TrainingCamp grants or a Calling discounts must exist, and every
    Calling must belong to a real camp. A dangling id here is silent in a way the
    other tables are not: a granted Charm that does not resolve simply never appears
    on the sheet, and a Calling Charm that does not resolve quietly charges full
    price."""
    for camp in camps.values():
        for cid in camp.granted_charms:
            if cid not in charms:
                problems.append(f"camp {camp.id!r}: granted charm {cid!r} does not exist")
        for choice in camp.granted_charm_choices:
            for group in choice.fixed_sets:
                for cid in group:
                    if cid not in charms:
                        problems.append(
                            f"camp {camp.id!r}: charm {cid!r} in a fixed_sets option does not exist")
            for cid in choice.pool_charms:
                if cid not in charms:
                    problems.append(
                        f"camp {camp.id!r}: charm {cid!r} in a pool_charms option does not exist")
            pooled = bool(choice.pool_categories or choice.pool_charms)
            if not choice.from_categories and not choice.fixed_sets and not pooled:
                problems.append(f"camp {camp.id!r}: granted_charm_choice {choice.label!r} offers nothing")
            if choice.from_categories and choice.pick < 1:
                problems.append(
                    f"camp {camp.id!r}: granted_charm_choice {choice.label!r} picks from categories "
                    f"but `pick` is {choice.pick}")
            if pooled and choice.pick < 1:
                problems.append(
                    f"camp {camp.id!r}: granted_charm_choice {choice.label!r} picks from a pool "
                    f"but `pick` is {choice.pick}")
            # A pool smaller than the package cannot be resolved at all, and the
            # failure would otherwise surface as a permanent chargen error on a
            # legal character rather than as a data problem here.
            if pooled and len(choice.pool_charm_ids(charms)) < choice.pick:
                problems.append(
                    f"camp {camp.id!r}: granted_charm_choice {choice.label!r} needs "
                    f"{choice.pick} Charm(s) but its pool holds "
                    f"{len(choice.pool_charm_ids(charms))}")
    known_camps = set(camps)
    for calling in callings.values():
        if calling.camp and calling.camp not in known_camps:
            problems.append(f"calling {calling.id!r}: unknown camp {calling.camp!r}")
        for cid in calling.charms:
            if cid not in charms:
                problems.append(f"calling {calling.id!r}: calling charm {cid!r} does not exist")


def _check_sorcery_reachable(
    charms: dict[str, Charm], spells: dict[str, Spell], problems: list[str]
) -> None:
    """Every spell's circle must be granted by at least one Charm, or no
    character could ever legally learn it."""
    granted = {ch.grants_circle for ch in charms.values() if ch.grants_circle}
    for sp in spells.values():
        if sp.circle not in granted:
            problems.append(
                f"spell '{sp.id}' is {sp.circle.value} circle, but no Charm grants that circle"
            )


def _merge_custom_gear(custom_dir: Path, catalogs: dict, problems: list[str]) -> None:
    """Overlay the user's gear library onto the book catalogues, in place.

    Same contract as the Charm layer above and for the same reasons: the BOOK ALWAYS
    WINS an id collision, a bad row is reported and dropped rather than raised on, and
    the app loads anyway. Gear needs no satisfiability pass — a weapon points at nothing
    the way a Charm points at prerequisites — so this is the whole of it.

    ⚠ Rows are tagged `custom` via their `tags`, not a model field: `WeaponType` and
    friends are frozen and shared with the book data, and adding a flag to them would
    put a homebrew concept in the printed models. The Buy dialog reads the tag to mark
    a row as yours.
    """
    for kind, (catalog, model) in catalogs.items():
        rows = custom_content.library_gear(kind, custom_dir)
        for raw in rows:
            try:
                entry = model.model_validate(raw)
            except ValidationError as ex:
                problems.append(f"custom {kind} row {raw.get('id', '?')!r}: {ex}")
                continue
            if entry.id in catalog:
                problems.append(
                    f"custom {kind} {entry.id!r} shadows an entry from the rulebook; "
                    f"ignored")
                continue
            catalog[entry.id] = entry.model_copy(
                update={"tags": list(entry.tags) + ["custom"]})


def _load_custom_layer(
    custom_dir: Path,
    charms: dict[str, Charm],
    spells: dict[str, Spell],
    gear_catalogs: dict | None = None,
) -> list[str]:
    """Merge the user's custom library over the book data, in place.

    Returns the problems found, which are deliberately NOT fatal: a bad row is
    dropped and reported, and the app loads anyway. The book's own data has already
    been link-checked and raised on by the time this runs, so anything wrong here is
    the user's homebrew and theirs alone to fix.

    Three rules, in order:
      * the book always wins an id collision — a printed Charm must never be
        silently replaced by homebrew that happens to reuse its id;
      * a custom Charm whose prerequisite group has NO satisfiable member is
        dropped, iterated to a fixpoint because dropping one row can orphan
        another that required it;
      * a custom spell whose circle no Charm grants is dropped, the same check the
        book data gets — such a spell could never legally be learned.
    """
    problems: list[str] = []

    custom_charms: dict[str, Charm] = {}
    charm_dir = custom_dir / "charms"
    if charm_dir.is_dir():
        for f in sorted(charm_dir.glob("*.json")):
            for row in _load_array(f, Charm, problems):
                if row.id in charms:
                    problems.append(
                        f"custom charm {row.id!r} shadows a Charm from the rulebook; ignored")
                elif row.id in custom_charms:
                    problems.append(
                        f"custom charm {row.id!r} is defined twice in the library; "
                        f"the first definition is used")
                else:
                    custom_charms[row.id] = row.model_copy(update={"custom": True})

    # Drop unsatisfiable rows before publishing any of them, so nothing downstream
    # ever sees a Charm pointing at an id that is not in the RuleSet.
    known = set(charms) | set(custom_charms)
    while True:
        doomed = {
            cid: group
            for cid, ch in custom_charms.items()
            for group in ch.prerequisites
            if not (set(group) & known)
        }
        if not doomed:
            break
        for cid, group in doomed.items():
            missing = ", ".join(repr(p) for p in group)
            problems.append(
                f"custom charm {cid!r} requires {missing}, which does not exist; dropped")
            del custom_charms[cid]
        known = set(charms) | set(custom_charms)

    charms.update(custom_charms)

    custom_spells = _load_array(custom_dir / "spells.json", Spell, problems)
    granted = {ch.grants_circle for ch in charms.values() if ch.grants_circle}
    for sp in custom_spells:
        if sp.id in spells:
            problems.append(
                f"custom spell {sp.id!r} shadows a spell from the rulebook; ignored")
        elif sp.circle not in granted:
            problems.append(
                f"custom spell {sp.id!r} is {sp.circle.value} circle, but no Charm grants "
                f"that circle, so it could never be learned; dropped")
        else:
            spells[sp.id] = sp.model_copy(update={"custom": True})

    if gear_catalogs:
        _merge_custom_gear(custom_dir, gear_catalogs, problems)

    return problems


def load_ruleset(data_dir: str | Path, custom_dir: str | Path | None = None) -> RuleSet:
    """Load and validate the full rulebook. Raises RuleDataError listing every
    problem found, so the data can be corrected in a single pass.

    `custom_dir` overlays a user-authored library on top of the book data (see
    custom_content.py and _load_custom_layer). None — the default — loads the book
    alone, which is what the engine tests want; the UI calls `load_app_ruleset`
    instead, which points it at the user's library.
    """
    data_dir = Path(data_dir)
    problems: list[str] = []

    castes = _index(
        _load_array(data_dir / "castes.json", CasteDefinition, problems),
        "id", "caste", problems,
    )

    charm_list: list[Charm] = []
    charm_dir = data_dir / "charms"
    if charm_dir.is_dir():
        for f in sorted(charm_dir.glob("*.json")):
            charm_list.extend(_load_array(f, Charm, problems))
    # Dragon-King Paths of Prehuman Mastery (PG pp.177-191). The rated-track
    # catalogue (10 Paths x 6 dot-level powers) loads here; then each PathPower is
    # PROJECTED into the charm list as a virtual Charm row so the Combo machinery
    # and the sheet have names/types/durations for the powers. The real state stays
    # the rated track on Character.paths — virtual rows are not purchasable (the
    # picker hides Charm.virtual) and every OTHER read site decides explicitly
    # whether to skip or include them (see the read-site inventory in the
    # Dragon-Kings plan).
    paths = _index(_load_array(data_dir / "paths.json", DragonKingPath, problems),
                   "id", "path", problems)
    charm_list.extend(_virtual_path_charms(paths.values()))
    charms = _index(charm_list, "id", "charm", problems)

    spells = _index(_load_array(data_dir / "spells.json", Spell, problems), "id", "spell", problems)
    armor = _index(_load_array(data_dir / "armor.json", ArmorType, problems), "id", "armor", problems)
    gear = _index(_load_array(data_dir / "gear.json", GearType, problems), "id", "gear", problems)
    weapons = _index(_load_array(data_dir / "weapons.json", WeaponType, problems), "id", "weapon", problems)
    artifacts = _index(_load_array(data_dir / "artifacts.json", ArtifactType, problems),
                       "id", "artifact", problems)
    backgrounds = _index(_load_array(data_dir / "backgrounds.json", BackgroundType, problems),
                         "id", "background", problems)
    _resolve_borrowed_ladders(backgrounds, problems)
    virtue_flaws = _index(_load_array(data_dir / "virtue_flaws.json", VirtueFlawType,
                                      problems), "id", "virtue flaw", problems)
    natures = _index(_load_array(data_dir / "natures.json", NatureType, problems),
                     "id", "nature", problems)
    materials = _index(_load_array(data_dir / "materials.json", MagicalMaterial, problems),
                       "id", "material", problems)
    colleges = _index(_load_array(data_dir / "colleges.json", College, problems),
                      "id", "college", problems)
    # Martial-arts styles — the preamble the `martial_arts:<slug>` categories always
    # implied. Optional and INERT: nothing in engine/ reads it (see MartialArtsStyle).
    ma_styles = _index(_load_array(data_dir / "martial_arts_styles.json",
                                   MartialArtsStyle, problems),
                       "id", "martial arts style", problems)
    _check_martial_arts_styles(ma_styles, charms, problems)
    _project_style_tier_onto_charms(ma_styles, charms)
    # Named base dice pools (decision 0016). Cross-splat and optional: absent means
    # the pool calculator simply offers no presets.
    rolls = _index(_load_array(data_dir / "dice_pools.json", RollDefinition, problems),
                   "id", "roll", problems)
    # Merits & Flaws (decision 0011). Optional, cross-splat and INERT — the file
    # carries printed text and costs only; effects live in engine.merits.
    merits_flaws = _index(_load_array(data_dir / "merits_flaws.json", MeritFlaw, problems),
                          "id", "merit", problems)
    # Elemental Powers (Core p.296 + GoD p.56, PG p.68) — the learnable Charm-like
    # catalogue for Elemental-origin God-Blooded. Optional, like merits.
    elemental_powers = _index(
        _load_array(data_dir / "elemental_powers.json", ElementalPower, problems),
        "id", "elemental power", problems)

    camps = _index(_load_array(data_dir / "camps.json", TrainingCamp, problems),
                   "id", "camp", problems)
    callings = _index(_load_array(data_dir / "callings.json", Calling, problems),
                      "id", "calling", problems)

    # Thaumaturgy (Player's Guide CH3). Cross-splat, so it is keyed by nothing and
    # every file is optional — a data set without them simply has no thaumaturgy.
    thaum_dir = data_dir / "thaumaturgy"
    thaum_arts = _index(_load_array(thaum_dir / "arts.json", ThaumaturgicArt, problems),
                        "id", "thaumaturgic art", problems)
    thaum_sciences = _index(_load_array(thaum_dir / "sciences.json", ThaumaturgicScience, problems),
                            "id", "thaumaturgic science", problems)
    thaum_rituals = _index(_load_array(thaum_dir / "rituals.json", ThaumaturgicRitual, problems),
                           "id", "thaumaturgic ritual", problems)
    thaum_formulas = _index(_load_array(thaum_dir / "formulas.json", ThaumaturgicFormula, problems),
                            "id", "thaumaturgic formula", problems)

    exalt_list = _load_array(data_dir / "exalts.json", ExaltDefinition, problems)
    exalts = (_index(exalt_list, "id", "exalt", problems) if exalt_list
              else {SOLAR_EXALT.id: SOLAR_EXALT})

    bonus_costs = _load_keyed_table(data_dir / "costs_bonus.json", BonusPointCosts, problems)
    xp_costs = _load_keyed_table(data_dir / "costs_xp.json", ExperienceCosts, problems)
    budgets = _load_keyed_table(data_dir / "chargen_budgets.json", ChargenBudgets, problems)
    st_screen = _load_object(data_dir / "st_screen.json", StScreen, problems)

    # referential integrity — only meaningful once the rows themselves parsed
    _check_prereqs(charms, problems)
    _check_sorcery_reachable(charms, spells, problems)
    _check_charm_references(exalts, castes, charms, spells, problems)
    _check_camps_and_callings(camps, callings, charms, problems)
    _check_thaumaturgy(thaum_arts, thaum_sciences, thaum_formulas, problems)
    _check_merits_flaws(merits_flaws, problems)
    _check_elemental_powers(elemental_powers, merits_flaws, problems)

    if problems:
        raise RuleDataError(problems)

    # The custom layer goes on only after the book has passed its own checks, so a
    # book error is never blamed on the user's homebrew (and vice versa).
    custom_problems: list[str] = []
    if custom_dir is not None and Path(custom_dir).is_dir():
        custom_problems = _load_custom_layer(
            Path(custom_dir), charms, spells,
            {"weapons": (weapons, WeaponType), "armor": (armor, ArmorType),
             "gear": (gear, GearType), "artifacts": (artifacts, ArtifactType)})

    return RuleSet(
        exalts=exalts,
        castes=castes,
        charms=charms,
        spells=spells,
        armor_catalog=armor,
        gear_catalog=gear,
        weapon_catalog=weapons,
        artifact_catalog=artifacts,
        background_catalog=backgrounds,
        nature_catalog=natures,
        virtue_flaw_catalog=virtue_flaws,
        material_catalog=materials,
        colleges=colleges,
        martial_arts_styles=ma_styles,
        roll_catalog=rolls,
        paths=paths,
        merits_flaws=merits_flaws,
        elemental_powers=elemental_powers,
        thaum_arts=thaum_arts,
        thaum_sciences=thaum_sciences,
        thaum_rituals=thaum_rituals,
        thaum_formulas=thaum_formulas,
        camps=camps,
        callings=callings,
        bonus_costs=bonus_costs,
        xp_costs=xp_costs,
        budgets=budgets,
        st_screen=st_screen,
        custom_problems=custom_problems,
    )


def reload_custom_layer(ruleset: RuleSet, custom_dir: str | Path | None = None) -> list[str]:
    """Re-read the custom library into an ALREADY LOADED RuleSet, in place. Returns
    the problems found (also stored on `ruleset.custom_problems`).

    In place on purpose. Every page closes over one RuleSet built at startup, so the
    authoring page has two ways to make an edit visible: rebuild the RuleSet and
    thread the new object through every page and renderer, or update the object they
    all already hold. The second is a few lines and cannot get out of sync; the book
    half is untouched, and only rows the loader stamped `custom` are replaced.

    Rebuilding from disk rather than patching one row keeps this honest: a Charm that
    was dropped for a dangling prerequisite comes back when the prerequisite is
    authored, without the caller having to know that.
    """
    for cid in [cid for cid, ch in ruleset.charms.items() if ch.custom]:
        del ruleset.charms[cid]
    for sid in [sid for sid, sp in ruleset.spells.items() if sp.custom]:
        del ruleset.spells[sid]

    target = Path(custom_dir) if custom_dir is not None else custom_content.custom_data_dir()
    problems = _load_custom_layer(target, ruleset.charms, ruleset.spells) \
        if target.is_dir() else []
    ruleset.custom_problems = problems
    return problems


def load_adversary_catalog(data_dir: str | Path) -> dict[str, Adversary]:
    """Load the Storyteller's adversary templates (data/adversaries.json).

    Deliberately NOT part of the RuleSet, and loaded by its own call. The
    templates are book data, but they are not rules: nothing resolves a
    prerequisite through them, nothing link-checks them, and no character is ever
    validated against one. Keeping them out also keeps models/rules.py from
    importing the character-domain Adversary, which would be an import cycle.

    Raises RuleDataError on malformed rows, the same as the rest of the book data
    — a template with a broken stat line is an authoring bug, not a user's
    homebrew. A missing file is fine and yields an empty catalogue: the roster
    still works, offering blank entries only.
    """
    data_dir = Path(data_dir)
    problems: list[str] = []
    rows = _load_array(data_dir / "adversaries.json", Adversary, problems)
    catalog = _index(rows, "id", "adversary", problems)
    if problems:
        raise RuleDataError(problems)
    return catalog


def load_app_ruleset(data_dir: str | Path) -> RuleSet:
    """What the UI pages call: the rulebook plus whatever the user has authored in
    their custom library. Split from `load_ruleset` so the engine tests can load the
    book alone and stay unaffected by whatever homebrew sits on the machine."""
    return load_ruleset(data_dir, custom_dir=custom_content.custom_data_dir())
