# The VTT: a hosted table with a dumb board

**Status: NOT RULED.** This is a costed plan and a draft decision, written 2026-09-11 at
the human's request. Nothing here is authority to build. Section 8 lists what needs his
ruling before the first line of code.

**What this document decides:** the phasing, the repository/package shape, and the cost of
the spatial surface — which was the question that was blocking the choice.

**What it does not decide:** whether to build it. Auth details, the DB schema and the
Docker/tunnel work are unchanged from `exaltedcharsheethostingplan.md` and
`hosting-state-model.md`, and are not restated.

**Read first:** `hosting-state-model.md` (the session refactor — §3 is the risky part),
`hosting-per-instance.md` (the declined alternative, kept for two findings that outlive
it), and decision `0019` (the no-wire rule, which §4 below copies in shape).

---

## 0. The finding that shapes the whole plan

The human's question was *"how hard would a basic whiteboard/spatial surface be?"*, with the
scope choice riding on the answer — table-only if hard, table-plus-board if not.

**The board is cheap. The substrate under it is expensive, and the table-only option needs
that same substrate.** So the two options are not a fork. Option 2 is option 1 plus roughly
a week, bolted on afterwards, and **the choice can be deferred at no cost.**

Three things make the board cheap, and all three were verified in the tree on 2026-09-11
rather than recalled:

1. **The custom-canvas bridge already exists and ships.** `ui/vendor/cytoscape.min.js`
   (373 KB) is inlined into a page by `ui/assets.py:19`, driven from Python by
   `ui.run_javascript` (`ui/picker.py:1813`), and it sends interaction back —
   `emitEvent('charm_select', {id: e.target.id()})` (`ui/picker.py:1842`) caught by
   `ui.on("charm_select", ...)` (`ui/builder.py:150`). A whiteboard is that identical round
   trip with a different vendored library and drag events instead of taps.
   ⚠ **This is the single most important fact in this document.** "Can this stack drive a
   custom canvas?" is not a risk to be spiked — it is answered, in shipped code, with a
   vendoring convention and a no-CDN rule already established.
2. **The broadcast primitive exists.** `nicegui.Client.instances` is a `dict` of live
   clients and `Client.run_javascript` is a per-client method (verified against the
   installed **NiceGUI 3.14.0**). Fan-out is iterating a subscriber set and calling that.
   `on_connect` / `on_disconnect` / `has_socket_connection` are on the same class, which is
   the subscription lifecycle.
3. **The engine does not have to learn anything.** `engine/` (15,515 lines) and `models/`
   (4,512 lines) import nothing from `ui/`, `qt/` or NiceGUI — checked, and the only grep
   hit is a comment in `engine/labels.py`. The board is not an engine feature and must not
   become one (§4).

### What would make it expensive, and the rule that prevents it

Live 60 fps co-presence: remote cursors, per-`mousemove` token positions, streaming
freehand points. That is a different engineering problem — interpolation, jitter buffers,
conflict resolution on a continuously-moving object.

**The rule: broadcast commitments, not motion.** A stroke goes out when the pen lifts. A
token goes out when it is dropped, or throttled to ~20 Hz if dragging must be visible.
No presence cursors in v1. That is the difference between one week and one month, and it
is a product decision made once, up front, not a performance problem discovered later.

---

## 1. Repository and package shape

The human's instinct — *"the whole hosting part of this should probably be its own repo"* —
is right, with one correction to how.

### 1.1 A package split, not a fork

```
exalted-engine          (new package: engine/ + models/ + data/ + rules_db + persistence)
   ├── exalted-builder-qt      (PySide6 native app — existing)
   ├── exalted-builder-web     (NiceGUI desktop app — existing)
   └── exalted-table           (NEW repo: the hosted server + the board)
```

The split is viable today: the engine is already toolkit-free by decision `0002`, and §0.3
confirms it. This is packaging work, not a refactor of logic.

⚠ **`0019`'s drift warning now applies to THREE shells, not two.** Its wording — *"A
feature that lands in one is how the two products drift"* — was written when there were
two. A third consumer does not make drift worse linearly; it makes "which shells did this
land in?" a question nobody can answer from memory. **Whatever mechanism is chosen for
that, choose it when the split happens, not after the first divergence.**

⚠ **The engine package cannot be public.** `data/` carries the transcribed rulebook prose
that keeps this repo private (`hosting-per-instance.md` records ~1.8 M characters, ~361
pages). If `exalted-table` is a public repo, its dependency on `exalted-engine` must be a
private one — a git+ssh requirement or a private index. **The repo-private /
service-public split is coherent and costs nothing to keep**; it just has to be deliberate
rather than discovered at first `pip install`.

### 1.2 What is NOT a rewrite

The human raised *"a rewrite of the engine might do good."* Against it:

- `engine/` + `models/` is ~20 k lines under ~3,390 tests, pure and dependency-free. It is
  the only part of this codebase that is demonstrated rather than believed.
- `hosting-state-model.md` §3.6 already establishes that `engine/`, `models/`, `ui/view.py`,
  `custom_content.py` and `rules_db.py` do **not** change for hosting, and §3.3 shows why:
  no tab module touches `ctx` at all.

**What genuinely needs rewriting is the `ctx` layer, and only that** — two modules, seven
keys, one process-global `Character` handed to every connection. That is §3 of
`hosting-state-model.md` and it is already scoped. **Extract, do not rewrite.**

### 1.3 The Table is a first-class entity — and it is what questions 2 and 4 both asked for

The human's rulings of 2026-09-11 on homebrew scope (Q2) and the GM page (Q4) arrived
separately and converge on one structure. Recording that convergence, because neither answer
implies it on its own:

> **Q2:** *"Could we have two ways to attach homebrew? Think of it like game modding — a
> table could have its own homebrew Charms/MA/Spells/Whatever, which characters have access
> to when they join, or a character can be made with homebrew charms stored on it."*
>
> **Q4:** *"It'd have to be an entirely new thing, linking to player characters. Honestly,
> given how most VTTs work, the GM page is probably gonna end up an artifact of the app's
> current only-offline existence — by default in a VTT, anyone can see anyone else."*

A table-scoped rules layer and a shared-by-default view are both properties of a **Table**,
which today does not exist as an entity. The `Party` is its offline stand-in. **Make `Table`
first-class in the DB layout rather than growing it out of `Party`**, and both answers fall
out of one design.

Supporting evidence that this is the existing grain, not a new idea: `HouseRules` already
carries every Storyteller switch, and `CLAUDE.md` §13 already requires each field to be
marked **TABLE-WIDE** or **PER-CHARACTER**. That distinction was written for an offline app
and it is exactly a table/character scope split. **It was already the right shape.**

#### Homebrew: three layers, and two of them already exist

⚠ **Q2 is not two new mechanisms. It is one new scope plus something 0012 shipped in
2026-07-29.** Verified in the tree 2026-09-11:

| Layer | Status | Mechanism |
|---|---|---|
| **Book data** | exists | `data/`, merged first |
| **Table** ("the mod") | **NEW** — the only thing to build | a `custom_dir` owned by the table |
| **Character** ("stored on it") | **exists** | 0012's carried copies: a save embeds the definitions it references plus their prerequisite closure |

And the precedence rules already exist and already compose, from
[0012](../decisions/0012-homebrew-library-plus-carried-copies.md) and verified in
`custom_content.py:505`:

* **The book wins an id collision**, and authored ids are forced to a `custom.` prefix — so
  homebrew can never shadow printed content, by construction.
* **The library wins an absorb conflict** — *"opening a character never silently rewrites
  the recipient's own version of a Charm"* (`custom_content.py:508`). Applied at table
  scope, that reads: **a joining character never overwrites the table's mod.** That is the
  behaviour you want, already implemented, for free.
* **Homebrew errors are never fatal** and are reported on `RuleSet.custom_problems`. On a
  server this matters more, not less: one player's bad row must not stop the table.

The plumbing is a path change, as `hosting-state-model.md` §5.3 says — `absorb_definitions`
already takes `custom_dir=`, and `custom_content.py` is stateless.

⚠ **The one real hazard, and it is the good version of an old bug.** `load_party()` already
absorbs *every member's* homebrew into one library (`persistence.py:236-239`). Offline that
is correct. Pointed at a table's `custom_dir` it becomes **exactly the "table mod" Q2 asks
for — and also an unprompted write path by which any joining player injects Charms into
everyone's game.** The same call is the feature and the hazard; only who authorised it
differs.

**So absorbing into the table layer must be an explicit Storyteller action, not a
side effect of a character joining.** The hook already exists: `load_character` and
`load_party` both take `absorb_custom=False`, and `absorb_definitions` *"returns the ids it
added"* precisely so a caller can tell the user what was imported (`persistence.py:168`).
**On a table, the default flips: `absorb_custom=False`, and the ST approves the diff.**

⚠ This is `hosting-state-model.md` §5.3's cross-contamination hazard, which is normally
described as a thing to *prevent*. Q2 makes the same write path a **feature** at table scope.
The distinction is consent, and nothing in the code expresses it today.

#### The GM page dissolves

Q4 replaces, rather than defers, open question 4. The consequence for phasing:

* There is no "GM page ships or does not ship in v1". **The table view is the main view**,
  visible to everyone, and it is P3.
* A small **ST-only surface survives** and must not be lost in the dissolve: the adversary
  roster, and the TABLE-WIDE `HouseRules` switches (`CLAUDE.md` §13 — *"A control that
  applies a value to all characters can change TABLE-WIDE fields only"*). Those need a
  Storyteller gate; the rest does not.
* ⚠ **Visible-by-default is a ruling about the UI, not a licence to drop authorisation.**
  "Anyone can see anyone else" must still be enforced as *members of this table*, server
  side. A hosted app where the check lives in the view is one URL away from being public —
  and per `hosting-per-instance.md`, an un-gated hostname is *"the character, the homebrew
  library and the ST screen open to whoever finds the name."*
* ⚠ **`Adversary` is not a `Character`** and a test asserts it (`CLAUDE.md` §13). The table
  view shows both. Do not let a shared roster be the thing that finally merges them.

---

## 2. Phasing

Each phase has a gate. A gate is a thing that must be observed, not a thing that must be
believed.

### P0 — The isolation test, written first and confirmed RED — ✅ DONE 2026-09-11

`hosting-state-model.md` §3.8, unchanged. Two sessions, one edit, assert the second does
not see it; then the same across the `/gm` → `/` navigation, which is the phase most
likely to leak.

⚠ **This is worth writing even if hosting never happens.** It documents a real property of
the current build, and `hosting-per-instance.md` closes by saying so: declining
per-instance left the defect exactly where it was.

**Gate: the test fails on today's tree.** A green run means the harness shares a client,
not that the app is isolated — and per the house-bug rule, a rule that passes in the phase
you tested is the project's signature defect.

#### What was built, 2026-09-11

Three files, and one production line changed:

* `tests/test_session_isolation.py` — the control plus the two phase tests.
* `tests/_isolation_main.py` — a main file using **production wiring**: it calls the real
  `builder.register_pages(RS, ctx)`. ⚠ It must not import `tests/_ui_main.py`, whose
  module-level characters are themselves shared and would make the test report sharing the
  app did not cause.
* `tests/_isolation_names.py` — the three names both files use. It exists because
  `_isolation_main.py` registers routes on import, so the test module must not import it.
* `ui/gm.py` — the "Builder" button gained `.mark(f"open-in-builder-{index}")`, following
  the `mark("batch-roll")` convention already on that page.

**Observed:** control passes, both phase tests fail with the leaked value —
`Session B opened '/' and found 'AliceEditedThis'` and `…found 'PartyGuest'`. The defect in
`hosting-state-model.md` §3.1 is now demonstrated rather than reasoned about.

⚠ **They carry `xfail(strict=True)`, so the suite stays green** and the handoff's
*"a red run is a real one"* invariant survives. **`strict` is load-bearing:** when the
refactor fixes the defect, pytest reports XPASS and **fails** the run, forcing whoever did
it to delete the marker. A non-strict xfail would go quietly green and nothing would ever
report the work as done.

#### ⚠ The trap this phase hit, and it is the reason the phase exists

**The first version of the `/gm` test PASSED, and it was wrong.** It clicked the button and
asserted `should_see(MEMBER_NAME)` — but **the `/gm` card prints the member's name**, so the
assertion matched whether or not the navigation happened. A test of the leakiest phase in
the plan was green while proving nothing.

Two separate causes, both worth keeping:

1. **`find("Builder")` matched TWO buttons.** `find(...).elements` is an unordered set, so
   the click was ambiguous. Hence the marker.
2. **The assertion was satisfied by the page it started on.** The fix is to assert on
   something only the *destination* can show — the builder's own Name field — and to assert
   **mid-test** that session A actually arrived, so the final assertion cannot pass
   vacuously.

**Generalisation: when a test navigates, assert on a value the origin page cannot produce.**
Same family as `a compensation is a hypothesis` and `serve-and-grep is not verification`.

### P1 — The package split — ⚠ RE-SCOPED 2026-09-11, because it was already done

Carve `exalted-engine` out, leave both existing shells building and green. No behaviour
changes.

**Gate: the full suite green from the split packages, and both shells launch.**

#### ⚠ The measurement that changed this phase

**The split's goal is already met by the existing packaging, and carving the package out
would buy nothing while touching 491 import sites.** Measured 2026-09-11, before any edit:

| | Count |
|---|---|
| Absolute imports a rename would rewrite — `tests/` | **456** |
| Absolute imports a rename would rewrite — `ui/` + `qt/` | **34** |
| Absolute imports a rename would rewrite — `pack/` + `tools/` | **1** |
| Relative imports inside the subset, which survive a rename untouched | 170 |

**And the reason it buys nothing:** `pyproject.toml` already declares **`pydantic` as the
only hard dependency**. `nicegui` and `PySide6` live in the optional `[ui]` and `[qt]`
extras. So a third consumer can already `pip install exalted-builder`, import
`exalted_builder.engine`, and never pull in a toolkit.

**Proved, not assumed** — a wheel built and installed into a clean venv with no extras:

```
charms 1921 | spells 306
nicegui imported: False
PySide6 imported: False
```

⚠ **This is the third time this project has found a carried plan item already done.** The
handoff's own section — *"Two carried items, re-measured — one shrank, two died"* — is the
pattern, and the cause is the same: **the item was written from a census that nothing
re-ran.** P1 was written on 2026-09-11 from `hosting-per-instance.md`'s comparison table,
not from the installed metadata.

#### What P1 became

1. **`tests/test_engine_seam.py`** — the boundary is now enforced instead of merely true.
   It parses the **syntax tree** of all 47 engine-side files and fails on any import of
   `nicegui`, `PySide6`, `reportlab`, `ui` or `qt`.
   ⚠ It reads the AST rather than the text, because two engine modules contain the words
   *"imports no `nicegui`"* in a comment and a text search reports them.
   ⚠ It reads **source files rather than imported modules**, so it catches an import inside
   a function body — negative-controlled with both shapes, and the lazy one
   (`engine/labels.py:46 imports 'ui'`) is the one an import-based check cannot see.
2. **The physical split is DEFERRED until `exalted-table` exists**, at which point the
   decision is informed by a real consumer rather than by a guess. Nothing blocks P2.

⚠ **The deferral is not a reversal of §1.1.** The three-product structure and the
private-dependency rule still stand. What is deferred is the *file move*, which is
reversible; the boundary it was meant to protect is now under test, which is the part that
rots silently.

#### 🐞 A real defect, found by building the wheel — FIXED

**The thaumaturgy rules data did not ship.** `package-data` listed `data/*.json` and
`data/charms/*.json` **by name**. `data/thaumaturgy/` was added later and nobody added it
here, so the wheel carried **189 of the 193 data files** and **zero** of the four
thaumaturgy files: 4 arts, 4 sciences, 30 formulas, 11 rituals.

⚠ **Nothing reported it, and the reason is a deliberate correct decision one layer over.**
`rules_db.py:790` treats every thaumaturgy file as optional — *"a data set without them
simply has no thaumaturgy"* — which is right for a data set that genuinely has none, and is
exactly what makes a packaging omission invisible. `load_ruleset` returned success with the
directory absent. **A ruled absence and a lost file are the same bytes.** That is
attunement-by-absence again, in the build.

Thaumaturgy is on **all** sheets (`CLAUDE.md` §13), so the loss is not small.

**Scope, stated precisely:** the four shipped release assets were **not** affected —
`pack/*.spec` copies the whole `data` directory recursively. Only `pip install` of the
wheel or sdist was. ⚠ **That is the deployment P2 uses**, which is why this surfaced now
and not at a release.

**Fixed:** the glob is now recursive, `data/**/*.json`. Verified by rebuilding —
193 of 193, and the clean-venv install reports `thaum_arts 4 · thaum_sciences 4 ·
thaum_formulas 30 · thaum_rituals 11`, matching the dev tree.

**`tests/test_packaging.py`** expands the globs from `pyproject.toml` the way setuptools
does and fails when any data file is uncovered, so it catches **the next** new directory
rather than only this one. Negative-controlled against the old globs: it fails and names
all four files.

### P2 — The hosting substrate

`hosting-state-model.md` §3 and §5 as written: the two-tier session store, per-request
`ctx` resolution, `save_path` → `save_fn`, debounced auto-save, auth, the DB.

✅ **§3 IS COMPLETE as of 2026-09-11.** All five rows of §3.9 are done: the registry, the
isolation tests, per-request `ctx`, `save_fn`, and per-session destinations plus
write-through auto-save.

✅ **§5 pieces 1 and 2 are DONE (2026-09-11).** `exalted_builder/server/main.py` passes
`session_root` to `register_pages`, so **§3 is no longer dormant** (§5.1a), and
`builder.save()` now has its **third branch**, so a hosted Save writes server-side
(§5.1b). **Auth and the DB remain**, and `§5.5` carries the four severed pieces and their
state.

⚠ A hosted run needs **two** environment variables: `EXALTED_STORAGE_SECRET` and
`EXALTED_SESSION_ROOT`. **`config.required_storage_secret()` is the one that raises on the
first**, and it was added by piece 1 — ⚠ **`config.storage_secret()` does not raise**, it
returns a random per-process key, which a server must never take.

⚠ **There is no auth**, so `server/main.py` binds loopback and refuses a public bind
without `--public`. That guard is a stand-in for the gate; **delete it when auth lands.**

✅ **The 3.14.0 re-verification is DONE (2026-09-11).** `hosting-state-model.md` §3.4 now
carries the corrected table, the method, and the three new constraints. Summary: the table
had **two wrong cells** (`tab` is not serialized by default and *does* survive navigation;
`general` is serialized), **the two-tier design survives**, and the Redis question is
answered — `NICEGUI_REDIS_URL` is an import-time read that turns *every* store into a
serialized one, so it cannot hold the live registry and **does not** relieve the
single-process assumption. Read §3.4 before writing `server/session.py`; do not re-open
this.

**Gate: P0's test goes green, and the `/gm` → `/` handoff still opens the right character.**

### P3 — The Table: shared view, linked characters

Per §1.3 this is **the main view, not a GM page** — the roster holds links to the players'
real characters instead of owning its own entries, and everyone at the table can see it. The
ST-only remainder is the adversary roster and the TABLE-WIDE `HouseRules` switches.

This is also what `status/dice-roller.md` names as the hard precondition for **roll
initiative for the whole table**, which is currently BLOCKED on exactly this.

⚠ **Preserve `open_member`'s by-reference semantics** (`hosting-state-model.md` §3.6).
Copying instead of sharing silently breaks the party-card live update, and no test catches
it.

**Gate: initiative for the whole table, which is the first feature that pays for P2.**

### P4 — The board (optional, additive, deferrable)

Only now, and only if still wanted. Nothing above depends on it.

---

## 3. The board, costed

| Piece | Estimate | Basis |
|---|---|---|
| Canvas surface: background image, draggable labelled tokens, freehand strokes, erase, clear | 2–3 days | The `ui/picker.py` ↔ `ui/builder.py` bridge, re-pointed at a vendored Konva/Fabric |
| Board state + fan-out: authoritative object list, last-write-wins per object id, snapshot for late joiners, reconnect | 3–4 days | `Client.instances` + per-client `run_javascript`; **this is a hosting problem in a whiteboard costume** |
| Persistence: the board travels with the party bundle | ~1 day | |
| **Board total** | **~1–1.5 weeks** | |

Against the substrate's **10–12 days** (`hosting-per-instance.md`'s comparison table), the
board is roughly **15 % of the total, not a doubling.**

⚠ **These are estimates and they carry this project's own warning.** `hosting-per-instance.md`
sold itself at "~1 day" on the strength of "no code changes", and the build immediately
turned up a required code change and a silent file-ownership bug. **A plan whose selling
point is that a pattern already exists is worth re-checking the moment the first exception
appears.**

**Vendor the library, do not CDN it.** `ui/assets.py` establishes the convention and the
reason (offline, deterministic, no third-party fetch), and `pyproject.toml` already ships
`ui/vendor/*.js` as package data.

---

## 4. Decision 0020 — the board is dumb

✅ **RATIFIED 2026-09-11** (human: *"Go ahead"*). **The record is
`docs/decisions/0020-the-board-is-dumb.md` and it is the authority.** What follows is the
draft it was written from, kept because a plan that silently loses its own reasoning is how
the next session re-argues it. ⚠ **If the two disagree, the decision record wins.**

### The shape, and why it is the same shape as 0019

`0019` permits rolling **a number of dice** and forbids rolling **a roll**, because the gap
between the pool and the roll box is the safety mechanism. The board needs the identical
cut:

**The board may hold a PICTURE of the table. It may not hold a MODEL of the table.**

In scope:

* Background images, freehand strokes, shapes, erase, clear.
* Tokens: an image or a colour, plus a **free-text label the player or ST types**.
* Moving, resizing and deleting those objects. A shared, persisted board per party.

Out of scope, and this is what keeps `0008` and `0016` intact:

* **A token that knows it is a `Character`.** No link from a board object to a character
  id, no derived stats on a token, no health track on the board.
* **Distance, range bands, reach, movement rates, facing, cover, line of sight.** Any of
  these is combat derivation under `0008`, arriving by a side door.
* **Any rule keyed to position.** The board never answers "can I reach him".
* A grid with **enforced** movement. A decorative grid is a background image and is fine.

### ⚠ The load-bearing part

**The moment a token knows which character it is, the next ask is "how far can I move",
and that is `0008`. No test will fail when that line is crossed** — exactly as `0019`
records that binding a roll definition to a roll result *"re-creates the thing 0009 was
written to prevent, and no test will fail."*

The defence is the same one: **it goes on the click-through list**, and the discriminator
is structural — a board object carrying a character id, or an engine import in the board
module. That is a grep, and `CLAUDE.md` §13's Merit-id precedent (*"No module outside
`engine/merits.py` can name a Merit id. A test finds violations"*) is the working model for
enforcing it.

⚠ **The label must be free text, for 0019's reason exactly.** A label the app chose is the
app asserting the board is right. A label the player wrote is the player's claim.

---

## 5. Traps carried in from the existing documents

These are already recorded elsewhere and will bite this work specifically.

* ⚠ **`persistence.load_character()` WRITES to the custom library** via
  `absorb_definitions()` (`persistence.py:174`). On a shared `custom/` volume, one user
  opening a save injects their homebrew into everyone's. `hosting-state-model.md` §5.3 has
  the fix (per-user `custom_dir`, which is *cheaper* than shared). **This is latent today
  and becomes real the instant two people share a directory by any route.**
* ✅ **The two-way save branch — CLOSED 2026-09-11.** `tests/test_hosted_save.py` is the
  discriminator. ⚠ **The fix is not the `--save-dir` / `EXALTED_SAVE_DIR` one this list
  used to name** — that design hung on a module-level global, safe only under one player
  per process, which the §3 registry ended. The destination is `ctx["path"]` and the
  switch is `hosted=`, the same bit that isolates the destination and starts auto-save.
  🐞 ⚠ **This entry, and every other copy of it, said `builder.save()` — and there were
  TWO sites.** `gm.save_party()` had the identical branch and `/gm` is a hosted route.
  Both are fixed. **A trap described in the singular is worth grepping before you close
  it.**
* ⚠ **The 9th save site.** `hosting-state-model.md` §3.5 counts 8 for `ui/`; `qt/main_window.py:593`
  is the ninth. A `save_fn` refactor assuming 8 leaves it uncompiling.
* ⚠ **The stale server wears a healthy port.** From the handoff: `reload=False` means a
  `kill` on the wrapper PID leaves the listener answering 200 off the old build. Get the
  PID from `ss -ltnp | grep 8080`. **Cost two sessions.** A hosted, long-running process
  makes this worse, not better.
* ⚠ **The app reports no version anywhere.** Already unanswerable on the desktop; on a
  server with players connecting, *"is everyone on the same build?"* becomes a support
  question with no answer. Worth closing before hosting, not after.

---

## 6. Rejected alternatives

* **Rewrite the engine.** §1.2. Discards the only proven asset to solve a problem located
  in a different layer.
* **One container per player.** Declined 2026-08-28 as clunky; full record and the honest
  trade-off table in `hosting-per-instance.md`. It routes around the `ctx` defect rather
  than fixing it, and bills per player.
* **Build the board first, because it is the fun part.** It has no substrate to sync
  through; it would be a single-user drawing toy, and the sync layer — the expensive half —
  would be written twice.
* **Export to an existing VTT (Foundry/Roll20) instead.** Not costed here, and it is a
  genuinely different product: it keeps the app single-user and hands the table to someone
  else's software. Named so it is not silently forgotten; **not rejected on merit.**
* **Live co-presence (remote cursors, streaming motion) in v1.** §0. Moves the board from
  one week to roughly one month, for polish.

---

## 7. Effort summary

| Phase | Estimate |
|---|---|
| P0 — isolation test, confirmed red | 1 day |
| P1 — package split | 2–3 days |
| P2 — hosting substrate (§3 + §5 of `hosting-state-model.md`) | 10–12 days part-time |
| P3 — party linked to real characters, then table initiative | 2–3 days |
| P4 — the board | 5–7 days |
| **Total** | **~4–5 weeks part-time** |

P0–P3 is a hosted table. P4 is the board. **P4 is severable at any point.**

---

## 8. The questions, and the rulings of 2026-09-11

Questions 1–4 were carried unanswered from `hosting-state-model.md`. All seven were put to
the human on 2026-09-11 and six are now ruled.

1. **Tab semantics — RULED: per browser.** Tier 1 is `app.storage.user`, cookie-keyed and
   shared across tabs of one browser. Opening a second character in a second tab repoints
   the first. This matches the desktop app, which edits one character at a time.
   ⚠ `app.storage.user` requires `storage_secret`, which is set nowhere in the tree today.
   Read it from an env var; do not commit one.
2. **Homebrew scope — RULED: both, layered like game mods.** Table layer and character
   layer. **See §1.3** — this is one new scope over a mechanism 0012 already shipped, the
   precedence rules already compose, and the one thing needing design is *consent* on the
   table-layer write.
3. **Eviction vs auto-save — RULED 2026-09-11: dissolve it.** The human accepted the
   recommendation below rather than pick a TTL, so **there is no "how long may an idle
   session hold unsaved work" number to agree** — auto-save removes the question.
   With auto-save, eviction stops being a data-loss question and becomes a memory-tuning
   one, and any idle TTL is defensible.
   ✅ **SHIPPED 2026-09-11** — `hosting-state-model.md` §3.7b is the record.
   ⚠ **The mechanism named in this ruling was wrong, and the correction matters more
   than the ruling.** "Debounced auto-save on the existing `changed()` callback — one
   helper, because every tab funnels mutations through it" was **false: three of the
   seven tabs define `changed()`.** Hooking it would have given auto-save in three tabs
   and silence in four, with every test green. What shipped is a dirty-hash `ui.timer`,
   which cannot be wired to the wrong phase because it is not wired to a phase.
   ⚠ Do **not** save on every mutation; the dot tracks fire their refresh per click.
4. **The GM page — RULED: it dissolves.** Not deferred, *replaced* — the shared table view
   is the main view. **See §1.3** for the consequences, including the two things that must
   survive the dissolve (the ST-only surface, and server-side membership checks).
5. **Is the board in or out — RULED 2026-09-11: assume yes, shape open.** Human:
   *"Board ships later; assume yes for now, we'll see how it ships."*

   **For planning: yes.** Do not design P0–P3 in a way that forecloses it, and do not list
   the board as an open question again.

   ⚠ **"We'll see how it ships" is a HEDGE on the SHAPE, recorded the way `CLAUDE.md` §10
   records the training-times hedge.** It is not authority to start P4, and it does not
   settle what the board is beyond decision 0020's boundary. **P4 still comes after P3**
   (§0: the board has no substrate to sync through until then), and it is still severable
   if it stops being worth it.
6. **Decision 0020 — RATIFIED** (human: *"Go ahead"*). Now
   `docs/decisions/0020-the-board-is-dumb.md`, Accepted 2026-09-11. §4 of this document is
   superseded by it and is kept only as the draft it was.
7. **Public repo for `exalted-table` — RULED: fine.** `exalted-table` is the VTT repo.
   ⚠ **The engine dependency stays private regardless**, because it carries `data/`. The
   human's exposure ruling (2026-09-11, reasoning from Lot-Casting Atemi and the Exalted:
   Essence webapp) is about **the service**; the source split in §1.1 is a separate thing
   and is unaffected by it.

### What is still unruled

**Only Q5** — whether the board ships at all — and §0 establishes that it is free to defer
until after P3. **Everything needed to start is ruled.**
