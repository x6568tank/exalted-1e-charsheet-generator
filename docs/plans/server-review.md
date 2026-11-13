# Review of `server/` — 2026-11-09

A read of all of `exalted_builder/server/` plus the hosted branches of `ui/builder.py`.
No code changed. The suite was not run (last green: 4425 + 1 skipped, 2026-10-09).

> ⚠ **This repo is PUBLIC and findings 1–3 are live on the site.** Do not push this file
> until the fixes for 1–3 are pushed AND deployed. Commit it with them or after them.

**Status 2026-11-13: 1–6, 8 and 9 FIXED and committed (`286bf82` for 1–3, the next
commit for the rest), NOT pushed, NOT deployed.** Suite 4476 passed + 1 skipped. Only 7
(NiceGUI's per-request `_users` entries) is open.

Numbers ruled by the human 2026-11-13 (from Claude's proposal):

* **4:** server-side size checks at the existing browser limits (12 MB board, 2 MB
  character import; the homebrew import had NO limit and now has 2 MB). Token images
  16 MP (`MAX_TOKEN_INPUT_PIXELS`); backgrounds keep 40 MP. One decode at a time
  (`table_board._IMAGE_LOCK`), run with `asyncio.to_thread` from `BoardSession`, whose
  `add_token_image`/`set_background` are now async. NiceGUI spools uploads over 1 MB to
  disk, so memory was safe until the handler's `read()` but disk was unbounded:
  `server/upload_guard.py` refuses an upload POST over 13 MB (413 on the declared
  length; counts the body too, since the length can lie). `auth.install_gate()`
  installs it, so `main`, both test main files and the `main()` wiring test all get it
  from one call. Handlers call `ui/upload_limit.too_large` before any read.
* **5:** ONE `LoginThrottle` in `build_server`, given to the login page and
  `/account`, keyed on the username: 5 free attempts in total across both pages. Each
  account action checks the password through it first (`_password_ok`), and a refusal
  clears the field, as the login page does.
* **6:** `MAX_CAMPAIGNS_RUN = 5` per Storyteller; joins are not capped. The count and
  the insert are one SQL statement, so parallel creates cannot pass it.
* **8:** the new-text branch is an `else` of `elif kind == "token"`; tests cover edit
  and create for both kinds (there was no UI test of the dialog before).
* **9:** absorb after `make_copy`. A copy's save keeps carried rows, and the campaign
  row still wins a clash, so the result of a successful approval is unchanged.

Negative controls run: the throttle (begin → 0), the size check (always None), the
guard install (removed). Each failed the new tests.

* **1:** `has_custom = home_path is None` in `build_app`. The hosted page does not build
  the Custom tab, and `visible_tabs`/`resolve_tab` take `custom=False`, so a forged
  "Custom" lands on Edit. The old test asserted `not visible` and passed against the
  defect; the new ones fire the tab bar's event (`_fire_tab` in
  `test_character_pages.py`). 🐞 The handler runs AFTER `_handle_event` returns: the
  first draft of the test checked at once and passed against the defect. It now waits
  for the bar to go back to Edit or the panel to draw. Sweep: no other hosted gate is a
  `set_visibility`; the table view builds its ST controls under `if self.is_st`.
* **2:** fixed at READ time, not with a store listener. The context records
  `"binding": (row.table_id, draft tag)`; `character_page` compares it with the fresh
  row and `ctx.update(bindings(row))` in place (no discard, so the open page and the
  registry keep one Character and the file keeps being saved). A listener would only
  fire on the server's own `TableStore` instance; the DB is the truth. Residue: a page
  that is ALREADY open keeps its build-time `ruleset` until reload (Custom is gone, so
  it can only read the campaign's homebrew); the 200-cap double-object case is not
  touched.
* **3:** one predicate, `site.is_local_path`, for `safe_target` and `_local`: refuses
  `\`, any whitespace and any non-printable character. A path with a decoded space now
  lands on `/home` after login; no route has one.

**Order of work:** 1, 2, 3 first (small, and 1 is exploitable now). Tests first for each.
Then 4–6, which each need a ruling on a number. 7–9 are optional.

## How each was established

"Confirmed" means a throwaway test or script ran and showed it. "By reading" means the
code says so and nothing was run. The throwaway probes were deleted; the recipes are below.

## 1. HIGH — a player can edit the campaign's homebrew without the Storyteller

* `ui/builder.py` `_sync_tabs` (~line 758) hides the Custom tab on a hosted character
  page with `set_visibility(False)`. The tab still exists, and `visible_tabs` still lists
  "Custom", so `resolve_tab` accepts it.
* The browser can fire the tab bar's value event with `"Custom"` (devtools: un-hide the
  tab and click it). `content()` (~line 344) then calls
  `custom_mod.build_custom(ruleset, custom_dir=ctx["custom_dir"], with_header=False)`.
* For a campaign copy, `ctx["custom_dir"]` is `<table folder>/custom` and `ruleset` is the
  table's shared RuleSet. `show_path` defaults to True, so the server path is printed.
* **Confirmed.** As a player on `/character/<copy>`: the label
  `Library: /tmp/…/table-<hex>/custom` appeared, and saving a Charm named "Probe Strike"
  put it in the campaign's library. On a solo character the same trick only leaks the
  path of the player's own folder.
* `tests/test_character_pages.py::test_the_character_page_has_no_custom_tab` asserts
  `not tabs[0].visible`. It passes against the defect.

**Fix shape:** do not build the branch. When `home_path is not None`, "Custom" must not
be a tab that `content()` can draw (leave it out of the tab set, or refuse it in
`resolve_tab` via a flag). Follow `unlock_button = None if in_campaign`, which is the
correct pattern already in that file.

**Test recipe** (the click that matters; visibility assertions are worthless here):

```python
(tabs,) = [e for e in player.client.elements.values() if isinstance(e, ui.tabs)
           and any(type(c).__name__ == "Tab" and c.props.get("name") == "Custom"
                   for c in e.descendants())]
for listener_id, listener in tabs._event_listeners.items():
    if listener.type.replace("-", "").lower() == "update:modelvalue":
        with player.client:
            tabs._handle_event({"id": tabs.id, "listener_id": listener_id,
                                "args": "Custom"})
# then: "Custom content" must NOT be drawn, and no label may contain str(state.ROOT)
```

Set-up helpers: `_campaign`, `_tables`, `_characters` in `tests/test_table_view.py`;
main file `tests/_auth_main.py`. ⚠ Settle with a `should_see` before any absence check.

**Also sweep for the same shape:** any other hosted or in-campaign restriction done with
`set_visibility` / a hidden class instead of not building the control. One was checked:
the hidden Finish & Lock on a locked copy can be fired; `lock_chargen` re-snapshots, which
moves the baseline but gives no XP (tested in the engine). Not a finding, but the same gap.

## 2. MEDIUM — a character context outlives its membership

* `home.register_character_pages.factory` builds the context once per character id:
  `row`, `custom_dir`, `library_dir`, `ruleset`. Nothing discards it on
  `TableStore.leave`, `remove`, `delete`, or when a draft's tag goes. Only
  `home._delete` and `accounts.delete_account` call `sessions.discard`.
* **Confirmed.** After `tables.remove(st, table, player)`, the DB row has
  `table_id None`, but `REGISTRY.ctx_for(copy.id)` still has `custom_dir ==` the campaign
  folder, `library_dir None`, and `ctx["row"].table_id` set.
* Consequences: finding 1 keeps working for a removed player; the copy keeps reading the
  campaign's homebrew and RuleSet; the now-solo copy has no library in its Gear tab; after
  a campaign delete the context points at a folder that is gone.
* **By reading:** `SessionRegistry.sweep()` is never called on the server and `on_evict`
  is not set, so a context leaves only at the 200 cap (LRU by `ctx_for`, not by edits).
  At the cap, an open page keeps its object while the registry builds a second one: an ST
  grant then lands on the file and the open page's auto-save overwrites it. Needs 200+
  characters opened since that page loaded, so unlikely on a small server.

**Fix shape:** `TableStore` cannot see the registry. Either a listener list on the store
(as `homebrew_listeners` does) that the wiring layer points at `sessions.discard`, or
have the page compare `ctx["row"]` with the fresh `store.owned` row and rebuild on a
difference. ⚠ A discard under an open page needs the `ctx["path"] = None` care of
`home._delete` thought through: here the file must keep being saved.

## 3. MEDIUM — open redirect after login

* `auth.safe_target` (auth.py ~146) accepts `"/\t/evil.example"` and `"/\n/evil.example"`.
  **Confirmed** by calling it.
* The login and signup handlers pass the target to `ui.navigate.to`, which runs
  `window.open(path, "_self")`. Browsers strip tab and newline from a URL, giving
  `//evil.example`. **Confirmed** with Node: `new URL("/\t/evil.example", base).href` is
  `https://evil.example/`.
* The already-logged-in branch uses `RedirectResponse`, which encodes the tab (`/%09/…`)
  and is safe. `site._local` has the same weak check but only feeds a `RedirectResponse`.

**Fix shape:** refuse any target with a character below 0x21 or 0x7f, or any whitespace,
in both `safe_target` and `_local`. Add the cases to `tests/test_auth_gate.py`.

## 4. MEDIUM — uploads have no server-side size limit

* `ui.upload(max_file_size=…)` is a browser-side prop. NiceGUI's upload route reads the
  whole body. The handlers then read it all into memory: `home.py` `on_import`
  (`e.file.text()`), `table_board_view.py` `uploaded` and `_on_upload` (`e.file.read()`),
  and the import in `ui/custom.py`.
* The container has `mem_limit: 2g`. A few large parallel uploads from one logged-in
  account can get it killed. A restart also empties the in-memory login throttle.
* **Measured:** a 166 KB PNG of 6300×6300 as a token image cost 0.5 s of blocked event
  loop and ~310 MB peak RSS. `MAX_INPUT_PIXELS` is 40 M; any member can upload a token
  image, and anyone can make their own campaign.
* `home.py` records the browser-only limit as known and rates it as a guard against
  mistakes. With open signup it is more than that.

**Fix shape:** check `e.file.size()` (or the Content-Length) before reading; lower
`MAX_INPUT_PIXELS` for tokens; run the Pillow work in `run.io_bound`. ❓ The numbers are
the human's to rule.

## 5. LOW–MEDIUM — password guesses on `/account` are not throttled

`account_page.py`: save email, rename, change password and delete each call
`db.password_matches` / `db.rename_user` / `db.change_password` with no rate limit.
Someone with a live session (a borrowed browser) can guess at bcrypt speed, then change
the password. By reading. **Fix shape:** the existing `LoginThrottle`, keyed on the
account; `register_account_page` needs the same instance as the login page.

## 6. LOW–MEDIUM — the disk quota is bypassable by count

`TableStore.create` has no cap per account, and each campaign folder has its own 50 MB.
By reading. ❓ A cap needs a ruling (signup caps were ruled "not now" on 2026-09-26; this
is a different lever). Smaller, same family: a member can fill a campaign's 50 MB with
homebrew proposals (each stores the full prerequisite closure) or token images. The
Storyteller can recover by rejecting and removing.

## 7. LOW — NiceGUI keeps ~1 KB per cookie-less request forever

`nicegui.storage.RequestTrackingMiddleware` makes a `_users` entry for each new session id
and never removes it. **Measured:** 1,064 bytes each, no file written. Crawlers make it a
slow leak; ~2 million requests would reach 2 GB. Upstream behaviour (NiceGUI 3.14.0).
Cheapest answer: a scheduled restart, or a periodic prune of empty entries.

## 8. BUG — editing an existing text object on the board fails

`table_board_view.py` `BoardPanel.ask.done` (~516–521): the `else` of
`if kind == "token"` also runs for an EXISTING text object and replaces `data` with a new
object whose `x`/`y` are None, so the server answers "That drawing is not valid." By
reading; `tests/test_table_board_view.py` covers only the token ask. Fix: make the new-text
branch an `elif existing is None`.

## 9. LOW — approval adds homebrew before the copy exists

`TableStore.approve` (tables.py ~556–567) absorbs the base's homebrew into the campaign,
then calls `make_copy`. If the copy fails (the player unlocked the base after asking), the
homebrew stays. By reading. Fix: check the base first, or absorb after the copy.

## What held

* `access()`: no page body or handler in the campaign pages was found without it, and
  the stores check every Storyteller operation again.
* Every hosted write goes through `persistence.atomic_write` / `atomic_write_bytes`.
* No hosted control takes a path from the browser (the only path shown is finding 1).
* Public HTML escapes consistently; no raw-HTML or script sink takes user text; SQL is
  parametrised; ids are pattern-checked before they reach a path.
* Wiki search costs 15–30 ms per request.

## Not covered

No real browser. `ui/` beyond the hosted branches of `builder.py` and the HTML/JS sinks.
The deploy config beyond the Dockerfile and the memory limit.
