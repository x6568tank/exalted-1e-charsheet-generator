"""Two browser sessions must not share one save destination.

Section 3.4a of `docs/plans/hosting-state-model.md` isolated the Character. It did
not isolate the destination: `session_context_factory` copied `prototype["path"]`,
so every session pointed at one file. Section 3.7 closes that, and the auto-save
timer is the live caller that makes it matter — without isolation it is N browsers
writing one file on a timer, last writer wins, with nothing reported.

The copy rule on its own is `tests/test_session_context_factory.py`. This file
runs the PRODUCTION wiring, because the factory being correct does not show that
the pages use it, and because two handlers recompute the destination AFTER the
factory has set it.

⚠ Read `test_the_harness_gives_two_independent_sessions` first. A shared harness
client makes the other cases fail for a reason that is not the defect.

⚠ Assert on the CONTEXT, not on a written file. A test that saves and reads one
file back passes when both sessions share that file. See section 3.7.
"""

import pytest
from nicegui.testing import User
from nicegui.timer import Timer

from exalted_builder import persistence
from exalted_builder.models.character import Character
from exalted_builder.ui import builder

from . import _session_dest_state as state

MAIN = "tests/_session_dest_main.py"


def _ctx(user: User) -> dict:
    """The live context of `user`'s session.

    Read it out of the registry by the session key, which is what the page
    handler does. ⚠ Read `state.REGISTRY` through the module; the main file
    assigns it after this test module is imported.
    """
    keys = state.REGISTRY.keys()
    assert keys, "No session reached the registry. The page did not resolve a context."
    return state.REGISTRY.ctx_for(keys[-1])


def _timers(user: User) -> list[Timer]:
    """The timers that `user`'s page registered.

    ⚠ Call `timer.callback()` rather than waiting. `saving.AUTOSAVE_SECONDS` is a
    real debounce, thus a test that waits for it costs that much and proves no
    more.
    """
    return [e for e in user.client.elements.values() if isinstance(e, Timer)]


def _paths_by_session() -> list:
    """The save path of every live session, in insertion order."""
    return [state.REGISTRY.ctx_for(k)["path"] for k in state.REGISTRY.keys()]


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_harness_gives_two_independent_sessions(create_user) -> None:
    """The control. Without it, a red run below is ambiguous: a harness that hands
    both users one client produces the same failure as an app that hands both
    users one destination."""
    a, b = create_user(), create_user()
    await a.open("/")
    await b.open("/")

    assert a.client.id != b.client.id, (
        "The harness gave both users one client. The cases below cannot tell app "
        "sharing from harness sharing until this passes."
    )
    assert len(state.REGISTRY) == 2, (
        f"Two clients produced {len(state.REGISTRY)} session(s) in the registry. "
        "The session key does not separate them, thus no destination can."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_sessions_get_two_destinations(create_user) -> None:
    """The section 3.7 blocker, through the real page."""
    a, b = create_user(), create_user()
    await a.open("/")
    await b.open("/")

    first, second = _paths_by_session()

    assert first != second, (
        f"Two sessions both save to {first}. One browser overwrites the other, "
        "and nothing reports it."
    )
    assert first.parent != second.parent


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_destination_is_inside_the_session_root(create_user) -> None:
    """The prototype's path is outside the root. A session that keeps it is the
    defect."""
    a = create_user()
    await a.open("/")

    path = _ctx(a)["path"]

    assert path.is_relative_to(state.ROOT), (
        f"The session saves to {path}, which is outside {state.ROOT}. It kept the "
        "prototype's path."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_new_character_stays_inside_the_session_root(create_user) -> None:
    """🐞 The handler that undoes the factory.

    `new_character` recomputed the destination from
    `persistence.default_save_dir()`, which is process-wide. Thus the factory gave
    the session its own directory and the first click of New took it back out, to
    a folder that every session shares. The same applies to an upload, which
    `_apply_loaded` handles with no path.

    ⚠ This is why this file exists. `test_session_context_factory.py` passes with
    this defect present: the factory is correct and a later handler overrules it.
    """
    a = create_user()
    await a.open("/")
    before = _ctx(a)["path"]

    a.find("New").click()
    await a.should_see("Start a new character?")
    a.find("New character").click()
    await a.should_see("Started a new character")

    after = _ctx(a)["path"]

    assert after != before, (
        "The New click did not repoint the destination, thus this test cannot see "
        "the defect it exists to find. The name drives the filename."
    )
    assert after.is_relative_to(state.ROOT), (
        f"A new character saves to {after}, which is outside {state.ROOT}. The "
        "handler recomputed the destination from a process-wide default and threw "
        "away the session's own directory."
    )


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_auto_save_timer_is_wired_and_writes_the_session_file(create_user) -> None:
    """The mechanism exists in `ui/saving.py` and has its own tests. This case
    says the page CALLS it — a correct mechanism with no call site is this
    project's usual defect.

    ⚠ Do not assert on a notification. The auto-save is quiet on purpose.
    """
    a = create_user()
    await a.open("/")
    ctx = _ctx(a)
    target = ctx["path"]
    assert not target.exists(), "The session file exists before any edit."

    ctx["char"].name = "AutoSavedName"
    # Run the callback that the timer runs. ⚠ The interval is 5 s; a test that
    # waits for it adds that to the suite and still does not prove the wiring.
    await a.should_see("Identity")
    assert _timers(a), "The page registered no timer at all."
    for timer in _timers(a):
        timer.callback()

    assert target.exists(), (
        f"No timer wrote {target}. The auto-save is not wired into the page, thus "
        "an evicted session loses every edit."
    )
    assert persistence.load_character(target).name == "AutoSavedName"


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_two_sessions_auto_save_to_their_own_files(create_user) -> None:
    """🐞 The hazard that section 3.7 names: auto-save is the live caller that
    makes a shared destination reachable. Two sessions editing at once must
    produce two files, each with its own name."""
    a, b = create_user(), create_user()
    await a.open("/")
    await b.open("/")

    keys = state.REGISTRY.keys()
    ctx_a, ctx_b = (state.REGISTRY.ctx_for(k) for k in keys)
    ctx_a["char"].name = "SessionAName"
    ctx_b["char"].name = "SessionBName"

    for user in (a, b):
        for timer in _timers(user):
            timer.callback()

    assert persistence.load_character(ctx_a["path"]).name == "SessionAName"
    assert persistence.load_character(ctx_b["path"]).name == "SessionBName", (
        "Session B's file holds another session's character. The two sessions "
        "auto-saved over one destination."
    )


def test_the_desktop_gets_no_auto_save_timer() -> None:
    """⚠ Auto-save and destination isolation share one switch, thus the hazardous
    pair cannot be configured. `build_app` defaults `auto_save` to False, which is
    the desktop: one user, no eviction, and manual Save is the honest UX."""
    import inspect

    signature = inspect.signature(builder.build_app)

    assert signature.parameters["auto_save"].default is False


def test_the_desktop_keeps_the_prototype_path() -> None:
    """The negative control for the whole file, and the shipped desktop
    behaviour.

    `register_pages` with no `session_root` must not isolate. One user owns the
    file system, thus Save writes the file that the user opened.
    """
    proto = builder.make_context(Character(id="desk", name="Desk"),
                                 state.ROOT / "opened.character.json")
    factory = builder.session_context_factory(proto)

    assert factory("one")["path"] == proto["path"] == factory("two")["path"]
