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

The constraint that picks the design is NiceGUI's storage semantics.

⚠ **RE-VERIFIED 2026-09-11 against the installed NiceGUI 3.14.0**, by running the stores
rather than reading about them. The 3.13 table had **two wrong cells**, and the corrected
table is below. The probe is preserved as the method, not as a test — see "How this was
checked" at the end of this section. **The design survives, but three new constraints
land.**

| Store | Survives `navigate.to`? | Holds arbitrary objects? | Verdict |
|---|---|---|---|
| `app.storage.client` | **No** — discarded when the connection ends | Yes | Dies on the `/gm` → `/` handoff |
| `app.storage.tab` | **Yes** (per tab, `sessionStorage`-keyed) | **Yes — if and only if `redis_url` is unset** | Per *tab*, not per browser. See the trap below |
| `app.storage.user` | Yes (per browser, cookie-keyed, server-persisted) | **No** — serialized | Cannot hold a `Character` |
| `app.storage.general` | Yes | **No** — serialized | Process-global — the bug we are fixing |

**Correction 1 — `app.storage.tab` is NOT serialized by default.** `storage.py:178`: with
no Redis configured it is a plain `ObservableDict`, in-process, and it holds a live
`Character`. `static/nicegui.js:383` keys it to `sessionStorage.__nicegui_tab_id`, which is
reused across a navigation, so it also survives `/gm` → `/`. Proven: a non-serializable
object written on `/a` was read back intact on `/b` after `ui.navigate.to`, in the same
run that saw `app.storage.client` come back `GONE`.

⚠ **This looks like it dissolves tier 2, and it does not. Do not take the shortcut.**
Tab storage is keyed per *tab*; the ruling in `vtt.md` §8 Q1 is per *browser*. A tab-keyed
live `Character` gives two tabs two divergent in-memory copies of the same character —
the isolation bug this section exists to remove, one scope down, and with no test that
would catch it. **Tier 2 stays keyed by the cookie session id.** The one thing worth
taking from this finding is that `prune_tab_storage` (a 10-second timer, `app/app.py:88`,
against `max_tab_storage_age`) is a working model for the tier-2 sweep 3.4 already
requires.

**Correction 2 — `app.storage.general` is serialized too** (`FilePersistentDict`), so its
"No" was right for the wrong reason. It rules itself out on scope regardless.

**Constraint 1 — reading `app.storage.tab` requires an established socket connection.**
`storage.py:162` raises if `client.has_socket_connection` is false, and a page body runs
*before* the client connects. Any page that touches tab storage must be `async` and
`await context.client.connected()` first. This is a real cost on the per-request `ctx`
resolution in §5 and is not in the estimate.

**Constraint 2 — `app.storage.user` accepts an unserializable value silently and fails
later, elsewhere.** The assignment succeeds; the write happens in a background task, and
`serialization.py:13` raises there. Observed: the page printed *"USER ACCEPTED THE OBJECT
AT THE ASSIGNMENT"*, and the `TypeError` naming the offending key path arrived as a logged
`ERROR` record. **Nothing fails at the line that caused it.** A test that puts a
`Character` into tier 1 by mistake passes unless it asserts on `caplog`. This is the same
shape as the `⚠` dialog-handler rule already in `feedback_nicegui_dialog_lifecycle`.

**Constraint 3 — `storage_secret` is load-bearing for the tests, not only for production.**
`app.storage.user` raises `RuntimeError` without it. The `User` harness passes a secret
**only** when it builds the app from a `root` function; with a `main_file` it `runpy`s the
file, so the secret must come from **that file's own `ui.run(...)` call**
(`testing/user_simulation.py:40` vs `:38`). ⚠ `tests/_isolation_main.py` calls bare
`ui.run()` today, so **P0's own main file cannot exercise tier 1 until it passes one.**

### The Redis question — answered: it does not rescue the single-process assumption

`vtt.md` flagged `app.storage.redis_url` / `redis_key_prefix` as possibly bearing on the
single-process design. **It does not, and it makes things worse if enabled.**

- Both are read from `NICEGUI_REDIS_URL` / `NICEGUI_REDIS_KEY_PREFIX` **at class-definition
  time** (`storage.py:78-82`) — an import-time env read. Setting the env var after import
  has no effect.
- With a URL set, `_create_persistent_dict` returns a `RedisPersistentDict` for *every*
  store including `tab` (`storage.py:172`). That **flips the tab row to "No"** and removes
  the only store that could have held a live object.
- Redis is therefore the multi-process escape hatch **for JSON-serializable state only**.
  The tier-2 registry holds a live `Character` and can never be JSON — so it is
  inherently single-process whether or not Redis is present.

**Conclusion: run one worker. Redis is not an alternative to that, and the plan's
single-process assumption stands.** ⚠ If Redis is ever turned on, everything above changes
and this table must be re-verified; treat `NICEGUI_REDIS_URL` as a design-breaking switch,
not a deployment detail.

No single store does both jobs at browser scope. So use two:

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

✅ **BUILT 2026-09-11** — `exalted_builder/server/session.py`, with
`tests/test_session_registry.py` (12 tests).

✅ **WIRED 2026-09-11** — `ui/builder.py:register_pages` now builds one registry per
process and both routes resolve their context in the page **body**. The two P0 isolation
tests XPASSed on the wiring commit and their `xfail` markers are deleted; they are live
tests now. **A green registry suite was never evidence that the app was isolated — the
isolation suite is.**

The shipped API differs from this sketch in two ways, both deliberate:

```python
registry = SessionRegistry(factory=..., max_idle_seconds=3600, max_sessions=200,
                           on_evict=..., clock=time.monotonic)
registry.ctx_for(session_key)   # same dict for the same key; factory on first use
registry.sweep()                # evict by idle time; returns the count
registry.discard(key)           # logout
```

1. **A class, not a module-level `_SESSIONS` dict.** A module global is itself
   process-global state, which is the shape of the bug being removed, and it leaks
   between tests. The wiring layer instantiates one per process.
2. **`factory(key)`, not `user_id`.** The registry does not know about auth or the DB.
   Mapping a cookie to a user is the caller's job, in the closure it passes.

The registry holds the real `Character` object, so in-place mutation, the by-reference
party handoff and every existing tab contract all keep working **unchanged**. What
changes is that there are now N of them instead of one.

⚠ **`on_evict` is the seam 3.7's auto-save plugs into, and it is load-bearing.** If the
hook raises, the registry **keeps** the session and re-raises. An eviction discards
unsaved work, so a failed save must not also lose the context — memory is the cheaper
loss.

⚠ **`protect` in `_apply_cap` has exactly one reachable failing case, and it is
`max_sessions=0`.** Above 0 the new session is always the most recently used, so the
least-recently-used rule can never select it and a defect in the protection cannot show.
The test uses a cap of 0 for that reason. This was found by mutation: the first version
of that test **passed against the broken implementation**, which is the
`CLAUDE.md` §7 pattern — a rule in a location where it does not operate.

⚠ **The registry is a leak unless it is bounded.** One `Character` (plus an embedded
`Party`) per browser session, held forever, is a slow OOM on a 16GB box. It needs a TTL
sweep or an LRU cap, and eviction must be safe: an evicted session's next request
rehydrates from the store. **That means an unsaved edit can be silently lost on
eviction** — which is the argument for auto-save (3.7), not an argument against
eviction.

⚠ **`app.storage.user` requires `storage_secret`.** `ui.run(..., storage_secret=...)`
is currently set nowhere in the tree — re-confirmed 2026-09-11, `grep -rn 'app.storage\|
storage_secret'` over `exalted_builder/` and `tests/` returns **nothing**. Read it from an
env var; do not commit one. See Constraint 3 above: this also blocks the P0 main file.

### How this was checked

Re-run this before trusting the table against any future NiceGUI. A copy of the probe is
**not** in the suite — it asserts a third-party library's semantics, and it belongs in a
session, not in 3443 tests.

Two files under `tests/`: a `_probe_main.py` with `@ui.page('/a')` and `@ui.page('/b')`,
each `async` and each awaiting `context.client.connected()`, writing a deliberately
non-JSON-serializable object into `app.storage.tab` and `app.storage.client` on `/a` and
reading both back on `/b`; and a test marked `@pytest.mark.nicegui_main_file(MAIN)` that
opens `/a`, clicks through, and reads the label on `/b`.

Three traps cost time and will cost it again:

1. `pytest_plugins = ['nicegui.testing.plugin']` pulls in Selenium. The project loads
   `nicegui.testing.user_plugin` in the **top-level** `conftest.py`; a probe outside the
   project root gets neither that nor `asyncio_mode`. **Put the probe in `tests/`.**
2. The main file needs the `if __name__ in {"__main__", "__mp_main__"}: ui.run()` guard,
   because the harness executes it with `runpy.run_path(run_name='__main__')`.
3. An `async` page body runs **after** the HTTP response. `user.find(...)` immediately
   after `user.open(...)` finds an empty page; `await user.should_see(...)` first.

### 3.4a The wiring, as shipped 2026-09-11

`register_pages(ruleset, ctx)` keeps its signature and now returns the registry. Three
things about it were decided at the keyboard and are not in the sketch above.

**1. The caller's `ctx` became a PROTOTYPE, not the live state.** This is the whole of the
change and it is a semantic reversal, not a plumbing detail. `builder.session_context_factory(prototype)`
returns `factory(key)`, and the registry calls it per session: a deep copy of the Character
and of the Party, the same paths, and the **same** adversary catalogue (read-only rules
data — §3.3 already says it is genuinely shareable). Desktop behaviour is unchanged because
a desktop run has exactly one session.

⚠ **The copy has one invariant and nothing else in the suite would have caught it.**
Inside one context `ctx["char"]` can *be* a party member's character, by identity —
`open_member` points it there by reference and `close_member` leaves it there with
`member` back to None. Copying `char` and `party` independently silently severs that, and
the party card stops following the builder's edits. The factory finds the member by `is`
and points at the copy. `tests/test_session_context_factory.py` covers it in both
`member` states, and the mutation was run: removing the identity branch fails exactly
those two cases and nothing else.

**2. The session key is `app.storage.browser["id"]`, and there is no fallback.** That is
the id NiceGUI writes into the signed session cookie: shared across the tabs of one
browser, and it survives a navigation — which is the ruling in `vtt.md` §8 Q1 and is why
this is not `tab`. ⚠ `builder.session_key()` **raises** when `ui.run` got no
`storage_secret`. A constant fallback would hand every browser one context, which is the
defect being removed, and no test would report it. A loud failure at the first page load
is the cheaper outcome.

**3. `ui/gm.py:main()` needed the secret too, and the earlier census missed it.** The
additive commit added `storage_secret()` to three `ui.run` call sites and recorded that
"the nine per-screen dev entry points are untouched; they use no storage." That was true
then and false the moment the routes read a cookie: `gm.py:main()` calls
`register_pages`, so both its pages would have raised at load. ⚠ **Any future `ui.run`
that registers these routes must pass a secret.** Nothing enforces it.

**Not done in this row, on purpose:** the idle `sweep()` is unwired. The registry is still
bounded by `max_sessions`, so this is not a leak; the sweep needs an app-wide timer and
belongs with the long-lived server in §5, next to the auto-save that `on_evict` feeds.

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

### 3.5a The refactor, as shipped 2026-09-11

`exalted_builder/ui/saving.py` is new. It holds the `SaveFn` type and
`save_to_path(path)`, which is the desktop callback: it writes the file and it shows the
notification. **Seven `build_*` tabs take `save_fn: SaveFn` as their third positional
argument** — editor, gear, advantages, picker, combos, play, storyteller. A tab can no
longer see a path, thus a tab can no longer assume a file system.

Four things were decided at the keyboard and correct the section above.

**1. ⚠ The 9th-save-site warning was wrong, and in a useful direction.** `qt/` imports
only `ui.theme` and `ui.view`; it calls no `build_*`. `qt/main_window.py:593` is a save
SITE, not a `save_path` PARAMETER, and it was untouched. The signature change is confined
to `ui/` and `tests/`. **The count that mattered was not 8 or 9 but 160** — the
`build_*` call sites in `tests/_ui_main.py`, which no estimate mentioned.

**2. 🐞 The tab-level `save_path` was DEAD in the hosted path, and that is why this was
cheap.** Each tab used it in exactly one place: a `save()` wired to a Save button that
renders only under `with_header=True`. The builder passes `with_header=False` to all
seven. So the parameter that §3.5 calls "the persistence seam" was reachable only from
the seven per-screen dev entry points. **The live save is `builder.save()`**, which is
the two-way branch and still has no third deployment. ⚠ Do not read this refactor as
having fixed hosted saving. It removed a false affordance; it did not add a write path.

**3. `build_app` keeps `save_path`, on purpose.** It is the app shell, not a tab: it owns
the file dialogs and it builds the fallback context. It now derives `tab_save` from the
LIVE `ctx["path"]` and hands that to each tab, so a load, a New, or a Save-As is picked
up without a refresh. That is the callback §3.7's auto-save should call.

⚠ **That asymmetry bit within the hour, and it will bite again.** "Every `build_*` takes
a callback now" is false for exactly one function, and the mechanical sweep converted
four `build_app` call sites in `tests/_ui_main.py` along with the rest. **The failure did
not name the argument, the function, or the call**: NiceGUI raised *"argument should be a
str or an os.PathLike object … not 'function'"* from inside a page handler, six tests
deep. `build_app` now rejects a callable with a TypeError that says which of the two
contracts the caller wanted, and `test_build_app_rejects_a_save_callback` holds it. This
is `feedback_turn_a_repeated_warning_into_a_mechanism`: the ⚠ in the docstring was
already there and was not enough.

**4. The two notification wordings are now one.** Five tabs said `Saved to {path}` and
play/storyteller said `Saved {path.name}`. `save_to_path` says the first. This is
visible only on the dev entry points.

#### 🐞 Seven wirings, seven chances for the house bug

⚠ **Before this change, no test in the suite clicked Save.** A tab could have dropped its
third argument entirely and the suite stayed green. `tests/test_tab_save_fn.py` is the
guard: one parametrised case per tab, each asserting the callback ran **once** and
received that tab's character **by identity** — a count alone passes when a tab saves the
wrong character, which a party of several members makes reachable. Plus a control that
rendering a tab saves nothing.

**The negative control was run per tab, and it is the reason to trust the seven cases.**
Replacing `save_fn(character)` with a no-op in one tab reddens exactly that tab's case
and leaves the other six green. Seven for seven. One shared assertion would have hidden
six of them.

⚠ **The runpy trap cost a cycle and will cost the next one too.** The harness executes
the `main_file` by PATH, so it becomes a module object that is *not* the one the test
imports. The first version of this test recorded calls into a module-level list in
`_save_fn_main.py` and read an always-empty list — **all seven failed for a reason that
was not the defect.** Shared state must live in a third module that both sides import by
name (`tests/_save_fn_state.py`; `tests/_isolation_names.py` exists for the same reason).

### 3.6 What must not change

Unchanged from the original plan and still correct: `engine/`, `models/`, `ui/view.py`,
`custom_content.py`, `rules_db.py`. Add to that list:

- **The tab contract `(ruleset, character, save_path|save_fn)`.** Widening it to take a
  session or a user id would push identity into modules that have no business knowing
  about it, and would break the desktop and Qt callers.
- **`open_member`'s by-reference semantics.** Copying instead of sharing would silently
  break the party-card live update, which has no test that would catch it.

### 3.7 Per-session store, and write-through auto-save

⚠ **This section was re-specified on 2026-09-11, before any code was written. Two of its
three original claims were false. Read 3.7a for what they were — the retraction is the
useful part.**

Manual save buttons stay; they are the honest UX and they already work. But see the
eviction hazard in 3.4: once a session can be evicted, "your edits are on the server
until you press Save" stops being true.

**This is one row, not two.** The debounce is the cheap half. The half that makes the
debounce mean anything is that a session must have somewhere of its own to write.

#### 🐞 The blocker: every session shares one save path

`ui/builder.py:session_context_factory` copies the prototype's path verbatim:

```python
return {"char": char, "path": prototype["path"], "dir": prototype["dir"], ...}
```

The isolation fix of 3.4a isolated the **Character**. It did not isolate the
**destination**. Every session on a hosted server therefore points at one file, and the
collision does not depend on the character's name — the path is literally the same
object. (The name only matters for `open_member`, which recomputes the filename from the
shared `ctx["dir"]`.)

⚠ **Auto-save wired to `tab_save` as it stands today would have N browsers writing one
file on a timer, last-writer-wins, with no error.** Nothing reports it. This is invisible
right now only because `with_header=False` means no tab save is reachable in the app
(3.5a finding 2), so the defect has no live caller yet. **Auto-save is the live caller.**

**`path` is a third thing the factory must produce per session**, alongside `char` and
`party`. That is the row.

#### The shape: RAM is a cache, the store is the truth

The mainstream web answer to "what if a session is evicted" is *there is nothing to
lose* — the store holds the truth and server memory is a cache. Adopt that **property**.
Do not adopt the **mechanism** that usually delivers it.

⚠ **The mechanism does not port, and the reason is worth keeping.** Google Docs, Figma
and Foundry can use stateless read-per-request handlers because the live document model
sits in the *browser* and the server is persistence plus broadcast. NiceGUI is the exact
inverse: the Python process holds the widget tree and the domain objects, and the browser
is a thin renderer. During an editing session there are no requests to be stateless
between. Porting it literally would mean tabs taking an **id** instead of a `Character` —
which is the tab-contract widening that **3.6 forbids**, and which breaks the desktop and
Qt callers — and it would destroy `open_member`'s by-reference identity, **which 3.6 also
names and which no test would catch**.

Write-through gets the property without either cost:

1. The registry keeps holding live objects. Unchanged.
2. Auto-save writes to a per-session destination.
3. Eviction discards RAM only. `on_evict` already exists for this.
4. The next request rehydrates from the store.

The registry stops being the **sole** copy. It does not stop holding live objects — that
distinction is the whole of the fix, and an earlier note in this session got it wrong by
conflating them.

Residual exposure is **one debounce interval** of unsaved edits. That is also Google
Docs' exposure. It is accepted.

#### Where it writes

**A per-session directory now; a SQLite row when auth lands in §5.**

`<root>/<session_key>/<name>.character.json`, with `<root>` from `server/config.py` —
which already owns the environment-derived deployment settings and already carries the
"no default in a file" discipline this needs.

Reasons, in order:

- `session_key()` exists and is already the registry's key. The directory falls out of
  what is built.
- It reuses `persistence` unchanged. No schema, no new dependency, no `[server]` extra.
- It is what `on_evict` needs to rehydrate **from**. Today nothing writes, so there is
  nothing to rehydrate from, which is why 3.4's rehydrate path has never run for real.
- ⚠ **The destination is swappable for free, and that is what the 3.5a refactor bought.**
  The seven tabs see only `save_fn`. Replacing a directory with a DB row touches none of
  them. Do not let the cheap choice here feel permanent.

⚠ **Anonymous-session ownership is standard practice, not a compromise** — CodePen,
JSFiddle and Figma anonymous files all key work to a cookie session and re-key it on
signup. Note for §5 that re-keying a **row** is an owner-column update, while re-keying a
**directory** is a move; that is a mild argument for the DB, and not a reason to build it
first.

#### The trigger: poll a dirty hash. Do NOT hook `changed()`.

⚠ **The original "one helper on `changed()`" recommendation was false. Only three of the
seven tabs define `changed()`** — editor, gear, advantages. The others funnel elsewhere:
`combos.refresh()`, and `play`, `storyteller` and `picker` calling `body.refresh()` /
`detail.refresh()` directly at roughly ten, one and twelve sites. **Hooking `changed()`
gives auto-save in three tabs and silence in four, with nothing red** — which is
`CLAUDE.md` §7's house bug exactly, in the plan that warns about it.

Use instead: **one `ui.timer` in `build_app` that compares a hash of
`ctx["char"].model_dump_json()` and calls `tab_save` when it differs.**

- Measured at **0.015 ms** for a 3 KB character (2026-09-11). The poll is free.
- ⚠ **It cannot be wired to the wrong phase, because it is not wired to a phase.** A
  mutation site added later is covered with no action. That immunity is the reason to
  prefer it, and it is worth more here than the per-tab provability of the alternative.
- ⚠ **The trigger is definitionally correct**: it fires when the bytes that would be
  written differ. A funnel call is a lossy proxy — `readout.refresh()` after a *failed*
  purchase would write a byte-identical file.
- ⚠ **It sees only what serializes.** Confirm the play-tab state (`willpower_spent`,
  fatigue, health boxes) is on the `Character` and not beside it. **Not verified.**
- ⚠ **Load and New must reset the baseline hash.** They repoint `ctx["char"]`, which
  reads as one enormous diff, and the timer would immediately write the just-loaded file
  back over itself. Harmless, but it is the one place this design can go wrong, and it is
  a third touchpoint in `build_app` beyond the timer itself.

⚠ The original warning still stands and generalises: **do not save per mutation.** The
dot tracks fire their funnel per click.

#### Write this test FIRST

Per 3.8's rule, and the failure mode here is specific: **two sessions must get two
destinations.** Assert it on the factory, not on the file — a test that writes and reads
one file back passes when both sessions share it.

⚠ The ⚠ in 3.5a's docstring was written an hour before it failed to prevent the mistake
it described. A warning is not a mechanism. See
`feedback_turn_a_repeated_warning_into_a_mechanism`.

### 3.7b The row, as shipped 2026-09-11

**The spec above is what was built. One thing it did not know about, and it is the
interesting part.**

#### 🐞 The factory was not the only place that set the destination

The spec fixed `session_context_factory` and stopped there. But **`new_character` and
the upload branch of `_apply_loaded` each recomputed the destination from
`persistence.default_save_dir()`**, which is process-wide. So the factory handed the
session its own directory and **the first click of New took it straight back out**, into
a folder that every session shares.

⚠ **This is the house bug in its type-1 form** — the rule was implemented in the wrong
place relative to a later phase — and the factory's own unit tests pass with it present,
because the factory *is* correct and a handler overrules it afterwards. That is exactly
why §3.7 says to assert on the factory **and** why that is not sufficient on its own:
`tests/test_session_destinations.py` runs the production wiring and clicks New, and it
was the only thing that saw this.

The fix is a `ctx["home_dir"]` — the one folder a session owns — read by both handlers.
⚠ **Do not call `persistence.default_save_dir()` in a handler.** That is the shape of
the defect, and `make_context`'s docstring now says so.

#### What shipped

* `server/config.session_root()` — reads `EXALTED_SESSION_ROOT`, **raises** when unset.
  No default, for the same reason `storage_secret()` has none: a fallback gives every
  session one directory and one browser looks perfectly healthy.
* `session_context_factory(prototype, session_root=None)` — `<root>/<key>/<filename>`.
  With **no** root it keeps the prototype path, which is the desktop: one user owns the
  file system, so Save must write the file the user opened. ⚠ That polarity is
  deliberate. Forgetting the root on the desktop is *loud* (the file does not update);
  a hosted run that forgets it gets the raise.
* `builder.session_dirname(key)` — one path component. ⚠ The unsafe-character
  replacement **alone was not sufficient**: it maps `"a/b"` and `"a_b"` to one name,
  which is this section's own defect one level down. A digest of the original key is
  appended whenever a character changed, so two keys never collide.
* `saving.AutoSave` + `saving.AUTOSAVE_SECONDS` (5 s) + `save_to_path(..., notify=False)`.
  The digest advances **on a successful write only** — a digest that advanced on failure
  would discard that edit permanently, because the next poll reads clean. A write error
  is caught and reported once per failure run, never raised: a NiceGUI timer callback
  that raises is logged, not surfaced.
* `build_app(..., auto_save=False)`, and `register_pages` passes
  `auto_save=session_root is not None`.

#### ⚠ Auto-save and isolation share ONE switch, on purpose

The hazard this section names — a timer plus a shared path — **cannot be configured**,
because the value that enables auto-save is the value that isolates the destination.
Two independent switches would leave the dangerous pair reachable, and it reports
nothing. Do not split them. See `feedback_turn_a_repeated_warning_into_a_mechanism`: the
⚠ in 3.5a's docstring was written an hour before it failed to prevent the mistake it
described, so this row spent the mechanism instead of another warning.

#### The precondition the spec flagged is CONFIRMED

Play-tab state serializes. `Character.play` is a real pydantic field (`PlayState`), so
`willpower_spent`, `fatigue`, `health`, `limit`, `clarity_temporary` and `renown` all
reach the digest. `test_a_play_state_change_changes_the_digest` holds it. ⚠ A tracker
added **beside** the Character in future would be invisible to auto-save with nothing
failing.

#### Not addressed by this row — ✅ CLOSED LATER THE SAME DAY by §5 piece 2

⚠ **`builder.save()`'s two-way branch was untouched by this row.** A hosted manual Save
showed a green *"Downloading …"* toast; auto-save did not go through it, so the hosted
story was *"your edits persist, but the Save button still lies."* **§5.1b closes it** —
`save()` branches three ways and the `hosted` bit drives all three behaviours.

### 3.7a What this section said before, and why it was wrong

Kept because both errors are the project's recurring shapes, not slips.

1. **"Every tab already funnels mutations through `changed()`, so this is one helper,
   not eight."** Three of seven. The plan asserted a uniformity that the code never had,
   and building on it would have produced a rule that runs in three places and is absent
   in four — with every test green. **A plan can carry a house bug before a line of code
   exists.**
2. **"Half a day."** True for the debounce alone, and the debounce alone does nothing —
   it would have written every session's edits into one shared file. The estimate priced
   the visible half. See `feedback_plan_estimates_are_not_wall_clock`.

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
| ✅ `server/session.py` — registry, rehydrate, eviction | 1 day — **DONE 2026-09-11** |
| ✅ Isolation tests (3.8), written first | 1 day — **DONE (P0), still `xfail`** |
| ✅ `register_pages` → per-request ctx resolution | 1 day — **DONE 2026-09-11** |
| ✅ `save_path` → `save_fn` across 7 tab signatures + call sites | 1–2 days — **DONE 2026-09-11** |
| ✅ Per-session save destination + write-through auto-save (3.7) | 1–1½ days — **DONE 2026-09-11** |
| **§3 total** | **~5½ days part-time** — **§3 IS COMPLETE** |

⚠ **That row was "half a day" until 2026-09-11.** It was re-estimated before any code was
written, when the shared-path blocker in 3.7 was found. The debounce is still half a day;
it is the per-session destination underneath it that was never priced. **Nothing was
built against the old number.**

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
        require_auth()                                # redirects if absent
        ctx = sessions.ctx_for(builder.session_key()) # per-request, NOT closed over
        build_app(ruleset, ctx["char"], ctx["save_fn"], ctx=ctx)
```

The difference from today is one line and the whole bug: `ctx` is **resolved in the body**
rather than captured by the closure. `ruleset` stays captured — it is genuinely shared.

✅ **`ui/builder.py:register_pages` already has this shape** (§3.4a). What `server/main.py`
adds over it is the auth gate and a factory that rehydrates from the DB instead of copying
a prototype. ⚠ Note the shipped `ctx_for` takes the key **only**; mapping a cookie to a
user is the factory's closure, not the registry's business.

✅ **Constraint 1's cost did not land.** The pages stayed **sync**. `app.storage.browser`
reads the request cookie and needs no socket connection — only `app.storage.tab` does, and
tier 2 does not use it.

Routes: `/login`, `/` (character index), `/builder`, `/gm`.

### 5.1a The entry point, as shipped 2026-09-11

`exalted_builder/server/main.py` exists. **It is §5.1's first piece only — the switch
that makes §3 reachable. There is no auth and no DB.**

* `build_server(session_root=None)` loads the ruleset, builds a prototype context and
  calls `register_pages(..., session_root=root)`. With no argument it reads
  `config.session_root()`, which raises when the environment gives none.
* `main()` reads both variables, makes the root, and runs `ui.run(reload=False)`.
* The split exists so a test can assert on the wiring. `ui.run` is not testable and the
  one argument this file adds is.

⚠ **`storage_secret()` does NOT raise, and §3.7b's handoff said it did.** It returns a
random per-process key, which is correct for the desktop. A server that takes it
invalidates every session cookie at each restart, so every browser gets a new session
id, a new session directory, and no view of the character the auto-save timer wrote for
it. **`config.required_storage_secret()` is the hosted accessor and it raises.** The
desktop accessor is unchanged.

⚠ **`DEFAULT_HOST` is `127.0.0.1`, which departs from §5.1's `0.0.0.0` sketch.** That
sketch assumes the auth gate, and the auth gate is not built. `check_bind_is_allowed`
raises on a non-loopback bind unless `--public` is passed. **Delete that function when
auth lands, not before** — it is the mechanism standing in for the gate.

⚠ **The prototype path is deliberately OUTSIDE the session root.** It is a marker: a
prototype path appearing inside a session directory shows the factory returned the
prototype's own path, which is §3.7's defect. A prototype inside the root would make
every `is_relative_to(root)` assertion pass with no isolation at all.

`tests/test_server_main.py` is the discriminator. ⚠ Its subject is *"the entry point
passes a root"*, not *"the factory isolates"* — `test_session_context_factory.py` and
`test_session_destinations.py` both stay green with this file deleted.

### 5.1b Server-side Save, as shipped 2026-09-11 (piece 2)

`builder.save()` branches **three** ways. The `hosted` bit selects the first:

| Deployment | Behaviour |
|---|---|
| hosted | write `ctx["path"]`, no dialog, `"Saved <name>"` *(new)* |
| native window | the OS "Save As" dialog *(unchanged)* |
| plain browser | filename prompt, then a download *(unchanged)* |

⚠ **This is NOT the `--save-dir` / `EXALTED_SAVE_DIR` design of
`hosting-per-instance.md`.** That one read a module-level `_SERVER_SAVE_DIR`, and its own
note says it was safe **only because the deployment was one player per process**. The §3
registry ended that. The destination here is `ctx["path"]`, which the session owns.

⚠ **`build_app`'s `auto_save` parameter is RENAMED to `hosted`,** because it now selects
three behaviours: the auto-save timer, server-side Save, and (via `register_pages`, which
passes `hosted=session_root is not None`) the isolated destination. **Do not split it
back into two parameters.** They could then disagree, which is a Save writing
server-side to a destination every session shares — §3.7's hazard on a button.
`tests/test_hosted_save.py` asserts no `auto_save` parameter exists.

🐞 **There were TWO save sites, and every document said one.** `gm.save_party()` carried
the identical two-way branch, and **`/gm` is a hosted route** — so a hosted Storyteller
clicking *"Save party"* got a download and the server kept no roster. Fixing only
`builder.save()` would have closed the trap in four documents and left the same failure
one page over: **the house bug, type 1.**

It was found by grepping `_native_window` across `ui/`, **not** by reading the plan, which
named `builder.save()` and nothing else. ⚠ `build_gm` now takes the same `hosted` bit and
`register_pages` passes it to both routes. The discriminator is
`test_hosted_party_save_writes_the_file`; the negative control is registering `/gm`
*without* the bit, which is the defect exactly.

⚠ **The other four `_native_window` sites in `gm.py` are correct as they are** — the party
PDF export, the party load, the character browse, and the add-to-party dialog shape. They
are downloads and uploads, which is what a hosted run wants. **Do not convert them.**

⚠ **The PDF export deliberately keeps TWO branches.** A character file is state the server
owns; a sheet is an artefact the player keeps. A hosted export downloads, and that
asymmetry is correct — do not "restore parity".

### 5.1c "Download a copy" — RULED 2026-09-11, BUILT 2026-09-11

Piece 2 left a hosted player with **no way to get their character JSON out**: Save writes
server-side and the download branch became unreachable. **Human's ruling, 2026-09-11:
*"They should have a way to download a copy."*** Scoped below, then built the same day —
see **"What shipped"** at the end of this section. The scope is kept as written because
the tests are built on it.

**This is wiring, not a new mechanism.** Every part already exists and works on a hosted
run — the PDF export downloads from a hosted page today, so `ui.download.content` is
proven on that path.

⚠ **"Save writes to the DB" is the intended END state, not the current one.** There is no
database. A hosted Save writes a JSON file to `<session_root>/<session-key>/<name>.character.json`;
the DB is piece 4 and is unbuilt. **This row does not depend on which of the two it is** —
Save goes through one call site, piece 4 changes that call site, and Download never reads
it. Build this before the DB without waiting.

⚠ **The pieces are present but UNREACHABLE, which reads exactly like present and working.**
A reader of `builder.py` sees `_open_browser_save_dialog` and `_browser_download` and
concludes that a browser gets a download. **A hosted browser does not** — `save()` returns
before them. Same for `gm.py`'s `_open_browser_party_save` and `_party_download`. Do not
assume these are live because they are there.

#### ⚠ The trap, and it is the whole reason this row needs care

**A download must NOT repoint the session's save destination.** Both existing helpers do
exactly that today:

* `builder._browser_download` sets `ctx["path"] = ctx["dir"] / filename`
* `gm._party_download` sets `ctx["party_path"] = ctx["dir"] / filename`

That is correct for the desktop, where the download *is* the save. **On a hosted run it
would move where the auto-save timer writes**, to a name the player typed into a download
box — silently, on a 5-second timer, with the old file left behind. ⚠ **Reuse those two
helpers unchanged and you ship that.** The hosted download must be read-only with respect
to `ctx`.

#### Two sites, not one

⚠ **The character AND the party.** Piece 2's own finding was that every document described
the save trap in the singular and there were two sites. **Do not repeat it here.** A
hosted player needs the character file; a hosted Storyteller needs the party bundle.

#### Shape — RULED 2026-09-11: hosted only

A **"Download a copy"** button beside Save, **rendered only when `hosted` is true**, on
both surfaces. Human's ruling: *"hosted only, yes."*

Reasons it is not always-present: on the desktop in a plain browser **Save already IS the
download dialog**, so a second button would duplicate it there; and Save now means *save
to the server*, which should keep meaning one thing.

⚠ **The button is gated on the SAME `hosted` bit** that selects the save branch, the
auto-save timer and the isolated destination. Do not introduce a fourth switch. A Download
button visible without a hosted save behind it is a Save/Download pair where both
download, which is the confusion this row exists to remove.

⚠ **The desktop is untouched by this row.** Not a parity port — see
`feedback_qt_and_webapp_are_separate_design_surfaces`. A test should assert the button is
**absent** on a non-hosted build, or nothing stops it appearing there later.

#### What the tests must say

⚠ **Assert on `ctx`, not only on the download.** The discriminator for the trap above is
that `ctx["path"]` (and `ctx["party_path"]`) are **unchanged** after a download, and that
no second file appears in the session directory. A test that only asserts a download
happened passes with the destination-repointing bug fully present.

Plus the gate itself: the button is **present hosted and absent not-hosted**. Both
directions — an absence assertion alone is satisfied by a button that never renders at
all, which would pass against a row that was never built.

⚠ **`should_not_see` cannot carry the absence assertion on its own.** It returns on the
first attempt at which the text is missing, so after a click it races the async handler.
Settle on something the branch produces first. This cost a green-against-the-defect case
in piece 2 — see `feedback_should_not_see_races_async_handlers`.

#### Cost, in this project's terms

**The smallest row left**, and smaller than piece 2: that one invented the three-way branch
and renamed a parameter tree-wide, whereas this one adds a button in front of helpers that
already exist. Roughly ~15 lines across `ui/builder.py` and `ui/gm.py`, 4–6 tests, no new
mechanism, no new dependency, no engine or data change. ⚠ **The real cost is one full suite
run**, as for any row. The only thing that can make it expensive is the `ctx` trap above.

#### What shipped

Both sites, gated on the one `hosted` bit, both helpers split so the trap cannot be reached
from the hosted button:

* **`builder._download_copy(filename)`** sends the character and touches nothing in `ctx`.
  `_browser_download` now calls it and **then** sets `ctx["path"]` itself, with a ⚠ comment
  that the line is desktop-only. The hosted **"Download a copy"** button (mark
  `top-bar-download`) calls `_download_copy` directly.
* **`gm._party_download_copy(filename)`** — the same split for the party. Button mark
  `gm-download-party`, beside Save party.
* **No filename prompt.** The hosted button downloads straight away under
  `suggested_filename` / `suggested_party_filename`. ⚠ A choice made without asking: a
  prompt would be a second place a typed name could leak into `ctx`, and the browser can
  rename the file anyway. Reversible if a prompt is wanted.

`tests/test_hosted_save.py` gained six cases (13 in the file), and `_hosted_save_main.py`
gained a `/desktop-gm` control route — the absent-when-not-hosted direction for the party
page had no route to run on.

⚠ **The character trap case edits the name first**, and asserts the fixture can see a
repoint before it clicks. Without the edit, the desktop helper's repoint writes the SAME
filename that is already in `ctx["path"]`, and the case passes against the trap.

**Negative controls, all run, restored from a copy:**

* `_download_copy` sets `ctx["path"]` → only the character trap case reddens.
* `_party_download_copy` sets `ctx["party_path"]` → only the party trap case reddens.
* Both gates forced open → the desktop-absence case reddens.
* **The party gate alone forced open** → the same case reddens on `gm-download-party`.
  Run separately because the case checks the builder first, so the both-at-once control
  never reached the party half.

**Browser-verified by the human, 2026-09-11**, on a local hosted server with two browsers.

### 5.1d Auth — piece 3, BUILT 2026-09-11

**Rulings (human, 2026-09-11), asked before the first line:**

| Question | Ruling |
|---|---|
| How do accounts get made? | **Self-signup page.** (Recommended was admin CLI only; declined.) |
| Where do accounts live before piece 4? | **SQLite `users` table now**, in the file piece 4 adds `characters` to. |
| Is the context and save folder keyed to the user or the browser? | **The user.** Two devices of one account see one character. |

**Second round of rulings, the same day, on the known limits of the first build:**

| Question | Ruling |
|---|---|
| Forgotten passwords | **Manual.** The player emails the admin address (the human is making `admin@x6568tank.com`); the operator runs `server/users.py reset`. No reset by email, no email column. |
| Rate limiting | **Yes — per username.** Not per IP: behind the tunnel every request has the tunnel's address. |
| Disk per account | **10 MB.** *"Characters are in the singular kilobytes."* |
| Username case | **Case-sensitive.** Reverses the `COLLATE NOCASE` the first build chose. |
| Password rules | **8 characters, no complexity rule.** (The 72-byte maximum stays; it is bcrypt's, not a rule.) |
| `Secure` cookie, session fixation, `.nicegui/` location | **Asked to explain, not ruled.** Explanations given; see the limits below. |

**Third round, the same day:**

| Question | Ruling |
|---|---|
| `Secure` cookie | **On.** |
| Session fixation | The human runs **other `x6568tank.com` subdomains** (Jellyfin, Calibre, Seafile, Filebrowser) — the condition under which the fixation risk is real. Closed by the cookie name, below. |
| `.nicegui/` | **Understood** — a deploy concern, no code. |

**What shipped (third round):** `server/main.SESSION_COOKIE`, passed to `ui.run` as
`session_middleware_kwargs`: name **`__Host-exalted-session`**, `https_only=True`, path
`/`, no domain. Checked on a live server: `set-cookie: __Host-exalted-session=…; path=/;
Max-Age=1209600; httponly; samesite=lax; secure`.

⚠ **The `__Host-` prefix is the fixation fix, not decoration.** Browsers refuse a
`__Host-` cookie that is not Secure, not path `/`, or that carries a `Domain` — so a
sibling subdomain can neither plant a session id before login nor overwrite one after.
That was the only realistic planting route. **Do not add a `domain`, and do not rename
the cookie without the prefix**; `test_the_session_cookie_is_secure_and_host_only`
guards both. Rotating the id at login would still close the physical-access case; it
stays deferred as defence in depth.

**What shipped:**

* `server/db.py` — `init_db` (WAL + busy timeout), `create_user`, `authenticate`,
  `username_for`, `set_password`, `list_users`. Usernames 3–32 of `[A-Za-z0-9_.-]`,
  unique and **case-sensitive**; passwords
  8 chars to **72 bytes** (bcrypt's limit — bcrypt 5 raises past it, and a longer one
  would share a hash with its prefix). An unknown name still costs a bcrypt compare.
  bcrypt is imported at the call, so nothing else needs the extra.
* `server/auth.py` — `AuthGate` middleware, `/login`, `/signup`, `/logout`,
  `current_user_key()` → `"user-<id>"`, `safe_target()` for `redirect_to`.
* `register_pages(..., key=)` — the registry key function. Default is still the browser
  key (desktop and the older hosted harnesses); `build_server` passes
  `auth.current_user_key`. Folder: `<root>/user-<id>/`.
* `server/main.py` — `EXALTED_DB_PATH` required (no default, `config.db_path()`), the
  gate installed **before** `ui.run`. **`check_bind_is_allowed` and `--public` are
  deleted**, as §5.1a said. `DEFAULT_HOST` stays loopback; a network deploy passes
  `--host`.
* A hosted-only **Log out** button on `/` and `/gm`, on the same `hosted` bit as the
  download buttons.
* `[server]` extra: `nicegui`, `reportlab`, `bcrypt`.
* **Second round:**
  * `server/throttle.py` — `LoginThrottle`, in memory, by exact username. 5 free
    failures; the fifth sets a 30 s wait that doubles per further failure to 15 min; a
    success clears the name; a name idle 1 h is forgotten; the table is bounded (10,000
    names). ⚠ **An attempt counts as a failure when it STARTS** (`begin`), and a success
    clears it — a count that waited for bcrypt would let parallel attempts all pass the
    check. A refused attempt does not extend the wait.
  * `server/quota.py` — `FolderQuota`, 10 MB per `<root>/user-<id>/`, installed by `main`
    through a new **`persistence.set_write_guard`** hook that `atomic_write` runs before
    each write. Every hosted write (Save, auto-save, tab save, Save party) goes through
    `atomic_write`, so the one hook covers every site, and any new site. Replacing a file
    frees its old size. Paths outside the root are not checked. The refusal reaches the
    player through the existing `Save failed:` toast and the auto-save's `on_error`.
  * `server/users.py` — `python -m exalted_builder.server.users list | reset <name>`.
    `reset` asks twice with no echo. It refuses to run on a DB path that does not exist
    rather than make an empty store.
  * `EXALTED_ADMIN_CONTACT` (optional) → *"Forgot your password? Email …"* on `/login`.

⚠ **The gate is a middleware, not a `require_auth()` in each page body** — a departure
from the §5.1 sketch. A per-page call leaves open every route that forgets it, and nothing
reddens. The middleware covers every route by default, FastAPI's `/docs` and
`/openapi.json` included (checked on a live server). `OPEN_PATHS` is the list of exceptions.

⚠ **Two layers, on purpose.** `current_user_key()` raises with no login, so a route the
gate somehow missed returns a 500 instead of quietly serving the browser-keyed context.

⚠ **`main` installs the gate and the quota, not `build_server`.** Starlette refuses
`add_middleware` once the app has started, and the unit tests call `build_server` in a
process where a User-harness test already started it. `test_server_main.py` asserts `main`
calls `install_gate`, then `set_write_guard(FolderQuota(root))`, then `ui.run`, in that
order — `ui.run` puts the session middleware *outside* the gate only if the gate is there
first.

**Tests:** `test_user_db.py` (25), `test_auth_gate.py` (27, production wiring through
`tests/_auth_main.py`), `test_login_throttle.py` (11), `test_folder_quota.py` (12),
`test_users_cli.py` (6), `test_server_main.py` rewritten for the gate and the quota. The route case
**enumerates `Client.page_routes`** rather than naming pages, with a guard that the
enumeration found `/` and `/gm`.

**Negative controls, all run, restored from copies — each went red:**

1. Gate not installed in the harness → 5 failed, 5 errors (the errors are the 500s of
   the second layer).
2. `build_server` without `key=` → the two account-key cases.
3. `/gm` added to `OPEN_PATHS` → the route enumeration.
4. `safe_target` without the `//` check → its parametrised case.
5. `main` without `install_gate()` → the order case.
6. The login page not calling `throttle.begin` → the page rate-limit case (the class's
   own 11 cases stay green, which is the point of the page case).
7. `main` without `set_write_guard` → the order case.
8. The harness without the guard → the full-folder Save case.
9. `set_password` without its `WHERE` → `test_a_reset_touches_one_account`.
10. The throttle's prune able to remove the name it just added → a case written for it.

#### 🐞 Found on the way, second round

* **The throttle was off by one.** The first draft blocked on the sixth failure, so a
  sixth attempt got through and only the seventh waited. Five tests red; fixed.
* **The prune could delete the record it just inserted.** A new record started with
  `last_failure = 0.0`, the oldest possible, so a full table pruned the new name and the
  failures were counted on an orphan — that name was never limited. The bound test
  checked only the table's length and stayed green. Fixed with `protect=`; the new case
  went red against the old code.
* **A test race, not a code bug, worth knowing:** `submit` reads the password field when
  its task RUNS. A loop that settles on *"Wrong username or password."* settles
  instantly after the first failure (the text stays), so the queued "wrong" attempts ran
  after the test had typed the correct password — and logged in. The loop now waits for
  the field to be cleared.

#### Known limits — not solved, recorded so nobody assumes they are

* **The session id does not change at login.** Since the third round the `__Host-`
  cookie stops a sibling subdomain from planting one, which was the realistic route. What
  remains is someone with physical access to the browser before login. Rotation would
  need a plain HTTP login route (NiceGUI's login runs over the websocket, which cannot set
  a cookie). Deferred as defence in depth.
* **The cookie is Secure, so it is not stored over plain HTTP to a LAN address.** Local
  testing works on `http://localhost` (browsers exempt it); a player on the LAN at
  `http://192.168.x.x` cannot log in. Use the HTTPS hostname.
* **A login lasts 14 days after the last visit** — Starlette's default `max_age`,
  refreshed on each response.
* **The login state lives in `.nicegui/storage-user-*.json` in the server's working
  directory**, one small file per browser that ever visited, bots included, never
  pruned. A deploy that discards that directory logs everyone out; no character is lost.
  **Understood by the human 2026-09-11; minor.** Deploy guidance: start the server
  from, or mount, a directory on the data volume.
* **A password reset does not end the logins that exist.** A browser that is logged in
  stays logged in. Matters only for a stolen password, not a forgotten one.
* **The rate limit is per username only** (the ruling). Someone can keep a friend's name
  in cooldown by guessing — at most 15 minutes at a time. It is in memory, so a restart
  clears it.
* **Signup is not rate-limited and the account count is not capped.** The quota bounds
  each account's disk, not the number of accounts.
* **No account delete, and no password change by the player.**
* **The homebrew library is outside the quota** — it is one process-wide library
  (§5.3, piece 4), and a loaded save still writes its homebrew into it.
* **Two devices of one account share one live `Character`.** Saves are consistent; the
  view that did not make an edit is stale until it reloads. This is the ruling's cost.

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

**Remaining after 2026-09-11**, in the order they were severed:

| Piece | State |
|---|---|
| 1. `server/main.py` — the switch | ✅ done, §5.1a |
| 2. the third save branch (both sites) | ✅ done, §5.1b |
| 2b. "Download a copy" on a hosted run | ✅ done, §5.1c — browser-verified |
| 3. Auth — `/login`, the gate, `bcrypt`, the `[server]` extra | ✅ done, §5.1d — not browser-verified |
| 4. The DB, and §5.3's per-user rulesets | ❌ not started; **measure one merged `RuleSet` before fixing the layout** |

⚠ Piece 1 shipped **without** piece 2, so a hosted run now persists edits by timer while
the Save button still downloads to the browser. That is a better failure than losing the
edits and it is still a failure.

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
