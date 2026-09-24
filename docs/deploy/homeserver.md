# Deploying to the home server

⚠ **This repository is PUBLIC**, so this file is published. It holds what the app needs
from its host and how a build reaches it, and nothing about the host itself. Keep out of
it: secrets, keys, access rules, addresses, ports of other services, the backup layout.
The server is described in the human's private homelab repository.

The live site is `https://exalted.x6568tank.com`. First deployed 2026-09-12 (`7cd594f`).
Checked from outside then: the public pages and `HEAD` answer 200, `/home` and `/gm` send
a visitor to the login page, and the session cookie arrives as
`__Host-exalted-session; path=/; httponly; samesite=lax; secure`.

## What the app needs from the host

* **HTTPS in front of it.** The session cookie is `Secure` + `__Host-`, and a browser only
  keeps it over HTTPS. A plain-HTTP address cannot log anyone in, so the container is
  published on `127.0.0.1` only and reached through the HTTPS proxy. **Players use
  `https://exalted.x6568tank.com`**, even on the LAN.
* **One secret**, `EXALTED_STORAGE_SECRET`, in the Compose `.env`. ⚠ Keep it: a new key
  logs every player out.
* **One data folder**, mounted at `/data`: accounts, characters, homebrew, NiceGUI storage.
* **One process.** `reload=False`; the registry holds live objects (`server/main.py`).

The Compose entry:

```yaml
  exalted:
    build: <the synced code folder>
    image: exalted-builder:local
    container_name: exalted
    restart: unless-stopped
    mem_limit: 2g                      # see "The memory limit" below
    ports:
      - "127.0.0.1:8090:8080"
    environment:
      EXALTED_STORAGE_SECRET: ${EXALTED_STORAGE_SECRET}
      EXALTED_SESSION_ROOT: /data/sessions
      EXALTED_DB_PATH: /data/accounts/exalted.db
      EXALTED_ADMIN_CONTACT: admin@x6568tank.com
    volumes:
      - ./exalted/data:/data
    labels:
      - com.centurylinklabs.watchtower.enable=false   # built locally; nothing to pull
```

### The memory limit

✅ **Applied 2026-09-24**: the container was recreated with it, and
`docker stats` shows a limit of 2 GiB (about 100 MiB in use at idle).

It protects the *other* apps on the host from this one. Without a limit, a container that
leaks or spikes takes memory from the rest, and the kernel's OOM killer picks the victim,
which need not be `exalted`. With it, only `exalted` dies, and `restart: unless-stopped`
brings it back. 2 GB is well above the need: `SessionRegistry` caps at 200 live contexts
with LRU eviction (`server/session.py`). Raise it if `docker stats exalted` shows it near
the ceiling in normal play.

## Updating to a new build

1. Commit. Ship the COMMIT, not the working tree:

   ```bash
   E=$(mktemp -d) && git archive HEAD | tar -x -C "$E" && git rev-parse --short HEAD > "$E/DEPLOYED_COMMIT"
   # then rsync "$E/" to the server's code folder, with --delete --exclude-from=.dockerignore
   rm -rf "$E"
   ```

   The host, the account, the folder and the permissions step are in the dev machine's
   notes, not here. `DEPLOYED_COMMIT` in the code folder says which commit the server builds.
2. Rebuild: `docker compose up -d --build exalted`, by the human or by the route the human
   set up for Claude (2026-09-24; not described here).
3. Check from outside: `/`, `/wiki` and `/login` answer 200; `/home` sends a visitor to the
   login page; the container log says NiceGUI is ready.

A restart drops the live sessions. Hosted saves are written through, so a player loses at
most the edit in flight, and logs in again only if the secret changed.

## Running it

* **Reset a password** (manual by design, `hosting-state-model.md` §5.1d):
  `docker exec -it exalted python -m exalted_builder.server.users reset <username>`
  (and `… users list`). It asks for the new password on the terminal.
* **Logs:** `docker logs -f exalted`.
* **Backups:** the host's backup makes a consistent copy of the account database first,
  with the SQLite backup API, as `/data/accounts/exalted.snapshot.db`. To restore, stop the
  container and copy `exalted.snapshot.db` over `exalted.db`.
* **Monitoring:** ⚠ NONE (checked 2026-09-24). An Uptime Kuma HTTP monitor on
  `https://exalted.x6568tank.com/` would cover the proxy and the app together; it was
  planned but never created. Adding one is the human's step in the Kuma UI.

## Before it is public

* The About prose is **Lorem Ipsum by the human's choice** (*"feel free to change it to
  Lorem Ipsum for now"*, 2026-09-12) (`exalted_builder/server/public.py`).
* ✅ A real browser signup worked through the tunnel (the human, 2026-09-12).
* The known limits of the login gate are in `docs/plans/hosting-state-model.md` §5.1d
  (a reset does not end existing logins; signup is not rate-limited; no account delete;
  homebrew is outside the quota).
