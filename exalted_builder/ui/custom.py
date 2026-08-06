"""
ui/custom.py — the "Custom" page: author your own Charms, styles and spells.

Three ways in, all landing in the same validate-then-write path so they cannot
disagree about what is legal:

  * the FORM — dropdowns for everything the models constrain (category, splat,
    Charm type, circle), numbers for the minimums and costs, free text only where
    the book itself is free-form;
  * the JSON PANE — the same row as text. It fills as the form is edited (copy it
    out to share a Charm), and a pasted row fills the form back in;
  * UPLOAD — a `.json` file of one row or many, for importing a whole homebrew set.

A Martial Arts style is not a separate thing to create: picking "New Martial Arts
style…" in the category dropdown writes `martial_arts:<slug>`, and the picker
derives its style groups from that string. So there is no Styles tab — the style
exists the moment a Charm uses it.

No game logic lives here. The form/payload shuffling is `view.custom_*`, validity
is the pydantic models, the filesystem is `custom_content`, and the merge back into
the live rule set is `rules_db.reload_custom_layer` — which updates the RuleSet
every page already holds, so an authored Charm shows up in the picker without a
restart.

Run:
    python -m exalted_builder.ui.custom
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nicegui import ui

from .. import custom_content, rules_db
from ..custom_content import CustomContentError
from ..models.rules import AbilityName, CharmType, RuleSet, SpellCircle
from . import theme
from . import view as viewmod

_PKG = Path(__file__).resolve().parents[1]
_DATA_DIR = _PKG / "data"

# How many characters could be affected by a delete is unknowable from here (saves
# live wherever the user put them), so the confirm dialog says what actually happens
# instead of guessing a number.
_DELETE_WARNING = (
    "Any character that already owns it keeps the id: the Charm shows on the sheet as "
    "a missing row (⚠) with an error, and comes back if you re-create it with the same "
    "name. Nothing else is changed.")


def build_custom(ruleset: RuleSet, *, custom_dir: Path | None = None,
                 with_header: bool = True) -> None:
    """Render the authoring page against `ruleset`, which is updated IN PLACE as
    rows are saved (see rules_db.reload_custom_layer)."""
    pal = theme.palette(None)
    root = custom_dir if custom_dir is not None else custom_content.custom_data_dir()

    state: dict = {
        "kind": "charm",
        "form": viewmod.custom_charm_form(),
        "editing": "",           # id being replaced, "" for a new row
    }

    # The book's own ids. Passed to the savers so homebrew can never shadow printed
    # content; recomputed on each save because the custom half of ruleset.charms
    # changes underneath us.
    def _reserved() -> set[str]:
        pool = ruleset.charms if state["kind"] == "charm" else ruleset.spells
        return {i for i, row in pool.items() if not row.custom}

    def _form() -> dict:
        return state["form"]

    def _set_form(form: dict, editing: str = "") -> None:
        state["form"], state["editing"] = form, editing
        editor.refresh()
        json_pane.refresh()

    def _new() -> None:
        _set_form(viewmod.custom_charm_form() if state["kind"] == "charm"
                  else viewmod.custom_spell_form())

    def _switch_kind(kind: str) -> None:
        state["kind"] = kind
        _new()

    def _reload() -> None:
        """Re-merge the library into the live rule set, then repaint everything that
        reads it. Problems are shown rather than raised — the same non-fatal contract
        the loader has."""
        problems = rules_db.reload_custom_layer(ruleset, root)
        library.refresh()
        if problems:
            ui.notify(f"{len(problems)} problem(s) in the library — see the list",
                      type="warning")

    # ---- save / delete ---------------------------------------------------- #

    def _save() -> None:
        form = _form()
        # The id follows the name for a NEW row, so a rename before the first save
        # does not leave a stale id behind. Once saved it is frozen: characters
        # reference it, so an edit must never change it.
        if not state["editing"]:
            form["id"] = custom_content.make_id(form.get("name", ""))
        try:
            if state["kind"] == "charm":
                saved = custom_content.save_charm(
                    viewmod.custom_charm_payload(form),
                    custom_dir=root, reserved_ids=_reserved())
            else:
                saved = custom_content.save_spell(
                    viewmod.custom_spell_payload(form),
                    custom_dir=root, reserved_ids=_reserved())
        except CustomContentError as exc:
            ui.notify(str(exc), type="negative")
            return
        _reload()
        # Saving does not clear the form: the row is now on disk and in the rule set,
        # and staying on it is what makes "save, look at the tree, adjust" work.
        _set_form(_form(), editing=saved.id)
        if saved.id not in (ruleset.charms if state["kind"] == "charm" else ruleset.spells):
            ui.notify(f"Saved {saved.name}, but it did not load — see the list",
                      type="warning")
        else:
            ui.notify(f"Saved {saved.name}", type="positive")

    def _edit(row: viewmod.CustomRow) -> None:
        state["kind"] = row.kind
        rows = (custom_content.library_charms(root) if row.kind == "charm"
                else custom_content.library_spells(root))
        raw = next((r for r in rows if r.get("id") == row.id), {})
        _set_form(viewmod.custom_charm_form(raw) if row.kind == "charm"
                  else viewmod.custom_spell_form(raw), editing=row.id)

    def _delete(row: viewmod.CustomRow) -> None:
        with ui.dialog() as dialog, ui.card().classes(f"w-[30rem] p-4 gap-2 {pal.card_solid}"):
            ui.label(f"Delete {row.name}?").classes("text-base font-bold")
            ui.label(_DELETE_WARNING).classes("text-xs")
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Cancel", on_click=dialog.close).props("flat")

                def confirm() -> None:
                    dialog.close()
                    gone = (custom_content.delete_charm(row.id, custom_dir=root)
                            if row.kind == "charm"
                            else custom_content.delete_spell(row.id, custom_dir=root))
                    _reload()
                    if state["editing"] == row.id:
                        _new()
                    ui.notify(f"Deleted {row.name}" if gone else f"{row.name} was not there",
                              type="info")

                ui.button("Delete", on_click=confirm, color="negative")
        dialog.open()

    # ---- JSON in / out ---------------------------------------------------- #

    def _apply_rows(rows: list[dict], *, label: str) -> None:
        """Save every row in `rows`. One row loads into the form as well, so a paste
        of a single Charm is an edit rather than a blind write; several are a bulk
        import and are reported as a count."""
        saved, failed = 0, []
        for row in rows:
            try:
                if state["kind"] == "charm":
                    custom_content.save_charm(row, custom_dir=root, reserved_ids=_reserved())
                else:
                    custom_content.save_spell(row, custom_dir=root, reserved_ids=_reserved())
                saved += 1
            except CustomContentError as exc:
                failed.append(f"{row.get('name') or row.get('id') or '?'}: {exc}")
        _reload()
        if len(rows) == 1 and saved:
            _edit_by_id(rows[0])
        for msg in failed[:3]:
            ui.notify(msg, type="negative")
        if saved:
            ui.notify(f"{label}: imported {saved} row(s)", type="positive")

    def _edit_by_id(row: dict) -> None:
        rid = custom_content.normalize_id(str(row.get("id", "")))
        _set_form(viewmod.custom_charm_form(row) if state["kind"] == "charm"
                  else viewmod.custom_spell_form(row), editing=rid)

    def _paste(text: str) -> None:
        try:
            rows = custom_content.parse_rows(text)
        except CustomContentError as exc:
            ui.notify(str(exc), type="negative")
            return
        if len(rows) == 1:
            # A single pasted row fills the form WITHOUT saving: the user gets to see
            # and adjust it first, which is the whole reason the pane is two-way.
            _edit_by_id(rows[0])
            ui.notify("Loaded into the form — press Save to keep it", type="info")
        else:
            _apply_rows(rows, label="Paste")

    async def _upload(e) -> None:
        try:
            text = (await e.file.text())
        except Exception as exc:                    # noqa: BLE001 - surface read errors
            ui.notify(f"Could not read that file: {exc}", type="negative")
            return
        try:
            rows = custom_content.parse_rows(text)
        except CustomContentError as exc:
            ui.notify(str(exc), type="negative")
            return
        _apply_rows(rows, label=e.name)

    # ---- rendering -------------------------------------------------------- #

    if with_header:
        with ui.header().classes("items-center justify-between px-4").style(
                f"background:{pal.accent}"):
            ui.label("Exalted 1e — Custom content").classes("text-lg font-bold text-white")
        ui.query("body").style(f"background:{pal.bg};color:{pal.ink}")

    with ui.row().classes("w-full items-center justify-between"):
        ui.label("Custom content").classes("text-lg font-bold").style(f"color:{pal.accent}")
        with ui.row().classes("items-center gap-2"):
            ui.label(f"Library: {root}").classes("text-xs text-gray-500")
            ui.button("New", icon="add", on_click=_new).props(f"color={pal.button}")

    with ui.tabs(value="charm").classes("w-full") as kind_tabs:
        ui.tab("charm", label="Charms", icon="auto_awesome")
        ui.tab("spell", label="Spells", icon="menu_book")
    kind_tabs.on_value_change(lambda e: _switch_kind(e.value))

    with ui.row().classes("w-full gap-2 items-start no-wrap"):

        # ---- left: the library ------------------------------------------- #
        @ui.refreshable
        def library() -> None:
            rows = [r for r in viewmod.build_custom_library(
                ruleset, custom_content.library_charms(root),
                custom_content.library_spells(root)) if r.kind == state["kind"]]
            with ui.card().classes(f"w-96 p-3 gap-1 {pal.card}"):
                ui.label(f"YOUR {state['kind'].upper()}S ({len(rows)})").classes(
                    "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
                if not rows:
                    ui.label("Nothing yet — fill in the form and press Save.").classes(
                        "text-xs text-gray-500")
                for row in rows:
                    with ui.row().classes("w-full items-center gap-1 no-wrap"):
                        ui.label("⚠" if not row.valid else "✎").classes(
                            "text-xs " + ("text-red-600" if not row.valid else "text-violet-700")
                        ).tooltip(row.problem or "Custom content")
                        with ui.column().classes("flex-1 gap-0 min-w-0"):
                            ui.label(row.name).classes("text-sm truncate")
                            ui.label(row.detail).classes("text-xs text-gray-500 truncate")
                        ui.button(icon="edit", on_click=lambda _=None, r=row: _edit(r)).props(
                            "flat dense size=sm")
                        ui.button(icon="delete", on_click=lambda _=None, r=row: _delete(r)).props(
                            "flat dense size=sm color=negative")
                if ruleset.custom_problems:
                    ui.separator()
                    ui.label("LIBRARY PROBLEMS").classes(
                        "text-xs font-bold tracking-widest text-red-700")
                    for p in ruleset.custom_problems:
                        ui.label(f"• {p}").classes("text-xs text-red-600")

        library()

        # ---- middle: the form -------------------------------------------- #
        @ui.refreshable
        def editor() -> None:
            form = _form()

            def bind(key: str):
                def _set(e) -> None:
                    form[key] = e.value
                    json_pane.refresh()
                return _set

            with ui.card().classes(f"flex-1 p-3 gap-2 {pal.card}"):
                ui.label("NEW " + state["kind"].upper() if not state["editing"]
                         else f"EDITING {state['editing']}").classes(
                    "text-xs font-bold tracking-widest").style(f"color:{pal.accent}")
                ui.input("Name", value=form["name"], on_change=bind("name")).classes("w-full")

                if state["kind"] == "charm":
                    _charm_fields(form, bind, ruleset, pal, editor.refresh)
                else:
                    _spell_fields(form, bind)

                ui.textarea("Description", value=form["description"],
                            on_change=bind("description")).classes("w-full").props("rows=4")
                with ui.row().classes("w-full items-center gap-2 no-wrap"):
                    ui.input("Source book", value=form["book"],
                             on_change=bind("book")).classes("flex-1")
                    ui.number("Page", value=form["page"], format="%d",
                              on_change=bind("page")).classes("w-24")
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Save", icon="save", on_click=_save).props(f"color={pal.button}")

        editor()

        # ---- right: JSON in/out ------------------------------------------ #
        @ui.refreshable
        def json_pane() -> None:
            payload = (viewmod.custom_charm_payload(_form()) if state["kind"] == "charm"
                       else viewmod.custom_spell_payload(_form()))
            if not state["editing"]:
                payload["id"] = custom_content.make_id(_form().get("name", "")) or "(from the name)"
            with ui.card().classes(f"w-[26rem] p-3 gap-2 {pal.card}"):
                ui.label("JSON").classes("text-xs font-bold tracking-widest").style(
                    f"color:{pal.accent}")
                ui.label("The same row as text — copy it to share, or paste one in "
                         "and press Load to fill the form.").classes("text-xs text-gray-500")
                ui.code(json.dumps(payload, indent=2), language="json").classes("w-full text-xs")
                paste = ui.textarea("Paste a row, or an array of them").classes(
                    "w-full").props("rows=6")
                with ui.row().classes("w-full justify-between items-center gap-2"):
                    ui.upload(label="Import .json", on_upload=_upload, auto_upload=True) \
                        .props("accept=.json flat dense").classes("max-w-[12rem]")
                    ui.button("Load", icon="input",
                              on_click=lambda: _paste(paste.value or "")).props("flat dense")

        json_pane()


def _extra_requirements(form: dict, refresh) -> None:
    """The repeatable "and also needs…" editor: any number of AND rows, each an OR
    over Abilities or over Attributes.

    Separate from the primary `min_ability` above it, which is the gate derived from
    the Charm's category and is what pricing and the Caste/Favoured discount key off.
    These rows are pure requirements — adding one never makes a Charm cheaper.

    Re-rendered rather than bound, because changing a row's axis changes which trait
    options its dropdown may offer.
    """
    rows = form.setdefault("extra_reqs", [])

    def add() -> None:
        rows.append({"kind": "ability", "traits": [], "rating": 1})
        refresh()

    def remove(i: int) -> None:
        del rows[i]
        refresh()

    def set_kind(i: int, kind: str) -> None:
        # The traits go with the axis: an Ability value is not a legal Attribute, and
        # leaving them would render a select whose value is not in its options (a 500).
        rows[i]["kind"] = kind
        rows[i]["traits"] = []
        refresh()

    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("w-full items-center gap-2"):
            ui.label("Also requires").classes("text-xs font-semibold")
            ui.button("Add", icon="add", on_click=add).props("flat dense size=sm") \
                .tooltip("An extra Ability or Attribute minimum, on top of the one above")
        if not rows:
            ui.label("No extra trait minimums — the Charm gates only on the Ability "
                     "above.").classes("text-xs text-gray-500")
        for i, req in enumerate(rows):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select({"ability": "Ability", "attribute": "Attribute"},
                          value=req["kind"],
                          on_change=lambda e, i=i: set_kind(i, e.value)).classes(
                    "w-32").props("dense")
                ui.select(viewmod.extra_req_trait_options(req["kind"]),
                          value=req["traits"], multiple=True, with_input=True,
                          on_change=lambda e, i=i: rows[i].update(traits=e.value)) \
                    .classes("flex-1").props("dense use-chips") \
                    .tooltip("Several traits in one row means ANY ONE of them satisfies "
                             "it; add another row for a second, separate requirement.")
                ui.number(value=req["rating"], min=1, max=10, format="%d",
                          on_change=lambda e, i=i: rows[i].update(
                              rating=int(e.value or 1))).classes("w-20") \
                    .props("dense").tooltip("Minimum rating")
                ui.button(icon="remove", on_click=lambda _=None, i=i: remove(i)).props(
                    "flat dense size=sm color=negative")


def _breadth_requirements(form: dict, refresh) -> None:
    """"Any three Lore Charms" — a COUNT over a category, which the id-based
    prerequisite list cannot express (three groups each listing all eleven Lore Charms
    would be satisfied three times over by one owned Charm)."""
    rows = form.setdefault("breadth_reqs", [])

    def add() -> None:
        rows.append({"category": "lore", "count": 3, "label": ""})
        refresh()

    def remove(i: int) -> None:
        del rows[i]
        refresh()

    with ui.column().classes("w-full gap-1"):
        with ui.row().classes("w-full items-center gap-2"):
            ui.label("Also requires N Charms of a kind").classes("text-xs font-semibold")
            ui.button("Add", icon="add", on_click=add).props("flat dense size=sm") \
                .tooltip('A breadth prerequisite, e.g. "any three Lore Charms"')
        for i, req in enumerate(rows):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.number(value=req["count"], min=1, max=20, format="%d",
                          on_change=lambda e, i=i: rows[i].update(
                              count=int(e.value or 1))).classes("w-20").props("dense")
                ui.select({a.value: a.value for a in AbilityName}, value=req["category"],
                          with_input=True,
                          on_change=lambda e, i=i: rows[i].update(category=e.value)) \
                    .classes("flex-1").props("dense").tooltip(
                        "Counted by the Charm's category — a Craft Charm printed in "
                        "another book still counts toward 'any three Craft Charms'")
                ui.button(icon="remove", on_click=lambda _=None, i=i: remove(i)).props(
                    "flat dense size=sm color=negative")


def _advanced_fields(form: dict, bind, ruleset: RuleSet) -> None:
    """Splat mechanics: the fields a homebrew Charm rarely needs, and that mean nothing
    outside the splat that invented them. Collapsed by default so the common case — a
    Charm with a category, a cost and a couple of minimums — stays a short form.

    Everything here is written only when it differs from the model default, so an
    ordinary Charm's JSON does not grow a dozen zeroes.
    """
    with ui.expansion("Advanced (splat mechanics)", icon="tune").classes("w-full"):
        with ui.column().classes("w-full gap-2 p-1"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(viewmod.charm_element_options(ruleset), value=form["element"],
                          label="Elemental tree", on_change=bind("element")).classes(
                    "flex-1").props("dense").tooltip(
                        "Dragon-Blooded organise Charms by element; it groups the picker")
                ui.select(viewmod.extra_req_trait_options("attribute") | {"": "—"},
                          value=form["min_attribute"], label="Gate on an Attribute",
                          on_change=bind("min_attribute")).classes("flex-1").props("dense") \
                    .tooltip("RETARGETS the 'Min ability' above at an Attribute instead "
                             "(the Attribute-keyed splats, e.g. Lunar). Unlike the extra "
                             "requirements, this one drives pricing and the "
                             "Caste/Favoured discount.")
            with ui.row().classes("w-full items-center gap-3 no-wrap flex-wrap"):
                ui.checkbox("Any splat may learn it", value=form["open_to_all"],
                            on_change=bind("open_to_all")).tooltip(
                    "The Terrestrial Martial Arts case — learnable by anyone with a tutor")
                ui.select(viewmod.charm_tier_options(ruleset), value=form["open_to_tiers"],
                          label="Open to tiers", multiple=True,
                          on_change=bind("open_to_tiers")).classes("w-56").props(
                    "dense use-chips").tooltip(
                        "Exalt tiers that may learn it besides its own splat")
            with ui.row().classes("w-full items-center gap-3 no-wrap flex-wrap"):
                ui.checkbox("Immaculate Order Charm", value=form["immaculate"],
                            on_change=bind("immaculate")).tooltip(
                    "Dragon-Blooded Fivefold Dragon Method — also priced on the "
                    "Immaculate row")
                ui.checkbox("Barred from foreign learning", value=form["no_foreign_learning"],
                            on_change=bind("no_foreign_learning")).tooltip(
                    "Unreachable even by the Eclipse/Moonshadow generalist rule (p.127)")
            ui.label("Alchemical only").classes("text-xs font-semibold text-gray-500")
            with ui.row().classes("w-full items-center gap-3 no-wrap flex-wrap"):
                ui.number("Install cost", value=form["installation_cost"], min=0,
                          format="%d", on_change=bind("installation_cost")).classes("w-28") \
                    .tooltip("Personal Essence committed while installed in a Charm Slot")
                ui.number("Clarity", value=form["permanent_clarity"], min=0, format="%d",
                          on_change=bind("permanent_clarity")).classes("w-24") \
                    .tooltip("Dots of permanent Clarity installing it grants")
                ui.checkbox("Usable in Arrays", value=form["arrayable"],
                            on_change=bind("arrayable"))
                ui.checkbox("Can never be uninstalled", value=form["permanent_install"],
                            on_change=bind("permanent_install"))
            ui.label("Repeatable Charms (Ox-Body-style variants) are not editable here — "
                     "use the JSON pane.").classes("text-xs text-gray-500")


def _charm_fields(form: dict, bind, ruleset: RuleSet, pal: theme.Palette,
                  refresh) -> None:
    """The Charm-specific half of the form. Dropdowns wherever the model constrains
    the value, so an invalid category or Charm type is not typeable."""
    categories = viewmod.custom_category_options(ruleset)
    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        ui.select(categories, value=form["category"], label="Category",
                  on_change=bind("category")).classes("flex-1").props("dense")
        ui.select({e.value: e.value for e in CharmType}, value=form["type"],
                  label="Type", on_change=bind("type")).classes("w-40").props("dense")
    if form["category"] == viewmod.NEW_STYLE:
        ui.input("New style name", value=form["style_name"],
                 on_change=bind("style_name")).classes("w-full").props("dense") \
            .tooltip("Creates martial_arts:<name> — the picker groups it as its own style")

    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        ui.select({e: e for e in sorted(ruleset.exalts)}, value=form["exalt_type"],
                  label="Splat", on_change=bind("exalt_type")).classes("flex-1").props("dense")
        ui.number("Min ability", value=form["min_ability"], min=0, max=5, format="%d",
                  on_change=bind("min_ability")).classes("w-28")
        ui.number("Min essence", value=form["min_essence"], min=1, max=10, format="%d",
                  on_change=bind("min_essence")).classes("w-28")

    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        ui.number("Motes", value=form["motes"], min=0, format="%d",
                  on_change=bind("motes")).classes("w-24")
        ui.number("WP", value=form["willpower"], min=0, format="%d",
                  on_change=bind("willpower")).classes("w-20")
        ui.number("Health", value=form["health"], min=0, format="%d",
                  on_change=bind("health")).classes("w-24")
        ui.select(viewmod.HEALTH_TYPE_OPTIONS, value=form["health_type"],
                  label="HL type", on_change=bind("health_type")).classes("w-36") \
            .props("dense").tooltip(
                "Which kind of health level the Charm spends. Every printed Charm "
                "just says 'health level', so 'unspecified' is the norm.")
        ui.checkbox("Committed", value=form["committed"], on_change=bind("committed"))
        ui.select(viewmod.CHARM_DURATIONS, value=form["duration"], label="Duration",
                  new_value_mode="add-unique", on_change=bind("duration")).classes(
            "flex-1").props("dense")
    ui.input("Cost override (variable costs, e.g. '1m per die')", value=form["cost_raw"],
             on_change=bind("cost_raw")).classes("w-full").props("dense")

    _extra_requirements(form, refresh)
    _breadth_requirements(form, refresh)

    # Prerequisites: every Charm in the rule set, homebrew included, so a custom tree
    # can hang off a printed Charm or off another custom one. Virtual rows (the
    # Dragon-King Path powers projected into the catalogue so Combos and the sheet
    # can name them) are excluded — they are never learnable (`charm_matches_splat`
    # rejects them first), so a prereq on one would be unsatisfiable.
    prereq_opts = {c.id: (f"✎ {c.name}" if c.custom else c.name)
                   for c in sorted(ruleset.charms.values(), key=lambda c: c.name)
                   if not c.virtual}
    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        ui.select(prereq_opts, value=form["prerequisites"], label="Prerequisites",
                  multiple=True, with_input=True, on_change=bind("prerequisites")) \
            .classes("flex-1").props("dense use-chips")
        ui.select({"all": "all required", "any": "any one of them"},
                  value=form["prereq_mode"], label="Mode",
                  on_change=bind("prereq_mode")).classes("w-40").props("dense") \
            .tooltip("Prerequisites are AND-of-OR; these are the two shapes the form "
                     "writes. Anything more complex: use the JSON pane.")
    ui.select({"": "grants no sorcery circle"} | {c.value: f"grants the {c.value} Circle"
                                                  for c in SpellCircle},
              value=form["grants_circle"], label="Sorcery initiation",
              on_change=bind("grants_circle")).classes("w-full").props("dense")
    _advanced_fields(form, bind, ruleset)


def _spell_fields(form: dict, bind) -> None:
    with ui.row().classes("w-full items-center gap-2 no-wrap"):
        ui.select({c.value: c.value for c in SpellCircle}, value=form["circle"],
                  label="Circle", on_change=bind("circle")).classes("flex-1").props("dense")
        ui.number("Motes", value=form["motes"], min=0, format="%d",
                  on_change=bind("motes")).classes("w-24")
        ui.number("WP", value=form["willpower"], min=0, format="%d",
                  on_change=bind("willpower")).classes("w-20")
    ui.input("Cost override (variable costs)", value=form["cost_raw"],
             on_change=bind("cost_raw")).classes("w-full").props("dense")


def load() -> RuleSet:
    return rules_db.load_app_ruleset(_DATA_DIR)


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e custom content editor")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset = load()

    @ui.page("/")
    def index() -> None:
        build_custom(ruleset)

    ui.run(title="Exalted 1e — Custom content", reload=False, show=args.show,
           port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
