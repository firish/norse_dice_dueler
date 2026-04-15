"""
simulator.py
------------
L0 simulation runner.

Usage:
    python3 simulator/simulator.py                    # 10,000 games, DIE_WARRIOR
    python3 simulator/simulator.py --games 50000
    python3 simulator/simulator.py --die DIE_WARRIOR --games 5000 --seed 0
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from dataclasses import dataclass, field

import numpy as np

# Allow running as `python3 simulator/simulator.py` from the repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from simulator.agents.random_agent import RandomAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------

@dataclass
class SimulationResults:
    n_games: int
    die_id: str
    p1_wins: int = 0
    p2_wins: int = 0
    draws: int = 0
    rounds_per_game: list[int] = field(default_factory=list)
    winner_hp_per_game: list[int] = field(default_factory=list)
    elapsed_sec: float = 0.0

    # -- Derived properties --

    @property
    def p1_win_rate(self) -> float:
        return self.p1_wins / self.n_games

    @property
    def p2_win_rate(self) -> float:
        return self.p2_wins / self.n_games

    @property
    def draw_rate(self) -> float:
        return self.draws / self.n_games

    @property
    def decisive_games(self) -> int:
        return self.p1_wins + self.p2_wins

    @property
    def p1_decisive_win_rate(self) -> float:
        """P1 wins / (P1 wins + P2 wins). Excludes draws. The L0 balance metric."""
        d = self.decisive_games
        return self.p1_wins / d if d > 0 else 0.5

    @property
    def avg_rounds(self) -> float:
        return float(np.mean(self.rounds_per_game))

    @property
    def median_rounds(self) -> float:
        return float(np.median(self.rounds_per_game))

    @property
    def avg_winner_hp(self) -> float:
        decisive = [hp for hp in self.winner_hp_per_game if hp > 0]
        return float(np.mean(decisive)) if decisive else 0.0

    @property
    def close_match_rate(self) -> float:
        """Fraction of decisive games where winner had ≤4 HP remaining."""
        decisive = [hp for hp in self.winner_hp_per_game if hp > 0]
        if not decisive:
            return 0.0
        return sum(1 for hp in decisive if hp <= 4) / len(decisive)

    @property
    def games_per_sec(self) -> float:
        return self.n_games / self.elapsed_sec if self.elapsed_sec > 0 else 0.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_simulation(
    n_games: int = 10_000,
    seed: int = 42,
    die_id: str = "DIE_WARRIOR",
) -> SimulationResults:
    rng = np.random.default_rng(seed)
    die_types = load_die_types()

    if die_id not in die_types:
        raise ValueError(f"Unknown die ID '{die_id}'. Available: {list(die_types)}")

    die = die_types[die_id]
    loadout = [die] * 6

    engine   = GameEngine(loadout, loadout, rng)
    p1_agent = RandomAgent(rng)
    p2_agent = RandomAgent(rng)

    results = SimulationResults(n_games=n_games, die_id=die_id)

    t0 = time.perf_counter()
    for _ in range(n_games):
        final_state, _ = engine.run_game(p1_agent, p2_agent)
        winner = final_state.winner
        rounds = final_state.round_num

        if winner == 1:
            results.p1_wins += 1
            results.winner_hp_per_game.append(final_state.p1.hp)
        elif winner == 2:
            results.p2_wins += 1
            results.winner_hp_per_game.append(final_state.p2.hp)
        else:
            results.draws += 1
            results.winner_hp_per_game.append(0)

        results.rounds_per_game.append(rounds)

    results.elapsed_sec = time.perf_counter() - t0
    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _status(value: float, green_lo: float, green_hi: float,
            yellow_lo: float, yellow_hi: float) -> str:
    if green_lo <= value <= green_hi:
        return "GREEN  ✓"
    if yellow_lo <= value <= yellow_hi:
        return "YELLOW !"
    return "RED    ✗"


def print_results(r: SimulationResults) -> None:
    n = r.n_games
    p_decisive = r.p1_decisive_win_rate
    ci = 1.96 * (p_decisive * (1 - p_decisive) / r.decisive_games) ** 0.5

    sep = "─" * 58

    print(f"\n{'═'*58}")
    print(f"  Fjöld — L0 Simulation Results")
    print(f"{'═'*58}")
    print(f"  Games  : {n:>10,}")
    print(f"  Die    : {r.die_id} × 6 per player")
    print(f"  Seed   : fixed (reproducible)")
    print()

    # --- Outcomes ---
    print(f"  {'Outcome':<26} {'Count':>8}   {'Rate':>7}")
    print(f"  {sep}")
    print(f"  {'P1 Win':<26} {r.p1_wins:>8,}   {r.p1_win_rate:>6.1%}")
    print(f"  {'P2 Win':<26} {r.p2_wins:>8,}   {r.p2_win_rate:>6.1%}")
    print(f"  {'Draw (simultaneous death)':<26} {r.draws:>8,}   {r.draw_rate:>6.1%}")
    print(f"  {'P1 Decisive Win Rate':<26} {'':>8}   {p_decisive:>6.1%}  ← L0 metric")
    print(f"    (draws excluded; 95% CI: [{p_decisive-ci:.1%}, {p_decisive+ci:.1%}])")
    print()

    # --- Match length ---
    rounds = r.rounds_per_game
    print(f"  {'Match Length':<26} {'Value':>10}")
    print(f"  {sep}")
    print(f"  {'Avg Rounds':<26} {r.avg_rounds:>10.1f}")
    print(f"  {'Median Rounds':<26} {r.median_rounds:>10.1f}")
    print(f"  {'Min Rounds':<26} {min(rounds):>10}")
    print(f"  {'Max Rounds':<26} {max(rounds):>10}")
    print(f"  {'≤ 8 Rounds':<26} {sum(1 for x in rounds if x <= 8)/n:>10.1%}")
    print()

    # --- HP at end ---
    print(f"  {'HP at Game End':<26} {'Value':>10}")
    print(f"  {sep}")
    print(f"  {'Avg Winner HP':<26} {r.avg_winner_hp:>10.1f}")
    print(f"  {'Close games (winner ≤4 HP)':<26} {r.close_match_rate:>10.1%}")
    print()

    # --- L0 validation ---
    # L0 metric: decisive P1 win rate 48-52% (first-mover parity check).
    # Match length target (5-8 rds) applies to the FULL game (L2+), not L0.
    # Draws at L0 are expected: symmetric dice + no GP → parallel HP decay.
    print(f"  {'L0 Validation':<30} {'Value':>8}  {'Target':>10}  Status")
    print(f"  {sep}")

    wr_status = _status(p_decisive, 0.48, 0.52, 0.46, 0.54)
    print(f"  {'Decisive P1 Win Rate':<30} {p_decisive:>7.1%}   {'48–52%':>10}  {wr_status}")

    ml_status = _status(r.avg_rounds, 5, 8, 4, 10)
    print(f"  {'Avg Match Length':<30} {r.avg_rounds:>7.1f}   {'5–8 rds':>10}  {ml_status}")
    print(f"    ^ L0 note: no GP means less damage/round; target applies at L2+")

    cm_status = _status(r.close_match_rate, 0.40, 1.0, 0.30, 1.0)
    print(f"  {'Close Matches (winner ≤4 HP)':<30} {r.close_match_rate:>7.1%}   {'≥ 40%':>10}  {cm_status}")

    draw_sym = abs(r.p1_wins - r.p2_wins) / n
    ds_status = "GREEN  ✓" if draw_sym < 0.02 else "YELLOW !"
    print(f"  {'Draw Symmetry (|P1-P2| wins)':<30} {draw_sym:>7.1%}   {'< 2%':>10}  {ds_status}")
    print(f"    ^ Draws are symmetric: neither player has an inherent advantage")
    print()

    print(f"  Elapsed : {r.elapsed_sec:.1f}s  ({r.games_per_sec:,.0f} games/sec)")
    print(f"{'═'*58}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Fjöld L0 balance simulation (raw dice, no God Powers)."
    )
    parser.add_argument(
        "--games", type=int, default=10_000,
        help="Number of games to simulate (default: 10,000).",
    )
    parser.add_argument(
        "--die", default="DIE_WARRIOR",
        help="Die ID for both players' loadouts (default: DIE_WARRIOR).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed for reproducibility (default: 42).",
    )
    args = parser.parse_args()

    print(f"Running {args.games:,} games…")
    results = run_simulation(n_games=args.games, seed=args.seed, die_id=args.die)
    print_results(results)


if __name__ == "__main__":
    main()
