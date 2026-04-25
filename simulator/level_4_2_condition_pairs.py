"""L4 benchmark: measure drift for the approved condition-pair pool.

What this file does:
  - Runs the approved L4 pair pool against the fixed L3B baseline.
  - Prints combined drift for each currently curated pair.

What this file does not do:
  - Brute-force every unordered condition pair.
  - Tune pair pools automatically.

Pair definitions live in `data/condition_pairs.json`. This harness benchmarks
the approved pool; broader pair search stays in `balance/`.
"""

from __future__ import annotations

import argparse

from game_mechanics.conditions import (
    load_approved_condition_pairs,
    load_conditions,
    load_reserve_condition_pairs,
)
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.level_4 import (
    DEFAULT_LEVEL_4_AGENT_MODE,
    DRIFT_IDEAL_MAX,
    DRIFT_IDEAL_MIN,
    DRIFT_PASS_THRESHOLD,
    level_4_matrix_error,
    max_drift,
    print_level_4_baseline,
    run_condition_matrix,
)
from simulator.common.reporting import print_directional_deltas, print_directional_rows


def print_pair_report(
    pair: tuple[str, str],
    conditions: dict[str, dict],
    baseline: dict[tuple[str, str], dict],
    results: dict[tuple[str, str], dict],
) -> None:
    """Print one approved-pair drift report versus the L4 baseline."""
    drift = max_drift(baseline, results)
    if DRIFT_IDEAL_MIN <= drift <= DRIFT_IDEAL_MAX:
        verdict = "IDEAL"
    elif drift <= DRIFT_PASS_THRESHOLD:
        verdict = "LOW"
    else:
        verdict = "TUNE"
    a, b = pair
    print(f"{a} + {b} [{verdict}]")
    print(f"  A: {conditions[a]['display_name']} - {conditions[a]['effect']}")
    print(f"  B: {conditions[b]['display_name']} - {conditions[b]['effect']}")
    print(f"  Max drift: {drift:.1f}pp")
    print(f"  Matrix error: {level_4_matrix_error(results):.1f}")
    print_directional_deltas(baseline, results)
    print()


def main() -> None:
    """CLI entrypoint for the fixed L4 approved-pair benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=240)
    add_seed_arg(parser)
    add_agent_mode_arg(parser, default=DEFAULT_LEVEL_4_AGENT_MODE)
    parser.add_argument("--pair", type=str, default="", help="benchmark only one pair: ID_A,ID_B")
    parser.add_argument(
        "--include-reserves",
        action="store_true",
        help="also benchmark reserve pairs from data/condition_pairs.json",
    )
    args = parser.parse_args()

    print(f"Pilot family: {args.agent_mode}")
    baseline = run_condition_matrix(args.games, args.seed, agent_mode=args.agent_mode)
    print_level_4_baseline("L4 CONDITION PAIRS", baseline, print_rows=print_directional_rows)

    conditions = load_conditions()
    pairs = load_approved_condition_pairs()
    if args.include_reserves:
        pairs = pairs + load_reserve_condition_pairs()
    if args.pair:
        raw = tuple(part.strip() for part in args.pair.split(",") if part.strip())
        if len(raw) != 2:
            raise ValueError("--pair must look like COND_A,COND_B")
        if raw[0] not in conditions or raw[1] not in conditions:
            raise ValueError(f"Unknown pair: {args.pair}")
        pairs = [raw]  # type: ignore[list-item]

    reports = []
    for pair in pairs:
        results = run_condition_matrix(args.games, args.seed, condition_ids=pair, agent_mode=args.agent_mode)
        reports.append((max_drift(baseline, results), pair, results))

    reports.sort(key=lambda item: item[0])
    for _, pair, results in reports:
        print_pair_report(pair, conditions, baseline, results)


if __name__ == "__main__":
    main()
