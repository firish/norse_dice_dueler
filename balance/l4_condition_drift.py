"""L4 balance search: battlefield-condition drift sweep.

What this file does:
  - Measures how much each single condition shifts the baseline matrix.
  - Helps identify which locations are safe, weak, or overtuned.

What this file does not do:
  - Serve as the player-facing L4 benchmark entrypoint.
  - Solve drift automatically without design judgment.

Uses the current L3B advanced-dice baseline and measures how much each current
condition shifts the 3x3 directional matrix relative to the no-condition
baseline.

Run:
    python -m balance.l4_condition_drift
    python -m balance.l4_condition_drift --games 120
    python -m balance.l4_condition_drift --condition COND_RAGNAROK --games 240
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
    """Print one condition's drift report versus the baseline matrix."""
    drift = max_drift(baseline, results)
    verdict = "PASS" if drift <= DRIFT_PASS_THRESHOLD else "TUNE"
    print(f"{condition['id']} - {condition['display_name']} [{verdict}]")
    print(f"  Effect: {condition['effect']}")
    print(f"  Max drift: {drift:.1f}pp")
    print(f"  Matrix error: {level_4_matrix_error(results):.1f}")
    print_directional_deltas(baseline, results)
    print()


def print_baseline(results: dict[tuple[str, str], dict]) -> None:
    """Print the no-condition L3B baseline used by the drift sweep."""
    print_level_4_baseline("L4 CONDITIONS BASELINE", results, print_rows=print_directional_rows)


def main() -> None:
    """CLI entrypoint for the single-condition drift harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=120)
    add_seed_arg(parser)
    parser.add_argument("--condition", type=str, default="", help="evaluate only one condition id")
    add_agent_mode_arg(parser, default=DEFAULT_LEVEL_4_AGENT_MODE)
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    baseline = run_condition_matrix(args.games, args.seed, agent_mode=args.agent_mode)
    print_baseline(baseline)

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
