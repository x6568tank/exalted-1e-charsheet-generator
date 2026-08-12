# Delegating a splat to a cheap model

The Godblooded splat (Phases A+B) was authored end to end by DeepSeek V4 Flash for
roughly **83 cents across ~140M tokens**. It shipped 1,887 green tests, followed the
house conventions closely, and its game values traced back to the pasted source. The
review that followed found **four defects in one pass** — all of the same kind.

This file is the audit that turns that into a repeatable trade. It is not a warning
against the practice; the economics are overwhelming and the work was mostly good. It
is the list of things a cheap model reliably will not do for you, written so the review
takes twenty minutes instead of an afternoon.

**Read `docs/adding-a-splat.md` first** — that is the how. This is the what-to-check-after.

## What it is good at, precisely

Everything that is *pattern-matching an established shape*:

* **Volume data.** Charm rows, caste rows, budget rows, M&F entries. 27 Merits and 8
  Charms authored, every id resolving, every value traceable to the source `.md`.
* **Following a precedent it can see.** It patched **both** Charm gates
  (`charm_matches_splat` *and* `charm_learnable_by_splat`) and cited the ghost preflight
  bug as the reason. It had read the postmortem and applied it.
* **Not breaking the other splats.** Every new cost shape (`magic_charm`,
  `new_magic_charm`, `essence_by_rating`, `repeatable_cap_virtue`) defaults falsy, so no
  other splat's numbers moved. That is the correct instinct and it had it unprompted.
* **Test scaffolding.** 39 tests including NiceGUI render tests for all four pages × both
  heritages — the blank-page class `preflight` exists to catch.

## What it is bad at, precisely

**One thing, wearing four costumes: it cannot tell the difference between describing a
rule and implementing one.** It writes the field, writes a docstring saying what the
field does, authors data into the field — and never wires up the read. Every defect
found was an instance of this:

| # | Defect | Shape |
|---|---|---|
| 1 | `heritage_traits.magic_track` authored `"necromancy"`, **zero read sites** | Field with a writer and no reader |
| 2 | `heritage_power` / `allowed_backgrounds`, **zero read sites** | Same (both were known/planned — see below) |
| 3 | p.48's summon-and-bind bar missed entirely, and **not in the status doc's Flags list** | Rule never modelled, never flagged |
| 4 | New id-bearing fields (`barred_charm_ids` et al) **not link-checked at load** | A bar that resolves to nothing bars nothing |

**Defect 1 is the one to study, because of how well it hid.** The field's docstring said
it makes Ghost-Blooded get Shadowlands Necromancy instead of Terrestrial Sorcery. The
field was never read — and yet **Ghost-Blooded behaved correctly anyway**, because the
Ghost catalogue happens to contain no sorcery, so Charm access produced the right answer
by accident.

The rule it was meant to enforce is two-way (p.48): sorcery for every heritage *save*
Ghost-Blooded and the Abyssal Half-Caste, necromancy for *only* those two. Charm access
gets that right exactly where the borrowed catalogue is single-track. It got it wrong in
both cases where the catalogue holds both:

* an **Abyssal Half-Caste** could learn Terrestrial Circle Sorcery — forbidden;
* a **Solar Half-Caste** could learn Shadowlands Circle Necromancy — forbidden.

Neither was reachable in the heritage that got click-tested. Both were live.

> **The rule this produces:** a cheap model's prose is a statement of *intent*, never of
> *fact*. Treat every docstring, comment and status-doc claim it writes as an unverified
> assertion about code you have not read yet — and note that **correct behaviour is not
> evidence the mechanism exists.** A dead field whose job is being done accidentally by
> something else is a bug waiting for the first input that separates them.

Defect 3 has a corollary worth stating on its own: **its self-flagging is not
exhaustive.** The status doc has a good, honest Flags section listing five deliberate
gaps. The summon/bind bar is not in it — not hidden, just never noticed. A gap list
written by the model tells you what it *knew* it skipped, which is a subset of what it
skipped.

## The audit

Four checks. Run them on the diff before the click-through, not after.

### 1. Dead-field sweep

Every field added to the models, with its read-site count outside the model:

```bash
git diff main -- exalted_builder/models/rules.py \
  | grep '^+' | grep -oP '^\+\s+\K\w+(?=:)' | sort -u \
  | while read f; do
      n=$(grep -rn "\.$f\b" exalted_builder/ --include=*.py \
          | grep -v 'models/rules.py' | wc -l)
      printf '%-30s %s\n' "$f" "$n"
    done
```

**Zero is a defect even when the behaviour looks right** — see defect 1 above; a dead
field can be shadowed by something else doing its job for the tested case. **One is a
suspect** — check that the single read site is not in the same lifecycle phase that
wrote it (the build's oldest bug, recorded in CLAUDE.md).
Low counts also need eyeballing for name collisions: `allowed_backgrounds` scored 1 in
the Godblooded run, but that hit was a *different* field of the same name on
`ChargenBudgets`. The heritage one was dead.

Not every zero has to be fixed. Two of the three here were deliberate — `heritage_power`
was headed for the Caste-info panel, `allowed_backgrounds` for after Half-Caste. **A
planned zero is fine; an unnoticed zero is the bug.** The sweep's job is to make you
decide, once, which one you are looking at.

### 2. Prohibition sweep against the source

The model reliably implements what the source *grants* and misses what it *forbids*.
Grep the pasted source for prohibitive language and walk the hits:

```bash
grep -inE "\b(may not|cannot|can never|may never|no [a-z-]+ (can|may))\b" \
  "images/<Splat>/<source>.md"
```

~96 hits for the Godblooded chapter — perhaps ten minutes to scan, and most are
narrative. This catches the missed rule exactly: line 412, *"No God-Blood can learn
spells to summon and bind elementals or demons."*

Each hit is one of three things: **implemented**, **deliberately flagged in the status
doc**, or **a defect**. There is no fourth category.

### 3. Link-check anything holding an id

If the splat added a field that holds Charm, Spell, caste or Merit ids, it needs a
`rules_db._check_*` entry. `_check_charm_references` now covers
`ExaltDefinition.barred_charm_ids` / `barred_spell_ids` and the heritage's
`barred_charm_ids` / `ox_body_charm_ids` / `gift_charm_ids`; extend it rather than
adding a parallel checker.

This class is invisible to tests in a specific way worth internalising: **a dangling id
in a bar list makes the bar silently pass.** The Charm stays learnable, no exception is
raised, and a test asserting the field's *contents* is perfectly green. Verify the
checker by poisoning a copy of `data/` and confirming it reports.

### 4. Stale identifiers

```bash
grep -rn "Character\.\w\+" exalted_builder/models/rules.py \
  | grep -oP 'Character\.\K\w+' | sort -u
```

Cross-check each against the real `Character` fields. The Godblooded models referred to
`Character.parent_exalt` in three comments; the shipped code uses `Character.origin`.
That is the fingerprint of a design change made mid-implementation with the prose left
behind — and prose left behind is how defect 1 happens.

Then run **`preflight`** as normal. It covers the phase-wiring and NiceGUI classes this
audit does not.

## Division of labour

**Delegate:** data authoring, transcription→JSON, the Nth repetition of an established
pattern, test scaffolding, UI render tests.

**Do not delegate:** the decision that a rule is *deliberately* unmodelled. That is a
rules-authority call, and the model's Flags list is a starting point for it rather than
a substitute. Everything on that list, plus everything the prohibition sweep turns up,
is yours to rule on.

**Verify, always:** any sentence in a docstring or status doc that claims a mechanism
works. One grep per claim. The model is not lying — it is describing the thing it meant
to build, and the gap between that and the thing it built is where the whole defect
class lives.

## Writing the brief: name the FUNCTION the test must call

From the second delegated run (the Background numeric rules, 2026-08-12,
`docs/briefs-background-rules.md` → `docs/status/backgrounds.md`). That brief already
said "tests are required per **binding**, not per field", and it was still not enough:
all nine tests called the helper directly —

```python
validate.background_issues(budgets, character.backgrounds, character)   # the read site
```

— while the production caller, `validate_chargen`, omitted the character argument
entirely. The rule was implemented, tested, documented, and never ran. **A test that
reaches past the caller into the helper cannot see the caller's mistake**, and the
optional-argument shape this codebase uses for its silent fallbacks (`derive.soak`,
`lifecycle.lock_chargen`, `background_issues`) turns that mistake into a quiet no-op
rather than a TypeError.

So the brief must say, per rule: **which entry point the test calls** — `validate_chargen`
/ `validate.validate` / the UI route — not merely what it asserts. Where a helper takes an
optional argument, require at least one test that never names the helper at all.

Three review rounds were needed on that run: the missing argument, then a fix that
narrowed the hole instead of closing it, then two defects only the browser could see (a
permission that lifted a bar without revealing the Background, and a total-cap leaking
into a per-row control). The pattern across all three is the same as the first run's, one
level up: **each fix was correct about the case in front of it and silent about the
neighbouring one.**

## Verdict

Worth it. Four defects across a two-phase splat is a good ratio at any price and an
absurd one at 83 cents, and none of them were in the game values — the part where a
wrong answer is hardest to notice and does the most damage. Every value traced back to
the pasted source; what went wrong was always the wiring, never the number.

The failure mode is narrow, consistent, and mechanically detectable, which is the best
thing you can say about a failure mode. It is also **exactly the failure mode this
codebase already had** — "a rule that IS implemented, sitting where it does not run when
it matters," recorded in CLAUDE.md long before any of this. The cheap model did not
introduce a new class of bug. It produces the house bug faster than a human does, which
is an argument for the audit, not against the model.
