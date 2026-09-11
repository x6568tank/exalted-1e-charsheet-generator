"""`builder.session_context_factory` gives each browser session its own context.

`register_pages` receives ONE context from its caller. That context stops being
the live application state and becomes a PROTOTYPE: the factory copies it for
each session key, thus two browsers get two `Character` objects.

See `docs/plans/hosting-state-model.md` section 3.4. The end-to-end proof is
`tests/test_session_isolation.py`; this file tests the copy rule on its own,
because the copy has one invariant that the end-to-end test cannot see.

⚠ THE INVARIANT: inside one context, `ctx["char"]` can BE a party member's
character, by identity. `open_member` points it there by reference and the party
card then follows the builder's edits with no syncing code. A factory that
copies `char` and `party` independently breaks that, and
`docs/plans/hosting-state-model.md` section 3.6 records that no other test
fails when it does.
"""

from pathlib import Path

import pytest

from exalted_builder import persistence
from exalted_builder.models.character import Character
from exalted_builder.models.party import Party, PartyMember
from exalted_builder.ui import builder


def _prototype() -> dict:
    """A context with a standalone character and a party of two."""
    ctx = builder.make_context(Character(id="proto", name="Prototype", caste="dawn"),
                               Path("/saves/proto.json"))
    ctx["party"] = Party(id="party.proto", members=[
        PartyMember(character=Character(id="m0", name="Member Zero", caste="dawn")),
        PartyMember(character=Character(id="m1", name="Member One", caste="zenith")),
    ])
    ctx["adversary_catalog"] = {"bandit": object()}
    return ctx


def test_two_keys_get_two_characters() -> None:
    factory = builder.session_context_factory(_prototype())
    a, b = factory("session-a"), factory("session-b")

    assert a is not b
    assert a["char"] is not b["char"]
    a["char"].name = "Edited"
    assert b["char"].name == "Prototype"


def test_the_copy_starts_equal_to_the_prototype() -> None:
    proto = _prototype()
    ctx = builder.session_context_factory(proto)("session-a")

    assert ctx["char"].name == proto["char"].name
    assert ctx["char"].id == proto["char"].id
    assert ctx["path"] == proto["path"]
    assert ctx["dir"] == proto["dir"]
    assert [m.character.name for m in ctx["party"].members] == ["Member Zero", "Member One"]


# --------------------------------------------------------------------------- #
# The destination. See hosting-state-model.md section 3.7.
#
# ⚠ These assert on the FACTORY, not on a written file. A test that writes a
# character and reads it back passes when both sessions share one destination.
# --------------------------------------------------------------------------- #

_ROOT = Path("/srv/exalted/sessions")


def test_two_keys_get_two_destinations() -> None:
    """The section 3.7 blocker.

    Section 3.4a isolated the Character and left the destination shared: the
    factory copied `prototype["path"]` verbatim, so every session pointed at one
    file. Auto-save then makes N browsers write that file on a timer, last
    writer wins, with nothing reported.
    """
    factory = builder.session_context_factory(_prototype(), session_root=_ROOT)
    a, b = factory("session-a"), factory("session-b")

    assert a["dir"] != b["dir"], (
        "Two sessions share one save directory. `open_member` derives its "
        "filename from `dir`, thus both sessions write one file."
    )
    assert a["path"] != b["path"], (
        "Two sessions share one save path. Auto-save writes one file from N "
        "browsers and reports no error."
    )


def test_the_destination_is_under_the_root_and_names_the_key() -> None:
    ctx = builder.session_context_factory(_prototype(), session_root=_ROOT)("session-a")

    assert ctx["dir"] == _ROOT / "session-a"
    assert ctx["path"].parent == _ROOT / "session-a"


def test_the_filename_still_comes_from_the_character() -> None:
    """Only the directory changes. The filename rule is unchanged, thus a rename
    still renames the file."""
    proto = _prototype()
    ctx = builder.session_context_factory(proto, session_root=_ROOT)("session-a")

    assert ctx["path"].name == persistence.suggested_filename(proto["char"])


def test_a_member_char_still_gets_its_own_filename() -> None:
    """The prototype points at a party member, thus the session's file is named
    for THAT character and not for the standalone one."""
    proto = _prototype()
    proto["char"] = proto["party"].members[1].character
    proto["member"] = 1

    ctx = builder.session_context_factory(proto, session_root=_ROOT)("session-a")

    assert ctx["path"].name == persistence.suggested_filename(proto["party"].members[1].character)
    assert ctx["path"] == _ROOT / "session-a" / "member-one.character.json"


def test_open_member_lands_inside_the_session_directory() -> None:
    """`open_member` recomputes the filename from `ctx["dir"]`. Thus isolating
    `dir` is what keeps a member's save inside this session."""
    factory = builder.session_context_factory(_prototype(), session_root=_ROOT)
    a, b = factory("session-a"), factory("session-b")

    builder.open_member(a, 0)
    builder.open_member(b, 0)

    assert a["path"] != b["path"], (
        "Two sessions opened the same party member and got one path. The "
        "members are different objects; the destination is not."
    )
    assert a["path"] == _ROOT / "session-a" / "member-zero.character.json"


def test_no_session_root_keeps_the_prototype_path() -> None:
    """The desktop. One user owns the file system, thus Save must write the file
    that the user opened.

    ⚠ This is the negative control for the tests above, and it is also the
    shipped desktop behaviour. Do not "fix" it to isolate. A hosted run supplies
    a root; see server/config.session_root, which raises when it is absent.
    """
    proto = _prototype()
    factory = builder.session_context_factory(proto)
    a, b = factory("session-a"), factory("session-b")

    assert a["path"] == proto["path"] == b["path"]
    assert a["dir"] == proto["dir"] == b["dir"]


@pytest.mark.parametrize("hostile", ["../../etc", "a/b", "..", "/absolute", ""])
def test_a_key_cannot_escape_the_root(hostile) -> None:
    """The key comes from a signed cookie, thus a client cannot choose it today.
    The containment does not depend on that staying true.

    ⚠ A key that reaches the file system unchecked makes `<root>/<key>` a path
    traversal. This asserts the containment, not a particular replacement
    character.
    """
    ctx = builder.session_context_factory(_prototype(), session_root=_ROOT)(hostile)

    assert _ROOT in ctx["dir"].parents or ctx["dir"].parent == _ROOT
    assert ctx["dir"].resolve().is_relative_to(_ROOT.resolve())


def test_a_normal_key_is_its_own_directory_name() -> None:
    """A NiceGUI session id is a UUID, thus the usual directory is readable and
    carries no digest."""
    assert builder.session_dirname("7d1f2e0a-4c3b-4a1d-9f77-0b2c3d4e5f60") == (
        "7d1f2e0a-4c3b-4a1d-9f77-0b2c3d4e5f60")


@pytest.mark.parametrize("left,right", [
    ("a/b", "a_b"),
    ("../x", ".._x"),
    ("", "session"),
])
def test_two_keys_never_get_one_directory_name(left, right) -> None:
    """⚠ The replacement of an unsafe character is not sufficient on its own. It
    maps `"a/b"` and `"a_b"` to one name, which is this section's own defect one
    level down: two sessions in one directory, writing one file."""
    assert builder.session_dirname(left) != builder.session_dirname(right)


def test_an_edit_in_one_session_does_not_reach_the_prototype() -> None:
    proto = _prototype()
    ctx = builder.session_context_factory(proto)("session-a")

    ctx["char"].name = "Edited"
    ctx["party"].members[0].character.name = "Edited Member"

    assert proto["char"].name == "Prototype"
    assert proto["party"].members[0].character.name == "Member Zero"


def test_the_party_is_copied_per_session() -> None:
    factory = builder.session_context_factory(_prototype())
    a, b = factory("session-a"), factory("session-b")

    assert a["party"] is not b["party"]
    a["party"].members[0].character.name = "Edited Member"
    assert b["party"].members[0].character.name == "Member Zero"


@pytest.mark.parametrize("member_index", [None, 1])
def test_the_char_is_the_party_member_when_the_prototype_says_so(member_index) -> None:
    """The invariant in this file's docstring.

    `member_index` None is the `close_member` state: the builder forgets WHICH
    member it edits, and `char` still IS that member's character.
    """
    proto = _prototype()
    proto["char"] = proto["party"].members[1].character
    proto["member"] = member_index

    ctx = builder.session_context_factory(proto)("session-a")

    assert ctx["char"] is ctx["party"].members[1].character, (
        "The copy points `char` at a different object from the party member. "
        "Builder edits stop reaching the party card, and nothing else fails."
    )
    ctx["char"].name = "Edited Member"
    assert ctx["party"].members[1].character.name == "Edited Member"


def test_a_standalone_char_is_not_smuggled_into_the_party() -> None:
    """The negative control for the test above. The prototype's `char` is NOT a
    party member, thus the copy's `char` must not be one either."""
    ctx = builder.session_context_factory(_prototype())("session-a")

    assert all(ctx["char"] is not m.character for m in ctx["party"].members)


def test_the_adversary_catalogue_is_shared() -> None:
    """Templates are read-only rules data. Copying them for each session costs
    memory and buys nothing. See section 3.3."""
    proto = _prototype()
    factory = builder.session_context_factory(proto)

    assert factory("session-a")["adversary_catalog"] is proto["adversary_catalog"]


def test_the_same_key_is_not_reused_by_the_factory() -> None:
    """The factory makes a NEW context on each call. The registry, not the
    factory, gives one key one context. See server/session.py."""
    factory = builder.session_context_factory(_prototype())

    assert factory("session-a") is not factory("session-a")
