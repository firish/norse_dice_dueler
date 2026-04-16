"""
greedy_agent.py
---------------
GreedyAgent - the L1 heuristic agent.

Keep strategy (offensive bias):
  - Keep FACE_AXE and FACE_ARROW (deal damage).
  - Keep FACE_HAND_BORDERED (generates tokens to fund GPs).
  - Keep FACE_HAND (steals tokens).
  - Reroll FACE_HELMET and FACE_SHIELD (no offensive value).

GP strategy:
  - Score each affordable (gp_id, tier) by expected net damage efficiency
    (expected damage to opponent / token cost).
  - Activate the highest-scoring option; pass if nothing is affordable.
  - Tier selection: always try highest tier first to maximise impact.

L1 validation target: GreedyAgent (offensive GP loadout) beats RandomAgent 60-70%.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent.parent))

from simulator.agents import Agent
from simulator.game_state import GameState
from simulator.god_powers import L1_OFFENSIVE_GP_IDS, load_god_powers

# Faces worth keeping for an offensive-biased agent.
_KEEP_FACES = frozenset({
    "FACE_AXE",
    "FACE_ARROW",
    "FACE_HAND_BORDERED",
    "FACE_HAND",
})


class GreedyAgent(Agent):
    """
    Heuristic agent that greedily keeps offensive dice and activates the most
    efficient affordable God Power each round.

    Args:
        rng: optional NumPy random generator (used for tie-breaking only).
    """

    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self.rng = rng or np.random.default_rng()
        self._god_powers = load_god_powers()

    # ------------------------------------------------------------------
    # Keep phase
    # ------------------------------------------------------------------

    def choose_keep(self, state: GameState, player_num: int) -> frozenset[int]:
        """Keep offensive faces (axes, arrows) and token-generating faces (bordered hands, hands)."""
        player = state.p1 if player_num == 1 else state.p2
        return frozenset(
            i for i, (face, kept) in enumerate(zip(player.dice_faces, player.dice_kept))
            if not kept and face in _KEEP_FACES
        )

    # ------------------------------------------------------------------
    # God Power phase
    # ------------------------------------------------------------------

    def choose_god_power(
        self, state: GameState, player_num: int
    ) -> tuple[str, int] | None:
        """
        Evaluate all affordable GPs and return the highest-efficiency option.

        Efficiency = expected_net_damage / cost.
          - Mjölnir: damage / cost
          - Surtr:   (damage - self_damage) / cost  (net damage after self-harm)
          - Loki:    midpoint(dmg_min, dmg_max) / cost
          - Skaði:   expected_bonus_damage / cost
                     (arrows in current dice * arrow_bonus; conservative estimate)

        Returns None if nothing is affordable or all options score <= 0.
        """
        player = state.p1 if player_num == 1 else state.p2
        opponent = state.p2 if player_num == 1 else state.p1

        best_score = 0.0
        best_choice: tuple[str, int] | None = None

        for gp_id in player.gp_loadout:
            if gp_id not in L1_OFFENSIVE_GP_IDS:
                continue
            gp = self._god_powers.get(gp_id)
            if gp is None:
                continue

            # Try tiers highest to lowest so we naturally pick the biggest
            # affordable tier when efficiency is equal.
            for tier_idx in (2, 1, 0):
                tier = gp.tiers[tier_idx]
                if player.tokens < tier.cost:
                    continue

                score = self._score_gp(gp_id, tier_idx, player, opponent)
                if score > best_score:
                    best_score = score
                    best_choice = (gp_id, tier_idx)
                # Only need the best affordable tier per GP.
                break

        return best_choice

    # ------------------------------------------------------------------
    # Internal scoring
    # ------------------------------------------------------------------

    def _score_gp(
        self,
        gp_id: str,
        tier_idx: int,
        player: object,
        opponent: object,
    ) -> float:
        """Return expected net damage per token for a given GP + tier."""
        gp = self._god_powers[gp_id]
        tier = gp.tiers[tier_idx]

        if gp_id == "GP_MJOLNIRS_WRATH":
            return tier.damage / tier.cost

        if gp_id == "GP_SURTRS_FLAME":
            net = tier.damage - tier.self_damage
            return net / tier.cost if net > 0 else 0.0

        if gp_id == "GP_LOKIS_GAMBIT":
            expected = (tier.dmg_min + tier.dmg_max) / 2.0
            return expected / tier.cost

        if gp_id == "GP_SKADIS_VOLLEY":
            # Estimate bonus from arrows currently showing.
            arrows = player.dice_faces.count("FACE_ARROW")  # type: ignore[union-attr]
            opp_shields = opponent.dice_faces.count("FACE_SHIELD")  # type: ignore[union-attr]
            unblocked = max(0, arrows - opp_shields)
            expected_bonus = unblocked * tier.arrow_bonus
            return expected_bonus / tier.cost if expected_bonus > 0 else 0.0

        return 0.0
