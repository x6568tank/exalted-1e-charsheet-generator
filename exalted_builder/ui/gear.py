"""
ui/gear.py — the Gear tab: everything the character OWNS, in one place.

Split out of `ui/editor.py` (weapons, armour, goods, the price list) and
`ui/advantages.py` (artifacts) on 2026-08-13, on the human's call. The two halves had
drifted apart for a structural reason, not an accidental one: an artifact daiklave had
its STATS on the Edit tab and its BUDGET on Advantages, and that split is what let the
same object be entered twice and charged twice (see `docs/status/rated-artifacts.md`).

⚠ Why a TOP-LEVEL tab rather than a sub-tab of Advantages, which was the first proposal:
"Advantages" is a 1e game term meaning Backgrounds plus Merits & Flaws, and equipment is
not one. Filing goods under it would read as wrong to anyone who knows the book, and
this build matches the book's vocabulary deliberately elsewhere (`charm_noun`, "Arrays"
for Alchemicals). Nesting would also cost a click on a surface used during play.

The Artifact Background link survives without nesting, and is stated in BOTH places: the
budget header sits on the Artifacts panel here (it is about what you own), and the
Artifact Background row on Advantages carries a one-line note saying what it buys. Two
surfaces stating one rule is the pattern that has caught bugs all day; one surface
owning it silently is the pattern that produced them.

Presentation only. Every derived list comes from `ui/view.py` and every rule from
`engine/` — see the `ui → engine → models` rule in docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from .. import custom_content as customs, persistence
from ..engine import artifacts as artifactsmod, derive, merits as meritsmod, validate
from ..models.character import (Armor, ArtifactEntry, Character, GearEntry, Weapon)
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

    # ---- mutators (moved with the panels they serve) ----------------------- #
    def add_item(field: str) -> None:
        factory = {"armor": lambda: Armor(name=""), "weapons": lambda: Weapon(name=""),
                   "gear": lambda: GearEntry(name="")}[field]
        getattr(character, field).append(factory())
        body.refresh(); changed()

    def remove_item(field: str, idx: int) -> None:
        del getattr(character, field)[idx]
        body.refresh(); changed()

    def set_armor(idx: int, name: str) -> None:
        entry = next((a for a in rs.armor_catalog.values() if a.name == name), None)
        if entry:
            character.armor[idx] = Armor(
                name=entry.name, soak_lethal=entry.soak_lethal,
                soak_bashing=entry.soak_bashing,
                mobility_penalty=entry.mobility_penalty, fatigue=entry.fatigue,
                artifact_rating=entry.artifact_rating, attunement=entry.attunement,
                resources_cost=entry.resources_cost,
                # Carried across for the same reason as the weapon row below.
                from_artifact=character.armor[idx].from_artifact)
        else:
            character.armor[idx].name = name or ""
        body.refresh(); changed()

    def set_weapon(idx: int, name: str) -> None:
        e = next((w for w in rs.weapon_catalog.values() if w.name == name), None)
        # The row is REPLACED by the catalogue copy, so anything not in the copy is
        # lost. `quantity` is the player's, not the catalogue's — carry it across, and
        # `from_artifact` with it: that link is what stops the artifact this row belongs
        # to being counted twice, and re-picking the same daiklave from the dropdown
        # would otherwise drop it silently and charge the budget again.
        quantity = character.weapons[idx].quantity
        from_artifact = character.weapons[idx].from_artifact
        if e:
            character.weapons[idx] = Weapon(
                quantity=quantity, from_artifact=from_artifact,
                name=e.name, speed=e.speed, accuracy=e.accuracy, damage=e.damage,
                damage_type=e.damage_type, defense=e.defense, rate=e.rate, range=e.range,
                min_strength=e.min_strength, min_dexterity=e.min_dexterity,
                min_martial_arts=e.min_martial_arts, max_strength=e.max_strength,
                artifact_rating=e.artifact_rating, attunement=e.attunement,
                resources_cost=e.resources_cost, notes=e.notes)
        else:
            character.weapons[idx].name = name or ""
        body.refresh(); changed()

    def add_artifact() -> None:
        character.artifacts.append(ArtifactEntry(name="", rating=1))
        refresh_all()

    def remove_artifact(idx: int) -> None:
        # The gear row this artifact granted is deliberately LEFT BEHIND. It may have
        # been edited, and deleting a player's equipment to tidy up a link is not this
        # panel's business; the orphaned row simply counts as an artifact in its own
        # right again (see `artifacts.artifact_items`), which is visible rather than
        # free. Deleting the weapon is one click and theirs to make.
        del character.artifacts[idx]
        refresh_all()

    def grant_gear(art_name: str) -> None:
        """Give a newly picked artifact its stat line on the equipment surface.

        ⚠ Owning "Daiklave" as an artifact and separately adding a "Daiklave" weapon to
        swing it counts the same object twice, which the corebook one-artifact rule
        turns into a false error (human's call, 2026-08-13). So the artifact grants the
        row and stamps `from_artifact` on it, and the budget counts the pair once.

        Silent when the artifact has no gear half (202 of the 222 do not), and when the
        row is already there — picking the same artifact twice must not breed daiklaves.
        """
        found = artifactsmod.gear_stat_line(rs, art_name)
        if found is None:
            return
        source, entry = found
        key = artifactsmod.item_key(artifactsmod.SOURCE_ARTIFACT, art_name)
        rows = (character.weapons if source == artifactsmod.SOURCE_WEAPON
                else character.armor)
        if any(row.from_artifact == key for row in rows):
            return
        if source == artifactsmod.SOURCE_WEAPON:
            rows.append(Weapon(
                name=entry.name, speed=entry.speed, accuracy=entry.accuracy,
                damage=entry.damage, damage_type=entry.damage_type,
                defense=entry.defense, rate=entry.rate, range=entry.range,
                min_strength=entry.min_strength, min_dexterity=entry.min_dexterity,
                min_martial_arts=entry.min_martial_arts,
                max_strength=entry.max_strength, artifact_rating=entry.artifact_rating,
                attunement=entry.attunement, resources_cost=entry.resources_cost,
                notes=entry.notes, from_artifact=key))
        else:
            rows.append(Armor(
                name=entry.name, soak_lethal=entry.soak_lethal,
                soak_bashing=entry.soak_bashing,
                mobility_penalty=entry.mobility_penalty, fatigue=entry.fatigue,
                artifact_rating=entry.artifact_rating, attunement=entry.attunement,
                resources_cost=entry.resources_cost, from_artifact=key))


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
        # The BUDGET's items, not everything owned: a purchased artifact is charged
        # to nothing, so counting it here would print a number the validator does
        # not agree with — the header and the rule must tell the same story.
        items = artifactsmod.budgeted_items(character)
        bought = artifactsmod.purchased_items(character)
        rule = artifactsmod.artifact_rule(validate.effective_budgets(rs, character))
        budgeted = rule is not None and bool(rule.budget_tiers)
        header = "Artifacts"
        rating = sum(bg.rating for bg in character.backgrounds
                     if bg.name.strip().lower() == artifactsmod.ARTIFACT_BACKGROUND)
        if artifactsmod.uses_corebook_rule(rule):
            # The corebook rule (ruling 2026-08-13) governs most splats, and until
            # it was enforced this header said the bare word "Artifacts" — so the
            # first a player heard of the one-artifact limit was a validation error
            # after they had picked two. The line states the rule whether or not
            # they are over it.
            #
            # ONE PER ROW: a character may hold the Artifact Background more than
            # once, and two Artifact •• rows are two artifacts (see
            # `validate.background_rows`). The header counts rows, not their sum —
            # printing "/1" beside two rows is what made the browser read the
            # validator's error as arbitrary.
            rows = sorted((r for r in validate.background_rows(
                character.backgrounds, artifactsmod.ARTIFACT_BACKGROUND) if r > 0),
                reverse=True)
            if rows:
                allowance = " + ".join(f"up to {r}" for r in rows)
                header = (f"Artifacts ({len(items)}/{len(rows)} — Artifact "
                          f"{'+'.join(str(r) for r in rows)}, {allowance})")
            else:
                header = f"Artifacts ({len(items)} — no Artifact Background)"
        elif budgeted:
            tier = artifactsmod.budget_tier(
                validate.effective_budgets(rs, character), rating)
            combined = sum(i.rating for i in items)
            if tier is not None:
                # The row name is optional — the Cult of the Illuminated's table
                # (p.96) prints bare dot rows where the Abyssal's names each one,
                # and a blank left a trailing comma inside the parenthesis.
                named = f", {tier.name}" if tier.name else ""
                header = (f"Artifacts ({combined}/{tier.combined_max} combined — "
                          f"Artifact {rating}{named})")
            else:
                header = f"Artifacts ({combined} combined — no Artifact Background)"

        with ui.row().classes("w-full items-baseline gap-2"):
            ui.label(header).classes(
                "text-sm font-bold tracking-widest").style(f"color:{pal.accent}")
            ui.label("bought with the Artifact Background").classes(
                "text-xs text-gray-500")
            if bought:
                # Said out loud, because the alternative is a header whose count is
                # lower than the visible list for no stated reason.
                ui.label(f"+ {len(bought)} bought with Resources, not charged to "
                         f"the Background").classes("text-xs text-gray-500"
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

        Was the body of the Artifacts panel, which is gone: the inventory is the
        one list of what is owned, and a panel repeating four of its rows was a
        second surface editing the same objects.
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

        def _on_art(e, art=art, number=number, sync=_sync):
            # A catalogue pick sets name + autofills rating; any other
            # value is free text and only renames, preserving the rating.
            entry = next((a for a in art_catalog
                          if a.name == (e.value or "")), None)
            if entry is not None:
                art.name, art.rating = entry.name, entry.rating
                # A merit-gated artifact is charged to no budget: the Merit was its
                # price. Stamped from the CATALOGUE at pick time rather than chosen,
                # so the player never has to know the channel exists.
                if entry.requires_merit:
                    art.acquired = artifactsmod.ACQUIRED_LEGENDARY
                # Keep the on-screen control in sync: the header refresh
                # recomputes the total but must NOT rebuild the body (see
                # the header docstring), so the number is pushed directly.
                number.value = entry.rating
                # Choosing a catalogue artifact HERE is the same act as
                # choosing one in the dialog, so it grants the same stat line.
                grant_gear(entry.name)
            else:
                art.name = e.value or ""
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

        ⚠ Counting alone does NOT stop a daiklave being entered twice — twenty names
        exist in both catalogues, so a player who owns the artifact AND adds the gear
        row to swing it is charged for two daiklaves. Picking an artifact GRANTS its
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
            gear = [i for i in artifactsmod.artifact_items(character)
                    if i.source != artifactsmod.SOURCE_ARTIFACT]
            if gear:
                ui.label("Also counted, from equipment: "
                         + ", ".join(f"{i.name} ({i.rating})" for i in gear)
                         ).classes("text-xs italic opacity-70")

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
                if name is None:
                    add_artifact()
                    return
                entry = next((a for a in _art_catalog() if a.name == name), None)
                if entry is not None:
                    character.artifacts.append(ArtifactEntry(
                        name=entry.name, rating=entry.rating,
                        acquired=(artifactsmod.ACQUIRED_LEGENDARY
                                  if entry.requires_merit
                                  else artifactsmod.ACQUIRED_BACKGROUND)))
                    grant_gear(entry.name)
                else:
                    character.artifacts.append(ArtifactEntry(name=name, rating=1))
                refresh_all()

            ui.button("Add artifact", icon="add", on_click=_open_artifact_catalogue
                      ).props("flat dense")

    # ---- the custom library ------------------------------------------------ #
    def _library_payload(kind: str, item) -> dict:
        """One owned row, as a library row of the shape `data/` uses.

        The four kinds have four models, so this is four small mappings rather than a
        generic dump — a `Weapon` is not a `WeaponType` (the character's copy has
        `quantity` and `from_artifact`, which are facts about ownership, not about the
        design) and shipping the difference into the library would put ownership state
        in a catalogue.
        """
        base = {"id": customs.make_id(item.name), "name": item.name}
        if kind == "weapons":
            return base | {
                "speed": item.speed, "accuracy": item.accuracy, "damage": item.damage,
                "damage_type": item.damage_type, "defense": item.defense,
                "rate": item.rate, "range": item.range,
                "min_strength": item.min_strength, "min_dexterity": item.min_dexterity,
                "min_martial_arts": item.min_martial_arts,
                "max_strength": item.max_strength,
                "artifact_rating": item.artifact_rating,
                "attunement": item.attunement, "resources_cost": item.resources_cost,
                "notes": item.notes}
        if kind == "armor":
            return base | {
                # ⚠ `weight` is REQUIRED by ArmorType and a character's armour row does
                # not carry one, so it is defaulted and SAID OUT LOUD in the notify
                # rather than guessed silently. The player edits the library file if it
                # matters; nothing in the engine reads armour weight today.
                "weight": "Light",
                "soak_lethal": item.soak_lethal, "soak_bashing": item.soak_bashing,
                "mobility_penalty": item.mobility_penalty, "fatigue": item.fatigue,
                "artifact_rating": item.artifact_rating,
                "attunement": item.attunement, "resources_cost": item.resources_cost}
        if kind == "gear":
            return base | {"kind": "goods", "category": "Your library",
                           "resources_cost": item.resources_cost, "notes": item.note}
        return base | {"rating": item.rating, "description": item.note}

    def _save_to_library(kind: str, item) -> None:
        """Put this row in the user's library so every future character can buy it."""
        try:
            payload = _library_payload(kind, item)
            customs.save_gear_row(kind, payload, reserved_ids=_reserved_ids())
        except customs.CustomContentError as ex:
            ui.notify(str(ex), type="warning")
            return
        extra = " (armour weight defaults to Light)" if kind == "armor" else ""
        ui.notify(f"Saved {item.name} to your library{extra}. It will appear in Buy "
                  f"the next time the app loads its rules.", type="positive")

    def _reserved_ids() -> set[str]:
        """Every id the BOOK uses, so a library row can never shadow printed content —
        the same rule `_load_custom_layer` enforces on load, checked here so the user
        hears about it while they can still rename the thing."""
        return (set(rs.weapon_catalog) | set(rs.armor_catalog)
                | set(rs.gear_catalog) | set(rs.artifact_catalog))

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
            # The heading names the ACTIVE filter, not just the total. Without it the
            # only evidence of a filter click is rows disappearing, which reads as loss
            # rather than as a view — and a test has nothing new to wait for either.
            # ⚠ EVERY state names its filter, including "all". A heading that reads
            # "Inventory (6)" when unfiltered is a strict PREFIX of the filtered one,
            # so anything matching on it — a test's `should_see`, a player's glance —
            # cannot tell the two apart.
            active = inv_filter["kind"]
            shown = "Everything" if active == "all" else active.capitalize()
            heading = (f"Inventory ({len(rows)}) · showing {shown} "
                       f"({counts.get(active, 0)})")
            with panel(heading):
                if not rows:
                    ui.label("Nothing owned yet — add weapons, armour or goods below."
                             ).classes("text-xs text-gray-500")
                    return
                with ui.row().classes("w-full gap-1 flex-wrap items-center"):
                    for kind in viewmod.INVENTORY_FILTERS:
                        n = counts.get(kind, 0)
                        if kind != "all" and not n:
                            continue        # an empty filter is noise, not a choice
                        label = ("Everything" if kind == "all"
                                 else kind.capitalize()) + f" ({n})"
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
                        for kind in row.kinds:
                            if kind == "artifact":
                                # A plot device has no rating to print — its dots are a
                                # placeholder the model's 1-5 bound demands and its page
                                # prints "(ARTIFACT N/A)". Showing "Artifact •••••" here
                                # would be the one place in the build that states the
                                # fiction as a fact.
                                if row.acquired == artifactsmod.ACQUIRED_LEGENDARY:
                                    tag = "Artifact N/A · by Merit"
                                else:
                                    tag = ("Artifact " + "•" * row.artifact_rating
                                           + (" · bought"
                                              if row.acquired == "purchased" else ""))
                            elif kind in ("weapon", "armor", "ammunition"):
                                continue    # the stat line already says which it is
                            else:
                                tag = kind.capitalize()
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
            rows, unaffordable, icons, group_of = [], set(), {}, {}

            def _add(key, name, kind, cost, summary, full=None, icon="", tags=()):
                afford = validate.gear_affordability(rs, character, cost)
                note = cataloguemod.gear_cost_note(cost, afford)
                bits = [kind] + [x for x in (summary, note) if x]
                # Your own library rows sit in the same list as the books', because
                # that is the point of a library — but they say which they are. The
                # loader tags them (`_merge_custom_gear`); nothing here decides it.
                if "custom" in tags:
                    bits.insert(0, "★ yours")
                rows.append((key, name, " · ".join(bits), full))
                icons[key] = icon
                group_of[key] = kind
                if afford == "unaffordable":
                    unaffordable.add(key)

            for w in sorted(rs.weapon_catalog.values(), key=lambda x: x.name):
                _add(f"weapon:{w.name}", w.name, "Weapon", w.resources_cost,
                     cataloguemod.catalog_weapon_summary(w),
                     icon=cataloguemod.icon_for(w.tags, "sym_o_swords"), tags=w.tags)
            for a in sorted(rs.armor_catalog.values(), key=lambda x: x.name):
                _add(f"armor:{a.name}", a.name, "Armour", a.resources_cost,
                     cataloguemod.catalog_armor_summary(a),
                     icon=cataloguemod.icon_for(a.tags, "security"), tags=a.tags)
            for g in sorted(rs.gear_catalog.values(), key=lambda x: x.name):
                if g.kind != "goods":
                    continue          # services are a price list, never bought (ruling)
                _add(f"goods:{g.id}", g.name, "Goods", g.resources_cost, g.category,
                     g.notes or None, icon=cataloguemod.icon_for(g.tags, "inventory_2"),
                     tags=g.tags)
            # Artifacts are sold ONLY post-lock, and only the ones a book prices —
            # decision 0017: the Artifact Background is the pre-game channel ("to start
            # the game owning", core p.342) and cash is the in-play one. A shop that
            # offered them at chargen would be the hole that decision closes.
            if character.chargen_locked:
                for art in sorted(artifactsmod.purchasable_with_artifact(
                        rs.artifact_catalog), key=lambda x: x.name):
                    if not art.resources_cost:
                        continue
                    # ⚠ The GROUP is the bare word "Artifact": `kind` doubles as the
                    # filter chip, and folding the rating into it ("Artifact •••")
                    # would make one chip per rating.
                    _add(f"artifact:{art.name}", art.name, "Artifact",
                         art.resources_cost, "•" * art.rating, art.description,
                         icon="auto_awesome", tags=art.tags)

            # Making a thing and buying a thing are ONE surface: the custom rows create
            # a blank item of the kind you name, which is what let the per-panel Add
            # buttons be deleted. Artifacts are absent from the custom list at chargen
            # for the same reason they are absent from the shop — decision 0017.
            kinds = {"weapons": "Custom weapon", "armor": "Custom armour",
                     "gear": "Custom goods"}
            if character.chargen_locked:
                kinds["artifacts"] = "Custom artifact"
            cataloguemod.catalogue_dialog(
                pal, "Buy", rows, _buy,
                subtitle=("Everything a book prices, against your Resources, plus your "
                          "own library. Nothing is deducted — the cost is a hint "
                          "(core p.325)."),
                dimmed=unaffordable, icons=icons, group_of=group_of,
                custom_kinds=kinds)

        def _buy(key) -> None:
            if not key:
                return
            kind, _, name = key.partition(":")
            if kind == "custom":
                # "Custom <kind>" — a blank row of that kind, for a player entering
                # something the catalogue does not hold.
                if name == "artifacts":
                    add_artifact()
                else:
                    add_item(name)
                return
            if kind == "weapon":
                add_item("weapons")
                set_weapon(len(character.weapons) - 1, name)
            elif kind == "armor":
                add_item("armor")
                set_armor(len(character.armor) - 1, name)
            elif kind == "goods":
                entry = rs.gear_catalog.get(name)
                character.gear.append(GearEntry(
                    name=entry.name, resources_cost=entry.resources_cost)
                    if entry is not None else GearEntry(name=""))
                refresh_all()
            elif kind == "artifact":
                entry = next((a for a in rs.artifact_catalog.values()
                              if a.name == name), None)
                if entry is None:
                    return
                # Bought with cash, so it is NOT charged to the Artifact Background.
                character.artifacts.append(ArtifactEntry(
                    name=entry.name, rating=entry.rating,
                    acquired=artifactsmod.ACQUIRED_PURCHASED))
                grant_gear(entry.name)
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
                services = [g for g in ruleset.gear_catalog.values()
                            if g.kind == "service"]
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
                        for g in sorted(services, key=lambda g: (g.category, g.name)):
                            if g.category != last_category:
                                last_category = g.category
                                ui.label(g.category).classes(
                                    "text-xs font-bold tracking-wide pt-2"
                                    ).style(f"color:{pal.accent}")
                            afford = validate.gear_affordability(ruleset, character,
                                                                 g.resources_cost)
                            faded = " opacity-50" if afford == "unaffordable" else ""
                            with ui.row().classes(
                                    "w-full items-baseline gap-2 no-wrap" + faded):
                                ui.label("•" * g.resources_cost).classes(
                                    "text-xs w-14 shrink-0")
                                ui.label(g.name).classes(
                                    "text-xs leading-tight flex-1 min-w-0")
                                if g.cash:
                                    ui.label(g.cash).classes(
                                        "text-xs opacity-70 shrink-0 text-right")
                            if g.notes:
                                ui.label(g.notes).classes(
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
