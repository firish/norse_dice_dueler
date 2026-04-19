"""
l1_random_gps.py
----------------
L1 validation: simple GP user vs RandomAgent.

Setup:
  - Both players use the same mirror die loadout.
  - P1 brings 3 random GPs sampled from the L1-useful subset.
  - P2 brings no GPs.
  - P1 uses GreedyAgent (simple random affordable GP user).
  - P2 uses RandomAgent.

Goal:
  - Check whether basic GP access beats no GP access.

Run:
    python -m simulator.l1_random_gps
    python -m simulator.l1_random_gps --games 1000
    python -m simulator.l1_random_gps --die DIE_WARRIOR
"""

from __future__ import annotations

import argparse

import numpy as np

from simulator.agents.greedy_agent import GreedyAgent
from simulator.agents.random_agent import RandomAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine
from simulator.game_state import GamePhase
from simulator.god_powers import load_god_powers

L1_USEFUL_GP_IDS: tuple[str, ...] = (
    "GP_SURTRS_FLAME",
    "GP_FENRIRS_BITE",
    "GP_MJOLNIRS_WRATH",
    "GP_GULLVEIGS_HOARD",
    "GP_TYRS_JUDGMENT",
)


def sample_gp_loadout(rng: np.random.Generator) -> tuple[str, str, str]:
    known_ids = load_god_powers().keys()
    gp_ids = [gp_id for gp_id in L1_USEFUL_GP_IDS if gp_id in known_ids]
    picks = rng.choice(gp_ids, size=3, replace=False)
    return tuple(str(x) for x in picks)


def run_l1(games: int, die_id: str, seed: int) -> tuple[int, int, int]:
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
