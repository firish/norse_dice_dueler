"""L0 symmetry benchmark: RandomAgent mirrors with no God Powers.

What this file does:
  - Runs a fixed mirror baseline to verify die symmetry and engine fairness.

What this file does not do:
  - Search over values or loadouts.
  - Evaluate archetype balance.

Defaults:
  - 6x Warrior die on both sides
  - RandomAgent vs RandomAgent
  - no GP loadouts

Run:
    python -m simulator.l0_symmetry_check
    python -m simulator.l0_symmetry_check --games 2000
    python -m simulator.l0_symmetry_check --die DIE_WARRIOR
"""

from __future__ import annotations

import argparse

import numpy as np

from agents.rule_based.random_agent import RandomAgent
from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GamePhase


def run_l0(games: int, die_id: str, seed: int) -> tuple[int, int, int]:
    """Run the L0 mirror benchmark and return wins plus draws."""
    die_types = load_die_types()
    if die_id not in die_types:
        raise ValueError(f"Unknown die id: {die_id}")

    loadout = [die_types[die_id] for _ in range(6)]
    rng = np.random.default_rng(seed)

    p1_wins = 0
    p2_wins = 0
    draws = 0

    for _ in range(games):
        engine = GameEngine(
            p1_die_types=loadout,
            p2_die_types=loadout,
            rng=rng,
            p1_gp_ids=(),
            p2_gp_ids=(),
        )
        p1_agent = RandomAgent(rng=rng)
        p2_agent = RandomAgent(rng=rng)
        state, _ = engine.run_game(p1_agent, p2_agent)
        assert state.phase == GamePhase.GAME_OVER

        if state.winner == 1:
            p1_wins += 1
        elif state.winner == 2:
            p2_wins += 1
        else:
            draws += 1

    return p1_wins, p2_wins, draws


def main() -> None:
    """CLI entrypoint for the L0 symmetry check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=1000, help="number of games")
    parser.add_argument("--die", type=str, default="DIE_WARRIOR", help="mirror die id")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    p1_wins, p2_wins, draws = run_l0(args.games, args.die, args.seed)
    decisive = p1_wins + p2_wins
    p1_rate = (p1_wins / decisive * 100) if decisive else 0.0

    print(f"L0 random mirror: {args.games} games, die={args.die}, seed={args.seed}")
    print(f"P1 wins: {p1_wins}")
    print(f"P2 wins: {p2_wins}")
    print(f"Draws:   {draws}")
    print(f"P1 decisive win rate: {p1_rate:.1f}%")


if __name__ == "__main__":
    main()
