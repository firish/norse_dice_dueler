"""L3 balance search: core-dice constrained loadout sweep.

What this file does:
  - Sweeps legal L3 core-dice loadouts and ranks them by balance quality.
  - Helps find expressive but safe deckbuilding rules.

What this file does not do:
  - Act as the final approved L3 benchmark.
  - Define player-facing progression directly.

Rule:
  - Every loadout starts with 3x DIE_WARRIOR.
  - The remaining 3 dice come from one archetype family:
      Aggro   -> DIE_BERSERKER / DIE_GAMBLER
      Control -> DIE_WARDEN / DIE_SKALD
      Economy -> DIE_MISER / DIE_HUNTER

This keeps deckbuilding expressive while preserving archetype identity.

Run:
    python -m balance.l3_core_dice_pool
    python -m balance.l3_core_dice_pool --games 120 --top 8
    python -m balance.l3_core_dice_pool --validate A_CORE31,C_CORE21,E_CORE21
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import product

from agents.rule_based.aggro_agent import AggroAgent
from agents.rule_based.control_agent import MatchupAwareControlAgent
from agents.rule_based.economy_agent import MatchupAwareEconomyAgent
from simulator.common.cli import add_games_arg, add_seed_arg
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
def run_package(
    aggro: ArchetypeLoadout,
    control: ArchetypeLoadout,
    economy: ArchetypeLoadout,
    games: int,
    seed: int,
) -> dict[tuple[str, str], dict]:
    """Run a full off-diagonal matrix for one candidate three-loadout package."""
    archetypes = {"AGGRO": aggro, "CONTROL": control, "ECONOMY": economy}
    return run_archetype_matrix(archetypes, games, seed, include_mirrors=False)


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return compute_matrix_error(results, TARGETS)


def print_results(name: str, results: dict[tuple[str, str], dict]) -> None:
    """Print one package's directional matrix and aggregate error."""
    print(name)
    print_directional_rows(results)
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
    add_games_arg(parser, default=80)
    add_seed_arg(parser)
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
