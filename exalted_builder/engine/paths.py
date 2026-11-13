"""Dragon-King Paths of Prehuman Mastery — the read sites of the Path track (PG
pp.175-191). No other module walks `Character.paths`.

A Path is rated 1-6, bought in fixed order, with its own pool, BP/XP tables and
Essence gate (p.177). Each power is also a virtual Charm row
(rules_db._virtual_path_charms) for Combos and the sheet. The rating is the source
value."""

from ..models.character import Character
from ..models.rules import RuleSet


def path_ratings(character: Character) -> dict[str, int]:
    """path_id -> rating for the character's Paths (0 for any unowned Path)."""
    return {p.path_id: p.rating for p in character.paths}


def breed_element(ruleset: RuleSet, character: Character) -> str:
    """The character's breed's element ("air"/"wood"/"fire"/"water"), or "" when their
    caste has no breed_traits (i.e. the character is not a Dragon-King)."""
    cd = ruleset.castes.get(character.caste)
    return cd.breed_traits.element if (cd and cd.breed_traits) else ""


def path_is_favored(ruleset: RuleSet, character: Character, path_id: str,
                    *, favored_path: str | None = None) -> bool:
    """Return True if the Path is Favoured: the chosen `favored_path`, or one of the
    two Paths of the breed element (human's ruling).

    `favored_path` overrides the live value, for a caller that reads the snapshot
    (decision 0003)."""
    if path_id == (favored_path if favored_path is not None else character.favored_path):
        return True
    path = ruleset.paths.get(path_id)
    if path is None:
        return False
    return bool(path.element) and path.element == breed_element(ruleset, character)


def path_power_ids(ruleset: RuleSet, character: Character) -> list[str]:
    """Return the virtual Charm ids of each owned Path dot, for Combos and the sheet.
    Order: catalogue order, dots ascending."""
    ratings = path_ratings(character)
    ids: list[str] = []
    for path in ruleset.paths.values():
        for dot in range(1, ratings.get(path.id, 0) + 1):
            ids.append(f"dk.path.{path.id}.dot{dot}")
    return ids


def path_essence_max(ruleset: RuleSet, character: Character) -> int:
    """Return the Path ceiling for the CURRENT Essence (p.177). Never
    `essence_start`: a BP-bought Essence raise lifts the cap."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return b.path_max_by_essence.get(character.essence_rating, 0)
