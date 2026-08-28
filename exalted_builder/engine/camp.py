"""
engine/camp.py — the training-camp / Calling view model (Cult of the Illuminated).

Input: a RuleSet and a Character. Output: a `CampView` describing the camp select,
its ability minimums, its free-Charm package (fixed grants plus each unresolved
player choice) and the Calling — or None when the character's origin has no camps.
Mechanism: resolve the stored camp and Calling through `engine.validate`, then
flatten the camp's `granted_charm_choices` into the two-control shape the editors
render.

⚠ **This is a VIEW, not a mutator.** `engine/camp_actions.py` holds the writes; the
two are split so a shell can re-derive the panel without risking a change to it.

⚠ **It lived in `ui/view.py` until 2026-08-22** and is re-exported from there, so
`viewmod.build_camp_view` and `viewmod.CampView` still resolve. It moved because
`engine/camp_actions.py` needs it and the engine may not import from `ui/`.
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
    """One option within a camp's grant choice.

    `available` is False when the option cannot actually be taken — which for this book
    means a martial-arts style the page offers but whose Charms `data/` cannot yet
    supply `pick` of. All four of the Tabernacle's styles are authored as of 2026-07-25,
    so nothing trips this today; it stays because the next book to offer a style before
    its Charms exist will. Such an option is still LISTED, because the rulebook offers
    it and hiding it would misrepresent the page — but the UI must refuse to select it
    rather than assign nothing and silently blank the control."""
    key: str
    label: str
    charm_ids: list[str]
    available: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CampCharmOption:
    """One Charm selectable inside an already-chosen category option.

    The Tabernacle's package is "two Charms from ONE of four martial arts" (p.90) —
    choosing the STYLE is only half the choice, and the player picks WHICH Charms.
    `meets_minimums` is False when the character does not yet meet the Charm's own trait
    minimums; the page requires those ("must meet the minimum requirements", p.90) and
    `validate.granted_charm_issues` raises `granted-charm-minimum` for a violation, so
    the option is still offered but flagged. Charm PREREQUISITES are deliberately not
    considered — the package hands out Charms whose tree the character has not climbed."""
    charm_id: str
    label: str
    meets_minimums: bool = True
    reason: str = ""


@dataclass(frozen=True)
class CampChoiceView:
    """One player choice inside a training camp's free-Charm package, flattened for the
    UI. For a fixed-set choice each option is a whole printed pair; for a category choice
    each option is one style and `pick` says how many Charms to take from it.

    A category choice is TWO controls, not one: `options`/`chosen_key` pick the style,
    then `charm_options`/`chosen_charm_ids` pick which `pick` of that style's Charms are
    granted. `charm_options` is empty until a style is chosen, and always empty for a
    fixed-set choice (there the printed pair IS the grant — no sub-choice).

    A flat-pool choice (GrantedCharmChoice.pool_categories/pool_charms) is the mirror
    image: `options` is EMPTY and `charm_options` holds the whole pool from the start,
    so the editor renders one control instead of two."""
    label: str
    pick: int
    is_category_choice: bool
    options: list[CampChoiceOption]
    chosen_key: str = ""
    charm_options: list[CampCharmOption] = field(default_factory=list)
    chosen_charm_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CampView:
    """Everything the editor needs to render the camp/Calling panel. Empty/None for
    every character whose origin has no camps, which is how the panel stays hidden."""
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
    """Whether this character's origin uses training camps (Cult of the Illuminated).
    Budget-driven, so no splat or origin is named in the UI."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return b.requires_camp or b.requires_calling


def build_camp_view(ruleset: RuleSet, character: Character) -> Optional[CampView]:
    """The camp/Calling panel, or None when the origin has no camps."""
    if not requires_camp(ruleset, character):
        return None

    camps = ruleset.camps_for(character.exalt_type, character.origin)
    camp = validate.camp_for(ruleset, character)
    calling = validate.calling_for(ruleset, character)
    # `camp_for` resolves the stored id against the WHOLE camp table, so a camp
    # belonging to another splat's Cult resolves fine and would be handed to the
    # select as a value that is not one of its options — which `ui.select` raises on
    # at BUILD time, taking the rest of the tab down with it. Clamp to something
    # offered; the engine still reports `camp-wrong-origin` in the issue panel, which
    # is where a mismatch belongs. Unreachable until Cult Dragon-Blooded shipped
    # (2026-08-12) — with one splat owning every camp, the value was always an option.
    # Only a MISMATCH is clamped. A character with no camp chosen yet keeps the empty
    # select it has always had — filling it in here would show a camp the character
    # does not actually hold.
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
            # A flat-pool choice reaches here with `options` still empty, and that is
            # what tells the editor to render only the Charm multi-select: the shape
            # has no style step, and a select over nothing would be an empty dropdown
            # the player can neither use nor dismiss.
            #
            # Choosing the style is only half a category choice — the page grants
            # "two Charms from ONE of four martial arts" (p.90), so the player also
            # picks WHICH. Offer the chosen style's whole roster, flagging any Charm
            # whose own trait minimums the character does not meet (still selectable:
            # validate.granted_charm_issues reports it as granted-charm-minimum, and
            # raising the trait later clears it).
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
