"""Tests for the Storyteller's adversary roster — the extras, beasts and NPCs a
GM runs against the party.

Two invariants are worth guarding here and most of this file exists for them:

  1. An Adversary is NOT a Character. It has no chargen, no lock and no XP
     ledger, and nothing in engine.validate or engine.advancement may ever grow
     an opinion about one.
  2. Instantiating a template yields an INDEPENDENT copy. Five bandits off one
     catalogue row must have five separate health tracks, or the feature is no
     better than hand-copying, which is the problem it exists to solve.
"""

from pathlib import Path

import pytest

from exalted_builder import persistence, rules_db
from exalted_builder.engine import adversaries as adv
from exalted_builder.models.adversary import (Adversary, AdversaryAttack,
                                              AdversaryTrait)
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.models.character import Character, Damage

_DATA_DIR = Path("exalted_builder/data")


@pytest.fixture(scope="module")
def ruleset():
    return rules_db.load_ruleset(_DATA_DIR)


def _extra() -> Adversary:
    """A Weak extra exactly as p.241 prints it: four numbers and three boxes."""
    return Adversary(id="adv.thug", name="Hired Thug", categories=["Extra"],
                     base_initiative=4, willpower=3,
                     virtues={"valor": 2},
                     health_levels=adv.expand_health("-1/-3/I"))


# --------------------------------------------------------------------------- #
# The model: optional everywhere, and not a Character
# --------------------------------------------------------------------------- #

def test_only_name_and_id_are_needed():
    """An extra fills four fields. Everything else must stay absent rather than
    defaulting to a zero the book never printed."""
    a = Adversary(id="adv.x")
    assert a.name == "" and a.attributes == {} and a.abilities == []
    assert a.base_initiative is None and a.dodge is None
    assert a.health_levels == [] and a.damage == []


def test_dodge_is_nullable_not_zero():
    """p.316's Bear prints no dodge and p.307's Nagezzer prints "Does not dodge".
    Absent must be distinguishable from a pool of 0 — they are different rules."""
    bear = Adversary(id="adv.bear", dodge=None)
    coward = Adversary(id="adv.c", dodge=0)
    assert bear.dodge is None and coward.dodge == 0


def test_charms_and_spells_are_prose_not_ids(ruleset):
    """The book prints "All Solar Charms the Storyteller cares to give him"
    (p.303). There is nothing to resolve, and resolving is what the loader's
    link-checking would try to do. Store the sentence."""
    a = Adversary(id="adv.dl",
                  charms="All Solar Charms the Storyteller cares to give him.",
                  spells="All three circles of sorcery.")
    assert "Storyteller" in a.charms
    # The invariant: no Charm id anywhere in the value, and no lookup performed.
    assert a.charms not in ruleset.charms


def test_attributes_omit_rather_than_zero():
    """A beast prints three of the nine Attributes (p.316) and the page states
    the rest default to Int 1 / Per 2 / Wits 3. Storing the absent six as 0 would
    claim the book printed a zero."""
    beast = Adversary(id="adv.boar", attributes={"strength": 4, "dexterity": 2,
                                                 "stamina": 4})
    assert set(beast.attributes) == {"strength", "dexterity", "stamina"}
    assert "wits" not in beast.attributes


def test_attack_defense_is_optional_for_beasts():
    """p.317: "use the provided Atk value for both attacks and parries" — a beast
    has no Defense column, so Defense must be absent, not 0."""
    bite = AdversaryAttack(name="Bite", speed=6, accuracy=7, damage=1,
                           damage_type="L")
    fist = AdversaryAttack(name="Fist", speed=4, accuracy=3, damage=2,
                           damage_type="B", defense=3)
    assert bite.defense is None and fist.defense == 3


def test_two_mote_pool_shapes_coexist():
    """Spirits print one `Essence Pool: 112`; Terrestrials print Personal 11 /
    Peripheral 27. An entry uses one shape or the other."""
    spirit = Adversary(id="adv.f", essence=6, essence_pool=112,
                       cost_to_materialize=75)
    exalt = Adversary(id="adv.n", essence=3, personal_essence=11,
                      peripheral_essence=27)
    assert spirit.essence_pool == 112 and spirit.personal_essence == 0
    assert exalt.personal_essence == 11 and exalt.essence_pool == 0


def test_adversary_is_not_a_character():
    """The scope line, asserted. If someone later makes Adversary subclass or
    embed Character, this fails and they have to argue for it."""
    assert not issubclass(Adversary, Character)
    assert "play" not in Adversary.model_fields          # no PlayState
    assert "xp_log" not in Adversary.model_fields        # no ledger
    assert "chargen" not in Adversary.model_fields       # no snapshot/lock


# --------------------------------------------------------------------------- #
# Health notation
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("printed, expected", [
    ("-1/-3/I", [-1, -3, adv.INCAPACITATED]),                       # extra, p.241
    ("-0/-1/-1/-2/-2/-4/Incap",                                     # NPC, p.277
     [0, -1, -1, -2, -2, -4, adv.INCAPACITATED]),
    ("-0/-1 x 2/-2 x 2/-4/I", [0, -1, -1, -2, -2, -4, adv.INCAPACITATED]),
])
def test_expand_health_printed_tracks(printed, expected):
    assert adv.expand_health(printed) == expected


def test_expand_health_repeat_notation_is_long():
    """The Mask of Winters, p.303: `-0/-1 x 7/-2 x 12/-4/Incap` is 22 boxes."""
    levels = adv.expand_health("-0/-1 x 7/-2 x 12/-4/Incap")
    assert len(levels) == 22
    assert levels.count(-1) == 7 and levels.count(-2) == 12


def test_expand_health_tolerates_junk():
    """This runs on GM keystrokes, so it must not raise mid-typing."""
    assert adv.expand_health("-1/??/-3") == [-1, -3]
    assert adv.expand_health("") == []


def test_format_health_round_trips():
    for printed in ("-1/-3/Incap", "-0/-1 x 7/-2 x 12/-4/Incap"):
        assert adv.expand_health(adv.format_health(
            adv.expand_health(printed))) == adv.expand_health(printed)


def test_format_health_uses_repeat_notation():
    assert adv.format_health([0, -1, -1, -1, adv.INCAPACITATED]) == "0/-1 x 3/Incap"


# --------------------------------------------------------------------------- #
# The damage tracker
# --------------------------------------------------------------------------- #

def test_marks_cycle_like_the_play_tab():
    a = _extra()
    for expected in (Damage.BASHING, Damage.LETHAL, Damage.AGGRAVATED, None):
        adv.cycle_mark(a, 0)
        assert a.damage[0] is expected


def test_damage_track_normalises_to_health_levels():
    """Editing the track later must not corrupt the marks already on it."""
    a = _extra()
    adv.cycle_mark(a, 2)
    a.health_levels = adv.expand_health("-0/-1/-1/-2/-4/I")
    marks = adv.normalize_damage(a)
    assert len(marks) == 6
    assert marks[2] is Damage.BASHING            # the existing mark survives
    a.health_levels = [-1]
    assert len(adv.normalize_damage(a)) == 1


def test_worst_penalty_reads_the_deepest_mark():
    a = _extra()
    assert adv.worst_penalty(a) is None
    adv.cycle_mark(a, 0)
    assert adv.worst_penalty(a) == -1
    adv.cycle_mark(a, 1)
    assert adv.worst_penalty(a) == -3


def test_worst_penalty_does_not_enforce_fill_order():
    """The GM decides which boxes are ticked; this is a read, not a rule."""
    a = _extra()
    adv.cycle_mark(a, 2)
    assert adv.worst_penalty(a) == adv.INCAPACITATED


# --------------------------------------------------------------------------- #
# Armour: mundane only, and it drives soak and the dodge penalty
# --------------------------------------------------------------------------- #

def test_armor_options_exclude_artifacts(ruleset):
    """The human's ruling: filter artifact armour out of the picker."""
    options = adv.armor_options(ruleset)
    assert options, "expected some mundane armour in the catalogue"
    assert all(a.artifact_rating == 0 for a in options)
    artifacts = [a for a in ruleset.armor_catalog.values() if a.artifact_rating]
    assert artifacts, "catalogue should contain artifact armour to exclude"
    assert not ({a.id for a in options} & {a.id for a in artifacts})


def test_soak_is_natural_plus_armor(ruleset):
    """Elite Troops print 6L/12B from 0L/4B of skin plus the armour (p.279)."""
    worn = adv.armor_options(ruleset)[0]
    a = Adversary(id="adv.s", soak_lethal=0, soak_bashing=4, armor_id=worn.id)
    assert adv.soak(ruleset, a) == (worn.soak_lethal, 4 + worn.soak_bashing)


def test_soak_without_armor_is_natural_only(ruleset):
    a = Adversary(id="adv.s", soak_lethal=3, soak_bashing=6)
    assert adv.soak(ruleset, a) == (3, 6)


def test_unresolvable_armor_degrades_gracefully(ruleset):
    """A stale id must not raise — the rest of the app treats them the same way."""
    a = Adversary(id="adv.s", soak_lethal=1, soak_bashing=2, armor_id="armor.nope")
    assert adv.armor_of(ruleset, a) is None
    assert adv.soak(ruleset, a) == (1, 2)


def test_dodge_after_armor_applies_the_mobility_penalty(ruleset):
    """p.278's "Dodge Pool: 4/3" is base 4 less a -1 mobility penalty. Only the
    base is stored; the second number is derived."""
    penalised = next(a for a in adv.armor_options(ruleset) if a.mobility_penalty)
    a = Adversary(id="adv.d", dodge=4, armor_id=penalised.id)
    assert adv.dodge_after_armor(ruleset, a) == max(
        0, 4 - abs(penalised.mobility_penalty))


def test_dodge_after_armor_never_goes_negative(ruleset):
    penalised = next(a for a in adv.armor_options(ruleset) if a.mobility_penalty)
    a = Adversary(id="adv.d", dodge=0, armor_id=penalised.id)
    assert adv.dodge_after_armor(ruleset, a) == 0


def test_no_dodge_stays_none_through_armor(ruleset):
    """A bear in a buff jacket still does not dodge."""
    worn = adv.armor_options(ruleset)[0]
    a = Adversary(id="adv.bear", dodge=None, armor_id=worn.id)
    assert adv.dodge_after_armor(ruleset, a) is None


# --------------------------------------------------------------------------- #
# Instancing — the reason the feature is worth building
# --------------------------------------------------------------------------- #

def test_instantiate_copies_the_template():
    tpl = _extra()
    one = adv.instantiate(tpl, "adv.1")
    assert one.id == "adv.1" and one.template_id == tpl.id
    assert one.name == tpl.name and one.health_levels == tpl.health_levels


def test_five_bandits_have_five_health_tracks():
    """The whole point. Damaging one must not touch the others or the template."""
    tpl = _extra()
    bandits = [adv.instantiate(tpl, f"adv.{i}", name=f"Bandit {i + 1}")
               for i in range(5)]
    adv.cycle_mark(bandits[2], 0)
    assert adv.worst_penalty(bandits[2]) == -1
    assert all(adv.worst_penalty(b) is None for i, b in enumerate(bandits) if i != 2)
    assert adv.worst_penalty(tpl) is None
    assert [b.name for b in bandits] == [f"Bandit {i + 1}" for i in range(5)]


def test_instantiate_deep_copies_nested_lists():
    """A shallow copy would share the attack list between every bandit."""
    tpl = _extra()
    tpl.abilities = [AdversaryTrait(name="Melee", rating=2)]
    tpl.attacks = [AdversaryAttack(name="Fist", speed=4, accuracy=3, damage=2)]
    one = adv.instantiate(tpl, "adv.1")
    one.abilities[0].rating = 5
    one.attacks[0].accuracy = 9
    assert tpl.abilities[0].rating == 2 and tpl.attacks[0].accuracy == 3


def test_instantiate_clears_tracked_state():
    """Duplicating a bloodied bandit gives a fresh one, not a bloodied clone."""
    tpl = _extra()
    adv.cycle_mark(tpl, 0)
    tpl.willpower_spent, tpl.motes_spent = 2, 7
    fresh = adv.instantiate(tpl, "adv.1")
    assert fresh.damage == [] and fresh.willpower_spent == 0 and fresh.motes_spent == 0


# --------------------------------------------------------------------------- #
# The bundle carries them
# --------------------------------------------------------------------------- #

def test_party_defaults_to_no_adversaries():
    assert Party(id="p").adversaries == []


def test_adversaries_round_trip_through_the_bundle(tmp_path):
    p = Party(id="p", name="Tonight",
              members=[PartyMember(character=Character(id="c", name="Ash"))])
    b = adv.instantiate(_extra(), "adv.1", name="Bandit 1")
    adv.cycle_mark(b, 0)
    b.notes = "fled north"
    p.adversaries.append(b)

    target = tmp_path / "t.party.json"
    persistence.save_party(p, target)
    loaded = persistence.load_party(target)

    assert len(loaded.adversaries) == 1
    got = loaded.adversaries[0]
    assert got.name == "Bandit 1" and got.notes == "fled north"
    assert got.damage[0] is Damage.BASHING
    assert got.health_levels == b.health_levels


def test_old_bundles_without_adversaries_still_load(tmp_path):
    """Bundles saved before the roster existed must not fail to parse."""
    target = tmp_path / "old.party.json"
    target.write_text('{"id":"p","name":"Old","members":[],"session_notes":""}')
    assert persistence.load_party(target).adversaries == []


# --------------------------------------------------------------------------- #
# The catalogue
#
# Generic templates only — the human's 2026-08-01 ruling. The named individuals
# in the same chapter (Fakharu, the Mask of Winters, Sesus Nagezzer, Denovah
# Avaku, Ahn-Aru, Typhon, Juggernaut) are NOT catalogue rows, and the Fair Folk
# are out of scope entirely under decision 0010.
#
# The soak/dodge assertions below are the real check on the transcription: the
# book prints the TOTAL, this file stores natural soak plus an armour id, and the
# engine has to put them back together into the printed figure.
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def catalog():
    return rules_db.load_adversary_catalog(_DATA_DIR)


def test_catalogue_loads(catalog):
    assert len(catalog) >= 49
    assert all(t.id == key for key, t in catalog.items())
    assert all(t.name for t in catalog.values())


def test_the_four_exalt_templates_are_roles_not_people(catalog):
    """The corebook stats Exalted only as named individuals, but four of those
    blocks sit under ROLE headings and are plainly meant as archetypes — the
    book says so itself of one: "Avaku could be any ambitious young
    Dragon-Blooded warrior" (p.308). Those four are in, with the names stripped;
    the genuinely unique ones (Fakharu, the Mask of Winters, Juggernaut) are not.

    Human's ruling 2026-08-01, taking option 2 of three."""
    exalts = {t.name for t in catalog.values() if "Exalt" in t.categories}
    assert exalts == {"Dynasty Noble", "Ambitious Young Officer",
                      "Bronze Faction Functionary", "Deathknight"}
    for t in (x for x in catalog.values() if "Exalt" in x.categories):
        assert t.caste, f"{t.name} should carry its Caste/Aspect"
        assert t.personal_essence and t.peripheral_essence, t.name


def test_the_lunar_trickster_is_deliberately_absent(catalog):
    """The fifth role-headed Exalt block (p.309-310) is NOT authored. Magnificent
    Jaguar's statblock prints every combat number as a base//combat-form PAIR, and
    alternate forms are deliberately unmodelled — so half his block has nowhere to
    go and inventing the other half is not an option. Recorded as a test so the
    omission reads as a decision rather than an oversight."""
    assert not any("trickster" in t.name.lower() or "jaguar" in t.name.lower()
                   for t in catalog.values())


def test_an_exalt_that_does_not_dodge_keeps_none(catalog):
    """The Dynasty Noble prints "Dodge Total: Does not dodge" and "Attack: Charms
    only" — he is a social predator with no combat line at all."""
    noble = catalog["adv.dynasty_noble"]
    assert noble.dodge is None
    assert noble.attacks == []
    assert noble.base_initiative is None
    assert "Charms only" in noble.notes


def test_every_template_is_generic_not_a_named_individual(catalog):
    """The scope ruling, asserted. If a named NPC is ever added, this fails and
    whoever added it has to reopen the decision."""
    named = {"fakharu", "erymanthus", "mask of winters", "nagezzer", "avaku",
             "ahn-aru", "sad ivory", "typhon", "juggernaut", "magnificent jaguar"}
    for t in catalog.values():
        assert not any(n in t.name.lower() for n in named), t.name


def test_no_fair_folk(catalog):
    """Decision 0010: permanently out of scope, statblocks included."""
    for t in catalog.values():
        assert "fair folk" not in t.name.lower()
        assert "fair folk" not in adv.category_label(t).lower()


def test_the_three_extra_tiers_are_p241(catalog):
    """p.241 prints four numbers per tier and three health levels."""
    for key, init, pool, valor, wp in (("adv.extra_weak", 4, 4, 2, 3),
                                       ("adv.extra_competent", 5, 5, 3, 4),
                                       ("adv.extra_elite", 6, 6, 4, 6)):
        t = catalog[key]
        assert (t.base_initiative, t.combat_pool) == (init, pool)
        assert t.virtues["valor"] == valor and t.willpower == wp
        assert t.health_levels == [-1, -3, adv.INCAPACITATED]
        # An extra has no Attributes or Abilities at all — one pool covers them.
        assert t.attributes == {} and t.abilities == []


@pytest.mark.parametrize("key, printed_l, printed_b", [
    ("adv.militia", 3, 6),          # p.278 "Soak: 3L/6B (Buff jacket, 3L/4B…)"
    ("adv.infantry", 5, 9),         # p.278 "Soak: 5L/9B (Reinforced buff jacket…)"
    ("adv.elite_troops", 6, 12),    # p.278 "Soak: 6L/12B (Lamellar armor…)"
    ("adv.merchant_prince", 5, 8),  # p.279 "Soak: 5L/8B (Reinforced buff jacket…)"
    ("adv.heretic", 3, 6),          # p.277 "Soak: 3L/6B (Buff jacket…)"
    ("adv.war_ghost", 7, 10),       # p.301 "Soak: 7L/10B (Chain hauberk…)"
    ("adv.nemissary", 6, 12),       # p.301 "Soak: 6L/12B (Breastplate…)"
    ("adv.typical_citizen", 0, 2),  # p.276 "Soak: 0L/2B (Skin)"
])
def test_soak_adds_back_up_to_the_printed_total(ruleset, catalog, key, printed_l, printed_b):
    assert adv.soak(ruleset, catalog[key]) == (printed_l, printed_b)


@pytest.mark.parametrize("key, base, printed_after", [
    ("adv.militia", 4, 3),            # p.278 "Dodge Pool: 4/3" — buff jacket, no shield
    ("adv.infantry", 3, 0),           # p.278 "Dodge Pool: 3/0" — reinforced -2, shield -1
    ("adv.elite_troops", 5, 2),       # p.278 "Dodge Pool: 5/2" — lamellar -2, shield -1
    ("adv.wyld_barbarian", 4, 2),     # p.282 "Dodge Pool: 4/2" — buff jacket -1, shield -1
])
def test_dodge_derives_the_second_printed_number(ruleset, catalog, key, base,
                                                 printed_after):
    """The human's ruling: only the base dodge is stored, and the mobility
    penalties of the worn armour AND the carried shield derive the rest.

    This used to come out one too high on the three shield-carrying rows,
    recorded as a known gap. The p.335 shield rules closed it: a target shield
    "adds 1 to the mobility penalty of her armor", so it simply sums. Every
    printed pair in the catalogue now round-trips."""
    t = catalog[key]
    assert t.dodge == base
    assert adv.dodge_after_armor(ruleset, t) == printed_after


def test_shields_give_no_soak(ruleset, catalog):
    """p.335 describes shields entirely in terms of difficulty and mobility —
    they add nothing to soak, so carrying one must not move the printed total."""
    t = catalog["adv.elite_troops"]
    assert t.shield_id == "shield.target"
    assert adv.soak(ruleset, t) == (6, 12)          # p.278's figure, unchanged


def test_shield_difficulty_is_carried_for_display(ruleset, catalog):
    """The statblocks print "+1 difficulty to attack" and nothing here resolves an
    attack (decision 0008), so the number is surfaced for the ST to apply."""
    assert adv.attack_difficulty(ruleset, catalog["adv.elite_troops"]) == (1, 1)
    assert adv.attack_difficulty(ruleset, catalog["adv.militia"]) == (0, 0)


def test_the_three_printed_shields_are_authored(ruleset):
    """p.335: buckler, target shield, tower shield.

    They are ARMOUR ROWS tagged "shield", not a model of their own — a shield is
    worn equipment with a mobility penalty and no soak, and a Character's armour
    is already a list, so this gets characters shields with no new machinery."""
    shields = {s.id: s for s in ruleset.shields()}
    assert set(shields) == {"shield.buckler", "shield.target", "shield.tower"}
    assert all("shield" in s.tags for s in shields.values())
    # the buckler "does nothing to protect the character from missile fire"
    assert shields["shield.buckler"].difficulty_ranged == 0
    assert shields["shield.buckler"].mobility_penalty == 0
    # a tower shield raises ranged difficulty by 2 and costs 2 mobility
    assert shields["shield.tower"].difficulty_ranged == 2
    assert shields["shield.tower"].mobility_penalty == -2
    # none of them grant soak, so summing one into a soak total changes nothing
    assert all(s.soak_lethal == 0 and s.soak_bashing == 0 for s in shields.values())


def test_shields_do_not_appear_in_the_body_armour_list(ruleset):
    """The two views must not overlap, or a GM picking "armour" is offered a
    buckler and the character sheet lists a shield as a suit. Helms (core pp.334-335)
    joined the catalogue as the third accessory kind and are excluded for the same
    reason — the three views partition the catalogue between them."""
    assert not ({a.id for a in ruleset.body_armor()} & {s.id for s in ruleset.shields()})
    assert not ({a.id for a in ruleset.body_armor()} & {h.id for h in ruleset.helms()})
    assert not ({h.id for h in ruleset.helms()} & {s.id for s in ruleset.shields()})
    assert (len(ruleset.body_armor()) + len(ruleset.shields()) + len(ruleset.helms())
            == len(ruleset.armor_catalog))


def test_a_character_can_hold_a_shield_in_its_armour_list(ruleset):
    """The reason shields are armour rows: a Character needs no new field. Its
    armour list takes one, and because a shield has no soak the total is
    unchanged while the mobility penalty shows on the sheet."""
    from exalted_builder.engine import derive
    from exalted_builder.models.character import Armor, Character

    shield = next(s for s in ruleset.shields() if s.id == "shield.target")
    c = Character(id="c", name="Guard", caste="dawn")
    c.armor.append(Armor(name="Buff Jacket", soak_lethal=3, soak_bashing=4,
                         mobility_penalty=-1))
    before = derive.soak(c, ruleset)
    c.armor.append(Armor(name=shield.name, soak_lethal=0, soak_bashing=0,
                         mobility_penalty=shield.mobility_penalty))
    after = derive.soak(c, ruleset)
    assert (after.lethal, after.bashing) == (before.lethal, before.bashing)
    assert sum(a.mobility_penalty for a in c.armor) == -2


def test_every_shield_reference_resolves(ruleset, catalog):
    shield_ids = {s.id for s in ruleset.shields()}
    for t in catalog.values():
        if t.shield_id:
            assert t.shield_id in shield_ids, f"{t.name}: {t.shield_id}"


def test_beasts_carry_the_p317_default_attributes(catalog):
    """p.317: assume Intelligence 1, Perception 2 and Wits 3 unless stated."""
    beasts = [t for t in catalog.values() if "Beast" in t.categories]
    assert len(beasts) >= 20
    for b in beasts:
        assert b.attributes["intelligence"] == 1
        assert b.attributes["perception"] == 2
        assert b.attributes["wits"] == 3
        # and the three the table actually prints
        assert {"strength", "dexterity", "stamina"} <= set(b.attributes)


def test_a_beast_with_no_printed_dodge_has_none(catalog):
    """The Bear's row prints only "3L/6B" — no dodge figure at all."""
    bear = catalog["adv.beast_bear"]
    assert bear.dodge is None
    assert (bear.soak_lethal, bear.soak_bashing) == (3, 6)


def test_beast_attacks_have_no_defense(catalog):
    """p.317 says to use the Atk value for parries, so the table has no Defense
    column and none may be invented."""
    for t in catalog.values():
        if "Beast" in t.categories:
            assert all(a.defense is None for a in t.attacks), t.name


def test_zombie_has_no_virtues(catalog):
    """p.299: "Virtues: Not applicable." An empty map, not four zeroes."""
    assert catalog["adv.common_zombie"].virtues == {}


def test_elemental_pays_to_dematerialize_not_materialize(catalog):
    """p.295/298: an elemental's natural state is the physical one."""
    z = catalog["adv.zephyr"]
    assert z.cost_to_dematerialize == 50 and z.cost_to_materialize == 0
    ghost = catalog["adv.war_ghost"]
    assert ghost.cost_to_materialize == 40 and ghost.cost_to_dematerialize == 0


def test_charms_and_powers_stay_prose_in_the_catalogue(ruleset, catalog):
    """No catalogue row may smuggle in a Charm id — these are printed names and
    sentences, and nothing resolves them."""
    for t in catalog.values():
        assert t.charms not in ruleset.charms
        assert t.powers not in ruleset.charms


def test_every_armor_reference_resolves(ruleset, catalog):
    """A typo'd armour id would silently drop the soak it was meant to add."""
    for t in catalog.values():
        if t.armor_id:
            assert t.armor_id in ruleset.armor_catalog, f"{t.name}: {t.armor_id}"
            assert not ruleset.armor_catalog[t.armor_id].artifact_rating


def test_the_yeddim_trample_has_no_invented_numbers(catalog):
    """p.317 prints "-2x3/-4/I" in the Yeddim's Attack column — health-level
    notation, not Speed/Accuracy/Damage. The human ruled it a misprint
    (2026-08-01): almost certainly the health track's own continuation typeset
    into the wrong column, which is why the health track ends in exactly those
    boxes. So the attack is named and left unrated.

    This test exists because a plausible number is the easy thing to add here,
    and the never-author-from-memory rule says it must not be."""
    y = catalog["adv.beast_yeddim"]
    trample = next(a for a in y.attacks if a.name == "Trample")
    assert (trample.speed, trample.accuracy, trample.damage) == (None, None, None)
    assert "misprint" in trample.note
    # the figures printed in the Attack column are the tail of the health track
    assert y.health_levels[-5:] == [-2, -2, -2, -4, adv.INCAPACITATED]


def test_templates_carry_no_tracked_state(catalog):
    """A template is a starting point, never a played entity."""
    for t in catalog.values():
        assert t.damage == [] and t.willpower_spent == 0 and t.motes_spent == 0
        assert t.template_id == ""


# --------------------------------------------------------------------------- #
# The roster mutations — shared by BOTH shells (ui/adversaries.py, qt/adversaries.py)
# --------------------------------------------------------------------------- #

def _played() -> Adversary:
    return Adversary(id="a.1", name="Bandit", willpower=3, essence_pool=10,
                     health_levels=adv.expand_health("-1/-3/I"),
                     damage=[Damage.LETHAL, None, None],
                     willpower_spent=2, motes_spent=5)


def test_reset_clears_exactly_what_instantiate_clears():
    """⚠ The two must agree on which fields are TRACKED. `instantiate` gives a duplicate
    a fresh start and `reset_tracking` gives an existing entry one — a new tracked field
    added to one and not the other means a "fresh" adversary carrying spent motes."""
    source = _played()
    fresh = adv.instantiate(source, "a.2")
    reset = source.model_copy(deep=True)
    adv.reset_tracking(reset)
    for field in Adversary.model_fields:
        if field in ("id", "name", "template_id"):
            continue
        assert getattr(fresh, field) == getattr(reset, field), field


def test_add_blank_gives_the_extras_printed_three_levels():
    """p.241: an extra has three health levels. A blank entry with an EMPTY track has no
    boxes to click, which is not what "bare minimum" means."""
    party = Party(id="p")
    entry = adv.add_blank(party)
    assert party.adversaries == [entry]
    assert len(entry.health_levels) == 3


def test_duplicate_sits_beside_its_original_and_is_numbered():
    party = Party(id="p", adversaries=[_played(), Adversary(id="a.9", name="Wolf")])
    copy = adv.duplicate(party, 0)
    assert [a.name for a in party.adversaries] == ["Bandit", "Bandit 2", "Wolf"]
    assert copy.damage == [] and copy.id not in ("a.1", "a.9")


def test_remove_returns_the_name_it_dropped():
    party = Party(id="p", adversaries=[_played()])
    assert adv.remove(party, 0) == "Bandit"
    assert party.adversaries == []


def test_the_mote_cap_is_whichever_pool_shape_the_entry_uses():
    """A spirit prints one pool; an Exalt prints Personal + Peripheral. Both spend
    downward against ONE counter — splitting it would be tracking for its own sake."""
    assert adv.mote_cap(Adversary(id="a", essence_pool=112)) == 112
    assert adv.mote_cap(Adversary(id="b", personal_essence=11,
                                  peripheral_essence=27)) == 38
    assert adv.mote_cap(Adversary(id="c")) == 0


def test_setting_motes_clamps_to_that_cap():
    entry = Adversary(id="a", essence_pool=10)
    adv.set_motes_spent(entry, 99)
    assert entry.motes_spent == 10
    adv.set_motes_spent(entry, -3)
    assert entry.motes_spent == 0


def test_a_count_track_fills_to_the_click_and_empties_back():
    """The same behaviour `engine.play.set_count` gives a character — one tracker to
    learn, not two."""
    entry = _played()
    adv.set_count(entry, "willpower_spent", 2, entry.willpower)
    assert entry.willpower_spent == 3
    adv.set_count(entry, "willpower_spent", 2, entry.willpower)
    assert entry.willpower_spent == 2


# --------------------------------------------------------------------------- #
# Categories — a LIST of equal filing labels (human, 2026-08-27)
# --------------------------------------------------------------------------- #

def test_the_category_codec_round_trips():
    """⚠ `category_line` and `parse_categories` are a CODEC PAIR, like the trait and
    attack pairs: one fills the input, the other reads it back."""
    for text in ("", "Extra", "Undead, Soldier", "Beast, Wyld, Darkbrood"):
        assert adv.category_line(adv.parse_categories(text)) == text


def test_parsing_categories_trims_drops_blanks_and_keeps_the_typed_order():
    """Order is the GM's, not alphabetical — they typed the one they file it under
    first. Duplicates go, because a chip list with "Undead" twice is a bug on screen."""
    assert adv.parse_categories(" Undead , , Soldier ,Undead") == ["Undead", "Soldier"]
    assert adv.parse_categories("   ") == []


def test_an_entry_is_filed_under_every_category_it_carries():
    """The whole point of the list: a picker's chips must offer BOTH, or a two-headed
    entry is unfindable under one of them."""
    templates = [Adversary(id="a", name="Legionnaire",
                           categories=["Undead", "Soldier"]),
                 Adversary(id="b", name="Bear", categories=["Beast"])]
    groups = adv.catalogue_groups(templates)
    assert groups["a"] == ["Undead", "Soldier"]
    assert [k for k, v in groups.items() if "Soldier" in v] == ["a"]
    assert [k for k, v in groups.items() if "Beast" in v] == ["b"]


def test_the_display_label_joins_them():
    assert adv.category_label(Adversary(id="a", categories=["Undead", "Soldier"])) == \
        "Undead  ·  Soldier"
    assert adv.category_label(Adversary(id="b")) == ""


def test_every_catalogue_row_still_carries_at_least_one_category(catalog):
    """⚠ The catalogue was CONVERTED, not re-authored: each template keeps exactly the
    heading the book filed it under, as a one-element list. Adding a second to any of
    them is an authoring decision that needs the page, not a migration."""
    for t in catalog.values():
        assert t.categories, f"{t.name} lost its category in the conversion"
        assert len(t.categories) == 1, (
            f"{t.name} gained a category the books did not print — "
            f"{t.categories}. That is authoring, and needs a page behind it.")
