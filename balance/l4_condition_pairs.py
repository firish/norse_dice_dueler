"""L4 balance search: battlefield-condition pair sweep.

What this file does:
  - Sweeps condition pairs and ranks them by combined drift.
  - Helps curate approved and reserve location pair pools.

What this file does not do:
  - Serve as the player-facing L4 benchmark entrypoint.
  - Guarantee that every condition must pair well with every other condition.

Tests L4 condition pairs against the current L3B baseline. By default this
uses the approved pair pool in data/condition_pairs.json; pass --all-pairs to
brute-force every unordered condition pair from data/conditions.json.

Run:
    python -m balance.l4_condition_pairs
    python -m balance.l4_condition_pairs --games 120
    python -m balance.l4_condition_pairs --all-pairs --games 120
    python -m balance.l4_condition_pairs --pair COND_RAGNAROK,COND_YGGDRASIL_ROOTS --games 240
"""

from __future__ import annotations

import argparse
import itertools

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


def all_condition_pairs(conditions: dict[str, dict]) -> list[tuple[str, str]]:
    """Return every unordered condition pair from the condition catalog."""
    return list(itertools.combinations(conditions.keys(), 2))


def print_baseline(results: dict[tuple[str, str], dict]) -> None:
    """Print the no-condition L3B baseline used by pair validation."""
    print_level_4_baseline("L4 CONDITION PAIRS BASELINE", results, print_rows=print_directional_rows)


def print_pair_report(
    pair: tuple[str, str],
    conditions: dict[str, dict],
    baseline: dict[tuple[str, str], dict],
    results: dict[tuple[str, str], dict],
) -> None:
    """Print one condition pair's drift report versus the baseline matrix."""
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
    """CLI entrypoint for the approved location-pair harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=120)
    add_seed_arg(parser)
    parser.add_argument("--pair", type=str, default="", help="evaluate only one pair: ID_A,ID_B")
    parser.add_argument(
        "--all-pairs",
        action="store_true",
        help="evaluate all unordered pairs from data/conditions.json",
    )
    parser.add_argument(
        "--include-reserves",
        action="store_true",
        help="include reserve pairs from data/condition_pairs.json",
    )
    add_agent_mode_arg(parser, default=DEFAULT_LEVEL_4_AGENT_MODE)
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    baseline = run_condition_matrix(args.games, args.seed, agent_mode=args.agent_mode)
    print_baseline(baseline)

    conditions = load_conditions()
    pairs = all_condition_pairs(conditions) if args.all_pairs else load_approved_condition_pairs()
    if args.include_reserves and not args.all_pairs:
        pairs.extend(load_reserve_condition_pairs())
    if args.pair:
        raw = tuple(part.strip() for part in args.pair.split(",") if part.strip())
        if len(raw) != 2:
            raise ValueError("--pair must look like COND_A,COND_B")
        if raw[0] not in conditions or raw[1] not in conditions:
            raise ValueError(f"Unknown pair: {args.pair}")
        pairs = [raw]  # type: ignore[list-item]

    reports = []
    for pair in pairs:
        results = run_condition_matrix(
            args.games,
            args.seed,
            condition_ids=pair,
            agent_mode=args.agent_mode,
        )
        reports.append((max_drift(baseline, results), pair, results))

    reports.sort(key=lambda item: item[0])
    for _, pair, results in reports:
        print_pair_report(pair, conditions, baseline, results)


if __name__ == "__main__":
    main()
