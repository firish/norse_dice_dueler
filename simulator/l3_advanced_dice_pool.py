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

from agents.rule_based.aggro_agent import AggroAgent
from agents.rule_based.control_agent import MatchupAwareControlAgent
from agents.rule_based.economy_agent import MatchupAwareEconomyAgent
from agents.game_aware.aggro_agent import GameAwareAggroAgent
from agents.game_aware.control_agent import GameAwareControlAgent
from agents.game_aware.economy_agent import GameAwareEconomyAgent
from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GamePhase

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


def run_matrix(games: int, seed: int, agent_mode: str = "rule-based") -> dict[tuple[str, str], dict]:
    """Run the L3B off-diagonal matrix for the approved advanced-dice baseline."""
    archetypes = build_archetypes(agent_mode)
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict] = {}
    for p1 in archetypes:
        for p2 in archetypes:
            if p1 == p2:
                continue
            results[(p1, p2)] = run_matchup(archetypes[p1], archetypes[p2], games, rng)
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
    parser.add_argument(
        "--agent-mode",
        choices=("rule-based", "game-aware"),
        default="rule-based",
        help="agent family to use for the archetype pilots",
    )
    args = parser.parse_args()

    print(f"Agent mode: {args.agent_mode}")
    results = run_matrix(args.games, args.seed, args.agent_mode)
    print_results(results)


if __name__ == "__main__":
    main()
