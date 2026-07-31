---
name: preflight
description: Run before handing UI or engine work to the human for a browser click-through. Finds the bug classes that every past click-through found and 1,400 passing tests did not — rules wired into only one lifecycle phase, NiceGUI build-time crashes, pages that render blank. Use when a work item is "tests green, not browser-verified", or when asked to check work before a click-through.
---

# Pre-click-through preflight

The human's browser click-through is the highest-yield activity in this project and
the scarcest. Every past one found real bugs with the full suite green:

- Mortals, 2026-07-30 — 3 bugs (`docs/status/mortals.md`)
- Merits & Flaws, 2026-07-31 — 13 findings, 10 real bugs, 1,370 tests passing
  throughout (`docs/status/merits-flaws.md:380`)

That doc names the pattern, and it is the thing this skill exists to catch:

> almost every one is a rule that WAS implemented, sitting somewhere that does not
> run when it matters. Nothing was missing; things were mis-placed. Unit tests
> assert the implemented thing directly and so never notice.

**This does not replace the click-through.** It is not verification — see the
`serve-and-grep is not verification` rule. Its whole purpose is to make sure the
human's browser time is spent finding *rules* bugs instead of crashes and blank tabs.

Work through the four passes in order. Report findings; fix the mechanical ones,
raise the rules ones with the human.

---

## Pass 1 — effect fields wired into only one lifecycle phase

This is the Callous bug: `willpower_virtue_margin` was read in exactly one place,
`validate`, as a **chargen ceiling**. A ceiling does nothing post-lock, so raising a
Virtue on a locked Callous character moved nothing. The rule was implemented and it
never ran.

Run:

```
.venv/bin/python .claude/skills/preflight/effect_reads.py
```

It reports, for every field on an effects dataclass, which modules read it. Read the
output against these categories — the script flags, you judge:

| Finding | What it usually means |
|---|---|
| **ZERO READS** — written by the calc, read by nothing in the package | Either dead (a real gap) or informational-for-display-only. Tests asserting the field prove nothing about behaviour. Decide which and say so. |
| **Read only in `validate.py`** | Chargen-only. Ask: should this also bind post-lock? If the trait it governs can change in play, this is the Callous shape. |
| **Read only in `derive.py`** | Derived-only. Ask: should chargen have refused an illegal build in the first place? |
| **Read only in `advancement.py`/`costs.py`** | Priced but never enforced, or vice versa. |
| **Read only in `ui/`** | The engine does not know about this rule. Game logic in the UI violates the `ui → engine → models` rule in `docs/ARCHITECTURE.md`. |

Two reads across `validate` + `derive` is the healthy shape for anything that spans
chargen and play. A field consumed *inside* `merits.py` by a helper the callers use
(`adjust_charm_cost`, `adjust_spell_cost`) is correct architecture, not a miss — the
script notes those separately.

For each single-site field, open the read site and check the phase it actually runs
in. Do not assume the comment there is right: the Callous comment claimed to be the
decision-0005 exception and was not.

## Pass 2 — the NiceGUI build-time crash class

`ui.select` raises at **build** time when its initial value is not among its options
— including when the options are empty and the value is not. The raise takes down
the whole enclosing `build_*` call, **siblings included**, so one bad select blanks
several tabs. This is `adding-a-splat.md` trap #3 and it has fired twice: the mortal
picker crash blanked Abilities *and* Thaumaturgy.

```
grep -rn "ui.select" exalted_builder/ui/*.py
```

For each one touched by the current work, check:

1. Can its options be **empty** for some splat/caste/origin? (Charmless splat,
   casteless splat, a splat with no Colleges, an unlocked vs locked character.)
2. Can its `value` come from saved character state that is not in the options?
   (A custom/homebrew id, a caste from another splat, a stale Nature.)
3. Does it `setdefault` its own value, or is it guarded by not offering the page at
   all? One of the two must be true.

Then sweep the rest of the same failure family:

- **Shadowed locals** — an XP tab went down to one. Check any name reassigned
  inside a `with`/`for` in a `build_*` that is also used after it.
- **Layout that renders nothing visible** — a sheet panel was crushed invisible by a
  `no-wrap` row. Grep new/changed rows for `no-wrap`, `w-0`, `overflow-hidden`
  around variable-length content.
- **A block with no rules text** — a sheet section showing a name and a number but
  not what the thing does. Check every new sheet block prints its description.

## Pass 3 — the render matrix

Unit tests assert the implemented thing directly. The render harness proves a page
*builds* for a shape nobody tested. Routes live in `tests/_ui_main.py` and are driven
by the NiceGUI `User` fixture:

```python
@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_x(user) -> None:
    await user.open('/route')
    await user.should_see("something the page must emit")
```

The existing routes are ad-hoc regression routes, not a matrix — coverage across the
seven splats is uneven. For the work in hand, add a route per **shape** the change
can produce, not per bug you already know about. The shapes that have broken before:

- a splat with **no Charms** (Mortal) — every Charm-shaped UI
- a splat with **no castes** (Mortal) — every caste-grouped UI
- a splat with **no ability-castes** (Lunar) — anything grouping Abilities by caste
- **locked vs unlocked**, and **in-play with marked state**
- a character carrying **homebrew** or **off-catalogue** gear
- an **origin/upbringing** variant, where a keyed-table suffix can miss

Prefer asserting on content the widget must emit over asserting it did not crash.

## Pass 4 — the report

Run the full suite (`.venv/bin/python -m pytest -q`) and give the human:

1. **What to click, in priority order** — the specific pages and the specific
   character shapes, so the click-through is aimed rather than exploratory.
2. **Open rules questions** — anything Pass 1 turned up where the right behaviour is
   a 1e ruling, not a code fix. The human is the rules authority; do not choose an
   interpretation.
3. **What preflight could not check** — say this plainly. Correct-looking output that
   is the wrong number is exactly what the click-through is for, and nothing here
   detects it.
