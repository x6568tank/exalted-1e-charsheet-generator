"""Seed and run a hosted server for a click-through of the campaign table.

Input:  a folder for the throwaway database and session files
Output: three accounts, one campaign, and the hosted server on a local port

    python tools/seed_table_clickthrough.py --seed      # make /tmp/exalted-click
    python tools/seed_table_clickthrough.py             # run it on :8080
    python tools/seed_table_clickthrough.py --root DIR --port N

The accounts are `storyteller`, `alice` and `bob`. The password of each is
`clickthrough`. The campaign is "Click Through":

  * alice brings Ashes (Dex 4, Wits 3, a Knife and a Daiklave).
  * bob brings Gearheart (Dex 3, Wits 4).
  * The Storyteller brings Bandit Lord (enemy NPC) and Old Friend (ally NPC).
  * The roster has Bandit (enemy, Base 6), Guard (ally, Base 4) and Beast (enemy,
    no Base initiative).

⚠ `--seed` refuses a folder that exists. Delete it to seed again.

⚠ The cookie is a plain cookie, not `__Host-`. Firefox does not keep a `__Host-`
cookie over plain HTTP. Use a separate browser or a private window for each
account, because each account needs its own cookie.

⚠ The server has `reload=False`. Stop it and start it again after a code change.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

DEFAULT_ROOT = Path("/tmp/exalted-click")
PASSWORD = "clickthrough"


def _environ(root: Path) -> None:
    """Point the server settings at `root`. Call before the server modules load."""
    os.environ["EXALTED_STORAGE_SECRET"] = "click-through-only"
    os.environ["EXALTED_SESSION_ROOT"] = str(root / "sessions")
    os.environ["EXALTED_DB_PATH"] = str(root / "exalted.db")


def _locked(name: str, dex: int, wits: int, weapons=()):
    """Return a locked Solar with `name`, Dexterity `dex`, Wits `wits` and `weapons`."""
    from exalted_builder.engine import lifecycle
    from exalted_builder.models.character import Character
    from exalted_builder.models.rules import AttributeName

    character = Character(id="x", name=name, caste="dawn")
    character.attributes[AttributeName.DEXTERITY] = dex
    character.attributes[AttributeName.WITS] = wits
    character.weapons = list(weapons)
    lifecycle.lock_chargen(character)
    return character


def seed(root: Path) -> str:
    """Make the accounts, the campaign, the characters and the roster in `root`.
    Return the campaign id."""
    from exalted_builder.models.adversary import ALLY, ENEMY, Adversary
    from exalted_builder.models.character import Weapon
    from exalted_builder.server import db
    from exalted_builder.server.characters import CharacterStore
    from exalted_builder.server.table_roster import TableRoster
    from exalted_builder.server.tables import TableStore

    database = root / "exalted.db"
    (root / "sessions").mkdir(parents=True)
    db.init_db(database)
    ids = {name: db.create_user(database, name, PASSWORD)
           for name in ("storyteller", "alice", "bob")}
    tables = TableStore(db_path=database, root=root / "sessions")
    store = CharacterStore(db_path=database, root=root / "sessions")
    st = ids["storyteller"]
    table = tables.create(st, "Click Through")

    ashes = _locked("Ashes", 4, 3, [Weapon(name="Knife", speed=1),
                                    Weapon(name="Daiklave", speed=3)])
    for user, character in ((ids["alice"], ashes),
                            (ids["bob"], _locked("Gearheart", 3, 4))):
        base = store.create(user, character)
        tables.approve(st, tables.request(user, table.join_code, base.id).id)
    for name, dex, wits, side in (("Bandit Lord", 5, 5, ENEMY), ("Old Friend", 2, 3, ALLY)):
        tables.bring(st, table.id, store.create(st, _locked(name, dex, wits)).id, side=side)

    roster = TableRoster(tables)
    party = roster.party(st, table.id)
    for name, side, base in (("Bandit", ENEMY, 6), ("Guard", ALLY, 4), ("Beast", ENEMY, None)):
        party.adversaries.append(Adversary(id=f"adv.{name.lower()}", name=name, side=side,
                                           base_initiative=base))
    roster.save(st, table.id)
    return table.id


def run(port: int) -> None:
    """Run the hosted server on `port`, with a plain session cookie."""
    from exalted_builder.server import main as server

    server.SESSION_COOKIE = {"session_cookie": "exalted-click", "https_only": False,
                             "path": "/", "same_site": "lax"}
    sys.argv = [sys.argv[0], "--port", str(port)]
    server.main()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--seed", action="store_true", help="make the data, then stop")
    args = parser.parse_args()
    _environ(args.root)
    if args.seed:
        if args.root.exists():
            print(f"{args.root} exists. Delete it to seed again.", file=sys.stderr)
            return 1
        print(f"Seeded campaign {seed(args.root)} in {args.root}.")
        return 0
    if not (args.root / "exalted.db").exists():
        print(f"There is no database in {args.root}. Run with --seed first.", file=sys.stderr)
        return 1
    run(args.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
