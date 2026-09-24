# P3 — Campaigns (the `Table`): design

**Status: build steps 1–2 DONE 2026-09-12; steps 3, 4 and 5 DONE and BROWSER-VERIFIED 2026-09-22; step 6 (house rules) and 6b (add a character from the campaign) DONE and BROWSER-VERIFIED 2026-09-22 (phone width not tested; the request-card house-rules warning browser-verified 2026-09-23); step 7 (the campaign homebrew) DONE and deployed 2026-09-23, NOT browser-verified (§14 is the build log). The layout was approved 2026-09-22 (§15). Steps 8–9 (the revised order, §15.4) are not started.**
Every product question the human was asked is ruled (`vtt.md` §9.1, §9.2, §9.3a, §9.10), and
so are the six the design turned up (§13).

**Read first:** `vtt.md` §1.3 (why a Table is first-class, and the three homebrew layers),
§9.2 (the base character), §9.10 (the P3 rulings), and `docs/lessons.md` on the house bug.
This file does not restate them; it builds on them.

"Campaign" is the word the UI uses. `Table` is the code name, as everywhere else.

---

## 1. The rulings this design must honour

| Source | Ruling |
|---|---|
| §9.1 | Joining is **a code, and the Storyteller approves**. Not an open link. |
| §1.3 / Q4 | The GM page dissolves: **the table view is the main view, visible to every member**. The ST-only surface is the adversary roster and the TABLE-WIDE house rules. ⚠ *"Visible-by-default is a ruling about the UI, not a licence to drop authorisation"* — membership is checked server side. |
| §1.3 / Q2 | Homebrew has three layers: book → **table** → **character** (carried copies). A joining character never writes into the table layer without the ST. |
| §9.2 | XP belongs to a **campaign copy**; a base never takes XP. `table_id` is nullable (solo copies exist). |
| §9.3a | A character is a file plus a DB row. |
| §9.10 | A copy is made **when you join as a player**. **The ST grants XP.** A leaver **keeps the copy as solo**. Codes are **six letters/digits, no expiry**. The table's data lives in **a folder of its own** (`<root>/table-<id>/`). **Spectators** join by the same code and approval, see what players see, and "spectator" is chosen **when opening** the campaign. A member can have **several characters** in one campaign. |

---

## 2. The data

### 2.1 Database (`server/db.py` SCHEMA)

```sql
CREATE TABLE IF NOT EXISTS tables (
    id TEXT PRIMARY KEY,                 -- "table.<12 hex>", the shape of character ids
    name TEXT NOT NULL,
    storyteller_id INTEGER NOT NULL REFERENCES users(id),
    join_code TEXT UNIQUE NOT NULL,      -- 6 characters, see 2.3
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- An approved member. The Storyteller is NOT a row here: `tables.storyteller_id` is the
-- one place the role lives, so there is nothing to keep in step.
CREATE TABLE IF NOT EXISTS memberships (
    table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    joined_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (table_id, user_id)
);

-- A request waiting for the Storyteller: to join, or (a member) to bring another base.
-- base_id NULL = "just watching". Approval makes the membership if it is absent and,
-- with a base, the campaign copy. Rejection deletes the row.
CREATE TABLE IF NOT EXISTS join_requests (
    id INTEGER PRIMARY KEY,
    table_id TEXT NOT NULL REFERENCES tables(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    base_id TEXT REFERENCES characters(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

`characters.table_id` already exists (piece 4, NULL everywhere). **Add the foreign key in
the same change** (`REFERENCES tables(id) ON DELETE SET NULL`) — ⚠ SQLite cannot add a
constraint to an existing column. The column holds only NULLs today, so the change is a
table rebuild of a table with no non-NULL values in it; that is not a migration of data,
but it IS schema code, and `CLAUDE.md` §10 wants the human told. Alternative: no FK, and
`TableStore.delete` clears the column itself (the store already owns every write).
**Recommendation: no FK; the store clears it.** One writer, tested.

**Why a request table, not a `state` column on memberships.** The rulings made a request
carry a *base* (a copy is made on approval) and allowed *several* requests per member
(bringing another character). A state column holds one of each; a request row holds as
many as there are.

### 2.2 Files (ruled: option A)

```
<root>/table-<id>/
    custom/              the table's homebrew layer, custom_content's shape
    adversaries.json     the roster (models/adversary.Adversary list)
    house_rules.json     the TABLE-WIDE HouseRules fields (see §5)
    notes/<user_id>.json each member's own notes, private (§15.6 Q8, 2026-09-22)
    log.json             the Log: messages and rolls, newest 500 (§15.3, added 2026-09-22)
```

* The quota (`server/quota.FolderQuota`) counts the first folder below the root, so a
  table gets **its own 10 MB** with no change.
* Every write goes through `persistence.atomic_write`, so the quota covers it.
* ⚠ The campaign copies stay in their **owners'** account folders. A table folder never
  holds a character. That keeps "who owns this file" a one-line answer and makes leaving
  (ruling 3) a DB change only.

### 2.3 The join code

Six characters from an alphabet **without look-alikes** — `ABCDEFGHJKMNPQRSTUVWXYZ23456789`
(no `0 O 1 I L`), **31⁶ ≈ 887 million**. Upper-case, compared case-insensitively. Generated
with `secrets.choice`, retried on a UNIQUE clash. No expiry (ruled).

⚠ **A code that never expires is a password that never changes.** The approval step is what
makes that safe: a leaked code yields a *request*, not access. So:
* **The join form is rate-limited** the way login is (`server/throttle.py`, keyed by user),
  or six characters can be enumerated at leisure.
* **The ST can issue a new code** (a button; the old one stops working). Not an expiry —
  a revocation, for the day a code ends up somewhere public. *A design choice, not a ruling;
  it contradicts nothing ruled.*

---

## 3. Stores (no UI)

`server/tables.py` — `TableStore(db_path, root)`, the shape of `CharacterStore`:

| Call | Does | Refuses |
|---|---|---|
| `create(st_id, name)` | row + folder + code | — |
| `access(user_id, table_id)` | `"storyteller"`, `"member"` or `None` | malformed id before the DB (as `CharacterStore.row`) |
| `for_user(user_id)` | tables the user runs or belongs to | — |
| `request(user_id, code, base_id or None)` | a join request | unknown code; a base the user does not own; an unlocked base; a copy as the base; a duplicate pending request for the same base |
| `approve(st_id, request_id)` | membership (if absent) + `make_copy(..., table_id=)` | not the ST |
| `reject(st_id, request_id)` | deletes the request | not the ST |
| `leave(user_id, table_id)` / `remove(st_id, table_id, user_id)` | deletes the membership, clears `table_id` on that user's copies in the table | the ST leaving their own table |
| `delete(st_id, table_id)` | clears `table_id` on every copy, deletes the rows and the folder | not the ST |
| `new_code(st_id, table_id)` | replaces the code | not the ST |
| `characters(table_id)` | the copies in the table, with owners | — |

`CharacterStore.make_copy` grows a `table_id=None` argument — the copy is born in the table
(ruling 1), not moved in afterwards.

⚠ **`access` is the authorisation check**, as `owned` is for characters. Every `/table`
page calls it in the page body before anything else; every ST action calls it again in its
handler. A hidden button is not a check.

---

## 4. Rules layers — which RuleSet a campaign copy sees

> ⚠ **Superseded in part by the step-7 rulings (§14 "Step 7", 2026-09-23):** one campaign
> layer, no per-character layer; the approval adds the carried homebrew (no separate
> "Add to campaign homebrew" button); player proposals. `AccountRulesets` became
> `server/rulesets.Rulesets`. The mechanics below (layers, precedence, the reload trap)
> are what was built.

Today a character's context gets `AccountRulesets.for_account(owner)`: book + the owner's
library. For a copy in a table it becomes **book → table layer → owner's library?** — and
the last arrow is **open question Q1 (§13)**. The mechanics either way:

* The table layer is `<table folder>/custom`. ⚠ **`with_custom_layer` does NOT compose
  as it stands.** `reload_custom_layer` first deletes *every* row flagged `custom` (and
  every gear row tagged `custom`), then merges one folder. So
  `with_custom_layer(with_custom_layer(book, table_dir), account_dir)` wipes the table
  layer in the outer call and leaves only the account's. (Found re-reading this design,
  2026-09-12. It is the reason the fifth mutation of §5.3 passed at first — the same
  delete-first behaviour, seen from the other side.)
* **So step 6 teaches the loader LAYERS**: `with_custom_layers(book, [table_dir, ...])`
  and `reload_custom_layers(ruleset, [dirs])`, which clear once and merge each folder in
  order. Each merged row records its layer (a `custom_layer` value, or the folder), so a
  reload of one layer — the ST editing the table's Custom page — can rebuild the whole
  stack instead of dropping the other layer. Tests: author into each layer, reload each,
  assert the other layer's rows survive.
* Precedence on an id clash (both layers carry `custom.x`): **the table wins** — the table
  is the shared agreement, by the same logic as `absorb_definitions`' "the recipient's own
  version wins". The loader keeps the first definition it sees, so this is the ORDER of
  the folders. Needs a test, and a problem message that names the losing layer (today's
  message says "defined twice in the library", which would be wrong across layers).
* ⚠ **The Custom tab reloads the RuleSet it is handed** (`reload_custom_layer(ruleset,
  root)`). A campaign copy's RuleSet is a stack; the account's Custom page must never be
  handed it, or a save on the Homebrew tab rebuilds the stack from one folder. The
  account RuleSet and each table's RuleSet stay separate objects.
* A `TableRulesets` cache keyed by table id, next to `AccountRulesets`. The table view and
  every copy in the table read it; the ST's edits on the table's Custom page reload it in
  place, so every member sees a new table Charm at once — the same behaviour the account
  layer has.
* **Consent (§1.3).** A join request shows the ST what the base carries
  (`character.custom_definitions`: "brings 2 homebrew Charms: …"). Approval admits the
  character *with* its carried homebrew, which stays on the character. Moving any of it
  into the table layer is a separate ST button ("Add to campaign homebrew"). **Nothing is
  ever absorbed into the table layer as a side effect** — `absorb_custom=False` on every
  table path, and a test that approves a join and asserts the table's `custom/` is empty.

---

## 5. House rules — the TABLE-WIDE fields

The TABLE-WIDE fields today (`models/character.HouseRules`, marked in comments):
`magic_for_everyone`, `restrict_chargen_ritual_level`, `restrict_chargen_science_rating`,
`all_backgrounds_available`, `mf_change_method`, `godblooded_inheritance_rating`.

**The table's `house_rules.json` is canonical; each copy in the table holds a synced copy.**
`tables.apply_table_rules(table_rules, character)` overwrites exactly the TABLE-WIDE fields.
It runs:
1. when a copy is made for the table (approval),
2. on every copy in the table when the ST changes a switch,
3. **in the character context factory, every time a campaign copy loads.**

(3) is what makes drift impossible: whatever a file says, the table's values are what the
page sees. ⚠ **Why sync-on-write and not overlay-on-read:** the engine reads
`character.house_rules` at many sites. An overlay would need each of them to know about the
table, and the one that does not is the house bug, type 1. A synced copy changes no read
site, and a downloaded copy still prices correctly on the desktop.

⚠ **House bug, type 3 — the switch the player can edit.** On a campaign copy the ST Options
tab must show the TABLE-WIDE fields **read-only** ("set by the campaign"). Otherwise a player
flips `restrict_chargen_ritual_level` off, and (3) flips it back on the next load, and the
player has meanwhile bought something the table forbids. The lockout is keyed on a field the
page cannot edit — `ctx["row"].table_id` — not on anything in the character. A test must
drive the tab on a campaign copy and assert the control is disabled.

The ST's switch panel lives on the table view (ST-only). The Party page's "apply to every
character" control is the precedent (`CLAUDE.md` §13: *"may change TABLE-WIDE fields only"*).

PER-CHARACTER fields (`st_foreign_charms`, `mortal_favored_ability`, …) are Storyteller
*permissions*. Who may set them on a campaign copy is **open question Q2**.

---

## 6. XP (ruled: the ST grants)

* ST-only on the table view: **Grant XP** — an amount and a note, to one character or to
  every copy in the table. It calls `advancement.add_xp` (negative corrects an over-grant,
  as now).
* ⚠ **Grant through the live context, not the file.** If the copy is open (its id is in the
  character registry), `add_xp` goes on `ctx["char"]` and the page's auto-save writes it.
  Writing the file behind an open page is overwritten by the next auto-save — a lost
  update. If the copy is not open: load, add, save through the store.
* **An award log** in the table folder (`awards.json`: when, who, how much, the note).
  `xp_earned` is a bare number; without a log nobody can answer "why do I have 47 XP?".
  *A design choice; needs no ruling.*
* ⚠ **House bug, type 3 again:** Edit's sticky column has **Adjust XP**, which lets the
  player set their own earned XP. On a campaign copy that must be absent (ruling 2 made XP a
  table mechanism). Solo copies keep it. Keyed on `table_id`, tested on the page.
  This is **open question Q5** only in that the human should confirm it.

---

## 7. Pages

### `/home` — a third section, **Campaigns**
* **Your campaigns**: each table you run or belong to — name, your characters in it, the
  member count, and for the ST the pending-request count.
* **New campaign** (name → you are its Storyteller).
* **Join a campaign**: the code, then *which base to bring* **or** *"just watch"*. Shows
  "pending" until approved.
* A base card gets **"Join a campaign with this"** as a shortcut into the same form.

### `/table/<id>` — the table view

> ⚠ **Superseded in part by §15 (2026-09-22).** The layout is §15.2, and the ST does NOT
> edit a player's trackers (R3). The rest of these bullets stands where §15 is silent.

* `access()` first; `None` → the same "There is no such campaign" as a missing one.
* **Open as** (ruling: chosen when opening): a small chooser — each of *your* characters in
  the table, or **Spectate**. Remembered per browser (`app.storage.user`), changeable from
  the header. The choice decides only which of your cards is highlighted and which "Open
  my sheet" link the header shows; **a spectator sees exactly what a player sees** (ruled),
  so the chooser changes emphasis, not permission.
* **The cards**: every copy in the table — the Party page's card (name, splat, health,
  motes, Willpower, the play trackers), read-only for everyone but the owner, whose card
  links to `/character/<copy>`. Built with the Party page's card code, not a second copy of
  it (`ui/view.py` owns the presenter; `ui/gm.py` the widgets).
* **ST-only**, drawn only when `access() == "storyteller"` AND checked again in each
  handler: requests (approve / reject, with what each base carries), members (remove),
  Grant XP, the TABLE-WIDE switches, the adversary roster, the campaign homebrew (the
  Custom page against the table's `custom/`), New code, Delete campaign.
* **Live**: a `ui.timer` polls a digest of each card's character — the live context if the
  copy is open, else the file — and repaints a card whose digest moved. ⚠ **Poll, do not
  hook**: the auto-save lesson (§3.7 of `hosting-state-model.md`) applies unchanged.

### `/character/<copy>` for a campaign copy
Unchanged, plus: the header shows `‹ <campaign> › <name>`, Adjust XP is absent, the
TABLE-WIDE switches are read-only, and the ST-permission fields follow Q2.

---

## 8. Contexts and live objects

* **Characters** keep one context per character id (piece 4). The table view **reads**
  them from the registry when present; it never builds one for a character the viewer
  does not own — it reads the file instead. ⚠ Building a context for someone else's
  character would give the viewer a live object the owner's page does not share.
* **Tables** get one context per table id, in a second `SessionRegistry`: the adversary
  roster, the notes, the table's RuleSet. The ST's two devices share it. Written back by
  the same poll-and-digest auto-save the builder uses, to the table folder.
* ⚠ **`open_member` by-reference semantics** (`hosting-state-model.md` §3.6) are a Party
  page fact. The table view does not embed characters, so it does not inherit that
  invariant — do not port `open_member`.

---

## 9. Initiative — the gate

`vtt.md` §2 names **roll initiative for the whole table** as P3's gate, and
`status/dice-roller.md` records it as blocked on exactly this. With the table view it is:
the ST presses one button; each card gets `1d10 + its initiative pool` (the pool comes from
`engine/initiative.initiative` via `view.build_initiative`; the +1d10 is the printed fixed count — **do not generalise it**,
per the handoff). Results shown on every member's view. Decision 0019's rule holds: the
roller rolls a count it is handed.

---

## 10. Leaving, removal, deletion

* **Leave** (a member) / **remove** (the ST): the membership goes; that user's copies in
  the table get `table_id = NULL` and become solo copies (ruling 3). Their XP, notes and
  play state stay. Their pending requests for that table are deleted.
* **The ST cannot leave their own table** (who would run it?). Handing a table over is not
  in scope; delete is.
* **Delete campaign** (ST, with a confirm naming the member count): every copy becomes solo
  (the same rule as leaving, applied to all — **open question Q3** asks the human to
  confirm); the rows, the requests and the table folder go.
* After any of these, a member's open `/table/<id>` page must stop: its next poll finds
  `access() == None` and replaces the page with "You are no longer in this campaign".

---

## 11. Build order

> ⚠ **From step 3 on, §15.4 replaces this list** (it adds the Log as step 4 and renumbers).

Each step is its own commit, tests first, green before the next.

1. ✅ **DONE 2026-09-12 (§14).** **`TableStore` + schema + codes + throttle.** No UI. The whole of §3 and §2.3, with the
   refusals as tests and the ownership / access checks mutation-checked.
2. ✅ **DONE 2026-09-12 (§14).** **`/home` Campaigns**: new, join (code + base or watch), pending. The ST's request list
   on a bare `/table/<id>` (approve / reject). Approval makes the copy with `table_id`.
3. **The table view**: cards, open-as, spectate, live poll, `access()` on every route and
   handler. The "no longer a member" path.
4. **ST tools**: Grant XP (live-context path + award log), remove member, new code,
   delete. The Adjust XP lockout on campaign copies.
5. **House rules**: `house_rules.json`, `apply_table_rules` at the three sites, the ST
   switch panel, the read-only TABLE-WIDE fields on copies. *Needs Q2.*
6. **The table homebrew layer**: `TableRulesets`, the composed overlay, the campaign
   Custom page, "Add to campaign homebrew", the no-absorb test. *Needs Q1.*
7. **Adversaries and notes** on the table context (port from the Party page's roster).
8. **Initiative for the whole table** — the gate.

Steps 1–4 need no further ruling.

---

## 12. Traps — the house-bug list for this phase

| Trap | Type | Guard |
|---|---|---|
| Membership checked in the view only | — | `access()` in every page body and every ST handler; a test per route that a non-member gets nothing, and a mutation that drops the check |
| House rules overlaid at read sites | 1 | sync-on-write at three sites (§5); a test that loads a campaign copy whose file disagrees with the table and sees the table's values |
| TABLE-WIDE switch editable on a copy | 3 | read-only on campaign copies, keyed on `table_id` |
| Adjust XP editable on a copy | 3 | absent on campaign copies, keyed on `table_id` |
| XP grant written behind an open page | 1 | grant through the live context when open; a test with the copy open that the auto-save keeps the grant |
| Table layer written by a join | — | `absorb_custom=False` on every table path; the empty-`custom/` test |
| The two layers sharing dicts, or one reload dropping the other layer | 2 | `with_custom_layers` clears once and merges in order; a test per layer that reloading it keeps the other (§4) |
| A spectator reaching an ST handler | — | the ST check is `access() == "storyteller"`, never "not a spectator" — spectator is a way of opening, not a role |
| A table context made for a non-member | — | `access()` before the table registry, as `owned` before the character registry |

---

## 13. Open questions — new, found while designing

**Answers, 2026-09-12:** **Q1 no** (a campaign copy does not see the owner's library).
**Q2 the ST.** **Q3 yes.** **Q4 allow it** (a GMPC; nothing to build). **Q5 "Maybe? Probably."**
— build it as removed, and flag it at the click-through. **Q6: in a campaign, unlocking is
up to the ST** (ST-only, as recommended). **Unlock after XP, everywhere: allowed, with a
warning** (ruled the same day; see the note under Q6).

These are the human's. Each has a recommendation.

**Q1. May a player use their OWN homebrew library on a campaign copy?** Today a copy's
RuleSet includes the owner's account library. In a campaign that means a player can author
a Charm at home and buy it on their campaign copy with no Storyteller involved — which is
the thing §1.3's consent rule exists to stop, arriving by a side door.
*Recommendation:* **no** — a campaign copy sees book → table layer → **only the homebrew it
carried in at approval** (which the ST saw and admitted). New personal homebrew reaches a
campaign through the ST's "Add to campaign homebrew".

**Q2. Who sets the PER-CHARACTER Storyteller permissions on a campaign copy?**
(`st_foreign_charms`, `mortal_favored_ability`, `st_celestial_manse_over_three`,
`st_mortal_artifact_manse`, `terrestrial_essence_transcendence`, and
`committed_motes_reduce_free_essence`.) They are ST permissions by their own comments;
today the player toggles them because the player is the only person at the desktop.
*Recommendation:* **the ST only**, from the table view; read-only on the copy.
(`committed_motes_reduce_free_essence` reads more like a table convention than a permission;
the human may prefer it TABLE-WIDE.)

**Q3. When a campaign is deleted, do the copies become solo?** Ruling 3 covers a player
leaving; deletion is every player leaving at once. *Recommendation:* **yes**, the same rule.

**Q4. Can the Storyteller also play a character in their own campaign?** The design allows
it for free (the ST is a user and can bring a base). *Recommendation:* **yes**, and it needs
nothing. (Co-Storytellers are a separate, later question — not designed.)

*Human, 2026-09-12: "Yes; isn't that what the Adversary system is for?"* — The adversary
roster covers the ST's NPCs (stat blocks; an `Adversary` is not a `Character`, `CLAUDE.md`
§13). Q4 is only about a full builder-made character, a GMPC. Asked back.

**Q5. Is Adjust XP removed from campaign copies?** ✅ *Confirmed at the step-5 click-through, 2026-09-22, Downtime… included.* It follows from ruling 2, but it removes
something a player can do today. *Recommendation:* **yes**.

**Q6. May a player Unlock a campaign copy?** `unlock_chargen` reopens chargen, which on a
copy with an XP log is how a player could re-spend creation points mid-campaign.
*Recommendation:* **ST only** on a campaign copy (a button on the table view); the player's
Unlock is absent there. Solo copies unchanged.

⚠ **Found while explaining Q6 to the human: unlock after XP has no policy anywhere.**
`lifecycle.unlock_chargen` drops the snapshot and nothing else; its own docstring says
*"No XP layer exists yet; if one is added, unlocking after XP has been spent will need an
explicit policy."* The XP layer exists (decisions 0004, 0013) and the policy was never set.
So on ANY character with a non-empty `xp_log` — desktop and solo copies too — Unlock turns
the XP-bought dots into creation dots while the log still records them as spent, and a
re-lock snapshots the inflated state as the character's creation. A rules-engine question
for the human, bigger than P3.

---

## 14. Build log

### Step 1 — `TableStore` + schema + codes + throttle (2026-09-12)

**Shipped, no UI:** `server/tables.py` (`TableStore`, `TableRow`, `JoinRequest`,
`JoinThrottle`, `new_join_code`); the three tables of §2.1 plus an index on
`characters(table_id)` in `server/db.SCHEMA` (all `IF NOT EXISTS`, so a deployed database
gains them at the next start — no migration); `CharacterStore.make_copy(..., table_id=None)`.
Tests: `tests/test_table_store.py`, **56 cases**. Targeted run with the character store,
pages, homebrew, auth, quota, throttle, server-main and seam files: **266 passed, 0 skipped
— OBSERVED.** The full suite was not re-run for this step.

**Mutation-checked (12, all killed):** `access` treating anyone as a member; the
Storyteller check as a no-op; the base-ownership, lock and copy-as-base checks dropped; the
throttle skipped; `delete` without its access check; `leave` clearing every owner's
copies; the Storyteller allowed to leave; the duplicate check written `base_id = ?`
(NULL never equals NULL); `delete` leaving `table_id` set; the id-shape check skipped in
`access`.

**Beyond the §3 table, needed by step 2:** `table(id)`, `table_dir(id)` (`<root>/table-<hex>`,
refuses a malformed id), `pending(st_id, table_id)` (ST-only), `requests_by(user_id)`.
`leave` by a non-member withdraws their pending requests and returns False — that is the
withdraw path. A watch request from someone who already has access (a member, or the ST)
is refused. The ST may bring a base (Q4) and approves their own request; no membership row
is written for the ST.

**Design choices made without asking, reversible:**
- **No foreign key on `characters.table_id`** — the §2.1 recommendation. The store clears
  the column at leave, remove and delete; three tests and a mutation cover it.
- `delete` by a non-Storyteller **returns False** (as `CharacterStore.delete` does); the other
  ST operations **raise** `TableStoreError`.
- The throttle numbers are the login throttle's (5 free, then 30 s doubling to 15 min).

🐞 **Found on the way — a correct code must not clear the count.** The login throttle
clears a name on success, which is safe there because the attacker does not know the
password. The join throttle is keyed by the **asking account**, and that account always
knows one correct code: its own campaign's. Clearing on success would let it guess four,
reset with its own code, and repeat forever. `JoinThrottle` counts every attempt and
never calls `succeeded`; `test_a_correct_code_does_not_clear_the_count` holds it. §2.3
said only "rate-limited the way login is", which would have shipped the bypass.

⚠ **For step 4+:** `server/quota.QuotaExceeded` says *"This account has no space left"*.
A table folder hitting its 10 MB will show the word "account". Reword when the table's
first write path lands.

### Step 2 — `/home` Campaigns + the bare `/table/<id>` (2026-09-12)

**Shipped:** `server/campaigns.py` — `HomeCampaigns` (the CAMPAIGNS section of `/home`:
cards, **New campaign**, **Join a campaign** with code + base-or-watch, the WAITING FOR
THE STORYTELLER list with **Withdraw**) and `register_table_page` (`/table/<id>`: name,
Storyteller, CHARACTERS, MEMBERS; for the ST also the JOIN CODE and REQUESTS with
Approve / Reject and what each base carries). A base card on `/home` has **Join**, the
shortcut into the same form with that base chosen. A copy card says *"· In <campaign>"*.
New shared module `server/chrome.py` — the page paths, the top bar, the grid and the
character card moved out of `home.py`, so `home.py` and `campaigns.py` do not import each
other. `TableStore` grew `withdraw` and `members`. `build_server` makes **one**
`TableStore` for the process (the join throttle lives in it).

**Tests:** `tests/test_campaign_pages.py` (21, production wiring through
`tests/_auth_main.py`) and 3 more in `test_table_store.py`. **Mutation-checked (8, all
killed):** `access` dropped from the page body; the code shown to members; withdraw done
with `leave`; the join form offering drafts and copies; the carried-homebrew line dropped;
`withdraw` ignoring the owner; `members` not filtered by table (survived at first — the
test had one table; a second table's member now kills it); the approve handler not
catching the store's refusal.

🐞 **Found on the way — `leave` is not a withdraw for a member.** The step-1 log and the
handoff said *"`leave` as withdraw"*. That holds only for a non-member. A member who asked
to bring a second character and withdrew with `leave` would be taken out of the campaign,
and their copies made solo. `withdraw(user_id, request_id)` deletes the one request;
`test_withdraw_deletes_one_request_and_keeps_the_membership` and its page twin hold it.

**Design choices made without asking, reversible:**
- The CAMPAIGNS section is the third section of `/home`'s Characters tab, after the
  copies (§7 says "a third section"), with its own New / Join buttons.
- The join code shows on the ST's `/home` card as well as on `/table/<id>`.
- The join form starts on the first base; "Just watch" is the last option. With no base
  it says how to get one.
- A member's `/table/<id>` lists the characters (a card links only to the viewer's own
  copy — another account's page would refuse it) and the members by username.
- A requester sees the name of a campaign they are waiting on (they typed its code).
- Each ST handler asks `access()` again (`still_storyteller`). ⚠ **No test can kill that
  mutation**: the store refuses the same call, so the page behaves the same without it.
  It is defence in depth; the store is the check.

✅ **BROWSER-VERIFIED 2026-09-12** — the human ran the six-step click-through (two accounts,
create, join by the Join shortcut with a lower-case code, approve, the copy "· In <name>",
the watch refusal, a stranger's "no such campaign"): *"everything looks good!"* With a
note: *"the campaign window will probably need to be redesigned at some point, but it's
fine for now."* ⚠ Step 3 replaces the bare `/table/<id>` body with the table view, so that
redesign lands there. Follow `match-the-builder-look` (spike, screenshot, iterate).

**Not live yet (step 3):** neither page polls. The ST sees a new request on reload, and a
player sees an approval on reload.

### Step 3 — the table view: shell and party (2026-09-22)

**Shipped:** `server/table_view.py` replaces step 2's bare `/table/<id>` body with layout A
(§15.2). The top bar: Home › campaign · role, **Open as** (a member with a copy in the
table: each own copy, or Spectate; remembered per browser in `app.storage.user`, key
`table-open-as:<table id>`), the ST's request button with a count badge (opens the ST
tab), and ⋮ → Log out. The left rail: `PARTY (n)`, **YOU PLAY** with the R2 controls
(health boxes cycle; each mote pool is a bar with − / + and a click-to-type menu with
Spend / Regain / Full; Willpower and Limit — or Clarity, or Paradox by
`derive.limit_label` — as click tracks; ↗ to `/character/<copy>`), then **THE OTHERS**,
read-only for everyone. The centre is the board frame and *"The board comes next."*
(Q7). The right rail: **Log** (a not-built line until step 4), **Notes** (MEMBERS, with
the ST starred and members with no copy marked "watching"; per-member notes are step
8), **ST** (the join code and the requests with Approve / Reject). A 2-second poll.
`campaigns.py` keeps `/home`'s section; `register_table_page` moved out and now takes
the character registry, so `build_server` registers the character pages first.

**Mechanics, as §15.3 asked:**
* YOU PLAY reads and writes **`sessions.ctx_for(copy)["char"]`** — the object the
  owner's `/character/<copy>` page edits — and saves the file after each click
  (`store.save`), so a click is kept with or without that page open.
* Every other copy is read with the new **`SessionRegistry.peek`**: the live context if
  its owner has one open, else the file. `peek` builds nothing and records no use, so a
  poll never keeps another player's context alive (§8).
* The handler asks `access()`, then `store.owned(...)` and `row.table_id == table`, before
  it touches the context. A removed member gets *"You are no longer in this campaign."*
  and the page stops; a deleted copy gets *"That character is no longer in this
  campaign."*
* The poll: `access()` first (None → the page is replaced by the "no longer" answer);
  then the structure (copy ids, members, the ST's pending ids) — changed → redraw the
  top bar, rail, members and ST tab; else a digest per copy (the live character's
  digest, or the file's mtime and size) — changed → redraw the rail.

**Tests:** `tests/test_table_view.py` (24), 2 `peek` cases in
`test_session_registry.py`, 1 in `test_party.py`; two step-2 assertions in
`test_campaign_pages.py` moved to the new text (`PARTY (3)`, the identity line).
**Mutation-checked (8, all killed):** the handler writing a fresh load instead of the
context; `read` using `ctx_for` instead of `peek`; others' boxes given a handler plus
the owner check dropped; the poll's `access()` dropped; the handler's `access()` dropped
(**survived at first** — the removed player's copy is solo, so the owner-and-table check
refused anyway and the page text came from a racing poll; the test now asserts the
notification before any await); Open as not remembered; the digest repaint dropped;
the save dropped.

🐞 **Found on the way:** `PartyCardView.identity_line` gave `" Caste · Mortal"` for a
casteless character. It now gives the splat alone. This also fixes the Party page and
the Qt party card, which share the presenter.

**Design choices made without asking, reversible:**
- MEMBERS sits in the Notes tab for everyone (the spike's round 4), not in the ST tab as
  §15.4 worded it. Remove-member (step 5) goes in the ST tab.
- A mote pool with a maximum of 0 and nothing attuned is not drawn (a Mortal has no
  bars). The Party page draws 0/0 inputs.
- Willpower shows what is LEFT as gold (the spike), while the Play tab and the Party
  page show what is SPENT. A click on box i leaves i dots; a click on the first empty
  box fills it again.
- The Open-as names come from each copy's current name; "(unnamed)" for none.
- A poll of 2 s.
- Log out moved into ⋮ on this page.

**Mortals with Essence Merits (the human asked, same day).** The bars follow
`build_play_view`'s maxima, so the Merits already work: Essence Awareness and Awakened
Essence give a Personal bar only, Beacon of Power one "All motes" bar, Aura of Power
both. 🐞 **The Essence Awareness free third was missing** from YOU PLAY. The sentence was
written twice already (`ui/play.py`, `qt/play.py`, differing by a full stop); it is now
**`view.free_motes_note`**, used by all three. Tests: 4 shape cases in
`test_table_view.py`, 2 in `test_play.py`; two mutations (the note dropped, the
zero-pool rule dropped) both killed.

**Audit against the Play tab (asked, same day).** Checked by listing every `PlayState`
field, every `PlayView` field and the play-state block of `MeritEffects`, then each
surface's read sites. Findings and what was done (the human: *"sounds fine to me; leave
leave campaign to later"*):
* 🐞 **YOU PLAY drew Limit to a constant 10.** It now reads `derive.limit_max`
  (Greater Curse p.40, permanent Resonance) and says BREAK at that maximum.
* 🐞 **The same 10 on the Party page, web (`ui/gm.py`) and Qt (`qt/party.py`).** The
  Play tab had the rule and the two ST surfaces did not. Both fixed. Tests:
  `test_gm.py::test_a_greater_curse_shortens_the_limit_track` (new route `/gm-curse`)
  and its Qt twin; each failed first.
* 🐞 **The Qt Party card's dot tracks were off by one.** It passed the 0-based box
  index to `engine.play.set_count`, which takes the 1-based box (the Qt Play tab and
  both web surfaces pass `i + 1`). A click on the first Limit or Willpower box of an
  empty track did nothing; a click on box n filled n − 1. No test clicked those boxes.
  `test_qt_party.py::test_a_click_on_a_limit_box_fills_up_to_that_box` (failed first).
  ⚠ `engine.adversaries.set_count` takes the 0-based index on purpose; the Qt
  adversary track is correct.
* **Added to YOU PLAY:** armour fatigue (p.332) as a − / + counter with the roll
  difficulties, shown for a character with armour or with points, as on the Play tab;
  the Clarity band and its printed effects for an Alchemical.
* **Left behind the ↗ (the full sheet), by agreement:** the luck pools (Lucky /
  Unlucky), the Great Geas panel, the health box labels (the labels were added in
  step 4, on request).
* **Leave campaign:** no UI anywhere, though `TableStore.leave` exists. **Deferred by
  the human** — added to step 5 in §15.4.

✅ **BROWSER-VERIFIED 2026-09-22.** The human ran the six-step click-through (the look
against the spike and at narrow width, the mote bar menu, Limit to 7 under Greater
Curse, fatigue, Clarity on an Alchemical, one character in two tabs, the live repaint
across accounts with the ST unable to mark a player, removal stopping the page): *"It
works. No notes."*

⚠ **Known limit:** another player's copy is shown against the BOOK RuleSet when its
owner has no page open (with the owner's account RuleSet while one is open). A homebrew
Charm that adds health levels or motes therefore shows only while the owner is on.
Step 7 (the table homebrew layer, §4) settles which RuleSet a campaign copy sees.

⚠ **Also not live:** the builder page of a character does not repaint when the table
changes its trackers. The object is shared, so the marks are there at its next redraw
and its auto-save writes them; the Play tab shows them on a tab switch or reload.

### Step 4 — the Log (2026-09-22)

**Shipped:** `server/table_log.py` (new): `TableLog(tables)` with `entries`, `version`,
`post` and `roll`, kept in `<table folder>/log.json`. The Log tab of `/table/<id>`
replaces the step-3 placeholder: the entries (name, the ST starred, HH:MM, the text,
and for a roll `N dice → 3 successes` with the faces high to low), a text box, a
**Dice** count, **Roll** and **Send** (Enter sends). `build_server` makes one `TableLog`
and passes it to `register_table_page`.

**Mechanics, as §15.3 asked:**
* **The server rolls**: `TableLog.roll` calls `engine/dice.roll` (TN 7, 10s double, a 1
  can botch). No call takes faces. An entry stores the count, the faces, the successes
  and the botch.
* **The caption rule**: Roll takes whatever is in the text box as the caption (it may
  be empty), then clears the box. The count stays for the next roll. Nothing fills
  the count (0019).
* **Bounds**: the newest **500** entries on each write; **1,000** characters for a
  message or caption (the store refuses more; the box also has `maxlength`).
* **Who**: `access()` is not None — the ST, players and watchers. The store checks it
  on each write, and the page handler checks it first and stops the page (GONE), as
  YOU PLAY's handler does.
* **The poll**: `version()` is the **newest entry id**, not the file's mtime and size.
  ⚠ A full Log can have the same size after a write, and two writes in one clock step can share an
  mtime, so a stat digest can miss a post. The id only rises. The poll reads the file
  (at most ~500 short entries) once per viewer per 2 s.
* **Append, not redraw**: a new entry is added below the ones on the page; the whole
  list is drawn only on the first draw or when the file lost entries. Then it scrolls
  to the newest.
* The username is resolved at render (`db.username_for`), never stored.
* `ui.label` only; `whitespace-pre-wrap break-words`.

**Tests:** `tests/test_table_log.py` (21, the store) and 10 new cases in
`tests/test_table_view.py` (a message reaches another member by the poll, Enter
sends, the caption rule, an empty caption, a bad count, `<b>` and `<script>` shown as
text, a watcher and the ST post, older entries with the star, a post after removal,
the append path). **Mutation-checked (10, all killed):** `ui.html` for the text (killed
by the `type is ui.label` assertion, not by a crash); the handler's `access()` dropped;
the store's member check dropped; no trim; the poll ignoring the Log; Roll dropping the
caption; the append path redrawing old entries (duplicates); `version` by length;
no text cap; the roll ignoring the injected RNG.
**Full suite: 3877 passed + 1 skipped — OBSERVED** on the dev machine (3846 + 31).

**Design choices made without asking, reversible:**
- **A count of 0 is refused** ("Type a number of dice from 1 to 100"), though
  `dice.roll` accepts 0. A roll of no dice has nothing to show.
- **No target-number or 10s/botch switches** in the Log (R5 names a count only). The
  Play tab's roller keeps them. A damage roll in the Log therefore counts 10s double.
- **Times are the server's local time**, HH:MM. The server does not know the
  browser's time zone.
- The count box starts empty (the spike had 6).
- An unreadable `log.json` reads as empty, with a warning in the server log; the next
  post then replaces it.

✅ **BROWSER-VERIFIED 2026-09-22.** The human ran the five-step click-through (a message across two accounts, the caption rule, `<b>` as text, the look and narrow width, removal) and checked the health labels: *"everything looks good! no issues on my end now and everything in the clickthrough passed"*.

⚠ **Known limit:** the Log has no paging. The newest 500 are all on the page.

**Asked after (the human, same day): the health box labels.** Step 3 left them behind
the ↗. Each box on YOU PLAY and on THE OTHERS now has its label above it, the Play tab's
`PlayHealthBox.label` (`-0`, `-1`, `-2`, `-4`, `Incap`, ★ for a level from a Charm).
No new calculation. Test: `test_each_health_box_has_its_penalty_label` (failed first).

### Step 5 — the ST tools, and Leave (2026-09-22)

**Shipped:** `server/table_st.py` (new): `TableStoryteller(tables, store, sessions, log)`
with `grant_xp`, `awards` and `unlock`; the award log is `<table folder>/awards.json`.
`register_table_page` makes one. The ST tab of `/table/<id>` now has, top to bottom:
JOIN CODE with **New code**, REQUESTS, **GRANT XP** (amount, Everyone or one character,
a note), **AWARDS** (the newest 10), **MEMBERS** with Remove, **CHARACTERS** with Unlock
on each locked copy, and **Delete campaign**. A member (not the ST) has **Leave
campaign** in ⋮. Every one of these confirms first except Grant; Delete names the member
count, Remove and Leave say the characters become solo copies, Unlock after XP shows
`view.unlock_warning`.

**The lockout (Q5, Q6):** `/character/<copy>` for a copy with `row.table_id` set builds
**no Unlock, no Adjust XP and no Downtime…** — not hidden: a hidden button keeps its
handler. The editor shows *"The Storyteller grants XP in this campaign."* in their
place. `build_app(in_campaign=)` → `build_editor(in_campaign=)`; `home.character_page`
reads `table_id` from the row it fetches on each open, so a copy that leaves gets them
back on its next open. Solo copies and the desktop are unchanged.

**Mechanics:**
* ⚠ **Grant through the live object** (§6, trap §12): `sessions.peek(copy)` — if a
  page holds the copy, `add_xp` goes on `ctx["char"]` and the file is saved from it;
  else load, add, save. `peek`, never `ctx_for`: a grant builds no context. The file is
  saved even when the page is open, because the registry has no save on eviction.
  Unlock takes the same path.
* **Failure**: a copy whose save fails (its owner's account is full) keeps its old XP
  (the live object too) and is named in a warning; the others get the grant. If none
  does, the grant is refused. The award log is written after the copies; if **it**
  fails, every copy goes back to its old XP and the error shows.
* **Each grant posts one Log line as the ST**: `+5 XP to Ashes, Gearheart — note`.
  A failed post leaves the award.
* `access() == "storyteller"` in the store (grant, unlock; remove, new code, delete
  already had it) and again in each page handler. The browser names the copy, so the
  store also refuses a copy not in the table.
* 🐞 **The quota message named the wrong owner.** A table folder has an account
  folder's quota, and a full one said *"This account has no space left"* — to a
  Storyteller whose account has room. `FolderQuota` now says *"This campaign…"* for a
  `table-` folder (`quota.TABLE_FOLDER_PREFIX`, which `TableStore.table_dir` now uses).
  This also fixes the Log's message.

**Tests:** `tests/test_table_st.py` (28, the store), 3 in `test_character_pages.py`
(a campaign copy has none of the three; a solo copy has all three — the negative
control; a copy that leaves gets them back), 1 in `test_folder_quota.py`, and 11 in
`test_table_view.py` (a grant reaches the player's open object and builds no context
for the other; one character; 0 refused; players see the grant in the Log; a grant
after the campaign is deleted elsewhere writes nothing; remove; leave; the ST has no
Leave and an empty campaign's ST tab builds; new code; delete names the count; unlock
after a warning). **Mutation-checked (16, all killed):** the grant reading the file
instead of the live object; `ctx_for` for `peek`; each store role check dropped (grant,
unlock); the copy-in-table check dropped; no restore when the award log fails; no
restore of a failed copy; the not-locked check dropped; 0 accepted; `home.py` passing
`in_campaign=False`; reading `table_id` from the cached `ctx["row"]` (the leave case);
Unlock built on a campaign copy; the page's `_grant` role check dropped; the target
ignored; delete counting characters instead of members; the quota wording.
**Full suite: 3921 passed + 1 skipped — OBSERVED** on the dev machine (3878 + 43).

**Design choices made without asking, reversible:**
- **Downtime… is removed with Adjust XP.** It grants XP too (the Elder Exalts
  award), so leaving it would be the same hole. The ST can grant a Downtime award
  by hand. **Flag at the click-through** with Q5.
- **Unlock (Q6) is in this step**, as a button per character in the ST tab. §15.4 did
  not list it, but removing the player's Unlock without it would leave a campaign copy
  that nobody can unlock.
- **Grant bounds**: 1–1000 XP either way, not 0; a note up to 200 characters.
- **The award posts to the Log** (§15.4 left it open).
- **The ST tab shows the newest 10 awards**; the file keeps all of them (the quota bounds it).
- New code asks for a confirm; the old code stops working and a waiting request stays.

✅ **BROWSER-VERIFIED 2026-09-22.** The human ran the nine-step click-through (the
lockout, grant to everyone and to one, 0 refused, unlock after XP with the warning, new
code, remove, leave, delete) and answered "Correct" to each. **Q5 ANSWERED: yes** —
Adjust XP is absent on a campaign copy, and Downtime… with it (step 1 asked both).

⚠ **Known limits:** a player whose character page is open when the ST grants or
unlocks sees the new XP, or the unlocked state, on their next tab switch or reload.
The object is right at once; the page is not redrawn. After an ST Unlock with the
page open, the player should reload before editing.

### Step 6 — house rules (2026-09-22)

**Shipped:** the table's `house_rules.json` (`TableStore.house_rules` /
`write_house_rules`; it holds the TABLE-WIDE fields only, and a file that does not read
gives the defaults). `models.character.TABLE_WIDE_HOUSE_RULES` is the one code list of
the six TABLE-WIDE fields; a test asserts it equals the "table" scope of
`view._HOUSE_RULES` and that the view lists every field. `engine.house_rule_actions`
gains `apply_table_rules` (copies the six fields, never the PER-CHARACTER ones or the
snapshot; a character with no rules and a default table keeps a clean save) and
`set_house_rule` (the coercion of `set_rule`, on a bare `HouseRules`).

**The three sites of §5:**
1. **Approval**: `make_copy(..., adjust=)` applies the table's rules before the first
   save. The base does not change.
2. **The ST's switch**: `TableStoryteller.set_table_rule` writes the table file FIRST
   (if the quota refuses it, nothing changes), then each copy through `peek` or the
   file (the §6 trap), then posts `House rule: <label> — <setting>` to the Log. A copy
   that cannot be saved is named; site 3 catches it up.
3. **The context factory** (`server/home.py`): a campaign copy takes the table's
   values each time its context is made, and the file is saved if they moved (the
   auto-save takes its first digest after the factory, so it would not write them).

**Q2 (the ST sets the PER-CHARACTER permissions):** `set_character_rule` — ST only (the
owner too is refused), PER-CHARACTER fields only, a copy in the table only. On the page,
a **tune** button on each row of CHARACTERS opens a dialog with that copy's permission
rows, with the same inert notes as the ST Options tab.

**The lockout (house bug type 3):** on a campaign copy the ST Options tab builds **no
control** — each rule is text, under *"The Storyteller of this campaign sets these."*
Both scopes (Q2). `build_storyteller(in_campaign=)` from `build_app`. Solo copies and
the desktop are unchanged.

🐞 **Found on the way: God-Blooded Inheritance priced from the LIVE rules on a locked
sheet.** `merits.inheritance_free_rating` read `character.house_rules`, while every
other chargen-accounting toggle reads the snapshot (`chargen_house_rules`). The existing
test checked that the value is frozen (the write) and not that it is read (house bug
type 2). Harmless on the desktop, where the tab is read-only after the lock; step 6 made
it reachable, because a table switch changes the live value on locked copies. Fixed to
read the snapshot when locked; `test_a_locked_sheet_prices_inheritance_from_the_snapshot`.

**Tests:** `tests/test_table_rules.py` (29), 3 in `test_character_pages.py` (a campaign
copy's tab has no controls; a solo copy's has — the negative control; a copy whose file
disagrees opens with the table's values), 5 in `test_table_view.py` (a switch reaches
the player's open object and builds no context for the other; a select rule; a
permission for one copy; a player has no controls; a switch after deletion writes
nothing), 1 in `test_godblooded.py`. **Mutation-checked (16, all killed):** approval
sync dropped; factory sync dropped; the switch writing the file, not the live object;
`ctx_for` for `peek`; each role check (switch, permission); each scope check (switch,
permission); the copy-in-table check; `apply_table_rules` copying every field; the
table file written after the copies; the file keeping every field; `build_app` not
passing `in_campaign` to the ST tab; Inheritance reading live; the ST panel not drawn;
the permission dialog showing both scopes.
**Full suite: 3959 passed + 1 skipped — OBSERVED** on the dev machine (3921 + 38).

**Design choices made without asking, reversible:**
- **A table switch posts a Log line; a permission does not** (a notify for the ST
  only). A table rule is everyone's business; a permission is one character's.
- **The ST can change a switch at any time.** A creation-rule switch (Magic for
  Everyone, the ritual and Science caps, Inheritance) changes the live value on locked
  copies, but the accounting reads the snapshot, so it reaches a copy only if the ST
  unlocks it. The panel says so. `mf_change_method` and `all_backgrounds_available`
  take effect at once, as their comments intend.
- **Permissions are editable on a locked copy**, with the tab's inert notes shown.
- **The campaign copy's tab shows both scopes as text** — not only the TABLE-WIDE ones,
  because Q2 gave the permissions to the ST as well.

**Answered 2026-09-22:** every campaign copy is born LOCKED, so its creation was priced
under its owner's switches, frozen in the snapshot, and the table's creation switches
reach it only through an ST Unlock. The human: *"make it a notification in the request
popup? 'ST house rules are different on this character'"*. Built: the request card in
the ST tab lists each TABLE-WIDE rule in which the base's creation rules
(`chargen_house_rules`) differ from the table's, as `<rule>: <setting> (campaign:
<setting>)` under that heading (`view.house_rule_differences`). PER-CHARACTER
permissions are not listed. 5 tests; 2 mutations killed.

⚠ **Known limits:** as step 5, a player's open character page shows a switch on the
next tab switch or reload; the object is right at once. A second ST device's panel
does not repaint on the poll.

✅ **BROWSER-VERIFIED 2026-09-22** (steps 6, 6b, the auto-approve and the Grant
checkboxes): the human ran the twelve-step click-through; steps 1–11 "works". Step 12,
phone width, **NOT checked** ("cannot currently"). The permissions button is Material's
`tune` icon (sliders), not a gear — the handover said ⚙.

### Step 6b — adding a character from the campaign (ruled 2026-09-22)

**The gap (the human, after step 6):** *"Should there be a way to join & create
characters from within a campaign?"* The campaign page was a dead end: a watcher, or a
player who wanted a second character, had to go to `/home` and retype the code; and a
character made for the campaign was built with no knowledge of it, under its owner's
switches (the ❓ of step 6).

**Ruled: "Correct."** to the proposal, which was:
1. **Bring a character** from the campaign page: a member picks one of their locked
   bases; the same join request, from the membership instead of the code.
2. **Create a character for this campaign**, option **(a)**: the draft stays an
   ordinary base, tagged for the campaign; it is built under the campaign's house rules
   (and, after step 7, its homebrew); Finish & Lock sends the join request; approval
   makes the copy as now. Rejected: (b), the draft born as the copy with no base — it
   breaks §9.2.
3. **Before step 7.**

**Shipped (same day), tests green, NOT browser-verified:**
* `TableStore.bring(user, table, base)`: the join request from the membership — access
  required, the same base checks as the code path, the same duplicate check (the insert
  is now one helper, `_insert_request`), **not throttled** (the throttle protects the code).
* **Campaign drafts:** a new table `campaign_drafts (character_id, table_id)`, both
  `ON DELETE CASCADE` — `CREATE TABLE IF NOT EXISTS`, as step 1's tables, no migration.
  `start_draft` makes an ordinary draft (no `table_id`) with the table's rules;
  `draft_table`, `drafts`; `send_draft` (owner only, locked only) inserts the request and
  deletes the tag. Leaving or removal deletes the member's tags (the drafts stay);
  deleting the campaign cascades.
* ⚠ **The tag is a DB row, not a Character field**: the page cannot edit it (type 3).
* The draft follows the table like a copy: the context factory applies the table's rules
  (site 3), a table switch reaches drafts (site 2), and the ST can set a draft's
  PER-CHARACTER permissions (Q2 — foreign Charms matters BEFORE the lock). Grant XP and
  Unlock refuse a draft (`_rows(drafts=False)` by default).
* **Pages:** PARTY has **Add a character** for every member (the ST too, Q4): pick a
  locked base and Send request, or **Create a character** → the builder. The builder
  shows *"For <campaign>: built under its house rules, and sent to its Storyteller when
  you Finish & Lock."*; its ST Options tab builds no control; Finish & Lock sends the
  request and lands on the base page. The ST tab lists **BEING MADE** with the tune
  button. `/home` shows "For <campaign>" on a draft card.

**Tests:** `tests/test_table_drafts.py` (27), 3 in `test_table_view.py`, 5 in
`test_character_pages.py`. **Mutation-checked (14, all killed):** each access check
(bring, start), the base check of bring, the draft without the table's rules, the
ownership and lock checks of send, the tag kept after send, the tags kept after leave,
the switch skipping drafts, the permission refusing drafts, Grant taking drafts, the
factory ignoring drafts, the lock not sending, the draft's ST tab editable. Targeted run
(table, campaign, character-page, God-Blooded, ST-tab, seam and store files): **619
passed — OBSERVED**; the full suite was not re-run after 6b.

**Design choices made without asking, reversible:** the ST sees drafts in progress
(BEING MADE) — needed for Q2 before the lock; a draft keeps its tag until the lock, so
a player can make one slowly; Add a character is shown to the ST too.

**Then (human, 2026-09-22, "Go ahead"): the Storyteller's own request is approved at
once.** `_insert_request` approves it as the requester, so only the Storyteller of the
table passes `approve`; a failed approval (a full account) leaves it in REQUESTS to
approve by hand. `JoinRequest.approved` tells the page to say "Added to the campaign."
instead of "It waits for the Storyteller." It covers all three paths: the code, Add a
character, and the lock of a draft. 5 tests; the mutations "never approve" and "approve
anyone as the Storyteller" are killed ("approve anyone as the requester" is equivalent:
`approve` refuses a non-Storyteller).

**Grant XP: a checkbox per character (human, 2026-09-22: "Build the checkboxes").** The
target was Everyone OR one character, so the ST could not leave one out (their own
character, an absent player). Now each copy has a checkbox, each ticked at the start;
Grant sends the ticked ids. ⚠ The list is the ticked copies at the DRAW, never "every
copy" at the click: a copy that joins in between gets nothing the ST did not see.
`grant_xp` refuses an empty list ("Tick at least one character.") — `[]` is nobody,
`None` is everyone. The Everyone/one select and `EVERYONE` are gone. 4 tests (3 page,
1 store); 4 mutations killed (the ticks ignored, `[]` as everyone, the boxes unticked
at the start, every copy at the click).

**The Storyteller's own full characters are NPCs (rulings, 2026-09-22).** The human
asked *"could we add a way to distinguish ST NPCs?"* and ruled:
* The word is **NPC**. A copy whose owner is the table's Storyteller carries an **NPC**
  badge wherever it is listed. Keyed on `row.owner_id == tables.storyteller_id` — a
  field the page cannot edit.
* **No NPC group in the rail for now.**
* **Grant XP: an NPC starts unticked.**
* **Shipped, same day:** `_TableView.is_npc`; the badge in YOU PLAY, THE OTHERS, the ST
  tab's CHARACTERS and BEING MADE, and "· NPC" on the Grant checkbox, which starts
  unticked. 4 page tests; 3 mutations killed (never an NPC; "NPC" = the viewer's own;
  the NPC ticked). ✅ **Browser-verified 2026-09-22** ("NPC badge looks good."). Phone width is **not being tested for now** (human, 2026-09-22) — dropped from the owed list, not verified.
* **Step 8: full-character NPCs get the Enemy / Ally switch too** (as the roster's
  `side`, R6), and are filed within the ALLIES / ENEMIES groups. ⚠ A hidden (enemy)
  full character must reach a player's page as nothing at all — the §15.3 projection
  rule applies: today every copy's data is sent to every member's page.

⚠ **Known limit:** if the ST unlocks-then-rejects, or the player unlocks the base while
its request waits, approval refuses it ("Finish and lock…") — the behaviour of any
request today.

### Step 7 — the campaign homebrew layer (ruled 2026-09-23)

**Found before building (2026-09-23):**
* A campaign copy resolved its homebrew only through the OWNER'S library
  (`rulesets.for_account(owner)` in the context factory). Q1 ("no") switches that off, so
  the homebrew it carried in needs another home.
* 🐞 **A side door Q1 did not see:** every save of a copy re-embeds its carried rows from
  the owner's library (`CharacterStore.save` → `embed_definitions(custom_dir=owner)`).
  An owner who edits a homebrew Charm at home changes it on the campaign copy at the next
  save, with no Storyteller.

**Ruled (the human, 2026-09-23, "Yes, build it"), replacing §4's per-character layer and
§4's separate "Add to campaign homebrew" button:**
* **One campaign layer.** A campaign copy sees book → the campaign's homebrew. No
  per-character layer; no owner library (Q1).
* **Three ways in, each through the ST:**
  1. **Approving a character adds the homebrew it carries** to the campaign. The request
     card says so before the click. The ST cannot approve a character and refuse its
     homebrew (its bought Charms would not resolve); they reject, and the player changes
     the character.
  2. **Player proposals.** A member picks rows from their own library and proposes them;
     the ST sees **HOMEBREW REQUESTS**, approves (added) or rejects (dropped).
  3. **The ST authors** on the campaign's Homebrew page, `/table/<id>/custom`. Members and
     watchers read it.
* **An id clash: the campaign's version wins**, and the card flags the difference.
* **A draft for a campaign (6b)** builds under book → campaign → the owner's library; what
  it uses of the library shows on the request card and is added by route 1.
* **The Custom tab is hidden on a campaign copy.** A copy re-embeds its carried rows from
  the campaign layer, never the owner's library (closes the side door).

**Shipped (same day), tests green, NOT browser-verified:**
* **Loader:** `rules_db.with_custom_layers(book, [dirs])` / `reload_custom_layers(rs,
  [dirs])` clear once and merge each folder in order; the first folder wins. A clash with
  an earlier folder says "already defined by an earlier homebrew layer", not "rulebook"
  (Charms, spells, rituals, gear). `reload_custom_layer` is the one-folder case.
* **`server/rulesets.Rulesets`** replaces `home.AccountRulesets`: `for_account`,
  `for_table`, `for_draft(table, user)` (campaign → owner), `for_row`. One per process,
  built in `main.build_server`. ⚠ **The store tells it of each write**
  (`TableStore.homebrew_listeners` / `library_listeners`): the Storyteller's own request
  is approved INSIDE the store, so a reload in a page handler would miss it.
* **The side door:** `CharacterStore.homebrew_dir(row)` — the campaign folder for a copy,
  the library otherwise; `save` embeds from it. The context gets `custom_dir` (embed
  source), `library_dir` (None on a copy: no "Save to my library" on its Gear tab) and
  `reload_library`.
* **Approval** absorbs the base's carried rows into `<table>/custom` (campaign wins);
  `TableStore.homebrew_preview` gives the card's two lines: *"Approving adds to the
  campaign homebrew: …"* and *"Different from the campaign's version, which stays: …"*.
  `campaigns.carried_summary` is gone (replaced by the preview).
* **Leaving, removal, deletion:** each copy's carried rows go into its owner's library
  first (the library wins; a full account logs a warning and the leave still happens).
  *Found while building, not asked:* without this a copy that became solo lost its
  campaign homebrew (⚠ rows). Ruled "Correct" 2026-09-23.
* **Proposals:** `server/table_homebrew.TableHomebrew` — `propose` (a copy of the row +
  its homebrew prerequisites the campaign lacks; refuses a non-member, a row not in the
  library, a row the campaign has, a duplicate), `approve` / `reject` (ST only),
  `withdraw` (own only), `proposals` / `proposals_by`. The Storyteller's own proposal is
  added at once. Stored in `<table>/homebrew_requests.json`.
* **Pages:** `/table/<id>/custom` (`server/table_custom.py`): the ST gets the authoring
  page on the campaign folder (its save reloads every kept stack); members and watchers
  get a read-only list with text; everyone gets FROM YOUR LIBRARY (Propose, or Add for
  the ST) and YOUR PROPOSALS (Withdraw). The table view's top bar has a **Homebrew**
  button (construction icon) for everyone; the ST tab has **HOMEBREW REQUESTS** after
  REQUESTS; the request badge counts both. The THE OTHERS rows read under the campaign
  RuleSet (closes step 3's "known limit").

**Tests:** `test_custom_layers.py` (10), `test_table_homebrew.py` (29),
`test_rulesets.py` (12), `test_table_homebrew_pages.py` (14); one step-1 test rewritten
(`test_a_join_request_writes_nothing_to_the_table` — the old "approval absorbs nothing"
was the superseded design). **Mutation-checked (23, all killed after one test was
added):** approval absorbing nothing; the side door reopened; the factory on the account
rules; a copy keeping a library; leave / delete keeping no homebrew; propose without
access; proposal approval without the ST check; no listeners; approval / proposal /
leave telling no listener; a draft's stack in the wrong order (survived until
`test_the_campaign_wins_a_clash_on_a_draft`); the preview calling everything new; a
proposal overwriting the campaign; `reload_account` skipping drafts; the Gear button
ignoring the flag; a member getting the editor; the page without access; the ST page,
`/home` and the Gear tab each without their reload hook. **Not mutation-checked:** the
table view reading THE OTHERS under the campaign RuleSet (no test drives it).

**Design choices, ruled "Correct" by the human (2026-09-23), all three:** (1) leaving,
removal and deletion put the copy's homebrew in the owner's library, the library winning a
clash; (2) proposals cover Charms, spells and rituals only — gear is carried inline on a
character (decision 0007), and the ST can author campaign gear on the Homebrew page;
(3) a proposed Charm brings its homebrew prerequisites. Also without asking: the
Storyteller's "Add" from their own library is immediate.

⚠ **Known limit:** after a leave, an open page of that copy keeps the campaign RuleSet and
embed folder until its context is rebuilt (a reload after eviction). The homebrew is
already in the owner's library by then.

✅ **Click-through — PASSED 2026-09-24**, all eight steps, with one defect and two
requests, all three fixed and clicked the same day:

* 🐞 **The Storyteller's editor was squished to unreadability.** `ui/custom.build_custom`
  is ONE no-wrap row: a 24 rem list card, the form, a 26 rem JSON card. `/home` gives it
  the full width; `/table/<id>/custom` put it in a `max-w-5xl` (64 rem) column, which
  left the form about 13 rem. The page is now full width.
  `test_the_editor_is_not_in_a_narrow_column` walks the editor's ancestors for a
  `max-w-` class. ⚠ Any new host of `build_custom` has the same trap.
* **Ruled 2026-09-24 — the Storyteller sees what is requested.** A join request card
  has **View character**: the base's full sheet, read-only, in a dialog
  (`chrome.sheet_dialog`, the desktop party screen's `render_sheet` path), drawn under
  `rulesets.for_row(base)`, which is how its owner sees it. Each row the base carries,
  and each row of a proposal, has **View**: a pop-up of the row as the wiki draws an
  entry (`chrome.homebrew_dialog` over the new pure `wiki_view.homebrew_page`, which
  validates the raw rows with the loader's models over a COPY of the campaign RuleSet).
  It shows the COPY the request holds: a proposal's snapshot (a library edit after it
  does not reach it) and, on a clash, the player's version, not the campaign's. A row
  that does not load shows its name, its text and a warning.
  ⚠ `render_sheet` adds a body `<style>` in the page head in the character's splat
  colour. The campaign page keeps its colours only because it sets an INLINE body
  style, which wins. Clicked with that in mind.
* **Ruled 2026-09-24 — a player writes a new row on the campaign's Homebrew page**:
  library + propose (not proposal-only). A member's page has **WRITE A NEW ROW**, the
  `/home` editor on the member's OWN library (`reload_account`, then FROM YOUR LIBRARY
  redraws), so a saved row is offered for Propose with no trip to `/home`. It never
  writes to the campaign folder (asserted). This reverses step 7's "a member getting
  the editor" mutation: the member now has AN editor, on their library, not the
  campaign's; the test became `test_a_member_reads_the_homebrew_of_the_campaign`.
* The proposal card's inline descriptions are gone; its rows have View instead.

Tests: `test_table_homebrew_pages.py` +5 (19), `test_table_homebrew.py` +3 (32, the
presenter). Not mutation-checked beyond the negative runs of each new test before the
code existed.

---

## 15. The table view — the approved layout (2026-09-22)

**The model is `spikes/campaign_page/` shape A, committed as `7f54cf1`.** Its README
has the five rounds with the human's words. This section is the plan built from it. It
**supersedes §7's `/table/<id>` bullets and §11's build order** where they disagree;
§7's `/home` and campaign-copy parts stand.

The human's request was to *"spike a couple different campaign designs; remember it'll
have the whiteboard."* Three shapes were compared: A, a tabletop layout (party rail |
board | log and tools); B, tabs like the builder; and C, a board with a party dock and a
drawer. The verdict: *"A tabletop is the best by far. B is just an absolutely not, C is a
little too cluttered."* Round 5 ended with *"There we go. Perfect."*

### 15.1 Rulings, 2026-09-22

| # | Question | Ruling |
|---|---|---|
| R1 | Layout | **Shape A.** Three columns: the party rail on the left, the board in the centre (P4) and the right rail with **Log / Notes / ST** tabs. |
| R2 | How a player spends motes and marks damage from the table | **Live controls on the viewer's OWN character**, at the top of the rail ("YOU PLAY"). Health boxes cycle on click. Willpower and Limit are click tracks. Each mote pool is a **bar of what is left with − / + at its ends; a click on the bar opens a box to type an amount** (Spend / Regain / Full). The first version, with four buttons per pool, was *"clunky"*. The other characters are read-only. |
| R3 | May the Storyteller change a player's trackers from the table? | **No.** *"ST can tell them if they fucked up."* The Party page's GM-marks-anything does not carry over. |
| R4 | Who sees the adversaries | **The ST only.** This reaffirms §1 (spectators never see the roster). The human first said everyone should see them, then took a friend's advice from more 1E GMing: *"Players should not see any enemy stats by default."* A "let players see it" ST toggle was floated, and the human leans against it: **not built**. |
| R5 | Text chat | **Yes, as ONE Log**: messages and rolls in time order, in the right rail's first tab. It has a text box and a dice count with **Roll**. If the text box holds text when you roll, that text becomes the roll's caption. Left out: player↔ST whispers and unbounded history. |
| R6 | Allied NPCs | **A setting on the roster entry** (`side`: enemy / ally), not a second kind of NPC. |
| R7 | What players see of an ally | **Name and health only.** Stats stay ST-only, as for enemies. |
| R8 | Who marks an ally's trackers | **The ST alone, "for now"**, and the human may reopen it. Linking an ally to the Background that bought it (Familiar, Followers…) is deferred. |

### 15.2 The page, column by column

**Top bar.** `‹ Home › <campaign>` and the viewer's role on the left. On the right is
**Open as: <character> / Spectate** (a member; §7's chooser), the request badge (the
ST), and ⋮. The request badge opens the ST tab.

**Left rail: the party.** `PARTY (n)`, then:
* **YOU PLAY**: the character chosen in *Open as*, with the R2 controls and an ↗ link to
  `/character/<copy>`. Absent when spectating, and absent for a viewer with no copy in the
  table. A member with two copies gets the one they opened as. The other copy is in THE
  OTHERS, and it is still theirs to open.
* **THE OTHERS**: a compact row for each other copy: accent strip, name, player, identity
  line, health strip, motes, and Willpower. Read-only for everyone, **the ST included (R3)**.
* **ALLIES**: every member sees this. A player sees each ally as a name and a read-only
  health track (R7). The ST sees each ally's full roster row, with its clickable health
  and the **Ally / Enemy** switch.
* **ENEMIES**: the ST only, with **+** to add from the catalogue.

**Centre.** The board is P4, and the centre is its place. Before P4 it holds the board's
frame and a "the board comes next" line, and nothing else (Q7).

**Right rail.** **Log** (R5) | **Notes** | **ST** (the ST only). The ST tab takes over step
2's join code, requests, Approve / Reject and members, and it gets each later ST tool:
Grant XP, house rules, campaign homebrew, Roll initiative, New code, Delete.

### 15.3 Mechanics

**Own-character controls go through the live context.** They change the same object that
the owner's `/character/<copy>` page uses: the character registry's context for that id,
built by the same factory if it is not open. This is safe because the viewer OWNS the
character, and §8 forbids a context only for someone else's. ⚠ It is the Grant-XP trap
(§6) again: a write to the file behind an open page is lost at the next auto-save. The
table page and the character page, both open, must show the same marks.
Each handler checks `row.owner_id == user_id` again. The ST gets no handler on a
player's card (R3), and a GMPC (§13 Q4) is the ST's own copy, so it is "YOU PLAY".

**The mote bar** calls `engine/play.set_motes` with `view.spent_motes`. It is the Party
page's arithmetic with a different control; no new calculation.

**The others' rows** read the live context if the copy is open, else the file (§8). The
page's poll repaints a row when its digest moves (§7 "Live").

**The Log** is `log.json` in the table folder (§2.2 gains a row). Each entry holds an id, a
`user_id`, a time, the text, and, for a roll, the count, faces, successes and botch.
* **The server rolls** (`engine/dice.roll`), in the handler. A result that came from the
  browser would be the browser's claim.
* **Bounded:** it keeps the newest **500** entries and drops the oldest on write, with a
  **1,000-character** cap on text. *Design choices, reversible.*
* Every member can post, spectating or not. Spectating is a way of opening the table, not
  a kind of membership (§9.10), so a spectator is still an approved member. The ST posts
  as themselves.
* Its repaint rides the page's existing poll: a length or version check, not a hook.
* The username is resolved at render, never stored, so a later rename shows everywhere.

**Allies and enemies.** `Adversary` gains `side: Literal["enemy", "ally"] = "enemy"`.
The default is the old meaning, so every roster in a `.party.json` loads as enemies.
The desktop Party page and Qt are **not changed**. They are ST-only surfaces, and a
parity port is not wanted (the Qt and webapp design-surfaces rule). The field is
harmless there.
* ⚠ **A non-ST page is built from a projection, never from the `Adversary`.**
  `view.ally_view(adversary) -> (name, marks)` is all that a player's page receives. An
  enemy is never passed in. `set_visibility(False)` and CSS still send the element to the
  browser, and a player can read it in the page source.
* The switch and the ally's health boxes are ST handlers, and each asks `access()`
  again.

### 15.4 The build order, revised

It replaces §11 from step 3. As before, each step is its own commit, with the tests
written first and green before the next.

3. **The table view: shell and party.** Layout A. The top bar with Open as and Spectate.
   The left rail: YOU PLAY with the R2 controls through the live context, the others
   read-only. The right rail's tabs, with the ST tab holding step 2's code, requests and
   members. The live poll. `access()` on every route and handler. The "no longer in
   this campaign" path. The centre is the placeholder (Q7).
4. **The Log.** `log.json`, server-side rolls, the caption rule, the bound, and the poll.
5. **ST tools.** It was step 4: Grant XP (through the live context, plus the award log),
   remove member, new code, delete, and the Adjust XP lockout. **Plus Leave campaign
   for a member** (in ⋮; `TableStore.leave`), deferred here from step 3 by the human. The award could also post
   a line to the Log. *A design choice; it needs no ruling.*
6. **House rules.** It was step 5.
7. **The table homebrew layer.** It was step 6.
8. **The roster on the table.** It was step 7, and now includes `Adversary.side`, the ally
   projection, the two rail sections, and each member's own Notes (Q8). **Plus the
   same switch for the Storyteller's full-character NPCs** (ruled 2026-09-22, §14
   step 6b), filed within ALLIES / ENEMIES.
9. **Initiative for the whole table**, the gate. It was step 8. **Its results go to the
   Log**, which is where every member already looks.

**P4, the board,** goes in the centre column. Decision 0020 applies unchanged: a token is a
picture and a label that someone typed.

### 15.5 Traps added by this section

| Trap | Type | Guard |
|---|---|---|
| Own-character controls writing the file behind an open page | 1 | through the registry context; a test with the character page open that the auto-save keeps a mark made on the table |
| The ST able to change a player's tracker | 3 | no handler on a non-owned card, and the handler re-checks the owner; a test drives the ST's page and asserts the row takes no click |
| Enemy stats or entries reaching a player's browser | — | the non-ST page is built from `ally_view` only; a test walks the player's element tree for any enemy name and any ally stat, **mutation-checked** by building from the `Adversary` |
| A roll result supplied by the browser | — | the handler rolls; a test that the posted entry's faces come from `dice.roll`, not the request |
| Log text rendered as markup | — | `ui.label` only, never `ui.html` or `ui.markdown`; a test posts `<b>` and finds it as text |
| A roll that names itself from a pool | — | 0019: the Log rolls a COUNT. Nothing in the own-character panel may pre-fill the count from a pool. **A "roll my Dex + Melee" button is the thin end.** |
| The Log growing without bound | — | trimmed on write; a test posts 501 |

### 15.6 Open questions from this section

**Q7. What fills the centre before P4? ANSWERED 2026-09-22: a placeholder.** I
recommended the selected character's sheet, arguing that an empty panel would waste the
widest column "for months". The human: *"Don't think it'd be months."* He was right. The
board is costed at 5–7 budget days, which is not elapsed time, and at this pace it follows
step 3 closely. A Sheet tab would be built only to be pushed aside. **The centre holds the
board's frame with a "the board comes next" line and nothing else.** The ↗ on YOU PLAY
already reaches the full sheet.

**Q8. Who writes the Notes tab? ANSWERED 2026-09-22: each member has their own.** The
human: *"Can they each have individual notes?"* Yes. That also removes the problem of
two people typing in one box and overwriting each other. The design:
* **Notes are per member, per campaign:** one text for each user in each table, the ST
  included. They are stored in the table folder as `notes/<user_id>.json` (§2.2's
  `notes.json` becomes this folder).
* **Private: only the writer reads them, the ST included (Q9, ruled).** The Log is the
  shared record. ⚠ Keyed on the ACCOUNT in the handler, not on anything the page sends:
  a test reads another member's notes as the ST and gets nothing.
* **They are written through the table context**, keyed by user id. A user's two devices
  then share one object, as the ST's do (§8), and neither overwrites the other on save.
* **Leaving or removal deletes that member's notes** with the membership. Their character
  copy keeps its own `notes` field (the bio block), which travels with it.
  *A design choice, reversible.*
* Why not use the character's own `notes`? A member can have two copies in one table, or
  none (a spectator). The notes belong to the person at the table, not to a character.

**Q9. Can the ST read a player's notes? ANSWERED 2026-09-22: no.** The human: *"your
conclusion is fine."* The recommendation was **no.** A player's notes are
where they plan things the ST should not see yet. The ST can ask, or the player can post
to the Log.
