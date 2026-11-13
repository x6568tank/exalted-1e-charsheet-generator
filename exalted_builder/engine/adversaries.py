"""
engine/adversaries.py — the small amount of computing the adversary roster needs.

No validation and no point accounting: an Adversary has no budget. The functions
here are the computation that the UI must not do: copy a template, expand the
health notation, normalize the damage track, and give soak and dodge from armor.
"""

from __future__ import annotations

import itertools
import re
from typing import Optional

from ..models.adversary import Adversary, AdversaryAttack, AdversaryTrait
from ..models.party import Party
from ..models.rules import ArmorType, Damage, RuleSet

# The mark cycle: empty -> bashing -> lethal -> aggravated -> empty, as on the Play
# tab (ui/play.py).
_MARK_CYCLE: list[Optional[Damage]] = [None, Damage.BASHING, Damage.LETHAL,
                                       Damage.AGGRAVATED]

# "-0", "-1 x 7", "-2x12", "Incap", "I" — one printed health-level token.
_LEVEL_RE = re.compile(r"^\s*(-?\d+|I|Incap\w*)\s*(?:x\s*(\d+))?\s*$", re.IGNORECASE)

# The penalty of an Incapacitated box. A sentinel: the UI shows "Incap".
INCAPACITATED = -99


def expand_health(printed: str) -> list[int]:
    """Expand a printed health track into one wound penalty per box.

    The book uses a repeat notation the roster cannot store directly:
    ``-0/-1 x 7/-2 x 12/-4/Incap`` (the Mask of Winters, p.303) is 22 boxes, not
    5. Extras print ``-1/-3/I`` (p.241) and a typical NPC ``-0/-1/-1/-2/-2/-4/
    Incap`` (p.277). Separators are ``/``; whitespace is irrelevant.

    Used at authoring and on GM input, not at render. An unparseable token is
    skipped.
    """
    out: list[int] = []
    for token in printed.split("/"):
        if not token.strip():
            continue
        m = _LEVEL_RE.match(token)
        if m is None:
            continue
        head, count = m.group(1), int(m.group(2) or 1)
        penalty = INCAPACITATED if head[0] in "iI" else int(head)
        out.extend([penalty] * count)
    return out


def format_health(levels: list[int]) -> str:
    """Return `levels` in the book notation (``-0/-1 x 7/-2 x 12/-4/Incap``). The
    inverse of expand_health for each printed track."""
    parts = []
    for penalty, group in itertools.groupby(levels):
        n = len(list(group))
        head = "Incap" if penalty == INCAPACITATED else str(penalty)
        parts.append(f"{head} x {n}" if n > 1 else head)
    return "/".join(parts)


def level_label(penalty: int) -> str:
    """The short label under one health box: "Incap", "-0", "-2"."""
    return "Incap" if penalty == INCAPACITATED else str(penalty)


def normalize_damage(adversary: Adversary) -> list[Optional[Damage]]:
    """Pad or trim the marks to the track length. Return the live list."""
    n = len(adversary.health_levels)
    marks = adversary.damage
    if len(marks) < n:
        marks += [None] * (n - len(marks))
    elif len(marks) > n:
        del marks[n:]
    return marks


def cycle_mark(adversary: Adversary, index: int) -> None:
    """Step one health box to its next mark: empty -> / -> x -> * -> empty."""
    marks = normalize_damage(adversary)
    if 0 <= index < len(marks):
        marks[index] = _MARK_CYCLE[(_MARK_CYCLE.index(marks[index]) + 1) % len(_MARK_CYCLE)]


def worst_penalty(adversary: Adversary) -> Optional[int]:
    """Return the penalty of the deepest marked box, or None if undamaged. Fill
    order is not enforced.
    """
    marks = normalize_damage(adversary)
    marked = [p for p, m in zip(adversary.health_levels, marks) if m is not None]
    return min(marked) if marked else None


def armor_options(ruleset: RuleSet) -> list[ArmorType]:
    """Return the mundane armor that an entry can wear. Artifact armor is excluded
    (human's ruling), by `artifact_rating`."""
    return sorted((a for a in ruleset.body_armor() if not a.artifact_rating),
                  key=lambda a: a.name)


def armor_of(ruleset: RuleSet, adversary: Adversary) -> Optional[ArmorType]:
    """Return the worn armor, or None. An unknown id gives None."""
    return ruleset.armor_catalog.get(adversary.armor_id) if adversary.armor_id else None


def shield_options(ruleset: RuleSet) -> list[ArmorType]:
    """Return the shields that an entry can carry: ArmorType rows tagged "shield".
    The three p.335 shields are mundane, thus there is no filter."""
    return sorted(ruleset.shields(), key=lambda s: s.name)


def shield_of(ruleset: RuleSet, adversary: Adversary) -> Optional[ArmorType]:
    """Return the carried shield, or None. An unknown id gives None."""
    return ruleset.armor_catalog.get(adversary.shield_id) if adversary.shield_id else None


def attack_difficulty(ruleset: RuleSet, adversary: Adversary) -> tuple[int, int]:
    """Return the (melee, ranged) difficulty bonuses of the carried shield. Display
    only (decision 0008)."""
    shield = shield_of(ruleset, adversary)
    return (shield.difficulty_melee, shield.difficulty_ranged) if shield else (0, 0)


def soak(ruleset: RuleSet, adversary: Adversary) -> tuple[int, int]:
    """Return (lethal, bashing) soak: natural soak plus armor, as the book prints it
    (Elite Troops: natural 0L/4B plus the armor 6L/8B)."""
    worn = armor_of(ruleset, adversary)
    if worn is None:
        return adversary.soak_lethal, adversary.soak_bashing
    return (adversary.soak_lethal + worn.soak_lethal,
            adversary.soak_bashing + worn.soak_bashing)


def dodge_after_armor(ruleset: RuleSet, adversary: Adversary) -> Optional[int]:
    """Return the dodge pool after the mobility penalty of the armor AND the shield
    (p.278; human's ruling).

    ⚠ Include the SHIELD. p.335: a target shield adds 1 to the mobility penalty.
    Infantry 3-(2+1)=0, elite troops 5-(2+1)=2, as printed.

    None (not 0) if the entry does not dodge. Never negative."""
    if adversary.dodge is None:
        return None
    worn = armor_of(ruleset, adversary)
    shield = shield_of(ruleset, adversary)
    penalty = (abs(worn.mobility_penalty) if worn else 0) + \
              (abs(shield.mobility_penalty) if shield else 0)
    return max(0, adversary.dodge - penalty)


def instantiate(template: Adversary, new_id: str, *, name: str = "") -> Adversary:
    """Return an independent copy of a catalogue template, with id `new_id`.

    A deep copy. The catalogue row is never changed, thus damage on one copy does not
    reach another.
    """
    entry = template.model_copy(deep=True)
    entry.id = new_id
    entry.template_id = template.id
    if name:
        entry.name = name
    # A fresh entry starts undamaged and unspent, whatever state the source was in.
    entry.damage = []
    entry.willpower_spent = 0
    entry.motes_spent = 0
    return entry


# --------------------------------------------------------------------------- #
# Roster mutations
#
# Both shells (`ui/adversaries.py`, `qt/adversaries.py`) use these functions. Each
# returns what the caller selects or reports.
# --------------------------------------------------------------------------- #

def add_blank(party: Party, *, name: str = "New adversary",
              health: str = "-1/-3/I") -> Adversary:
    """Append an empty entry with the extra's printed three-level track (p.241)."""
    entry = Adversary(id=next_id(party), name=name, health_levels=expand_health(health))
    party.adversaries.append(entry)
    return entry


def add_from_template(party: Party, template: Adversary) -> Adversary:
    """Append an editable copy of a catalogue row. The row is never written to."""
    entry = instantiate(template, next_id(party))
    party.adversaries.append(entry)
    return entry


def duplicate(party: Party, index: int) -> Adversary:
    """Append a numbered copy of entry `index` next to it."""
    source = party.adversaries[index]
    copy = instantiate(source, next_id(party),
                       name=_copy_name(party.adversaries, source.name))
    party.adversaries.insert(index + 1, copy)
    return copy


def remove(party: Party, index: int) -> str:
    """Remove entry `index`. Return its name."""
    gone = party.adversaries[index].name or "adversary"
    del party.adversaries[index]
    return gone


def reset_tracking(adversary: Adversary) -> None:
    """Clear damage and both spent pools. Not a healing rule.

    ⚠ The three fields that `instantiate` clears: `damage`, `willpower_spent`,
    `motes_spent`.
    """
    adversary.damage = []
    adversary.willpower_spent = 0
    adversary.motes_spent = 0


def mote_cap(adversary: Adversary) -> int:
    """Return the maximum of the one mote track, for either pool shape. 0 = no
    motes."""
    return adversary.essence_pool or (adversary.personal_essence
                                      + adversary.peripheral_essence)


def set_motes_spent(adversary: Adversary, value) -> None:
    """Write the mote counter, clamped to the entry's own pool."""
    adversary.motes_spent = max(0, min(mote_cap(adversary), int(value or 0)))


def set_count(adversary: Adversary, field: str, clicked: int, cap: int) -> None:
    """Fill track `field` to box `clicked`, or empty it to there if that box is the
    last full one. The behavior of engine.play.set_count."""
    cur = getattr(adversary, field)
    setattr(adversary, field, max(0, min(cap, clicked if clicked + 1 == cur
                                         else clicked + 1)))


# --------------------------------------------------------------------------- #
# Ids, duplicate naming, and the free-text trait/attack codec
#
# ⚠ `parse_traits`/`trait_line` and `parse_attacks`/`attack_line` are CODEC PAIRS. The
# `*_line` function fills the input. The `parse_*` function reads it back.
# `tests/test_adversaries_ui.py` asserts the round trip. Change both sides.
# --------------------------------------------------------------------------- #

def next_id(party: Party) -> str:
    """Return an id unique in the roster. Never collides after a delete."""
    used = {a.id for a in party.adversaries}
    n = len(party.adversaries) + 1
    while f"adv.{n}" in used:
        n += 1
    return f"adv.{n}"


def _copy_name(existing: list[Adversary], base: str) -> str:
    """Return a numbered name: "Bandit" -> "Bandit 2" -> "Bandit 3"."""
    stem = (base or "Adversary").rstrip()
    taken = {a.name for a in existing}
    n = 2
    while f"{stem} {n}" in taken:
        n += 1
    return f"{stem} {n}"


def category_line(categories: list[str]) -> str:
    """The roster's filing labels as one editable line: "Undead, Soldier"."""
    return ", ".join(categories)


def parse_categories(text: str) -> list[str]:
    """Read the category line back. Drop blanks and duplicates. Keep the order.

    ⚠ A CODEC PAIR with `category_line`. The round trip is asserted.
    """
    return list(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))


def category_label(adversary: Adversary) -> str:
    """The filing labels as one cell/line of display: "Undead · Soldier"."""
    return "  ·  ".join(adversary.categories)


def catalogue_groups(templates) -> dict[str, list[str]]:
    """Return `{template id: its categories}` for the picker chips. ⚠ All categories,
    not the first."""
    return {t.id: list(t.categories) for t in templates}


def attack_line(atk: AdversaryAttack) -> str:
    """One printed attack, rendered the way the book prints it."""
    parts = []
    if atk.speed is not None:
        parts.append(f"Spd {atk.speed}")
    if atk.accuracy is not None:
        parts.append(f"Acc {atk.accuracy}")
    if atk.damage is not None:
        parts.append(f"Dmg {atk.damage}{atk.damage_type}")
    if atk.defense is not None:
        parts.append(f"Def {atk.defense}")
    line = f"{atk.name}: " + " ".join(parts) if parts else atk.name
    return f"{line}  ({atk.note})" if atk.note else line


def trait_line(traits: list[AdversaryTrait]) -> str:
    """"Melee 3 (Swords +2), Dodge 2" — the book's own inline format."""
    out = []
    for t in traits:
        text = f"{t.name} {t.rating}"
        if t.specialties:
            text += f" ({t.specialties})"
        out.append(text)
    return ", ".join(out)



# --------------------------------------------------------------------------- #
# Parsing the two free-text trait fields
#
# The GM types these the way the book prints them, so the roster reads them back
# the same way rather than making them fill a row of boxes per Ability.


def parse_traits(text: str) -> list[AdversaryTrait]:
    """"Melee 3 (Swords +2), Dodge 2" -> two AdversaryTraits.

    An unrated entry gets rating 0. A stray comma gives nothing."""
    out: list[AdversaryTrait] = []
    depth = 0
    current = ""
    # Split on commas that are NOT inside the parenthesised specialty list —
    # "Linguistics 5 (Native: Old Realm; High Realm, Riverspeak)" is one trait.
    for ch in text or "":
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(current)
            current = ""
        else:
            current += ch
    out.append(current)

    traits: list[AdversaryTrait] = []
    for chunk in out:
        chunk = chunk.strip()
        if not chunk:
            continue
        spec = ""
        if chunk.endswith(")") and "(" in chunk:
            head, _, tail = chunk.rpartition("(")
            spec, chunk = tail[:-1].strip(), head.strip()
        parts = chunk.rsplit(" ", 1)
        if len(parts) == 2 and parts[1].lstrip("-").isdigit():
            traits.append(AdversaryTrait(name=parts[0].strip(), rating=int(parts[1]),
                                         specialties=spec))
        else:
            traits.append(AdversaryTrait(name=chunk, rating=0, specialties=spec))
    return traits


# --------------------------------------------------------------------------- #
# Catalogue picking
#
# The picker writes the printed NAME, never the id: `charms`, `spells` and `powers`
# are prose (see the models docstring). These two helpers are the ONE write path.


def _already_lists(text: str, name: str) -> bool:
    """Return True if `name` is an entry of `text`. Splits on commas and sentence
    ends, thus a substring does not match ("Strike" in "Excellent Strike")."""
    wanted = name.strip().casefold()
    return any(part.strip().casefold() == wanted
               for part in re.split(r"[,.!?]", text or ""))


def append_prose(existing: str, name: str) -> str:
    """Return `existing` with `name` added.

    Empty field: the name. After sentence punctuation: a space, then the name. Else a
    comma list. Idempotent and case-insensitive."""
    existing = (existing or "").strip()
    name = (name or "").strip()
    if not name or _already_lists(existing, name):
        return existing
    if not existing:
        return name
    if existing.endswith((".", "!", "?")):
        return f"{existing} {name}"
    return f"{existing.rstrip(',')}, {name}"


def append_trait(line: str, name: str, rating: int = 1) -> str:
    """Return `line` with the trait `name` added, through `trait_line`.

    ⚠ The default rating is 1, NOT the 0 that `parse_traits` gives: "Awareness 0"
    claims a printed zero. A trait on the line already is not changed."""
    name = (name or "").strip()
    traits = parse_traits(line)
    if not name or any(t.name.strip().casefold() == name.casefold() for t in traits):
        return line
    return trait_line(traits + [AdversaryTrait(name=name, rating=rating)])


def parse_attacks(text: str) -> list[AdversaryAttack]:
    """One attack per line, in the book's own wording:

        Bite: Speed 6 Accuracy 7 Damage 1L Defense 5
        Venom: Speed 18 Accuracy 8 Damage 24L  (once per 10 turns)

    Keywords match with any case and each is optional."""
    import re

    out: list[AdversaryAttack] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        note = ""
        if "(" in line and line.endswith(")"):
            head, _, tail = line.rpartition("(")
            note, line = tail[:-1].strip(), head.strip()
        name, _, rest = line.partition(":")
        if not rest:
            name, rest = line, ""

        def grab(word: str) -> Optional[int]:
            m = re.search(rf"{word}\s*(-?\d+)", rest, re.IGNORECASE)
            return int(m.group(1)) if m else None

        dmg_match = re.search(r"(?:damage|dmg)\s*(-?\d+)\s*([BLA])?", rest, re.IGNORECASE)
        out.append(AdversaryAttack(
            name=name.strip() or "Attack",
            speed=grab(r"(?:speed|spd)"),
            accuracy=grab(r"(?:accuracy|acc|atk)"),
            damage=int(dmg_match.group(1)) if dmg_match else None,
            damage_type=(dmg_match.group(2) or "").upper() if dmg_match else "",
            defense=grab(r"(?:defense|def)"),
            note=note))
    return out
