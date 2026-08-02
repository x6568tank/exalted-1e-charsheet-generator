"""Render and interaction tests for the adversary roster (ui/adversaries.py).

These exist for the bug class this build keeps hitting: a rule that IS
implemented, sitting where it does not run. The engine tests in
test_adversaries.py prove instantiate() copies and dodge stays nullable; these
prove the PAGE actually calls them — that the roster renders at all, that the
duplicate button really produces an independent tracker, and that a no-dodge
beast says so on its card.

Each test drives its own route with its own roster (see tests/_ui_main.py) and
asserts through the rendered UI, never by reaching into the harness's globals.
"""

import pytest
from nicegui.testing import User

from exalted_builder.models.adversary import Adversary
from exalted_builder.ui import adversaries as adv_ui

MAIN = "tests/_ui_main.py"


# --------------------------------------------------------------------------- #
# The page renders
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_roster_section_appears_on_the_party_page(user: User) -> None:
    await user.open('/gm-adv')
    await user.should_see("ADVERSARIES")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_empty_roster_invites_rather_than_rendering_a_bare_grid(user: User) -> None:
    await user.open('/gm-adv-empty')
    await user.should_see("No adversaries yet.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_every_entry_is_listed(user: User) -> None:
    await user.open('/gm-adv')
    await user.should_see("Bear")
    await user.should_see("Sad Ivory")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_party_still_renders_beside_the_roster(user: User) -> None:
    """The roster is a section of the party page, not a replacement for it."""
    await user.open('/gm-adv')
    await user.should_see("Player One")
    await user.should_see("SESSION NOTES")


# --------------------------------------------------------------------------- #
# What the card shows
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_creature_that_does_not_dodge_says_so(user: User) -> None:
    """The nullable-dodge ruling, at the place a GM actually reads it. A bear
    prints no dodge on p.316 and must not render as "Dodge 0"."""
    await user.open('/gm-adv')
    await user.should_see("No dodge")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_dodging_npc_shows_its_pool(user: User) -> None:
    await user.open('/gm-adv')
    await user.should_see("Dodge 9")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_attacks_and_abilities_print_as_the_book_does(user: User) -> None:
    await user.open('/gm-adv')
    await user.should_see("Bite: Spd 2 Acc 6 Dmg 8L")
    await user.should_see("Brawl 3")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_charms_render_as_prose(user: User) -> None:
    """Not a Charm id, not a link — the sentence the book printed."""
    await user.open('/gm-adv')
    await user.should_see("Adds dice to Melee and Archery as a supplemental action.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_mote_pool_shows_the_exalted_split(user: User) -> None:
    """16 personal + 47 peripheral = one 63-mote counter, labelled with both."""
    await user.open('/gm-adv')
    await user.should_see("16 personal + 47 peripheral")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_health_track_renders_one_box_per_level(user: User) -> None:
    """"-0/-1 x 2/-2/-4/I" is six boxes, so the deepest label is on the page."""
    await user.open('/gm-adv')
    await user.should_see("HEALTH  ·  penalty none")
    await user.should_see("Incap")


# --------------------------------------------------------------------------- #
# The render matrix — shapes, not known bugs
#
# Every tracker on a card is conditional (no health levels, no Willpower, no
# motes = no section), which is exactly the shape that produces a card that only
# renders when it happens to have something to render.
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_bare_entry_still_renders(user: User) -> None:
    """No health track, no Willpower, no motes, no attacks — a blank a GM just
    added and has not filled in yet."""
    await user.open('/gm-adv-bare')
    await user.should_see("Nameless Thing")
    await user.should_see("No dodge")            # the stat line still prints


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_spirit_mote_shape_renders(user: User) -> None:
    """One `Essence Pool` rather than the Personal/Peripheral split."""
    await user.open('/gm-adv-spirit')
    await user.should_see("Hungry Ghost")
    await user.should_see("39/39 left (pool)")
    await user.should_see("Cunning Thief, Measure the Wind")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_add_dialog_works_with_no_catalogue(user: User) -> None:
    """The catalogue is optional data — a missing adversaries.json must leave a
    working roster, not a dialog with nothing in it."""
    await user.open('/gm-adv-nocat')
    user.find("Add adversary").click()
    await user.should_see("Add a blank adversary")
    user.find("Add a blank adversary").click()
    await user.should_see("New adversary")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_shipped_catalogue_renders(user: User) -> None:
    """The authored data itself, off disk — an extra, a beast and a soldier.
    No hand-built fixture can prove data/adversaries.json renders."""
    await user.open('/gm-adv-real')
    await user.should_see("Weak Opponent")
    await user.should_see("Bear")
    await user.should_see("Militia")
    await user.should_see("No dodge")            # the bear's omitted dodge
    await user.should_see("Soak 3L/6B")          # militia, armour added back in
    await user.should_see("Pool 4")              # the extra's single dice pool
    await user.should_see("Str 7  Dex 2  Sta 6")  # the bear's printed Attributes
    await user.should_see("Virtues: Val 2")      # the extra's only Virtue
    # the elemental pays to DEmaterialize, not to materialize (p.295)
    await user.should_see("Dematerialize 50")
    await user.should_see("Elemental Powers: Dragon's Suspire")
    # the shield: its mobility penalty lands in the dodge pool (p.278's "5/2"),
    # and its difficulty bonus is surfaced for the ST to apply by hand
    await user.should_see("Dodge 2")
    await user.should_see("+1/+1 difficulty to hit (melee/ranged)")


# --------------------------------------------------------------------------- #
# Interaction: the two things the feature is for
# --------------------------------------------------------------------------- #

@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_clicking_a_health_box_marks_it(user: User) -> None:
    """The tracker is the whole point of the roster; this proves the click is
    wired to engine.cycle_mark and that the card re-reads the penalty after."""
    await user.open('/gm-adv-click')
    await user.should_see("HEALTH  ·  penalty none")
    user.find(marker="adv-health-adv.c-0").click()
    await user.should_see("penalty -1")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_duplicate_gives_an_independent_tracker(user: User) -> None:
    """Instancing, at the button. Damage the original, duplicate it, and the copy
    must come up clean — five bandits, five health tracks."""
    await user.open('/gm-adv-click')
    user.find(marker="adv-health-adv.c-0").click()
    await user.should_see("penalty -1")
    user.find(marker="adv-dup-adv.c").click()
    await user.should_see("Bandit 2")
    # the copy's own boxes exist and are unmarked: its penalty reads "none"
    await user.should_see("penalty none")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_reset_clears_the_damage(user: User) -> None:
    await user.open('/gm-adv-click')
    user.find(marker="adv-health-adv.c-0").click()
    await user.should_see("penalty -1")
    user.find(marker="adv-reset-adv.c").click()
    await user.should_see("penalty none")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_delete_removes_the_entry(user: User) -> None:
    await user.open('/gm-adv-click')
    await user.should_see("Bandit")
    user.find(marker="adv-del-adv.c").click()
    await user.should_see("No adversaries yet.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_add_dialog_offers_the_catalogue_and_a_blank(user: User) -> None:
    await user.open('/gm-adv-add')
    user.find("Add adversary").click()
    await user.should_see("Hired Thug")                   # the template
    await user.should_see("Add a blank adversary")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_adding_a_blank_entry_puts_it_on_the_roster(user: User) -> None:
    await user.open('/gm-adv-add')
    user.find("Add adversary").click()
    await user.should_see("Add a blank adversary")
    user.find("Add a blank adversary").click()
    await user.should_see("New adversary")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_instantiating_a_template_puts_a_copy_on_the_roster(user: User) -> None:
    """A GM picks "Hired Thug" and gets an editable copy on the roster. Asserted
    through the section's count, not the name — the name is on screen either way,
    which would make this test pass without the click doing anything."""
    await user.open('/gm-adv-add')
    await user.should_see("No adversaries yet.")
    user.find("Add adversary").click()
    await user.should_see("Hired Thug")
    user.find(marker="adv-tpl-adv.tpl.thug").click()
    await user.should_not_see("No adversaries yet.")
    await user.should_see("(1)")
    # and it came through with the template's stats, not as a blank
    await user.should_see("Init 4")


# --------------------------------------------------------------------------- #
# The parsers behind the editor dialog
#
# Pure functions, tested directly: they turn what a GM types back into the model,
# and a silent failure here loses typed stats.
# --------------------------------------------------------------------------- #

def test_parse_traits_reads_the_books_inline_format():
    traits = adv_ui.parse_traits("Melee 3 (Swords +2), Dodge 2, Awareness 1")
    assert [(t.name, t.rating) for t in traits] == [("Melee", 3), ("Dodge", 2),
                                                    ("Awareness", 1)]
    assert traits[0].specialties == "Swords +2"


def test_parse_traits_keeps_commas_inside_a_specialty_together():
    """"Linguistics 5 (Native: Old Realm; High Realm, Riverspeak)" is ONE trait —
    splitting naively on commas would make three, two of them nonsense."""
    traits = adv_ui.parse_traits(
        "Linguistics 5 (Native: Old Realm; High Realm, Riverspeak), Lore 3")
    assert len(traits) == 2
    assert traits[0].name == "Linguistics" and traits[0].rating == 5
    assert "Riverspeak" in traits[0].specialties
    assert traits[1].name == "Lore"


def test_parse_traits_tolerates_junk():
    assert adv_ui.parse_traits("") == []
    assert adv_ui.parse_traits(", ,") == []
    unrated = adv_ui.parse_traits("Brawl")
    assert unrated[0].name == "Brawl" and unrated[0].rating == 0


def test_parse_attacks_reads_the_npc_format():
    atks = adv_ui.parse_attacks("Fist: Speed 4 Accuracy 3 Damage 2B Defense 3")
    assert len(atks) == 1
    a = atks[0]
    assert (a.name, a.speed, a.accuracy, a.damage, a.damage_type, a.defense) == \
        ("Fist", 4, 3, 2, "B", 3)


def test_parse_attacks_leaves_beast_defense_absent():
    """p.317: a beast has no Defense column. Absent, not 0."""
    a = adv_ui.parse_attacks("Bite: Spd 6 Acc 7 Dmg 1L")[0]
    assert a.defense is None and a.damage_type == "L"


def test_parse_attacks_keeps_the_footnote():
    a = adv_ui.parse_attacks("Venom: Speed 18 Accuracy 8 Damage 24L (once per 10 turns)")[0]
    assert a.note == "once per 10 turns" and a.damage == 24


def test_parse_attacks_round_trips_through_the_display_format():
    """What the card prints must be re-readable by the editor, or opening and
    saving an entry without touching it would quietly lose its attacks."""
    source = "Fist: Speed 4 Accuracy 3 Damage 2B Defense 3"
    once = adv_ui.parse_attacks(source)
    twice = adv_ui.parse_attacks("\n".join(adv_ui.attack_line(a) for a in once))
    assert [a.model_dump() for a in once] == [a.model_dump() for a in twice]


def test_trait_line_round_trips():
    source = "Melee 3 (Swords +2), Dodge 2"
    assert adv_ui.trait_line(adv_ui.parse_traits(source)) == source


# --------------------------------------------------------------------------- #
# The dead-field guard
#
# This build's most-repeated bug is a value written by one side and read by
# nobody. It happened again here during preflight: `powers`, `combat_pool` and
# `cost_to_dematerialize` were authored into the catalogue, printed on no card,
# and — worse — absent from the editor, so opening and saving any spirit or extra
# silently wiped them.
#
# These two tests make the whole class impossible to reintroduce: every stat
# field must be BOTH editable and displayed. A new field fails them until it is
# wired to both ends.
# --------------------------------------------------------------------------- #

# Everything that is not a printed stat: identity, provenance, tracked state.
_NOT_STATS = {"id", "name", "template_id", "category", "nature", "caste",
              "damage", "willpower_spent", "motes_spent", "notes"}


def test_every_stat_field_survives_an_edit():
    """Open the editor on a fully-populated entry, save without changing a thing,
    and nothing may be lost. This is the test the wiped-Powers bug needed."""
    import inspect
    source = inspect.getsource(adv_ui.edit_dialog)
    for field in Adversary.model_fields:
        if field in _NOT_STATS:
            continue
        assert f"a.{field} =" in source, (
            f"edit_dialog never writes {field!r} — opening and saving an entry "
            f"would silently drop it")


def test_every_stat_field_reaches_the_card():
    """A field the catalogue can carry but no card prints is data nobody can read.

    The read set is the card renderer, its line helpers AND engine.adversaries —
    several fields reach the card only through the engine (`dodge` via
    dodge_after_armor, the soak pair and `armor_id` via soak), which is the
    correct path, not a miss."""
    import inspect

    from exalted_builder.engine import adversaries as adv_engine

    source = "".join(inspect.getsource(f) for f in
                     (adv_ui.build_roster, adv_ui.summary_line, adv_ui.attack_line,
                      adv_ui.trait_line, adv_ui.trait_map_line))
    source += inspect.getsource(adv_engine)
    for field in Adversary.model_fields:
        if field in _NOT_STATS or field == "attacks":
            continue
        assert f".{field}" in source, f"nothing on the card ever reads {field!r}"


# --------------------------------------------------------------------------- #
# Naming duplicates
# --------------------------------------------------------------------------- #

def test_duplicate_names_are_numbered():
    existing = [Adversary(id="a", name="Bandit")]
    assert adv_ui._copy_name(existing, "Bandit") == "Bandit 2"
    existing.append(Adversary(id="b", name="Bandit 2"))
    assert adv_ui._copy_name(existing, "Bandit") == "Bandit 3"


def test_ids_do_not_collide_after_a_deletion():
    from exalted_builder.models.party import Party
    p = Party(id="p", adversaries=[Adversary(id="adv.1"), Adversary(id="adv.2")])
    del p.adversaries[0]
    assert adv_ui.next_id(p) not in {a.id for a in p.adversaries}
