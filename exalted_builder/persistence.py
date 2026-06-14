"""
persistence.py — load and save a Character to/from JSON.

An edge module: pure I/O plus pydantic (de)serialisation, no game logic. It does
NOT validate legality — that is engine.validate's job — only structural validity,
which pydantic enforces on load. Rules data is loaded separately by rules_db.

Saves are written atomically (temp file + os.replace) so a crash mid-write cannot
truncate an existing save. JSON is indented for hand-editing. Enum-keyed dicts
(attributes/abilities/virtues) round-trip through their string values, e.g.
{"strength": 3} — see models.character.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

from .models.character import Character

# Conventional extension for character saves (see .gitignore). Not enforced; any
# path is accepted.
SAVE_SUFFIX = ".character.json"


def slugify_name(name: str) -> str:
    """Filesystem-safe stem from a character name: lower-cased, runs of
    non-alphanumerics collapsed to single hyphens, trimmed. A blank/symbol-only
    name falls back to 'new-character' so a file always has a sensible stem."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "new-character"


def suggested_filename(character: Character) -> str:
    """The save filename a character should use, derived from its name —
    e.g. 'Ashes-of-Dawn' -> 'ashes-of-dawn.character.json'."""
    return f"{slugify_name(character.name)}{SAVE_SUFFIX}"


def normalize_save_filename(text: str, character: Character) -> str:
    """The save filename to use given free-text user input. Blank falls back to the
    character-derived name; a name that already ends in '.json' is kept verbatim
    (so 'hero.character.json' or 'hero.json' are honoured); anything else is treated
    as a bare stem and slugified with the conventional suffix appended."""
    text = (text or "").strip()
    if not text:
        return suggested_filename(character)
    if text.endswith(".json"):
        return text
    return f"{slugify_name(text)}{SAVE_SUFFIX}"


def default_save_dir() -> Path:
    """Where new saves should land by default: next to the executable in a
    packaged (PyInstaller) build, otherwise the current working directory. So a
    double-clicked ExaltedBuilder writes its .character.json beside itself, in
    whatever folder it was launched from."""
    if getattr(sys, "frozen", False):          # PyInstaller bundle
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def character_to_json(character: Character) -> str:
    """Serialise a Character to an indented JSON string."""
    return character.model_dump_json(indent=2)


def character_from_json(data: str) -> Character:
    """Parse a Character from a JSON string. Raises pydantic.ValidationError if
    the data is structurally invalid."""
    return Character.model_validate_json(data)


def save_character(character: Character, path: str | os.PathLike) -> Path:
    """Write `character` to `path` as JSON, atomically. Creates parent directories
    if needed. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = character_to_json(character)

    # Write to a temp file in the same directory, then atomically replace, so the
    # destination is never a partially written file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, path)
    except BaseException:
        # Best-effort cleanup of the temp file on any failure.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def load_character(path: str | os.PathLike) -> Character:
    """Read and parse a Character from `path`. Propagates FileNotFoundError and
    pydantic.ValidationError unchanged so callers can distinguish them."""
    text = Path(path).read_text(encoding="utf-8")
    return character_from_json(text)
