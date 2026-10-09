"""
ui/view/adversary_rows.py — the adversary cards, the ally views, and the rows
of the adversary catalogue picker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from ...engine import adversaries as advmod
from ...models.adversary import Adversary
from ...models.character import Character
from ...models.rules import AbilityName, Damage, RuleSet

from .play_state import build_party_card_view


# --------------------------------------------------------------------------- #
# Adversary card presentation
#
# Moved verbatim out of `ui/adversaries.py` 2026-08-10 (the engine module was
# aliased `adv` there and is `advmod` here — the only edit). Display composition,
# not rules: every number comes from `engine.adversaries`, this just words it.
#
# Their siblings `trait_line` / `attack_line` did NOT come here despite also being
# model-to-text: those are half of a round-tripped edit-field codec and live with
# their parsers in `engine/adversaries.py`. See the note above them there.
# --------------------------------------------------------------------------- #

def summary_line(ruleset: RuleSet, a: Adversary) -> str:
    """The one-line stat readout under the name: initiative, dodge, soak.

    Reads through the engine so the armour's mobility penalty and soak land here
    the same way they would anywhere else."""
    lethal, bashing = advmod.soak(ruleset, a)
    dodge = advmod.dodge_after_armor(ruleset, a)
    bits = []
    if a.base_initiative is not None:
        bits.append(f"Init {a.base_initiative}")
    # An extra's single pool replaces every Attribute + Ability roll it makes, so
    # it belongs on the stat line rather than buried among the traits.
    if a.combat_pool is not None:
        bits.append(f"Pool {a.combat_pool}")
    bits.append(f"Dodge {dodge}" if dodge is not None else "No dodge")
    bits.append(f"Soak {lethal}L/{bashing}B")
    if a.essence:
        bits.append(f"Essence {a.essence}")
    if a.cost_to_materialize:
        bits.append(f"Materialize {a.cost_to_materialize}")
    if a.cost_to_dematerialize:
        bits.append(f"Dematerialize {a.cost_to_dematerialize}")
    # The shield's contribution the dodge pool cannot show: the book prints this
    # on the statblocks themselves ("+1 difficulty to attack"), and nothing here
    # resolves an attack, so the Storyteller applies it.
    melee, ranged = advmod.attack_difficulty(ruleset, a)
    if melee or ranged:
        bits.append(f"+{melee}/+{ranged} difficulty to hit (melee/ranged)")
    return "  ·  ".join(bits)


@dataclass(frozen=True)
class AllyBox:
    """One health box of an ally: the label and the mark, or None."""
    label: str
    mark: Optional[Damage]


@dataclass(frozen=True)
class AllyView:
    """What the page of a player gets of an ally: the name and the health track (R7).

    ⚠ The page of a player is built from this and from nothing else. An attribute
    added here reaches the browser of each player. `key` is the id of the entry or
    of the copy. It identifies the element, and it is not shown.
    """
    key: str
    name: str
    boxes: tuple[AllyBox, ...]


def ally_view(a: Adversary) -> AllyView:
    """Project the roster entry `a` to its name and health track."""
    marks = advmod.normalize_damage(a)
    return AllyView(a.id, a.name or "(unnamed)", tuple(
        AllyBox(advmod.level_label(penalty), mark)
        for penalty, mark in zip(a.health_levels, marks)))


def character_ally_view(ruleset: RuleSet, character: Character, key: str) -> AllyView:
    """Project the full character `character` to its name and health track. `key` is
    the id of the copy."""
    play = build_party_card_view(ruleset, character).play
    health = list((character.play.health if character.play else []))
    return AllyView(key, character.name or "(unnamed)", tuple(
        AllyBox(box.label, health[i] if i < len(health) else None)
        for i, box in enumerate(play.health_boxes)))


def trait_map_line(values: dict[str, int], order: list[str]) -> str:
    """"Str 4  Dex 2  Sta 4" — the printed Attributes/Virtues, abbreviated to fit
    a card. Absent keys are skipped, never shown as 0 (a beast prints three of the
    nine, and the book means absent, not zero)."""
    return "  ".join(f"{k[:3].title()} {values[k]}" for k in order if k in values)


# --------------------------------------------------------------------------- #
# Adversary catalogue picking
#
# The roster's "add from catalogue" buttons browse the same Charms, spells and
# Backgrounds the builder does — and apply NONE of its rules. No splat filter, no
# prerequisite check, no minimum: a Storyteller giving a bandit-chief one Solar
# Charm is not building a Solar, and the roster has never validated anything (see
# engine/adversaries.py). The picker's job is to save typing, not to have opinions.
#
# ⚠ What a pick WRITES is the printed name, never the key. `Adversary.charms`,
# `.spells` and `.powers` are prose by decision, and an id in one would face the
# loader's link-checking and fail. The row key is the dialog's own handle; the
# caller turns it into a name with the map `picker_names` builds off these rows.
#
# ⚠ TWO keying schemes, and the difference is not an inconsistency:
#
#   * Charms/spells/powers key by ID, because five Charm NAMES are shared across
#     splats — "Ox-Body Technique" is seven different Charms — and keying by name
#     silently drops 18 rows and mis-files their group chip. Duplicate names in the
#     list are correct: they are different Charms, and the chips separate them.
#   * Abilities/Backgrounds key by NAME, because the name is the whole record as
#     far as an adversary is concerned. Here the collisions are the SAME Background
#     printed per splat — seven "Artifact" rows — and collapsing them to one is the
#     right answer, not a loss.
# --------------------------------------------------------------------------- #

# Title-case display names for the 25-ability roster, "martial_arts" -> "Martial Arts".
def _ability_label(name: str) -> str:
    return name.replace("_", " ").title()


def adversary_picker_rows(
    ruleset: RuleSet, kind: str,
) -> tuple[list[tuple[str, str, str, Optional[str]]], dict[str, str]]:
    """`(rows, group_of)` for one adversary picker.

    `kind` is "charms", "spells", "powers", "abilities" or "backgrounds". Rows are
    the `(key, name, summary, full)` tuples the catalogue dialog takes; `group_of`
    maps a key to its filter chip, and is empty where the list is short enough not
    to need one (25 abilities, 63 Backgrounds).

    Sorted by group then name, so the dialog is browsable before the text filter is
    touched.

    ⚠ Virtual Charms are excluded. They exist so a Dragon-Kings Path's granted
    powers can be NAMED on a sheet and are not purchasable content — the builder's
    picker hides them for that reason and this one agrees, or a GM picks a row that
    means nothing on its own. (All 60 of them are Dragon-Kings Path powers, which is
    why "Dragon-Kings" is not among the Charm chips.)
    """
    rows: list[tuple[str, str, str, Optional[str]]] = []
    group_of: dict[str, str] = {}

    if kind == "charms":
        for c in ruleset.charms.values():
            if c.virtual:
                continue
            rows.append((c.id, c.name, c.description or "", c.description or None))
            group_of[c.id] = c.exalt_type or "Other"

    elif kind == "spells":
        for sp in ruleset.spells.values():
            rows.append((sp.id, sp.name, sp.description or "", sp.description or None))
            group_of[sp.id] = getattr(sp.circle, "value", str(sp.circle))

    elif kind == "powers":
        # The separate `Powers:` line ghosts and elementals print. Two catalogues
        # feed it because the book does: the God-Blooded Elemental Powers, and the
        # Spirit Charms a ghost's line names ("Materialize, Measure the Wind").
        for pw in ruleset.elemental_powers.values():
            rows.append((pw.id, pw.name, pw.description or "", pw.description or None))
            group_of[pw.id] = "Elemental Power"
        for c in ruleset.charms.values():
            if c.virtual or c.exalt_type != "Spirit":
                continue
            rows.append((c.id, c.name, c.description or "", c.description or None))
            group_of[c.id] = "Spirit Charm"

    elif kind == "abilities":
        # The 25-ability roster, keyed and displayed by name. No group chips: 25 rows
        # fit on one screen, and the caste groupings are a chargen concept an
        # adversary has no use for. The summary is Chapter Four's per-Ability text
        # where the file carries it; there is no per-Ability dot ladder to show (the
        # rungs are generic, see TraitDescriptions).
        for ab in AbilityName:
            label = _ability_label(ab.value)
            info = (ruleset.trait_descriptions.ability(ab)
                    if ruleset.trait_descriptions else None)
            text = info.description if info else ""
            rows.append((label, label, text, text or None))

    elif kind == "backgrounds":
        # Deduped by name: the catalogue prints per-splat rows for the same
        # Background (seven "Artifact"), and an adversary's line records the name.
        # First row wins, which is arbitrary and harmless — the descriptions differ
        # only in splat-specific framing and nothing here resolves the pick.
        for b in ruleset.background_catalog.values():
            if b.name in group_of or any(r[0] == b.name for r in rows):
                continue
            rows.append((b.name, b.name, b.description or "", b.description or None))

    else:
        raise ValueError(f"unknown adversary picker kind: {kind!r}")

    rows.sort(key=lambda r: (group_of.get(r[0], ""), r[1]))
    return rows, group_of


def picker_names(rows: Sequence[tuple[str, str, str, Optional[str]]]) -> dict[str, str]:
    """`{row key: printed name}` — what a pick callback appends to the field.

    The one hop between the dialog's key and the prose the model stores. Trivial, and
    it exists so both shells make the same hop rather than each inlining it."""
    return {key: name for key, name, _summary, _full in rows}


def merit_requirement_line(ruleset: RuleSet, definition, effects=None) -> str:
    """What a Merit or Flaw REQUIRES, as one line, or "" when it requires nothing.

    Input: the rule set (to resolve prerequisite ids to printed names) and a
    `MeritFlawDefinition`. Output: "Requires: …" content — the trait minimums, the
    repeat cap, the printed note, and the entries that must already be held — joined
    with "; ". Mechanism: each source contributes its own phrase; an OR group inside
    `trait_prerequisites` is joined with " or ".

    The point of it is that a player sees the gate BEFORE the issues panel tells them
    they failed it.

    ⚠ `definition.prerequisites` — the OTHER entries an entry requires — used to be
    missing from this line in BOTH shells, which is why the line is now built here
    instead of twice. 32 entries carry one, and every one of them stated no gate at
    all: The Flow of Essence requires Essence Awareness specifically, and a
    God-Blooded holding Awakened Essence was told nothing until the validator
    refused the build (human, 2026-09-02). The field had exactly one read site,
    `engine/validate/merit_checks.py` — the dead-field shape, one read short of
    dead.

    ⚠ Tier-keyed groups are shown WHOLE. Which tier needs what is the point of
    Innocuous, and hiding the other tier's line would hide it.

    `effects` is an optional `MeritEffects` for the character being looked at. A
    prerequisite it reports as already satisfied is marked so rather than dropped —
    a God-Blooded holding Awakened Essence needs no Essence Awareness, and is barred
    from buying it, so a bare "Requires: Essence Awareness" would name something they
    cannot get and do not need. Passing nothing gives the catalogue's own statement,
    which is what a splat-independent caller wants.

    ⚠ No Merit id is named here, and none may be. Which entries substitute for which
    is `engine.merits`' business; this asks the effects object whether the id in hand
    is in its set (`prerequisites_satisfied`) and says so.
    """
    wants = [" or ".join(f"{r.trait} {r.rating}" for r in group)
             for groups in definition.trait_prerequisites.values()
             for group in groups]
    satisfied = frozenset(getattr(effects, "prerequisites_satisfied", ()) or ())
    for pid in definition.prerequisites:
        entry = ruleset.merits_flaws.get(pid)
        name = entry.name if entry is not None else pid
        wants.append(f"{name} (already satisfied)" if pid in satisfied else name)
    if definition.max_purchases_from_trait:
        wants.append(f"at most {definition.max_purchases_from_trait} purchases")
    if definition.prerequisite_note:
        wants.append(definition.prerequisite_note)
    return "; ".join(wants)
