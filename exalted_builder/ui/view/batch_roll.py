"""
ui/view/batch_roll.py — the batch roll of the Storyteller (decision 0019). The
Storyteller types each count. Nothing reads a pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from .roller import ROLL_LOG_LENGTH, RollEntry, roll_detail, roll_dice


# --------------------------------------------------------------------------- #
# The GM's batch roll (decision 0019, the same no-wire rule)
#
# ⚠ Every count in a batch is TYPED BY THE STORYTELLER, one per row. Nothing here
# reads a character's pool, and nothing may: a batch that filled its counts from
# a named roll would have the app claiming to know what five sheets are rolling
# at once, which is the wire 0019 rejects by name ("a roller wired to the named
# rolls… the version that generates the Charm-dice ask"). A ROW'S name is the
# character's, which is not a roll's name and asserts nothing about the pool.
#
# The batch NAME is the Storyteller's free text too, for the same reason the
# single roller's label is. It is what the fold shows when collapsed.
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BatchRoll:
    """One batch: the Storyteller's name for it, and a `RollEntry` per row.

    `key` is a monotonic id so a surface can remember which batches the user
    opened. It identifies the batch in the log and nothing else — it is not
    persisted and means nothing between sessions.
    """
    key: int
    name: str
    rolls: tuple[RollEntry, ...]
    detail: str                              # "4 rolls · TN 7 · 10s double · can botch"

    @property
    def caption(self) -> str:
        """What the collapsed fold shows: the batch's name, or a neutral
        stand-in when the Storyteller did not name it."""
        return self.name or f"{len(self.rolls)} rolls"


def new_batch_state() -> dict:
    """The GM roller's controls. Owned by the CALLER, like `new_roller_state` —
    the party page rebuilds on every roster change and a batch mid-setup (typed
    counts, a half-written name) must survive that.

    `counts` and `labels` are keyed by a caller-supplied row key rather than a
    list position, because the roster renumbers when a member is removed and a
    positional key would silently move one character's dice onto another's row.
    """
    from ...engine import dice as dicemod
    return {"name": "",
            "counts": {}, "labels": {}, "included": set(), "times": {},
            "target_number": dicemod.DEFAULT_TARGET_NUMBER,
            "doubles_tens": True, "can_botch": True,
            "log": [], "open": set(), "next_key": 1}


def batch_roster(party) -> list[tuple[str, str]]:
    """The party page's rows as (key, display name): every member, then every
    adversary. ONE builder so the two shells cannot disagree about who is in a
    batch.

    ⚠ Keyed by the record's own id, never by position — the roster renumbers when
    a member is removed, and a positional key moves one character's typed dice
    onto another's row. Adversaries are in because a batch rolls a NUMBER: an
    `Adversary` is not a `Character` and never may be, but a dice count does not
    care which it came from.

    ⚠ A DUPLICATE id gets a `#n` suffix so the keys stay unique. Every app path
    that made a blank character once handed it the literal `"char.new"`, so two
    of them in one party shared a key and the second row's dice silently
    overwrote the first's — both rows then rolled the same count (human, found at
    the browser 2026-09-09). `new_character_id` fixes new characters; parties
    already SAVED with the duplicate cannot be migrated (there are no save
    migrations here), so the key derivation has to be total on its own. The
    suffix is positional and therefore carries the renumbering trap above — but
    only among records that were already indistinguishable, where there is
    nothing better to key on.
    """
    rows: list[tuple[str, str]] = []
    seen: dict[str, int] = {}
    for prefix, record, name in (
            [("m", m.character, m.character.name) for m in party.members]
            + [("a", a, a.name) for a in party.adversaries]):
        key = f"{prefix}:{record.id}"
        seen[key] = seen.get(key, 0) + 1
        if seen[key] > 1:
            key = f"{key}#{seen[key]}"
        rows.append((key, name or "(unnamed)"))
    return rows


# How many times one row may be rolled in a single batch. A guard on the input
# field, not a rule — nothing printed caps it. Low enough that a fat-fingered
# entry cannot render a thousand transcript lines.
MAX_BATCH_REPEATS = 20


@dataclass(frozen=True)
class BatchRow:
    """One roster row as the batch controls show it: who, how many dice, how
    many times, the Storyteller's label, and whether the row is in the batch.

    ⚠ `count` and `times` are both TYPED. Neither is read from a pool, and the
    row carries the CHARACTER's name, never a roll's — see the module note above.
    """
    key: str
    name: str
    count: int
    label: str
    included: bool
    times: int

    @property
    def rolls(self) -> int:
        """How many transcript lines this row will produce: `times` when it is
        actually taking part, 0 otherwise. One place answers it, so the controls
        and `roll_batch` cannot disagree about whether a row sits out."""
        return self.times if (self.included and self.count > 0) else 0


def set_batch_count(state: dict, key: str, count) -> None:
    """Store a row's typed dice count, and tick the row INTO the batch when the
    count goes above 0.

    ⚠ The auto-tick is the whole reason this is a function rather than a dict
    write in each shell. Without it a Storyteller types dice into an unticked row,
    presses Roll and nothing happens — a silent no-op with the number sitting
    right there. Unticking afterwards still parks the row without clearing what
    was typed, which is the point of keeping the two fields apart.
    """
    value = max(0, int(count or 0))
    state["counts"][key] = value
    if value > 0:
        state["included"].add(key)


def set_batch_included(state: dict, key: str, included: bool) -> None:
    """Tick a row into the batch or out of it, leaving its typed dice alone."""
    if included:
        state["included"].add(key)
    else:
        state["included"].discard(key)


def set_batch_times(state: dict, key: str, times) -> None:
    """Store how many times this row rolls, clamped to 1..`MAX_BATCH_REPEATS`.

    ⚠ Floors at 1, never 0: "not this one" is the include tick, and having two
    different controls that both mean "sit out" is how one of them ends up
    silently overriding the other.
    """
    state["times"][key] = max(1, min(MAX_BATCH_REPEATS, int(times or 1)))


def batch_rows(state: dict, rows: Sequence[tuple[str, str]]) -> list[BatchRow]:
    """In: the state and the roster as (key, display name) pairs. Out: one
    `BatchRow` per row, carrying whatever the Storyteller has typed so far —
    0 dice, one roll and unticked for a row they have not touched.

    A row sits out of the batch by being unticked OR by having 0 dice; `BatchRow.rolls`
    is the single answer to which — see `roll_batch`.
    """
    return [BatchRow(key=key, name=name,
                     count=int(state["counts"].get(key) or 0),
                     label=state["labels"].get(key, ""),
                     included=key in state.get("included", ()),
                     times=max(1, int(state.get("times", {}).get(key) or 1)))
            for key, name in rows]


def roll_batch(state: dict, rows: Sequence[tuple[str, str]], *,
               rng=None) -> Optional[BatchRoll]:
    """In: the state and the roster as (key, display name) pairs. Out: a
    `BatchRoll` of every row with at least one die, also prepended to
    `state["log"]`; None when no row has any dice.

    Each row's `RollEntry.label` is the Storyteller's typed label, falling back
    to the row's display NAME so a line is never anonymous. ⚠ That fallback is a
    character's name, never a roll's — see the module note above.

    A row rolls `times` times, each line suffixed "(2 of 3)" so the repeats can be
    told apart. ⚠ That suffix is an ORDINAL, not a roll's name: it says which of
    the Storyteller's own repeats this is and asserts nothing about the pool.

    Rows sit out by being unticked or by having 0 dice — `BatchRow.rolls` decides,
    so the controls and this function cannot disagree. In a party of six the usual
    case is three of them rolling.
    """
    from ...engine import dice as dicemod
    entries: list[RollEntry] = []
    target = int(state.get("target_number") or dicemod.DEFAULT_TARGET_NUMBER)
    doubles = bool(state.get("doubles_tens", True))
    botching = bool(state.get("can_botch", True))
    for row in batch_rows(state, rows):
        base = row.label or row.name
        for n in range(1, row.rolls + 1):
            row_state = {"count": row.count,
                         "label": base if row.rolls == 1 else f"{base} ({n} of {row.rolls})",
                         "target_number": target, "doubles_tens": doubles,
                         "can_botch": botching, "log": []}
            entries.append(roll_dice(row_state, rng=rng))
    if not entries:
        return None

    batch = BatchRoll(
        key=state["next_key"], name=(state.get("name") or "").strip(),
        rolls=tuple(entries),
        detail=(f"{len(entries)} {'roll' if len(entries) == 1 else 'rolls'} · "
                + roll_detail(0, target, doubles, botching).split(" · ", 1)[1]))
    state["next_key"] += 1
    log = state.setdefault("log", [])
    log.insert(0, batch)
    del log[ROLL_LOG_LENGTH:]
    # Newest open, so the roll just made is readable without a click; older ones
    # stay as the Storyteller left them.
    state["open"] = {batch.key} | {b.key for b in log if b.key in state["open"]}
    return batch
