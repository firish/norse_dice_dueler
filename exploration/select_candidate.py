"""Generic candidate selector for exploration pools.

Selection happens in two stages:
  1. run intra-archetype tournaments to identify strong legal candidates
  2. evaluate packages built from the top-k candidates in each archetype
"""

from __future__ import annotations

import argparse
from itertools import product

from exploration.candidate_pools import ARCHETYPE_ORDER, get_candidate_pool, package_name
from exploration.common import package_matrix_error, package_name as format_package_name, run_package_matrix
from exploration.stress_test import print_stress_test, run_stress_test
from exploration.tournament import run_all_tournaments
from exploration.types import CandidatePool, CandidateStanding, PackageEvaluation
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.reporting import print_directional_rows


def _rank_maps(standings_by_arch: dict[str, list[CandidateStanding]]) -> dict[str, dict[str, int]]:
    """Build zero-based tournament rank maps for quick package scoring."""
    return {
        archetype: {row.candidate_id: index for index, row in enumerate(rows)}
        for archetype, rows in standings_by_arch.items()
    }


def _candidate_satisfies_identity(pool: CandidatePool, archetype: str, candidate_id: str) -> bool:
    """Return whether one candidate satisfies the pool's identity requirements."""
    candidate = pool.candidates_by_archetype[archetype][candidate_id]
    requirements = pool.identity_requirements.get(archetype, {})
    return all(candidate.dice_ids.count(die_id) >= count for die_id, count in requirements.items())


def _package_satisfies_identity(pool: CandidatePool, package_ids: dict[str, str]) -> bool:
    """Return whether every candidate in the package satisfies identity requirements."""
    return all(_candidate_satisfies_identity(pool, archetype, package_ids[archetype]) for archetype in ARCHETYPE_ORDER)


def _identity_filtered_standings(
    pool: CandidatePool,
    standings_by_arch: dict[str, list[CandidateStanding]],
) -> dict[str, list[CandidateStanding]]:
    """Keep only standings rows whose candidates satisfy identity requirements."""
    filtered: dict[str, list[CandidateStanding]] = {}
    for archetype, rows in standings_by_arch.items():
        filtered_rows = [
            row for row in rows
            if _candidate_satisfies_identity(pool, archetype, row.candidate_id)
        ]
        if not filtered_rows:
            raise ValueError(f"No identity-valid candidates found for {archetype}")
        filtered[archetype] = filtered_rows
    return filtered


def evaluate_package_candidates(
    pool: CandidatePool,
    standings_by_arch: dict[str, list[CandidateStanding]],
    games: int,
    seed: int,
    top_k: int,
) -> list[PackageEvaluation]:
    """Evaluate all packages built from the top-k candidates in each archetype."""
    rank_maps = _rank_maps(standings_by_arch)
    top_ids = {
        archetype: [row.candidate_id for row in rows[:top_k]]
        for archetype, rows in standings_by_arch.items()
    }

    evaluations: list[PackageEvaluation] = []
    for package_index, ids in enumerate(product(*(top_ids[arch] for arch in ARCHETYPE_ORDER))):
        package_ids = dict(zip(ARCHETYPE_ORDER, ids, strict=True))
        results = run_package_matrix(pool, package_ids, games, seed + package_index * 97)
        rank_sum = sum(rank_maps[arch][package_ids[arch]] for arch in ARCHETYPE_ORDER)
        identity_sum = sum(
            pool.candidates_by_archetype[arch][package_ids[arch]].identity_score
            for arch in ARCHETYPE_ORDER
        )
        evaluations.append(
            PackageEvaluation(
                package_ids=package_ids,
                matrix_error=package_matrix_error(pool, results),
                rank_sum=rank_sum,
                identity_sum=identity_sum,
                results=results,
            )
        )
    return evaluations


def select_package(
    pool: CandidatePool,
    standings_by_arch: dict[str, list[CandidateStanding]],
    games: int,
    seed: int,
    top_k: int,
    policy: str,
) -> tuple[PackageEvaluation, list[PackageEvaluation]]:
    """Select one package using the requested tournament/package policy."""
    if policy == "strongest":
        strongest_ids = {
            archetype: standings_by_arch[archetype][0].candidate_id
            for archetype in ARCHETYPE_ORDER
        }
        results = run_package_matrix(pool, strongest_ids, games, seed)
        selected = PackageEvaluation(
            package_ids=strongest_ids,
            matrix_error=package_matrix_error(pool, results),
            rank_sum=0,
            identity_sum=sum(
                pool.candidates_by_archetype[arch][strongest_ids[arch]].identity_score
                for arch in ARCHETYPE_ORDER
            ),
            results=results,
        )
        return selected, [selected]

    evaluations = evaluate_package_candidates(pool, standings_by_arch, games, seed, top_k)

    if policy == "balanced":
        ranked = sorted(evaluations, key=lambda item: (item.matrix_error, item.rank_sum, -item.identity_sum))
    elif policy == "identity":
        identity_standings = _identity_filtered_standings(pool, standings_by_arch)
        identity_evaluations = evaluate_package_candidates(pool, identity_standings, games, seed, top_k)
        identity_evaluations = [
            item for item in identity_evaluations
            if _package_satisfies_identity(pool, item.package_ids)
        ]
        if not identity_evaluations:
            raise ValueError("No identity-valid package found in the current top-k search space")
        ranked = sorted(identity_evaluations, key=lambda item: (-item.identity_sum, item.matrix_error, item.rank_sum))
    else:
        raise ValueError(f"Unknown selection policy: {policy}")

    return ranked[0], ranked


def print_selection(
    pool: CandidatePool,
    selected: PackageEvaluation,
    ranked: list[PackageEvaluation],
    policy: str,
    show_top: int,
) -> None:
    """Render one selected package and the top alternatives."""
    print(pool.display_name)
    print(f"Selection policy: {policy}")
    print(f"Selected package: {format_package_name(selected.package_ids)}")
    for archetype in ARCHETYPE_ORDER:
        candidate = pool.candidates_by_archetype[archetype][selected.package_ids[archetype]]
        print(f"  {archetype:<8} {candidate.id}")
        print(f"    {candidate.summary}")
    print_directional_rows(selected.results)
    print(
        f"  Matrix error: {selected.matrix_error:.1f}  "
        f"rank_sum={selected.rank_sum}  "
        f"identity_sum={selected.identity_sum:.1f}"
    )

    print()
    print("Top package options:")
    for package in ranked[:show_top]:
        print(
            f"  {package_name(package.package_ids):<80} "
            f"error={package.matrix_error:5.1f}  "
            f"rank_sum={package.rank_sum}  "
            f"identity={package.identity_sum:3.1f}"
        )


def main() -> None:
    """CLI entrypoint for generic candidate selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=("l3_core", "l3_advanced"), required=True)
    add_agent_mode_arg(parser, default="game-aware-tier")
    add_games_arg(parser, default=40)
    add_seed_arg(parser)
    parser.add_argument("--top-k", type=int, default=3, help="top tournament candidates to consider per archetype")
    parser.add_argument("--show-top", type=int, default=5, help="packages to print after selection")
    parser.add_argument(
        "--policy",
        choices=("strongest", "balanced", "identity"),
        default="balanced",
        help="how to choose the package that should graduate into the benchmark harness",
    )
    parser.add_argument(
        "--stress-games",
        type=int,
        default=20,
        help="games per symmetric answer-check pairing after selection",
    )
    args = parser.parse_args()

    pool = get_candidate_pool(args.pool, args.agent_mode)
    standings_by_arch = run_all_tournaments(pool, args.games, args.seed)
    selected, ranked = select_package(pool, standings_by_arch, args.games, args.seed + 50_000, args.top_k, args.policy)
    print_selection(pool, selected, ranked, args.policy, args.show_top)

    print()
    print("Stress check:")
    stress_report = run_stress_test(pool, selected.package_ids, args.stress_games, args.seed + 90_000)
    print_stress_test(pool, selected.package_ids, stress_report)


if __name__ == "__main__":
    main()
