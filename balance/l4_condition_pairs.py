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
import json
import pathlib

from simulator.l3_advanced_dice_pool import TARGETS, build_archetypes
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)
from simulator.common.reporting import print_directional_deltas, print_directional_rows

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
DRIFT_PASS_THRESHOLD = 10.0
DRIFT_IDEAL_MIN = 5.0
DRIFT_IDEAL_MAX = 10.0


def load_conditions() -> dict[str, dict]:
    """Load the location catalog keyed by condition id."""
    path = DATA_DIR / "conditions.json"
    return {cond["id"]: cond for cond in json.loads(path.read_text(encoding="utf-8"))}


def load_condition_pairs(include_reserves: bool) -> list[tuple[str, str]]:
    """Load the approved unordered pair pool, optionally adding reserve pairs."""
    path = DATA_DIR / "condition_pairs.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    pairs = [tuple(entry["ids"]) for entry in raw["approved_pairs"]]
    if include_reserves:
        pairs.extend(tuple(entry["ids"]) for entry in raw["reserve_pairs"])
    return pairs


def all_condition_pairs(conditions: dict[str, dict]) -> list[tuple[str, str]]:
    """Return every unordered condition pair from the condition catalog."""
    return list(itertools.combinations(conditions.keys(), 2))


def run_matrix(
    games: int,
    seed: int,
    condition_ids: tuple[str, ...] | None,
    agent_mode: str = "rule-based",
) -> dict[tuple[str, str], dict]:
    """Run the full off-diagonal matrix for one condition pair."""
    archetypes = build_archetypes(agent_mode)
    return run_archetype_matrix(
        archetypes,
        games,
        seed,
        include_mirrors=False,
        condition_ids=condition_ids,
    )


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return compute_matrix_error(results, TARGETS)


def max_drift(
    baseline: dict[tuple[str, str], dict],
    pair_results: dict[tuple[str, str], dict],
) -> float:
    """Return the worst absolute directional swing versus the no-condition baseline."""
    return max(abs(pair_results[key]["p1_rate"] - baseline[key]["p1_rate"]) for key in TARGETS)


def print_baseline(results: dict[tuple[str, str], dict]) -> None:
    """Print the no-condition L3B baseline used by pair validation."""
    print("L4 CONDITION PAIRS BASELINE")
    print("Baseline package: L3B fixed rule")
    print("  Aggro   = 3 Warrior + 2 Berserker + 1 Gambler")
    print("  Control = 3 Warrior + 2 Warden + 1 Skald")
    print("  Economy = 3 Warrior + 2 Miser + 1 Hunter")
    print(f"  Baseline matrix error: {matrix_error(results):.1f}")
    print_directional_rows(results)
    print()


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
    print(f"  Matrix error: {matrix_error(results):.1f}")
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
    add_agent_mode_arg(parser)
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    baseline = run_matrix(args.games, args.seed, None, args.agent_mode)
    print_baseline(baseline)

    conditions = load_conditions()
    pairs = all_condition_pairs(conditions) if args.all_pairs else load_condition_pairs(
        include_reserves=args.include_reserves
    )
    if args.pair:
        raw = tuple(part.strip() for part in args.pair.split(",") if part.strip())
        if len(raw) != 2:
            raise ValueError("--pair must look like COND_A,COND_B")
        if raw[0] not in conditions or raw[1] not in conditions:
            raise ValueError(f"Unknown pair: {args.pair}")
        pairs = [raw]  # type: ignore[list-item]

    reports = []
    for pair in pairs:
        results = run_matrix(args.games, args.seed, pair, args.agent_mode)
        reports.append((max_drift(baseline, results), pair, results))

    reports.sort(key=lambda item: item[0])
    for _, pair, results in reports:
        print_pair_report(pair, conditions, baseline, results)


if __name__ == "__main__":
    main()
