"""
l2_three_arch.py
----------------
L2 three-archetype round robin (Aggro / Control / Economy).

Goal: validate a clean 3x3 rock-paper-scissors matchup matrix using only
  - 4 dice (Warrior, Berserker, Warden, Miser)
  - 9 God Powers (T1 tier only, no band-aid mechanics)
  - No Battlefield Conditions, no Runes.

Archetype loadouts:
  AGGRO   : 4x Berserker + 2x Warrior, GPs = Surtr, Fenrir, Tyr
  CONTROL : 3x Warden    + 3x Warrior, GPs = Aegis,  Tyr,    Frigg
  ECONOMY : 3x Miser     + 3x Warrior, GPs = Mjolnir, Gullveig, Bragi

Target matrix (rows beat columns if > 50):
           AGGRO  CONTROL  ECONOMY
  AGGRO     50     40       60
  CONTROL   60     50       40
  ECONOMY   40     60       50

Run:
    python -m simulator.l2_three_arch                   # defaults to 2000 games/cell
    python -m simulator.l2_three_arch --games 5000
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace

import numpy as np

from simulator.agents import choose_keep_by_faces, first_affordable_gp, try_gp, with_banked_tokens
from simulator.agents.aggro_agent import AggroAgent
from simulator.agents.control_agent import ControlAgent
from simulator.agents.economy_agent import EconomyAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine
from simulator.game_state import GamePhase

# ---------------------------------------------------------------------------
# Archetype definitions
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Archetype:
    name: str
    dice_ids: tuple[str, ...]       # length 6
    gp_ids: tuple[str, ...]         # length 3
    agent_cls: type


class L2ControlAgent(ControlAgent):
    """Control pilot tuned for anti-economy timing without losing the aggro edge."""

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        opp = state.p2 if player_num == 1 else state.p1
        if "GP_MJOLNIRS_WRATH" in opp.gp_loadout:
            keep_faces = frozenset({
                "FACE_HELMET", "FACE_SHIELD", "FACE_HAND_BORDERED",
                "FACE_HAND", "FACE_AXE",
            })
        else:
            keep_faces = self.keep_faces
        return choose_keep_by_faces(player, keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opp = with_banked_tokens(state.p2 if player_num == 1 else state.p1)

        if "GP_MJOLNIRS_WRATH" in opp.gp_loadout:
            choice = try_gp(player, self._god_powers, "GP_FRIGGS_VEIL", self.tier_order)
            if choice is not None:
                return choice
            choice = try_gp(player, self._god_powers, "GP_TYRS_JUDGMENT", self.tier_order)
            if choice is not None:
                return choice
            return try_gp(player, self._god_powers, "GP_AEGIS_OF_BALDR", self.tier_order)

        priority = self.gp_priority_hurt if player.hp <= self.hp_threshold else self.gp_priority_healthy
        return first_affordable_gp(player, self._god_powers, priority, self.tier_order)


class L2EconomyAgent(EconomyAgent):
    """Economy pilot that uses Bragi only as an anti-race tool into Aggro."""

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        keep_faces = frozenset({
            "FACE_HAND_BORDERED", "FACE_HAND", "FACE_AXE",
            "FACE_HELMET", "FACE_SHIELD",
        })
        return choose_keep_by_faces(player, keep_faces)

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)
        opp = state.p2 if player_num == 1 else state.p1

        opp_axes = opp.dice_faces.count("FACE_AXE")
        opp_arrows = opp.dice_faces.count("FACE_ARROW")
        my_helmets = player.dice_faces.count("FACE_HELMET")
        my_shields = player.dice_faces.count("FACE_SHIELD")
        predicted_incoming = max(
            0,
            (opp_axes + opp_arrows)
            - (min(opp_axes, my_helmets) + min(opp_arrows, my_shields)),
        )

        if "GP_SURTRS_FLAME" in opp.gp_loadout and predicted_incoming >= 2:
            choice = try_gp(player, self._god_powers, "GP_BRAGIS_SONG", self.tier_order)
            if choice is not None:
                return choice

        choice = try_gp(player, self._god_powers, "GP_MJOLNIRS_WRATH", self.tier_order)
        if choice is not None:
            return choice

        return try_gp(player, self._god_powers, "GP_GULLVEIGS_HOARD", self.tier_order)


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


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------


def _resolve_dice(die_types, ids):
    return [die_types[d] for d in ids]


def run_matchup(
    p1_arch: Archetype,
    p2_arch: Archetype,
    games: int,
    rng: np.random.Generator,
) -> dict:
    """Play `games` games of p1 vs p2. Return summary metrics."""
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
    names = list(ARCHETYPES.keys())
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}

    for p1 in names:
        for p2 in names:
            r = run_matchup(ARCHETYPES[p1], ARCHETYPES[p2], games, rng)
            results[(p1, p2)] = r
    return results


def _format_pct(x: float) -> str:
    return f"{x:5.1f}"


def print_matrix(results: dict[tuple[str, str], dict]) -> None:
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=2000, help="games per cell")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    args = parser.parse_args()

    print(f"Running L2 three-archetype matrix: {args.games} games/cell, seed={args.seed}")
    results = run_matrix(args.games, args.seed)
    print_matrix(results)


if __name__ == "__main__":
    main()
