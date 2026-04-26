"""Curated realistic L3 build space for exploration.

This pool intentionally mixes both core-style and advanced-style L3 loadouts in
one player-facing space. Every candidate is meant to be believable for its
archetype rather than merely legal.
"""

from __future__ import annotations

from archetypes.common import agent_classes
from exploration.types import Candidate, CandidatePool

from ._shared import gp_combo_summary, gp_combo_suffix, specialist_summary

TARGETS: dict[tuple[str, str], float] = {
    ("AGGRO", "CONTROL"): 40.0,
    ("CONTROL", "AGGRO"): 60.0,
    ("AGGRO", "ECONOMY"): 60.0,
    ("ECONOMY", "AGGRO"): 40.0,
    ("CONTROL", "ECONOMY"): 40.0,
    ("ECONOMY", "CONTROL"): 60.0,
}

DICE_VARIANTS_BY_ARCHETYPE: dict[str, dict[str, tuple[str, ...]]] = {
    "AGGRO": {
        "BBB": ("DIE_BERSERKER", "DIE_BERSERKER", "DIE_BERSERKER"),
        "BBM": ("DIE_BERSERKER", "DIE_BERSERKER", "DIE_MISER"),
        "BBW": ("DIE_BERSERKER", "DIE_BERSERKER", "DIE_WARDEN"),
        "BBG": ("DIE_BERSERKER", "DIE_BERSERKER", "DIE_GAMBLER"),
        "BMG": ("DIE_BERSERKER", "DIE_MISER", "DIE_GAMBLER"),
    },
    "CONTROL": {
        "WWW": ("DIE_WARDEN", "DIE_WARDEN", "DIE_WARDEN"),
        "WWM": ("DIE_WARDEN", "DIE_WARDEN", "DIE_MISER"),
        "WMM": ("DIE_WARDEN", "DIE_MISER", "DIE_MISER"),
        "WWS": ("DIE_WARDEN", "DIE_WARDEN", "DIE_SKALD"),
        "WMS": ("DIE_WARDEN", "DIE_MISER", "DIE_SKALD"),
        "WWB": ("DIE_WARDEN", "DIE_WARDEN", "DIE_BERSERKER"),
        "WMB": ("DIE_WARDEN", "DIE_MISER", "DIE_BERSERKER"),
        "WSB": ("DIE_WARDEN", "DIE_SKALD", "DIE_BERSERKER"),
    },
    "ECONOMY": {
        "MMM": ("DIE_MISER", "DIE_MISER", "DIE_MISER"),
        "BMM": ("DIE_BERSERKER", "DIE_MISER", "DIE_MISER"),
        "WMM": ("DIE_WARDEN", "DIE_MISER", "DIE_MISER"),
        "MMH": ("DIE_MISER", "DIE_MISER", "DIE_HUNTER"),
        "WMH": ("DIE_WARDEN", "DIE_MISER", "DIE_HUNTER"),
    },
}

GP_VARIANTS_BY_ARCHETYPE: dict[str, dict[str, tuple[str, str, str]]] = {
    "AGGRO": {
        "CAN": ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        "CASH": ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_MJOLNIRS_WRATH"),
        "PRESS": ("GP_SURTRS_FLAME", "GP_TYRS_JUDGMENT", "GP_MJOLNIRS_WRATH"),
        "DISRUPT": ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_FRIGGS_VEIL"),
    },
    "CONTROL": {
        "CAN": ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        "SUSTAIN": ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_BRAGIS_SONG"),
        "COUNTER": ("GP_AEGIS_OF_BALDR", "GP_TYRS_JUDGMENT", "GP_FRIGGS_VEIL"),
        "STALL": ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_FRIGGS_VEIL"),
        "SPIKED": ("GP_AEGIS_OF_BALDR", "GP_BRAGIS_SONG", "GP_TYRS_JUDGMENT"),
        "FORTRESS": ("GP_AEGIS_OF_BALDR", "GP_BRAGIS_SONG", "GP_FRIGGS_VEIL"),
        "PRESSURE": ("GP_EIRS_MERCY", "GP_BRAGIS_SONG", "GP_TYRS_JUDGMENT"),
        "VEIL": ("GP_EIRS_MERCY", "GP_BRAGIS_SONG", "GP_FRIGGS_VEIL"),
    },
    "ECONOMY": {
        "CAN": ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        "PRESS": ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_TYRS_JUDGMENT"),
        "COUNTER": ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_FRIGGS_VEIL"),
        "SAFE": ("GP_MJOLNIRS_WRATH", "GP_BRAGIS_SONG", "GP_FRIGGS_VEIL"),
    },
}

APPROVED_PACKAGE_IDS: dict[str, str] = {
    "AGGRO": "A_L3R_BBG_GSUFEFR",
    "CONTROL": "C_L3R_WMM_GAEBRTY",
    "ECONOMY": "E_L3R_BMM_GMJGUBR",
}
IDENTITY_REQUIREMENTS: dict[str, dict[str, int]] = {
    "AGGRO": {"DIE_BERSERKER": 1},
    "CONTROL": {"DIE_WARDEN": 1},
    "ECONOMY": {"DIE_MISER": 1},
}
IDENTITY_DIE_BY_ARCHETYPE = {
    "AGGRO": "DIE_BERSERKER",
    "CONTROL": "DIE_WARDEN",
    "ECONOMY": "DIE_MISER",
}
PREFIX_BY_ARCHETYPE = {
    "AGGRO": "A",
    "CONTROL": "C",
    "ECONOMY": "E",
}


def _candidate_name(prefix: str, dice_code: str, gp_ids: tuple[str, str, str]) -> str:
    """Encode one realistic L3 candidate."""
    return f"{prefix}_L3R_{dice_code}_{gp_combo_suffix(gp_ids)}"


def _candidate_summary(extra_dice: tuple[str, ...], gp_ids: tuple[str, str, str]) -> str:
    """Build a readable dice+GP summary."""
    return f"{specialist_summary(extra_dice)} | GPs: {gp_combo_summary(gp_ids)}"


def _identity_score(archetype: str, extra_dice: tuple[str, ...]) -> float:
    """Return a lightweight archetype-fit score based on signature dice count."""
    return float(extra_dice.count(IDENTITY_DIE_BY_ARCHETYPE[archetype]))


def build_candidate_pool(agent_mode: str = "game-aware-tier-loadout") -> CandidatePool:
    """Build the curated realistic L3 candidate pool."""
    classes = agent_classes(agent_mode)
    candidates_by_archetype: dict[str, dict[str, Candidate]] = {}

    for archetype, prefix in PREFIX_BY_ARCHETYPE.items():
        candidates: dict[str, Candidate] = {}
        for dice_code, extra_dice in DICE_VARIANTS_BY_ARCHETYPE[archetype].items():
            for _, gp_ids in GP_VARIANTS_BY_ARCHETYPE[archetype].items():
                candidate_id = _candidate_name(prefix, dice_code, gp_ids)
                candidates[candidate_id] = Candidate(
                    id=candidate_id,
                    archetype=archetype,
                    dice_ids=("DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR") + extra_dice,
                    gp_ids=gp_ids,
                    agent_cls=classes[archetype],
                    summary=_candidate_summary(extra_dice, gp_ids),
                    identity_score=_identity_score(archetype, extra_dice),
                )
        candidates_by_archetype[archetype] = candidates

    return CandidatePool(
        pool_id="l3_realistic",
        display_name="L3 Realistic Variants",
        grammar="Curated realistic L3 loadouts (core and advanced) plus curated archetype GP trios",
        targets=TARGETS,
        candidates_by_archetype=candidates_by_archetype,
        approved_package_ids=APPROVED_PACKAGE_IDS,
        identity_requirements=IDENTITY_REQUIREMENTS,
    )
