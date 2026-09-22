# Campaign page spike — three shapes for `/table/<id>`, with room for the board

> **THE MODEL, 2026-09-22.** The human approved shape **A** as it stands after round 5
> (*"There we go. Perfect"*) as the model for P3 step 3. `docs/plans/p3-tables.md` §15 is
> the plan built from it. `/b`, `/b-board` and `/c` are kept only as the record of what
> was compared and rejected. The spike does not track the shipped code.

Answers the human's note after the P3 step-2 click-through (2026-09-12): *"the campaign
window will probably need to be redesigned at some point"*, and on 2026-09-22: *"spike a
couple different campaign designs; remember it'll have the whiteboard."*

Throwaway. Nothing in `exalted_builder/` is edited. The cards read the shipped presenter
`view.build_party_card_view` over the four `examples/*.character.json`, with some damage
marked, so the numbers and name lengths are real. Members, requests, rolls and notes are
mock text. The board is a **placeholder** for P4, drawn inside decision 0020: strokes,
a shape, and tokens that are a colour plus a free-text label — no token knows a character.

## Run it

```sh
.venv/bin/python -m spikes.campaign_page     # http://localhost:8765/
```

Each page takes `?st=0` for the player view (the default is the Storyteller's).

| Path | Shape |
|---|---|
| `/a` | **Tabletop.** Party rail (compact rows) · board in the centre · a side rail with Rolls / Notes / ST tabs. The board is always on screen. |
| `/b` | **Tabs, like the builder.** Party (full cards, a grid) · Board · Notes & rolls · Storyteller (badge = waiting requests). One surface at a time; the Board tab can simply be absent until P4. |
| `/b-board` | B with the Board tab open. |
| `/c` | **Board + dock.** Board fills the page, the party is a dock of compact tiles along the bottom (collapsible), ST tools / rolls / notes in a right drawer. |

In all three, the ST's join requests are a badge in the top bar, and a player gets an
**Open as: <character> / Spectate** chooser there (P3 §7).

## Status

**The human chose A, 2026-09-22:** *"A tabletop is the best by far. B is just an
absolutely not, C is a little too cluttered."*

Then asked how a player spends motes in the player view: there were no controls. A's
player view now puts the viewer's own character first ("YOU PLAY") with live controls:
health boxes cycle on click, the motes have −5 / −1 / +1 / full, and Willpower and Limit are
clickable dot tracks. The others' rows stay read-only. Nothing ported.

Round 2, same day. The human: *"Mote controls work but are clunky."* Rulings: the ST does
**not** edit a player's trackers from the table (*"ST can tell them if they fucked up"*),
and adversaries go **at the bottom**, because *"everyone needs to be able to see them"*.
⚠ That second one reverses P3 §1's spectator ruling, which named the adversary roster as
ST-only. What a non-ST sees of an adversary is not yet ruled.

* Each mote pool is now a bar of what is left, with − and + at its ends; a click on the
  bar opens a box to type an amount and Spend / Regain / Full.
* Adversaries are three REAL catalogue templates, at the bottom of the party column, for
  everyone: name, category, health track, penalty. Only the ST's boxes click.

Round 3, same day. On advice from a friend who has run more 1E: **players see no enemy
stats; the adversary roster is ST-only** — back to P3 §1's ruling. A "let players see it"
ST toggle was floated and the human leans against it, so it is not built. Adversaries stay
at the bottom of the party column, on the ST's page only.

Round 4, same day. The human asked for a text chat; built as **one Log** replacing the
Rolls tab: messages and rolls in time order, a text box, and a dice count with **Roll**. If
the text box is filled when you roll, the text becomes the roll's caption — a caption the
player typed, never one the app chose (decision 0019). Members moved to the Notes tab.
The log is process-wide in the spike, so two browser windows (`/a` and `/a?st=0`) share
it; a 1 s `ui.timer` repaints on growth, the way the table page's poll will. Left out on
purpose: player↔ST whispers, unbounded history.

Round 5, same day. **Allied NPCs.** Asked *"do we have a system in place for allied NPCs?"*
— no. Rulings: **a setting on the roster entry, not a second kind of NPC**; players see an
ally's **name and health only**; **only the ST** marks an ally's trackers, *"for now"*.
The spike keeps the side in a dict (`SIDE`) standing in for an `Adversary.side` field.
The ST's rail shows ALLIES then ENEMIES, each entry with an **Ally / Enemy** switch; a
player's shows ALLIES only, as a name and a read-only health track. Deferred: linking an
ally to the Background that bought it (Familiar, Followers…).
