"""`engine.charm_actions` — the shared Charm/spell/variant-menu purchase dispatchers.

These used to be closures inside `ui/picker.py`, and the Qt port copied them by hand.
The copies drifted immediately: the web picker grew a variant menu for Ox-Body and
Deadly Beastman Transformation, and the Qt copy — which toggles straight from a node
click, with no detail-card branch in front of it — would have appended the package
Charm's id into `character.charms`, a purchase the engine cannot price or validate.

So the interesting tests here are the variant-menu refusals: they are what makes the
shape safe for a shell that has no widget-level guard. The rest pin the lock dispatch
(a chargen list edit before, an XP purchase after) and the refusal type, which both
shells catch to turn into a notification.
"""
from pathlib import Path

import pytest

from exalted_builder import rules_db
from exalted_builder.engine import advancement, charm_actions, lifecycle, validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName as AB

DATA_DIR = Path(__file__).resolve().parents[1] / "exalted_builder" / "data"

STRIKE = "solar.melee.excellent-strike"
TIGER = "solar.melee.hungry-tiger-technique"      # requires STRIKE


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _solar() -> Character:
    c = Character(id="c.act", exalt_type="Solar", caste="dawn")
    c.abilities[AB.MELEE] = 3
    c.abilities[AB.ENDURANCE] = 3
    return c


# ---- the lock dispatch -------------------------------------------------- #

def test_learn_appends_at_chargen_and_toggle_takes_it_back(rs):
    c = _solar()
    assert "Excellent Strike" in charm_actions.learn_charm(rs, c, STRIKE)
    assert c.charms == [STRIKE]
    assert "Removed" in charm_actions.toggle_charm(rs, c, STRIKE)
    assert c.charms == []


def test_chargen_removal_refuses_while_a_dependant_holds_it(rs):
    c = _solar()
    charm_actions.learn_charm(rs, c, STRIKE)
    charm_actions.learn_charm(rs, c, TIGER)
    with pytest.raises(advancement.AdvancementError) as ex:
        charm_actions.toggle_charm(rs, c, STRIKE)
    assert "needed by" in str(ex.value)
    assert STRIKE in c.charms


def test_learning_without_prerequisites_refuses(rs):
    c = _solar()
    with pytest.raises(advancement.AdvancementError) as ex:
        charm_actions.learn_charm(rs, c, TIGER)
    assert "prerequisites not met" in str(ex.value)
    assert c.charms == []


def test_post_lock_a_charm_is_an_xp_purchase_and_a_second_click_never_refunds(rs):
    """⚠ The post-lock asymmetry: a click in a shop is a purchase, and clicking the
    same node again must NOT read as a drop. The refusal points at the XP ledger,
    which is the only refund (decision 0004)."""
    c = _solar()
    lifecycle.lock_chargen(c, rs)
    c.xp_earned = 50
    before = advancement.xp_available(c)
    assert "XP" in charm_actions.toggle_charm(rs, c, STRIKE)
    assert c.charms == [STRIKE]
    assert advancement.xp_available(c) < before

    with pytest.raises(advancement.AdvancementError) as ex:
        charm_actions.toggle_charm(rs, c, STRIKE)
    assert "Edit tab" in str(ex.value)
    assert c.charms == [STRIKE]          # not dropped, not double-bought


def test_drop_charm_post_lock_refuses_outright(rs):
    c = _solar()
    charm_actions.learn_charm(rs, c, STRIKE)
    lifecycle.lock_chargen(c, rs)
    with pytest.raises(advancement.AdvancementError):
        charm_actions.drop_charm(rs, c, STRIKE)
    assert c.charms == [STRIKE]


def test_an_unknown_id_refuses_rather_than_being_ignored(rs):
    c = _solar()
    with pytest.raises(advancement.AdvancementError):
        charm_actions.learn_charm(rs, c, "solar.melee.no-such-charm")


# ---- the variant-menu guard — the reason this module exists -------------- #

def test_ox_body_cannot_be_toggled_into_the_plain_charm_list(rs):
    """⚠ THE bug this extraction closes. Ox-Body is bought as a package into
    `character.ox_body`; appending its id to `character.charms` produces a Charm the
    point accounting cannot price and `validate.check_ox_body` never sees."""
    c = _solar()
    ox = validate.ox_body_charm_id(rs, c)
    assert ox, "the Solar catalogue must hold Ox-Body for this test to mean anything"
    with pytest.raises(advancement.AdvancementError) as ex:
        charm_actions.toggle_charm(rs, c, ox)
    assert "package" in str(ex.value)
    assert ox not in c.charms
    assert c.ox_body == []


def test_the_variant_menu_reason_is_empty_for_an_ordinary_charm(rs):
    """A negative control: the guard must not refuse things it does not own. Without
    this, a reason() that returned a string for everything would pass the test above."""
    c = _solar()
    assert charm_actions.variant_menu_reason(rs, c, STRIKE) == ""


def test_gift_charm_cannot_be_toggled_either(rs):
    c = Character(id="c.lunar", exalt_type="Lunar", caste="full-moon")
    gift = validate.gift_charm_id(rs, c)
    if not gift:
        pytest.skip("no Deadly Beastman Transformation in this catalogue")
    with pytest.raises(advancement.AdvancementError):
        charm_actions.toggle_charm(rs, c, gift)
    assert gift not in c.charms
    assert c.beastman_gifts == []


def test_ox_body_buys_into_its_own_list_and_caps_on_the_splat_trait(rs):
    c = _solar()
    charm = validate.ox_body_charm(rs, c)
    cap = validate.ox_body_cap(rs, c)
    assert cap == c.abilities[AB.ENDURANCE]        # Solar counts Endurance, p.170
    key = charm.variants[0].key
    for _ in range(cap):
        charm_actions.add_ox_body(rs, c, key)
    assert len(c.ox_body) == cap
    assert not c.charms                            # never the plain list

    with pytest.raises(advancement.AdvancementError) as ex:
        charm_actions.add_ox_body(rs, c, key)
    # The cap trait is per-splat DATA and the message must name the one in play
    # rather than hardcoding "Endurance" (Lunar Ox-Body counts Stamina, p.132).
    assert validate.repeatable_cap_trait_name(charm) in str(ex.value)


def test_removing_an_ox_body_package_by_index(rs):
    c = _solar()
    charm = validate.ox_body_charm(rs, c)
    charm_actions.add_ox_body(rs, c, charm.variants[0].key)
    charm_actions.remove_ox_body(c, 0)
    assert c.ox_body == []
    with pytest.raises(advancement.AdvancementError):
        charm_actions.remove_ox_body(c, 0)


# ---- spells ------------------------------------------------------------- #

def test_spell_toggle_round_trips_at_chargen(rs):
    c = _solar()
    c.abilities[AB.OCCULT] = 3
    c.essence_rating = 3                            # Terrestrial Circle needs both
    charm_actions.learn_charm(rs, c, "solar.occult.terrestrial-circle-sorcery")
    spell = next(s for s in rs.spells.values()
                 if validate.meets_spell_requirements(rs, c, s))
    assert "Learned" in charm_actions.toggle_spell(rs, c, spell.id)
    assert c.spells == [spell.id]
    assert "Dropped" in charm_actions.toggle_spell(rs, c, spell.id)
    assert c.spells == []


def test_an_unavailable_spell_refuses(rs):
    c = _solar()                                    # no sorcery Charm, no Circle
    spell = next(iter(rs.spells.values()))
    with pytest.raises(advancement.AdvancementError):
        charm_actions.learn_spell(rs, c, spell.id)
    assert c.spells == []
