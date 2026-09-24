"""Tests for engine.initiative — the initiative RATING (core p.227).

A rating, not a pool and not a roll: Dexterity + Wits + the wielded weapon's
Speed, to which the table adds 1d10 each turn. Decision 0019 lifted this out of
0016's exclusion on the express condition that it is NOT authored as a row in
`data/dice_pools.json`, and one test here asserts that absence.

The modifiers are the human's ruling of 2026-09-08 with their citations: Speed
adjusted by magical material (p.341) and by the weapon's unmet minimums; armour
mobility and encumbrance excluded; fatigue left to the Storyteller; wound
penalties Power-Combat-only and therefore out.
"""

import pathlib

import pytest

from exalted_builder import rules_db
from exalted_builder.engine import initiative
from exalted_builder.models.character import Armor, Character, PlayState, Weapon
from exalted_builder.models.rules import AttributeName

_DATA = pathlib.Path(__file__).resolve().parents[1] / "exalted_builder" / "data"


@pytest.fixture(scope="module")
def app_ruleset():
    return rules_db.load_app_ruleset(_DATA)


def _char(dex=4, wits=2, **kw) -> Character:
    c = Character(id="c.init", name="Duelist", exalt_type="Solar", caste="dawn", **kw)
    c.attributes[AttributeName.DEXTERITY] = dex
    c.attributes[AttributeName.WITS] = wits
    return c


# --- the base rating (p.227) ---------------------------------------------

def test_the_rating_is_dexterity_plus_wits_unarmed(app_ruleset):
    assert initiative.initiative(app_ruleset, _char(dex=4, wits=2)).total == 6


def test_the_two_attributes_are_itemised_not_summed_into_one_line(app_ruleset):
    """Same mitigation 0016 accepted for pools: a bare number is what decision
    0008 rejected, so the terms stay visible."""
    rating = initiative.initiative(app_ruleset, _char())
    assert [(ln.label, ln.value) for ln in rating.lines] == [
        ("Dexterity", 4), ("Wits", 2)]


def test_the_total_is_the_sum_of_the_lines_and_nothing_else(app_ruleset):
    rating = initiative.initiative(
        app_ruleset, _char(), weapon=Weapon(name="Daiklave", speed=3))
    assert rating.total == sum(ln.value for ln in rating.lines)


# --- weapon Speed (p.227, p.326) -----------------------------------------

def test_weapon_speed_is_a_flat_modifier_not_dice(app_ruleset):
    rating = initiative.initiative(
        app_ruleset, _char(), weapon=Weapon(name="Daiklave", speed=3))
    assert rating.total == 9


def test_a_negative_speed_subtracts(app_ruleset):
    """Sledge -6, Grand Daiklave -3 — the sign is stored, not derived."""
    rating = initiative.initiative(
        app_ruleset, _char(), weapon=Weapon(name="Sledge", speed=-6))
    assert rating.total == 0


def test_a_rating_may_go_negative_and_is_not_clamped(app_ruleset):
    """Nothing printed floors it, so inventing a floor would be inventing a rule
    — the same reasoning `PoolBreakdown.below_one` carries for pools."""
    rating = initiative.initiative(
        app_ruleset, _char(dex=1, wits=1), weapon=Weapon(name="Sledge", speed=-6))
    assert rating.total == -4


def test_a_speed_zero_weapon_still_gets_a_line(app_ruleset):
    """Most swords are +0. The line has to appear anyway, or the player cannot
    tell the weapon was counted from the one that was not chosen."""
    rating = initiative.initiative(
        app_ruleset, _char(), weapon=Weapon(name="Straight Sword", speed=0))
    assert any("Straight Sword" in ln.label for ln in rating.lines)
    assert rating.total == 6


# --- the two Speed adjustments -------------------------------------------

def test_unmet_weapon_minimums_subtract_one_per_dot(app_ruleset):
    """p.327's note: a dot short costs 1 from speed, attack AND defense. The
    shortfall count comes from `pools.weapon_minimum_shortfall`, which owns it."""
    weapon = Weapon(name="Grand Daiklave", speed=-3, min_strength=5)
    rating = initiative.initiative(app_ruleset, _char(), weapon=weapon)
    # Strength 1 against a minimum of 5 is four dots short.
    assert rating.total == 4 + 2 - 3 - 4
    assert any("minimums" in ln.label for ln in rating.lines)


def test_orichalcum_adds_its_speed_for_a_solar(app_ruleset):
    """p.341: +1 Speed, and only because the wielder is a Solar."""
    weapon = Weapon(name="Daiklave", speed=3, material="orichalcum")
    plain = initiative.initiative(
        app_ruleset, _char(), weapon=Weapon(name="Daiklave", speed=3)).total
    assert initiative.initiative(app_ruleset, _char(), weapon=weapon).total == plain + 1


def test_a_material_that_does_not_resonate_adds_no_speed(app_ruleset):
    """Jade is +3 Speed for the Dragon-Blooded and nothing for a Solar. The gate
    is `derive.effective_weapon`'s, which is why initiative must go through it
    rather than reading `weapon.speed` itself."""
    weapon = Weapon(name="Daiklave", speed=3, material="jade")
    assert initiative.initiative(app_ruleset, _char(), weapon=weapon).total == 9


def test_moonsilver_grants_no_speed_bonus(app_ruleset):
    """p.341: moonsilver, starmetal and soulsteel carry no Speed at all."""
    lunar = Character(id="c.l", name="L", exalt_type="Lunar", caste="full-moon")
    lunar.attributes[AttributeName.DEXTERITY] = 4
    lunar.attributes[AttributeName.WITS] = 2
    weapon = Weapon(name="Moonsilver Daiklave", speed=3, material="moonsilver")
    assert initiative.initiative(app_ruleset, lunar, weapon=weapon).total == 9


# --- what does NOT reach the rating (human's ruling, 2026-09-08) ----------

def test_armour_mobility_does_not_slow_the_wearer(app_ruleset):
    """p.332 scopes mobility to rolls needing agility — dodge and Athletics. A
    rating is not such a roll. ⚠ The human's reading of scope, not an explicit
    exclusion in the text; it is a ruling and reversing it is theirs to do."""
    char = _char()
    char.armor.append(Armor(name="Breastplate", soak_lethal=5, mobility_penalty=-1,
                            fatigue=2))
    assert initiative.initiative(app_ruleset, char).total == 6


def test_accumulated_fatigue_does_not_reach_the_rating(app_ruleset):
    """'-1 to all actions' (p.332) — whether that reaches initiative is a
    judgement call the core initiative rules do not make, so the app does not
    make it either. The excludes list says so on the surface."""
    char = _char()
    char.play = PlayState(fatigue=3)
    assert initiative.initiative(app_ruleset, char).total == 6


def test_a_wound_penalty_does_not_reach_the_rating(app_ruleset):
    """Wound penalties apply to initiative only under POWER COMBAT (Player's
    Guide), which this build does not implement. ⚠ If Power Combat is ever added,
    Speed is redefined wholesale and every weapon value changes with it — that is
    a bigger job than adding a line here."""
    from exalted_builder.models.character import Damage
    char = _char()
    char.play = PlayState(health=[Damage.LETHAL] * 4)
    assert initiative.initiative(app_ruleset, char).total == 6


# --- 0019's conditions ----------------------------------------------------

def test_initiative_is_not_a_row_in_the_roll_catalogue(app_ruleset):
    """⚠ Decision 0019 lifted 0016's exclusion ONLY as a rating. A row in
    `data/dice_pools.json` would make it a POOL — which the sidebar renders with a
    total in dice and the roller sits beside, inviting a player to roll the whole
    rating as a handful. It is a rating plus ONE d10."""
    ids = set(app_ruleset.roll_catalog)
    names = {r.name.lower() for r in app_ruleset.roll_catalog.values()}
    assert "initiative" not in ids
    assert not [n for n in names if "initiative" in n]


def test_the_rating_states_the_d10_and_the_tie_break(app_ruleset):
    rating = initiative.initiative(app_ruleset, _char())
    assert "1d10" in rating.turn_note
    assert "Dexterity + Wits" in rating.tie_break


def test_it_says_what_it_leaves_out(app_ruleset):
    """Charms first — the same open-ended thing 0008 refused to model."""
    text = " ".join(initiative.initiative(app_ruleset, _char()).excludes).lower()
    for term in ("charm", "mobility", "fatigue", "power combat"):
        assert term in text


def test_nothing_here_rolls_anything(app_ruleset):
    """The rating is arithmetic. The d10 is the player's, in the dumb roller."""
    import inspect
    source = inspect.getsource(initiative)
    assert "random" not in source
    assert "import" not in source.split("def initiative")[1]


def test_jade_does_add_its_speed_for_a_dragon_blooded(app_ruleset):
    """The positive half of the resonance gate. Without this, the Solar-with-jade
    test above would pass just as happily if jade's +3 were missing from the
    catalogue entirely — it would be asserting the bug it exists to guard."""
    db = Character(id="c.db", name="D", exalt_type="Dragon-Blooded", caste="earth")
    db.attributes[AttributeName.DEXTERITY] = 4
    db.attributes[AttributeName.WITS] = 2
    weapon = Weapon(name="Jade Daiklave", speed=3, material="jade")
    assert initiative.initiative(app_ruleset, db, weapon=weapon).total == 12


# --- the turn order of a table (P3 step 9) --------------------------------
#
# Human, 2026-09-24: ties break on the higher Dexterity + Wits (p.227) when each
# tied entry has it; a tie that remains is marked "tied" and the table rolls off.

def _roll(key, rating, d10, dex_wits=None):
    return initiative.TurnRoll(key=key, rating=rating, d10=d10, dex_wits=dex_wits)


def test_the_total_is_the_rating_plus_the_d10():
    assert _roll("a", 6, 7).total == 13
    assert _roll("a", -2, 1).total == -1


def test_the_order_is_the_highest_total_first():
    placed = initiative.turn_order([_roll("a", 5, 2), _roll("b", 4, 9), _roll("c", 6, 5)])
    assert [p.roll.key for p in placed] == ["b", "c", "a"]
    assert not any(p.tied for p in placed)


def test_a_tie_breaks_on_the_higher_dexterity_plus_wits():
    placed = initiative.turn_order([_roll("a", 5, 5, dex_wits=5),
                                    _roll("b", 7, 3, dex_wits=7)])
    assert [p.roll.key for p in placed] == ["b", "a"]
    assert not any(p.tied for p in placed)


def test_a_tie_on_dexterity_plus_wits_too_is_marked_tied():
    placed = initiative.turn_order([_roll("a", 5, 5, dex_wits=5),
                                    _roll("b", 5, 5, dex_wits=5),
                                    _roll("c", 9, 5, dex_wits=9)])
    assert [p.roll.key for p in placed] == ["c", "a", "b"]
    assert [p.tied for p in placed] == [False, True, True]


def test_a_tie_with_an_entry_that_has_no_dexterity_plus_wits_stays_tied():
    """A roster entry that does not print both Attributes cannot lose the
    tie-break by default. The whole tie stays for the table."""
    placed = initiative.turn_order([_roll("a", 5, 5, dex_wits=9),
                                    _roll("b", 5, 5, dex_wits=None),
                                    _roll("c", 4, 6, dex_wits=2)])
    assert [p.roll.key for p in placed] == ["a", "b", "c"]
    assert all(p.tied for p in placed)


def test_only_the_equal_dexterity_plus_wits_stay_tied_inside_a_tie():
    placed = initiative.turn_order([_roll("a", 5, 5, dex_wits=5),
                                    _roll("b", 8, 2, dex_wits=8),
                                    _roll("c", 5, 5, dex_wits=5)])
    assert [p.roll.key for p in placed] == ["b", "a", "c"]
    assert [p.tied for p in placed] == [False, True, True]


def test_dexterity_plus_wits_of_a_character():
    assert initiative.dex_wits(_char(dex=4, wits=2)) == 6
