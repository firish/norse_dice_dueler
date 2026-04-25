"""Generic stress test for selected exploration packages.

For each selected archetype candidate, test whether the opposing candidate pools
contain credible answers.
"""

from __future__ import annotations

import argparse

from exploration.candidate_pools import ARCHETYPE_ORDER, get_candidate_pool, package_name
from exploration.common import package_from_ids, run_symmetric_matchup
from exploration.types import CandidatePool
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg


def _parse_package_arg(raw: str, pool: CandidatePool) -> dict[str, str]:
    """Parse a comma-separated package id string or fall back to the approved package."""
    if not raw:
        return dict(pool.approved_package_ids)
    parts = tuple(part.strip() for part in raw.split(",") if part.strip())
    if len(parts) != 3:
        raise ValueError("Package must contain exactly three candidate ids")
    return dict(zip(ARCHETYPE_ORDER, parts, strict=True))


def run_stress_test(
    pool: CandidatePool,
    package_ids: dict[str, str],
    games: int,
    seed: int,
) -> dict[str, dict[str, dict[str, float | int | str]]]:
    """Run answer verification for one selected package."""
    selected = package_from_ids(pool, package_ids)
    report: dict[str, dict[str, dict[str, float | int | str]]] = {}
    offset = 0
    for archetype in ARCHETYPE_ORDER:
        report[archetype] = {}
        selected_candidate = selected[archetype]
        for opponent_arch in ARCHETYPE_ORDER:
            if opponent_arch == archetype:
                continue

            best_id = ""
            best_rate = -1.0
            answers_50 = 0
            answers_55 = 0

            for opponent_candidate in pool.candidates_by_archetype[opponent_arch].values():
                result = run_symmetric_matchup(selected_candidate, opponent_candidate, games, seed + offset)
                offset += 1
                opponent_rate = float(result["b_rate"])
                if opponent_rate > best_rate:
                    best_rate = opponent_rate
                    best_id = opponent_candidate.id
                if opponent_rate > 50.0:
                    answers_50 += 1
                if opponent_rate >= 55.0:
                    answers_55 += 1

            report[archetype][opponent_arch] = {
                "best_answer_id": best_id,
                "best_answer_rate": best_rate,
                "answers_over_50": answers_50,
                "answers_over_55": answers_55,
                "candidate_count": len(pool.candidates_by_archetype[opponent_arch]),
            }
    return report


def print_stress_test(pool: CandidatePool, package_ids: dict[str, str], report: dict[str, dict[str, dict[str, float | int | str]]]) -> None:
    """Print a compact answer-coverage report."""
    print(pool.display_name)
    print(f"Stress package: {package_name(package_ids)}")
    for archetype in ARCHETYPE_ORDER:
        print()
        print(f"{archetype} candidate: {package_ids[archetype]}")
        print(f"  {pool.candidates_by_archetype[archetype][package_ids[archetype]].summary}")
        for opponent_arch in ARCHETYPE_ORDER:
            if opponent_arch == archetype:
                continue
            row = report[archetype][opponent_arch]
            print(
                f"  {opponent_arch:<8} best_answer={row['best_answer_id']}  "
                f"rate={float(row['best_answer_rate']):5.1f}%  "
                f">50={row['answers_over_50']}/{row['candidate_count']}  "
                f">=55={row['answers_over_55']}/{row['candidate_count']}"
            )


def main() -> None:
    """CLI entrypoint for answer verification across candidate pools."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=("l3_core", "l3_advanced"), required=True)
    add_agent_mode_arg(parser, default="game-aware-tier")
    add_games_arg(parser, default=40)
    add_seed_arg(parser)
    parser.add_argument(
        "--package",
        type=str,
        default="",
        help="comma-separated AGGRO,CONTROL,ECONOMY candidate ids; defaults to the approved package",
    )
    args = parser.parse_args()

    pool = get_candidate_pool(args.pool, args.agent_mode)
    package_ids = _parse_package_arg(args.package, pool)
    report = run_stress_test(pool, package_ids, args.games, args.seed)
    print_stress_test(pool, package_ids, report)


if __name__ == "__main__":
    main()
