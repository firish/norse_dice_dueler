"""Run the full realistic exploration flow once and present the key findings.

Flow:
  1. tournament
  2. matrix
  3. selection
  4. answers

The driver reuses the in-memory tournament standings so later stages do not
rerun the same intra-archetype round robins.
"""

from __future__ import annotations

import argparse

from exploration.answers import print_answers, run_answers
from exploration.candidate_pools import POOL_IDS, get_candidate_pool
from exploration.common import sample_candidate_pool
from exploration.matrix import evaluate_package_candidates, print_matrix_packages, rank_package_evaluations
from exploration.selection import print_selection
from exploration.tournament import print_tournament, run_all_tournaments
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg


def main() -> None:
    """CLI entrypoint for the full realistic exploration flow."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=POOL_IDS, required=True)
    add_agent_mode_arg(parser, default="game-aware-tier-loadout")
    add_games_arg(parser, default=20)
    add_seed_arg(parser)
    parser.add_argument("--top-k", type=int, default=8, help="top tournament variants to consider per archetype")
    parser.add_argument("--show-top", type=int, default=5, help="rows to print in tournament and matrix sections")
    parser.add_argument(
        "--selection-policy",
        choices=("balanced", "strongest"),
        default="balanced",
        help="how to choose the representative package from the realistic frontier",
    )
    parser.add_argument(
        "--matrix-policy",
        choices=("balanced", "strongest"),
        default="balanced",
        help="how to rank the evaluated package matrix candidates",
    )
    parser.add_argument("--answer-games", type=int, default=12, help="games per symmetric answer-check pairing")
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

    print(f"Pool: {pool.display_name}")
    print(f"Agent mode: {args.agent_mode}")
    if args.sample_per_archetype > 0:
        print(f"Sampling: {args.sample_per_archetype} variants per archetype")
    print()

    standings_by_arch = run_all_tournaments(pool, args.games, args.seed)
    print("TOURNAMENT")
    print("----------")
    print_tournament(pool, standings_by_arch, args.show_top)
    print()

    evaluations = evaluate_package_candidates(pool, standings_by_arch, args.games, args.seed + 50_000, args.top_k)
    matrix_ranked = rank_package_evaluations(evaluations, args.matrix_policy)
    print("MATRIX")
    print("------")
    print(pool.display_name)
    print(f"Matrix policy: {args.matrix_policy}")
    print_matrix_packages(matrix_ranked, show_top=args.show_top)
    print()

    if args.selection_policy == "strongest":
        selected = rank_package_evaluations(evaluations, "strongest")[0]
        selection_ranked = rank_package_evaluations(evaluations, "strongest")
    else:
        selected = rank_package_evaluations(evaluations, "balanced")[0]
        selection_ranked = rank_package_evaluations(evaluations, "balanced")
    print("SELECTION")
    print("---------")
    print_selection(pool, selected, selection_ranked, args.selection_policy, args.show_top)
    print()

    answers = run_answers(pool, standings_by_arch, top_k=args.top_k, games=args.answer_games, seed=args.seed + 90_000)
    print("ANSWERS")
    print("-------")
    print_answers(pool, answers)


if __name__ == "__main__":
    main()
