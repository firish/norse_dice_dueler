"""Shared agent-family helpers for canonical archetype packages."""

from __future__ import annotations

from agents.game_aware.aggro_agent import GameAwareAggroAgent
from agents.game_aware.control_agent import GameAwareControlAgent
from agents.game_aware.economy_agent import GameAwareEconomyAgent
from agents.game_aware_tier.aggro_agent import GameAwareTierAggroAgent
from agents.game_aware_tier.control_agent import GameAwareTierControlAgent
from agents.game_aware_tier.economy_agent import GameAwareTierEconomyAgent
from agents.game_aware_tier_loadout.aggro_agent import GameAwareTierLoadoutAggroAgent
from agents.game_aware_tier_loadout.control_agent import GameAwareTierLoadoutControlAgent
from agents.game_aware_tier_loadout.economy_agent import GameAwareTierLoadoutEconomyAgent
from agents.rollout.aggro_agent import RolloutAggroAgent
from agents.rollout.control_agent import RolloutControlAgent
from agents.rollout.economy_agent import RolloutEconomyAgent
from agents.rule_based.aggro_agent import MatchupAwareAggroAgent
from agents.rule_based.control_agent import MatchupAwareControlAgent
from agents.rule_based.economy_agent import MatchupAwareEconomyAgent
from agents.rule_based.aggro_agent import TierAwareAggroAgent
from agents.rule_based.control_agent import TierAwareControlAgent
from agents.rule_based.economy_agent import TierAwareEconomyAgent

AGENT_MODES: tuple[str, ...] = (
    "rule-based",
    "game-aware",
    "tier-aware",
    "game-aware-tier",
    "game-aware-tier-loadout",
    "rollout",
)


def agent_classes(agent_mode: str = "rule-based") -> dict[str, type]:
    """Return the canonical Aggro/Control/Economy pilots for an agent family."""
    if agent_mode == "rule-based":
        return {
            "AGGRO": MatchupAwareAggroAgent,
            "CONTROL": MatchupAwareControlAgent,
            "ECONOMY": MatchupAwareEconomyAgent,
        }
    if agent_mode == "tier-aware":
        return {
            "AGGRO": TierAwareAggroAgent,
            "CONTROL": TierAwareControlAgent,
            "ECONOMY": TierAwareEconomyAgent,
        }
    if agent_mode == "game-aware-tier":
        return {
            "AGGRO": GameAwareTierAggroAgent,
            "CONTROL": GameAwareTierControlAgent,
            "ECONOMY": GameAwareTierEconomyAgent,
        }
    if agent_mode == "game-aware-tier-loadout":
        return {
            "AGGRO": GameAwareTierLoadoutAggroAgent,
            "CONTROL": GameAwareTierLoadoutControlAgent,
            "ECONOMY": GameAwareTierLoadoutEconomyAgent,
        }
    if agent_mode == "game-aware":
        return {
            "AGGRO": GameAwareAggroAgent,
            "CONTROL": GameAwareControlAgent,
            "ECONOMY": GameAwareEconomyAgent,
        }
    if agent_mode == "rollout":
        return {
            "AGGRO": RolloutAggroAgent,
            "CONTROL": RolloutControlAgent,
            "ECONOMY": RolloutEconomyAgent,
        }
    raise ValueError(f"Unknown agent mode: {agent_mode}")
