"""Light single-condition heuristic nudges for smart agents.

This module intentionally keeps L4 awareness additive and composable. Each
condition contributes a few small keep-score or GP-score adjustments; pair
interactions are left emergent for now.
"""

from __future__ import annotations

from collections.abc import Mapping

from agents.state_aware_agents.god_powers.gp_scoring import GP_LOW_HP_URGENCY_THRESHOLD
from agents.state_aware_agents.locations.location_rules import effective_gp_cost
from agents.state_aware_agents.state.state_features import AgentView, count_faces
from game_mechanics.conditions import condition_param
from game_mechanics.god_powers import GodPower

ODIN_GAZE_KEEP_DELTAS = {
    "FACE_AXE": 0.2,
    "FACE_ARROW": 0.15,
    "FACE_HELMET": 0.2,
    "FACE_SHIELD": 0.2,
    "FACE_HAND": -0.25,
    "FACE_HAND_BORDERED": 0.05,
}
MIDGARD_HEARTH_HEAL_GP_KEEP_DELTAS = {
    "FACE_HAND_BORDERED": 0.12,
    "FACE_HAND": 0.08,
    "FACE_HELMET": 0.12,
    "FACE_SHIELD": 0.12,
}
MIDGARD_HEARTH_NON_HEAL_KEEP_DELTAS = {
    "FACE_AXE": 0.05,
    "FACE_ARROW": 0.05,
}
FENRIR_HUNT_KEEP_DELTAS = {
    "FACE_AXE": 0.2,
    "FACE_ARROW": 0.15,
}
YGGDRASIL_ROOTS_CONTROL_KEEP_DELTAS = {
    "FACE_HAND_BORDERED": 0.1,
    "FACE_HAND": 0.1,
    "FACE_HELMET": 0.1,
    "FACE_SHIELD": 0.1,
}
YGGDRASIL_ROOTS_DEFAULT_KEEP_DELTAS = {
    "FACE_HAND_BORDERED": 0.05,
    "FACE_HAND": 0.05,
}
RAGNAROK_KEEP_DELTAS = {
    "FACE_AXE": 0.15,
    "FACE_ARROW": 0.1,
    "FACE_HAND": -0.2,
    "FACE_HAND_BORDERED": -0.05,
}
FREYA_BLESSING_KEEP_DELTAS = {
    "FACE_HAND_BORDERED": 0.5,
    "FACE_HAND": 0.1,
}
TYR_ARENA_KEEP_DELTAS = {
    "FACE_AXE": 0.2,
    "FACE_ARROW": 0.15,
    "FACE_HELMET": 0.15,
    "FACE_SHIELD": 0.15,
    "FACE_HAND": -0.25,
    "FACE_HAND_BORDERED": -0.15,
}
LOKI_MISCHIEF_CONTROL_KEEP_DELTAS = {
    "FACE_HELMET": 0.22,
    "FACE_SHIELD": 0.22,
    "FACE_HAND": -0.05,
    "FACE_HAND_BORDERED": 0.05,
}
LOKI_MISCHIEF_DEFAULT_KEEP_DELTAS = {
    "FACE_AXE": 0.05,
    "FACE_HELMET": 0.1,
    "FACE_SHIELD": 0.1,
    "FACE_HAND": -0.15,
}
NIFLHEIM_CHILL_CONTROL_KEEP_DELTAS = {
    "FACE_HELMET": 0.25,
    "FACE_SHIELD": 0.25,
}
NIFLHEIM_CHILL_BRAGI_KEEP_DELTAS = {
    "FACE_HELMET": 0.1,
    "FACE_SHIELD": 0.1,
}
JOTUN_MIGHT_CONTROL_KEEP_DELTAS = {
    "FACE_HAND_BORDERED": 0.18,
    "FACE_HAND": 0.08,
}
JOTUN_MIGHT_DEFAULT_KEEP_DELTAS = {
    "FACE_HAND_BORDERED": 0.1,
    "FACE_HAND": 0.05,
}

MIDGARD_HEARTH_EXTRA_HEAL_POINT_VALUE = 1.4
MIDGARD_HEARTH_LOW_HP_BONUS_PER_HEAL = 0.5
YGGDRASIL_ROOTS_TOKEN_GAIN_CAP = 4
YGGDRASIL_ROOTS_TOKEN_GAIN_POINT_VALUE = 0.2
YGGDRASIL_ROOTS_HEAL_BONUS = 0.4
YGGDRASIL_ROOTS_DEFENSE_BONUS = 0.35
YGGDRASIL_ROOTS_NONLETHAL_DAMAGE_PENALTY = 0.2
RAGNAROK_DAMAGE_BASE_BONUS = 0.35
RAGNAROK_DAMAGE_POINT_VALUE = 0.1
RAGNAROK_TOKEN_GAIN_PENALTY = 0.35
RAGNAROK_HEAL_PENALTY = 0.05
RAGNAROK_DEFENSE_PENALTY = 0.05
FREYA_BLESSING_TOKEN_GAIN_BONUS = 0.25
FREYA_BLESSING_RAMP_FINISHER_BONUS = 0.2
NIFLHEIM_CHILL_DEFENSE_READY_BONUS = 0.45
NIFLHEIM_CHILL_DEFENSE_EARLY_BONUS = 0.1
JOTUN_MIGHT_BASE_COST_BONUS = 0.05
JOTUN_MIGHT_DISCOUNT_POINT_VALUE = 0.15
JOTUN_MIGHT_HIGHER_TIER_BONUS = 0.1
JOTUN_MIGHT_DEFENSIVE_ROLE_BONUS = 0.15
JOTUN_MIGHT_RAMP_FINISHER_PENALTY = 0.1


def _add(scores: dict[str, float], face_id: str, delta: float) -> None:
    """Adjust one face score if it exists in the caller's score map."""
    if face_id in scores:
        scores[face_id] += delta


def _apply_deltas(scores: dict[str, float], deltas: Mapping[str, float]) -> None:
    """Apply a named bundle of per-face score nudges."""
    for face_id, delta in deltas.items():
        _add(scores, face_id, delta)


def adjust_keep_scores(view: AgentView, face_scores: Mapping[str, float]) -> dict[str, float]:
    """Apply light single-condition keep-score adjustments."""
    scores = dict(face_scores)
    round_num = view.state.round_num
    condition_ids = set(view.state.condition_ids)
    combat_faces = count_faces(view.player, "FACE_AXE") + count_faces(view.player, "FACE_ARROW")
    gp_loadout = set(view.player.gp_loadout)
    has_heal_gp = "GP_EIRS_MERCY" in gp_loadout
    has_control_defense_gp = has_heal_gp or "GP_AEGIS_OF_BALDR" in gp_loadout
    has_bragi = "GP_BRAGIS_SONG" in gp_loadout

    if "COND_ODIN_GAZE" in condition_ids:
        active_rounds = int(condition_param("COND_ODIN_GAZE", "active_rounds", 2))
        if round_num <= active_rounds:
            _apply_deltas(scores, ODIN_GAZE_KEEP_DELTAS)

    if "COND_MIDGARD_HEARTH" in condition_ids:
        if has_heal_gp:
            _apply_deltas(scores, MIDGARD_HEARTH_HEAL_GP_KEEP_DELTAS)
        else:
            _apply_deltas(scores, MIDGARD_HEARTH_NON_HEAL_KEEP_DELTAS)

    if "COND_FENRIR_HUNT" in condition_ids:
        start_round = int(condition_param("COND_FENRIR_HUNT", "start_round", 5))
        min_combat_faces = int(condition_param("COND_FENRIR_HUNT", "min_combat_faces", 3))
        if round_num >= start_round and combat_faces >= max(1, min_combat_faces - 1):
            _apply_deltas(scores, FENRIR_HUNT_KEEP_DELTAS)

    if "COND_YGGDRASIL_ROOTS" in condition_ids:
        if has_control_defense_gp or has_bragi:
            _apply_deltas(scores, YGGDRASIL_ROOTS_CONTROL_KEEP_DELTAS)
        else:
            _apply_deltas(scores, YGGDRASIL_ROOTS_DEFAULT_KEEP_DELTAS)

    if "COND_RAGNAROK" in condition_ids:
        start_round = int(condition_param("COND_RAGNAROK", "start_round", 6))
        if round_num >= start_round:
            _apply_deltas(scores, RAGNAROK_KEEP_DELTAS)

    if "COND_FREYA_BLESSING" in condition_ids:
        start_round = int(condition_param("COND_FREYA_BLESSING", "start_round", 6))
        if round_num >= start_round:
            _apply_deltas(scores, FREYA_BLESSING_KEEP_DELTAS)

    if "COND_TYR_ARENA" in condition_ids:
        blocked_rounds = int(condition_param("COND_TYR_ARENA", "blocked_rounds", 1))
        if round_num <= blocked_rounds:
            _apply_deltas(scores, TYR_ARENA_KEEP_DELTAS)

    if "COND_LOKI_MISCHIEF" in condition_ids:
        active_rounds = int(condition_param("COND_LOKI_MISCHIEF", "active_rounds", 3))
        if round_num <= active_rounds:
            if has_control_defense_gp or has_bragi:
                _apply_deltas(scores, LOKI_MISCHIEF_CONTROL_KEEP_DELTAS)
            else:
                _apply_deltas(scores, LOKI_MISCHIEF_DEFAULT_KEEP_DELTAS)

    if "COND_NIFLHEIM_CHILL" in condition_ids:
        if has_control_defense_gp:
            _apply_deltas(scores, NIFLHEIM_CHILL_CONTROL_KEEP_DELTAS)
        elif has_bragi:
            _apply_deltas(scores, NIFLHEIM_CHILL_BRAGI_KEEP_DELTAS)

    if "COND_JOTUN_MIGHT" in condition_ids:
        if has_control_defense_gp or has_bragi:
            _apply_deltas(scores, JOTUN_MIGHT_CONTROL_KEEP_DELTAS)
        else:
            _apply_deltas(scores, JOTUN_MIGHT_DEFAULT_KEEP_DELTAS)

    return scores


def choice_location_bonus(
    view: AgentView,
    god_powers: Mapping[str, GodPower],
    choice: tuple[str, int],
) -> float:
    """Return an additive GP score bonus from active single conditions."""
    gp_id, tier_idx = choice
    gp = god_powers[gp_id]
    tier = gp.tiers[tier_idx]
    round_num = view.state.round_num
    condition_ids = set(view.state.condition_ids)
    score = 0.0

    if "COND_MIDGARD_HEARTH" in condition_ids and tier.heal:
        heal_bonus = int(condition_param("COND_MIDGARD_HEARTH", "heal_bonus", 1))
        score += min(float(heal_bonus), max(0.0, float(view.missing_hp - tier.heal))) * MIDGARD_HEARTH_EXTRA_HEAL_POINT_VALUE
        if view.player.hp <= GP_LOW_HP_URGENCY_THRESHOLD:
            score += heal_bonus * MIDGARD_HEARTH_LOW_HP_BONUS_PER_HEAL

    if "COND_YGGDRASIL_ROOTS" in condition_ids:
        if tier.token_gain:
            score += min(tier.token_gain, YGGDRASIL_ROOTS_TOKEN_GAIN_CAP) * YGGDRASIL_ROOTS_TOKEN_GAIN_POINT_VALUE
        if tier.heal:
            score += YGGDRASIL_ROOTS_HEAL_BONUS
        if tier.damage_reduction or tier.block_amount:
            score += YGGDRASIL_ROOTS_DEFENSE_BONUS
        if tier.damage and tier.damage < view.opponent.hp:
            score -= YGGDRASIL_ROOTS_NONLETHAL_DAMAGE_PENALTY

    if "COND_RAGNAROK" in condition_ids:
        start_round = int(condition_param("COND_RAGNAROK", "start_round", 6))
        if round_num >= start_round:
            if tier.damage:
                score += RAGNAROK_DAMAGE_BASE_BONUS + tier.damage * RAGNAROK_DAMAGE_POINT_VALUE
            if tier.token_gain:
                score -= RAGNAROK_TOKEN_GAIN_PENALTY
            if tier.heal:
                score -= RAGNAROK_HEAL_PENALTY
            if tier.damage_reduction or tier.block_amount:
                score -= RAGNAROK_DEFENSE_PENALTY

    if "COND_FREYA_BLESSING" in condition_ids:
        start_round = int(condition_param("COND_FREYA_BLESSING", "start_round", 6))
        threshold = int(condition_param("COND_FREYA_BLESSING", "bordered_threshold", 2))
        if round_num >= start_round and count_faces(view.player, "FACE_HAND_BORDERED") >= threshold:
            if tier.token_gain:
                score += FREYA_BLESSING_TOKEN_GAIN_BONUS
            if gp.primary_role in {"ramp", "finisher"}:
                score += FREYA_BLESSING_RAMP_FINISHER_BONUS

    if "COND_NIFLHEIM_CHILL" in condition_ids:
        threshold = int(condition_param("COND_NIFLHEIM_CHILL", "block_threshold", 4))
        if view.combat.blocked_by_me >= max(1, threshold - 1):
            if tier.damage_reduction or tier.block_amount:
                score += NIFLHEIM_CHILL_DEFENSE_READY_BONUS
        elif tier.damage_reduction or tier.block_amount:
            score += NIFLHEIM_CHILL_DEFENSE_EARLY_BONUS

    if "COND_JOTUN_MIGHT" in condition_ids:
        min_base_cost = int(condition_param("COND_JOTUN_MIGHT", "min_base_cost", 8))
        discounted_cost = effective_gp_cost(tier.cost, round_num, condition_ids)
        if tier.cost >= min_base_cost:
            score += JOTUN_MIGHT_BASE_COST_BONUS + max(0, tier.cost - discounted_cost) * JOTUN_MIGHT_DISCOUNT_POINT_VALUE
            if tier_idx >= 1:
                score += JOTUN_MIGHT_HIGHER_TIER_BONUS
            if gp.primary_role in {"block", "heal", "anti_race"}:
                score += JOTUN_MIGHT_DEFENSIVE_ROLE_BONUS
            elif gp.primary_role in {"finisher", "ramp"}:
                score -= JOTUN_MIGHT_RAMP_FINISHER_PENALTY

    return score
