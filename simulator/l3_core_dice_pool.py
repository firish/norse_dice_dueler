"""Core-dice constrained L3 harness for the tuned three-archetype branch.

Rule:
  - Every loadout starts with 3x DIE_WARRIOR.
  - The remaining 3 dice come from one archetype family:
      Aggro   -> DIE_BERSERKER / DIE_GAMBLER
      Control -> DIE_WARDEN / DIE_SKALD
      Economy -> DIE_MISER / DIE_HUNTER

This keeps deckbuilding expressive while preserving archetype identity.

Run:
    python -m simulator.l3_core_dice_pool
    python -m simulator.l3_core_dice_pool --games 120 --top 8
    python -m simulator.l3_core_dice_pool --validate A_CORE31,C_CORE21,E_CORE21
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import product

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
class ArchetypeLoadout:
    """Concrete legal loadout inside the L3 core-dice grammar."""

    name: str
    archetype: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


def _make_loadout(
    name: str,
    archetype: str,
    core_die: str,
    support_die: str,
    gp_ids: tuple[str, ...],
    agent_cls: type,
    core_count: int,
    support_count: int,
) -> ArchetypeLoadout:
    """Build one constrained loadout from a core/support split."""
    assert core_count + support_count == 3
    dice_ids = ("DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR") + (core_die,) * core_count + (support_die,) * support_count
    return ArchetypeLoadout(
        name=name,
        archetype=archetype,
        dice_ids=dice_ids,
        gp_ids=gp_ids,
        agent_cls=agent_cls,
    )


AGGRO_CANDIDATES: dict[str, ArchetypeLoadout] = {
    "A_CORE30": _make_loadout(
        "A_CORE30", "AGGRO", "DIE_BERSERKER", "DIE_GAMBLER",
        ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        AggroAgent, 3, 0,
    ),
    "A_CORE21": _make_loadout(
        "A_CORE21", "AGGRO", "DIE_BERSERKER", "DIE_GAMBLER",
        ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        AggroAgent, 2, 1,
    ),
    "A_CORE12": _make_loadout(
        "A_CORE12", "AGGRO", "DIE_BERSERKER", "DIE_GAMBLER",
        ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        AggroAgent, 1, 2,
    ),
}

CONTROL_CANDIDATES: dict[str, ArchetypeLoadout] = {
    "C_CORE30": _make_loadout(
        "C_CORE30", "CONTROL", "DIE_WARDEN", "DIE_SKALD",
        ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        MatchupAwareControlAgent, 3, 0,
    ),
    "C_CORE21": _make_loadout(
        "C_CORE21", "CONTROL", "DIE_WARDEN", "DIE_SKALD",
        ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        MatchupAwareControlAgent, 2, 1,
    ),
    "C_CORE12": _make_loadout(
        "C_CORE12", "CONTROL", "DIE_WARDEN", "DIE_SKALD",
        ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        MatchupAwareControlAgent, 1, 2,
    ),
}

ECONOMY_CANDIDATES: dict[str, ArchetypeLoadout] = {
    "E_CORE30": _make_loadout(
        "E_CORE30", "ECONOMY", "DIE_MISER", "DIE_HUNTER",
        ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        MatchupAwareEconomyAgent, 3, 0,
    ),
    "E_CORE21": _make_loadout(
        "E_CORE21", "ECONOMY", "DIE_MISER", "DIE_HUNTER",
        ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        MatchupAwareEconomyAgent, 2, 1,
    ),
    "E_CORE12": _make_loadout(
        "E_CORE12", "ECONOMY", "DIE_MISER", "DIE_HUNTER",
        ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        MatchupAwareEconomyAgent, 1, 2,
    ),
}


def _resolve_dice(ids: tuple[str, ...]):
    """Resolve die ids into the concrete six-die loadout."""
    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_matchup(
    p1_arch: ArchetypeLoadout,
    p2_arch: ArchetypeLoadout,
    games: int,
    rng: np.random.Generator,
) -> dict:
    """Run one directional matchup between two constrained L3 loadouts."""
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


def run_package(
    aggro: ArchetypeLoadout,
    control: ArchetypeLoadout,
    economy: ArchetypeLoadout,
    games: int,
    seed: int,
) -> dict[tuple[str, str], dict]:
    """Run a full off-diagonal matrix for one candidate three-loadout package."""
    rng = np.random.default_rng(seed)
    archetypes = {"AGGRO": aggro, "CONTROL": control, "ECONOMY": economy}
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


def print_results(name: str, results: dict[tuple[str, str], dict]) -> None:
    """Print one package's directional matrix and aggregate error."""
    print(name)
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


def all_packages():
    """Yield every legal Aggro/Control/Economy package in the L3A search space."""
    for a_name, c_name, e_name in product(AGGRO_CANDIDATES, CONTROL_CANDIDATES, ECONOMY_CANDIDATES):
        package_name = f"{a_name},{c_name},{e_name}"
        yield package_name, AGGRO_CANDIDATES[a_name], CONTROL_CANDIDATES[c_name], ECONOMY_CANDIDATES[e_name]


def search_packages(games: int, seed: int, top: int) -> None:
    """Score all legal packages and print the best few by matrix error."""
    scored: list[tuple[float, str, dict[tuple[str, str], dict]]] = []
    for package_name, aggro, control, economy in all_packages():
        results = run_package(aggro, control, economy, games, seed)
        scored.append((matrix_error(results), package_name, results))

    scored.sort(key=lambda item: item[0])
    for error, package_name, results in scored[:top]:
        print_results(f"{package_name}  error={error:.1f}", results)
        print()


def main() -> None:
    """CLI entrypoint for the L3 core-dice harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=80, help="games per directional matchup")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--top", type=int, default=8, help="packages to print in search mode")
    parser.add_argument("--validate", type=str, default="", help="validate one package by name")
    args = parser.parse_args()

    if args.validate:
        for package_name, aggro, control, economy in all_packages():
            if package_name == args.validate:
                results = run_package(aggro, control, economy, args.games, args.seed)
                print_results(package_name, results)
                return
        raise ValueError(f"Unknown package: {args.validate}")

    search_packages(args.games, args.seed, args.top)


if __name__ == "__main__":
    main()
