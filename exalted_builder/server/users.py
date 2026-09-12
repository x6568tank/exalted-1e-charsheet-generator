"""
server/users.py — the operator command for the accounts of the hosted server.

    python -m exalted_builder.server.users list
    python -m exalted_builder.server.users reset <username>

`reset` asks for the new password two times and does not echo it. The database is
`EXALTED_DB_PATH`, the same file as the server uses.

A player with a forgotten password writes to the address that the login page
gives (`EXALTED_ADMIN_CONTACT`). The operator runs `reset` and gives the player the
new password. The human chose this on 2026-09-11; there is no reset by email.

⚠ A reset does not end the logins that exist. A browser that is logged in stays
logged in. See section 5.1d of docs/plans/hosting-state-model.md.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import getpass
import sys

from . import config, db


def main(argv: Sequence[str] | None = None,
         ask: Callable[[str], str] = getpass.getpass) -> int:
    """Run the command in `argv`. Return the exit status.

    `ask` reads a password with no echo. A test supplies its own.
    """
    parser = argparse.ArgumentParser(prog="python -m exalted_builder.server.users",
                                     description="Manage the hosted server's accounts.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the accounts")
    reset = commands.add_parser("reset", help="set a new password for an account")
    reset.add_argument("username")
    args = parser.parse_args(argv)

    path = config.db_path()
    if not path.exists():
        print(f"There is no database at {path}.", file=sys.stderr)
        return 1

    if args.command == "list":
        for user_id, username, created in db.list_users(path):
            print(f"{user_id}\t{username}\t{created}")
        return 0

    password = ask(f"New password for {args.username}: ")
    if ask("Password again: ") != password:
        print("The two passwords are different. Nothing changed.", file=sys.stderr)
        return 1
    try:
        db.set_password(path, args.username, password)
    except db.AccountError as exc:
        print(f"{exc} Nothing changed.", file=sys.stderr)
        return 1
    print(f"The password of {args.username} is changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
