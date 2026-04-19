"""
l2_identity_3.py
----------------
L2 identity check for the 3-archetype branch.

Purpose:
  - Verify that the Aggro / Control / Economy loop exists at all.
  - This is not the final balance harness.
  - It uses a stripped-but-real shell: 3 specialist dice + 3 Warrior dice,
    with the current full archetype GP packages.

Identity target:
  - Aggro beats Economy
  - Economy beats Control
  - Control beats Aggro

Run:
    python -m simulator.l2_identity_3
    python -m simulator.l2_identity_3 --games 1000
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np

from simulator.agents.aggro_agent import AggroAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine
from simulator.game_state import GamePhase
from simulator.l2_three_arch import L2ControlAgent, L2EconomyAgent


@dataclass(frozen=True)
class Archetype:
    name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


ARCHETYPES: dict[str, Archetype] = {
    "AGGRO": Archetype(
        name="AGGRO",
        dice_ids=(
            "DIE_BERSERKER", "DIE_BERSERKER", "DIE_BERSERKER",
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        agent_cls=AggroAgent,
    ),
    "CONTROL": Archetype(
        name="CONTROL",
        dice_ids=(
            "DIE_WARDEN", "DIE_WARDEN", "DIE_WARDEN",
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        agent_cls=L2ControlAgent,
    ),
    "ECONOMY": Archetype(
        name="ECONOMY",
        dice_ids=(
            "DIE_MISER", "DIE_MISER", "DIE_MISER",
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        agent_cls=L2EconomyAgent,
    ),
}


def _resolve_dice(ids: tuple[str, ...]):
    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_matchup(p1_arch: Archetype, p2_arch: Archetype, games: int, rng: np.random.Generator) -> dict:
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


def run_identity(games: int, seed: int) -> dict[tuple[str, str], dict]:
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}
    names = list(ARCHETYPES.keys())
    for p1 in names:
        for p2 in names:
            if p1 == p2:
                continue
            results[(p1, p2)] = run_matchup(ARCHETYPES[p1], ARCHETYPES[p2], games, rng)
    return results


def identity_passes(results: dict[tuple[str, str], dict]) -> bool:
    return (
        results[("AGGRO", "ECONOMY")]["p1_rate"] > 50
        and results[("ECONOMY", "CONTROL")]["p1_rate"] > 50
        and results[("CONTROL", "AGGRO")]["p1_rate"] > 50
    )


def print_results(results: dict[tuple[str, str], dict]) -> None:
    print()
    print("=" * 56)
    print("L2 IDENTITY 3")
    print("=" * 56)
    for p1, p2 in (
        ("AGGRO", "CONTROL"),
        ("CONTROL", "AGGRO"),
        ("AGGRO", "ECONOMY"),
        ("ECONOMY", "AGGRO"),
        ("CONTROL", "ECONOMY"),
        ("ECONOMY", "CONTROL"),
    ):
        result = results[(p1, p2)]
        print(f"{p1:>8} -> {p2:<8} {result['p1_rate']:5.1f}%   draws={result['draws']}")

    print()
    if identity_passes(results):
        print("Verdict: PASS - the intended 3-way loop emerges.")
    else:
        print("Verdict: FAIL - the intended 3-way loop does not emerge cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=500, help="games per directional matchup")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    print(f"Running L2 identity check: {args.games} games/matchup, seed={args.seed}")
    results = run_identity(args.games, args.seed)
    print_results(results)


if __name__ == "__main__":
    main()
