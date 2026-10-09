"""
models/rules/gear.py — the equipment catalogue models: goods, armor, weapons, and
artifacts.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ._base import Source


# --------------------------------------------------------------------------- #
# Equipment catalog
#
# Catalog entries are autofill sources for the corebook gear tables. The
# character stores a *resolved inline copy* (see character.Weapon / .Armor),
# not a reference, because equipment frequently varies per character (artifacts,
# masterwork, enchantment) in a way Charms and spells never do.
# --------------------------------------------------------------------------- #

class ArmorWeight(str, Enum):
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"
    SUPERHEAVY = "Superheavy"


class GearType(BaseModel):
    """One row of the mundane price tables (Manacle and Coin p.123, which follows the
    corebook's pp.323-324 and prices it in cash as well as Resources dots).

    Two kinds, and the split is the human's ruling of 2026-08-13:

    * `goods` — something the character then HOLDS: clothes, jewelry, an animal, an
      estate. These can be bought into `Character.gear` and appear in the inventory.
    * `service` — upkeep, an event, a commission or a rental ("Staff a grand palace for
      a month", "Rent a mercenary company", "Donatives necessary to be named an
      imperial prefect"). Priced, never owned, and shown as a REFERENCE price list. A
      character does not carry a month of stabling in her pack, and modelling one as an
      inventory row would be the tracker pretending to be a chronicle simulator — the
      same reasoning that keeps training times out (see CLAUDE.md).

    `cash` is the printed jade/silver equivalent kept verbatim as text ("6 minae 950
    dinars"). It is REFERENCE, never arithmetic: the book says outright that the
    Resources ladder is not linear and that converting it is a Storyteller judgement
    (M&C p.122), so this build stores what is printed and computes nothing from it.
    """
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: str = "goods"                    # "goods" (ownable) | "service" (reference)
    category: str = ""                     # the printed table heading
    resources_cost: int = Field(default=0, ge=0)
    cash: str = ""                         # printed jade/silver equivalent, verbatim
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    source: Source = Field(default_factory=Source)


class ArmorType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    weight: ArmorWeight
    soak_lethal: int                       # corebook table is Soak (L/B)
    soak_bashing: int
    mobility_penalty: int = 0
    fatigue: int = 0
    resources_cost: int = Field(default=0, ge=0)   # dots of Resources required to buy
    # Artifact armour (0 = mundane). artifact_rating is the dots of Artifact
    # Background needed to start with it; attunement is the motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    # Everything the fields above cannot hold — the Most Terrifying Armor of the Air
    # Dragon prints a Strength bonus column and flight rules (Aspect Book: Air p.81).
    # The WeaponType twin holds Strength-relative damage and odd rates.
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    # SHIELDS ride on this model rather than getting one of their own. They are
    # worn equipment with a mobility penalty and no soak, and a character's armour
    # is already a LIST, so a shield is simply another row — no second slot, no
    # second catalogue, and characters get shields for free. `tags: ["shield"]` is
    # the discriminator; RuleSet.shields / .body_armor split on it.
    #
    # These two are the only shield-specific numbers, 0 on every real armour: the
    # p.335 shields differ on them (a buckler "does nothing to protect the
    # character from missile fire", a tower shield raises ranged difficulty by 2).
    # Display only — decision 0008 keeps attack resolution out of this build.
    difficulty_melee: int = 0          # +N to hit the bearer hand-to-hand
    difficulty_ranged: int = 0         # +N to hit the bearer with missile fire


class WeaponType(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    speed: int = 0                         # melee; modifier to initiative
    accuracy: int = 0
    damage: int = 0
    damage_type: str = "L"                 # "L" lethal / "B" bashing
    defense: int = 0                       # melee
    rate: int = 0
    range: int = Field(default=0, ge=0)    # yards; 0 = melee only (thrown/archery)
    max_strength: int = Field(default=0, ge=0)   # bows: the Strength the bow is built for
    # Minimums to wield without penalty (Str / Dex / Martial Arts; 0 = none).
    min_strength: int = Field(default=0, ge=0)
    min_dexterity: int = Field(default=0, ge=0)
    min_martial_arts: int = Field(default=0, ge=0)
    # Artifact weapons (0 = mundane). artifact_rating is the dots of Artifact
    # Background needed to start with it; attunement is the motes to commit.
    artifact_rating: int = Field(default=0, ge=0)
    attunement: int = Field(default=0, ge=0)
    resources_cost: int = Field(default=0, ge=0)
    notes: str = ""                        # special cases (e.g. charge damage)
    tags: list[str] = Field(default_factory=list)
    # The page that prints this row. None when no page is known. ⚠ None, not
    # `Source()`, which names "Core". Read site: the public wiki (`ui/wiki_view`).
    source: Optional[Source] = None


class ArtifactType(BaseModel):
    """One entry in the rated-artifact catalogue (data/artifacts.json) — the list the
    standalone-artifact rows' name dropdown is fed from.

    An artifact here is a rated object a character can own that is neither weapon nor
    armour (the shape `Character.artifacts` stores), plus the book's own gear-statblocked
    artifacts which ALSO live in weapons.json/armor.json — a Skirmish Pike appears here
    (so the catalogue is complete) and there (so a player who wants its stats adds it as
    a weapon). `rating` is the entry's primary printed rating; `rating_notes` carries the
    ranges some print ("• or •••" — an echo jewel or shieldstone gauntlet). The dropdown
    autofills `name` and `rating` on a pick, so `rating` is the default the player then
    edits."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    rating: int = Field(ge=1, le=5)
    rating_notes: str = ""                  # e.g. "• or •••", "• to •••••"
    # Motes a wielder commits to use it (core p.344). Copied onto a fresh
    # `character.ArtifactEntry` on a pick, like `rating`.
    #
    # ⚠ Author a nonzero value ONLY for genuinely standalone Wonders. The rows that are
    # gear-statblocked duplicates of a weapons.json/armor.json entry (the Skirmish Pike
    # above) already have an authoritative number on `Weapon`/`Armor`; a second copy
    # here is two numbers that can drift. Leave those at 0 and let the player enter the
    # item as a weapon or armour row — the steer the catalogue already gives for stats.
    #
    # ⚠ Zero-defaulted, so "authored clean" and "never backfilled" look identical. The
    # backfill is its own authoring pass and has not been done.
    attunement: int = Field(default=0, ge=0)
    description: str = ""                   # short, human-vetted from the source page
    source: str = ""                        # e.g. "MF p.279"
    # What it costs to BUY one, in Resources dots (Manacle and Coin p.125). A different
    # question from `rating`, and a different scale — a daiklave is Artifact •• and
    # Resources ••••, because `rating` is what the Background spends "to start the game
    # owning" it (core p.342) and this is what cash buys in play. Decision 0017; only
    # the seven wonders M&C prices carry it, and 0 means the book gives no price.
    resources_cost: int = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list)   # kind: tool/communication/weapon/...
    # WHICH Background pays for this entry, and therefore which budget its rating is
    # denominated in. Everything in the catalogue was Artifact until the corebook
    # Hearthstones (pp.338-340) were authored, and a Hearthstone's dots are its MANSE
    # rating — the stone comes with the Manse that grew it, not with Artifact dots.
    # Without this field the ten stones would be indistinguishable from artifacts in
    # `data/artifacts.json` and picking one would append an `ArtifactEntry` that
    # charges the p.131 Artifact budget for something the Artifact Background never
    # bought. `engine.artifacts.purchasable_with_artifact` is the read site; the
    # artifact row's combobox and its catalogue dialog are both filtered through it.
    background: str = "artifact"            # "artifact" | "manse"
    # A MERIT id this entry is gated behind, or "" for the ordinary majority. The third
    # acquisition channel, and the reason `rating` can be a polite fiction: the Mantle
    # of Brigid and the Sword of Ice (Book of Three Circles pp.25-27) print
    # "(ARTIFACT N/A)" where every other entry prints dots, because they are plot
    # devices rather than items a Background buys. The human's ruling 2026-08-13 is
    # that they cost the **Legendary Artifact 10-pt Merit** (PG p.24) — which the Merit's
    # own printed text all but says, naming "the Mantle of Brigid or the Eye of
    # Autochthon" as its examples and warning that Storytellers "do not need to allow
    # this Merit ever".
    #
    # ⚠ The id lives HERE, in data, and nowhere in code: no module outside
    # `engine/merits.py` may name a Merit id (decision 0011, and a test greps for it).
    # Every read site is generic — it compares this field against the ids the character
    # holds. Read sites: `engine.artifacts.purchasable_with_artifact` (which EXCLUDES
    # these, so they never reach an Artifact-dot surface), `engine.artifacts.
    # purchasable_artifacts` (which adds them back once the Merit is held) and
    # `engine.validate.check_artifacts` (which reports owning one without it).
    requires_merit: str = ""
