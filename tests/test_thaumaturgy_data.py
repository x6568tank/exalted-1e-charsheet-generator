"""Thaumaturgy — catalogue data and model shape (Player's Guide CH3).

Values are pinned against `images/Mortals/Mortals & Heroic Mortals/Player's Guide.md`.
Design notes and the rules-authority calls live in docs/status/thaumaturgy.md.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder.engine import costs
from exalted_builder.models.character import (
    ArtSpecialty,
    Character,
    FormulaEntry,
    RitualEntry,
    ScienceRating,
    ThaumaturgyState,
)
from exalted_builder.models.rules import (
    SOLAR_EXALT,
    Orientation,
    ScienceLevel,
    ThaumaturgicScience,
)
from exalted_builder.rules_db import RuleDataError, load_ruleset

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def ruleset():
    return load_ruleset(DATA_DIR)


@pytest.fixture
def minimal_character() -> Character:
    return Character(id="c")


# --------------------------------------------------------------------------- #
# Catalogue
# --------------------------------------------------------------------------- #

def test_the_four_arts_load_with_their_printed_gates(ruleset):
    arts = ruleset.thaum_arts
    assert len(arts) == 4
    # Occult minimums, p.126/130/133/135.
    assert arts["art.summoning"].min_occult == 1
    assert arts["art.warding"].min_occult == 1
    assert arts["art.exorcism"].min_occult == 3
    assert arts["art.astrology"].min_occult == 4
    # Astrology is the only Art that costs nothing to attempt (p.135).
    assert arts["art.astrology"].cost.startswith("0 motes")
    assert arts["art.exorcism"].cost.startswith("6 motes")


def test_only_summoning_gates_its_aspects_individually(ruleset):
    """Summoning prints an Occult minimum per aspect (Beasts/Mortals 1, Demons/
    Elementals 2, Ghosts/Spirits 3, p.126-129). The other three Arts print aspect
    lists with no per-aspect gate, so their aspects carry min_occult 0 meaning
    'no gate beyond the parent Art's own'."""
    summoning = ruleset.thaum_arts["art.summoning"]
    assert {a.name: a.min_occult for a in summoning.aspects} == {
        "Beasts": 1, "Mortals": 1, "Demons": 2,
        "Elementals": 2, "Ghosts": 3, "Spirits": 3,
    }
    for art_id in ("art.warding", "art.exorcism", "art.astrology"):
        assert all(a.min_occult == 0 for a in ruleset.thaum_arts[art_id].aspects), art_id


def test_summoning_is_the_only_art_that_may_narrow_an_aspect(ruleset):
    """"A thaumaturge may choose to further limit one or more of their summoning
    aspects … This halves the cost of the aspect" (p.127). No other Art prints it."""
    assert ruleset.thaum_arts["art.summoning"].aspect_narrowing is True
    for art_id in ("art.warding", "art.exorcism", "art.astrology"):
        assert ruleset.thaum_arts[art_id].aspect_narrowing is False, art_id


def test_warding_carries_all_eleven_printed_aspects(ruleset):
    assert len(ruleset.thaum_arts["art.warding"].aspects) == 11


def test_the_four_sciences_load(ruleset):
    assert set(ruleset.thaum_sciences) == {
        "science.alchemy", "science.enchantment",
        "science.geomancy", "science.weather-working",
    }


def test_weather_working_keeps_its_always_plus_two_difficulty(ruleset):
    """p.148 — "Because of the effort involved, weather working is always performed
    at +2 difficulty." It is part of the roll, not a situational modifier."""
    assert "+2 difficulty" in ruleset.thaum_sciences["science.weather-working"].roll


def test_weather_working_has_its_full_dot_ladder(ruleset):
    """The ladder is printed inside the "Council of Winds" sidebar rather than under
    the Weather Working heading — it is NOT missing from the source."""
    levels = ruleset.thaum_sciences["science.weather-working"].levels
    assert [lv.rating for lv in levels] == [1, 2, 3, 4, 5]


# --------------------------------------------------------------------------- #
# Alchemy's six-dot ladder — the awkward one
# --------------------------------------------------------------------------- #

def test_alchemy_tops_out_at_five_like_every_other_science(ruleset):
    """**REVERSES the 2026-07-29 ruling**, which read the printed ladder literally
    (1-2-3-4 then SIX, no five-dot rung) and said "never renumber the six-dot rung down
    to close it". The human reversed that 2026-07-30 on a report from a player familiar
    with the system: the printed 6 is a typographical error for 5.

    The internal evidence agrees, which is why the reversal was accepted — see
    `test_the_typo_reading_resolves_every_alchemy_anomaly` below.

    This is a DELIBERATE departure from the printed page (decision 0001 normally forbids
    exactly this), recorded in the Science's own `description` so it cannot be quietly
    "corrected" back by a later session reading the book."""
    alchemy = ruleset.thaum_sciences["science.alchemy"]
    assert alchemy.max_rating == 5
    assert [lv.rating for lv in alchemy.levels] == [1, 2, 3, 4, 5]
    assert alchemy.level(5) is not None
    assert alchemy.level(6) is None


def test_the_typo_reading_resolves_every_alchemy_anomaly(ruleset):
    """Why the reversal was believed. Under the literal reading Alchemy was the only
    Science with a hole in its ladder AND the only one whose formulas required a rung
    the book never describes. Read as 5, both vanish at once: the two level-5 formulas
    land on a described rung, and Alchemy matches the other three Sciences exactly."""
    alchemy = ruleset.thaum_sciences["science.alchemy"]
    at_five = [f for f in ruleset.thaum_formulas.values()
               if f.science_id == "science.alchemy" and f.level == 5]
    assert {f.name for f in at_five} == {
        "Heavenly Transmutation Processes", "Six-Demon Potion",
    }
    # every formula now sits on a rung that HAS a printed description
    for formula in ruleset.thaum_formulas.values():
        if formula.science_id == "science.alchemy":
            assert alchemy.level(formula.level) is not None, formula.name
    assert "typographical error" in alchemy.description


def test_the_other_three_sciences_stop_at_five(ruleset):
    for sid in ("science.enchantment", "science.geomancy", "science.weather-working"):
        assert ruleset.thaum_sciences[sid].max_rating == 5, sid


# --------------------------------------------------------------------------- #
# Rituals and formulas
# --------------------------------------------------------------------------- #

def test_the_chapter_prints_five_rituals_as_eight_purchasable_ids(ruleset):
    """Dishonest Spirit's Rebuke is one printed entry but four separate purchases:
    "This is actually four related rituals — one each for spirits, demons,
    elementals and ghosts … each must be learned separately" (p.150)."""
    rituals = ruleset.thaum_rituals
    assert len(rituals) == 8
    rebuke = [r for r in rituals.values() if r.name.startswith("Dishonest Spirit")]
    assert len(rebuke) == 4
    assert all(r.level == 3 for r in rebuke)


def test_every_ritual_is_within_the_printed_one_to_five_band(ruleset):
    assert all(1 <= r.level <= 5 for r in ruleset.thaum_rituals.values())


def test_all_fourteen_alchemical_formulas_load(ruleset):
    formulas = ruleset.thaum_formulas
    assert len(formulas) == 14
    assert all(f.science_id == "science.alchemy" for f in formulas.values())


def test_a_formula_may_price_its_materials_in_prose_instead_of_dots(ruleset):
    """Two formulas do not cost a number of Resources dots: Venom-Allaying Draught
    is "Equal to poison cost" and Heavenly Transmutation Processes is "Varies".
    `materials_raw` is authoritative when set."""
    venom = ruleset.thaum_formulas["formula.venom-allaying-draught"]
    assert venom.materials_resources is None
    assert venom.materials_raw == "Equal to poison cost"

    compress = ruleset.thaum_formulas["formula.blood-staunching-compress"]
    assert compress.materials_resources == 1
    assert compress.materials_raw == ""


def test_formula_rolls_are_not_all_intelligence_plus_occult(ruleset):
    """The stat-block default is Intelligence + Occult (p.138) but five formulas
    print something else — Wits, Perception and Stamina all appear. Authoring them
    all as the default would have been silently wrong."""
    rolls = {f.roll for f in ruleset.thaum_formulas.values()}
    assert "Wits + Occult" in rolls
    assert "Perception + Occult" in rolls
    assert "Stamina + Occult" in rolls


# --------------------------------------------------------------------------- #
# Load-time link checking
# --------------------------------------------------------------------------- #

def test_a_formula_naming_an_unknown_science_is_a_load_error(tmp_path):
    _write_min_dataset(tmp_path, formulas=[{
        "id": "formula.bogus", "name": "Bogus", "science_id": "science.nope", "level": 1,
    }])
    with pytest.raises(RuleDataError) as exc:
        load_ruleset(tmp_path)
    assert "unknown science" in str(exc.value)


def test_a_formula_above_its_sciences_ceiling_is_a_load_error(tmp_path):
    """Enchantment stops at 5; a formula demanding 6 of it is a data bug. The same
    check must NOT fire for Alchemy 6, which is legal."""
    _write_min_dataset(tmp_path, sciences=[{
        "id": "science.enchantment", "name": "Enchantment", "max_rating": 5,
        "levels": [{"rating": 1}],
    }], formulas=[{
        "id": "formula.too-high", "name": "Too High",
        "science_id": "science.enchantment", "level": 6,
    }])
    with pytest.raises(RuleDataError) as exc:
        load_ruleset(tmp_path)
    assert "max_rating" in str(exc.value)


def test_a_duplicate_aspect_id_across_two_arts_is_a_load_error(tmp_path):
    """Aspect ids must be globally unique — the UI resolves them by id across Arts."""
    shared = {"id": "art.x.ghosts", "name": "Ghosts"}
    _write_min_dataset(tmp_path, arts=[
        {"id": "art.a", "name": "A", "aspects": [shared]},
        {"id": "art.b", "name": "B", "aspects": [shared]},
    ])
    with pytest.raises(RuleDataError) as exc:
        load_ruleset(tmp_path)
    assert "already used by" in str(exc.value)


def test_the_shipped_dataset_link_checks_clean(ruleset):
    # load_ruleset raises on any problem, so reaching the fixture at all proves it.
    assert ruleset.thaum_formulas
    assert ruleset.thaum_arts


# --------------------------------------------------------------------------- #
# Character-side shape
# --------------------------------------------------------------------------- #

def test_a_specialty_may_name_an_art_the_character_does_not_own():
    """Stated three times in the source, e.g. the BP table footnote: "You do not
    have to buy the relevant Art in order to buy a specialty in that Art" (p.116).
    There must be no prerequisite tying one to the other."""
    state = ThaumaturgyState(
        arts=[],                                     # owns no Arts at all
        art_specialties=[ArtSpecialty(art_id="art.warding", name="Local Fair Folk")],
    )
    assert state.art_specialties[0].art_id == "art.warding"
    assert state.arts == []


def test_a_ritual_holding_carries_its_orientations_not_just_an_id():
    """The crux of the design: each extra regional version costs a flat 1 point
    (p.124), so ownership is (id, {orientations}) and a bare id cannot express it."""
    entry = RitualEntry(ritual_id="ritual.calling-the-flames-beneficence",
                        orientations=[Orientation.EAST, Orientation.REALM])
    assert entry.orientations == [Orientation.EAST, Orientation.REALM]


def test_orientations_default_to_realm_and_never_empty():
    assert RitualEntry(ritual_id="r").orientations == [Orientation.REALM]
    assert RitualEntry(ritual_id="r", orientations=[]).orientations == [Orientation.REALM]
    assert FormulaEntry(formula_id="f", orientations=[]).orientations == [Orientation.REALM]


def test_duplicate_orientations_collapse():
    """Paying twice for the same region is meaningless, and a duplicate would
    inflate the cost function, which counts len(orientations)."""
    entry = RitualEntry(ritual_id="r",
                        orientations=[Orientation.NORTH, Orientation.NORTH, Orientation.SOUTH])
    assert entry.orientations == [Orientation.NORTH, Orientation.SOUTH]


def test_a_ritual_may_be_custom_instead_of_catalogued():
    """Catalogue + custom (human's call, 2026-07-29) — the book prints five rituals
    and expects STs to write more."""
    entry = RitualEntry(name="Grandmother's Hearth-Blessing", level=2,
                        description="A homebrew ward against kitchen fires.")
    assert entry.ritual_id == ""
    assert entry.level == 2


def test_a_science_rating_is_not_capped_at_five_on_the_character():
    """Alchemy 6 must be storable. The per-Science ceiling is a RULES fact
    (ThaumaturgicScience.max_rating) enforced in the engine, not a model bound —
    models guard shape, the engine guards legality."""
    assert ScienceRating(science_id="science.alchemy", rating=6).rating == 6


def test_thaumaturgy_is_optional_so_old_saves_load_unchanged(minimal_character):
    """The PlayState precedent: absent means None, not an empty state."""
    assert minimal_character.thaumaturgy is None
    round_tripped = Character.model_validate_json(minimal_character.model_dump_json())
    assert round_tripped.thaumaturgy is None


def test_thaumaturgy_round_trips_through_json(minimal_character):
    minimal_character.thaumaturgy = ThaumaturgyState(
        arts=["art.summoning"],
        art_specialties=[ArtSpecialty(art_id="art.summoning", name="War Gods")],
        sciences=[ScienceRating(science_id="science.alchemy", rating=6)],
        rituals=[RitualEntry(ritual_id="ritual.dedicated-purification",
                             orientations=[Orientation.NORTH, Orientation.WEST])],
        formulas=[FormulaEntry(formula_id="formula.heros-recovery")],
    )
    back = Character.model_validate_json(minimal_character.model_dump_json())
    assert back.thaumaturgy is not None
    assert back.thaumaturgy.sciences[0].rating == 6
    assert back.thaumaturgy.rituals[0].orientations == [Orientation.NORTH, Orientation.WEST]


# --------------------------------------------------------------------------- #
# Splat-level flags
# --------------------------------------------------------------------------- #

def test_every_shipped_splat_may_use_thaumaturgy_at_normal_cost(ruleset):
    """p.114 — the Exalted learn it "without any difficulty". The two exceptions
    (the dead cannot use it; spirits pay double) belong to splats that do not exist
    yet, so every shipped splat must sit on the defaults."""
    for exalt in ruleset.exalts.values():
        assert exalt.thaumaturgy_usable is True, exalt.id
        assert exalt.thaumaturgy_cost_multiplier == 1, exalt.id


def test_a_science_level_above_its_own_max_rating_is_rejected_at_load(tmp_path):
    _write_min_dataset(tmp_path, sciences=[{
        "id": "science.x", "name": "X", "max_rating": 5,
        "levels": [{"rating": 6, "description": "impossible"}],
    }])
    with pytest.raises(RuleDataError) as exc:
        load_ruleset(tmp_path)
    assert "exceeds its max_rating" in str(exc.value)


def test_science_level_lookup_is_by_rating_not_position():
    """The sparse ladder means positional indexing would silently return the wrong
    rung — asking Alchemy for level 5 must give None, not the six-dot text."""
    science = ThaumaturgicScience(
        id="s", name="S", max_rating=6,
        levels=[ScienceLevel(rating=1, description="one"),
                ScienceLevel(rating=6, description="six")],
    )
    assert science.level(1).description == "one"
    assert science.level(5) is None
    assert science.level(6).description == "six"


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _write_min_dataset(tmp_path, *, arts=None, sciences=None, formulas=None) -> None:
    """The smallest data set load_ruleset accepts, plus the thaumaturgy rows under
    test. Everything else is optional and falls back to model defaults."""
    import json

    (tmp_path / "castes.json").write_text(json.dumps([
        {"id": "dawn", "exalt_type": "Solar", "label": "Dawn"},
    ]))
    thaum = tmp_path / "thaumaturgy"
    thaum.mkdir()
    (thaum / "arts.json").write_text(json.dumps(arts or []))
    (thaum / "sciences.json").write_text(json.dumps(sciences or []))
    (thaum / "formulas.json").write_text(json.dumps(formulas or []))


# --------------------------------------------------------------------------- #
# Cost ladder (Player's Guide BP p.116 / XP p.115)
# --------------------------------------------------------------------------- #

def test_the_two_cost_tables_deliberately_disagree(ruleset, minimal_character):
    """An Art is 5 in both currencies, but an Art Specialty is 2 BP and 3 XP, and
    a ritual's base is 2 BP and 3 XP. Collapsing them into one number would be
    wrong in one direction or the other."""
    c = minimal_character
    assert costs.thaum_art_bp(ruleset, c) == 5
    assert costs.thaum_art_xp(ruleset, c) == 5
    assert costs.thaum_specialty_bp(ruleset, c) == 2
    assert costs.thaum_specialty_xp(ruleset, c) == 3


@pytest.mark.parametrize("level, bp, xp", [(1, 3, 4), (2, 4, 5), (3, 5, 6), (5, 7, 8)])
def test_ritual_cost_scales_with_level(ruleset, minimal_character, level, bp, xp):
    """"Ritual | 2 + 1 per level of Ritual" (BP) and "3, +1 per level" (XP)."""
    assert costs.thaum_ritual_bp(ruleset, minimal_character, level) == bp
    assert costs.thaum_ritual_xp(ruleset, minimal_character, level) == xp


def test_each_extra_orientation_adds_exactly_one_point(ruleset, minimal_character):
    """p.124 — "additional versions for other orientations cost only a single
    experience or bonus point to learn (so to completely master all versions of a
    given spell would cost four bonus points, in addition to the normal cost)"."""
    c = minimal_character
    one = costs.thaum_ritual_bp(ruleset, c, 3, orientations=1)
    all_five = costs.thaum_ritual_bp(ruleset, c, 3, orientations=5)
    assert all_five - one == 4          # the book's own worked figure
    assert costs.thaum_formula_bp(ruleset, c, orientations=1) == 1
    assert costs.thaum_formula_bp(ruleset, c, orientations=5) == 5


def test_narrowing_a_summoning_aspect_halves_it_but_never_to_free(ruleset, minimal_character):
    """p.127 — "This halves the cost of the aspect". Rounded UP: 2 BP -> 1, not 0.
    Rounding down would make narrowing strictly dominant and free."""
    c = minimal_character
    assert costs.thaum_specialty_bp(ruleset, c, narrowed=True) == 1
    assert costs.thaum_specialty_xp(ruleset, c, narrowed=True) == 2


def test_a_spirits_double_rate_multiplies_every_thaumaturgy_purchase(ruleset, minimal_character):
    """p.114 — spirits "pay twice the normal experience (or bonus) points when
    learning or improving any Art, Science or ritual". No playable spirit splat
    exists, so this is exercised against a synthetic ExaltDefinition."""
    spirit = SOLAR_EXALT.model_copy(update={"id": "Spirit",
                                            "thaumaturgy_cost_multiplier": 2})
    rs = ruleset.model_copy(update={"exalts": {**ruleset.exalts, "Spirit": spirit}})
    c = minimal_character
    c.exalt_type = "Spirit"
    assert costs.thaum_art_bp(rs, c) == 10
    assert costs.thaum_specialty_bp(rs, c) == 4
    assert costs.thaum_ritual_xp(rs, c, 3) == 12
    assert costs.thaum_formula_bp(rs, c, orientations=3) == 6
