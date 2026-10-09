"""
ui/view/__init__.py — the presenter: it makes a display-ready view model from a
RuleSet and a Character. This file is the public surface of the package.

The presenter is the seam between the engine and the rendering layers. It calls the
engine (derive, validate), changes Charm and spell ids to names, groups the
abilities, and gives plain dataclasses that a shell can show directly. It contains
no game logic and imports no UI toolkit. The NiceGUI shell (`ui/`), the Qt shell
(`qt/`) and the hosted server (`server/`) all read it.

The domain modules, in dependency order (a module imports only modules above it):

    _base            the shared row types and formatters
    dice_pools       the base dice pools (decision 0016)
    inventory        the gear stat lines, the inventory, the Buy shop
    charm_trees      the Charm and spell detail cards, the Charm tree graph
    spell_picker     the spell picker rows
    xp_log           the XP log rows
    sheet            the sheet view model and its helpers
    packages         the variant-menu packages
    augments         the Alchemical Augmentation groups
    play_state       the play capacities and the party card
    adversary_rows   the adversary cards and the catalogue picker rows
    roller           the dice roller (decision 0019)
    batch_roll       the batch roll of the Storyteller
    custom_forms     the custom content forms and library rows
    combo_rows, tabs, origins, thaumaturgy, house_rules, trait_info,
    advantages_text  (these import no sibling module)
"""

from __future__ import annotations

# Re-exported, not defined here. `view.X` is the ONE public path to every presenter
# name. A domain module is an implementation detail, not a second front door.
# tests/test_package_facades.py fails if a caller reads a name that is not here.
#
# ⚠ A monkeypatch on this module does not reach the domain modules. Patch the
# module that defines the name AND each module that reads it.
from ._base import (           # noqa: F401 — re-exported for callers
    CharmDetail,
    CharmGraph,
    CharmNode,
    CharmRow,
    PathPowerRow,
    PathRow,
    SpellPickRow,
    SpellRow,
    TraitRow,
    _charm_description,
    _cost_str,
    source_label,
)
from .advantages_text import ( # noqa: F401 — re-exported for callers
    CUSTOM_MERIT_NOTE,
    DEMESNE_TOGGLE_LABEL,
    MERIT_EXPERIENCE_PRICING_NOTE,
    fetter_budget_text,
    flaw_excess_note,
    flaw_room_note,
    merit_method_note,
    merit_side_label,
    xp_debt_note,
)
from .adversary_rows import (  # noqa: F401 — re-exported for callers
    AllyBox,
    AllyView,
    _ability_label,
    adversary_picker_rows,
    ally_view,
    character_ally_view,
    merit_requirement_line,
    picker_names,
    summary_line,
    trait_map_line,
)
from .augments import (        # noqa: F401 — re-exported for callers
    AugmentEntry,
    AugmentGroup,
    augmentation_category,
    build_augmentation_view,
)
from .batch_roll import (      # noqa: F401 — re-exported for callers
    BatchRoll,
    BatchRow,
    MAX_BATCH_REPEATS,
    batch_roster,
    batch_rows,
    new_batch_state,
    roll_batch,
    set_batch_count,
    set_batch_included,
    set_batch_times,
)
from .charm_trees import (     # noqa: F401 — re-exported for callers
    SpellDetail,
    UNKEYED_SUBTREE,
    build_charm_detail,
    build_charm_graph,
    build_spell_detail,
    charm_on_splat_page,
    charm_prerequisite_links,
    charm_requirements,
    virtue_split,
)
from .combo_rows import (      # noqa: F401 — re-exported for callers
    ArrayCharmRow,
    ArrayRow,
    ArrayView,
    ComboCharmRow,
    ComboRow,
    ComboView,
    SubmoduleRow,
    build_array_view,
    build_combo_view,
    build_submodule_rows,
    has_combos_tab,
    uses_arrays,
)
from .custom_forms import (    # noqa: F401 — re-exported for callers
    CHARM_DURATIONS,
    CUSTOM_GEAR_FIELDS,
    CUSTOM_GEAR_KINDS,
    CUSTOM_KINDS,
    CustomKind,
    CustomRow,
    DRAFT_NODE_ID,
    GearField,
    HEALTH_TYPE_OPTIONS,
    NEW_STYLE,
    build_custom_gear_library,
    build_custom_library,
    charm_element_options,
    charm_tier_options,
    charm_tree_title,
    custom_category_options,
    custom_charm_form,
    custom_charm_payload,
    custom_charm_preview,
    custom_export,
    custom_gear_form,
    custom_gear_payload,
    custom_gear_summary,
    custom_prerequisite_options,
    custom_ritual_form,
    custom_ritual_payload,
    custom_spell_form,
    custom_spell_payload,
    extra_req_trait_options,
    unlock_warning,
)
from .dice_pools import (      # noqa: F401 — re-exported for callers
    InitiativeView,
    PoolChoicesView,
    PoolRow,
    PoolSidebarView,
    PoolView,
    build_custom_pool,
    build_initiative,
    build_pool_choices,
    build_pool_sidebar,
    build_pool_view,
    clamp_pool_selection,
    pool_mobility_lines,
    pool_roll_options,
    pool_trait_options,
    wielded_index,
)
from .house_rules import (     # noqa: F401 — re-exported for callers
    HOUSE_RULE_SCOPES,
    HouseRuleRow,
    _HOUSE_RULES,
    build_house_rules,
    build_table_house_rules,
    house_rule_differences,
    house_rule_setting_label,
)
from .inventory import (       # noqa: F401 — re-exported for callers
    INVENTORY_FILTERS,
    InventoryRow,
    ShopRow,
    _AFFORDABILITY_NOTE,
    armor_stat_line,
    artifacts_also_counted,
    artifacts_bought_note,
    artifacts_header,
    catalog_armor_summary,
    catalog_weapon_summary,
    filter_inventory,
    gear_cost_note,
    inventory_counts,
    inventory_filter_label,
    inventory_heading,
    inventory_row_tags,
    inventory_rows,
    service_rows,
    shop_custom_kinds,
    shop_rows,
    weapon_stat_line,
)
from .origins import (         # noqa: F401 — re-exported for callers
    _ORIGIN_UPBRINGINGS,
    _SPLAT_ORIGINS,
    _heritage_uses_origin,
    _origin_options,
    upbringing_options,
)
from .packages import (        # noqa: F401 — re-exported for callers
    PackageHeld,
    PackageMenu,
    PackagePick,
    build_package_menu,
    package_menu_kind,
    prune_package_selection,
)
from .play_state import (      # noqa: F401 — re-exported for callers
    PartyCardView,
    PlayHealthBox,
    PlayView,
    build_party_card_view,
    build_play_view,
    committed_note,
    free_motes_note,
    spent_motes,
    worst_penalty,
)
from .roller import (          # noqa: F401 — re-exported for callers
    ROLLER_CAVEAT,
    ROLL_LOG_LENGTH,
    RollEntry,
    RollFace,
    new_roller_state,
    previous_rolls_label,
    roll_detail,
    roll_dice,
    roll_log_split,
)
from .sheet import (           # noqa: F401 — re-exported for callers
    DEFAULT_ABILITY_GROUPS,
    SheetView,
    SlotBudget,
    StyleView,
    _DOTS,
    ability_group_defs,
    attribute_budget_summary,
    attunement_mark,
    background_ladder,
    background_rung,
    build_sheet_view,
    calling_ability_marks,
    charm_slot_budget,
    college_rows,
    default_merit_tier,
    granted_charm_rows,
    is_calling_charm,
    merit_option_label,
    merit_price,
    merit_rows,
    merit_tier_label,
    repeatable_cap_trait,
    specialty_groups,
    style_for_category,
    thaumaturgy_rows,
    uses_caste_favored_attributes,
)
from .spell_picker import (    # noqa: F401 — re-exported for callers
    CIRCLE_DISPLAY_ORDER,
    build_spell_picker,
)
from .tabs import (            # noqa: F401 — re-exported for callers
    _TABS,
    resolve_tab,
    visible_tabs,
)
from .thaumaturgy import (     # noqa: F401 — re-exported for callers
    ElementalPowerRow,
    ElementalPowerView,
    ThaumArtRow,
    ThaumEntryRow,
    ThaumOwnedRow,
    ThaumPickerView,
    ThaumScienceLevelRow,
    ThaumScienceRow,
    ThaumSpecialtyRow,
    _thaum_entry_detail,
    build_elemental_power_picker,
    build_thaum_picker,
)
from .trait_info import (      # noqa: F401 — re-exported for callers
    TraitInfo,
    ability_info,
    attribute_info,
    virtue_info,
)
from .xp_log import (          # noqa: F401 — re-exported for callers
    XpLogRow,
    build_xp_log,
)

# Moved to the engine on 2026-08-22, and re-exported for the existing callers.
# `ui/picker.py` reads `view._style_label`, and
# `test_no_second_style_label_generator_disagrees_with_the_authored_name` asserts it.
from ...engine.camp import (CampCharmOption, CampChoiceOption,  # noqa: F401
                            CampChoiceView, CampView, build_camp_view, requires_camp)
from ...engine.labels import _label, _style_label  # noqa: F401
from ...engine.validate import _charm_name  # noqa: F401
