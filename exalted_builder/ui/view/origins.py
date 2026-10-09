"""
ui/view/origins.py — the intra-splat origin and upbringing choices that the
editor offers for each Exalt type.
"""

from __future__ import annotations

from ...models.rules import RuleSet


# Presentation-only: intra-splat chargen origins to offer per Exalt type, and their
# display labels. The origin *value* drives ruleset.budgets_for (keyed "<exalt>" for
# the first/default origin and "<exalt>:<origin>" for the rest); all the budget
# numbers live in chargen_budgets.json — this map is just which choices to show.
_SPLAT_ORIGINS: dict[str, dict[str, str]] = {
    # A Solar trained by the Cult of the Illuminated has a different initiation
    # entirely (p.89): 30 Abilities, 9 Backgrounds, 8 Charms, Essence 3, plus a
    # training camp and a Calling. "standard" has no `Solar:standard` budget row, so
    # it falls back to the plain "Solar" row — the same trick "dynastic" and "loyal"
    # use below.
    "Solar": {"standard": "Standard", "illuminated": "Cult of the Illuminated"},
    # The Outcaste book adds four Dragon-Blooded origins on top of the core two. Each
    # varies by UPBRINGING as well — see _ORIGIN_UPBRINGINGS below, which is the second
    # dropdown; the origin decides Backgrounds/Charms/Virtues, the upbringing decides
    # the Ability budget and its minimums.
    "Dragon-Blooded": {
        "dynastic": "Dynastic", "outcaste": "Outcaste",
        "lookshy": "Lookshy (Seventh Legion)",
        "forest-witch": "Forest Witch",
        "lost-egg": "Lost Egg",
        "pirate": "Pirate (Eos and Ossissa)",
        # Cult p.96: a Dragon-Blooded trained by the Cult of the Illuminated is
        # generated as a standard outcaste with four exceptions (30 Abilities, 7
        # Backgrounds, the Cult's Backgrounds, and a training camp). Unlike the
        # Solar Cult origin there is no Calling — the page never gives them one.
        "illuminated": "Cult of the Illuminated",
    },
    # Abyssal Backgrounds depend on standing with the Deathlord: 13 dots for a loyal
    # deathknight, 5 for a fugitive/renegade (p.122). First key is the default
    # (plain "Abyssal" budget row); "fugitive" maps to "Abyssal:fugitive".
    "Abyssal": {"loyal": "Loyal Deathknight", "fugitive": "Fugitive"},
    # Unlike the above two, Lunar "casteless" is coupled to the Caste field itself,
    # not independent of it (engine.validate.check_lunar_casteless_consistency) — the
    # editor doesn't yet auto-sync the Caste dropdown when this is picked, so choosing
    # "Casteless" here also requires setting Caste to Casteless, or validation flags it.
    "Lunar": {"society": "Society (Silver Pact)", "casteless": "Casteless"},
    # A ronin Sidereal evaded the Celestial Hierarchy entirely (p.100): 25 abilities,
    # 7 backgrounds from a fixed list, 8 Charms with no Sidereal Martial Arts, no
    # Colleges and no Ability minimums. Independent of the Caste field (a ronin still
    # has a Caste), unlike Lunar's casteless.
    "Sidereal": {"hierarchy": "Celestial Hierarchy", "ronin": "Ronin"},
    # Core p.103 draws one line through the mortal rules: a heroic mortal gets 6/4/3
    # Attributes and 22 Ability dots, an ordinary one 4/3/3 and 16. Everything else on
    # the page (5 Backgrounds, no Charms, Essence 1, 21 bonus points) is shared, which
    # is why this is an origin and not two splats. "heroic" is the default and so has
    # no `Mortal:heroic` row — it falls back to the plain "Mortal" row, the same trick
    # "dynastic" and "loyal" use above.
    "Mortal": {"heroic": "Heroic Mortal", "ordinary": "Ordinary Mortal"},
    # E:Ab p.126 and its "THE MUNDANE DEAD" sidebar: the heroic dead get 6/4/3
    # Attributes, 22 Ability dots, six Arcanoi and 21 bonus points; the mundane dead
    # 4/3/3, 16, two and 15. Everything else (Virtues, Essence 2, Fetters, the Essence
    # pool) is shared, which is why this is an origin and not two splats — the same
    # shape the mortal line above takes.
    #
    # Unlike every origin above it, "heroic" is NOT a bare default: ghosts also carry
    # an UPBRINGING, and `_keyed_row` only consults the ":origin:upbringing" key when
    # the origin is non-empty. See _ORIGIN_UPBRINGINGS.
    "Ghost": {"heroic": "Heroic Dead", "mundane": "Mundane Dead"},
    # The God-Blooded Half-Caste heritage (p.47): "learn the Charms of their parents",
    # where the parent's Exalt type IS the origin. Only the Half-Caste heritage uses it —
    # the origin select is gated on heritage_traits.charm_access_parent, so a Ghost-
    # Blooded never sees these. The values are the Exalt type strings themselves, so
    # validate.heritage_charm_access returns character.origin directly.
    # The God-Blooded have no entry HERE — their origin is HERITAGE-keyed
    # (`GodbloodedHeritage.origin_options`: the Half-Caste's five parents, the
    # Fae-Blooded's Noble/Commoner), read by `_origin_options` from the data.
    # The Dragon-Kings (PG p.159-160): two origins with different budgets, Path pools,
    # Backgrounds and mandatory abilities. "modern" has no `Dragon-Kings:modern` budget
    # row, so it falls back to the plain "Dragon-Kings" row — the dynastic trick.
    "Dragon-Kings": {"modern": "Modern", "ancient": "Ancient"},
    # The Mountain Folk (CH6 pp.230-231): Enlightenment is the origin axis, and it
    # rewrites nearly every chargen number — 16/13/10 vs 8/4/3 Attributes, a two-pool
    # Ability budget, per-caste Background dots, trait ceilings, Essence and
    # Willpower caps. "enlightened" HAS a `Mountain-Folk:enlightened` row (unlike the
    # dynastic trick above), so it is the default explicitly.
    "Mountain-Folk": {"enlightened": "Enlightened", "unenlightened": "Unenlightened"},
}

# The second axis, keyed by "<exalt_type>:<origin>". Only origins that HAVE variants
# appear here, and the first key of each is the origin's own default (it has no
# ":<upbringing>" budget row, so it falls back to the origin row — the same trick the
# origins above use against the splat row). The Outcaste book is the only source of
# these so far; every other splat has no entry and so gets no second dropdown.
_ORIGIN_UPBRINGINGS: dict[str, dict[str, str]] = {
    # p.68: a Lookshy Terrestrial who was not raised there trades the 35 Ability dots
    # and the Lookshy minimums for 25/10, but keeps the 13 Backgrounds and 6 Charms.
    "Dragon-Blooded:lookshy": {
        "": "Born in Lookshy", "foreign": "Raised elsewhere"},
    # p.132: an ex-Dynast keeps the Realm schooling; other outcastes get 25 dots; one
    # raised by Oreithyia also buys Virtues and Essence cheaper (p.133).
    "Dragon-Blooded:forest-witch": {
        "": "Ex-Dynast", "outcaste": "Outcaste", "oreithyia": "Raised by Oreithyia"},
    # p.159: three Realm cases plus the Threshold, which is the only one that drops
    # the Aspect/Favored minimum to 10.
    "Dragon-Blooded:lost-egg": {
        "": "Realm, lower-class birth",
        "graduate": "Pasiap's Stair / Cloister of Wisdom",
        "patrician": "Patrician-born",
        "threshold": "Threshold outcaste"},
    # p.96: Dynast or born outcaste; both need Sail.
    "Dragon-Blooded:pirate": {"": "Dynast", "outcaste": "Born outcaste"},
    # E:Ab p.126: where the ghost is FROM decides the Background pool — "Ghosts from
    # areas that uphold the Immaculate Philosophy have five (5) dots to spend on
    # Backgrounds, while those from areas with active ancestor worship have eight (8)",
    # and an Immaculate-region ghost may not buy Ancestor Cult or Grave Goods above •.
    # Independent of heroic/mundane, so both origins carry it.
    "Ghost:heroic": {"": "Ancestor-worshipping region",
                     "immaculate": "Immaculate-dominated region"},
    "Ghost:mundane": {"": "Ancestor-worshipping region",
                      "immaculate": "Immaculate-dominated region"},
}


def _heritage_uses_origin(ruleset: RuleSet, character) -> bool:
    """Whether the character's heritage keys off the origin axis. Two God-Blooded
    heritages do: the Half-Caste's parent Exalt type (p.47) and the Fae-Blooded's
    Noble/Commoner (p.73-79). `GodbloodedHeritage.origin_options` is the single source
    — the editor renders the Origin dropdown from it."""
    cd = ruleset.castes.get(character.caste)
    return bool(cd is not None and cd.heritage_traits is not None
                and cd.heritage_traits.origin_options)


def _origin_options(ruleset: RuleSet, character) -> dict[str, str]:
    """The Origin dropdown options for this character: the splat's origins, EXCEPT
    the God-Blooded, whose origin is their HERITAGE's own axis — the Half-Caste's
    parent Exalt type, the Fae-Blooded's Noble/Commoner — and appears only for that
    heritage (a Ghost-Blooded never sees a meaningless Solar origin). Every other
    splat's origins are unconditional, so they render exactly as before."""
    if character.exalt_type == "God-Blooded":
        cd = ruleset.castes.get(character.caste)
        opts = cd.heritage_traits.origin_options if (
            cd is not None and cd.heritage_traits is not None) else []
        return {o: o for o in opts} if opts else {}
    return _SPLAT_ORIGINS.get(character.exalt_type, {})


def upbringing_options(exalt_type: str, origin: str) -> dict[str, str]:
    """The upbringing choices for this splat/origin, or {} when it has none (which is
    every splat but the Outcaste-book Dragon-Blooded). The UI renders the second
    dropdown only when this is non-empty, so no other splat grows a control."""
    return _ORIGIN_UPBRINGINGS.get(f"{exalt_type}:{origin}", {})
