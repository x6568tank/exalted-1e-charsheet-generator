# Variant-menu Charms — the generic `variant_purchases` list

Built 2026-08-22. The human's call, over the alternative of restoring the deferral
recorded in `docs/status/solar-castebooks.md`.

**Suite at that moment: 2,837 passed, 1 skipped** (main PC, `qt-port`), of which
`tests/test_variant_purchases.py` is 21.

⚠ **Not browser-verified.** The Qt chooser was rendered offscreen and looked at; the
**webapp's `variant_menu_detail` panel has never been rendered at all**, in a browser
or otherwise — it is covered by engine tests through `build_package_menu` and by
nothing else. What to click: a Solar with Resistance 5 selecting Environmental
Hazard-Resisting Meditation on the Resistance tree, adding two versions, checking the
third is offered and a taken one is greyed with "Already taken", then locking and
buying a fourth with XP.

## What a variant-menu Charm is

A repeatable Charm bought as a **package**: each purchase picks one or more named
versions, and the purchase lands on its own `Character` list rather than appending the
Charm id to `character.charms` — because N copies must be representable AND each copy
has to remember *which* version it took.

There are eleven in the catalogue and **every one of them is a Charm carrying
`variants`**. That is the discriminator: `validate.is_variant_menu_charm` asks the
data, not an id list, so a new one needs data and nothing else.

| Storage | Charms | Why separate |
|---|---|---|
| `character.ox_body` | the nine Ox-Body Techniques | predates this; per-splat id via `ExaltDefinition.ox_body_charm_id` |
| `character.beastman_gifts` | Deadly Beastman Transformation | predates this; 2 picks on the first purchase, prerequisite chains between Gifts |
| `character.variant_purchases` | **everything else** | keyed by `charm_id`, so one list serves any number |

Today `variant_purchases` has exactly one member: **Environmental Hazard-Resisting
Meditation** (Caste Book: Zenith p.72-73).

⚠ **Migrating Ox-Body and the Gifts onto the generic list is possible and was NOT
done.** Both work; the migration is churn with a real chance of breaking two shipped
surfaces. A sweep that lists them as "not using the generic list" is counting a
deliberate non-migration as an oversight.

## The two caps, and which one actually binds

The Zenith text prints **both**:

> "an Exalt can take it repeatedly, until she has purchased all four versions. A
> character cannot purchase this Charm more times than she has dots in the Resistance
> Ability."

- the **trait** cap — `repeatable_cap_ability: resistance`, the existing field;
- the **version** cap — new `Charm.variants_unique`, which bounds the purchase count
  by `len(variants)` and forbids taking a version twice.

⚠ **For this Charm the trait cap can never bind.** `min_ability` is 5, so anyone who
can learn it at all has Resistance ≥ 5 > 4 versions. Both the refusal message and
`PackageMenu.cap_phrase` say "one of each of its 4 versions" rather than "once per dot
of Resistance", which would be simply untrue. Do not "correct" it back. The trait half
is still tested as a pure function — it is what a *second* Charm of this shape would
lean on.

## What had to be touched

The `docs/status/solar-castebooks.md` note was right that the enumeration blocker was
already gone, and right about the remaining list. For the record, in order:

| Layer | Change |
|---|---|
| `models/character.py` | `VariantPurchase`; the field on `Character` **and** `ChargenSnapshot` |
| `models/rules.py` | `Charm.variants_unique` |
| `data/charms/solar_resistance.json` | `variants_unique: true` — a one-line diff |
| `validate/_base.py` | `_chargen_source` gains a 21st element |
| `validate/charms.py` | `is_variant_menu_charm`, `variant_purchase_cap`, `variant_purchases_for`, `known_variant_keys`, `check_variant_purchases`, and the pick enumeration |
| `charm_actions.py` | `add_variant_purchase` / `remove_variant_purchase`, and the `variant_menu_reason` branch that refuses the toggle |
| `advancement.py` | `learn_variant_purchase`, the `undo_last` domain, the `_expected_cost` row |
| `ui/view.py` | `_xp_entry_label`, `package_menu_kind`, `build_package_menu`'s third branch, `PackageMenu.cap_phrase` |
| `lifecycle.py` | the lock snapshot copies the list |
| `costs.py` | `variant_purchase_cost` |
| both shells | the chooser — Qt via the existing package dialog, the web picker via a new `variant_menu_detail` driven off `build_package_menu` |

## Traps this cost

- ⚠ **`_chargen_source` returns a positional tuple and has BOTH indexers and
  unpackers.** Appending an element is safe for `src[6]` and breaks
  `(a, b, …) = _chargen_source(…)` — three call sites in `validate/budgets.py`. Append
  only, and grep for the unpackers.
- ⚠ **A new XP domain must extend `undo_last` AND `_xp_entry_label` AND
  `_expected_cost`.** The first two are the standing rule; the third is what makes the
  audit able to re-price the row, and a domain it cannot price silently accepts every
  wrong cost forever.
- ⚠ **A list the lock snapshot does not copy silently empties at the lock**, and the
  chargen audit then reads a character who never bought it.
- ⚠ **The refusal message must name the cap that actually bound.** `_cap_phrase` reads
  the trait fields and was confidently wrong here.
- **Existing tests can be pointed at the wrong subject.** The Qt "Add another" tests
  used this Charm as their generic repeatable; once it became a variant menu they had
  to move to the Mountain Folk pair, which is what the code comments cite anyway. A
  green suite before the change was not evidence the subject was right.
