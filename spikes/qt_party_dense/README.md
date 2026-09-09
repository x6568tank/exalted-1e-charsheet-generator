# Qt Party-tab density spike — two shapes against the card grid

> **RESOLVED 2026-09-09 — the human took B** (*"B is easily the best"*), with two
> amendments: the per-box **wound-penalty caption stays** (spike B dropped it to hover),
> and the row actions get **a border** rather than flat muted text. B is now the shipped
> Qt Party tab — `docs/plans/qt-port.md`, "The Party tab is a LIST plus a fixed RAIL".
> **The webapp's `/gm` was deliberately left alone.** This spike is kept only as the
> record of what was compared; it is not a live proposal, and it does NOT track the
> shipped code (its numbers were the pre-measurement guesses).

Answers the human's note of 2026-09-09: *"it's currently card-based, which feels off
compared to the rest of the app… for gm management i don't think we need to use that
much space & scrolling"*.

Throwaway. Nothing in `exalted_builder/` is edited — both spikes read the **same
presenters the shipped tab reads** (`view.build_party_card_view`, `view.batch_roster` /
`batch_rows`), so the numbers on screen are a real party's, not a mock's. If a direction
lands, a follow-up ports it into `exalted_builder/qt/party.py`.

## Run it

```sh
.venv/bin/python -m spikes.qt_party_dense           # the window, three tabs
.venv/bin/python -m spikes.qt_party_dense --render  # three PNGs into renders/
```

Both open at **1250x950** — the size the complaint was measured against — with a demo
party of the four `examples/*.character.json` and the first six **real** adversary
templates. Ten combatants, some damage already marked.

The third tab is the **shipped `PartyPage`, unmodified**, in the same window at the same
size. The comparison has to be against the thing itself, not a memory of it.

## The measurement

Scrollable content height for the same ten combatants, viewport 1250x950:

| | content | viewport | verdict |
|---|---|---|---|
| **A — combat line** | **358px** | 689px | everything above the fold, 1.9× headroom |
| **B — two columns** | **505px** | 919px | everything above the fold, 1.8× headroom |
| Today — cards | **2,097px** | 814px | **2.6 screens**; adversaries start at the fold, the roller is far below it |

## A — the combat line

One **row per combatant**, party and adversaries in ONE list (a fight is run off one
screen, which is already why the roster cards moved onto this tab). The row is
`▸ · name · what it is · health strip · penalty · E · WP · Limit`, ~31px tall.

- Health is **inline and uncaptioned**. The per-box wound-penalty caption is what makes
  the shipped card tall — it doubles the track's height, and triples it for an Ox-Body
  character whose track wraps. The penalty is carried once as text beside the strip, and
  per box on hover.
- The **▸ expander** opens the rest in place: mote spinners, the Willpower/Limit strips,
  notes, the four buttons. Nothing is removed, it is one click away.
- The **batch roller is docked** at the bottom, outside the scroll area, and its own row
  list scrolls at 150px so the dock cannot grow with the roster.

## B — two columns

A **two-line block per combatant** on the left; the batch roller and session notes in a
**fixed 330px right rail**. Middle density: the mote spinners and both count strips stay
on screen, and the height is bought back by dropping the card frame, the captions and the
button row (the buttons become a flat text strip on the right of the stat line).
Adversaries go two-up underneath, since their blocks are shorter.

## What to judge

1. **Which density.** A is a combat tracker; B keeps more of the tab as a dashboard. They
   are not exclusive — A's row with B's rail is a legitimate third answer.
2. **Is losing the per-box wound-penalty caption acceptable?** That is the single biggest
   height saving in both, and it is the one thing a Storyteller reads off a card
   mid-fight. Hover carries it in both spikes; on ten rows that may not be enough.
3. **Where the roller belongs** — docked bottom (A) or a rail (B). Independent of 1.
4. **B's flat text buttons** — do Sheet/PDF/Builder/Remove read as clickable at that
   weight, or do they look like more stat text?

## What this deliberately does NOT do

- ⚠ **Neither is a master-detail.** The Party tab is the THIRD written exception to the
  port's one collection layout *because* these are live trackers with nothing to select
  (`docs/plans/qt-port.md`); a detail pane would hide the health tracks the surface exists
  to show. What is under attack here is the card-grid-and-scroll structure, which is not
  what makes it an exception.
- ⚠ **Decision 0019's no-wire rule is untouched.** Every batch count is typed, no row
  offers a named roll, nothing reads a pool. A denser layout is not a licence to fill
  those boxes from a `PoolRow`.
- Play-state stays isolated (decision 0006) — clicks go through `engine.play`, exactly as
  the shipped tab does.

## Traps this spike re-paid

- ⚠ **`Ignored` horizontal policy beats `setFixedWidth`.** The elided-label class used for
  the stretchy columns collapsed the name and splat columns to nothing and let the health
  strip paint over them. Already written up against the batch roll's name column in
  `qt/party.py`; it bit again on the first render. Fixed columns elide against their own
  known width (`_column`), stretchy ones use the `Ignored` class (`_Elided`) — one class
  cannot be both.
- ⚠ **The first grab lies, and it lies unfairly.** `PartyPage._fit_columns` measures the
  viewport, and a viewport measured before the layout settles reports **one** column where
  the real window reflows to two — which would have made the card page look twice as bad
  as it is. The render pass reloads it after the layout settles.
- `Adversary.health_levels` is a **list of wound penalties**, and `damage` is a tracker
  aligned positionally to it — not a count and a total.
