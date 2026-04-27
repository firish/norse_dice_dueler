"""Shared state-reading helpers for game-aware agents.

These helpers are deliberately deterministic and lightweight. They do not
simulate future rolls; they summarize the visible board so agents can make
better keep and God Power decisions than fixed priority scripts.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from agents.state_aware_agents.god_powers.gp_scoring import score_tier_core_impact
from agents.state_aware_agents.god_powers.gp_loadout import infer_archetype_from_gp_loadout
from agents.state_aware_agents.locations.location_rules import effective_gp_cost, gp_activation_blocked
from agents.state_aware_agents.dice_deck.loadout_profile import LoadoutProfile, profile_for_loadout
from game_mechanics.conditions import condition_param
from game_mechanics.game_state import GameState, PlayerState
from game_mechanics.god_powers import GodPower, load_god_powers

ATTACK_FACES = frozenset({"FACE_AXE", "FACE_ARROW"})
DEFENSE_FACES = frozenset({"FACE_HELMET", "FACE_SHIELD"})
TOKEN_FACES = frozenset({"FACE_HAND", "FACE_HAND_BORDERED"})
_DEFAULT_GOD_POWERS = load_god_powers()


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
        return banked_tokens_for_player(self.state, self.player)

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


def banked_tokens_for_player(state: GameState, player: PlayerState) -> int:
    """Return same-round banked tokens for any player under current L4 rules."""
    extra = count_faces(player, "FACE_HAND_BORDERED")
    freya_start_round = int(condition_param("COND_FREYA_BLESSING", "start_round", 6))
    freya_threshold = int(condition_param("COND_FREYA_BLESSING", "bordered_threshold", 2))
    freya_bonus_tokens = int(condition_param("COND_FREYA_BLESSING", "bonus_tokens", 1))
    if "COND_FREYA_BLESSING" in state.condition_ids and state.round_num >= freya_start_round:
        if count_faces(player, "FACE_HAND_BORDERED") >= freya_threshold:
            extra += freya_bonus_tokens
    return extra


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


def opponent_has_role(
    view: AgentView,
    role: str,
    god_powers: dict[str, GodPower] | None = None,
) -> bool:
    """Infer an opponent archetype from the currently equipped GP loadout."""
    god_powers = god_powers if god_powers is not None else _DEFAULT_GOD_POWERS
    inferred = infer_archetype_from_gp_loadout(view.opponent.gp_loadout, god_powers)
    return inferred == role.upper()


def estimate_opponent_gp_damage(
    view: AgentView,
    tier_order: tuple[int, ...] = (0,),
    god_powers: dict[str, GodPower] | None = None,
) -> int:
    """Estimate the largest immediate offensive GP damage the opponent can afford."""
    if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
        return 0
    tokens = view.opponent.tokens + banked_tokens_for_player(view.state, view.opponent)
    god_powers = god_powers if god_powers is not None else _DEFAULT_GOD_POWERS
    best = 0
    for gp_id in view.opponent.gp_loadout:
        gp = god_powers.get(gp_id)
        if gp is None:
            continue
        for tier_idx in tier_order:
            tier = gp.tiers[tier_idx]
            if tokens >= effective_gp_cost(tier.cost, view.state.round_num, view.state.condition_ids):
                best = max(best, int(tier.damage))
                break
    return best


def estimate_opponent_gp_value(
    view: AgentView,
    tier_order: tuple[int, ...] = (0,),
    god_powers: dict[str, GodPower] | None = None,
) -> float:
    """Estimate the opponent's best affordable GP impact on the shared GP score scale."""
    if gp_activation_blocked(view.state.round_num, view.state.condition_ids):
        return 0.0
    tokens = view.opponent.tokens + banked_tokens_for_player(view.state, view.opponent)
    god_powers = god_powers if god_powers is not None else _DEFAULT_GOD_POWERS
    max_seen_hp = max(15, view.player.hp, view.opponent.hp)
    if "COND_YGGDRASIL_ROOTS" in view.state.condition_ids:
        bonus_hp = int(condition_param("COND_YGGDRASIL_ROOTS", "bonus_hp", 2))
        max_seen_hp = max(max_seen_hp, 15 + bonus_hp)
    opponent_missing_hp = max(0, max_seen_hp - view.opponent.hp)
    best = 0.0

    for gp_id in view.opponent.gp_loadout:
        gp = god_powers.get(gp_id)
        if gp is None:
            continue
        for tier_idx in tier_order:
            tier = gp.tiers[tier_idx]
            effective_cost = effective_gp_cost(tier.cost, view.state.round_num, view.state.condition_ids)
            if tokens < effective_cost:
                continue

            score = score_tier_core_impact(
                tier,
                primary_role=gp.primary_role,
                effective_cost=effective_cost,
                target_hp=view.player.hp,
                missing_hp=opponent_missing_hp,
                preventable_block_damage=view.combat.outgoing_total,
                preventable_reduction_damage=view.combat.outgoing_total,
                cancel_target_available=view.available_tokens > 0,
            )
            best = max(best, score)
            break

    return best


def estimate_total_threat(
    view: AgentView,
    tier_order: tuple[int, ...] = (0,),
    god_powers: dict[str, GodPower] | None = None,
) -> int:
    """Estimate visible incoming damage from combat plus likely offensive GP pressure."""
    return view.combat.incoming_total + estimate_opponent_gp_damage(view, tier_order, god_powers)


def player_with_available_tokens(view: AgentView) -> PlayerState:
    """Return a player copy with same-round banked tokens included for GP checks."""
    return replace(view.player, tokens=view.available_tokens)


def loadout_profile(player: PlayerState) -> LoadoutProfile:
    """Return expected-value loadout features for the player's equipped dice."""
    return profile_for_loadout(player.die_loadout)
