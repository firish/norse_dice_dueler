"""Shared GP tactical scoring scale and component weights.

All game-aware GP heuristics use the same coarse score scale:

- `0-2`: minor or noisy effect
- `4+`: meaningful threat worth respecting or countering
- `8+`: lethal or strongly round-swinging impact

These numbers are not exact expected value math. They are hand-tuned heuristic
weights, centralized here so threat estimation and GP choice scoring stay on
the same numeric language.
"""

from __future__ import annotations

from game_mechanics.god_powers import GodPowerTier

# Shared threat cutoffs on the GP tactical score scale.
MEANINGFUL_GP_THREAT_SCORE = 4.0
HIGH_GP_THREAT_SCORE = 5.5
EXTREME_GP_THREAT_SCORE = 6.0

# Core score weights shared by both threat estimation and choice scoring.
GP_DAMAGE_POINT_VALUE = 2.2
GP_LETHAL_BONUS = 4.0
GP_NET_TOKEN_POINT_VALUE = 2.2
GP_TOKEN_PRESENCE_CAP = 4
GP_TOKEN_PRESENCE_VALUE = 0.4
GP_BLOCK_POINT_VALUE = 1.2
GP_DAMAGE_REDUCTION_POINT_VALUE = 1.4
GP_HEAL_POINT_VALUE = 1.6
GP_CANCEL_BASE_VALUE = 1.0
GP_CANCEL_ACTIVE_BONUS = 2.0
GP_ROLE_RAMP_BONUS = 0.8
GP_ROLE_FINISHER_BONUS = 0.5
GP_ROLE_COUNTER_BONUS = 0.4

# Choice-only adjustments layered on top of the shared core score.
GP_COST_POINT_PENALTY = 0.22
GP_HIGHER_TIER_PENALTY = 0.35
GP_WASTED_DAMAGE_PENALTY = 0.7
GP_SELF_DAMAGE_POINT_PENALTY = 1.0
GP_SELF_DAMAGE_LOW_HP_PENALTY = 2.0
GP_UNUSED_BLOCK_PENALTY = 0.5
GP_BLOCK_LETHAL_URGENCY_BONUS = 2.0
GP_UNUSED_HEAL_PENALTY = 0.4
GP_HEAL_LOW_HP_URGENCY_BONUS = 1.2
GP_TOKEN_UNDER_PRESSURE_COST_PENALTY = 0.25
GP_REFLECT_POINT_VALUE = 1.8
GP_UNUSED_DAMAGE_REDUCTION_PENALTY = 0.35
GP_DAMAGE_REDUCTION_LETHAL_URGENCY_BONUS = 2.0
GP_CANCEL_NO_TARGET_PENALTY = 1.5
GP_CANCEL_THREAT_BONUS_CAP = 8.0
GP_CANCEL_THREAT_BONUS_MULTIPLIER = 0.75
GP_CANCEL_DIRECT_THREAT_BONUS = 2.0
GP_CANCEL_TOKEN_WINDOW_CAP = 8
GP_CANCEL_TOKEN_PRESENCE_VALUE = 0.25
GP_LOW_HP_URGENCY_THRESHOLD = 5


def score_damage_impact(damage: float, target_hp: int) -> float:
    """Score direct damage using the shared GP tactical scale."""
    if damage <= 0 or target_hp <= 0:
        return 0.0
    score = min(float(damage), float(target_hp)) * GP_DAMAGE_POINT_VALUE
    if damage >= target_hp:
        score += GP_LETHAL_BONUS
    return score


def score_token_gain_impact(token_gain: int, effective_cost: int) -> float:
    """Score token ramp from net fuel gain plus a small raw-presence bump."""
    if token_gain <= 0:
        return 0.0
    score = max(0, token_gain - effective_cost) * GP_NET_TOKEN_POINT_VALUE
    score += min(token_gain, GP_TOKEN_PRESENCE_CAP) * GP_TOKEN_PRESENCE_VALUE
    return score


def score_block_impact(block_amount: int, preventable_damage: int) -> float:
    """Score point-for-point prevention for block-style GP effects."""
    return min(block_amount, preventable_damage) * GP_BLOCK_POINT_VALUE


def score_damage_reduction_impact(damage_reduction: int, preventable_damage: int) -> float:
    """Score flat incoming-damage prevention for reduction-style GP effects."""
    return min(damage_reduction, preventable_damage) * GP_DAMAGE_REDUCTION_POINT_VALUE


def score_heal_impact(heal: int, missing_hp: int) -> float:
    """Score only the heal that can actually matter right now."""
    return min(heal, missing_hp) * GP_HEAL_POINT_VALUE


def score_cancel_impact(cancel_target_available: bool, inactive_value: float = GP_CANCEL_BASE_VALUE) -> float:
    """Score GP cancellation from the shared scale.

    Threat estimators treat a cancel as still worth a little even when inactive,
    while choice scoring can pass `inactive_value=0.0` to avoid giving dead
    cancels free credit.
    """
    if cancel_target_available:
        return GP_CANCEL_BASE_VALUE + GP_CANCEL_ACTIVE_BONUS
    return inactive_value


def score_role_impact(primary_role: str) -> float:
    """Small role priors used only as tie-break nudges."""
    if primary_role == "ramp":
        return GP_ROLE_RAMP_BONUS
    if primary_role == "finisher":
        return GP_ROLE_FINISHER_BONUS
    if primary_role == "counter":
        return GP_ROLE_COUNTER_BONUS
    return 0.0


def score_tier_core_impact(
    tier: GodPowerTier,
    *,
    primary_role: str,
    effective_cost: int,
    target_hp: int,
    missing_hp: int,
    preventable_block_damage: int,
    preventable_reduction_damage: int,
    cancel_target_available: bool,
    inactive_cancel_value: float = GP_CANCEL_BASE_VALUE,
) -> float:
    """Score the shared tactical value of one GP tier.

    This intentionally captures only the overlapping core heuristics that both
    threat estimation and active GP choice care about. Callers can then layer
    on context-specific bonuses or penalties without redefining the base scale.
    """
    score = 0.0
    score += score_damage_impact(tier.damage, target_hp)
    score += score_token_gain_impact(tier.token_gain, effective_cost)
    score += score_block_impact(tier.block_amount, preventable_block_damage)
    score += score_damage_reduction_impact(tier.damage_reduction, preventable_reduction_damage)
    score += score_heal_impact(tier.heal, missing_hp)
    if tier.cancel_gp:
        score += score_cancel_impact(cancel_target_available, inactive_value=inactive_cancel_value)
    score += score_role_impact(primary_role)
    return score
