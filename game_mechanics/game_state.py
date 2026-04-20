"""
game_state.py
-------------
Immutable GameState and supporting types.

Pattern:  GameState + Action -> GameEngine.apply() -> (NewGameState, [GameEvent])

Everything here is pure data - no logic, no RNG, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class GamePhase(str, Enum):
    """All 11 phases of a round, plus GAME_OVER sentinel."""
    REVEAL      = "REVEAL"       # Phase 1  - battlefield conditions (L4+)
    ROLL        = "ROLL"         # Phase 2  - initial dice roll
    KEEP_1      = "KEEP_1"       # Phase 3  - first keep selection
    REROLL_1    = "REROLL_1"     # Phase 4  - reroll unkept dice
    KEEP_2      = "KEEP_2"       # Phase 5  - second keep selection
    REROLL_2    = "REROLL_2"     # Phase 6  - final reroll
    GOD_POWER   = "GOD_POWER"    # Phase 7  - god power selection (L1+)
    COMBAT      = "COMBAT"       # Phase 8  - dice attacks resolve
    GOD_RESOLVE = "GOD_RESOLVE"  # Phase 9  - god powers activate (L1+)
    TOKENS      = "TOKENS"       # Phase 10 - hand dice generate / steal tokens
    END_CHECK   = "END_CHECK"    # Phase 11 - win condition; advance round or end
    GAME_OVER   = "GAME_OVER"    # Terminal state


@dataclass(frozen=True)
class PlayerState:
    """Snapshot of one player's state at a given point in the game.

    Example (start of round 1, Huskarl loadout, with GP loadout):
        PlayerState(
            hp=15,
            tokens=0,
            dice_faces=("FACE_AXE", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD", "FACE_HAND", "FACE_HAND_BORDERED"),
            dice_kept=(False, False, False, False, False, False),
            gp_loadout=("GP_MJOLNIRS_WRATH", "GP_SURTRS_FLAME", "GP_LOKIS_GAMBIT"),
            gp_choice=None,
        )
    """
    hp: int                       # health points
    tokens: int                   # the number of accumalated god favor tokens
    dice_faces: tuple[str, ...]   # face IDs for each of the 6 dice in the loadout
    dice_kept: tuple[bool, ...]   # True = die is locked in for this round
    gp_loadout: tuple[str, ...] = ()          # GP IDs brought into the match (empty = L0, no GPs)
    gp_choice: tuple[str, int] | None = None  # (gp_id, tier_idx 0-2) chosen this round; None = pass


@dataclass(frozen=True)
class GameState:
    """Full snapshot of the game at a single point in time.

    Example (start of round 2, both players mid-game):
        GameState(
            round_num=2,
            phase=GamePhase.ROLL,
            p1=PlayerState(hp=13, tokens=2, dice_faces=(...), dice_kept=(...)),
            p2=PlayerState(hp=14, tokens=1, dice_faces=(...), dice_kept=(...)),
            winner=None,
        )
    """
    round_num: int          # the number of the current round in current game
    phase: GamePhase        # the number of the current phase in current round
    p1: PlayerState         # the player 1 state at the current gamestate
    p2: PlayerState         # the player 2 state at the current gamestate
    winner: Optional[int]   # None = ongoing  |  1 = P1 wins  |  2 = P2 wins  |  0 = draw


@dataclass
class GameEvent:
    """Lightweight event emitted by the engine for logging / analysis.

    Example (a damage event):
        GameEvent(type="DAMAGE", data={"target": 1, "amount": 2, "source": "FACE_AXE"})
    """
    type: str                   # event type
    data: dict[str, Any]        # event data (can log any type of event)
