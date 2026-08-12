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


def test_command_henchmen_and_reputation_are_dragon_blooded_backgrounds(rs):
    """These three, and Family with them, are printed in E:DB CH4's NEW BACKGROUNDS
    (pp.158-160) — Dragon-Blooded content (human, rules authority, 2026-08-11). They
    shipped untagged and were therefore offered to every splat in the build, the same
    leak as Lookshy's Arsenal. A Solar's own Backgrounds section (core pp.141-148)
    prints none of them."""
    for db_only in ("Command", "Henchmen", "Reputation", "Family"):
        assert db_only in _names(rs, "Dragon-Blooded"), db_only
        for splat in ("Solar", "Sidereal", "Lunar", "Abyssal"):
            assert db_only not in _names(rs, splat), f"{db_only} leaked to {splat}"


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


# --------------------------------------------------------------------------- #
# The printed dot ladder (BackgroundType.ladder)
# --------------------------------------------------------------------------- #
# Every Background in the book prints a dot-by-dot ladder saying what each RATING
# actually gets you, and the build showed none of it — a single blurb, the same at
# Resources • as at Resources •••••. The ladder is TEXT: nothing in the engine reads
# a rung, and the numeric rules a rung happens to state live in BackgroundRule.

def test_a_transcribed_ladder_renders_the_rung_for_the_held_rating(rs):
    """Core p.142: "•• Two allies or one significant one." A character with Allies 2
    should be shown that rung and no other."""
    from exalted_builder.ui import view as viewmod
    cat = rs.backgrounds_for("Solar")
    assert "Two allies or one significant one" in viewmod.background_rung(cat, "Allies", 2)
    assert "Five allies" in viewmod.background_rung(cat, "Allies", 5)
    # The zero rung is the book's "x" row and still says something worth reading.
    assert "no one close to turn to" in viewmod.background_rung(cat, "Allies", 0)


def test_the_ladder_degrades_to_nothing_rather_than_a_blank_rung(rs):
    """Backgrounds are free text, so the rung lookup must survive a name no catalogue
    entry covers, a rating off the scale, and a Background whose ladder has not been
    transcribed yet — all three return "" and the label simply hides."""
    from exalted_builder.ui import view as viewmod
    cat = rs.backgrounds_for("Solar")
    assert viewmod.background_rung(cat, "Wholly Invented Background", 3) == ""
    assert viewmod.background_rung(cat, "Allies", 9) == ""
    assert viewmod.background_ladder(cat, "Wholly Invented Background") == []


def test_a_partial_ladder_is_rejected_at_load(rs):
    """The sheet indexes the ladder BY RATING, so four rungs would print the wrong
    text for a rating rather than no text — worse than the empty default. The model
    takes six entries or none."""
    import pytest as _pytest
    from exalted_builder.models.rules import BackgroundType
    BackgroundType(id="b.x", name="X", ladder=tuple("abcdef"))      # 6 is fine
    BackgroundType(id="b.y", name="Y")                              # none is fine
    with _pytest.raises(ValueError):
        BackgroundType(id="b.z", name="Z", ladder=("a", "b", "c", "d"))


# --------------------------------------------------------------------------- #
# The per-splat catalogue list (ChargenBudgets.catalogue_backgrounds)
# --------------------------------------------------------------------------- #
# Each book enumerates its own Backgrounds — Ghosts CH3 names eleven, Lookshy's p.66
# summary fifteen, E:DB's Traits chapter thirteen. That list is what the dropdown
# offers. Backgrounds shipped almost entirely untagged, so every splat saw every
# other splat's: a Solar could take the Seventh Legion's Arsenal.

def test_each_splats_catalogue_is_its_own_books_list(rs):
    """Spot-checked against the transcribed books, one splat per shape: a splat whose
    summary enumerates (Ghost), one whose Traits chapter does (Dragon-Blooded), and
    an ORIGIN that prints a different list from its splat (Lookshy).

    `universal` entries are subtracted first — they sit outside the per-splat lists by
    definition, so including them here would make this a test of the universal flag
    rather than of each book's enumeration."""
    universal = {b.name for b in rs.background_catalog.values() if b.universal}
    assert set(_names(rs, "Ghost")) - universal == {
        "Allies", "Ancestor Cult", "Artifact", "Backing", "Contacts", "Followers",
        "Grave Goods", "Influence", "Mentor", "Resources", "Underworld Cult"}
    assert set(_names(rs, "Solar")) - universal == {
        "Allies", "Artifact", "Backing", "Contacts", "Familiar", "Followers",
        "Influence", "Manse", "Mentor", "Resources"}
    lookshy = {b.name for b in rs.backgrounds_for("Dragon-Blooded", "lookshy")}
    # Retainers is NOT in this delta: the Dragon-Blooded chargen summary lists it too,
    # so only the Seventh Legion's armoury and its sorcery training are Lookshy's own.
    assert lookshy - set(_names(rs, "Dragon-Blooded")) == {"Arsenal", "Sorcery"}


def test_the_catalogue_list_never_makes_a_typed_background_illegal(rs):
    """The invariant this field exists to protect. `catalogue_backgrounds` narrows
    what is OFFERED; `allowed_backgrounds` is the separate HARD list that errors.
    Writing one field for both jobs made every free-text Background illegal for every
    splat whose book got transcribed — do not merge them back."""
    from exalted_builder.engine import validate
    from exalted_builder.models.character import BackgroundEntry, Character
    c = Character(id="c", exalt_type="Solar", caste="dawn")
    c.backgrounds = [BackgroundEntry(name="Something The Book Never Printed", rating=1)]
    assert [i for i in validate.validate_chargen(rs, c)
            if i.code == "background-not-allowed"] == []
    assert rs.budgets_for("Solar").allowed_backgrounds == []


def test_an_untranscribed_splat_degrades_to_the_old_filter(rs):
    """A splat whose book has not been read yet must keep the behaviour it had — the
    per-Background `exalt_type` tag — rather than showing nothing. That is what makes
    transcribing the books incremental instead of all-or-nothing."""
    # No shipped splat is untranscribed any more — Dragon-Kings was the last, and its
    # own list is covered above and in test_dragonkings.py. The fallback is still LIVE
    # CODE in `backgrounds_for` though, and it is what makes adding splat number twelve
    # incremental rather than all-or-nothing, so it is exercised through a key no book
    # will ever define. A synthetic splat is the honest way to test a branch that no
    # real character currently reaches; delete this only if the fallback itself goes.
    assert rs.catalogue_backgrounds_for("Some-Unread-Splat") == set()
    names = _names(rs, "Some-Unread-Splat")
    assert "Allies" in names and "Resources" in names   # untagged, offered to everyone
    assert "Cult" in names                              # universal, needs no list
    assert "Celestial Manse" not in names               # Dragon-Kings'/Sidereal's
    assert "Whispers" not in names                      # Abyssal's
    assert "Heart's Blood" not in names                 # Lunar's


# --------------------------------------------------------------------------- #
# Universal Backgrounds (BackgroundType.universal)
# --------------------------------------------------------------------------- #
# Human's ruling, 2026-08-11: "Cult is universal, as are any other backgrounds not in
# specific splats if such exist." Cult is printed in Games of Divinity, which is not a
# splat book, so no character-creation summary names it — and without the flag it was
# visible only to the splats whose lists had not been transcribed yet, and would have
# vanished one splat at a time as the sweep finished.

def test_a_universal_background_reaches_every_splat(rs):
    for splat in ("Solar", "Dragon-Blooded", "Ghost", "Sidereal", "Lunar", "Abyssal"):
        assert "Cult" in _names(rs, splat), splat
    assert "Cult" in {b.name for b in rs.backgrounds_for("Dragon-Blooded", "lookshy")}


def test_universal_does_not_mean_unbannable(rs):
    """Universal means "belongs to no one book", not "cannot be forbidden". The Great
    Geas explicitly prohibits a Mountain Folk a Cult (CH6 p.234), and that ban is
    about the splat, not about which supplement is open — so it still bites, and the
    Storyteller's all_backgrounds_available does not lift it either."""
    for origin in ("enlightened", "unenlightened"):
        assert "Cult" not in {b.name for b in
                              rs.backgrounds_for("Mountain-Folk", origin)}
        assert "Cult" not in {b.name for b in rs.backgrounds_for(
            "Mountain-Folk", origin, all_available=True)}


def test_no_background_ends_up_belonging_to_nobody(rs):
    """The guard that keeps the sweep from creating orphans. A Background with no
    `exalt_type`, no `universal` flag and no splat list naming it would be offered to
    NOBODY once every book is transcribed — present in the catalogue, reachable from
    nowhere. Adding one must therefore force a decision about who owns it.

    NOTE this deliberately checks one direction only. The obvious mirror — "a
    universal Background appears in no splat's list" — is FALSE against the books:
    Cult is marked universal on the human's ruling (2026-08-11) AND is named outright
    in the Lunar chargen summary. Being enumerated by one book does not stop a
    Background belonging to no book in particular, so `universal` and "listed
    somewhere" are independent, not exclusive."""
    listed = set()
    for row in rs.budgets.values():
        listed |= {n.strip().lower() for n in row.catalogue_backgrounds}

    orphans = [bg.name for bg in rs.background_catalog.values()
               if not bg.universal and not bg.exalt_type
               and bg.name.strip().lower() not in listed]
    assert not orphans, (
        f"{orphans} belong to no splat: no exalt_type, not universal, and no splat's "
        f"catalogue_backgrounds names them. Mark them universal, tag them, or add "
        f"them to the list of the splat whose book prints them.")


def test_every_hard_allowed_background_exists_in_the_catalogue(rs):
    """`allowed_backgrounds` is the HARD list — a name outside it is an error — so a
    name INSIDE it that no catalogue entry provides is legal to hold and impossible to
    find in any dropdown. Illumination and Tiger Warriors sat in that state: named by
    `Solar:illuminated` since the Cult of the Illuminated shipped, backed by no entry."""
    names = {bg.name.strip().lower() for bg in rs.background_catalog.values()}
    for key, row in rs.budgets.items():
        for allowed in row.allowed_backgrounds:
            assert allowed.strip().lower() in names, (
                f"{key} allows {allowed!r}, which no Background in the catalogue "
                f"provides — it can be held but never picked.")


def test_the_dropdown_never_offers_a_background_the_hard_list_forbids(rs):
    """Two lists, one sheet: `catalogue_backgrounds` decides what is OFFERED and
    `allowed_backgrounds` decides what is LEGAL, so a row carrying both must not let
    them disagree. The Sidereal ronin did: its catalogue inherited the twelve of the
    base Sidereal row while p.100 limits it to eight, so the dropdown offered
    Celestial Manse, Salary, Savant and Sifu and each errored the moment it was
    picked.

    Compared by NAME on both sides: `allowed_backgrounds` is name-keyed (it validates
    a `BackgroundEntry`, which stores a name), while a catalogue entry may be either a
    name or an exact id — the Illuminated Solars' Artifact is listed by id so it cannot
    be confused with the corebook's. Resolving ids to their name first is what keeps
    the two lists comparable at all."""
    for key, row in rs.budgets.items():
        if not (row.allowed_backgrounds and row.catalogue_backgrounds):
            continue
        allowed = {n.strip().lower() for n in row.allowed_backgrounds}
        offered = set()
        for entry in row.catalogue_backgrounds:
            entry = entry.strip()
            bg = rs.background_catalog.get(entry)
            offered.add((bg.name if bg is not None else entry).strip().lower())
        assert offered <= allowed, (
            f"{key} offers {sorted(offered - allowed)}, which its allowed_backgrounds "
            f"forbids — the player can pick a name that immediately errors.")


def test_every_catalogue_list_entry_resolves_to_exactly_one_background(rs):
    """A `catalogue_backgrounds` entry is a lowercased NAME or an exact id, and either
    way it must land on precisely one Background for that splat.

    Both failure modes are silent. An entry naming nothing (a typo, a renamed
    Background) just quietly shrinks the dropdown. An ambiguous NAME — one of the five
    printed twice, like Salary or Connections — either offers the wrong splat's copy
    or offers the row twice; ids exist for exactly that case."""
    for key, row in rs.budgets.items():
        if not row.catalogue_backgrounds:
            continue
        splat = key.split(":")[0]
        offered = [bg.name for bg in rs.backgrounds_for(
            splat, key.split(":")[1] if ":" in key else "")]
        assert len(offered) == len(set(offered)), (
            f"{key} offers a duplicate name: "
            f"{sorted(n for n in offered if offered.count(n) > 1)}. Name the copy it "
            f"means by id.")
        names = {bg.name.strip().lower() for bg in rs.background_catalog.values()}
        ids = set(rs.background_catalog)
        for entry in row.catalogue_backgrounds:
            e = entry.strip()
            assert (e in ids) or (e.lower() in names), (
                f"{key} lists {entry!r}, which matches no Background name or id — "
                f"the dropdown silently drops it.")


def test_the_god_blooded_are_offered_every_background_their_book_grants(rs):
    """PG p.50 prints twenty-five Backgrounds for the God-Blooded, twelve of them
    published in OTHER splats' books and granted by cross-reference — Whispers from
    E:Ab p.134, Renown from E:L p.100, Salary from E:S pp.107/109, and so on.

    Those copies are tagged for the splat that PRINTED them, and `exalt_type` is a
    single string that cannot say "Abyssal and God-Blooded", so the tag vetoed all
    twelve and the dropdown offered thirteen of twenty-five. Naming them by id in the
    catalogue list is what bypasses the tag."""
    offered = {b.name for b in rs.backgrounds_for("God-Blooded")}
    assert len(offered) == 25
    for borrowed in ("Whispers", "Renown", "Salary", "Reputation", "Spies",
                     "Abyssal Command", "Underworld Manse", "Family"):
        assert borrowed in offered, borrowed
    # …without dragging in the rest of those splats' books.
    assert "Necromancy" not in offered and "Heart's Blood" not in offered
    # The three ambiguous names take the SIDEREAL copy, which is what PG cites.
    salary = next(b for b in rs.backgrounds_for("God-Blooded") if b.name == "Salary")
    assert salary.id == "background.salary-sidereal"


# --------------------------------------------------------------------------- #
# Backgrounds that are genuinely REWORKED per splat, not merely repriced
# --------------------------------------------------------------------------- #
# Two different differences, two different mechanisms:
#   * a MECHANICAL difference is a `BackgroundRule` on the budget row — the
#     Dragon-Blooded x2, the Alchemical x3, the Abyssal budget tiers;
#   * a TEXTUAL difference is a second BackgroundType with its own id.
# Artifact and Manse used to do neither: one entry whose description was a pile of
# per-splat parentheses and whose ladder was always the Solar one. The engine charged
# a Dragon-Blooded the doubled rate while the sheet read them the Solar rungs.

def test_a_reworked_background_shows_its_own_splats_rungs(rs):
    from exalted_builder.ui import view as viewmod
    def artifact(splat, origin=""):
        cat = rs.backgrounds_for(splat, origin)
        return next(b for b in cat if b.name == "Artifact"), cat

    solar, _ = artifact("Solar")
    db, db_cat = artifact("Dragon-Blooded")
    ab, ab_cat = artifact("Abyssal")
    assert len({solar.id, db.id, ab.id}) == 3, "each must be its own entry"
    # E:DB p.157 counts ARTIFACTS, not dots — that is what the doubling looks like on
    # the page — and its zero rung still grants an item, unlike every other splat's.
    assert "pair of level 1 artifacts" in viewmod.background_rung(db_cat, "Artifact", 1)
    assert "single level 1 artifact" in db.ladder[0]
    # E:Ab p.131 is a BUDGET: combined ratings, not one item.
    assert "combined Artifact rating no higher than 7" in \
        viewmod.background_rung(ab_cat, "Artifact", 3)
    # And the Manse rework: a Dragon-Blooded's rating is how many Manses she is
    # ATTUNED to, capped in total Hearthstone levels — not one Manse of that level.
    assert "attuned to several level 1 and 2 Manses" in viewmod.background_rung(
        db_cat, "Manse", 1)


def test_the_abyssal_artifact_ladder_matches_the_rule_that_prices_it(rs):
    """The rungs and `BackgroundRule.budget_tiers` are the same five tiers off the
    same page (E:Ab p.131), so a change to one that misses the other is a sheet that
    promises what the engine will not allow. Checked by the numbers, not the prose."""
    tiers = rs.budgets_for("Abyssal").background_rules["artifact"].budget_tiers
    ladder = rs.background_catalog["background.artifact-abyssal"].ladder
    assert [t.combined_max for t in tiers] == [3, 5, 7, 10, 13]
    for tier in tiers:
        rung = ladder[tier.rating]
        assert tier.name.lower() in rung.lower()
        assert str(tier.combined_max) in rung


def test_a_renegade_abyssal_uses_the_core_artifact_background(rs):
    """E:Ab p.131: the Deathlord budget "only applies to those Abyssals who continue
    to faithfully serve their Deathlords. Renegade Abyssals use the Artifact
    Background found in Chapter Four: Traits of the main Exalted rulebook." The
    fugitive also loses Liege — the relationship they renounced — and may begin with
    Backing or Mentor, which a serving deathknight may not."""
    fug = rs.backgrounds_for("Abyssal", "fugitive")
    loyal = {b.name for b in rs.backgrounds_for("Abyssal")}
    assert next(b for b in fug if b.name == "Artifact").id == "background.artifact"
    names = {b.name for b in fug}
    assert "Liege" not in names and "Liege" in loyal
    assert {"Backing", "Mentor"} <= names
    assert "Backing" not in loyal and "Mentor" not in loyal


# --------------------------------------------------------------------------- #
# The rung LABEL, through the UI (the ladder tests above only exercise view.py)
# --------------------------------------------------------------------------- #
# `background_rung` being right proves nothing about the row: the label is refreshed by
# a callback the RATING CONTROL has to invoke, and the play regime's number input does
# not rebuild the panel. A rung that keeps describing the rating the row was drawn at
# is exactly the shape the suite cannot see and the browser can.

def _bg_rung_labels(user) -> list:
    return [el for el in user.find(ui.label).elements
            if el.props.get("data-testid") == "bg-rung"]


def _bg_rung_texts(user) -> list[str]:
    return [el.text or "" for el in _bg_rung_labels(user)]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_row_prints_the_rung_for_the_rating_it_holds(user) -> None:
    await user.open('/backgrounds-rung')
    texts = _bg_rung_texts(user)
    assert any("Two allies or one significant one" in t for t in texts), texts
    assert all(el.visible for el in _bg_rung_labels(user))


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_rung_follows_the_rating_in_play(user) -> None:
    """The play regime edits the rating through a plain number input and does NOT
    rebuild the panel, so the rung only moves if the control invokes the row's sync."""
    await user.open('/backgrounds-rung-xp')
    assert any("Two allies" in t for t in _bg_rung_texts(user)), _bg_rung_texts(user)
    number = next(e for e in user.client.elements.values()
                  if isinstance(e, ui.number) and e.props.get("label") is None
                  and e.value == 2)
    number.value = 5
    await user.should_see("Five allies")
    texts = _bg_rung_texts(user)
    assert any("Five allies" in t for t in texts), texts
    assert not any("Two allies" in t for t in texts), texts


def _click_pip(el) -> None:
    """Dispatch a click to ONE pip icon. `user.find(...).click()` would fire every
    matching element and `.elements` is an unordered set, so the pip is picked by id
    order and its own listener invoked directly — the harness dispatches no bubbling
    click to an icon inside a row anyway."""
    el._handle_event({"id": el.id, "listener_id": list(el._event_listeners)[0],
                      "args": {}})


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file("tests/_ui_main.py")
async def test_the_rung_follows_a_dot_track_click_at_chargen(user) -> None:
    """The other regime: chargen rates a Background with the dot track, whose click
    writes the rating and must call the row's sync. The page holds exactly one dotted
    row (one Background, no Merits), so the pips are unambiguous."""
    await user.open('/backgrounds-rung')
    pips = sorted([e for e in user.client.elements.values() if isinstance(e, ui.icon)],
                  key=lambda e: e.id)
    assert len(pips) == 5, f"expected one 5-pip Background row, got {len(pips)} pips"
    _click_pip(pips[4])                                   # Allies 2 -> 5
    await user.should_see("Five allies")
    texts = _bg_rung_texts(user)
    assert not any("Two allies" in t for t in texts), texts


# --------------------------------------------------------------------------- #
# Borrowed ladders (BackgroundType.ladder_from)
# --------------------------------------------------------------------------- #
# The Mountain Folk book prints its ten shared Backgrounds as PROSE, with no dot-by-dot
# breakdown (human, rules authority, 2026-08-12), so those rows showed a description and
# no rung where a Solar showed both. Their entries now point at the core entry's ladder.
# The ruling is "point at the Solar ones"; it is NOT a same-name fallback — see the
# Alchemical Artifact test below for why that distinction is load-bearing.

def test_the_mountain_folk_copies_show_a_rung(rs):
    """The whole point: a Mountain Folk row must print a rung for its rating, borrowed
    from the entry that carries the printed ladder."""
    from exalted_builder.ui import view as viewmod
    cat = rs.backgrounds_for("Mountain-Folk")
    for name in ("Allies", "Backing", "Contacts", "Familiar", "Followers",
                 "Influence", "Manse", "Mentor", "Resources", "Artifact"):
        assert viewmod.background_rung(cat, name, 2), f"{name} shows no rung"


def test_a_borrowed_ladder_keeps_its_own_printed_description(rs):
    """Borrowing the RUNGS must not borrow the prose: the Mountain Folk description is
    their own book's and is the reason these entries exist as separate rows at all."""
    mf = next(b for b in rs.backgrounds_for("Mountain-Folk", "enlightened")
              if b.name == "Allies")
    core = rs.background_catalog["background.allies"]
    assert "Jadeborn" in mf.description or "own kind" in mf.description
    assert mf.description != core.description
    assert mf.ladder == core.ladder


def test_the_deliberate_no_ladder_entries_stay_empty(rs):
    """Alchemical Artifact and Family have no ladder ON PURPOSE — the Alchemical book
    prints none and E:DB p.159 prints a random table instead. A same-name FALLBACK
    (rather than the per-entry pointer that shipped) would hand Alchemical Artifact the
    core Artifact ladder, which is a different Background wearing the same name."""
    for bid in ("background.artifact-alchemical", "background.family"):
        assert not rs.background_catalog[bid].ladder, bid


def test_a_broken_ladder_pointer_is_a_load_problem():
    """The pointer is resolved once at load, so a typo must be LOUD there rather than
    silently rendering no rung. All four ways to get it wrong are reported."""
    from exalted_builder.models.rules import BackgroundType
    from exalted_builder.rules_db import _resolve_borrowed_ladders
    full = tuple("abcdef")
    good = BackgroundType(id="b.good", name="Good", ladder=full)
    cases = {
        "b.dangling": BackgroundType(id="b.dangling", name="D", ladder_from="b.nope"),
        "b.unladdered": BackgroundType(id="b.unladdered", name="U", ladder_from="b.bare"),
        "b.chained": BackgroundType(id="b.chained", name="C", ladder_from="b.dangling"),
        "b.both": BackgroundType(id="b.both", name="B", ladder=full,
                                 ladder_from="b.good"),
    }
    table = {"b.good": good, "b.bare": BackgroundType(id="b.bare", name="Bare"), **cases}
    problems: list[str] = []
    _resolve_borrowed_ladders(table, problems)
    for bid in cases:
        assert any(bid in p for p in problems), f"{bid} resolved silently: {problems}"
    # …and the healthy pointer still resolves alongside the broken ones.
    table = {"b.good": good,
             "b.ok": BackgroundType(id="b.ok", name="OK", ladder_from="b.good")}
    problems = []
    _resolve_borrowed_ladders(table, problems)
    assert table["b.ok"].ladder == full and not problems


def test_the_shipped_data_resolves_every_pointer_cleanly():
    """The loader reports into `problems`; nothing enforced that the shipped file is
    clean. Re-reads the file rather than the loaded ruleset, because resolution has
    already run on the latter — asking a resolved table again would report every
    borrower as carrying "both a ladder and ladder_from"."""
    import json
    from pathlib import Path
    import exalted_builder
    from exalted_builder import rules_db
    from exalted_builder.models.rules import BackgroundType
    raw = json.loads(
        (Path(exalted_builder.__file__).parent / "data" / "backgrounds.json").read_text())
    table = {b["id"]: BackgroundType(**b) for b in raw}
    problems: list[str] = []
    rules_db._resolve_borrowed_ladders(table, problems)
    assert not problems, problems
    assert any(b.ladder_from for b in table.values()), \
        "no entry borrows a ladder; this test would pass vacuously"


def test_a_splats_own_copy_displaces_the_untagged_one(rs):
    """The Mountain Folk shipped with their ten Backgrounds AND the ten core entries
    they replace, so every name appeared in the dropdown twice — visible only with a
    blank origin (their catalogue list is keyed by origin), which is what an older save
    or a programmatically built character has. No splat may offer a name twice."""
    from collections import Counter
    for splat in ("Solar", "Sidereal", "Abyssal", "Dragon-Blooded", "Lunar",
                  "Alchemical", "Mortal", "Ghost", "God-Blooded", "Dragon-Kings",
                  "Mountain-Folk"):
        for origin in ("", "enlightened"):
            names = Counter(b.name for b in rs.backgrounds_for(splat, origin))
            assert not [n for n, c in names.items() if c > 1], (splat, origin, names)


def test_the_storyteller_override_still_shows_every_books_version(rs):
    """The displacement must NOT reach `all_available`: there the ST asked for every
    book's version, and the six differently-reworked Artifacts are the point."""
    rows = rs.backgrounds_for("Solar", all_available=True)
    assert len([b for b in rows if b.name == "Artifact"]) == 6
