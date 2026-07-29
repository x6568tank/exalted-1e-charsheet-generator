"""Tests for the Thaumaturgy engine wiring — the enumeration, the bonus-point
breakdown, the chargen gates, the snapshot freeze, and the XP transitions/audit.

The catalogue and cost-ladder tests live in test_thaumaturgy_data.py; this file is
about integration, i.e. that thaumaturgy reaches the same two accountings every
other purchasable domain reaches.
"""

import pytest

from exalted_builder.engine import advancement, lifecycle, validate
from exalted_builder.models.character import (
    ArtSpecialty, Character, FormulaEntry, RitualEntry, ScienceRating, ThaumaturgyState)
from exalted_builder.models.rules import (
    AbilityName, CasteDefinition, Orientation, RuleSet, ScienceLevel,
    SOLAR_EXALT, ThaumaturgicArt, ThaumaturgicAspect, ThaumaturgicFormula,
    ThaumaturgicRitual, ThaumaturgicScience)

A, O = AbilityName, Orientation


def _ruleset(**exalt_kwargs) -> RuleSet:
    """A miniature thaumaturgy rule set: one gated Art with a gated aspect, one
    six-dot Science, one level-3 ritual and one formula."""
    arts = {
        "art.summoning": ThaumaturgicArt(
            id="art.summoning", name="Summoning", min_occult=1, aspect_narrowing=True,
            aspects=[
                ThaumaturgicAspect(id="asp.beasts", name="Beasts", min_occult=1),
                ThaumaturgicAspect(id="asp.spirits", name="Spirits", min_occult=3),
            ]),
        "art.astrology": ThaumaturgicArt(
            id="art.astrology", name="Astrology", min_occult=4,
            aspects=[ThaumaturgicAspect(id="asp.gods", name="Gods")]),
    }
    sciences = {
        "science.alchemy": ThaumaturgicScience(
            id="science.alchemy", name="Alchemy", max_rating=6,
            levels=[ScienceLevel(rating=1), ScienceLevel(rating=6)]),
        "science.geomancy": ThaumaturgicScience(id="science.geomancy", name="Geomancy"),
    }
    rituals = {"rit.gate": ThaumaturgicRitual(id="rit.gate", name="Warded Gateway", level=3)}
    formulas = {"for.draught": ThaumaturgicFormula(
        id="for.draught", name="Draught", science_id="science.alchemy", level=2)}
    # Copy the real Solar definition rather than hand-build one: this test only
    # varies the two thaumaturgy flags, and everything else should stay canonical.
    exalts = {"Solar": SOLAR_EXALT.model_copy(update=exalt_kwargs)}
    castes = {"dawn": CasteDefinition(id="dawn", label="Dawn", caste_abilities=[A.MELEE])}
    return RuleSet(castes=castes, exalts=exalts, charms={}, thaum_arts=arts,
                   thaum_sciences=sciences, thaum_rituals=rituals, thaum_formulas=formulas)


def _character(occult: int = 5, **thaum) -> Character:
    c = Character(id="c", caste="dawn")
    c.abilities[A.OCCULT] = occult
    if thaum:
        c.thaumaturgy = ThaumaturgyState(**thaum)
    return c


# --------------------------------------------------------------------------- #
# The enumeration
# --------------------------------------------------------------------------- #

def test_no_thaumaturgy_enumerates_nothing():
    """The overwhelmingly common case: Character.thaumaturgy is None."""
    assert validate.thaum_purchases(_ruleset(), _character()) == []


def test_thaum_state_of_none_is_an_empty_state():
    assert validate.thaum_state(_character()).arts == []


def test_enumeration_covers_all_five_lists_in_sheet_order():
    c = _character(
        arts=["art.summoning"],
        art_specialties=[ArtSpecialty(art_id="art.summoning", name="Beasts")],
        sciences=[ScienceRating(science_id="science.alchemy", rating=2)],
        rituals=[RitualEntry(ritual_id="rit.gate")],
        formulas=[FormulaEntry(formula_id="for.draught")])
    kinds = [p.kind for p in validate.thaum_purchases(_ruleset(), c)]
    assert kinds == ["art", "specialty", "science", "ritual", "formula"]


def test_zero_rated_science_is_not_a_purchase():
    c = _character(sciences=[ScienceRating(science_id="science.alchemy", rating=0)])
    assert validate.thaum_purchases(_ruleset(), c) == []


def test_unresolvable_id_is_still_yielded_with_the_raw_id():
    """A stale save must show the problem, not silently lose the row."""
    c = _character(arts=["art.nonesuch"])
    (pick,) = validate.thaum_purchases(_ruleset(), c)
    assert pick.label == "art.nonesuch"


def test_ritual_level_comes_from_the_catalogue_not_the_entry():
    """A catalogue reference must not be re-levelled by a stale inline field."""
    entry = RitualEntry(ritual_id="rit.gate", level=1)
    assert validate.thaum_ritual_level(_ruleset(), entry) == 3


def test_custom_ritual_level_comes_from_the_entry():
    entry = RitualEntry(name="Home-brew", level=2)
    assert validate.thaum_ritual_level(_ruleset(), entry) == 2


def test_label_records_the_orientations_owned():
    c = _character(rituals=[RitualEntry(ritual_id="rit.gate",
                                        orientations=[O.NORTH, O.REALM])])
    (pick,) = validate.thaum_purchases(_ruleset(), c)
    assert pick.orientations == 2
    assert "North, Realm" in pick.label


# --------------------------------------------------------------------------- #
# Bonus points
# --------------------------------------------------------------------------- #

def test_bp_breakdown_has_no_thaumaturgy_line_without_purchases():
    """Every existing splat's breakdown must be byte-identical to before."""
    bd = validate.bonus_point_breakdown(_ruleset(), _character())
    assert not any(line.domain == "Thaumaturgy" for line in bd.lines)


def test_bp_breakdown_prices_each_kind_off_the_table():
    c = _character(
        arts=["art.summoning"],                                     # 5
        art_specialties=[ArtSpecialty(art_id="art.summoning", name="Beasts")],   # 2
        rituals=[RitualEntry(ritual_id="rit.gate")],                # 2 + 1*3 = 5
        formulas=[FormulaEntry(formula_id="for.draught")])          # 1
    bd = validate.bonus_point_breakdown(_ruleset(), c)
    (line,) = [ln for ln in bd.lines if ln.domain == "Thaumaturgy"]
    assert line.points == 13


def test_extra_orientations_add_one_point_each():
    base = _character(rituals=[RitualEntry(ritual_id="rit.gate")])
    both = _character(rituals=[RitualEntry(ritual_id="rit.gate",
                                           orientations=[O.NORTH, O.SOUTH, O.REALM])])
    rs = _ruleset()

    def thaum(ch):
        return next(ln.points for ln in validate.bonus_point_breakdown(rs, ch).lines
                    if ln.domain == "Thaumaturgy")

    assert thaum(both) - thaum(base) == 2


def test_narrowed_specialty_costs_half_rounded_up():
    plain = _character(art_specialties=[ArtSpecialty(art_id="art.summoning", name="Beasts")])
    narrow = _character(art_specialties=[
        ArtSpecialty(art_id="art.summoning", name="Beasts", narrowed=True)])
    rs = _ruleset()

    def thaum(ch):
        return next(ln.points for ln in validate.bonus_point_breakdown(rs, ch).lines
                    if ln.domain == "Thaumaturgy")

    assert (thaum(plain), thaum(narrow)) == (2, 1)


@pytest.mark.parametrize("rating,bp", [(1, 5), (2, 12), (3, 19), (5, 33), (6, 40)])
def test_science_bp_is_five_then_seven_a_dot(rating, bp):
    """5 for the first dot, 7 for each after. NOT from the printed tables — those
    omit Sciences entirely, which is a printing error Grabowski cleared up later;
    the rate comes from the rules authority (human, 2026-07-29)."""
    c = _character(sciences=[ScienceRating(science_id="science.alchemy", rating=rating)])
    line = next(ln for ln in validate.bonus_point_breakdown(_ruleset(), c).lines
                if ln.domain == "Thaumaturgy")
    assert line.points == bp


def test_science_dots_no_longer_raise_an_unpriced_issue():
    c = _character(sciences=[ScienceRating(science_id="science.alchemy", rating=2)])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-science-unpriced" not in codes


def test_thaumaturgy_bp_reaches_the_grand_total():
    plain = validate.bonus_point_breakdown(_ruleset(), _character()).total
    with_art = validate.bonus_point_breakdown(
        _ruleset(), _character(arts=["art.summoning"])).total
    assert with_art - plain == 5


# --------------------------------------------------------------------------- #
# Chargen gates
# --------------------------------------------------------------------------- #

def test_art_below_its_occult_minimum_is_an_issue():
    c = _character(occult=2, arts=["art.astrology"])       # needs Occult 4
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-art-occult" in codes


def test_art_at_its_occult_minimum_is_legal():
    c = _character(occult=4, arts=["art.astrology"])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-art-occult" not in codes


def test_summoning_aspect_carries_its_own_occult_gate():
    c = _character(occult=2, art_specialties=[
        ArtSpecialty(art_id="art.summoning", name="Spirits")])     # needs Occult 3
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-aspect-occult" in codes


def test_player_invented_specialty_is_ungated():
    """The book invites invented specialties; only printed aspects carry minima."""
    c = _character(occult=1, art_specialties=[
        ArtSpecialty(art_id="art.summoning", name="Ancestral Ghosts of My Village")])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-aspect-occult" not in codes


def test_specialty_without_the_art_is_legal():
    """Stated three times in the source (p.116, p.126 twice). Never gate this."""
    c = _character(art_specialties=[ArtSpecialty(art_id="art.summoning", name="Beasts")])
    assert validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy) == []


def test_narrowing_outside_summoning_is_an_issue():
    c = _character(art_specialties=[
        ArtSpecialty(art_id="art.astrology", name="Gods", narrowed=True)])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-narrowing-unavailable" in codes


def test_narrowing_on_summoning_is_legal():
    c = _character(art_specialties=[
        ArtSpecialty(art_id="art.summoning", name="Beasts", narrowed=True)])
    assert validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy) == []


def test_ritual_needs_occult_equal_to_its_level():
    c = _character(occult=2, rituals=[RitualEntry(ritual_id="rit.gate")])   # level 3
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-ritual-occult" in codes


def test_ritual_at_exactly_its_level_is_legal():
    c = _character(occult=3, rituals=[RitualEntry(ritual_id="rit.gate")])
    assert validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy) == []


def test_custom_ritual_is_gated_on_its_inline_level():
    c = _character(occult=1, rituals=[RitualEntry(name="Home-brew", level=4)])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-ritual-occult" in codes


def test_science_above_its_own_max_rating_is_an_issue():
    c = _character(sciences=[ScienceRating(science_id="science.geomancy", rating=6)])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-science-range" in codes


def test_alchemy_six_is_legal_where_geomancy_six_is_not():
    """The six-dot rung is printed, and is the reason max_rating is per-Science."""
    c = _character(sciences=[ScienceRating(science_id="science.alchemy", rating=6)])
    codes = [i.code for i in validate.thaumaturgy_issues(_ruleset(), c, c.thaumaturgy)]
    assert "thaum-science-range" not in codes


def test_unusable_splat_holding_thaumaturgy_is_info_not_an_error():
    """Ghosts keep what they learned and may never use it — a flag, not a bar."""
    rs = _ruleset(thaumaturgy_usable=False)
    c = _character(arts=["art.summoning"])
    (issue,) = [i for i in validate.thaumaturgy_issues(rs, c, c.thaumaturgy)
                if i.code == "thaum-unusable"]
    assert issue.severity == "info"


def test_unusable_splat_with_no_thaumaturgy_says_nothing():
    rs = _ruleset(thaumaturgy_usable=False)
    c = _character()
    assert validate.thaumaturgy_issues(rs, c, c.thaumaturgy or ThaumaturgyState()) == []


def test_validate_chargen_runs_the_thaumaturgy_gates():
    c = _character(occult=1, arts=["art.astrology"])
    codes = [i.code for i in validate.validate_chargen(_ruleset(), c)]
    assert "thaum-art-occult" in codes


# --------------------------------------------------------------------------- #
# The chargen freeze
# --------------------------------------------------------------------------- #

def test_lock_freezes_thaumaturgy():
    c = _character(arts=["art.summoning"])
    lifecycle.lock_chargen(c)
    assert c.chargen_snapshot.thaumaturgy.arts == ["art.summoning"]


def test_snapshot_is_a_deep_copy():
    c = _character(rituals=[RitualEntry(ritual_id="rit.gate")])
    lifecycle.lock_chargen(c)
    c.thaumaturgy.rituals[0].orientations.append(O.NORTH)
    assert c.chargen_snapshot.thaumaturgy.rituals[0].orientations == [O.REALM]


def test_lock_leaves_thaumaturgy_none_when_there_is_none():
    c = _character()
    lifecycle.lock_chargen(c)
    assert c.chargen_snapshot.thaumaturgy is None


def test_bp_reads_the_snapshot_not_post_lock_purchases():
    """Post-lock XP purchases must never inflate the chargen bonus-point spend."""
    c = _character(arts=["art.summoning"])
    lifecycle.lock_chargen(c)
    c.xp_earned = 50
    advancement.learn_thaum_ritual(_ruleset(), c, "rit.gate")
    line = next(ln for ln in validate.bonus_point_breakdown(_ruleset(), c).lines
                if ln.domain == "Thaumaturgy")
    assert line.points == 5           # the Art alone; the ritual was bought with XP


# --------------------------------------------------------------------------- #
# XP transitions
# --------------------------------------------------------------------------- #

def _locked(xp: int = 50, **thaum) -> Character:
    c = _character(**thaum)
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    return c


def test_learn_art_costs_and_records():
    rs, c = _ruleset(), _locked()
    entry = advancement.learn_thaum_art(rs, c, "art.summoning")
    assert entry.cost == 5
    assert c.thaumaturgy.arts == ["art.summoning"]
    assert advancement.xp_available(c) == 45


def test_learn_art_creates_the_state_on_a_character_that_had_none():
    c = _locked()
    assert c.thaumaturgy is None
    advancement.learn_thaum_art(_ruleset(), c, "art.summoning")
    assert c.thaumaturgy is not None


def test_learn_unknown_art_refuses():
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_thaum_art(_ruleset(), _locked(), "art.nonesuch")


def test_learn_art_twice_refuses():
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_art(rs, c, "art.summoning")
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_thaum_art(rs, c, "art.summoning")


def test_specialty_xp_differs_from_its_bp_rate():
    """The two printed tables deliberately disagree: 2 BP but 3 XP."""
    entry = advancement.add_thaum_specialty(_ruleset(), _locked(), "art.summoning", "Beasts")
    assert entry.cost == 3


def test_narrowed_specialty_xp_is_halved_rounded_up():
    entry = advancement.add_thaum_specialty(
        _ruleset(), _locked(), "art.summoning", "Beasts", narrowed=True)
    assert entry.cost == 2


def test_specialty_does_not_require_the_art():
    c = _locked()
    advancement.add_thaum_specialty(_ruleset(), c, "art.summoning", "Beasts")
    assert c.thaumaturgy.arts == []


def test_ritual_xp_base_is_three_not_the_bp_table_two():
    entry = advancement.learn_thaum_ritual(_ruleset(), _locked(), "rit.gate")
    assert entry.cost == 6          # 3 + 1 per level, level 3


def test_ritual_is_learned_in_exactly_one_orientation():
    c = _locked()
    advancement.learn_thaum_ritual(_ruleset(), c, "rit.gate", orientation=O.NORTH)
    assert c.thaumaturgy.rituals[0].orientations == [O.NORTH]


def test_custom_ritual_can_be_learned():
    c = _locked()
    entry = advancement.learn_thaum_ritual(_ruleset(), c, name="Home-brew", level=2)
    assert entry.cost == 5
    assert c.thaumaturgy.rituals[0].ritual_id == ""


def test_custom_ritual_needs_a_name():
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_thaum_ritual(_ruleset(), _locked(), name="   ")


def test_formula_is_a_flat_point_regardless_of_level():
    entry = advancement.learn_thaum_formula(_ruleset(), _locked(), "for.draught")
    assert entry.cost == 1


def test_formula_inherits_its_science_from_the_catalogue():
    c = _locked()
    advancement.learn_thaum_formula(_ruleset(), c, "for.draught")
    assert c.thaumaturgy.formulas[0].science_id == "science.alchemy"


def test_extra_orientation_is_one_point():
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, "rit.gate")
    entry = advancement.add_thaum_orientation(rs, c, "ritual", "rit.gate", O.NORTH)
    assert entry.cost == 1
    assert c.thaumaturgy.rituals[0].orientations == [O.REALM, O.NORTH]


def test_mastering_all_five_orientations_costs_four_over_the_base():
    """The book's own worked figure (p.124): "to completely master all versions of a
    given spell would cost four bonus points, in addition to the normal cost"."""
    rs, c = _ruleset(), _locked()
    base = advancement.learn_thaum_ritual(rs, c, "rit.gate").cost
    extra = sum(advancement.add_thaum_orientation(rs, c, "ritual", "rit.gate", o).cost
                for o in (O.NORTH, O.SOUTH, O.EAST, O.WEST))
    assert extra == 4 and base == 6


def test_duplicate_orientation_refuses():
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, "rit.gate", orientation=O.NORTH)
    with pytest.raises(advancement.AdvancementError):
        advancement.add_thaum_orientation(rs, c, "ritual", "rit.gate", O.NORTH)


def test_orientation_of_an_unknown_ritual_refuses():
    with pytest.raises(advancement.AdvancementError):
        advancement.add_thaum_orientation(_ruleset(), _locked(), "ritual", "rit.gate", O.NORTH)


def test_thaumaturgy_purchases_require_a_lock():
    c = _character()
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_thaum_art(_ruleset(), c, "art.summoning")


def test_unaffordable_purchase_refuses():
    with pytest.raises(advancement.AdvancementError):
        advancement.learn_thaum_art(_ruleset(), _locked(xp=1), "art.summoning")


# --------------------------------------------------------------------------- #
# Undo
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("buy,attr", [
    (lambda rs, c: advancement.learn_thaum_art(rs, c, "art.summoning"), "arts"),
    (lambda rs, c: advancement.add_thaum_specialty(rs, c, "art.summoning", "Beasts"),
     "art_specialties"),
    (lambda rs, c: advancement.learn_thaum_ritual(rs, c, "rit.gate"), "rituals"),
    (lambda rs, c: advancement.learn_thaum_formula(rs, c, "for.draught"), "formulas"),
])
def test_undo_reverses_each_kind(buy, attr):
    rs, c = _ruleset(), _locked()
    buy(rs, c)
    advancement.undo_last(rs, c)
    assert getattr(c.thaumaturgy, attr) == []
    assert c.xp_log == []
    assert advancement.xp_available(c) == 50


def test_undo_an_orientation_leaves_the_ritual():
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, "rit.gate")
    advancement.add_thaum_orientation(rs, c, "ritual", "rit.gate", O.NORTH)
    advancement.undo_last(rs, c)
    assert c.thaumaturgy.rituals[0].orientations == [O.REALM]


def test_undo_never_strips_the_last_orientation():
    """An entry with no orientations is not a state the model allows, and the base
    purchase paid for one."""
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, "rit.gate", orientation=O.NORTH)
    c.xp_log.append(c.xp_log[0].model_copy(
        update={"target": "thaum_orientations.ritual", "detail": "rit.gate:North",
                "cost": 1}))
    advancement.undo_last(rs, c)
    assert c.thaumaturgy.rituals[0].orientations == [O.NORTH]


def test_undo_a_custom_ritual_whose_name_contains_a_colon():
    """detail for an orientation row is "<key>:<Orientation>" — parsed right-to-left
    precisely so a custom name may contain a colon."""
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, name="Rite: The Gate", level=1)
    advancement.add_thaum_orientation(rs, c, "ritual", "Rite: The Gate", O.NORTH)
    advancement.undo_last(rs, c)
    assert c.thaumaturgy.rituals[0].orientations == [O.REALM]


# --------------------------------------------------------------------------- #
# The XP audit
# --------------------------------------------------------------------------- #

def _audit_codes(rs, c):
    return [i.code for i in advancement.validate_xp(rs, c)]


@pytest.mark.parametrize("buy", [
    lambda rs, c: advancement.learn_thaum_art(rs, c, "art.summoning"),
    lambda rs, c: advancement.add_thaum_specialty(rs, c, "art.summoning", "Beasts"),
    lambda rs, c: advancement.add_thaum_specialty(rs, c, "art.summoning", "Beasts",
                                                  narrowed=True),
    lambda rs, c: advancement.learn_thaum_ritual(rs, c, "rit.gate"),
    lambda rs, c: advancement.learn_thaum_formula(rs, c, "for.draught"),
])
def test_audit_reprices_each_kind_to_the_same_figure(buy):
    rs, c = _ruleset(), _locked()
    buy(rs, c)
    assert "xp-cost-mismatch" not in _audit_codes(rs, c)


def test_audit_reprices_an_orientation_row():
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, "rit.gate")
    advancement.add_thaum_orientation(rs, c, "ritual", "rit.gate", O.NORTH)
    assert "xp-cost-mismatch" not in _audit_codes(rs, c)


def test_audit_catches_an_underpaid_ritual():
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, "rit.gate")
    c.xp_log[-1].cost = 2
    assert "xp-cost-mismatch" in _audit_codes(rs, c)


def test_audit_reprices_a_custom_ritual_from_the_log_row():
    """A custom ritual is absent from the catalogue, so the level must ride on the
    log row or the audit could not price it at all."""
    rs, c = _ruleset(), _locked()
    advancement.learn_thaum_ritual(rs, c, name="Home-brew", level=4)
    assert c.xp_log[-1].cost == 7
    assert "xp-cost-mismatch" not in _audit_codes(rs, c)


def test_audit_distinguishes_a_narrowed_specialty_from_a_plain_one():
    """The two rows are otherwise identical; mispricing here is exactly the failure
    the narrowed flag exists to prevent."""
    rs, c = _ruleset(), _locked()
    advancement.add_thaum_specialty(rs, c, "art.summoning", "Beasts", narrowed=True)
    c.xp_log[-1].cost = 3                        # the un-narrowed rate
    assert "xp-cost-mismatch" in _audit_codes(rs, c)


# --------------------------------------------------------------------------- #
# Sciences (rate from the rules authority, not the printed tables)
# --------------------------------------------------------------------------- #

def test_first_science_dot_costs_seven_xp():
    rs, c = _ruleset(), _locked()
    entry = advancement.raise_thaum_science(rs, c, "science.alchemy")
    assert entry.cost == 7
    assert c.thaumaturgy.sciences[0].rating == 1


@pytest.mark.parametrize("to_rating,cost", [(2, 6), (3, 12), (4, 18)])
def test_later_science_dots_cost_current_rating_times_six(to_rating, cost):
    rs, c = _ruleset(), _locked(xp=200)
    for _ in range(to_rating):
        entry = advancement.raise_thaum_science(rs, c, "science.alchemy")
    assert entry.cost == cost


def test_science_xp_and_bp_ladders_deliberately_disagree():
    """5/7 BP a dot against 7 then current x 6 XP — the same shape asymmetry the
    Art Specialty rows already have. Do not tidy them into agreement."""
    rs, c = _ruleset(), _locked(xp=200)
    xp_to_three = sum(advancement.raise_thaum_science(rs, c, "science.alchemy").cost
                      for _ in range(3))
    bp_to_three = next(
        ln.points for ln in validate.bonus_point_breakdown(
            rs, _character(sciences=[ScienceRating(science_id="science.alchemy", rating=3)])
        ).lines if ln.domain == "Thaumaturgy")
    assert (xp_to_three, bp_to_three) == (25, 19)


def test_science_stops_at_its_own_max_rating():
    """Geomancy caps at 5 where Alchemy runs to 6 — the reason max_rating is
    per-Science rather than the usual _DOT_MAX."""
    rs, c = _ruleset(), _locked(xp=500)
    for _ in range(5):
        advancement.raise_thaum_science(rs, c, "science.geomancy")
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_thaum_science(rs, c, "science.geomancy")


def test_alchemy_reaches_six():
    rs, c = _ruleset(), _locked(xp=500)
    for _ in range(6):
        advancement.raise_thaum_science(rs, c, "science.alchemy")
    assert c.thaumaturgy.sciences[0].rating == 6


def test_raise_unknown_science_refuses():
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_thaum_science(_ruleset(), _locked(), "science.nonesuch")


def test_undo_removes_a_freshly_learned_science():
    rs, c = _ruleset(), _locked()
    advancement.raise_thaum_science(rs, c, "science.alchemy")
    advancement.undo_last(rs, c)
    assert c.thaumaturgy.sciences == []


def test_undo_a_raise_restores_the_previous_rating():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_thaum_science(rs, c, "science.alchemy")
    advancement.raise_thaum_science(rs, c, "science.alchemy")
    advancement.undo_last(rs, c)
    assert c.thaumaturgy.sciences[0].rating == 1


def test_audit_reprices_science_rows():
    rs, c = _ruleset(), _locked(xp=200)
    for _ in range(3):
        advancement.raise_thaum_science(rs, c, "science.alchemy")
    assert "xp-cost-mismatch" not in _audit_codes(rs, c)


def test_audit_catches_an_underpaid_science_raise():
    rs, c = _ruleset(), _locked(xp=200)
    advancement.raise_thaum_science(rs, c, "science.alchemy")
    advancement.raise_thaum_science(rs, c, "science.alchemy")
    c.xp_log[-1].cost = 3
    assert "xp-cost-mismatch" in _audit_codes(rs, c)
