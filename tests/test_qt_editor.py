"""The Qt Identity + Traits pages (exalted_builder/qt/editor.py) — retained-mode
trait surface.

Covers the DotTrack control (chargen free setter, post-lock XP buyer), the two pages
(Identity's structural + bio + caste info; Traits' favoured picks + dot tracks), the
structural cascades and the scroll-hold. The post-lock downward dialog is exercised
only through its `_buy` preconditions — a modal QDialog.exec() would block a headless
test.
"""

import pytest

# ⚠ PySide6 is the OPTIONAL `qt` extra (pyproject), so it is legitimately absent on a
# machine that only runs the webapp. Skip the module rather than letting a bare import
# turn into a COLLECTION ERROR — that kills the whole run, not just these tests.
pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtWidgets import QApplication, QPushButton

from exalted_builder.engine import advancement, lifecycle
from exalted_builder.models.character import AbilityName, AttributeName, Character
from exalted_builder.qt.editor import DotTrack, IdentityPage, TraitsPage, _FavoredPicker


def _identity(ruleset, character, **kw):
    return IdentityPage(ruleset, {"char": character},
                        notify=lambda *a, **k: None,
                        on_theme_change=lambda: None, **kw)


def _traits(ruleset, character, **kw):
    return TraitsPage(ruleset, {"char": character},
                      notify=lambda *a, **k: None, **kw)


# --------------------------------------------------------------------------- #
# DotTrack
# --------------------------------------------------------------------------- #

def test_dot_track_renders_pips_and_clicks_set(qtbot):
    value = {"v": 1}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000")
    qtbot.addWidget(track)
    assert len(track._pips) == 5
    track._click(4)
    assert value["v"] == 4
    assert len(track._pips) == 5


def test_dot_track_shows_enough_pips_to_step_a_too_high_value_down(qtbot):
    value = {"v": 7}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000")
    qtbot.addWidget(track)
    # hi is 5 but the value is 7 — the row must offer pip 7 so it can be clicked down.
    assert len(track._pips) == 7
    track._click(7)          # stepping down clamps to the hard ceiling of 5
    assert value["v"] == 5


def test_dot_track_clicking_current_top_steps_down(qtbot):
    value = {"v": 3}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000")
    qtbot.addWidget(track)
    track._click(3)
    assert value["v"] == 2


def test_dot_track_clamps_to_lo(qtbot):
    value = {"v": 2}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     1, 5, accent="#000000")
    qtbot.addWidget(track)
    track._click(1)          # step down from 2 → 1
    assert value["v"] == 1
    track._click(1)          # step down from 1 → clamped at lo 1
    assert value["v"] == 1


def test_favored_picker_adds_and_removes_chips(qtbot):
    changes = []
    picker = _FavoredPicker({"melee": "Melee", "dodge": "Dodge", "brawl": "Brawl"},
                            ["melee"], 3, "#000000", lambda p: changes.append(list(p)))
    qtbot.addWidget(picker)
    # The combo holds every option (so clicking shows the list) and starts blank.
    assert picker.combo.count() == 3
    assert picker.combo.currentText() == ""
    # typing a valid name + Enter adds it as a chip and fires on_change.
    picker.combo.lineEdit().setText("Dodge")
    picker.combo.lineEdit().returnPressed.emit()
    assert changes[-1] == ["melee", "dodge"]
    assert picker._picked == ["melee", "dodge"]
    # removing a chip fires on_change again.
    picker._remove("melee")
    assert changes[-1] == ["dodge"]


def test_dot_track_fires_on_change(qtbot):
    calls = []
    value = {"v": 1}
    track = DotTrack(lambda: value["v"], lambda v: value.__setitem__("v", v),
                     0, 5, accent="#000000", on_change=lambda: calls.append(1))
    qtbot.addWidget(track)
    track._click(3)
    assert calls == [1]


# --------------------------------------------------------------------------- #
# The two pages — chargen side
# --------------------------------------------------------------------------- #

def test_pages_build_for_a_fresh_character(qtbot, ruleset):
    from PySide6.QtWidgets import QLabel
    char = Character(id="char.new")
    idp = _identity(ruleset, char)
    trp = _traits(ruleset, char)
    qtbot.addWidget(idp)
    qtbot.addWidget(trp)
    id_text = " | ".join(l.text() for l in idp.findChildren(QLabel))
    tr_text = " | ".join(l.text() for l in trp.findChildren(QLabel))
    assert "Identity" in id_text and "Biography" in id_text and "Caste" in id_text
    assert "Favoured Picks" in tr_text and "Attributes" in tr_text


def test_identity_bio_fields_bind_to_the_model(qtbot, ruleset):
    from PySide6.QtWidgets import QLineEdit, QTextEdit
    char = Character(id="char.new")
    page = _identity(ruleset, char)
    qtbot.addWidget(page)
    edits = page.findChildren(QLineEdit)
    # the bio fields are the trailing seven (Name/Concept/Anima and Nature's internal
    # line edit come first); Sex is the first of them
    edits[-7].setText("M")
    assert char.sex == "M"
    backs = page.findChildren(QTextEdit)      # Description, Backstory, Notes
    backs[1].setPlainText("Born in the River Province")
    assert char.backstory == "Born in the River Province"


def test_traits_changed_updates_ability_tally(qtbot, ruleset):
    char = Character(id="char.new")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    before = _ability_tally_text(page)
    char.abilities[AbilityName.MELEE] = 3
    page._changed()
    after = _ability_tally_text(page)
    assert before != after


def test_identity_structural_switch_cascades(qtbot, ruleset):
    char = Character(id="char.new")
    page = _identity(ruleset, char)
    qtbot.addWidget(page)
    page.set_exalt_type("Dragon-Blooded")
    assert char.exalt_type == "Dragon-Blooded"
    assert char.caste in {cd.id for cd in ruleset.castes.values()
                          if cd.exalt_type == "Dragon-Blooded"}
    assert char.origin == "dynastic"
    # Mortal has no castes — switching clears the stale one.
    page.set_exalt_type("Mortal")
    assert char.exalt_type == "Mortal"
    assert char.caste == ""
    assert char.origin == "heroic"


def test_traits_post_lock_buy_spends_xp(qtbot, ruleset):
    char = Character(id="char.new")
    advancement.add_xp(char, 50)
    lifecycle.lock_chargen(char, ruleset)
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    available = advancement.xp_available(char)
    page._buy("attributes.strength", 1, 2, lambda: None)
    assert char.attributes[AttributeName.STRENGTH] == 2
    assert advancement.xp_available(char) < available


def test_traits_pre_lock_buy_falls_through(qtbot, ruleset):
    char = Character(id="char.new")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    # Pre-lock the buy handler returns False so the track free-sets instead.
    assert page._buy("attributes.strength", 1, 2, lambda: None) is False


def test_traits_reload_holds_scroll_position(qtbot, ruleset):
    # A body rebuild (here: adding a craft) can yank the scrollbar, so reload must
    # hold the scroll position where it was.
    char = Character(id="c", exalt_type="Solar")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    for _ in range(6):
        QApplication.processEvents()
    bar = page._body_scroll.verticalScrollBar()
    assert bar.maximum() > 0                # the form really overflows
    bar.setValue(bar.maximum() // 2)
    saved = bar.value()
    page.add_craft()                        # a body reload
    for _ in range(6):
        QApplication.processEvents()
    assert bar.value() == saved


def test_traits_removing_a_favored_chip_holds_scroll(qtbot, ruleset):
    # The nasty one: deleting a FOCUSED chip (its ✕) makes Qt's focus handling
    # scroll the body to whatever focusable widget it picks next — a QSpinBox deep
    # in the form. The picker parks focus on its combo before deleting, and the
    # reload's scroll-hold catches the residue, so the view must stay put.
    char = Character(id="c", exalt_type="Solar")
    char.favored_abilities = [AbilityName.MELEE, AbilityName.DODGE,
                              AbilityName.ARCHERY]
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    QApplication.processEvents()
    qtbot.wait(250)                       # let the construction scroll-hold release
    bar = page._body_scroll.verticalScrollBar()
    assert bar.maximum() > 0
    bar.setValue(bar.maximum() // 2)
    QApplication.processEvents()
    saved = bar.value()
    picker = page.findChildren(_FavoredPicker)[0]
    picker.findChildren(QPushButton)[0].setFocus()     # as a real click would
    QApplication.processEvents()
    picker._remove("melee")                # the whole removal path
    for _ in range(8):
        QApplication.processEvents()
    assert bar.value() == saved


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _ability_tally_text(page) -> str:
    from PySide6.QtWidgets import QLabel
    for label in page._body_container.findChildren(QLabel):
        if "dots spent" in label.text():
            return label.text()
    return ""


def test_trait_columns_do_not_inherit_the_column_gap_as_row_spacing(ruleset, qtbot):
    """⚠ A nested layout whose spacing is unset (-1) INHERITS its parent's.

    The Attributes and Abilities panels put three columns in a QHBoxLayout with a 24px
    gap between them; each column is a bare QVBoxLayout, which silently took that 24 as
    its ROW spacing. Attribute rows sat 41px apart against the Virtues' 21, which reads
    as the card trying to fill itself vertically (human, 2026-08-22).

    Pins the MECHANISM — every column's spacing is the deliberate row spacing and none
    is the column gap — rather than a pixel measurement, which would rot the first time
    a font changed.
    """
    from PySide6.QtWidgets import QVBoxLayout
    from exalted_builder.qt.editor import _ROW_SPACING, _Panel

    page = TraitsPage(ruleset, {"char": Character(id="c.sp", exalt_type="Solar",
                                                  caste="dawn")})
    qtbot.addWidget(page)
    columns = []
    for card in page.findChildren(_Panel):
        for lay in card.findChildren(QVBoxLayout):
            # A trait column: a vertical layout holding rows, nested inside a card.
            if lay.count() > 1 and lay is not card.layout():
                columns.append(lay)
    assert columns, "no nested trait columns found — has the layout changed?"
    assert all(lay.spacing() == _ROW_SPACING for lay in columns), \
        [lay.spacing() for lay in columns]
    assert _ROW_SPACING != 24, "the column gap must not double as the row spacing"


# --------------------------------------------------------------------------- #
# the shell hook contract
# --------------------------------------------------------------------------- #

def test_a_structural_change_pings_the_shell(qtbot, ruleset):
    """⚠ `reload()` is what a structural change does, and it has to move the shell's
    readout bar.

    Species 1 of the house bug: `_changed()` pinged `on_change`, `reload()` did not,
    and the ten reload call sites — Exalt type, caste, origin, upbringing, the two
    favoured setters, add/remove craft, `_do_trait`, `_lower_willpower` — all changed
    the bonus-point spend while the bar kept showing the previous answer. Asserting on
    the PAGE would have passed: its own body rebuilt correctly every time.
    """
    pings = []
    char = Character(id="char.new")
    page = _identity(ruleset, char, on_change=lambda: pings.append(1))
    qtbot.addWidget(page)
    before = len(pings)
    page.set_exalt_type("Dragon-Blooded")
    assert len(pings) > before, "a structural change left the shell readout stale"


# --------------------------------------------------------------------------- #
# permanent Resonance
# --------------------------------------------------------------------------- #

_DEATH_TAINT = "mf.death-taint"


def _tainted_abyssal(*, xp=0, permanent=0):
    from exalted_builder.models.character import MeritFlawPurchase as MP
    char = Character(id="c.ab", exalt_type="Abyssal", caste="dusk", essence_rating=3,
                     merits_flaws=[MP(merit_id=_DEATH_TAINT, points=4)])
    char.limit_permanent = permanent
    char.chargen_locked = True
    advancement.add_xp(char, xp)
    return char


def _button(page, prefix: str):
    return next((b for b in page._body_container.findChildren(QPushButton)
                 if b.text().startswith(prefix)), None)


def test_traits_offers_permanent_resonance_only_where_the_cap_is_nonzero(qtbot, ruleset):
    """The panel is gated on `permanent_limit_cap`, which is the engine's way of asking
    "does this character hold Death's Taint" without any caller naming a Merit id."""
    plain = Character(id="c.s", exalt_type="Solar", caste="dawn")
    lifecycle.lock_chargen(plain, ruleset)
    assert _button(_traits(ruleset, plain), "Gain") is None
    assert _button(_traits(ruleset, _tainted_abyssal()), "Gain") is not None


def test_permanent_resonance_is_not_offered_before_the_lock(qtbot, ruleset):
    """It is gained and shed through the XP ledger, so it has no pre-lock gesture."""
    from exalted_builder.models.character import MeritFlawPurchase as MP
    char = Character(id="c.ab", exalt_type="Abyssal", caste="dusk", essence_rating=3,
                     merits_flaws=[MP(merit_id=_DEATH_TAINT, points=4)])
    assert _button(_traits(ruleset, char), "Gain") is None


def test_gaining_permanent_resonance_from_the_panel_is_free(qtbot, ruleset):
    char = _tainted_abyssal()
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    available = advancement.xp_available(char)
    _button(page, "Gain").click()
    assert char.limit_permanent == 1
    assert advancement.xp_available(char) == available


def test_shedding_permanent_resonance_from_the_panel_spends_xp(qtbot, ruleset):
    from exalted_builder.engine import merits as merits_engine
    char = _tainted_abyssal(xp=10, permanent=2)
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    available = advancement.xp_available(char)
    _button(page, "Shed").click()
    assert char.limit_permanent == 1
    assert available - advancement.xp_available(char) == \
        merits_engine.PERMANENT_RESONANCE_SHED_XP


def test_shedding_past_zero_warns_instead_of_raising(qtbot, ruleset):
    """`_do_trait` catches AdvancementError and notifies — the panel must not let an
    engine refusal escape as a crash."""
    warnings = []
    char = _tainted_abyssal(xp=10)
    page = TraitsPage(ruleset, {"char": char},
                      notify=lambda text, kind="info": warnings.append((text, kind)))
    qtbot.addWidget(page)
    _button(page, "Shed").click()
    assert char.limit_permanent == 0
    assert warnings and warnings[0][1] == "warning"


# --------------------------------------------------------------------------- #
# the Virtue Flaw
# --------------------------------------------------------------------------- #
# ⚠ Every lookup below is BY OBJECT NAME. The first draft of these tests located the
# sample-Flaw dropdown by walking out to the label's parent widget and taking the first
# QComboBox it held — which is the Flawed Virtue box, because a QHBoxLayout does not
# reparent, so every combo in the panel shares one parent. It asserted a true thing
# about the wrong widget and failed on a Virtue id.

from PySide6.QtWidgets import QComboBox, QLineEdit

from exalted_builder.models.character import VirtueName


def _named(page, name: str, kind):
    return page._body_container.findChild(kind, name)


def test_virtue_flaw_panel_is_splat_gated(qtbot, ruleset):
    """⚠ Having a Virtue Flaw is NOT the same question as having a Limit track — a
    Sidereal has Paradox and no flawed Virtue, so a gate written on the limit label
    would offer them one."""
    solar = Character(id="c.s", exalt_type="Solar", caste="dawn")
    assert _named(_traits(ruleset, solar), "virtue_flaw.virtue", QComboBox) is not None
    sid = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    assert _named(_traits(ruleset, sid), "virtue_flaw.virtue", QComboBox) is None


def test_virtue_flaw_starts_unset_rather_than_defaulting(qtbot, ruleset):
    """Qt has no empty state for a combo, so an unset Flaw needs an explicit blank —
    landing on Compassion would write a pick the player never made."""
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    assert _named(page, "virtue_flaw.virtue", QComboBox).currentData() is None
    assert char.virtue_flaw is None


def test_picking_a_flawed_virtue_rebuilds_the_sample_list(qtbot, ruleset):
    """⚠ The sample list is built from the flawed Virtue, so setting the Virtue has to
    rebuild — otherwise the dropdown keeps offering the OLD Virtue's Flaws and is wrong
    exactly while it is being read."""
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.set_virtue_flaw_virtue(VirtueName.VALOR)
    assert char.virtue_flaw.virtue == VirtueName.VALOR
    samples = _named(page, "virtue_flaw.sample", QComboBox)
    if samples is None:
        pytest.skip("no sample Flaws are authored for Valor")
    offered = {samples.itemData(i) for i in range(samples.count())} - {None}
    assert offered
    assert all(ruleset.virtue_flaw_catalog[fid].virtue == VirtueName.VALOR
               for fid in offered), "the sample list offers another Virtue's Flaws"
    # and it moves with the Virtue rather than sticking
    page.set_virtue_flaw_virtue(VirtueName.COMPASSION)
    moved = _named(page, "virtue_flaw.sample", QComboBox)
    if moved is not None:
        now = {moved.itemData(i) for i in range(moved.count())} - {None}
        assert now != offered


def test_a_sample_flaw_copies_its_text_rather_than_its_id(qtbot, ruleset):
    """Decision 0007's line: the player edits this text, so storing the id would make an
    edited Flaw claim to be the printed one."""
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.set_virtue_flaw_virtue(VirtueName.VALOR)
    sample = next((f for f in ruleset.virtue_flaw_catalog.values()
                   if f.virtue == VirtueName.VALOR and f.description), None)
    if sample is None:
        pytest.skip("no Valor sample Flaw carries printed text")
    page.set_virtue_flaw_sample(sample.id)
    assert char.virtue_flaw.description == sample.description
    assert sample.id not in char.model_dump_json()


def test_the_flawed_virtue_freezes_at_the_lock(qtbot, ruleset):
    """One of the eight chargen choices frozen once locked — greyed but readable."""
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    lifecycle.lock_chargen(char, ruleset)
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    combo = _named(page, "virtue_flaw.virtue", QComboBox)
    assert combo is not None, "the panel must stay READABLE after the lock"
    assert not combo.isEnabled()


def test_editing_the_description_does_not_rebuild_under_the_cursor(qtbot, ruleset):
    """A per-keystroke reload would take the focused QLineEdit out from under the
    typist, so the description writes straight to the model. Asserts widget IDENTITY
    survives the edit — asserting the text would pass either way."""
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.set_virtue_flaw_virtue(VirtueName.VALOR)
    box = _named(page, "virtue_flaw.description", QLineEdit)
    box.setText("Charges the biggest thing in the room")
    assert char.virtue_flaw.description == "Charges the biggest thing in the room"
    assert _named(page, "virtue_flaw.description", QLineEdit) is box


# --------------------------------------------------------------------------- #
# bonus health levels
# --------------------------------------------------------------------------- #

def test_health_tier_boxes_show_the_printed_track_on_a_fresh_character(qtbot, ruleset):
    """⚠ The stored list is a DELTA, so an untouched character holds NO entries — the
    boxes must still read the printed counts, not zero."""
    from PySide6.QtWidgets import QSpinBox
    from exalted_builder.engine import health_actions
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    assert not char.health_bonus_levels
    for penalty, base in health_actions.BASE_COUNTS.items():
        if penalty not in health_actions.EDITABLE_TIERS:
            continue
        spin = _named(page, f"health.{penalty}", QSpinBox)
        assert spin is not None and spin.value() == base


def test_raising_a_health_tier_adds_levels_and_lowering_removes_them(qtbot, ruleset):
    from PySide6.QtWidgets import QSpinBox
    from exalted_builder.engine import derive, health_actions
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    base = health_actions.BASE_COUNTS[-1]
    before = len(derive.health_track(char))
    _named(page, "health.-1", QSpinBox).setValue(base + 2)
    assert health_actions.level_total(char, -1) == base + 2
    assert len(derive.health_track(char)) == before + 2
    _named(page, "health.-1", QSpinBox).setValue(base - 1)
    assert health_actions.level_total(char, -1) == base - 1
    assert len(derive.health_track(char)) == before - 1


def test_editing_one_health_tier_leaves_the_others_alone(qtbot, ruleset):
    from PySide6.QtWidgets import QSpinBox
    from exalted_builder.engine import health_actions
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    _named(page, "health.-2", QSpinBox).setValue(9)
    _named(page, "health.0", QSpinBox).setValue(4)
    assert health_actions.level_total(char, -2) == 9
    assert health_actions.level_total(char, 0) == 4
    assert health_actions.level_total(char, -4) == health_actions.BASE_COUNTS[-4]


# --------------------------------------------------------------------------- #
# specialties
# --------------------------------------------------------------------------- #

def _spec_rows(page):
    from PySide6.QtWidgets import QPushButton
    return [b for b in page._body_container.findChildren(QPushButton)
            if b.text() == "✕"]


def test_a_specialty_is_an_instance_not_a_rated_track(qtbot, ruleset):
    """⚠ The ruling (human, 2026-07-31): you do not RAISE a specialty, you take the
    same one again. Taking Swords twice must be two rows, and there must be no dot
    track offering to raise one."""
    from exalted_builder.models.character import Specialty
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    char.specialties = [Specialty(ability=AbilityName.MELEE, name="Swords", rating=1),
                        Specialty(ability=AbilityName.MELEE, name="Swords", rating=1)]
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    assert len(_spec_rows(page)) == 2


def test_adding_a_specialty_pre_lock_appends_a_blank_row(qtbot, ruleset):
    """⚠ The cap is deliberately NOT enforced on the add: the row starts on Melee and
    is retargeted, so blocking here would block it on the wrong Ability."""
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    for _ in range(4):
        page.add_spec()
    assert len(char.specialties) == 4
    assert all(sp.ability == AbilityName.MELEE for sp in char.specialties)


def test_retargeting_a_specialty_re_runs_validation(qtbot, ruleset):
    """⚠ The stale-error trap. Four blank rows land on Melee and put a `specialty-cap`
    error on screen; retargeting one fixes the MODEL, and without a re-run the old
    error stays up — three Melee plus three Dodge reading back as "Melee has 4"."""
    pings = []
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = TraitsPage(ruleset, {"char": char}, notify=lambda *a, **k: None,
                      on_change=lambda: pings.append(1))
    qtbot.addWidget(page)
    for _ in range(4):
        page.add_spec()
    combos = [c for c in page._body_container.findChildren(QComboBox)
              if c.count() == len(list(AbilityName)) and c.currentIndex() ==
              list(AbilityName).index(AbilityName.MELEE)]
    assert combos, "no specialty ability combo found"
    before = len(pings)
    combos[-1].setCurrentIndex(combos[-1].findData(AbilityName.DODGE))
    assert char.specialties[-1].ability == AbilityName.DODGE
    assert len(pings) > before, "the retarget left the stale cap error on screen"


def test_specialties_go_read_only_at_the_lock(qtbot, ruleset):
    """Removal in play is undo, not deletion — the same reason the Charms rows are."""
    from exalted_builder.models.character import Specialty
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    char.specialties = [Specialty(ability=AbilityName.MELEE, name="Swords", rating=1)]
    lifecycle.lock_chargen(char, ruleset)
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    assert not _spec_rows(page), "existing specialties are still deletable post-lock"
    assert _named(page, "specialty.new", QLineEdit) is not None


def test_buying_a_specialty_post_lock_spends_xp(qtbot, ruleset):
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    advancement.add_xp(char, 50)
    lifecycle.lock_chargen(char, ruleset)
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    available = advancement.xp_available(char)
    _named(page, "specialty.new", QLineEdit).setText("Swords")
    next(b for b in page._body_container.findChildren(QPushButton)
         if b.text() == "Buy").click()
    assert [sp.name for sp in char.specialties] == ["Swords"]
    assert advancement.xp_available(char) < available


def test_a_combo_hands_back_the_key_object_not_a_qt_degraded_copy(qtbot, ruleset):
    """⚠ Qt stores item data as a QVariant and a `str`-valued Enum comes back out of
    `currentData()` as a plain `str`. `Character` has no `validate_assignment`, so a
    handler writing that onto an enum-typed field succeeds silently and fails later at
    the first `.value`. Pins the mechanism at the helper, where one fix covers every
    caller."""
    from exalted_builder.models.character import Specialty
    char = Character(id="c.s", exalt_type="Solar", caste="dawn")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.add_spec()
    combo = next(c for c in page._body_container.findChildren(QComboBox)
                 if c.count() == len(list(AbilityName)) and c.currentIndex() ==
                 list(AbilityName).index(AbilityName.MELEE))
    combo.setCurrentIndex(list(AbilityName).index(AbilityName.DODGE))
    assert type(char.specialties[-1].ability) is AbilityName
    assert char.specialties[-1].ability.value == "dodge"


# --------------------------------------------------------------------------- #
# Astrological Colleges
# --------------------------------------------------------------------------- #

def _panel_titled(page, prefix: str):
    from PySide6.QtWidgets import QLabel
    from exalted_builder.qt.editor import _Panel
    for card in page._body_container.findChildren(_Panel):
        for label in card.findChildren(QLabel):
            if label.text().startswith(prefix):
                return card
    return None


def test_colleges_are_offered_only_to_splats_that_ship_them(qtbot, ruleset):
    """Gated on the BUDGET (`college_dots`), not on the splat name — a Solar has no
    college pool and must not be shown an empty one."""
    sid = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    assert _panel_titled(_traits(ruleset, sid), "Astrological Colleges") is not None
    solar = Character(id="c.s", exalt_type="Solar", caste="dawn")
    assert _panel_titled(_traits(ruleset, solar), "Astrological Colleges") is None


def test_a_new_college_row_defaults_to_the_characters_own_house(qtbot, ruleset):
    """It counts toward the own-house minimum immediately rather than landing the
    character in violation of a budget they have not spent yet."""
    char = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.add_college()
    assert len(char.colleges) == 1
    college = ruleset.colleges[char.colleges[0].college_id]
    assert college.house == char.caste


def test_a_college_row_can_be_reduced_to_zero(qtbot, ruleset):
    """⚠ Colleges can be REDUCED — a usability escape hatch, not a printed rule
    (docs/status/edit-xp-merge.md). The track's floor is 0, not 1."""
    from exalted_builder.qt.editor import DotTrack
    char = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.add_college()
    panel = _panel_titled(page, "Astrological Colleges")
    track = panel.findChild(DotTrack)
    assert track is not None and track._lo == 0


def test_an_off_catalogue_college_id_keeps_its_own_row(qtbot, ruleset):
    """⚠ An old save naming a college that no longer exists must still show that id —
    snapping the row to another college would silently rewrite the character."""
    from exalted_builder.models.character import CollegeRating
    char = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    char.colleges = [CollegeRating(college_id="college.not-a-real-id", rating=2)]
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    panel = _panel_titled(page, "Astrological Colleges")
    combo = panel.findChild(QComboBox)
    assert combo.currentText() == "college.not-a-real-id"
    assert char.colleges[0].college_id == "college.not-a-real-id"


def test_removing_a_college_drops_that_row(qtbot, ruleset):
    from exalted_builder.models.character import CollegeRating
    char = Character(id="c.sid", exalt_type="Sidereal", caste="journeys")
    ids = list(ruleset.colleges)[:2]
    char.colleges = [CollegeRating(college_id=cid, rating=1) for cid in ids]
    page = _traits(ruleset, char)
    qtbot.addWidget(page)
    page.remove_college(0)
    assert [cr.college_id for cr in char.colleges] == ids[1:]
