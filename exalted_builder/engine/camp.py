"""
engine/camp.py — the training-camp / Calling view model (Cult of the Illuminated).

Input: a RuleSet and a Character. Output: a `CampView` describing the camp select,
its ability minimums, its free-Charm package (fixed grants plus each unresolved
player choice) and the Calling — or None when the character's origin has no camps.
Mechanism: resolve the stored camp and Calling through `engine.validate`, then
flatten the camp's `granted_charm_choices` into the two-control shape the editors
render.

⚠ **A VIEW, not a mutator.** `engine/camp_actions.py` holds the writes.

`ui/view/` re-exports `build_camp_view` and `CampView`. The engine must not import
from `ui/`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..models.character import Character
from ..models.rules import RuleSet
from . import validate
from .labels import _label, _style_label
from .validate import _charm_name


@dataclass(frozen=True)
class CampChoiceOption:
    """One option of a camp grant choice.

    `available` is False if `data/` has fewer than `pick` Charms of the style. The
    option is still listed. ⚠ The UI must refuse to select it."""
    key: str
    label: str
    charm_ids: list[str]
    available: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CampCharmOption:
    """One Charm in a chosen category option (p.90).

    `meets_minimums` is False if the character fails the trait minimums of the Charm.
    The option is offered with a flag: `validate.granted_charm_issues` reports
    `granted-charm-minimum`. Charm prerequisites are not checked."""
    charm_id: str
    label: str
    meets_minimums: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CampChoiceView:
    """One player choice of a camp package, for the UI.

    Fixed-set choice: each option is a printed pair. `charm_options` is empty.
    Category choice: TWO controls. `options`/`chosen_key` select the style.
    `charm_options`/`chosen_charm_ids` select `pick` Charms of it.
    Flat-pool choice: `options` is empty. `charm_options` holds the pool."""
    label: str
    pick: int
    is_category_choice: bool
    options: list[CampChoiceOption]
    chosen_key: str = ""
    charm_options: list[CampCharmOption] = field(default_factory=list)
    chosen_charm_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CampView:
    """The data of the camp/Calling panel. Empty/None if the origin has no camps."""
    camp_options: list[tuple[str, str]]          # (id, label)
    camp_id: str
    camp_label: str
    camp_description: str
    minimums: list[str]                          # e.g. "Melee 2", "Archery or Brawl 1"
    granted_fixed: list[tuple[str, str]]         # (charm id, name) — always received
    choices: list[CampChoiceView]
    calling_options: list[tuple[str, str]]       # (id, label) for the CHOSEN camp
    calling_id: str
    calling_label: str
    calling_description: str
    calling_abilities: list[str]                 # display labels, ★-marked by the UI
    calling_charms: list[tuple[str, str]]        # (charm id, name)


def requires_camp(ruleset: RuleSet, character: Character) -> bool:
    """Return True if the origin uses training camps, from the budget."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return b.requires_camp or b.requires_calling


def build_camp_view(ruleset: RuleSet, character: Character) -> Optional[CampView]:
    """Return the camp/Calling panel, or None if the origin has no camps."""
    if not requires_camp(ruleset, character):
        return None

    camps = ruleset.camps_for(character.exalt_type, character.origin)
    camp = validate.camp_for(ruleset, character)
    calling = validate.calling_for(ruleset, character)
    # ⚠ `camp_for` resolves against ALL camps. A camp of a different splat is not an
    # option, and `ui.select` raises at BUILD time. Clear a MISMATCH only. The engine
    # reports `camp-wrong-origin`. An empty value stays empty.
    if camps and character.camp and camp not in camps:
        camp = camps[0]
    if calling is not None and camp is not None and \
            calling not in ruleset.callings_for(camp.id):
        calling = None

    minimums: list[str] = []
    granted_fixed: list[tuple[str, str]] = []
    choices: list[CampChoiceView] = []
    if camp is not None:
        for req in camp.required_min_abilities:
            names = " or ".join(_label(a.value) for a in req.abilities)
            minimums.append(f"{names} {req.rating}")
        granted_fixed = [(cid, _charm_name(ruleset, cid)) for cid in camp.granted_charms]

        held = set(character.granted_charms)
        for choice in camp.granted_charm_choices:
            options: list[CampChoiceOption] = []
            chosen = ""
            if choice.fixed_sets:
                for group in choice.fixed_sets:
                    key = "|".join(group)
                    label = " + ".join(_charm_name(ruleset, c) for c in group)
                    missing = [c for c in group if c not in ruleset.charms]
                    options.append(CampChoiceOption(
                        key=key, label=label, charm_ids=list(group),
                        available=not missing,
                        reason="" if not missing else "Charm not in data"))
                    if all(c in held for c in group):
                        chosen = key
            else:
                for cat in choice.from_categories:
                    ids = [c.id for c in ruleset.charms.values() if c.category == cat]
                    ok = len(ids) >= choice.pick
                    if ok:
                        reason = ""
                    elif not ids:
                        reason = "no Charms authored yet"
                    else:
                        reason = f"only {len(ids)} Charm(s) authored, needs {choice.pick}"
                    options.append(CampChoiceOption(
                        key=cat, label=_style_label(cat, ruleset), charm_ids=ids,
                        available=ok, reason=reason))
                    if ids and any(c in held for c in ids):
                        chosen = cat
            # A flat-pool choice has no `options`: the editor shows only the Charm
            # control.
            #
            # A category choice offers all Charms of the chosen style (p.90), with a
            # flag on a Charm whose minimums fail (granted-charm-minimum).
            charm_options: list[CampCharmOption] = []
            chosen_charm_ids: list[str] = []
            pool: list[str] = []
            if chosen and choice.from_categories:
                pool = next((o.charm_ids for o in options if o.key == chosen), [])
            elif not choice.fixed_sets and not choice.from_categories:
                # The flat pool is offered whole and immediately — there is no style
                # to choose first, so this control is the entire choice.
                pool = choice.pool_charm_ids(ruleset.charms)
            if pool:
                for cid in sorted(pool, key=lambda i: _charm_name(ruleset, i)):
                    charm = ruleset.charms.get(cid)
                    short = validate.charm_ability_shortfalls(character, charm) if charm else []
                    reason = ("needs " + ", ".join(f"{_label(t)} {req}"
                                                   for t, req, _ in short)
                              if short else "")
                    charm_options.append(CampCharmOption(
                        charm_id=cid, label=_charm_name(ruleset, cid),
                        meets_minimums=not short, reason=reason))
                chosen_charm_ids = [c for c in pool if c in held]

            choices.append(CampChoiceView(
                label=choice.label, pick=choice.pick,
                is_category_choice=bool(choice.from_categories),
                options=options, chosen_key=chosen,
                charm_options=charm_options, chosen_charm_ids=chosen_charm_ids))

    return CampView(
        camp_options=[(c.id, c.label) for c in camps],
        camp_id=camp.id if camp else "",
        camp_label=camp.label if camp else "",
        camp_description=camp.description if camp else "",
        minimums=minimums,
        granted_fixed=granted_fixed,
        choices=choices,
        calling_options=[(c.id, c.label) for c in ruleset.callings_for(camp.id)] if camp else [],
        calling_id=calling.id if calling else "",
        calling_label=calling.label if calling else "",
        calling_description=calling.description if calling else "",
        calling_abilities=[_label(a.value) for a in calling.abilities] if calling else [],
        calling_charms=[(cid, _charm_name(ruleset, cid)) for cid in calling.charms]
                       if calling else [],
    )
