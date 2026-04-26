"""Select one representative realistic package from tournament and matrix results."""

from __future__ import annotations

import argparse

from exploration.candidate_pools import ARCHETYPE_ORDER, POOL_IDS, get_candidate_pool, package_name
from exploration.common import sample_candidate_pool
from exploration.matrix import evaluate_package_candidates, rank_package_evaluations
from exploration.tournament import run_all_tournaments
from exploration.types import CandidatePool, PackageEvaluation
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.reporting import print_directional_rows


def select_package(
    pool: CandidatePool,
    standings_by_arch,
    games: int,
    seed: int,
    top_k: int,
    policy: str,
) -> tuple[PackageEvaluation, list[PackageEvaluation]]:
    """Select one representative package under the requested realistic-pool policy."""
    if policy == "strongest":
        package_ids = {
            archetype: standings_by_arch[archetype][0].candidate_id
            for archetype in ARCHETYPE_ORDER
        }
        evaluations = evaluate_package_candidates(pool, standings_by_arch, games, seed, 1)
        selected = next(item for item in evaluations if item.package_ids == package_ids)
        ranked = rank_package_evaluations(evaluations, "strongest")
        return selected, ranked

    evaluations = evaluate_package_candidates(pool, standings_by_arch, games, seed, top_k)
    ranked = rank_package_evaluations(evaluations, "balanced")
    return ranked[0], ranked


def print_selection(
    pool: CandidatePool,
    selected: PackageEvaluation,
    ranked: list[PackageEvaluation],
    policy: str,
    show_top: int,
) -> None:
    """Render the selected package and top alternatives."""
    print(pool.display_name)
    print(f"Selection policy: {policy}")
    print(f"Selected package: {package_name(selected.package_ids)}")
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
            f"  {package_name(package.package_ids):<100} "
            f"error={package.matrix_error:5.1f}  "
            f"rank_sum={package.rank_sum}  "
            f"identity={package.identity_sum:3.1f}"
        )


def main() -> None:
    """CLI entrypoint for realistic package selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=POOL_IDS, required=True)
    add_agent_mode_arg(parser, default="game-aware-tier-loadout")
    add_games_arg(parser, default=20)
    add_seed_arg(parser)
    parser.add_argument("--top-k", type=int, default=8, help="top tournament variants to consider per archetype")
    parser.add_argument("--show-top", type=int, default=5, help="packages to print after selection")
    parser.add_argument(
        "--policy",
        choices=("balanced", "strongest"),
        default="balanced",
        help="how to choose the representative package from realistic variants",
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
    selected, ranked = select_package(pool, standings_by_arch, args.games, args.seed + 50_000, args.top_k, args.policy)
    print_selection(pool, selected, ranked, args.policy, args.show_top)


if __name__ == "__main__":
    main()
