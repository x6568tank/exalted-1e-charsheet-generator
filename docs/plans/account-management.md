# Account management — email, password change, logout elsewhere, delete

Asked for by the human 2026-09-26: *"we should add more account management in general;
a linked email would be useful for password resets so I know someone emailing me
actually owns the account"*.

## Rulings (2026-09-26)

⚠ **This reopens a 2026-09-11 ruling.** `hosting-state-model.md` §5.1d recorded
*"Forgotten passwords: Manual … No reset by email, no email column."* The human reopened
the email half. The reset stays manual.

| Question | Ruling |
|---|---|
| Who sends a reset password | **The operator, by hand.** `users reset` shows the stored email and sets a temporary password; the operator sends it TO THE STORED ADDRESS, whoever wrote in. A forged sender never sees it. The server sends no mail. |
| Email at signup | **Optional, with a nudge.** Signup asks; `/account` says an account with no email cannot prove it is yours. Existing accounts have none. |
| Confirm the email address | **No.** Follows from the manual reset: a typo hurts only the person who typed it. |
| `/account` holds | **Change password, add/change email, log out other devices, delete account.** |
| A deleted account that is Storyteller of campaigns | **Its campaigns are deleted too**, by the ordinary campaign delete: each other player's copy becomes a solo copy (`p3-tables.md` §10). The confirm names each campaign and its member count. |
| Delete confirmation | **Password only.** |
| The username after a delete | **Freed.** Anyone can sign up with it. |
| An account cap / signup limit | **Not now.** Watch `users list` and the disk instead. |

## Design

### Two new tables, no migration

The live server has accounts. `init_db` runs `CREATE TABLE IF NOT EXISTS`, so a NEW
table reaches the existing database at the next start. A new COLUMN on `users` would
need an `ALTER`, which is a migration (CLAUDE.md §10). Thus:

* `user_emails(user_id PRIMARY KEY → users ON DELETE CASCADE, email)`
* `login_epochs(user_id PRIMARY KEY → users ON DELETE CASCADE, epoch INTEGER)` —
  absent row = epoch 0.

### Ending logins

A login stores the account's epoch in `app.storage.user`. `current_user_id()` answers
None when the stored epoch differs from the database's. A password change, a reset
(`users reset`, in another process — hence the DB, not memory) and "Log out other
devices" raise the epoch. The browser that made the change stores the new epoch and
stays logged in. Closes the §5.1d limit *"A password reset does not end the logins
that exist."*

### ⚠ The delete keeps a tombstone row — ids must never be reused

`users.id` is `INTEGER PRIMARY KEY` without `AUTOINCREMENT`: SQLite gives a new row
`max(id) + 1`, so deleting the NEWEST account hands its id to the next signup. The
campaign log stores the account id (`table_log.py`), notes files are named by id,
and folders are `user-<id>`. A reused id inherits all of them.

So a delete **keeps the `users` row**: the username becomes a placeholder the username
pattern can never match (thus it can never log in, and the real name is free), the hash
becomes a value bcrypt never verifies, and the epoch is raised. Everything the account
owns is removed:

1. each campaign it runs → `TableStore.delete` (players keep solo copies);
2. each membership → `TableStore.leave` (clears nothing of anyone else);
3. its notes file in each campaign it was in;
4. its pending join requests and campaign drafts;
5. its characters (rows and files) and its folder `<root>/user-<id>/` (library too);
6. its email row; its live sessions in the registry.

A log line of a deleted account shows "a deleted account".

## Build order

1. `db.py`: the two tables; email get/set; password change (checks the current one);
   epoch get/raise; tombstone. Tests first.
2. The epoch in `log_in` / `current_user_id`; the gate follows for free.
3. `users` CLI: `list` shows the email; `reset` shows it and raises the epoch; `delete`.
4. The delete orchestration (a function the page and the CLI share).
5. `/account` page and its menu entry; the optional email on `/signup`.
6. The log's "a deleted account".

## Build log — 2026-09-26: all six steps built, tests green, ✅ browser-verified the same day

* `server/db.py` — `user_emails` and `login_epochs` tables; `check_email`, `email_for`,
  `set_email`, `password_matches`, `change_password`, `login_epoch`,
  `raise_login_epoch`, `tombstone_user`, `user_id_for`; `create_user(email=)`;
  `set_password` raises the epoch; `list_users` returns the email and hides tombstones.
  The placeholder is `deleted:<id>` — `:` is outside the username pattern. (A first
  draft used a NUL byte; SQLite's `substr` stops at it, and the listing filter failed.)
* `server/auth.py` — the epoch is stored at `log_in` and compared in `current_user_id`.
  ⚠ **The database path is on `app.state`, not a module global.** A NiceGUI main-file
  test imports the package again; the gate installed by an EARLIER case belongs to the
  old module and read a global that nothing had set, so the gate skipped the check
  while the page did not — the page then raised `PermissionError` mid-request. Found by
  the second case of `test_account_page.py`, which passed alone.
* `server/accounts.py` — `delete_account` and `campaigns_run`. Sets `ctx["path"] = None`
  on each live session before the discard (mutation-checked: the open-page case goes red
  without it).
* `server/quota.py` — `FolderQuota(db_path=)` refuses a write into the folder of a
  deleted account. The operator's `users delete` runs in another process and cannot
  reach the sessions; this stops an open page's auto-save from making the folder again.
  `test_server_main.py` asserts `main` passes the database.
* `server/users.py` — `list` shows the email; `reset` names the address BEFORE it asks;
  `delete` lists the campaigns it deletes and asks for the username (with echo).
* `server/account_page.py` — `/account`, four cards in the login pages' frame
  (`auth.form_frame(cards=4)`), linked from the menu as "Account settings". Signup has an
  optional email. Screenshotted at 1400/1000/420 px.
* A log line or member of a deleted account already showed "(a deleted account)".

**For the human's click-through:** sign up with an email; `/account`: change the email,
change the password (a second browser is logged out), Log out other devices (same),
delete an account that runs a campaign (the other player keeps a solo copy). Then
`users list`, `users reset <name>` (shows the email), `users delete <name>`.

✅ **Clicked by the human, 2026-09-26** — the short list (what the tests cannot see): the
build-line icon, the look of `/account` (1400 and phone width), a password change and
"Log out other devices" ending a second real browser's login, the delete landing on the
front page, and `users reset` in a real terminal. All six: "Works."
