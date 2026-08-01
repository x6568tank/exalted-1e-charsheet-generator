"""The four Dragon-Blooded origins from Exalted: The Outcaste, and the `upbringing`
axis they needed.

Each book prints a Character Creation Summary that varies the budget by how the
character was RAISED while everything else about the origin holds, so origin alone
could not key the rows:

  * Lookshy and the Seventh Legion, p.68-69 (`images/Dragonblooded/Origins/
    Lookshy 65-66/`) — 13 Backgrounds, 6 Charms, its own Ability minimums; a
    Terrestrial not raised in Lookshy gets 25 Ability dots instead of 35.
  * The Forest Witches, p.132-133 — 6 Virtue dots; ex-Dynasts 35, other outcastes 25,
    and one raised by Oreithyia buys Virtues at 2 BP and Essence at 8.
  * Lost Eggs, p.159-160 — 7 Backgrounds and a dearer Background BP rate (2/3);
    lower-class 25, patrician-born 30, Threshold 25.
  * Eos and Ossissa (the pirates), p.96-97 — every pirate needs Sail, Dynast or not.

The cascade is `"E:o:u"` -> `"E:o"` -> `"E"` -> default (`models.rules._keyed_row`),
which is what lets an origin with no variants author no upbringing rows and lets the
three Lost Egg upbringings share one bonus-point row.

NOT modelled, deliberately (see CLAUDE.md -> TODO): the numina / Mist aspect, whose
pages have not landed.
"""

from pathlib import Path

import pytest
from nicegui.testing import User

import exalted_builder
from exalted_builder import rules_db
from exalted_builder.engine import validate
from exalted_builder.models.character import BackgroundEntry, Character
from exalted_builder.models.rules import AbilityName as AB

DATA_DIR = Path(exalted_builder.__file__).parent / "data"

DB = "Dragon-Blooded"


@pytest.fixture(scope="module")
def rs():
    return rules_db.load_ruleset(DATA_DIR)


def _mins(budget) -> dict[tuple[str, ...], int]:
    """The row's Ability minimums as {(ability, ...): rating}, so a test can name the
    'Brawl or Martial Arts' pair as the OR-group it is."""
    return {tuple(sorted(a.value for a in m.abilities)): m.rating
            for m in budget.required_min_abilities}


# --- the printed budgets ----------------------------------------------------- #

@pytest.mark.parametrize("origin,upbringing,dots,cf,backgrounds,charms,virtues", [
    # origin              upbringing    ability dots / on Aspect-Favored, bg, charms, virtues
    ("lookshy",           "",           35, 13, 13, 6, 5),   # p.68
    ("lookshy",           "foreign",    25, 10, 13, 6, 5),   # p.68 "not raised in Lookshy"
    ("forest-witch",      "",           35, 13, 12, 7, 6),   # p.132 ex-Dynast
    ("forest-witch",      "outcaste",   25, 10, 12, 7, 6),   # p.132 "raised elsewhere"
    ("forest-witch",      "oreithyia",  25, 10, 12, 7, 6),   # p.132
    ("lost-egg",          "",           25, 13,  7, 7, 5),   # p.159 lower-class birth
    ("lost-egg",          "graduate",   25, 13,  7, 7, 5),   # p.159 Pasiap's Stair / Cloister
    ("lost-egg",          "patrician",  30, 13,  7, 7, 5),   # p.159 patrician-born
    ("lost-egg",          "threshold",  25, 10,  7, 7, 5),   # p.159 Threshold outcaste
    ("pirate",            "",           35, 13, 12, 7, 5),   # p.96 Dynast
    ("pirate",            "outcaste",   25, 10, 12, 7, 5),   # p.96 born outcaste
])
def test_origin_budgets_match_the_character_creation_summaries(
        rs, origin, upbringing, dots, cf, backgrounds, charms, virtues):
    b = rs.budgets_for(DB, origin, upbringing)
    assert (b.ability_dots, b.ability_min_caste_favored) == (dots, cf)
    assert b.background_dots == backgrounds
    assert b.charm_count == charms
    assert b.virtue_dots == virtues
    # Constant across all four books.
    assert tuple(b.attribute_pools) == (7, 6, 4)
    assert b.favored_count == 3
    assert b.charm_min_caste_favored == 4
    assert b.essence_start == 2
    assert b.bonus_points == 15


def test_lost_eggs_keep_13_caste_favored_out_of_only_25_dots(rs):
    """Printed as-is on p.159 and deliberately NOT 'corrected' to 10: an outcaste of
    lower-class birth "receive[s] 25 Ability points — at least 13 must be from Aspect
    or Favored Abilities". Only the Threshold row drops to 10."""
    assert rs.budgets_for(DB, "lost-egg").ability_min_caste_favored == 13
    assert rs.budgets_for(DB, "lost-egg", "threshold").ability_min_caste_favored == 10


# --- the Ability minimums ---------------------------------------------------- #

def test_lookshy_born_minimums(rs):
    """p.68: "Characters born in Lookshy must have a minimum of Performance •,
    Presence •, Ride •, Stealth •, Archery ••, Brawl or Martial Arts ••, Lore ••,
    Melee •• and Linguistics •••." — the only origin whose floor reaches 3."""
    assert _mins(rs.budgets_for(DB, "lookshy")) == {
        ("performance",): 1, ("presence",): 1, ("ride",): 1, ("stealth",): 1,
        ("archery",): 2, ("brawl", "martial_arts"): 2, ("lore",): 2, ("melee",): 2,
        ("linguistics",): 3,
    }
    # A Lookshy Terrestrial raised elsewhere has no minimums at all.
    assert _mins(rs.budgets_for(DB, "lookshy", "foreign")) == {}


def test_oreithyia_raised_witches_have_the_forest_walkers_minimums(rs):
    """p.132: Athletics •, Awareness •, Brawl •, Stealth •, Endurance ••, Occult ••
    and Survival •• — a wilderness list, nothing like the Realm schooling one."""
    assert _mins(rs.budgets_for(DB, "forest-witch", "oreithyia")) == {
        ("athletics",): 1, ("awareness",): 1, ("brawl",): 1, ("stealth",): 1,
        ("endurance",): 2, ("occult",): 2, ("survival",): 2,
    }
    assert _mins(rs.budgets_for(DB, "forest-witch", "outcaste")) == {}


def test_realm_schooling_minimums_are_the_same_list_the_core_row_uses(rs):
    """The Dynasty-raised list is reprinted verbatim by the Forest Witch and Pirate
    books and by the patrician Lost Egg, so all four must agree with the core
    Dragon-Blooded row — if one drifts, one of them was mis-transcribed."""
    core = _mins(rs.budgets_for(DB))
    assert core == _mins(rs.budgets_for(DB, "forest-witch"))
    assert core == _mins(rs.budgets_for(DB, "lost-egg", "patrician"))
    # The pirate row is that list PLUS Sail (below), so subtract Sail to compare.
    pirate = _mins(rs.budgets_for(DB, "pirate"))
    assert {k: v for k, v in pirate.items() if k != ("sail",)} == core


def test_every_pirate_needs_sail_whichever_upbringing(rs):
    """p.96: "All pirate characters must have at least Sail •, whether Dynast or born
    outcaste." — the born-outcaste row has no other minimum, so Sail is the whole
    list there."""
    assert _mins(rs.budgets_for(DB, "pirate"))[("sail",)] == 1
    assert _mins(rs.budgets_for(DB, "pirate", "outcaste")) == {("sail",): 1}


def test_lost_egg_school_graduates_have_the_lighter_list(rs):
    """p.159, graduates of Pasiap's Stair or the Cloister of Wisdom — one dot each,
    and Performance OR Presence rather than both."""
    assert _mins(rs.budgets_for(DB, "lost-egg", "graduate")) == {
        ("archery",): 1, ("brawl", "martial_arts"): 1, ("lore",): 1, ("melee",): 1,
        ("performance", "presence"): 1, ("ride",): 1, ("socialize",): 1,
    }
    assert _mins(rs.budgets_for(DB, "lost-egg")) == {}


# --- the bonus-point rates --------------------------------------------------- #

def test_only_two_origins_deviate_from_the_dragon_blooded_bp_table(rs):
    """Lookshy p.69, Forest Witch p.133 and Pirate p.97 print the DB table key for
    key, so they need no row of their own. Two exceptions get one."""
    base = rs.bonus_costs_for(DB)
    assert (base.background, base.background_above_3) == (1, 2)
    assert (base.virtue, base.essence) == (3, 10)
    assert (base.immaculate_charm, base.immaculate_charm_favored_caste) == (10, 7)

    for origin in ("lookshy", "forest-witch", "pirate"):
        assert rs.bonus_costs_for(DB, origin) is base, origin


def test_lost_eggs_pay_more_per_background_dot(rs):
    """p.160: "Background 2 (3 if the Background is being raised above 3)" — every
    other Outcaste-book table says 1 (2)."""
    c = rs.bonus_costs_for(DB, "lost-egg")
    assert (c.background, c.background_above_3) == (2, 3)
    # ...and the rate is the origin's, so all three upbringings inherit it via the
    # cascade rather than repeating it.
    for up in ("graduate", "patrician", "threshold"):
        assert rs.bonus_costs_for(DB, "lost-egg", up) is c, up


def test_oreithyia_raised_witches_buy_virtues_and_essence_cheaper(rs):
    """p.133: "Virtue 3 (2 if raised by Oreithyia)", "Essence 10 (8 if raised by
    Oreithyia)". This is a rate that varies by UPBRINGING, not by origin — the
    reason bonus_costs_for needed the third key at all."""
    c = rs.bonus_costs_for(DB, "forest-witch", "oreithyia")
    assert (c.virtue, c.essence) == (2, 8)
    # The other two Forest Witch upbringings pay the ordinary rates.
    for up in ("", "outcaste"):
        other = rs.bonus_costs_for(DB, "forest-witch", up)
        assert (other.virtue, other.essence) == (3, 10), up


# --- the cascade itself ------------------------------------------------------ #

def test_an_unauthored_upbringing_falls_back_to_the_origin_row(rs):
    """A save naming an upbringing this origin never had must not fall all the way
    to the splat default and silently hand out the wrong budget."""
    assert rs.budgets_for(DB, "lookshy", "no-such-upbringing") is rs.budgets_for(DB, "lookshy")
    assert rs.budgets_for(DB, "no-such-origin", "foreign") is rs.budgets_for(DB)


def test_upbringing_alone_does_nothing_without_an_origin(rs):
    """`upbringing` is meaningful only under an origin — it is never a key on its own,
    so a stray value on a Solar cannot reach any row."""
    assert rs.budgets_for("Solar", "", "oreithyia") is rs.budgets_for("Solar")
    assert rs.bonus_costs_for("Solar", "", "patrician") is rs.bonus_costs_for("Solar")


def test_the_new_axis_leaves_every_existing_splat_untouched(rs):
    """The regression guard for adding a third key: no character anywhere has an
    upbringing yet, so every previously-authored row must still be what resolves."""
    for splat in ("Solar", "Abyssal", "Lunar", "Sidereal", "Alchemical", DB):
        assert rs.budgets_for(splat, "", "") is rs.budgets_for(splat)
        assert rs.bonus_costs_for(splat, "", "") is rs.bonus_costs_for(splat)
    # The two pre-existing Dragon-Blooded origins are unchanged.
    assert rs.budgets_for(DB, "outcaste").ability_dots == 25
    assert rs.budgets_for(DB, "dynastic") is rs.budgets_for(DB)


def test_the_character_carries_the_axis_and_defaults_to_empty(rs):
    c = Character(id="c", exalt_type=DB, caste="air")
    assert c.upbringing == ""
    c.origin, c.upbringing = "lost-egg", "patrician"
    assert rs.budgets_for(c.exalt_type, c.origin, c.upbringing).ability_dots == 30


# --- Lookshy's two free Charms and its Immaculate bar (p.68) ----------------- #

def _lookshy(rs, **kw) -> Character:
    c = Character(id="c.lookshy", exalt_type=DB, caste="air", origin="lookshy", **kw)
    c.abilities = {a: 3 for a in AB}
    return c


def test_lookshy_grants_two_charms_free_to_both_upbringings(rs):
    """p.68: "all Lookshy Dragon-Blooded have the Charms Wind-Carried Word Technique
    and Elemental Bolt Attack, at no cost." Our data spells them the way the core
    Dragon-Blooded book does — Wind-Carried WORDS Technique, ELEMENT Bolt Attack —
    which is the same pair of Charms."""
    granted = validate.origin_granted_charm_ids(rs, _lookshy(rs))
    assert granted == ["dragonblooded.linguistics.wind-carried-words-technique",
                       "dragonblooded.lore.element-bolt-attack"]
    assert all(rs.charms.get(cid) is not None for cid in granted)
    # Both upbringings; the page says "all Lookshy Dragon-Blooded", not "born there".
    assert validate.origin_granted_charm_ids(rs, _lookshy(rs, upbringing="foreign")) == granted
    # ...and nobody else grants anything.
    assert validate.origin_granted_charm_ids(rs, Character(id="x", exalt_type=DB)) == []


def test_origin_granted_charms_are_listed_but_cost_no_pick_and_no_bp(rs):
    """They flow through the one canonical enumeration, so the sheet shows them and
    the chargen counter and the BP pricing both ignore them."""
    c = _lookshy(rs)
    c.charms = ["dragonblooded.melee.dragon-graced-weapon"]
    picks = validate.charm_picks(rs, c)
    origin_picks = [p for p in picks if p.source == "origin"]
    assert len(origin_picks) == 2
    assert all(not p.counts_toward_pool and p.label.endswith(" (origin)")
               for p in origin_picks)
    assert validate.charm_pick_count(rs, c) == 1              # only the bought one
    assert len(validate.charm_pick_bp_costs(rs, c, picks)) == 1


def test_a_granted_charm_the_character_also_bought_is_not_listed_twice(rs):
    """Buying it spends a pick, so the bought copy is the one that must show."""
    c = _lookshy(rs)
    c.charms = ["dragonblooded.lore.element-bolt-attack"]
    picks = validate.charm_picks(rs, c)
    rows = [p for p in picks if p.charm_id == "dragonblooded.lore.element-bolt-attack"]
    assert len(rows) == 1
    assert rows[0].source == "charms" and rows[0].counts_toward_pool


def test_lookshy_may_not_take_immaculate_charms_at_chargen(rs):
    """p.68: "Lookshy Dragon-Blooded may not learn the Immaculate Martial Arts before
    play begins." A chargen bar only — the same page sends a player who wants them to
    the Dynastic rules, and the XP economy is untouched."""
    c = _lookshy(rs)
    immaculate = next(ch for ch in sorted(rs.charms.values(), key=lambda ch: ch.id)
                      if ch.immaculate and not ch.prerequisites)
    c.charms = [immaculate.id]
    codes = {i.code for i in validate.validate_chargen(rs, c)}
    assert "charm-immaculate-barred-at-chargen" in codes
    # The bar replaces the Immaculate path rather than layering on top of it, so the
    # player is not also told to put every Charm in one elemental tree.
    assert "immaculate-single-tree" not in codes

    # A Dynastic Dragon-Blooded taking the same Charm is not barred.
    dyn = Character(id="c.dyn", exalt_type=DB, caste="air")
    dyn.abilities = {a: 3 for a in AB}
    dyn.charms = [immaculate.id]
    assert "charm-immaculate-barred-at-chargen" not in {
        i.code for i in validate.validate_chargen(rs, dyn)}


def test_the_immaculate_bar_is_data_and_no_other_origin_carries_it(rs):
    lookshy = rs.budgets_for(DB, "lookshy")
    assert lookshy.bar_immaculate_charms_at_chargen is True
    assert rs.budgets_for(DB, "lookshy", "foreign").bar_immaculate_charms_at_chargen is True
    for origin in ("", "outcaste", "forest-witch", "lost-egg", "pirate"):
        assert rs.budgets_for(DB, origin).bar_immaculate_charms_at_chargen is False, origin


# --- Lookshy Breeding, p.66 -------------------------------------------------- #

def _lookshy_with_pool_spent(rs, breeding: int) -> Character:
    """A Lookshy character whose 13 Background dots are already gone, so the whole
    Breeding rating falls through to bonus points and can be read off directly."""
    c = _lookshy(rs)
    b = rs.budgets_for(DB, "lookshy")
    c.backgrounds = [BackgroundEntry(name="Artifact", rating=3),
                     BackgroundEntry(name="Manse", rating=3),
                     BackgroundEntry(name="Resources", rating=3),
                     BackgroundEntry(name="Retainers", rating=3),
                     BackgroundEntry(name="Allies", rating=1)]
    assert sum(x.rating for x in c.backgrounds) == b.background_dots
    if breeding:
        c.backgrounds.append(BackgroundEntry(name="Breeding", rating=breeding))
    return c


def _bg_points(rs, character) -> int:
    return next(l.points for l in validate.bonus_point_breakdown(rs, character).lines
                if l.domain == "Backgrounds")


@pytest.mark.parametrize("rating,total", [(1, 1), (2, 2), (3, 4), (4, 7), (5, 10)])
def test_lookshy_breeding_reproduces_the_pages_own_totals(rs, rating, total):
    """p.66: "Levels 1 and 2 of this Background are priced normally, but each level
    beyond costs an additional Background or bonus point (on top of the extra cost to
    buy Backgrounds above 3). So level 3 costs 4 points, level 4 costs 7, and level 5
    costs 10 points."

    Three of these five numbers are printed on the page, which makes this test
    self-verifying: the surcharge is +1 per dot above 2 taken on BOTH payment routes
    (pool via expensive_dot_cost, bonus points via bp_surcharge_per_dot), and nothing
    else reproduces 4/7/10 together with the p.69 above-3 rate.
    """
    assert _bg_points(rs, _lookshy_with_pool_spent(rs, rating)) == total


def test_breeding_dots_inside_the_pool_cost_pool_dots_not_bonus_points(rs):
    """The surcharge is "a Background OR a bonus point" — a character with pool left
    pays it in dots, and only dots above 3 reach the bonus-point side at all."""
    c = _lookshy(rs)
    c.backgrounds = [BackgroundEntry(name="Breeding", rating=3)]
    assert _bg_points(rs, c) == 0                     # 4 pool dots of the 13, no BP
    c.backgrounds = [BackgroundEntry(name="Breeding", rating=5)]
    assert _bg_points(rs, c) == 6                     # dots 4-5 at (2 + 1) each


def test_the_breeding_rule_is_lookshys_alone(rs):
    """Every other origin prices Breeding normally, so a 5 costs the ordinary
    2 BP/dot above 3 and nothing more."""
    for origin in ("", "outcaste", "forest-witch", "lost-egg", "pirate"):
        assert validate.background_rule(rs.budgets_for(DB, origin), "Breeding") is None, origin
    rule = validate.background_rule(rs.budgets_for(DB, "lookshy"), "Breeding")
    assert (rule.expensive_above, rule.expensive_dot_cost, rule.bp_surcharge_per_dot) == (2, 2, 1)
    # ...and it applies to the Lookshy character raised elsewhere too (p.68 makes the
    # Background rules Lookshy's, and says dynastic exiles use them as well).
    assert validate.background_rule(
        rs.budgets_for(DB, "lookshy", "foreign"), "Breeding") is not None


# --- Eos and Ossissa: the pirates' Sail Charms and spells, p.93-95 ----------- #

PIRATE_SAIL = {
    # id slug                                    (min Sail, min Essence, prerequisite slug)
    "wind-summoning-whistle":                    (3, 3, "storm-outrunning-technique"),
    "terrible-glow-of-nautical-valor":           (4, 3, "fine-passage-negotiating-style"),
    "pleasant-convocation-of-the-like-minded":   (4, 3, "fine-passage-negotiating-style"),
    "enemy-fouling-method":                      (4, 3, "pleasant-convocation-of-the-like-minded"),
    "false-color-flying-demonstration":          (5, 4, "pirate-masquerading-method"),
}


@pytest.mark.parametrize("slug", sorted(PIRATE_SAIL))
def test_pirate_sail_charm_stat_blocks(rs, slug):
    """Straight off the stat blocks on p.93-94. Every one is Simple, and every one
    hangs off a Sail Charm the Dragon-Blooded book already shipped — the pirate
    chapter extends the existing tree rather than starting a new one."""
    min_ability, min_essence, prereq = PIRATE_SAIL[slug]
    charm = rs.charms[f"dragonblooded.sail.{slug}"]
    assert (charm.min_ability, charm.min_essence) == (min_ability, min_essence)
    assert charm.type.value == "Simple"
    assert charm.category == "sail"
    assert charm.exalt_type == DB
    # Sail is a Water Aspect Ability (the aspect tables on p.69/97/133), which is why
    # every Sail Charm in the data carries Water — the stat blocks never say so.
    assert charm.element == "Water"
    assert charm.prerequisites == [[f"dragonblooded.sail.{prereq}"]]
    assert rs.charms.get(f"dragonblooded.sail.{prereq}") is not None
    assert charm.source.book == "Exalted 1e The Outcaste"


def test_the_pirate_charms_extend_the_shipped_sail_tree(rs):
    """5 new on top of the 5 from Exalted: The Dragon-Blooded, and no orphans — a
    prerequisite naming a Charm that does not exist would leave a dead branch the
    picker can never reach."""
    sail = [c for c in rs.charms.values()
            if c.exalt_type == DB and c.category == "sail"]
    assert len(sail) == 13          # 5 core + 5 pirates + 3 from Aspect Book: Water
    from_outcaste = [c for c in sail if c.source.book == "Exalted 1e The Outcaste"]
    assert len(from_outcaste) == 5
    for c in sail:
        for group in c.prerequisites:
            for pid in group:
                assert pid in rs.charms, f"{c.id} -> missing {pid}"


PIRATE_SPELLS = {
    "calling-the-gulls-with-beaks-of-steel": 25,
    "invocation-of-the-living-ship": 20,
    "keel-cleaves-the-clouds": 25,
    "lightning-whip-smites-the-waters": 15,
}


@pytest.mark.parametrize("slug,motes", sorted(PIRATE_SPELLS.items()))
def test_pirate_spells_are_terrestrial_circle(rs, slug, motes):
    """p.94: "The following spells are all Terrestrial Circle and are not taught as
    widely in the Heptagram as other, more generally useful spells." — so a
    Dragon-Blooded, whose only circle is Terrestrial, can actually cast them."""
    spell = rs.spells[f"spell.terrestrial.{slug}"]
    assert spell.circle.value == "Terrestrial"
    assert spell.cost.motes == motes
    assert spell.source.book == "Exalted 1e The Outcaste"


# --- the editor's two dropdowns ---------------------------------------------- #

def test_only_the_outcaste_origins_offer_an_upbringing(rs):
    """The second dropdown is rendered only where `upbringing_options` is non-empty,
    so no other splat or origin grows a control it has no rows for."""
    from exalted_builder.ui import editor

    for origin in ("lookshy", "forest-witch", "lost-egg", "pirate"):
        assert editor.upbringing_options(DB, origin), origin
    for origin in ("", "dynastic", "outcaste"):
        assert editor.upbringing_options(DB, origin) == {}, origin
    for splat, origin in [("Solar", "illuminated"), ("Sidereal", "ronin"),
                          ("Abyssal", "fugitive"), ("Lunar", "casteless"),
                          ("Alchemical", "")]:
        assert editor.upbringing_options(splat, origin) == {}, splat


def test_every_offered_upbringing_resolves_to_an_authored_row(rs):
    """The dropdown and the data must not drift: every key the editor offers has to
    reach a row, and the first key of each origin is the origin's own default (which
    deliberately has NO ':<upbringing>' row and falls back).

    Reads the SPLAT out of each key rather than assuming Dragon-Blooded. The Outcaste
    book was the only source of upbringings until the ghosts arrived (2026-08-01) with
    their ancestor-worship/Immaculate axis, and a hardcoded splat here silently checked
    the ghosts' rows against Dragon-Blooded's budgets."""
    from exalted_builder.ui import editor

    for key, options in editor._ORIGIN_UPBRINGINGS.items():
        splat, _, origin = key.partition(":")
        origin_row = rs.budgets_for(splat, origin)
        keys = list(options)
        assert keys[0] == "", f"{key}: first option must be the origin default"
        assert rs.budgets_for(splat, origin, keys[0]) is origin_row
        for sub in keys[1:]:
            row = rs.budgets_for(splat, origin, sub)
            assert row is not origin_row, f"{key}:{sub} resolved to the origin row"


def test_every_offered_origin_has_a_budget_row(rs):
    """Same guard on the first dropdown: the four new Dragon-Blooded origins must each
    reach their own row rather than silently falling back to the splat's."""
    from exalted_builder.ui import editor

    splat_row = rs.budgets_for(DB)
    for origin in editor._SPLAT_ORIGINS[DB]:
        row = rs.budgets_for(DB, origin)
        if origin == "dynastic":            # the default, deliberately has no row
            assert row is splat_row
        else:
            assert row is not splat_row, origin


def test_changing_origin_clears_a_stale_upbringing(rs):
    """A Lost Egg 'patrician' must not survive a switch to Pirate, where the key does
    not exist — it would resolve to the pirate origin row and look fine while meaning
    something the player never chose."""
    c = Character(id="c", exalt_type=DB, caste="air", origin="lost-egg",
                  upbringing="patrician")
    assert rs.budgets_for(c.exalt_type, c.origin, c.upbringing).ability_dots == 30
    c.origin, c.upbringing = "pirate", ""       # what editor.set_origin does
    assert rs.budgets_for(c.exalt_type, c.origin, c.upbringing).ability_dots == 35


def test_the_outcaste_backgrounds_are_in_the_autofill_catalog(rs):
    """Backgrounds stay soft free text — the catalog is an autofill source only — but
    the four books name several the catalog did not have."""
    names = {b.name for b in rs.backgrounds_for(DB)}
    for name in ("Arsenal", "Command", "Cult", "Henchmen", "Breeding", "Sorcery",
                 "Retainers", "Reputation", "Manse", "Artifact"):
        assert name in names, name


# --- render routes ----------------------------------------------------------- #
# A ui.select whose value is not among its options raises at RENDER time, not in a
# unit test (CLAUDE.md's NiceGUI 3.x gotcha) — and both dropdowns here are seeded from
# character state. These prove the controls reach the DOM; they do NOT prove the
# layout is right. Budget a browser click-through regardless.

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_editor_renders_both_origin_dropdowns(user: User) -> None:
    await user.open('/lookshy-editor')
    await user.should_see("Origin")
    await user.should_see("Upbringing")
    # A closed ui.select puts only its VALUE in the DOM, so these are the two chosen
    # labels, not the option lists.
    await user.should_see("Lookshy (Seventh Legion)")
    await user.should_see("Raised elsewhere")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_sheet_lists_the_origin_granted_charms(user: User) -> None:
    """Lookshy's two free Charms are not stored on the Character at all — they come
    from the budget row through the canonical enumeration, so the only way to know
    they reach the sheet is to render it."""
    await user.open('/lookshy-sheet')
    await user.should_see("Wind-Carried Words Technique (origin)")
    await user.should_see("Element Bolt Attack (origin)")
