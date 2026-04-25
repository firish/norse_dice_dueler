"""Shared helpers for exploration package evaluation and symmetric matchups."""

from __future__ import annotations

import numpy as np

from exploration.types import Candidate, CandidatePool
from simulator.common.matchup_runner import matrix_error as compute_matrix_error
from simulator.common.matchup_runner import run_directional_matchup, run_matrix as run_archetype_matrix

ARCHETYPE_ORDER: tuple[str, str, str] = ("AGGRO", "CONTROL", "ECONOMY")


def package_name(package_ids: dict[str, str]) -> str:
    """Return a stable package identifier string in canonical archetype order."""
    return ",".join(package_ids[arch] for arch in ARCHETYPE_ORDER)


def package_from_ids(pool: CandidatePool, package_ids: dict[str, str]) -> dict[str, Candidate]:
    """Resolve one package-id mapping into concrete candidates."""
    return {
        arch: pool.candidates_by_archetype[arch][package_ids[arch]]
        for arch in ARCHETYPE_ORDER
    }


def run_package_matrix(
    pool: CandidatePool,
    package_ids: dict[str, str],
    games: int,
    seed: int,
) -> dict[tuple[str, str], dict[str, float | int]]:
    """Run the off-diagonal matrix for one candidate package."""
    return run_archetype_matrix(
        package_from_ids(pool, package_ids),
        games,
        seed,
        include_mirrors=False,
    )


def package_matrix_error(pool: CandidatePool, results: dict[tuple[str, str], dict[str, float | int]]) -> float:
    """Return the absolute error of one package from the pool's target matrix."""
    return compute_matrix_error(results, pool.targets)


def run_symmetric_matchup(
    candidate_a: Candidate,
    candidate_b: Candidate,
    games: int,
    seed: int,
) -> dict[str, float | int]:
    """Run both seat orders for a head-to-head candidate matchup."""
    result_ab = run_directional_matchup(candidate_a, candidate_b, games, np.random.default_rng(seed))
    result_ba = run_directional_matchup(candidate_b, candidate_a, games, np.random.default_rng(seed + 1))

    a_wins = int(result_ab["p1_wins"]) + int(result_ba["p2_wins"])
    b_wins = int(result_ab["p2_wins"]) + int(result_ba["p1_wins"])
    draws = int(result_ab["draws"]) + int(result_ba["draws"])
    decisive = a_wins + b_wins
    a_rate = (a_wins / decisive * 100.0) if decisive else 50.0
    b_rate = (b_wins / decisive * 100.0) if decisive else 50.0

    return {
        "a_wins": a_wins,
        "b_wins": b_wins,
        "draws": draws,
        "a_rate": a_rate,
        "b_rate": b_rate,
        "avg_rounds": (float(result_ab["avg_rounds"]) + float(result_ba["avg_rounds"])) / 2.0,
        "avg_winner_hp": (float(result_ab["avg_winner_hp"]) + float(result_ba["avg_winner_hp"])) / 2.0,
    }
