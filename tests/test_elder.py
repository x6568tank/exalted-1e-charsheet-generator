"""Tests for engine.elder — Essence and trait ceilings, and the p.259 downtime
calculator (Player's Guide pp.258-259).

Human ruling 2026-08-06: Essence is XP-purchasable to the splat's ceiling (9 for an
Exalt, the Terrestrial-7 held), and Essence in turn lets Abilities and Attributes pass
5. Both are tested through `advancement.raise_to`, the merged trait surface the UI
actually calls, rather than through the per-dot `raise_*` alone: this build's
recurring bug is a rule that IS implemented sitting where it does not run when it
matters (CLAUDE.md), and the buy path is what matters here.
"""

import pytest

from exalted_builder.engine import advancement, elder, lifecycle, validate
from exalted_builder.models.character import Character, HouseRules
from exalted_builder.models.rules import (
    AbilityName,
    AttributeName,
    CasteDefinition,
    EssencePoolSpec,
    ExaltDefinition,
    RuleSet,
    VirtueName,
)

A, AT, V = AbilityName, AttributeName, VirtueName


def _ruleset() -> RuleSet:
    return RuleSet(
        exalts={
            "solar": ExaltDefinition(id="solar", label="Solar",
                                     essence=EssencePoolSpec(personal_essence_coeff=3, peripheral_essence_coeff=7)),
            "dragon-blooded": ExaltDefinition(id="dragon-blooded", label="Dragon-Blooded",
                                              tier="Terrestrial",
                                              essence=EssencePoolSpec(personal_essence_coeff=3, peripheral_essence_coeff=7)),
        },
        charms={},
        castes={"dawn": CasteDefinition(
            id="dawn", label="Dawn", exalt_type="solar",
            caste_abilities=[A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN])},
    )


def _locked(xp: int = 500, *, exalt_type: str = "solar", essence: int = 5) -> Character:
    """A locked character at the top of the ordinary range — Essence 5, Melee 5 — which
    is where every ceiling starts to bite. Locked BEFORE the Essence is raised: a
    character may not leave creation above 5, and the tests must not smuggle one out."""
    c = Character(id="char.elder", exalt_type=exalt_type, caste="dawn")
    c.attributes[AT.DEXTERITY] = 5
    c.abilities[A.MELEE] = 5
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    lifecycle.lock_chargen(c)
    c.xp_earned = xp
    # Post-lock state, set directly: the point of these tests is the ceiling, not the
    # ledger that got the character here.
    c.essence_rating = essence
    return c


# --------------------------------------------------------------------------- #
# The ceilings
# --------------------------------------------------------------------------- #

def test_young_character_gets_the_ordinary_ceilings():
    """The regression guard: nothing about an ordinary sheet changes — the trait
    ceiling is 5 at Essence 5, and a Solar's Essence ceiling is the flat 9."""
    c = _locked()
    assert elder.trait_ceiling(c) == 5
    assert elder.essence_cap(_ruleset(), c) == (9, False)


# --------------------------------------------------------------------------- #
# Essence → Abilities and Attributes
# --------------------------------------------------------------------------- #

def test_essence_is_purchasable_past_5_with_xp():
    """p.175 for the Dragon-Kings, and the general ruling for everyone: past 5 the only
    gate on Essence is the splat's ceiling — no age chart."""
    rs, c = _ruleset(), _locked(essence=5)
    advancement.raise_to(rs, c, "essence", 6)
    assert c.essence_rating == 6


def test_essence_stops_at_the_splat_cap():
    """A Solar's ceiling is 9, the p.258 chart's printed max taken flat — however much
    XP is banked."""
    rs, c = _ruleset(), _locked(essence=9)
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "essence", 10)
    assert "above 9" in str(ex.value)


def test_abilities_and_attributes_follow_essence_past_5():
    rs, c = _ruleset(), _locked(essence=8)
    advancement.raise_to(rs, c, "abilities.melee", 6)
    advancement.raise_to(rs, c, "attributes.dexterity", 6)
    assert c.abilities[A.MELEE] == 6
    assert c.attributes[AT.DEXTERITY] == 6


def test_a_trait_may_not_pass_permanent_essence():
    """The ceiling is Essence itself."""
    rs, c = _ruleset(), _locked(essence=6)
    advancement.raise_to(rs, c, "abilities.melee", 6)
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "abilities.melee", 7)
    assert "already at 6" in str(ex.value)


def test_low_essence_never_lowers_the_ordinary_5():
    """The human's ruling, 2026-07-31: the Essence ceiling binds only ABOVE 5. Read
    literally it would cap an Essence 2 character's Melee at 2, which is nonsense."""
    rs, c = _ruleset(), _locked(essence=2)
    c.abilities[A.MELEE] = 4
    advancement.raise_to(rs, c, "abilities.melee", 5)
    assert c.abilities[A.MELEE] == 5
    assert elder.trait_ceiling(c) == 5


def test_crafts_follow_essence():
    """p.258 names "Abilities and Attributes", and a per-focus Craft IS an Ability
    (core p.136). An Astrological College is not one, and stays at 5 — see
    advancement.raise_college."""
    rs, c = _ruleset(), _locked(essence=8)
    advancement.learn_craft(rs, c, "Smithing")
    for _ in range(5):
        advancement.raise_craft(rs, c, "Smithing")
    assert next(cr.rating for cr in c.crafts if cr.focus == "Smithing") == 6


def test_virtues_never_pass_5():
    """"Exalted cannot raise their Virtues above 5" — no exception."""
    rs, c = _ruleset(), _locked(essence=9)
    c.virtues[V.VALOR] = 5
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_to(rs, c, "virtues.valor", 6)


# --------------------------------------------------------------------------- #
# The Terrestrial clause
# --------------------------------------------------------------------------- #

def test_terrestrial_held_at_7():
    """p.258: "Terrestrial Exalts may never raise their permanent Essence above 7
    without outside energies". The hold is the splat's ceiling, and the flag names it
    as the rule that stopped the raise."""
    rs, c = _ruleset(), _locked(exalt_type="dragon-blooded", essence=7)
    assert elder.essence_cap(rs, c) == (7, True)
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "essence", 8)
    assert "outside energies" in str(ex.value)


def test_the_storyteller_can_lift_the_terrestrial_ceiling():
    rs, c = _ruleset(), _locked(exalt_type="dragon-blooded", essence=7)
    c.house_rules = HouseRules(terrestrial_essence_transcendence=True)
    assert elder.essence_cap(rs, c) == (9, False)
    advancement.raise_to(rs, c, "essence", 8)
    assert c.essence_rating == 8


def test_the_celestial_splats_are_untouched_by_the_terrestrial_clause():
    rs, c = _ruleset(), _locked(essence=8)
    assert elder.essence_cap(rs, c) == (9, False)


# --------------------------------------------------------------------------- #
# Chargen cannot reach any of it
# --------------------------------------------------------------------------- #

def test_essence_above_5_is_a_chargen_error():
    rs = _ruleset()
    c = Character(id="char.young", exalt_type="solar", caste="dawn")
    c.essence_rating = 6
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "essence-above-elder-chargen-cap" in codes


def test_essence_5_is_legal_at_chargen():
    rs = _ruleset()
    c = Character(id="char.young", exalt_type="solar", caste="dawn")
    c.essence_rating = 5
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "essence-above-elder-chargen-cap" not in codes


# --------------------------------------------------------------------------- #
# Render matrix — the dot tracks are BUILT from these ceilings (preflight pass 3)
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_an_elder(user) -> None:
    """Essence 8, Melee 7: the first ratings in the build that legally exceed the pip
    count every track was written against.

    Age is not a character trait at all — the "Exalted years" box lives inside the
    Downtime dialog as the p.259 calculator's input, and nothing on the editor page
    itself mentions it.
    """
    await user.open('/editor-elder')
    await user.should_see("Abilities")
    await user.should_see("Experience")
    await user.should_not_see("Exalted years")
    user.find("Downtime…").click()
    await user.should_see("Exalted years so far")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_an_elder_terrestrial(user) -> None:
    """A Terrestrial at the 7-hold renders; the hold is now purely an Essence ceiling,
    so the editor builds and the Essence track tops out at 7."""
    await user.open('/editor-elder-terrestrial')
    await user.should_see("Abilities")
    await user.should_see("Essence")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_sheet_builds_for_an_elder(user) -> None:
    await user.open('/sheet-elder')
    await user.should_see("Elder Solar")


def test_essence_rebuilds_the_whole_editor_body():
    """A dot click normally redraws its own row. Essence must redraw everything: past 5
    it is the ceiling on every Ability and Attribute track, so those rows' pip counts
    are stale the moment it moves. Found in the browser (human, 2026-07-31) — Essence
    went to 6 but the Ability tracks kept five pips until the tab was left and re-entered.
    """
    from exalted_builder.ui import editor

    assert "essence" in editor.BODY_REBUILD_TARGETS


# --------------------------------------------------------------------------- #
# The p.259 downtime awards (2026-08-01)
# --------------------------------------------------------------------------- #
# A CALCULATOR, not an enforcement. These pin the arithmetic and the two rulings the
# page does not settle: how a downtime crossing an age band is rated, and what the
# split does with a lump sum that is not a multiple of ten.

def test_the_annual_award_chart_matches_the_page() -> None:
    """p.259's third column, and its floor: the chart starts at 100 years."""
    assert elder.annual_xp_for_age(99) == 0
    assert elder.annual_xp_for_age(100) == 5
    assert elder.annual_xp_for_age(249) == 5
    assert elder.annual_xp_for_age(250) == 4
    assert elder.annual_xp_for_age(500) == 3
    assert elder.annual_xp_for_age(1000) == 2
    assert elder.annual_xp_for_age(5000) == 2


def test_a_downtime_inside_one_band_is_years_times_rate() -> None:
    award = elder.downtime_award(100, 20)
    assert award.total == 100
    assert award.to_age == 120
    assert len(award.bands) == 1


def test_a_downtime_crossing_a_band_is_rated_year_by_year() -> None:
    """The human's ruling, 2026-08-01: walk the years, do not flatten to either end.
    Age 90 + 40 years = 9 unpaid years to 99, then 31 paid at 5. A flat rate at the
    final age would have paid 200, at the starting age 0."""
    award = elder.downtime_award(90, 40)
    assert award.total == 155
    assert [(b.rate, b.years) for b in award.bands] == [(0, 9), (5, 31)]


def test_consecutive_years_at_one_rate_coalesce_into_a_single_band() -> None:
    """A 400-year downtime must not print 400 rows to say it crossed two bands."""
    award = elder.downtime_award(200, 400)
    assert [b.rate for b in award.bands] == [5, 4, 3]
    assert sum(b.years for b in award.bands) == 400


def test_a_downtime_below_the_chart_awards_nothing() -> None:
    """Not a bug: the page prints no row under 100 years and this build never invents
    one. The UI says so rather than showing a bare zero."""
    assert elder.downtime_award(10, 50).total == 0


def test_the_split_follows_the_pages_four_three_two_one() -> None:
    parts = dict(elder.split_downtime_experience(200))
    assert parts["Charms and Combos"] == 80
    assert parts["Abilities"] == 60
    assert parts["Attributes and Virtues"] == 40
    assert parts["Essence"] == 20


def test_the_split_never_loses_experience_to_rounding() -> None:
    """The page's shortcut only divides cleanly on a multiple of ten. Ours floors and
    gives the remainder to the largest category, so the parts always sum back."""
    for total in range(0, 400):
        assert sum(v for _, v in elder.split_downtime_experience(total)) == total


def test_a_zero_year_downtime_is_inert() -> None:
    award = elder.downtime_award(500, 0)
    assert award.total == 0
    assert award.bands == ()
    assert award.to_age == 500


def _set_calculator_age(user, value: int) -> None:
    """Type a start-age into the Downtime calculator's 'Exalted years so far' field —
    a calculator-local input, not a character trait, so the tests drive it through the
    widget rather than presetting a character."""
    from nicegui import ui

    num = next(e for e in user.client.elements.values()
               if isinstance(e, ui.number)
               and (e.props.get("label") or "") == "Exalted years so far")
    num.set_value(value)


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_downtime_calculator_shows_its_working(user) -> None:
    """The control the human asked for: a calculator in the XP column that prints the
    lump sum, the per-band working and the 4:3:2:1 split. Age 240 with the default 10
    years crosses the 250-year boundary, so two bands at different rates must show."""
    await user.open('/editor-downtime-view')
    await user.should_see("Downtime…")
    user.find("Downtime…").click()
    _set_calculator_age(user, 240)
    await user.should_see("Age 240 → 250")
    await user.should_see("× 5 =")
    await user.should_see("× 4 =")
    await user.should_see("Charms and Combos")
    await user.should_see("Attributes and Virtues")
    await user.should_see("nothing here enforces it")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_granting_a_downtime_awards_xp_and_advances_the_calculator_age(user) -> None:
    """The grant half. Age 90 + the default 10 years = one paid year, the one that
    reaches 100. The grant advances the calculator's LOCAL age (a pure input, not a
    character trait), so a later grant is priced from where the last one ended.

    Asserted THROUGH THE UI, not by reaching into `_ui_main` for the character: under
    the main-file fixture that module is not always the same object the route was built
    from, so a direct read passes alone and fails in the suite.
    """
    await user.open('/editor-downtime')
    user.find("Downtime…").click()
    _set_calculator_age(user, 90)
    await user.should_see("Age 90 → 100")
    user.find("Grant").click()
    await user.should_see("Granted 5 XP")
    await user.should_see("age is now 100")
    # The award landed in the column, not only in the notification.
    await user.should_see("XP available")
    # Reopening reads the calculator back: the local age it now starts from is the one
    # the grant wrote.
    user.find("Downtime…").click()
    await user.should_see("Age 100 → 110")
