"""
ui/picker.py — NiceGUI charm-tree picker (Cytoscape).

Renders a Charm category's prerequisite graph with Cytoscape.js. Nodes are
colour-coded owned / available / locked (from view.build_charm_graph, which asks
the engine). Tapping a node toggles ownership: an available Charm is learned, an
owned one is dropped; locked Charms refuse with a notice. A live readout re-runs
validation on each change. Save writes JSON via persistence.

No game logic here: the toggle asks engine.validate.meets_charm_requirements, and
node states come from the engine. Cytoscape is loaded from a CDN, so the browser
needs network access.

Run:
    python -m exalted_builder.ui.picker [path/to/foo.character.json] [--show] [--port N]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from nicegui import ui

from .. import persistence, rules_db
from ..engine import validate
from ..models.character import Character
from ..models.rules import RuleSet
from . import view as viewmod

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "exalted_builder" / "data"
_EXAMPLE = _REPO_ROOT / "examples" / "ashes-of-dawn.character.json"
_ACCENT = "#8a5a1a"
_CYTOSCAPE_CDN = "https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js"

_STYLE = [
    {"selector": "node", "style": {
        "label": "data(label)", "font-size": "7px", "text-wrap": "wrap",
        "text-max-width": "72px", "text-valign": "bottom", "text-margin-y": 3,
        "color": "#3a2e1f", "width": 16, "height": 16,
        "background-color": "#cbd5e1", "border-width": 1, "border-color": "#94a3b8"}},
    {"selector": "node.owned", "style": {
        "background-color": _ACCENT, "border-color": "#5b3a10", "width": 22, "height": 22,
        "font-weight": "bold"}},
    {"selector": "node.available", "style": {
        "background-color": "#bbf7d0", "border-color": "#15803d", "border-width": 2}},
    {"selector": "node.locked", "style": {
        "background-color": "#e5e7eb", "border-color": "#cbd5e1", "color": "#9ca3af"}},
    {"selector": "edge", "style": {
        "width": 1, "line-color": "#9ca3af", "target-arrow-color": "#9ca3af",
        "target-arrow-shape": "triangle", "curve-style": "bezier", "arrow-scale": 0.7}},
]


def _elements(graph: viewmod.CharmGraph) -> list[dict]:
    nodes = [{"data": {"id": n.id, "label": n.label}, "classes": n.state} for n in graph.nodes]
    edges = [{"data": {"id": f"{s}__{t}", "source": s, "target": t}} for s, t in graph.edges]
    return nodes + edges


def build_picker(ruleset: RuleSet, character: Character, save_path: Path) -> None:
    categories = sorted({c.category for c in ruleset.charms.values()})
    state = {"category": "melee" if "melee" in categories else (categories[0] if categories else "")}

    # ---- live readout ----------------------------------------------------- #
    @ui.refreshable
    def readout() -> None:
        view = viewmod.build_sheet_view(ruleset, character)
        bp = next((i.message for i in view.issues if i.code == "bonus-points"), "")
        errors = [i for i in view.issues if i.severity == "error"]
        ui.label(f"Charms: {len(character.charms)}").classes("text-sm font-semibold").style(f"color:{_ACCENT}")
        ui.label(bp).classes("text-xs text-gray-600")
        ui.separator()
        ui.label("✓ Legal" if not errors else f"✗ {len(errors)} error(s)").classes("text-sm font-bold").style(
            "color:#15803d" if not errors else "color:#b91c1c")
        for issue in view.issues:
            if issue.code == "bonus-points":
                continue
            color = {"error": "text-red-600", "warning": "text-amber-600"}.get(issue.severity, "text-gray-500")
            ui.label(f"• {issue.message}").classes(f"text-xs {color}")

    # ---- graph (re)build / update ---------------------------------------- #
    def init_graph() -> None:
        graph = viewmod.build_charm_graph(ruleset, character, state["category"])
        ui.run_javascript(f"""
        (function() {{
          function go() {{
            if (!window.cytoscape) return setTimeout(go, 50);
            var el = document.getElementById('charm-graph');
            if (!el) return setTimeout(go, 50);
            if (window.cy) {{ window.cy.destroy(); }}
            window.cy = cytoscape({{
              container: el,
              elements: {json.dumps(_elements(graph))},
              style: {json.dumps(_STYLE)},
              layout: {{name: 'breadthfirst', directed: true, roots: {json.dumps(graph.roots)},
                        spacingFactor: 1.1, padding: 16}},
            }});
            window.cy.on('tap', 'node', function(e) {{ emitEvent('charm_toggle', {{id: e.target.id()}}); }});
          }}
          go();
        }})();
        """)

    def update_graph() -> None:
        graph = viewmod.build_charm_graph(ruleset, character, state["category"])
        states = {n.id: n.state for n in graph.nodes}
        ui.run_javascript(f"""
        if (window.cy) {{
          var s = {json.dumps(states)};
          Object.keys(s).forEach(function(id) {{
            var n = window.cy.getElementById(id);
            if (n) n.classes(s[id]);
          }});
        }}
        """)
        readout.refresh()

    def toggle(charm_id: str) -> None:
        if charm_id in character.charms:
            character.charms.remove(charm_id)
            ui.notify(f"Removed {ruleset.charms[charm_id].name}", type="info")
        else:
            charm = ruleset.charms.get(charm_id)
            if charm is None:
                return
            if validate.meets_charm_requirements(ruleset, character, charm):
                character.charms.append(charm_id)
                ui.notify(f"Learned {charm.name}", type="positive")
            else:
                ui.notify(f"{charm.name}: prerequisites not met", type="warning")
                return
        update_graph()

    def set_category(value: str) -> None:
        state["category"] = value
        init_graph()
        readout.refresh()

    def save() -> None:
        persistence.save_character(character, save_path)
        ui.notify(f"Saved to {save_path}", type="positive")

    ui.on("charm_toggle", lambda e: toggle(e.args["id"]))

    # ---- layout ----------------------------------------------------------- #
    ui.add_head_html(f'<script src="{_CYTOSCAPE_CDN}"></script>')
    ui.add_head_html("<style>body{background:#f7f1e3;color:#3a2e1f;}</style>")

    with ui.row().classes("w-full max-w-7xl mx-auto gap-4 p-4 items-start no-wrap"):
        with ui.column().classes("flex-1 gap-2"):
            with ui.row().classes("w-full items-center justify-between"):
                ui.label("Charm-Tree Picker").classes("text-xl font-bold")
                with ui.row().classes("items-center gap-3"):
                    ui.select(categories, value=state["category"], label="Category",
                              on_change=lambda e: set_category(e.value)).classes("w-40")
                    ui.button("Save", icon="save", on_click=save).props("color=brown")
            with ui.row().classes("gap-4 text-xs items-center"):
                ui.html('<span style="color:#8a5a1a">●</span> owned')
                ui.html('<span style="color:#15803d">●</span> available')
                ui.html('<span style="color:#9ca3af">●</span> locked (tap to see why in the panel)')
            ui.html('<div id="charm-graph" style="height:640px;width:100%;'
                    'border:1px solid rgba(138,90,26,0.3);border-radius:8px;background:#fffdf7"></div>')
        with ui.column().classes("w-72 gap-2 sticky top-4"):
            with ui.card().classes("w-full p-3 bg-amber-50/60 border border-amber-900/30"):
                ui.label("Live Validation").classes("text-sm font-bold tracking-widest").style(f"color:{_ACCENT}")
                readout()

    # defer the first graph build until the client is connected and the div exists
    ui.timer(0.1, init_graph, once=True)


def load(character_path: Path | str | None = None) -> tuple[RuleSet, Character, Path]:
    ruleset = rules_db.load_ruleset(_DATA_DIR)
    path = Path(character_path) if character_path else _EXAMPLE
    character = persistence.load_character(path)
    return ruleset, character, path


def main() -> None:
    parser = argparse.ArgumentParser(description="Exalted 1e charm-tree picker")
    parser.add_argument("character", nargs="?", help="path to a .character.json (defaults to the example)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--show", action="store_true")
    args = parser.parse_args()

    ruleset, character, path = load(args.character)

    @ui.page("/")
    def index() -> None:
        build_picker(ruleset, character, path)

    ui.run(title=f"Exalted 1e — charms: {character.name or path.stem}",
           reload=False, show=args.show, port=args.port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
