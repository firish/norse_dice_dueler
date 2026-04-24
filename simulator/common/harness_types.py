"""Common dataclasses and protocols used by simulator harnesses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ArchetypeLike(Protocol):
    """Minimal shape needed by the shared matchup runner."""

    name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


@dataclass(frozen=True)
class Archetype:
    """Fixed archetype definition used by benchmark-style harnesses."""

    name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type
