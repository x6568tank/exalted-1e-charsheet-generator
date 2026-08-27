# Session handoff — 2026-08-27 (the Party / ST window — THE PORT IS FEATURE-COMPLETE)

# 👉 YOU ARE HERE

Last FULL green suite: **3,015 passed, 1 skipped** (main PC, `qt-port`, 7m34s), run
after the last code change. The tree is clean and nothing is half-finished.

**The Qt port has nothing left to build.** The Party / ST window shipped this session —
the one thing that was a design question rather than a port, and the last item on the
list. Every tab and both windows now exist.

## 👉 NEXT: click the Party window on a real display

**That is the only owed work.** `qt/party.py` (Party · Adversaries · Reference) and
`qt/adversaries.py` were rendered offscreen tab by tab and dialog by dialog, and looked
at — which is not the same thing as being used. Scope the click-through to what only the
display can answer:

1. **Open the Party window from the builder toolbar, add the open character, click a
   health box, then go back and spend XP in the builder.** The card must redraw. (This
   is the one cross-window path; everything else on the card is Play's shape, already
   approved.)
2. **"Builder" on a card, edit something, come back.** One builder, retargeted, same
   object — the human's call. Does that read right in use, with two windows open?
3. **The Adversaries tab as a COLLECTION rather than cards.** This is the half of the
   design that changed shape from the webapp: add a template, duplicate it twice, damage
   one. Does the Damage column carry what the card stack used to?
4. **Close the builder.** The party window must go with it.

## The click-through started, and its first finding is fixed

**"The adversaries list doesn't load anything?"** — an empty collection table is a header
over a blank rectangle, and reads as broken rather than empty. **Every collection tab in
the port had it** (Gear, Advantages, Combos, Custom); the roster is where it bit because
empty is that tab's opening state. `qt/layout.py::empty_note` is the fix, wired to the
model's own row signals so no `_fill_table` can forget it, and guarded by a SWEEP —
`test_no_empty_table_anywhere_in_the_port_is_a_bare_void` fails for any table anywhere in
either window that holds no rows and says nothing. ⚠ Its slot must be a bound method of
the label, not a closure: the Advantages/Custom tables are rebuilt with their sub-tab
pages, so a closure fires into a deleted C++ object — and that crash surfaces in the NEXT
test, not the one that caused it.

**The rest of the click-through is still owed.**

## What shipped this session

| Thing | Where |
|---|---|
| The Party window — a second `QMainWindow`, three tabs | `qt/party.py` |
| The Adversaries collection tab | `qt/adversaries.py` |
| The ST reference screen, ported for the first time anywhere in Qt | `qt/party.py::reference_html` |
| The tracker box + damage colours, now shared by all three surfaces | `qt/trackers.py` |
| Roster mutations moved into the engine; the webapp calls them too | `engine/adversaries.py` |
| The Party toolbar action, `_open_member`, the visible-only redraw, `closeEvent` | `qt/main_window.py` |
| 30 + 49 + 8 + 7 tests | `tests/test_qt_party.py`, `test_qt_adversaries.py`, `test_qt_shell.py`, `test_adversaries.py` |

Full write-up, with every trap: **`docs/plans/qt-port.md`**, the last section. Do not
re-derive it.

## The four design answers, so they are not re-litigated

Asked before any code was written; all four taken as recommended (human, 2026-08-27):
a **second window** (not a dialog, not a mode) · **sub-tabs with mixed layouts** (cards
for members, the collection layout for adversaries) · **"Open in builder" retargets the
one builder** · **the ST reference screen lives on this window**, not on ST Options.

⚠ **The Party tab is the THIRD written exception to the collection layout**, and it is
Play's exception for Play's reason: a card is a live tracker with nothing to select. The
Adversaries tab beside it IS a collection. **Two shapes in one window is the design.**

## The gap list was a lower bound — SEVEN for seven

"~1,100 lines, `ui/gm.py` + `ui/adversaries.py`" did not mention:

* the **ST reference screen**, which existed in no Qt module at all;
* the **roster mutations having no engine home** — the same hole Combos had a day
  earlier, closures inside `ui/adversaries.py` that the native shell could not reach;
* **four layout defects only a render could show** (a nested layout's inherited 11px
  margin ×6 per card, a grid stretching cards to the tallest in the row, full-width spin
  boxes, and a first screenshot that lied because the scroll area had not settled).

## A webapp bug found and deliberately NOT fixed

⚠ **`ui/gm.py`'s card ignores `PlayView.single_pool`.** A merged Essence pool is ONE
track (p.41), so a merged-pool character's card draws a Personal box sitting at a
permanent 0/0. The Qt card honours it. The webapp card was left alone — it is a one-line
fix in a surface nobody asked to touch this session, and it should be its own change.

## Not blocking, but not clicked either

Group 4's five per-splat **Charm surfaces** (Eclipse foreign tree, MA style panel,
Alchemical submodules, the DB Immaculate banner, the Jadeborn repeat), plus the POST-lock
half of the variant chooser. Each was rendered offscreen and each has test coverage.

⚠ **`ui/picker.py::variant_menu_detail` — the WEBAPP's variant panel — has still never
been rendered at all.** It remains the least-verified code in the tree.

## No open rules questions

Nothing here introduced a rules interpretation. The three printed rules the widgets had
to encode — 0-means-absent in a trait grid (p.316), absent-is-not-zero for dodge (p.307),
and Charms/Spells/Powers as prose (p.303) — were all already decided in
`models/adversary.py` and are carried, not invented.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), and the one martial-arts absence
(`enlightenment`). Training times are still a no.
