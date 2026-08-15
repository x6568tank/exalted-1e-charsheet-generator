# Phase 1 — the never-opened books (2026-08-15)

The first half of the "one last scan" before 1.0. **Scope: the books that had never
contributed a single authored entry and have a usable PDF text layer.** Phase 2 (the
two scan-only books) is not started.

## Result in one line

**Five books extracted, 331 pages. Twenty-two gear rows authored (`gear.json` 56 → 78).
Every Charm the scan found was already out of scope by a ruling made on 2026-08-14.**

That is a *good* outcome, not a thin one: it is direct evidence the catalogue is closer
to complete than "six books never opened" suggested.

## How the six books were identified

A census of every `source.book` in `data/` against `sources/`. ⚠ **The first census was
wrong** — it walked only the `{book, page}` dict shape and missed every plain-string
`source`, which made Kingdom of Halta look untouched when it already had five artifacts.
Both shapes must be walked; `_authored_books()` in `tests/test_data.py` now does it and
is the copy to reuse.

## What was extracted

`tools/extract_born_digital.py`, whole-book, into `images/_extracted/`:

| Book | Pages | GARBLED pages |
|---|---|---|
| Bastions of the North | 145 | 10 |
| Houses of the Bullgod | 129 | 6 |
| Kingdom of Halta | 91 | 8 |
| Creatures of the Wyld (Extra) | 27 | 6 |
| Tomb of Five Corners | 23 | 11 |

## What was authored — 22 gear rows, `gear.json` 56 → 78

**Kingdom of Halta pp.89-93** (20 rows), the printed `PLANTS AND MEDICINES` and
`TALISMANS` sections, as `goods` under two new categories (`Halta — Plants and
Medicines`, `Halta — Talismans`):

> blood berries · coldvine · Deathlord's breath · iron bush · liar's mushroom ·
> message seed · mother's moss · succor blossom · totem leaf · Wyld seeds ·
> Young Monkey · bark-skin charm · cat claws (initiative) · cat claws (Dexterity) ·
> ground charm (iron) · ground charm (iron nutshell) · ground charm (worked amber) ·
> hunter's shirt · lucky rock · lucky javelin or boomerang

**Bastions of the North** (2 rows) — the ice weasel fur (p.39) and the glider (p.98),
both under existing M&C categories.

`GearType` has no description field, so each row's printed effect lives in `notes`,
along with the printed cost string verbatim. Two rows are `resources_cost: 0` because
the page prints a price of none — the message seed ("None within Halta") and the lucky
rock ("Nothing for rocks"). **Those zeroes are authored, not missing.**

⚠ **The ice weasel row prices the FUR, not the animal.** The page reads "ice weasel
furs… among the most expensive in Creation"; the weasel itself has a creature stat line
(Str/Dex/Sta 4/6/4, Bite 6/9/6L, dodge/soak 12/6L/10B) and is an adversary-roster beast
that has NOT been authored. Reading "ice weasel — Resources •••" as a purchasable
animal is the error this row was one step away from.

⚠ **`Bastions of the North` is a new `source.book`**, and the guard added in the same
session (`test_every_source_book_is_a_canonical_name`) failed on it immediately, naming
the file. That is the intended workflow: a genuinely new book is added to
`CANONICAL_BOOKS` **and** to the table in `docs/source-attribution.md`, together.

## The dual-cost rows — the ruling, and why it is not one rule

Eight printed entries carry TWO Resources costs and `GearType.resources_cost` is one
`int`. **The rules authority ruled on 2026-08-15 that the encoding follows the REASON
there are two numbers**, which is not the same reason in each case. Do not collapse
this into a single rule later.

**A. Two genuinely different products → one row each.** The page is pricing separate
items, not a range.

| Entry | Cheap | Dear | Rows |
|---|---|---|---|
| Cat claws (p.92) | `••` +2 base initiative | `•••` +1 die Dexterity | 2 |
| Ground charms (p.93) | `••` iron scrap (= corebook warding charm, p.337) **or** `••` iron nutshell (tastes bitter near fey) | `•••` worked amber (the fey *may* accept it as a bribe) | **3** |
| Lucky rock (p.93) | free — a found stone that returns to its owner | `•••` a made javelin/boomerang: returns **and** +1–2 dice accuracy | 2 |

⚠ Ground charms is **three** rows off two prices: the iron charm and the nutshell share
`••` and do entirely different things. A price is not an identity.

**B. An open-ended quality tier → ONE row at the defined price.** The hunter's shirt
prints `••` for +1 die to Stealth while hunting, and `•••` for versions the page
refuses to define ("might confer additional dice or actually attract prey animals").
Splitting would invent a product the book deliberately left to the Storyteller.

**C. One product, two markets → ONE row, priced OUTSIDE the region of origin.**
Mother's moss `••••` (`••` in Halta), ice weasel fur `••••` (`•••` in the North),
glider `•••` (`••` in the North). The consistency argument is the **p.89 blanket
rule** — *"Assume that the Resources cost is one lower to obtain the product within the
Republic"* — which means every other printed Haltan price already IS the
general-Creation figure. Pricing mother's moss at `••` would have made it the only
domestically-priced row in the set. The local price is preserved in `notes`; a
location-dependent price still has no model and this does not argue for one.

⚠ **Mother's moss was nearly authored as a clean single value.** The first read
truncated at the `Cost:` line; the second figure is three lines further down, in prose.
**A cost line does not end where the line ends** — and the same mistake would have hit
the ice weasel and the glider, whose second figures also sit mid-sentence.

⚠ **The hunter's shirt heading came out as**
`<!--SHATTERED HEADING, name unreadable: 'H UNTER ’ S SHIRT'-->`. Rule 0 blocks a
marked passage even when the name is legible, so it went to the human, who cleared it
(2026-08-15). The row records that in its `notes`. **The rule held; the exception was
granted by the authority, not taken.**

## What the scan found that is already out of scope

**Every Charm the scan turned up is creature-embedded**, which you ruled out on
2026-08-14. Naming them so a future sweep does not re-report them:

* **Bastions of the North pp.42-43** — Gale of Barbs, Might of the Slaughterer, Primal
  Fusion, Turning Steel. Printed under a `UNIQUE CHARMS` heading inside the stat block
  of **Vorvin-Derlin, Slayer of Armies**, a behemoth, whose own `Charms:` line names
  all four.
* **Kingdom of Halta p.58** — Den of Shadows, "a unique Charm" of the Shade Tiger.
* **Creatures of the Wyld (Extra) p.3** — the Ebon Curtain, a power of the Shrouded Ones.

## What has no model, and is not proposed

* **Houses of the Bullgod p.110** — Fire Galleons, a warship stat block (Damage, Rate,
  Range, Crew). There is no vehicle model and this is not an argument for one.
* **The glider's vehicle stat block** (Bastions p.98: Speed 3, Maneuver 3, Armor 3L/5B,
  Health Levels 10, Repair 2) — the same shape as the Fire Galleons. Only its Resources
  price was catalogue-able; the stat line has nowhere to go. The rarer **Folding
  Gliders** are in Caste Book: Night p.78 and are not authored either.
* **The ice weasel as a creature** — see the warning above. A roster candidate, not a
  gap.
* **Houses of the Bullgod, passim** — Resources figures embedded in setting prose
  ("maintaining it costs at least Resources ••• every month"). Prices in a narrative,
  not a catalogue.

⚠ **Both Bastions rows were ruled IN scope by the human on 2026-08-15** and are
authored; what is listed here is the residue each left behind, not the row itself.

## Tomb of Five Corners — genuinely nothing

23 pages, an adventure module. Zero Charms, zero spells, zero priced rows, zero
Merits. It is now *checked*, which is worth more than it sounds: it can come off every
future list of unopened books.

## Merits and Backgrounds — the record-type blind spot, half closed

The 2026-08-14 scan was keyed on printed stat blocks and so was structurally blind to
Merits, Backgrounds and rituals. For Merits that blindness turns out to have cost
nothing: all **52** Player's Guide merit/flaw cost-lines diff clean against
`data/merits_flaws.json` (170 entries), and **none of these five books prints a single
Merit or Flaw**. Backgrounds and prose-described artifacts in the eight transcribed
books remain unswept.

⚠ The first Merit matcher returned **0 hits in all eight transcribed books** — the
printed shape is `(1- PT . MERIT )`, letter-spaced small caps, not `(1 pt. Merit)`.
A zero from a sweep is a claim about the matcher until you have looked at one page.

## What phase 2 is

The two scan-only books — **Creatures of the Wyld (130 pp.)** and **Scavenger Sons
(144 pp.)** — rasterised with `pdftoppm` and read directly. Creatures of the Wyld is a
bestiary, and its Charms will be creature-embedded, so the expected yield there is
adversary templates on top of the 49 already shipped. **Scavenger Sons is the likelier
payload.**
