"""
ui/view/dice_pools.py — the dice-pool calculator (decision 0016). It gives a
BASE pool, never a final pool.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Optional

from ...engine.labels import _label
from ...models.character import Character, Weapon
from ...models.rules import AbilityName, AttributeName, PoolKind, RuleSet, VirtueName


# --------------------------------------------------------------------------- #
# The dice-pool calculator (decision 0016)
#
# A BASE pool, never a final one. Everything derived lives here so the widget
# module only lays out what this returns — including the exclusions text, which is
# not decoration: it is the mitigation 0016 accepted for 0008's objection that a
# static combat number "looks authoritative and is wrong the moment a Charm fires".
# --------------------------------------------------------------------------- #

@dataclass
class PoolChoicesView:
    """Everything the calculator's controls can offer for one selected roll —
    which of them are relevant is a property of the RollDefinition, so the widget
    module never has to know that (say) a Virtue check takes no weapon."""
    needs_weapon: bool
    needs_virtue: bool
    weapons: list[str]                       # inline weapon names, in owned order
    virtues: list[str]                       # display labels
    specialties: list[str]                   # "Swords (+2 dice)" for the ones that apply
    takes_mobility: bool                     # this roll carries the armour penalty
    mobility_lines: list[str]                # what would be subtracted, for the toggle label
    takes_wound: bool                        # False where a page exempts the roll (p.233)
    wound_exempt_note: str = ""              # why, when it does not
    fatigue_points: int = 0                  # accumulated armour fatigue, as a positive count


@dataclass
class PoolView:
    """One computed base pool, ready to render."""
    roll_name: str
    lines: list[tuple[str, int]]             # (label, signed value), in order
    total: int
    summary: str                             # "Dexterity 4 + Melee 3 … = 9"
    excludes: list[str]
    notes: str = ""
    wound_label: str = ""                    # "-2", "Incapacitated", or ""
    below_one: bool = False                  # penalties took it under a single die


def pool_roll_options(ruleset: RuleSet) -> list[tuple[str, str]]:
    """(id, label) for every shipped roll, grouped by category in the label so one
    flat select reads as a grouped one. Empty when no dice_pools.json shipped."""
    rows = sorted(ruleset.roll_catalog.values(), key=lambda r: (r.category, r.name))
    return [(r.id, f"{r.category} · {r.name}" if r.category else r.name) for r in rows]


def build_pool_choices(ruleset: RuleSet, character: Character,
                       roll) -> PoolChoicesView:
    from ...engine import pools as poolsmod
    return PoolChoicesView(
        needs_weapon=roll.weapon_stat.value != "none",
        needs_virtue=roll.kind.value == "virtue",
        weapons=[w.name or "(unnamed)" for w in character.weapons],
        virtues=[v.value.title() for v in VirtueName],
        # One entry per NAME, already summed across instances — see SpecialtyOption.
        specialties=[f"{s.name} (+{s.dice} {'die' if s.dice == 1 else 'dice'})"
                     for s in poolsmod.specialties_for(character, roll)],
        takes_mobility=roll.mobility_applies,
        mobility_lines=[f"{name} -{points}" for name, points
                        in poolsmod.mobility_penalty(ruleset, character)],
        takes_wound=roll.wound_applies,
        wound_exempt_note=("" if roll.wound_applies else
                           "Wound penalties do not subtract from this roll (p.233)."),
        fatigue_points=-poolsmod.fatigue_penalty(character),
    )


def build_pool_view(ruleset: RuleSet, character: Character, roll, *,
                    weapon_index: Optional[int] = None,
                    virtue: Optional[VirtueName] = None,
                    specialty_index: Optional[int] = None,
                    include_mobility: bool = True,
                    include_wound: bool = True,
                    include_fatigue: bool = True) -> PoolView:
    """Compute the base pool for `roll` with the calculator's current selections.

    The wound and fatigue penalties are read HERE — the visible play-state reads,
    handed to the engine as plain integers (decision 0006; see engine/pools.py).
    `include_wound` / `include_fatigue` are the toggles, so switching one off is a
    presentation choice that never has to reach into Character.play.

    ⚠ `include_wound=True` is a REQUEST, not a guarantee: a roll whose row is
    exempt (p.233) drops the line inside the engine. Read the returned lines, never
    the flag, to know what is in the total.
    """
    from ...engine import pools as poolsmod
    penalty, wound_label = poolsmod.wound_penalty(ruleset, character)
    fatigue = poolsmod.fatigue_penalty(character)
    weapon = (character.weapons[weapon_index]
              if weapon_index is not None and 0 <= weapon_index < len(character.weapons)
              else None)
    applicable = poolsmod.specialties_for(character, roll)
    specialty = (applicable[specialty_index]
                 if specialty_index is not None and 0 <= specialty_index < len(applicable)
                 else None)
    bd = poolsmod.base_pool(
        ruleset, character, roll,
        weapon=weapon, virtue=virtue, specialty=specialty,
        include_mobility=include_mobility,
        wound_penalty=penalty if include_wound else 0,
        fatigue_penalty=fatigue if include_fatigue else 0)
    return PoolView(
        roll_name=bd.roll,
        lines=[(ln.label, ln.value) for ln in bd.lines],
        total=bd.total,
        summary=bd.summary,
        excludes=list(bd.excludes),
        notes=bd.notes,
        wound_label=wound_label,
        below_one=bd.below_one,
    )


@dataclass
class PoolRow:
    """One roll in the sidebar list: a name, its arithmetic on one line, and the
    total. `compact` is a BREAKDOWN, not a caption — a row that showed only `total`
    would be the bare number decision 0016 forbids."""
    name: str
    compact: str                             # "+4 dex +3 melee +2 acc -1 wnd -2 ftg"
    total: int
    below_one: bool = False
    note: str = ""                           # a printed rider worth one short line


@dataclass
class PoolSidebarView:
    """Everything the dice-pool sidebar renders: the shared controls at the top, the
    grouped roll list in the middle, and the standing exclusions at the bottom."""
    # (index into character.weapons, display name). PAIRS rather than a bare list
    # because the list is now FILTERED — ammunition is excluded — and a filtered list
    # whose position was used as the index would attack with the wrong weapon.
    weapons: list[tuple[int, str]]
    groups: list[tuple[str, list[PoolRow]]]  # (category, rows), in catalogue order
    excludes: list[str]
    wound_label: str = ""                    # "-1", "Incapacitated", or ""
    fatigue_points: int = 0
    mobility_lines: list[str] = dc_field(default_factory=list)
    any_below_one: bool = False
    # Ammunition the character carries, same (index, name) shape. Only populated when
    # the chosen weapon is one that fires it.
    arrows: list[tuple[int, str]] = dc_field(default_factory=list)
    # The chosen arrow's printed damage line — REFERENCE, never a pool term. An arrow
    # changes what the shot does, not what you roll to hit (core p.330 gives arrows a
    # base damage and a soak clause and no accuracy at all), and decision 0008 keeps
    # damage out of this build entirely. Shown beside the Archery rows so the player
    # can see which arrow is nocked without it touching a single die.
    arrow_note: str = ""


def _ammunition_indices(ruleset: RuleSet, character: Character) -> set[int]:
    """Positions in `character.weapons` holding ammunition rather than a weapon.

    The character's `Weapon` is an inline copy carrying no tags (decision 0007), so the
    kind is recovered by matching the name back to the catalogue — the same recovery
    `pools.weapon_abilities` does, and with the same failure direction: a homebrew name
    matches nothing and is treated as a weapon, because a custom weapon that silently
    stopped being attackable-with would be the worse bug."""
    ammo = {w.name for w in ruleset.weapon_catalog.values() if "ammunition" in w.tags}
    return {i for i, w in enumerate(character.weapons) if w.name in ammo}


def _fires_ammunition(ruleset: RuleSet, weapon: Optional[Weapon]) -> bool:
    """Whether this weapon takes arrows — an Archery weapon that is not itself ammo."""
    if weapon is None:
        return False
    entry = next((w for w in ruleset.weapon_catalog.values() if w.name == weapon.name),
                 None)
    return entry is not None and "archery" in entry.tags and "ammunition" not in entry.tags


def clamp_pool_selection(state: dict, sidebar: PoolSidebarView) -> None:
    """Drop a weapon/arrow choice that no longer names a row, in place.

    `state` OUTLIVES the weapon list it indexes: the Play tab's sidebar is rebuilt on
    every play-state change, and between two builds the player can delete a weapon on
    the equipment surface. A `ui.select` whose value is not among its options raises at
    BUILD time and takes the whole tab down with it, siblings included
    (`docs/adding-a-splat.md` trap #3).

    Clearing rather than remapping is deliberate: the list renumbers when a row is
    deleted, so the index that survives names a DIFFERENT weapon than the one chosen.

    ⚠ A PURE function so it can be tested without the browser harness. Driving this
    through a delete-and-rebuild is untestable in a full-suite run: a `@ui.page` route
    builds once per session and `user.client.elements` accumulates across every route
    the session has opened, so "the last select labelled X" — and `user.find(marker=
    ...)` with it — can belong to another page entirely. Such a test passes alone and
    fails in the suite, firing its trigger at somebody else's widget.
    """
    for key, rows in (("weapon", sidebar.weapons), ("arrow", sidebar.arrows)):
        if state.get(key) not in {i for i, _ in rows}:
            state[key] = None


def build_pool_sidebar(ruleset: RuleSet, character: Character, *,
                       weapon_index: Optional[int] = None,
                       arrow_index: Optional[int] = None,
                       include_mobility: bool = True,
                       include_wound: bool = True,
                       include_fatigue: bool = True) -> PoolSidebarView:
    """Every roll the catalogue knows, computed at once for the sidebar.

    Two rolls expand into several rows, because in a LIST there is nothing to pick
    from — the choice has to be visible as separate lines:

    * a Virtue check becomes one row per Virtue;
    * a roll whose Ability carries specialties gets one extra row per specialty
      NAME, since a specialty applies only to its own facet (p.134) and folding it
      into the base row would claim dice the character does not always have.
    """
    from ...engine import pools as poolsmod
    penalty, wound_label = poolsmod.wound_penalty(ruleset, character)
    fatigue = poolsmod.fatigue_penalty(character)
    weapon = (character.weapons[weapon_index]
              if weapon_index is not None and 0 <= weapon_index < len(character.weapons)
              else None)

    def _row(roll, name: str, **kw) -> PoolRow:
        # The weapon joins only the rolls it is actually used with — a daiklave
        # lends nothing to an Archery pool. Unknown (homebrew) weapons apply
        # everywhere, which is the safe direction.
        wp = weapon if (weapon is not None
                        and poolsmod.weapon_applies(ruleset, weapon, roll)) else None
        bd = poolsmod.base_pool(
            ruleset, character, roll, weapon=wp,
            include_mobility=include_mobility,
            wound_penalty=penalty if include_wound else 0,
            fatigue_penalty=fatigue if include_fatigue else 0, **kw)
        return PoolRow(name=name, compact=bd.compact, total=bd.total,
                       below_one=bd.below_one, note=bd.notes)

    groups: dict[str, list[PoolRow]] = {}
    for roll in sorted(ruleset.roll_catalog.values(),
                       key=lambda r: (r.category, r.name)):
        rows = groups.setdefault(roll.category or "Other", [])
        if roll.kind is PoolKind.VIRTUE:
            rows += [_row(roll, f"{roll.name} — {v.value.title()}", virtue=v)
                     for v in VirtueName]
            continue
        rows.append(_row(roll, roll.name))
        for spec in poolsmod.specialties_for(character, roll):
            rows.append(_row(roll, f"{roll.name} · {spec.name}", specialty=spec))

    ammo_idx = _ammunition_indices(ruleset, character)
    arrows: list[tuple[int, str]] = []
    arrow_note = ""
    if _fires_ammunition(ruleset, weapon):
        arrows = [(i, character.weapons[i].name or "(unnamed)") for i in sorted(ammo_idx)]
        if arrow_index is not None and arrow_index in ammo_idx:
            arrow = character.weapons[arrow_index]
            sign = "+" if arrow.damage >= 0 else ""
            arrow_note = (f"{arrow.name}: Strength {sign}{arrow.damage}"
                          f"{arrow.damage_type or 'L'} base damage"
                          + (f" — {arrow.notes}" if arrow.notes else ""))

    return PoolSidebarView(
        weapons=[(i, w.name or "(unnamed)") for i, w in enumerate(character.weapons)
                 if i not in ammo_idx],
        arrows=arrows,
        arrow_note=arrow_note,
        groups=list(groups.items()),
        excludes=list(poolsmod.EXCLUDES),
        wound_label=wound_label,
        fatigue_points=-fatigue,
        mobility_lines=[f"{name} -{points}" for name, points
                        in poolsmod.mobility_penalty(ruleset, character)],
        any_below_one=any(r.below_one for rows in groups.values() for r in rows),
    )


def pool_trait_options() -> tuple[dict[str, str], dict[str, str]]:
    """(attributes, abilities) as {enum value: label} for the custom-pool selects.
    The full nine and the full 25 — a custom pool is for whatever the table is
    doing, so nothing is filtered by caste, favouring or rating."""
    return ({a.value: _label(a.value) for a in AttributeName},
            {a.value: _label(a.value) for a in AbilityName})


def pool_mobility_lines(ruleset: RuleSet, character: Character) -> list[str]:
    """"Buff Jacket -1" per worn piece, for a surface that needs to know whether the
    armour-mobility question arises at all. Same read `build_pool_sidebar` does."""
    from ...engine import pools as poolsmod
    return [f"{name} -{points}"
            for name, points in poolsmod.mobility_penalty(ruleset, character)]


def build_custom_pool(ruleset: RuleSet, character: Character,
                      attribute: AttributeName, ability: AbilityName, *,
                      agility_based: bool = False,
                      include_mobility: bool = True,
                      include_wound: bool = True,
                      include_fatigue: bool = True) -> list[PoolRow]:
    """The player's own Attribute + Ability pool, plus one row per applicable
    specialty (same reasoning as the preset rows — p.134 scopes a specialty to its
    own facet, so it cannot be folded into the base row).

    `agility_based` is the player's answer to p.332's discretionary clause, not a
    guess: the mobility penalty applies to dodge and whole-body Athletics feats by
    the printed rule, and to anything else "the Storyteller deems becomes more
    difficult in 20 or more pounds of protective gear".
    """
    from ...engine import pools as poolsmod
    penalty, _ = poolsmod.wound_penalty(ruleset, character)
    fatigue = poolsmod.fatigue_penalty(character)
    roll = poolsmod.custom_roll(attribute, ability, mobility_applies=agility_based)

    def _row(name: str, **kw) -> PoolRow:
        bd = poolsmod.base_pool(
            ruleset, character, roll,
            include_mobility=include_mobility,
            wound_penalty=penalty if include_wound else 0,
            fatigue_penalty=fatigue if include_fatigue else 0, **kw)
        return PoolRow(name=name, compact=bd.compact, total=bd.total,
                       below_one=bd.below_one)

    rows = [_row(roll.name)]
    rows += [_row(f"{roll.name} · {s.name}", specialty=s)
             for s in poolsmod.specialties_for(character, roll)]
    return rows


@dataclass(frozen=True)
class InitiativeView:
    """The initiative rating as a surface shows it: the number, its arithmetic,
    and the standing riders.

    ⚠ NOT a `PoolRow`, and the separate type is the point — a rating rendered in
    the pool list is a number in DICE beside a roller, which is how a player ends
    up rolling nine dice for a rating that takes ONE d10. `engine/initiative.py`
    carries the rule and decision 0019's condition.
    """
    total: int
    compact: str                             # "+4 dex +2 wits +3 spd"
    summary: str                             # "Dexterity 4 + Wits 2 + ... = 9"
    weapon: str                              # "" when unarmed
    excludes: tuple[str, ...] = ()
    turn_note: str = ""
    tie_break: str = ""


def wielded_index(character: Character) -> Optional[int]:
    """In: a character. Out: the index of the first weapon whose name is
    `PlayState.in_hand`, or None for unarmed and for a name that no weapon has."""
    name = character.play.in_hand if character.play is not None else ""
    if not name:
        return None
    for i, weapon in enumerate(character.weapons):
        if weapon.name == name:
            return i
    return None


def build_initiative(ruleset: RuleSet, character: Character, *,
                     weapon_index: Optional[int] = None) -> InitiativeView:
    """The initiative rating for the weapon at `weapon_index` (None = unarmed).

    Takes the SAME index the pool sidebar's "Attack with" control uses, so the
    two surfaces cannot disagree about what is in the character's hand.
    """
    from ...engine import initiative as initmod
    weapon = (character.weapons[weapon_index]
              if weapon_index is not None and 0 <= weapon_index < len(character.weapons)
              else None)
    rating = initmod.initiative(ruleset, character, weapon=weapon)
    return InitiativeView(
        total=rating.total, compact=rating.compact, summary=rating.summary,
        weapon=(weapon.name or "Weapon") if weapon is not None else "",
        excludes=rating.excludes, turn_note=rating.turn_note,
        tie_break=rating.tie_break)
