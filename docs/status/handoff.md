# Session handoff — 2026-08-22d (group 4 is CLOSED; nothing is human-clicked yet)

# 👉 YOU ARE HERE

Last FULL green suite: **2,837 passed, 1 skipped** (main PC, `qt-port`, 7m26s), run
after the last code change. The tree is clean and nothing is half-finished.

**Group 4 — the within-tab gaps — is closed.** All three items ship. ⚠ **The third
item is NOT human-clicked**, and neither is the variant-menu work that came out of it.
That is the only thing outstanding from this session.

## What shipped this session

| Thing | Where |
|---|---|
| The five per-splat Charm surfaces | `qt/charms.py` |
| Detail-pane flag lines (5, cost-relevant) — **on no gap list** | `qt/charms.py::_charm_flags_html` |
| `QPushButton:disabled` — every disabled button in the port looked live | `qt/theme.py::qss` |
| Submodule add/remove moved into the engine | `engine/charm_actions.py` |
| Immaculate BP preview: quoted 7 BP, charged 21 | `qt/charms.py::_chargen_pick_bp` |
| Post-lock repeatable buys, unshadowed | `engine/charm_actions.py::learn_charm` |
| Post-lock Remove = the last XP entry | `engine/charm_actions.py::undo_charm` |
| Variant-menu Charms on a generic list | `models/`, `engine/`, both shells |

Full write-ups: **`docs/plans/qt-port.md`** (group 4 item 3 and its tail) and
**`docs/plans/variant-menu-charms.md`** (the generic list). Do not re-derive them.

## 👉 NEXT: click it, then ST Options

**1 — the click-through, which is the only unfinished thing.** Five surfaces have been
rendered offscreen and looked at but never touched by a human:

- an **Eclipse with ST permission** switching the Splat dropdown and buying a foreign
  Charm (check the tree re-renders in the foreign splat's accent, and that buying does
  not snap it back to the native page);
- a **martial-arts tab** expanding the style panel and changing category;
- an **Alchemical** selecting Chemical Fog Generator, adding a submodule, and checking
  the two Essence-3 gases read as disabled;
- a **Dragon-Blooded** readout before and after picking a Dragon-style Charm;
- a **Jadeborn** buying a second Essence Satiation Method ("Add another");
- a **Solar with Resistance 5** on Environmental Hazard-Resisting Meditation — the
  variant chooser, both pre- and post-lock. ⚠ **The WEBAPP's version of this panel
  (`ui/picker.py::variant_menu_detail`) has never been rendered at all**, in a browser
  or otherwise. It is the least-verified thing in the tree.

**2 — then ST Options**, then Custom, then the Combos sub-tab, then Party. Both
placeholders get the COLLECTION layout; copy `qt/gear.py` or `qt/advantages.py`, never
transliterate `ui/<tab>.py`.

## ⚠ What is left overall — the rail is STILL not the measure

**1 — the last two rail placeholders.** `ui/storyteller.py` (183 lines) and
`ui/custom.py` (576).

**2 — the Combos sub-tab** (`ui/combos.py`, 423 lines), still a placeholder under
Charms. ⚠ Easy to miss because it is not on the rail.

**3 — the Party / ST screen has NO Qt counterpart at all.** `ui/gm.py` (610) +
`ui/adversaries.py` (489) ≈ 1,100 lines. A second WINDOW, not a tab, so the settled tab
layout does not decide its shape — an open design question, not a port.

**4 — the within-tab gaps: CLOSED.**

**NOT a gap:** the Play tab renders no Lunar **Renown** or **face** — neither does the
webapp's, so that is parity. Nor does the Qt Charm readout list per-issue lines: the
shell's details popover carries them (`main_window.py:297-330`).

**Parity limitation, deliberately not fixed:** the tab set is decided by NATIVE trees,
so an Eclipse whose own splat has no Arcanoi cannot reach foreign Arcanoi. The webapp
has the same limitation for the same reason.

## Decisions taken this session — do not relitigate

- **Environmental Hazard-Resisting Meditation is WIRED**, not deferred (human's call),
  and onto a **generic** `Character.variant_purchases` keyed by charm_id rather than a
  fifth bespoke list. The discriminator is `Charm.variants` being non-empty — all
  eleven such Charms in the catalogue are variant menus, so there is no id list.
- **Ox-Body and the Gifts keep their own lists.** Migrating them onto the generic list
  is possible and was deliberately NOT done. Not a gap.
- **Post-lock Remove reaches the LAST XP entry only** (human: "similar to what we have
  for things in the Edit tab"). The log is append-only and undo is LIFO (decision
  0004), so there is no correct removal for anything else.

## The lesson this session keeps re-teaching

**The gap list is a lower bound — three items, three times, without exception.** And
the two worst finds were invisible to the whole suite: the missing detail-pane flag
lines, and a QSS with no `QPushButton:disabled` rule that made every unmet-prerequisite
"Add" in the port read as clickable. **The offscreen grab is what caught both.** Render
it and LOOK, even when 2,837 tests are green.

## No open rules questions

The one that arose — the "four versions" cap on Environmental Hazard-Resisting
Meditation — was answered by the page itself (Caste Book: Zenith p.72-73), which prints
both caps. It is now `Charm.variants_unique` in the data.

⚠ One thing to be aware of rather than answer: that Charm's TRAIT cap can never bind
(it needs Resistance 5 to learn, so its four versions always run out first).
`PackageMenu.cap_phrase` says so — do not "correct" it back to "once per dot of
Resistance".

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
