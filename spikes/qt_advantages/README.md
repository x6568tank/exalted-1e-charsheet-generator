# Advantages layout spike — four shapes for one tab

Raised by the human 2026-08-21, right after the Gear tab was rebuilt from a
transliterated NiceGUI page into the Charms tab's native shape: *"I think it's fine
as is, but I am curious."* So this exists to answer curiosity, not to schedule work.

**Nothing in `exalted_builder/` is edited.** The first tab is the REAL
`qt.advantages.AdvantagesPage`; the other three are throwaway mockups in this file.

## Run

```sh
.venv/bin/python -m spikes.qt_advantages                       # ashes-of-dawn
.venv/bin/python -m spikes.qt_advantages examples/gearheart.character.json
```

Any character path works. The window's tab bar switches shape; the line under the
toolbar names the trade-off the current tab is making.

## ⚠ The three candidates are LAYOUT MOCKUPS

They render real data off the loaded character and their controls move, but they do
**not** buy, price or validate anything. Wiring three throwaway surfaces to
`engine.advancement` would cost more than the answer is worth. Read them as "what
would this feel like", not "does this work".

The one thing they do share honestly is their DATA: all three read
`advantage_rows()`, one derivation, so a difference you see between them is a
difference in layout and never a difference in what the character has.

## The four shapes

| Tab | Shape | The bet it makes | What it costs |
|---|---|---|---|
| **As shipped** | Card stack, rows edited in place | Advantages is a form you fill in; every row visible | Reads as a web page — the thing that prompted the Gear rebuild |
| **A · One table** | Gear's layout exactly — one filterable table + detail pane | A Background and a Merit are both "a thing you have"; one surface beats four | You see ONE rating at a time; the rest are numbers in a column |
| **B · Sub-tabs** | Charms' layout — a tab per category, tables + shared detail | They are different game concepts with different budgets, so different surfaces | A click to reach the other half; the two budgets can't be read together |
| **C · Native form** | The shipped structure with the web chrome removed | Advantages IS a form; keep it, just stop it looking like HTML | Least consistent with Gear/Charms — a third pattern in the app |

## What to judge

The real question is not "which is prettiest" but **which claim about Advantages is
true**:

- If it is a **list of objects** you browse and revisit — A or B, and the app gets one
  pattern everywhere.
- If it is a **form** you fill in at chargen and rarely reopen — C, and the app
  deliberately carries two patterns: tables for collections, forms for sheets.

That distinction is worth settling even if the answer is "leave it alone", because
**Play, ST Options and Custom are all still unported** and each will be one or the
other.

Specific things to look at:

- On **A**, whether losing the all-Backgrounds-at-once view hurts. That is the shipped
  page's real strength and the one thing a table cannot give back.
- On **B**, whether splitting Backgrounds from Merits & Flaws feels right or arbitrary
  — they are separate in the book, but they are budgeted together in the readout.
- On **C**, whether removing the cards is *enough* to stop it reading as a web page,
  or whether the accordion-free form still feels like a scrolled document.
- On all three, the **Fetters and Passions** sections: they only appear for a ghost, so
  load one (`examples/` has none — make a Ghost in the app and save it) if you want to
  see how each shape handles a splat with extra categories.

## If a direction lands

A follow-up ports it into `exalted_builder/qt/advantages.py` with the real buy paths
intact, and `tests/test_qt_advantages.py` (44 tests) is rewritten against the new
shape — the same way `tests/test_qt_gear.py` was when Gear moved to the table.

**Delete this directory once the question is answered**, whichever way it goes. The
other three spikes were kept because they became build records; this one is a
comparison, and a stale comparison is worse than none.
