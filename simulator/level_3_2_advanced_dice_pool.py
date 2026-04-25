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

from archetypes.level_3_advanced import APPROVED_PACKAGE_NAME, ARCHETYPES, TARGETS, build_archetypes
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)
from simulator.common.reporting import print_directional_rows


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
    print(f"Approved package: {APPROVED_PACKAGE_NAME}")
    print("  Aggro    = 3 Warrior + Berserker + Berserker + Gambler")
    print("  Control  = 3 Warrior + Warden + Warden + Skald")
    print("  Economy  = 3 Warrior + Miser + Miser + Hunter")
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
