"""Shared CLI helpers for simulator and balance entrypoints."""

from __future__ import annotations

import argparse

from archetypes.common import AGENT_MODES


def add_games_arg(
    parser: argparse.ArgumentParser,
    *,
    default: int,
    help_text: str = "games per directional matchup",
) -> None:
    """Add the common `--games` argument to a harness parser."""
    parser.add_argument("--games", type=int, default=default, help=help_text)


def add_seed_arg(
    parser: argparse.ArgumentParser,
    *,
    default: int = 42,
) -> None:
    """Add the common `--seed` argument to a harness parser."""
    parser.add_argument("--seed", type=int, default=default, help="RNG seed")


def add_agent_mode_arg(
    parser: argparse.ArgumentParser,
    *,
    default: str = "rule-based",
) -> None:
    """Add the shared `--agent-mode` selector to a harness parser."""
    parser.add_argument(
        "--agent-mode",
        choices=AGENT_MODES,
        default=default,
        help="agent family to use for the archetype pilots",
    )
