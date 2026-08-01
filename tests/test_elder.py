"""Tests for engine.elder — the elder-Exalt ceilings of Player's Guide pp.258-259.

Age lets Essence pass 5; Essence lets Abilities and Attributes pass 5. Both are tested
through `advancement.raise_to`, the merged trait surface the UI actually calls, rather
than through the per-dot `raise_*` alone: this build's recurring bug is a rule that IS
implemented sitting where it does not run when it matters (CLAUDE.md), and the buy path
is what matters here.
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


def _locked(xp: int = 500, *, exalt_type: str = "solar", essence: int = 5,
            age: int = 0) -> Character:
    """A locked character at the top of the ordinary range — Essence 5, Melee 5 — which
    is where every elder rule starts to bite. Locked BEFORE the Essence is raised: a
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
    c.age = age
    return c


# --------------------------------------------------------------------------- #
# The p.259 chart
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("age,cap", [
    (0, 5), (1, 5), (99, 5),
    (100, 6), (249, 6),
    (250, 7), (499, 7),
    (500, 8), (999, 8),
    (1000, 9), (10_000, 9),          # "9+" ships as a flat 9 — see engine.elder
])
def test_essence_cap_for_age(age, cap):
    assert elder.essence_cap_for_age(age) == cap


def test_young_character_gets_the_ordinary_ceilings():
    """The regression guard: nothing about an ordinary sheet changes."""
    caps = elder.elder_caps(_ruleset(), _locked())
    assert (caps.essence, caps.trait) == (5, 5)
    assert not caps.is_elder


# --------------------------------------------------------------------------- #
# Age → Essence
# --------------------------------------------------------------------------- #

def test_essence_stops_at_5_before_a_century():
    rs, c = _ruleset(), _locked(age=99)
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "essence", 6)
    assert "100 years" in str(ex.value)
    assert c.essence_rating == 5


def test_a_century_of_exalted_existence_buys_essence_6():
    rs, c = _ruleset(), _locked(age=100)
    advancement.raise_to(rs, c, "essence", 6)
    assert c.essence_rating == 6


def test_essence_stops_at_the_age_bracket_not_at_9():
    """250 years permits 7 and no more, however much XP is banked."""
    rs, c = _ruleset(), _locked(age=250, essence=7)
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "essence", 8)
    assert "250 years" in str(ex.value)


# --------------------------------------------------------------------------- #
# Essence → Abilities and Attributes
# --------------------------------------------------------------------------- #

def test_abilities_and_attributes_follow_essence_past_5():
    rs, c = _ruleset(), _locked(age=500, essence=8)
    advancement.raise_to(rs, c, "abilities.melee", 6)
    advancement.raise_to(rs, c, "attributes.dexterity", 6)
    assert c.abilities[A.MELEE] == 6
    assert c.attributes[AT.DEXTERITY] == 6


def test_a_trait_may_not_pass_permanent_essence():
    """The ceiling is Essence itself, not the Essence age would have permitted."""
    rs, c = _ruleset(), _locked(age=1000, essence=6)
    advancement.raise_to(rs, c, "abilities.melee", 6)
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "abilities.melee", 7)
    assert "already at 6" in str(ex.value)


def test_low_essence_never_lowers_the_ordinary_5(monkeypatch):
    """The human's ruling, 2026-07-31: the Essence ceiling binds only ABOVE 5. Read
    literally it would cap an Essence 2 character's Melee at 2, which is nonsense."""
    rs, c = _ruleset(), _locked(essence=2)
    c.abilities[A.MELEE] = 4
    advancement.raise_to(rs, c, "abilities.melee", 5)
    assert c.abilities[A.MELEE] == 5
    assert elder.elder_caps(rs, c).trait == 5


def test_crafts_follow_essence():
    """p.258 names "Abilities and Attributes", and a per-focus Craft IS an Ability
    (core p.136). An Astrological College is not one, and stays at 5 — see
    advancement.raise_college."""
    rs, c = _ruleset(), _locked(age=500, essence=8)
    advancement.learn_craft(rs, c, "Smithing")
    for _ in range(5):
        advancement.raise_craft(rs, c, "Smithing")
    assert next(cr.rating for cr in c.crafts if cr.focus == "Smithing") == 6


def test_virtues_never_pass_5():
    """"Exalted cannot raise their Virtues above 5" — no elder exception."""
    rs, c = _ruleset(), _locked(age=1000, essence=9)
    c.virtues[V.VALOR] = 5
    with pytest.raises(advancement.AdvancementError):
        advancement.raise_to(rs, c, "virtues.valor", 6)


# --------------------------------------------------------------------------- #
# The Terrestrial clause
# --------------------------------------------------------------------------- #

def test_terrestrial_held_at_7_however_old():
    rs, c = _ruleset(), _locked(exalt_type="dragon-blooded", age=1000, essence=7)
    caps = elder.elder_caps(rs, c)
    assert caps.essence == 7 and caps.terrestrial_limited
    with pytest.raises(advancement.AdvancementError) as ex:
        advancement.raise_to(rs, c, "essence", 8)
    assert "outside energies" in str(ex.value)


def test_the_storyteller_can_lift_the_terrestrial_ceiling():
    rs, c = _ruleset(), _locked(exalt_type="dragon-blooded", age=1000, essence=7)
    c.house_rules = HouseRules(terrestrial_essence_transcendence=True)
    assert elder.elder_caps(rs, c).essence == 9
    advancement.raise_to(rs, c, "essence", 8)
    assert c.essence_rating == 8


def test_a_young_terrestrial_is_not_flagged_as_limited():
    """The flag means "held BELOW what age allowed", so it must stay off when age is
    the binding rule — otherwise the error names the wrong one."""
    caps = elder.elder_caps(_ruleset(), _locked(exalt_type="dragon-blooded", age=100))
    assert caps.essence == 6 and not caps.terrestrial_limited


def test_the_celestial_splats_are_untouched_by_the_terrestrial_clause():
    assert elder.elder_caps(_ruleset(), _locked(age=1000, essence=8)).essence == 9


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
    count every track was written against."""
    await user.open('/editor-elder')
    await user.should_see("Exalted years")
    await user.should_see("Abilities")
    await user.should_see("Experience")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_editor_builds_for_an_elder_terrestrial(user) -> None:
    await user.open('/editor-elder-terrestrial')
    await user.should_see("Exalted years")
    await user.should_see("Abilities")


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
