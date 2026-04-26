"""Shared scoring functions for game-aware agents."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from agents.game_aware.location_bias import adjust_keep_scores, choice_location_bonus
from agents.game_aware.location_rules import effective_gp_cost, gp_activation_blocked
from agents.game_aware.state_features import AgentView, estimate_opponent_gp_damage, estimate_opponent_gp_value
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
    tier = god_powers[gp_id].tiers[tier_idx]
    effective_cost = choice_cost(view, god_powers, gp_id, tier_idx)
    cost_penalty = effective_cost * 0.22
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
    score -= tier_idx * 0.35

    if tier.damage:
        effective_damage = min(float(tier.damage), float(view.opponent.hp))
        wasted_damage = max(0.0, float(tier.damage) - float(view.opponent.hp))
        score += effective_damage * 2.3
        score -= wasted_damage * 0.7
        if view.opponent.hp <= tier.damage:
            score += 8.0

    if tier.self_damage:
        score -= tier.self_damage * (2.0 if view.player.hp <= 5 else 1.0)

    if tier.block_amount:
        prevented = min(tier.block_amount, incoming_gp)
        score += prevented * 2.4
        score -= max(0, tier.block_amount - prevented) * 0.5
        if incoming_gp >= view.player.hp:
            score += prevented * 2.0

    if tier.heal:
        healed = min(tier.heal, missing_hp)
        score += healed * 1.9
        score -= max(0, tier.heal - healed) * 0.4
        if view.player.hp <= 5:
            score += healed * 1.2

    if tier.token_gain:
        score += max(0, tier.token_gain - tier.cost) * 1.6
        score += min(tier.token_gain, 4) * 0.25
        if incoming_dice + incoming_gp >= view.player.hp:
            score -= tier.cost * 0.25

    if tier.damage_reduction:
        prevented = min(tier.damage_reduction, incoming_dice)
        score += prevented * 2.5
        score += round(prevented * tier.reflect_pct) * 1.8
        score -= max(0, tier.damage_reduction - prevented) * 0.35
        if incoming_dice >= view.player.hp:
            score += prevented * 2.0

    if tier.cancel_gp:
        if incoming_gp_value > 0:
            score += 2.0 + min(incoming_gp_value, 8.0) * 0.75
        else:
            score -= 1.5
        if incoming_gp > 0:
            score += 2.0
        score += min(view.opponent.tokens, 8) * 0.25

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
