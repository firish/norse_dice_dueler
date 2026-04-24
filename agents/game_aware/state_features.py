"""Shared state-reading helpers for game-aware agents.

These helpers are deliberately deterministic and lightweight. They do not
simulate future rolls; they summarize the visible board so agents can make
better keep and God Power decisions than fixed priority scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from game_mechanics.conditions import condition_param
from game_mechanics.game_state import GameState, PlayerState

ATTACK_FACES = frozenset({"FACE_AXE", "FACE_ARROW"})
DEFENSE_FACES = frozenset({"FACE_HELMET", "FACE_SHIELD"})
TOKEN_FACES = frozenset({"FACE_HAND", "FACE_HAND_BORDERED"})


@dataclass(frozen=True)
class CombatPreview:
    """Visible combat forecast before God Powers resolve."""

    outgoing_unblocked: int
    incoming_unblocked: int
    blocked_by_me: int
    blocked_by_opponent: int
    thorn_damage_to_me: int
    thorn_damage_to_opponent: int

    @property
    def outgoing_total(self) -> int:
        """Damage the player expects to deal during combat, including thorns."""
        return self.outgoing_unblocked + self.thorn_damage_to_opponent

    @property
    def incoming_total(self) -> int:
        """Damage the player expects to take during combat, including thorns."""
        return self.incoming_unblocked + self.thorn_damage_to_me


@dataclass(frozen=True)
class AgentView:
    """Convenient player-centric view of a game state."""

    state: GameState
    player_num: int
    player: PlayerState
    opponent: PlayerState
    combat: CombatPreview

    @property
    def banked_tokens(self) -> int:
        """Bordered-hand tokens available at GP timing under current rules."""
        extra = self.player.dice_faces.count("FACE_HAND_BORDERED")
        freya_start_round = int(condition_param("COND_FREYA_BLESSING", "start_round", 6))
        freya_threshold = int(condition_param("COND_FREYA_BLESSING", "bordered_threshold", 2))
        freya_bonus_tokens = int(condition_param("COND_FREYA_BLESSING", "bonus_tokens", 1))
        if self.has_condition("COND_FREYA_BLESSING") and self.state.round_num >= freya_start_round:
            if self.player.dice_faces.count("FACE_HAND_BORDERED") >= freya_threshold:
                extra += freya_bonus_tokens
        return extra

    @property
    def available_tokens(self) -> int:
        """Current tokens plus same-round bordered-hand bank."""
        return self.player.tokens + self.banked_tokens

    @property
    def missing_hp(self) -> int:
        """Approximate missing HP using the current player/opponent max as context."""
        max_seen_hp = max(15, self.player.hp, self.opponent.hp)
        if self.has_condition("COND_YGGDRASIL_ROOTS"):
            bonus_hp = int(condition_param("COND_YGGDRASIL_ROOTS", "bonus_hp", 2))
            max_seen_hp = max(max_seen_hp, 15 + bonus_hp)
        return max(0, max_seen_hp - self.player.hp)

    def has_condition(self, condition_id: str) -> bool:
        """Return whether this state is under a specific L4 condition."""
        return condition_id in self.state.condition_ids


def count_faces(player: PlayerState, face_id: str) -> int:
    """Count visible dice faces for one player."""
    return player.dice_faces.count(face_id)


def combat_preview(player: PlayerState, opponent: PlayerState) -> CombatPreview:
    """Forecast visible dice combat using the current engine's combat rules."""
    my_axes = count_faces(player, "FACE_AXE")
    my_arrows = count_faces(player, "FACE_ARROW")
    opp_axes = count_faces(opponent, "FACE_AXE")
    opp_arrows = count_faces(opponent, "FACE_ARROW")
    my_helmets = count_faces(player, "FACE_HELMET")
    my_shields = count_faces(player, "FACE_SHIELD")
    opp_helmets = count_faces(opponent, "FACE_HELMET")
    opp_shields = count_faces(opponent, "FACE_SHIELD")

    blocked_by_me = min(opp_axes, my_helmets) + min(opp_arrows, my_shields)
    blocked_by_opponent = min(my_axes, opp_helmets) + min(my_arrows, opp_shields)

    return CombatPreview(
        outgoing_unblocked=max(0, my_axes + my_arrows - blocked_by_opponent),
        incoming_unblocked=max(0, opp_axes + opp_arrows - blocked_by_me),
        blocked_by_me=blocked_by_me,
        blocked_by_opponent=blocked_by_opponent,
        thorn_damage_to_me=blocked_by_opponent // 3,
        thorn_damage_to_opponent=blocked_by_me // 3,
    )


def view_for(state: GameState, player_num: int) -> AgentView:
    """Build a player-centric feature view for `state`."""
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    return AgentView(
        state=state,
        player_num=player_num,
        player=player,
        opponent=opponent,
        combat=combat_preview(player, opponent),
    )


def opponent_has_role(view: AgentView, role: str) -> bool:
    """Infer an opponent archetype from signature GP ids."""
    if role == "aggro":
        return "GP_SURTRS_FLAME" in view.opponent.gp_loadout
    if role == "control":
        return "GP_AEGIS_OF_BALDR" in view.opponent.gp_loadout
    if role == "economy":
        return "GP_MJOLNIRS_WRATH" in view.opponent.gp_loadout
    return False


def estimate_opponent_gp_damage(view: AgentView) -> int:
    """Estimate the largest immediate offensive GP damage the opponent can afford."""
    tokens = view.opponent.tokens + view.opponent.dice_faces.count("FACE_HAND_BORDERED")
    best = 0
    if "GP_SURTRS_FLAME" in view.opponent.gp_loadout and tokens >= 3:
        best = max(best, 2)
    if "GP_FENRIRS_BITE" in view.opponent.gp_loadout and tokens >= 7:
        best = max(best, 4)
    if "GP_TYRS_JUDGMENT" in view.opponent.gp_loadout and tokens >= 5:
        best = max(best, 3)
    if "GP_MJOLNIRS_WRATH" in view.opponent.gp_loadout and tokens >= 8:
        best = max(best, 3)
    return best


def estimate_total_threat(view: AgentView) -> int:
    """Estimate visible incoming damage from combat plus likely offensive GP pressure."""
    return view.combat.incoming_total + estimate_opponent_gp_damage(view)


def player_with_available_tokens(view: AgentView) -> PlayerState:
    """Return a player copy with same-round banked tokens included for GP checks."""
    return replace(view.player, tokens=view.available_tokens)
