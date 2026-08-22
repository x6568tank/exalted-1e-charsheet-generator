# Spike: four shapes for the Traits tab

**Question (human, 2026-08-22):** *"should we change the design of the Traits tab to be
more inline with the rest of the app? The dot-displays are non-negotiable, but it feels
a little odd being a UI of scrolled cards."*

```
.venv/bin/python spikes/qt_traits/traits_spike.py
```

Two switchers at the top: **Variant** and **Character**. Every variant renders the same
rows through the real `qt.editor.DotTrack` and the real `qt.theme` palette — **the only
thing that differs is the container**, which is what is being decided.

| # | Shape | The argument for it |
|---|---|---|
| 0 | **Cards (today)** | the baseline to judge the others against |
| 1 | **Sub-tabs** | already the settled layout's own idiom — "a sub-tab per category where a tab has more than one". Cheapest route to "in line with the rest of the app". |
| 2 | **Sheet grid** | one pane, newspaper columns, headings instead of cards. Closest to the paper sheet. |
| 3 | **Flat rules** | one scroll like today, cards replaced by headings + hairlines. Isolates whether it is the CARDS or the SCROLLING that reads wrong. |
| 4 | **Collection** | the app's *actual* design language — a QTreeWidget like Gear and Advantages, grouped by category, toolbar above, detail pane beside. Dots ride in the Rating column. |
| 5 | **Sheet grid v2** | variant 2 with the human's notes applied: Attributes narrowed to one column, Crafts moved under Abilities, Virtues/Essence/Willpower/Virtue Flaw merged, Specialties inline on their Ability. |

## What to weigh

- **Variant 1 trades scrolling for clicking.** The Attributes pane is nine rows and then
  700px of empty — the tab stops scrolling but you can no longer see Attributes and
  Abilities at once, which is what chargen prioritisation needs.
- **Variants 2 and 3 both fit a Solar on one screen.** 2 is denser and pairs
  Attributes↔Abilities side by side; 3 keeps today's top-to-bottom reading order.
- **The five panels in "STILL TO PLACE" are deliberately unplaced** — Specialties,
  Colleges, Virtue Flaw, bonus health levels and Permanent Resonance all landed on
  Traits after the card layout was designed, and where they go is part of the answer.

## ⚠ Traps this spike already paid for

- **A stretch on the row's NAME label pushes the dots to the far edge of the column.**
  Invisible inside a narrow card, glaring the moment a column goes full width. The
  stretch belongs after the track.
- **QGridLayout cells overlap silently.** A `section()` helper that returned the row it
  *started* at drew CRAFTS straight through the middle of VIRTUES, with no warning and
  no exception.
- **A short final row of ability groups must be PADDED**, or its columns spread to fill
  the width and stop lining up with the rows above.

Nothing here is wired to buying — the tracks free-set on both sides of the lock, so
clicking is safe and tells you nothing about XP.
