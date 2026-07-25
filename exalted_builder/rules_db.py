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

Expected layout:
    data/
      castes.json            array of CasteDefinition
      charms/*.json          each an array of Charm
      spells.json            array of Spell           (optional)
      armor.json             array of ArmorType       (optional)
      weapons.json           array of WeaponType      (optional)
      natures.json           array of NatureType      (optional)
      costs_bonus.json       BonusPointCosts object   (optional -> defaults)
      costs_xp.json          ExperienceCosts object   (optional -> defaults)
      chargen_budgets.json   ChargenBudgets object    (optional -> defaults)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .models.rules import (
    ArmorType,
    BackgroundType,
    BonusPointCosts,
    CasteDefinition,
    ChargenBudgets,
    Charm,
    College,
    TrainingCamp,
    Calling,
    ExaltDefinition,
    ExperienceCosts,
    MagicalMaterial,
    SOLAR_EXALT,
    NatureType,
    RuleSet,
    Spell,
    StScreen,
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


def _index(items: list[M], key: str, kind: str, problems: list[str]) -> dict:
    out: dict = {}
    for it in items:
        k = getattr(it, key)
        if k in out:
            problems.append(f"duplicate {kind} id: {k}")
        out[k] = it
    return out


def _check_prereqs(charms: dict[str, Charm], problems: list[str]) -> None:
    for ch in charms.values():
        for group in ch.prerequisites:
            for pid in group:
                if pid not in charms:
                    problems.append(f"charm '{ch.id}' references unknown prerequisite '{pid}'")


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
            if not choice.from_categories and not choice.fixed_sets:
                problems.append(f"camp {camp.id!r}: granted_charm_choice {choice.label!r} offers nothing")
            if choice.from_categories and choice.pick < 1:
                problems.append(
                    f"camp {camp.id!r}: granted_charm_choice {choice.label!r} picks from categories "
                    f"but `pick` is {choice.pick}")
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


def load_ruleset(data_dir: str | Path) -> RuleSet:
    """Load and validate the full rulebook. Raises RuleDataError listing every
    problem found, so the data can be corrected in a single pass."""
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
    charms = _index(charm_list, "id", "charm", problems)

    spells = _index(_load_array(data_dir / "spells.json", Spell, problems), "id", "spell", problems)
    armor = _index(_load_array(data_dir / "armor.json", ArmorType, problems), "id", "armor", problems)
    weapons = _index(_load_array(data_dir / "weapons.json", WeaponType, problems), "id", "weapon", problems)
    backgrounds = _index(_load_array(data_dir / "backgrounds.json", BackgroundType, problems),
                         "id", "background", problems)
    natures = _index(_load_array(data_dir / "natures.json", NatureType, problems),
                     "id", "nature", problems)
    materials = _index(_load_array(data_dir / "materials.json", MagicalMaterial, problems),
                       "id", "material", problems)
    colleges = _index(_load_array(data_dir / "colleges.json", College, problems),
                      "id", "college", problems)
    camps = _index(_load_array(data_dir / "camps.json", TrainingCamp, problems),
                   "id", "camp", problems)
    callings = _index(_load_array(data_dir / "callings.json", Calling, problems),
                      "id", "calling", problems)

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
    _check_camps_and_callings(camps, callings, charms, problems)

    if problems:
        raise RuleDataError(problems)

    return RuleSet(
        exalts=exalts,
        castes=castes,
        charms=charms,
        spells=spells,
        armor_catalog=armor,
        weapon_catalog=weapons,
        background_catalog=backgrounds,
        nature_catalog=natures,
        material_catalog=materials,
        colleges=colleges,
        camps=camps,
        callings=callings,
        bonus_costs=bonus_costs,
        xp_costs=xp_costs,
        budgets=budgets,
        st_screen=st_screen,
    )
