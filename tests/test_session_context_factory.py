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
