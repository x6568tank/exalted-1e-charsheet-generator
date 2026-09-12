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

    lists = (wv.charm_list, wv.style_list, wv.spell_list, wv.merit_list, wv.background_list)
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
    await user.should_see("Identity")

    response = await user.http_client.get("/")

    assert "Your characters" in response.text
    assert "Harmonious" in response.text


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_party_page_returns_to_the_hosted_builder(user: User,
                                                            homebrew_library) -> None:
    """🐞 The house-bug shape. The builder moved to `/home`, and "/" is the public
    front page. A party page that still went to "/" would leave the builder."""
    pytest.importorskip("bcrypt")
    await user.open("/signup")
    user.find(marker="signup-username").type("Harmonious")
    user.find(marker="signup-password").type(homebrew_library.PASSWORD)
    user.find(marker="signup-confirm").type(homebrew_library.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see("Identity")

    await user.open("/gm")
    user.find(marker="gm-builder").click()

    await user.should_see("Identity")


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
                 "/wiki/backgrounds", "/wiki/backgrounds/background.abyssal-command"):
        response = await user.http_client.get(path, follow_redirects=False)
        assert response.status_code == 200, f"{path} answered {response.status_code}."
        assert response.headers["content-type"].startswith("text/html")


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
