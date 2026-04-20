"""L4 battlefield-condition pair harness.

Tests a curated shortlist of condition pairs against the current L3B baseline.
Pairs are chosen to have either opposing or mostly orthogonal swing directions,
so this harness is meant to find promising pairings rather than brute-force all
36 unordered combinations.

Run:
    python -m simulator.l4_condition_pairs
    python -m simulator.l4_condition_pairs --games 120
    python -m simulator.l4_condition_pairs --pair COND_RAGNAROK,COND_YGGDRASIL_ROOTS --games 240
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from simulator.game_engine import GameEngine
from simulator.game_state import GamePhase
from simulator.l3_advanced_dice_pool import ARCHETYPES, TARGETS

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
DRIFT_PASS_THRESHOLD = 10.0


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


def _resolve_dice(ids: tuple[str, ...]):
    """Resolve die ids into the concrete six-die loadout."""
    from simulator.die_types import load_die_types

    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_matchup(
    p1_arch,
    p2_arch,
    games: int,
    rng: np.random.Generator,
    condition_ids: tuple[str, ...] | None,
) -> dict:
    """Run one directional matchup with an optional unordered condition pair."""
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
            condition_ids=condition_ids,
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
    condition_ids: tuple[str, ...] | None,
) -> dict[tuple[str, str], dict]:
    """Run the full off-diagonal matrix for one condition pair."""
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}
    for p1 in ARCHETYPES:
        for p2 in ARCHETYPES:
            if p1 == p2:
                continue
            results[(p1, p2)] = run_matchup(ARCHETYPES[p1], ARCHETYPES[p2], games, rng, condition_ids)
    return results


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return sum(abs(results[key]["p1_rate"] - target) for key, target in TARGETS.items())


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


def print_pair_report(
    pair: tuple[str, str],
    conditions: dict[str, dict],
    baseline: dict[tuple[str, str], dict],
    results: dict[tuple[str, str], dict],
) -> None:
    """Print one condition pair's drift report versus the baseline matrix."""
    drift = max_drift(baseline, results)
    verdict = "PASS" if drift <= DRIFT_PASS_THRESHOLD else "TUNE"
    a, b = pair
    print(f"{a} + {b} [{verdict}]")
    print(f"  A: {conditions[a]['display_name']} - {conditions[a]['effect']}")
    print(f"  B: {conditions[b]['display_name']} - {conditions[b]['effect']}")
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


def main() -> None:
    """CLI entrypoint for the approved location-pair harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=120, help="games per directional matchup")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--pair", type=str, default="", help="evaluate only one pair: ID_A,ID_B")
    parser.add_argument(
        "--include-reserves",
        action="store_true",
        help="include reserve pairs from data/condition_pairs.json",
    )
    args = parser.parse_args()

    baseline = run_matrix(args.games, args.seed, None)
    print_baseline(baseline)

    conditions = load_conditions()
    pairs = load_condition_pairs(include_reserves=args.include_reserves)
    if args.pair:
        raw = tuple(part.strip() for part in args.pair.split(",") if part.strip())
        if len(raw) != 2:
            raise ValueError("--pair must look like COND_A,COND_B")
        if raw[0] not in conditions or raw[1] not in conditions:
            raise ValueError(f"Unknown pair: {args.pair}")
        pairs = [raw]  # type: ignore[list-item]

    reports = []
    for pair in pairs:
        results = run_matrix(args.games, args.seed, pair)
        reports.append((max_drift(baseline, results), pair, results))

    reports.sort(key=lambda item: item[0])
    for _, pair, results in reports:
        print_pair_report(pair, conditions, baseline, results)


if __name__ == "__main__":
    main()
