"""Shared scoring functions for game-aware agents."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from agents.state_aware_agents.god_powers.gp_scoring import (
    GP_BLOCK_LETHAL_URGENCY_BONUS,
    GP_CANCEL_DIRECT_THREAT_BONUS,
    GP_CANCEL_NO_TARGET_PENALTY,
    GP_CANCEL_THREAT_BONUS_CAP,
    GP_CANCEL_THREAT_BONUS_MULTIPLIER,
    GP_CANCEL_TOKEN_PRESENCE_VALUE,
    GP_CANCEL_TOKEN_WINDOW_CAP,
    GP_COST_POINT_PENALTY,
    GP_DAMAGE_REDUCTION_LETHAL_URGENCY_BONUS,
    GP_HEAL_LOW_HP_URGENCY_BONUS,
    GP_HIGHER_TIER_PENALTY,
    GP_LOW_HP_URGENCY_THRESHOLD,
    GP_REFLECT_POINT_VALUE,
    GP_SELF_DAMAGE_LOW_HP_PENALTY,
    GP_SELF_DAMAGE_POINT_PENALTY,
    GP_TOKEN_UNDER_PRESSURE_COST_PENALTY,
    GP_UNUSED_BLOCK_PENALTY,
    GP_UNUSED_DAMAGE_REDUCTION_PENALTY,
    GP_UNUSED_HEAL_PENALTY,
    GP_WASTED_DAMAGE_PENALTY,
    score_tier_core_impact,
)
from agents.state_aware_agents.locations.location_bias import adjust_keep_scores, choice_location_bonus
from agents.state_aware_agents.locations.location_rules import effective_gp_cost, gp_activation_blocked
from agents.state_aware_agents.state.state_features import AgentView, estimate_opponent_gp_damage, estimate_opponent_gp_value
from game_mechanics.god_powers import GodPower


def affordable_choices(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    tier_order: Iterable[int] = (0,),
) -> list[tuple[str, int]]:
    """Return all legal GP/tier choices the player can currently afford."""
    choices: list[tuple[str, int]] = []
    if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
        return choices
    player = view.player
    for gp_id in player.gp_loadout:
        gp = god_powers.get(gp_id)
        if gp is None:
            continue
        for tier_idx in tier_order:
            if choice_cost(view, god_powers, gp_id, tier_idx) <= view.available_tokens:
                choices.append((gp_id, tier_idx))
    return choices


def choose_keep_by_scores(
    view: AgentView,
    face_scores: Mapping[str, float],
    keep_threshold: float = 0.0,
) -> frozenset[int]:
    """Keep unlocked dice whose current faces score above `keep_threshold`."""
    scores = adjust_keep_scores(view, face_scores)
    kept: set[int] = set()
    for idx, (face, already_kept) in enumerate(zip(view.player.dice_faces, view.player.dice_kept)):
        if already_kept:
            continue
        if scores.get(face, -999.0) >= keep_threshold:
            kept.add(idx)
    return frozenset(kept)


def choice_cost(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    gp_id: str,
    tier_idx: int,
) -> int:
    """Return the effective cost of one GP/tier choice under current conditions."""
    gp = god_powers.get(gp_id)
    if gp is None:
        return 10**9
    return effective_gp_cost(gp.tiers[tier_idx].cost, view.state.round_num, view.state.condition_ids)


def try_view_gp(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    gp_id: str,
    tier_order: Iterable[int],
) -> tuple[str, int] | None:
    """Return the first affordable GP choice for the current `AgentView`."""
    if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
        return None
    if gp_id not in view.player.gp_loadout:
        return None
    gp = god_powers.get(gp_id)
    if gp is None:
        return None
    for tier_idx in tier_order:
        if choice_cost(view, god_powers, gp_id, tier_idx) <= view.available_tokens:
            return (gp_id, tier_idx)
    return None


def score_gp_choice(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    choice: tuple[str, int],
    threat_tier_order: Iterable[int] = (0,),
) -> float:
    """Score one GP/tier choice from visible tactical context."""
    gp_id, tier_idx = choice
    gp = god_powers[gp_id]
    tier = gp.tiers[tier_idx]
    effective_cost = choice_cost(view, god_powers, gp_id, tier_idx)
    cost_penalty = effective_cost * GP_COST_POINT_PENALTY
    missing_hp = view.missing_hp
    incoming_dice = view.combat.incoming_total
    incoming_gp = estimate_opponent_gp_damage(
        view,
        tier_order=threat_tier_order,
        god_powers=god_powers,
    )
    incoming_gp_value = estimate_opponent_gp_value(
        view,
        tier_order=threat_tier_order,
        god_powers=god_powers,
    )

    score = -cost_penalty
    score -= tier_idx * GP_HIGHER_TIER_PENALTY
    score += score_tier_core_impact(
        tier,
        primary_role=gp.primary_role,
        effective_cost=effective_cost,
        target_hp=view.opponent.hp,
        missing_hp=missing_hp,
        preventable_block_damage=incoming_gp,
        preventable_reduction_damage=incoming_dice,
        cancel_target_available=incoming_gp_value > 0,
        inactive_cancel_value=0.0,
    )

    if tier.damage:
        wasted_damage = max(0.0, float(tier.damage) - float(view.opponent.hp))
        score -= wasted_damage * GP_WASTED_DAMAGE_PENALTY

    if tier.self_damage:
        score -= tier.self_damage * (
            GP_SELF_DAMAGE_LOW_HP_PENALTY
            if view.player.hp <= GP_LOW_HP_URGENCY_THRESHOLD
            else GP_SELF_DAMAGE_POINT_PENALTY
        )

    if tier.block_amount:
        prevented = min(tier.block_amount, incoming_gp)
        score -= max(0, tier.block_amount - prevented) * GP_UNUSED_BLOCK_PENALTY
        if incoming_gp >= view.player.hp:
            score += prevented * GP_BLOCK_LETHAL_URGENCY_BONUS

    if tier.heal:
        healed = min(tier.heal, missing_hp)
        score -= max(0, tier.heal - healed) * GP_UNUSED_HEAL_PENALTY
        if view.player.hp <= GP_LOW_HP_URGENCY_THRESHOLD:
            score += healed * GP_HEAL_LOW_HP_URGENCY_BONUS

    if tier.token_gain:
        if incoming_dice + incoming_gp >= view.player.hp:
            score -= effective_cost * GP_TOKEN_UNDER_PRESSURE_COST_PENALTY

    if tier.damage_reduction:
        prevented = min(tier.damage_reduction, incoming_dice)
        score += round(prevented * tier.reflect_pct) * GP_REFLECT_POINT_VALUE
        score -= max(0, tier.damage_reduction - prevented) * GP_UNUSED_DAMAGE_REDUCTION_PENALTY
        if incoming_dice >= view.player.hp:
            score += prevented * GP_DAMAGE_REDUCTION_LETHAL_URGENCY_BONUS

    if tier.cancel_gp:
        if incoming_gp_value > 0:
            score += min(incoming_gp_value, GP_CANCEL_THREAT_BONUS_CAP) * GP_CANCEL_THREAT_BONUS_MULTIPLIER
        else:
            score -= GP_CANCEL_NO_TARGET_PENALTY
        if incoming_gp > 0:
            score += GP_CANCEL_DIRECT_THREAT_BONUS
        score += min(view.opponent.tokens, GP_CANCEL_TOKEN_WINDOW_CAP) * GP_CANCEL_TOKEN_PRESENCE_VALUE

    score += choice_location_bonus(view, god_powers, choice)
    return score


def best_scored_gp(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    gp_priority: Iterable[str],
    tier_order: Iterable[int] = (0,),
    threat_tier_order: Iterable[int] = (0,),
    minimum_score: float = 0.5,
    choice_filter: Callable[[str, int], bool] | None = None,
) -> tuple[str, int] | None:
    """Return the highest-scoring affordable GP from a priority-filtered set."""
    if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
        return None
    best_choice: tuple[str, int] | None = None
    best_score = minimum_score
    priority_set = tuple(gp_priority)

    for gp_id in priority_set:
        for tier_idx in tier_order:
            choice = try_view_gp(view, god_powers, gp_id, (tier_idx,))
            if choice is None:
                continue
            if choice_filter is not None and not choice_filter(gp_id, tier_idx):
                continue
            score = score_gp_choice(view, god_powers, choice, threat_tier_order=threat_tier_order)
            if score > best_score:
                best_choice = choice
                best_score = score

    return best_choice
