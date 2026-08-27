"""custom_content.py — where the user's OWN Charms, styles and spells live.

An edge module: filesystem paths only, no game logic and no rules parsing (that is
rules_db's job, which imports this to find the library).

The custom library holds the same file shapes as the shipped `data/` directory —
`charms/*.json` and `spells.json` — so anything `tools/md_to_charms.py` emits can be
dropped straight in, and rules_db can reuse the same loaders. What differs is how
failures are treated: a broken file in `data/` is a fatal RuleDataError, a broken
file here is reported and skipped. A Storyteller must not be able to brick the
builder with a typo in their homebrew.

Location, in order of precedence:
  1. $EXALTED_CUSTOM_DIR, if set — how the tests and a power user relocate it;
  2. `custom/` beside the executable in a packaged (PyInstaller) build, else
     `custom/` in the current working directory.

(2) deliberately mirrors persistence.default_save_dir(), which already puts saves
beside a double-clicked ExaltedBuilder: the user's characters and the homebrew they
depend on then sit in one place and can be copied together.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from pydantic import ValidationError

from .models.rules import Charm, Spell
from .persistence import atomic_write, default_save_dir

# Environment variable that relocates the whole library.
CUSTOM_DIR_ENV = "EXALTED_CUSTOM_DIR"

# Directory name used when the variable is unset.
CUSTOM_DIR_NAME = "custom"

# Every id the authoring page writes starts with this. Book ids are namespaced by
# splat and ability ("solar.melee.fire-and-stones-strike"), so reserving one prefix
# makes a collision with printed content impossible by construction rather than by
# checking. The user never types it: the form derives the id from the name.
ID_PREFIX = "custom."

# The file the page writes new rows into. Rows the user dropped into the library by
# hand live in whatever file they chose, and are edited in place there — this is only
# the destination for content created in the app.
CHARMS_FILE = "charms/custom-charms.json"
SPELLS_FILE = "spells.json"

# The gear library (2026-08-13). Same shapes as the shipped `data/` files, so a row
# copied out of one is a valid row here — and the same non-fatal treatment: a typo in
# homebrew must never brick the builder.
#
# Gear got this late because "custom" for equipment used to mean free text on ONE
# character: you invented a homebrew daiklave, and it existed on that sheet alone, to be
# retyped for the next character with no way to fix a mistake everywhere. Charms and
# spells have had the library since decision 0012; this is the same answer for the same
# problem.
GEAR_FILES = {
    "weapons": "weapons.json",
    "armor": "armor.json",
    "gear": "gear.json",
    "artifacts": "artifacts.json",
}


class CustomContentError(Exception):
    """A custom row could not be saved: it is structurally invalid, or its id is
    already taken by the rulebook. Carries a message meant for the user."""


def custom_data_dir() -> Path:
    """Where the user's custom rules data lives. Not created, and not guaranteed to
    exist — an absent library is the normal case and simply means no homebrew."""
    override = os.environ.get(CUSTOM_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return default_save_dir() / CUSTOM_DIR_NAME


def _dir(custom_dir: str | Path | None) -> Path:
    return Path(custom_dir) if custom_dir is not None else custom_data_dir()


def slug(text: str) -> str:
    """'White Crane Style!' -> 'white-crane-style'. Shared by ids and style keys."""
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def make_id(name: str) -> str:
    """The id the page assigns to a Charm/spell called `name`. Empty name -> "" so
    the caller can refuse to save rather than writing `custom.`."""
    s = slug(name)
    return f"{ID_PREFIX}{s}" if s else ""


def normalize_id(raw: str) -> str:
    """The id to store for `raw`, as typed by a user or read from imported JSON.

    A bare slug with no namespace ('house-strike') is taken to be homebrew and gets
    the prefix. Anything already namespaced is left alone — rewriting an id would
    break every character that references it — and `save_*` refuses it if it is not
    ours, which is a clearer failure than silently renaming someone's content.
    """
    raw = (raw or "").strip()
    if not raw or raw.startswith(ID_PREFIX):
        return raw
    return raw if "." in raw else f"{ID_PREFIX}{slug(raw)}"


def style_category(style_name: str) -> str:
    """A Martial Arts style name -> the Charm `category` that creates it. The picker
    derives its style groups from this string, so a new style needs nothing else."""
    return f"martial_arts:{slug(style_name)}"


# --------------------------------------------------------------------------- #
# reading the library
# --------------------------------------------------------------------------- #

def _read_rows(path: Path) -> list[dict]:
    """The rows in one library file. A missing or unreadable file reads as empty —
    the loader is what reports a broken file to the user; the writers must not also
    raise on it, or one bad file would make the whole page unusable."""
    if not path.exists():
        return []
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def charm_files(custom_dir: str | Path | None = None) -> list[Path]:
    """Every Charm file in the library, the page's own file first so a row created in
    the app is found there before any hand-dropped duplicate."""
    root = _dir(custom_dir)
    own = root / CHARMS_FILE
    rest = sorted(p for p in (root / "charms").glob("*.json") if p != own) \
        if (root / "charms").is_dir() else []
    return ([own] if own.exists() else []) + rest


def _locate(files: Iterable[Path], row_id: str) -> tuple[Optional[Path], int]:
    """Which file holds `row_id`, and at which index. (None, -1) when absent."""
    for path in files:
        for i, row in enumerate(_read_rows(path)):
            if row.get("id") == row_id:
                return path, i
    return None, -1


def library_charms(custom_dir: str | Path | None = None) -> list[dict]:
    """Every Charm row in the library, as raw dicts — what the authoring page lists
    and loads back into its form. Raw rather than parsed on purpose: a row that fails
    validation must still be editable, or a typo would be unfixable in the app."""
    return [row for path in charm_files(custom_dir) for row in _read_rows(path)]


def library_spells(custom_dir: str | Path | None = None) -> list[dict]:
    return _read_rows(_dir(custom_dir) / SPELLS_FILE)


# --------------------------------------------------------------------------- #
# writing
# --------------------------------------------------------------------------- #

def _validated(payload: dict, model, reserved_ids: Optional[set[str]]) -> Any:
    """Structural + id checks shared by both savers. `reserved_ids` is the BOOK's
    ids: homebrew may never shadow printed content, and catching it here gives the
    user a message on the spot instead of a row that loads and is then dropped."""
    row = dict(payload)
    row["id"] = normalize_id(str(row.get("id", "")))
    if not row["id"]:
        raise CustomContentError("Give it a name first — the id comes from the name.")
    if not row["id"].startswith(ID_PREFIX):
        raise CustomContentError(
            f"{row['id']!r} is not a custom id. Ids created here must start with "
            f"{ID_PREFIX!r} so they can never collide with the rulebook.")
    if reserved_ids and row["id"] in reserved_ids:
        raise CustomContentError(f"{row['id']!r} is already used by the rulebook.")
    row.pop("custom", None)          # the loader stamps this; never store it
    try:
        return model(**row)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "row"
        raise CustomContentError(f"{where}: {first['msg']}") from exc


def _upsert(path: Path, row: dict, index: int) -> None:
    rows = _read_rows(path)
    if index < 0:
        rows.append(row)
    else:
        rows[index] = row
    _atomic_rows(path, rows)


def save_charm(payload: dict, *, custom_dir: str | Path | None = None,
               reserved_ids: Optional[set[str]] = None) -> Charm:
    """Create or replace one custom Charm. Returns the parsed Charm; raises
    CustomContentError with a user-facing message if it will not do.

    Replacement keeps the id, which is the whole point — a character that owns the
    Charm keeps owning it across an edit. Only a DELETE can orphan a reference.
    """
    charm = _validated(payload, Charm, reserved_ids)
    root = _dir(custom_dir)
    path, index = _locate(charm_files(root), charm.id)
    if path is None:
        path, index = root / CHARMS_FILE, -1
    _upsert(path, charm.model_dump(mode="json", exclude={"custom"}), index)
    return charm


def save_spell(payload: dict, *, custom_dir: str | Path | None = None,
               reserved_ids: Optional[set[str]] = None) -> Spell:
    """Create or replace one custom spell. See save_charm."""
    spell = _validated(payload, Spell, reserved_ids)
    root = _dir(custom_dir)
    path = root / SPELLS_FILE
    _, index = _locate([path], spell.id)
    _upsert(path, spell.model_dump(mode="json", exclude={"custom"}), index)
    return spell


def library_gear(kind: str, custom_dir: str | Path | None = None) -> list[dict]:
    """The user's own rows for one gear kind — "weapons", "armor", "gear", "artifacts".

    Raw dicts, like `library_charms`: rules_db validates them against the same models
    the book data uses, and reports rather than raises on a bad row.
    """
    return _read_rows(_dir(custom_dir) / GEAR_FILES[kind])


def save_gear_row(kind: str, payload: dict, *,
                  custom_dir: str | Path | None = None,
                  reserved_ids: Optional[set[str]] = None) -> dict:
    """Put one gear row into the library, creating or replacing by id.

    Takes a plain dict rather than a model because the four kinds have four different
    models and this module deliberately holds no game logic — the caller has already
    built a row of the right shape from the character's own item, and rules_db is what
    validates it on the next load.

    ⚠ The id is REQUIRED and must carry `ID_PREFIX`. A library row that reused a
    printed id would shadow the book, and the book must always win a collision
    (`_load_custom_layer`); making the prefix a preconditon means the collision cannot
    be constructed rather than being caught later.
    """
    if kind not in GEAR_FILES:
        raise CustomContentError(f"unknown gear kind {kind!r}")
    row_id = str(payload.get("id") or "")
    if not row_id.startswith(ID_PREFIX):
        raise CustomContentError(
            f"a library id must start with {ID_PREFIX!r}; got {row_id!r}")
    if reserved_ids and row_id in reserved_ids:
        raise CustomContentError(f"{row_id!r} is already used by the rulebook")
    if not str(payload.get("name") or "").strip():
        raise CustomContentError("give it a name first")
    root = _dir(custom_dir)
    path = root / GEAR_FILES[kind]
    _, index = _locate([path], row_id)
    _upsert(path, payload, index)
    return payload


def _delete(files: Iterable[Path], row_id: str) -> bool:
    path, index = _locate(files, row_id)
    if path is None:
        return False
    rows = _read_rows(path)
    del rows[index]
    _atomic_rows(path, rows)
    return True


def delete_charm(charm_id: str, *, custom_dir: str | Path | None = None) -> bool:
    """Remove a custom Charm from the library. False if it was not there.

    A character that already owns it is NOT rewritten: the id stays on the character
    and shows as a missing row (⚠) on the sheet, with an `unknown-charm` error from
    engine.validate. Editing the character is the user's call, not this function's.
    """
    return _delete(charm_files(custom_dir), charm_id)


def delete_spell(spell_id: str, *, custom_dir: str | Path | None = None) -> bool:
    return _delete([_dir(custom_dir) / SPELLS_FILE], spell_id)


def delete_gear(kind: str, row_id: str, *,
                custom_dir: str | Path | None = None) -> bool:
    """Remove one gear row from the library. False if it was not there.

    ⚠ Written well after `save_gear_row` (2026-08-27), and its absence is why the gear
    half of the library was WRITE-ONLY: a row saved with a typo could be neither seen
    nor removed except by hand-editing the JSON. `library_gear` had exactly one caller
    — the loader — so nothing surfaced the list either.

    A character that already owns the item is NOT rewritten, for the same reason as
    `delete_charm`: saves carry inline COPIES of gear (decision 0007), so an owned
    weapon keeps working and only the shop's offer goes away.
    """
    if kind not in GEAR_FILES:
        raise CustomContentError(f"unknown gear kind {kind!r}")
    return _delete([_dir(custom_dir) / GEAR_FILES[kind]], row_id)


def parse_rows(text: str) -> list[dict]:
    """JSON text from the paste box or an uploaded file -> rows. Accepts a single
    object or an array of them, so pasting one Charm and importing a whole file are
    the same path."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CustomContentError(f"That is not valid JSON ({exc.msg}, line {exc.lineno}).") from exc
    rows = data if isinstance(data, list) else [data]
    if not all(isinstance(r, dict) for r in rows):
        raise CustomContentError("Expected a Charm object, or an array of them.")
    if not rows:
        raise CustomContentError("Nothing to import.")
    return rows


# --------------------------------------------------------------------------- #
# Travelling with a character: embed on save, absorb on load
#
# A character references Charms by id, so handing a save to another player would
# otherwise hand them a sheet full of ⚠ rows — the ids resolve only against the
# author's library. So the definitions the character actually uses ride along inside
# the save, and are absorbed into the recipient's library when it is opened.
#
# The library remains the store; the copy in the save is a carrier, not a second
# source of truth. On a conflict the LIBRARY wins: a recipient who has since edited
# their own copy of a Charm must not have it silently reverted by opening someone's
# character.
# --------------------------------------------------------------------------- #

def referenced_ids(character) -> tuple[set[str], set[str]]:
    """Every Charm id and Spell id a character mentions, from every list that can
    hold one: the installed Charms, the Alchemical Panoply, camp-granted Charms,
    Combo and Array membership, spells, and — for a locked character — the chargen
    snapshot, whose ids are what the XP audit re-prices against.

    Returned as (charm_ids, spell_ids). Missing a list here means the definition of a
    Charm used only there would not travel, so it walks the character rather than
    trusting a curated subset.
    """
    charms: set[str] = set()
    charms.update(character.charms, character.retainer_charms, character.granted_charms)
    for combo in character.combos:
        charms.update(combo.charm_ids)
    for array in character.arrays:
        charms.update(array.charm_ids)
    spells: set[str] = set(character.spells)
    snap = character.chargen_snapshot
    if snap is not None:
        charms.update(snap.charms)
        spells.update(snap.spells)
    return charms, spells


def _closure(rows: dict[str, dict], wanted: set[str]) -> list[dict]:
    """The rows for `wanted`, plus every custom row they depend on, transitively.

    A homebrew Charm's prerequisite may itself be homebrew: embedding the leaf alone
    would land in the recipient's library as a row the loader drops for a dangling
    prerequisite, which is the one failure mode this function exists to prevent.
    """
    out: dict[str, dict] = {}
    frontier = [i for i in wanted if i in rows]
    while frontier:
        rid = frontier.pop()
        if rid in out:
            continue
        row = rows[rid]
        out[rid] = row
        for group in row.get("prerequisites") or []:
            frontier.extend(p for p in group if p in rows and p not in out)
    return [out[k] for k in sorted(out)]


def collect_definitions(character, *, custom_dir: str | Path | None = None) -> dict:
    """The custom definitions `character` depends on, ready to embed. Empty dict when
    it uses no homebrew, which is the overwhelmingly common case."""
    charm_ids, spell_ids = referenced_ids(character)
    charm_rows = {r["id"]: r for r in library_charms(custom_dir) if r.get("id")}
    spell_rows = {r["id"]: r for r in library_spells(custom_dir) if r.get("id")}

    charms = _closure(charm_rows, charm_ids)
    spells = [spell_rows[i] for i in sorted(spell_ids) if i in spell_rows]
    out: dict[str, list[dict]] = {}
    if charms:
        out["charms"] = charms
    if spells:
        out["spells"] = spells
    return out


def embed_definitions(character, *, custom_dir: str | Path | None = None) -> int:
    """Refresh `character.custom_definitions` from the library. Returns how many rows
    were embedded.

    Rewritten from the library on every save rather than accumulated, so dropping a
    homebrew Charm from a character drops its definition too, and an edit to the
    Charm travels on the next save.

    A definition already carried by the character but NO LONGER in the library is
    KEPT: that is the case of a save made on another machine, opened here, and saved
    again — losing the row would strip the homebrew out of someone else's character.
    """
    fresh = collect_definitions(character, custom_dir=custom_dir)
    carried = character.custom_definitions or {}
    merged: dict[str, list[dict]] = {}
    for key in ("charms", "spells"):
        by_id = {r.get("id"): r for r in carried.get(key, []) if isinstance(r, dict)}
        by_id.update({r["id"]: r for r in fresh.get(key, [])})
        rows = [by_id[k] for k in sorted(by_id) if k]
        if rows:
            merged[key] = rows
    # Only keep ids the character still references — otherwise a save accumulates the
    # definitions of every homebrew Charm it has ever held.
    charm_ids, spell_ids = referenced_ids(character)
    if "charms" in merged:
        keep = {r["id"] for r in _closure({r["id"]: r for r in merged["charms"]}, charm_ids)}
        merged["charms"] = [r for r in merged["charms"] if r["id"] in keep]
    if "spells" in merged:
        merged["spells"] = [r for r in merged["spells"] if r.get("id") in spell_ids]
    merged = {k: v for k, v in merged.items() if v}
    character.custom_definitions = merged
    return sum(len(v) for v in merged.values())


def absorb_definitions(character, *, custom_dir: str | Path | None = None) -> list[str]:
    """Import the definitions a save carries into the library. Returns the ids added.

    Only ids the library does not already have are written — the library wins any
    conflict, so opening a character never silently rewrites the recipient's own
    version of a Charm. Rows are written raw, WITHOUT validation: a malformed one is
    the loader's problem to report (and the authoring page's to fix), and refusing it
    here would leave the recipient with a character referencing a Charm whose only
    copy had just been thrown away.
    """
    carried = character.custom_definitions or {}
    if not carried:
        return []
    root = _dir(custom_dir)
    added: list[str] = []

    have_charms = {r.get("id") for r in library_charms(root)}
    new_charms = [r for r in carried.get("charms", [])
                  if isinstance(r, dict) and r.get("id") and r["id"] not in have_charms]
    if new_charms:
        path = root / CHARMS_FILE
        _atomic_rows(path, _read_rows(path) + new_charms)
        added += [r["id"] for r in new_charms]

    have_spells = {r.get("id") for r in library_spells(root)}
    new_spells = [r for r in carried.get("spells", [])
                  if isinstance(r, dict) and r.get("id") and r["id"] not in have_spells]
    if new_spells:
        path = root / SPELLS_FILE
        _atomic_rows(path, _read_rows(path) + new_spells)
        added += [r["id"] for r in new_spells]

    return added


def _atomic_rows(path: Path, rows: list[dict]) -> None:
    atomic_write(path, json.dumps(rows, indent=2) + "\n")
