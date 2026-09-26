"""The board of a campaign: `server/table_board.py`.

Step 1 of the build order in `docs/plans/p4-board.md` section 6. The rulings are
section 5 (2026-09-25): each player and the Storyteller change any object, only the
Storyteller clears the board and sets the background, a spectator watches, one board
for each campaign, and no hidden layer. Decision 0020 fixes the scope.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import re

import pytest
from PIL import Image

from exalted_builder import persistence
from exalted_builder.engine import lifecycle
from exalted_builder.models.character import Character
from exalted_builder.server import db, table_board
from exalted_builder.server.characters import CharacterStore
from exalted_builder.server.quota import FolderQuota, QuotaExceeded
from exalted_builder.server.table_board import TableBoard, TableBoardError
from exalted_builder.server.tables import TableStore

ST, PLAYER, WATCHER, STRANGER = 1, 2, 3, 4

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def tables(tmp_path: Path) -> TableStore:
    path = tmp_path / "accounts" / "exalted.db"
    db.init_db(path)
    with db.connect(path) as connection:
        connection.executemany(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, 'x')",
            [(ST, "storyteller"), (PLAYER, "player"), (WATCHER, "watcher"),
             (STRANGER, "stranger")])
    return TableStore(db_path=path, root=tmp_path / "sessions")


@pytest.fixture
def table(tables: TableStore):
    """A table with a player who brings a character and a member with no character."""
    table = tables.create(ST, "The Scarlet Gambit")
    characters = CharacterStore(db_path=tables.db_path, root=tables.root)
    base = Character(id="x", name="Ashes", caste="dawn")
    lifecycle.lock_chargen(base)
    for user, base_id in ((PLAYER, characters.create(PLAYER, base).id), (WATCHER, None)):
        tables.approve(ST, tables.request(user, table.join_code, base_id).id)
    return table


@pytest.fixture
def board(tables: TableStore) -> TableBoard:
    return TableBoard(tables)


def token(object_id: str = "t1", **overrides) -> dict:
    data = {"kind": "token", "id": object_id, "x": 100, "y": 120, "r": 20,
            "colour": "#aa3322", "label": "Ashes"}
    data.update(overrides)
    return data


def stroke(object_id: str = "s1", **overrides) -> dict:
    data = {"kind": "stroke", "id": object_id, "points": [0, 0, 10, 10, 20, 5],
            "colour": "#000000", "width": 3}
    data.update(overrides)
    return data


def png_bytes(size: tuple[int, int] = (64, 48), mode: str = "RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, size, "red").save(buffer, "PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# Decision 0020: the structural guard. A board object is a picture.
# --------------------------------------------------------------------------- #

# Each module of the board. ⚠ Add each new board module here. The test fails for a
# name that is not on disk, thus a rename cannot empty the list.
BOARD_MODULES = [
    "exalted_builder/server/table_board.py",
    "exalted_builder/server/table_board_view.py",
    "exalted_builder/server/board.js",
]

# A name of the model of the table. None of them can be in a board module.
FORBIDDEN = re.compile(
    r"\bengine\b|character_id|copy_id|\bcharacter\b|\bCharacter\b|adversar|roster|"
    r"initiative|\bhealth\b|\bessence\b|\bmotes?\b",
    re.IGNORECASE)


def _code_lines(path: Path) -> list[tuple[int, str]]:
    """Return the lines of `path` that are code. Skip comments and the header of
    the file, which cite decision 0020 and thus name what it forbids."""
    text = path.read_text(encoding="utf-8")
    header, comment = ('"""', '"""'), "#"
    if path.suffix == ".js":
        header, comment = ("/*", "*/"), "//"
    if text.startswith(header[0]):
        end = text.index(header[1], len(header[0])) + len(header[1])
        skipped = text[:end].count("\n")
        text = "\n" * skipped + text[end:]
    lines = []
    for number, line in enumerate(text.splitlines(), 1):
        code = line.split(comment, 1)[0]
        if code.strip():
            lines.append((number, code))
    return lines


@pytest.mark.parametrize("module", BOARD_MODULES)
def test_no_board_module_names_the_model_of_the_table(module: str) -> None:
    """0020: a board object that knows a character is the forbidden link. A grep
    finds it. A test of the behaviour cannot."""
    path = REPO / module
    assert path.is_file(), f"{module} is not on disk: update BOARD_MODULES"
    hits = [f"{module}:{n}: {line.strip()}" for n, line in _code_lines(path)
            if FORBIDDEN.search(line)]
    assert hits == []


def test_the_guard_finds_a_link_to_a_character(tmp_path: Path) -> None:
    """Mutation check of the grep: a planted link is found, in each language."""
    planted = tmp_path / "planted.py"
    planted.write_text('"""Docstring: character."""\n'
                       "from ..engine import derive\n"
                       'FIELDS = {"character_id": str}  # a comment\n')
    hits = [line for _, line in _code_lines(planted) if FORBIDDEN.search(line)]
    assert len(hits) == 2
    planted = tmp_path / "planted.js"
    planted.write_text("/* header: character */\n"
                       "var o = {label: sheet.character.name};  // a comment\n"
                       "// motes\n")
    hits = [line for _, line in _code_lines(planted) if FORBIDDEN.search(line)]
    assert len(hits) == 1


def test_the_fields_of_a_board_object_are_the_permitted_fields() -> None:
    """A positive list. A new field fails this test, and a person must read 0020
    before they add it here."""
    assert table_board.object_fields() == {
        "stroke": {"kind", "id", "points", "colour", "width"},
        "shape": {"kind", "id", "shape", "x", "y", "w", "h", "colour", "fill", "width"},
        "text": {"kind", "id", "x", "y", "text", "size", "colour"},
        "token": {"kind", "id", "x", "y", "r", "colour", "label"},
    }


def test_an_unknown_field_is_refused_not_dropped(board: TableBoard, table) -> None:
    with pytest.raises(TableBoardError):
        board.put(PLAYER, table.id, token(character_id="abc"))
    assert board.state(PLAYER, table.id).objects == ()


def test_a_token_label_is_the_text_that_the_person_typed(board: TableBoard,
                                                        table) -> None:
    state = board.put(PLAYER, table.id, token(label="  Ashes, maybe  "))
    assert state.objects[0]["label"] == "Ashes, maybe"
    state = board.put(PLAYER, table.id, token(label=""))
    assert state.objects[0]["label"] == ""


# --------------------------------------------------------------------------- #
# Objects
# --------------------------------------------------------------------------- #


def test_an_object_is_kept_in_the_table_folder(board: TableBoard, tables, table) -> None:
    state = board.put(PLAYER, table.id, token())

    assert board.path(table.id) == tables.table_dir(table.id) / "board.json"
    assert state.version == 1
    assert [o["id"] for o in state.objects] == ["t1"]
    assert board.state(WATCHER, table.id) == state


def test_a_new_object_goes_on_top_and_a_move_keeps_its_layer(board: TableBoard,
                                                             table) -> None:
    board.put(PLAYER, table.id, stroke("a"))
    board.put(ST, table.id, token("b"))
    state = board.put(PLAYER, table.id, stroke("a", colour="#ffffff"))

    assert [o["id"] for o in state.objects] == ["a", "b"]
    assert state.objects[0]["colour"] == "#ffffff"
    assert state.version == 3


def test_each_player_moves_and_deletes_each_object(board: TableBoard, table) -> None:
    """Q1: as at a real table. The ST's token is the player's to move."""
    board.put(ST, table.id, token("t1"))
    board.put(PLAYER, table.id, token("t1", x=400))
    state = board.delete(WATCHER, table.id, "t1")
    assert state.objects == ()


def test_a_delete_of_an_absent_object_changes_nothing(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token())
    state = board.delete(PLAYER, table.id, "gone")
    assert state.version == 1


def test_an_object_moves_to_the_front_and_the_back(board: TableBoard, table) -> None:
    for name in "abc":
        board.put(PLAYER, table.id, token(name))
    assert [o["id"] for o in board.to_front(PLAYER, table.id, "a").objects] == list("bca")
    assert [o["id"] for o in board.to_back(PLAYER, table.id, "c").objects] == list("cba")


def test_a_restack_that_moves_nothing_writes_nothing(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token("a"))
    board.put(PLAYER, table.id, token("b"))
    assert board.to_front(PLAYER, table.id, "b").version == 2
    assert board.to_back(PLAYER, table.id, "a").version == 2
    assert board.to_front(PLAYER, table.id, "gone").version == 2


def test_a_spectator_watches(board: TableBoard, table) -> None:
    """Q1. Spectating is how the page is opened. The handler passes it."""
    board.put(PLAYER, table.id, token())
    for change in (lambda: board.put(PLAYER, table.id, token("t2"), spectating=True),
                   lambda: board.delete(PLAYER, table.id, "t1", spectating=True),
                   lambda: board.to_front(PLAYER, table.id, "t1", spectating=True)):
        with pytest.raises(TableBoardError):
            change()
    assert board.state(PLAYER, table.id).version == 1


def test_a_stranger_can_neither_read_nor_write(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token())
    with pytest.raises(TableBoardError):
        board.state(STRANGER, table.id)
    with pytest.raises(TableBoardError):
        board.put(STRANGER, table.id, token("t2"))
    with pytest.raises(TableBoardError):
        board.delete(STRANGER, table.id, "t1")
    assert board.background_file(STRANGER, table.id) is None


@pytest.mark.parametrize("bad", [
    token(kind="dragon"),
    token(id="has space"),
    token(id=""),
    token(colour="red"),
    token(r=0),
    token(x=float("inf")),
    token(x=10**9),
    token(label="x" * (table_board.MAX_LABEL + 1)),
    stroke(points=[0, 0, 1]),
    stroke(points=[0, 0]),
    stroke(points=[0.0] * (2 * table_board.MAX_POINTS + 2)),
    stroke(width=0),
    {"kind": "text", "id": "x", "x": 0, "y": 0, "text": "  ", "size": 20,
     "colour": "#000000"},
    {"kind": "shape", "id": "x", "shape": "star", "x": 0, "y": 0, "w": 1, "h": 1,
     "colour": "#000000", "fill": None, "width": 2},
    "not an object",
])
def test_a_malformed_object_is_refused(board: TableBoard, table, bad) -> None:
    with pytest.raises(TableBoardError):
        board.put(PLAYER, table.id, bad)
    assert not board.path(table.id).exists()


def test_the_board_has_a_limit_of_objects(board: TableBoard, table, monkeypatch) -> None:
    monkeypatch.setattr(table_board, "MAX_OBJECTS", 2)
    board.put(PLAYER, table.id, token("a"))
    board.put(PLAYER, table.id, token("b"))
    board.put(PLAYER, table.id, token("b", x=5))  # A move is not a new object.
    with pytest.raises(TableBoardError):
        board.put(PLAYER, table.id, token("c"))


def test_the_points_of_a_stroke_are_rounded(board: TableBoard, table) -> None:
    state = board.put(PLAYER, table.id, stroke(points=[0.123, 1.987, 5, 6]))
    assert state.objects[0]["points"] == [0.1, 2.0, 5.0, 6.0]


# --------------------------------------------------------------------------- #
# Clear and the background: the Storyteller only
# --------------------------------------------------------------------------- #


def test_only_the_storyteller_clears(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token())
    with pytest.raises(TableBoardError):
        board.clear(PLAYER, table.id)
    state = board.clear(ST, table.id)
    assert (state.objects, state.version) == ((), 2)


def test_the_storyteller_sets_a_background(board: TableBoard, table) -> None:
    state = board.set_background(ST, table.id, png_bytes((64, 48)))

    assert (state.background.width, state.background.height) == (64, 48)
    path = board.background_file(PLAYER, table.id)
    assert path is not None and path.parent == board.path(table.id).parent / "board"
    with Image.open(path) as image:
        assert image.size == (64, 48)


def test_a_player_cannot_set_or_remove_the_background(board: TableBoard, table) -> None:
    board.set_background(ST, table.id, png_bytes())
    with pytest.raises(TableBoardError):
        board.set_background(PLAYER, table.id, png_bytes())
    with pytest.raises(TableBoardError):
        board.remove_background(PLAYER, table.id)
    assert board.state(PLAYER, table.id).background is not None


def test_clear_keeps_the_background_and_remove_takes_it(board: TableBoard,
                                                       table) -> None:
    board.set_background(ST, table.id, png_bytes())
    board.put(PLAYER, table.id, token())
    assert board.clear(ST, table.id).background is not None

    state = board.remove_background(ST, table.id)
    assert state.background is None
    assert board.background_file(ST, table.id) is None


def test_the_background_is_re_encoded_not_copied(board: TableBoard, table) -> None:
    """A file is opened as an image. Bytes that are not an image are refused, and
    the bytes that are kept are the encoder's, not the upload's."""
    with pytest.raises(TableBoardError):
        board.set_background(ST, table.id, b"<script>alert(1)</script>")
    raw = png_bytes() + b"TRAILING PAYLOAD"
    board.set_background(ST, table.id, raw)
    assert b"TRAILING PAYLOAD" not in board.background_file(ST, table.id).read_bytes()


def test_a_large_background_is_scaled_down(board: TableBoard, table,
                                           monkeypatch) -> None:
    monkeypatch.setattr(table_board, "MAX_SIDE", 100)
    state = board.set_background(ST, table.id, png_bytes((400, 200)))
    assert (state.background.width, state.background.height) == (100, 50)


def test_a_background_over_the_size_cap_is_refused(board: TableBoard, table,
                                                   monkeypatch) -> None:
    monkeypatch.setattr(table_board, "MAX_BACKGROUND_BYTES", 10)
    with pytest.raises(TableBoardError):
        board.set_background(ST, table.id, png_bytes())
    assert board.state(ST, table.id).background is None


def test_an_image_with_too_many_pixels_is_refused_before_it_is_decoded(
        board: TableBoard, table, monkeypatch) -> None:
    monkeypatch.setattr(table_board, "MAX_INPUT_PIXELS", 100)
    with pytest.raises(TableBoardError):
        board.set_background(ST, table.id, png_bytes((20, 20)))


# --------------------------------------------------------------------------- #
# The folder
# --------------------------------------------------------------------------- #


def test_the_quota_of_the_table_folder_applies_to_objects(board: TableBoard, tables,
                                                          table) -> None:
    persistence.set_write_guard(FolderQuota(tables.root, table_limit=10))
    try:
        with pytest.raises(QuotaExceeded):
            board.put(PLAYER, table.id, token())
    finally:
        persistence.set_write_guard(None)
    assert not board.path(table.id).exists()


def test_the_quota_of_the_table_folder_applies_to_the_background(
        board: TableBoard, tables, table) -> None:
    persistence.set_write_guard(FolderQuota(tables.root, table_limit=100))
    try:
        with pytest.raises(QuotaExceeded):
            board.set_background(ST, table.id, png_bytes((200, 200)))
    finally:
        persistence.set_write_guard(None)
    assert board.background_file(ST, table.id) is None


def test_a_board_file_that_does_not_read_is_an_empty_board(board: TableBoard,
                                                           table) -> None:
    board.path(table.id).parent.mkdir(parents=True, exist_ok=True)
    board.path(table.id).write_text("{not json")
    state = board.state(PLAYER, table.id)
    assert (state.objects, state.background) == ((), None)


def test_a_deleted_campaign_takes_its_board(board: TableBoard, tables, table) -> None:
    board.put(PLAYER, table.id, token())
    board.set_background(ST, table.id, png_bytes())

    tables.delete(ST, table.id)

    assert not board.path(table.id).exists()
    assert not (board.path(table.id).parent / "board").exists()


def test_the_file_holds_only_the_permitted_fields(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token())
    stored = json.loads(board.path(table.id).read_text())
    assert set(stored) == {"version", "objects", "background"}
    assert set(stored["objects"][0]) == table_board.object_fields()["token"]


# --------------------------------------------------------------------------- #
# Several objects at once (multiselect, the human 2026-09-25)
# --------------------------------------------------------------------------- #


def test_several_objects_move_in_one_version(board: TableBoard, table) -> None:
    for name in "abc":
        board.put(PLAYER, table.id, token(name))

    state = board.put_many(PLAYER, table.id, [token("a", x=1), token("c", x=3)])

    assert state.version == 4
    assert [(o["id"], o["x"]) for o in state.objects] == [
        ("a", 1.0), ("b", 100.0), ("c", 3.0)]


def test_a_batch_with_one_bad_object_writes_nothing(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token("a"))
    with pytest.raises(TableBoardError):
        board.put_many(PLAYER, table.id, [token("a", x=1), token("b", colour="red")])
    assert board.state(PLAYER, table.id).objects[0]["x"] == 100.0
    assert board.version(table.id) == 1


def test_a_batch_that_repeats_an_id_is_refused(board: TableBoard, table) -> None:
    with pytest.raises(TableBoardError):
        board.put_many(PLAYER, table.id, [token("a"), token("a", x=5)])


def test_a_batch_counts_against_the_limit(board: TableBoard, table, monkeypatch) -> None:
    monkeypatch.setattr(table_board, "MAX_OBJECTS", 2)
    board.put(PLAYER, table.id, token("a"))
    with pytest.raises(TableBoardError):
        board.put_many(PLAYER, table.id, [token("b"), token("c")])


def test_several_objects_are_deleted_in_one_version(board: TableBoard, table) -> None:
    for name in "abc":
        board.put(PLAYER, table.id, token(name))
    state = board.delete_many(PLAYER, table.id, ["a", "c", "gone"])
    assert ([o["id"] for o in state.objects], state.version) == (["b"], 4)
    assert board.delete_many(PLAYER, table.id, ["gone"]).version == 4


def test_several_objects_go_to_the_front_in_their_own_order(board: TableBoard,
                                                           table) -> None:
    for name in "abcd":
        board.put(PLAYER, table.id, token(name))
    state = board.restack_many(PLAYER, table.id, ["c", "a"], front=True)
    assert [o["id"] for o in state.objects] == list("bdac")
    state = board.restack_many(PLAYER, table.id, ["c", "d"], front=False)
    assert [o["id"] for o in state.objects] == list("dcba")
    before = state.version
    assert board.restack_many(PLAYER, table.id, ["d", "c"], front=False).version == before


def test_a_spectator_cannot_change_several(board: TableBoard, table) -> None:
    board.put(PLAYER, table.id, token("a"))
    for change in (
            lambda: board.put_many(PLAYER, table.id, [token("a", x=1)], spectating=True),
            lambda: board.delete_many(PLAYER, table.id, ["a"], spectating=True),
            lambda: board.restack_many(PLAYER, table.id, ["a"], front=True,
                                       spectating=True)):
        with pytest.raises(TableBoardError):
            change()
    with pytest.raises(TableBoardError):
        board.put_many(STRANGER, table.id, [token("a", x=1)])
