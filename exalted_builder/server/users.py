"""
server/users.py — the operator command for the accounts of the hosted server.

    python -m exalted_builder.server.users list
    python -m exalted_builder.server.users reset <username>
    python -m exalted_builder.server.users delete <username>

`reset` asks for the new password two times and does not echo it. The database is
`EXALTED_DB_PATH`, the same file as the server uses.

A player with a forgotten password writes to the address that the login page
gives (`EXALTED_ADMIN_CONTACT`). The operator runs `reset` and sends the new password
to the email of the account. `reset` shows that email first.

⚠ Send the password to the stored email, not to the sender of the request. A sender
address can be forged. See docs/plans/account-management.md.

A reset ends each login of the account.

`delete` asks for the username again. It deletes the campaigns that the account
runs; each other player keeps a solo copy. See `server/accounts.py`.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import getpass
import sys

from . import accounts, config, db
from .characters import CharacterStore
from .tables import TableStore


def main(argv: Sequence[str] | None = None,
         ask: Callable[[str], str] = getpass.getpass,
         confirm: Callable[[str], str] = input) -> int:
    """Run the command in `argv`. Return the exit status.

    `ask` reads a password with no echo. `confirm` reads the typed name of a
    delete, with echo. A test supplies its own of each.
    """
    parser = argparse.ArgumentParser(prog="python -m exalted_builder.server.users",
                                     description="Manage the hosted server's accounts.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list the accounts")
    reset = commands.add_parser("reset", help="set a new password for an account")
    reset.add_argument("username")
    delete = commands.add_parser("delete", help="delete an account and all it owns")
    delete.add_argument("username")
    args = parser.parse_args(argv)

    path = config.db_path()
    if not path.exists():
        print(f"There is no database at {path}.", file=sys.stderr)
        return 1

    if args.command == "list":
        for user_id, username, created, email in db.list_users(path):
            print(f"{user_id}\t{username}\t{created}\t{email or '(no email)'}")
        return 0

    user_id = db.user_id_for(path, args.username)
    if user_id is None:
        print(f"There is no account named {args.username!r}. Nothing changed.",
              file=sys.stderr)
        return 1
    if args.command == "delete":
        return _delete(path, user_id, args.username, confirm)

    email = db.email_for(path, user_id)
    if email:
        print(f"Send the new password to {email}, not to the sender of the request.")
    else:
        print(f"⚠ {args.username} has no email. You cannot confirm who owns it.")

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


def _delete(path, user_id: int, username: str, confirm: Callable[[str], str]) -> int:
    """Delete account `user_id` after the operator types `username` again."""
    root = config.session_root()
    tables = TableStore(db_path=path, root=root)
    campaigns = accounts.campaigns_run(tables, user_id)
    print(f"This deletes {username}, each of its characters and its homebrew.")
    for name, members in campaigns:
        print(f"  It also deletes the campaign {name!r} ({members} members keep "
              f"solo copies).")
    if confirm(f"Type {username} to delete it: ").strip() != username:
        print("The name is different. Nothing changed.", file=sys.stderr)
        return 1
    accounts.delete_account(user_id, characters=CharacterStore(db_path=path, root=root),
                            tables=tables)
    print(f"{username} is deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
