"""The Qt Play page (exalted_builder/qt/play.py) — the in-play tracker.

Covers what the widget decides for itself: that the health track is drawn to the
DERIVED box count and cycles a box through the four marks, that merely opening the tab
writes no PlayState onto a never-played character, that the spent-mote inputs clamp to
their pool, that a splat gets Clarity or Limit but never both, that the fatigue counter
appears only where it can matter, and that the dice-pool column re-derives when a mark
or a switch moves.

⚠ **This tab is the ONE approved exception to the collection layout** — a tracker has
nothing to select, so there is no table and no detail pane here. Tests address named
boxes (`play.health.3`, `play.limit.0`) and named inputs, never a position in a
`findChildren` list: the tab is full of same-shaped boxes and an index picks whichever
happened to be built first.

⚠ Play-state is validation-isolated (decision 0006). Nothing here should assert that a
mark changed a budget, a pool maximum or a validation issue — `tests/test_play.py`
enforces the direction.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QCheckBox, QComboBox, QLabel, QPushButton, QSpinBox

from exalted_builder.engine import derive, lifecycle
from exalted_builder.models.character import (Armor, Character, Damage, PlayState,
                                              Weapon)
from exalted_builder.models.rules import VirtueName
from exalted_builder.qt.play import PlayPage
from exalted_builder.ui import view as viewmod


@pytest.fixture
def make_page(ruleset, qtbot):
    """Build a PlayPage over `character`. A FIXTURE rather than a helper because
    pytest-qt's `qtbot` is what constructs the QApplication and owns widget cleanup."""
    def build(character, notes=None):
        sink = notes if notes is not None else []
        page = PlayPage(ruleset, {"char": character},
                        notify=lambda text, kind="info": sink.append((kind, text)))
        qtbot.addWidget(page)
        return page
    return build


def _solar(**kw) -> Character:
    c = Character(id="c.play", name="Test", exalt_type="Solar", caste="dawn",
                  essence_rating=2)
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def _named(page, prefix, kind=QPushButton):
    """Every widget of `kind` whose objectName starts with `prefix`, in build order."""
    return [w for w in page.findChildren(kind)
            if w.objectName().startswith(prefix)]


def _one(page, name, kind=QPushButton):
    return next(w for w in page.findChildren(kind) if w.objectName() == name)


def _texts(page, kind=QLabel):
    return [w.text() for w in page.findChildren(kind)]


# ---------------------------------------------------------------- health ---- #

def test_the_health_track_is_drawn_to_the_derived_box_count(ruleset, make_page):
    char = _solar()
    expected = len(derive.derive(ruleset, char).health_levels)
    assert len(_named(make_page(char), "play.health.")) == expected


def test_a_health_box_cycles_through_the_four_marks_and_wraps(make_page):
    char = _solar()
    page = make_page(char)
    for expected in (Damage.BASHING, Damage.LETHAL, Damage.AGGRAVATED, None):
        _one(page, "play.health.2").click()
        assert char.play.health[2] is expected


def test_opening_the_tab_writes_no_play_state(make_page):
    """⚠ A character who has never been played must still save clean. Rendering reads
    through `char.play or PlayState()`; only a click creates the state."""
    char = _solar()
    make_page(char)
    assert char.play is None


def test_the_wound_penalty_readout_follows_the_deepest_mark(make_page):
    char = _solar()
    page = make_page(char)
    assert _one(page, "play.woundPenalty", QLabel).text() == "Wound penalty: none"
    _one(page, "play.health.3").click()
    label = _one(page, "play.woundPenalty", QLabel).text()
    assert label != "Wound penalty: none"


def test_clear_damage_wipes_every_mark(make_page):
    char = _solar(play=PlayState(health=[Damage.LETHAL, Damage.BASHING]))
    page = make_page(char)
    next(b for b in page.findChildren(QPushButton)
         if b.text() == "Clear damage").click()
    assert char.play.health == []


def test_marks_longer_than_the_track_do_not_overflow_the_row(ruleset, make_page):
    """A track can SHRINK (a Charm-granted level dropped), and the stored marks are
    positional. The extra marks are not drawn; nothing indexes past the boxes."""
    char = _solar()
    n = len(derive.derive(ruleset, char).health_levels)
    char.play = PlayState(health=[Damage.LETHAL] * (n + 4))
    page = make_page(char)
    assert len(_named(page, "play.health.")) == n


# ----------------------------------------------------------------- motes ---- #

def test_the_mote_inputs_are_capped_at_the_derived_pools(ruleset, make_page):
    char = _solar()
    d = derive.derive(ruleset, char)
    page = make_page(char)
    assert _one(page, "play.motes_personal_spent", QSpinBox).maximum() == d.essence_personal
    assert _one(page, "play.motes_peripheral_spent", QSpinBox).maximum() == d.essence_peripheral


def test_spending_motes_writes_through_and_moves_only_its_own_readout(ruleset, make_page):
    char = _solar()
    page = make_page(char)
    _one(page, "play.motes_personal_spent", QSpinBox).setValue(3)
    assert char.play.motes_personal_spent == 3
    cap = derive.derive(ruleset, char).essence_personal
    assert (_one(page, "play.motes_personal_spent.available", QLabel).text()
            == f"{cap - 3} / {cap} available")


def test_clear_motes_resets_both_pools_and_leaves_the_rest_alone(make_page):
    """⚠ MOTES ONLY. Willpower, health and Limit recover on their own terms, so the
    tracker must not bulk-reset them — that would be it deciding a recovery rule."""
    char = _solar(play=PlayState(motes_personal_spent=4, motes_peripheral_spent=6,
                                 willpower_spent=2, limit=3,
                                 health=[Damage.LETHAL]))
    page = make_page(char)
    next(b for b in page.findChildren(QPushButton)
         if b.text() == "Clear motes spent").click()
    assert (char.play.motes_personal_spent, char.play.motes_peripheral_spent) == (0, 0)
    assert (char.play.willpower_spent, char.play.limit) == (2, 3)
    assert char.play.health == [Damage.LETHAL]


def test_a_merged_pool_renders_one_track_not_a_dead_personal_box(make_page, monkeypatch):
    """"All of which is considered Peripheral" (p.41) — a Personal box would sit at a
    permanent 0/0 and read as broken, so the rule goes in the heading instead."""
    import exalted_builder.ui.view as viewmod
    real = viewmod.build_play_view

    def merged(rs, ch):
        view = real(rs, ch)
        view.single_pool = True
        return view

    monkeypatch.setattr(viewmod, "build_play_view", merged)
    page = make_page(_solar())
    assert not _named(page, "play.motes_personal_spent", QSpinBox)
    assert any("SINGLE POOL" in t for t in _texts(page))


# ------------------------------------------------- willpower / limit -------- #

def test_the_willpower_track_runs_to_permanent_willpower(ruleset, make_page):
    char = _solar()
    page = make_page(char)
    assert (len(_named(page, "play.willpower_spent."))
            == derive.derive(ruleset, char).willpower)


def test_clicking_the_top_filled_box_clears_it(make_page):
    """The dot-track rule: clicking the box you are on steps back rather than being a
    no-op, so a mis-click is undoable without a second control."""
    char = _solar(virtues={VirtueName.COMPASSION: 3, VirtueName.CONVICTION: 3,
                           VirtueName.TEMPERANCE: 1, VirtueName.VALOR: 1})
    page = make_page(char)
    _one(page, "play.willpower_spent.2").click()
    assert char.play.willpower_spent == 3
    _one(page, "play.willpower_spent.2").click()
    assert char.play.willpower_spent == 2


def test_a_solar_gets_limit_and_no_clarity(make_page):
    page = make_page(_solar())
    assert len(_named(page, "play.limit.")) == 10
    assert not _named(page, "play.clarity_temporary.")


def test_an_alchemical_gets_clarity_and_no_limit(ruleset, make_page):
    char = Character(id="c.alch", name="Gear", exalt_type="Alchemical",
                     caste="orichalcum", essence_rating=2)
    if not derive.uses_clarity(ruleset, char):
        pytest.skip("this build's Alchemical definition does not carry Clarity")
    page = make_page(char)
    assert len(_named(page, "play.clarity_temporary.")) == derive.CLARITY_MAX
    assert not _named(page, "play.limit.")


def test_the_limit_track_is_drawn_to_the_derived_maximum(ruleset, make_page):
    """Greater Curse and permanent Resonance shorten the track, so Limit Break arrives
    sooner — the boxes follow `derive.limit_max`, never a hardcoded 10."""
    char = _solar(limit_permanent=3)
    page = make_page(char)
    assert len(_named(page, "play.limit.")) == derive.limit_max(ruleset, char)


# --------------------------------------------------------------- fatigue ---- #

def test_no_fatigue_counter_without_armour_or_points(make_page):
    assert not _named(make_page(_solar()), "play.fatigue", QSpinBox)


def test_the_fatigue_counter_appears_for_worn_armour(make_page):
    char = _solar(armor=[Armor(name="Buff Jacket", soak_bashing=3, soak_lethal=2,
                               fatigue=1)])
    assert _named(make_page(char), "play.fatigue", QSpinBox)


def test_accumulated_points_keep_the_counter_after_the_armour_comes_off(make_page):
    """Fatigue points dissipate with REST, not with undressing (p.332), so a character
    who has stripped still needs to see the clock."""
    char = _solar(play=PlayState(fatigue=2))
    assert _named(make_page(char), "play.fatigue", QSpinBox)


def test_setting_fatigue_writes_through(make_page):
    char = _solar(armor=[Armor(name="Buff Jacket", fatigue=1)])
    page = make_page(char)
    _one(page, "play.fatigue", QSpinBox).setValue(3)
    assert char.play.fatigue == 3


# ------------------------------------------------------------ dice pools ---- #

def test_every_pool_row_shows_its_breakdown(make_page):
    """⚠ Decision 0016 narrowed 0008 only on the promise that every pool is ITEMISED.
    A column of bare totals is precisely the surface 0008 rejected."""
    page = make_page(_solar())
    labels = _texts(page)
    # The compact breakdown is a signed-term string; at least one must reach the page.
    assert any(t.startswith("+") and " " in t for t in labels)


def test_the_exclusions_block_is_always_present(make_page):
    """NOT collapsible and NOT dismissible — it is the mitigation 0016 accepted."""
    labels = _texts(make_page(_solar()))
    assert "These are BASE pools. They do not include:" in labels
    assert "No dice are rolled here, and nothing is resolved." in labels


def test_the_wound_switch_appears_only_once_there_is_damage(make_page):
    char = _solar()
    page = make_page(char)
    assert not _named(page, "play.include.wound", QCheckBox)
    _one(page, "play.health.3").click()
    assert _named(page, "play.include.wound", QCheckBox)


def test_the_wound_switch_reaches_both_columns(make_page):
    """One `_pool_state` drives the roll list AND the custom block in the other column,
    so the switch cannot go on working where you can see it and stop where you cannot —
    the silent failure the webapp's version of this shares."""
    char = _solar()
    page = make_page(char)
    _one(page, "play.health.3").click()
    assert any("wnd" in t for t in _texts(page))
    _one(page, "play.include.wound", QCheckBox).setChecked(False)
    assert not any("wnd" in t for t in _texts(page))


def test_a_printed_rider_rides_as_a_tooltip(ruleset, make_page):
    """`PoolRow.note` is a printed rider, sometimes a paragraph. Sixty rows each showing
    one is a wall of text on the surface whose whole job is scanning — but the webapp
    rendered it NOWHERE, so on-screen it was a field with no reader at all."""
    page = make_page(_solar())
    if not any(r.note for _, rows in
               viewmod.build_pool_sidebar(ruleset, _solar()).groups for r in rows):
        pytest.skip("no roll in this catalogue carries a printed rider")
    assert any(w.toolTip() for w in page.findChildren(QLabel)
               if w.text().startswith("+"))


def test_an_unarmed_character_is_told_so_rather_than_offered_a_weapon(make_page):
    page = make_page(_solar())
    assert not _named(page, "play.weapon", QComboBox)
    assert "No weapon owned — the attack rows are unarmed." in _texts(page)


def test_choosing_a_weapon_re_derives_the_rows(make_page):
    char = _solar(weapons=[Weapon(name="Daiklave", accuracy=3, damage=5)])
    page = make_page(char)
    combo = _one(page, "play.weapon", QComboBox)
    before = _texts(page)
    combo.setCurrentIndex(combo.findData(0))
    assert _texts(page) != before


def test_a_weapon_deleted_elsewhere_drops_the_stale_selection(make_page):
    """⚠ `_pool_state` outlives the weapon list it indexes — the player can delete the
    weapon on the Gear tab between two rebuilds. The index that survives would name a
    DIFFERENT weapon, so it is cleared, not remapped."""
    char = _solar(weapons=[Weapon(name="Daiklave"), Weapon(name="Short Sword")])
    page = make_page(char)
    combo = _one(page, "play.weapon", QComboBox)
    combo.setCurrentIndex(combo.findData(1))
    assert page._pool_state["weapon"] == 1
    char.weapons.pop()
    page.reload()
    assert page._pool_state["weapon"] is None


def test_the_custom_pool_offers_every_attribute_and_ability(make_page):
    """A custom pool is for whatever the table is doing, so nothing is filtered by
    caste, favouring or rating."""
    page = make_page(_solar())
    assert _one(page, "play.custom.attribute", QComboBox).count() == 9
    assert _one(page, "play.custom.ability", QComboBox).count() == 25


def test_the_custom_pool_re_derives_on_a_trait_change(make_page):
    page = make_page(_solar())
    before = _texts(page)
    combo = _one(page, "play.custom.ability", QComboBox)
    combo.setCurrentIndex((combo.currentIndex() + 4) % combo.count())
    assert _texts(page) != before


def test_the_agility_switch_appears_only_where_armour_could_bite(make_page):
    """p.332's discretionary clause is the Storyteller's call, so it is a control — but
    only for a character actually wearing something that penalises mobility."""
    assert not _named(make_page(_solar()), "play.custom.agility", QCheckBox)
    char = _solar(armor=[Armor(name="Lamellar", mobility_penalty=-2)])
    assert _named(make_page(char), "play.custom.agility", QCheckBox)


# ------------------------------------------------------------- rebuilding --- #

def test_a_thrashed_rebuild_leaks_no_widgets(make_page):
    """⚠ Test a teardown by THRASHING it and counting live descendants — a single
    rebuild passes while leaking (`qt/layout.py`)."""
    page = make_page(_solar())
    before = len(page.findChildren(QLabel))
    for _ in range(8):
        page.reload()
    assert len(page.findChildren(QLabel)) == before


def test_the_tab_is_live_on_both_sides_of_the_lock(ruleset, make_page):
    """Play happens after creation, but the tracker never blocks: a locked and an
    unlocked character both get a full track."""
    char = _solar()
    unlocked = len(_named(make_page(char), "play.health."))
    lifecycle.lock_chargen(char, ruleset)
    assert len(_named(make_page(char), "play.health.")) == unlocked
