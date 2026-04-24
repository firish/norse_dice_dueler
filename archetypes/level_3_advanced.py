"""Canonical L3 advanced-dice archetype package."""

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


def build_archetypes(agent_mode: str = "rule-based") -> dict[str, Archetype]:
    """Build the approved L3 advanced-dice package using the requested pilots."""
    classes = agent_classes(agent_mode)
    return {
        "AGGRO": Archetype(
            name="AGGRO",
            dice_ids=(
                "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
                "DIE_BERSERKER", "DIE_BERSERKER", "DIE_GAMBLER",
            ),
            gp_ids=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
            agent_cls=classes["AGGRO"],
        ),
        "CONTROL": Archetype(
            name="CONTROL",
            dice_ids=(
                "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
                "DIE_WARDEN", "DIE_WARDEN", "DIE_SKALD",
            ),
            gp_ids=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
            agent_cls=classes["CONTROL"],
        ),
        "ECONOMY": Archetype(
            name="ECONOMY",
            dice_ids=(
                "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
                "DIE_MISER", "DIE_MISER", "DIE_HUNTER",
            ),
            gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
            agent_cls=classes["ECONOMY"],
        ),
    }


ARCHETYPES: dict[str, Archetype] = build_archetypes()
