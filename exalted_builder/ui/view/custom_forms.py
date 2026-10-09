"""
ui/view/custom_forms.py — the custom content forms: the Charm, spell, ritual,
and gear forms, their payloads, and the library rows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional

from ... import custom_content
from ...engine import advancement
from ...engine.labels import _label, _style_label
from ...models.character import Character
from ...models.rules import (DAMAGE_LABELS, AbilityName, ArmorType, ArmorWeight,
                             ArtifactType, AttributeName, Damage, GearType, RuleSet,
                             SpellCircle, WeaponType)

from ._base import CharmGraph, CharmNode
from .charm_trees import build_charm_graph, charm_on_splat_page
from .inventory import catalog_armor_summary, catalog_weapon_summary


# --------------------------------------------------------------------------- #
# Custom content (the /custom authoring page)
#
# The page is a JSON editor with dropdowns, so everything here is shape-shuffling
# between a flat form dict and a Charm/Spell payload — no game logic, and no
# writing: custom_content owns the filesystem, models own validity.
#
# It lives in ui/view/ with the other presenters so it can be tested without
# NiceGUI, which matters more here than for most panels: the form is where a typo
# turns into an unloadable library.
# --------------------------------------------------------------------------- #

# The health-cost damage types, for the form's dropdown. "" is "the source does not
# say", which is how every printed Charm with a health cost reads.
HEALTH_TYPE_OPTIONS = {"": "unspecified"} | {
    d.value: DAMAGE_LABELS[d] for d in Damage}

# The one field that is a free-text escape hatch rather than a dropdown. Seeded
# from what the shipped data actually uses, most common first, and a combobox so
# anything else can still be typed.
CHARM_DURATIONS = ["Instant", "One scene", "One turn", "One day", "One hour",
                   "Indefinite", "Permanent", "Varies", "Special", "N/A"]

# `keywords` is deliberately omitted: EVERY shipped Charm leaves it empty, so a
# control for it would be clutter.


@dataclass
class CustomRow:
    """One row in the library list on the left of the authoring page."""
    id: str
    name: str
    kind: str                  # "charm" | "spell" | "gear" | "ritual"
    detail: str                # category/circle, for the list's second line
    valid: bool                # False = in the library but rejected by the loader
    problem: str = ""          # why it was rejected, when it was
    # Which gear catalogue a `kind == "gear"` row lives in ("weapons" / "armor" /
    # "gear" / "artifacts"). Empty for Charms and spells. The four are ONE concept on
    # screen — things you own — so they share a list and this is the column that tells
    # them apart; it is also what `custom_content.delete_gear` needs.
    subkind: str = ""


# Sentinel category: the page swaps in a style-name box and writes
# martial_arts:<slug>. Not a storable value — never reaches a payload.
NEW_STYLE = "__new_style__"


def _style_categories(ruleset: RuleSet) -> list[str]:
    """Every Martial Arts style category present in the rule set, custom included."""
    return sorted({c.category for c in ruleset.charms.values()
                   if c.category.startswith("martial_arts:")})


def custom_category_options(ruleset: RuleSet) -> dict[str, str]:
    """The category dropdown: every Ability, then every known Martial Arts style,
    then the sentinel that creates a NEW style. Keys are the stored `category`
    strings, values the labels."""
    opts = {a.value: _label(a.value) for a in AbilityName}
    opts.update({cat: _style_label(cat, ruleset) for cat in _style_categories(ruleset)})
    opts["sorcery"] = "Sorcery (no gating Ability)"
    opts[NEW_STYLE] = "New Martial Arts style…"
    return opts


def charm_element_options(ruleset: RuleSet) -> dict[str, str]:
    """The elemental-tree dropdown, read from the data rather than hardcoded so a
    splat with a different elemental axis needs no change here."""
    elements = sorted({c.element for c in ruleset.charms.values() if c.element})
    return {"": "no elemental tree"} | {e: e for e in elements}


def charm_tier_options(ruleset: RuleSet) -> dict[str, str]:
    """The Exalt tiers a Charm may be opened to (`open_to_tiers`), from the splat
    definitions — "Celestial" on the cross-tier Martial Arts styles."""
    return {t: t for t in sorted({e.tier for e in ruleset.exalts.values() if e.tier})}


def extra_req_trait_options(kind: str) -> dict[str, str]:
    """The trait dropdown for one extra-requirement row: Abilities or Attributes.
    Both are OR-lists, so the control is a multi-select either way."""
    names = AttributeName if kind == "attribute" else AbilityName
    return {t.value: _label(t.value) for t in names}


def custom_charm_form(row: Optional[dict] = None) -> dict:
    """The form state for a Charm: blank for a new one, or filled from a library
    row for an edit. Flat and JSON-safe so the page can bind straight to it."""
    row = row or {}
    cost = row.get("cost") or {}
    source = row.get("source") or {}
    groups = row.get("prerequisites") or []
    # AND-of-OR collapses to two shapes the form can express: every group a single
    # id ("all of these"), or one group of several ("any one of these"). Anything
    # more complex was hand-authored and is left to the JSON pane, which is why the
    # mode is reported rather than guessed at save time.
    any_of = len(groups) == 1 and len(groups[0]) > 1
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "category": row.get("category", AbilityName.MELEE.value),
        "style_name": "",
        "exalt_type": row.get("exalt_type", "Solar"),
        "type": row.get("type", "Supplemental"),
        "min_ability": row.get("min_ability", 1),
        "min_essence": row.get("min_essence", 1),
        "motes": cost.get("motes", 0),
        "willpower": cost.get("willpower", 0),
        "health": cost.get("health", 0),
        "health_type": cost.get("health_type") or "",
        "committed": bool(cost.get("committed", False)),
        "cost_raw": cost.get("raw", ""),
        "duration": row.get("duration", "Instant"),
        "extra_reqs": ([{"kind": "ability", "traits": list(r.get("abilities") or []),
                         "rating": r.get("rating", 1)}
                        for r in (row.get("extra_min_abilities") or [])]
                       + [{"kind": "attribute", "traits": list(r.get("attributes") or []),
                           "rating": r.get("rating", 1)}
                          for r in (row.get("extra_min_attributes") or [])]),
        "prerequisites": [g[0] for g in groups] if not any_of else list(groups[0]),
        "prereq_mode": "any" if any_of else "all",
        "grants_circle": row.get("grants_circle") or "",
        # --- advanced: splat mechanics, behind the form's collapsed section ---
        "element": row.get("element", ""),
        "immaculate": bool(row.get("immaculate", False)),
        "open_to_all": bool(row.get("open_to_all", False)),
        "open_to_tiers": list(row.get("open_to_tiers") or []),
        "min_attribute": row.get("min_attribute", ""),
        "no_foreign_learning": bool(row.get("no_foreign_learning", False)),
        "installation_cost": row.get("installation_cost", 0),
        "arrayable": bool(row.get("arrayable", True)),
        "permanent_install": bool(row.get("permanent_install", False)),
        "permanent_clarity": row.get("permanent_clarity", 0),
        "breadth_reqs": [{"category": r.get("category", ""), "count": r.get("count", 1),
                          "label": r.get("label", "")}
                         for r in (row.get("prerequisite_counts") or [])],
        "description": row.get("description", ""),
        "book": source.get("book", "Homebrew"),
        "page": source.get("page") or None,
    }


def custom_charm_payload(form: dict) -> dict:
    """Form state -> a Charm payload for custom_content.save_charm. Drops empty
    optional fields rather than storing zeros and "", so a hand-read library file
    stays as short as the Charm actually is."""
    category = form.get("category") or ""
    if category == NEW_STYLE:
        category = custom_content.style_category(form.get("style_name", ""))
    ids = [i for i in (form.get("prerequisites") or []) if i]
    prerequisites = ([list(ids)] if form.get("prereq_mode") == "any" and len(ids) > 1
                     else [[i] for i in ids])
    cost = {k: int(form.get(k) or 0) for k in ("motes", "willpower", "health")}
    cost = {k: v for k, v in cost.items() if v}
    # Only meaningful alongside a health cost: naming a damage type for a Charm that
    # spends no health levels would be stored and then never read.
    if cost.get("health") and form.get("health_type"):
        cost["health_type"] = form["health_type"]
    if form.get("committed"):
        cost["committed"] = True
    if (form.get("cost_raw") or "").strip():
        cost["raw"] = form["cost_raw"].strip()

    payload = {
        "id": form.get("id") or "",
        "name": (form.get("name") or "").strip(),
        "category": category,
        "exalt_type": form.get("exalt_type") or "Solar",
        "type": form.get("type") or "Supplemental",
        "min_ability": int(form.get("min_ability") or 0),
        "min_essence": int(form.get("min_essence") or 1),
        "duration": form.get("duration") or "Instant",
        "description": (form.get("description") or "").strip(),
        "source": {"book": (form.get("book") or "Homebrew").strip(),
                   "page": form.get("page") or None},
    }
    if cost:
        payload["cost"] = cost
    if prerequisites:
        payload["prerequisites"] = prerequisites
    if form.get("grants_circle"):
        payload["grants_circle"] = form["grants_circle"]
    # Extra trait minimums. One control in the form, two typed lists in the payload:
    # the engine budgets Abilities and Attributes differently and the models keep them
    # apart. A row with no traits picked is dropped rather than stored empty.
    extra_abilities, extra_attributes = [], []
    for req in form.get("extra_reqs") or []:
        traits = [t for t in (req.get("traits") or []) if t]
        rating = int(req.get("rating") or 1)
        if not traits:
            continue
        if req.get("kind") == "attribute":
            extra_attributes.append({"attributes": traits, "rating": rating})
        else:
            extra_abilities.append({"abilities": traits, "rating": rating})
    if extra_abilities:
        payload["extra_min_abilities"] = extra_abilities
    if extra_attributes:
        payload["extra_min_attributes"] = extra_attributes

    # Breadth prerequisites ("any three Lore Charms") — a COUNT over a category,
    # which the id-based `prerequisites` cannot express.
    breadth = [{"category": r["category"], "count": int(r.get("count") or 1)}
               | ({"label": r["label"]} if (r.get("label") or "").strip() else {})
               for r in (form.get("breadth_reqs") or []) if (r.get("category") or "")]
    if breadth:
        payload["prerequisite_counts"] = breadth

    # Advanced splat mechanics. Each is written only when it differs from the model
    # default, so an ordinary homebrew Charm's JSON stays short and readable.
    for key in ("element", "min_attribute"):
        if (form.get(key) or "").strip():
            payload[key] = form[key].strip()
    for key in ("immaculate", "open_to_all", "no_foreign_learning", "permanent_install"):
        if form.get(key):
            payload[key] = True
    if form.get("open_to_tiers"):
        payload["open_to_tiers"] = list(form["open_to_tiers"])
    for key in ("installation_cost", "permanent_clarity"):
        if int(form.get(key) or 0):
            payload[key] = int(form[key])
    # `arrayable` defaults TRUE, so only the False case is worth storing.
    if not form.get("arrayable", True):
        payload["arrayable"] = False
    return payload


def custom_spell_form(row: Optional[dict] = None) -> dict:
    row = row or {}
    cost = row.get("cost") or {}
    source = row.get("source") or {}
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "circle": row.get("circle", SpellCircle.TERRESTRIAL.value),
        "motes": cost.get("motes", 0),
        "willpower": cost.get("willpower", 0),
        "cost_raw": cost.get("raw", ""),
        "description": row.get("description", ""),
        "book": source.get("book", "Homebrew"),
        "page": source.get("page") or None,
    }


def custom_spell_payload(form: dict) -> dict:
    cost = {k: int(form.get(k) or 0) for k in ("motes", "willpower")}
    cost = {k: v for k, v in cost.items() if v}
    if (form.get("cost_raw") or "").strip():
        cost["raw"] = form["cost_raw"].strip()
    payload = {
        "id": form.get("id") or "",
        "name": (form.get("name") or "").strip(),
        "circle": form.get("circle") or SpellCircle.TERRESTRIAL.value,
        "description": (form.get("description") or "").strip(),
        "source": {"book": (form.get("book") or "Homebrew").strip(),
                   "page": form.get("page") or None},
    }
    if cost:
        payload["cost"] = cost
    return payload


@dataclass(frozen=True)
class CustomKind:
    """One authorable library kind, as everything a shell needs to hold it: the form
    round-trip, the three `custom_content` calls, and the RuleSet dict the loader
    merges it into.

    ⚠ ONE table, read by both shells. The two Custom pages each carried their own
    `charm if kind == "charm" else spell` ternary at a dozen sites — a shape that
    treats "not a Charm" as a spell, so adding the third kind was a dozen chances to
    forget one silently. A missing key raises here instead.

    ⚠ GEAR is deliberately absent. Its four catalogues need a second key (which
    catalogue), its models are frozen and tagged rather than flagged, and it has no
    neutral blank row — `CUSTOM_GEAR_KINDS` and `build_custom_gear_library` are its
    equivalents, and every `if kind == "gear"` branch in a shell is that difference.
    """
    key: str
    label: str                 # plural: the sub-tab caption
    noun: str                  # singular: "New <noun>"
    form: Callable             # raw row -> form dict
    payload: Callable          # form dict -> raw row
    save: Callable             # custom_content saver
    delete: Callable           # custom_content deleter
    library: Callable          # custom_content reader: every row on disk
    pool: str                  # the RuleSet attribute it merges into


def custom_ritual_form(row: Optional[dict] = None) -> dict:
    """The authoring form for a library ritual (p.148: the chapter prints five and
    expects more). ⚠ `cost`, `roll` and `resources` are free TEXT, not numbers — a
    printed ritual has no stat block, and its cost reads "1 mote or one Willpower"."""
    row = row or {}
    source = row.get("source") or {}
    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "level": row.get("level", 1),
        "cost": row.get("cost", ""),
        "roll": row.get("roll", ""),
        "resources": row.get("resources", ""),
        "description": row.get("description", ""),
        "book": source.get("book", "Homebrew"),
        "page": source.get("page") or None,
    }


def custom_ritual_payload(form: dict) -> dict:
    return {
        "id": form.get("id") or "",
        "name": (form.get("name") or "").strip(),
        "level": int(form.get("level") or 1),
        "cost": (form.get("cost") or "").strip(),
        "roll": (form.get("roll") or "").strip(),
        "resources": (form.get("resources") or "").strip(),
        "description": (form.get("description") or "").strip(),
        "source": {"book": (form.get("book") or "Homebrew").strip(),
                   "page": form.get("page") or None},
    }


CUSTOM_KINDS: dict[str, CustomKind] = {
    "charm": CustomKind("charm", "Charms", "Charm", custom_charm_form,
                        custom_charm_payload, custom_content.save_charm,
                        custom_content.delete_charm, custom_content.library_charms,
                        "charms"),
    "spell": CustomKind("spell", "Spells", "spell", custom_spell_form,
                        custom_spell_payload, custom_content.save_spell,
                        custom_content.delete_spell, custom_content.library_spells,
                        "spells"),
    "ritual": CustomKind("ritual", "Rituals", "ritual", custom_ritual_form,
                         custom_ritual_payload, custom_content.save_ritual,
                         custom_content.delete_ritual, custom_content.library_rituals,
                         "thaum_rituals"),
}


def unlock_warning(character: Character) -> str:
    """Return the warning to show before an Unlock, or "" if none is needed.

    Ruled 2026-09-12: an Unlock after XP is allowed, with a warning.
    `lifecycle.unlock_chargen` drops the snapshot and nothing else. Thus the dots
    bought with XP count as creation dots, and the XP log still records them."""
    spent = advancement.xp_spent(character)
    if not spent:
        return ""
    return (f"This character has spent {spent} XP. Unlocking reopens character "
            "creation: the dots bought with XP then count as creation dots, and the XP "
            "log still records them as spent. Locking again takes the build as it is "
            "then as the character's creation.")


def charm_tree_title(category: str) -> str:
    """Return the name of the tree of `category`: "Melee", "War", "Snake Style"."""
    if category.startswith("martial_arts:"):
        return category.split(":", 1)[1].replace("-", " ").title() + " Style"
    return category.replace("_", " ").title()


def custom_prerequisite_options(ruleset: RuleSet, form: dict, editing: str) -> dict[str, str]:
    """Return the prerequisite choices for the Charm on `form`, as {id: label}.

    The choices are the Charms of the splat of the form, by the filter of the
    picker's splat page (`charm_on_splat_page`). The Charms of the tree of the
    form come first. The other trees of the splat follow only if
    `form["prereq_other_trees"]` is set, each label with its tree name. A book
    Charm can require a Charm of another tree, thus they stay available.

    ⚠ Each id already in `form["prerequisites"]` is in the result, filter or not.
    A NiceGUI select raises at build time when its value is not in its options.
    Virtual rows and the Charm `editing` itself are never choices.
    """
    payload = custom_charm_payload(form)
    splat, category = payload["exalt_type"], payload["category"]
    reader = Character(id="preview", exalt_type=splat)

    def label(charm) -> str:
        name = f"✎ {charm.name}" if charm.custom else charm.name
        return name if charm.category == category else (
            f"{name} — {charm_tree_title(charm.category)}")

    splat_charms = [c for c in ruleset.charms.values()
                    if not c.virtual and c.id != editing
                    and charm_on_splat_page(ruleset, reader, c, splat)]
    tree = sorted((c for c in splat_charms if c.category == category), key=lambda c: c.name)
    others = (sorted((c for c in splat_charms if c.category != category),
                     key=lambda c: (charm_tree_title(c.category), c.name))
              if form.get("prereq_other_trees") else [])
    options = {c.id: label(c) for c in tree + others}
    for charm_id in form.get("prerequisites") or []:
        if charm_id not in options:
            charm = ruleset.charms.get(charm_id)
            options[charm_id] = label(charm) if charm is not None else charm_id
    return options


# The node of a Charm that is on the form and not saved yet.
DRAFT_NODE_ID = "custom.__draft__"


def custom_charm_preview(ruleset: RuleSet, form: dict, editing: str) -> CharmGraph:
    """Return the tree that the Charm on `form` joins, with that Charm drawn in.

    The tree is the category and the splat of the form, book and homebrew both,
    from `build_charm_graph` for a blank character of that splat. The node states
    are cleared: no character is being built, thus owned and available mean
    nothing here. The form is one node with state "draft". Its id is `editing`,
    or `DRAFT_NODE_ID` for a new Charm.

    An edit replaces the saved node of `editing`: its old prerequisite edges go,
    and the edges to the Charms that require it stay. A prerequisite from another
    tree is added as an external node.
    """
    payload = custom_charm_payload(form)
    splat = payload["exalt_type"]
    graph = build_charm_graph(ruleset, Character(id="preview", exalt_type=splat),
                              payload["category"], splat)
    draft_id = editing or DRAFT_NODE_ID

    nodes = [CharmNode(n.id, n.label, "", n.min_ability, n.min_essence,
                       external=n.external, count_requirement=n.count_requirement,
                       custom=n.custom)
             for n in graph.nodes if n.id != draft_id]
    present = {n.id for n in nodes}
    for group in payload.get("prerequisites", []):
        for req in group:
            charm = ruleset.charms.get(req)
            if req not in present and charm is not None and req != draft_id:
                nodes.append(CharmNode(req, charm.name, "", charm.min_ability,
                                       charm.min_essence, external=True,
                                       custom=charm.custom))
                present.add(req)
    nodes.append(CharmNode(draft_id, payload["name"] or "(new Charm)", "draft",
                           payload["min_ability"], payload["min_essence"], custom=True))

    edges = [(src, dst) for src, dst in graph.edges if dst != draft_id]
    edges += [(req, draft_id) for group in payload.get("prerequisites", [])
              for req in group if req in present]
    has_parent = {dst for _, dst in edges}
    roots = [n.id for n in nodes if n.id not in has_parent]
    return CharmGraph(category=payload["category"], nodes=nodes, edges=edges, roots=roots)


def custom_export(kind: str, custom_dir) -> tuple[str, str] | None:
    """Give the file that exports each `kind` row of the library at `custom_dir`.

    The output is (filename, JSON text): one array of the raw rows on disk, from
    all the files of the library. The Import of the same kind tab reads it back.
    Rows that did not load are in the array too. The output is None for an empty
    library, because `parse_rows` refuses an empty array."""
    spec = CUSTOM_KINDS[kind]
    rows = spec.library(custom_dir)
    if not rows:
        return None
    return f"homebrew-{spec.label.lower()}.json", json.dumps(rows, indent=2)


def build_custom_library(ruleset: RuleSet, charm_rows: list[dict],
                         spell_rows: list[dict],
                         ritual_rows: Optional[list[dict]] = None) -> list[CustomRow]:
    """The library list: every row ON DISK, whether or not it loaded.

    Taking the rows as arguments keeps this pure — the page reads the disk. A row
    the loader rejected still appears, marked invalid with the loader's reason, so
    the only copy of a broken Charm is not invisible in the one screen that could
    fix it.
    """
    problems = {p: p for p in ruleset.custom_problems}

    def _problem_for(row_id: str) -> str:
        return next((p for p in problems if f"{row_id!r}" in p), "")

    out: list[CustomRow] = []
    for row in charm_rows:
        rid = row.get("id", "")
        loaded = ruleset.charms.get(rid)
        out.append(CustomRow(
            id=rid, name=row.get("name") or rid, kind="charm",
            detail=(_style_label(loaded.category, ruleset) if loaded and loaded.category.startswith("martial_arts:")
                    else _label(loaded.category) if loaded
                    else row.get("category", "?")),
            valid=loaded is not None and loaded.custom,
            problem=_problem_for(rid)))
    for row in spell_rows:
        rid = row.get("id", "")
        loaded = ruleset.spells.get(rid)
        out.append(CustomRow(
            id=rid, name=row.get("name") or rid, kind="spell",
            detail=f"{loaded.circle.value} Circle" if loaded else row.get("circle", "?"),
            valid=loaded is not None and loaded.custom,
            problem=_problem_for(rid)))
    for row in ritual_rows or []:
        rid = row.get("id", "")
        loaded = ruleset.thaum_rituals.get(rid)
        out.append(CustomRow(
            id=rid, name=row.get("name") or rid, kind="ritual",
            detail=f"level {loaded.level if loaded else row.get('level', '?')}",
            valid=loaded is not None and loaded.custom,
            problem=_problem_for(rid)))
    return out


# The four gear catalogues the custom library can hold, in the order the list shows
# them, mapped to the RuleSet attribute each merges into and the label for the Kind
# column. Keys are `custom_content.GEAR_FILES`' keys — `delete_gear` takes one.
CUSTOM_GEAR_KINDS: dict[str, tuple[str, str]] = {
    "weapons": ("weapon_catalog", "Weapon"),
    "armor": ("armor_catalog", "Armour"),
    "gear": ("gear_catalog", "Goods"),
    "artifacts": ("artifact_catalog", "Artifact"),
}


def custom_gear_summary(kind: str, entry) -> str:
    """One line of stats for a library gear row, reusing the shop's own formatters so
    a homebrew weapon reads exactly as it does in Buy."""
    if kind == "weapons":
        return catalog_weapon_summary(entry)
    if kind == "armor":
        return catalog_armor_summary(entry)
    if kind == "artifacts":
        return f"{'•' * entry.rating} {entry.description}".strip()
    return entry.category or entry.kind or ""


@dataclass(frozen=True)
class GearField:
    """One control on the gear authoring form. A spec rather than a widget so both
    shells build the same form from one description."""
    key: str
    label: str
    kind: str = "int"           # "int" | "signed" | "text" | "longtext" | "choice"
    options: tuple[tuple[str, str], ...] = ()     # (stored value, label) for "choice"
    tip: str = ""


# The four gear models, as forms. ⚠ Derived from `models/rules.py` FIELD BY FIELD, not
# from the Gear tab's owned-row editors: a character's `Weapon` is not a `WeaponType`
# (`gear_actions.library_payload` is the codec between them), and the two field sets
# differ at both ends.
#
# ⚠ Three fields are deliberately ABSENT from every form:
#   * `id` — it follows the name on first save and freezes after, like a custom Charm's.
#   * `tags` — the loader stamps `custom` itself, and the one meaningful tag is
#     `["shield"]` on an ArmorType. Rare enough for the JSON pane.
#   * `requires_merit` (ArtifactType) — decision 0011: **no module outside
#     engine/merits.py may name a Merit id**, and a dropdown of Merits would put one in
#     UI code. A homebrew plot device sets it through the JSON pane.
#
# ⚠ `source` is NOT uniform and is not made uniform here: GearType carries a `Source`
# model, ArtifactType a bare string, and WeaponType/ArmorType have no source field at
# all. Inventing one for the two that lack it would write a key the model rejects.
CUSTOM_GEAR_FIELDS: dict[str, tuple[GearField, ...]] = {
    "weapons": (
        GearField("speed", "Speed", "signed"),
        GearField("accuracy", "Accuracy", "signed"),
        GearField("damage", "Damage", "signed"),
        GearField("damage_type", "Damage type", "choice",
                  (("L", "Lethal"), ("B", "Bashing"))),
        GearField("defense", "Defence", "signed"),
        GearField("rate", "Rate"),
        GearField("range", "Range", tip="yards; 0 is melee only"),
        GearField("min_strength", "Min Strength"),
        GearField("min_dexterity", "Min Dexterity"),
        GearField("min_martial_arts", "Min Martial Arts"),
        GearField("max_strength", "Max Strength",
                  tip="bows: the Strength the bow is built for"),
        GearField("artifact_rating", "Artifact rating",
                  tip="0 is mundane; dots of the Artifact Background to start with it"),
        GearField("attunement", "Attunement", tip="motes committed to attune"),
        GearField("resources_cost", "Resources", tip="dots of Resources to buy one"),
        GearField("notes", "Notes", "text"),
    ),
    "armor": (
        # ⚠ `weight` is REQUIRED by ArmorType and the Gear tab's "Save to my library"
        # cannot know it — a character's armour row carries none, so that path defaults
        # to Light and apologises in its notify. Asking here is the point of the form.
        GearField("weight", "Weight", "choice",
                  tuple((w.value, w.value) for w in ArmorWeight)),
        GearField("soak_lethal", "Soak (lethal)"),
        GearField("soak_bashing", "Soak (bashing)"),
        GearField("mobility_penalty", "Mobility", "signed",
                  tip="stored NEGATIVE — a penalty is e.g. -2"),
        GearField("fatigue", "Fatigue"),
        GearField("difficulty_melee", "Difficulty (melee)", "signed",
                  tip="shields: +N to hit the bearer hand-to-hand"),
        GearField("difficulty_ranged", "Difficulty (ranged)", "signed",
                  tip="shields: +N to hit the bearer with missile fire"),
        GearField("artifact_rating", "Artifact rating"),
        GearField("attunement", "Attunement"),
        GearField("resources_cost", "Resources"),
        GearField("notes", "Notes", "text"),
    ),
    "gear": (
        # ⚠ `kind` decides whether the thing is OWNABLE. `view.shop_rows` skips
        # everything that is not "goods", so a row saved as a service never appears in
        # Buy — invisible unless the form says so.
        GearField("kind", "Kind", "choice",
                  (("goods", "Goods — ownable, appears in Buy"),
                   ("service", "Service — a price you consult, never owned"))),
        GearField("category", "Category", "text", tip="the printed table heading"),
        GearField("resources_cost", "Resources"),
        GearField("cash", "Cash price", "text",
                  tip="printed jade/silver equivalent, verbatim — never arithmetic "
                      "(M&C p.122 makes the conversion the Storyteller's call)"),
        GearField("notes", "Notes", "text"),
    ),
    "artifacts": (
        GearField("rating", "Artifact rating",
                  tip="1-5; the dots of Artifact Background that buy it (core p.342)"),
        GearField("rating_notes", "Rating notes", "text",
                  tip='e.g. "• or •••" where the book prints a range'),
        GearField("background", "Paid for by", "choice",
                  (("artifact", "the Artifact Background"),
                   ("manse", "the Manse Background — a Hearthstone"))),
        GearField("resources_cost", "Resources",
                  tip="what CASH buys one in play (M&C p.125) — a different scale from "
                      "the rating, and 0 means the book gives no price"),
        GearField("source", "Source", "text", tip='e.g. "MF p.279"'),
        GearField("description", "Description", "longtext"),
    ),
}

# The model behind each form, so defaults are READ from it rather than restated.
_GEAR_MODELS = {"weapons": WeaponType, "armor": ArmorType,
                "gear": GearType, "artifacts": ArtifactType}

# Fields with no model default, which a payload must always carry — and what a BLANK
# form starts them at, since there is nothing on the model to read.
#
# ⚠ An artifact's rating starts at 1, not 0: `ArtifactType.rating` is `ge=1`, so a zero
# makes the row unloadable. The others are honest zeroes.
_GEAR_REQUIRED: dict[str, dict[str, object]] = {
    "armor": {"weight": ArmorWeight.LIGHT.value, "soak_lethal": 0, "soak_bashing": 0},
    "artifacts": {"rating": 1},
}


def custom_gear_form(kind: str, row: Optional[dict] = None) -> dict:
    """The form state for one library gear row: blank for a new one, or filled from a
    library row for an edit. Flat and JSON-safe, the `custom_charm_form` shape.

    ⚠ Defaults come from the MODEL, not from a hand-written copy — `WeaponType` and
    friends are frozen and shared with the book data, so a form that invented its own
    defaults would drift from what the loader accepts."""
    row = row or {}
    model = _GEAR_MODELS[kind]
    form = {"name": row.get("name", "")}
    blanks = _GEAR_REQUIRED.get(kind, {})
    for spec in CUSTOM_GEAR_FIELDS[kind]:
        field_info = model.model_fields[spec.key]
        fallback = (blanks[spec.key] if field_info.is_required()
                    else field_info.default)
        value = row.get(spec.key, fallback)
        form[spec.key] = value.value if hasattr(value, "value") else value
    if kind == "gear":
        source = row.get("source") or {}
        form["book"] = source.get("book", "Homebrew")
        form["page"] = source.get("page") or None
    return form


def custom_gear_payload(kind: str, form: dict) -> dict:
    """Form state -> a library row for `custom_content.save_gear_row`.

    Drops empty optional fields so a hand-read library file stays as short as the item
    actually is — but ⚠ never drops one the model REQUIRES, which is why
    `_GEAR_REQUIRED` exists: `ArmorType.soak_lethal` has no default, so omitting a zero
    soak makes the row unloadable rather than making it zero."""
    payload: dict = {"id": form.get("id") or "",
                     "name": (form.get("name") or "").strip()}
    required = _GEAR_REQUIRED.get(kind, {})
    for spec in CUSTOM_GEAR_FIELDS[kind]:
        value = form.get(spec.key)
        if isinstance(value, str):
            value = value.strip()
        if value or spec.key in required:
            payload[spec.key] = value
    if kind == "gear":
        payload["source"] = {"book": (form.get("book") or "Homebrew").strip(),
                             "page": form.get("page") or None}
    return payload


def build_custom_gear_library(ruleset: RuleSet,
                              rows_by_kind: dict[str, list[dict]]) -> list[CustomRow]:
    """The gear half of the library list: every row ON DISK, whether or not it loaded.

    Takes the rows as an argument for the same reason `build_custom_library` does —
    the page reads the disk, this stays pure.

    ⚠ A loaded gear row carries no `custom` FIELD. `WeaponType` and friends are frozen
    and shared with the book data, so `rules_db._merge_custom_gear` tags them
    (`"custom" in entry.tags`) rather than flagging them, and that tag is what says the
    row is yours. Reading a `.custom` attribute here would raise.
    """
    problems = list(ruleset.custom_problems)

    def _problem_for(row_id: str) -> str:
        return next((p for p in problems if f"{row_id!r}" in p), "")

    out: list[CustomRow] = []
    for kind, (attribute, label) in CUSTOM_GEAR_KINDS.items():
        catalog = getattr(ruleset, attribute)
        for row in rows_by_kind.get(kind) or []:
            row_id = row.get("id", "")
            loaded = catalog.get(row_id)
            out.append(CustomRow(
                id=row_id, name=row.get("name") or row_id, kind="gear",
                subkind=kind,
                detail=(custom_gear_summary(kind, loaded) if loaded
                        else row.get("name", "")),
                valid=loaded is not None and "custom" in getattr(loaded, "tags", ()),
                problem=_problem_for(row_id)))
    return out
