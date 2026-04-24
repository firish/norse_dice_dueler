"""L1 benchmark: simple GP user versus the no-GP random baseline.

What this file does:
  - Measures whether basic GP access beats a no-GP baseline.

What this file does not do:
  - Search for the best GP values.
  - Tune archetype balance.

Setup:
  - Both players use the same mirror die loadout.
  - P1 brings 3 random GPs sampled from the L1-useful subset.
  - P2 brings no GPs.
  - P1 uses GreedyAgent (simple random affordable GP user).
  - P2 uses RandomAgent.

Goal:
  - Check whether basic GP access beats no GP access.

Run:
    python -m simulator.l1_god_power_advantage
    python -m simulator.l1_god_power_advantage --games 1000
    python -m simulator.l1_god_power_advantage --die DIE_WARRIOR
"""

from __future__ import annotations

import argparse

import numpy as np

from agents.rule_based.greedy_agent import GreedyAgent
from agents.rule_based.random_agent import RandomAgent
from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GamePhase
from game_mechanics.god_powers import load_god_powers

L1_USEFUL_GP_IDS: tuple[str, ...] = (
    "GP_SURTRS_FLAME",
    "GP_FENRIRS_BITE",
    "GP_MJOLNIRS_WRATH",
    "GP_GULLVEIGS_HOARD",
    "GP_TYRS_JUDGMENT",
)


def sample_gp_loadout(rng: np.random.Generator) -> tuple[str, str, str]:
    """Sample a simple three-GP loadout from the curated L1-useful subset."""
    known_ids = load_god_powers().keys()
    gp_ids = [gp_id for gp_id in L1_USEFUL_GP_IDS if gp_id in known_ids]
    picks = rng.choice(gp_ids, size=3, replace=False)
    return tuple(str(x) for x in picks)


def run_l1(games: int, die_id: str, seed: int) -> tuple[int, int, int]:
    """Run the L1 benchmark and return wins plus draws."""
    die_types = load_die_types()
    if die_id not in die_types:
        raise ValueError(f"Unknown die id: {die_id}")

    loadout = [die_types[die_id] for _ in range(6)]
    rng = np.random.default_rng(seed)

    p1_wins = 0
    p2_wins = 0
    draws = 0

    for _ in range(games):
        p1_gps = sample_gp_loadout(rng)
        engine = GameEngine(
            p1_die_types=loadout,
            p2_die_types=loadout,
            rng=rng,
            p1_gp_ids=p1_gps,
            p2_gp_ids=(),
        )
        p1_agent = GreedyAgent(rng=rng)
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
    """CLI entrypoint for the L1 GP-advantage check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=1000, help="number of games")
    parser.add_argument("--die", type=str, default="DIE_WARRIOR", help="mirror die id")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    p1_wins, p2_wins, draws = run_l1(args.games, args.die, args.seed)
    decisive = p1_wins + p2_wins
    p1_rate = (p1_wins / decisive * 100) if decisive else 0.0

    print(f"L1 random GPs: {args.games} games, die={args.die}, seed={args.seed}")
    print("P1: GreedyAgent with 3 random L1-useful GPs")
    print("P2: RandomAgent with no GPs")
    print(f"P1 wins: {p1_wins}")
    print(f"P2 wins: {p2_wins}")
    print(f"Draws:   {draws}")
    print(f"P1 decisive win rate: {p1_rate:.1f}%")


if __name__ == "__main__":
    main()
