"""Shared GP-choice logic for game-aware and game+tier-aware agents."""

from __future__ import annotations

from collections.abc import Mapping

from agents.game_aware.evaluator import best_scored_gp
from agents.game_aware.gp_loadout import (
    equipped_gp_ids,
    equipped_gp_ids_matching,
    merge_gp_priority_groups,
    minimum_tier_cost,
)
from agents.game_aware.state_features import (
    AgentView,
    estimate_opponent_gp_damage,
    estimate_total_threat,
    opponent_has_role,
)
from game_mechanics.god_powers import GodPower


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
        minimum_score=-999.0,
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
            minimum_score=0.1,
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
            minimum_score=0.1,
        )
        if choice is not None:
            return choice

    return best_scored_gp(
        view,
        god_powers,
        merge_gp_priority_groups(groups["burst"], groups["finisher"], groups["hybrid"], groups["all"]),
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=0.2,
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
    threat = estimate_total_threat(view, tier_order=threat_tier_order, god_powers=dict(god_powers))

    if opponent_has_role(view, "economy", dict(god_powers)):
        if threat < max(5, view.player.hp):
            proactive = best_scored_gp(
                view,
                god_powers,
                merge_gp_priority_groups(groups["hybrid"], groups["counter"], groups["all"]),
                tier_order=tier_order,
                threat_tier_order=threat_tier_order,
                minimum_score=-999.0,
            )
            if proactive is not None:
                return proactive
        if incoming_gp > 0:
            direct_answer = best_scored_gp(
                view,
                god_powers,
                merge_gp_priority_groups(groups["hybrid"], groups["block"], groups["heal"], groups["all"]),
                tier_order=tier_order,
                threat_tier_order=threat_tier_order,
                minimum_score=0.2,
            )
            if direct_answer is not None:
                return direct_answer

    return best_scored_gp(
        view,
        god_powers,
        merge_gp_priority_groups(groups["block"], groups["heal"], groups["hybrid"], groups["all"]),
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=0.2,
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
        minimum_score=-999.0,
        choice_filter=_lethal_filter(view, god_powers),
    )
    if lethal is not None:
        return lethal

    threat = estimate_total_threat(view, tier_order=threat_tier_order, god_powers=dict(god_powers))
    if opponent_has_role(view, "aggro", dict(god_powers)) and (
        view.combat.incoming_total >= 2 or threat >= view.player.hp
    ):
        anti_race = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["anti_race"], groups["block"], groups["heal"], groups["all"]),
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=0.1,
        )
        if anti_race is not None:
            return anti_race

        race_answer = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["finisher"], groups["all"]),
            tier_order=tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=0.4,
        )
        if race_answer is not None:
            return race_answer

    cashout = best_scored_gp(
        view,
        god_powers,
        merge_gp_priority_groups(groups["finisher"], groups["all"]),
        tier_order=tier_order,
        threat_tier_order=threat_tier_order,
        minimum_score=0.2,
    )
    if cashout is not None and threat < view.player.hp:
        return cashout

    if opponent_has_role(view, "control", dict(god_powers)):
        ramp_threshold = 9
        ramp_tier_order = tuple(idx for idx in tier_order if idx in (1, 0)) or tier_order
    else:
        ramp_threshold = 12
        ramp_tier_order = tier_order
    if view.player.tokens < ramp_threshold:
        ramp = best_scored_gp(
            view,
            god_powers,
            merge_gp_priority_groups(groups["ramp"], groups["all"]),
            tier_order=ramp_tier_order,
            threat_tier_order=threat_tier_order,
            minimum_score=0.2,
        )
        if ramp is not None:
            return ramp

    return cashout
