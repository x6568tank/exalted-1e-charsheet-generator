"""Splat-aware Background availability (Dragon-Blooded Traits chapter, p156-160):
DB gain Breeding and Connections (both DB-only), and — oddly — lose Contacts,
Influence and Followers. Command, Henchmen and Reputation are shared (all splats).
Availability is autofill-only (backgrounds stay free text; nothing is hard-validated).
"""

from pathlib import Path

import pytest
from nicegui import ui

import exalted_builder
from exalted_builder import rules_db

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _names(rs, exalt_type):
    return [b.name for b in rs.backgrounds_for(exalt_type)]


def test_db_only_backgrounds_hidden_from_solar(rs):
    solar = _names(rs, "Solar")
    assert "Breeding" not in solar
    assert "Connections" not in solar


def test_db_gets_breeding_and_connections(rs):
    db = _names(rs, "Dragon-Blooded")
    assert "Breeding" in db
    assert "Connections" in db


def test_db_barred_from_contacts_influence_followers(rs):
    db = _names(rs, "Dragon-Blooded")
    for barred in ("Contacts", "Influence", "Followers"):
        assert barred not in db
    # …but everyone else keeps them
    solar = _names(rs, "Solar")
    for kept in ("Contacts", "Influence", "Followers"):
        assert kept in solar


def test_shared_backgrounds_visible_to_all(rs):
    for shared in ("Command", "Henchmen", "Reputation"):
        assert shared in _names(rs, "Solar")
        assert shared in _names(rs, "Dragon-Blooded")


def test_core_ten_still_present_for_solar(rs):
    solar = _names(rs, "Solar")
    for core in ("Allies", "Artifact", "Backing", "Contacts", "Familiar",
                 "Followers", "Influence", "Manse", "Mentor", "Resources"):
        assert core in solar


def test_breeding_id_matches_the_essence_coefficient(rs):
    # derive.essence_pools reads the Breeding term by Background NAME; the DB exalt
    # row names it "Breeding" — the shipped catalog entry must carry that exact name.
    spec = rs.exalt_for("Dragon-Blooded").essence
    assert spec.breeding_background == "Breeding"
    assert any(b.name == "Breeding" for b in rs.background_catalog.values())


# --- Background descriptions surface in the picker -------------------------- #
# The catalog descriptions were authored but entirely unread by the UI until the
# Background selects started rendering them as per-option hover tooltips.

def test_every_background_has_a_description(rs):
    """A Background with no description shows no tooltip, which reads as a bug."""
    missing = [b.id for b in rs.background_catalog.values() if not b.description.strip()]
    assert not missing, missing


def test_backgrounds_are_chosen_in_exactly_one_place():
    """Backgrounds used to be picked on the chargen editor AND on the XP tab, in two
    near-identical panels that drifted. They now live once, on the Advantages tab, which
    carries both budget regimes. The described select is asserted there — and the two
    old homes are asserted NOT to have grown one back, which is the half of this test
    that will actually fail one day."""
    import inspect
    from exalted_builder.ui import advantages, editor
    assert "DescribedSelect(_opts_with(bg_names" in inspect.getsource(advantages)
    for module in (editor,):        # the XP tab, the other old home, is gone (0013)
        src = inspect.getsource(module)
        assert "bg_names" not in src, (
            f"{module.__name__} has grown a second Background panel; there is one, "
            f"in ui/advantages.py")


# The picker descriptions also print PERSISTENTLY under each row (2026-08-05), the way
# the M&F rows print their rules text — a picked Background is no longer a bare row.
# `/merits-backgrounds` holds Allies and Resources, both of which have descriptions.
#
# These tests are DELIBERATELY discriminating, and must stay so: the catalogue text also
# ships inside the dropdown options as hover-tooltip data (`DescribedSelect`), so a bare
# `should_see(description)` would pass against code with NO persistent label at all.
# Every assertion reads the label element found by its `data-testid`, never the page text.

def _bg_desc_labels(user) -> list:
    """The per-row Background description labels — found by `data-testid`, the one prop
    that distinguishes them from the M&F rules-text labels sharing their styling classes.
    Empty (not None) when the feature is absent, which is what makes these tests fail
    against code that does not have it."""
    return [el for el in user.find(ui.label).elements
            if el.props.get("data-testid") == "bg-desc"]


def _bg_desc_texts(user) -> list[str]:
    return [el.text or "" for el in _bg_desc_labels(user)]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_picked_background_prints_its_catalogue_description(user) -> None:
    await user.open('/merits-backgrounds')
    texts = _bg_desc_texts(user)
    assert any("each Ally is a Storyteller character" in t for t in texts), texts
    assert any("destitute to fabulously wealthy" in t for t in texts), texts
    assert all(el.visible for el in _bg_desc_labels(user)), \
        "a description label is hidden though its Background has one"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_picking_a_background_swaps_its_description_live(user) -> None:
    """A pick swaps the blurb without rebuilding the panel — a rebuilt input eats every
    keystroke after the first (the M&F filter bar's lesson), so the row's own select
    refreshes only its own description.

    The row is found by its select's VALUE ("Allies"), not by position — `user.find`
    does not return elements in model/creation order, so `[0]` is not the first row."""
    await user.open('/merits-backgrounds')
    allies_sel = next(sel for sel in user.find(ui.select).elements
                      if (sel.props.get("label") or "") == "Background"
                      and sel.value == "Allies")
    allies_sel.set_value("Manse")
    texts = [el.text or "" for el in _bg_desc_labels(user)]
    assert any("geomantic structure over a demesne" in t for t in texts), texts
    assert not any("Aides and friends" in t for t in texts), \
        "the swapped row still shows its old blurb"
    assert any("destitute to fabulously wealthy" in t for t in texts), \
        "switching one row clobbered the other row's blurb"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_descriptions_print_in_play_too(user) -> None:
    """The whole point of `_background_rows` being shared: the same row body, both
    regimes. Post-lock the dot track becomes a plain number, but the description under
    the row must still print."""
    await user.open('/backgrounds-description-xp')
    texts = _bg_desc_texts(user)
    assert any("each Ally is a Storyteller character" in t for t in texts), texts
    assert any("destitute to fabulously wealthy" in t for t in texts), texts


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_a_free_text_background_name_hides_its_description(user) -> None:
    """A name no catalogue entry covers gets nothing — the label exists but hides (the
    `set_visibility(bool(text))` path). `/advantages-unknown` holds just such a name.

    Read via `user.client.elements`, not `user.find`: the harness's `find` filters to
    visible elements (`only_visible=True`), and this label is invisible by design."""
    await user.open('/advantages-unknown')
    labels = [el for el in user.client.elements.values()
              if getattr(el, 'props', {}).get("data-testid") == "bg-desc"]
    assert len(labels) == 1, f"expected one (hidden) description label, got {len(labels)}"
    assert not labels[0].visible, "an unknown Background still shows a description"
    assert not (labels[0].text or ""), labels[0].text
