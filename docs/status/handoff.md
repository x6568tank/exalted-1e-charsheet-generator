# Session handoff — 2026-08-20 (the comment pass finished, and the `ui/` audit)

# 👉 YOU ARE HERE

**GREEN — 2,455 passed, 1 skipped, 1 warning** (this machine, 2026-08-20).

```
.venv/bin/python -m pytest -q     # expect: 2,455 passed, 1 skipped, 1 warning
```

**State: one commit (`ea0df0e`) pushed; a second batch of prose edits is UNCOMMITTED in
the working tree** — 17 source files plus `tests/test_merits_flaws.py`. See "What is
uncommitted" below before you commit or discard.

⚠ The 1 SKIP is conditional and healthy:
`test_buy_merit_prices_the_tier_against_the_characters_own_menu` skips when no tier
exists that is generic-but-not-Solar. A guard against a bug shape, not a disabled test.

⚠ **The 71-entry M&F deferral WARNING is expected** and is not a failure — the
Godblooded chapter markdown is not present on this machine. CLAUDE.md says neither
outcome of `test_every_description_matches_the_source_text` is a regression. **Not
something to fix.**

## What happened: the comment pass now covers the whole build

The 2026-08-17 standard (docstring = input, output, mechanism; page citations and ⚠
traps stay; narration goes to the commit log) has been applied to everything. Last
session did `engine/validate/`; this session did the rest.

| Area | Prose lines | Share |
|---|---|---|
| `models/` | 2,622 | 61.7% → 61.3% |
| `engine/` outside validate | 2,492 | 38.2% → 38.0% |
| `ui/` | ~3,650 | 24.8% |

⚠ **Judge it by what the prose IS, not by line count** — the percentages barely moved,
which is the same outcome validate's 35%→34% had and is correct. Most of what came out
was narration with a live trap buried in it, and the trap came back as an explicit ⚠.

`tools/prose_guard.py` is the method and it earned itself twice more: it caught a
dropped `PG pp.120-122` citation in `models/rules.py`, and it flagged every file where a
string literal changed (see below) instead of letting them pass as prose.

## The `ui/` audit — the part worth reading

`ui/` was first swept by grepping for dated narration markers. That was **not enough**,
and the line-by-line audit afterwards is where the real findings were. The dangerous
class is **prose that is calmly wrong in the present tense** — it reads exactly like
correct prose and no marker sweep sees it.

### Five user-facing strings pointed players at a tab that does not exist

Decision 0013 deleted the XP tab. Fourteen references survived it; nine were comments,
**five were on-screen text**:

| Where | Said | Truth |
|---|---|---|
| `storyteller.py` | "Use Unlock on the XP tab" | Unlock is on the **top bar** |
| `play.py` | shed permanent Resonance "on the XP tab" | the **Edit** tab |
| `combos.py`, `picker.py` ×3 | "Undo a purchase on the XP tab" | Edit tab's **Experience card** |

### `picker.py` claimed Cytoscape loads from a CDN

> "Cytoscape is loaded from a CDN, so the browser needs network access."

It is **vendored** — `ui/vendor/cytoscape.min.js` (373 KB), inlined by
`ui/assets.py`, whose own docstring says "no CDN dependency" so the packaged build works
offline. The two files contradicted each other outright, and the user-facing failure
message blamed the network too. Both corrected. ⚠ **Never reintroduce a CDN here.**

### Thirteen stale counts, all checked against live data

Mostly rotted when the 1.0 catalogue sweep grew the data underneath them:

`222 artifacts → 330` · `twenty dual-catalogue names → 31` · `1,470 Charms → 1,861` ·
`52 health-cost Charms → 54` · `36 of 78 Mountain Folk → 50 of 94` · `56 Arcanoi → 127` ·
`six ghost paths → 14` · `19 Gifts → 22` · `79 of 80 spirit Charms → 89 of 90` ·
`99 M&F → 170` · `56 of 122 gear rows → 68 of 140` · `46 of 232 untiered MA Charms → 6` ·
`eight of 19 untiered styles → 0 of 21`

⚠ Each was replaced with **the invariant it was illustrating**, not a fresh number.
They rotted once and would rot again. Do not re-add inventory counts to prose.

### Two smaller classes

* **An orphaned comment.** `play.py` carried the two-column layout note above
  `def tracker()`, 180 lines from the row it describes (an accurate copy already sat in
  the right place). Found by sweeping for near-duplicate comment blocks; it was the only
  one in the package.
* **Stale forward-looking references.** "the picker is the next slice" (shipped as
  `ui/picker.py`), "arrive here in P3" (already there), "Phase 2 has not reached the
  eighteen styles" (**one** remains, deliberately), "Phase 5 owns the rest",
  "(later phase)" for Half-Caste Charm access (implemented).

### What the audit ruled OUT

* Every backticked identifier in `ui/` prose resolves — no stale renames.
* No other duplicated or orphaned comment blocks.
* `view.py`'s note that "every style in the catalogue now has a tier, so there is no real
  subject left to point a render test at" is **accurate** — a negative control correctly
  documented as having gone subject-less.

## ⚠ I broke two tests and fixed them — read this

`test_advantages_tab_offers_merit_gain_and_loss_in_play` and
`test_play_tracker_shows_the_shortened_renamed_resonance_track` pinned the exact
on-screen strings corrected above. I updated both assertions to the corrected text; the
tests' subject (that the readout says where undo lives; that permanent Resonance is
read-only on the tracker) is unchanged.

**The process failure is worth more than the fix:** I checked for pinned strings first,
piped the grep through `head`, and reported "no test pins these strings" on truncated
output. The two `should_see` lines were below the cut. **Never conclude an absence from
a truncated search.**

## What is uncommitted

17 source files + `tests/test_merits_flaws.py`. Verified three ways:

* `prose_guard.py` clean on every file (code byte-identical, no citation or ⚠ lost);
* the five files it flags as CODE CHANGED were proven, by AST comparison with all string
  constants normalised, to differ **only in string literals** — the user-facing text above;
* full suite green.

The one earlier structural change — deleting `_BackgroundBudgetTierMoved`, a dead
grep-marker class in `models/rules.py` — is already in `ea0df0e`.

## Corrected: the martial-arts absences are ONE, not three

`docs/status/handoff.md` used to say the deferred absences were `snake`,
`hungry-ghost` and `enlightenment`. **`snake` and `hungry-ghost` have authored styles**;
only `martial_arts:enlightenment` has none, and it is the Dragon-Path initiation tree
rather than a style. CLAUDE.md:290 was already correct ("21 of 22 authored") — this file
was the one that drifted.

## Known remainder (small, and yours to take or leave)

Two stale counts survive in **test comments** (not assertions, so nothing fails):
`tests/test_merits_flaws.py:3348,3376` say "99 entries" and `tests/test_ghost.py:199`
says "the 56 Arcanoi". Same class as the thirteen above; left alone because the audit's
scope was `ui/`.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
