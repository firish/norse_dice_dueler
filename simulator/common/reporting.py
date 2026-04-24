"""Shared printing helpers for simulator and balance harnesses."""

from __future__ import annotations

from simulator.common.matchup_runner import DIRECTIONAL_MATCHUPS


def print_directional_rows(
    results: dict[tuple[str, str], dict],
    *,
    rate_key: str = "p1_rate",
    draw_key: str = "draws",
    prefix: str = "  ",
) -> None:
    """Print the standard six off-diagonal directional matchup rows."""
    for matchup in DIRECTIONAL_MATCHUPS:
        result = results[matchup]
        print(
            f"{prefix}{matchup[0]:>8} -> {matchup[1]:<8} "
            f"{result[rate_key]:5.1f}%  draws={result[draw_key]}"
        )


def print_directional_deltas(
    baseline: dict[tuple[str, str], dict],
    results: dict[tuple[str, str], dict],
    *,
    rate_key: str = "p1_rate",
    prefix: str = "  ",
) -> None:
    """Print the standard directional rows with drift deltas versus baseline."""
    for matchup in DIRECTIONAL_MATCHUPS:
        base = baseline[matchup][rate_key]
        curr = results[matchup][rate_key]
        delta = curr - base
        print(
            f"{prefix}{matchup[0]:>8} -> {matchup[1]:<8} "
            f"{curr:5.1f}%  delta={delta:+5.1f}pp  draws={results[matchup]['draws']}"
        )
