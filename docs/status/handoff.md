# Session handoff — 2026-09-25 (P4 board + Pools tab + token images: done, clicked, deployed)

# 👉 YOU ARE HERE

**P4 (the board) is DONE and BROWSER-VERIFIED by the human, 2026-09-25**, and so are the
two additions asked for after it: the table's **Pools** tab and **token images**
(*"Everything looks good."*).

* The board: `docs/plans/p4-board.md` (§5 rulings, §8 build log, the click-through
  additions: colour → Pen, multiselect, right-drag pans / left-drag boxes, token images).
* The Pools tab: `docs/plans/p3-tables.md` §14 "The Pools tab". A player sees the pools
  of the copy they open as; the ST picks from their NPCs and every player's copy.
  Decisions 0016 and 0019 are unchanged: no row rolls itself.
* Campaign folders are 50 MB; accounts stay 10 MB. The Log's Enter sends its text with
  the key event.
* 🐞 Carry: an icon name missing from NiceGUI's font draws as invisible overflowing
  text that steals hover (`ink_eraser`). No test catches it; sweep in a browser.

**Full suite: 4294 passed + 1 skipped — OBSERVED** at this close-out (20 min), after all
of the above. P3's close-out was 4192 + 1 skipped.

**Working tree:** clean after the close-out commit; pushed to `origin/main`.

**Deployed (2026-09-25):** `6c8658d` is LIVE on `https://exalted.x6568tank.com`, rebuilt by `claude` with `exalted-rebuild`. Checked from outside: `/`, `/wiki`, `/login` 200; `/home` and the new `/table/…/board-token/…` route send a visitor to login; the log says NiceGUI ready.

🖱 **Owed:** nothing.

❓ **Open for the human:** nothing.

**Next:** open. P0–P4 of `vtt.md` are done.

---

## The session before — P4 built (2026-09-25)

Steps 1–4 built and driven in a browser by me; the human's click-through followed the same day (above).

---

## The session before — P3 step 9 clicked (2026-09-25)

Step 9 browser-verified; P3's gate met. Full suite 4192 passed + 1 skipped, observed. `f6d8c56` deployed. Detail: `p3-tables.md` §14 "Step 9".

---

## The session before — P3 step 9 built (2026-09-24)

Step 9 built, committed and pushed as `dd997e5`; the full suite was stopped at ~18
minutes and first completed on 2026-09-25 (4177 passed + 1 skipped). Detail:
`p3-tables.md` §14 "Step 9".

---

## The session before — P3 step 8 clicked (2026-09-24)

Step 8 (the roster, the NPC sides, the Storyteller view) DONE and BROWSER-VERIFIED,
deployed as `555688e`; the navigate/notify flake fixed in `tests/conftest.py`. Suite then:
4148 passed + 1 skipped, observed. Detail: `p3-tables.md` §14 "Step 8".

---

## The session before — P3 step 7 clicked; the request views; the login name (2026-09-24)

**P3 step 7 (the campaign homebrew) PASSED its click-through on 2026-09-24**, all eight
steps. The click-through found one defect and two requests; all three are built, tested
and **browser-verified the same day**. `docs/plans/p3-tables.md` §14 "Step 7" is the
record (the click-through paragraph is at its end).

* 🐞 **The Storyteller's editor on `/table/<id>/custom` was squished to unreadability.**
  `build_custom` is one no-wrap row of two fixed cards and the form; the page put it in a
  64 rem column. The page is full width now. ⚠ Any new host of `build_custom` has the
  same trap (a test walks the ancestors for `max-w-`).
* **Ruled 2026-09-24 — the ST sees what is requested:** **View character** on a join
  request (the full sheet, read-only, in a dialog), and **View** on each carried or
  proposed homebrew row (a pop-up of the row as the wiki draws it, from the COPY the
  request holds). New: `chrome.sheet_dialog`, `chrome.homebrew_dialog`, the pure
  `wiki_view.homebrew_page`.
* **Ruled 2026-09-24 — a player writes a new row on the campaign's Homebrew page:**
  library + propose. A member gets **WRITE A NEW ROW**, the `/home` editor on their OWN
  library; a saved row appears at once in FROM YOUR LIBRARY with Propose.
* **The login name** (the human: *"There's no way to see who you're logged in as"*),
  ruled menu AND top bar: **"Logged in as <name>"** in the site menu, **"<name> · Log
  out"** in the top bar and in the ⋮ menu of the builder and campaign pages. One source,
  `server/nav.py`. Record: `docs/plans/vtt.md` §9.7, after the site menu.

**Also this session:** the other machine's wiki commit (`03fdb22`, seven reference
sections) was merged with step 7 (`7869480`, no conflicts) and pushed.

**Full suite: 4109 passed + 1 skipped — OBSERVED** on the dev machine at this close-out, after all of
the above. ⚠ The count moves by machine and optional dependency (`docs/testing.md`).
⚠ `test_table_view.py::test_a_character_that_joins_after_the_form_is_drawn_is_not_granted`
failed 3 times in about 20 runs mid-session (the second user's sign-up timed out before
`/home`), 0 in 42 runs without the login-name change, then passed 43 runs in a row with it.
Not explained; watch for it.

**Working tree:** clean after this session's one commit (the login name, the step-7
follow-ups and these docs, on top of the merge `7869480`), pushed. Check `git status`.

**Deployed (2026-09-24):** `c7153ec` is LIVE on `https://exalted.x6568tank.com` (checked
from outside: `/`, `/wiki`, `/login` 200, `/home` → login; the log says NiceGUI ready). The
laptop now has its own deploy key, and `claude` can run the rebuild itself; see
`docs/deploy/homeserver.md`. ⚠ **The repo is PUBLIC**: that doc must never gain access
rules or secrets (the human, 2026-09-24).

🖱 **Owed:** nothing from P3. The click-through server ran from `/tmp/exalted-click8/`
(accounts `storyteller`, `alice`, `bob`, `watcher`, password `clickthrough`).

❓ **Open for the human:** nothing.

**Next:** P3 **step 8**, the roster on the table, with the Enemy / Ally switch for roster
entries AND for full-character NPCs (ruled).
---

## The session before — P3 step 7 built (2026-09-23)

Step 7 shipped and deployed: one campaign homebrew layer, `<table folder>/custom`; a copy
sees book → campaign, a draft book → campaign → the owner's library; rows come in by
approval of a carrying character, by player proposal, or by the ST authoring. 🐞 Closed:
a copy's save re-embedded homebrew from the OWNER'S library (`CharacterStore.homebrew_dir`).
⚠ The store notifies the RuleSets of each homebrew write (`homebrew_listeners` /
`library_listeners`). Suite then: 4080 passed + 1 skipped, observed. Detail: `p3-tables.md`
§14 "Step 7".

---

## The session before — P3 steps 6 and 6b closed out (2026-09-22/23)

**P3 steps 6 and 6b are DONE and BROWSER-VERIFIED** (human, 2026-09-22: click-through
steps 1–11 "works"; "NPC badge looks good."). **The request-card house-rules warning**,
built after that click-through, **passed its own click-through on 2026-09-23** (steps
1–5 "works"). Phone width was
not tested (human: "we're not testing for phone width right now"): not verified, and
not owed. **`docs/plans/p3-tables.md` §14 "Step 6" and "Step 6b" are the record.**

In one breath:
* **Step 6, house rules:** the table's `house_rules.json` (TABLE-WIDE fields only);
  `apply_table_rules` at approval, at the ST's switch (through `peek`, the table file
  first) and in the context factory. The ST tab has HOUSE RULES (a switch posts to the
  Log) and a **tune** button (sliders icon) per character for its PER-CHARACTER
  permissions (Q2). A campaign copy's ST Options tab builds **no control**.
* **Step 6b, add a character from the campaign** (the human asked, then ruled
  "Correct."): **Add a character** in PARTY brings a locked base (a request from the
  membership, no code) or **creates a draft for the campaign** (`campaign_drafts`, a
  new DB table), built under its rules. Finish & Lock sends the request. The ST sees
  drafts under BEING MADE and can grant them permissions.
* **Then, on the human's rulings:** the Storyteller's own request is **approved at
  once**; **Grant XP has a checkbox per character**; a copy owned by the Storyteller
  has an **NPC** badge and starts **unticked** in Grant XP; the ST's request card says
  **"ST house rules are different on this character"** and lists each TABLE-WIDE rule
  that differs.

🐞 **Found on the way:** `merits.inheritance_free_rating` priced God-Blooded Inheritance
from the LIVE house rules on a locked sheet; every other creation toggle reads the
snapshot. Step 6 made it reachable. Fixed, with a read test (§14 "Step 6").

**Full suite: 3959 passed + 1 skipped — OBSERVED** on the dev machine after step 6
only. **Not re-run after 6b** (a close-out run was stopped at the human's request).
After the last change, the table, campaign and character-page files: **300 passed —
OBSERVED**. Step 6b and the later rulings add about 50 tests; the full count after them
is not observed. ⚠ The count moves by machine and optional dependency (`docs/testing.md`).

**Working tree:** clean, committed on `main` and **pushed** (`b3eb99a`, `a3c9528`, and this close-out commit). Check `git status`.

✅ **Click-through (request-card warning) — PASSED 2026-09-23**, all five steps: a
base made without a switched-on table rule shows the heading and
`Magic for Everyone: Off (campaign: On)`; a base that agrees shows nothing; two
differing rules list both. The server ran from `/tmp/exalted-click7/` (same accounts,
password `clickthrough`) and is stopped.

❓ **Open for the human:** nothing from this session.

**Next:** P3 **step 7, the table homebrew layer** (§4 / §15.4): `with_custom_layers`,
`TableRulesets`, the campaign Custom page, "Add to campaign homebrew", the no-absorb
test. ⚠ Q1 is ruled **no**: a campaign copy stops seeing the owner's library — the
context factory still hands it `rulesets.for_account(owner)` today. ⚠ A draft for a
campaign (6b) must get the table layer too: it uses the same factory branch
(`row.table_id or tables.draft_table(row.id)`). Then **step 8**: the roster on the
table, with the Enemy / Ally switch for roster entries AND for full-character NPCs
(ruled). **Steps 2–6b are not deployed**; deploy when the human asks.

---

## The session before — P3 step 5, the ST tools (2026-09-22)

**P3 step 5 is DONE and BROWSER-VERIFIED** (human, 2026-09-22: all nine steps "Correct"). `docs/plans/p3-tables.md`
§14 "Step 5" is the record: what shipped, the mechanics, 16 mutations (all killed), the
design choices made without asking, the known limits.

In one breath: new `server/table_st.py` (`TableStoryteller`: `grant_xp`, `awards`,
`unlock`; the award log is `<table folder>/awards.json`). The ST tab gains New code,
GRANT XP (Everyone or one character, a note; posts a Log line), AWARDS, MEMBERS with
Remove, CHARACTERS with Unlock (Q6), Delete campaign (confirm names the member count).
A member has **Leave campaign** in ⋮. A campaign copy's `/character/<copy>` page builds
**no Unlock, no Adjust XP, no Downtime…** (keyed on `row.table_id`). 🐞 The quota
message now says "This campaign" for a table folder (it said "This account").

⚠ Grants and unlocks go on the live object (`sessions.peek`) and save the file from it.

**Full suite: 3921 passed + 1 skipped — OBSERVED** (3878 + 43) on the dev machine, once, after all of step 5
(the human asked for one run at the end). ⚠ The count moves by machine and optional
dependency (`docs/testing.md`).

**Working tree:** clean, committed and **pushed** (this handoff is in the step-5 commit).
Check `git status`. **Not deployed** (steps 2–5); deploy when the human asks. The
click-through server may still be running on :8080 from `/tmp/exalted-click/`.

✅ **Click-through (step 5) — PASSED 2026-09-22.** **Q5 answered: yes**, Downtime… included.
The server ran from `/tmp/exalted-click/` (throwaway DB, seeded accounts). For the record:
1. As the player, open `/character/<copy>`: the Edit tab says *"The Storyteller grants
   XP in this campaign."*; no Adjust XP, no Downtime…, no Unlock in the top bar.
   **Q5 flag:** is removing Adjust XP right? And Downtime… with it (a choice I made)?
2. Keep that page open. As the ST, Grant 5 XP to Everyone with a note. The ST sees the
   award; both see `+5 XP to … — note` in the Log. The player switches tab: 5 XP.
3. Grant −2 to one character only. The other is unchanged.
4. ST: Unlock the copy (a character that spent XP shows the warning). The player
   reloads: the builder is in creation mode with Finish & Lock.
5. ST: New code — the old code no longer joins.
6. ST: Remove a member — their open table page says "You are no longer in this
   campaign."; their copy on `/home` is now solo and has Adjust XP again.
7. As a member, ⋮ → Leave campaign → lands on `/home`.
8. ST: Delete campaign — the confirm names the member count; lands on `/home`.

**Next:** P3 **step 6, house rules** (§15.4 / §5): `house_rules.json`, `apply_table_rules`
at the three sites, the ST's TABLE-WIDE switches, read-only on campaign copies.

---

## The session before — P3 step 4, the Log (2026-09-22)

**P3 step 4 is DONE and BROWSER-VERIFIED** (human, 2026-09-22: *"everything looks good!
no issues on my end now and everything in the clickthrough passed"*), the health labels
included. **`docs/plans/p3-tables.md` §14 "Step 4" is the record**: what shipped, the
mechanics, 10 mutations (all killed), the design choices made without asking.

In one breath: new `server/table_log.py` (`TableLog`: `entries`, `version`, `post`,
`roll`, kept in `<table folder>/log.json`); the Log tab of `/table/<id>` has the entries,
a text box, a Dice count, **Roll** and **Send**. The server rolls (`engine/dice.roll`);
Roll takes the text box as its caption; the newest 500 entries; 1,000 characters; the
ST, players and watchers post; `access()` in the store AND the handler; the 2 s poll
appends new entries. ⚠ `version()` is the **newest entry id**, not the file's mtime and
size, which can miss a post once the Log is full.

**Asked after:** the health box labels (-0 / -1 / -2 / -4 / Incap, ★ for a Charm level)
are now on YOU PLAY and THE OTHERS, from `PlayHealthBox.label`. Browser-checked.

**Design choices made without asking, reversible** (§14 Step 4): a count of 0 is
refused; no TN or 10s/botch switches in the Log (R5 names a count only); times are the
server's local HH:MM; the count box starts empty; no paging of the 500.

**Tests:** `tests/test_table_log.py` (21) + 11 in `test_table_view.py` (10 Log, 1
labels). **Full suite: 3877 passed + 1 skipped — OBSERVED** on this machine after all of the
Log work, BEFORE the labels commit (`da6d389`). ⚠ **The full suite was NOT re-run after
the labels commit**: a close-out run was stopped at 55% (green so far) because the
laptop had to leave. The labels change was checked by `tests/test_table_view.py`
alone (43 passed). **3878 + 1 skipped is COMPUTED**, not observed. Run the full suite
once at the start of the next session before building on it.
⚠ The count moves by machine and optional dependency (`docs/testing.md`).

**Working tree:** clean, committed and **pushed** at close-out (this handoff is the last
commit). Check `git status`.

✅ **Click-through (step 4) — PASSED 2026-09-22**: a message and a roll across two
accounts, the caption rule, `<b>` shown as text, the look at narrow width, removal
stopping the page, and the health labels.

**Next:** P3 **step 5, ST tools** (§15.4): Grant XP through the live context + the
award log (⚠ the §6 / §15.3 trap: a write to the file behind an open page is lost at the
next auto-save), remove member, new code, delete, the Adjust XP lockout on campaign
copies, and **Leave campaign** for a member (in ⋮; `TableStore.leave`). The award could
also post a line to the Log (a design choice). **Steps 2–4 are not deployed**; deploy
when the human asks. The click-through server may still be running on :8080 from
`/tmp/exalted-click/`.

---

## The session before — P3 step 3, the table view (2026-09-22)


**P3 step 3 is DONE and BROWSER-VERIFIED** (human, 2026-09-22: *"It works. No notes."*). Committed.
`/table/<id>` is now layout A: `server/table_view.py` (new; step 2's page body moved out
of `campaigns.py`). **`docs/plans/p3-tables.md` §14 "Step 3" is the record**: what
shipped, the mechanics, 8 mutations (all killed, one after a fix), the design choices
made without asking, and two known limits.

In one breath: top bar with **Open as / Spectate** (remembered per browser) and the ST's
request badge; **YOU PLAY** with health, mote bars (− / + / click to type), Willpower and
Limit/Clarity/Paradox tracks, all written through the character registry's live context
and saved on each click; **THE OTHERS** read-only for everyone (R3), read with the new
`SessionRegistry.peek` so no context is built for another account; the board frame in the
centre; **Log** (placeholder) / **Notes** (MEMBERS) / **ST** (code, requests); a 2 s poll
that repaints what moved and replaces the page with *"You are no longer in this
campaign."* when `access()` goes.

🐞 Fixed on the way: `PartyCardView.identity_line` said `" Caste · Mortal"` for a
casteless character (shared by the Party page and Qt).

Asked after: **a Mortal with Essence Merits** gets exactly the bars the engine gives
(Awareness/Awakened → Personal; Beacon → one bar; Aura → both). The Essence Awareness
"N may be spent freely" note was missing; it is now `view.free_motes_note`, one string for
the web Play tab, the Qt Play tab and the table view (§14 Step 3).

Then an audit against the Play tab (§14 Step 3 has the list). 🐞 Three defects fixed:
YOU PLAY's Limit track ran to 10 regardless of Greater Curse / permanent Resonance;
**the web and Qt Party pages had the same 10**; and **the Qt Party card's Limit and
Willpower tracks were off by one** (a click on the first box of an empty track did
nothing). YOU PLAY gained armour fatigue and the Clarity band. Luck, the Great Geas and
box labels stay behind ↗. **Leave campaign is deferred to step 5** (the human).

**Tests:** `tests/test_table_view.py` (32) + 2 `peek` + 1 identity-line + 2 free-note
+ 2 Qt party + 1 web GM cases. **Full suite: 3846 passed + 1 skipped — OBSERVED** on this
machine after all of it (3806 + 40). Reused at close-out: only a comment and docs changed since. ⚠ The count
moves by machine and optional dependency (`docs/testing.md`).

**Working tree:** clean, committed and **pushed** (`669ce5b` and this close-out). Check `git status`. Steps 2–3 are not deployed.

✅ **Click-through (step 3) — PASSED 2026-09-22**, all six steps: the look and narrow
width, the mote menu, Limit 7 / fatigue / Clarity, one character in two tabs, live repaint
across accounts (the ST cannot mark a player), removal stops the page.

**Next:** P3 **step 4, the Log** (§15.4): `log.json`, server-side rolls, the caption
rule, the 500 bound, the poll. Steps 2–3 are not deployed; deploy when the human asks.

---

## The session before — the campaign page layout (2026-09-22)

**The layout of the P3 table view is APPROVED, and the plan is written.**
`spikes/campaign_page/` compared three shapes. The human took **A, the tabletop
layout** (party rail | board | Log / Notes / ST), then refined it over five rounds.
Commit `7f54cf1` has the spike, and its README has each round in the human's words.
**`docs/plans/p3-tables.md` §15 is the plan**: rulings R1–R8, the page column by
column, the mechanics, the **revised build order (§15.4, which replaces §11 from
step 3 on)**, the new traps, and two open questions.

The rulings in one line each: own-character live controls (a mote BAR with − / + and
type-an-amount); **the ST does not edit players' trackers**; **enemies are ST-only**
(no show-players toggle); **one Log** of messages and rolls, where the text box
captions a roll; **allies are a `side` setting** on a roster entry, and players see
an ally's name and health only; **only the ST marks allies**, "for now".

**§15.6 answers (2026-09-22):** **Q7**: the centre is a placeholder until the board.
My sheet-tab idea rested on "for months", which was wrong. **Q8**: **each member has
their own notes** (`notes/<user_id>.json`, through the table context). **Q9**: the ST
cannot read a player's notes (ruled: *"your conclusion is fine"*). **§15 has no open
question left.**

**Next:** P3 **step 3** (§15.4): the shell, the party rail with YOU PLAY through the
live context, the poll, the no-longer-member path, and the placeholder centre.
No code changed this session, so the suite was not run. Everything is **pushed**.
Step 2 is still not deployed.

---

## The session before — P3 build step 2, the campaign pages (2026-09-12)

**P3 build step 2 is DONE and BROWSER-VERIFIED** (human, 2026-09-12: *"everything looks
good!"* — and *"the campaign window will probably need to be redesigned at some point,
but it's fine for now"*; step 3 is where that redesign goes). `/home` has a CAMPAIGNS
section (New campaign, Join a campaign with code + base or "just watch", the waiting list
with Withdraw, a **Join** shortcut on each base card), and `/table/<id>` is a bare page:
characters and members for everyone, plus the join code and Approve / Reject for the
Storyteller. **`docs/plans/p3-tables.md` §14 "Step 2" is the record** — what shipped, 8
mutations (all killed), the design choices made without asking.

**Tests:** `tests/test_campaign_pages.py` (21) + 3 in `test_table_store.py`. Targeted run
(campaign, character, store, gate, server-main, homebrew, seam files) **218 passed —
OBSERVED**, before the shape case was added. **Full suite: 3806 passed + 1 skipped — OBSERVED** on this machine after all of step 2
(the shape case included). ⚠ The count moves by machine and by optional dependency
(`docs/testing.md`); ⚠ `bcrypt` is optional, and without it the page files skip whole.

**Working tree: COMMITTED** — step 2 is the commit titled *"P3 step 2: …"*. New
modules `server/campaigns.py` and `server/chrome.py` (the top bar and the character card
moved out of `home.py`). `main` is 4 commits ahead of `origin`, **unpushed**. Not
deployed. Check `git status`.

🐞 **Found on the way:** step 1's *"`leave` as withdraw"* is wrong for a MEMBER — it takes
them out of the campaign. `TableStore.withdraw` cancels one request. §14.

✅ **Click-through (step 2) — PASSED 2026-09-12**, all seven steps below. The server ran
from `/tmp/exalted-click/` (throwaway DB, fixed secret). For the record:
1. A: `/home` → **New campaign** "Test" → lands on `/table/<id>` with a JOIN CODE.
2. B: make and lock a character; on its card press **Join**, type A's code in lower
   case, Send → WAITING FOR THE STORYTELLER (1) with **Withdraw**.
3. A: reload `/table/<id>` → REQUESTS (1) names B and the character → **Approve** → the
   copy appears under CHARACTERS, B under MEMBERS.
4. B: reload `/home` → the campaign card ("Player", "Your characters: …"); the copy card
   says "· In Test"; the copy opens in the builder.
5. B: **Join a campaign** → "Just watch" with the same code → refused ("already in").
6. A third account opening A's `/table/<id>` URL → "There is no such campaign."
7. A's `/home` card shows the code and "1 request waiting" while one waits.

**Next:** P3 **build step 3** — the table view: the Party page's cards, open-as /
spectate, the live poll, the "no longer in this campaign" path. It is also the
**redesign of the campaign page** the human flagged — spike it, screenshot it, iterate
(`match-the-builder-look`). Step 2 is not deployed; deploy when the human asks.

## The session before — P3 build step 1, `TableStore`

**P3 build step 1 is DONE, tests green, no UI** — so there is nothing to click.
`server/tables.py` (`TableStore`: create, access, request, approve, reject, leave, remove,
delete, new code, the join throttle), the `tables` / `memberships` / `join_requests`
schema, and `CharacterStore.make_copy(..., table_id=)`. **`docs/plans/p3-tables.md` §14 is
the record**: what shipped beyond the §3 table, the 12 mutations (all killed), and the
design choices made without asking.

**Tests:** `tests/test_table_store.py`, 56 cases. **Targeted run 266 passed, 0 skipped —
OBSERVED** (the new file with the character-store, character-pages, account-homebrew,
user-db, quota, throttle, server-main, auth-gate and seam files). **The full suite was not
re-run** (the human's targeted-tests rule). Last full count: 3721 + 1 skipped computed
after item 8 of the previous session; the unlock-warning commit `0f3466f` added cases to
three files that were never counted into it, so the next full run is the first real number.
⚠ The count moves by machine and by optional dependency (`docs/testing.md`); ⚠ **`bcrypt`
is optional**, and without it several server files skip whole.

**Working tree: clean and COMMITTED** — step 1 is the commit titled *"P3 step 1: the
campaign store…"*. `main` is 3 commits ahead of `origin`, **unpushed**. `.nicegui/` is
untracked noise. Check `git status`.

🐞 **Found on the way:** the design said the join form is "rate-limited the way login is".
Done literally, that ships a bypass — login clears the count on success, and the join
count is keyed by the ASKING account, which always knows one correct code (its own
campaign's). `JoinThrottle` counts every attempt and never clears. p3-tables.md §14.

**Deployed:** `4a614bb` is on `gilserver`. The schema change is `IF NOT EXISTS` only, so a
deploy adds the empty tables at start with no migration.

**Next:** P3 **build step 2** — `/home` Campaigns (new, join with code + base or watch,
pending), the ST's request list on a bare `/table/<id>`, approval makes the copy. The store
already has every call step 2 needs (`pending`, `requests_by`, `leave` as withdraw).
⚠ `access()` in every page body AND every handler (p3-tables.md §3, §12). Friends'
feedback on the new look may come first.

## The session before — piece 4, the navigation pass, the P3 design

**2026-09-12, third session.** §5 piece 4 (the character store, `/home`, per-character
pages, base / campaign copy) DONE, deployed and clicked — `vtt.md` §9.8, rulings §9.3a.
Per-account homebrew built (`hosting-state-model.md` §5.3). 🐞 The hosted Load dialog took a
server path — closed, §5.1d. ⚠ **A hosted control must never take a path from the browser.**
The navigation and look pass approved (`vtt.md` §9.9). P3 fully ruled (`vtt.md` §9.10) and
designed (`docs/plans/p3-tables.md`), its §13 Q1–Q6 answered. Unlock after XP ruled:
allowed with a warning, built in both shells (`0f3466f`).

---

## The session before — the public pages

**2026-09-12, second session: the public pages SHIPPED, tests green. The human approved
the LOOK (*"a lot more in line with the rest of the site, I like it"*); the functional
click-through steps below are not yet confirmed.** `/` (front page), `/about` (Lorem Ipsum for now) and `/wiki` (Charms, Martial
Arts, Spells, Merits & Flaws, Backgrounds — list + entry pages, search, filters) are plain
server-rendered HTML with no login. The hosted builder moved to **`/home`**, and a login
with no target lands there. **`vtt.md` §9.7 is the record.** Earlier the same day: the auth
click-through passed (§5.1d) and the site map was ruled (§9).

Last FULL suite: **3668 passed + 1 skipped** — OBSERVED 2026-09-12 after this work.
Preflight then added two cases to `test_public_pages.py` (the render sweep, and the
party page's **Builder** → `/home` round trip, mutation-checked), run with the seam, gate
and party-page files (546 passed). **3670 passed + 1 skipped OBSERVED** on the full
suite after the restyle, before the commit. Then `test_each_public_page_answers_head`
(the deployed `curl -I` gave 405): **3671 computed.**
**The arithmetic agrees:** 3637 (computed, previous handoff) + 20 `test_public_pages.py`
+ 11 net in `test_auth_gate.py` (two enumeration cases for one, six prefix cases, the
dot-segment case, three more redirect-target cases) = 3668.
⚠ The count moves by machine and by optional dependency — see `docs/testing.md`, and do
not reconcile this against another machine. ⚠ **`bcrypt` is optional**: without it the
auth test files skip, and so does one case of `test_public_pages.py`.

**Working tree:** clean and **pushed** 2026-09-12 (`5dfa31e` and the doc commit after it).
The server copy is `5dfa31e`; the human rebuilds to pick up the Lorem Ipsum About page. Check `git status`.

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
* The About prose is **Lorem Ipsum by the human's choice** (*"feel free to change it to Lorem Ipsum for now"*, 2026-09-12); the contact line and the
  unofficial-fan-site notice are real. The human writes the text.
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

- **Make the signup and login pages look good** (human, 2026-09-22). `/login` and
  `/signup` (`server/auth.py`) are still the plain forms from §5 piece 3. Follow
  `match-the-builder-look`: copy the builder's design, spike, screenshot, iterate.
- **The About text** is Lorem Ipsum until the human writes it (`server/public.py`).
- ✅ **DEPLOYED 2026-09-12 to `https://exalted.x6568tank.com`** (commit `7cd594f`,
  checked from outside). ✅ **A real signup in the human's browser worked**, and a
  name change survived leaving — so the websocket crosses the Cloudflare Tunnel and the
  hosted save writes through. `claude` now logs in to the server by key
  (`~/.ssh/id_ed25519_gilserver_claude` on the dev machine).
- **Deploy to `gilserver`** — `docs/deploy/homeserver.md` has every step. `Dockerfile` +
  `.dockerignore` are new and the image was built and probed locally (front page, wiki,
  `/home` → login, `__Host-` cookie, database owned by uid 1000). HTTPS is the existing
  Cloudflare Tunnel; the container is published on `127.0.0.1:8090` only. The `claude`
  account on the server has no `docker`/`sudo` on purpose, so the build, the Compose
  entry and the tunnel rule are the human's to run.
- **Wiki sections not yet shown**, all in `data/`, same pattern: trait text, the
  ST-screen tables, artifacts, thaumaturgy, the Dragon-King Paths. Plus `robots.txt` and a
  sitemap once the public base URL is settled, and a Wiki link in the logged-in builder.
- **§5 piece 4 — the DB.** ✅ §5.3's per-account homebrew is measured, ruled and
  built (this session, top of file). What is left is the DB layout itself.
  ⚠ **The layout grew on 2026-09-12** — several characters, base characters, tables,
  pending memberships: `vtt.md` §9.3. Both base-character questions are ruled (§9.2):
  a base change reaches **later copies only**, and a copy **can** exist with no campaign.
- **Backgrounds `source` — 51 of 63 DONE. 12 left, and they need a human with a page.**
  `status/backgrounds.md` lists all 12 with their scores. Two are Lunar and have no
  page-marked text on this machine at all. ⚠ **Do not lower the matcher threshold to
  clear them.**
- ✅ **Roll initiative for the whole table — DONE 2026-09-25** (P3 step 9, the gate).
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
become stacked rows. Then log in: it lands on `/home`; `/` now says **Your characters**;
**Log out** lands on `/`.

**Piece 4 (new 2026-09-12)** — logged in, at `http://localhost:8080`:
1. `/home` shows CHARACTERS (0) and CAMPAIGN COPIES (0). **New character** opens
   `/character/<id>` in the builder; the top bar has **Home**, and no Party, New or Load.
2. Name it, wait 5 s (auto-save) or press Save, press **Home**: it is listed as **Draft**.
3. Open it, **Finish & Lock**: the page becomes the read-only **Base** page (sheet, no
   tabs). **Make a campaign copy** opens the copy in the builder (locked, XP mode).
4. `/home` lists the base as **Base** and the copy as **Copy of <name>**.
5. **Unlock to edit** on the base returns it to the builder.
6. **Import a .character.json** on `/home` (use a Download a copy file) makes a new
   character; homebrew it carries appears on that character's Custom tab.
7. **Delete** the base: the confirm names it; the copy stays, "Its base is deleted".
8. A second account cannot open the first account's `/character/<id>` URL: "There is
   no such character."
9. `/gm` answers 404 on the server.

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
