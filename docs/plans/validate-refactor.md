# Splitting `engine/validate.py` — DONE 2026-08-17

**Human, 2026-08-14:** *"I glance over your code before committing and it is becoming
seriously unwieldy."*

Six commits, suite green at every one. `validate.py` is now the package
`engine/validate/`, 15 modules, largest 1,492 lines.

| | before | after |
|---|---|---|
| Largest file | **5,791** | 1,492 (`budgets.py`) |
| `validate_chargen` | **645** | 176 |
| Modules | 1 | 15 |
| Call sites changed | — | **3** (of 1,465) |

```
charms 1,488 · budgets 1,492 · backgrounds 591 · thaumaturgy 481
merit_checks 477 · __init__ 330 · traits 326 · artifact_checks 286
illuminated 285 · alchemical 249 · combos 153 · _base 153
spells 124 · elemental 115 · castes 111
```

## The two decisions the human made

1. **A facade, not a call-site sweep.** `validate/__init__.py` re-exports every name,
   so `validate.X` still resolves for all 1,465 references. Rejected: rewriting ~67
   files, which the plan warned was the unreviewable shape.
2. **A package (`engine/validate/`), not flat `validate_*.py` siblings.**

## Import order — a DAG, and it must stay one

    _base                     Issue, trait readers, effective_budgets, chargen_house_rules
    castes                    caste/favoured membership          (may import _base)
    charms                    access, prereqs, picks, slots
    backgrounds, spells, combos, thaumaturgy, illuminated, alchemical, elemental
    artifact_checks, merit_checks, traits
    budgets                   the chargen accounting + validate_chargen
    __init__                  validate() + the facade

`_base` and `castes` are the bottom and must import no sibling domain. Two genuine
cycles exist and are handled by call-time imports inside the two functions that need
them, each with a comment: `charms` ← `illuminated.calling_charm_ids` (a Calling
grants Charms) and `charms` ← `alchemical._installation_motes` (an Array holds them).

## ⚠ The naming rule that is not cosmetic

`artifact_checks.py` and `merit_checks.py` are NOT `artifacts.py`/`merits.py`. Both
read `engine/artifacts.py` and `engine/merits.py` as `artifacts.X`/`merits.X`
throughout, which a same-named sibling makes ambiguous to a reader and to grep.

**In the Merit case it was a live trap.** Decision 0011's containment test —
`test_no_module_outside_engine_merits_names_a_merit_id`, the only enforcement that
rule has — exempted `if path.name == "merits.py"`, a BASENAME. A new
`engine/validate/merits.py` would have exempted **itself**. Now keyed on the path,
with that path asserted to exist. Verified by planting a `merits.py` naming a Merit
id: red now, green before.

## The safety net — `tests/test_validator_rollup.py`

Written FIRST, before anything moved, and every guard in it is proven by mutation.

| Test | Catches |
|---|---|
| `test_every_validator_is_reachable_from_a_root` | a `check_*` dropped from `validate()` / `validate_chargen` / `validate_xp` — the house bug, in the shape a refactor produces it |
| `test_every_name_in_a_domain_module_is_reachable_as_validate_X` | a **public** name that left the facade |
| `test_every_validate_dot_reference_in_the_codebase_resolves` | the inverse walk: any `validate.<attr>` written anywhere that no longer resolves |
| `test_no_engine_function_reads_a_name_it_never_binds` | per-FUNCTION undefined names, with real nested-scope handling |
| `test_the_roots_exist`, `test_the_reachability_check_can_fail`, `test_the_undefined_name_check_can_fail` | the premises and negative controls |

⚠ The reachability walk uses **rglob**. A non-recursive glob would have gone blind
the instant `engine/validate/` became a package — this test's own subject matter
turned on itself. `test_the_roots_exist` is the canary if it regresses.

## The three things that actually went wrong

1. **A boundary that swallowed a binding — twice.** `mf_caps` and then `wp_total`
   were assigned inside a range extracted into a helper, while the PARENT still read
   them. 384 tests each time. **Invisible to an import smoke test and to a
   file-scoped undefined-name check** — the name is defined in the file, just not in
   the function that reads it. That is why the guard is per-function; it reproduces
   the bug in 1 second where the suite needs 6.5 minutes.
2. **An accidental re-export that was load-bearing.** Trimming the now-unused
   `from .. import artifacts, derive, elder, merits` from `__init__.py` broke 22
   tests: `advancement.py` reached `validate.merits.merits_and_flaws_calc` — the
   MODULE, through validate. It already imported `merits` directly, so the three
   sites were fixed. **Imported modules are part of the public surface whether anyone
   intended it or not**, and the facade test could not see it because it walked
   outward from what the package DEFINES.
3. **A file-wide filter for a function-scoped intent.** Removing the dead
   `caste_attr_category` local from `validate_chargen` also removed the live one in
   `bonus_point_breakdown`.

## What is left

Nothing structural. `budgets.py` (1,492) and `charms.py` (1,488) are the two large
modules; both are cohesive and neither has an obvious further seam. Two follow-ups
that are NOT part of this work:

* **The docstring pass** the human asked for on 2026-08-17: comments should carry
  input, output and mechanism only — no decision logs, no chain of thought. Page
  citations stay.
* `merits.merits_and_flaws_calc(ruleset, character)` is called twice inside
  `validate_chargen` (as `mf_caps` and again as `mf`). It is pure, so this is wasted
  work rather than a bug; left alone to keep this refactor behaviour-identical.
