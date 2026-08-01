"""Splat-aware Background availability (Dragon-Blooded Traits chapter, p156-160):
DB gain Breeding and Connections (both DB-only), and — oddly — lose Contacts,
Influence and Followers. Command, Henchmen and Reputation are shared (all splats).
Availability is autofill-only (backgrounds stay free text; nothing is hard-validated).
"""

from pathlib import Path

import pytest

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
