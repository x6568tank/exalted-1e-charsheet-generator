# Status detail — Dragon-Blooded origins (Exalted: The Outcaste)

Referenced from `CLAUDE.md` → Status. DONE 2026-07-29 (data, engine and UI).
Read from `images/Dragonblooded/Origins/*` — four folders, nine page scans, each
origin's **Character Creation Summary** box plus its Bonus Points table.
Tests: `tests/test_dragonblooded_origins.py` (53).

**Not authored, blocked on pages:** the **numina / Mist aspect** (Forest Witches
p.131-133) — see `CLAUDE.md` → TODO.

## The `upbringing` axis — a FOURTH axis, under `origin`
Each book varies the budget by how the character was RAISED while everything else
about the origin holds, so `origin` alone could not key the rows (rules-authority
call, 2026-07-29: two axes rather than ~11 flat origins).
- `Character.upbringing`, and **both** `RuleSet.budgets_for` and
  `RuleSet.bonus_costs_for` now cascade `"E:o:u"` → `"E:o"` → `"E"` → `default`
  through one shared `models.rules._keyed_row`, so the two can never disagree about
  which row wins. `bonus_costs_for` had NO origin dimension before this.
- The cascade is what lets an upbringing row carry only its differences and an origin
  with no variants author no `:u` rows at all. **The first option of every origin is
  `""`** — the origin's own default, which deliberately has no `:u` row and falls
  back; `tests/…::test_every_offered_upbringing_resolves_to_an_authored_row` pins
  that both directions.
- `editor.set_origin` **clears `upbringing`**: a stale `patrician` surviving a switch
  to Pirate would resolve to the pirate origin row and look fine while meaning
  something the player never chose.

## The eleven budget rows
| origin | upbringing | abilities | bg | charms | virtues |
|---|---|---|---|---|---|
| `lookshy` | (born) | 35 / 13 | **13** | **6** | 5 |
| `lookshy` | `foreign` | 25 / 10 | 13 | 6 | 5 |
| `forest-witch` | (ex-Dynast) | 35 / 13 | 12 | 7 | **6** |
| `forest-witch` | `outcaste` | 25 / 10 | 12 | 7 | 6 |
| `forest-witch` | `oreithyia` | 25 / 10 | 12 | 7 | 6 |
| `lost-egg` | (lower-class) | 25 / **13** | **7** | 7 | 5 |
| `lost-egg` | `graduate` | 25 / 13 | 7 | 7 | 5 |
| `lost-egg` | `patrician` | **30** / 13 | 7 | 7 | 5 |
| `lost-egg` | `threshold` | 25 / 10 | 7 | 7 | 5 |
| `pirate` | (Dynast) | 35 / 13 | 12 | 7 | 5 |
| `pirate` | `outcaste` | 25 / 10 | 12 | 7 | 5 |

**Authored exactly as printed, do NOT "correct":**
- **Lost Eggs get 25 Ability dots but still need 13 on Aspect/Favored** (p.159). Every
  other 25-dot variant in the book is 10; only the Threshold row drops to 10.
- **Lookshy's Linguistics •••** (p.68) — the only origin whose Ability floor reaches 3,
  and it sits on the Ability the Heliocode section spends a column on.
- The Realm-schooling minimum list (Archery •, Brawl or Martial Arts •, Melee •,
  Performance •, Presence •, Ride •, Lore ••, Socialize ••) is reprinted by three of
  the four books and is **the same list the core `Dragon-Blooded` row already had** —
  pinned from all four sides, so a mis-transcription in any one of them fails a test.
- **Every pirate needs Sail •**, Dynast or born outcaste (p.96).

## Bonus points — only two origins deviate
Lookshy p.69, Forest Witch p.133 and Pirate p.97 print the existing `Dragon-Blooded`
table key for key, so they get **no row** (pinned by asserting they resolve to the
same OBJECT). The two that differ:
- `Dragon-Blooded:lost-egg` — Background **2 (3 above 3)**, not 1 (2) (p.160). Shared
  by all three Lost Egg upbringings via the cascade.
- `Dragon-Blooded:forest-witch:oreithyia` — Virtue **2**, Essence **8** (p.133). This
  is a rate that varies by UPBRINGING, and is the reason `bonus_costs_for` needed the
  third key at all.

## Lookshy specifics
- **`ChargenBudgets.granted_charms`** — Charms the ORIGIN hands out free (p.68:
  Wind-Carried Word Technique + Elemental Bolt Attack "at no cost"; our data spells
  them the Dragon-Blooded core way, **Wind-Carried WORDS Technique** and **ELEMENT
  Bolt Attack** — the same pair). Distinct from a `TrainingCamp` package, which the
  player CHOOSES from and which is validated; these are fixed, so they are **not
  stored on the Character at all** — they follow from the budget row, and a character
  who changes origin simply stops having them. They enter through the canonical
  Charm-pick enumeration as `source="origin"`, `counts_toward_pool=False`, so the
  sheet lists them and both the pick counter and the BP pricing ignore them for free.
  A Charm the character ALSO bought is not listed twice; the bought copy wins.
- **`ChargenBudgets.bar_immaculate_charms_at_chargen`** (p.68: "may not learn the
  Immaculate Martial Arts before play begins"). Keys off the existing
  `Charm.immaculate` flag, raises `charm-immaculate-barred-at-chargen`, and
  **suppresses the Immaculate path** so the player is not additionally told to put
  every Charm in one elemental tree — a rule they are forbidden to satisfy. Chargen
  only; the XP economy is untouched.
- **Breeding (p.66) — `BackgroundRule.bp_surcharge_per_dot`.** The page's arithmetic
  is self-consistent once read carefully (human confirmed the reading 2026-07-29):
  the surcharge is **+1 per Breeding dot above 2, accumulating**, taken on whichever
  route pays for that dot — pool (`expensive_above: 2, expensive_dot_cost: 2`) or
  bonus points (`bp_surcharge_per_dot: 1`, riding on top of `background_above_3`).
  With p.69's 1/2 base rate that reproduces the page's own totals:

  | Breeding | • | •• | ••• | •••• | ••••• |
  |---|---|---|---|---|---|
  | base BP (1/dot, 2 above 3) | 1 | 2 | 3 | 5 | 7 |
  | +1 per dot above 2 | — | — | +1 | +2 | +3 |
  | **total** | 1 | 2 | **4** | **7** | **10** |

  **4, 7 and 10 are printed on p.66**, so the test is self-verifying — nothing else
  reproduces all three alongside the p.69 rate. Dots inside the Background pool cost
  pool dots and no BP; only dots above 3 reach the bonus-point side.

## Eos and Ossissa (pirates) — new magic, p.93-95
**5 Sail Charms**, all Simple, appended to `dragonblooded_sail.json` (5 → 10). Every
one hangs off a Charm the Dragon-Blooded book already shipped, so the pirate chapter
EXTENDS the existing tree rather than starting one:

| Charm | Sail | Ess | prerequisite |
|---|---|---|---|
| Wind-Summoning Whistle | 3 | 3 | Storm-Outrunning Technique |
| Terrible Glow of Nautical Valor | 4 | 3 | Fine Passage Negotiating Style |
| Pleasant Convocation of the Like-Minded | 4 | 3 | Fine Passage Negotiating Style |
| Enemy-Fouling Method | 4 | 3 | Pleasant Convocation of the Like-Minded |
| False Color Flying Demonstration | 5 | 4 | Pirate-Masquerading Method |

`element: "Water"` on all five — **derived from the aspect tables** (Water: Brawl,
Bureaucracy, Investigation, Larceny, **Sail**), which is where every other Sail Charm's
Water comes from too; the stat blocks never print an element.

**4 Terrestrial Circle spells** (p.94: "all Terrestrial Circle and are not taught as
widely in the Heptagram"): Calling the Gulls with Beaks of Steel (25m), Invocation of
the Living Ship (20m), Keel Cleaves the Clouds (25m), Lightning Whip Smites the
Waters (15m). Terrestrial is the Dragon-Blooded's only circle, so they are castable.

## UI
`editor._SPLAT_ORIGINS["Dragon-Blooded"]` gained the four origins; the new
`editor.upbringing_options(exalt_type, origin)` drives a SECOND select rendered only
when non-empty, so no other splat grows a control. Render routes `/lookshy-editor`
and `/lookshy-sheet` in `tests/_ui_main.py` cover both selects and the origin-granted
Charm rows — the granted rows exist only at render time, since nothing stores them.

**Backgrounds** named by the four books and added to the autofill catalog (soft free
text, no mechanics): Arsenal, Cult, Sorcery, Retainers, Family. Command, Henchmen,
Contacts, Followers, Influence, Breeding and Reputation were already there.

**Not modelled from these pages:** Lookshy's Craft (First Age Weapons) / Craft (War) /
Linguistics (Heliocode) are Craft foci and specialties, which the project already
handles as free text; Arsenal's doubled cost is written for heroic mortals and belongs
with the Mortals splat; the Sorcerers of the Heptagram box (level 4 costs 4 BP instead
of 2, level 5 costs 8 instead of 4) is a Storyteller's-discretion sidebar.
