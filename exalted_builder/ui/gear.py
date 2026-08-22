"""
ui/gear.py — the Gear tab: everything the character OWNS, in one place.

One tab for weapons, armour, goods, artifacts and the price list (human's call,
2026-08-13). ⚠ Keep them together: splitting an artifact daiklave's STATS onto Edit and
its BUDGET onto Advantages is what lets the same object be entered twice and charged
twice (see `docs/status/rated-artifacts.md`).

⚠ Why a TOP-LEVEL tab rather than a sub-tab of Advantages, which was the first proposal:
"Advantages" is a 1e game term meaning Backgrounds plus Merits & Flaws, and equipment is
not one. Filing goods under it would read as wrong to anyone who knows the book, and
this build matches the book's vocabulary deliberately elsewhere (`charm_noun`, "Arrays"
for Alchemicals). Nesting would also cost a click on a surface used during play.

The Artifact Background link is stated in BOTH places: the budget line sits in this
tab's readout (it is about what you own), and the Artifact Background row on Advantages
carries a one-line note saying what it buys. Two surfaces stating one rule is
deliberate — one surface owning it silently is what produced the double-charge above.

Presentation only. Every derived list comes from `ui/view.py` and every rule from
`engine/` — see the `ui → engine → models` rule in docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from .. import custom_content as customs, persistence
from ..engine import artifacts as artifactsmod, derive, gear_actions, validate
from ..models.character import Character
from ..models.rules import RuleSet
from . import catalogue as cataloguemod
from . import theme
from . import view as viewmod
from .editor import DescribedSelect, _opts_with, panel_card


def build_gear(ruleset: RuleSet, character: Character, save_path: Path,
               *, with_header: bool = True) -> None:
    """Render the Gear tab — the inventory, the per-kind editors, and the price list."""
    rs = ruleset
    pal = theme.palette(character.exalt_type)

    def panel(title: str):
        return panel_card(pal, title)

    def changed() -> None:
        readout.refresh()

    def refresh_all() -> None:
        body.refresh()
        changed()

    # ---- mutators — thin refresh wrappers over `engine.gear_actions` -------- #
    # ⚠ The rules moved OUT of this file on 2026-08-21 (the Qt port's milestone-4 prep):
    # what a re-pick carries across, what an artifact grants, and which channel stamps a
    # purchase are decisions two shells now make, so they live in one place.
    def add_item(field: str) -> None:
        gear_actions.add_row(character, field)
        body.refresh(); changed()

    def remove_item(field: str, idx: int) -> None:
        gear_actions.remove_row(character, field, idx)
        body.refresh(); changed()

    def set_armor(idx: int, name: str) -> None:
        gear_actions.set_armor(rs, character, idx, name)
        body.refresh(); changed()

    def set_weapon(idx: int, name: str) -> None:
        gear_actions.set_weapon(rs, character, idx, name)
        body.refresh(); changed()

    def add_artifact() -> None:
        gear_actions.add_artifact(rs, character)
        refresh_all()

    def remove_artifact(idx: int) -> None:
        gear_actions.remove_artifact(character, idx)
        refresh_all()


    # ⚠ These helpers are at build_gear scope, NOT inside body(). The row editors
    # below are called FROM body but DEFINED here, so a helper local to body is a
    # NameError at call time — and NiceGUI swallows that into an empty panel
    # rather than a crash, which is how it presented (2026-08-13).
    # equipment — inline copies; the catalog autofills, then every stat is
    # editable per item (custom or tweaked artifact/masterwork). Each item's
    # numbers live behind an "Edit stats" expander; the summary updates live.
    armor_names = [a.name for a in ruleset.armor_catalog.values()]
    weapon_names = [w.name for w in ruleset.weapon_catalog.values()]
    # "" = mundane; material bonuses apply only for the matching Exalt (p.341).
    material_opts = {"": "— none —"} | {
        m.id: m.name for m in ruleset.material_catalog.values()}

    # The format lives in view.weapon_stat_line / armor_stat_line — the catalogue
    # dialog renders the same line for a pre-pick entry, and writing it twice is
    # how the two drifted. Here the stats are the EFFECTIVE ones (material folded
    # in) and the material tag is the wielder's.
    def _weapon_summary(wp) -> str:
        mat = derive.applied_material(ruleset, character, wp)
        return viewmod.weapon_stat_line(
            derive.effective_weapon(ruleset, character, wp),
            material=mat.name if mat else "")

    def _armor_summary(ar) -> str:
        mat = derive.applied_material(ruleset, character, ar)
        return viewmod.armor_stat_line(
            derive.effective_armor(ruleset, character, ar),
            material=mat.name if mat else "")

    def material_select(item, sm_label, sm_fn):
        def _on(e, item=item, sm_label=sm_label, sm_fn=sm_fn):
            setattr(item, "material", e.value or "")
            sm_label.set_text(sm_fn(item))
            changed()
        ui.select(material_opts, value=item.material or "", label="Material",
                  on_change=_on).classes("w-40").props("dense")

    def stat_num(item, attr, label, sm_label, sm_fn, *, signed=False):
        def _on(e, item=item, attr=attr, sm_label=sm_label, sm_fn=sm_fn):
            setattr(item, attr, int(e.value or 0))
            sm_label.set_text(sm_fn(item))
            changed()
        kwargs = {} if signed else {"min": 0}
        ui.number(label=label, value=getattr(item, attr), format="%d",
                  on_change=_on, **kwargs).classes("w-20").props("dense")

    # ⚠ At build_gear scope: the row editor refreshes this when a rating changes,
    # and the editor is defined out here. Inside `_artifacts_panel` it was a
    # NameError that NiceGUI logs and turns into an empty panel.
    @ui.refreshable
    def _artifacts_header() -> None:
        """The budget line, its own refreshable so a rating edit updates it WITHOUT
        rebuilding the panel. Rebuilding the body from inside the rating input's
        on_change destroyed the widget mid-interaction — NiceGUI drops events that
        target a deleted element (Client.handle_event), so a rapid second click
        (5→4→5) was silently lost, the stored rating desynced from the number on
        screen, and the two-flagships warning never came back. The header and the
        readout are the only things a rating edit moves."""
        with ui.row().classes("w-full items-baseline gap-2"):
            ui.label(viewmod.artifacts_header(rs, character)).classes(
                "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            ui.label("bought with the Artifact Background").classes(
                "text-xs text-gray-500")
            note = viewmod.artifacts_bought_note(character)
            if note:
                ui.label(note).classes("text-xs text-gray-500"
                                       ).props('data-testid="art-bought"')

    # The artifact catalogue, shared by the row editor and the panel's picker — hoisted
    # so both can close over it. ⚠ A closure over a name defined in a function it no
    # longer lives in is a NameError that NiceGUI reports as an EMPTY PANEL, not as a
    # crash.
    # Merit-gated plot devices join the list only once the character holds the Merit —
    # `purchasable_artifacts` moves the OFFER with the permission, not just the bar.
    #
    # ⚠ A FUNCTION, not a value computed here. The list now depends on character state
    # that changes on ANOTHER tab (taking or dropping the Legendary Artifact Merit), and
    # this body runs once per page build — captured, it would be the stale-closure trap
    # verbatim: a player takes the Merit, comes back, and the artifact she just paid ten
    # bonus points for is not in the dropdown. Every call site recomputes.
    def _art_catalog() -> list:
        return artifactsmod.purchasable_artifacts(rs.artifact_catalog, character)

    def _art_descs(catalog) -> dict:
        return {a.name: f"{a.rating_notes or ('•' * a.rating)} — {a.description}"
                for a in catalog}

    def _artifact_editor(idx, art) -> None:
        """One standalone artifact's editor, rendered inside its inventory row.

        ⚠ Rendered in the row, never in a panel of its own: the inventory is the ONE
        list of what is owned, and a panel repeating four of its rows is a second
        surface editing the same objects.
        """
        art_catalog = _art_catalog()
        art_names = [a.name for a in art_catalog]
        art_descs = _art_descs(art_catalog)
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            sel = (DescribedSelect(_opts_with(art_names, art.name),
                                   descriptions=art_descs,
                                   value=art.name or None, label="Artifact name",
                                   with_input=True, new_value_mode="add-unique")
                   .props("dense").classes("flex-1"))
            ui.input(value=art.note, placeholder="note",
                     on_change=lambda e, art=art: setattr(art, "note", e.value)
                     ).props("dense").classes("flex-1")
            number = ui.number(value=art.rating, min=1, max=5, format="%d",
                               label="Rating",
                               on_change=lambda e, art=art: (
                                   setattr(art, "rating",
                                           max(1, min(5, int(e.value or 1)))),
                                   _artifacts_header.refresh(),
                                   changed())
                               ).props("dense").classes("w-24")
            # How it was acquired. POST-LOCK ONLY: at creation the Background
            # is the only channel there is (core p.342, "to start the game
            # owning"), so offering the choice would be offering an illegal
            # pick — the same reasoning that filters the Virtue Flaw dropdown
            # to the flawed Virtue. `validate` bars it either way; this stops
            # the player reaching the bar.
            if character.chargen_locked:
                ui.select({artifactsmod.ACQUIRED_BACKGROUND: "Background",
                           artifactsmod.ACQUIRED_PURCHASED: "Bought",
                           artifactsmod.ACQUIRED_LEGENDARY: "Merit"},
                          value=art.acquired, label="Acquired",
                          on_change=lambda e, art=art: (
                              setattr(art, "acquired",
                                      e.value or artifactsmod.ACQUIRED_BACKGROUND),
                              _artifacts_header.refresh(), changed())
                          ).props("dense").classes("w-32").mark("art-acquired")
            _library_button("artifacts", art)
            ui.button(icon="delete",
                      on_click=lambda e=None, idx=idx: remove_artifact(idx)
                      ).props("flat dense round")
        # The catalogue description under the row, mirroring the Background rows:
        # the dropdown tooltip made permanent. Refreshed by the row's own select
        # WITHOUT rebuilding the panel (a rebuilt input eats every keystroke —
        # the filter bar's lesson). A free-text name no catalogue entry covers
        # gets nothing — the label just hides. `data-testid` is the one prop that
        # distinguishes this label from the M&F rules-text labels, which share its
        # styling classes.
        desc = ui.label("").classes("text-xs opacity-70 pl-1"
                                    ).props('data-testid="art-desc"')

        def _sync(art=art, desc=desc):
            entry = next((a for a in art_catalog if a.name == art.name), None)
            text = entry.description if entry else ""
            desc.set_text(text)
            desc.set_visibility(bool(text))

        def _on_art(e, idx=idx, art=art, number=number, sync=_sync):
            # A catalogue pick sets name + autofills rating (and stamps the channel and
            # grants the stat line); any other value is free text and only renames,
            # preserving the rating. All of that is `gear_actions.set_artifact`.
            if gear_actions.set_artifact(rs, character, idx, e.value or ""):
                # Keep the on-screen control in sync: the header refresh
                # recomputes the total but must NOT rebuild the body (see
                # the header docstring), so the number is pushed directly.
                number.value = art.rating
            sync()
            _artifacts_header.refresh()
            changed()

        sel.on_value_change(_on_art)
        _sync()

    def _artifacts_panel() -> None:
        """The standalone artifacts — those that are neither weapon nor armour.

        On the Advantages tab because artifacts are bought with the Artifact Background
        and budgeted by it (E:Ab p.131), so the two belong under one eye. Weapons and
        armour keep their own `artifact_rating` on the equipment surface and are NOT
        editable here — they are only counted, in the budget line below.

        ⚠ Counting alone does NOT stop a daiklave being entered twice — a number of
        names exist in both catalogues, so a player who owns the artifact AND adds the
        gear row to swing it is charged for two daiklaves. Picking an artifact GRANTS its
        stat line, stamped with `from_artifact`, and the budget counts the pair once —
        see `grant_gear` and `artifacts.artifact_items`.

        One panel, both regimes: an artifact is equipment, and equipment has never been
        XP-priced or log-tracked on either side of the lock.

        The name field is a combobox fed from `RuleSet.artifact_catalog`
        (`data/artifacts.json`): picking a catalogue entry fills the name and autofills
        the rating, and a typed off-catalogue name is free text that renames while
        preserving the rating. Entering a gear item both here and on the equipment
        surface counts it twice toward the budget — the same contract free text already
        has; there is no cross-catalogue dedup.
        """

        # The name combobox is fed from the catalogue (`data/artifacts.json`). Option
        # labels stay plain names so `art.name` stores cleanly; the rating and
        # description ride the option tooltip.
        # Filtered to what Artifact dots actually buy: the Hearthstones in the same
        # catalogue file come with the Manse Background, and picking one here would
        # charge the p.131 Artifact budget for something Artifact never bought. They
        # get their own picker on the Manse Background row instead.
        with ui.card().classes(f"w-full p-3 {pal.card} gap-1"):
            _artifacts_header()
            # Artifact weapons and armour count against the same budget but are edited
            # on the equipment surface. Listed read-only so the combined total above is
            # accounted for rather than looking wrong.
            also = viewmod.artifacts_also_counted(character)
            if also:
                ui.label(also).classes("text-xs italic opacity-70")

            # The catalogue picker replaces the blind "Add artifact": browse the
            # catalogue (name + rating + description), pick one — name AND rating
            # autofilled — or choose Custom for a blank row.
            def _open_artifact_catalogue() -> None:
                # Recomputed per OPEN, not captured — see `_art_catalog`.
                art_catalog = _art_catalog()
                rows = [(a.name, a.name,
                         f"{a.rating_notes or ('•' * a.rating)} — {a.description}",
                         a.description)
                        for a in art_catalog]
                icons = {a.name: cataloguemod.icon_for(a.tags, "auto_awesome")
                         for a in art_catalog}
                cataloguemod.catalogue_dialog(pal, "Artifacts", rows, _pick_artifact,
                                              icons=icons)

            def _pick_artifact(name) -> None:
                gear_actions.add_artifact(rs, character, name)
                refresh_all()

            ui.button("Add artifact", icon="add", on_click=_open_artifact_catalogue
                      ).props("flat dense")

    # ---- the custom library ------------------------------------------------ #
    def _save_to_library(kind: str, item) -> None:
        """Put this row in the user's library so every future character can buy it."""
        try:
            customs.save_gear_row(kind, gear_actions.library_payload(kind, item),
                                  reserved_ids=gear_actions.reserved_ids(rs))
        except customs.CustomContentError as ex:
            ui.notify(str(ex), type="warning")
            return
        extra = " (armour weight defaults to Light)" if kind == "armor" else ""
        ui.notify(f"Saved {item.name} to your library{extra}. It will appear in Buy "
                  f"the next time the app loads its rules.", type="positive")

    def _library_button(kind: str, item) -> None:
        ui.button(icon="bookmark_add",
                  on_click=lambda e=None, k=kind, it=item: _save_to_library(k, it)
                  ).props("flat dense round").tooltip(
            "Save to my library — it becomes buyable for every character"
        ).mark("save-to-library")

    # ---- readout ----------------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        """The gear-relevant issues, live. ⚠ Artifact findings belong HERE, with the
        panel that produces them: a report sitting on a surface that no longer edits
        the thing it reports about is the house bug in UI form."""
        rows = viewmod.inventory_rows(rs, character)
        ui.label(f"{len(rows)}").classes("text-2xl font-bold").style(
            f"color:{pal.accent}")
        ui.label("items owned").classes("text-xs text-gray-600")
        res = validate.effective_background_rating(rs, character, "Resources")
        ui.label(f"Resources {'•' * res if res else '—'}").classes(
            "text-xs text-gray-600")
        ui.separator()
        issues = [i for i in viewmod.build_sheet_view(rs, character).issues
                  if "artifact" in i.code or "hearthstone" in i.code]
        if not issues:
            ui.label("No artifact issues.").classes("text-xs text-gray-500")
        for issue in issues:
            color = {"error": "text-red-600",
                     "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    def _armor_editor(idx, ar) -> None:
        """One owned row's editor, rendered inside its inventory row."""
        with ui.column().classes(f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(_opts_with(armor_names, ar.name), value=ar.name or None,
                          with_input=True,
                          new_value_mode="add-unique", label="Armor",
                          on_change=lambda e, idx=idx: set_armor(idx, e.value)).classes("flex-1")
                asm = ui.label(_armor_summary(ar)).classes("text-xs")
                _library_button("armor", ar)
                ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_item("armor", idx)).props("flat dense round")
            with ui.expansion("Edit stats", icon="tune").classes("w-full"):
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    stat_num(ar, "soak_lethal", "Soak L", asm, _armor_summary)
                    stat_num(ar, "soak_bashing", "Soak B", asm, _armor_summary)
                    stat_num(ar, "mobility_penalty", "Mob", asm, _armor_summary, signed=True)
                    stat_num(ar, "fatigue", "Ftg", asm, _armor_summary)
                    stat_num(ar, "artifact_rating", "Art", asm, _armor_summary)
                    stat_num(ar, "attunement", "Attune", asm, _armor_summary)
                    stat_num(ar, "resources_cost", "Res", asm, _armor_summary)
                    material_select(ar, asm, _armor_summary)


    def _weapon_editor(idx, wp) -> None:
        """One owned row's editor, rendered inside its inventory row."""
        with ui.column().classes(f"w-full gap-1 border-b border-{pal.fam}-900/10 pb-1"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.select(_opts_with(weapon_names, wp.name), value=wp.name or None,
                          with_input=True,
                          new_value_mode="add-unique", label="Weapon",
                          on_change=lambda e, idx=idx: set_weapon(idx, e.value)).classes("flex-1")
                wsm = ui.label(_weapon_summary(wp)).classes("text-xs")
                # Stackable gear. Ammunition is the case that put it here —
                # a player holds arrows by the score — but nothing stops a
                # stack of javelins, so every weapon row carries it. It is a
                # COUNT and nothing more: no engine reads it, because nothing
                # derives an attack (decision 0008).
                ui.number(value=wp.quantity, min=1, format="%d", label="Qty",
                          on_change=lambda e, wp=wp: (
                              setattr(wp, "quantity",
                                      max(1, int(e.value or 1))),
                              _inventory.refresh(), changed())
                          ).props("dense").classes("w-16")
                _library_button("weapons", wp)
                ui.button(icon="delete", on_click=lambda e=None, idx=idx: remove_item("weapons", idx)).props("flat dense round")
            with ui.expansion("Edit stats", icon="tune").classes("w-full"):
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    stat_num(wp, "speed", "Spd", wsm, _weapon_summary, signed=True)
                    stat_num(wp, "accuracy", "Acc", wsm, _weapon_summary, signed=True)
                    stat_num(wp, "damage", "Dmg", wsm, _weapon_summary, signed=True)
                    ui.select(["L", "B"], value=wp.damage_type or "L", label="Type",
                              on_change=lambda e, wp=wp, wsm=wsm: (setattr(wp, "damage_type", e.value or "L"),
                                                                  wsm.set_text(_weapon_summary(wp)), changed())
                              ).classes("w-16").props("dense")
                    stat_num(wp, "defense", "Def", wsm, _weapon_summary, signed=True)
                    stat_num(wp, "rate", "Rate", wsm, _weapon_summary)
                    stat_num(wp, "range", "Rng", wsm, _weapon_summary)
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    stat_num(wp, "min_strength", "Min Str", wsm, _weapon_summary)
                    stat_num(wp, "min_dexterity", "Min Dex", wsm, _weapon_summary)
                    stat_num(wp, "min_martial_arts", "Min MA", wsm, _weapon_summary)
                    stat_num(wp, "max_strength", "Max Str", wsm, _weapon_summary)
                    stat_num(wp, "artifact_rating", "Art", wsm, _weapon_summary)
                    stat_num(wp, "attunement", "Attune", wsm, _weapon_summary)
                    stat_num(wp, "resources_cost", "Res", wsm, _weapon_summary)
                    material_select(wp, wsm, _weapon_summary)
                ui.input("Notes", value=wp.notes,
                         on_change=lambda e, wp=wp: (setattr(wp, "notes", e.value), changed())).classes("w-full").props("dense")


    def _goods_editor(idx, item) -> None:
        """One owned row's editor, rendered inside its inventory row."""
        with ui.row().classes("w-full items-center gap-2 no-wrap"):
            # ⚠ `_inventory.refresh()`, never `body.refresh()`: the
            # inventory panel is a different widget tree from this input,
            # so refreshing it leaves the keystroke alone. Rebuilding the
            # body from an input's on_change eats every character typed.
            ui.input(value=item.name, label="Item",
                     on_change=lambda e, it=item: (
                         setattr(it, "name", e.value or ""),
                         _inventory.refresh(), changed())
                     ).props("dense").classes("flex-1")
            ui.number(value=item.quantity, min=1, format="%d", label="Qty",
                      on_change=lambda e, it=item: (
                          setattr(it, "quantity", max(1, int(e.value or 1))),
                          _inventory.refresh(), changed())
                      ).props("dense").classes("w-16")
            # LABELLED. A bare "•••" beside an item is unreadable — the
            # browser asked what it meant (2026-08-13), and every other dot
            # column on the sheet is a rated trait, which this is not: it
            # is what the thing COST.
            ui.label(f"Res {'•' * item.resources_cost}"
                     if item.resources_cost else "Res —"
                     ).classes("text-xs opacity-70 w-20 shrink-0").tooltip(
                "The Resources rating needed to buy one (M&C p.123). "
                "A record of the price, not a trait.")
            _library_button("gear", item)
            ui.button(icon="delete",
                      on_click=lambda e=None, idx=idx: remove_item("gear", idx)
                      ).props("flat dense round")


    # ---- body -------------------------------------------------------------- #
    @ui.refreshable
    def body() -> None:
        # ---- INVENTORY: everything owned, in one filterable list ---------------- #
        # The human's model (2026-08-13): "your inventory, which is Everything, but you
        # can filter it down to certain types of goods, some of which would overlap."
        # A VIEW over the four typed lists, never a storage shape — see
        # `view.inventory_rows`. The per-type editors below stay: this answers "what do
        # I have", they answer "change its stats", and merging those two jobs into one
        # widget is how the equipment surface got unreadable in the first place.
        inv_filter = {"kind": "all"}

        @ui.refreshable
        def _inventory() -> None:
            rows = viewmod.inventory_rows(ruleset, character)
            counts = viewmod.inventory_counts(rows)
            active = inv_filter["kind"]
            with panel(viewmod.inventory_heading(rows, counts, active)):
                if not rows:
                    ui.label("Nothing owned yet — add weapons, armour or goods below."
                             ).classes("text-xs text-gray-500")
                    return
                with ui.row().classes("w-full gap-1 flex-wrap items-center"):
                    for kind in viewmod.INVENTORY_FILTERS:
                        n = counts.get(kind, 0)
                        if kind != "all" and not n:
                            continue        # an empty filter is noise, not a choice
                        label = viewmod.inventory_filter_label(kind, n)
                        ui.button(label, on_click=lambda k=kind: (
                                      inv_filter.__setitem__("kind", k),
                                      _inventory.refresh())
                                  ).props("dense flat"
                                          + ("" if inv_filter["kind"] == kind
                                             else " outline")).classes("text-xs")
                # ⚠ The counts SUM TO MORE than the row count whenever anything
                # overlaps — an artifact daiklave is both a weapon and an artifact —
                # and that is correct. The filters are not a partition.
                shown = viewmod.filter_inventory(rows, inv_filter["kind"])
                # ⚠ Each row carries its OWN editor, in an expansion. There are NO
                # per-type panels below this list (human's call, 2026-08-13): an
                # inventory beside three panels editing the same objects is four
                # surfaces for one job, and the list is the only one that can show a
                # daiklave as both weapon and artifact.
                #
                # `row.list_name` / `row.index` are what make it possible — the view
                # records where each row came FROM, so a display row can hand back the
                # object it describes.
                editors = {"armor": _armor_editor, "weapons": _weapon_editor,
                           "gear": _goods_editor, "artifacts": _artifact_editor}
                for row in shown:
                  with ui.column().classes(
                          f"w-full gap-0 border-b border-{pal.fam}-900/10 pb-1"):
                    with ui.row().classes("w-full items-baseline gap-2 no-wrap"):
                        # Marked so a test can address the INVENTORY's rows.
                        ui.label(row.name).classes(
                            "text-sm leading-tight shrink-0").mark("inv-row")
                        if row.quantity > 1:
                            ui.label(f"×{row.quantity}").classes(
                                "text-xs opacity-70 shrink-0")
                        ui.label(row.detail).classes(
                            "text-xs opacity-70 flex-1 min-w-0 truncate")
                        for tag in viewmod.inventory_row_tags(row):
                            ui.label(tag).classes(
                                "text-xs px-1 rounded shrink-0"
                                f" bg-{pal.fam}-900/10")
                        if row.resources_cost:
                            ui.label("Res " + "•" * row.resources_cost).classes(
                                "text-xs opacity-60 shrink-0")
                    with ui.expansion("Edit", icon="tune").classes("w-full"):
                        owner = getattr(character, row.list_name)
                        if row.index < len(owner):
                            editors[row.list_name](row.index, owner[row.index])
                        # A merged row is one object with TWO stored halves — the
                        # artifact and the stat line `grant_gear` stamped for it — so
                        # its editor is both, under one Edit. ⚠ Without this the stat
                        # line is uneditable: there are no per-kind panels, and the
                        # merged row is the only place it appears.
                        if row.linked_list_name:
                            linked = getattr(character, row.linked_list_name)
                            if row.linked_index < len(linked):
                                ui.label("Stat line").classes(
                                    "text-xs uppercase tracking-wide opacity-60 mt-2")
                                editors[row.linked_list_name](
                                    row.linked_index, linked[row.linked_index])

        # ---- BUY: one shop over every catalogue ------------------------------- #
        # The human's unification (2026-08-13): "Add weapon" / "Add armor" / "Add goods"
        # opened the same dialog against three catalogues, which is three shops. This is
        # one, and the kind rides in the KEY so the pick knows which list to append to.
        #
        # ⚠ It has no Custom row (`allow_custom=False`): "custom" needs a type, and a
        # dialog spanning three catalogues cannot know whether a blank row is a weapon,
        # a suit of armour or a bolt of silk. The per-panel Add buttons keep that job —
        # they are the typed affordance, this is the priced one.
        def _open_shop() -> None:
            # The rows, their groups and their prices come from `view.shop_rows`; the
            # ICONS stay here, because they are Material Icon names and the Qt shell
            # draws from a different set.
            _default_icon = {"Weapon": "sym_o_swords", "Armour": "security",
                             "Goods": "inventory_2", "Artifact": "auto_awesome"}
            shop = viewmod.shop_rows(rs, character)
            rows = [(r.key, r.name, r.summary, r.full) for r in shop]
            icons = {r.key: cataloguemod.icon_for(
                r.tags, _default_icon.get(r.group, "")) for r in shop}
            group_of = {r.key: r.group for r in shop}
            dimmed = {r.key for r in shop if r.affordability == "unaffordable"}
            cataloguemod.catalogue_dialog(
                pal, "Buy", rows, _buy,
                subtitle=("Everything a book prices, against your Resources, plus your "
                          "own library. Nothing is deducted — the cost is a hint "
                          "(core p.325)."),
                dimmed=dimmed, icons=icons, group_of=group_of,
                custom_kinds=viewmod.shop_custom_kinds(character))

        def _buy(key) -> None:
            gear_actions.buy(rs, character, key)
            refresh_all()

        _inventory()
        with ui.row().classes("w-full items-center gap-2"):
            ui.button("Buy", icon="storefront", on_click=_open_shop
                      ).props(f"color={pal.button}").mark("buy-button")
            ui.label("Weapons, armour and goods — everything a book prices."
                     ).classes("text-xs text-gray-500")

        with ui.row().classes("w-full gap-2 no-wrap items-start"):
            # The other half of the same tables, and NOT inventory: upkeep, events,
            # commissions and rentals. A character does not carry a month of stabling
            # in her pack, so these are a price list she can consult — the same
            # reference treatment the nocked arrow and the Great Geas panel get.
            #
            # ⚠ `GearType.cash` (the printed jade and silver equivalents) is the whole
            # point of this panel and its only read site. A name and a dot column alone
            # is a PRICE list showing no prices — the house bug. What makes a reference
            # panel worth its space is the information you cannot get anywhere else.
            with panel("Prices — services & upkeep").classes("flex-1"):
                services = viewmod.service_rows(ruleset, character)
                if services:
                    ui.label("Reference only — not owned, and nothing here is tracked. "
                             "Jade and silver are the printed equivalents (M&C p.123); "
                             "the conversion is the Storyteller's call, so nothing is "
                             "computed from them.").classes("text-xs text-gray-500")
                    # ⚠ A DEFINITE height and nothing else. `flex-1 min-h-0` is the
                    # right recipe when the PARENT is a fixed-height flex column (the
                    # catalogue dialog's `h-[85vh]` card), and it is self-defeating
                    # here: this panel's card has no height, so `flex: 1 1 0%` collapses
                    # the area to its 0 basis and `min-h-0` removes the content-based
                    # floor that would have saved it. The rows still render — the tests
                    # see them in the DOM — while the browser shows an empty panel.
                    with ui.scroll_area().classes("w-full").style("height:16rem"):
                        last_category = ""
                        for category, name, dots, cash, notes, afford in services:
                            if category != last_category:
                                last_category = category
                                ui.label(category).classes(
                                    "text-xs font-bold tracking-wide pt-2"
                                    ).style(f"color:{pal.accent}")
                            faded = "" if afford else " opacity-50"
                            with ui.row().classes(
                                    "w-full items-baseline gap-2 no-wrap" + faded):
                                ui.label("•" * dots).classes("text-xs w-14 shrink-0")
                                ui.label(name).classes(
                                    "text-xs leading-tight flex-1 min-w-0")
                                if cash:
                                    ui.label(cash).classes(
                                        "text-xs opacity-70 shrink-0 text-right")
                            if notes:
                                ui.label(notes).classes(
                                    "text-xs italic opacity-60 pl-14 leading-tight")

        _artifacts_panel()

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    # ---- layout ------------------------------------------------------------ #
    if with_header:
        ui.add_head_html(pal.head_style())
    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            if with_header:
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("Gear").classes("text-xl font-bold")
                    ui.button("Save", icon="save", on_click=save
                              ).props(f"color={pal.button}")
            body()
        with ui.column().classes("w-80 gap-2 sticky top-4"):
            with ui.card().classes(f"w-full p-3 {pal.card}"):
                ui.label("Gear").classes(
                    "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
                readout()
