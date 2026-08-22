# Session handoff — 2026-08-22b (group 4 item 1: Edit's deferred panels, all seven)

# 👉 YOU ARE HERE

Last FULL green suite: **2,766 passed, 1 skipped** (main PC, `qt-port`, 7m36s), run
after the last code change. The tree is clean and nothing is half-finished.

**Edit's seven deferred panels are DONE and the suite is green — but NONE of it is
human-clicked.** That is the one outstanding thing on this work, and it is deliberate:
the human's call was to finish all seven and then click the whole Edit surface in one
go, rather than clicking after each panel.

## 👉 NEXT: click through the Edit surface

Two commits, `d157913` and `b9ee454`. Run `python -m exalted_builder.qt [path]`. What
has never been looked at on a real display:

* **Traits** — Colleges (Sidereal), Specialties, Permanent Resonance (Abyssal with
  Death's Taint), Virtue Flaw + bonus health levels (these two share a row).
* **Identity** — Training Camp & Calling (an Illuminated Solar; and a Cult
  Dragon-Blooded, whose panel must be titled "Training Camp" with no Calling control).
* **The popover** — "Downtime…" beside Adjust XP, post-lock.

⚠ **The offscreen grab has earned its keep twice now** (the Deadly Beastman description
pushing every pick off the first screen; the 24px column gap becoming row spacing). No
test sees a layout problem. The Virtue Flaw / health row and the camp panel's two
columns are the new two-column layouts and the likeliest place for one.

## What shipped

Seven panels, all off existing presenters — no new rules calls, no new numbers.

| Panel | Home | Note |
|---|---|---|
| Permanent Resonance / Limit | `qt/editor.py` TraitsPage | gated on `derive.permanent_limit_cap`, so no caller names a Merit id |
| Virtue Flaw | TraitsPage | gated on `derive.has_virtue_flaw` |
| Specialties | TraitsPage | instances, not rated traits |
| Astrological Colleges | TraitsPage | gated on the `college_dots` budget |
| Bonus health levels | TraitsPage | new `engine/health_actions.py` |
| Training Camp & Calling | `qt/editor.py` IdentityPage | new `engine/camp_actions.py` |
| Downtime | **`qt/main_window.py`** | ⚠ not an editor panel — see below |

**Three new engine modules**, all because two shells now drive one write:
`health_actions.py` (the health-tier delta), `camp_actions.py` (the four camp writes),
`labels.py` (`_label` + `_style_label`, one copy).

**`build_camp_view` and `CampView` moved from `ui/view.py` to `engine/camp.py`** — the
human's call, over a `ui/`-side module or a duplicate. `camp_actions` needs the view and
`engine/` may not import `ui/`. `view.py` re-exports everything, so
`viewmod.build_camp_view`, `viewmod.CampView`, `viewmod._style_label` and
`viewmod._label` all still resolve. `_charm_name` turned out to be a straight duplicate
of `engine/validate`'s; view.py re-exports that one now instead of keeping a second.

## The lessons this session bought

- **Auditing before building found two defects the gap list did not contain**, which is
  exactly what last session's stale-readout bug was supposed to buy. Both are the house
  bug's first species, and neither was visible from the rail, the tests or the tab.
  1. **`_EditorPage.reload()` never pinged `on_change`.** Ten call sites — every
     structural change, both purchase paths — moved the bonus-point spend while the
     shell's readout bar showed the previous answer. **The page's own body rebuilt
     correctly every time, which is what hid it.** Fixed in the WRAPPER, not at the ten
     sites; the test asserts the ping, because asserting the page would have passed.
  2. **`_combo` handed enum keys back degraded.** Qt stores item data as a QVariant and
     a `str`-valued Enum comes back out of `currentData()` as a plain `str`; `Character`
     has no `validate_assignment`, so `setattr(row, "ability", …)` wrote `"dodge"` onto
     a field typed `AbilityName` and **failed nowhere at the write** — it would have
     failed later at the first `.value`. The key is now looked up by INDEX in the
     caller's own dict, so every key type round-trips identically.
- ⚠ **"Address a widget by name, not position" bit while writing the TEST for it.** The
  first Virtue Flaw locator walked out to the label's parent and took the first
  QComboBox — but a `QHBoxLayout` does not reparent, so every combo in a panel shares one
  parent, and it grabbed the Flawed Virtue box while looking for the sample list. Every
  new control here has an `setObjectName`; the tests use `findChild(kind, name)`.
- ⚠ **A gap-list entry can name the wrong MODULE.** Downtime was filed under "Edit's
  deferred panels" for two sessions. It is not a panel — in the webapp it is a button
  beside Adjust XP, so its Qt home is the shell's popover. **Check where the webapp puts
  a thing before porting it to where the list says it is.**
- ⚠ **Two different things wore the name `age`.** The 2026-08-06 ruling removed the
  numeric age trait; a free-text biography `age` was added 2026-08-21 and is unrelated.
  A test now pins that the calculator does not read the bio field.

## ⚠ What is actually left — the rail is STILL not the measure

Item 4 is the only one that moved. **Two rail tabs, one sub-tab, one whole window, and
the rest of the within-tab gaps.**

**1 — the last two rail placeholders.** `ui/storyteller.py` (183 lines) and
`ui/custom.py` (576). Both get the COLLECTION layout — toolbar · sub-tab per category ·
sortable table · splitter with a detail pane. Copy `qt/gear.py` or `qt/advantages.py`;
never transliterate `ui/<tab>.py`.

**2 — the Combos sub-tab** (`ui/combos.py`, 423 lines) is still a placeholder in its new
home under Charms. ⚠ **It is easy to miss because it is not on the rail.**

**3 — the Party / ST screen has NO Qt counterpart at all.** `ui/gm.py` (610) +
`ui/adversaries.py` (489) ≈ 1,100 lines, and the toolbar's `Party` button still answers
"not part of this milestone". A second WINDOW rather than a tab, so the settled tab
layout does not decide its shape — an open design question, not a port.

**4 — the within-tab gaps.** Edit's are CLOSED. What remains is the per-splat Charm
surfaces, and they have **never been re-derived against the webapp** — treat the list as
a lower bound, exactly as Edit's turned out to be:

- ~~Ox-Body Technique + Deadly Beastman: the variant MENU.~~ **DONE 2026-08-22.**
- ~~Edit's seven deferred panels.~~ **DONE 2026-08-22, not yet clicked.**
- Submodules (Alchemical), the Immaculate-vs-standard DB banner, the MA style panel, the
  foreign-charms splat dropdown, "Add another" for repeatable Charms.

**NOT a gap:** the Play tab does not render Lunar **Renown** or **face** — neither does
the webapp's, so that is parity. Both are wholly Storyteller-adjudicated.

**After group 4:** ST Options, then Custom, then Combos, then Party.

## CLOSED: the `acquired` migration is not a thing to do

`set_weapon` / `set_armor` used to drop an artifact's `acquired` channel; the routes are
all closed (`gear_actions.set_acquired` is the only writer in either shell) and it was
carried for two sessions as "no migration exists". **The human closed it 2026-08-22:
there are no characters with cash-bought artifacts, and the build is ~2 months old — do
not write migrations for pre-1.0 save damage.** ⚠ Applies generally: **backwards
compatibility with old saves is NOT a standing concern on this project.** Do not add a
migration, a version field or a compat shim without asking.

## No open questions

No rules questions. Every number came from `engine.validate`, `engine.elder` and the
existing presenters. The one decision this session needed — where the shared camp logic
should live — the human made: move it into the engine.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
