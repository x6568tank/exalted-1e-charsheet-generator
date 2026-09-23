"""The public pages of the hosted server: the front page, About and the wiki.

`docs/plans/vtt.md` sections 9.4 and 9.5.

⚠ The route cases use PRODUCTION wiring (`tests/_public_main.py` calls
`server/main.build_server`). The homebrew case must: a wiki test that builds its
own ruleset proves nothing about which ruleset the server gives the wiki.

⚠ The homebrew case has a positive control. The library of the fixture must load
into the builder's ruleset, or the absence from the wiki shows nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from nicegui.testing import User

from exalted_builder import custom_content, rules_db
from exalted_builder.ui import view, wiki_view as wv

_DATA = Path(__file__).resolve().parent.parent / "exalted_builder" / "data"
MAIN = "tests/_public_main.py"


@pytest.fixture(scope="module")
def book():
    return rules_db.load_ruleset(_DATA)


# The reference sections of the wiki: (list builder, entry page builder).
_REFERENCE = ((wv.trait_list, wv.trait_page), (wv.caste_list, wv.caste_page),
              (wv.equipment_list, wv.equipment_page), (wv.artifact_list, wv.artifact_page),
              (wv.thaumaturgy_list, wv.thaumaturgy_page), (wv.power_list, wv.power_page))


def _all_rows(book, build) -> list[wv.Row]:
    """Return the rows of each page of a list."""
    first = build(book)
    return [row for number in range(1, first.pages + 1) for row in build(book, page=number).rows]


# --------------------------------------------------------------------------- #
# The presenter
# --------------------------------------------------------------------------- #


def test_the_charm_list_filters_by_splat_and_category(book) -> None:
    listing = wv.charm_list(book, splat="Solar", category="melee")

    assert listing.total > 0
    for card in listing.rows:
        charm = book.charms[card.href.rsplit("/", 1)[-1]]
        assert (charm.exalt_type, charm.category) == ("Solar", "melee")


def test_an_unknown_filter_value_is_ignored(book) -> None:
    assert (wv.charm_list(book, splat="Fair Folk").total
            == wv.charm_list(book).total)


def test_the_search_needs_each_word(book) -> None:
    names = {c.title for c in wv.charm_list(book, query="ox body").rows}

    assert "Ox-Body Technique" in names
    assert wv.charm_list(book, query="ox body zzzznotaword").total == 0


def test_a_virtual_path_power_has_no_charm_page(book) -> None:
    """⚠ The loader projects the Dragon-King Path powers into the Charm list. They
    are not Charms of the book."""
    virtual = [cid for cid, c in book.charms.items() if c.virtual]
    assert virtual, "The ruleset has no virtual Charm, thus this case covers nothing."

    assert wv.charm_page(book, virtual[0]) is None
    hrefs = {c.href for c in wv.charm_list(book, splat="Dragon-Kings").rows}
    assert wv.charm_href(virtual[0]) not in hrefs


def test_a_charm_page_links_its_prerequisites(book) -> None:
    charm = next(c for c in book.charms.values()
                 if c.prerequisites and not c.virtual and c.exalt_type == "Solar")
    entry = wv.charm_page(book, charm.id)

    linked = {link.href for group in entry.prerequisites for link in group}
    for prerequisite in charm.prerequisites[0]:
        assert wv.charm_href(prerequisite) in linked


def test_the_charm_card_and_the_builder_card_give_one_requirement(book) -> None:
    """One requirement formatter. The wiki must not grow a second copy."""
    charm = book.charms["solar.melee.excellent-strike"]
    requirement, _ = view.charm_requirements(book, charm)

    assert requirement == "Melee 1, Essence 1"
    assert requirement in wv.charm_row(book, charm).cells


def test_a_style_page_lists_the_charms_of_the_style(book) -> None:
    entry = wv.style_page(book, "snake")

    assert entry.title == "Snake Style"
    expected = {c.id for c in book.charms.values() if c.category == "martial_arts:snake"}
    assert {c.href for c in entry.rows} == {wv.charm_href(cid) for cid in expected}


def test_the_style_title_is_the_authored_name(book) -> None:
    """`praying-mantis` is printed "Mantis Style". One label generator."""
    assert wv.style_page(book, "praying-mantis").title == view._style_label(
        "martial_arts:praying-mantis", book)


def test_the_background_filter_is_what_the_builder_offers(book) -> None:
    """Dragon-Blooded are barred from Contacts. The filter reads
    `RuleSet.backgrounds_for`, not the `exalt_type` field."""
    offered = {b.id for b in book.backgrounds_for("Dragon-Blooded")}
    listing = wv.background_list(book, splat="Dragon-Blooded")

    assert listing.total == len(offered)
    assert {c.href for c in listing.rows} == {wv.background_href(b) for b in offered}


def test_a_background_source_reaches_the_page(book) -> None:
    """🐞 `backgrounds.json` carried 51 sources and the model dropped each one:
    `BackgroundType` had no `source` field. The wiki is the first read site."""
    sourced = [b for b in book.background_catalog.values() if b.source]
    assert len(sourced) >= 51

    entry = wv.background_page(book, "background.abyssal-command")
    assert entry.source == "The Abyssals p.132"


def test_an_unsourced_background_names_no_book(book) -> None:
    """⚠ `Source()` defaults the book to "Core". An unsourced row must show none."""
    unsourced = [b for b in book.background_catalog.values() if b.source is None]
    assert unsourced, "Each Background has a source, thus this case covers nothing."

    assert wv.background_page(book, unsourced[0].id).source == ""


def test_each_entry_and_each_filter_value_builds(book) -> None:
    """The render sweep. Each entry page and each filter value of each list builds.
    An odd data row, for example an empty ladder or a raw cost, cannot fail a page
    that no case opened."""
    pages = [(wv.charm_page, [c for c, x in book.charms.items() if not x.virtual]),
             (wv.spell_page, list(book.spells)),
             (wv.merit_page, list(book.merits_flaws)),
             (wv.background_page, list(book.background_catalog))]
    for build, ids in pages:
        for entry_id in ids:
            assert build(book, entry_id) is not None, f"{build.__name__}({entry_id!r})"
    for card in wv.style_list(book).rows:
        assert wv.style_page(book, card.href.rsplit("/", 1)[-1]) is not None, card.href
    # The reference sections: each row with an address opens its page.
    for build, lookup in _REFERENCE:
        for row in _all_rows(book, build):
            if row.href:
                assert lookup(book, row.href.rsplit("/", 1)[-1]) is not None, row.href

    lists = (wv.charm_list, wv.style_list, wv.spell_list, wv.merit_list, wv.background_list,
             *(build for build, _lookup in _REFERENCE))
    for build in lists:
        for f in build(book).filters:
            for option in f.options:
                listing = build(book, **{"splat" if f.name == "splat" else f.name: option.value})
                assert listing.total > 0, f"{build.__name__} {f.name}={option.value} is empty."


def test_the_page_number_is_clamped(book) -> None:
    listing = wv.charm_list(book, page=10_000)

    assert listing.page == listing.pages
    assert listing.rows


# --------------------------------------------------------------------------- #
# The routes, through the production wiring
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def homebrew_library(monkeypatch):
    """Write a homebrew library and point the builder at it before the main file
    runs. Autouse fixtures run before `user`, thus before the main file."""
    from tests import _public_state as state

    custom_content.save_charm({"id": state.HOMEBREW_ID, "name": state.HOMEBREW_NAME,
                               "category": "melee", "type": "Supplemental",
                               "exalt_type": "Solar",
                               "description": "A homebrew Charm of one player."},
                              custom_dir=state.CUSTOM)
    monkeypatch.setenv(custom_content.CUSTOM_DIR_ENV, str(state.CUSTOM))
    return state


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_wiki_does_not_show_homebrew(user: User, homebrew_library) -> None:
    """⚠ The central ruling of section 9.5. The builder's ruleset merges the
    homebrew library of the process, and the wiki is public."""
    state = homebrew_library
    # The positive control: this library loads into the builder's ruleset.
    assert state.HOMEBREW_ID in rules_db.load_app_ruleset(_DATA).charms

    page = await user.http_client.get(f"/wiki/charms/{state.HOMEBREW_ID}")
    assert page.status_code == 404, "The wiki shows a homebrew Charm."

    for path in ("/wiki/charms?q=Zanzibar+Quokka", "/wiki?q=Zanzibar+Quokka",
                 "/wiki/charms?splat=Solar&category=melee"):
        response = await user.http_client.get(path)
        assert response.status_code == 200
        assert state.HOMEBREW_NAME not in response.text, f"{path} shows the homebrew Charm."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_front_page_is_public(user: User) -> None:
    response = await user.http_client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert 'href="/login"' in response.text
    assert "Your characters" not in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_front_page_knows_a_login(user: User, homebrew_library) -> None:
    pytest.importorskip("bcrypt")
    await user.open("/signup")
    user.find(marker="signup-username").type("Harmonious")
    user.find(marker="signup-password").type(homebrew_library.PASSWORD)
    user.find(marker="signup-confirm").type(homebrew_library.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")

    response = await user.http_client.get("/")

    assert "Your characters" in response.text
    assert "Harmonious" in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_character_page_returns_to_home(user: User, homebrew_library) -> None:
    """🐞 The house-bug shape. "/" is the public front page, thus a way back that
    still went to "/" would leave the logged-in pages. The Party page had that
    trap; piece 4 removed it from the server and the Home button has it now."""
    pytest.importorskip("bcrypt")
    await user.open("/signup")
    user.find(marker="signup-username").type("Harmonious")
    user.find(marker="signup-password").type(homebrew_library.PASSWORD)
    user.find(marker="signup-confirm").type(homebrew_library.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")
    user.find(marker="home-new").click()
    await user.should_see("Identity")

    user.find(marker="top-bar-home").click()

    await user.should_see(marker="home-new")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_about_page_is_public(user: User) -> None:
    response = await user.http_client.get("/about", follow_redirects=False)

    assert response.status_code == 200
    assert "unofficial fan site" in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_wiki_page_kind_opens(user: User) -> None:
    for path in ("/wiki", "/wiki?q=shadow", "/wiki/charms", "/wiki/charms?page=2",
                 "/wiki/charms/solar.melee.excellent-strike",
                 "/wiki/martial-arts", "/wiki/martial-arts/snake",
                 "/wiki/spells", "/wiki/spells?circle=Solar",
                 "/wiki/merits", "/wiki/merits/mf.acute-sense",
                 "/wiki/backgrounds", "/wiki/backgrounds/background.abyssal-command",
                 "/wiki/thaumaturgy", "/wiki/thaumaturgy/science.alchemy",
                 "/wiki/powers", "/wiki/powers/dk.celestial-air",
                 "/wiki/traits", "/wiki/traits/ability.archery",
                 "/wiki/castes?splat=Sidereal", "/wiki/castes/dawn",
                 "/wiki/castes/camp.sequestered-tabernacle",
                 "/wiki/equipment?kind=armor", "/wiki/equipment/weapon.melee.daiklave",
                 "/wiki/artifacts?rating=5", "/wiki/artifacts?tag=weapon",
                 "/wiki/st-screen"):
        response = await user.http_client.get(path, follow_redirects=False)
        assert response.status_code == 200, f"{path} answered {response.status_code}."
        assert response.headers["content-type"].startswith("text/html")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_each_public_page_answers_head(user: User) -> None:
    """🐞 `curl -I` on the deployed server gave 405. FastAPI does not add HEAD to a
    GET route, and link checkers and monitors send HEAD."""
    for path in ("/", "/about", "/wiki", "/wiki/charms",
                 "/wiki/charms/solar.melee.excellent-strike"):
        response = await user.http_client.head(path, follow_redirects=False)
        assert response.status_code == 200, f"HEAD {path} answered {response.status_code}."


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_absent_entry_is_a_404(user: User) -> None:
    response = await user.http_client.get("/wiki/spells/spell.nothing")

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_wiki_is_plain_html(user: User) -> None:
    """Crawlable, and no NiceGUI client for an anonymous visitor. See 9.5."""
    response = await user.http_client.get("/wiki/charms/solar.melee.excellent-strike")

    assert "Excellent Strike" in response.text
    assert response.headers.get("X-Nicegui-Content") != "page"
    assert "client_id" not in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_search_query_is_escaped(user: User) -> None:
    response = await user.http_client.get("/wiki/charms", params={"q": '"><script>x</script>'})

    assert "<script>x</script>" not in response.text
    assert "&lt;script&gt;" in response.text


# --------------------------------------------------------------------------- #
# The reference sections: traits, castes, equipment, artifacts, thaumaturgy,
# Paths and powers, the Storyteller screen
# --------------------------------------------------------------------------- #


def test_each_section_has_a_count_and_an_icon(book) -> None:
    """`nav.groups` and the tab strip index the icons by slug. A section with no icon
    raises on every public page."""
    from exalted_builder.server import nav

    counts = {s.slug: s.count for s in wv.section_counts(book)}
    assert set(counts) == {slug for slug, _title in wv.SECTIONS} == set(nav.SECTION_ICONS)
    assert all(counts.values()), counts


def test_an_unset_weapon_stat_is_a_dash_not_zero(book) -> None:
    """The model gives an absent stat the value 0. The wiki must not print "+0" for a
    stat that the book does not print."""
    weapon = next(w for w in book.weapon_catalog.values()
                  if "speed" not in w.model_fields_set and not w.artifact_rating)
    (row,) = [r for r in _all_rows(book, wv.equipment_list) if r.title == weapon.name]

    assert row.cells[wv._WEAPON_COLUMNS.index("Speed")] == "—"
    assert "Speed" not in {f.label for f in wv.equipment_page(book, weapon.id).facts}


def test_each_equipment_kind_has_its_own_columns(book) -> None:
    listing = wv.equipment_list(book, kind="armor")

    assert {row.group for row in listing.rows} <= set(listing.group_columns)
    assert listing.group_columns["Armor"][0] == "Soak"
    for row in listing.rows:
        assert len(row.cells) == len(listing.group_columns[row.group]), row.title


@pytest.mark.parametrize("path", ["weapons", "camps", "callings"])
def test_a_source_in_the_data_reaches_the_page(book, path) -> None:
    """🐞 These models had no `source` field, thus pydantic dropped the citation of
    each row at load. The wiki is the read site."""
    import json

    rows = [r for r in json.loads((_DATA / f"{path}.json").read_text()) if r.get("source")]
    assert rows, f"No row of {path}.json has a source, thus this case covers nothing."
    row = rows[0]
    page = (wv.equipment_page(book, row["id"]) if path == "weapons"
            else wv.caste_page(book, f"{path[:-1]}.{row['id']}"))

    assert page.source == f"{row['source']['book']} p.{row['source']['page']}"


def test_an_uncited_row_names_no_book(book) -> None:
    armor = next(iter(book.armor_catalog))

    assert wv.equipment_page(book, armor).source == ""


def test_a_virtue_flaw_page_has_its_limit_break(book) -> None:
    flaw = next(iter(book.virtue_flaw_catalog.values()))
    page = wv.trait_page(book, flaw.id)

    assert [b.title for b in page.blocks][:1] == ["Limit Break"]
    assert page.source == flaw.source


def test_an_ability_page_has_the_rating_ladder(book) -> None:
    page = wv.trait_page(book, "ability.archery")

    assert page.extra_title == "Ratings"
    assert len(page.extra_lines) == len(book.trait_descriptions.ability_ladder)


def test_a_caste_page_has_its_anima_powers(book) -> None:
    page = wv.caste_page(book, "dawn")

    assert page.blocks[0].title == "Anima powers"
    assert page.blocks[0].paragraphs[0].startswith(book.castes["dawn"].anima_powers[:20])


def test_the_colleges_have_no_page(book) -> None:
    colleges = [r for r in wv.caste_list(book, splat="Sidereal").rows
                if r.group.endswith("Astrological Colleges")]

    assert len(colleges) == len(book.colleges)
    assert all(r.href == "" for r in colleges)


def test_an_artifact_names_its_merit_not_its_id(book) -> None:
    artifact = next(a for a in book.artifact_catalog.values() if a.requires_merit)
    facts = {f.label: f.value for f in wv.artifact_page(book, artifact.id).facts}

    assert facts["Requires"] == book.merits_flaws[artifact.requires_merit].name


def test_one_mote_is_singular(book) -> None:
    artifact = next(a for a in book.artifact_catalog.values() if a.attunement == 1)
    facts = {f.label: f.value for f in wv.artifact_page(book, artifact.id).facts}

    assert facts["Attunement"] == "1 mote"


def test_a_science_page_lists_its_formulas(book) -> None:
    page = wv.thaumaturgy_page(book, "science.alchemy")
    formulas = [f for f in book.thaum_formulas.values() if f.science_id == "science.alchemy"]

    assert page.rows_title == "Formulas"
    assert len(page.rows) == len(formulas) > 0


def test_the_search_reaches_the_reference_sections(book) -> None:
    sections = {listing.section for listing, _action in wv.search_all(book, "daiklave")}

    assert {"equipment", "artifacts"} <= sections


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_college_is_text_and_the_st_screen_shows_its_tables(user: User) -> None:
    castes = await user.http_client.get("/wiki/castes", params={"splat": "Sidereal"})
    screen = await user.http_client.get("/wiki/st-screen")

    assert '<td class="name">The Captain</td>' in castes.text
    assert "Attack Sequence" in screen.text
    assert '<th scope="col">What happens</th>' in screen.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_an_armor_card_has_the_armor_columns(user: User) -> None:
    response = await user.http_client.get("/wiki/equipment", params={"kind": "armor"})

    assert '<th scope="col">Soak</th>' in response.text
    assert '<th scope="col">Accuracy</th>' not in response.text
