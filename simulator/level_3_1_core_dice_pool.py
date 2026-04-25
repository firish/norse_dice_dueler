"""L3 benchmark: approved core-dice constrained package.

What this file does:
  - Validates the fixed approved L3A core-dice package.
  - Checks whether the constrained 3 Warrior + 3 core-dice rule preserves balance.

What this file does not do:
  - Search across the legal L3A package space.
  - Tune values automatically.
"""

from __future__ import annotations

import argparse

from archetypes.level_3_core import APPROVED_PACKAGE_NAME, TARGETS, build_archetypes
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)
from simulator.common.reporting import print_directional_rows

DEFAULT_AGENT_MODE = "rule-based"


def run_matrix(
    games: int,
    seed: int,
    agent_mode: str = DEFAULT_AGENT_MODE,
) -> dict[tuple[str, str], dict]:
    """Run the approved L3A off-diagonal matrix."""
    return run_archetype_matrix(build_archetypes(agent_mode), games, seed, include_mirrors=False)


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return compute_matrix_error(results, TARGETS)


def print_results(results: dict[tuple[str, str], dict]) -> None:
    """Print the approved L3A benchmark report."""
    print("L3A CORE DICE")
    print("Rule: 3 Warrior + approved 3-die core package")
    print(f"Approved package: {APPROVED_PACKAGE_NAME}")
    print("Core pool: Berserker / Warden / Miser")
    print("  Aggro    = 3 Warrior + Berserker + Berserker + Berserker")
    print("  Control  = 3 Warrior + Warden + Warden + Miser")
    print("  Economy  = 3 Warrior + Berserker + Miser + Miser")
    print_directional_rows(results)
    print(f"  Matrix error: {matrix_error(results):.1f}")


def main() -> None:
    """CLI entrypoint for the L3 core-dice benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=240)
    add_seed_arg(parser)
    add_agent_mode_arg(parser, default=DEFAULT_AGENT_MODE)
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    results = run_matrix(args.games, args.seed, args.agent_mode)
    print_results(results)


if __name__ == "__main__":
    main()
