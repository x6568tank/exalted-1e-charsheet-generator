"""The Adversaries tab of the native Party window (exalted_builder/qt/adversaries.py).

Covers what the widget decides for itself: that the roster table shows damage at a
glance (the column that replaces the webapp's card stack), that the four toolbar
actions go through `engine.adversaries`, that a duplicate lands beside its original,
and — the test this surface actually needs — that EVERY field of the model is both
editable in the detail pane and readable off the roster.

⚠ **The dead-field bug has already shipped here once**: `powers`, `combat_pool` and
`cost_to_dematerialize` were authored into the catalogue, editable nowhere, and
silently wiped whenever an entry was opened and saved. 1,777 tests were green over it.
`test_every_stat_field_is_editable` walks `Adversary.model_fields` and DRIVES each
widget rather than grepping the source, so a field wired to a widget that writes the
wrong attribute fails too.

⚠ Widgets are addressed by objectName (`adv.dodge`, `adv.attributes.strength`), never
by position in a `findChildren` list — the pane is full of same-shaped spin boxes.
"""

import pytest

pytest.importorskip("PySide6", reason="the optional [qt] extra is not installed")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QLineEdit, QPlainTextEdit, QSpinBox

from exalted_builder.engine import adversaries as adv
from exalted_builder.models.adversary import Adversary, AdversaryAttack, AdversaryTrait
from exalted_builder.models.party import Party
from exalted_builder.models.rules import Damage
from exalted_builder.qt.adversaries import AdversariesPage

# Fields that are not stats a GM types: the id, the provenance, and the three tracked
# ones (which the trackers own, not the editor).
_NOT_STATS = {"id", "template_id", "damage", "willpower_spent", "motes_spent"}


@pytest.fixture
def make_page(ruleset, qtbot):
    def build(party=None, catalog=None, notes=None):
        sink = notes if notes is not None else []
        ctx = {"party": party if party is not None else Party(id="p.test"),
               "adversary_catalog": catalog or {}}
        page = AdversariesPage(ruleset, ctx,
                               notify=lambda text, kind="info": sink.append((kind, text)))
        qtbot.addWidget(page)
        return page
    return build


def _template() -> Adversary:
    return Adversary(id="tpl.bandit", name="Bandit", category="Extra",
                     base_initiative=5, combat_pool=4, willpower=3,
                     health_levels=adv.expand_health("-1/-3/I"))


def _full() -> Adversary:
    """An entry with every field filled — the fixture the field walks drive."""
    return Adversary(
        id="adv.1", name="Fakharu", template_id="tpl.x", category="Spirit",
        nature="Bureaucrat", caste="Water",
        attributes={"strength": 5, "wits": 4}, virtues={"valor": 3},
        abilities=[AdversaryTrait(name="Melee", rating=4, specialties="Swords +2")],
        backgrounds=[AdversaryTrait(name="Cult", rating=3)],
        base_initiative=7, combat_pool=6,
        attacks=[AdversaryAttack(name="Bite", speed=6, accuracy=7, damage=1,
                                 damage_type="L", defense=5)],
        dodge=4, soak_lethal=6, soak_bashing=8, willpower=8, essence=5,
        essence_pool=112, personal_essence=11, peripheral_essence=27,
        cost_to_materialize=50, cost_to_dematerialize=25,
        health_levels=adv.expand_health("-0/-1 x 2/-2/-4/Incap"),
        charms="All listed Charms", spells="None", powers="Materialize",
        notes="A worked example")


def _widget(page, name, kind):
    found = [w for w in page.findChildren(kind) if w.objectName() == name]
    assert found, f"no {kind.__name__} named {name!r} in the detail pane"
    return found[0]


# --------------------------------------------------------------------------- #
# The roster table
# --------------------------------------------------------------------------- #

def test_the_table_lists_the_roster_and_selects_the_first_entry(make_page):
    party = Party(id="p", adversaries=[_template(), _full()])
    page = make_page(party)
    assert page.table.topLevelItemCount() == 2
    assert page._selected == "tpl.bandit"


def test_the_table_keeps_roster_order_until_a_header_is_clicked(make_page):
    """⚠ A duplicate is inserted BESIDE its original so a squad reads as a squad. An
    alphabetically-sorted default would scatter it on the click that made it."""
    party = Party(id="p", adversaries=[_full(), _template()])   # F before B
    page = make_page(party)
    assert [page.table.topLevelItem(i).text(0) for i in range(2)] == ["Fakharu", "Bandit"]
    page.table.sortByColumn(0, Qt.AscendingOrder)               # still sortable
    assert [page.table.topLevelItem(i).text(0) for i in range(2)] == ["Bandit", "Fakharu"]


def test_the_damage_column_shows_marks_and_the_worst_penalty(make_page):
    """⚠ This column is not decoration: it is the one thing the webapp's card stack did
    better, and the reason a collection layout is acceptable for the roster at all."""
    party = Party(id="p", adversaries=[_template()])
    page = make_page(party)
    assert page.table.topLevelItem(0).text(2) == ""      # undamaged reads as blank
    page._cycle(0)                                       # -> bashing on the -1 box
    assert page.table.topLevelItem(0).text(2) == "1/ 0x 0*  (-1)"


def test_an_incapacitated_mark_is_labelled_not_printed_as_minus_99(make_page):
    party = Party(id="p", adversaries=[_template()])
    page = make_page(party)
    page._cycle(2)                                       # the Incap box
    assert "Incap" in page.table.topLevelItem(0).text(2)
    assert "-99" not in page.table.topLevelItem(0).text(2)


# --------------------------------------------------------------------------- #
# The toolbar
# --------------------------------------------------------------------------- #

def test_add_from_a_template_leaves_the_catalogue_row_untouched(make_page):
    template = _template()
    page = make_page(catalog={template.id: template})
    page._add(template.id)
    entry = page._current()
    assert entry.name == "Bandit" and entry.template_id == "tpl.bandit"
    entry.name = "Someone else"
    assert template.name == "Bandit"


def test_the_custom_button_adds_a_blank_entry(make_page):
    template = _template()
    page = make_page(catalog={template.id: template})
    page._add(None)                                      # the dialog's Custom button
    assert page._current().name == "New adversary"
    # An extra's three printed levels (p.241) — not an empty track nobody can click.
    assert len(page._current().health_levels) == 3


def test_duplicate_numbers_the_copy_and_sits_it_beside_its_original(make_page):
    party = Party(id="p", adversaries=[_template(), _full()])
    page = make_page(party)
    page._selected = "tpl.bandit"
    page._duplicate()
    assert [a.name for a in party.adversaries] == ["Bandit", "Bandit 2", "Fakharu"]
    # The duplicate is what you are now editing — you made it to change it.
    assert page._current().name == "Bandit 2"


def test_a_duplicate_gets_its_own_health_track(make_page):
    party = Party(id="p", adversaries=[_template()])
    page = make_page(party)
    page._cycle(0)
    page._duplicate()
    # ⚠ Not `== []`: rendering normalises the track to one None per box, so "undamaged"
    # is a list of Nones, not an empty list.
    assert all(m is None for m in adv.normalize_damage(party.adversaries[1]))
    assert party.adversaries[0].damage[0] == Damage.BASHING


def test_reset_clears_all_three_tracked_fields(make_page):
    entry = _full()
    entry.willpower_spent, entry.motes_spent = 4, 30
    party = Party(id="p", adversaries=[entry])
    page = make_page(party)
    page._cycle(0)
    page._reset()
    assert all(m is None for m in entry.damage)
    assert (entry.willpower_spent, entry.motes_spent) == (0, 0)


def test_delete_drops_the_entry_and_the_selection(make_page):
    party = Party(id="p", adversaries=[_template()])
    page = make_page(party)
    page._delete()
    assert party.adversaries == []
    assert page._selected is None
    # ⚠ The actions that need a selection go dead with it, rather than raising.
    assert not page.delete_btn.isEnabled()


def test_the_add_dialog_offers_every_template_grouped_by_category(make_page):
    template = _template()
    page = make_page(catalog={template.id: template})
    dialog = page.build_add_dialog()
    assert dialog._entries[0][0] == "tpl.bandit"


# --------------------------------------------------------------------------- #
# The trackers
# --------------------------------------------------------------------------- #

def test_a_health_box_cycles_through_the_four_marks(make_page):
    party = Party(id="p", adversaries=[_template()])
    page = make_page(party)
    entry = party.adversaries[0]
    for expected in (Damage.BASHING, Damage.LETHAL, Damage.AGGRAVATED, None):
        page._cycle(0)
        assert adv.normalize_damage(entry)[0] == expected


def test_the_mote_counter_clamps_to_the_entrys_own_pool(make_page):
    entry = Adversary(id="a", name="Spirit", essence_pool=12)
    page = make_page(Party(id="p", adversaries=[entry]))
    spin = _widget(page, "adv.motes_spent", QSpinBox)
    assert spin.maximum() == 12
    spin.setValue(12)
    assert entry.motes_spent == 12


def test_an_entry_with_no_motes_gets_no_mote_counter(make_page):
    page = make_page(Party(id="p", adversaries=[_template()]))
    assert not [w for w in page.findChildren(QSpinBox)
                if w.objectName() == "adv.motes_spent"]


def test_a_willpower_box_fills_to_the_click_and_empties_back(make_page):
    entry = _template()
    page = make_page(Party(id="p", adversaries=[entry]))
    page._count(2)
    assert entry.willpower_spent == 3
    page._count(2)
    assert entry.willpower_spent == 2


# --------------------------------------------------------------------------- #
# The editor — the dead-field guard
# --------------------------------------------------------------------------- #

_DRIVERS = {}


def _drive(page, entry, field):
    """Move the widget that owns `field` and return what the model should now hold."""
    if field in ("attributes", "virtues"):
        key = "strength" if field == "attributes" else "valor"
        _widget(page, f"adv.{field}.{key}", QSpinBox).setValue(7)
        return {**getattr(entry, field), key: 7}
    if field in ("abilities", "backgrounds"):
        line = _widget(page, f"adv.{field}", QLineEdit)
        line.setText("Awareness 2 (Owls +1)")
        line.editingFinished.emit()
        return [AdversaryTrait(name="Awareness", rating=2, specialties="Owls +1")]
    if field == "attacks":
        _widget(page, "adv.attacks", QPlainTextEdit).setPlainText(
            "Claw: Spd 3 Acc 2 Dmg 1L Def 4")
        return [AdversaryAttack(name="Claw", speed=3, accuracy=2, damage=1,
                                damage_type="L", defense=4)]
    if field == "health_levels":
        line = _widget(page, "adv.health_levels", QLineEdit)
        line.setText("-0/-2 x 2/Incap")
        line.editingFinished.emit()
        return adv.expand_health("-0/-2 x 2/Incap")
    if field in ("armor_id", "shield_id"):
        combo = _widget(page, f"adv.{field}", QComboBox)
        assert combo.count() > 1, f"{field} offers nothing to pick"
        combo.setCurrentIndex(1)
        return combo.itemData(1)
    for kind, value in ((QLineEdit, "typed"), (QPlainTextEdit, "typed")):
        widgets = [w for w in page.findChildren(kind) if w.objectName() == f"adv.{field}"]
        if widgets:
            (widgets[0].setText if kind is QLineEdit
             else widgets[0].setPlainText)(value)
            return value
    _widget(page, f"adv.{field}", QSpinBox).setValue(3)
    return 3


@pytest.mark.parametrize("field", sorted(set(Adversary.model_fields) - _NOT_STATS))
def test_every_stat_field_is_editable(make_page, field):
    """Every printed field must have a widget that writes IT. Driving the widget rather
    than grepping the source also catches one wired to the wrong attribute."""
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    expected = _drive(page, entry, field)
    assert getattr(entry, field) == expected


def test_a_trait_left_at_the_minimum_is_absent_not_zero(make_page):
    """⚠ 0 means ABSENT in the trait grid. A beast prints three of the nine Attributes
    and storing a zero would claim the book printed one (models/adversary.py)."""
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    _widget(page, "adv.attributes.strength", QSpinBox).setValue(0)
    assert "strength" not in entry.attributes


def test_a_nullable_combat_number_can_be_cleared_to_absent(make_page):
    """⚠ Absent is not zero: the Bear prints no dodge (p.316) and Nagezzer prints "Does
    not dodge" (p.307). Both must be reachable from the same box."""
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    spin = _widget(page, "adv.dodge", QSpinBox)
    spin.setValue(0)
    assert entry.dodge == 0
    spin.setValue(-1)
    assert entry.dodge is None
    assert spin.specialValueText() == "—"


def test_retracking_the_health_line_renormalises_the_marks(make_page):
    """Marks are POSITIONAL. Shortening the track must drop the marks that fell off it,
    or the tracker renders against a list that no longer exists."""
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    for i in range(len(entry.health_levels)):
        page._cycle(i)
    line = _widget(page, "adv.health_levels", QLineEdit)
    line.setText("-1/Incap")
    line.editingFinished.emit()
    assert len(entry.damage) == 2


def test_charms_spells_and_powers_stay_free_text(make_page):
    """⚠ The book prints "All Solar Charms the Storyteller cares to give him" (p.303).
    Never a list of ids — the loader's link-checking would reject them."""
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    for field in ("charms", "spells", "powers"):
        widget = _widget(page, f"adv.{field}", QPlainTextEdit)
        widget.setPlainText("whatever the ST likes")
        assert getattr(entry, field) == "whatever the ST likes"


def test_editing_a_name_tracks_the_table_without_losing_the_selection(make_page):
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    _widget(page, "adv.name", QLineEdit).setText("Renamed")
    assert page.table.topLevelItem(0).text(0) == "Renamed"
    assert page._selected == "adv.1"


def test_the_stats_column_reads_through_the_engine(make_page):
    """Soak and the dodge-after-armour figure reach the row only through
    `engine.adversaries`, which is the correct path — the tab computes nothing."""
    entry = _full()
    page = make_page(Party(id="p", adversaries=[entry]))
    row = page.table.topLevelItem(0).text(3)
    assert "Init 7" in row and "Dodge 4" in row and "Soak" in row
