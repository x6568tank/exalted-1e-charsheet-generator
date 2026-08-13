"""Tests for engine.pools — BASE dice pools (decision 0016).

The boundary this file exists to defend: the engine computes an itemised,
labelled BASE pool and nothing else. No rolling (0009), no resolution, no damage
or soak interaction, and NO Charm dice — Charms need activation state, which is
play-state (0006). Several tests here assert those absences directly, because the
risk 0016 names is a number that *looks* authoritative.
"""

import pathlib

import pytest

from exalted_builder import rules_db
from exalted_builder.engine import pools
from exalted_builder.models.character import (
    Armor, Character, Damage, PlayState, Specialty, Weapon)
from exalted_builder.models.rules import (
    AbilityName, AttributeName, PoolKind, RollDefinition, RuleSet, VirtueName,
    WeaponStat)

_RS = RuleSet(castes={}, charms={})

_DATA = pathlib.Path(__file__).resolve().parents[1] / "exalted_builder" / "data"


@pytest.fixture(scope="module")
def app_ruleset():
    return rules_db.load_app_ruleset(_DATA)


_ATTACK = RollDefinition(
    id="attack-melee", name="Attack — Melee", attribute=AttributeName.DEXTERITY,
    ability=AbilityName.MELEE, weapon_stat=WeaponStat.ACCURACY)
_PARRY = RollDefinition(
    id="parry-melee", name="Parry — Melee", attribute=AttributeName.DEXTERITY,
    ability=AbilityName.MELEE, weapon_stat=WeaponStat.DEFENSE)
_DODGE = RollDefinition(
    id="dodge", name="Dodge", attribute=AttributeName.DEXTERITY,
    ability=AbilityName.DODGE, mobility_applies=True)
_VIRTUE = RollDefinition(id="virtue-check", name="Virtue check", kind=PoolKind.VIRTUE)
_WILL = RollDefinition(id="willpower-check", name="Willpower check",
                       kind=PoolKind.WILLPOWER)


def _char(**kw) -> Character:
    c = Character(id="char.pools")
    c.attributes[AttributeName.DEXTERITY] = 4
    c.abilities[AbilityName.MELEE] = 3
    c.abilities[AbilityName.DODGE] = 2
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _labels(bd) -> list[str]:
    return [ln.label for ln in bd.lines]


# --------------------------------------------------------------------------- #
# The base arithmetic
# --------------------------------------------------------------------------- #

def test_attribute_plus_ability_is_the_base_pool():
    bd = pools.base_pool(_RS, _char(), _ATTACK)
    assert bd.total == 7                                    # Dex 4 + Melee 3
    assert [(ln.label, ln.value) for ln in bd.lines] == [
        ("Dexterity", 4), ("Melee", 3)]


def test_every_contribution_is_a_labelled_line_not_a_bare_number():
    """0016's mitigation for 0008's 'looks authoritative' objection is
    presentational and load-bearing: the output is an itemised breakdown."""
    bd = pools.base_pool(_RS, _char(), _ATTACK)
    assert bd.total == sum(ln.value for ln in bd.lines)
    assert all(ln.label for ln in bd.lines)


def test_a_virtue_check_is_the_virtue_rating_alone():
    c = _char()
    c.virtues[VirtueName.VALOR] = 3
    bd = pools.base_pool(_RS, c, _VIRTUE, virtue=VirtueName.VALOR)
    assert bd.total == 3
    assert _labels(bd) == ["Valor"]


def test_a_virtue_check_without_a_named_virtue_is_an_error():
    with pytest.raises(ValueError):
        pools.base_pool(_RS, _char(), _VIRTUE)


def test_a_willpower_check_uses_permanent_willpower_not_the_temporary_track():
    """p.88: 'Dice actions using Willpower are based on the character's permanent
    score (the dots), not the current rating (the squares).'"""
    c = _char()
    c.virtues = {VirtueName.COMPASSION: 3, VirtueName.CONVICTION: 2,
                 VirtueName.TEMPERANCE: 4, VirtueName.VALOR: 1}
    c.play = PlayState(willpower_spent=5)
    bd = pools.base_pool(_RS, c, _WILL)
    assert bd.total == 7                                    # 4 + 3, spend ignored
    assert _labels(bd) == ["Willpower (permanent)"]


# --------------------------------------------------------------------------- #
# Specialties (core p.134: an extra die per instance, max three per Ability)
# --------------------------------------------------------------------------- #

def test_a_specialty_adds_one_die_per_instance():
    """p.134: 'Characters may take the same specialty more than once to increase the
    bonus they gain.' Two instances of Swords is +2 dice.

    ⚠ The instances must be SUMMED BY NAME. The loader splits a legacy `rating: 2`
    into two rows of 1 (the 2026-07-31 instance ruling), so offering the raw
    Specialty rows gives the player two identical entries worth one die each and
    quietly under-counts the pool — which is exactly what the first cut did.
    """
    c = _char(specialties=[Specialty(ability=AbilityName.MELEE, name="Swords", rating=1),
                           Specialty(ability=AbilityName.MELEE, name="Swords", rating=1)])
    options = pools.specialties_for(c, _ATTACK)
    assert [(o.name, o.dice) for o in options] == [("Swords", 2)]
    bd = pools.base_pool(_RS, c, _ATTACK, specialty=options[0])
    assert bd.total == 9                                    # 4 + 3 + 2
    assert ("Swords (specialty)", 2) in [(ln.label, ln.value) for ln in bd.lines]


def test_a_stored_rating_is_still_worth_its_full_dice():
    """A save that predates the instance split carries one row with rating 2."""
    c = _char(specialties=[Specialty(ability=AbilityName.MELEE, name="Swords", rating=2)])
    assert [(o.name, o.dice) for o in pools.specialties_for(c, _ATTACK)] == [("Swords", 2)]


def test_two_DIFFERENT_specialties_stay_separate_options():
    """Only same-name instances merge — a player picks one facet per roll."""
    c = _char(specialties=[Specialty(ability=AbilityName.MELEE, name="Swords", rating=1),
                           Specialty(ability=AbilityName.MELEE, name="Axes", rating=1)])
    assert sorted(o.name for o in pools.specialties_for(c, _ATTACK)) == ["Axes", "Swords"]


def test_a_specialty_for_another_ability_is_refused():
    c = _char(specialties=[Specialty(ability=AbilityName.DODGE, name="Arrows", rating=1)])
    wrong = pools.specialties_for(c, _DODGE)[0]
    with pytest.raises(ValueError):
        pools.base_pool(_RS, c, _ATTACK, specialty=wrong)


def test_specialties_for_this_roll_lists_only_matching_abilities():
    c = _char(specialties=[
        Specialty(ability=AbilityName.MELEE, name="Swords", rating=1),
        Specialty(ability=AbilityName.DODGE, name="Arrows", rating=1)])
    assert [s.name for s in pools.specialties_for(c, _ATTACK)] == ["Swords"]
    assert pools.specialties_for(c, _VIRTUE) == []


# --------------------------------------------------------------------------- #
# Weapons (core p.327: accuracy on attacks, defense on parries)
# --------------------------------------------------------------------------- #

def test_weapon_accuracy_joins_an_attack_pool():
    w = Weapon(name="Short sword", accuracy=2, defense=3)
    bd = pools.base_pool(_RS, _char(), _ATTACK, weapon=w)
    assert bd.total == 9                                    # 4 + 3 + 2 accuracy
    assert ("Short sword (accuracy)", 2) in [(ln.label, ln.value) for ln in bd.lines]


def test_weapon_defense_joins_a_parry_pool_and_accuracy_does_not():
    w = Weapon(name="Short sword", accuracy=2, defense=3)
    bd = pools.base_pool(_RS, _char(), _PARRY, weapon=w)
    assert bd.total == 10                                   # 4 + 3 + 3 defense
    assert "Short sword (accuracy)" not in _labels(bd)


def test_a_weapon_is_ignored_by_a_roll_that_names_no_weapon_stat():
    bd = pools.base_pool(_RS, _char(), _DODGE, weapon=Weapon(name="Sword", accuracy=9))
    assert bd.total == 6                                    # 4 + 2, no accuracy
    assert not any("accuracy" in ln.label for ln in bd.lines)


def test_a_missing_weapon_minimum_subtracts_one_per_dot_short():
    """p.327: 'For each dot the character is missing from any minimum, she
    subtracts 1 from the speed, attack and defense of the weapon.'"""
    c = _char()                                             # Strength defaults to 1
    w = Weapon(name="Grand daiklave", accuracy=3, min_strength=4)
    bd = pools.base_pool(_RS, c, _ATTACK, weapon=w)
    assert ("Grand daiklave (minimums not met)", -3) in [
        (ln.label, ln.value) for ln in bd.lines]
    assert bd.total == 7                                    # 4 + 3 + 3 - 3


def test_weapon_minimum_shortfalls_are_summed_across_the_minima():
    c = _char()                                             # Str 1, Dex 4, MA 0
    w = Weapon(name="Exotic", accuracy=0, min_strength=3, min_dexterity=5,
               min_martial_arts=2)
    bd = pools.base_pool(_RS, c, _ATTACK, weapon=w)
    short = next(ln for ln in bd.lines if "minimums" in ln.label)
    assert short.value == -(2 + 1 + 2)


def test_a_magical_material_bonus_reaches_the_pool_for_a_matching_exalt():
    """derive.effective_weapon is Exalt-gated (p.341); the pool must see the
    material-adjusted accuracy, not the raw stat."""
    from exalted_builder.models.rules import MagicalMaterial
    rs = RuleSet(castes={}, charms={}, material_catalog={
        "orichalcum": MagicalMaterial(id="orichalcum", name="Orichalcum",
                                      exalt_type="Solar", weapon_accuracy=1)})
    w = Weapon(name="Daiklave", accuracy=2, material="orichalcum")
    solar = pools.base_pool(rs, _char(exalt_type="Solar"), _ATTACK, weapon=w)
    lunar = pools.base_pool(rs, _char(exalt_type="Lunar"), _ATTACK, weapon=w)
    assert solar.total == 10                                # 4 + 3 + (2 + 1)
    assert lunar.total == 9                                 # no resonance, no bonus


# --------------------------------------------------------------------------- #
# Armour mobility (core p.332) — a PER-ROLL fact, not a blanket subtraction
# --------------------------------------------------------------------------- #

def test_mobility_penalty_applies_to_dodge():
    """⚠ The catalogue stores this field ALREADY SIGNED and negative (a buff jacket
    is -1), so it is written that way here too — see the sign test below."""
    c = _char(armor=[Armor(name="Chain shirt", mobility_penalty=-2)])
    bd = pools.base_pool(_RS, c, _DODGE)
    assert ("Chain shirt (mobility)", -2) in [(ln.label, ln.value) for ln in bd.lines]
    assert bd.total == 4                                    # 4 + 2 - 2


def test_mobility_penalty_does_not_apply_to_attack_or_parry():
    c = _char(armor=[Armor(name="Chain shirt", mobility_penalty=-2)])
    for roll in (_ATTACK, _PARRY):
        bd = pools.base_pool(_RS, c, roll)
        assert not any("mobility" in ln.label for ln in bd.lines)
        assert bd.total == 7


def test_mobility_is_summed_across_worn_pieces():
    c = _char(armor=[Armor(name="Chain shirt", mobility_penalty=-2),
                     Armor(name="Target shield", mobility_penalty=-3)])
    bd = pools.base_pool(_RS, c, _DODGE)
    assert bd.total == 1                                    # 4 + 2 - 5


def test_moonsilver_negates_the_mobility_penalty_for_a_lunar():
    from exalted_builder.models.rules import MagicalMaterial
    rs = RuleSet(castes={}, charms={}, material_catalog={
        "moonsilver": MagicalMaterial(id="moonsilver", name="Moonsilver",
                                      exalt_type="Lunar",
                                      armor_negate_mobility_penalty=True)})
    armor = [Armor(name="Articulated plate", mobility_penalty=-4, material="moonsilver")]
    lunar = pools.base_pool(rs, _char(exalt_type="Lunar", armor=armor), _DODGE)
    solar = pools.base_pool(rs, _char(exalt_type="Solar", armor=armor), _DODGE)
    assert lunar.total == 6
    assert solar.total == 2


def test_the_mobility_line_can_be_turned_off():
    """0016: the penalties 'render as separate, labelled, toggleable lines'."""
    c = _char(armor=[Armor(name="Chain shirt", mobility_penalty=-2)])
    bd = pools.base_pool(_RS, c, _DODGE, include_mobility=False)
    assert not any("mobility" in ln.label for ln in bd.lines)
    assert bd.total == 6


# --------------------------------------------------------------------------- #
# Wound penalties — play-state, and isolated (decision 0006)
# --------------------------------------------------------------------------- #

def test_wound_penalty_is_the_deepest_marked_box():
    c = _char()
    c.play = PlayState(health=[Damage.BASHING, Damage.LETHAL])   # -0 then -1
    assert pools.wound_penalty(_RS, c) == (-1, "-1")


def test_an_undamaged_character_has_no_wound_penalty():
    assert pools.wound_penalty(_RS, _char()) == (0, "")


def test_a_character_who_never_played_has_no_wound_penalty():
    c = _char()
    assert c.play is None
    assert pools.wound_penalty(_RS, c) == (0, "")
    assert c.play is None                # reading must not create play-state


def test_incapacitated_reports_itself_rather_than_a_penalty():
    """The Incapacitated level carries no dice penalty (its `penalty` is None) —
    a character there is not taking dice actions at all."""
    c = _char()
    c.play = PlayState(health=[Damage.LETHAL] * 8)
    penalty, label = pools.wound_penalty(_RS, c)
    assert label == "Incapacitated"


def test_the_wound_line_is_labelled_and_can_be_turned_off():
    c = _char()
    c.play = PlayState(health=[Damage.BASHING] * 4)          # into the -2 band
    on = pools.base_pool(_RS, c, _ATTACK, wound_penalty=-2)
    off = pools.base_pool(_RS, c, _ATTACK, wound_penalty=0)
    assert ("Wound penalty", -2) in [(ln.label, ln.value) for ln in on.lines]
    assert on.total == 5 and off.total == 7


def test_play_state_never_enters_the_pool_by_itself():
    """Decision 0006 — the caller passes the wound penalty in explicitly. If
    base_pool read Character.play on its own, play-state would have leaked into an
    engine derivation through the back door."""
    c = _char()
    c.play = PlayState(health=[Damage.LETHAL] * 4)
    assert pools.base_pool(_RS, c, _ATTACK).total == 7


# --------------------------------------------------------------------------- #
# What the number is NOT — the whole point of 0016
# --------------------------------------------------------------------------- #

def test_the_breakdown_states_what_it_excludes():
    bd = pools.base_pool(_RS, _char(), _ATTACK)
    text = " ".join(bd.excludes).lower()
    for missing in ("charm", "stunt", "difficulty"):
        assert missing in text


def test_charm_dice_are_never_added():
    """No Charm effect is modelled for this feature (0016). A character holding
    Charms gets exactly the same pool as one holding none."""
    bare = pools.base_pool(_RS, _char(), _ATTACK)
    charmed = pools.base_pool(_RS, _char(charms=["charm.solar.melee.example"]), _ATTACK)
    assert charmed.total == bare.total


def test_no_module_in_the_chargen_or_xp_path_imports_pools():
    """Play-state isolation, mechanically. `pools` is the only engine module that
    knows what a wound penalty is; if validate or advancement ever imports it, the
    isolation that decision 0006 protects has been breached."""
    import re
    root = pathlib.Path(pools.__file__).parent
    importer = re.compile(r"^\s*(from\s+\S*\s+import\s+.*\bpools\b|import\s+.*\bpools\b)",
                          re.MULTILINE)
    for name in ("validate.py", "advancement.py", "lifecycle.py", "costs.py"):
        assert not importer.search((root / name).read_text()), name


def test_pools_does_not_roll_anything():
    """Decision 0009, mechanically: no randomness anywhere in the module."""
    import pathlib
    src = pathlib.Path(pools.__file__).read_text()
    for banned in ("import random", "randint", "secrets", "numpy.random"):
        assert banned not in src


# --------------------------------------------------------------------------- #
# The shipped catalogue
# --------------------------------------------------------------------------- #

def test_the_shipped_roll_catalogue_loads_and_covers_the_printed_rolls(app_ruleset):
    ids = set(app_ruleset.roll_catalog)
    for expected in ("attack-melee", "attack-archery", "parry-melee", "dodge",
                     "virtue-check", "willpower-check"):
        assert expected in ids


def test_only_dodge_and_athletics_carry_the_mobility_penalty(app_ruleset):
    """p.332: the mobility penalty 'doesn't normally apply to attack and parry
    rolls, but does apply to dodge rolls and Athletics rolls for feats that
    require whole-body agility'."""
    mobile = {r.id for r in app_ruleset.roll_catalog.values() if r.mobility_applies}
    assert mobile == {"dodge", "athletics-feat"}


def test_every_shipped_roll_cites_a_page(app_ruleset):
    for roll in app_ruleset.roll_catalog.values():
        assert roll.source.page, f"{roll.id} has no page citation"


def test_every_shipped_roll_computes(app_ruleset):
    c = _char()
    for roll in app_ruleset.roll_catalog.values():
        virtue = VirtueName.VALOR if roll.kind is PoolKind.VIRTUE else None
        bd = pools.base_pool(app_ruleset, c, roll, virtue=virtue)
        assert bd.roll == roll.name
        assert bd.total == sum(ln.value for ln in bd.lines)


# --------------------------------------------------------------------------- #
# Wound penalties: which rolls they touch (human's ruling, 2026-08-12)
# --------------------------------------------------------------------------- #

def test_wound_penalties_apply_to_a_virtue_check():
    """Ruled 2026-08-12: p.229's Order of Modifiers lists wound penalties among the
    subtractions for an action, and nothing exempts a Personality-Trait roll."""
    c = _char()
    c.virtues[VirtueName.VALOR] = 3
    bd = pools.base_pool(_RS, c, _VIRTUE, virtue=VirtueName.VALOR, wound_penalty=-2)
    assert bd.total == 1
    assert ("Wound penalty", -2) in [(ln.label, ln.value) for ln in bd.lines]


def test_wound_penalties_apply_to_a_willpower_check():
    c = _char()
    c.virtues = {VirtueName.COMPASSION: 3, VirtueName.CONVICTION: 2,
                 VirtueName.TEMPERANCE: 4, VirtueName.VALOR: 1}
    bd = pools.base_pool(_RS, c, _WILL, wound_penalty=-1)
    assert bd.total == 6                                    # 7 - 1


def test_a_roll_the_page_exempts_drops_the_wound_line_in_the_ENGINE():
    """p.233 on resisting infection: 'Wound penalties do not subtract from the
    character's dice pool for the purposes of this roll.'

    The gate is here rather than in the caller on purpose — the caller passes the
    penalty in exactly as it would for any other roll, and the row's `wound_applies`
    is what drops it. A rule enforced only by one caller stops running the day a
    second one appears."""
    exempt = RollDefinition(
        id="resist-infection", name="Resist infection",
        attribute=AttributeName.STAMINA, ability=AbilityName.RESISTANCE,
        wound_applies=False)
    bd = pools.base_pool(_RS, _char(), exempt, wound_penalty=-4)
    assert not any("Wound" in ln.label for ln in bd.lines)


def test_the_shipped_catalogue_exempts_exactly_the_one_printed_roll(app_ruleset):
    exempt = {r.id for r in app_ruleset.roll_catalog.values() if not r.wound_applies}
    assert exempt == {"resist-infection"}


# --------------------------------------------------------------------------- #
# Accumulated armour fatigue (core p.332)
# --------------------------------------------------------------------------- #

def test_accumulated_fatigue_subtracts_from_every_roll():
    """'-1 penalty to all actions', unqualified — so unlike mobility there is no
    per-roll gate."""
    for roll in (_ATTACK, _DODGE, _VIRTUE, _WILL):
        virtue = VirtueName.VALOR if roll is _VIRTUE else None
        bd = pools.base_pool(_RS, _char(), roll, virtue=virtue, fatigue_penalty=-2)
        assert ("Fatigue", -2) in [(ln.label, ln.value) for ln in bd.lines], roll.id


def test_fatigue_still_applies_to_the_roll_that_is_wound_exempt():
    """The p.233 exemption names wound penalties and nothing else."""
    exempt = RollDefinition(
        id="resist-infection", name="Resist infection",
        attribute=AttributeName.STAMINA, ability=AbilityName.RESISTANCE,
        wound_applies=False)
    bd = pools.base_pool(_RS, _char(), exempt, wound_penalty=-4, fatigue_penalty=-1)
    labels = [ln.label for ln in bd.lines]
    assert "Fatigue" in labels and not any("Wound" in x for x in labels)


def test_fatigue_is_read_from_play_state_as_a_signed_value():
    c = _char()
    c.play = PlayState(fatigue=3)
    assert pools.fatigue_penalty(c) == -3


def test_a_character_who_never_played_has_no_fatigue():
    c = _char()
    assert pools.fatigue_penalty(c) == 0
    assert c.play is None                # reading must not create play-state


def test_fatigue_never_enters_the_pool_by_itself():
    """Same isolation as the wound penalty (decision 0006) — the caller passes it."""
    c = _char()
    c.play = PlayState(fatigue=5)
    assert pools.base_pool(_RS, c, _ATTACK).total == 7


def test_fatigue_has_no_printed_maximum():
    """'This penalty continues to accumulate' — the model imposes no ceiling."""
    assert PlayState(fatigue=99).fatigue == 99


def test_fatigue_roundtrips_through_a_save():
    from exalted_builder import persistence
    c = _char()
    c.play = PlayState(fatigue=2)
    back = persistence.character_from_json(persistence.character_to_json(c))
    assert back.play.fatigue == 2


def test_an_old_save_loads_with_no_fatigue():
    from exalted_builder import persistence
    c = persistence.character_from_json('{"id": "legacy", "play": {"limit": 2}}')
    assert c.play.fatigue == 0


def test_mobility_is_a_penalty_whichever_sign_it_is_stored_with():
    """The catalogue writes this field NEGATIVE (buff jacket -1), but it is
    hand-editable on the equipment surface and a player may reasonably type "2".
    Either way it must subtract — reading it raw would turn a typed positive into
    bonus dice, which is the failure this test exists for."""
    stored_negative = _char(armor=[Armor(name="Plate", mobility_penalty=-3)])
    typed_positive = _char(armor=[Armor(name="Plate", mobility_penalty=3)])
    assert pools.base_pool(_RS, stored_negative, _DODGE).total == 3     # 4 + 2 - 3
    assert pools.base_pool(_RS, typed_positive, _DODGE).total == 3


def test_the_shipped_armour_catalogue_stores_mobility_negative(app_ruleset):
    """Pins the convention this module had to be taught. If a future row lands
    positive, the sign handling above is what keeps it from adding dice — but the
    data should be fixed, not the engine loosened further."""
    values = [a.mobility_penalty for a in app_ruleset.armor_catalog.values()]
    assert values and max(values) <= 0


# --------------------------------------------------------------------------- #
# A pool driven below one die — reported, never invented away
# --------------------------------------------------------------------------- #

def test_a_pool_below_one_die_is_flagged_and_NOT_clamped():
    """The corebook floors exactly one thing — range penalties, which 'can never
    reduce a character's dice pool below 1' (p.229) — and prints no general rule.
    Clamping every pool would be inventing one, so the arithmetic stands and the
    surface says what happened."""
    c = _char()
    c.virtues[VirtueName.VALOR] = 1
    bd = pools.base_pool(_RS, c, _VIRTUE, virtue=VirtueName.VALOR,
                         wound_penalty=-1, fatigue_penalty=-2)
    assert bd.total == -2
    assert bd.below_one


def test_a_healthy_pool_is_not_flagged():
    assert not pools.base_pool(_RS, _char(), _ATTACK).below_one


def test_a_pool_of_exactly_one_die_is_not_flagged():
    c = _char()
    c.virtues[VirtueName.VALOR] = 1
    assert not pools.base_pool(_RS, c, _VIRTUE, virtue=VirtueName.VALOR).below_one


# --------------------------------------------------------------------------- #
# Which rolls a weapon belongs to (core weapon tags)
#
# Only matters because the sidebar shows every roll at once: with one weapon
# selected, a daiklave that lent its accuracy to the Archery row would be visibly,
# confidently wrong — the exact failure mode decision 0008 named.
# --------------------------------------------------------------------------- #

def test_a_melee_weapon_does_not_join_an_archery_pool(app_ruleset):
    sword = Weapon(name="Short Sword", accuracy=2)
    melee = app_ruleset.roll_catalog["attack-melee"]
    archery = app_ruleset.roll_catalog["attack-archery"]
    assert pools.weapon_applies(app_ruleset, sword, melee)
    assert not pools.weapon_applies(app_ruleset, sword, archery)


def test_a_bow_joins_only_the_archery_pool(app_ruleset):
    bow = Weapon(name="Self Bow", accuracy=0)
    assert pools.weapon_applies(app_ruleset, bow, app_ruleset.roll_catalog["attack-archery"])
    assert not pools.weapon_applies(app_ruleset, bow, app_ruleset.roll_catalog["attack-melee"])


def test_an_unknown_weapon_applies_everywhere(app_ruleset):
    """⚠ None means UNKNOWN, not "none of them". The character's Weapon is an inline
    copy carrying no tags (decision 0007), so the Ability is recovered by matching
    the name back to the catalogue — and a homebrew or renamed weapon matches
    nothing. It must keep working on every attack roll; the alternative is that the
    first thing a player names themselves silently stops adding its accuracy."""
    home = Weapon(name="Grandpa's Cleaver", accuracy=3)
    assert pools.weapon_abilities(app_ruleset, home) is None
    for rid in ("attack-melee", "attack-archery", "attack-brawl", "parry-melee"):
        assert pools.weapon_applies(app_ruleset, home, app_ruleset.roll_catalog[rid])


def test_no_weapon_joins_a_roll_that_names_no_weapon_stat(app_ruleset):
    sword = Weapon(name="Short Sword", accuracy=2)
    for rid in ("dodge", "virtue-check", "willpower-check", "resist-infection"):
        assert not pools.weapon_applies(app_ruleset, sword, app_ruleset.roll_catalog[rid])


def test_only_the_five_attack_abilities_are_read_off_the_tags(app_ruleset):
    """`weapons.json` also tags shape and provenance — "blade", "impact", "spear",
    "artifact", "ranged" — none of which name a roll."""
    daiklave = Weapon(name="Reaver Daiklave")     # tagged melee AND artifact
    assert pools.weapon_abilities(app_ruleset, daiklave) == {AbilityName.MELEE}


# --------------------------------------------------------------------------- #
# The compact one-line breakdown the sidebar renders
# --------------------------------------------------------------------------- #

def test_the_compact_line_is_a_breakdown_not_a_bare_total():
    """A column of bare totals is what 0008 rejected; the sidebar shows this string
    on every row, so it has to carry every term."""
    c = _char(armor=[Armor(name="Plate", mobility_penalty=-1)])
    bd = pools.base_pool(_RS, c, _DODGE, wound_penalty=-1, fatigue_penalty=-2)
    assert bd.compact == "+4 dex +2 dodge -1 mob -1 wnd -2 ftg"
    assert str(bd.total) not in bd.compact.split()   # the total is NOT in the line


def test_every_line_carries_a_short_label():
    c = _char(specialties=[Specialty(ability=AbilityName.MELEE, name="Swords", rating=1)])
    bd = pools.base_pool(_RS, c, _ATTACK, weapon=Weapon(name="Sword", accuracy=2),
                         specialty=pools.specialties_for(c, _ATTACK)[0],
                         wound_penalty=-1, fatigue_penalty=-1)
    assert all(ln.short for ln in bd.lines)


# --------------------------------------------------------------------------- #
# The custom Attribute + Ability pool
#
# The catalogue covers the rolls the corebook spells out; the rest of 1e is "roll
# Attribute + Ability" for whatever the table is doing, and there is no printed
# roster of those to author. So it is a builder, not data — and it must not claim
# a page it does not have.
# --------------------------------------------------------------------------- #

def test_a_custom_roll_is_just_attribute_plus_ability():
    roll = pools.custom_roll(AttributeName.WITS, AbilityName.AWARENESS)
    c = _char()
    c.attributes[AttributeName.WITS] = 3
    c.abilities[AbilityName.AWARENESS] = 2
    bd = pools.base_pool(_RS, c, roll)
    assert bd.total == 5
    assert bd.roll == "Wits + Awareness"
    assert [ln.label for ln in bd.lines] == ["Wits", "Awareness"]


def test_a_custom_roll_cites_no_page():
    """It has no printed source, and must not imply one — the never-author-from-
    memory rule applies to a synthesised row exactly as it does to data/."""
    roll = pools.custom_roll(AttributeName.WITS, AbilityName.AWARENESS)
    assert roll.source.page is None
    assert roll.notes == ""


def test_a_custom_roll_takes_no_weapon():
    """No weapon_stat, so a weapon passed in is ignored rather than guessed at."""
    roll = pools.custom_roll(AttributeName.DEXTERITY, AbilityName.MELEE)
    bd = pools.base_pool(_RS, _char(), roll, weapon=Weapon(name="Sword", accuracy=9))
    assert bd.total == 7
    assert not any("accuracy" in ln.label for ln in bd.lines)


def test_a_custom_roll_carries_no_mobility_penalty_by_default():
    """p.332 names dodge and whole-body Athletics feats; everything else is the
    Storyteller's discretion, so the default must not assume it."""
    c = _char(armor=[Armor(name="Plate", mobility_penalty=-3)])
    roll = pools.custom_roll(AttributeName.DEXTERITY, AbilityName.ATHLETICS)
    assert not any("mobility" in ln.label
                   for ln in pools.base_pool(_RS, c, roll).lines)


def test_a_custom_roll_can_opt_into_the_mobility_penalty():
    """'The Storyteller can also apply this penalty to anything else she deems
    becomes more difficult in 20 or more pounds of protective gear' (p.332)."""
    c = _char(armor=[Armor(name="Plate", mobility_penalty=-3)])
    roll = pools.custom_roll(AttributeName.DEXTERITY, AbilityName.ATHLETICS,
                             mobility_applies=True)
    assert ("Plate (mobility)", -3) in [
        (ln.label, ln.value) for ln in pools.base_pool(_RS, c, roll).lines]


def test_a_custom_roll_still_takes_wound_and_fatigue():
    c = _char()
    roll = pools.custom_roll(AttributeName.WITS, AbilityName.AWARENESS)
    bd = pools.base_pool(_RS, c, roll, wound_penalty=-2, fatigue_penalty=-1)
    labels = [ln.label for ln in bd.lines]
    assert "Wound penalty" in labels and "Fatigue" in labels


def test_a_custom_roll_finds_the_specialties_on_its_ability():
    c = _char(specialties=[Specialty(ability=AbilityName.MELEE, name="Swords", rating=1),
                           Specialty(ability=AbilityName.MELEE, name="Swords", rating=1)])
    roll = pools.custom_roll(AttributeName.DEXTERITY, AbilityName.MELEE)
    assert [(o.name, o.dice) for o in pools.specialties_for(c, roll)] == [("Swords", 2)]


def test_every_attribute_ability_pair_computes():
    """9 x 25 = 225 combinations, all of which the two selects can produce. A pair
    that raised would be a blank sidebar, and only for the player who picked it."""
    c = _char()
    for attribute in AttributeName:
        for ability in AbilityName:
            bd = pools.base_pool(_RS, c, pools.custom_roll(attribute, ability))
            assert bd.total == sum(ln.value for ln in bd.lines)


# --------------------------------------------------------------------------- #
# The Play tab's stored selection vs a weapon list that changed under it
# --------------------------------------------------------------------------- #

def test_a_stale_weapon_or_arrow_choice_is_cleared_not_remapped():
    """The Play tab's `state` outlives the weapon list it indexes — the player deletes
    a weapon on the equipment surface and the sidebar rebuilds with the old choice. A
    `ui.select` whose value is not among its options raises at BUILD time and blanks
    the whole tab, siblings included (adding-a-splat trap #3).

    Cleared, never remapped: deleting a row renumbers everything after it, so the index
    that survives names a DIFFERENT weapon than the one the player chose."""
    from exalted_builder.ui import view as viewmod

    sidebar = viewmod.PoolSidebarView(weapons=[(0, "Long Bow")], groups=[], excludes=[],
                                      arrows=[(1, "Broadhead Arrow")])
    state = {"weapon": 0, "arrow": 1}
    viewmod.clamp_pool_selection(state, sidebar)
    assert state == {"weapon": 0, "arrow": 1}          # both still name a row

    # The Fowling Arrow at index 1 is deleted: the Broadhead renumbers 2 -> 1, and the
    # stored 2 names nothing.
    state = {"weapon": 0, "arrow": 2}
    viewmod.clamp_pool_selection(state, sidebar)
    assert state == {"weapon": 0, "arrow": None}

    # ...and with no rows at all, both clear rather than pointing at a gap.
    empty = viewmod.PoolSidebarView(weapons=[], groups=[], excludes=[])
    state = {"weapon": 0, "arrow": 1}
    viewmod.clamp_pool_selection(state, empty)
    assert state == {"weapon": None, "arrow": None}
