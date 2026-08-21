# Qt app-shell spike — the master-detail layout as the whole UI

The Edit-tab redesign spike grew into a shell mockup, because the layout the human
liked (a left rail + content + a readout bar) is really the whole app's pattern.
This spike shows **the entire app** in that shape:

- a **top toolbar** (New / Load / Save / Print / Finish & Lock / Unlock / Party) —
  accent-filled by `qt/theme.py`'s QSS;
- a **left rail of app tabs** — Identity / Traits / Gear / Advantages / Charms /
  Combos / Play / ST Options / Custom / Sheet, all peers at one level (the app's
  `viewmod._TABS` with the Edit tab split into Identity + Traits), selected item in
  the splat accent;
- the selected tab's content — **Identity** and **Traits** are the sections that
  started this, the rest are placeholders;
- a **readout bar** (budget · validation) whose "≡ details" opens the
  click-to-open popover (full issue list + bonus-point breakdown);
- a **bottom status strip** (Willpower · pools · Soak).

It reuses `qt/theme.py` and `qt/editor.py`'s widgets unchanged; nothing in
`exalted_builder/` is edited. Throwaway — if the direction lands, a follow-up ports
the layout into `exalted_builder/qt/`.

## Run the window (real display)

```sh
.venv/bin/python -m spikes.qt_edit
```

Loads `examples/ashes-of-dawn.character.json` (a chargen Solar) or falls back to a
fresh Solar. Click the app rail, then the Identity/Traits sub-rail inside Edit; open
"≡ details" on the readout bar.

## What to judge

- The one-level rail — does splitting Edit into Identity + Traits at the top level
  hold up, and do the page headings feel redundant against the rail?
- The top toolbar + readout bar + status strip as the shell chrome.
- Whether the whole-app pattern holds for the other tabs' future content.
