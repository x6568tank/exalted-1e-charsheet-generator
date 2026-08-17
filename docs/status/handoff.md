# Session handoff — 2026-08-17 (the validate split, the comment pass, and 1.0)

# 👉 YOU ARE HERE

**Everything below is DONE, COMMITTED and GREEN — 2,455 passed, 1 skipped.** Nothing is
half-finished and nothing is waiting on a decision.

**`pyproject.toml` reads 1.0.0. The tag is not pushed — that is yours.**

**State: clean tree, fifteen commits ahead of v0.9.9.**

```
.venv/bin/python -m pytest -q     # expect: 2,455 passed, 1 skipped, 1 warning
```

⚠ The 1 SKIP is conditional and healthy: `test_buy_merit_prices_the_tier_against_the_
characters_own_menu` skips when no tier exists that is generic-but-not-Solar. It is a
guard against a bug shape, not a disabled test.

⚠ **The 71-entry M&F deferral WARNING is expected** and is not a failure. Unlike the
last session, `test_every_description_matches_the_source_text` PASSES here — the
Godblooded chapter markdown is not present on this machine. CLAUDE.md says neither
outcome is a regression. **Not something to fix.**

## What happened: the last structural TODO is closed

`engine/validate.py` — 5,791 lines, 47% of the engine — is now the package
`engine/validate/`: **15 modules, largest 1,492 lines**, `validate_chargen` 645 → 176,
and **3 call sites changed out of 1,465**.

**Full record: `docs/plans/validate-refactor.md`.** Read it before touching the package;
`docs/ARCHITECTURE.md` now carries the import DAG.

All three of the TODOs written when the catalogue closed on 2026-08-14 are done (the
printable sheet, martial-arts styles, and this).

## Post-lock Merit legality — closed, and it was a real bug

Found by the preflight before tagging, and **pre-existing** rather than caused by the
refactor: `merit_issues` was called from exactly one place, `validate_chargen`, while
`buy_merit` / `gain_flaw` / `drop_merit` all work post-lock. The split is what made it
visible, because `merit_issues` landed in the chargen-only module.

Two fixes, because the five unenforced gates were not one problem:

* **The buy path** — `_merit_purchase_gates`, shared by `buy_merit` and `gain_flaw`.
  `thaumaturges_only`, `tier_barred_exalt_types`, `trait_prerequisites`,
  `points_limits` and `max_purchases_from_trait` were checked at chargen and skipped
  entirely on XP purchases. Plus a real bug: both validated the tier against the
  GENERIC `cost_options` rather than the character's own menu.
* **The drift gates** — `merit_issues(..., post_lock=True)` returns just the three
  gates that measure something the story can change, as WARNINGS (your ruling).

⚠ The post-lock pass reads LIVE traits, not the snapshot. A snapshot read would check
the values as they were AT the lock and never fire. Its own test asserts this.

**Alternative Divination is now repeatable** (`repeatable_by: "ritual"`, PG p.24). It
carried `""`, so a second copy was refused as `merit-repeated` and the printed Occult
cap could never bind. ⚠ Two code comments cited "(p.17)" for that rule; p.17 is the
unrelated 10-point Flaw cap. Corrected to PG p.24.

## The comment pass — DONE for `engine/validate/`

Your 2026-08-17 request, applied to all 15 modules: a docstring states input, output and
mechanism; the narration moved to the git log and `docs/status/`. Kept per your ruling —
every page citation, and every ⚠ record of a behavioural trap.

⚠ **Prose only went 35% → 34%, and that is the right outcome.** Most of what came out was
narration with a live trap buried inside it, so the trap came back as an explicit ⚠.
About twenty are now findable that were mid-paragraph before. **Judge it by what the
prose IS, not by line count.**

The standard is recorded in CLAUDE.md and applies to all new code from here.

**Not done — the rest of the build**, in size order. Say the word and I will continue;
it is mechanical but not quick:

| Area | Prose lines | % |
|---|---|---|
| `ui/` | 3,676 | 24% |
| `models/` | 2,672 | **61%** — the densest in the build |
| `engine/` outside validate | 2,496 | 38% |

`tools/prose_guard.py` is the method: strip all docstrings, compare the AST
(byte-identical ⇒ no code changed), then assert no page citation and no ⚠ marker was
lost. ⚠ It earned itself — it caught two citations (core p.325, BoTC pp.25-27) I dropped
while rewriting `artifact_checks.py`.

## 1.0 — `pyproject.toml` is bumped to 1.0.0; the tag is YOURS to push

```
git tag v1.0.0 && git push --tags
```

CI does the rest: `.github/workflows/release.yml` builds Linux + Windows on any `v*`
tag and attaches both to the release. It has succeeded on every tag back to v0.9.2.

⚠ **"Packaged builds" was never actually outstanding.** It sat in this file as the last
1.0 blocker for three days while being complete — every release back to v0.9.4 already
carries both binaries. I repeated the claim from the previous handoff without checking
it. Verified 2026-08-17 against the GitHub API, and the release binary was built and run
from this tree as well.

⚠ **macOS is deliberately OFF** (commented out in the CI matrix: unsigned, so Gatekeeper
quarantines it). 1.0 ships Linux + Windows. That is a standing decision, not an oversight.

## If you do one thing after tagging

Carry the comment pass into `models/`, which is 61% prose and the densest area in the
build.

## Nothing is pending your ruling

You made two calls this session and both are implemented: the **facade** over a
call-site sweep, and the **package** layout over flat `validate_*.py` siblings.

---

## The three bugs the refactor hit — all mine, all now guarded

Worth reading, because two of them are shapes that will recur.

1. **A section boundary swallowed a binding the parent still read** — `mf_caps`, then
   `wp_total`. 384 tests each time. **Invisible to an import smoke test AND to a
   file-scoped undefined-name check**, because the name IS defined in the file, just not
   in the function reading it. `test_no_engine_function_reads_a_name_it_never_binds` now
   does per-function scope analysis over all of `engine/` and reproduces it in 1 second
   where the suite needs 6.5 minutes.
2. **An accidental re-export was load-bearing.** Trimming the now-unused
   `from .. import artifacts, derive, elder, merits` broke 22 tests: `advancement.py`
   reached `validate.merits.merits_and_flaws_calc` — the MODULE, through validate. It
   already imported `merits` directly, so three sites were fixed. **Imported modules are
   public surface whether anyone intended it or not.**
3. **A file-wide filter for a function-scoped intent.** Deleting the dead
   `caste_attr_category` local from `validate_chargen` also deleted the live one in
   `bonus_point_breakdown`.

## Two traps found in EXISTING tests, both fixed

Neither was caused by this work; both were latent.

* **`test_no_module_outside_engine_merits_names_a_merit_id` exempted a BASENAME**
  (`path.name == "merits.py"`). A new `engine/validate/merits.py` would have exempted
  **itself** from the only enforcement decision 0011 has. Now keyed on the path, with
  the path asserted to exist. That is why the module is called `merit_checks.py`.
  **An exemption keyed on a basename is one anything can claim.**
* **`test_no_module_in_the_chargen_or_xp_path_imports_pools` hardcoded `"validate.py"`**
  in a filename list. It failed loudly with `FileNotFoundError` rather than passing over
  a missing file — luck, not design. Now walks the package with rglob and asserts its
  targets exist.

⚠ And I nearly shipped the same shape in my own safety net: the reachability test
globbed `engine/*.py`, non-recursively, so it would have gone blind the instant the
package existed. Caught before the split; it uses **rglob** now.

## Two dead locals removed (behaviour-neutral, worth knowing)

`validate_chargen` computed `caste_attr_category` and `caste_fav_attrs` and read
neither. Both call pure functions, so this is wasted work, not a bug — but
`caste_fav_attrs = _caste_favored_attr_names(...)` sat at the head of the Charm section
and read as though caste/favoured Attributes were checked there. They are, inside
`charm_slot_usage`.

## How the split was verified — three checks, not inspection

Reusable if you ever do this again:

* **AST name diff** against the pre-split file in git: 200 top-level names before, 200
  after, none lost and none invented.
* **Facade resolution**: all 200 still resolve as `validate.X`.
* **Statement-set identity** for the `validate_chargen` decomposition: the old
  function's statements compared as `ast.dump` against the new function with all 15
  helpers inlined. Only difference was the two dead assignments.

Every guard in `tests/test_validator_rollup.py` was proven by mutation — deleting the
thing it exists to catch and confirming it goes red.

## One thing left alone deliberately

`merits.merits_and_flaws_calc(ruleset, character)` is called **twice** inside
`validate_chargen` (as `mf_caps`, then as `mf`). It is pure, so merging them changes
nothing but wasted work — left as-is to keep the refactor behaviour-identical. A
one-line cleanup whenever you want it.

## Still deferred, still NOT gaps

The Mist numina and Cult Abyssals (both indefinitely), the three martial-arts absences
(`snake`, `hungry-ghost`, `enlightenment`). Training times are still a no.
