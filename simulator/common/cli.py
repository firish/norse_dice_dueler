"""Shared CLI helpers for simulator and balance entrypoints."""

from __future__ import annotations

import argparse


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
        choices=("rule-based", "game-aware", "tier-aware", "game-aware-tier"),
        default=default,
        help="agent family to use for the archetype pilots",
    )
