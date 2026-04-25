"""Legal candidate pool for the L3 core grammar."""

from __future__ import annotations

from itertools import combinations_with_replacement

from archetypes.common import agent_classes
from exploration.types import Candidate, CandidatePool

TARGETS: dict[tuple[str, str], float] = {
    ("AGGRO", "CONTROL"): 40.0,
    ("CONTROL", "AGGRO"): 60.0,
    ("AGGRO", "ECONOMY"): 60.0,
    ("ECONOMY", "AGGRO"): 40.0,
    ("CONTROL", "ECONOMY"): 40.0,
    ("ECONOMY", "CONTROL"): 60.0,
}

APPROVED_PACKAGE_IDS: dict[str, str] = {
    "AGGRO": "A_CORE_B111",
    "CONTROL": "C_CORE_B111",
    "ECONOMY": "E_CORE_B111",
}
IDENTITY_REQUIREMENTS: dict[str, dict[str, int]] = {
    "AGGRO": {"DIE_BERSERKER": 1},
    "CONTROL": {"DIE_WARDEN": 1},
    "ECONOMY": {"DIE_MISER": 1},
}

CORE_DICE = ("DIE_BERSERKER", "DIE_WARDEN", "DIE_MISER")
GP_IDS_BY_ARCHETYPE = {
    "AGGRO": ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
    "CONTROL": ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
    "ECONOMY": ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
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


def _candidate_name(prefix: str, extra_dice: tuple[str, str, str]) -> str:
    """Encode the 3-die core multiset as BWM counts."""
    berserker_count = extra_dice.count("DIE_BERSERKER")
    warden_count = extra_dice.count("DIE_WARDEN")
    miser_count = extra_dice.count("DIE_MISER")
    return f"{prefix}_CORE_B{berserker_count}{warden_count}{miser_count}"


def _candidate_summary(extra_dice: tuple[str, str, str]) -> str:
    """Build a human-readable dice summary for one candidate."""
    short = {
        "DIE_BERSERKER": "Berserker",
        "DIE_WARDEN": "Warden",
        "DIE_MISER": "Miser",
    }
    parts = [short[die_id] for die_id in extra_dice]
    return "3 Warrior + " + " + ".join(parts)


def _identity_score(archetype: str, extra_dice: tuple[str, str, str]) -> float:
    """Return a simple archetype-fit score based on specialist dice count."""
    return float(extra_dice.count(IDENTITY_DIE_BY_ARCHETYPE[archetype]))


def build_candidate_pool(agent_mode: str = "rule-based") -> CandidatePool:
    """Build the full legal L3 core candidate pool."""
    classes = agent_classes(agent_mode)
    candidates_by_archetype: dict[str, dict[str, Candidate]] = {}

    for archetype, prefix in PREFIX_BY_ARCHETYPE.items():
        candidates: dict[str, Candidate] = {}
        for extra_dice in combinations_with_replacement(CORE_DICE, 3):
            candidate_id = _candidate_name(prefix, extra_dice)
            candidates[candidate_id] = Candidate(
                id=candidate_id,
                archetype=archetype,
                dice_ids=("DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR") + extra_dice,
                gp_ids=GP_IDS_BY_ARCHETYPE[archetype],
                agent_cls=classes[archetype],
                summary=_candidate_summary(extra_dice),
                identity_score=_identity_score(archetype, extra_dice),
            )
        candidates_by_archetype[archetype] = candidates

    return CandidatePool(
        pool_id="l3_core",
        display_name="L3 Core Dice",
        grammar="3 Warrior + any 3 core dice (Berserker / Warden / Miser)",
        targets=TARGETS,
        candidates_by_archetype=candidates_by_archetype,
        approved_package_ids=APPROVED_PACKAGE_IDS,
        identity_requirements=IDENTITY_REQUIREMENTS,
    )
