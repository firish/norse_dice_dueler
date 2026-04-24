"""Shared matchup and matrix helpers for benchmark and search harnesses."""

from __future__ import annotations

from typing import Any

import numpy as np

from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GamePhase
from simulator.common.harness_types import ArchetypeLike

DIRECTIONAL_MATCHUPS: tuple[tuple[str, str], ...] = (
    ("AGGRO", "CONTROL"),
    ("CONTROL", "AGGRO"),
    ("AGGRO", "ECONOMY"),
    ("ECONOMY", "AGGRO"),
    ("CONTROL", "ECONOMY"),
    ("ECONOMY", "CONTROL"),
)


def resolve_dice(ids: tuple[str, ...]) -> list[Any]:
    """Resolve die ids into the concrete six-die loadout."""
    die_types = load_die_types()
    return [die_types[die_id] for die_id in ids]


def run_directional_matchup(
    p1_arch: ArchetypeLike,
    p2_arch: ArchetypeLike,
    games: int,
    rng: np.random.Generator,
    *,
    god_powers: dict[str, Any] | None = None,
    condition_id: str | None = None,
    condition_ids: tuple[str, ...] | None = None,
) -> dict[str, float | int]:
    """Run one directional matchup and return shared summary statistics."""
    p1_dice = resolve_dice(p1_arch.dice_ids)
    p2_dice = resolve_dice(p2_arch.dice_ids)

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
            god_powers=god_powers,
            condition_id=condition_id,
            condition_ids=condition_ids,
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
        if state.winner != 0 and winner_hp - loser_hp <= 4:
            close_matches += 1

    decisive = p1_wins + p2_wins
    p1_rate = (p1_wins / decisive * 100) if decisive else 0.0
    return {
        "p1_wins": p1_wins,
        "p2_wins": p2_wins,
        "draws": draws,
        "p1_rate": p1_rate,
        "p1_win_rate_decisive": p1_rate,
        "avg_rounds": total_rounds / games,
        "avg_winner_hp": (total_winner_hp / decisive) if decisive else 0.0,
        "close_match_rate": close_matches / games * 100,
    }


def run_matrix(
    archetypes: dict[str, ArchetypeLike],
    games: int,
    seed: int,
    *,
    include_mirrors: bool,
    god_powers: dict[str, Any] | None = None,
    condition_id: str | None = None,
    condition_ids: tuple[str, ...] | None = None,
) -> dict[tuple[str, str], dict[str, float | int]]:
    """Run a full matrix for the provided archetype package."""
    rng = np.random.default_rng(seed)
    results: dict[tuple[str, str], dict[str, float | int]] = {}
    for p1 in archetypes:
        for p2 in archetypes:
            if not include_mirrors and p1 == p2:
                continue
            results[(p1, p2)] = run_directional_matchup(
                archetypes[p1],
                archetypes[p2],
                games,
                rng,
                god_powers=god_powers,
                condition_id=condition_id,
                condition_ids=condition_ids,
            )
    return results


def matrix_error(
    results: dict[tuple[str, str], dict[str, float | int]],
    targets: dict[tuple[str, str], float],
    *,
    rate_key: str = "p1_rate",
) -> float:
    """Return absolute error from the supplied directional target matrix."""
    return sum(abs(float(results[key][rate_key]) - target) for key, target in targets.items())
