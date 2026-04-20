"""Advanced-dice constrained L3 harness for the tuned three-archetype branch.

Rule:
  - Every loadout starts with 3x DIE_WARRIOR.
  - Add 2x archetype core dice.
  - Add 1x archetype advanced support die.

Current approved families:
  Aggro   -> 2x DIE_BERSERKER + 1x DIE_GAMBLER
  Control -> 2x DIE_WARDEN    + 1x DIE_SKALD
  Economy -> 2x DIE_MISER     + 1x DIE_HUNTER

This tests whether a small amount of advanced specialization can be introduced
without breaking the current 3-way balance.

Run:
    python -m simulator.l3_advanced_dice_pool
    python -m simulator.l3_advanced_dice_pool --games 240
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np

from simulator.agents.aggro_agent import AggroAgent
from simulator.agents.control_agent import MatchupAwareControlAgent
from simulator.agents.economy_agent import MatchupAwareEconomyAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine
from simulator.game_state import GamePhase

TARGETS: dict[tuple[str, str], float] = {
    ("AGGRO", "CONTROL"): 40.0,
    ("CONTROL", "AGGRO"): 60.0,
    ("AGGRO", "ECONOMY"): 60.0,
    ("ECONOMY", "AGGRO"): 40.0,
    ("CONTROL", "ECONOMY"): 40.0,
    ("ECONOMY", "CONTROL"): 60.0,
}


@dataclass(frozen=True)
class Archetype:
    """Fixed advanced-dice archetype definition for the L3B baseline."""

    name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


ARCHETYPES: dict[str, Archetype] = {
    "AGGRO": Archetype(
        name="AGGRO",
        dice_ids=(
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
            "DIE_BERSERKER", "DIE_BERSERKER", "DIE_GAMBLER",
        ),
        gp_ids=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        agent_cls=AggroAgent,
    ),
    "CONTROL": Archetype(
        name="CONTROL",
        dice_ids=(
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
            "DIE_WARDEN", "DIE_WARDEN", "DIE_SKALD",
        ),
        gp_ids=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        agent_cls=MatchupAwareControlAgent,
    ),
    "ECONOMY": Archetype(
        name="ECONOMY",
        dice_ids=(
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
            "DIE_MISER", "DIE_MISER", "DIE_HUNTER",
        ),
        gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        agent_cls=MatchupAwareEconomyAgent,
    ),
}


def _resolve_dice(ids: tuple[str, ...]):
    """Resolve die ids into the concrete six-die loadout."""
    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_matchup(
    p1_arch: Archetype,
    p2_arch: Archetype,
    games: int,
    rng: np.random.Generator,
) -> dict:
    """Run one directional advanced-dice matchup and report decisive win rate."""
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


def run_matrix(games: int, seed: int) -> dict[tuple[str, str], dict]:
    """Run the L3B off-diagonal matrix for the approved advanced-dice baseline."""
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}
    for p1 in ARCHETYPES:
        for p2 in ARCHETYPES:
            if p1 == p2:
                continue
            results[(p1, p2)] = run_matchup(ARCHETYPES[p1], ARCHETYPES[p2], games, rng)
    return results


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return sum(abs(results[key]["p1_rate"] - target) for key, target in TARGETS.items())


def print_results(results: dict[tuple[str, str], dict]) -> None:
    """Print the approved L3B baseline report."""
    print("L3B ADVANCED DICE")
    print("Rule: 3 Warrior + 2 core + 1 advanced")
    print("  Aggro   = 3 Warrior + 2 Berserker + 1 Gambler")
    print("  Control = 3 Warrior + 2 Warden + 1 Skald")
    print("  Economy = 3 Warrior + 2 Miser + 1 Hunter")
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
    print(f"  Matrix error: {matrix_error(results):.1f}")


def main() -> None:
    """CLI entrypoint for the L3 advanced-dice harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=240, help="games per directional matchup")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    results = run_matrix(args.games, args.seed)
    print_results(results)


if __name__ == "__main__":
    main()
