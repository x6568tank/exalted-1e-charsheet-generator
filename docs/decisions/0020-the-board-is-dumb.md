# 0020 — The board is dumb: a picture of the table, not a model of it

**Status:** Accepted, 2026-09-11. Scopes the spatial surface of the hosted table planned in
`docs/plans/vtt.md`. Protects [0008](0008-no-combat-derivation.md) and applies the same cut
[0019](0019-a-dumb-dice-roller.md) applies to the dice roller.

⚠ Nothing here authorises building the board. It fixes what the board may be **if** it is
built. Whether it ships is open question 5 of `docs/plans/vtt.md`.

## Problem

A hosted table wants a shared visual surface — a map, a sketch, tokens to push around. Every
virtual tabletop has one, and a player who has used one will expect it.

The danger is not drawing. It is that a spatial surface is the most natural possible home
for the thing [0008](0008-no-combat-derivation.md) rejected. Once a token is on a board, the
board knows where it is; once it knows where two tokens are, it knows the distance between
them; once it knows the distance, "is he in reach?" is a subtraction. **Combat derivation
arrives by geometry rather than by anyone deciding to add it.**

This is the identical failure mode [0019](0019-a-dumb-dice-roller.md) records for the
roller: *"the thin end: once the app knows a pool, rolling it is a small change."* There,
the safety mechanism was the gap between the pool and the roll box. Here it is the gap
between a token and a character.

## Decision

**The board may hold a PICTURE of the table. It may not hold a MODEL of the table.**

In scope:

* Background images, freehand strokes, shapes, erase, clear.
* Tokens: an image or a colour, plus a **free-text label the player or Storyteller types**.
* Moving, resizing, deleting and layering those objects.
* One shared, persisted board per table, synchronised between connected clients.
* A **decorative** grid — it is a background image and carries no rule.

Out of scope, and this is what keeps [0008](0008-no-combat-derivation.md) and
[0016](0016-base-dice-pools-are-in-scope.md) intact:

* **A token that knows it is a `Character`.** No link from a board object to a character id,
  no derived traits on a token, no health track, no Essence pool, no initiative order drawn
  on the board.
* **Distance, range bands, reach, movement rates, facing, cover, line of sight.** Each is
  combat derivation entering through a side door.
* **Any rule keyed to position.** The board never answers "can I reach him", "am I in
  cover", "how far can I move this turn".
* **A grid with enforced movement**, snapping that means something, or measured templates.
* **Fog of war derived from a character's senses.** A GM hiding part of an image by hand is
  drawing; the app computing what a character can see is modelling.

### ⚠ The load-bearing part

**The moment a token knows which character it is, the next ask is "how far can I move", and
no test will fail when that line is crossed.**

That sentence is the whole record. It is the same one [0019](0019-a-dumb-dice-roller.md)
writes about binding a roll definition to a roll result, and it needs the same two defences:

1. **A structural discriminator, not a behavioural one.** A board object carrying a
   character id, or the board module importing from `engine/`, is a **grep**. The working
   model is `CLAUDE.md` §13's Merit rule — *"No module outside `engine/merits.py` can name a
   Merit id. A test finds violations"* — and the handoff's own lesson: **reach for a grep
   test whenever a defect is a repeated literal.** Testing that the board "does not compute
   distance" proves nothing, because a board that does not yet compute distance and a board
   that may not are the same bytes. That is the attunement-by-absence shape again.
2. **The click-through list.** A convenience that quietly binds a token to a character will
   look like an improvement in review and will pass every test.

⚠ **The token label is free text, for [0019](0019-a-dumb-dice-roller.md)'s reason exactly.**
A label the app chose is the app asserting the board is right. A label the player wrote is
the player's claim. Auto-filling a token's label from a linked character is not a shortcut —
it *is* the link this record forbids, wearing a cosmetic disguise.

## Alternatives rejected

* **No board at all.** Costs the one thing a table with a map actually wants, to protect a
  line that a structural test can hold instead. This record exists so the board is
  affordable rather than forbidden.
* **A board that links tokens to characters but computes nothing.** The link is the whole
  risk; computing nothing is a property of today's code, not of the design. Rejected as the
  version that generates every subsequent ask.
* **A full tactical VTT** — grid movement, ranges, templates, line of sight. This is
  [0008](0008-no-combat-derivation.md)'s rejected scope in its entirety, plus modelling
  Charm effects across 1,921 Charms, which is what made the old Merits & Flaws
  implementation unmaintainable ([0011](0011-merits-and-flaws-return-centralized.md)).
* **Deciding later, once the board exists.** A scope record written after the code is a
  description, not a decision. This is why it is ratified before P4 rather than during it.

## Consequences

* The board is a **presentation module with no engine dependency**, and that absence is
  enforced by a grep test rather than by intent.
* 1e is not a grid game, so the cost of this record is low in practice: the printed rules
  give movement in yards and no battle map, and there is no positional subsystem being
  withheld.
* **The board is severable.** It is phase P4 of `docs/plans/vtt.md` and nothing before it
  depends on it.
* Board state is **table state, not character state**. It is not play-state under
  [0006](0006-play-state-is-isolated.md) and it never touches validation — consistent with
  [0019](0019-a-dumb-dice-roller.md)'s ruling that roll results are a transcript, not
  permanent state.
* If a future session wants range bands, **this record is what it must reopen**, and only
  the human can. Citing "the board already knows the positions" is not an argument; it is
  the prediction this record makes.
