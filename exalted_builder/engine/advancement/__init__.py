"""
engine/advancement/__init__.py — post-lock XP advancement transitions. This file is
the public surface of the package.

The chargen counterpart is engine.lifecycle; this is the *post-lock* layer. Each
`raise_*`/`learn_*`/`add_*` is a transition that mutates the Character: it prices
the advance via engine.costs, checks it is legal and affordable, applies the trait
change, and appends an append-only XpEntry to character.xp_log. `undo_last`
reverses the most recent entry (last-in-first-out, so the log and the traits never
drift out of sync). `validate_xp` audits the result.

Not pure — like lifecycle, these are state transitions. Legality that needs the
rules (Charm prerequisites, spell-circle access, Combo composition) is delegated to
engine.validate; the trait caps live here.

⚠ A new `XpEntry.target` domain needs a purchase function AND a branch in
`undo.undo_last` AND a branch in `audit._expected_cost` (and a label in
`ui/view/xp_log.py`). The three are in different modules now.

The domain modules, in dependency order (a module imports only modules above it):

    _base            the XP ledger, the commit helpers, the specialty cap
    undo             undo_last
    traits           raises, the dot track, reductions, Paths, Resonance, specialties
    magic            Charms, spells, Combos, Arrays, Ox-Body, Gifts, variants
    charm_slots      the Alchemical Charm-Slot economy
    thaumaturgy      Arts, Sciences, Rituals, Formulas, Orientations
    audit            _expected_cost and validate_xp
    merit_purchases  Merit and Flaw changes after the lock
    fetters          ghost Fetters and Passions
"""

from __future__ import annotations

# Re-exported, not defined here. `advancement.X` is the ONE public path to every
# name. A domain module is an implementation detail, not a second front door.
# tests/test_package_facades.py fails if a caller reads a name that is not here.
#
# ⚠ A monkeypatch on this module does not reach the domain modules. Patch the
# module that defines the name AND each module that reads it.
from ._base import (           # noqa: F401 — re-exported for callers
    AdvancementError,
    SPECIALTIES_PER_ABILITY,
    add_xp,
    specialty_cap,
    specialty_count,
    xp_available,
    xp_debt,
    xp_spent,
)
from .audit import (           # noqa: F401 — re-exported for callers
    _expected_cost,
    validate_xp,
)
from .charm_slots import (     # noqa: F401 — re-exported for callers
    buy_charm_slot,
    learn_retainer_charm,
    learn_submodule,
    upgrade_charm_slot,
)
from .fetters import (         # noqa: F401 — re-exported for callers
    add_fetter,
    raise_fetter,
    shift_fetter,
    shift_passion,
)
from .magic import (           # noqa: F401 — re-exported for callers
    add_array,
    add_combo,
    learn_charm,
    learn_elemental_power,
    learn_gift,
    learn_martial_arts_charm,
    learn_ox_body,
    learn_spell,
    learn_variant_purchase,
)
from .merit_purchases import ( # noqa: F401 — re-exported for callers
    buy_merit,
    drop_merit,
    gain_flaw,
    gain_merit_or_flaw,
    merit_change_xp,
    mf_change_method,
)
from .thaumaturgy import (     # noqa: F401 — re-exported for callers
    add_thaum_orientation,
    add_thaum_specialty,
    learn_thaum_art,
    learn_thaum_formula,
    learn_thaum_ritual,
    raise_thaum_science,
)
from .traits import (          # noqa: F401 — re-exported for callers
    add_specialty,
    gain_permanent_resonance,
    learn_college,
    learn_craft,
    learn_path,
    lower_ability,
    lower_attribute,
    lower_college,
    lower_craft,
    lower_essence,
    lower_path,
    lower_to,
    lower_virtue,
    lower_willpower,
    raise_ability,
    raise_attribute,
    raise_college,
    raise_craft,
    raise_essence,
    raise_path,
    raise_to,
    raise_virtue,
    raise_willpower,
    refund_to,
    refundable_depth,
    shed_permanent_resonance,
)
from .undo import (            # noqa: F401 — re-exported for callers
    undo_last,
)

