# Session handoff — 2026-09-12 (the public pages: front page, About, wiki — tests green)

# 👉 YOU ARE HERE

**2026-09-12, second session: the public pages SHIPPED, tests green. The human approved
the LOOK (*"a lot more in line with the rest of the site, I like it"*); the functional
click-through steps below are not yet confirmed.** `/` (front page), `/about` (⚠ DRAFT text) and `/wiki` (Charms, Martial
Arts, Spells, Merits & Flaws, Backgrounds — list + entry pages, search, filters) are plain
server-rendered HTML with no login. The hosted builder moved to **`/home`**, and a login
with no target lands there. **`vtt.md` §9.7 is the record.** Earlier the same day: the auth
click-through passed (§5.1d) and the site map was ruled (§9).

Last FULL suite: **3668 passed + 1 skipped** — OBSERVED 2026-09-12 after this work.
Preflight then added two cases to `test_public_pages.py` (the render sweep, and the
party page's **Builder** → `/home` round trip, mutation-checked), run with the seam, gate
and party-page files (546 passed). **3670 passed + 1 skipped OBSERVED** on the full
suite after the restyle, before the commit.
**The arithmetic agrees:** 3637 (computed, previous handoff) + 20 `test_public_pages.py`
+ 11 net in `test_auth_gate.py` (two enumeration cases for one, six prefix cases, the
dot-segment case, three more redirect-target cases) = 3668.
⚠ The count moves by machine and by optional dependency — see `docs/testing.md`, and do
not reconcile this against another machine. ⚠ **`bcrypt` is optional**: without it the
auth test files skip, and so does one case of `test_public_pages.py`.

**Working tree:** committed 2026-09-12 in two commits (the public pages; the deploy
files). Not pushed. Check `git status`.

## ✅ SHIPPED 2026-09-12 — the public pages (§9.7 of `vtt.md`)

* **Book-only wiki, mutation-checked.** `build_server` gives the wiki
  `rules_db.load_ruleset`; the builder keeps `load_app_ruleset`. A test writes a real
  homebrew Charm, runs production wiring, and asserts the wiki cannot show it. ⚠ **Do not
  add a `custom` filter in `ui/wiki_view.py`** — it would keep that test green with the
  wiring broken.
* **The gate test enumerates `app.routes` too**, because plain FastAPI routes never
  appear in `Client.page_routes`. Public routes are **named** in
  `tests/test_auth_gate.py::PUBLIC_ROUTES`, each a ruling. Mutation-checked.
* 🐞 **`BackgroundType.source` did not exist** — the 51 citations of the 2026-09-11
  backfill were dropped at load. Added as `Optional[Source] = None` (⚠ not `Source()`,
  whose book defaults to "Core"). The wiki is the first read site.
* **Design choices made without asking, all reversible:** `/home` IS the builder until
  piece 4 builds the landing page; `/logout` lands on `/`; paging at 100; no
  `robots.txt`/sitemap yet (needs the public base URL); the whole look — restyled
  twice the same day and now **matching the NiceGUI builder** (header bar, tab strip,
  tinted cards, Roboto/Material icons from NiceGUI's own fonts, per-splat palette); §9.7
  has both rounds of the human's feedback. ⚠ A new `Palette.fam` needs a row in
  `server/site._FAMILY`.
* ⚠ **The About text is a draft** (`server/public.py`). The human approves it before any
  deployment shows it.
* A book `RuleSet` measured **~15 MB traced / 0.07 s** — the first number for §5.3.

## ✅ SHIPPED and BROWSER-VERIFIED 2026-09-12 — §5 piece 3, auth

**§5.1d of `docs/plans/hosting-state-model.md` is the record** — the rulings, the
mechanics, the five negative controls and the known limits. What a reader needs first:

* **Rulings, asked before building (human, 2026-09-11):** self-signup page; SQLite
  `users` table now; context and save folder keyed to the **account**
  (`<root>/user-<id>/`), so a player's devices see one character.
* The gate is **`auth.AuthGate`, a middleware** — not a per-page `require_auth()` as the
  §5.1 sketch had. It covers every route by default, `/docs` and `/openapi.json`
  included. `OPEN_PATHS` is the exception list.
* ⚠ **`main()` installs the gate, `build_server` does not.** Starlette refuses
  `add_middleware` after the app starts, and unit tests call `build_server` in a process
  where a User-harness test already started it. `test_server_main.py` asserts `main`
  calls `install_gate` before `ui.run`. **Do not move the call into `build_server`.**
* `check_bind_is_allowed` and `--public` are **deleted**, as §5.1a required. The server
  now needs a third env var: **`EXALTED_DB_PATH`**, no default.
* `[server]` extra in `pyproject.toml`: `nicegui`, `reportlab`, `bcrypt` (not `passlib`).

### ✅ Second round, same session — the human ruled on the known limits

**§5.1d is the record** (a second rulings table, what shipped, controls 6–10, and
"Found on the way, second round"). In short:

* **Usernames are now case-sensitive** (ruling; reverses the first build).
* **Rate limit per username** — `server/throttle.py`. ⚠ Counts an attempt at its
  START, not after bcrypt; do not "fix" that, it is what closes the parallel race.
* **10 MB per account** — `server/quota.py`, through a new
  **`persistence.set_write_guard`** hook in `atomic_write`, installed by `main()`.
  ⚠ Every hosted write goes through `atomic_write`; a new write path that bypasses it
  bypasses the quota.
* **Manual password reset** — `python -m exalted_builder.server.users reset <name>`
  (and `list`). `EXALTED_ADMIN_CONTACT` puts *"Forgot your password? Email …"* on
  `/login`. The human is making `admin@x6568tank.com` for it.

### ✅ Third round — the cookie

**`Secure` ON** (ruling). The cookie is now **`__Host-exalted-session`**
(`server/main.SESSION_COOKIE`): the prefix makes browsers refuse it from any other
subdomain, which closes session fixation via the human's other `x6568tank.com` apps
(Jellyfin, Calibre, Seafile, Filebrowser). ⚠ **Never give it a `domain`** — the browser
then drops it. Checked on a live server's `Set-Cookie`. `.nicegui/` → a deploy concern,
understood.

### ⚠ Known limits still open — §5.1d has each with its cost

A reset does not end existing logins; signup is not rate-limited; no account delete;
homebrew is outside the quota; the session id still does not rotate at login (only the
physical-access case remains); **a LAN player on plain `http://192.168…` cannot log in**
— the Secure cookie needs HTTPS or `localhost`.

## 🎲 Answered this session — the Table replaces `/gm`

The human asked whether a shared Table an ST sets up replaces the GM screen. **Yes —
already ruled** (`vtt.md` §8 Q4 and §1.3): the GM page dissolves into a first-class
`Table` at **P3**. Auth only supplies the user id that Table membership will point at.
**There is deliberately no global admin/ST role on accounts** — Storyteller is a property
of a table.

## 👉 NEXT — in rough order of what would bite

- 👉 **The human: click through the public pages and approve (or rewrite) the About
  text.** See "Not browser-verified" below.
- **Deploy to `gilserver`** — `docs/deploy/homeserver.md` has every step. `Dockerfile` +
  `.dockerignore` are new and the image was built and probed locally (front page, wiki,
  `/home` → login, `__Host-` cookie, database owned by uid 1000). HTTPS is the existing
  Cloudflare Tunnel; the container is published on `127.0.0.1:8090` only. The `claude`
  account on the server has no `docker`/`sudo` on purpose, so the build, the Compose
  entry and the tunnel rule are the human's to run.
- **Wiki sections not yet shown**, all in `data/`, same pattern: trait text, the
  ST-screen tables, artifacts, thaumaturgy, the Dragon-King Paths. Plus `robots.txt` and a
  sitemap once the public base URL is settled, and a Wiki link in the logged-in builder.
- **§5 piece 4 — the DB, and §5.3's per-user rulesets.** ⚠ **Measure one merged `RuleSet`
  in memory BEFORE fixing the DB layout.** §5.3 reverses the original plan (per-user is
  *easier* than shared, because shared needs the `load_character` write hazard solved and
  per-user dissolves it) and that reversal has to be decided before the layout, not after.
  ⚠ **The layout grew on 2026-09-12** — several characters, base characters, tables,
  pending memberships: `vtt.md` §9.3. Both base-character questions are ruled (§9.2):
  a base change reaches **later copies only**, and a copy **can** exist with no campaign.
- **Backgrounds `source` — 51 of 63 DONE. 12 left, and they need a human with a page.**
  `status/backgrounds.md` lists all 12 with their scores. Two are Lunar and have no
  page-marked text on this machine at all. ⚠ **Do not lower the matcher threshold to
  clear them.**
- **Roll initiative for the whole table — BLOCKED** on the party holding real characters.
  That is phase **P3** of `docs/plans/vtt.md`, so it is scheduled rather than stuck.
  Stays a one-off: initiative's +1d10 is a printed fixed count. Do not generalise it.
- **A content-fidelity SCRIPT** (`tools/`) — diff authored descriptions against pasted
  source and REPORT differences. ⚠ **An option, not a debt.** It must never go into the suite.
- ⚠ **The duplicated Merit/Flaw strings — and it is TEN, not one.** Intersecting the
  string literals of `qt/advantages.py` and `ui/advantages.py` with `ast` gives **10 shared
  literals of 40+ characters**, byte-identical, with nothing stopping them drifting.
  ⚠ Older handoffs called this "the duplicated sentence", singular — a one-sentence framing
  invites a one-line fix that leaves nine behind. `ui/view.py` owns every other shared
  string and should own these.

## ⚠ Traps still live

**`config.storage_secret()` does not raise; `config.required_storage_secret()` does.** The
first returns a random per-process key — right for the desktop, silently wrong for a
server (every restart invalidates every session cookie, so every browser gets a new
session directory and loses sight of its auto-saved character). ⚠ **Do not call
`storage_secret()` from anything hosted.** §5.1a.

**Never patch by dotted string in this repo.** After any `nicegui_main_file` test,
`sys.modules["exalted_builder"]` is a hollow stub, and a dotted monkeypatch target fails
by test-file ORDER. `test_engine_seam.py::test_no_test_patches_by_dotted_string` enforces
it. Import the module and patch the object.

**`should_not_see` races async click handlers.** It returns on the first attempt at which
the text is absent. After a click, settle with a `should_see` on something the branch
produces first. See `feedback_should_not_see_races_async_handlers`.

**The prototype path is OUTSIDE the session root, on purpose.** A prototype inside the
root makes every `is_relative_to(root)` assertion pass with no isolation at all. §5.1a.

**The stale server wears a healthy port.** `reload=False`; a `kill` on the PID from
`pgrep … | tail -1` kills the WRAPPER, not the listener, and `curl` still answers **200**
off the old build. **Get the PID from `ss -ltnp | grep <port>`.**

**Any `ui.run` that registers these routes must pass a `storage_secret`.** `session_key()`
raises without one, on purpose. `server/main.py` passes the **required** accessor.

**The width budget** — `_BOXES_PER_ROW`, the tracker box sizes and `_RAIL_WIDTH` are ONE
budget, and no test can see it. Measure `page._scroll.widget().minimumSizeHint().width()`
against `page._scroll.viewport().width()`.

**The app still reports no version anywhere.** There is a runnable server, so *"is
everyone on the same build?"* is a live support question. Pair it with the launcher trap:
`branding.install_desktop_entry()` writes `Exec=` from `sys.executable`. ⚠ Check the DATES
before blaming the build; the stale-binary theory has been wrong twice.

## 🖱 Not browser-verified — what a human should click

**The public pages (new 2026-09-12).** Start the hosted server and, logged OUT:
`/` shows Wiki / Log in or make an account / About; `/wiki` shows five tabs with counts; a
Charm page links its prerequisite; the dropdowns filter on change; search finds
"ox body"; a Lunar Charm page (or the Exalt-type filter set to Lunar) re-themes to the
builder's Lunar palette; at phone width the header buttons shrink to icons and tables
become stacked rows. Then log in: it lands on `/home` (the builder); `/` now says **Your characters**;
the builder's **Party** → `/gm` → **Builder** returns to `/home`; **Log out** lands on
`/`. Read `/about` — it is a draft for the human's approval.

✅ **Auth — PASSED 2026-09-12**, all eleven steps (§5.1d). ⚠ For the next hosted
click-through: browse to `http://localhost:8080`, not `127.0.0.1` (Secure cookie), and
hand `users reset` over for a real terminal (`getpass`).

1. **Save on the DESKTOP still opens the filename prompt and downloads** (carried).
   Run `python -m exalted_builder.ui.builder`. Confirm the hosted-only buttons —
   **now three: Download a copy, Log out, and the party's Download a copy** — are
   absent there.

⚠ The Qt shell is untouched by this session.

## ❓ Open for the human

- **No open RULES questions.** This session touched no game values.
- **Design choices made without asking, all reversible:**
  - **Rate-limit numbers:** 5 free, 30 s doubling to 15 min, forget after 1 h.
  - **`DEFAULT_HOST` stays loopback** now that `--public` is gone.
  - **No filename prompt on "Download a copy"** (carried).
  - **A separate strict secret accessor** (carried).

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the one martial-arts absence
(`enlightenment`), and Haltan pets. Training times are still a no. The other splats'
Charms were explicitly left as they are (human, 2026-09-01). The caste/aspect-book
Background sweep is closed for planning on the human's hedge of 2026-09-11 — ⚠ a hedge,
not authority to author one.
