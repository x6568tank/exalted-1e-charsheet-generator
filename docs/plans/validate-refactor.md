# Splitting `engine/validate.py` — NOT STARTED

**Human, 2026-08-14:** *"I glance over your code before committing and it is becoming
seriously unwieldy."*

## The measurement

| | |
|---|---|
| Lines | **5,791** — 47% of the entire `engine/` package (12,307 lines) |
| Functions | **182** |
| Of those, `check_*` (Issue-producing validators) | **15** |
| Helper / public API | **141** |
| Private | **26** |
| Largest function | `validate_chargen`, **643 lines** |
| Runners-up | `bonus_point_breakdown` 345, `merit_issues` 225, `background_issues` 144, `check_artifacts` 142, `charm_matches_splat` 124 |

## ⚠ The seam is DOMAIN, not splat

The obvious split — one module per splat — is wrong here, and the data says so: only
**four** of the 182 functions carry a splat in their name (3 Mountain Folk, 1 each
Alchemical/Mortal/Lunar). The file is not splat-shaped; it is domain-shaped, with splat
differences already pushed into `data/` where decision 0002 wants them. Splitting by splat
would fight the architecture and produce eleven near-empty modules.

The real clusters, by what the functions actually name:

* **Charms** — `charm_matches_splat`, `charm_picks`, `charm_slot_counts`,
  `uses_charm_slots`, `meets_charm_requirements`, `charm_fits_dedicated_slot`,
  `charm_ability_requirements`, `ox_body_charm`, `gift_charm`, `charm_learnable_by_splat`,
  `_repeatable_purchase_cap`. The single biggest cluster and the most cross-referenced.
* **Budgets / bonus points** — `effective_budgets`, `bonus_point_breakdown`, and the bulk
  of `validate_chargen`.
* **Backgrounds** — `background_issues`, `background_rating_cap`,
  `effective_background_rating`.
* **Merits & Flaws** — `merit_issues`, `merit_cost_overrides` reads. ⚠ Whatever moves,
  **no module outside `engine/merits.py` may name a Merit id** — a test greps for it.
* **Artifacts** — `check_artifacts`, and its interplay with `engine/artifacts.py`.
* **Traits & specialties** — `check_specialties`, ceilings, Virtues, Willpower.
* **Splat consistency** — `check_splat_consistency`, `splat_of`.

## ⚠ The refactor risk is THE HOUSE BUG, exactly

This project's recurring defect is *a rule that IS implemented, sitting where it does not
run when it matters* — and a split of the validator is the ideal way to produce one. Two
specific shapes to guard:

1. **A `check_*` dropped from the `validate()` / `validate_chargen()` roll-up.** The
   function still exists, its unit tests still pass, and it never runs. This is the Callous
   bug and the R1 delegation bug in one. **Assert the roll-up's membership**, not just each
   checker: a test that enumerates every `check_*` in the package and asserts each is
   reachable from `validate()` would make this class impossible.
2. **A caller left pointing at the old path.** `validate.X` is referenced from across
   `ui/` and `engine/`; the most-called are `uses_charm_slots`, `meets_charm_requirements`
   and `charm_matches_splat` (9 sites each). Re-export from `validate` or fix every site —
   do not leave both.

**Do it with the suite green at every step and no behaviour change in the same commit.**
A pure move is reviewable; a move plus a fix is not.

## Suggested order

1. Add the roll-up membership test FIRST, while everything is still in one file — it is
   the safety net for everything after.
2. Extract the **Charm** cluster (biggest, most self-contained).
3. Extract **Backgrounds**, then **Artifacts**, then **Merits** — each already has a
   neighbouring engine module to sit beside.
4. Break up `validate_chargen`'s 643 lines LAST, once the helpers it calls have moved out
   from under it.
