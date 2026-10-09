"""
ui/view/house_rules.py — the Storyteller options: the rows of the per-character
and the table-wide house rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field, field as dc_field

from ...engine import derive, validate
from ...models.character import Character, HouseRules
from ...models.rules import RuleSet


# --------------------------------------------------------------------------- #
# Storyteller options (Character.house_rules)
#
# The model marks TABLE-WIDE vs PER-CHARACTER in comments only — a deliberate
# choice (human, 2026-07-29) to keep HouseRules one flat model. The tab still has
# to *show* that split, so the machine-readable version lives here, in the
# presenter, rather than being pushed back into the model. A future party-wide
# "apply to all" control should read `scope` from here too.
# --------------------------------------------------------------------------- #

@dataclass
class HouseRuleRow:
    field: str
    label: str
    scope: str              # 'table' | 'character'
    citation: str
    description: str
    # bool for a plain toggle; a str for a multiple-choice rule, whose `options` maps
    # stored value -> label. `options` empty means it renders as a checkbox. The
    # Inheritance-rating row is an int (1-5) on the model, shown in the select as its
    # option key (a str), with "per-character" standing in for None.
    value: bool | str | int | None
    options: dict[str, str] = dc_field(default_factory=dict)
    note: str = ""          # why it currently does nothing, when it doesn't
    # True when the rule CANNOT bite for this character as she stands — a wrong splat,
    # a wrong caste, a threshold not yet reached, or a gate the lock has already
    # closed. The row is still offered (an ST hunting for a toggle must find it), so
    # this is what lets a renderer dim it. ⚠ Derived HERE and not by reading `note`
    # for a prefix: the note is prose and rewording it would silently un-dim rows.
    inert: bool = False


# (field, label, scope, citation, description) — ordered as the tab renders them.
_HOUSE_RULES = [
    ("magic_for_everyone", "Magic for Everyone", "table", "Player's Guide p.115",
     "Every starting character gets one free ritual, formula or printed aspect per "
     "two dots of Occult (level 3 or lower). Arts and Sciences are never free."),
    ("restrict_chargen_ritual_level", "Cap starting rituals at level 3", "table",
     "Player's Guide p.113",
     "Starting characters may not buy rituals above level 3. Independent of the "
     "Science cap — the book offers them as 'and/or'."),
    ("restrict_chargen_science_rating", "Cap starting Sciences at 3 dots", "table",
     "Player's Guide p.113",
     "Starting characters may not buy a Science above three dots. Experience is "
     "unaffected: a Science raised past 3 in play stays legal."),
    ("st_foreign_charms", "May start play knowing foreign Charms", "character",
     "Core p.127",
     "Storyteller permission for THIS character to begin play already knowing "
     "another Exalt type's Charms. After chargen the rule asks only for a willing "
     "tutor, so this stops mattering once the sheet is locked."),
    ("mortal_favored_ability", "Heroic mortal may pick a Favored Ability", "character",
     "Core p.103",
     "Grants one Favored Ability, discount included. The price is a ceiling: no other "
     "Ability may be rated above it. Only affects splats with no castes."),
    ("st_celestial_manse_over_three", "Sidereal may hold Celestial Manse above 3 dots",
     "character", "The Sidereals p.106",
     "Storyteller permission for THIS Sidereal to own a Celestial Manse above three "
     "dots — 'Characters cannot buy above Celestial Manse ••• without special "
     "Storyteller permission'. The ceiling binds on both sides of the lock, and this "
     "lifts it for one character only."),
    ("st_mortal_artifact_manse", "Mortal may hold Artifact and Manse", "character",
     "Core p.103",
     "Storyteller permission for THIS mortal to take the Artifact or Manse Background "
     "— 'may not purchase the Artifacts or Manse Backgrounds without Storyteller "
     "permission; if a mortal has control over one of these, it's a plot device'. "
     "Chargen only: there is no post-lock purchase to bar."),
    ("committed_motes_reduce_free_essence",
     "Committed motes come out of the freely-drawable third", "character",
     "Player's Guide p.120 — unsourced interaction",
     "Essence Awareness splits a mortal's pool into a third drawable normally and two "
     "thirds needing a Willpower roll. The book never says which portion motes "
     "committed to an artifact leave from. OFF: the third is taken of the printed "
     "pool, so committing does not move the line. ON: it is taken of what remains "
     "after commitments. Affects the Play tracker only, never the sheet."),
    ("terrestrial_essence_transcendence", "Terrestrial may pass Essence 7", "character",
     "Player's Guide p.258",
     "Terrestrial Exalts are held at Essence 7 without 'outside energies' — dietary "
     "and meditational regimens, powerful Hearthstones and the like. None of that is "
     "on the sheet, so this is the Storyteller asserting it happened."),
    ("all_backgrounds_available", "Open every Background to every splat", "table",
     "The Outcaste p.66",
     "By default a character is offered the Backgrounds her own book prints — "
     "Arsenal belongs to Lookshy, Sifu to the Sidereals. The books ask for this "
     "switch in so many words: Storytellers 'may wish to introduce them in other "
     "games where they are appropriate'. Does not lift a splat's own prohibitions, "
     "such as the Great Geas barring the Mountain Folk a Cult."),
    ("mf_change_method", "Merits & Flaws after character creation", "table",
     "Player's Guide p.17",
     "How a Merit or Flaw gained or lost in play is accounted for. The book offers "
     "three methods and lets the Storyteller pick, or combine them per situation."),
    ("godblooded_inheritance_rating", "God-Blooded Inheritance rating", "table",
     "Player's Guide p.61",
     "How many dots of the Inheritance Background the table's God-Blooded hold. The "
     "book leaves the rating to the Storyteller — 'assigns a consistent rating to set "
     "the series' power level' — and the rating sets each God-Blooded's bonus-point "
     "pool and Flaw capacity. Per character: each uses their own Inheritance dots."),
]

# Multiple-choice house rules: field -> {stored value: label}. Everything absent here
# is a plain boolean toggle.
_HOUSE_RULE_OPTIONS: dict[str, dict[str, str]] = {
    "mf_change_method": {
        "experience": "Experience — pay/receive twice the point value (default)",
        "backgrounds": "Like Backgrounds — changes cost and reward nothing",
        "swap": "Equal-value swap — a lost Trait is replaced, a gained one erodes another",
    },
    # Keys are the select's option values; "per-character" maps to None on the model
    # (each God-Blooded uses their own Inheritance dots). The p.61 dot names are the
    # labels — Thin blood through Divine.
    "godblooded_inheritance_rating": {
        "per-character": "Per character — each uses their own Inheritance dots",
        "1": "1 • Thin blood",
        "2": "2 •• Good blood",
        "3": "3 ••• Notable ancestry",
        "4": "4 •••• Impeccable scion",
        "5": "5 ••••• Divine",
    },
}


# `HouseRuleRow.scope` -> (heading, what the scope means). ONE copy: both shells group
# the rules by scope, and a party-wide "apply to all" control may only touch 'table'
# (models.character.HouseRules says so), so the two must not word it differently.
HOUSE_RULE_SCOPES: dict[str, tuple[str, str]] = {
    "table": ("Table-wide", "Applies to the whole game — every character at this "
                            "table should have it set the same way."),
    "character": ("This character", "A permission granted to this one character."),
}


def house_rule_setting_label(row: HouseRuleRow) -> str:
    """A house rule's current setting, short enough for a table cell.

    A boolean toggle reads On/Off. A multiple-choice rule reads its option label with
    the explanatory tail cut at the em dash — the full label belongs beside the control
    in a detail pane, not in a column."""
    if not row.options:
        return "On" if row.value else "Off"
    label = row.options.get(str(row.value), str(row.value))
    return label.split(" — ")[0].strip()


def build_house_rules(ruleset: RuleSet, character: Character) -> list[HouseRuleRow]:
    """The Storyteller-options rows for this character, with any that cannot bite
    annotated rather than hidden — an ST looking for a toggle should find it and be
    told why it is inert, not wonder where it went."""
    rules = character.house_rules or HouseRules()
    rows: list[HouseRuleRow] = []
    for fld, label, scope, citation, description in _HOUSE_RULES:
        note, inert = "", False
        if fld == "st_foreign_charms":
            if validate.foreign_charms_caste(ruleset, character) is None:
                inert = True
                # The printed caste NAME, not the id — `Character.caste` stores "dawn"
                # and the sentence read "and dawn is not one".
                caste = ruleset.castes.get(character.caste)
                note = (f"No effect: only a caste with the generalist privilege "
                        f"(Eclipse, Moonshadow) can learn foreign Charms, and "
                        f"{caste.label if caste else 'this caste'} is not one.")
            elif character.chargen_locked:
                inert = True
                note = ("No longer applies: chargen is locked, so a willing tutor "
                        "is the only remaining gate.")
        elif fld == "mortal_favored_ability":
            b = ruleset.budgets_for(character.exalt_type, character.origin,
                                    character.upbringing)
            if not b.optional_favored_ability:
                inert = True
                note = ("No effect: core p.103 offers this to HEROIC mortals only, "
                        f"and this character is {character.exalt_type}"
                        f"{'/' + character.origin if character.origin else ''}.")
            elif getattr(rules, fld):
                note = "Granting 1 Favored Ability, which must stay the highest-rated."
        elif fld == "st_celestial_manse_over_three":
            if character.exalt_type != "Sidereal":
                inert = True
                note = (f"No effect: the Celestial Manse ≤3 ceiling is a Sidereal rule "
                        f"(Sidereals p.106), and this character is {character.exalt_type}.")
            elif getattr(rules, fld):
                note = "Permission granted: this Sidereal may hold Celestial Manse above 3 dots."
        elif fld == "st_mortal_artifact_manse":
            if character.exalt_type != "Mortal":
                inert = True
                note = (f"No effect: core p.103 bars MORTALS from Artifact and Manse, "
                        f"and this character is {character.exalt_type}.")
            elif getattr(rules, fld):
                note = "Permission granted: this mortal may take Artifact and Manse Backgrounds."
        elif fld == "committed_motes_reduce_free_essence":
            # Inert for anyone whose pool is unrestricted — every Exalt, and any mortal
            # who has bought Essence Mastery. `essence_free` is the ONE test: it is
            # None exactly when the whole pool is freely drawable.
            if derive.essence_freely_accessible(ruleset, character) is None:
                inert = True
                note = ("No effect: this character draws on their whole pool freely. "
                        "The split is Essence Awareness's, and only a mortal holding "
                        "it without Essence Mastery has one.")
            elif not sum(derive.committed_attunement(ruleset, character).values()):
                inert = True
                note = ("Nothing committed yet: no attuned artifact is holding motes, "
                        "so there is nothing for this to move. It starts mattering "
                        "the moment one is attuned.")
        elif fld == "terrestrial_essence_transcendence":
            if ruleset.exalt_for(character.exalt_type).tier != "Terrestrial":
                inert = True
                note = (f"No effect: the Essence 7 ceiling is a Terrestrial rule, and "
                        f"{ruleset.exalt_for(character.exalt_type).label} are not "
                        f"Terrestrial.")
            elif character.essence_rating < 7:
                # Inert for NOW rather than never — the toggle starts biting the moment
                # Essence reaches 7, and the note says so.
                inert = True
                note = ("Nothing to lift yet: Essence is below the Terrestrial "
                        "ceiling of 7. The toggle matters once it reaches 7.")
        elif fld == "all_backgrounds_available":
            # Say what the toggle is actually worth to THIS character, in names.
            # A count is the honest measure: the ST wants to know whether flipping
            # it changes anything before they flip it.
            own = len(ruleset.backgrounds_for(character.exalt_type, character.origin))
            everything = len(ruleset.backgrounds_for(
                character.exalt_type, character.origin, all_available=True))
            if getattr(rules, fld):
                note = (f"Offering all {everything} Backgrounds, up from the "
                        f"{own} this character's own books print.")
            else:
                note = (f"Offering the {own} Backgrounds this character's own books "
                        f"print; {everything - own} more exist in other splats' books.")
        elif fld == "magic_for_everyone" and getattr(rules, fld):
            grant = validate.magic_for_everyone_grant(ruleset, character)
            inert = not grant
            note = (f"Currently granting {grant} free purchase(s)." if grant else
                    "Granting nothing yet: the allowance is Occult ÷ 2, rounded down.")
        elif fld == "godblooded_inheritance_rating":
            b = ruleset.budgets_for(character.exalt_type, character.origin,
                                    character.upbringing)
            if not b.inheritance_bonus_points:
                inert = True
                note = (f"No effect: Inheritance bonus points are a God-Blooded rule, "
                        f"and this character is {character.exalt_type}.")
            elif getattr(rules, fld) is not None:
                rating = getattr(rules, fld)
                # The ST's pick is how many Inheritance DOTS are FREE, not the rating
                # itself (human 2026-08-02) — the bonus points always follow the sheet.
                note = (f"Setting the first {rating} dot(s) of Inheritance free for "
                        f"every God-Blooded: no pool dots, no above-cap bonus points. "
                        f"The bonus points and Flaw capacity still follow each "
                        f"character's own sheet rating.")
        rows.append(HouseRuleRow(field=fld, label=label, scope=scope,
                                 citation=citation, description=description,
                                 value=_house_rule_value(rules, fld),
                                 options=dict(_HOUSE_RULE_OPTIONS.get(fld, {})),
                                 note=note, inert=inert))
    return rows


def _house_rule_value(rules: HouseRules, fld: str) -> bool | str | int | None:
    value = getattr(rules, fld)
    if fld == "godblooded_inheritance_rating":
        # The select's option keys are the strings "1".."5" plus a sentinel for
        # None, so an int rating must become its key (and None its sentinel) or
        # the select's build-time value check fails.
        value = "per-character" if value is None else str(value)
    return value


def build_table_house_rules(rules: HouseRules) -> list[HouseRuleRow]:
    """The TABLE-WIDE rows of the house rules of a campaign, with the values of
    `rules`. The rows have no note: a campaign has no one character to test a
    rule against."""
    return [HouseRuleRow(field=fld, label=label, scope=scope, citation=citation,
                         description=description, value=_house_rule_value(rules, fld),
                         options=dict(_HOUSE_RULE_OPTIONS.get(fld, {})))
            for fld, label, scope, citation, description in _HOUSE_RULES
            if scope == "table"]


def house_rule_differences(character_rules: HouseRules,
                           table_rules: HouseRules) -> list[str]:
    """One line for each TABLE-WIDE rule in which `character_rules` differ from
    `table_rules`: "<rule>: <character setting> (campaign: <table setting>)".

    The Storyteller sees these on a join request (p3-tables.md section 14, step 6b).
    Give the rules that priced the creation (`validate.chargen_house_rules`).
    """
    table_rows = {row.field: row for row in build_table_house_rules(table_rules)}
    lines = []
    for row in build_table_house_rules(character_rules):
        theirs = table_rows[row.field]
        if row.value != theirs.value:
            lines.append(f"{row.label}: {house_rule_setting_label(row)} "
                         f"(campaign: {house_rule_setting_label(theirs)})")
    return lines
