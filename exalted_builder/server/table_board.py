"""
server/table_board.py — the board of a campaign: a shared picture of the table.

Step 1 of the build order in `docs/plans/p4-board.md` section 6. The rulings are
section 5 (2026-09-25):

  * One board for each table, in `<table folder>/board.json`. The background
    image is `<table folder>/board/background.img`.
  * Each member changes each object: a player, the Storyteller too (Q1). A member
    who spectates watches. The page tells `put` that it spectates.
  * Only the Storyteller clears the board and sets the background (Q1, Q2).
  * No hidden layer (Q4). Each member sees each object.

⚠ Decision 0020: the board holds a PICTURE of the table, never a MODEL of it. No
object has a field that names a character, a copy or an NPC. A token label is
the text that a person typed. `tests/test_table_board.py` greps this module for
the names of the model and holds the list of the permitted fields.

⚠ Each object model refuses an unknown field (`extra="forbid"`). Thus a field that
a browser adds is an error, not a silent drop.

⚠ Each call asks `TableStore.access`. A page that shows a control only to the
Storyteller is not a check.

⚠ The background is opened as an image and encoded again. The bytes of the upload
are never written.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import io
import json
import logging
from pathlib import Path
from typing import Annotated, Literal, Union

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import (AfterValidator, BaseModel, ConfigDict, Field, TypeAdapter,
                      ValidationError)

from ..persistence import atomic_write, atomic_write_bytes
from .tables import STORYTELLER, TableStore

log = logging.getLogger(__name__)

BOARD_FILE = "board.json"
BOARD_DIRNAME = "board"
BACKGROUND_FILE = "background.img"

# Design choices, reversible (p4-board.md section 2).
MAX_OBJECTS = 1000
MAX_POINTS = 2000
MAX_LABEL = 40
MAX_TEXT = 500
COORD_LIMIT = 20_000.0

# The background (Q2). The cap applies to the encoded file.
MAX_BACKGROUND_BYTES = 2 * 1024 * 1024
MAX_SIDE = 4096
MAX_INPUT_PIXELS = 40_000_000
_INPUT_FORMATS = ("PNG", "JPEG", "WEBP", "GIF")


class TableBoardError(ValueError):
    """A change that the board refuses. The message is safe to show to the user."""


# ---- the objects ------------------------------------------------------------ #

ObjectId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")]
Colour = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Coord = Annotated[float, Field(ge=-COORD_LIMIT, le=COORD_LIMIT, allow_inf_nan=False)]
Width = Annotated[float, Field(ge=1, le=50, allow_inf_nan=False)]


def _even_points(points: list[float]) -> list[float]:
    """Refuse an odd count of numbers. Round each number to one decimal."""
    if len(points) % 2:
        raise ValueError("points are x, y pairs")
    return [round(p, 1) for p in points]


class _Object(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class Stroke(_Object):
    """A freehand line: `points` is x0, y0, x1, y1, and so on."""

    kind: Literal["stroke"]
    id: ObjectId
    points: Annotated[list[Coord], Field(min_length=4, max_length=2 * MAX_POINTS),
                      AfterValidator(_even_points)]
    colour: Colour
    width: Width


class Shape(_Object):
    """A rectangle or an ellipse in the box `x`, `y`, `w`, `h`. A line or an arrow
    goes from `x`, `y` to `x + w`, `y + h`."""

    kind: Literal["shape"]
    id: ObjectId
    shape: Literal["rect", "ellipse", "line", "arrow"]
    x: Coord
    y: Coord
    w: Coord
    h: Coord
    colour: Colour
    fill: Colour | None = None
    width: Width


class Text(_Object):
    """A text that a person typed, at `x`, `y`."""

    kind: Literal["text"]
    id: ObjectId
    x: Coord
    y: Coord
    text: Annotated[str, Field(min_length=1, max_length=MAX_TEXT)]
    size: Annotated[float, Field(ge=8, le=200, allow_inf_nan=False)]
    colour: Colour


class Token(_Object):
    """A disc of `colour` at `x`, `y`, with the radius `r`. `label` is the text that
    a person typed, and it can be empty."""

    kind: Literal["token"]
    id: ObjectId
    x: Coord
    y: Coord
    r: Annotated[float, Field(ge=5, le=500, allow_inf_nan=False)]
    colour: Colour
    label: Annotated[str, Field(max_length=MAX_LABEL)]


_MODELS = (Stroke, Shape, Text, Token)
_ADAPTER: TypeAdapter = TypeAdapter(
    Annotated[Union[_MODELS], Field(discriminator="kind")])  # noqa: UP007


def object_fields() -> dict[str, set[str]]:
    """Return the permitted fields of each kind of object, by kind."""
    return {model.model_fields["kind"].annotation.__args__[0]: set(model.model_fields)
            for model in _MODELS}


def parse_object(data: object) -> dict:
    """Return the object `data` in its stored form. Raise `TableBoardError` for an
    object that is not valid."""
    try:
        return _ADAPTER.validate_python(data).model_dump()
    except ValidationError as exc:
        raise TableBoardError("That drawing is not valid.") from exc


# ---- the state -------------------------------------------------------------- #


@dataclass(frozen=True)
class Background:
    """The background image. Its pixels are the units of the board. `stamp` is the
    version of the board that set it. The address of the image contains it."""

    width: int
    height: int
    mime: str
    stamp: int = 0


@dataclass(frozen=True)
class BoardState:
    """The board at `version`. `objects` is in the order of the layers, the bottom
    first. `version` goes up by one at each change."""

    version: int
    objects: tuple[dict, ...]
    background: Background | None


_EMPTY = BoardState(version=0, objects=(), background=None)


class TableBoard:
    """Read and write the board of each table of `tables`."""

    def __init__(self, tables: TableStore) -> None:
        self.tables = tables

    def path(self, table_id: str) -> Path:
        """Return the path of the board of `table_id`. Raise `ValueError` for a
        malformed id."""
        return self.tables.table_dir(table_id) / BOARD_FILE

    def _background_path(self, table_id: str) -> Path:
        return self.tables.table_dir(table_id) / BOARD_DIRNAME / BACKGROUND_FILE

    # ---- reads -------------------------------------------------------------- #

    def state(self, user_id: int, table_id: str) -> BoardState:
        """Return the board of `table_id` for the member `user_id`. Refuse a viewer
        who is not a member."""
        self._role(user_id, table_id)
        return self._read(table_id)

    def version(self, table_id: str) -> int:
        """Return the version of the board. Do not check the access."""
        return self._read(table_id).version

    def background_file(self, user_id: int, table_id: str) -> Path | None:
        """Return the background image of `table_id` for the member `user_id`.

        Give None to a viewer who is not a member, and for no background.
        """
        if self.tables.access(user_id, table_id) is None:
            return None
        if self._read(table_id).background is None:
            return None
        path = self._background_path(table_id)
        return path if path.is_file() else None

    def _read(self, table_id: str) -> BoardState:
        """Return the stored board. An absent file gives an empty board. A file that
        does not read gives an empty board, and a warning in the server log."""
        path = self.path(table_id)
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return _EMPTY
        try:
            data = json.loads(raw)
            background = data.get("background")
            return BoardState(
                version=int(data["version"]),
                objects=tuple(parse_object(item) for item in data["objects"]),
                background=None if background is None else Background(
                    width=int(background["width"]), height=int(background["height"]),
                    mime=str(background["mime"]), stamp=int(background.get("stamp", 0))))
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            log.warning("The board %s does not read: %s", path, exc)
            return _EMPTY

    # ---- the objects -------------------------------------------------------- #

    def put(self, user_id: int, table_id: str, data: object, *,
            spectating: bool = False) -> BoardState:
        """Add the object `data`, or replace the object with its id. Return the board.

        A new object goes on top. A replaced object keeps its layer. Refuse a
        viewer who is not a member, a spectator, an object that is not valid, and
        a new object on a full board.
        """
        self._require_player(user_id, table_id, spectating)
        item = parse_object(data)
        state = self._read(table_id)
        objects = list(state.objects)
        for index, existing in enumerate(objects):
            if existing["id"] == item["id"]:
                objects[index] = item
                break
        else:
            if len(objects) >= MAX_OBJECTS:
                raise TableBoardError(
                    f"The board is full: {MAX_OBJECTS:,} objects. Delete some first.")
            objects.append(item)
        return self._write(table_id, state, objects)

    def put_many(self, user_id: int, table_id: str, items: object, *,
                 spectating: bool = False) -> BoardState:
        """Add or replace each object of `items` in one version. Return the board.

        Each new object goes on top, in the order of `items`. Refuse the whole list
        if one object is not valid, if an id repeats, or if the new objects do not
        fit on the board. Refuse a viewer who is not a member, and a spectator.
        """
        self._require_player(user_id, table_id, spectating)
        if not isinstance(items, list) or not items or len(items) > MAX_OBJECTS:
            raise TableBoardError("That drawing is not valid.")
        parsed = [parse_object(data) for data in items]
        ids = [item["id"] for item in parsed]
        if len(set(ids)) != len(ids):
            raise TableBoardError("That drawing is not valid.")
        state = self._read(table_id)
        objects = list(state.objects)
        where = {o["id"]: n for n, o in enumerate(objects)}
        new = [item for item in parsed if item["id"] not in where]
        if len(objects) + len(new) > MAX_OBJECTS:
            raise TableBoardError(
                f"The board is full: {MAX_OBJECTS:,} objects. Delete some first.")
        for item in parsed:
            if item["id"] in where:
                objects[where[item["id"]]] = item
        return self._write(table_id, state, objects + new)

    def delete_many(self, user_id: int, table_id: str, object_ids: list[str], *,
                    spectating: bool = False) -> BoardState:
        """Remove each object of `object_ids` in one version. Return the board. An
        absent id changes nothing. Refuse a viewer who is not a member, and a
        spectator."""
        self._require_player(user_id, table_id, spectating)
        gone = set(object_ids)
        state = self._read(table_id)
        objects = [o for o in state.objects if o["id"] not in gone]
        if len(objects) == len(state.objects):
            return state
        return self._write(table_id, state, objects)

    def restack_many(self, user_id: int, table_id: str, object_ids: list[str], *,
                     front: bool, spectating: bool = False) -> BoardState:
        """Move each object of `object_ids` to the top layers (`front`) or to the
        bottom layers, in one version. The moved objects keep their order between
        them. Return the board. A move that changes no layer writes nothing."""
        self._require_player(user_id, table_id, spectating)
        chosen = set(object_ids)
        state = self._read(table_id)
        moved = [o for o in state.objects if o["id"] in chosen]
        rest = [o for o in state.objects if o["id"] not in chosen]
        objects = rest + moved if front else moved + rest
        if tuple(objects) == state.objects:
            return state
        return self._write(table_id, state, objects)

    def delete(self, user_id: int, table_id: str, object_id: str, *,
               spectating: bool = False) -> BoardState:
        """Remove the object `object_id`. Return the board. An absent id changes
        nothing. Refuse a viewer who is not a member, and a spectator."""
        self._require_player(user_id, table_id, spectating)
        state = self._read(table_id)
        objects = [o for o in state.objects if o["id"] != object_id]
        if len(objects) == len(state.objects):
            return state
        return self._write(table_id, state, objects)

    def to_front(self, user_id: int, table_id: str, object_id: str, *,
                 spectating: bool = False) -> BoardState:
        """Move the object `object_id` to the top layer. Return the board. An
        absent id, or an object on the top layer, changes nothing."""
        return self._restack(user_id, table_id, object_id, spectating, front=True)

    def to_back(self, user_id: int, table_id: str, object_id: str, *,
                spectating: bool = False) -> BoardState:
        """Move the object `object_id` to the bottom layer. Return the board. An
        absent id, or an object on the bottom layer, changes nothing."""
        return self._restack(user_id, table_id, object_id, spectating, front=False)

    def _restack(self, user_id: int, table_id: str, object_id: str, spectating: bool,
                 *, front: bool) -> BoardState:
        return self.restack_many(user_id, table_id, [object_id], front=front,
                                 spectating=spectating)

    # ---- the Storyteller ---------------------------------------------------- #

    def clear(self, user_id: int, table_id: str) -> BoardState:
        """Remove each object. Keep the background. Return the board. Refuse a
        viewer who is not the Storyteller."""
        self._require_storyteller(user_id, table_id)
        return self._write(table_id, self._read(table_id), [])

    def set_background(self, user_id: int, table_id: str, raw: bytes) -> BoardState:
        """Open `raw` as an image, encode it again, and make it the background.
        Return the board.

        Scale the image down to `MAX_SIDE` pixels on its longer side. Keep an image
        with transparency as PNG, and encode each other image as JPEG. Refuse a
        viewer who is not the Storyteller, bytes that are not an image, an image of
        more than `MAX_INPUT_PIXELS`, and a result of more than
        `MAX_BACKGROUND_BYTES`.

        ⚠ The quota of the table folder applies (`atomic_write_bytes`). Its error
        propagates.
        """
        self._require_storyteller(user_id, table_id)
        payload, background = _encode_background(raw)
        state = self._read(table_id)
        atomic_write_bytes(self._background_path(table_id), payload)
        return self._write(table_id, state, list(state.objects),
                           replace(background, stamp=state.version + 1))

    def remove_background(self, user_id: int, table_id: str) -> BoardState:
        """Remove the background. Return the board. Refuse a viewer who is not the
        Storyteller."""
        self._require_storyteller(user_id, table_id)
        state = self._read(table_id)
        state = self._write(table_id, state, list(state.objects), None)
        self._background_path(table_id).unlink(missing_ok=True)
        return state

    # ---- checks and writes -------------------------------------------------- #

    def _role(self, user_id: int, table_id: str) -> str:
        role = self.tables.access(user_id, table_id)
        if role is None:
            raise TableBoardError("You are not in this campaign.")
        return role

    def _require_player(self, user_id: int, table_id: str, spectating: bool) -> None:
        self._role(user_id, table_id)
        if spectating:
            raise TableBoardError("A spectator watches the board.")

    def _require_storyteller(self, user_id: int, table_id: str) -> None:
        if self._role(user_id, table_id) != STORYTELLER:
            raise TableBoardError("Only the Storyteller can do that.")

    _KEEP = object()

    def _write(self, table_id: str, state: BoardState, objects: list[dict],
               background: Background | None | object = _KEEP) -> BoardState:
        """Write `objects` and `background` as the next version of `state`.

        ⚠ The quota of the table folder applies (`atomic_write`). Its error
        propagates.
        """
        if background is TableBoard._KEEP:
            background = state.background
        new = BoardState(version=state.version + 1, objects=tuple(objects),
                         background=background)
        atomic_write(self.path(table_id), json.dumps({
            "version": new.version,
            "objects": list(new.objects),
            "background": None if background is None else {
                "width": background.width, "height": background.height,
                "mime": background.mime, "stamp": background.stamp},
        }, ensure_ascii=False))
        return new


def _encode_background(raw: bytes) -> tuple[bytes, Background]:
    """Return the encoded image of `raw` and its size. Raise `TableBoardError` for
    bytes that are not an image, too many pixels, or a result that is too large."""
    try:
        with Image.open(io.BytesIO(raw), formats=_INPUT_FORMATS) as image:
            if image.width * image.height > MAX_INPUT_PIXELS:
                raise TableBoardError(
                    f"That image is too large: {image.width} x {image.height} pixels.")
            image = ImageOps.exif_transpose(image)
            alpha = image.mode in ("RGBA", "LA", "PA") or (
                image.mode == "P" and "transparency" in image.info)
            image = image.convert("RGBA" if alpha else "RGB")
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            out = io.BytesIO()
            if alpha:
                image.save(out, "PNG", optimize=True)
            else:
                image.save(out, "JPEG", quality=85)
            size = image.size
    except TableBoardError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError,
            Image.DecompressionBombError) as exc:
        raise TableBoardError("That file is not an image that the board can show.") \
            from exc
    payload = out.getvalue()
    if len(payload) > MAX_BACKGROUND_BYTES:
        raise TableBoardError(
            f"That image is {len(payload) / 2**20:.1f} MB after it is encoded. "
            f"The limit is {MAX_BACKGROUND_BYTES / 2**20:.0f} MB.")
    return payload, Background(width=size[0], height=size[1],
                               mime="image/png" if alpha else "image/jpeg")

