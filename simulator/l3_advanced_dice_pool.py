"""L3 benchmark: advanced-dice constrained harness for the tuned branch.

What this file does:
  - Validates the fixed approved L3 advanced-dice package.
  - Checks whether a small amount of advanced specialization preserves balance.

What this file does not do:
  - Search across the full deckbuilding space.
  - Tune values automatically.

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

from agents.rule_based.aggro_agent import AggroAgent
from agents.rule_based.control_agent import MatchupAwareControlAgent
from agents.rule_based.economy_agent import MatchupAwareEconomyAgent
from agents.game_aware.aggro_agent import GameAwareAggroAgent
from agents.game_aware.control_agent import GameAwareControlAgent
from agents.game_aware.economy_agent import GameAwareEconomyAgent
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.harness_types import Archetype
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)
from simulator.common.reporting import print_directional_rows

TARGETS: dict[tuple[str, str], float] = {
    ("AGGRO", "CONTROL"): 40.0,
    ("CONTROL", "AGGRO"): 60.0,
    ("AGGRO", "ECONOMY"): 60.0,
    ("ECONOMY", "AGGRO"): 40.0,
    ("CONTROL", "ECONOMY"): 40.0,
    ("ECONOMY", "CONTROL"): 60.0,
}

def build_archetypes(agent_mode: str = "rule-based") -> dict[str, Archetype]:
    """Build the approved L3B archetype set using the requested agent family."""
    if agent_mode == "rule-based":
        agent_classes = {
            "AGGRO": AggroAgent,
            "CONTROL": MatchupAwareControlAgent,
            "ECONOMY": MatchupAwareEconomyAgent,
        }
    elif agent_mode == "game-aware":
        agent_classes = {
            "AGGRO": GameAwareAggroAgent,
            "CONTROL": GameAwareControlAgent,
            "ECONOMY": GameAwareEconomyAgent,
        }
    else:
        raise ValueError(f"Unknown agent mode: {agent_mode}")

    return {
        "AGGRO": Archetype(
            name="AGGRO",
            dice_ids=(
                "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
                "DIE_BERSERKER", "DIE_BERSERKER", "DIE_GAMBLER",
            ),
            gp_ids=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
            agent_cls=agent_classes["AGGRO"],
        ),
        "CONTROL": Archetype(
            name="CONTROL",
            dice_ids=(
                "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
                "DIE_WARDEN", "DIE_WARDEN", "DIE_SKALD",
            ),
            gp_ids=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
            agent_cls=agent_classes["CONTROL"],
        ),
        "ECONOMY": Archetype(
            name="ECONOMY",
            dice_ids=(
                "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
                "DIE_MISER", "DIE_MISER", "DIE_HUNTER",
            ),
            gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
            agent_cls=agent_classes["ECONOMY"],
        ),
    }


ARCHETYPES: dict[str, Archetype] = build_archetypes()


def run_matrix(games: int, seed: int, agent_mode: str = "rule-based") -> dict[tuple[str, str], dict]:
    """Run the L3B off-diagonal matrix for the approved advanced-dice baseline."""
    archetypes = build_archetypes(agent_mode)
    return run_archetype_matrix(archetypes, games, seed, include_mirrors=False)


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return compute_matrix_error(results, TARGETS)


def print_results(results: dict[tuple[str, str], dict]) -> None:
    """Print the approved L3B baseline report."""
    print("L3B ADVANCED DICE")
    print("Rule: 3 Warrior + 2 core + 1 advanced")
    print("  Aggro   = 3 Warrior + 2 Berserker + 1 Gambler")
    print("  Control = 3 Warrior + 2 Warden + 1 Skald")
    print("  Economy = 3 Warrior + 2 Miser + 1 Hunter")
    print_directional_rows(results)
    print(f"  Matrix error: {matrix_error(results):.1f}")


def main() -> None:
    """CLI entrypoint for the L3 advanced-dice harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=240)
    add_seed_arg(parser)
    add_agent_mode_arg(parser)
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    results = run_matrix(args.games, args.seed, args.agent_mode)
    print_results(results)


if __name__ == "__main__":
    main()
