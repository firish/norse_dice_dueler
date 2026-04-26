"""Cross-archetype package matrix evaluation for realistic exploration pools."""

from __future__ import annotations

import argparse
from itertools import product

from exploration.candidate_pools import ARCHETYPE_ORDER, POOL_IDS, get_candidate_pool, package_name
from exploration.common import package_matrix_error, run_package_matrix, sample_candidate_pool
from exploration.tournament import run_all_tournaments
from exploration.types import CandidatePool, CandidateStanding, PackageEvaluation
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg


def rank_maps(standings_by_arch: dict[str, list[CandidateStanding]]) -> dict[str, dict[str, int]]:
    """Build zero-based tournament rank maps for quick package scoring."""
    return {
        archetype: {row.candidate_id: index for index, row in enumerate(rows)}
        for archetype, rows in standings_by_arch.items()
    }


def evaluate_package_candidates(
    pool: CandidatePool,
    standings_by_arch: dict[str, list[CandidateStanding]],
    games: int,
    seed: int,
    top_k: int,
) -> list[PackageEvaluation]:
    """Evaluate all packages built from the top-k candidates in each archetype."""
    rank_map = rank_maps(standings_by_arch)
    top_ids = {
        archetype: [row.candidate_id for row in rows[:top_k]]
        for archetype, rows in standings_by_arch.items()
    }

    evaluations: list[PackageEvaluation] = []
    for package_index, ids in enumerate(product(*(top_ids[arch] for arch in ARCHETYPE_ORDER))):
        package_ids = dict(zip(ARCHETYPE_ORDER, ids, strict=True))
        results = run_package_matrix(pool, package_ids, games, seed + package_index * 97)
        rank_sum = sum(rank_map[arch][package_ids[arch]] for arch in ARCHETYPE_ORDER)
        evaluations.append(
            PackageEvaluation(
                package_ids=package_ids,
                matrix_error=package_matrix_error(pool, results),
                rank_sum=rank_sum,
                identity_sum=sum(
                    pool.candidates_by_archetype[arch][package_ids[arch]].identity_score
                    for arch in ARCHETYPE_ORDER
                ),
                results=results,
            )
        )
    return evaluations


def rank_package_evaluations(
    evaluations: list[PackageEvaluation],
    policy: str = "balanced",
) -> list[PackageEvaluation]:
    """Rank package evaluations under a simple realistic-pool policy."""
    if policy == "balanced":
        return sorted(evaluations, key=lambda item: (item.matrix_error, item.rank_sum))
    if policy == "strongest":
        return sorted(evaluations, key=lambda item: (item.rank_sum, item.matrix_error))
    raise ValueError(f"Unknown matrix policy: {policy}")


def print_matrix_packages(
    ranked: list[PackageEvaluation],
    *,
    show_top: int,
) -> None:
    """Render the top package candidates."""
    print("Top package options:")
    for package in ranked[:show_top]:
        print(
            f"  {package_name(package.package_ids):<100} "
            f"error={package.matrix_error:5.1f}  "
            f"rank_sum={package.rank_sum}  "
            f"identity={package.identity_sum:3.1f}"
        )


def main() -> None:
    """CLI entrypoint for cross-archetype package matrix evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=POOL_IDS, required=True)
    add_agent_mode_arg(parser, default="game-aware-tier-loadout")
    add_games_arg(parser, default=20)
    add_seed_arg(parser)
    parser.add_argument("--top-k", type=int, default=8, help="top tournament variants to consider per archetype")
    parser.add_argument("--show-top", type=int, default=5, help="packages to print")
    parser.add_argument(
        "--policy",
        choices=("balanced", "strongest"),
        default="balanced",
        help="how to rank the evaluated package matrix candidates",
    )
    parser.add_argument(
        "--sample-per-archetype",
        type=int,
        default=0,
        help="sample this many variants per archetype before tournaments (0 = use all)",
    )
    args = parser.parse_args()

    pool = get_candidate_pool(args.pool, args.agent_mode)
    if args.sample_per_archetype > 0:
        pool = sample_candidate_pool(pool, args.sample_per_archetype, args.seed)

    standings_by_arch = run_all_tournaments(pool, args.games, args.seed)
    evaluations = evaluate_package_candidates(pool, standings_by_arch, args.games, args.seed + 50_000, args.top_k)
    ranked = rank_package_evaluations(evaluations, args.policy)

    print(pool.display_name)
    print(f"Matrix policy: {args.policy}")
    print_matrix_packages(ranked, show_top=args.show_top)


if __name__ == "__main__":
    main()
