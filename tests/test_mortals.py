"""Mortal and Heroic Mortal chargen — the first non-Exalt splat, and the first that
is CASTELESS ("Mortals select Nature as normal but do not select a caste") and barred
from Charms outright ("Mortals cannot purchase Charms").

Heroic and ordinary mortals are ONE splat with two origins, not two splats: p.103
draws a single procedure through both and varies only the Attribute pools and the
Ability dots. Everything else on the page — 5 Backgrounds, no Charms, Essence 1,
21 bonus points — is shared.

Sources: Exalted core p.103 ("Down and Dirty, or Playing Humans", the whole chargen
procedure) and Player's Guide p.11-12 (heroic-mortal clarifications: no extra health
levels, no attunement) and p.115 (the mortal XP table). Magic access is deliberately
absent: it is gated on Merits, which are not implemented — see CLAUDE.md's Merits &
Flaws TODO for the rulings that work must carry.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import advancement, costs, derive, validate
from exalted_builder.models.character import Character, HouseRules
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import VirtueName as V
from exalted_builder.ui import theme, view

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _codes(issues, code):
    return [i for i in issues if i.code == code]


def _mortal(origin="heroic", **kw) -> Character:
    """A blank mortal: no caste, Essence pinned at 1."""
    c = Character(id="c.mortal", name="Nine Cups", exalt_type="Mortal", caste="",
                  origin=origin, essence_rating=1)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


# --- the two origins' distinctive numbers ---------------------------------- #
# adding-a-splat.md trap #2: a keyed-table row that does not exist falls back
# SILENTLY, so both rows are asserted on a number the other one does not share.

def test_heroic_and_ordinary_are_two_origins_of_one_splat(rs):
    heroic = rs.budgets_for("Mortal", "heroic", "")
    ordinary = rs.budgets_for("Mortal", "ordinary", "")
    # the only two things p.103 varies between them...
    assert heroic.attribute_pools == (6, 4, 3)
    assert ordinary.attribute_pools == (4, 3, 3)
    assert heroic.ability_dots == 22
    assert ordinary.ability_dots == 16
    # ...and everything the page shares. 21 bonus points is FLAT: the page says
    # "mortal characters get 21 bonus points" with no heroic/ordinary split.
    for b in (heroic, ordinary):
        assert b.bonus_points == 21
        assert b.background_dots == 5
        assert b.charm_count == 0
        assert b.essence_start == 1 and b.essence_start_cap == 1
        assert b.favored_count == 0          # "no Caste or Favored Abilities"

    # "heroic" has no row of its own and must resolve to the plain "Mortal" row;
    # if it ever gained one, this catches the divergence.
    assert rs.budgets_for("Mortal", "", "").attribute_pools == (6, 4, 3)


def test_a_blank_mortal_raises_no_errors_but_is_not_called_finished(rs):
    """No caste, no Charms and no Essence pool must not read as ERRORS — none of
    those is a defect for a mortal.

    But a blank sheet is not a legal character either. This test originally asserted
    the blank mortal was clean, which was how the missing unspent-dots check got
    through review: with no caste rules left to fail, a mortal made the engine's
    one-sided budget arithmetic visible."""
    issues = validate.validate_chargen(rs, _mortal())
    assert [i for i in issues if i.severity == "error"] == []
    assert _codes(issues, "unknown-caste") == []
    # every free pool is reported unspent, and none of it blocks
    unspent = {i.where for i in _codes(issues, "unspent-chargen-dots")}
    assert unspent == {"attribute", "ability", "virtue", "background"}
    assert all(i.severity == "warning" for i in _codes(issues, "unspent-chargen-dots"))


# --- casteless ------------------------------------------------------------- #

def test_mortals_are_casteless_by_design_not_misconfigured(rs):
    assert validate.splat_has_castes(rs, "Mortal") is False
    assert validate.splat_has_castes(rs, "Solar") is True
    # A Lunar HAS castes; they merely carry no Caste Abilities. The distinction is
    # what keeps the missing-caste check alive for them.
    assert validate.splat_has_castes(rs, "Lunar") is True
    # an Exalt with a genuinely bad caste is still reported
    bad = Character(id="c.bad", exalt_type="Solar", caste="not-a-caste")
    assert _codes(validate.validate_chargen(rs, bad), "unknown-caste")


def test_ability_roster_falls_back_to_the_players_guide_grouping(rs):
    """Nothing lays a mortal's Abilities out by caste, so the sheet and editor use
    the default grouping rather than rendering blank (adding-a-splat.md trap #5)."""
    assert [g[0] for g in view.ability_group_defs(rs, "Mortal")] == ["War", "Life", "Wisdom"]


# --- no Charms ------------------------------------------------------------- #

def test_mortals_cannot_hold_charms_at_all(rs):
    assert validate.charms_available(rs, _mortal()) is False
    assert validate.charms_available(rs, Character(id="s", exalt_type="Solar",
                                                   caste="dawn")) is True


def test_the_charm_bar_survives_open_to_all(rs):
    """`charm_count: 0` alone is NOT enough. Eight cross-splat Charms have
    min_essence 1 and would otherwise be buyable with bonus points by an Essence-1
    mortal, because open_to_all short-circuits the splat match."""
    reachable = [c for c in rs.charms.values() if c.open_to_all and c.min_essence <= 1]
    assert reachable, "fixture assumes some open_to_all Charm is reachable at Essence 1"
    c = _mortal(charms=[reachable[0].id])
    assert _codes(validate.validate(rs, c), "charms-not-available")
    # ...and it is NOT reported as a wrong-splat problem, which would misdescribe a
    # Charm that belongs to no one splat.
    assert _codes(validate.validate(rs, c), "charm-wrong-splat") == []


def test_xp_refuses_a_charm_to_a_mortal(rs):
    c = _mortal()
    c.chargen_locked = True
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError, match="cannot purchase Charms"):
        advancement.learn_charm(rs, c, "dragonblooded.air-dragon.air-dragons-sight")


# --- Essence --------------------------------------------------------------- #

def test_essence_is_pinned_at_one_through_chargen_and_xp(rs):
    """p.103: "All mortals have an Essence of 1. This Trait cannot be raised with
    bonus points." PG p.11 adds they have "no way to gain access to their Essence
    pool" — so XP is barred too, until the Essence Mastery Merit lands."""
    over = _mortal(essence_rating=2)
    assert _codes(validate.validate_chargen(rs, over), "essence-above-chargen-cap")

    c = _mortal()
    c.chargen_locked = True
    advancement.add_xp(c, 100)
    with pytest.raises(advancement.AdvancementError, match="cannot raise Essence"):
        advancement.raise_essence(rs, c)
    # an Exalt is untouched by the cap
    assert rs.exalt_for("Solar").essence_cap == 0


def test_a_mortal_has_no_essence_pool(rs):
    """"Mortal characters have an Essence of 1, but no way to gain access to their
    Essence pool" (PG p.11) — expressed as all-zero coefficients, not a code branch."""
    c = _mortal(willpower_purchased=1)
    c.virtues = {V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 3, V.VALOR: 3}
    assert derive.essence_pools(rs, c) == (0, 0)


def test_mortal_xp_table_overrides_the_solar_fallback(rs):
    """PG p.115. Two rows differ from the Solar baseline and would be SILENTLY wrong
    if the splat had no row of its own (adding-a-splat.md trap #7)."""
    m, s = _mortal(), Character(id="s", exalt_type="Solar", caste="dawn")
    # Virtues cost current x4 for a mortal, x3 for a Solar.
    assert rs.xp_costs_for("Mortal").virtue.coeff == 4
    assert rs.xp_costs_for("Solar").virtue.coeff == 3
    # Essence is priced flat by destination, not by a coefficient: 20 then 40.
    assert costs.essence_step(rs, m, 1) == 20
    assert costs.essence_step(rs, m, 2) == 40
    assert costs.essence_step(rs, s, 2) == 16          # Solar stays linear (x8)
    # The shared rows really are shared, so the table is not over-authored.
    assert rs.xp_costs_for("Mortal").attribute.coeff == 4
    assert rs.xp_costs_for("Mortal").ability.coeff == 2


# --- health, Virtue Flaw, Ox-Body ------------------------------------------ #

def test_seven_health_levels_and_no_ox_body(rs):
    """PG p.11: heroic mortals "cannot normally gain extra health levels, but they
    have the full normal mortal complement" — the same 7 levels, with no repeatable
    Charm to extend them (and no Charms at all to reach one with)."""
    assert rs.exalt_for("Mortal").ox_body_charm_id == ""
    assert len(derive.health_track(_mortal())) == 7


def test_mortals_have_no_virtue_flaw(rs):
    assert rs.exalt_for("Mortal").has_virtue_flaw is False
    assert derive.has_virtue_flaw(rs, _mortal()) is False


# --- the optional Favored Ability (core p.103, ST toggle) ------------------- #

def test_favored_ability_is_off_by_default(rs):
    assert validate.favored_ability_count(rs, _mortal()) == 0
    assert _codes(validate.validate_chargen(rs, _mortal()), "favored-count") == []


def test_favored_ability_toggle_grants_exactly_one(rs):
    c = _mortal(house_rules=HouseRules(mortal_favored_ability=True))
    assert validate.favored_ability_count(rs, c) == 1
    # ...and is then required, so the ST's grant cannot be silently ignored.
    assert _codes(validate.validate_chargen(rs, c), "favored-count")
    c.favored_abilities = [A.MELEE]
    c.abilities = {A.MELEE: 3}
    assert _codes(validate.validate_chargen(rs, c), "favored-count") == []


def test_favored_ability_must_be_the_highest_rated(rs):
    """The price of the discount: "the character can never have any other Ability
    rated higher than his Favored Ability" (p.103)."""
    c = _mortal(house_rules=HouseRules(mortal_favored_ability=True),
                favored_abilities=[A.MELEE],
                abilities={A.MELEE: 2, A.ARCHERY: 4, A.DODGE: 1})
    bad = _codes(validate.validate_chargen(rs, c), "mortal-favored-not-highest")
    assert [i.where for i in bad] == ["archery"]
    # equal is explicitly fine — "equal to or greater than every other skill"
    c.abilities = {A.MELEE: 4, A.ARCHERY: 4, A.DODGE: 1}
    assert _codes(validate.validate_chargen(rs, c), "mortal-favored-not-highest") == []


def test_the_toggle_cannot_leak_onto_a_splat_with_castes(rs):
    """A stray flag on an Exalt must not demand a sixth Favoured Ability."""
    s = Character(id="s", exalt_type="Solar", caste="dawn",
                  house_rules=HouseRules(mortal_favored_ability=True))
    assert validate.favored_ability_count(rs, s) == 5
    assert validate.mortal_favored_ability_issues(rs, s) == []


def test_the_toggle_is_listed_in_st_options_with_a_scope_note(rs):
    rows = {r.field: r for r in view.build_house_rules(rs, _mortal())}
    row = rows["mortal_favored_ability"]
    assert row.scope == "character" and "p.103" in row.citation
    # ...and on an Exalt it is shown but annotated inert rather than hidden
    s = Character(id="s", exalt_type="Solar", caste="dawn")
    solar_row = {r.field: r for r in view.build_house_rules(rs, s)}["mortal_favored_ability"]
    assert "No effect" in solar_row.note


# --- theme ----------------------------------------------------------------- #

def test_mortal_theme_is_muddy_brown(rs):
    assert theme.palette("Mortal").fam == "stone"
    assert theme.palette("Mortal").accent != theme.palette("Solar").accent


# --- UI render (NiceGUI User harness) --------------------------------------- #
# adding-a-splat.md trap #3: `ui.select` 500s at render when its initial value is
# not among its options, and a unit test will never catch it. A casteless splat is
# exactly the shape that trips it — caste="" against an empty option list.

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_mortal_editor_renders_without_a_caste_control(user) -> None:
    from nicegui.elements.select import Select
    await user.open('/mortal')
    await user.should_see("Identity")
    labels = {e._props.get('label')
              for e in user.client.elements.values() if isinstance(e, Select)}
    assert "Caste" not in labels          # no caste control for a casteless splat
    assert "Exalt type" in labels and "Origin" in labels
    await user.should_see("Not one of the Chosen")   # the box that replaces it


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_mortal_sheet_renders(user) -> None:
    await user.open('/mortal-sheet')
    await user.should_see("Nine Cups")
    await user.should_see("War")          # default Ability grouping, not blank


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_mortal_picker_offers_no_charm_pages_and_still_renders(user) -> None:
    """Regression, reported 2026-07-30: a mortal has no Charm categories, so the
    Category dropdown was built with an empty option list and raised at build time —
    blanking the Abilities page AND the Thaumaturgy sub-tabs beside it."""
    await user.open('/mortalpicker')
    # It lands on the Thaumaturgy page, whose content really renders. (The page
    # TOGGLE is hidden: with no Charm pages, Thaumaturgy is the only group left, so
    # asserting on its label would test the toggle, not the page.)
    await user.should_see("Divination")
    await user.should_see("Live Validation")
    # ...and no Charm-tree page is on offer.
    await user.should_not_see("Martial Arts")
    await user.should_not_see("Category")


def test_optional_favored_ability_is_heroic_only(rs):
    """Reported 2026-07-30: the ST toggle was letting an ORDINARY mortal take one.
    Core p.103 offers it to "heroic mortals"; it varies by origin, so it is a budget
    flag and both halves (origin allows + ST switches on) must hold."""
    assert rs.budgets_for("Mortal", "heroic", "").optional_favored_ability is True
    assert rs.budgets_for("Mortal", "ordinary", "").optional_favored_ability is False
    on = HouseRules(mortal_favored_ability=True)
    heroic = _mortal("heroic", house_rules=on)
    ordinary = _mortal("ordinary", house_rules=on)
    assert validate.optional_favored_ability_open(rs, heroic) is True
    assert validate.optional_favored_ability_open(rs, ordinary) is False
    assert validate.favored_ability_count(rs, heroic) == 1
    assert validate.favored_ability_count(rs, ordinary) == 0
    # ...and the ceiling constraint follows the same gate
    ordinary.favored_abilities = [A.MELEE]
    ordinary.abilities = {A.MELEE: 1, A.ARCHERY: 4}
    assert validate.mortal_favored_ability_issues(rs, ordinary) == []


def test_st_options_says_why_the_toggle_is_inert_for_an_ordinary_mortal(rs):
    rows = {r.field: r for r in view.build_house_rules(rs, _mortal("ordinary"))}
    assert "HEROIC mortals only" in rows["mortal_favored_ability"].note
