"""Merge the five VARIABLE Mountain Folk Charm templates (CH6 pp.248-274) into the
pattern files written by _extract_mountain_folk.py.

Each template is one block the book prints once with per-variant sections; each
variant is a separate Charm. The one exception is Fivefold Embodiment of (Color)
Jade, which the book describes as a single repeatable Charm ("For each purchase of
this Charm, the Jadeborn permanently gains the effects of one (Color) Jade
Transformation Charm") — so it is ONE entry with five variants and a cap on
permanent Essence.

Run _extract_mountain_folk.py first, then this, then validate_charms.py.
"""
import json

OUT = "exalted_builder/data/charms"
BOOK = "Exalted: The Mountain Folk (CH6)"
SRC_PAGE = {
    "pillar-of-compassion": 248, "pillar-of-conviction": 248, "pillar-of-temperance": 248,
    "pillar-of-valor": 248,
    "compassion-bolstering-meditation": 247, "conviction-bolstering-meditation": 247,
    "temperance-bolstering-meditation": 247, "valor-bolstering-meditation": 247,
    "green-jade-transformation": 255, "red-jade-transformation": 255,
    "black-jade-transformation": 255, "blue-jade-transformation": 255,
    "white-jade-transformation": 255,
    "fivefold-embodiment-of-green-jade": 256, "fivefold-embodiment-of-red-jade": 256,
    "fivefold-embodiment-of-black-jade": 256, "fivefold-embodiment-of-blue-jade": 256,
    "fivefold-embodiment-of-white-jade": 256,
    "mien-of-compassion": 273, "mien-of-conviction": 273,
    "mien-of-temperance": 273, "mien-of-valor": 273,
}

# ---- Pillar of (Virtue) — worker, p.248, Enchantment, 3 motes, Ess 1 ---------- #
PILLAR_INTRO = (
    "With solemnity and dignity fueled by Essence, a Worker accepts the burdens and "
    "blessings of service. Pillar of (Virtue) is actually four separate Charms, one for "
    "each Virtue. Characters who know multiple versions can activate them in conjunction "
    "on the same initiative as if they were a single Charm. Additionally, Jadeborn who "
    "master all four versions reduce the activation cost to 2 motes per Charm instead of "
    "3. Characters can only benefit from one application of each version at a time. "
    "Reactivating the Charm before the effect wears off merely resets the duration.\n\n")
PILLAR_VARIANTS = {
    "compassion": ("Compassion: The Jadeborn becomes deeply empathic, adding a bonus of "
                   "half her Compassion rating (rounded up) to all Ability dice pools to "
                   "discern the emotional state or health of others."),
    "conviction": ("Conviction: The Worker becomes unswervingly loyal to his superiors "
                   "(or personal values, if Enlightened). Whenever anyone attempts to make "
                   "the Worker directly betray the subject of his loyalty (either magically "
                   "or through mundane means), add the Jadeborn's Conviction rating to the "
                   "resistance roll. In the case of magic that offers no resistance roll, "
                   "the Worker's player may roll Conviction + Essence at a difficulty of the "
                   "opposing character's Essence rating to ignore the effect. This Charm "
                   "does not protect characters from all forms of mind-control and "
                   "influence, only such effects as would lead to a betrayal of true "
                   "loyalties."),
    "temperance": ("Temperance: The Jadeborn gains a practical intuition for task "
                   "management. She can determine the complexity and efforts required for "
                   "any job, as well as gauge the expected interference of all perceived "
                   "and predictable obstacles. Furthermore, she can determine any required "
                   "tools and calculate the projected time required for the task. From a "
                   "rules perspective, the Worker's player knows the final difficulty of "
                   "any roll after applying all modifiers, as well as all other "
                   "supplementary information outlined above. Her foresight also adds bonus "
                   "dice equal to half of her Temperance rating (rounded up) to all "
                   "Physical and Mental Attribute actions with a duration of two turns or "
                   "more, provided she spends a full turn contemplating the task in advance "
                   "as a simple action. This bonus cannot stack with itself for longer "
                   "planning efforts."),
    "valor": ("Valor: The Worker grows inured to hardship, adding half his Valor rating to "
              "all Endurance and Resistance pools to withstand harsh environmental "
              "conditions or fatigue."),
}

# ---- (Virtue)-Bolstering Meditation — warrior, p.247, Enchantment, 3 motes, Ess 1 -- #
BOLSTER_INTRO = (
    "The Warrior clears his mind of distractions with a chant or yell, hardening his "
    "spirit against suffering. (Virtue)-Bolstering Meditation is actually four separate "
    "Charms, one for each Virtue. Characters who know multiple versions can activate them "
    "in conjunction on the same initiative as if they were a single Charm. Additionally, a "
    "Jadeborn who masters all four versions reduces the activation cost to 2 motes per "
    "Charm instead of 3. Characters can only benefit from one application of each version "
    "at a time. Reactivating the Charm before the effect wears off merely resets the "
    "duration.\n\n")
BOLSTER_VARIANTS = {
    "compassion": ("Compassion: The character adds one bonus die to all actions intended "
                   "to protect or rescue an ally from immediate physical danger. Once per "
                   "scene, the character may increase this bonus to her Compassion rating "
                   "for a single turn."),
    "conviction": ("Conviction: The character subtracts his Conviction rating from all "
                   "wound penalties."),
    "temperance": ("Temperance: The character subtracts his Temperance rating from all "
                   "environmental penalties."),
    "valor": ("Valor: The character gains one additional dot of Valor, plus one for every "
              "five allies in line of sight who are also using the Valor permutation of "
              "this Charm. If this results in a Valor rating of 6+, the character's Valor "
              "remains at five dots, but she becomes truly fearless, like an automaton. "
              "She is incapable of failing Valor rolls and becomes immune to all magic and "
              "penalties based on fear. The character immediately loses additional Valor "
              "if the number of linked allies in range drops below the number required for "
              "the bonus. Valor bonuses gained with this Charm are considered part of the "
              "character's natural rating."),
}

# ---- (Color) Jade Transformation — warrior, p.255, Enchantment, 8 motes, Ess 2 ---- #
COLOR_INTRO = (
    "The Mountain Folk begin and end their lives entombed in stone. Warriors who learn "
    "this Charm may call upon that heritage, briefly transmuting their bodies into statues "
    "of living jade. Five versions of this Charm exist, one for each color of jade. All "
    "versions grant a natural lethal soak equal to the character's Stamina and permit "
    "characters to parry lethal attacks unarmed without a stunt. Each version also "
    "provides a unique benefit as listed below. Characters who know multiple versions of "
    "this Charm may activate multiple versions at the same instant as a single Charm use. "
    "The cost to use any of these Charms is (8 - the number of [Color] Jade Transformation "
    "Charms the character already has active) motes. While Jadeborn can stack multiple "
    "versions of this Charm together, they cannot benefit from more than one application "
    "of the same version at a time. Reactivating a Charm before its effect runs out resets "
    "the duration.\n\n")
COLOR_BOLSTER = {
    "green": "compassion", "red": "valor", "black": "temperance", "blue": "conviction",
}
COLOR_VARIANTS = {
    "green": ("Green: The Warrior resonates with the elemental aspect of wood, "
              "regenerating one level of bashing damage every turn and one level of lethal "
              "damage every hour."),
    "red": ("Red: The character resonates with fire, gaining total immunity to damage from "
            "non-magical fire and extreme heat. Against magical sources of flame, the "
            "character adds his Valor to his lethal soak. The flickering sparks of Essence "
            "also accelerate the character's reflexes, adding half his Valor rating to "
            "base initiative (rounded up)."),
    "black": ("Black: By resonating with water, the character gains flowing quickness and "
              "greater freedom of movement. She adds one to her Dexterity and subtracts "
              "her Temperance from the total mobility penalty of any armor and/or "
              "encumbering possessions she carries."),
    "blue": ("Blue: Through resonance with air, the Warrior becomes light and deft, "
             "subtracting his Conviction from the fatigue ratings for armor and similarly "
             "encumbering possessions. Furthermore, he doubles his usual leaping distance "
             "and halves the actual distance of any fall for the purposes of determining "
             "damage sustained on impact."),
    "white": ("White: Embodying the balance and harmony of earth, the character adds (the "
              "rating of her highest Virtue + Essence) to her natural bashing and lethal "
              "soak values. In addition, her hardened body becomes a deadly weapon, "
              "causing all her unarmed attacks to inflict lethal damage unless she "
              "deliberately pulls her blows (see Exalted, p. 238). Finally, she cannot be "
              "stunned, thrown or otherwise tackled to the ground, nor can she suffer any "
              "other form of knockback or knockdown (see Exalted, pp. 234-235). This "
              "immunity does not extend to magical effects that induce these conditions, "
              "nor does it prevent injuries associated with unsuccessful maneuvers. For "
              "example, a tackle still strikes with full force even if it cannot knock the "
              "character to the ground."),
}

# ---- Fivefold Embodiment of (Color) Jade — warrior, p.256, Special, None, Ess 3 -- #
FIVEFOLD_BODY = (
    "Where lesser Warriors may briefly change flesh into enchanted jade, more powerful "
    "veterans can permanently sculpt their bodies into armored form. For each purchase of "
    "this Charm, the Jadeborn permanently gains the effects of one (Color) Jade "
    "Transformation Charm he already knows. Characters with Fivefold Embodiment of Black "
    "Jade consider the bonus dot of Dexterity part of their natural rating for all "
    "purposes, including raising the Attribute with experience. This effect can raise "
    "Dexterity above normal maximums. Note that the temporary and permanent versions of "
    "the same effect do not stack, so characters with any version of this Charm have no "
    "further use for its prerequisite. Mountain Folk may not learn more versions of this "
    "Charm than their permanent Essence. Eclipse and Moonshadow Caste Exalted may not "
    "learn any versions of this Charm.")

# ---- Mien of (Virtue) — enlightened, p.273, Enchantment, 2 motes, Ess 2 ----------- #
MIEN_INTRO = (
    "The Conclave of the Mountain Folk is a ruthless sea of treachery and infighting held "
    "together by strictures of custom and decorum. Artisans hate and fight one another "
    "over factional and personal differences or simply for sport, but they accept that "
    "social warfare requires rules in order to preserve the very society they all wish to "
    "control. Mien of (Virtue) is one of the most ubiquitous and yet powerful weapons of "
    "Jadeborn politics, encompassing the four fundamental Charms that define acceptable "
    "social interaction. While under the effects of a mien, characters project a specific "
    "emotional archetype that helps them act the part of their assumed role.\n\nAlthough "
    "these Charms are enchantment-type, they are designed to be extremely fluid. "
    "Characters may be assumed to be able to switch back and forth in a social engagement "
    "as often as desired or as the situation demands. The timing restrictions for the "
    "enchantment type only matter if these Charms are used during combat.\n\nIn addition "
    "to their basic powers, each Charm includes a greater effect for extreme circumstances "
    "and emergencies. Characters with Essence 3+ who are wearing a mien can access this "
    "power for a reflexive cost of 10 motes or 1 temporary point of the appropriate "
    "Virtue. The greater effect lasts until voluntarily relinquished or the Jadeborn ends "
    "the mien.\n\n")
MIEN_VARIANTS = {
    "compassion": ("Compassion: The Jadeborn assumes inquisitive or amicable mode, "
                   "projecting an amount of gregariousness and curiosity appropriate to "
                   "the situation. This mode is the least common one, predominantly "
                   "employed in private negotiations and liaisons. In public, it lacks the "
                   "protective and offensive benefits of the other Charms. Add the "
                   "character's Compassion rating to all Social rolls based on friendliness "
                   "and Charm, as well as to all Investigation rolls where he politely "
                   "attempts to get information from someone else. The greater effect of "
                   "this mien makes the character irresistibly charming and attractive. He "
                   "converts the standard mien dice bonus into automatic successes for all "
                   "seduction attempts."),
    "conviction": ("Conviction: The Jadeborn assumes defensive mode, projecting stalwart "
                   "and implacable calm. He is no more or less noticeable than usual, but "
                   "his motives and emotional state remain obscured. This is the default "
                   "mood appropriate for most social encounters, particularly in unfamiliar "
                   "company. While wearing this mien, anyone targeting the character with a "
                   "Social roll of any kind adds his Conviction rating to the difficulty. "
                   "He receives no bonus penalty of any sort to his own interactions. The "
                   "greater effect of this mien grants total immunity to magic intended to "
                   "alter his thoughts, perceptions or emotions, provided that the "
                   "aggressor employing the magic has a lower permanent Essence. This "
                   "specifically does not defend against the lesser effects of any Mien of "
                   "(Virtue) Charm."),
    "temperance": ("Temperance: The Jadeborn assumes passive mode, withdrawing behind a "
                   "shroud of complete detachment. This mood is the default one of neutral "
                   "witnesses who do not wish to take part in hostilities. Any roll to "
                   "notice the character amidst a crowd has its difficulty increased by her "
                   "Temperance rating, and similarly, add her Temperance to active Stealth "
                   "rolls in such environs. Most sentient beings ignore her outright. This "
                   "bonus only applies so long as she does nothing to draw attention to "
                   "herself. She is not invisible or undetectable, just deliberately "
                   "unremarkable. As a final benefit, she adds her Temperance rating to the "
                   "difficulty of all Social rolls targeting her. Unfortunately, characters "
                   "wearing this mien cannot effectively draw attention to themselves even "
                   "if they want to, adding their Temperance to the difficulty of their own "
                   "Social rolls. This mien does not interfere with attempts to understand "
                   "a social situation or to discern the feelings of a target. Switching "
                   "from Compassion or Valor to Temperance creates a jarring emotional "
                   "disconnect that helps end or postpone discussion. Anyone currently "
                   "interacting with the character must cease doing so unless their players "
                   "make a successful Willpower roll at a difficulty of the character's "
                   "Temperance. If this roll fails, the conversation is interrupted, and "
                   "the Jadeborn can gracefully retreat from the situation. The greater "
                   "effects of this mien allow a character to retreat even further from "
                   "social interaction. The player of anyone attempting to speak with her "
                   "(after succeeding at the difficult task of noticing her in the first "
                   "place) must make a successful reflexively Willpower roll at a "
                   "difficulty of the character's Temperance each turn."),
    "valor": ("Valor: The Jadeborn dons aggressive mode, projecting arrogance and glorious "
              "anger. For all that he retains superficial signs of courtesy, his whispers "
              "carry the same stunning force as shouted epithets. Every word is a seething "
              "manifestation of epic tyranny. Obviously, this mood draws immediate "
              "attention and aids in arguments and attacks. For all its advantages, "
              "however, the mood carries a stigma as a weapon of sparing or last resort. "
              "Those who overuse its power are viewed as crass and barbaric. This mien "
              "adds the character's Valor to all Social rolls involving raw force of "
              "personality or intimidation. Also, add half the character's Valor (rounded "
              "up) to the difficulty of all Social rolls targeting him. Unfortunately, his "
              "aggressive demeanor makes him far less likeable, adding his Valor to the "
              "difficulty of all his player's own Social rolls where the Jadeborn cannot "
              "triumph through domination. Furthermore, the mien voids all Stealth "
              "attempts and makes the character preternaturally conspicuous. The players "
              "of all observers receive a reflexive Perception + Awareness roll at standard "
              "difficulty for their characters to notice him in any situation, and he "
              "cannot hope to blend in to a crowd. The greater effect of this mien converts "
              "the standard dice bonus into automatic successes for actual intimidation "
              "attempts only. Furthermore, the character's voice carries clearly over any "
              "ambient noise. Everyone in line of sight can hear him clearly as if he "
              "stood directly before them."),
}


def entry(pattern, name, type_, cost_raw, duration, min_ess, prereqs, desc, slug_override=None):
    slug = slug_override or name.lower().replace(" ", "-")
    return {
        "id": f"mountainfolk.{pattern}.{slug}",
        "name": name,
        "category": f"mountain_folk:{pattern}",
        "exalt_type": "Mountain-Folk",
        "type": type_,
        "min_essence": min_ess,
        "prerequisites": prereqs,
        "cost": {"raw": cost_raw} if cost_raw in ("None",) else {"motes": int(cost_raw.split()[0]), "raw": cost_raw},
        "duration": duration,
        "description": desc,
        "source": {"book": BOOK, "page": SRC_PAGE.get(slug, 0)},
    }


def main():
    worker = json.load(open(f"{OUT}/mountain_folk_worker.json", encoding="utf-8"))
    warrior = json.load(open(f"{OUT}/mountain_folk_warrior.json", encoding="utf-8"))
    enlightened = json.load(open(f"{OUT}/mountain_folk_enlightened.json", encoding="utf-8"))

    # Pillar of (Virtue) — worker
    for v in ("compassion", "conviction", "temperance", "valor"):
        worker.append(entry(
            "worker", f"Pillar of {v.title()}", "Enchantment", "3 motes",
            "(Essence + 1) hours", 1, [],
            PILLAR_INTRO + PILLAR_VARIANTS[v], f"pillar-of-{v}"))

    # (Virtue)-Bolstering Meditation — warrior
    for v in ("compassion", "conviction", "temperance", "valor"):
        warrior.append(entry(
            "warrior", f"{v.title()}-Bolstering Meditation", "Enchantment", "3 motes",
            "(Essence + 1) hours", 1, [],
            BOLSTER_INTRO + BOLSTER_VARIANTS[v], f"{v}-bolstering-meditation"))

    # (Color) Jade Transformation — warrior (prereq: the matching Bolstering)
    for color, body in COLOR_VARIANTS.items():
        prereq_virtue = "compassion" if color == "green" else "valor" if color == "red" \
            else "temperance" if color == "black" else "conviction" if color == "blue" else None
        prereq = ([] if color == "white"
                  else [[f"mountainfolk.warrior.{prereq_virtue}-bolstering-meditation"]])
        if color == "white":
            prereq = [[f"mountainfolk.warrior.{v}-bolstering-meditation"]
                      for v in ("compassion", "conviction", "temperance", "valor")]
        warrior.append(entry(
            "warrior", f"{color.title()} Jade Transformation", "Enchantment", "8 motes",
            "(Essence + 1) hours", 2, prereq,
            COLOR_INTRO + body, f"{color}-jade-transformation"))

    # Fivefold Embodiment of (Color) Jade — warrior, FIVE separate Charms, one per
    # color, each requiring its own (Color) Jade Transformation. The book describes
    # it as one repeatable Charm ("For each purchase ... gains the effects of one
    # (Color) Jade Transformation Charm he already knows"), but each purchase's
    # prerequisite is a DIFFERENT external Charm, which the engine's variant model
    # cannot express — so the five colors are separate entries, exactly like the
    # (Color) Jade Transformations they chain from. The "not more versions than
    # permanent Essence" cap (CH6 p.256) is a display note, not enforced.
    for color in ("green", "red", "black", "blue", "white"):
        warrior.append(entry(
            "warrior", f"Fivefold Embodiment of {color.title()} Jade", "Special", "None",
            "Permanent", 3,
            [[f"mountainfolk.warrior.{color}-jade-transformation"]],
            FIVEFOLD_BODY, f"fivefold-embodiment-of-{color}-jade"))

    # Mien of (Virtue) — enlightened (prereq: Upon Strands Lightly)
    for v in ("compassion", "conviction", "temperance", "valor"):
        enlightened.append(entry(
            "enlightened", f"Mien of {v.title()}", "Enchantment", "2 motes",
            "One scene", 2,
            [["mountainfolk.enlightened.upon-strands-lightly"]],
            MIEN_INTRO + MIEN_VARIANTS[v], f"mien-of-{v}"))

    for path, data in ((f"{OUT}/mountain_folk_worker.json", worker),
                       (f"{OUT}/mountain_folk_warrior.json", warrior),
                       (f"{OUT}/mountain_folk_enlightened.json", enlightened)):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    print(f"variable merge done: worker={len(worker)} warrior={len(warrior)} "
          f"enlightened={len(enlightened)}")


if __name__ == "__main__":
    main()
