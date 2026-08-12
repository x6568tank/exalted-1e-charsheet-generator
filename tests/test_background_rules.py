"""Tests for docs/briefs-background-rules.md — enforcing the Background numeric rules.

R1  Sidereal Connections ≤ the Attribute total (chargen only)
R2  Sidereal Celestial Manse ≤3 on BOTH sides, a PER-CHARACTER HouseRules toggle lifts it
R3  Mortals barred from Artifact/Manse (both origins, chargen only), ST toggle lifts it
R4  Mountain Folk Artifact ≤10 (both sides), one bonus point per dot above 5
R5  the rating controls take their ceiling from the engine; only R2/R4 bind post-lock

Which test pins which ruling is stated in each docstring. The R5 UI tests are the ones
the two hardcoded 5s in ui/advantages.py were invisible to — an engine-only test cannot
see a widget's `max`, which is why the ceilings survived this long.

Every genuinely new rule test (R1-R4, and the MF half of R5) FAILS against the code
before this brief: R1-R3 because the rules had no read site, R4 because the model
capped BackgroundEntry.rating at 5 and the controls at 5. The guard tests (Solar still
stops at 5; the chargen-only caps stay chargen-only) pass before and after — they pin
the behaviour that must NOT move, which is the whole point of test #6 in the brief.
"""

from pathlib import Path

import pytest
from nicegui import ui

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import lifecycle, validate
from exalted_builder.models.character import (BackgroundEntry, Character, HouseRules)
from exalted_builder.models.rules import AttributeName

_DATA = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_app_ruleset(_DATA)


def _all_one_attributes():
    """Every attribute at 1 — a clean base. R1's cap is the COMPUTED sum of these, so
    the tests never assert the printed 27 (what the sum happens to be for a default
    chargen spend, not a rule)."""
    return {a: 1 for a in AttributeName}


def _sidereal(backgrounds=(), **kw):
    c = Character(id="r-sid", exalt_type="Sidereal", caste="battles", **kw)
    c.attributes = _all_one_attributes()
    c.backgrounds = list(backgrounds)
    return c


def _mortal(origin="", backgrounds=(), **kw):
    c = Character(id="r-mort", exalt_type="Mortal", origin=origin, **kw)
    c.attributes = _all_one_attributes()
    c.backgrounds = list(backgrounds)
    return c


def _mf(origin="enlightened", backgrounds=(), **kw):
    c = Character(id="r-mf", exalt_type="Mountain-Folk", origin=origin, caste="worker",
                  essence_rating=2, **kw)
    c.attributes = {a: 3 for a in AttributeName}
    c.backgrounds = list(backgrounds)
    return c


# --------------------------------------------------------------------------- #
# R1 — Sidereal Connections capped by the Attribute total (chargen only)
# --------------------------------------------------------------------------- #

def test_r1_connections_capped_by_the_attribute_sum(rs):
    """R1. Sidereals pp.106-108: "You cannot manage more points of Connections than the
    sum of your character's Physical, Social and Mental Attributes combined." Chargen
    only. The cap is the COMPUTED attribute sum — never the literal 27 — and spending
    BP on Attributes raises the allowance."""
    c = _sidereal()
    b = rs.budgets_for("Sidereal")
    attr_sum = sum(c.attributes.values())
    # The cap is a TOTAL, so it is exercised with ROWS — each within the universal 5,
    # which is the per-row ceiling (human's ruling 2026-08-12). A single row carrying
    # the whole allowance was the original fixture here and stopped being expressible
    # when the row was held to 5; it also conflated the two ceilings.
    def rows(total):
        full, rest = divmod(total, 5)
        return [BackgroundEntry(name="Connections", rating=5)] * full + (
            [BackgroundEntry(name="Connections", rating=rest)] if rest else [])

    # over the sum errors
    over = [i.code for i in validate.background_issues(b, rows(attr_sum + 1), c)]
    assert over == ["background-above-attribute-cap"]
    # at exactly the sum is legal
    assert validate.background_issues(b, rows(attr_sum), c) == []
    # spending BP on Attributes raises the allowance: one more dot is now legal
    c.attributes[AttributeName.STRENGTH] += 1
    raised_sum = sum(c.attributes.values())
    assert validate.background_issues(b, rows(raised_sum), c) == []
    # chargen only: post-lock a locked Sidereal may be handed Connections by the story
    locked = _sidereal([BackgroundEntry(name="Connections", rating=5)] * 2)
    lifecycle.lock_chargen(locked, rs)
    assert not [i for i in validate.validate(rs, locked)
                if "background-above-attribute" in i.code]


def test_r1_connections_capped_through_validate_chargen(rs):
    """R1, driven through the REAL chargen path. The test above calls
    `background_issues` with the character by hand, which is what let `validate_chargen`
    omit the character and silently skip the cap in production — the house bug in its
    purest form. A rule whose required input is omitted by its caller is a rule that
    does not run. The Attribute-sum cap and the ST-toggle reads both go through this
    path."""
    # Two rows of 5, not one of 10: the per-row ceiling is the universal 5, and a
    # single illegal row would make this pass on the wrong error.
    c = _sidereal([BackgroundEntry(name="Connections", rating=5)] * 2)  # base attrs sum 9
    assert any(i.code == "background-above-attribute-cap"
               for i in validate.validate_chargen(rs, c))
    # spending BP on Attributes raises the allowance through the same path
    c2 = _sidereal([BackgroundEntry(name="Connections", rating=5)] * 2)
    c2.attributes[AttributeName.STRENGTH] += 1                        # sum 10
    assert not [i for i in validate.validate_chargen(rs, c2)
                if i.code == "background-above-attribute-cap"]


# --------------------------------------------------------------------------- #
# R2 — Sidereal Celestial Manse ≤3, both sides, PER-CHARACTER toggle
# --------------------------------------------------------------------------- #

def test_r2_celestial_manse_ceiling_binds_both_sides_and_the_toggle_lifts_both(rs):
    """R2. Sidereals p.106: "Characters cannot buy above Celestial Manse ••• without
    special Storyteller permission." One of exactly TWO rules that bind post-lock, so
    a locked Sidereal is still held to ••• — and the PER-CHARACTER toggle lifts both
    sides while a second character at the same table stays capped."""
    b = rs.budgets_for("Sidereal")
    c = _sidereal([BackgroundEntry(name="Celestial Manse", rating=4)])
    # chargen
    assert [i.code for i in validate.background_issues(b, c.backgrounds, c)] == [
        "background-above-origin-cap"]
    # post-lock
    lifecycle.lock_chargen(c, rs)
    assert [i.code for i in validate.validate(rs, c)
            if i.code == "background-above-origin-cap"]
    # the per-character toggle lifts both sides
    c.house_rules = HouseRules(st_celestial_manse_over_three=True)
    assert validate.background_issues(b, c.backgrounds, c) == []
    assert not [i.code for i in validate.validate(rs, c)
                if i.code == "background-above-origin-cap"]
    # a SECOND character at the same table is unaffected (it is PER-CHARACTER)
    c2 = _sidereal([BackgroundEntry(name="Celestial Manse", rating=4)])
    assert [i.code for i in validate.background_issues(b, c2.backgrounds, c2)] == [
        "background-above-origin-cap"]
    # three dots are legal on both sides without any permission
    c3 = _sidereal([BackgroundEntry(name="Celestial Manse", rating=3)])
    assert validate.background_issues(b, c3.backgrounds, c3) == []


# --------------------------------------------------------------------------- #
# R3 — Mortals barred from Artifact/Manse (chargen only)
# --------------------------------------------------------------------------- #

def test_r3_mortals_barred_from_artifact_and_manse_in_both_origins(rs):
    """R3. Core p.103: "Mortals … may not purchase the Artifacts or Manse Backgrounds
    without Storyteller permission." A BAR (rating must be 0) on BOTH mortal origins,
    lifted by the per-character toggle; a non-mortal is unaffected."""
    for origin in ("", "ordinary"):
        b = rs.budgets_for("Mortal", origin)
        for name in ("Artifact", "Manse"):
            c = _mortal(origin=origin, backgrounds=[BackgroundEntry(name=name, rating=1)])
            assert [i.code for i in validate.background_issues(b, c.backgrounds, c)] == [
                "background-barred"], (origin, name)
    # the per-character toggle lifts it
    c = _mortal(backgrounds=[BackgroundEntry(name="Artifact", rating=3)])
    c.house_rules = HouseRules(st_mortal_artifact_manse=True)
    assert validate.background_issues(rs.budgets_for("Mortal"), c.backgrounds, c) == []
    # a non-mortal is unaffected
    solar = Character(id="r3-sol", exalt_type="Solar", caste="dawn")
    solar.attributes = _all_one_attributes()
    solar.backgrounds = [BackgroundEntry(name="Artifact", rating=5)]
    assert validate.background_issues(rs.budgets_for("Solar"), solar.backgrounds,
                                      solar) == []


def test_r3_mortal_toggle_lifts_through_validate_chargen(rs):
    """R3, through the REAL chargen path. Before `validate_chargen` passed the
    character, the PER-CHARACTER toggle could never lift the bar in production — the
    bar read no permission and bound unconditionally, with no way to clear it. The
    pure `background_issues` tests above hid that by passing the character by hand."""
    c = _mortal(backgrounds=[BackgroundEntry(name="Manse", rating=2)])
    assert any(i.code == "background-barred"
               for i in validate.validate_chargen(rs, c))
    c.house_rules = HouseRules(st_mortal_artifact_manse=True)
    assert not [i for i in validate.validate_chargen(rs, c)
                if i.code == "background-barred"]


# --------------------------------------------------------------------------- #
# R4 — Mountain Folk Artifact ≤10 (both sides), one BP per dot above 5
# --------------------------------------------------------------------------- #

def test_r4_mountain_folk_artifact_reaches_ten_and_is_refused_at_eleven(rs):
    """R4. CH6 p.234-235: "The greatest Enlightened heroes of the Mountain Folk can
    possess this Background above a rating of 5." The ceiling is 10 — the human's
    ruling 2026-08-12, since the book prints no upper bound — and it binds on BOTH
    sides: a character who leaves chargen at 6 still holds 6, and can reach 7 when the
    story grants one. Both Mountain Folk origins carry the lift."""
    for origin in ("enlightened", "unenlightened"):
        b = rs.budgets_for("Mountain-Folk", origin)
        c = _mf(origin=origin, backgrounds=[BackgroundEntry(name="Artifact", rating=10)])
        assert validate.background_issues(b, c.backgrounds, c) == []
        # refused at 11 (a value past the structural 10 the model allows, as a
        # hand-edited save or a click past the control's ceiling would be)
        c.backgrounds[0].rating = 11
        assert [i.code for i in validate.background_issues(b, c.backgrounds, c)] == [
            "background-above-origin-cap"]
    # post-lock: 10 stays legal, 11 is refused — the ceiling follows the story
    b = rs.budgets_for("Mountain-Folk", "enlightened")
    c = _mf(backgrounds=[BackgroundEntry(name="Artifact", rating=10)])
    lifecycle.lock_chargen(c, rs)
    assert not [i for i in validate.validate(rs, c) if "background-above" in i.code]
    c.backgrounds[0].rating = 11
    assert [i.code for i in validate.validate(rs, c) if "background-above" in i.code] == [
        "background-above-origin-cap"]


def test_r4_dots_above_five_cost_one_bonus_point(rs):
    """R4. "…with each dot beyond 5 costing one bonus point." Artifact 7 = dots 1-5
    from the Background pool, dots 6-7 one bonus point each — a 2-BP bill, not a pool
    bill and not the ordinary above-3 rate."""
    c = _mf(backgrounds=[BackgroundEntry(name="Artifact", rating=7)])
    b = rs.budgets_for("Mountain-Folk", "enlightened")
    within, above = validate.background_pool_spend(rs, c, b, c.backgrounds)
    assert within == 5, f"dots 1-5 should come from the pool, got within={within}"
    assert above == [1, 1], f"dots 6-7 should cost one bonus point each, got {above}"
    bd = validate.bonus_point_breakdown(rs, c)
    bg_line = next(l for l in bd.lines if l.domain == "Backgrounds")
    assert bg_line.points == 2


def test_r4_every_other_splat_still_stops_at_five(rs):
    """R4's guard: the 10-ceiling belongs to the Mountain Folk Artifact alone. No other
    splat's Artifact rule raises the ceiling above 5, so the universal trait cap still
    binds everyone else."""
    for key, row in rs.budgets.items():
        if key.startswith("Mountain-Folk"):
            continue
        rule = row.background_rules.get("artifact")
        if rule is None:
            continue
        assert rule.max_rating <= 5, (key, rule.max_rating)


# --------------------------------------------------------------------------- #
# R5 — the rating controls take their ceiling from the engine
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_r5_chargen_dot_track_offers_ten_for_mf_artifact_and_five_for_solar(user):
    """R5. The chargen dot track's ceiling comes from the engine, not the hardcoded
    `min(meritsmod.DOT_MAX, …)`: a Mountain Folk Artifact row offers 10 pips (the CH6
    lift) and a Solar one stays at 5. This is the control a hardcoded 5 was invisible
    to — the lift could not even be recorded."""
    await user.open('/mf-artifact-chargen')
    mf_pips = sorted([e for e in user.client.elements.values() if isinstance(e, ui.icon)],
                     key=lambda e: e.id)
    assert len(mf_pips) == 10, \
        f"MF Artifact row should offer 10 pips, got {len(mf_pips)}"
    await user.open('/solar-artifact-chargen')
    sol_pips = sorted([e for e in user.client.elements.values() if isinstance(e, ui.icon)],
                      key=lambda e: e.id)
    assert len(sol_pips) == 5, \
        f"Solar Artifact row should stay at 5 pips, got {len(sol_pips)}"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_r5_play_number_input_ceiling_comes_from_the_engine(user):
    """R5. The play number input's max is the engine's post-lock ceiling, not the
    hardcoded `max=5`: it accepts 7 for a Mountain Folk Artifact (ceiling 10) and
    refuses it for a Solar one (ceiling 5). This is the other control the hardcoded 5
    lived in — game logic in a widget, which is also what this test catches."""
    await user.open('/mf-artifact-play')
    mf_number = next(e for e in user.client.elements.values()
                     if isinstance(e, ui.number) and e.props.get("label") is None)
    assert mf_number.max == 10, f"MF Artifact should accept up to 10, got max {mf_number.max}"
    # 7 is accepted and written through to the row: the 3-dot rung (the borrowed
    # ladder's rung for the rating the row held) is replaced by nothing, because
    # rating 7 is off the 5-dot ladder. The write-through is read on the page —
    # `should_not_see` polls, which is what lets the on_change actually run — rather
    # than on a module-level character, whose identity against the page's copy is
    # harness-order-dependent.
    mf_number.value = 7
    await user.should_not_see("A powerful weapon or suit of armor")
    await user.open('/solar-artifact-play')
    sol_number = next(e for e in user.client.elements.values()
                      if isinstance(e, ui.number) and e.props.get("label") is None)
    assert sol_number.max == 5, f"Solar Artifact should stop at 5, got max {sol_number.max}"


# --------------------------------------------------------------------------- #
# R5 — the second call site must not move the chargen-only caps
# --------------------------------------------------------------------------- #

def test_r5_existing_chargen_only_caps_still_do_not_bind_post_lock(rs):
    """R5's guard (brief test #6). Adding the post-lock `background_issues` call site
    must NOT make every existing `max_rating` bind post-lock — only R2/R4 do. A locked
    Unenlightened Mountain Folk can be given Backing 4 by the story (characters change
    Backgrounds through the story, not by purchase), while chargen still refuses it."""
    # chargen: the Unenlightened Backing ≤2 cap still binds
    c = _mf(origin="unenlightened", backgrounds=[BackgroundEntry(name="Backing", rating=3)])
    b = rs.budgets_for("Mountain-Folk", "unenlightened")
    assert [i.code for i in validate.background_issues(b, c.backgrounds, c)] == [
        "background-above-origin-cap"]
    # post-lock: the same cap does NOT bind — no background-above-origin-cap at all
    lifecycle.lock_chargen(c, rs)
    assert not [i for i in validate.validate(rs, c)
                if i.code == "background-above-origin-cap"]


def test_universal_cap_holds_every_background_on_both_sides(rs):
    """R5's other guard. Relaxing `BackgroundEntry.rating` to `le=10` removed the
    model's structural enforcement of the universal trait cap (5) — a hand-edited or
    older save could hold a Solar Artifact 10 and no rule would flag it. The engine
    now enforces the cap on BOTH sides: any Background over 5 is refused unless a rule
    explicitly raises the ceiling (only the Mountain Folk Artifact ≤10 does)."""
    sol = Character(id="r5-sol", exalt_type="Solar", caste="dawn")
    sol.attributes = _all_one_attributes()
    sol.backgrounds = [BackgroundEntry(name="Artifact", rating=10)]
    assert any(i.code == "background-above-universal-cap"
               for i in validate.validate_chargen(rs, sol))
    lifecycle.lock_chargen(sol, rs)
    assert any(i.code == "background-above-universal-cap"
               for i in validate.validate(rs, sol))
    # the raised ceiling stays legal on both sides
    mf = _mf(backgrounds=[BackgroundEntry(name="Artifact", rating=10)])
    assert not [i for i in validate.validate_chargen(rs, mf)
                if i.code == "background-above-universal-cap"]
    lifecycle.lock_chargen(mf, rs)
    assert not [i for i in validate.validate(rs, mf)
                if i.code == "background-above-universal-cap"]


def test_a_rule_may_raise_the_universal_cap_but_never_remove_it(rs):
    """The third round of one root cause, and the narrowest opening it left.

    The universal 5 used to be a structural invariant on `BackgroundEntry.rating`;
    every fix since has re-derived it from `BackgroundRule`, which was never meant to
    carry it. The version before this one skipped the check whenever a rule merely
    EXISTED — so the three rules that state no maximum at all lost the cap at chargen
    while keeping it post-lock, which is the "correct in the case you tested" shape.

    Alchemical Class states `min_rating`, Alchemical Backing states `requires`, and
    Illuminated Illumination states `min_rating`. None of them says anything about a
    ceiling, so all three are held to 5."""
    for exalt, caste, origin, rows in (
            ("Alchemical", "orichalcum", "", [("Class", 10)]),
            ("Alchemical", "orichalcum", "", [("Class", 3), ("Backing", 10)]),
            ("Solar", "dawn", "illuminated", [("Illumination", 10)]),
    ):
        c = Character(id="ucap", exalt_type=exalt, caste=caste, origin=origin,
                      essence_rating=2)
        c.attributes = _all_one_attributes()
        c.backgrounds = [BackgroundEntry(name=n, rating=r) for n, r in rows]
        assert any(i.code == "background-above-universal-cap"
                   for i in validate.validate_chargen(rs, c)), (exalt, rows)

    # A rule that caps LOWER reports through its own check, and must not be reported
    # twice for the same row.
    mf = _mf(origin="unenlightened",
             backgrounds=[BackgroundEntry(name="Backing", rating=10)])
    codes = [i.code for i in validate.validate_chargen(rs, mf)
             if i.code.startswith("background-above")]
    assert codes == ["background-above-origin-cap"], codes


def test_connections_caps_the_row_at_five_and_the_total_at_the_attribute_sum(rs):
    """Two ceilings on one Background, measuring different things.

    `max_rating_is_attribute_sum` reads `background_rating`, which SUMS every row
    sharing the name — the printed rule caps the TOTAL ("the total number of dots in
    Connections may not exceed" the sum, Sidereals pp.106-108). It therefore says
    nothing about a single row, which keeps the universal 5 like every other Background
    (human's ruling 2026-08-12; a row briefly shipped at 10 and was reverted — 27 or
    even 10 pips in one row looks unlike anything else on the sheet)."""
    b = rs.budgets_for("Sidereal")
    c = _sidereal()
    c.attributes = {a: 3 for a in AttributeName}        # sum 27

    # the control offers the universal 5 — never the 27-dot allowance
    assert validate.background_rating_cap(b, c, "Connections") == 5

    # one row is held to 5…
    c.backgrounds = [BackgroundEntry(name="Connections", rating=8)]
    assert [i.code for i in validate.validate_chargen(rs, c)
            if i.code.startswith("background-above")] == ["background-above-universal-cap"]
    # …two legal rows are legal…
    c.backgrounds = [BackgroundEntry(name="Connections", rating=5)] * 2
    assert not [i for i in validate.validate_chargen(rs, c)
                if i.code.startswith("background-above")]
    # …and the TOTAL still binds across rows: six rows of 5 is 30 against a sum of 27.
    c.backgrounds = [BackgroundEntry(name="Connections", rating=5)] * 6
    assert [i.code for i in validate.validate_chargen(rs, c)
            if i.code.startswith("background-above")] == ["background-above-attribute-cap"]


# --------------------------------------------------------------------------- #
# Preflight render matrix — three ceiling shapes the R5 tests do not produce
# --------------------------------------------------------------------------- #

def _pips(user) -> int:
    """Pip icons on the page. Each route holds exactly ONE dotted Background row."""
    from nicegui import ui as _ui
    return len([e for e in user.client.elements.values() if isinstance(e, _ui.icon)])


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_connections_row_offers_the_universal_five(user) -> None:
    """The rule's cap measures a TOTAL, so it must not reach the row: 27 pips would
    mean the attribute-sum leaked into the control, which is what shipped first."""
    await user.open('/sidereal-connections-chargen')
    assert _pips(user) == 5, _pips(user)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_barred_row_the_character_holds_can_still_be_stepped_down(user) -> None:
    """The mortal Artifact bar puts the ceiling at 0 while the character holds 2 — an
    older save, or the moment after the ST revokes permission. The dot track draws
    `max(hi, current)`, so the row must still show its 2 pips; a row drawn at the
    ceiling would strand the player with an error and no control to clear it."""
    await user.open('/mortal-artifact-barred-chargen')
    assert _pips(user) == 2, _pips(user)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_locked_row_above_its_post_lock_ceiling_still_renders(user) -> None:
    """Celestial Manse 5 against a post-lock ceiling of 3: the play control is a
    `ui.number` whose `max` is now engine-supplied, and a value above `max` must not
    stop the panel building (the blank-tab class). The row renders and the rule still
    reports the excess."""
    from nicegui import ui as _ui
    await user.open('/sidereal-over-ceiling-play')
    await user.should_see("Celestial Manse")
    numbers = [e for e in user.client.elements.values()
               if isinstance(e, _ui.number) and e.props.get("label") is None]
    assert numbers and numbers[0].value == 5, [n.value for n in numbers]


def test_the_mortal_toggle_moves_the_OFFER_list_not_only_the_bar(rs):
    """Found in the browser, 2026-08-12: a mortal with Storyteller permission still
    could not find Artifact or Manse in the catalogue.

    The bar and the offer are SEPARATE mechanisms — `BackgroundRule.barred` decides
    legality, `catalogue_backgrounds` decides what the dropdown lists — and the toggle
    moved only the first. Lifting a prohibition the player cannot then act on is worse
    than not offering the toggle. `background_catalogue_for` now hides a barred
    Background until its toggle lifts it, the same treatment `banned_backgrounds`
    already gets, and both mortal rows list Artifact and Manse so there is something
    for the permission to reveal."""
    from exalted_builder.models.character import HouseRules
    for origin in ("heroic", "ordinary"):
        c = Character(id="mcat", exalt_type="Mortal", caste="", origin=origin,
                      essence_rating=1)
        c.attributes = _all_one_attributes()
        offered = lambda: {b.name for b in validate.background_catalogue_for(rs, c)}
        assert not {"Artifact", "Manse"} & offered(), \
            f"{origin}: barred Backgrounds must not be offered without permission"
        c.house_rules = HouseRules(st_mortal_artifact_manse=True)
        assert {"Artifact", "Manse"} <= offered(), \
            f"{origin}: permission must reveal them in the catalogue"

    # The hiding is keyed to the character's OWN barred rules: no other splat loses a
    # Background to it.
    solar = Character(id="scat", exalt_type="Solar", caste="dawn", essence_rating=2)
    solar.attributes = _all_one_attributes()
    assert {"Artifact", "Manse"} <= {b.name for b in
                                     validate.background_catalogue_for(rs, solar)}
