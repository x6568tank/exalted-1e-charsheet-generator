# Hosting: the state model — revised §3 and §5

**Replaces sections 3 and 5 of `exaltedcharsheethostingplan.md`** (drafted by Opus 4.6
against the v1.1 tree, before the Qt port). Everything else in that plan — the SQLite
JSON-blob store, the auth shape, the Docker/tunnel/backup work — survives review and is
not restated here.

⚠ **Why these two sections needed rewriting.** The original §5 asserts:

> The `ctx` dict is per-page-load, created inside `build_app()`. Multiple users each get
> their own `ctx` — NiceGUI isolates page instances automatically. No global state conflicts.

That is false, and it is the assumption the original effort estimate rests on. The
correction and its consequences are the whole of §3 below.

---

## 3. Session and state management — the core refactor

### 3.1 What is actually true today

`ui/builder.py:456`:

```python
def register_pages(ruleset: RuleSet, ctx: dict) -> None:
    @ui.page("/")
    def index() -> None:
        build_app(ruleset, ctx["char"], ctx["path"], ctx=ctx)

    @ui.page("/gm")
    def party_page() -> None:
        gm_mod.build_gm(ruleset, ctx)
```

`ctx` is built **once**, in `main()`, by `make_context(character, path)`, and both route
handlers close over that one dict. `build_app`'s `if ctx is None: ctx = make_context(...)`
fallback exists for standalone/test callers and never fires under `register_pages`.

**Consequence:** every browser that hits `/` is handed the same `ctx` and therefore the
same `Character` object. Two users on one server edit one character. There is no
isolation to preserve — there is isolation to *introduce*.

### 3.2 It is deliberate, and something depends on it

This is not an oversight to patch in passing. `make_context`'s docstring:

> The app's shared, mutable context. **Held outside any one page** so the builder ('/')
> and the GM party page ('/gm') work on the same objects — see `register_pages`.

The GM handoff is built on that object identity. `gm.py:147`:

```python
def open_in_builder(index: int) -> None:
    builder_mod.open_member(ctx, index)
    ui.navigate.to("/")
```

`open_member` repoints `ctx["char"]` at `party.members[index].character` **by reference,
not by copy** (`builder.py:114`), so builder edits mutate the party member in place with
no syncing code. Then `ui.navigate.to("/")` is a **full page load** — a new NiceGUI
client. The only reason the builder comes up pointed at the right character is that the
route closure reads the same process-global dict.

⚠ **So the session store must survive navigation.** This rules out the obvious first
answer (`app.storage.client`) before it is proposed — see 3.4.

### 3.3 The blast radius is small — the good news

```
$ grep -rln 'ctx\[' exalted_builder/ui/*.py
exalted_builder/ui/builder.py
exalted_builder/ui/gm.py
```

**Two modules.** Seven keys, and their read/write counts:

| Key | Sites | What it is |
|---|---|---|
| `char` | 23 | the active Character — **the object that must become per-session** |
| `dir` | 16 | save directory |
| `path` | 9 | save path |
| `party_path` | 7 | party file path |
| `party` | 6 | the GM's Party |
| `member` | 2 | index into the party, or None |
| `adversary_catalog` | 1 | template list — **read-only, genuinely shareable** |

No tab module touches `ctx` at all. They receive `(ruleset, character, save_path)` and
mutate the character in place. That contract does not have to change for isolation —
only for persistence (3.6).

### 3.4 The design: two-tier session state

The constraint that picks the design is NiceGUI 3.13's storage semantics (verified
against the installed version, not from memory):

| Store | Survives `navigate.to`? | Holds arbitrary objects? | Verdict |
|---|---|---|---|
| `app.storage.client` | **No** — discarded when the connection ends | Yes | Dies on the `/gm` → `/` handoff |
| `app.storage.tab` | Yes (per tab) | **No** — serialized | Cannot hold a `Character` |
| `app.storage.user` | Yes (per browser, cookie-keyed, server-persisted) | **No** — serialized | Cannot hold a `Character` |
| `app.storage.general` | Yes | No | Process-global — the bug we are fixing |

No single store does both jobs. So use two:

**Tier 1 — `app.storage.user`: identity and pointers only, all JSON-serializable.**

```python
app.storage.user = {
    "user_id": 3,
    "character_id": 41,     # DB row, or filename under the user's dir
    "party_id": None,
    "member": None,         # index into the party, or None
}
```

This is what survives a browser restart, and it is what `open_in_builder` writes before
navigating. It is *pointers*, never objects.

**Tier 2 — a server-side registry holding the live `ctx`, keyed by session.**

```python
# exalted_builder/server/session.py
_SESSIONS: dict[str, dict] = {}

def ctx_for(session_key: str, user_id: int) -> dict:
    """The live, mutable context for one browser session. Created on first use from
    whatever app.storage.user points at; reused on every subsequent page load in that
    session, which is what makes the /gm -> / handoff keep working."""
```

The registry holds the real `Character` object, so in-place mutation, the by-reference
party handoff and every existing tab contract all keep working **unchanged**. What
changes is that there are now N of them instead of one.

⚠ **The registry is a leak unless it is bounded.** One `Character` (plus an embedded
`Party`) per browser session, held forever, is a slow OOM on a 16GB box. It needs a TTL
sweep or an LRU cap, and eviction must be safe: an evicted session's next request
rehydrates from the store. **That means an unsaved edit can be silently lost on
eviction** — which is the argument for auto-save (3.7), not an argument against
eviction.

⚠ **`app.storage.user` requires `storage_secret`.** `ui.run(..., storage_secret=...)`
is currently set nowhere in the tree (`grep app.storage` returns nothing outside this
plan). Read it from an env var; do not commit one.

### 3.5 The seam is the `ctx` lifetime, not `save_path`

The original plan named `save_path` as "the abstraction seam." It is *a* seam, and the
persistence one — but it is not where the isolation bug lives, and fixing it alone
produces per-user *files* under one shared in-memory character. That is the plan's
Option C, and it does not work.

Revised options:

- **Option A (callback) — now REQUIRED, not the "if you want to do it properly" branch.**
  On a server there is no meaningful filesystem path per character; the row id is the
  identity. Replace `save_path: Path` with `save_fn: Callable[[Character], None]` across
  the 8 `build_*` signatures.
- **Option B (monkey-patching `persistence.save_character` per request) — STRUCK.**
  Not merely "fragile": a module-global rebind is itself process-global state, so under
  concurrent requests it reintroduces the exact bug this section exists to remove.
- **Option C (per-user directories) — demoted to a storage detail.** Orthogonal to
  isolation. Adopt it or the SQLite blob store on its own merits; neither changes the
  work in 3.4.

⚠ **The 9th save site.** The plan counts 8, which is right for `ui/`. Since the Qt port
merged there is also `qt/main_window.py:593`. It is out of scope for hosting — the native
app keeps filesystem saves — but a `save_fn` refactor that assumes 8 will leave it
uncompiling if the signature is shared.

### 3.6 What must not change

Unchanged from the original plan and still correct: `engine/`, `models/`, `ui/view.py`,
`custom_content.py`, `rules_db.py`. Add to that list:

- **The tab contract `(ruleset, character, save_path|save_fn)`.** Widening it to take a
  session or a user id would push identity into modules that have no business knowing
  about it, and would break the desktop and Qt callers.
- **`open_member`'s by-reference semantics.** Copying instead of sharing would silently
  break the party-card live update, which has no test that would catch it.

### 3.7 Auto-save

Manual save buttons stay; they are the honest UX and they already work. But see the
eviction hazard in 3.4: once a session can be evicted, "your edits are on the server
until you press Save" stops being true.

Recommendation: **debounced auto-save on the existing `changed()` callback** — at most
once per N seconds after the last mutation, via `ui.timer`. Every tab already funnels
mutations through `changed()`, so this is one helper, not eight.

⚠ Do **not** save on every `changed()` call. The dot tracks fire it per click.

### 3.8 Write this test FIRST

Per the house-bug rule in `CLAUDE.md`: a rule wired into one lifecycle phase passes its
own tests and never runs. The session equivalent is a session that is isolated in the
phase you tested and shared in the one you did not.

**Before any refactor**, write a NiceGUI `User`-harness test that:

1. Opens `/` as session A, edits a trait.
2. Opens `/` as session B.
3. Asserts B does **not** see A's edit.
4. Repeats across the `/gm` → `/` navigation, which is the phase most likely to leak.

⚠ It must fail on today's code. A green run against the current tree means the harness
is sharing a client, not that the app is isolated. **Confirm the red before writing the
fix** — see the `negative-control-goes-positive` trap.

⚠ The existing UI harness (`tests/_ui_main.py`) builds shared module-level fixture
characters, and a `@ui.page` route builds once per test session. This test needs **its
own route**, or it will pass alone and fail — or worse, pass meaninglessly — in the
suite.

### 3.9 Revised scope

| Piece | Effort |
|---|---|
| `server/session.py` — registry, rehydrate, eviction | 1 day |
| Isolation tests (3.8), written first | 1 day |
| `register_pages` → per-request ctx resolution | 1 day |
| `save_path` → `save_fn` across 8 signatures + call sites | 1–2 days |
| Debounced auto-save helper | Half a day |
| **§3 total** | **~5 days part-time** |

The original plan budgeted **half a day** for this section (Option C, "path construction
only"). That is the single largest correction to the estimate.

---

## 5. Entry point refactor

### 5.1 Shape

A new `exalted_builder/server/main.py`, leaving `ui/builder.py:main()` intact so the
desktop entry point keeps working (a hard constraint in the original plan, retained).

```python
def main() -> None:
    ruleset = rules_db.load_app_ruleset(_DATA_DIR)   # once; read-only, see 5.3
    db.init_db()                                     # WAL mode — see 5.4
    register_server_pages(ruleset)
    ui.run(host="0.0.0.0", port=8080, reload=False,
           storage_secret=os.environ["EXALTED_STORAGE_SECRET"])
```

⚠ **Routes register once, at import. State resolves per request, inside the handler.**
This is the structural fix for §3, and it is easy to get subtly wrong:

```python
def register_server_pages(ruleset: RuleSet) -> None:
    @ui.page("/builder")
    def builder_page() -> None:
        user_id = require_auth()                      # redirects if absent
        ctx = session.ctx_for(session_key(), user_id) # per-request, NOT closed over
        build_app(ruleset, ctx["char"], ctx["save_fn"], ctx=ctx)
```

The difference from today is one line and the whole bug: `ctx` is **resolved in the body**
rather than captured by the closure. `ruleset` stays captured — it is genuinely shared.

Routes: `/login`, `/` (character index), `/builder`, `/gm`.

### 5.2 Correcting the original §5 on `app.storage.user`

The original says:

> ⚠ NiceGUI's `app.storage.user` is per-browser, not per-account. Two browsers logged
> into the same account get separate storage dicts. This is fine — it means each browser
> tab has its own active character, which is the correct behavior.

Half right, and the conclusion does not follow. Per-browser is correct. But "each browser
**tab** has its own active character" is wrong — `app.storage.user` is cookie-keyed and
therefore **shared across tabs of the same browser**. Two tabs of one browser get one
session and one active character; opening a second character in a second tab will
repoint the first.

That may be acceptable (it matches the desktop app, which edits one character at a
time). It is a **product decision that needs your ruling**, not a property to assume.
If per-tab is wanted, tier 1 moves to `app.storage.tab` and the cost is that it does not
survive a browser restart.

### 5.3 The ruleset is shared — and the custom layer makes that a real problem

`load_app_ruleset` merges the user's custom library over the book data (`rules_db.py:17`,
`_load_custom_layer`). Loading it once at startup and sharing it is right for the
rules — they are read-only — but it has two consequences the original plan does not see:

1. **Homebrew is a shared namespace and only refreshes on restart.** A user saving a
   custom Charm will not see it until the process reloads.
2. ⚠ **`persistence.load_character()` WRITES to the custom library on load.** It calls
   `custom_content.absorb_definitions()` by default (`persistence.py:174`). With a shared
   `custom/` volume, **user A opening a save injects their homebrew into everyone's
   library.** That is a multi-user data hazard, not a cosmetic one.

**The fix is cheaper than the problem looks.** `custom_content.py` is stateless — every
function takes `custom_dir`. Per-user homebrew is a path change, not a feature:

- give each user `<data>/users/<id>/custom/`
- load a per-user ruleset (or cache one per user) rather than one process-wide
- pass `custom_dir=` through `load_character`

⚠ This **reverses** the original plan's "per-user custom content libraries — future
enhancement, not needed for v1." Per-user is *easier* than shared, because shared needs
#2 solved and per-user dissolves it.

**Open question for you:** per-user rulesets mean N merged `RuleSet` objects in memory.
Measure one before committing — if it is large, cache with an LRU keyed by user, or
keep one shared read-only book ruleset and overlay per-user custom at request time.

### 5.4 Smaller corrections

- **SQLite needs WAL** (`PRAGMA journal_mode=WAL`) with concurrent writers, plus a busy
  timeout. One line at `init_db()`; unmentioned in the original.
- **The `[server]` extra.** As the original says — but note `bcrypt` directly rather than
  `passlib`, which is unmaintained and pins an old bcrypt.

### 5.5 Revised scope

~150 lines for the entry point and page registration (up from the original's 100 — the
auth gate and per-request resolution are the additions), plus whatever 5.3's ruling costs.

---

## Open questions — these need your ruling, not a default

1. **Tab semantics (5.2).** One active character per browser, or per tab?
2. **Per-user vs shared homebrew (5.3).** Recommendation is per-user, reversing the
   original plan. Confirm before the DB layout is fixed.
3. **Eviction vs auto-save (3.4, 3.7).** How long may an idle session hold an unsaved
   character before it is dropped?
4. **Does the GM page ship in v1?** The original defers it, but `/gm` shares `ctx` with
   `/` and the session work has to handle it either way. Deferring the *page* does not
   defer the *state* problem.
