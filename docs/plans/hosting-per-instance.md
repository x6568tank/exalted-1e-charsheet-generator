# Hosting: one container per player

**A rejected alternative to `hosting-state-model.md`, kept for its findings.** That
document specifies a multi-user server (accounts, a DB, session-scoped state) and remains
the right plan *if* multi-user is ever wanted. This one changed the question instead of
answering it: rather than teaching one process to serve many players, run one process per
player and let the container boundary do the isolation.

**Status: DECLINED 2026-08-28** (human: *"this is a clunky solution — I'd rather keep
the current versions"*). It was built and smoke-verified that day — the image built, the
container served, saves landed in the volume — and then **reverted in full**. No code,
Dockerfile or compose file from it remains in the tree.

Kept because two findings from the build are real and outlive the approach (see
**What this cost, and what survived it**), and because the trade-off table below is the
honest comparison to reach for if hosting is ever reconsidered.

⚠ **Nothing in this document describes code that exists.** The `--save-dir` flag,
`_SERVER_SAVE_DIR` and `server_save_dir()` were reverted; `builder.save()` still branches
two ways, and a hosted Save would still download to the player's browser.

## Why this instead

`ui/builder.py` builds its `ctx` once in `main()` and both `@ui.page` routes close over
it, so a single process serves a single character to everyone who connects. The
multi-user plan's §3 exists entirely to fix that — ~5 days, and the riskiest part of the
work.

⚠ **One player per container is not a deployment style here. It is the isolation
mechanism.** Adding a second player to one instance is a data-loss bug, not a config
change. Everything below depends on it.

| | Multi-user app | Per-player instances |
|---|---|---|
| Session refactor | ~5 days, the risky part | not needed |
| Auth | login page, bcrypt, sessions (~200 lines) | Cloudflare Access, zero app code |
| Character isolation | your bug to get right | kernel-enforced |
| Homebrew cross-contamination | must be solved | dissolved (see below) |
| Effort | 10–12 days | ~1 day |

**Measured cost per instance:** the merged `RuleSet` is **14 MB** resident; a Python
process with NiceGUI imported is **73 MB**. Call it ~110 MB. Six players ≈ 660 MB on a
16 GB box alongside the existing stack.

**What you give up:** no character index page, no accounts, no sharing between players.
The GM sees the party through the existing `.party.json` bundle, not a live DB.

## What this cost, and what survived it

### The one code change it needed (built, then reverted)

Everything else was already deployment-ready — `persistence.default_save_dir()` returns
`Path.cwd()` (so `WORKDIR /data` is enough) and `custom_content.custom_data_dir()`
already honours `EXALTED_CUSTOM_DIR`. One thing was not:

⚠ **The top-bar Save downloaded to the browser and kept nothing on the server.**
`builder.save()` branched on `_native_window()` — native gets an OS dialog, everything
else gets `ui.download.content`. That was correct when "plain browser" meant *the process
is yours, running on your own machine*: a download was the only place a file could go.
A hosted instance breaks the assumption — the browser is remote, but there IS a canonical
server-side home.

**This is the shape that hides.** A hosted Save would have shown the player a green
"Downloading …" toast and left the volume empty. It looks like it worked.

The fix is a third branch, gated on a new `--save-dir` (or `EXALTED_SAVE_DIR`):

- native window → OS "Save As" dialog *(unchanged)*
- `--save-dir` set → write straight to the volume, no dialog *(new)*
- otherwise → browser download *(unchanged)*

Also added: `--host`, because `ui.run()`'s default does not accept connections from
outside a container.

⚠ `_SERVER_SAVE_DIR` is a module-level global set once at startup. That is safe **only
because this deployment is one player per process.** It is the first thing to revisit if
that ever stops being true.

Tests: four in `tests/test_builder.py`, asserting on **the written file** rather than on
`server_save_dir()` returning a path — a flag being set is the "single read site in the
phase that wrote it" trap and proves nothing about whether Save persists. Reverted with
the rest.

⚠ **The finding survives the revert.** `builder.save()`'s native-vs-browser branch is
correct for the two deployments that exist and silently wrong for any third one. Any
future hosted, remote or kiosk deployment hits it, and it fails in the worst way — a
green "Downloading …" toast over an empty volume. **Whoever adds a third deployment must
add a third branch**, and will not be warned by anything in the code today.

## What per-instance dissolves for free

⚠ `persistence.load_character()` calls `custom_content.absorb_definitions()` by default
(`persistence.py:174`) — **loading a character WRITES to the custom library.** On a
shared `custom/` volume that means one player opening a save injects their homebrew into
everyone's library. The multi-user plan has to solve this. Here, `EXALTED_CUSTOM_DIR`
points at each container's own volume and the problem cannot occur.

Cost of that: homebrew is per-player, so a table sharing a house rule copies it, or the
GM ships it inside the `.party.json` bundle (saves already carry their homebrew — see
decision 0012).

## Deploy (the shape it took; files no longer in the tree)

Four files, none touching the app: a `Dockerfile` (`WORKDIR /data`, non-root,
`--save-dir`), a compose file with one service per player off a YAML anchor, a
cloudflared ingress fragment, and a backup script writing dated tarballs. All deleted.

Measured while it ran, in case the numbers are wanted again: image **280 MB**, container
served `/` and `/gm` at HTTP 200, and a save written inside the container appeared on the
host side of the volume.

⚠ **`user: "1000:1000"` in the compose is required, not hygiene.** Without it the
container runs as root and every character file lands root-owned `0600` in the volume —
which `backup.sh`, running as `gil`, cannot read. Verified both ways: root-owned without
it, `gil`-owned with it.

⚠ **Cloudflare Access in front of every hostname.** This app has no login page and no
concept of a user; it was built as a single-user desktop tool. An un-gated hostname is
the character, the homebrew library and the ST screen open to whoever finds the name.
Access is what makes per-instance safe, and it is what replaces the auth the multi-user
plan would have needed.

## Why it was declined

The human's call, 2026-08-28: **clunky.** Fairly — the approach trades an application
problem for an operations one, and the bill is per player. Adding someone is a
copy-pasted compose block, a port bump and a DNS route; six players is six containers,
six volumes, six hostnames and six things to notice when one stops. It scales to a table,
not to an audience, and it makes the admin visible in a way a login page does not.

⚠ **It was never the cheap answer it looked like.** The estimate said "~1 day", and that
was true of the Docker work — but the build immediately turned up a code change the app
needed (above) and a file-ownership bug that would have broken backups silently. A plan
whose selling point is "no code changes" is worth re-checking the moment the first one
appears.

**If it is ever reconsidered, three things were left undone:** nobody clicked it through
a browser or the tunnel (so Save-across-restart and Cloudflare's 100s WebSocket idle
timeout are both untested); the copyright question below was unanswered; and building on
the server needs the repo cloned there.

⚠ **The copyright question is independent of all of this and still open.** `data/`
carries ~1.8 M characters of transcribed rulebook prose — roughly 361 pages — and the
GitHub repo is private for that reason. Any hosted deployment, per-instance or
multi-user, changes the exposure profile from "a binary handed to five friends" to "a
service on the open internet." Access-gating helps; serving mechanics without the
verbatim descriptions would help more.

## What this does not decide

The `ctx` finding in `hosting-state-model.md` §3 is a real defect independent of hosting,
and its §3.8 isolation test is worth writing whenever that is touched. Per-instance would
have routed *around* it, not fixed it — and declining per-instance leaves it exactly where
it was. **The builder still serves one process-global `Character` to every connection.**
That is harmless for a desktop app run by one person, which is what this is, and it is the
first thing to fix if that ever changes.

The second surviving finding is the `absorb_definitions()` write-on-load above. It is
latent today for the same reason — one user, one machine — and it is a real hazard the
moment two people share a `custom/` directory by any route, hosting or not.
