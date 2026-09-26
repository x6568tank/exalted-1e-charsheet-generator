"""
server/table_initiative.py — the initiative roll of the whole table (core p.227).

Step 9 of the build order in `docs/plans/p3-tables.md` section 15.4, the gate of
P3 (section 9). Rulings, human, 2026-09-24:

  * The combatants are each player copy, each NPC and each roster entry. The
    Storyteller unticks the entries that do not fight.
  * A character's rating is `engine.initiative` with the weapon in hand
    (`PlayState.in_hand`, set by the player). A roster entry's rating is its Base
    initiative. An entry with no Base initiative cannot roll.
  * Each combatant rolls 1d10, added to the rating. The order is
    `engine.initiative.turn_order`: ties break on Dexterity + Wits, else "tied".
  * The result is one entry in the Log. Each combatant is named there, an enemy
    NPC too (human, 2026-09-25).

Rulings, human, 2026-09-25: Charms that change initiative are not modelled
(decision 0008). The Storyteller types a bonus for one roll, and ticks "first" for
a Charm that acts before everyone. Two or more "first" entries go in the normal
order between them (`engine.initiative.turn_order`).

⚠ The server rolls the d10 with `engine.dice.roll`. The browser sends the keys of
the ticked combatants only. A key that is not a combatant now does not roll.

⚠ Decision 0019: the d10 is the printed fixed count of p.227. Do not make it a
parameter, and do not add a roll of any other pool here.

⚠ Each call asks that the caller is the Storyteller. A page that shows the button
only to the Storyteller is not a check.

⚠ A character with a live context is read from that context (`peek`), because the
player sets the weapon in hand on the live object. Never `ctx_for`: this module
never builds a context for the character of another account (section 8).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import random

from ..engine import dice, initiative as initmod
from ..models.adversary import ALLY, ENEMY, Adversary
from ..models.character import Character
from ..models.rules import RuleSet
from ..ui import view as viewmod
from .characters import CharacterRow, CharacterStore
from .rulesets import Rulesets
from .session import SessionRegistry
from .table_log import InitiativeLine, LogEntry, TableLog, TableLogError
from .table_roster import TableRoster
from .tables import STORYTELLER, TableStore, TableStoreError

log = logging.getLogger(__name__)

PARTY = "party"

# The largest bonus that the dialog accepts, plus or minus. An input check, not a
# rule of the game.
MAX_BONUS = 99

# The order of the groups in the checklist.
_GROUPS = (PARTY, ALLY, ENEMY)


@dataclass(frozen=True)
class Combatant:
    """One entry that can roll. `key` is "char:<copy id>" or "adv:<roster id>".

    `name` is the name of the character or the entry. `rating` is None for a roster
    entry with no Base initiative. `weapon` is the weapon in hand, "" for unarmed
    and for a roster entry. `dex_wits` is None when the entry does not have both.
    """

    key: str
    name: str
    group: str
    rating: int | None
    weapon: str = ""
    dex_wits: int | None = None


class TableInitiative:
    """Roll initiative for the combatants of each table of `tables`."""

    def __init__(self, tables: TableStore, store: CharacterStore, rulesets: Rulesets,
                 sessions: SessionRegistry, roster: TableRoster, log: TableLog) -> None:
        self.tables = tables
        self.store = store
        self.rulesets = rulesets
        self.sessions = sessions
        self.roster = roster
        self.log = log

    def combatants(self, st_id: int, table_id: str) -> list[Combatant]:
        """Return the combatants of `table_id`: the party, then the allies, then the
        enemies. In each group, the characters come before the roster entries.

        Refuse all but the Storyteller. Leave out a character that does not read.
        """
        self._require_storyteller(st_id, table_id)
        found: list[Combatant] = []
        sides = self.tables.npc_sides(table_id)
        storyteller = self.tables.table(table_id).storyteller_id
        for row in self.tables.characters(table_id):
            group = sides.get(row.id, ENEMY) if row.owner_id == storyteller else PARTY
            combatant = self._character(table_id, row, group)
            if combatant is not None:
                found.append(combatant)
        for entry in self.roster.party(st_id, table_id).adversaries:
            found.append(_adversary(entry))
        return sorted(found, key=lambda c: (_GROUPS.index(c.group), c.key.startswith("adv:")))

    def roll(self, st_id: int, table_id: str, keys: list[str], *,
             bonus: dict[str, int] | None = None, first: set[str] | None = None,
             rng: random.Random | None = None) -> LogEntry:
        """Roll 1d10 for each combatant in `keys`, in the order of `keys`. Post the
        turn order to the Log. Return the entry.

        `bonus` maps a key to a number that is added to its total. `first` is the
        keys that go before the others. A key in them that does not roll does
        nothing.

        Refuse all but the Storyteller, and a bonus that is not a whole number from
        -`MAX_BONUS` to `MAX_BONUS`. Skip a key that is not a combatant now and a
        combatant with no rating. Refuse when nothing is left. `rng` is for the tests.
        """
        bonus = dict(bonus or {})
        first = set(first or ())
        for value in bonus.values():
            # ⚠ `bool` is an `int`. A tick sent as a bonus is refused.
            if (not isinstance(value, int) or isinstance(value, bool)
                    or abs(value) > MAX_BONUS):
                raise TableLogError(
                    f"A bonus is a whole number from -{MAX_BONUS} to {MAX_BONUS}.")
        by_key = {c.key: c for c in self.combatants(st_id, table_id)}
        rolling = [by_key[k] for k in dict.fromkeys(keys)
                   if k in by_key and by_key[k].rating is not None]
        rolls = [initmod.TurnRoll(key=c.key, rating=c.rating,
                                  d10=dice.roll(1, rng=rng).faces[0], dex_wits=c.dex_wits,
                                  bonus=bonus.get(c.key, 0), first=c.key in first)
                 for c in rolling]
        lines = []
        for placed in initmod.turn_order(rolls):
            c = by_key[placed.roll.key]
            lines.append(InitiativeLine(
                name=c.name, group=c.group, rating=placed.roll.rating,
                d10=placed.roll.d10, tied=placed.tied, bonus=placed.roll.bonus,
                first=placed.roll.first))
        return self.log.post_initiative(st_id, table_id, lines)

    # ---- helpers ------------------------------------------------------------ #

    def _character(self, table_id: str, row: CharacterRow,
                   group: str) -> Combatant | None:
        character, ruleset = self._read(table_id, row)
        if character is None:
            return None
        index = viewmod.wielded_index(character)
        rating = viewmod.build_initiative(ruleset, character, weapon_index=index)
        return Combatant(key=f"char:{row.id}", name=character.name or "(unnamed)",
                         group=group, rating=rating.total, weapon=rating.weapon,
                         dex_wits=initmod.dex_wits(character))

    def _read(self, table_id: str, row: CharacterRow) -> tuple[Character | None, RuleSet]:
        """Return the live object and RuleSet of `row` if a page holds them, else the
        file and the RuleSet of the table. ⚠ `peek`, never `ctx_for`."""
        ctx = self.sessions.peek(row.id)
        if ctx is not None:
            return ctx["char"], ctx.get("ruleset") or self.rulesets.for_table(table_id)
        try:
            return self.store.load(row), self.rulesets.for_table(table_id)
        except Exception:                           # noqa: BLE001 - leave it out
            log.warning("The character %s does not read.", row.id)
            return None, self.rulesets.for_table(table_id)

    def _require_storyteller(self, user_id: int, table_id: str) -> None:
        if self.tables.access(user_id, table_id) != STORYTELLER:
            raise TableStoreError("Only the Storyteller of this campaign can do that.")


def _adversary(entry: Adversary) -> Combatant:
    """Return the roster entry `entry` as a combatant. Its Dexterity + Wits are the
    printed Attributes, if it prints both."""
    dex, wits = entry.attributes.get("dexterity"), entry.attributes.get("wits")
    return Combatant(key=f"adv:{entry.id}", name=entry.name or "(unnamed)",
                     group=entry.side, rating=entry.base_initiative,
                     dex_wits=None if dex is None or wits is None else dex + wits)
