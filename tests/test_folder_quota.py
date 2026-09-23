"""The 10 MB limit of each account folder: `server/quota.py`.

The human set the limit on 2026-09-11.

⚠ The subject is the CHOKE POINT, not the check. The last two sections write
through `persistence.save_character` and `save_party`, which each hosted write site
calls. A check that is correct and not installed is the house bug; the install is
asserted in `test_server_main.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exalted_builder import custom_content, persistence
from exalted_builder.models.character import Character
from exalted_builder.models.party import Party
from exalted_builder.server.quota import FolderQuota, QuotaExceeded, folder_size

LIMIT = 100_000


@pytest.fixture
def root(tmp_path: Path) -> Path:
    path = tmp_path / "sessions"
    (path / "user-1").mkdir(parents=True)
    (path / "user-2").mkdir(parents=True)
    return path


@pytest.fixture
def guard(root: Path):
    """Install a small quota on `root`, and remove it after the case."""
    quota = FolderQuota(root, limit=LIMIT)
    persistence.set_write_guard(quota)
    yield quota
    persistence.set_write_guard(None)


def _fill(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


# --------------------------------------------------------------------------- #
# The check
# --------------------------------------------------------------------------- #


def test_a_write_inside_the_limit_is_allowed(root: Path) -> None:
    FolderQuota(root, limit=LIMIT)(root / "user-1" / "a.json", LIMIT)


def test_a_write_past_the_limit_is_refused(root: Path) -> None:
    _fill(root / "user-1" / "old.json", LIMIT - 400)

    with pytest.raises(QuotaExceeded, match="no space left"):
        FolderQuota(root, limit=LIMIT)(root / "user-1" / "new.json", 401)


def test_a_campaign_folder_is_named_as_a_campaign(root: Path) -> None:
    """A table folder has the quota of an account folder. The message must not say
    "This account" to a Storyteller whose own account has space."""
    _fill(root / "table-0123456789ab" / "log.json", LIMIT - 400)

    with pytest.raises(QuotaExceeded, match="This campaign has no space left") as error:
        FolderQuota(root, limit=LIMIT)(root / "table-0123456789ab" / "awards.json", 401)
    assert "account" not in str(error.value)


def test_a_replaced_file_frees_its_size(root: Path) -> None:
    """A save rewrites one file. Counting the old copy and the new one refuses a
    save that makes the folder no larger."""
    _fill(root / "user-1" / "hero.json", LIMIT - 100)

    FolderQuota(root, limit=LIMIT)(root / "user-1" / "hero.json", LIMIT - 50)


def test_the_files_below_the_folder_count(root: Path) -> None:
    _fill(root / "user-1" / "deep" / "old.json", LIMIT - 100)

    with pytest.raises(QuotaExceeded):
        FolderQuota(root, limit=LIMIT)(root / "user-1" / "new.json", 200)


def test_one_account_does_not_use_the_space_of_another(root: Path) -> None:
    _fill(root / "user-1" / "old.json", LIMIT - 100)

    FolderQuota(root, limit=LIMIT)(root / "user-2" / "new.json", LIMIT - 100)


def test_a_path_outside_the_root_is_not_checked(root: Path, tmp_path: Path) -> None:
    """The desktop library and the desktop saves are outside the session root."""
    FolderQuota(root, limit=LIMIT)(tmp_path / "custom" / "charms.json", 10 * LIMIT)


def test_the_default_limit_is_ten_megabytes(root: Path) -> None:
    assert FolderQuota(root).limit == 10 * 1024 * 1024


def test_folder_size_of_a_missing_folder_is_zero(root: Path) -> None:
    assert folder_size(root / "user-9") == 0


# --------------------------------------------------------------------------- #
# The choke point
# --------------------------------------------------------------------------- #


def test_a_character_save_past_the_limit_is_refused(root: Path, guard) -> None:
    _fill(root / "user-1" / "old.json", LIMIT - 10)
    target = root / "user-1" / "hero.character.json"

    with pytest.raises(QuotaExceeded):
        persistence.save_character(Character(id="hero", name="Hero"), target)

    assert not target.exists(), "A refused save left a file."


def test_a_refused_save_leaves_the_old_file(root: Path, guard) -> None:
    target = root / "user-1" / "hero.character.json"
    persistence.save_character(Character(id="hero", name="Hero"), target)
    before = target.read_bytes()
    _fill(root / "user-1" / "old.json", LIMIT - len(before))

    with pytest.raises(QuotaExceeded):
        persistence.save_character(
            Character(id="hero", name="Hero", player="x" * LIMIT), target)

    assert target.read_bytes() == before


def test_a_party_save_past_the_limit_is_refused(root: Path, guard) -> None:
    _fill(root / "user-1" / "old.json", LIMIT - 10)

    with pytest.raises(QuotaExceeded):
        persistence.save_party(Party(id="circle", name="Circle"), root / "user-1" / "circle.party.json")


def test_a_homebrew_row_past_the_limit_is_refused(root: Path, guard) -> None:
    """The library of an account is `<account folder>/custom` (section 5.3), thus
    the quota of the account covers it. Before 2026-09-12 the library was one
    folder for the process, outside the root, with no limit."""
    _fill(root / "user-1" / "old.json", LIMIT - 10)

    with pytest.raises(QuotaExceeded):
        custom_content.save_charm(
            {"id": "custom.big", "name": "Big", "category": "melee",
             "type": "Supplemental", "description": "x" * 1000},
            custom_dir=root / "user-1" / "custom")

    assert custom_content.library_charms(root / "user-1" / "custom") == []


def test_no_guard_means_no_limit(root: Path) -> None:
    """The desktop installs no guard."""
    _fill(root / "user-1" / "old.json", LIMIT)

    persistence.save_character(Character(id="hero", name="Hero"),
                               root / "user-1" / "hero.character.json")
