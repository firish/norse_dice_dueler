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
import json
import pathlib

from archetypes.level_3_advanced import TARGETS, build_archetypes
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)
from simulator.common.reporting import print_directional_deltas, print_directional_rows

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
DRIFT_PASS_THRESHOLD = 10.0


def load_conditions() -> list[dict]:
    """Load the current location roster from the JSON data file."""
    path = DATA_DIR / "conditions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_matrix(
    games: int,
    seed: int,
    condition_id: str | None,
    agent_mode: str = "rule-based",
) -> dict[tuple[str, str], dict]:
    """Run the full off-diagonal matrix for one condition (or baseline if none)."""
    archetypes = build_archetypes(agent_mode)
    return run_archetype_matrix(
        archetypes,
        games,
        seed,
        include_mirrors=False,
        condition_id=condition_id,
    )


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return compute_matrix_error(results, TARGETS)


def max_drift(
    baseline: dict[tuple[str, str], dict],
    condition_results: dict[tuple[str, str], dict],
) -> float:
    """Return the worst absolute directional swing versus the no-condition baseline."""
    return max(abs(condition_results[key]["p1_rate"] - baseline[key]["p1_rate"]) for key in TARGETS)


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
    print(f"  Matrix error: {matrix_error(results):.1f}")
    print_directional_deltas(baseline, results)
    print()


def print_baseline(results: dict[tuple[str, str], dict]) -> None:
    """Print the no-condition L3B baseline used by the drift sweep."""
    print("L4 CONDITIONS BASELINE")
    print("Baseline package: L3B fixed rule")
    print("  Aggro   = 3 Warrior + 2 Berserker + 1 Gambler")
    print("  Control = 3 Warrior + 2 Warden + 1 Skald")
    print("  Economy = 3 Warrior + 2 Miser + 1 Hunter")
    print(f"  Baseline matrix error: {matrix_error(results):.1f}")
    print_directional_rows(results)
    print()


def main() -> None:
    """CLI entrypoint for the single-condition drift harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=120)
    add_seed_arg(parser)
    parser.add_argument("--condition", type=str, default="", help="evaluate only one condition id")
    add_agent_mode_arg(parser)
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    baseline = run_matrix(args.games, args.seed, None, args.agent_mode)
    print_baseline(baseline)

    conditions = load_conditions()
    if args.condition:
        conditions = [cond for cond in conditions if cond["id"] == args.condition]
        if not conditions:
            raise ValueError(f"Unknown condition: {args.condition}")

    reports = []
    for condition in conditions:
        results = run_matrix(args.games, args.seed, condition["id"], args.agent_mode)
        reports.append((max_drift(baseline, results), condition, results))

    reports.sort(key=lambda item: item[0])
    for _, condition, results in reports:
        print_condition_report(condition, baseline, results)


if __name__ == "__main__":
    main()
