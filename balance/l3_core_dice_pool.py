"""L3 balance search: core-dice constrained loadout sweep.

What this file does:
  - Sweeps legal L3 core-dice loadouts and ranks them by balance quality.
  - Helps find expressive but safe deckbuilding rules.

What this file does not do:
  - Act as the final approved L3 benchmark.
  - Define player-facing progression directly.

Rule:
  - Every loadout starts with 3x DIE_WARRIOR.
  - The remaining 3 dice may be any mix of core dice:
      DIE_BERSERKER / DIE_WARDEN / DIE_MISER

This keeps deckbuilding expressive while preserving the bounded L3 core grammar.

Run:
    python -m balance.l3_core_dice_pool
    python -m balance.l3_core_dice_pool --games 120 --top 8
    python -m balance.l3_core_dice_pool --validate A_CORE_B111,C_CORE_B111,E_CORE_B111
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from itertools import combinations_with_replacement, product

from archetypes.common import agent_classes
from archetypes.level_3_core import TARGETS
from simulator.common.cli import add_games_arg, add_seed_arg
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)
from simulator.common.reporting import print_directional_rows


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
    extra_dice: tuple[str, str, str],
    gp_ids: tuple[str, ...],
    agent_cls: type,
) -> ArchetypeLoadout:
    """Build one constrained loadout from the 3 Warrior + any 3 core grammar."""
    dice_ids = ("DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR") + extra_dice
    return ArchetypeLoadout(
        name=name,
        archetype=archetype,
        dice_ids=dice_ids,
        gp_ids=gp_ids,
        agent_cls=agent_cls,
    )


CORE_DICE = ("DIE_BERSERKER", "DIE_WARDEN", "DIE_MISER")


def _candidate_name(prefix: str, extra_dice: tuple[str, str, str]) -> str:
    """Encode one legal core-dice multiset as a compact stable name."""
    berserker_count = extra_dice.count("DIE_BERSERKER")
    warden_count = extra_dice.count("DIE_WARDEN")
    miser_count = extra_dice.count("DIE_MISER")
    return f"{prefix}_CORE_B{berserker_count}{warden_count}{miser_count}"


def _build_candidates(
    prefix: str,
    archetype: str,
    gp_ids: tuple[str, ...],
    agent_cls: type,
) -> dict[str, ArchetypeLoadout]:
    """Build every legal loadout for one archetype under the shared core grammar."""
    candidates: dict[str, ArchetypeLoadout] = {}
    for extra_dice in combinations_with_replacement(CORE_DICE, 3):
        name = _candidate_name(prefix, extra_dice)
        candidates[name] = _make_loadout(name, archetype, extra_dice, gp_ids, agent_cls)
    return candidates


RULE_BASED_CLASSES = agent_classes("rule-based")

AGGRO_CANDIDATES = _build_candidates(
    "A",
    "AGGRO",
    ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
    RULE_BASED_CLASSES["AGGRO"],
)

CONTROL_CANDIDATES = _build_candidates(
    "C",
    "CONTROL",
    ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
    RULE_BASED_CLASSES["CONTROL"],
)

ECONOMY_CANDIDATES = _build_candidates(
    "E",
    "ECONOMY",
    ("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
    RULE_BASED_CLASSES["ECONOMY"],
)
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
