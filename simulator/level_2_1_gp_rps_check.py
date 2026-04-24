"""L2 benchmark: identity check for the tuned three-archetype.

What this file does:
  - Verifies that the intended Aggro / Control / Economy direction exists.
  - Acts as a lighter-weight L2 sanity check before full gp-balance validation.

What this file does not do:
  - Prove final matchup magnitudes are correct.
  - Search over tuning candidates.

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
    python -m simulator.l2_identity_check
    python -m simulator.l2_identity_check --games 1000
"""

from __future__ import annotations

import argparse

from archetypes.level_2 import GP_RPS_ARCHETYPES
from simulator.common.cli import add_games_arg, add_seed_arg
from simulator.common.matchup_runner import run_matrix as run_archetype_matrix
from simulator.common.reporting import print_directional_rows


def run_identity(games: int, seed: int) -> dict[tuple[str, str], dict]:
    """Run the off-diagonal identity matrix for Aggro, Control, and Economy."""
    return run_archetype_matrix(GP_RPS_ARCHETYPES, games, seed, include_mirrors=False)


def identity_passes(results: dict[tuple[str, str], dict]) -> bool:
    """Return whether the intended Aggro > Economy > Control > Aggro loop appears."""
    return (
        results[("AGGRO", "ECONOMY")]["p1_rate"] > 50
        and results[("ECONOMY", "CONTROL")]["p1_rate"] > 50
        and results[("CONTROL", "AGGRO")]["p1_rate"] > 50
    )


def print_results(results: dict[tuple[str, str], dict]) -> None:
    """Render the compact identity report."""
    print()
    print("=" * 56)
    print("L2 IDENTITY 3")
    print("=" * 56)
    print_directional_rows(results, prefix="",)

    print()
    if identity_passes(results):
        print("Verdict: PASS - the intended 3-way loop emerges.")
    else:
        print("Verdict: FAIL - the intended 3-way loop does not emerge cleanly.")


def main() -> None:
    """CLI entrypoint for the L2 identity harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=500)
    add_seed_arg(parser)
    args = parser.parse_args()

    print(f"Running L2 identity check: {args.games} games/matchup, seed={args.seed}")
    results = run_identity(args.games, args.seed)
    print_results(results)


if __name__ == "__main__":
    main()
