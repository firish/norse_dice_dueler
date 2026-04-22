"""L4 battlefield-condition drift harness.

Uses the current L3B advanced-dice baseline and measures how much each current
condition shifts the 3x3 directional matrix relative to the no-condition
baseline.

Run:
    python -m simulator.l4_condition_drift
    python -m simulator.l4_condition_drift --games 120
    python -m simulator.l4_condition_drift --condition COND_RAGNAROK --games 240
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GamePhase
from simulator.l3_advanced_dice_pool import TARGETS, build_archetypes

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
DRIFT_PASS_THRESHOLD = 10.0


def load_conditions() -> list[dict]:
    """Load the current location roster from the JSON data file."""
    path = DATA_DIR / "conditions.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_dice(ids: tuple[str, ...]):
    """Resolve die ids into the concrete six-die loadout."""
    from game_mechanics.die_types import load_die_types

    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_matchup(p1_arch, p2_arch, games: int, rng: np.random.Generator, condition_id: str | None) -> dict:
    """Run one directional matchup with an optional single active condition."""
    p1_dice = _resolve_dice(p1_arch.dice_ids)
    p2_dice = _resolve_dice(p2_arch.dice_ids)

    p1_wins = 0
    p2_wins = 0
    draws = 0

    for _ in range(games):
        engine = GameEngine(
            p1_die_types=p1_dice,
            p2_die_types=p2_dice,
            rng=rng,
            p1_gp_ids=p1_arch.gp_ids,
            p2_gp_ids=p2_arch.gp_ids,
            condition_id=condition_id,
        )
        p1_agent = p1_arch.agent_cls(rng=rng)
        p2_agent = p2_arch.agent_cls(rng=rng)
        state, _ = engine.run_game(p1_agent, p2_agent)
        assert state.phase == GamePhase.GAME_OVER
        if state.winner == 1:
            p1_wins += 1
        elif state.winner == 2:
            p2_wins += 1
        else:
            draws += 1

    decisive = p1_wins + p2_wins
    p1_rate = (p1_wins / decisive * 100) if decisive else 0.0
    return {"p1_rate": p1_rate, "draws": draws}


def run_matrix(
    games: int,
    seed: int,
    condition_id: str | None,
    agent_mode: str = "rule-based",
) -> dict[tuple[str, str], dict]:
    """Run the full off-diagonal matrix for one condition (or baseline if none)."""
    archetypes = build_archetypes(agent_mode)
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}
    for p1 in archetypes:
        for p2 in archetypes:
            if p1 == p2:
                continue
            results[(p1, p2)] = run_matchup(archetypes[p1], archetypes[p2], games, rng, condition_id)
    return results


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return sum(abs(results[key]["p1_rate"] - target) for key, target in TARGETS.items())


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
    for matchup in (
        ("AGGRO", "CONTROL"),
        ("CONTROL", "AGGRO"),
        ("AGGRO", "ECONOMY"),
        ("ECONOMY", "AGGRO"),
        ("CONTROL", "ECONOMY"),
        ("ECONOMY", "CONTROL"),
    ):
        base = baseline[matchup]["p1_rate"]
        curr = results[matchup]["p1_rate"]
        delta = curr - base
        print(
            f"  {matchup[0]:>8} -> {matchup[1]:<8} "
            f"{curr:5.1f}%  delta={delta:+5.1f}pp  draws={results[matchup]['draws']}"
        )
    print()


def print_baseline(results: dict[tuple[str, str], dict]) -> None:
    """Print the no-condition L3B baseline used by the drift sweep."""
    print("L4 CONDITIONS BASELINE")
    print("Baseline package: L3B fixed rule")
    print("  Aggro   = 3 Warrior + 2 Berserker + 1 Gambler")
    print("  Control = 3 Warrior + 2 Warden + 1 Skald")
    print("  Economy = 3 Warrior + 2 Miser + 1 Hunter")
    print(f"  Baseline matrix error: {matrix_error(results):.1f}")
    for matchup in (
        ("AGGRO", "CONTROL"),
        ("CONTROL", "AGGRO"),
        ("AGGRO", "ECONOMY"),
        ("ECONOMY", "AGGRO"),
        ("CONTROL", "ECONOMY"),
        ("ECONOMY", "CONTROL"),
    ):
        result = results[matchup]
        print(f"  {matchup[0]:>8} -> {matchup[1]:<8} {result['p1_rate']:5.1f}%  draws={result['draws']}")
    print()


def main() -> None:
    """CLI entrypoint for the single-condition drift harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=120, help="games per directional matchup")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--condition", type=str, default="", help="evaluate only one condition id")
    parser.add_argument(
        "--agent-mode",
        choices=("rule-based", "game-aware"),
        default="rule-based",
        help="agent family to use for the archetype pilots",
    )
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
