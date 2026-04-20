"""L2 balance matrix for the tuned three-archetype shell.

Goal: validate a clean 3x3 rock-paper-scissors matchup matrix using only
  - 4 dice (Warrior, Berserker, Warden, Miser)
  - 9 God Powers (T1 tier only, no band-aid mechanics)
  - No Battlefield Conditions, no Runes.

Archetype loadouts:
  AGGRO   : 4x Berserker + 2x Warrior, GPs = Surtr, Fenrir, Tyr
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
from dataclasses import dataclass

import numpy as np

from agents.aggro_agent import AggroAgent
from agents.control_agent import MatchupAwareControlAgent
from agents.economy_agent import MatchupAwareEconomyAgent
from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GamePhase

# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Archetype:
    """Fixed archetype definition used by a benchmark harness."""

    name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


ARCHETYPES: dict[str, Archetype] = {
    "AGGRO": Archetype(
        name="AGGRO",
        dice_ids=(
            "DIE_BERSERKER", "DIE_BERSERKER", "DIE_BERSERKER", "DIE_BERSERKER",
            "DIE_WARRIOR",   "DIE_WARRIOR",
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
        agent_cls=MatchupAwareControlAgent,
    ),
    "ECONOMY": Archetype(
        name="ECONOMY",
        dice_ids=(
            "DIE_MISER", "DIE_MISER", "DIE_MISER",
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        agent_cls=MatchupAwareEconomyAgent,
    ),
}


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------


def _resolve_dice(die_types, ids):
    """Turn a tuple of die ids into the concrete `DieType` loadout."""
    return [die_types[d] for d in ids]


def run_matchup(
    p1_arch: Archetype,
    p2_arch: Archetype,
    games: int,
    rng: np.random.Generator,
) -> dict:
    """Play one directional archetype matchup and return summary metrics."""
    die_types = load_die_types()
    p1_dice = _resolve_dice(die_types, p1_arch.dice_ids)
    p2_dice = _resolve_dice(die_types, p2_arch.dice_ids)

    p1_wins = 0
    p2_wins = 0
    draws = 0
    total_rounds = 0
    total_winner_hp = 0
    close_matches = 0

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
            winner_hp = state.p1.hp
            loser_hp = state.p2.hp
        elif state.winner == 2:
            p2_wins += 1
            winner_hp = state.p2.hp
            loser_hp = state.p1.hp
        else:
            draws += 1
            winner_hp = 0
            loser_hp = 0

        total_rounds += state.round_num
        total_winner_hp += winner_hp
        if winner_hp - loser_hp <= 4 and state.winner != 0:
            close_matches += 1

    decisive = p1_wins + p2_wins
    p1_rate_decisive = (p1_wins / decisive * 100) if decisive else 0.0

    return {
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "draws": draws,
        "p1_win_rate_decisive": p1_rate_decisive,
        "avg_rounds": total_rounds / games,
        "avg_winner_hp": (total_winner_hp / decisive) if decisive else 0.0,
        "close_match_rate": (close_matches / games * 100),
    }


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------


def run_matrix(games: int, seed: int = 42) -> dict[tuple[str, str], dict]:
    """Run the full 3x3 matrix, including mirrors, for reporting purposes."""
    names = list(ARCHETYPES.keys())
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}

    for p1 in names:
        for p2 in names:
            r = run_matchup(ARCHETYPES[p1], ARCHETYPES[p2], games, rng)
            results[(p1, p2)] = r
    return results


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
    parser.add_argument("--games", type=int, default=2000, help="games per cell")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    print(f"Running L2 balance matrix: {args.games} games/cell, seed={args.seed}")
    results = run_matrix(args.games, args.seed)
    print_matrix(results)


if __name__ == "__main__":
    main()
