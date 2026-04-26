"""Answer-check harness for the top-k realistic variants in each archetype."""

from __future__ import annotations

import argparse

from exploration.candidate_pools import ARCHETYPE_ORDER, POOL_IDS, get_candidate_pool
from exploration.common import run_symmetric_matchup, sample_candidate_pool
from exploration.tournament import run_all_tournaments
from exploration.types import CandidatePool, CandidateStanding
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg


def run_answers(
    pool: CandidatePool,
    standings_by_arch: dict[str, list[CandidateStanding]],
    *,
    top_k: int,
    games: int,
    seed: int,
) -> dict[str, dict[str, list[dict[str, float | int | str]]]]:
    """Check whether the top-k builds in each archetype still have opposing answers."""
    report: dict[str, dict[str, list[dict[str, float | int | str]]]] = {}
    offset = 0
    for archetype in ARCHETYPE_ORDER:
        selected_rows = standings_by_arch[archetype][:top_k]
        report[archetype] = {}
        for opponent_arch in ARCHETYPE_ORDER:
            if opponent_arch == archetype:
                continue
            opponent_rows = standings_by_arch[opponent_arch][:top_k]
            answers: list[dict[str, float | int | str]] = []
            for row in selected_rows:
                candidate = pool.candidates_by_archetype[archetype][row.candidate_id]
                best_id = ""
                best_rate = -1.0
                answers_over_50 = 0
                answers_over_55 = 0
                for opponent_row in opponent_rows:
                    opponent = pool.candidates_by_archetype[opponent_arch][opponent_row.candidate_id]
                    result = run_symmetric_matchup(candidate, opponent, games, seed + offset)
                    offset += 1
                    opponent_rate = float(result["b_rate"])
                    if opponent_rate > best_rate:
                        best_rate = opponent_rate
                        best_id = opponent.id
                    if opponent_rate > 50.0:
                        answers_over_50 += 1
                    if opponent_rate >= 55.0:
                        answers_over_55 += 1
                answers.append(
                    {
                        "candidate_id": candidate.id,
                        "best_answer_id": best_id,
                        "best_answer_rate": best_rate,
                        "answers_over_50": answers_over_50,
                        "answers_over_55": answers_over_55,
                        "candidate_count": len(opponent_rows),
                    }
                )
            report[archetype][opponent_arch] = answers
    return report


def print_answers(
    pool: CandidatePool,
    report: dict[str, dict[str, list[dict[str, float | int | str]]]],
) -> None:
    """Print a compact top-k answer-coverage report."""
    print(pool.display_name)
    for archetype in ARCHETYPE_ORDER:
        print()
        print(archetype)
        for opponent_arch in ARCHETYPE_ORDER:
            if opponent_arch == archetype:
                continue
            print(f"  vs {opponent_arch}")
            for row in report[archetype][opponent_arch]:
                candidate = pool.candidates_by_archetype[archetype][str(row['candidate_id'])]
                print(
                    f"    {row['candidate_id']:<32} "
                    f"best_answer={row['best_answer_id']:<32} "
                    f"rate={float(row['best_answer_rate']):5.1f}%  "
                    f">50={row['answers_over_50']}/{row['candidate_count']}  "
                    f">=55={row['answers_over_55']}/{row['candidate_count']}"
                )
                print(f"      {candidate.summary}")


def main() -> None:
    """CLI entrypoint for top-k answer coverage checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=POOL_IDS, required=True)
    add_agent_mode_arg(parser, default="game-aware-tier-loadout")
    add_games_arg(parser, default=12)
    add_seed_arg(parser)
    parser.add_argument("--top-k", type=int, default=8, help="top tournament variants per archetype to answer-check")
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
    report = run_answers(pool, standings_by_arch, top_k=args.top_k, games=args.games, seed=args.seed + 90_000)
    print_answers(pool, report)


if __name__ == "__main__":
    main()
