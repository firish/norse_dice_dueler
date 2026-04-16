"""
game_engine.py
--------------
Pure game logic. Holds only an RNG as mutable state; everything else is
derived from the immutable GameState passed in.

Pattern:
    state, events = engine.step(state, p1_action, p2_action)

Agents only need to supply actions for KEEP_1, KEEP_2, and GOD_POWER phases.
All other phases advance automatically (no agent input required).

L0 scope:
    - No God Powers (GOD_POWER and GOD_RESOLVE are no-ops).
    - No Battlefield Conditions (REVEAL is a no-op).
    - No Runes, no status effects (Bleed / Poison).
    - Full dice rolling, keep/reroll cycle, combat, and token resolution.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import numpy as np

from simulator.game_state import GameEvent, GamePhase, GameState, PlayerState
from simulator.die_types import DieType
from simulator.god_powers import GodPower, L1_OFFENSIVE_GP_IDS, load_god_powers

if TYPE_CHECKING:
    from simulator.agents import Agent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NUM_DICE = 6
STARTING_HP = 15
STARTING_TOKENS = 0
_BLANK_FACES = ("",) * NUM_DICE
_ALL_FREE = (False,) * NUM_DICE


# ---------------------------------------------------------------------------
# Internal die-rolling helpers (not part of the public API)
# ---------------------------------------------------------------------------

def _roll_die(die: DieType, rng: np.random.Generator) -> str:
    """Return one randomly selected face from the given die."""
    return die.faces[rng.integers(0, NUM_DICE)]


def _roll_all(die_types: list[DieType], rng: np.random.Generator) -> tuple[str, ...]:
    """Roll each die in the loadout once and return the resulting faces."""
    return tuple(_roll_die(d, rng) for d in die_types)


def _reroll_unkept(
    faces: tuple[str, ...],
    kept: tuple[bool, ...],
    die_types: list[DieType],
    rng: np.random.Generator,
) -> tuple[str, ...]:
    """Reroll only the dice not marked as kept and return the new faces."""
    new = list(faces)
    for i, (k, die) in enumerate(zip(kept, die_types)):
        if not k:
            new[i] = _roll_die(die, rng)
    return tuple(new)


def _apply_keep(
    prev_kept: tuple[bool, ...],
    new_indices: frozenset[int],
) -> tuple[bool, ...]:
    """Merge newly kept indices into the existing keep mask."""
    return tuple(prev_kept[i] or (i in new_indices) for i in range(NUM_DICE))


# ---------------------------------------------------------------------------
# GameEngine
# ---------------------------------------------------------------------------

class GameEngine:
    """
    Stateless game-rule machine (except for the RNG).

    Args:
        p1_die_types:  Ordered list of 6 DieType objects for player 1's loadout.
        p2_die_types:  Ordered list of 6 DieType objects for player 2's loadout.
        rng:           numpy Generator. Pass a seeded rng for reproducibility.
        p1_gp_ids:     Tuple of up to 3 GP IDs for player 1 (empty = L0, no GPs).
        p2_gp_ids:     Tuple of up to 3 GP IDs for player 2 (empty = L0, no GPs).
    """

    def __init__(
        self,
        p1_die_types: list[DieType],
        p2_die_types: list[DieType],
        rng: np.random.Generator | None = None,
        p1_gp_ids: tuple[str, ...] = (),
        p2_gp_ids: tuple[str, ...] = (),
    ) -> None:
        assert len(p1_die_types) == NUM_DICE, f"P1 loadout must have {NUM_DICE} dice"
        assert len(p2_die_types) == NUM_DICE, f"P2 loadout must have {NUM_DICE} dice"
        self.p1_die_types = p1_die_types
        self.p2_die_types = p2_die_types
        self.rng = rng or np.random.default_rng()
        self.p1_gp_ids = p1_gp_ids
        self.p2_gp_ids = p2_gp_ids
        # Load GP definitions once; empty if no GPs in either loadout.
        if p1_gp_ids or p2_gp_ids:
            self._god_powers = load_god_powers()
        else:
            self._god_powers: dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def new_game(self) -> GameState:
        """Return the initial GameState at the start of round 1."""
        return GameState(
            round_num=1,
            phase=GamePhase.REVEAL,
            p1=PlayerState(
                hp=STARTING_HP,
                tokens=STARTING_TOKENS,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_loadout=self.p1_gp_ids,
            ),
            p2=PlayerState(
                hp=STARTING_HP,
                tokens=STARTING_TOKENS,
                dice_faces=_BLANK_FACES,
                dice_kept=_ALL_FREE,
                gp_loadout=self.p2_gp_ids,
            ),
            winner=None,
        )

    def step(
        self,
        state: GameState,
        p1_action: frozenset[int] | tuple[str, int] | None = None,
        p2_action: frozenset[int] | tuple[str, int] | None = None,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Advance the game by one phase.

        p1_action / p2_action meaning depends on the current phase:
          KEEP_1 / KEEP_2:  frozenset[int] - die indices to lock in.
          GOD_POWER:        tuple[str, int] - (gp_id, tier_idx 0-2), or None to pass.
          All other phases: ignored.
        """
        phase = state.phase
        if phase == GamePhase.REVEAL:
            return self._phase_reveal(state)
        if phase == GamePhase.ROLL:
            return self._phase_roll(state)
        if phase == GamePhase.KEEP_1:
            return self._phase_keep(state, p1_action, p2_action, next_phase=GamePhase.REROLL_1)
        if phase == GamePhase.REROLL_1:
            return self._phase_reroll(state, next_phase=GamePhase.KEEP_2)
        if phase == GamePhase.KEEP_2:
            return self._phase_keep(state, p1_action, p2_action, next_phase=GamePhase.REROLL_2)
        if phase == GamePhase.REROLL_2:
            return self._phase_reroll(state, next_phase=GamePhase.GOD_POWER)
        if phase == GamePhase.GOD_POWER:
            return self._phase_god_power(state, p1_action, p2_action)  # type: ignore[arg-type]
        if phase == GamePhase.COMBAT:
            return self._phase_combat(state)
        if phase == GamePhase.GOD_RESOLVE:
            return self._phase_god_resolve(state)
        if phase == GamePhase.TOKENS:
            return self._phase_tokens(state)
        if phase == GamePhase.END_CHECK:
            return self._phase_end_check(state)
        raise ValueError(f"Cannot step from terminal phase {phase}")

    def run_round(
        self,
        state: GameState,
        p1_agent: "Agent",
        p2_agent: "Agent",
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Run all phases of one round, collecting agent decisions where needed.
        Assumes state.phase == REVEAL at entry.
        Returns the state after END_CHECK (either GAME_OVER or REVEAL of next round).
        """
        all_events: list[GameEvent] = []

        def tick(p1_act=None, p2_act=None):
            nonlocal state
            state, evts = self.step(state, p1_act, p2_act)
            all_events.extend(evts)

        tick()                                              # REVEAL -> ROLL
        tick()                                              # ROLL -> KEEP_1
        tick(p1_agent.choose_keep(state, 1),                # KEEP_1 -> REROLL_1
             p2_agent.choose_keep(state, 2))
        tick()                                              # REROLL_1 -> KEEP_2
        tick(p1_agent.choose_keep(state, 1),                # KEEP_2 -> REROLL_2
             p2_agent.choose_keep(state, 2))
        tick()                                              # REROLL_2 -> GOD_POWER
        tick(p1_agent.choose_god_power(state, 1),           # GOD_POWER -> COMBAT
             p2_agent.choose_god_power(state, 2))
        tick()                                              # COMBAT -> GOD_RESOLVE
        tick()                                              # GOD_RESOLVE -> TOKENS
        tick()                                              # TOKENS -> END_CHECK
        tick()                                              # END_CHECK -> REVEAL / GAME_OVER

        return state, all_events

    def run_game(
        self,
        p1_agent: "Agent",
        p2_agent: "Agent",
        max_rounds: int = 100,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Play a complete game from start to GAME_OVER.

        max_rounds is a safety cap; a game that reaches it is recorded as a draw.
        """
        state = self.new_game()
        all_events: list[GameEvent] = []

        while state.phase != GamePhase.GAME_OVER:
            if state.round_num > max_rounds:
                state = replace(state, phase=GamePhase.GAME_OVER, winner=0)
                all_events.append(GameEvent(
                    "game_over",
                    {"winner": 0, "round": state.round_num,
                     "p1_hp": state.p1.hp, "p2_hp": state.p2.hp,
                     "reason": "max_rounds_exceeded"},
                ))
                break
            state, events = self.run_round(state, p1_agent, p2_agent)
            all_events.extend(events)

        return state, all_events

    # ------------------------------------------------------------------
    # Phase implementations (private)
    # ------------------------------------------------------------------

    def _phase_reveal(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        # L0: no battlefield conditions -> immediate pass-through to ROLL.
        return replace(state, phase=GamePhase.ROLL), []

    def _phase_roll(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        p1_faces = _roll_all(self.p1_die_types, self.rng)
        p2_faces = _roll_all(self.p2_die_types, self.rng)
        new_state = replace(
            state,
            phase=GamePhase.KEEP_1,
            p1=replace(state.p1, dice_faces=p1_faces, dice_kept=_ALL_FREE),
            p2=replace(state.p2, dice_faces=p2_faces, dice_kept=_ALL_FREE),
        )
        return new_state, [GameEvent("dice_rolled", {"p1": p1_faces, "p2": p2_faces})]

    def _phase_keep(
        self,
        state: GameState,
        p1_action: frozenset[int] | None,
        p2_action: frozenset[int] | None,
        next_phase: GamePhase,
    ) -> tuple[GameState, list[GameEvent]]:
        p1_kept = _apply_keep(state.p1.dice_kept, p1_action or frozenset())
        p2_kept = _apply_keep(state.p2.dice_kept, p2_action or frozenset())
        new_state = replace(
            state,
            phase=next_phase,
            p1=replace(state.p1, dice_kept=p1_kept),
            p2=replace(state.p2, dice_kept=p2_kept),
        )
        return new_state, []

    def _phase_reroll(
        self,
        state: GameState,
        next_phase: GamePhase,
    ) -> tuple[GameState, list[GameEvent]]:
        p1_faces = _reroll_unkept(
            state.p1.dice_faces, state.p1.dice_kept, self.p1_die_types, self.rng
        )
        p2_faces = _reroll_unkept(
            state.p2.dice_faces, state.p2.dice_kept, self.p2_die_types, self.rng
        )
        new_state = replace(
            state,
            phase=next_phase,
            p1=replace(state.p1, dice_faces=p1_faces),
            p2=replace(state.p2, dice_faces=p2_faces),
        )
        return new_state, []

    def _phase_god_power(
        self,
        state: GameState,
        p1_action: tuple[str, int] | None,
        p2_action: tuple[str, int] | None,
    ) -> tuple[GameState, list[GameEvent]]:
        """
        Accept GP choices from both agents, validate them, deduct token costs,
        and write the confirmed choice into each PlayerState for GOD_RESOLVE.

        Validation rules:
          - GP must be in the player's loadout.
          - Tier index must be 0, 1, or 2.
          - Player must have enough tokens to pay the cost.
        Invalid choices are silently treated as a pass (None).
        """
        p1 = state.p1
        p2 = state.p2
        events: list[GameEvent] = []

        def _validate(
            player: PlayerState,
            action: tuple[str, int] | None,
            player_num: int,
        ) -> tuple[PlayerState, tuple[str, int] | None]:
            if action is None:
                return player, None
            gp_id, tier_idx = action
            if gp_id not in player.gp_loadout:
                return player, None
            if tier_idx not in (0, 1, 2):
                return player, None
            gp = self._god_powers.get(gp_id)
            if gp is None:
                return player, None
            tier = gp.tiers[tier_idx]
            if player.tokens < tier.cost:
                return player, None
            # Valid - deduct tokens and record choice.
            new_player = replace(
                player,
                tokens=player.tokens - tier.cost,
                gp_choice=(gp_id, tier_idx),
            )
            events.append(GameEvent("gp_chosen", {
                "player": player_num, "gp_id": gp_id,
                "tier": tier_idx, "cost": tier.cost,
            }))
            return new_player, (gp_id, tier_idx)

        p1, _ = _validate(p1, p1_action, 1)
        p2, _ = _validate(p2, p2_action, 2)

        return replace(state, phase=GamePhase.COMBAT, p1=p1, p2=p2), events

    def _phase_combat(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Simultaneous attack resolution (Constitution resolution order step 3).
        Axes blocked by opponent Helmets; Arrows blocked by opponent Shields.
        Both players deal damage at the same time.
        """
        p1 = state.p1
        p2 = state.p2

        p1_axes   = p1.dice_faces.count("FACE_AXE")
        p1_arrows = p1.dice_faces.count("FACE_ARROW")
        p2_axes   = p2.dice_faces.count("FACE_AXE")
        p2_arrows = p2.dice_faces.count("FACE_ARROW")
        p1_helmets = p1.dice_faces.count("FACE_HELMET")
        p1_shields = p1.dice_faces.count("FACE_SHIELD")
        p2_helmets = p2.dice_faces.count("FACE_HELMET")
        p2_shields = p2.dice_faces.count("FACE_SHIELD")

        # Net damage: attacker's unblocked faces each deal 1 HP.
        dmg_to_p2 = max(0, p1_axes - p2_helmets) + max(0, p1_arrows - p2_shields)
        dmg_to_p1 = max(0, p2_axes - p1_helmets) + max(0, p2_arrows - p1_shields)

        new_state = replace(
            state,
            phase=GamePhase.GOD_RESOLVE,
            p1=replace(p1, hp=p1.hp - dmg_to_p1),
            p2=replace(p2, hp=p2.hp - dmg_to_p2),
        )
        return new_state, [
            GameEvent("combat", {"dmg_to_p1": dmg_to_p1, "dmg_to_p2": dmg_to_p2})
        ]

    def _phase_god_resolve(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Apply both players' chosen God Powers simultaneously (L1: offensive GPs only).

        Resolution order (CLAUDE.md step 5): offensive GPs activate after combat.
        Both players' damage is calculated first, then applied simultaneously.
        This means Surtr self-damage and opponent damage both land at the same time.

        GPs implemented at L1 (Fenrir deferred to L2):
          GP_MJOLNIRS_WRATH  - direct damage to opponent
          GP_SKADIS_VOLLEY   - bonus per unblocked arrow (recalculated from final dice)
          GP_SURTRS_FLAME    - direct damage to opponent + self damage
          GP_LOKIS_GAMBIT    - random damage in [dmg_min, dmg_max] inclusive
        """
        p1 = state.p1
        p2 = state.p2

        if p1.gp_choice is None and p2.gp_choice is None:
            return replace(state, phase=GamePhase.TOKENS), []

        events: list[GameEvent] = []

        # Calculate all damage before applying (simultaneous resolution).
        dmg_to_p2 = 0
        dmg_to_p1 = 0
        self_dmg_to_p1 = 0
        self_dmg_to_p2 = 0

        def _resolve_offensive(
            attacker: PlayerState,
            defender: PlayerState,
            gp_id: str,
            tier_idx: int,
        ) -> tuple[int, int]:
            """Return (damage_to_defender, self_damage_to_attacker)."""
            gp = self._god_powers.get(gp_id)
            if gp is None or gp_id not in L1_OFFENSIVE_GP_IDS:
                return 0, 0
            tier = gp.tiers[tier_idx]

            if gp_id == "GP_MJOLNIRS_WRATH":
                return int(tier.damage), 0

            if gp_id == "GP_SURTRS_FLAME":
                return int(tier.damage), tier.self_damage

            if gp_id == "GP_LOKIS_GAMBIT":
                dmg = int(self.rng.integers(tier.dmg_min, tier.dmg_max + 1))
                return dmg, 0

            if gp_id == "GP_SKADIS_VOLLEY":
                # Bonus applies to arrows that were unblocked during combat this round.
                # Recalculate from final dice state (dice unchanged since REROLL_2).
                attacker_arrows = attacker.dice_faces.count("FACE_ARROW")
                defender_shields = defender.dice_faces.count("FACE_SHIELD")
                unblocked = max(0, attacker_arrows - defender_shields)
                return unblocked * tier.arrow_bonus, 0

            return 0, 0

        if p1.gp_choice is not None:
            gp_id, tier_idx = p1.gp_choice
            d, sd = _resolve_offensive(p1, p2, gp_id, tier_idx)
            dmg_to_p2 += d
            self_dmg_to_p1 += sd
            events.append(GameEvent("gp_resolved", {
                "player": 1, "gp_id": gp_id, "tier": tier_idx,
                "dmg_to_opponent": d, "self_damage": sd,
            }))

        if p2.gp_choice is not None:
            gp_id, tier_idx = p2.gp_choice
            d, sd = _resolve_offensive(p2, p1, gp_id, tier_idx)
            dmg_to_p1 += d
            self_dmg_to_p2 += sd
            events.append(GameEvent("gp_resolved", {
                "player": 2, "gp_id": gp_id, "tier": tier_idx,
                "dmg_to_opponent": d, "self_damage": sd,
            }))

        new_state = replace(
            state,
            phase=GamePhase.TOKENS,
            p1=replace(p1, hp=p1.hp - dmg_to_p1 - self_dmg_to_p1, gp_choice=None),
            p2=replace(p2, hp=p2.hp - dmg_to_p2 - self_dmg_to_p2, gp_choice=None),
        )
        return new_state, events

    def _phase_tokens(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Resolution order steps 7-8:
          7. Bordered Hands generate 1 token each (both players simultaneously).
          8. Bordered Hands + Tithing Hands each steal 1 token from opponent
             (amounts capped at opponent's post-generation total, resolved simultaneously).
        """
        p1 = state.p1
        p2 = state.p2

        p1_bordered = p1.dice_faces.count("FACE_HAND_BORDERED")
        p2_bordered = p2.dice_faces.count("FACE_HAND_BORDERED")
        p1_plain    = p1.dice_faces.count("FACE_HAND")
        p2_plain    = p2.dice_faces.count("FACE_HAND")

        # Step 7: simultaneous generation.
        p1_after_gen = p1.tokens + p1_bordered
        p2_after_gen = p2.tokens + p2_bordered

        # Step 8: simultaneous theft (capped at what the opponent had post-generation).
        p1_steal = min(p1_bordered + p1_plain, p2_after_gen)
        p2_steal = min(p2_bordered + p2_plain, p1_after_gen)

        p1_final = max(0, p1_after_gen + p1_steal - p2_steal)
        p2_final = max(0, p2_after_gen + p2_steal - p1_steal)

        new_state = replace(
            state,
            phase=GamePhase.END_CHECK,
            p1=replace(p1, tokens=p1_final),
            p2=replace(p2, tokens=p2_final),
        )
        return new_state, [
            GameEvent("tokens", {
                "p1_generated": p1_bordered, "p2_generated": p2_bordered,
                "p1_stole": p1_steal,        "p2_stole": p2_steal,
                "p1_final": p1_final,        "p2_final": p2_final,
            })
        ]

    def _phase_end_check(self, state: GameState) -> tuple[GameState, list[GameEvent]]:
        """
        Win condition: player(s) at or below 0 HP lose.
        Both dropping simultaneously -> draw (winner = 0).
        """
        p1_dead = state.p1.hp <= 0
        p2_dead = state.p2.hp <= 0

        if p1_dead and p2_dead:
            winner: int | None = 0
        elif p1_dead:
            winner = 2
        elif p2_dead:
            winner = 1
        else:
            winner = None

        if winner is not None:
            return replace(state, phase=GamePhase.GAME_OVER, winner=winner), [
                GameEvent("game_over", {
                    "winner": winner,
                    "round": state.round_num,
                    "p1_hp": state.p1.hp,
                    "p2_hp": state.p2.hp,
                })
            ]

        # No winner yet - start next round.
        new_state = replace(
            state,
            round_num=state.round_num + 1,
            phase=GamePhase.REVEAL,
            p1=replace(state.p1, dice_faces=_BLANK_FACES, dice_kept=_ALL_FREE, gp_choice=None),
            p2=replace(state.p2, dice_faces=_BLANK_FACES, dice_kept=_ALL_FREE, gp_choice=None),
        )
        return new_state, [GameEvent("round_end", {"round": state.round_num})]
