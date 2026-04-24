"""L2 benchmark: balance matrix (RPS branch magnitude) for the tuned three-archetype shell.

What this file does:
  - Runs the fixed L2 Aggro / Control / Economy 3x3 matrix.
  - Reports how close the current shell is to the intended RPS targets.

What this file does not do:
  - Search over candidate GP values.
  - Explore alternate loadout grammars.

Goal: validate a clean 3x3 rock-paper-scissors matchup matrix using only
  - 4 dice (Warrior, Berserker, Warden, Miser)
  - 9 God Powers (T1 tier only)
  - No band-aid mechanics
  - No Battlefield Conditions
  - No Runes.

Archetype loadouts:
  AGGRO   : 3x Berserker + 3x Warrior, GPs = Surtr, Fenrir, Tyr
  CONTROL : 3x Warden    + 3x Warrior, GPs = Aegis, Eir, Tyr
  ECONOMY : 3x Miser     + 3x Warrior, GPs = Mjolnir, Gullveig, Bragi

Target matrix (rows beat columns if > 50):
           AGGRO  CONTROL  ECONOMY
  AGGRO     50     40       60
  CONTROL   60     50       40
  ECONOMY   40     60       50

Run:
    python -m simulator.l2_balance_matrix
    python -m simulator.l2_balance_matrix --games 5000
"""

from __future__ import annotations

import argparse

from archetypes.level_2 import ARCHETYPES, build_archetypes
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg
from simulator.common.matchup_runner import run_matrix as run_archetype_matrix

# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------


def run_matrix(games: int, seed: int = 42, agent_mode: str = "rule-based") -> dict[tuple[str, str], dict]:
    """Run the full 3x3 matrix, including mirrors, for reporting purposes."""
    archetypes = build_archetypes(agent_mode)
    return run_archetype_matrix(archetypes, games, seed, include_mirrors=True)


def _format_pct(x: float) -> str:
    """Format a percentage for the printed matrix table."""
    return f"{x:5.1f}"


def print_matrix(results: dict[tuple[str, str], dict]) -> None:
    """Print the human-readable L2 balance report."""
    names = list(ARCHETYPES.keys())

    print()
    print("=" * 60)
    print("L2 THREE-ARCHETYPE MATRIX (P1 decisive win rate, %)")
    print("=" * 60)
    header = "  ROW vs COL    " + "   ".join(f"{n:>7}" for n in names)
    print(header)
    for p1 in names:
        row = f"  {p1:<12}"
        for p2 in names:
            r = results[(p1, p2)]
            row += f"  {_format_pct(r['p1_win_rate_decisive'])}  "
        print(row)

    print()
    print("-" * 60)
    print("Target (rows win vs cols if > 50):")
    print("                 AGGRO  CONTROL  ECONOMY")
    print("  AGGRO            50     40       60")
    print("  CONTROL          60     50       40")
    print("  ECONOMY          40     60       50")

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

    print()
    print("-" * 60)
    print("Overall archetype win rate (symmetric, excludes self-mirror):")
    for arch in names:
        wins = 0
        games_played = 0
        for other in names:
            if other == arch:
                continue
            r = results[(arch, other)]
            wins += r["p1_wins"]
            games_played += r["p1_wins"] + r["p2_wins"]
            r2 = results[(other, arch)]
            wins += r2["p2_wins"]
            games_played += r2["p1_wins"] + r2["p2_wins"]
        rate = (wins / games_played * 100) if games_played else 0.0
        print(f"  {arch:<10} {rate:5.1f}%  ({wins}/{games_played})")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint for the tuned L2 balance matrix harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_games_arg(parser, default=2000, help_text="games per cell")
    add_seed_arg(parser)
    add_agent_mode_arg(parser)
    args = parser.parse_args()

    print(
        f"Running L2 balance matrix: {args.games} games/cell, "
        f"seed={args.seed}, agent_mode={args.agent_mode}"
    )
    results = run_matrix(args.games, args.seed, args.agent_mode)
    print_matrix(results)


if __name__ == "__main__":
    main()
