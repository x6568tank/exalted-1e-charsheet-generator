"""
engine/adversaries.py — the small amount of computing the adversary roster needs.

There is no validation here and no point accounting: an Adversary is never built
to a budget, so there is nothing to check it against. What lives here is the
handful of pure functions the UI must not do itself — instantiating a catalogue
template into an editable copy, expanding the book's health-level notation,
normalising the damage track, and turning a worn armour into soak and a dodge
penalty.

The rule this module exists to keep: the roster page draws widgets, it does not
compute. Same boundary as everywhere else — ui -> engine -> models.
"""

from __future__ import annotations

import itertools
import re
from typing import Optional

from ..models.adversary import Adversary, AdversaryAttack, AdversaryTrait
from ..models.party import Party
from ..models.rules import ArmorType, Damage, RuleSet

# Marks cycle empty -> bashing -> lethal -> aggravated -> empty, the same order
# and the same symbols the Play tab uses (ui/play.py). Kept in step deliberately:
# a GM should not have to learn two damage trackers.
_MARK_CYCLE: list[Optional[Damage]] = [None, Damage.BASHING, Damage.LETHAL,
                                       Damage.AGGRAVATED]

# "-0", "-1 x 7", "-2x12", "Incap", "I" — one printed health-level token.
_LEVEL_RE = re.compile(r"^\s*(-?\d+|I|Incap\w*)\s*(?:x\s*(\d+))?\s*$", re.IGNORECASE)

# The wound penalty an Incapacitated box carries. The book prints the box as a
# word rather than a number on every template; -4 is what the printed NPC tracks
# put immediately before it, and Incapacitated is not a dice penalty at all — the
# character is out. Stored as a sentinel so the UI can label it "Incap".
INCAPACITATED = -99


def expand_health(printed: str) -> list[int]:
    """Expand a printed health track into one wound penalty per box.

    The book uses a repeat notation the roster cannot store directly:
    ``-0/-1 x 7/-2 x 12/-4/Incap`` (the Mask of Winters, p.303) is 22 boxes, not
    5. Extras print ``-1/-3/I`` (p.241) and a typical NPC ``-0/-1/-1/-2/-2/-4/
    Incap`` (p.277). Separators are ``/``; whitespace is irrelevant.

    Called when authoring catalogue data and when a GM types a track by hand —
    never at render time, which reads the expanded list straight off the model.

    Unparseable tokens are skipped rather than raising: this runs on GM input.
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
    """Render an expanded track back into the book's notation, so a GM editing an
    entry sees ``-0/-1 x 7/-2 x 12/-4/Incap`` rather than 22 numbers. Inverse of
    expand_health for every track the book actually prints."""
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
    """Pad/trim the stored marks to the current track length and return the live
    list. Mirrors ui.play.normalize_health — editing an entry's health levels
    later must not corrupt or drop the marks already on it."""
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
    """The deepest marked box's wound penalty, or None when undamaged.

    A convenience read of the marks, exactly like ui.play.worst_penalty: it does
    not enforce fill order, because the GM is in charge of which boxes are ticked.
    """
    marks = normalize_damage(adversary)
    marked = [p for p, m in zip(adversary.health_levels, marks) if m is not None]
    return min(marked) if marked else None


def armor_options(ruleset: RuleSet) -> list[ArmorType]:
    """The armour a roster entry may wear: mundane only.

    Artifact armour is filtered out by the human's ruling — the roster is for
    throwaway opposition, and a suit of artifact plate is a plot point, not a
    stat line. `artifact_rating` is the discriminator the catalogue already
    carries, so this needs no new data."""
    return sorted((a for a in ruleset.body_armor() if not a.artifact_rating),
                  key=lambda a: a.name)


def armor_of(ruleset: RuleSet, adversary: Adversary) -> Optional[ArmorType]:
    """The worn armour, or None. Unresolvable ids degrade to None rather than
    raising, the same way the rest of the app treats a stale reference."""
    return ruleset.armor_catalog.get(adversary.armor_id) if adversary.armor_id else None


def shield_options(ruleset: RuleSet) -> list[ArmorType]:
    """The shields a roster entry may carry.

    Shields are ArmorType rows tagged "shield" — they are worn equipment with a
    mobility penalty and no soak, so they need no model of their own, and a
    character's armour list can hold one without any new machinery. All three
    p.335 shields are mundane, so unlike body armour there is nothing to filter."""
    return sorted(ruleset.shields(), key=lambda s: s.name)


def shield_of(ruleset: RuleSet, adversary: Adversary) -> Optional[ArmorType]:
    """The carried shield, or None. Degrades on a stale id like armor_of."""
    return ruleset.armor_catalog.get(adversary.shield_id) if adversary.shield_id else None


def attack_difficulty(ruleset: RuleSet, adversary: Adversary) -> tuple[int, int]:
    """The (melee, ranged) difficulty bonuses the carried shield gives the bearer.

    Display only. Nothing in this build resolves an attack — decision 0008 — so
    these are printed on the card for the Storyteller to apply, exactly as the
    book's own statblocks print "+1 difficulty to attack"."""
    shield = shield_of(ruleset, adversary)
    return (shield.difficulty_melee, shield.difficulty_ranged) if shield else (0, 0)


def soak(ruleset: RuleSet, adversary: Adversary) -> tuple[int, int]:
    """Total (lethal, bashing) soak: the entry's natural soak plus any armour.

    Natural soak is what the printed block gives with no armour named — a beast's
    hide, "Skin" on a mortal, a Deathlord's chill flesh. Armour adds on top,
    which is how the book prints it: Elite Troops' "6L/12B (Lamellar armor and
    target shield, 6L/8B…)" is natural 0L/4B plus the armour's 6L/8B."""
    worn = armor_of(ruleset, adversary)
    if worn is None:
        return adversary.soak_lethal, adversary.soak_bashing
    return (adversary.soak_lethal + worn.soak_lethal,
            adversary.soak_bashing + worn.soak_bashing)


def dodge_after_armor(ruleset: RuleSet, adversary: Adversary) -> Optional[int]:
    """The dodge pool actually rolled, after the mobility penalty of the worn
    armour AND the carried shield.

    The book prints both numbers — "Dodge Pool: 4/3" for militia in a buff jacket
    (p.278) — and the human confirmed the second is simply the first minus the
    mobility penalty. Only the base is stored and this derives the rest.

    ⚠ The SHIELD is why this takes two slots, and omitting it puts the pool one too
    high. p.335: a target shield "adds 1 to the mobility penalty of her armor or
    suffers a 1 point mobility penalty, if she is using no other armor" — the same
    figure either way, so it simply sums. Infantry 3-(2+1)=0 and elite troops
    5-(2+1)=2, exactly as printed.

    None (not 0) when the entry does not dodge at all — a bear, or Nagezzer's
    printed "Does not dodge". Never returns a negative pool."""
    if adversary.dodge is None:
        return None
    worn = armor_of(ruleset, adversary)
    shield = shield_of(ruleset, adversary)
    penalty = (abs(worn.mobility_penalty) if worn else 0) + \
              (abs(shield.mobility_penalty) if shield else 0)
    return max(0, adversary.dodge - penalty)


def instantiate(template: Adversary, new_id: str, *, name: str = "") -> Adversary:
    """Copy a catalogue template into an independent roster entry.

    This is the whole interaction the feature exists for (the human's words: "so
    GMs can set up enemy NPCs without going through the full chargen") and it is
    also what instancing needs: five bandits are five calls to this, each with
    its own health track to tick off. The copy is deep and the catalogue row is
    never written back to, so damaging bandit #3 cannot touch bandit #4 or the
    template they both came from.
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
# The four things a GM does to the list itself. They live here rather than in
# either shell because BOTH shells do them — the webapp roster (`ui/adversaries.py`)
# and the native Party window (`qt/adversaries.py`) — and a duplicate that inserts
# in the wrong place or a reset that forgets a field is the kind of divergence
# nothing catches. Each returns what the caller has to select or report.
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
    """Instancing: five bandits, five health tracks. The copy is numbered and sits
    NEXT TO its original rather than at the end — a squad should read as a squad."""
    source = party.adversaries[index]
    copy = instantiate(source, next_id(party),
                       name=_copy_name(party.adversaries, source.name))
    party.adversaries.insert(index + 1, copy)
    return copy


def remove(party: Party, index: int) -> str:
    """Drop entry `index`; returns the name that went, for the caller's message."""
    gone = party.adversaries[index].name or "adversary"
    del party.adversaries[index]
    return gone


def reset_tracking(adversary: Adversary) -> None:
    """Clear damage and both spent pools — "the scene ended", not a healing rule.

    ⚠ Every tracked field, and nothing else. `damage`, `willpower_spent` and
    `motes_spent` are the three, and they are the same three `instantiate` clears;
    a reset that misses one leaves a "fresh" adversary carrying spent motes.
    """
    adversary.damage = []
    adversary.willpower_spent = 0
    adversary.motes_spent = 0


def mote_cap(adversary: Adversary) -> int:
    """The one mote track's maximum, whichever pool shape the entry uses. A spirit's
    single pool and an Exalt's Personal+Peripheral both spend downward, so the
    tracker is one counter rather than two (0 = the entry has no motes at all)."""
    return adversary.essence_pool or (adversary.personal_essence
                                      + adversary.peripheral_essence)


def set_motes_spent(adversary: Adversary, value) -> None:
    """Write the mote counter, clamped to the entry's own pool."""
    adversary.motes_spent = max(0, min(mote_cap(adversary), int(value or 0)))


def set_count(adversary: Adversary, field: str, clicked: int, cap: int) -> None:
    """A click on box `clicked` of a spent-count track: fill to here, or empty back
    to here when this box is already the last full one. Mirrors engine.play.set_count,
    which drives the character trackers — one behaviour to learn, not two."""
    cur = getattr(adversary, field)
    setattr(adversary, field, max(0, min(cap, clicked if clicked + 1 == cur
                                         else clicked + 1)))


# --------------------------------------------------------------------------- #
# Ids, duplicate naming, and the free-text trait/attack codec
#
# Moved verbatim out of `ui/adversaries.py` 2026-08-10: none of it touched the
# toolkit, and parsing the book's printed notation is the same job `expand_health`
# above already does here.
#
# ⚠ `parse_traits`/`trait_line` and `parse_attacks`/`attack_line` are CODEC PAIRS,
# not a parser plus a display helper. The GM edits these fields as text: the `*_line`
# function fills the input, the `parse_*` function reads it back, and
# `tests/test_adversaries_ui.py` asserts the round trip (`trait_line(parse_traits(s))
# == s`). Change one side and you must change the other — which is why they live
# together rather than the formatters going to `view.py` with the other presenters.
# --------------------------------------------------------------------------- #

def next_id(party: Party) -> str:
    """A roster-unique id. Ids are internal — the GM never sees or types one —
    so a counter is enough, but it must not collide after deletions."""
    used = {a.id for a in party.adversaries}
    n = len(party.adversaries) + 1
    while f"adv.{n}" in used:
        n += 1
    return f"adv.{n}"


def _copy_name(existing: list[Adversary], base: str) -> str:
    """"Bandit" -> "Bandit 2" -> "Bandit 3". Numbering the duplicates is the
    difference between a usable roster and five identically-named rows."""
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
    """Read that line back. Blanks dropped, duplicates dropped, ORDER KEPT — the GM
    typed them in the order they want them shown, and `dict.fromkeys` is the one-liner
    that dedupes without sorting.

    ⚠ A CODEC PAIR with `category_line`, like the trait and attack pairs below: the
    formatter fills the input, this reads it back, and the round trip is asserted.
    """
    return list(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))


def category_label(adversary: Adversary) -> str:
    """The filing labels as one cell/line of display: "Undead · Soldier"."""
    return "  ·  ".join(adversary.categories)


def catalogue_groups(templates) -> dict[str, list[str]]:
    """`{template id: its categories}` for a picker's group chips. ⚠ Every category,
    not the first: an entry filed under two headings must be findable under both, which
    is the whole point of the list."""
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

    Tolerant by design: an unrated entry keeps rating 0 rather than vanishing,
    and a stray comma yields nothing instead of raising."""
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
# The roster's picker browses the same Charm/spell catalogue the builder does, but
# what it writes is the printed NAME, never the id. `charms`, `spells` and `powers`
# are prose by decision (see the models docstring): the book prints "All Solar Charms
# the Storyteller cares to give him", ids would face the loader's link-checking, and
# an adversary has no prerequisite graph to resolve them against anyway. These two
# helpers are the ONE place a pick reaches the model, which is what keeps that true.
# --------------------------------------------------------------------------- #


def _already_lists(text: str, name: str) -> bool:
    """Is `name` already one of the entries in `text`?

    Splits on the separators `append_prose` writes — commas and sentence ends — so
    that a substring does not count: picking "Strike" when "Excellent Strike" is
    present must still add it."""
    wanted = name.strip().casefold()
    return any(part.strip().casefold() == wanted
               for part in re.split(r"[,.!?]", text or ""))


def append_prose(existing: str, name: str) -> str:
    """Add one picked entry's NAME to a prose field, and return the new text.

    Empty field -> the name alone. A field that ends in sentence punctuation gets
    the name after a space, because the book's own wording is a sentence and
    ``"...give him., Excellent Strike"`` is not English. Anything else is treated
    as the comma list it looks like.

    Idempotent and case-insensitive: the picker stays open across picks, so the
    same row being clicked twice must be one Charm, not two."""
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
    """Add one picked Ability/Background to a trait line, and return the new line.

    Goes out through `trait_line` rather than string-appending, so the codec's
    round trip still holds for whatever was already typed there.

    ⚠ Defaults to rating 1, NOT the 0 `parse_traits` gives an unrated entry: a card
    reading "Awareness 0" claims the book printed a zero, which is the same lie
    `Adversary.attributes` omits absent Attributes to avoid. A trait already on the
    line is left exactly as it is — picking it again must not reset a rating the GM
    has already set."""
    name = (name or "").strip()
    traits = parse_traits(line)
    if not name or any(t.name.strip().casefold() == name.casefold() for t in traits):
        return line
    return trait_line(traits + [AdversaryTrait(name=name, rating=rating)])


def parse_attacks(text: str) -> list[AdversaryAttack]:
    """One attack per line, in the book's own wording:

        Bite: Speed 6 Accuracy 7 Damage 1L Defense 5
        Venom: Speed 18 Accuracy 8 Damage 24L  (once per 10 turns)

    Keywords are matched case-insensitively and any may be missing — a beast has
    no Defense, and a Clinch has no damage rating at all."""
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
