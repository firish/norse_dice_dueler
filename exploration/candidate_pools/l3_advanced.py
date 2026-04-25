"""Legal candidate pool for the L3 advanced grammar."""

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
    "AGGRO": "A_ADV_C200_GAMBLER",
    "CONTROL": "C_ADV_C020_SKALD",
    "ECONOMY": "E_ADV_C002_HUNTER",
}
IDENTITY_REQUIREMENTS: dict[str, dict[str, int]] = {
    "AGGRO": {"DIE_BERSERKER": 1, "DIE_GAMBLER": 1},
    "CONTROL": {"DIE_WARDEN": 1, "DIE_SKALD": 1},
    "ECONOMY": {"DIE_MISER": 1, "DIE_HUNTER": 1},
}

CORE_DICE = ("DIE_BERSERKER", "DIE_WARDEN", "DIE_MISER")
ADVANCED_DICE = ("DIE_GAMBLER", "DIE_SKALD", "DIE_HUNTER")
ADVANCED_LABELS = {
    "DIE_GAMBLER": "GAMBLER",
    "DIE_SKALD": "SKALD",
    "DIE_HUNTER": "HUNTER",
}
GP_IDS_BY_ARCHETYPE = {
    "AGGRO": ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
    "CONTROL": ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
    "ECONOMY": ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
}
IDENTITY_CORE_BY_ARCHETYPE = {
    "AGGRO": "DIE_BERSERKER",
    "CONTROL": "DIE_WARDEN",
    "ECONOMY": "DIE_MISER",
}
IDENTITY_ADVANCED_BY_ARCHETYPE = {
    "AGGRO": "DIE_GAMBLER",
    "CONTROL": "DIE_SKALD",
    "ECONOMY": "DIE_HUNTER",
}
PREFIX_BY_ARCHETYPE = {
    "AGGRO": "A",
    "CONTROL": "C",
    "ECONOMY": "E",
}


def _candidate_name(prefix: str, core_dice: tuple[str, str], advanced_die: str) -> str:
    """Encode one legal advanced candidate."""
    berserker_count = core_dice.count("DIE_BERSERKER")
    warden_count = core_dice.count("DIE_WARDEN")
    miser_count = core_dice.count("DIE_MISER")
    return f"{prefix}_ADV_C{berserker_count}{warden_count}{miser_count}_{ADVANCED_LABELS[advanced_die]}"


def _candidate_summary(core_dice: tuple[str, str], advanced_die: str) -> str:
    """Build a human-readable dice summary for one advanced candidate."""
    short = {
        "DIE_BERSERKER": "Berserker",
        "DIE_WARDEN": "Warden",
        "DIE_MISER": "Miser",
        "DIE_GAMBLER": "Gambler",
        "DIE_SKALD": "Skald",
        "DIE_HUNTER": "Hunter",
    }
    parts = [short[die_id] for die_id in core_dice] + [short[advanced_die]]
    return "3 Warrior + " + " + ".join(parts)


def _identity_score(archetype: str, core_dice: tuple[str, str], advanced_die: str) -> float:
    """Return a simple archetype-fit score based on matching core and advanced dice."""
    score = float(core_dice.count(IDENTITY_CORE_BY_ARCHETYPE[archetype]))
    if advanced_die == IDENTITY_ADVANCED_BY_ARCHETYPE[archetype]:
        score += 1.0
    return score


def build_candidate_pool(agent_mode: str = "rule-based") -> CandidatePool:
    """Build the full legal L3 advanced candidate pool."""
    classes = agent_classes(agent_mode)
    candidates_by_archetype: dict[str, dict[str, Candidate]] = {}

    for archetype, prefix in PREFIX_BY_ARCHETYPE.items():
        candidates: dict[str, Candidate] = {}
        for core_dice in combinations_with_replacement(CORE_DICE, 2):
            for advanced_die in ADVANCED_DICE:
                candidate_id = _candidate_name(prefix, core_dice, advanced_die)
                candidates[candidate_id] = Candidate(
                    id=candidate_id,
                    archetype=archetype,
                    dice_ids=("DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR") + core_dice + (advanced_die,),
                    gp_ids=GP_IDS_BY_ARCHETYPE[archetype],
                    agent_cls=classes[archetype],
                    summary=_candidate_summary(core_dice, advanced_die),
                    identity_score=_identity_score(archetype, core_dice, advanced_die),
                )
        candidates_by_archetype[archetype] = candidates

    return CandidatePool(
        pool_id="l3_advanced",
        display_name="L3 Advanced Dice",
        grammar="3 Warrior + any 2 core dice + any 1 advanced die",
        targets=TARGETS,
        candidates_by_archetype=candidates_by_archetype,
        approved_package_ids=APPROVED_PACKAGE_IDS,
        identity_requirements=IDENTITY_REQUIREMENTS,
    )
