"""
game_state.py
-------------
Immutable GameState and supporting types.

Pattern:  GameState + Action → GameEngine.apply() → (NewGameState, [GameEvent])

Everything here is pure data — no logic, no RNG, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class GamePhase(str, Enum):
    """All 11 phases of a round, plus GAME_OVER sentinel."""
    REVEAL      = "REVEAL"       # Phase 1  — battlefield conditions (L4+)
    ROLL        = "ROLL"         # Phase 2  — initial dice roll
    KEEP_1      = "KEEP_1"       # Phase 3  — first keep selection
    REROLL_1    = "REROLL_1"     # Phase 4  — reroll unkept dice
    KEEP_2      = "KEEP_2"       # Phase 5  — second keep selection
    REROLL_2    = "REROLL_2"     # Phase 6  — final reroll
    GOD_POWER   = "GOD_POWER"    # Phase 7  — god power selection (L1+)
    COMBAT      = "COMBAT"       # Phase 8  — dice attacks resolve
    GOD_RESOLVE = "GOD_RESOLVE"  # Phase 9  — god powers activate (L1+)
    TOKENS      = "TOKENS"       # Phase 10 — hand dice generate / steal tokens
    END_CHECK   = "END_CHECK"    # Phase 11 — win condition; advance round or end
    GAME_OVER   = "GAME_OVER"    # Terminal state


@dataclass(frozen=True)
class PlayerState:
    hp: int
    tokens: int
    dice_faces: tuple[str, ...]   # face IDs for each of the 6 dice in the loadout
    dice_kept: tuple[bool, ...]   # True = die is locked in for this round


@dataclass(frozen=True)
class GameState:
    round_num: int
    phase: GamePhase
    p1: PlayerState
    p2: PlayerState
    winner: Optional[int]   # None = ongoing  |  1 = P1 wins  |  2 = P2 wins  |  0 = draw


@dataclass
class GameEvent:
    """Lightweight event emitted by the engine for logging / analysis."""
    type: str
    data: dict[str, Any]

    def __repr__(self) -> str:
        return f"GameEvent({self.type}, {self.data})"
