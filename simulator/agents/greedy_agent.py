"""
greedy_agent.py
---------------
Simple L1 GP user.

Keep strategy:
  - Keep FACE_AXE and FACE_ARROW (damage).
  - Keep FACE_HAND_BORDERED (tokens).
  - Keep FACE_HAND (steal).

GP strategy:
  - Bring a 3-GP loadout chosen outside the agent.
  - At GP phase, cast a random affordable GP from that loadout.
  - Use T1 only.

This keeps L1 intentionally lightweight: it answers the narrow question
"does having access to God Powers beat a no-GP random baseline?"
without pulling in archetype-specific logic yet.
"""

from __future__ import annotations

import numpy as np

from simulator.agents import Agent, try_gp, with_banked_tokens
from simulator.game_state import GameState
from simulator.god_powers import load_god_powers

_KEEP_FACES = frozenset({
    "FACE_AXE",
    "FACE_ARROW",
    "FACE_HAND_BORDERED",
    "FACE_HAND",
})


class GreedyAgent(Agent):
    """Simple L1 agent: offensive keeps, random affordable GP choice."""

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        player = state.p1 if player_num == 1 else state.p2
        return frozenset(
            i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
            if not kept and face in _KEEP_FACES
        )

    def choose_god_power(self, state: GameState, player_num: int) -> tuple[str, int] | None:
        player = with_banked_tokens(state.p1 if player_num == 1 else state.p2)

        affordable: list[tuple[str, int]] = []
        for gp_id in player.gp_loadout:
            choice = try_gp(player, self._god_powers, gp_id, (0,))
            if choice is not None:
                affordable.append(choice)

        if not affordable:
            return None

        return affordable[int(self.rng.integers(0, len(affordable)))]
