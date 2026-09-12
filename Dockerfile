# The hosted server (`python -m exalted_builder.server.main`) in a container.
# docs/deploy/homeserver.md gives the Compose entry, the tunnel rule and the steps.
#
# ⚠ ONE process, one worker. The session registry holds live objects. See
# docs/plans/hosting-state-model.md section 3.4.
#
# ⚠ Each piece of state is under /data, which is a volume: the accounts, the
# characters, the homebrew library and the NiceGUI storage. The image holds none.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    NICEGUI_STORAGE_PATH=/data/nicegui \
    EXALTED_CUSTOM_DIR=/data/custom

WORKDIR /app

# ⚠ The `[server]` extra of pyproject.toml is the one list of the dependencies.
# Do not copy the list into this file.
# The server runs from /app, not from site-packages, because `branding.assets_dir`
# finds `assets/` beside the package. `python -m` puts /app first on the path.
COPY pyproject.toml ./
COPY exalted_builder ./exalted_builder
COPY assets ./assets
RUN pip install --no-cache-dir ".[server]"

# The owner of the files in /data. 1000:1000 is the account that owns the Compose
# folder on the home server. Change it in Compose with `user:`.
USER 1000:1000

EXPOSE 8080

# ⚠ `--host 0.0.0.0` is inside the container only. Compose publishes the port on
# 127.0.0.1 of the host, thus only the tunnel on that host can reach it.
CMD ["python", "-m", "exalted_builder.server.main", "--host", "0.0.0.0", "--port", "8080"]
