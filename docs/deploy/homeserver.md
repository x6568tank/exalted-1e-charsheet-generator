# Deploying to the home server (`gilserver`, 192.168.1.2)

Written 2026-09-12 from a read-only look at the server as the `claude` account.
**APPLIED 2026-09-12** — the human ran steps 2–4; `https://exalted.x6568tank.com` serves
commit `7cd594f`. Checked from outside through Cloudflare: the public pages and `HEAD` answer
200, `/home` and `/gm` send a visitor to the login page, and the session cookie arrives as
`__Host-exalted-session; path=/; httponly; samesite=lax; secure`. The first `curl -I` gave
405 (FastAPI adds no HEAD to a GET route) — fixed in `7cd594f`. Step 6 (the backup
snapshot) is the human's to add. Steps marked **(gil)** need the `docker` or `sudo` group;
`claude` has neither, on purpose.

## What the server already looks like

* Ubuntu 24.04, 8 cores, 15 GB RAM, 408 GB free on `/`.
* **Every app is a container in one Compose file**, `/home/gil/homelab/docker-compose.yml`,
  one folder per app bind-mounted as `./<app>/…`, `restart: unless-stopped`,
  `container_name` set. Watchtower (`nickfedor/watchtower`) auto-updates images.
* **HTTPS is a Cloudflare Tunnel**: `cloudflared` runs as a root systemd service from
  `/etc/cloudflared/config.yml`, which maps each `*.x6568tank.com` hostname to a
  `localhost` port and ends in an `http_status:404` catch-all. Nothing listens on 80/443.
  ⚠ This is what makes login work: the session cookie is `Secure` + `__Host-`, and the
  browser only keeps it over HTTPS. **Players use `https://exalted.x6568tank.com`, never
  `http://192.168.1.2:…`**, even on the LAN.
* Ports in use: 8080 (Filebrowser), 8082, 8083, 8096, 3001, 6233, 6234. **8090 is free.**
* `backup.sh` tars all of `/home/gil/homelab/` daily into `/storage/backups/<date>/`
  (30 days kept), so `./exalted/data` and the `.env` are backed up with no new tar line.
  `/storage` is a separate **~12 TB ZFS RAIDZ2 pool** (the human, 2026-09-12); the source
  data sits on the NVMe root disk. So an NVMe failure loses at most a day. What it does not
  cover is loss of the whole machine or pool (fire, theft, ransomware, a root `rm -rf`) —
  an off-site copy is the human's call, not a deploy step.

## One-time setup

### 1. The code (claude)

The code goes to `/home/claude/exalted-app` by `rsync` from the dev machine — no GitHub
key on the server (the repo is private). `gil` runs the build, so the folder must be
readable to `gil`:

```bash
# from the dev machine, in the repo — ship the COMMIT, not the working tree:
E=$(mktemp -d) && git archive HEAD | tar -x -C "$E" && git rev-parse --short HEAD > "$E/DEPLOYED_COMMIT"
rsync -a --delete --delete-excluded --exclude-from=.dockerignore "$E/" claude@192.168.1.2:exalted-app/
rm -rf "$E"
# on the server, as claude (the chmod 711 once; the a+rX after every sync):
chmod 711 /home/claude && chmod -R a+rX /home/claude/exalted-app
```

`cat /home/claude/exalted-app/DEPLOYED_COMMIT` says which commit the server builds.

### 2. The data folder and the secret (gil)

```bash
mkdir -p ~/homelab/exalted/data
# The key that signs the session cookie. ⚠ Keep it: a new key logs every player out.
echo "EXALTED_STORAGE_SECRET=$(openssl rand -hex 32)" >> ~/homelab/.env
chmod 600 ~/homelab/.env
```

### 3. The Compose entry (gil)

Add under `services:` in `~/homelab/docker-compose.yml`:

```yaml
  exalted:
    build: /home/claude/exalted-app
    image: exalted-builder:local
    container_name: exalted
    restart: unless-stopped
    ports:
      - "127.0.0.1:8090:8080"          # only cloudflared on this host can reach it
    environment:
      EXALTED_STORAGE_SECRET: ${EXALTED_STORAGE_SECRET}
      EXALTED_SESSION_ROOT: /data/sessions
      EXALTED_DB_PATH: /data/accounts/exalted.db
      EXALTED_ADMIN_CONTACT: admin@x6568tank.com
    volumes:
      - ./exalted/data:/data           # accounts, characters, homebrew, NiceGUI storage
    labels:
      - com.centurylinklabs.watchtower.enable=false   # built here; nothing to pull
```

Then:

```bash
cd ~/homelab && docker compose up -d --build exalted
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8090/     # expect: 200
```

⚠ The port is published on `127.0.0.1` only, unlike the other services. That is on
purpose: the plain-HTTP LAN address cannot log anyone in, so it should not be reachable.

### 4. The tunnel (gil, sudo)

In `/etc/cloudflared/config.yml`, add **above** the final `- service: http_status:404`:

```yaml
  - hostname: exalted.x6568tank.com
    service: http://localhost:8090
```

Then the DNS record, and a restart:

```bash
sudo cloudflared tunnel route dns <tunnel-name-or-id> exalted.x6568tank.com
sudo systemctl restart cloudflared
```

If `route dns` complains about a missing `cert.pem`, add the record in the Cloudflare
dashboard instead: a proxied `CNAME` `exalted` → `<tunnel-id>.cfargotunnel.com`. (The
tunnel id is the name of the `.json` file in `/etc/cloudflared/`.)

### 5. Check it

* `https://exalted.x6568tank.com/` shows the front page; `/wiki` works logged out.
* Sign up → lands on the builder at `/home`. Log out → back on `/`.
* In the browser's dev tools, the cookie `__Host-exalted-session` is `Secure`.

### 6. The backup snapshot (gil) — recommended

`tar` copies the account database while the app may be writing it. Add this line to
`backup.sh` **before** the first `tar`, so the archive holds a consistent copy too:

```bash
docker exec exalted python -c "import sqlite3; s=sqlite3.connect('/data/accounts/exalted.db'); d=sqlite3.connect('/data/accounts/exalted.snapshot.db'); s.backup(d); d.close(); s.close()"
```

To restore, stop the container and copy `exalted.snapshot.db` over `exalted.db`.

## Updating to a new build

1. (claude) Commit, then sync as in step 1.
2. (gil) `cd ~/homelab && docker compose up -d --build exalted`

A restart drops the live sessions; hosted saves are written through, so a player loses
at most the edit in flight, and logs in again only if the secret changed.

## Running it

* **Reset a password** (the reset is manual by design — `hosting-state-model.md` §5.1d):
  `docker exec -it exalted python -m exalted_builder.server.users reset <username>`
  (and `… users list`). It asks for the new password on the terminal.
* **Logs:** `docker logs -f exalted`.
* **Uptime Kuma** (port 3001): an HTTP monitor on `https://exalted.x6568tank.com/` covers
  the tunnel and the app together.

## Before it is public

* ⚠ **The About text is a draft** (`exalted_builder/server/public.py`) until the human
  approves it.
* The known limits of the login gate are in `docs/plans/hosting-state-model.md` §5.1d
  (a reset does not end existing logins; signup is not rate-limited; no account delete;
  homebrew is outside the quota).
