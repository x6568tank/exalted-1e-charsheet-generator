"""Homebrew layers that stack: `rules_db.with_custom_layers` and
`rules_db.reload_custom_layers`.

Step 7 of `docs/plans/p3-tables.md`. A draft for a campaign builds under the book,
then the homebrew of the campaign, then the library of its owner (ruled
2026-09-23).

⚠ `reload_custom_layer` deletes each custom row before it merges ONE folder. Thus
two nested calls keep only the outer folder. The layer functions clear once and
merge each folder in order.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from exalted_builder import rules_db
from exalted_builder.rules_db import load_ruleset


def _write_book(d: Path) -> None:
    (d / "charms").mkdir(parents=True)
    (d / "castes.json").write_text(json.dumps([
        {"id": "twilight", "exalt_type": "Solar", "label": "Twilight",
         "caste_abilities": ["craft", "investigation", "lore", "medicine", "occult"]},
    ]))
    (d / "charms" / "occult.json").write_text(json.dumps([
        {"id": "t", "name": "Terrestrial Circle Sorcery", "category": "occult",
         "type": "Permanent", "min_ability": 3, "min_essence": 1,
         "grants_circle": "Terrestrial"},
    ]))
    (d / "spells.json").write_text(json.dumps([
        {"id": "s1", "name": "A Terrestrial Spell", "circle": "Terrestrial"},
    ]))


def _charm(cid: str, **over) -> dict:
    row = {"id": cid, "name": cid.replace("custom.", "").title(), "category": "melee",
           "type": "Supplemental", "min_ability": 1, "min_essence": 1}
    row.update(over)
    return row


def _charms(d: Path, rows: list[dict]) -> None:
    (d / "charms").mkdir(parents=True, exist_ok=True)
    (d / "charms" / "mine.json").write_text(json.dumps(rows))


def _spells(d: Path, rows: list[dict]) -> None:
    d.mkdir(parents=True, exist_ok=True)
    (d / "spells.json").write_text(json.dumps(rows))


@pytest.fixture
def book(tmp_path: Path):
    _write_book(tmp_path / "data")
    return load_ruleset(tmp_path / "data")


def test_two_layers_both_merge(book, tmp_path) -> None:
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _charms(first, [_charm("custom.a")])
    _charms(second, [_charm("custom.b")])

    rs = rules_db.with_custom_layers(book, [first, second])

    assert {"custom.a", "custom.b"} <= set(rs.charms)
    assert rs.charms["custom.a"].custom and rs.charms["custom.b"].custom
    assert rs.custom_problems == []


def test_the_book_does_not_change(book, tmp_path) -> None:
    first = tmp_path / "campaign"
    _charms(first, [_charm("custom.a")])

    rules_db.with_custom_layers(book, [first])

    assert "custom.a" not in book.charms


def test_the_first_layer_wins_a_clash(book, tmp_path) -> None:
    """The campaign is first, thus its version wins (ruled 2026-09-23)."""
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _charms(first, [_charm("custom.a", name="Campaign Version")])
    _charms(second, [_charm("custom.a", name="Owner Version")])

    rs = rules_db.with_custom_layers(book, [first, second])

    assert rs.charms["custom.a"].name == "Campaign Version"
    [problem] = rs.custom_problems
    assert "earlier homebrew layer" in problem
    # ⚠ Not the message for a clash with a printed Charm.
    assert "rulebook" not in problem


def test_the_book_still_wins_over_every_layer(book, tmp_path) -> None:
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _charms(first, [])
    _charms(second, [_charm("t", name="Homebrew Sorcery")])

    rs = rules_db.with_custom_layers(book, [first, second])

    assert rs.charms["t"].name == "Terrestrial Circle Sorcery"
    assert any("rulebook" in p for p in rs.custom_problems)


def test_a_later_layer_may_require_an_earlier_one(book, tmp_path) -> None:
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _charms(first, [_charm("custom.root")])
    _charms(second, [_charm("custom.leaf", prerequisites=[["custom.root"]])])

    rs = rules_db.with_custom_layers(book, [first, second])

    assert "custom.leaf" in rs.charms
    assert rs.custom_problems == []


def test_a_spell_clash_names_the_layer(book, tmp_path) -> None:
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _spells(first, [{"id": "custom.sp", "name": "First", "circle": "Terrestrial"}])
    _spells(second, [{"id": "custom.sp", "name": "Second", "circle": "Terrestrial"}])

    rs = rules_db.with_custom_layers(book, [first, second])

    assert rs.spells["custom.sp"].name == "First"
    [problem] = rs.custom_problems
    assert "earlier homebrew layer" in problem


def test_a_gear_clash_names_the_layer(book, tmp_path) -> None:
    first, second = tmp_path / "campaign", tmp_path / "owner"
    for d, name in ((first, "First"), (second, "Second")):
        d.mkdir(parents=True)
        (d / "gear.json").write_text(json.dumps(
            [{"id": "custom.rope", "name": name, "cost": 1}]))

    rs = rules_db.with_custom_layers(book, [first, second])

    assert rs.gear_catalog["custom.rope"].name == "First"
    assert any("earlier homebrew layer" in p for p in rs.custom_problems)


def test_reloading_the_stack_keeps_each_layer(book, tmp_path) -> None:
    """⚠ The trap of p3-tables.md section 4: a reload of one folder drops the other."""
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _charms(first, [_charm("custom.a")])
    _charms(second, [_charm("custom.b")])
    rs = rules_db.with_custom_layers(book, [first, second])

    _charms(first, [_charm("custom.a"), _charm("custom.a2")])
    rules_db.reload_custom_layers(rs, [first, second])

    assert {"custom.a", "custom.a2", "custom.b"} <= set(rs.charms)


def test_a_reload_drops_a_deleted_row(book, tmp_path) -> None:
    first, second = tmp_path / "campaign", tmp_path / "owner"
    _charms(first, [_charm("custom.a")])
    _charms(second, [_charm("custom.b")])
    rs = rules_db.with_custom_layers(book, [first, second])

    _charms(second, [])
    rules_db.reload_custom_layers(rs, [first, second])

    assert "custom.b" not in rs.charms
    assert "custom.a" in rs.charms


def test_an_absent_folder_is_no_layer(book, tmp_path) -> None:
    second = tmp_path / "owner"
    _charms(second, [_charm("custom.b")])

    rs = rules_db.with_custom_layers(book, [tmp_path / "absent", second])

    assert "custom.b" in rs.charms
    assert rs.custom_problems == []
