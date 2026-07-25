"""The five Solar castebooks' Charms, spells and gear.

Sources (human-vetted page scans, `images/Solars/Castebooks/<Caste>/`):
  Caste Book: Dawn      p.71-81
  Caste Book: Eclipse   p.71-78
  Caste Book: Night     p.67-81
  Caste Book: Twilight  p.69-76
  Caste Book: Zenith    p.71-81

The three martial-arts styles here (Tiger, Praying Mantis, Ebon Shadow) are the ones
`data/camps.json` has named since the Cult of the Illuminated work; their category keys
must not drift.
"""
from collections import Counter
from pathlib import Path

import pytest

from exalted_builder import rules_db
from exalted_builder.engine import costs, validate
from exalted_builder.models.character import Character
from exalted_builder.models.rules import AbilityName as AB
from exalted_builder.models.rules import SpellCircle

DATA_DIR = Path(__file__).resolve().parents[1] / "exalted_builder" / "data"

CASTEBOOKS = {
    "Exalted 1e Caste Book: Dawn",
    "Exalted 1e Caste Book: Eclipse",
    "Exalted 1e Caste Book: Night",
    "Exalted 1e Caste Book: Twilight",
    "Exalted 1e Caste Book: Zenith",
}


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _castebook_charms(rs):
    return [c for c in rs.charms.values() if c.source.book in CASTEBOOKS]


# --------------------------------------------------------------------------- #
# Catalogue shape
# --------------------------------------------------------------------------- #

def test_every_castebook_charm_is_solar_and_page_marked(rs):
    charms = _castebook_charms(rs)
    assert len(charms) == 139
    for c in charms:
        assert c.exalt_type == "Solar", c.id
        assert c.source.page, c.id
        assert c.id.startswith("solar."), c.id


def test_castebook_charm_counts_by_book(rs):
    """One count per book, so a lost or duplicated entry shows up as the book it came
    from rather than as an anonymous total."""
    per_book = Counter(c.source.book for c in _castebook_charms(rs))
    assert per_book == {
        # 3 Archery + 3 Brawl + 9 Tiger Style + 2 Melee + 4 Thrown + 3 Performance
        # + 1 Presence. Prey-Freezing Gaze (p.76) is NOT counted: it is already in
        # data/ from Cult of the Illuminated, which reprints it in an altered form.
        "Exalted 1e Caste Book: Dawn": 25,
        # 2 Bureaucracy + 5 Linguistics + 10 Praying Mantis + 1 Presence + 4 Ride
        # + 3 Sail + 7 Socialize. Tireless Traveler's Stamina, Excellent Emissary's
        # Tongue and Graceful Courtier Attitude are already in data/ (Illuminated).
        "Exalted 1e Caste Book: Eclipse": 32,
        # 11 Ebon Shadow + 4 Melee + 1 Investigation + 3 Lore + 2 Medicine
        # + 7 Athletics + 3 Awareness + 1 Dodge + 2 Larceny + 1 Stealth.
        "Exalted 1e Caste Book: Night": 35,
        # 4 Craft + 3 Investigation + 1 Linguistics + 4 Lore + 4 Medicine + 3 Occult.
        "Exalted 1e Caste Book: Twilight": 19,
        # 7 Endurance + 8 Resistance + 5 Survival + 6 Performance + 2 Presence.
        # Game-Snaring Huntsman's Method is already in data/ (Illuminated, altered).
        "Exalted 1e Caste Book: Zenith": 28,
    }


def test_the_three_castebook_styles_use_the_keys_camps_json_already_names(rs):
    """data/camps.json's Sequestered Tabernacle package offers four styles by category
    key. Renaming a style's category silently empties that grant, so the keys are
    pinned from BOTH sides here."""
    (choice,) = rs.camps["sequestered-tabernacle"].granted_charm_choices
    assert set(choice.from_categories) == {
        "martial_arts:ebon-shadow", "martial_arts:praying-mantis",
        "martial_arts:snake", "martial_arts:tiger"}
    cats = Counter(c.category for c in rs.charms.values() if c.exalt_type == "Solar")
    assert cats["martial_arts:tiger"] == 9
    assert cats["martial_arts:praying-mantis"] == 10
    assert cats["martial_arts:ebon-shadow"] == 11


@pytest.mark.parametrize("category,root", [
    ("martial_arts:tiger", "solar.martial-arts.crimson-leaping-cat-technique"),
    ("martial_arts:praying-mantis", "solar.martial-arts.leaping-mantis-technique"),
    ("martial_arts:ebon-shadow", "solar.martial-arts.image-of-death-technique"),
])
def test_each_castebook_style_is_a_self_contained_single_root_cascade(rs, category, root):
    style = [c for c in rs.charms.values() if c.category == category]
    ids = {c.id for c in style}
    roots = [c.id for c in style if not c.prerequisites]
    assert roots == [root]
    for c in style:
        for group in c.prerequisites:
            for pid in group:
                assert pid in ids, f"{c.id} reaches outside its style: {pid}"


def test_castebook_styles_are_solar_only(rs):
    """Unlike Falling Blossom (a Terrestrial style, so `open_to_all`), nothing on these
    three styles' pages opens them to other Exalt types. Do not widen them without a
    page that says so."""
    for category in ("martial_arts:tiger", "martial_arts:praying-mantis",
                     "martial_arts:ebon-shadow"):
        for c in (x for x in rs.charms.values() if x.category == category):
            assert not c.open_to_all, c.id
            assert c.open_to_tiers == [], c.id


# --------------------------------------------------------------------------- #
# Prerequisite cascades into the corebook trees
# --------------------------------------------------------------------------- #

def _maxed(rs, charms):
    from exalted_builder.models.character import CraftRating
    c = Character(id="c.castebook", exalt_type="Solar", caste="dawn")
    c.essence_rating = 7
    for ab in AB:
        c.abilities[ab] = 7
    # Craft is per-focus (core p.136) — the AbilityName.CRAFT dot is unused, so a
    # Craft-gated Charm reads this list instead.
    c.crafts = [CraftRating(focus="Smithing", rating=5)]
    c.charms = list(charms)
    return c


def test_every_castebook_charm_resolves_with_its_full_prerequisite_chain(rs):
    """Walk each castebook Charm's transitive prerequisites (which mostly reach back
    into the corebook trees) and confirm a maxed character holding the closure has no
    outstanding prerequisite or minimum issue."""
    closure = set()
    frontier = [c.id for c in _castebook_charms(rs)]
    while frontier:
        cid = frontier.pop()
        if cid in closure:
            continue
        closure.add(cid)
        for group in rs.charms[cid].prerequisites:
            frontier.extend(group)
    c = _maxed(rs, closure)
    assert validate.check_charm_prerequisites(rs, c) == []


def test_deep_cascades_reach_back_into_the_corebook_trees(rs):
    """Spot-checks that the castebooks hang off the right corebook Charms, since a
    typo'd prerequisite id would have been caught by the loader but a WRONG-but-real
    one would not."""
    p = rs.charms
    assert p["solar.archery.bolt-of-fiery-devastation-technique"].prerequisites == [
        ["solar.archery.solar-spike"]]
    assert p["solar.brawl.adamantine-fists-of-battle"].prerequisites == [
        ["solar.brawl.heaven-thunder-hammer"], ["solar.brawl.hammer-on-iron-technique"]]
    assert p["solar.melee.steel-devil-style"].prerequisites == [
        ["solar.melee.ready-in-eight-directions-stance"],
        ["solar.melee.two-swords-technique"]]
    assert p["solar.athletics.cloud-foot-style"].prerequisites == [
        ["solar.athletics.spider-foot-style"], ["solar.athletics.feather-foot-style"]]
    assert p["solar.occult.power-disrupting-blow"].prerequisites == [
        ["solar.occult.all-encompassing-sorcerers-sight"],
        ["solar.occult.power-draining-whisper"]]


def test_awareness_charms_gate_on_the_generic_unsurpassed_sense_discipline(rs):
    """Caste Book: Night p.75 prints "Unsurpassed (Sense) Discipline" for one Charm and
    "Unsurpassed Sight Discipline" for the other. `data/` has ONE Charm for the family
    (solar.awareness.unsurpassed-sense-discipline, the corebook's own templated entry),
    so both point at it."""
    for cid in ("solar.awareness.barrier-bypassing-senses",
                "solar.awareness.eye-of-the-unconquered-sun"):
        assert rs.charms[cid].prerequisites == [
            ["solar.awareness.unsurpassed-sense-discipline"]]


# --------------------------------------------------------------------------- #
# Multi-gate Charms (extra_min_abilities)
# --------------------------------------------------------------------------- #

def test_castebook_multi_gate_charms_check_but_never_price_their_second_ability(rs):
    """Four castebook Charms print a second "Minimum <Ability>" line. `min_ability`
    stays the PRIMARY (category) gate — the extras are requirement checks only and must
    never leak into Caste/Favoured pricing (the rule set out in models/rules.py)."""
    extras = {
        "solar.linguistics.masterful-training-manual": (AB.LORE, 3),
        "solar.performance.impenetrable-identity": (AB.PRESENCE, 3),
        "solar.resistance.drunken-warrior-technique": (AB.PERFORMANCE, 2),
        "solar.resistance.inebriated-fool-defense": (AB.PERFORMANCE, 3),
    }
    for cid, (ability, rating) in extras.items():
        charm = rs.charms[cid]
        (extra,) = charm.extra_min_abilities
        assert extra.abilities == [ability] and extra.rating == rating, cid

    # The second gate bites.
    c = _maxed(rs, ["solar.resistance.alcohol-resisting-prana",
                    "solar.resistance.drunken-warrior-technique"])
    c.abilities[AB.PERFORMANCE] = 1
    assert any(i.code == "charm-min-ability" and "drunken" in i.where
               for i in validate.check_charm_prerequisites(rs, c))
    c.abilities[AB.PERFORMANCE] = 2
    assert validate.check_charm_prerequisites(rs, c) == []

    # ...and does not change the price. A Zenith Solar has Resistance as a Caste
    # Ability and Performance as one too, so use a Dawn to keep both un-favoured, then
    # favour ONLY the extra gate's ability and confirm nothing moves.
    buyer = Character(id="c.price", exalt_type="Solar", caste="dawn")
    buyer.essence_rating = 3
    charm = rs.charms["solar.resistance.drunken-warrior-technique"]
    plain = costs.charm_cost(rs, buyer, charm)
    buyer.favored_abilities = [AB.PERFORMANCE]
    assert costs.charm_cost(rs, buyer, charm) == plain


# --------------------------------------------------------------------------- #
# The repeatable Zenith Resistance Charm
# --------------------------------------------------------------------------- #

def test_environmental_hazard_resisting_meditation_is_repeatable_data(rs):
    """Caste Book: Zenith p.72-73: four versions, "cannot purchase this Charm more times
    than she has dots in the Resistance Ability". The Charm carries the repeatable
    shape Ox-Body uses, but Solars have no `Character` list for a SECOND repeatable
    Charm, so today it is only holdable once (see the canonical-Charm-pick refactor in
    CLAUDE.md's TODO). This test pins the DATA so the refactor has something to wire."""
    charm = rs.charms["solar.resistance.environmental-hazard-resisting-meditation"]
    assert charm.repeatable_cap_ability == "resistance"
    assert [v.key for v in charm.variants] == [
        "extreme_heat", "extreme_cold", "acid", "windblown_particles"]
    assert charm.min_ability == 5 and charm.min_essence == 2
    # It is NOT the splat's Ox-Body Charm — that machinery stays pointed at Ox-Body.
    assert rs.exalt_for("Solar").ox_body_charm_id == "solar.endurance.ox-body-technique"

    # Meanwhile it behaves as an ordinary Charm pick: legal, priced, gated.
    c = _maxed(rs, [charm.id])
    assert validate.check_charm_prerequisites(rs, c) == []
    c.abilities[AB.RESISTANCE] = 4
    assert any(i.code == "charm-min-ability"
               for i in validate.check_charm_prerequisites(rs, c))


# --------------------------------------------------------------------------- #
# Spells and gear
# --------------------------------------------------------------------------- #

def test_twilight_castebook_spells(rs):
    """Caste Book: Twilight p.74-77 — all seven. Evocation from the Mirror spans the
    p.76/77 break; p.77 then turns to hearthstones, which are out of scope per the
    human's note.md, so the castebook spell list is complete."""
    spells = [s for s in rs.spells.values()
              if s.source.book == "Exalted 1e Caste Book: Twilight"]
    assert len(spells) == 7
    by_circle = Counter(s.circle for s in spells)
    assert by_circle == {SpellCircle.TERRESTRIAL: 2, SpellCircle.CELESTIAL: 3,
                         SpellCircle.SOLAR: 2}
    assert rs.spells["spell.solar.evocation-from-the-mirror"].cost.motes == 40
    assert rs.spells["spell.solar.atrocious-fire-transformation"].cost.motes == 35


def test_castebook_gear_loads_with_its_table_values(rs):
    """Spot-checks against the printed tables — the parts most likely to be mis-read."""
    w = rs.weapon_catalog
    claws = w["weapon.melee.razor_claws"]
    assert (claws.speed, claws.accuracy, claws.damage, claws.defense) == (1, 1, 4, 2)
    assert claws.artifact_rating == 1 and claws.attunement == 2

    lance = w["weapon.melee.flame_lance"]
    assert (lance.speed, lance.accuracy, lance.defense) == (12, 1, 0)

    bow = w["weapon.archery.powerbow_of_perfect_accuracy"]
    assert (bow.accuracy, bow.damage, bow.rate, bow.range) == (3, 3, 2, 350)

    # Night's mundane missile table: crossbows do FLAT damage, slings/blowguns add
    # Strength — the distinction is recorded in `notes`, since the model has no field.
    assert w["weapon.archery.siege_crossbow"].damage == 8
    assert "Rate 1/10" in w["weapon.archery.siege_crossbow"].notes
    assert "Strength + 2L" in w["weapon.thrown.sling"].notes

    # The Ultimately Useful Tube and the Gauntlets of Distant Claws each have two
    # profiles, so each is TWO catalog rows sharing one artifact rating.
    for a, b in (("weapon.melee.ultimately_useful_tube_staff",
                  "weapon.thrown.ultimately_useful_tube_blowgun"),
                 ("weapon.melee.gauntlets_of_distant_claws",
                  "weapon.thrown.gauntlets_of_distant_claws_fired")):
        assert w[a].artifact_rating == w[b].artifact_rating

    a = rs.armor_catalog
    shirt = a["armor.artifact.chain_shirt"]
    assert (shirt.soak_lethal, shirt.soak_bashing) == (5, 3)
    assert shirt.artifact_rating == 2 and shirt.attunement == 3
    cloak = a["armor.artifact.cloak_of_vanishing_escape"]
    assert (cloak.soak_lethal, cloak.soak_bashing) == (1, 1)
    assert cloak.artifact_rating == 4 and cloak.attunement == 5
