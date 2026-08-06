"""Dragon-King Paths of Prehuman Mastery — the shared read sites for the rated-track
subsystem (PG pp.175-191). Everything that prices, validates, derives or renders the
Paths goes through this module, so no other module walks `Character.paths` itself.

The Paths are a rated Advantage with their own chargen pool, exactly the College
shape: a first-class rating 1-6 per Path, bought in fixed order, with its own BP/XP
tables and an Essence gate (max rating 1/3/5/6 at Essence 1/2/3-5/6, p.177). Each
dot-level power is ALSO projected into the charm catalogue as a virtual Charm row
(see rules_db._virtual_path_charms) so the Combo machinery and the sheet can name
them — the rating here is the truth, the virtual rows are a projection.

Two of these functions (path_is_favored, path_power_ids) are load-bearing for the
favour mechanics and the Combos bridge respectively; the tests pin both."""

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
    """A Path is Favoured when it is the player's chosen `favored_path` OR one of the
    breed's two element-matching Paths (human ruling 2026-08-05: each breed
    auto-favours its two element Paths — Pterok/Air → Celestial Air + Clear Air, etc.
    — plus one player-chosen Path from any of the other eight). Favoured Paths get the
    Breed/Favoured discount rate on both BP and XP.

    `favored_path` overrides the live character's choice for callers that must read a
    frozen chargen source — the post-lock bonus-point recompute (decision 0003): the
    snapshot is the accounting source once locked, and a drift in `character.favored_path`
    must not re-price creation. Every other caller omits it and gets the live value."""
    if path_id == (favored_path if favored_path is not None else character.favored_path):
        return True
    path = ruleset.paths.get(path_id)
    if path is None:
        return False
    return bool(path.element) and path.element == breed_element(ruleset, character)


def path_power_ids(ruleset: RuleSet, character: Character) -> list[str]:
    """The virtual Charm ids for every dot the character owns in every Path — dots
    1..rating for each rated Path. Feeds the Combos bridge (the virtual rows are
    Charm-format, so Combo legality and the combo panel can resolve them) and the
    sheet. Stable order: Path catalogue order, dots ascending."""
    ratings = path_ratings(character)
    ids: list[str] = []
    for path in ruleset.paths.values():
        for dot in range(1, ratings.get(path.id, 0) + 1):
            ids.append(f"dk.path.{path.id}.dot{dot}")
    return ids


def path_essence_max(ruleset: RuleSet, character: Character) -> int:
    """The Path-rating ceiling for the character's CURRENT Essence rating (p.177:
    1/3/5/6). Resolved against the live rating, never the budget's `essence_start` —
    a chargen BP-bought Essence raise legitimately lifts the cap (round-2 finding 2),
    and keying off the budget row would silently over-cap."""
    b = ruleset.budgets_for(character.exalt_type, character.origin, character.upbringing)
    return b.path_max_by_essence.get(character.essence_rating, 0)
