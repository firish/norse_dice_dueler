"""Registry and helpers for legal exploration candidate pools."""

from __future__ import annotations

from exploration.common import ARCHETYPE_ORDER, package_from_ids, package_name
from exploration.types import CandidatePool

from .l3_advanced import APPROVED_PACKAGE_IDS as L3_ADVANCED_APPROVED_PACKAGE_IDS
from .l3_advanced import build_candidate_pool as build_l3_advanced_pool
from .l3_core import APPROVED_PACKAGE_IDS as L3_CORE_APPROVED_PACKAGE_IDS
from .l3_core import build_candidate_pool as build_l3_core_pool

POOL_BUILDERS = {
    "l3_core": build_l3_core_pool,
    "l3_advanced": build_l3_advanced_pool,
}


def get_candidate_pool(pool_id: str, agent_mode: str) -> CandidatePool:
    """Build the requested exploration pool with the chosen pilot family."""
    if pool_id not in POOL_BUILDERS:
        raise ValueError(f"Unknown candidate pool: {pool_id}")
    return POOL_BUILDERS[pool_id](agent_mode)


__all__ = [
    "ARCHETYPE_ORDER",
    "L3_ADVANCED_APPROVED_PACKAGE_IDS",
    "L3_CORE_APPROVED_PACKAGE_IDS",
    "get_candidate_pool",
    "package_from_ids",
    "package_name",
]
