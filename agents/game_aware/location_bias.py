"""Light single-condition heuristic nudges for smart agents.

This module intentionally keeps L4 awareness additive and composable. Each
condition contributes a few small keep-score or GP-score adjustments; pair
interactions are left emergent for now.
"""

from __future__ import annotations

from collections.abc import Mapping

from agents.game_aware.location_rules import effective_gp_cost
from agents.game_aware.state_features import AgentView, count_faces
from game_mechanics.conditions import condition_param
from game_mechanics.god_powers import GodPower


def _add(scores: dict[str, float], face_id: str, delta: float) -> None:
    """Adjust one face score if it exists in the caller's score map."""
    if face_id in scores:
        scores[face_id] += delta


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
            _add(scores, "FACE_AXE", 0.2)
            _add(scores, "FACE_ARROW", 0.15)
            _add(scores, "FACE_HELMET", 0.2)
            _add(scores, "FACE_SHIELD", 0.2)
            _add(scores, "FACE_HAND", -0.25)
            _add(scores, "FACE_HAND_BORDERED", 0.05)

    if "COND_MIDGARD_HEARTH" in condition_ids:
        if has_heal_gp:
            _add(scores, "FACE_HAND_BORDERED", 0.12)
            _add(scores, "FACE_HAND", 0.08)
            _add(scores, "FACE_HELMET", 0.12)
            _add(scores, "FACE_SHIELD", 0.12)
        else:
            _add(scores, "FACE_AXE", 0.05)
            _add(scores, "FACE_ARROW", 0.05)

    if "COND_FENRIR_HUNT" in condition_ids:
        start_round = int(condition_param("COND_FENRIR_HUNT", "start_round", 5))
        min_combat_faces = int(condition_param("COND_FENRIR_HUNT", "min_combat_faces", 3))
        if round_num >= start_round and combat_faces >= max(1, min_combat_faces - 1):
            _add(scores, "FACE_AXE", 0.2)
            _add(scores, "FACE_ARROW", 0.15)

    if "COND_YGGDRASIL_ROOTS" in condition_ids:
        if has_control_defense_gp or has_bragi:
            _add(scores, "FACE_HAND_BORDERED", 0.1)
            _add(scores, "FACE_HAND", 0.1)
            _add(scores, "FACE_HELMET", 0.1)
            _add(scores, "FACE_SHIELD", 0.1)
        else:
            _add(scores, "FACE_HAND_BORDERED", 0.05)
            _add(scores, "FACE_HAND", 0.05)

    if "COND_RAGNAROK" in condition_ids:
        start_round = int(condition_param("COND_RAGNAROK", "start_round", 6))
        if round_num >= start_round:
            _add(scores, "FACE_AXE", 0.15)
            _add(scores, "FACE_ARROW", 0.1)
            _add(scores, "FACE_HAND", -0.2)
            _add(scores, "FACE_HAND_BORDERED", -0.05)

    if "COND_FREYA_BLESSING" in condition_ids:
        start_round = int(condition_param("COND_FREYA_BLESSING", "start_round", 6))
        if round_num >= start_round:
            _add(scores, "FACE_HAND_BORDERED", 0.5)
            _add(scores, "FACE_HAND", 0.1)

    if "COND_TYR_ARENA" in condition_ids:
        blocked_rounds = int(condition_param("COND_TYR_ARENA", "blocked_rounds", 1))
        if round_num <= blocked_rounds:
            _add(scores, "FACE_AXE", 0.2)
            _add(scores, "FACE_ARROW", 0.15)
            _add(scores, "FACE_HELMET", 0.15)
            _add(scores, "FACE_SHIELD", 0.15)
            _add(scores, "FACE_HAND", -0.25)
            _add(scores, "FACE_HAND_BORDERED", -0.15)

    if "COND_LOKI_MISCHIEF" in condition_ids:
        active_rounds = int(condition_param("COND_LOKI_MISCHIEF", "active_rounds", 3))
        if round_num <= active_rounds:
            if has_control_defense_gp or has_bragi:
                _add(scores, "FACE_HELMET", 0.22)
                _add(scores, "FACE_SHIELD", 0.22)
                _add(scores, "FACE_HAND", -0.05)
                _add(scores, "FACE_HAND_BORDERED", 0.05)
            else:
                _add(scores, "FACE_AXE", 0.05)
                _add(scores, "FACE_HELMET", 0.1)
                _add(scores, "FACE_SHIELD", 0.1)
                _add(scores, "FACE_HAND", -0.15)

    if "COND_NIFLHEIM_CHILL" in condition_ids:
        if has_control_defense_gp:
            _add(scores, "FACE_HELMET", 0.25)
            _add(scores, "FACE_SHIELD", 0.25)
        elif has_bragi:
            _add(scores, "FACE_HELMET", 0.1)
            _add(scores, "FACE_SHIELD", 0.1)

    if "COND_JOTUN_MIGHT" in condition_ids:
        if has_control_defense_gp or has_bragi:
            _add(scores, "FACE_HAND_BORDERED", 0.18)
            _add(scores, "FACE_HAND", 0.08)
        else:
            _add(scores, "FACE_HAND_BORDERED", 0.1)
            _add(scores, "FACE_HAND", 0.05)

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
        score += min(float(heal_bonus), max(0.0, float(view.missing_hp - tier.heal))) * 1.4
        if view.player.hp <= 5:
            score += heal_bonus * 0.5

    if "COND_YGGDRASIL_ROOTS" in condition_ids:
        if tier.token_gain:
            score += min(tier.token_gain, 4) * 0.2
        if tier.heal:
            score += 0.4
        if tier.damage_reduction or tier.block_amount:
            score += 0.35
        if tier.damage and tier.damage < view.opponent.hp:
            score -= 0.2

    if "COND_RAGNAROK" in condition_ids:
        start_round = int(condition_param("COND_RAGNAROK", "start_round", 6))
        if round_num >= start_round:
            if tier.damage:
                score += 0.35 + tier.damage * 0.1
            if tier.token_gain:
                score -= 0.35
            if tier.heal:
                score -= 0.05
            if tier.damage_reduction or tier.block_amount:
                score -= 0.05

    if "COND_FREYA_BLESSING" in condition_ids:
        start_round = int(condition_param("COND_FREYA_BLESSING", "start_round", 6))
        threshold = int(condition_param("COND_FREYA_BLESSING", "bordered_threshold", 2))
        if round_num >= start_round and count_faces(view.player, "FACE_HAND_BORDERED") >= threshold:
            if tier.token_gain:
                score += 0.25
            if gp.primary_role in {"ramp", "finisher"}:
                score += 0.2

    if "COND_NIFLHEIM_CHILL" in condition_ids:
        threshold = int(condition_param("COND_NIFLHEIM_CHILL", "block_threshold", 4))
        if view.combat.blocked_by_me >= max(1, threshold - 1):
            if tier.damage_reduction or tier.block_amount:
                score += 0.45
        elif tier.damage_reduction or tier.block_amount:
            score += 0.1

    if "COND_JOTUN_MIGHT" in condition_ids:
        min_base_cost = int(condition_param("COND_JOTUN_MIGHT", "min_base_cost", 8))
        discounted_cost = effective_gp_cost(tier.cost, round_num, condition_ids)
        if tier.cost >= min_base_cost:
            score += 0.05 + max(0, tier.cost - discounted_cost) * 0.15
            if tier_idx >= 1:
                score += 0.1
            if gp.primary_role in {"block", "heal", "anti_race"}:
                score += 0.15
            elif gp.primary_role in {"finisher", "ramp"}:
                score -= 0.1

    return score
