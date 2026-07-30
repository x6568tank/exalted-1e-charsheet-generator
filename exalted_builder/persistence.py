"""
persistence.py — load and save a Character (or a GM's Party) to/from JSON.

An edge module: pure I/O plus pydantic (de)serialisation, no game logic. It does
NOT validate legality — that is engine.validate's job — only structural validity,
which pydantic enforces on load. Rules data is loaded separately by rules_db.

Saves are written atomically (temp file + os.replace) so a crash mid-write cannot
truncate an existing save. JSON is indented for hand-editing. Enum-keyed dicts
(attributes/abilities/virtues) round-trip through their string values, e.g.
{"strength": 3} — see models.character.

A Party save embeds full Character copies, so it round-trips through exactly the
same machinery; the party helpers below mirror the character ones one for one.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

from .models.character import Character
from .models.party import Party

# Conventional extension for character saves (see .gitignore). Not enforced; any
# path is accepted.
SAVE_SUFFIX = ".character.json"

# Conventional extension for a GM party bundle.
PARTY_SUFFIX = ".party.json"


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


def atomic_write(path: str | os.PathLike, payload: str) -> Path:
    """Write `payload` to `path`, atomically. Creates parent directories if needed.
    Returns the path written.

    Writes to a temp file in the same directory then os.replace()s it, so the
    destination is never observed as a partially written file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

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


def _custom_content():
    """custom_content, imported lazily to break the cycle — it imports this module
    for `atomic_write` and `default_save_dir`. The builder does the same for ui.gm."""
    from . import custom_content
    return custom_content


def save_character(character: Character, path: str | os.PathLike, *,
                   embed_custom: bool = True,
                   custom_dir: str | os.PathLike | None = None) -> Path:
    """Write `character` to `path` as JSON, atomically. Creates parent directories
    if needed. Returns the path written.

    Also refreshes the homebrew definitions the character carries (see
    custom_content.embed_definitions), so a save handed to another player brings its
    custom Charms with it. This happens HERE, at the single choke point, rather than
    in each of the UI's save handlers — there are a dozen, and the one that got missed
    would produce a save that silently loses homebrew.

    `embed_custom=False` writes the character exactly as it is, for the rare caller
    that wants no filesystem read of the library.
    """
    if embed_custom:
        _custom_content().embed_definitions(character, custom_dir=custom_dir)
    return atomic_write(path, character_to_json(character))


def load_character(path: str | os.PathLike, *, absorb_custom: bool = True,
                   custom_dir: str | os.PathLike | None = None) -> Character:
    """Read and parse a Character from `path`. Propagates FileNotFoundError and
    pydantic.ValidationError unchanged so callers can distinguish them.

    Any homebrew definitions the save carries are absorbed into the local library
    (see custom_content.absorb_definitions) so the Charms resolve on this machine.
    Only ids the library lacks are written: the local copy always wins. A caller that
    wants to TELL the user what was imported passes `absorb_custom=False` and calls
    `custom_content.absorb_definitions` itself, which returns the ids it added — doing
    it here first would leave nothing for it to report.
    """
    text = Path(path).read_text(encoding="utf-8")
    character = character_from_json(text)
    if absorb_custom:
        _custom_content().absorb_definitions(character, custom_dir=custom_dir)
    return character


# --------------------------------------------------------------------------- #
# Party bundles (the GM's table copy — see models.party)
# --------------------------------------------------------------------------- #

def suggested_party_filename(party: Party) -> str:
    """The save filename a party should use, derived from its name — e.g.
    'Tuesday Game' -> 'tuesday-game.party.json'. An unnamed party falls back to
    'party.party.json' rather than the character-flavoured 'new-character'."""
    slug = slugify_name(party.name) if party.name.strip() else "party"
    return f"{slug}{PARTY_SUFFIX}"


def normalize_party_filename(text: str, party: Party) -> str:
    """The party filename to use given free-text user input. Mirrors
    normalize_save_filename: blank falls back to the party-derived name, an
    explicit '.json' is kept verbatim, anything else is a bare stem to slugify."""
    text = (text or "").strip()
    if not text:
        return suggested_party_filename(party)
    if text.endswith(".json"):
        return text
    return f"{slugify_name(text)}{PARTY_SUFFIX}"


def party_to_json(party: Party) -> str:
    """Serialise a Party to an indented JSON string."""
    return party.model_dump_json(indent=2)


def party_from_json(data: str) -> Party:
    """Parse a Party from a JSON string. Raises pydantic.ValidationError if the
    data is structurally invalid."""
    return Party.model_validate_json(data)


def save_party(party: Party, path: str | os.PathLike, *, embed_custom: bool = True,
               custom_dir: str | os.PathLike | None = None) -> Path:
    """Write `party` to `path` as JSON, atomically. Returns the path written.

    A party embeds full Character copies, so each member gets the same homebrew
    treatment a standalone save does — otherwise the GM's party file would be the one
    save format that loses custom Charms."""
    if embed_custom:
        cc = _custom_content()
        for member in party.members:
            cc.embed_definitions(member.character, custom_dir=custom_dir)
    return atomic_write(path, party_to_json(party))


def load_party(path: str | os.PathLike, *, absorb_custom: bool = True,
               custom_dir: str | os.PathLike | None = None) -> Party:
    """Read and parse a Party from `path`. Propagates FileNotFoundError and
    pydantic.ValidationError unchanged so callers can distinguish them.

    Absorbs every member's homebrew, so a GM opening the table's party file gets the
    whole group's custom content at once."""
    party = party_from_json(Path(path).read_text(encoding="utf-8"))
    if absorb_custom:
        cc = _custom_content()
        for member in party.members:
            cc.absorb_definitions(member.character, custom_dir=custom_dir)
    return party
