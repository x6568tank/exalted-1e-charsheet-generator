---
name: add-splat
description: Drive the implementation of a new splat (Godblooded, Ghosts, Dragon-Kings, Mountain Folk) or a sub-source like a castebook or Aspect book. Use when asked to start, estimate, or continue a splat, or when rulebook pages for one land in images/. Enforces the source gate and the authoring loop; the reference material is docs/adding-a-splat.md.
---

# Adding a splat

`docs/adding-a-splat.md` is the reference — the four data rows, the eight questions,
what each of the seven finished splats actually cost, the seven traps, and what is
genuinely free. **Read it in full before estimating anything.** This skill is the
procedure that wraps it, and it exists because the failures here are sequencing
failures, not knowledge failures.

Four splats remain: **Godblooded, Ghosts, Dragon-Kings, Mountain Folk**. All four are
blocked on source material. The Fair Folk are permanently out of scope (decision
0010) — six non-Exalt splats were never seven.

## Gate 0 — pages, or stop

**Check `images/<Splat>/` exists and covers what you need before writing one line.**
If it does not: say so, list what is missing, and stop. Do not start, do not scaffold
"pending the numbers", do not fill a gap from your own knowledge of Exalted.

This is decision 0001 and it is the project's first rule. 2e is far better
represented in training data than 1e, so a remembered value will feel right and be
wrong. Reading the PDFs in `sources/` yourself is forbidden — the human's copy step
is the vetting checkpoint.

Minimum coverage before work starts (from `adding-a-splat.md` step 0): character
creation, traits/backgrounds/virtues deltas, Charms or the trees it borrows, and XP
costs (absent those, it silently inherits Solar's).

Do not assume a new splat shares budgets, a Charm economy, or even a shape with any
finished one. Mortals + Heroic Mortals merging into one splat with two origins was a
finding from *their* pages; it says nothing about the other four.

## Step 1 — read the pages, then answer the eight questions

Before estimating, answer `adding-a-splat.md` step 2's table against the actual
Traits and Character Creation pages. Each "yes" is engine work, and the honest
estimate is **data as a known quantity, the novel subsystem as the real project** —
roughly 90/10 by volume and 10/90 by effort across the seven done.

Give the human that estimate, split into data and subsystem, before writing code.

## Step 2 — the four data rows

`exalts.json`, `castes.json`, `chargen_budgets.json`, `costs_bonus.json` +
`costs_xp.json`, then a `theme.py` palette. `docs/content.md` has the conventions.
A surprising amount of UI works immediately, because it iterates `ruleset.exalts`.

Two traps to check explicitly at this step, both of which have bitten:

- **`highest_magic_circle_id` is the circle barred at chargen**, not the highest
  reachable. `""` withholds nothing.
- **A keyed-table row that does not exist falls back silently** at the wrong prices.
  Assert one distinctive number per row in a test so a typo cannot pass.

## Step 3 — the Charm authoring loop

Source text is `.md` the human pasted (preferred, exact for numbers) or PNGs
(diagrams and Charm-tree boxes-and-arrows). `tools/CHARM_AUTHORING_SPEC.md` is the
format.

Run the linter **as you author, per file** — not once at the end:

```
.venv/bin/python tools/validate_charms.py --splat <splat>
```

It catches transcription mistakes and "2e crept in" smells. It cannot tell you a
transcribed number is the wrong number, and it is not a substitute for
`load_ruleset`, which owns cross-file reference integrity.

Extract mechanically where the text allows it and verify every parse — fixing the
parser beats hand-typing, and "this vetted source is unparseable" has been wrong
before. When pasted text looks column-scrambled, flag it and ask for a screenshot
rather than guessing.

Every spell circle must be granted by some Charm or the loader refuses the data set;
author the initiation Charm and its spells together.

## Step 4 — the subsystem

Whatever the eight questions turned up. Test-first: that is where the bugs are.

Two invariants to hold while doing it:

- **Do not walk `character.charms` yourself** — Charms live on four lists, call
  `validate.charm_picks`. Four call sites once each walked their own subset and all
  four missed Gifts the day Gifts landed.
- **`view.ability_group_defs` is the single decision point** for Ability grouping.
  A splat with no ability-castes renders blank panels anywhere else that decides it.

## Step 5 — done means done

From `adding-a-splat.md` step 5 — a splat is not done when the tests pass:

1. Data authored from source, page numbers recorded.
2. Suite green, including a splat-specific test module asserting the distinctive
   numbers (`tests/test_lunar.py` is the pattern).
3. Run `preflight`, then **the human drives it in a browser**, every tab, with a
   real character of that splat. All seven turned up something only clicking found.
4. `docs/status/<splat>.md` written — what was authored, which pages, every ruling.
5. CLAUDE.md updated: status table, splat colour table, TODO. Use `close-out`.

## Throughout

**Flag, do not choose.** 1e has ambiguous and errata'd corners, and the human is the
rules authority. A splat's first pass always surfaces two or three of them; collect
them as questions in the status doc rather than picking an interpretation and
writing it into `data/` where it becomes indistinguishable from a printed value.
