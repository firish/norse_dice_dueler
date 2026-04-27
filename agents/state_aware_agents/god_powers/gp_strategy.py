"""Shared GP-choice logic for game-aware and game+tier-aware agents."""

from __future__ import annotations

from collections.abc import Mapping

from agents.state_aware_agents.state.state_evaluator import best_scored_gp
from agents.state_aware_agents.god_powers.gp_scoring import MEANINGFUL_GP_THREAT_SCORE
from agents.state_aware_agents.god_powers.gp_loadout import (
    equipped_gp_ids,
    equipped_gp_ids_matching,
    merge_gp_priority_groups,
)
from agents.state_aware_agents.state.state_features import (
    AgentView,
    estimate_opponent_gp_damage,
    estimate_opponent_gp_value,
    estimate_total_threat,
    opponent_has_role,
)
from game_mechanics.god_powers import GodPower

# Strategy policy thresholds.
# These are intentionally separate from `gp_scoring.py`, which defines the
# shared GP effect score scale rather than agent decision policy.
FORCE_CHOICE_SCORE_FLOOR = -999.0
SPECULATIVE_CHOICE_SCORE_FLOOR = -0.1
LOW_CONFIDENCE_CHOICE_SCORE_FLOOR = 0.1
DEFAULT_CHOICE_SCORE_FLOOR = 0.2
PRESSURED_RACE_CHOICE_SCORE_FLOOR = 0.4

COUNTER_TOKEN_THREAT_THRESHOLD = 5
PROACTIVE_CONTROL_MIN_SAFE_HP = 5
AGGRO_PRESSURE_INCOMING_DAMAGE_THRESHOLD = 2
RAMP_TOKEN_THRESHOLD_VS_CONTROL = 9
RAMP_TOKEN_THRESHOLD_DEFAULT = 12


def _role_groups(view: AgentView, god_powers: Mapping[str, GodPower]) -> dict[str, tuple[str, ...]]:
    """Return equipped GP subsets grouped by generic tactical roles."""
    player = view.player
    return {
        "all": equipped_gp_ids(player, god_powers),
        "burst": equipped_gp_ids_matching(player, god_powers, primary_roles=("burst",)),
        "finisher": equipped_gp_ids_matching(player, god_powers, primary_roles=("finisher",)),
        "block": equipped_gp_ids_matching(player, god_powers, primary_roles=("block",), tags=("block",)),
        "heal": equipped_gp_ids_matching(player, god_powers, primary_roles=("heal",), tags=("heal",)),
        "ramp": equipped_gp_ids_matching(player, god_powers, primary_roles=("ramp",), tags=("ramp", "token_gain")),
        "counter": equipped_gp_ids_matching(player, god_powers, primary_roles=("counter",), tags=("counter",)),
        "anti_race": equipped_gp_ids_matching(
            player,
            god_powers,
            primary_roles=("anti_race",),
            tags=("anti_race", "reflect"),
        ),
        "hybrid": equipped_gp_ids_matching(
            player,
            god_powers,
            primary_roles=("hybrid_pressure",),
            tags=("hybrid_pressure",),
        ),
        "direct": equipped_gp_ids_matching(player, god_powers, tags=("direct_damage",)),
    }


def _lethal_filter(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
):
    """Return a predicate that keeps only safe lethal GP choices."""

    def _predicate(gp_id: str, tier_idx: int) -> bool:
        tier = god_powers[gp_id].tiers[tier_idx]
        return tier.damage >= view.opponent.hp and view.player.hp > tier.self_damage

    return _predicate


def _choose_from_groups(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    priority_groups: tuple[tuple[str, ...], ...],
    *,
    tier_order: tuple[int, ...],
    threat_tier_order: tuple[int, ...],
    minimum_score: float,
) -> tuple[str, int] | None:
    """Try ordered GP groups one at a time, returning the first viable choice."""
    for group in priority_groups:
        if not group:
            continue
        choice = best_scored_gp(
            view,
            god_powers,
            group,
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=minimum_score,
        )
        if choice is not None:
            return choice
    return None


def choose_aggro_gp(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    *,
    tier_order: tuple[int, ...] = (0,),
    threat_tier_order: tuple[int, ...] = (0,),
) -> tuple[str, int] | None:
    """Choose an equipped GP for an Aggro pilot using role-aware priorities."""
    groups = _role_groups(view, god_powers)
    lethal_priority = merge_gp_priority_groups(groups["finisher"], groups["burst"], groups["direct"], groups["hybrid"])
    lethal = best_scored_gp(
        view,
        god_powers,
        lethal_priority,
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=FORCE_CHOICE_SCORE_FLOOR,
        choice_filter=_lethal_filter(view, god_powers),
    )
    if lethal is not None:
        return lethal

    if opponent_has_role(view, "control", dict(god_powers)):
        choice = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["finisher"], groups["hybrid"], groups["burst"], groups["all"]),
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=LOW_CONFIDENCE_CHOICE_SCORE_FLOOR,
        )
        if choice is not None:
            return choice

    if opponent_has_role(view, "economy", dict(god_powers)):
        choice = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["finisher"], groups["burst"], groups["hybrid"], groups["all"]),
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=LOW_CONFIDENCE_CHOICE_SCORE_FLOOR,
        )
        if choice is not None:
            return choice

    return best_scored_gp(
        view,
        god_powers,
        merge_gp_priority_groups(groups["burst"], groups["finisher"], groups["hybrid"], groups["all"]),
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=DEFAULT_CHOICE_SCORE_FLOOR,
    )


def choose_control_gp(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    *,
    tier_order: tuple[int, ...] = (0,),
    threat_tier_order: tuple[int, ...] = (0,),
) -> tuple[str, int] | None:
    """Choose an equipped GP for a Control pilot using role-aware priorities."""
    groups = _role_groups(view, god_powers)
    incoming_gp = estimate_opponent_gp_damage(view, tier_order=threat_tier_order, god_powers=dict(god_powers))
    incoming_gp_value = estimate_opponent_gp_value(view, tier_order=threat_tier_order, god_powers=dict(god_powers))
    threat = estimate_total_threat(view, tier_order=threat_tier_order, god_powers=dict(god_powers))

    if opponent_has_role(view, "economy", dict(god_powers)):
        if (
            incoming_gp_value >= MEANINGFUL_GP_THREAT_SCORE
            or view.opponent.tokens >= COUNTER_TOKEN_THREAT_THRESHOLD
        ) and groups["counter"]:
            counter = best_scored_gp(
                view,
                god_powers,
                merge_gp_priority_groups(groups["counter"], groups["all"]),
                tier_order=tier_order,
                threat_tier_order=threat_tier_order,
                minimum_score=SPECULATIVE_CHOICE_SCORE_FLOOR,
            )
            if counter is not None:
                return counter
        if threat < max(PROACTIVE_CONTROL_MIN_SAFE_HP, view.player.hp):
            proactive = best_scored_gp(
                view,
                god_powers,
                merge_gp_priority_groups(groups["counter"], groups["hybrid"], groups["anti_race"], groups["all"]),
                tier_order=tier_order,
                threat_tier_order=threat_tier_order,
                minimum_score=FORCE_CHOICE_SCORE_FLOOR,
            )
            if proactive is not None:
                return proactive
        if incoming_gp > 0 or incoming_gp_value >= MEANINGFUL_GP_THREAT_SCORE:
            direct_answer = best_scored_gp(
                view,
                god_powers,
                merge_gp_priority_groups(groups["counter"], groups["hybrid"], groups["anti_race"], groups["block"], groups["heal"], groups["all"]),
                tier_order=tier_order,
                threat_tier_order=threat_tier_order,
                minimum_score=DEFAULT_CHOICE_SCORE_FLOOR,
            )
            if direct_answer is not None:
                return direct_answer

    return best_scored_gp(
        view,
        god_powers,
        merge_gp_priority_groups(groups["block"], groups["heal"], groups["anti_race"], groups["hybrid"], groups["all"]),
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=DEFAULT_CHOICE_SCORE_FLOOR,
    )


def choose_economy_gp(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    *,
    tier_order: tuple[int, ...] = (0,),
    threat_tier_order: tuple[int, ...] = (0,),
) -> tuple[str, int] | None:
    """Choose an equipped GP for an Economy pilot using role-aware priorities."""
    groups = _role_groups(view, god_powers)
    offensive_priority = merge_gp_priority_groups(groups["finisher"], groups["direct"], groups["hybrid"], groups["burst"])
    lethal = best_scored_gp(
        view,
        god_powers,
        offensive_priority,
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=FORCE_CHOICE_SCORE_FLOOR,
        choice_filter=_lethal_filter(view, god_powers),
    )
    if lethal is not None:
        return lethal

    threat = estimate_total_threat(view, tier_order=threat_tier_order, god_powers=dict(god_powers))
    if opponent_has_role(view, "aggro", dict(god_powers)) and (
        view.combat.incoming_total >= AGGRO_PRESSURE_INCOMING_DAMAGE_THRESHOLD or threat >= view.player.hp
    ):
        anti_race = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["anti_race"], groups["block"], groups["heal"], groups["all"]),
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=LOW_CONFIDENCE_CHOICE_SCORE_FLOOR,
        )
        if anti_race is not None:
            return anti_race

        race_answer = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["finisher"], groups["all"]),
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=PRESSURED_RACE_CHOICE_SCORE_FLOOR,
        )
        if race_answer is not None:
            return race_answer

    cashout = best_scored_gp(
        view,
        god_powers,
        merge_gp_priority_groups(groups["finisher"], groups["all"]),
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=DEFAULT_CHOICE_SCORE_FLOOR,
    )
    if cashout is not None and threat < view.player.hp:
        return cashout

    if opponent_has_role(view, "control", dict(god_powers)):
        ramp_threshold = RAMP_TOKEN_THRESHOLD_VS_CONTROL
        ramp_tier_order = tuple(idx for idx in tier_order if idx in (1, 0)) or tier_order
    else:
        ramp_threshold = RAMP_TOKEN_THRESHOLD_DEFAULT
        ramp_tier_order = tier_order
    if view.player.tokens < ramp_threshold:
        ramp = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["ramp"], groups["all"]),
            tier_order=ramp_tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=DEFAULT_CHOICE_SCORE_FLOOR,
        )
        if ramp is not None:
            return ramp

    return cashout
