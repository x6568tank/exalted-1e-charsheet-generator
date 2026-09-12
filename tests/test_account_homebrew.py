"""Each hosted account has its own homebrew library (section 5.3, ruled 2026-09-12).

The library is `<account folder>/custom`. The RuleSet of a session merges that
library over the book and no other. The hosted server switches the default
library off, thus a call site that forgets the folder of its account raises.

⚠ THE SWITCH IS ON in each case of this file (the autouse fixture). A site that
still reads the default library fails here with `NoDefaultLibrary`. With the
switch off, the same site passes and writes to a library that each account
shares. That is why the fixture must not be removed.

`DEFAULT_LIBRARY` is the other half: the environment points the default at it,
and each case asserts that it stays empty.

PRODUCTION wiring: `tests/_auth_main.py` runs `server/main.build_server`. Each
case signs up and presses New character, as a player does.

The static half, `test_each_library_call_in_the_hosted_pages_names_its_folder`,
covers the sites that no case can click: the upload import, the auto-save timer,
and the native file dialogs.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile

import pytest
from nicegui import ui
from nicegui.testing import User

pytest.importorskip("bcrypt")

from exalted_builder import custom_content, rules_db  # noqa: E402
from exalted_builder.models.character import Weapon  # noqa: E402

from . import _auth_state as state  # noqa: E402

MAIN = "tests/_auth_main.py"

# The DEFAULT library. The environment points at it; nothing may write into it.
DEFAULT_LIBRARY = Path(tempfile.gettempdir()) / f"exalted-default-library-{os.getpid()}"


@pytest.fixture(autouse=True)
def _no_default_library(monkeypatch):
    """The hosted switch, and a default library that must stay empty."""
    monkeypatch.setenv(custom_content.CUSTOM_DIR_ENV, str(DEFAULT_LIBRARY))
    custom_content.require_explicit_dir(True)
    yield
    custom_content.require_explicit_dir(False)
    assert not DEFAULT_LIBRARY.exists() or not any(DEFAULT_LIBRARY.rglob("*")), (
        f"A hosted action wrote into the default library {DEFAULT_LIBRARY}.")


_ACCOUNTS = iter(f"Player{n}" for n in range(1000))


async def _open(create_user) -> tuple[User, dict]:
    """Sign up a new account in a new browser and press New character. Return
    the user and the context of the character."""
    user = create_user()
    await user.open("/signup")
    user.find(marker="signup-username").type(next(_ACCOUNTS))
    user.find(marker="signup-password").type(state.PASSWORD)
    user.find(marker="signup-confirm").type(state.PASSWORD)
    user.find(marker="signup-submit").click()
    await user.should_see(marker="home-new")
    before = set(state.REGISTRY.keys())
    user.find(marker="home-new").click()
    await user.should_see("Identity")
    (key,) = set(state.REGISTRY.keys()) - before
    return user, state.REGISTRY.ctx_for(key)


def _show_tab(user: User, name: str) -> None:
    """Select a tab of the builder's own tab bar."""
    bar = next(e for e in user.client.elements.values()
               if isinstance(e, ui.tabs) and e.value in {"Edit", "Sheet"})
    bar.set_value(name)


def _author(ctx: dict, name: str) -> str:
    """Write a Charm into the library of `ctx` and merge it. Return its id."""
    charm_id = custom_content.make_id(name)
    custom_content.save_charm(
        {"id": charm_id, "name": name, "category": "melee", "type": "Supplemental",
         "min_ability": 1, "min_essence": 1}, custom_dir=ctx["custom_dir"])
    rules_db.reload_custom_layer(ctx["ruleset"], ctx["custom_dir"])
    return charm_id


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_library_is_in_the_account_folder(create_user) -> None:
    _, ctx = await _open(create_user)

    assert ctx["custom_dir"] == ctx["home_dir"] / "custom"
    assert ctx["path"].is_relative_to(ctx["home_dir"])
    assert ctx["custom_dir"].is_relative_to(state.ROOT), (
        "The library is outside the session root, thus outside the quota.")


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_the_custom_tab_shows_the_accounts_own_homebrew_only(create_user) -> None:
    user_a, ctx_a = await _open(create_user)
    user_b, ctx_b = await _open(create_user)
    charm_id = _author(ctx_a, "Alpha Only Strike")

    _show_tab(user_a, "Custom")
    await user_a.should_see("Alpha Only Strike")

    _show_tab(user_b, "Custom")
    await user_b.should_see("Custom content")
    await user_b.should_not_see("Alpha Only Strike")
    assert charm_id in ctx_a["ruleset"].charms
    assert charm_id not in ctx_b["ruleset"].charms


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_a_hosted_save_carries_the_accounts_homebrew(create_user) -> None:
    """Save embeds the definitions from the library of the account. A save that
    reads the default library raises under the switch, and no file appears."""
    user, ctx = await _open(create_user)
    charm_id = _author(ctx, "Carried Strike")
    ctx["char"].charms.append(charm_id)

    user.find("top-bar-save").click()
    await user.should_see("Saved")

    saved = ctx["path"].read_text()
    assert charm_id in saved and "custom_definitions" in saved


@pytest.mark.asyncio
@pytest.mark.nicegui_main_file(MAIN)
async def test_save_to_my_library_writes_to_the_account(create_user) -> None:
    user, ctx = await _open(create_user)
    ctx["char"].weapons.append(Weapon(name="Account Blade", accuracy=1, damage=3))
    _show_tab(user, "Gear")
    await user.should_see("Weapons")

    button = next(e for e in user.client.elements.values()
                  if "save-to-library" in getattr(e, "_markers", []))
    button._handle_event({"id": button.id,
                          "listener_id": list(button._event_listeners)[0], "args": {}})
    await user.should_see("to your library")

    rows = custom_content.library_gear("weapons", ctx["custom_dir"])
    assert [r["name"] for r in rows] == ["Account Blade"]
    assert any(w.name == "Account Blade" for w in ctx["ruleset"].weapon_catalog.values())


# --------------------------------------------------------------------------- #
# The static half
# --------------------------------------------------------------------------- #

# The calls that read or write a homebrew library. Each takes the folder as
# `custom_dir=`. `reload_custom_layer` can also take it as its second argument.
_LIBRARY_CALLS = {
    "save_character", "load_character", "save_party", "load_party",
    "absorb_definitions", "embed_definitions", "collect_definitions",
    "reload_custom_layer", "save_gear_row", "build_custom", "build_gear",
    "save_to_path",
}

# The modules that a hosted session runs. The Qt shell is desktop only.
_HOSTED_MODULES = ["builder.py", "gm.py", "gear.py", "saving.py", "custom.py"]

# The desktop entry points in those modules. The server calls none of them.
# `builder.load` opens the starting character of the desktop app.
_DESKTOP_ENTRY_POINTS = {"main", "load"}


def _calls_without_a_folder(source: str) -> list[str]:
    """Return each library call that names no folder, outside a desktop entry point.

    `custom_data_dir` is not checked: it is the desktop fallback of a call that
    got None, and the hosted switch makes it raise."""
    missing: list[str] = []

    def visit(node: ast.AST, in_main: bool) -> None:
        for child in ast.iter_child_nodes(node):
            inside = in_main or (isinstance(child, ast.FunctionDef)
                                 and child.name in _DESKTOP_ENTRY_POINTS)
            if isinstance(child, ast.Call):
                func = child.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
                if name in _LIBRARY_CALLS and not inside:
                    named = any(k.arg == "custom_dir" for k in child.keywords)
                    positional = name == "reload_custom_layer" and len(child.args) >= 2
                    if not (named or positional):
                        missing.append(f"line {child.lineno}: {name}()")
            visit(child, inside)

    visit(ast.parse(source), False)
    return missing


@pytest.mark.parametrize("module", _HOSTED_MODULES)
def test_each_library_call_in_the_hosted_pages_names_its_folder(module: str) -> None:
    """⚠ A call with no folder uses the default library. On the server that is
    one library for each account, which section 5.3 removes. The switch makes it
    raise at run time; this finds it before a player does."""
    source = (Path("exalted_builder/ui") / module).read_text()

    missing = _calls_without_a_folder(source)

    assert not missing, (
        f"ui/{module} calls the homebrew library with no folder: {missing}. Give "
        "each call `custom_dir=ctx[\"custom_dir\"]`, or a parameter that carries it.")


def test_the_static_check_finds_a_call_with_no_folder() -> None:
    """The control. Without it, the check passes on a parser that finds nothing."""
    source = ("def page(ctx):\n"
              "    persistence.save_character(c, p)\n"
              "    rules_db.reload_custom_layer(rs)\n"
              "    rules_db.reload_custom_layer(rs, ctx['custom_dir'])\n"
              "def main():\n"
              "    persistence.load_character(p)\n")

    assert _calls_without_a_folder(source) == [
        "line 2: save_character()", "line 3: reload_custom_layer()"]
