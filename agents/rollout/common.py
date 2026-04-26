"""Shared rollout helpers for GP-choice search.

The first rollout family keeps the existing keep/reroll heuristics and only
searches over the current God Power decision. Each candidate GP choice is
scored by simulating the rest of the match with the current loadout/location-
aware heuristic pilots.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TypeAlias

import numpy as np

from agents.game_aware.evaluator import affordable_choices, score_gp_choice
from agents.game_aware.gp_loadout import infer_archetype_from_gp_loadout
from agents.game_aware.state_features import view_for
from agents.game_aware_tier_loadout.aggro_agent import GameAwareTierLoadoutAggroAgent
from agents.game_aware_tier_loadout.control_agent import GameAwareTierLoadoutControlAgent
from agents.game_aware_tier_loadout.economy_agent import GameAwareTierLoadoutEconomyAgent
from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GameEvent, GamePhase, GameState
from game_mechanics.god_powers import GodPower

HeuristicAgentCls: TypeAlias = type

ROLLOUT_TIER_ORDER: tuple[int, ...] = (2, 1, 0)
ROLLOUTS_PER_CHOICE = 2
MAX_CANDIDATES = 3
MAX_GAME_ROUNDS = 80
WIN_SCORE = 100.0

_HEURISTIC_CLASSES: dict[str, HeuristicAgentCls] = {
    "AGGRO": GameAwareTierLoadoutAggroAgent,
    "CONTROL": GameAwareTierLoadoutControlAgent,
    "ECONOMY": GameAwareTierLoadoutEconomyAgent,
}


def _child_rng(rng: np.random.Generator) -> np.random.Generator:
    """Create an independent RNG stream for one rollout component."""
    return np.random.default_rng(int(rng.integers(0, 2**63 - 1)))


def _resolve_die_loadout(die_ids: tuple[str, ...]):
    """Resolve die ids into concrete die definitions for the engine."""
    die_types = load_die_types()
    return [die_types[die_id] for die_id in die_ids]


def _heuristic_class_for_player(
    gp_loadout: tuple[str, ...],
    god_powers: dict[str, GodPower],
) -> HeuristicAgentCls:
    """Infer the current player's heuristic archetype from the equipped GP loadout."""
    role = infer_archetype_from_gp_loadout(gp_loadout, god_powers)
    return _HEURISTIC_CLASSES[role]


def _simulate_to_game_over(
    engine: GameEngine,
    state: GameState,
    p1_agent,
    p2_agent,
    *,
    first_p1_action: tuple[str, int] | None = None,
    first_p2_action: tuple[str, int] | None = None,
    max_rounds: int = MAX_GAME_ROUNDS,
) -> GameState:
    """Advance from an arbitrary state until GAME_OVER using the supplied agents."""
    first_step_done = False

    while state.phase != GamePhase.GAME_OVER:
        if state.round_num > max_rounds:
            return replace(state, phase=GamePhase.GAME_OVER, winner=0)

        if state.phase == GamePhase.KEEP_1:
            state, _ = engine.step(
                state,
                p1_agent.choose_keep(state, 1),
                p2_agent.choose_keep(state, 2),
            )
            continue
        if state.phase == GamePhase.KEEP_2:
            state, _ = engine.step(
                state,
                p1_agent.choose_keep(state, 1),
                p2_agent.choose_keep(state, 2),
            )
            continue
        if state.phase == GamePhase.GOD_POWER:
            if not first_step_done:
                p1_action = first_p1_action
                p2_action = first_p2_action
                first_step_done = True
            else:
                p1_action = p1_agent.choose_god_power(state, 1)
                p2_action = p2_agent.choose_god_power(state, 2)
            state, _ = engine.step(state, p1_action, p2_action)
            continue
        state, _ = engine.step(state)

    return state


def _terminal_value(state: GameState, player_num: int) -> float:
    """Score one terminal state from the rollout player's perspective."""
    me = state.p1 if player_num == 1 else state.p2
    opp = state.p2 if player_num == 1 else state.p1
    hp_diff = float(me.hp - opp.hp)

    if state.winner == player_num:
        return WIN_SCORE + hp_diff - (state.round_num * 0.1)
    if state.winner == 0:
        return hp_diff * 0.5
    return -WIN_SCORE + hp_diff + (state.round_num * 0.1)


def _rollout_value(
    state: GameState,
    player_num: int,
    choice: tuple[str, int] | None,
    *,
    rng: np.random.Generator,
    god_powers: dict[str, GodPower],
    current_heuristic_cls: HeuristicAgentCls,
) -> float:
    """Evaluate one GP choice by rolling the rest of the game forward."""
    engine = GameEngine(
        p1_die_types=_resolve_die_loadout(state.p1.die_loadout),
        p2_die_types=_resolve_die_loadout(state.p2.die_loadout),
        rng=_child_rng(rng),
        p1_gp_ids=state.p1.gp_loadout,
        p2_gp_ids=state.p2.gp_loadout,
        god_powers=god_powers,
        condition_ids=state.condition_ids,
    )

    if player_num == 1:
        p1_agent = current_heuristic_cls(rng=_child_rng(rng), god_powers=god_powers)
        p2_cls = _heuristic_class_for_player(state.p2.gp_loadout, god_powers)
        p2_agent = p2_cls(rng=_child_rng(rng), god_powers=god_powers)
        opponent_choice = p2_agent.choose_god_power(state, 2)
        end_state = _simulate_to_game_over(
            engine,
            state,
            p1_agent,
            p2_agent,
            first_p1_action=choice,
            first_p2_action=opponent_choice,
        )
    else:
        p1_cls = _heuristic_class_for_player(state.p1.gp_loadout, god_powers)
        p1_agent = p1_cls(rng=_child_rng(rng), god_powers=god_powers)
        p2_agent = current_heuristic_cls(rng=_child_rng(rng), god_powers=god_powers)
        opponent_choice = p1_agent.choose_god_power(state, 1)
        end_state = _simulate_to_game_over(
            engine,
            state,
            p1_agent,
            p2_agent,
            first_p1_action=opponent_choice,
            first_p2_action=choice,
        )

    return _terminal_value(end_state, player_num)


def choose_gp_by_rollout(
    state: GameState,
    player_num: int,
    *,
    rng: np.random.Generator,
    god_powers: dict[str, GodPower],
    heuristic_choice: tuple[str, int] | None,
    current_heuristic_cls: HeuristicAgentCls,
) -> tuple[str, int] | None:
    """Choose the best GP by simulating a short shortlist of candidate choices."""
    view = view_for(state, player_num)
    candidates = affordable_choices(view, god_powers, tier_order=ROLLOUT_TIER_ORDER)
    if heuristic_choice is not None and heuristic_choice not in candidates:
        candidates.append(heuristic_choice)

    heuristic_scores: dict[tuple[str, int] | None, float] = {None: -0.25}
    for choice in candidates:
        heuristic_scores[choice] = score_gp_choice(
            view,
            god_powers,
            choice,
            threat_tier_order=ROLLOUT_TIER_ORDER,
        )

    ordered = sorted(
        candidates,
        key=lambda choice: (heuristic_scores[choice], choice[1], choice[0]),
        reverse=True,
    )
    shortlist: list[tuple[str, int] | None] = ordered[:MAX_CANDIDATES]
    if heuristic_choice not in shortlist:
        shortlist.append(heuristic_choice)
    if None not in shortlist:
        shortlist.append(None)
    shortlist = [choice for idx, choice in enumerate(shortlist) if choice not in shortlist[:idx]]

    if shortlist == [None]:
        return None
    if len(shortlist) == 1:
        return shortlist[0]

    best_choice = heuristic_choice
    best_value = float("-inf")
    best_heuristic = heuristic_scores.get(heuristic_choice, -999.0)

    for choice in shortlist:
        total = 0.0
        for _ in range(ROLLOUTS_PER_CHOICE):
            total += _rollout_value(
                state,
                player_num,
                choice,
                rng=rng,
                god_powers=god_powers,
                current_heuristic_cls=current_heuristic_cls,
            )
        average = total / ROLLOUTS_PER_CHOICE
        heuristic_score = heuristic_scores.get(choice, -999.0)
        if average > best_value or (average == best_value and heuristic_score > best_heuristic):
            best_choice = choice
            best_value = average
            best_heuristic = heuristic_score

    return best_choice
