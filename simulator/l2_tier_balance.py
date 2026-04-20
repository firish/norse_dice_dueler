"""L2 tier-escalation balance harness for the tuned three-archetype shell.

Question:
  - If we re-enable T2/T3, does the same Aggro / Control / Economy shape survive?
  - Can we tune only T2/T3 values while keeping the balanced T1 shell intact?

Default behavior:
  - Search a small T2/T3-only profile space.
  - Report the best profiles by matrix error.

Run:
    python -m simulator.l2_tier_balance
    python -m simulator.l2_tier_balance --games 40 --top 10
    python -m simulator.l2_tier_balance --validate SURTR69_GULL710_MJ1418_BRAGI75_106
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from itertools import product

import numpy as np

from simulator.agents.aggro_agent import TierAwareAggroAgent
from simulator.agents.control_agent import TierAwareControlAgent
from simulator.agents.economy_agent import TierAwareEconomyAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine
from simulator.game_state import GamePhase
from simulator.god_powers import GodPower, load_god_powers

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
    """Archetype definition used by the tier-balance harness."""

    name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


@dataclass(frozen=True)
class TierProfile:
    """Compact description of the T2/T3 tuning knobs explored by the harness."""

    name: str
    control_soft: bool
    surtr_t2_cost: int
    surtr_t3_cost: int
    gullveig_t2_cost: int
    gullveig_t3_cost: int
    mjolnir_t2_cost: int
    mjolnir_t3_cost: int
    bragi_t2_cost: int
    bragi_t2_reduce: int
    bragi_t2_reflect: float
    bragi_t3_cost: int
    bragi_t3_reduce: int
    bragi_t3_reflect: float


ARCHETYPES: dict[str, Archetype] = {
    "AGGRO": Archetype(
        name="AGGRO",
        dice_ids=(
            "DIE_BERSERKER", "DIE_BERSERKER", "DIE_BERSERKER", "DIE_BERSERKER",
            "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_TYRS_JUDGMENT"),
        agent_cls=TierAwareAggroAgent,
    ),
    "CONTROL": Archetype(
        name="CONTROL",
        dice_ids=(
            "DIE_WARDEN", "DIE_WARDEN", "DIE_WARDEN",
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        agent_cls=TierAwareControlAgent,
    ),
    "ECONOMY": Archetype(
        name="ECONOMY",
        dice_ids=(
            "DIE_MISER", "DIE_MISER", "DIE_MISER",
            "DIE_WARRIOR", "DIE_WARRIOR", "DIE_WARRIOR",
        ),
        gp_ids=("GP_MJOLNIRS_WRATH", "GP_GULLVEIGS_HOARD", "GP_BRAGIS_SONG"),
        agent_cls=TierAwareEconomyAgent,
    ),
}


def build_god_powers(profile: TierProfile) -> dict[str, GodPower]:
    """Return a God Power table with the profile's T2/T3 overrides applied."""
    god_powers = load_god_powers()

    if profile.control_soft:
        aegis = god_powers["GP_AEGIS_OF_BALDR"]
        god_powers["GP_AEGIS_OF_BALDR"] = replace(
            aegis,
            tiers=(
                aegis.tiers[0],
                replace(aegis.tiers[1], cost=8, block_amount=4),
                replace(aegis.tiers[2], cost=12, block_amount=6),
            ),
        )

        eir = god_powers["GP_EIRS_MERCY"]
        god_powers["GP_EIRS_MERCY"] = replace(
            eir,
            tiers=(
                eir.tiers[0],
                replace(eir.tiers[1], cost=9, heal=3),
                replace(eir.tiers[2], cost=12, heal=5),
            ),
        )

        tyr = god_powers["GP_TYRS_JUDGMENT"]
        god_powers["GP_TYRS_JUDGMENT"] = replace(
            tyr,
            tiers=(
                tyr.tiers[0],
                replace(tyr.tiers[1], cost=9, damage=3, block_amount=2),
                replace(tyr.tiers[2], cost=12, damage=4, block_amount=3),
            ),
        )

    gullveig = god_powers["GP_GULLVEIGS_HOARD"]
    god_powers["GP_GULLVEIGS_HOARD"] = replace(
        gullveig,
        tiers=(
            gullveig.tiers[0],
            replace(gullveig.tiers[1], cost=profile.gullveig_t2_cost),
            replace(gullveig.tiers[2], cost=profile.gullveig_t3_cost),
        ),
    )

    surtr = god_powers["GP_SURTRS_FLAME"]
    god_powers["GP_SURTRS_FLAME"] = replace(
        surtr,
        tiers=(
            surtr.tiers[0],
            replace(surtr.tiers[1], cost=profile.surtr_t2_cost),
            replace(surtr.tiers[2], cost=profile.surtr_t3_cost),
        ),
    )

    mjolnir = god_powers["GP_MJOLNIRS_WRATH"]
    god_powers["GP_MJOLNIRS_WRATH"] = replace(
        mjolnir,
        tiers=(
            mjolnir.tiers[0],
            replace(mjolnir.tiers[1], cost=profile.mjolnir_t2_cost),
            replace(mjolnir.tiers[2], cost=profile.mjolnir_t3_cost),
        ),
    )

    bragi = god_powers["GP_BRAGIS_SONG"]
    god_powers["GP_BRAGIS_SONG"] = replace(
        bragi,
        tiers=(
            bragi.tiers[0],
            replace(
                bragi.tiers[1],
                cost=profile.bragi_t2_cost,
                effect=f"Prevent up to {profile.bragi_t2_reduce} dice-combat damage and reflect part back.",
                damage_reduction=profile.bragi_t2_reduce,
                reflect_pct=profile.bragi_t2_reflect,
            ),
            replace(
                bragi.tiers[2],
                cost=profile.bragi_t3_cost,
                effect=f"Prevent up to {profile.bragi_t3_reduce} dice-combat damage and reflect part back.",
                damage_reduction=profile.bragi_t3_reduce,
                reflect_pct=profile.bragi_t3_reflect,
            ),
        ),
    )

    return god_powers


def generate_profiles() -> list[TierProfile]:
    """Enumerate the compact search space of tier-balance candidates."""
    profiles: list[TierProfile] = []
    for (
        control_soft,
        surtr_t2_cost,
        surtr_t3_cost,
        gullveig_t2_cost,
        gullveig_t3_cost,
        mjolnir_t2_cost,
        mjolnir_t3_cost,
        bragi_t2,
        bragi_t3,
    ) in product(
        (False, True),
        (6, 7),
        (9, 10),
        (7,),
        (10,),
        (14,),
        (18,),
        ((7, 5, 0.5), (7, 6, 0.5), (8, 5, 0.5)),
        ((10, 6, 0.66), (10, 7, 0.66), (11, 6, 0.66)),
    ):
        b2_cost, b2_reduce, b2_reflect = bragi_t2
        b3_cost, b3_reduce, b3_reflect = bragi_t3
        name = (
            f"{'SOFTCTRL_' if control_soft else ''}"
            f"SURTR{surtr_t2_cost}{surtr_t3_cost}_"
            f"GULL{gullveig_t2_cost}{gullveig_t3_cost}_"
            f"MJ{mjolnir_t2_cost}{mjolnir_t3_cost}_"
            f"BRAGI{b2_cost}{b2_reduce}_{b3_cost}{b3_reduce}"
        )
        profiles.append(
            TierProfile(
                name=name,
                control_soft=control_soft,
                surtr_t2_cost=surtr_t2_cost,
                surtr_t3_cost=surtr_t3_cost,
                gullveig_t2_cost=gullveig_t2_cost,
                gullveig_t3_cost=gullveig_t3_cost,
                mjolnir_t2_cost=mjolnir_t2_cost,
                mjolnir_t3_cost=mjolnir_t3_cost,
                bragi_t2_cost=b2_cost,
                bragi_t2_reduce=b2_reduce,
                bragi_t2_reflect=b2_reflect,
                bragi_t3_cost=b3_cost,
                bragi_t3_reduce=b3_reduce,
                bragi_t3_reflect=b3_reflect,
            )
        )
    return profiles


def _resolve_dice(ids: tuple[str, ...]):
    """Resolve die ids into the concrete six-die loadout."""
    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_matchup(
    p1_arch: Archetype,
    p2_arch: Archetype,
    god_powers: dict[str, GodPower],
    games: int,
    rng: np.random.Generator,
) -> dict:
    """Run one directional matchup under a specific tier profile."""
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
            god_powers=god_powers,
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


def run_profile(profile: TierProfile, games: int, seed: int) -> dict[tuple[str, str], dict]:
    """Run the full off-diagonal matrix for one tier profile."""
    rng = np.random.default_rng(seed)
    god_powers = build_god_powers(profile)
    results: dict[tuple[str, str], dict] = {}
    for p1 in ARCHETYPES:
        for p2 in ARCHETYPES:
            if p1 == p2:
                continue
            results[(p1, p2)] = run_matchup(ARCHETYPES[p1], ARCHETYPES[p2], god_powers, games, rng)
    return results


def matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the target directional matrix."""
    return sum(abs(results[key]["p1_rate"] - target) for key, target in TARGETS.items())


def print_results(name: str, results: dict[tuple[str, str], dict]) -> None:
    """Print a compact report for one tier profile."""
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


def search_profiles(games: int, seed: int, top: int) -> None:
    """Score the full profile search space and print the best candidates."""
    scored: list[tuple[float, TierProfile, dict[tuple[str, str], dict]]] = []
    for profile in generate_profiles():
        results = run_profile(profile, games, seed)
        scored.append((matrix_error(results), profile, results))

    scored.sort(key=lambda item: item[0])
    for error, profile, results in scored[:top]:
        print_results(f"{profile.name}  error={error:.1f}", results)
        print()


def main() -> None:
    """CLI entrypoint for the tier-balance search and validation harness."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=40, help="games per directional matchup")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument("--top", type=int, default=8, help="profiles to print in search mode")
    parser.add_argument("--validate", type=str, default="", help="validate one profile by name")
    args = parser.parse_args()

    profiles = {profile.name: profile for profile in generate_profiles()}
    if args.validate:
        if args.validate not in profiles:
            raise ValueError(f"Unknown profile: {args.validate}")
        results = run_profile(profiles[args.validate], args.games, args.seed)
        print_results(args.validate, results)
        return

    search_profiles(args.games, args.seed, args.top)


if __name__ == "__main__":
    main()
