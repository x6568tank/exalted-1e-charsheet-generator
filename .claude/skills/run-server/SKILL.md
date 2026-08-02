---
name: run-server
description: Run the NiceGUI builder app so the human can drive it in a browser — for every click-through, and for the human's "run the server" requests. Use when a work item is "tests green, not browser-verified", when the human asks to start the app, or when a running server is showing stale behaviour.
---

# Running the builder server

The browser click-through is how engine work gets verified, and every server run has
the same shape. The app is a NiceGUI builder: `exalted_builder/ui/builder.py` wraps
`ui.run`, one process, `reload=False`.

## 1. The command

```
.venv/bin/python -m exalted_builder.ui.builder [character.json] --port 8080
```

- No character arg → the default example character loads.
- Pass a save path (e.g. `/tmp/fae-noble.character.json`) to open that character at
  startup — how every Godblooded/Fae-Blooded click-through has been launched.
- `--show` auto-opens a browser tab; without it the human opens `http://localhost:8080`
  themselves.

## 2. reload=False means code changes require a restart

The running process does NOT pick up edits. If the server was started before a change
(any engine/UI/data edit), it is showing stale behaviour and must be restarted before
the human clicks anything. Kill-and-restart:

```
fuser -k 8080/tcp
sleep 1
.venv/bin/python -m exalted_builder.ui.builder <save> --port 8080 &
```

Run it as a background task (Bash `run_in_background`), then wait for it with an until
loop on `curl -s -o /dev/null http://localhost:8080` before telling the human it is up.

## 3. Smoke test before handing over

The server being up is not the same as the pages building. Curl the root to confirm
HTTP 200, and — when a specific page was touched — hit the route directly. The render
routes in `tests/_ui_main.py` are the reliable way to reproduce a page shape without
the human; drive them through the test harness (they need the NiceGUI User fixture,
not a browser).

## 4. The human's click-through saves

Click-through saves live in `/tmp/*.character.json` and are throwaway (the app's own
Save writes into the project save dir). For a checklist that needs a specific illegal
or stale shape, craft the save by editing a known-good one's JSON before launching —
e.g. the review-fix pass needed a Fae-Blooded save carrying `"origin": "Solar"` to
exercise the stale-origin editor path.

## 5. The checklist comes first

Give the human the numbered click-list BEFORE they open the browser, aimed at the
shapes the change produces, not a tour of the app. End the handover with: server URL,
what to click in order, and what each one should show. See the `preflight` skill for
what to check before booking browser time at all.
