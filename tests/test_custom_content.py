"""Tests for the user-authored custom-content layer (docs/plans/custom-content.md).

The invariant under test throughout: a problem in the BOOK data is fatal (one
RuleDataError listing everything), but a problem in the USER's custom library is
never fatal — the offending row is dropped, the reason is recorded on
`RuleSet.custom_problems`, and the app still loads. A Storyteller must not be able
to brick their character builder with a typo.
"""

import json
from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import custom_content, persistence, rules_db
from exalted_builder.engine import advancement, lifecycle, validate
from exalted_builder.models.character import Array, Character, Combo
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.models.rules import AbilityName, AttributeName
from exalted_builder.rules_db import RuleDataError, load_app_ruleset, load_ruleset
from exalted_builder.ui import view as viewmod


def _write_clean_set(d: Path) -> None:
    """The same minimal book data set test_rules_db.py uses: two linked Occult
    Charms (one granting the Terrestrial circle) and one Terrestrial spell."""
    (d / "charms").mkdir(parents=True)
    (d / "castes.json").write_text(json.dumps([
        {"id": "twilight", "exalt_type": "Solar", "label": "Twilight",
         "caste_abilities": ["craft", "investigation", "lore", "medicine", "occult"]},
    ]))
    (d / "charms" / "occult.json").write_text(json.dumps([
        {"id": "t", "name": "Terrestrial Circle Sorcery", "category": "occult",
         "type": "Permanent", "min_ability": 3, "min_essence": 1,
         "grants_circle": "Terrestrial"},
        {"id": "c", "name": "Celestial Circle Sorcery", "category": "occult",
         "type": "Permanent", "min_ability": 4, "min_essence": 3,
         "prerequisites": [["t"]], "grants_circle": "Celestial"},
    ]))
    (d / "spells.json").write_text(json.dumps([
        {"id": "s1", "name": "A Terrestrial Spell", "circle": "Terrestrial"},
    ]))


def _custom_charms(d: Path, rows: list[dict], stem: str = "mine") -> Path:
    (d / "charms").mkdir(parents=True, exist_ok=True)
    path = d / "charms" / f"{stem}.json"
    path.write_text(json.dumps(rows))
    return path


def _charm(cid: str, **over) -> dict:
    row = {"id": cid, "name": cid.replace("custom.", "").title(), "category": "melee",
           "type": "Supplemental", "min_ability": 1, "min_essence": 1}
    row.update(over)
    return row


# --------------------------------------------------------------------------- #
# the happy path
# --------------------------------------------------------------------------- #

def test_custom_charm_merges_and_is_flagged(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.house-strike")])

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.custom_problems == []
    assert set(rs.charms) == {"t", "c", "custom.house-strike"}
    # the flag is what lets the UI badge it and decide what is editable
    assert rs.charms["custom.house-strike"].custom is True
    assert rs.charms["t"].custom is False


def test_custom_charm_may_require_a_book_charm(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.deeper", category="occult",
                                prerequisites=[["t"]])])

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.custom_problems == []
    assert rs.charms["custom.deeper"].prerequisites == [["t"]]


def test_custom_martial_arts_style_needs_no_schema(tmp_path):
    """A custom style is just a new `martial_arts:<slug>` category string — the
    picker derives its style groups from the category, so nothing else is needed."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.crane-1", category="martial_arts:white-crane")])

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.custom_problems == []
    assert rs.charms["custom.crane-1"].category == "martial_arts:white-crane"


def test_no_custom_dir_is_a_plain_load(tmp_path):
    book = tmp_path / "data"
    _write_clean_set(book)

    rs = load_ruleset(book, custom_dir=tmp_path / "does-not-exist")

    assert rs.custom_problems == []
    assert set(rs.charms) == {"t", "c"}


# --------------------------------------------------------------------------- #
# custom problems are non-fatal
# --------------------------------------------------------------------------- #

def test_malformed_custom_json_does_not_brick_the_load(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    (mine / "charms").mkdir(parents=True)
    (mine / "charms" / "broken.json").write_text("{ this is not json")
    _custom_charms(mine, [_charm("custom.fine")], stem="ok")

    rs = load_ruleset(book, custom_dir=mine)

    assert any("broken.json" in p for p in rs.custom_problems)
    assert "custom.fine" in rs.charms            # the good file still loaded


def test_invalid_custom_row_is_dropped_not_raised(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [
        {"id": "custom.nameless", "category": "melee", "type": "Supplemental"},  # no name
        _charm("custom.good"),
    ])

    rs = load_ruleset(book, custom_dir=mine)

    assert "custom.good" in rs.charms
    assert "custom.nameless" not in rs.charms
    assert any("mine.json[0]" in p for p in rs.custom_problems)


def test_book_data_errors_are_still_fatal(tmp_path):
    """The custom layer must not soften the book's link-checking."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(book, [_charm("b", prerequisites=[["does-not-exist"]])], stem="bad")
    _custom_charms(mine, [_charm("custom.fine")])

    with pytest.raises(RuleDataError) as ei:
        load_ruleset(book, custom_dir=mine)
    assert any("does-not-exist" in p for p in ei.value.problems)


# --------------------------------------------------------------------------- #
# collisions and dangling references
# --------------------------------------------------------------------------- #

def test_book_wins_an_id_collision(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("t", name="Shadowing The Book")])

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.charms["t"].name == "Terrestrial Circle Sorcery"
    assert rs.charms["t"].custom is False
    assert any("'t'" in p and "shadow" in p.lower() for p in rs.custom_problems)


def test_duplicate_id_within_the_custom_library(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.dup", name="First")], stem="a")
    _custom_charms(mine, [_charm("custom.dup", name="Second")], stem="b")

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.charms["custom.dup"].name == "First"      # first one loaded wins
    assert any("custom.dup" in p for p in rs.custom_problems)


def test_dangling_prerequisite_drops_the_custom_charm(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.orphan", prerequisites=[["ghost"]])])

    rs = load_ruleset(book, custom_dir=mine)

    assert "custom.orphan" not in rs.charms
    assert any("ghost" in p for p in rs.custom_problems)


def test_dropping_a_custom_charm_cascades_to_its_dependants(tmp_path):
    """Dropping one row orphans anything that required it, so the drop pass has to
    run to a fixpoint rather than once."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [
        _charm("custom.a", prerequisites=[["ghost"]]),
        _charm("custom.b", prerequisites=[["custom.a"]]),
        _charm("custom.c", prerequisites=[["custom.b"]]),
        _charm("custom.safe"),
    ])

    rs = load_ruleset(book, custom_dir=mine)

    assert "custom.safe" in rs.charms
    for cid in ("custom.a", "custom.b", "custom.c"):
        assert cid not in rs.charms
        assert any(cid in p for p in rs.custom_problems)


def test_or_group_survives_one_missing_alternative(tmp_path):
    """Prerequisites are AND-of-OR: a group is satisfied by any one member, so a
    group that still has a live alternative must not drop the Charm."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.either", category="occult",
                                 prerequisites=[["ghost", "t"]])])

    rs = load_ruleset(book, custom_dir=mine)

    assert "custom.either" in rs.charms
    assert rs.custom_problems == []


# --------------------------------------------------------------------------- #
# custom spells
# --------------------------------------------------------------------------- #

def test_custom_spell_in_a_granted_circle_loads(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    (mine).mkdir(parents=True, exist_ok=True)
    (mine / "spells.json").write_text(json.dumps([
        {"id": "custom.spell", "name": "House Spell", "circle": "Celestial"},
    ]))

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.custom_problems == []
    assert rs.spells["custom.spell"].custom is True


def test_custom_spell_in_an_unreachable_circle_is_dropped(tmp_path):
    """No Charm grants the Solar circle in this data set, so the spell could never
    be learned. Dropped, not fatal."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    mine.mkdir(parents=True, exist_ok=True)
    (mine / "spells.json").write_text(json.dumps([
        {"id": "custom.unreachable", "name": "Nope", "circle": "Solar"},
    ]))

    rs = load_ruleset(book, custom_dir=mine)

    assert "custom.unreachable" not in rs.spells
    assert any("Solar" in p for p in rs.custom_problems)


def test_custom_charm_can_grant_the_circle_its_custom_spell_needs(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.solar-sorcery", category="occult",
                                 type="Permanent", grants_circle="Solar")])
    (mine / "spells.json").write_text(json.dumps([
        {"id": "custom.big", "name": "Big One", "circle": "Solar"},
    ]))

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.custom_problems == []
    assert "custom.big" in rs.spells


def test_custom_spell_shadowing_a_book_spell_is_rejected(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    mine.mkdir(parents=True, exist_ok=True)
    (mine / "spells.json").write_text(json.dumps([
        {"id": "s1", "name": "Shadowing", "circle": "Terrestrial"},
    ]))

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.spells["s1"].name == "A Terrestrial Spell"
    assert any("s1" in p and "shadow" in p.lower() for p in rs.custom_problems)


# --------------------------------------------------------------------------- #
# where the library lives
# --------------------------------------------------------------------------- #

def test_custom_data_dir_honours_the_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv(custom_content.CUSTOM_DIR_ENV, str(tmp_path / "elsewhere"))
    assert custom_content.custom_data_dir() == tmp_path / "elsewhere"


def test_custom_data_dir_defaults_beside_the_saves(tmp_path, monkeypatch):
    monkeypatch.delenv(custom_content.CUSTOM_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    assert custom_content.custom_data_dir() == tmp_path / custom_content.CUSTOM_DIR_NAME


def test_load_app_ruleset_picks_up_the_library(tmp_path, monkeypatch):
    """What the UI pages call: book data plus whatever the user has authored."""
    book, mine = tmp_path / "data", tmp_path / "elsewhere"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.via-env")])
    monkeypatch.setenv(custom_content.CUSTOM_DIR_ENV, str(mine))

    rs = load_app_ruleset(book)

    assert "custom.via-env" in rs.charms


# --------------------------------------------------------------------------- #
# a character holding content that has GONE (the library was deleted, or the save
# came from a machine that had it and this one does not)
# --------------------------------------------------------------------------- #

def _shipped():
    """The real shipped ruleset plus the bundled example — the missing-id paths are
    only worth testing against the data the app actually runs on."""
    data_dir = Path(exalted_builder.__file__).parent / "data"
    example = Path(exalted_builder.__file__).parent.parent / "examples" / "ashes-of-dawn.character.json"
    return load_ruleset(data_dir), persistence.load_character(example)


def test_missing_charm_and_spell_are_reported_as_errors():
    rs, char = _shipped()
    char.charms.append("custom.deleted-charm")
    char.spells.append("custom.deleted-spell")

    codes = {(i.code, i.where) for i in validate.validate(rs, char)}

    assert ("unknown-charm", "custom.deleted-charm") in codes
    assert ("unknown-spell", "custom.deleted-spell") in codes


def test_missing_charm_in_the_panoply_is_reported():
    """`charms` was the only list checked; a Charm can also sit in an Alchemical's
    Panoply or come from a training camp, and a vanished definition there is the
    same defect."""
    rs, char = _shipped()
    char.retainer_charms.append("custom.deleted-panoply")
    char.granted_charms.append("custom.deleted-granted")

    messages = {i.where: i.message for i in validate.validate(rs, char)
                if i.code == "unknown-charm"}

    assert "Panoply" in messages["custom.deleted-panoply"]
    assert "training camp" in messages["custom.deleted-granted"]


def test_missing_charm_still_gets_a_sheet_row():
    """The row must never be silently dropped — a character that quietly loses a
    Charm looks legal and cheap, and the player never finds out."""
    rs, char = _shipped()
    char.charms.append("custom.deleted-charm")

    rows = [r for r in viewmod.build_sheet_view(rs, char).charms if r.missing]

    assert [r.name for r in rows] == ["custom.deleted-charm"]
    assert rows[0].category == "?"


def test_missing_spell_still_gets_a_sheet_row():
    rs, char = _shipped()
    char.spells.append("custom.deleted-spell")

    rows = [r for r in viewmod.build_sheet_view(rs, char).spells if r.missing]

    assert [r.name for r in rows] == ["custom.deleted-spell"]


def test_a_missing_id_never_crashes_a_render_path():
    """Blanket regression: every presenter that walks a character's Charms or spells
    must tolerate an id that does not resolve. This is the guard rail for deleting a
    custom Charm a character already owns — the one destructive thing the authoring
    page can do."""
    rs, char = _shipped()
    char.charms.append("custom.deleted-charm")
    char.spells.append("custom.deleted-spell")
    char.combos.append(Combo(name="Ghost Combo",
                             charm_ids=["custom.deleted-charm", char.charms[0]]))

    # each of these walks the held Charms/spells by a different route
    viewmod.build_sheet_view(rs, char)
    viewmod.build_combo_view(rs, char)
    viewmod.build_play_view(rs, char)
    viewmod.build_party_card_view(rs, char)
    viewmod.build_xp_log(rs, char)
    viewmod.build_spell_picker(rs, char)
    viewmod.build_charm_graph(rs, char, "melee")
    assert viewmod.build_charm_detail(rs, char, "custom.deleted-charm") is None
    assert viewmod.build_spell_detail(rs, char, "custom.deleted-spell") is None
    validate.validate_chargen(rs, char)
    advancement.validate_xp(rs, char)


# --------------------------------------------------------------------------- #
# the non-canon badge (human's requirement: custom content must be obvious)
# --------------------------------------------------------------------------- #

def _one_custom_charm(tmp_path) -> tuple[object, object]:
    """The shipped ruleset with one homebrew Melee Charm overlaid, plus a character
    holding it."""
    data_dir = Path(exalted_builder.__file__).parent / "data"
    _custom_charms(tmp_path, [_charm("custom.house-strike", name="House Strike")])
    rs = load_ruleset(data_dir, custom_dir=tmp_path)
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.house-strike"]
    return rs, char


def test_sheet_row_flags_a_custom_charm(tmp_path):
    rs, char = _one_custom_charm(tmp_path)

    row = next(r for r in viewmod.build_sheet_view(rs, char).charms
               if r.name == "House Strike")

    assert row.custom is True
    assert row.missing is False


def test_printed_charms_are_not_flagged_custom():
    rs, char = _shipped()

    assert all(r.custom is False for r in viewmod.build_sheet_view(rs, char).charms)


def test_charm_detail_and_graph_flag_a_custom_charm(tmp_path):
    rs, char = _one_custom_charm(tmp_path)

    detail = viewmod.build_charm_detail(rs, char, "custom.house-strike")
    node = next(n for n in viewmod.build_charm_graph(rs, char, "melee").nodes
                if n.id == "custom.house-strike")

    assert detail.custom is True
    assert node.custom is True


# --------------------------------------------------------------------------- #
# the authoring page's pure half: form <-> payload, and the write path
# --------------------------------------------------------------------------- #

def test_form_round_trips_through_a_payload():
    form = viewmod.custom_charm_form()
    form.update(name="House Strike", category="melee", min_ability=3, min_essence=2,
                motes=4, willpower=1, duration="One scene", description="Hit harder.")
    form["id"] = custom_content.make_id(form["name"])

    payload = viewmod.custom_charm_payload(form)
    back = viewmod.custom_charm_form(payload)

    assert payload["id"] == "custom.house-strike"
    assert payload["cost"] == {"motes": 4, "willpower": 1}
    assert back["name"] == "House Strike"
    assert back["min_ability"] == 3
    assert back["duration"] == "One scene"


def test_payload_omits_empty_optional_fields():
    """A hand-read library file should be as short as the Charm actually is."""
    form = viewmod.custom_charm_form()
    form.update(name="Plain", category="melee")

    payload = viewmod.custom_charm_payload(form)

    assert "cost" not in payload            # no motes/willpower/health
    assert "prerequisites" not in payload
    assert "grants_circle" not in payload


def test_new_style_option_becomes_a_martial_arts_category():
    form = viewmod.custom_charm_form()
    form.update(name="Crane Opens", category=viewmod.NEW_STYLE, style_name="White Crane")

    assert viewmod.custom_charm_payload(form)["category"] == "martial_arts:white-crane"


def test_prerequisite_mode_writes_the_two_and_of_or_shapes():
    form = viewmod.custom_charm_form()
    form.update(name="Needs Both", prerequisites=["a", "b"], prereq_mode="all")
    assert viewmod.custom_charm_payload(form)["prerequisites"] == [["a"], ["b"]]

    form["prereq_mode"] = "any"
    assert viewmod.custom_charm_payload(form)["prerequisites"] == [["a", "b"]]


def test_an_or_group_read_back_keeps_its_mode():
    row = {"id": "custom.x", "name": "X", "prerequisites": [["a", "b"]]}
    assert viewmod.custom_charm_form(row)["prereq_mode"] == "any"
    assert viewmod.custom_charm_form(row)["prerequisites"] == ["a", "b"]


def test_category_options_include_abilities_styles_and_the_new_style_sentinel():
    rs, _ = _shipped()

    opts = viewmod.custom_category_options(rs)

    assert opts["melee"] == "Melee"
    assert "martial_arts:tiger" in opts                    # a style already in the data
    assert viewmod.NEW_STYLE in opts


def test_save_charm_writes_a_loadable_row(tmp_path):
    form = viewmod.custom_charm_form()
    form.update(name="House Strike", category="melee", min_ability=2)
    form["id"] = custom_content.make_id(form["name"])

    saved = custom_content.save_charm(viewmod.custom_charm_payload(form), custom_dir=tmp_path)

    assert saved.id == "custom.house-strike"
    assert (tmp_path / custom_content.CHARMS_FILE).exists()
    # and it loads back through the real loader
    book = tmp_path / "book"
    _write_clean_set(book)
    rs = load_ruleset(book, custom_dir=tmp_path)
    assert rs.charms["custom.house-strike"].custom is True


def test_saving_the_same_id_replaces_rather_than_duplicates(tmp_path):
    """An edit must keep the id — characters reference it — so re-saving is a
    replace, not an append."""
    form = viewmod.custom_charm_form()
    form.update(name="House Strike", category="melee")
    form["id"] = custom_content.make_id(form["name"])
    custom_content.save_charm(viewmod.custom_charm_payload(form), custom_dir=tmp_path)

    form["description"] = "Now with prose."
    custom_content.save_charm(viewmod.custom_charm_payload(form), custom_dir=tmp_path)

    rows = custom_content.library_charms(tmp_path)
    assert len(rows) == 1
    assert rows[0]["description"] == "Now with prose."


def test_save_refuses_a_book_id(tmp_path):
    payload = {"id": "solar.melee.fire-and-stones-strike", "name": "Nope",
               "category": "melee", "type": "Supplemental"}

    with pytest.raises(custom_content.CustomContentError) as ei:
        custom_content.save_charm(payload, custom_dir=tmp_path,
                                  reserved_ids={"solar.melee.fire-and-stones-strike"})
    assert "not a custom id" in str(ei.value)


def test_save_refuses_an_unnamed_row(tmp_path):
    with pytest.raises(custom_content.CustomContentError):
        custom_content.save_charm({"id": "", "name": "", "category": "melee",
                                   "type": "Supplemental"}, custom_dir=tmp_path)


def test_save_reports_the_offending_field(tmp_path):
    with pytest.raises(custom_content.CustomContentError) as ei:
        custom_content.save_charm({"id": "custom.bad", "name": "Bad", "category": "melee",
                                   "type": "Nonsense Type"}, custom_dir=tmp_path)
    assert "type" in str(ei.value)


def test_a_bare_id_gets_the_custom_prefix_but_a_namespaced_one_does_not():
    assert custom_content.normalize_id("house-strike") == "custom.house-strike"
    assert custom_content.normalize_id("custom.house-strike") == "custom.house-strike"
    assert custom_content.normalize_id("someone.else.charm") == "someone.else.charm"


def test_delete_removes_the_row_and_leaves_the_file_valid(tmp_path):
    for name in ("One", "Two"):
        form = viewmod.custom_charm_form()
        form.update(name=name, category="melee")
        form["id"] = custom_content.make_id(name)
        custom_content.save_charm(viewmod.custom_charm_payload(form), custom_dir=tmp_path)

    assert custom_content.delete_charm("custom.one", custom_dir=tmp_path) is True
    assert custom_content.delete_charm("custom.one", custom_dir=tmp_path) is False
    assert [r["id"] for r in custom_content.library_charms(tmp_path)] == ["custom.two"]


def test_delete_edits_the_file_the_row_actually_lives_in(tmp_path):
    """Rows dropped into the library by hand live in their own files; an edit or a
    delete has to find them there, not only in the file the page writes."""
    _custom_charms(tmp_path, [_charm("custom.handmade")], stem="theirs")

    assert custom_content.delete_charm("custom.handmade", custom_dir=tmp_path) is True
    assert custom_content.library_charms(tmp_path) == []


def test_parse_rows_accepts_one_object_or_an_array():
    assert len(custom_content.parse_rows('{"id": "custom.a"}')) == 1
    assert len(custom_content.parse_rows('[{"id": "custom.a"}, {"id": "custom.b"}]')) == 2


def test_parse_rows_explains_bad_json():
    with pytest.raises(custom_content.CustomContentError) as ei:
        custom_content.parse_rows("{not json")
    assert "valid JSON" in str(ei.value)


def test_spell_save_and_reload(tmp_path):
    book = tmp_path / "book"
    mine = tmp_path / "mine"
    _write_clean_set(book)
    form = viewmod.custom_spell_form()
    form.update(name="House Spell", circle="Celestial", motes=15)
    form["id"] = custom_content.make_id(form["name"])

    custom_content.save_spell(viewmod.custom_spell_payload(form), custom_dir=mine)
    rs = load_ruleset(book, custom_dir=mine)

    assert rs.spells["custom.house-spell"].cost.motes == 15
    assert custom_content.delete_spell("custom.house-spell", custom_dir=mine) is True


# --------------------------------------------------------------------------- #
# reload_custom_layer — the authoring page edits the RuleSet every page holds
# --------------------------------------------------------------------------- #

def test_reload_picks_up_a_new_row_in_place(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    rs = load_ruleset(book, custom_dir=mine)
    assert "custom.later" not in rs.charms

    _custom_charms(mine, [_charm("custom.later")])
    problems = rules_db.reload_custom_layer(rs, mine)

    assert problems == []
    assert rs.charms["custom.later"].custom is True       # same RuleSet object


def test_reload_drops_a_deleted_row_and_keeps_the_book(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.doomed")])
    rs = load_ruleset(book, custom_dir=mine)

    custom_content.delete_charm("custom.doomed", custom_dir=mine)
    rules_db.reload_custom_layer(rs, mine)

    assert "custom.doomed" not in rs.charms
    assert set(rs.charms) == {"t", "c"}                   # book rows untouched


def test_reload_revives_a_row_once_its_prerequisite_is_authored(tmp_path):
    """A Charm dropped for a dangling prerequisite must come back when the
    prerequisite appears — which is why the reload re-reads the library rather than
    patching the one row that changed."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.child", prerequisites=[["custom.parent"]])])
    rs = load_ruleset(book, custom_dir=mine)
    assert "custom.child" not in rs.charms

    _custom_charms(mine, [_charm("custom.parent")], stem="parent")
    rules_db.reload_custom_layer(rs, mine)

    assert "custom.child" in rs.charms and "custom.parent" in rs.charms


def test_reload_reports_problems_on_the_ruleset(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    rs = load_ruleset(book, custom_dir=mine)

    _custom_charms(mine, [_charm("custom.orphan", prerequisites=[["ghost"]])])
    rules_db.reload_custom_layer(rs, mine)

    assert rs.custom_problems and any("ghost" in p for p in rs.custom_problems)


# --------------------------------------------------------------------------- #
# the library list the page draws
# --------------------------------------------------------------------------- #

def test_library_list_marks_a_rejected_row_invalid_with_its_reason(tmp_path):
    """A row the loader threw out must still be listed — the authoring page is the
    only place it can be fixed, and an invisible broken Charm is unfixable."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.good"),
                          _charm("custom.orphan", prerequisites=[["ghost"]])])
    rs = load_ruleset(book, custom_dir=mine)

    rows = {r.id: r for r in viewmod.build_custom_library(
        rs, custom_content.library_charms(mine), custom_content.library_spells(mine))}

    assert rows["custom.good"].valid is True
    assert rows["custom.orphan"].valid is False
    assert "ghost" in rows["custom.orphan"].problem


# --------------------------------------------------------------------------- #
# health-cost damage type (CharmCost.health_type)
# --------------------------------------------------------------------------- #

def test_health_type_is_unset_wherever_the_page_does_not_name_a_damage_type():
    """`health_type` shipped with custom content as a homebrew-only field: every
    printed Charm with a health cost just said "1 health level", so the field had to
    default to unset and change nothing about how they read.

    **That stopped being true on 2026-08-01.** Stolen Wax Discipline (E:Ab p.238) is
    the first PRINTED Charm to name the type — "5 motes, one lethal health level" —
    so the field now has exactly one book-data consumer. The invariant that still
    holds, and the one worth testing, is the narrower one: the field is set only where
    the page actually names a type, and unset everywhere else."""
    rs, _ = _shipped()
    with_health = [c for c in rs.charms.values() if c.cost.health]
    typed = [c for c in with_health if c.cost.health_type is not None]

    assert with_health                                   # the corpus still has them
    assert [c.id for c in typed] == ["ghost.shifting-ghost-clay.stolen-wax-discipline"]
    for c in typed:
        # Whatever names a type must say so in its printed cost line.
        assert "lethal" in c.cost.raw or "bashing" in c.cost.raw \
            or "aggravated" in c.cost.raw, c.id


def test_cost_string_names_the_damage_type_only_when_set():
    from exalted_builder.models.rules import CharmCost, Damage

    assert viewmod._cost_str(CharmCost(motes=3, health=1)) == "3m, 1hl"
    assert viewmod._cost_str(
        CharmCost(motes=3, health=1, health_type=Damage.AGGRAVATED)) == "3m, 1hl aggravated"


def test_health_type_round_trips_through_the_form():
    form = viewmod.custom_charm_form()
    form.update(name="Blood Price", health=1, health_type="x")

    payload = viewmod.custom_charm_payload(form)

    assert payload["cost"] == {"health": 1, "health_type": "x"}
    assert viewmod.custom_charm_form(payload)["health_type"] == "x"


def test_a_damage_type_without_a_health_cost_is_not_stored():
    """Naming a type for a Charm that spends no health levels would be written and
    then never read."""
    form = viewmod.custom_charm_form()
    form.update(name="No Blood", motes=2, health=0, health_type="x")

    assert "health_type" not in (viewmod.custom_charm_payload(form).get("cost") or {})


def test_a_custom_charm_can_carry_a_typed_health_cost(tmp_path):
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.blood", cost={"health": 2, "health_type": "*"})])

    rs = load_ruleset(book, custom_dir=mine)

    assert rs.custom_problems == []
    assert rs.charms["custom.blood"].cost.health_type.value == "*"


# --------------------------------------------------------------------------- #
# extra trait minimums: several Abilities and/or Attributes as requirements
# --------------------------------------------------------------------------- #

def test_extra_requirements_split_into_the_two_typed_lists():
    """One control in the form; two lists in the payload, because the engine budgets
    Abilities and Attributes differently."""
    form = viewmod.custom_charm_form()
    form.update(name="Twin Gate", extra_reqs=[
        {"kind": "ability", "traits": ["brawl", "endurance"], "rating": 5},
        {"kind": "attribute", "traits": ["stamina"], "rating": 3},
    ])

    payload = viewmod.custom_charm_payload(form)

    assert payload["extra_min_abilities"] == [{"abilities": ["brawl", "endurance"],
                                              "rating": 5}]
    assert payload["extra_min_attributes"] == [{"attributes": ["stamina"], "rating": 3}]


def test_extra_requirements_round_trip_and_keep_their_axis():
    form = viewmod.custom_charm_form()
    form.update(name="Twin Gate", extra_reqs=[
        {"kind": "attribute", "traits": ["wits", "perception"], "rating": 4}])

    back = viewmod.custom_charm_form(viewmod.custom_charm_payload(form))

    assert back["extra_reqs"] == [{"kind": "attribute",
                                   "traits": ["wits", "perception"], "rating": 4}]


def test_an_empty_requirement_row_is_dropped():
    form = viewmod.custom_charm_form()
    form.update(name="Nothing Extra",
                extra_reqs=[{"kind": "ability", "traits": [], "rating": 3}])

    payload = viewmod.custom_charm_payload(form)

    assert "extra_min_abilities" not in payload
    assert "extra_min_attributes" not in payload


def test_multiple_attribute_minimums_are_enforced_and_displayed(tmp_path):
    """The point of the feature: a Charm may gate on more than one Attribute, ANDed,
    each row an OR over its own traits."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm(
        "custom.twin-gate", min_ability=0,
        extra_min_attributes=[{"attributes": ["stamina"], "rating": 3},
                              {"attributes": ["wits", "perception"], "rating": 4}])])
    rs = load_ruleset(book, custom_dir=mine)
    charm = rs.charms["custom.twin-gate"]

    char = Character(id="x", caste="twilight")
    char.attributes[AttributeName.STAMINA] = 3
    # Wits/Perception both 1 -> the second row fails, the first passes
    shortfalls = validate.charm_ability_shortfalls(char, charm)
    assert [s[0] for s in shortfalls] == ["wits or perception"]
    assert validate.meets_charm_requirements(rs, char, charm) is False

    char.attributes[AttributeName.PERCEPTION] = 4      # the OR is satisfied by either
    assert validate.charm_ability_shortfalls(char, charm) == []
    assert validate.meets_charm_requirements(rs, char, charm) is True

    labels = [t for t, _ in validate.charm_ability_requirements(charm)]
    assert "stamina" in labels and "wits or perception" in labels


def test_no_printed_charm_uses_extra_attribute_minimums():
    """Documents that this axis is homebrew-only: no 1e page gates a Charm on more
    than one Attribute. If a splat ever does, this test is the thing to revisit."""
    rs, _ = _shipped()

    assert all(not c.extra_min_attributes for c in rs.charms.values())


# --------------------------------------------------------------------------- #
# travelling with a character: embed on save, absorb on load
# --------------------------------------------------------------------------- #

def _library_with(tmp_path: Path, rows: list[dict]) -> Path:
    mine = tmp_path / "library"
    _custom_charms(mine, rows)
    return mine


def test_saving_embeds_only_the_definitions_the_character_uses(tmp_path):
    mine = _library_with(tmp_path, [_charm("custom.used"), _charm("custom.unused")])
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.used", "solar.melee.fire-and-stones-strike"]

    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    assert [r["id"] for r in char.custom_definitions["charms"]] == ["custom.used"]


def test_an_ordinary_character_carries_nothing(tmp_path):
    """Every existing save must be unaffected: no homebrew, no new key."""
    mine = _library_with(tmp_path, [_charm("custom.unused")])
    char = Character(id="x", caste="dawn")
    char.charms = ["solar.melee.fire-and-stones-strike"]

    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    assert char.custom_definitions == {}


def test_embedding_pulls_in_a_homebrew_prerequisite_chain(tmp_path):
    """A custom Charm's prerequisite may itself be custom. Embedding only the leaf
    would land in the recipient's library as a row the loader drops."""
    mine = _library_with(tmp_path, [
        _charm("custom.root"),
        _charm("custom.middle", prerequisites=[["custom.root"]]),
        _charm("custom.leaf", prerequisites=[["custom.middle"]]),
    ])
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.leaf"]

    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    assert {r["id"] for r in char.custom_definitions["charms"]} == {
        "custom.root", "custom.middle", "custom.leaf"}


def test_every_list_that_can_hold_a_charm_is_walked(tmp_path):
    mine = _library_with(tmp_path, [_charm(f"custom.{n}") for n in
                                    ("installed", "panoply", "granted", "combo", "array")])
    (mine / "spells.json").write_text(json.dumps([
        {"id": "custom.spell", "name": "S", "circle": "Terrestrial"}]))
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.installed"]
    char.retainer_charms = ["custom.panoply"]
    char.granted_charms = ["custom.granted"]
    char.combos = [Combo(name="C", charm_ids=["custom.combo"])]
    char.arrays = [Array(name="A", charm_ids=["custom.array"])]
    char.spells = ["custom.spell"]

    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    assert len(char.custom_definitions["charms"]) == 5
    assert [r["id"] for r in char.custom_definitions["spells"]] == ["custom.spell"]


def test_a_locked_characters_snapshot_ids_travel_too(tmp_path):
    """The snapshot is what the XP audit re-prices against, so its ids must resolve
    on the recipient's machine as much as the current ones."""
    mine = _library_with(tmp_path, [_charm("custom.at-chargen")])
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.at-chargen"]
    lifecycle.lock_chargen(char)
    char.charms = []                                  # dropped after the lock

    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    assert [r["id"] for r in char.custom_definitions["charms"]] == ["custom.at-chargen"]


def test_definitions_no_longer_referenced_are_dropped_on_the_next_save(tmp_path):
    mine = _library_with(tmp_path, [_charm("custom.a"), _charm("custom.b")])
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.a", "custom.b"]
    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    char.charms = ["custom.a"]
    persistence.save_character(char, tmp_path / "c.json", custom_dir=mine)

    assert [r["id"] for r in char.custom_definitions["charms"]] == ["custom.a"]


def test_a_definition_missing_from_this_library_is_still_carried(tmp_path):
    """Someone else's character, opened and re-saved here: the homebrew it depends on
    must not be stripped out just because this machine did not author it."""
    theirs = {"id": "custom.foreign", "name": "Foreign", "category": "melee",
              "type": "Supplemental"}
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.foreign"]
    char.custom_definitions = {"charms": [theirs]}

    persistence.save_character(char, tmp_path / "c.json",
                               custom_dir=tmp_path / "empty-library")

    assert char.custom_definitions["charms"] == [theirs]


def test_the_full_hand_off_round_trip(tmp_path):
    """The whole point: author on one machine, open on another that has no library,
    and the Charm resolves."""
    author_lib = _library_with(tmp_path, [_charm("custom.gift", name="Gift Of Ash")])
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.gift"]
    save = tmp_path / "hero.character.json"
    persistence.save_character(char, save, custom_dir=author_lib)

    recipient_lib = tmp_path / "recipient"
    reloaded = persistence.load_character(save, custom_dir=recipient_lib)

    assert [r["id"] for r in custom_content.library_charms(recipient_lib)] == ["custom.gift"]
    # and it now loads as a real Charm on the recipient's machine
    book = tmp_path / "book"
    _write_clean_set(book)
    rs = load_ruleset(book, custom_dir=recipient_lib)
    assert rs.charms["custom.gift"].name == "Gift Of Ash"
    assert reloaded.charms == ["custom.gift"]


def test_absorb_never_overwrites_the_local_copy(tmp_path):
    """The recipient may have edited their own version of the same id. Opening a
    character must not silently revert it."""
    mine = _library_with(tmp_path, [_charm("custom.shared", name="My Version")])
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.shared"]
    char.custom_definitions = {"charms": [_charm("custom.shared", name="Their Version")]}

    added = custom_content.absorb_definitions(char, custom_dir=mine)

    assert added == []
    assert custom_content.library_charms(mine)[0]["name"] == "My Version"


def test_absorb_is_idempotent(tmp_path):
    char = Character(id="x", caste="dawn")
    char.charms = ["custom.once"]
    char.custom_definitions = {"charms": [_charm("custom.once")]}
    mine = tmp_path / "library"

    first = custom_content.absorb_definitions(char, custom_dir=mine)
    second = custom_content.absorb_definitions(char, custom_dir=mine)

    assert first == ["custom.once"]
    assert second == []
    assert len(custom_content.library_charms(mine)) == 1


def test_a_party_file_carries_every_members_homebrew(tmp_path):
    mine = _library_with(tmp_path, [_charm("custom.her"), _charm("custom.him")])
    a = Character(id="a", name="A", caste="dawn")
    a.charms = ["custom.her"]
    b = Character(id="b", name="B", caste="dawn")
    b.charms = ["custom.him"]
    party = Party(id="p", name="Tuesday",
                  members=[PartyMember(character=a), PartyMember(character=b)])
    path = tmp_path / "t.party.json"

    persistence.save_party(party, path, custom_dir=mine)
    recipient = tmp_path / "gm-library"
    persistence.load_party(path, custom_dir=recipient)

    assert {r["id"] for r in custom_content.library_charms(recipient)} == {
        "custom.her", "custom.him"}


# --------------------------------------------------------------------------- #
# advanced fields: splat mechanics and breadth prerequisites
# --------------------------------------------------------------------------- #

def test_advanced_fields_are_written_only_when_they_differ_from_the_default():
    """An ordinary homebrew Charm's JSON must not grow a dozen zeroes and falses."""
    form = viewmod.custom_charm_form()
    form.update(name="Plain", category="melee")

    payload = viewmod.custom_charm_payload(form)

    for key in ("element", "immaculate", "open_to_all", "open_to_tiers", "min_attribute",
                "no_foreign_learning", "installation_cost", "arrayable",
                "permanent_install", "permanent_clarity", "prerequisite_counts"):
        assert key not in payload


def test_arrayable_stores_only_the_false_case():
    """It defaults TRUE, so True is the absence of the key."""
    form = viewmod.custom_charm_form()
    form.update(name="Loose", arrayable=False)
    assert viewmod.custom_charm_payload(form)["arrayable"] is False

    form["arrayable"] = True
    assert "arrayable" not in viewmod.custom_charm_payload(form)


def test_advanced_fields_round_trip(tmp_path):
    form = viewmod.custom_charm_form()
    form.update(name="Deep Cut", category="martial_arts:white-crane", element="Fire",
                immaculate=True, open_to_all=True, open_to_tiers=["Celestial"],
                min_attribute="dexterity", no_foreign_learning=True,
                installation_cost=3, permanent_clarity=1, arrayable=False,
                permanent_install=True)
    form["id"] = custom_content.make_id(form["name"])

    payload = viewmod.custom_charm_payload(form)
    saved = custom_content.save_charm(payload, custom_dir=tmp_path)
    back = viewmod.custom_charm_form(custom_content.library_charms(tmp_path)[0])

    assert saved.element == "Fire" and saved.immaculate is True
    assert saved.open_to_tiers == ["Celestial"] and saved.min_attribute == "dexterity"
    assert saved.installation_cost == 3 and saved.permanent_clarity == 1
    assert saved.arrayable is False and saved.permanent_install is True
    assert back["element"] == "Fire" and back["open_to_tiers"] == ["Celestial"]


def test_breadth_prerequisite_round_trips_and_is_enforced(tmp_path):
    """"Any three Lore Charms" — a count over a category, which the id-based
    prerequisite list cannot express."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    form = viewmod.custom_charm_form()
    form.update(name="Broad Study", category="occult",
                breadth_reqs=[{"category": "occult", "count": 2, "label": ""}])
    form["id"] = custom_content.make_id(form["name"])
    custom_content.save_charm(viewmod.custom_charm_payload(form), custom_dir=mine)

    rs = load_ruleset(book, custom_dir=mine)
    charm = rs.charms["custom.broad-study"]
    assert [(r.category, r.count) for r in charm.prerequisite_counts] == [("occult", 2)]

    char = Character(id="x", caste="twilight")
    char.abilities[AbilityName.OCCULT] = 5
    char.essence_rating = 3
    assert validate.meets_charm_requirements(rs, char, charm) is False   # holds none
    char.charms = ["t", "c"]                                            # two Occult Charms
    assert validate.meets_charm_requirements(rs, char, charm) is True


def test_an_empty_breadth_row_is_dropped():
    form = viewmod.custom_charm_form()
    form.update(name="X", breadth_reqs=[{"category": "", "count": 3, "label": ""}])

    assert "prerequisite_counts" not in viewmod.custom_charm_payload(form)


def test_element_and_tier_options_come_from_the_data():
    rs, _ = _shipped()

    assert set(viewmod.charm_element_options(rs)) == {
        "", "Air", "Earth", "Fire", "Water", "Wood"}
    assert "Celestial" in viewmod.charm_tier_options(rs)


def test_an_instant_custom_charm_is_combo_eligible(tmp_path):
    """Combo eligibility is derived from the duration (core p.213), so it needs no
    field of its own — but a custom Charm must actually land in the pool."""
    book, mine = tmp_path / "data", tmp_path / "custom"
    _write_clean_set(book)
    _custom_charms(mine, [_charm("custom.quick", duration="Instant"),
                          _charm("custom.slow", duration="One scene")])
    rs = load_ruleset(book, custom_dir=mine)

    char = Character(id="x", caste="dawn")
    char.charms = ["custom.quick", "custom.slow"]

    assert validate.eligible_combo_charms(rs, char) == ["custom.quick"]
