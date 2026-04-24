"""Canonical L3 core-dice package shared by the benchmark harnesses.

What this file does:
  - Defines the approved L3A package chosen from the legal core-dice grammar.
  - Exposes the canonical target matrix for L3 core validation.

What this file does not do:
  - Enumerate every legal core-dice package for search.
  - Perform ranking or balancing sweeps.
"""

from __future__ import annotations

from archetypes.common import agent_classes
from simulator.common.harness_types import Archetype

TARGETS: dict[tuple[str, str], float] = {
    ("AGGRO", "CONTROL"): 40.0,
    ("CONTROL", "AGGRO"): 60.0,
    ("AGGRO", "ECONOMY"): 60.0,
    ("ECONOMY", "AGGRO"): 40.0,
    ("CONTROL", "ECONOMY"): 40.0,
    ("ECONOMY", "CONTROL"): 60.0,
}

APPROVED_PACKAGE_NAME = "A_CORE_B111,C_CORE_B111,E_CORE_B111"


def build_archetypes(agent_mode: str = "rule-based") -> dict[str, Archetype]:
    """Build the approved L3A core-dice package using the requested pilot family."""
    classes = agent_classes(agent_mode)
    shared_dice = (
        "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        "DIE_BERSERKER", "DIE_WARDEN", "DIE_MISER",
    )
    return {
        "AGGRO": Archetype(
            name="AGGRO",
            dice_ids=shared_dice,
            gp_ids=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
            agent_cls=classes["AGGRO"],
        ),
        "CONTROL": Archetype(
            name="CONTROL",
            dice_ids=shared_dice,
            gp_ids=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
            agent_cls=classes["CONTROL"],
        ),
        "ECONOMY": Archetype(
            name="ECONOMY",
            dice_ids=shared_dice,
            gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
            agent_cls=classes["ECONOMY"],
        ),
    }


ARCHETYPES: dict[str, Archetype] = build_archetypes()
