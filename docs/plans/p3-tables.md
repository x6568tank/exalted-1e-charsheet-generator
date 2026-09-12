# P3 — Campaigns (the `Table`): design

**Status: DESIGN, 2026-09-12. No P3 code exists.** Every product question the human was asked
is ruled (`vtt.md` §9.1, §9.2, §9.3a, §9.10). Designing turned up **six more questions**
(§13). Those need rulings before the build steps that depend on them — not before step 1.

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
    notes.json           session notes (the Party page had them)
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

Each step is its own commit, tests first, green before the next.

1. **`TableStore` + schema + codes + throttle.** No UI. The whole of §3 and §2.3, with the
   refusals as tests and the ownership / access checks mutation-checked.
2. **`/home` Campaigns**: new, join (code + base or watch), pending. The ST's request list
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
**Q2 the ST.** **Q3 yes.** **Q5 "Maybe? Probably."** — build it as removed, and flag it at the
click-through. **Q4 and Q6 came back as questions** — see the notes under each.

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

**Q5. Is Adjust XP removed from campaign copies?** It follows from ruling 2, but it removes
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
