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

#### Still true, still not addressed by this row

⚠ **`builder.save()`'s two-way branch is untouched.** A hosted manual Save still shows a
green *"Downloading …"* toast. Auto-save does not go through it — it writes server-side —
so the hosted story is now "your edits persist, but the Save button still lies."

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
| 2. `builder.save()`'s third branch | ❌ still the trap in `vtt.md` §5 |
| 3. Auth — `/login`, the gate, `bcrypt`, the `[server]` extra | ❌ not started |
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
