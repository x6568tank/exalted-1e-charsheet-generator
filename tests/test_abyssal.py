"""Abyssal (deathknight) chargen foundation: exercises the shipped Abyssal data
(exalts.json, chargen_budgets.json, the five Castes, the Abyssal Backgrounds) and
the loyal/fugitive Backgrounds origin split. Values are from the Abyssal splatbook
Character Creation summary (p120-125). Necromancy and the Abyssal charm trees are
authored in later phases; this covers only the chargen foundation.
"""

from pathlib import Path

import pytest

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import derive
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName as A
from exalted_builder.models.rules import VirtueName as V
from exalted_builder.models.rules import (Charm, CharmType, Spell, SpellCircle,
                                           TRACK_CIRCLES, circle_kind)

DATA_DIR = Path(exalted_builder.__file__).parent / "data"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


# --- exalt row -------------------------------------------------------------- #

def test_abyssal_exalt_row(rs):
    ab = rs.exalt_for("Abyssal")
    assert ab.label == "Abyssal Exalted"
    assert ab.magic_track == "necromancy"          # deathknights work Necromancy, not Sorcery
    assert ab.caste_noun == "Caste"                # Abyssals keep the Solar "Caste" noun
    # NOTHING is barred at creation: the Abyssal book states no chargen restriction on
    # Void-Circle necromancy (rules-authority confirmed 2026-07-19), unlike Solars who
    # are barred from the Solar Circle.
    assert ab.highest_magic_circle_id == ""
    assert ab.ox_body_charm_id == "abyssal.endurance.ox-body-technique"


# --- budgets: loyal (13) vs fugitive (5) Backgrounds ------------------------ #

def test_abyssal_background_origin_split(rs):
    loyal = rs.budgets_for("Abyssal", "loyal")
    fugitive = rs.budgets_for("Abyssal", "fugitive")
    assert loyal.background_dots == 13
    assert fugitive.background_dots == 5
    # default (no origin) is the loyal row
    assert rs.budgets_for("Abyssal").background_dots == 13


def test_abyssal_budget_matches_solar_shape(rs):
    b = rs.budgets_for("Abyssal")
    assert b.attribute_pools == (8, 6, 4)
    assert (b.ability_dots, b.ability_min_caste_favored) == (25, 10)
    assert b.favored_count == 5
    assert (b.charm_count, b.charm_min_caste_favored) == (10, 5)
    assert b.virtue_dots == 5
    assert b.essence_start == 2
    assert b.bonus_points == 15
    assert b.required_min_abilities == []          # no Dynastic-style schooling floor


def test_abyssal_bonus_costs_fall_back_to_solar_defaults(rs):
    # Abyssal BP costs are identical to Solar (p125) — no explicit row, so they use
    # the "default" table.
    bc = rs.bonus_costs_for("Abyssal")
    assert (bc.charm, bc.charm_favored_caste) == (5, 4)
    assert bc.essence == 7


# --- the five Castes -------------------------------------------------------- #

def test_abyssal_castes(rs):
    castes = {c.id: c for c in rs.castes.values() if c.exalt_type == "Abyssal"}
    assert set(castes) == {"dusk", "midnight", "daybreak", "day", "moonshadow"}
    # groupings mirror the Solar castes (Dusk=Dawn, Midnight=Zenith, etc.)
    assert castes["dusk"].caste_abilities == [A.ARCHERY, A.BRAWL, A.MARTIAL_ARTS, A.MELEE, A.THROWN]
    assert castes["daybreak"].caste_abilities == [A.CRAFT, A.INVESTIGATION, A.LORE, A.MEDICINE, A.OCCULT]
    assert castes["moonshadow"].caste_abilities == [A.BUREAUCRACY, A.LINGUISTICS, A.RIDE, A.SAIL, A.SOCIALIZE]
    for c in castes.values():
        assert c.description and c.anima_powers


# --- Backgrounds (p125): 8 universal + 6 Abyssal-only ----------------------- #

def test_abyssal_backgrounds(rs):
    names = {b.name for b in rs.backgrounds_for("Abyssal")}
    assert {"Abyssal Command", "Liege", "Necromancy",
            "Spies", "Underworld Manse", "Whispers"} <= names
    assert {"Allies", "Artifact", "Contacts", "Familiar",
            "Followers", "Influence", "Manse", "Resources"} <= names
    # not on the Abyssal list (barred for this splat)
    assert names.isdisjoint({"Backing", "Mentor", "Command", "Henchmen", "Reputation"})
    # DB-only backgrounds never leak to Abyssal
    assert names.isdisjoint({"Breeding", "Connections"})


# --- essence pools: Abyssal reuses the Solar formula (Ess*3+WP / Ess*7+WP+ΣV) - #

def test_abyssal_essence_pools(rs):
    c = Character(id="ab.dusk", exalt_type="Abyssal", caste="dusk", origin="loyal")
    c.virtues.update({V.COMPASSION: 3, V.CONVICTION: 3, V.TEMPERANCE: 2, V.VALOR: 1})
    c.essence_rating = 2
    # WP = 6 (two highest Virtues 3+3). Personal = 2*3+6 = 12.
    # Peripheral = 2*7+6+(3+3+2+1) = 14+6+9 = 29.
    assert derive.essence_pools(rs, c) == (12, 29)


# --- Phase B: Necromancy magic-track engine -------------------------------- #
#
# Necromancy is a distinct track from sorcery, with three circles ascending in
# power Shadowlands -> Labyrinth -> Void (Abyssal p.223). The engine's circle-access
# logic is track-agnostic (exact-circle match + the initiation-Charm prerequisite
# chain), so these tests layer synthetic necromancy Charms/spells on `rs`.

from exalted_builder.engine import validate                 # noqa: E402
from exalted_builder.ui import view                          # noqa: E402


def test_necromancy_circles_and_kinds():
    assert TRACK_CIRCLES["necromancy"] == (
        SpellCircle.SHADOWLANDS, SpellCircle.LABYRINTH, SpellCircle.VOID)
    assert circle_kind(SpellCircle.VOID) == "necromancy"
    assert circle_kind(SpellCircle.SOLAR) == "sorcery"


def test_abyssal_has_no_chargen_circle_bar(rs):
    # No Necromancy circle is barred at creation (rules-authority confirmed).
    c = Character(id="ab", exalt_type="Abyssal", caste="daybreak", origin="loyal")
    assert validate.chargen_barred_circle(rs, c) is None
    # Solar's Sorcery bar is untouched
    solar = Character(id="s", exalt_type="Solar", caste="twilight")
    assert validate.chargen_barred_circle(rs, solar) == SpellCircle.SOLAR


def _rs_with_necromancy(rs):
    """`rs` plus a chained Shadowlands->Labyrinth->Void necromancy initiation trio
    and one spell of each of the three circles."""
    def charm(cid, circle, prereqs):
        return Charm(id=cid, name=cid, category="occult", exalt_type="Abyssal",
                     type=CharmType.SIMPLE, min_ability=1, min_essence=1,
                     grants_circle=circle, prerequisites=prereqs)
    charms = {
        "ab.occult.shadowlands": charm("ab.occult.shadowlands", SpellCircle.SHADOWLANDS, []),
        "ab.occult.labyrinth": charm("ab.occult.labyrinth", SpellCircle.LABYRINTH,
                                     [["ab.occult.shadowlands"]]),
        "ab.occult.void": charm("ab.occult.void", SpellCircle.VOID, [["ab.occult.labyrinth"]]),
    }
    spells = {
        "sp.shadow": Spell(id="sp.shadow", name="Shadow Spell", circle=SpellCircle.SHADOWLANDS),
        "sp.laby": Spell(id="sp.laby", name="Labyrinth Spell", circle=SpellCircle.LABYRINTH),
        "sp.void": Spell(id="sp.void", name="Void Spell", circle=SpellCircle.VOID),
    }
    return rs.model_copy(update={"charms": {**rs.charms, **charms},
                                 "spells": {**rs.spells, **spells}})


def _abyssal():
    c = Character(id="ab.necro", exalt_type="Abyssal", caste="daybreak", origin="loyal")
    c.abilities[A.OCCULT] = 3
    c.essence_rating = 3
    return c


def test_necromancer_learns_granted_circle(rs):
    rs2 = _rs_with_necromancy(rs)
    c = _abyssal()
    c.charms = ["ab.occult.shadowlands"]
    assert validate.meets_spell_requirements(rs2, c, rs2.spells["sp.shadow"]) is True
    # a circle with no known granting Charm is not learnable
    assert validate.meets_spell_requirements(rs2, c, rs2.spells["sp.laby"]) is False


def test_void_necromancer_may_learn_all_three_circles_at_chargen(rs):
    rs2 = _rs_with_necromancy(rs)
    c = _abyssal()
    c.charms = ["ab.occult.shadowlands", "ab.occult.labyrinth", "ab.occult.void"]
    # No circle is barred at creation, so a Void necromancer may learn Void spells at
    # chargen, plus the lower circles (higher-grants-lower via the prereq chain).
    assert validate.meets_spell_requirements(rs2, c, rs2.spells["sp.void"], chargen=True) is True
    assert validate.meets_spell_requirements(rs2, c, rs2.spells["sp.laby"], chargen=True) is True
    assert validate.meets_spell_requirements(rs2, c, rs2.spells["sp.shadow"], chargen=True) is True


def test_sorcery_and_necromancy_do_not_cross_grant(rs):
    rs2 = _rs_with_necromancy(rs)
    c = _abyssal()
    c.charms = ["ab.occult.void"]                      # a necromancy Charm
    # does not unlock a Sorcery-circle spell
    terr = rs2.spells["spell.terrestrial.death-of-obsidian-butterflies"]
    assert validate.meets_spell_requirements(rs2, c, terr) is False


def test_spell_picker_shows_every_reachable_circle(rs):
    rs2 = _rs_with_necromancy(rs)
    ab = _abyssal()
    ab.charms = ["ab.occult.shadowlands"]
    circles = {r.circle for r in view.build_spell_picker(rs2, ab)}
    # Abyssals reach BOTH tracks: their Occult tree carries the Terrestrial/Celestial
    # Sorcery initiations AND the three Necromancy initiations, so the picker shows
    # Sorcery circles alongside Necromancy (having a granting Charm is the gate, not
    # the nominal magic_track).
    assert {"Shadowlands", "Labyrinth", "Void"} <= circles
    assert {"Terrestrial", "Celestial"} <= circles
    assert "Solar" not in circles                              # Abyssals top out at Celestial sorcery
    # a Solar reaches Sorcery plus Shadowlands/Labyrinth Necromancy (core allows
    # Solars into necromancy up to the Labyrinth Circle) but NEVER the Void Circle.
    solar = Character(id="s", exalt_type="Solar", caste="twilight")
    solar_circles = {r.circle for r in view.build_spell_picker(rs2, solar)}
    assert {"Terrestrial", "Celestial", "Solar", "Shadowlands", "Labyrinth"} <= solar_circles
    assert "Void" not in solar_circles


def test_solars_learn_shadowlands_and_labyrinth_necromancy_not_void(rs):
    # The Solar Occult tree now carries the Shadowlands & Labyrinth Necromancy
    # initiations (free-standing chain, mirroring the Abyssal stats) but NO Void
    # initiation — Solars may learn necromancy only up to the Labyrinth Circle.
    assert "solar.occult.shadowlands-circle-necromancy" in rs.charms
    assert "solar.occult.labyrinth-circle-necromancy" in rs.charms
    assert "solar.occult.void-circle-necromancy" not in rs.charms
    # the Labyrinth init requires the Shadowlands init (chain), Shadowlands is a root
    assert rs.charms["solar.occult.shadowlands-circle-necromancy"].prerequisites == []
    assert rs.charms["solar.occult.labyrinth-circle-necromancy"].prerequisites == \
        [["solar.occult.shadowlands-circle-necromancy"]]

    solar = Character(id="s", exalt_type="Solar", caste="twilight")
    solar.charms = ["solar.occult.shadowlands-circle-necromancy",
                    "solar.occult.labyrinth-circle-necromancy"]
    a_spell = lambda circle: next(s for s in rs.spells.values() if s.circle == circle)
    assert validate.meets_spell_requirements(rs, solar, a_spell(SpellCircle.SHADOWLANDS))
    assert validate.meets_spell_requirements(rs, solar, a_spell(SpellCircle.LABYRINTH))
    # Void remains unreachable: no learnable Solar Charm grants it
    assert SpellCircle.VOID not in validate.accessible_circles(rs, solar)


# --- Phase C: the authored Abyssal charm + necromancy-spell catalogue ------- #
#
# These exercise the SHIPPED data (data/charms/abyssal_*.json + the 23 necromancy
# spells in spells.json), not synthetic Charms. All corebook Abyssal charms across
# every Ability are authored (Abyssal p156-223).

def test_abyssal_charm_catalogue_complete(rs):
    ab = [c for c in rs.charms.values() if c.exalt_type == "Abyssal"]
    assert len(ab) == 233
    cats = {c.category.split(":")[0] for c in ab}
    # a spread of Abilities across all five Castes is authored
    for ability in ("melee", "occult", "socialize", "sail", "medicine",
                    "endurance", "athletics", "bureaucracy"):
        assert ability in cats, ability
    # Hungry Ghost Style martial arts uses the style-qualified category
    assert any(c.category == "martial_arts:hungry-ghost" for c in ab)


def test_abyssal_necromancy_initiation_charms_grant_their_circles(rs):
    trio = {
        "abyssal.occult.shadowlands-circle-necromancy": SpellCircle.SHADOWLANDS,
        "abyssal.occult.labyrinth-circle-necromancy": SpellCircle.LABYRINTH,
        "abyssal.occult.void-circle-necromancy": SpellCircle.VOID,
    }
    for cid, circle in trio.items():
        assert rs.charms[cid].grants_circle == circle
    # Void needs Essence 5 (Abyssal p198) — real page value, not a chargen bar
    assert rs.charms["abyssal.occult.void-circle-necromancy"].min_essence == 5


def test_abyssal_necromancy_spells_authored(rs):
    by_circle = {}
    for s in rs.spells.values():
        by_circle.setdefault(s.circle, []).append(s)
    # 2026-08-11: Book of Bone and Ebony — the Arcanoi/necromancy book — was extracted
    # and its 59 necromancy spells authored, roughly tripling these circles. The counts
    # are the E:Ab originals plus that batch (docs/status/spell-batch-notes.md).
    assert len(by_circle[SpellCircle.SHADOWLANDS]) == 42
    assert len(by_circle[SpellCircle.LABYRINTH]) == 24
    assert len(by_circle[SpellCircle.VOID]) == 17
    # a known spell of each circle
    assert "spell.shadowlands.summon-ghost" in rs.spells
    assert "spell.labyrinth.ivory-razor-forest" in rs.spells
    assert "spell.void.lord-of-the-dead" in rs.spells


def test_real_shadowlands_necromancer_learns_real_shadowlands_spell(rs):
    c = _abyssal()
    c.charms = ["abyssal.occult.shadowlands-circle-necromancy"]
    shadow = rs.spells["spell.shadowlands.hungry-creeping-shadow"]
    laby = rs.spells["spell.labyrinth.ivory-razor-forest"]
    assert validate.meets_spell_requirements(rs, c, shadow) is True
    # Shadowlands initiation does NOT reach up to Labyrinth
    assert validate.meets_spell_requirements(rs, c, laby) is False
