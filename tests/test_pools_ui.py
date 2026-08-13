"""Render tests for the dice-pool sidebar on the Play tab (decision 0016).

These are BINDING tests, not helper tests: they open the page the player actually
uses and assert the rows appear with their arithmetic and — the part that matters —
the exclusions. 0016 narrowed 0008 only because the surface says what it leaves out
and shows a breakdown rather than a bare number; a change that drops either has
re-created what 0008 rejected, and this file is what catches it.
"""

import pytest
from nicegui.elements.select import Select
from nicegui.testing import User

MAIN = "tests/_ui_main.py"


def _weapon_select(user: User) -> Select:
    return next(e for e in user.client.elements.values()
                if isinstance(e, Select) and e._props.get('label') == 'Attack with')


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_sidebar_renders_with_its_groups(user: User) -> None:
    await user.open('/pools')
    await user.should_see("DICE POOLS")
    await user.should_see("COMBAT")
    await user.should_see("PERSONALITY")
    await user.should_see("Attack with")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_every_row_shows_its_arithmetic_not_just_a_total(user: User) -> None:
    """The list must stay a list of BREAKDOWNS. A column of bare totals is exactly
    the 'looks authoritative' surface 0008 rejected, and the compact line is what
    0016 accepted in its place."""
    await user.open('/pools')
    await user.should_see("Attack — Melee")
    await user.should_see("+4 dex +3 melee -1 wnd")     # unarmed until a weapon is picked
    await user.should_see("Dodge")
    await user.should_see("+4 dex +2 dodge -1 mob -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_it_states_what_it_excludes(user: User) -> None:
    await user.open('/pools')
    await user.should_see("These are BASE pools. They do not include:")
    await user.should_see("No dice are rolled here, and nothing is resolved.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_picking_a_weapon_adds_its_accuracy_to_the_rolls_that_use_it(
        user: User) -> None:
    """CHAR_POOLS carries a Short Sword (accuracy 2, defense 3), tagged `melee` in
    the catalogue. It must join the Melee rows and stay out of the Archery one — a
    daiklave lends nothing to a bow, and a list shows every row at once, so a weapon
    applied indiscriminately is visibly wrong."""
    await user.open('/pools')
    _weapon_select(user).set_value(0)
    await user.should_see("+4 dex +3 melee +2 acc -1 wnd")      # Attack — Melee
    await user.should_see("+4 dex +3 melee +3 def -1 wnd")      # Parry — Melee
    await user.should_see("+4 dex +0 archery -1 wnd")           # Archery, unarmed


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_specialty_gets_its_own_row_summed_across_instances(user: User) -> None:
    """A specialty applies only to its own facet (p.134), so folding it into the
    base row would claim dice the character does not always have — it is a separate
    row. CHAR_POOLS holds Swords twice, which is +2 dice, not +1."""
    await user.open('/pools')
    await user.should_see("Attack — Melee · Swords")
    await user.should_see("+4 dex +3 melee +2 spec -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_virtue_check_becomes_one_row_per_virtue(user: User) -> None:
    """In a list there is nothing to pick from, so the choice has to be visible."""
    await user.open('/pools')
    for virtue in ("Compassion", "Conviction", "Temperance", "Valor"):
        await user.should_see(f"Virtue check — {virtue}")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_wound_exempt_row_carries_no_wound_term(user: User) -> None:
    """p.233: 'Wound penalties do not subtract from the character's dice pool for
    the purposes of this roll.' CHAR_POOLS is at -1, and this row must not show it."""
    await user.open('/pools')
    await user.should_see("Resist infection")
    await user.should_see("+1 sta +0 resistance")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_marking_damage_does_not_reset_the_chosen_weapon(user: User) -> None:
    """The sidebar is rebuilt on every health click (it shares the tracker's
    refreshable body), and a deepening wound is exactly what sends a player back to
    it. State owned by the sidebar would drop the weapon on that click, so it lives
    one level up in build_play — this is the binding for it.

    The assertion is on the RENDERED row, not the Select's `value`: after a refresh
    the Select fetched from the client is a stale one still carrying the old value,
    so reading it passes either way. (It did — a negative control caught that before
    this test was trusted.)
    """
    await user.open('/pools-click')
    _weapon_select(user).set_value(0)
    await user.should_see("+4 dex +3 melee +2 acc -1 wnd")
    # Marking a -2 box deepens the wound term; the weapon's +2 acc must survive.
    user.find(marker="play-health-3").click()
    await user.should_see("+4 dex +3 melee +2 acc -2 wnd")
    await user.should_not_see("+4 dex +3 melee -2 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_armour_fatigue_is_tracked_and_reaches_every_row(user: User) -> None:
    """p.332. The counter is manual — the app neither rolls for it nor tracks the
    eight hours of rest that shed a point — and the penalty is 'to all actions', so
    it lands on every row with no per-roll gate, the p.233 row included."""
    await user.open('/pools-fatigue')
    await user.should_see("Armour fatigue")
    await user.should_see("Fatigue roll difficulty: Buff Jacket 2")
    await user.should_see("+4 dex +3 melee -2 ftg")         # no damage on this one
    await user.should_see("+1 sta +0 resistance -2 ftg")    # wound-exempt ≠ fatigue-exempt


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_row_driven_below_one_die_is_flagged_not_clamped(user: User) -> None:
    """The core floors range penalties and nothing else (p.229), so a general floor
    would be invented. CHAR_POOLS_FATIGUE has Valor 1 against -2 fatigue."""
    await user.open('/pools-fatigue')
    await user.should_see("Virtue check — Valor")
    await user.should_see("taken below one die by the penalties")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_it_renders_for_a_character_owning_no_weapons_or_armour(user: User) -> None:
    """The empty shapes at once: no weapons (the weapon select's options would be
    empty, which is the NiceGUI build-time crash class), no armour, no specialties,
    no damage. A Mortal fresh off chargen is exactly this."""
    await user.open('/pools-bare')
    await user.should_see("DICE POOLS")
    await user.should_see("No weapon owned — the attack rows are unarmed.")
    await user.should_see("Attack — Melee")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_custom_pool_block_computes_from_two_dropdowns(user: User) -> None:
    """The builder for everything the catalogue does not name. It lives in the MAIN
    column, not the sidebar — the roll list is long and the tracker beside it is
    short. It renders a real number on arrival rather than an empty frame, and
    changing either select recomputes: CHAR_POOLS is Dexterity 4 / Athletics 0 /
    Awareness 0 / Wits 1, at -1 wound."""
    await user.open('/pools')
    await user.should_see("your own Attribute + Ability")
    await user.should_see("Dexterity + Athletics")
    await user.should_see("+4 dex +0 athletics -1 wnd")
    ability = next(e for e in user.client.elements.values()
                   if isinstance(e, Select) and e._props.get('label') == 'Ability')
    ability.set_value("melee")
    await user.should_see("Dexterity + Melee")
    await user.should_see("+4 dex +3 melee -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_custom_pool_shows_its_arithmetic_like_every_other_row(
        user: User) -> None:
    """It goes through the same _pool_row renderer, so it cannot drift into being a
    bare number while the preset rows stay itemised."""
    await user.open('/pools')
    attribute = next(e for e in user.client.elements.values()
                     if isinstance(e, Select) and e._props.get('label') == 'Attribute')
    attribute.set_value("wits")
    await user.should_see("Wits + Athletics")
    await user.should_see("+1 wits +0 athletics -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_custom_pool_omits_mobility_until_the_player_asks(user: User) -> None:
    """p.332 names dodge and whole-body Athletics feats and leaves the rest to the
    Storyteller, so the checkbox is the player's answer, not a default."""
    from nicegui.elements.checkbox import Checkbox
    await user.open('/pools')
    await user.should_see("+4 dex +0 athletics -1 wnd")      # no mob term
    box = next(e for e in user.client.elements.values() if isinstance(e, Checkbox))
    box.set_value(True)
    await user.should_see("+4 dex +0 athletics -1 mob -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_custom_pool_picks_up_a_specialty_on_the_chosen_ability(
        user: User) -> None:
    await user.open('/pools')
    ability = next(e for e in user.client.elements.values()
                   if isinstance(e, Select) and e._props.get('label') == 'Ability')
    ability.set_value("melee")
    await user.should_see("Dexterity + Melee · Swords")
    await user.should_see("+4 dex +3 melee +2 spec -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_sidebar_toggle_reaches_the_custom_panel_in_the_other_column(
        user: User) -> None:
    """The two blocks now live in different columns and share one state dict, so a
    penalty switch flipped in the sidebar has to redraw BOTH. That only works
    because each takes the caller's refresh rather than owning a private
    refreshable — this is the binding for it, and it is exactly the shape that
    fails silently: the switch keeps working where you can see it and stops working
    where you cannot.
    """
    from nicegui.elements.switch import Switch
    await user.open('/pools')
    await user.should_see("+4 dex +0 athletics -1 wnd")       # custom row, wound on
    wound = next(e for e in user.client.elements.values()
                 if isinstance(e, Switch) and "Wound penalty" in (e.text or ""))
    wound.set_value(False)
    await user.should_see("+4 dex +0 athletics")              # custom row, wound gone
    await user.should_not_see("+4 dex +0 athletics -1 wnd")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_ammunition_is_not_offered_as_a_weapon_to_attack_with(user) -> None:
    """An arrow is not a thing you attack with — it is what the bow throws. It also
    must not shift the indices of the real weapons: the select's value is a position in
    `character.weapons`, so a filtered list numbered by position would attack with the
    wrong weapon."""
    from nicegui import ui as _ui
    await user.open('/archer-pools')
    sel = next(e for e in user.client.elements.values()
               if isinstance(e, _ui.select) and e.props.get("label") == "Attack with")
    assert sel.options == {0: "Long Bow"}, "the arrow row is excluded, index preserved"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_nocked_arrow_shows_its_damage_and_adds_no_dice(user) -> None:
    """The arrow control is REFERENCE. core p.330 gives arrows a base damage and a soak
    clause and no accuracy at all, and this build derives no damage (decision 0008) —
    so the pool totals must be identical before and after nocking one."""
    from nicegui import ui as _ui
    await user.open('/archer-pools')
    weapon_sel = next(e for e in user.client.elements.values()
                      if isinstance(e, _ui.select)
                      and e.props.get("label") == "Attack with")
    weapon_sel.set_value(0)
    await user.should_see("Nocked arrow")
    before = sorted(e.text for e in user.client.elements.values()
                    if isinstance(e, _ui.label) and "Archery" in (e.text or ""))
    arrow_sel = next(e for e in user.client.elements.values()
                     if isinstance(e, _ui.select)
                     and e.props.get("label") == "Nocked arrow")
    assert arrow_sel.options == {1: "Frog Crotch Arrow"}
    arrow_sel.set_value(1)
    await user.should_see("Frog Crotch Arrow: Strength +4L base damage")
    await user.should_see("Damage only — an arrow adds no dice to the attack pool.")
    after = sorted(e.text for e in user.client.elements.values()
                   if isinstance(e, _ui.label) and "Archery" in (e.text or ""))
    assert before == after, "nocking an arrow changed a pool"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_arrow_control_is_hidden_for_a_weapon_that_fires_nothing(user) -> None:
    """A duelist with a short sword and no ammunition never sees it."""
    await user.open('/pools')
    await user.should_not_see("Nocked arrow")
