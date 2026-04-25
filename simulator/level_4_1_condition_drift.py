"""L4 benchmark: measure drift for the current single-condition roster.

What this file does:
  - Runs the approved L4 single-condition roster against the fixed L3B baseline.
  - Prints how much each condition shifts the directional matchup matrix.

What this file does not do:
  - Sweep alternate location numbers or auto-tune conditions.
  - Brute-force pair combinations.

Condition definitions live in `data/conditions.json`. This harness benchmarks
the current roster under the canonical L4 pilot family.
"""

from __future__ import annotations

import argparse

from game_mechanics.conditions import load_condition_list
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.level_4 import (
    DEFAULT_LEVEL_4_AGENT_MODE,
    DRIFT_PASS_THRESHOLD,
    level_4_matrix_error,
    max_drift,
    print_level_4_baseline,
    run_condition_matrix,
)
from simulator.common.reporting import print_directional_deltas, print_directional_rows


def print_condition_report(
    condition: dict,
    baseline: dict[tuple[str, str], dict],
    results: dict[tuple[str, str], dict],
) -> None:
    """Print one single-condition drift report versus the L4 baseline."""
    drift = max_drift(baseline, results)
    verdict = "PASS" if drift <= DRIFT_PASS_THRESHOLD else "TUNE"
    print(f"{condition['id']} - {condition['display_name']} [{verdict}]")
    print(f"  Effect: {condition['effect']}")
    print(f"  Max drift: {drift:.1f}pp")
    print(f"  Matrix error: {level_4_matrix_error(results):.1f}")
    print_directional_deltas(baseline, results)
    print()


def main() -> None:
    """CLI entrypoint for the fixed L4 single-condition benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=240)
    add_seed_arg(parser)
    add_agent_mode_arg(parser, default=DEFAULT_LEVEL_4_AGENT_MODE)
    parser.add_argument("--condition", type=str, default="", help="benchmark only one condition id")
    args = parser.parse_args()

    print(f"Pilot family: {args.agent_mode}")
    baseline = run_condition_matrix(args.games, args.seed, agent_mode=args.agent_mode)
    print_level_4_baseline("L4 SINGLE-CONDITION DRIFT", baseline, print_rows=print_directional_rows)

    conditions = load_condition_list()
    if args.condition:
        conditions = [cond for cond in conditions if cond["id"] == args.condition]
        if not conditions:
            raise ValueError(f"Unknown condition: {args.condition}")

    reports = []
    for condition in conditions:
        results = run_condition_matrix(
            args.games,
            args.seed,
            condition_id=condition["id"],
            agent_mode=args.agent_mode,
        )
        reports.append((max_drift(baseline, results), condition, results))

    reports.sort(key=lambda item: item[0])
    for _, condition, results in reports:
        print_condition_report(condition, baseline, results)


if __name__ == "__main__":
    main()
