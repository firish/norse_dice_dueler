"""L2 benchmark: GP tier check for the canonical three-archetype shell.

What this file does:
  - Runs the fixed L2 shell with tier-aware agents and the current T1/T2/T3 data.
  - Checks whether the same RPS shape still holds once agents can escalate tiers.

What this file does not do:
  - Search over candidate tier profiles.
  - Mutate GP values automatically.
"""

from __future__ import annotations

import argparse

from archetypes.level_2 import TARGETS, build_gp_tier_archetypes
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)

DEFAULT_AGENT_MODE = "game-aware-tier"


def run_matrix(
    games: int,
    seed: int = 42,
    agent_mode: str = DEFAULT_AGENT_MODE,
) -> dict[tuple[str, str], dict]:
    """Run the full L2 matrix using the canonical shell and tier-aware pilots."""
    return run_archetype_matrix(build_gp_tier_archetypes(agent_mode), games, seed, include_mirrors=True)


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return compute_matrix_error(results, TARGETS, rate_key="p1_win_rate_decisive")


def _format_pct(x: float) -> str:
    """Format a percentage for the printed matrix table."""
    return f"{x:5.1f}"


def print_matrix(results: dict[tuple[str, str], dict], agent_mode: str = DEFAULT_AGENT_MODE) -> None:
    """Print the human-readable L2 tier-check report."""
    names = list(build_gp_tier_archetypes(agent_mode).keys())

    print()
    print("=" * 60)
    print("L2 GP TIER MATRIX (P1 decisive win rate, %)")
    print("=" * 60)
    header = "  ROW vs COL    " + "   ".join(f"{n:>7}" for n in names)
    print(header)
    for p1 in names:
        row = f"  {p1:<12}"
        for p2 in names:
            row += f"  {_format_pct(results[(p1, p2)]['p1_win_rate_decisive'])}  "
        print(row)

    print()
    print("-" * 60)
    print("Target (rows win vs cols if > 50):")
    print("                 AGGRO  CONTROL  ECONOMY")
    print("  AGGRO            50     40       60")
    print("  CONTROL          60     50       40")
    print("  ECONOMY          40     60       50")
    print(f"  Matrix error: {matrix_error(results):.1f}")

    print()
    print("-" * 60)
    print("Avg rounds and avg winner HP per matchup:")
    for p1 in names:
        for p2 in names:
            r = results[(p1, p2)]
            print(
                f"  {p1:<8} vs {p2:<8}  "
                f"rounds={r['avg_rounds']:4.1f}  "
                f"winner_hp={r['avg_winner_hp']:4.1f}  "
                f"draws={r['draws']:4d}  "
                f"close={r['close_match_rate']:4.1f}%"
            )


def main() -> None:
    """CLI entrypoint for the L2 GP tier benchmark."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=500, help_text="games per cell")
    add_seed_arg(parser)
    add_agent_mode_arg(parser, default=DEFAULT_AGENT_MODE)
    args = parser.parse_args()

    print(
        f"Running L2 GP tier check: {args.games} games/cell, "
        f"seed={args.seed}, agent_mode={args.agent_mode}"
    )
    results = run_matrix(args.games, args.seed, args.agent_mode)
    print_matrix(results, args.agent_mode)


if __name__ == "__main__":
    main()
