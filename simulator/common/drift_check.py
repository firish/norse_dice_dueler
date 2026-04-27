"""Shared L4 helpers for condition-drift benchmarks and balance sweeps."""

from __future__ import annotations

from archetypes.level_3_advanced import APPROVED_PACKAGE_NAME, TARGETS, build_archetypes
from simulator.common.matchup_runner import (
    matrix_error as compute_matrix_error,
    run_matrix as run_archetype_matrix,
)

DEFAULT_LEVEL_4_AGENT_MODE = "game-aware-tier"
DRIFT_PASS_THRESHOLD = 10.0
DRIFT_IDEAL_MIN = 5.0
DRIFT_IDEAL_MAX = 10.0


def run_condition_matrix(
    games: int,
    seed: int,
    *,
    condition_id: str | None = None,
    condition_ids: tuple[str, ...] | None = None,
    agent_mode: str = DEFAULT_LEVEL_4_AGENT_MODE,
) -> dict[tuple[str, str], dict]:
    """Run the L4 off-diagonal matrix for one condition or one condition pair."""
    archetypes = build_archetypes(agent_mode)
    return run_archetype_matrix(
        archetypes,
        games,
        seed,
        include_mirrors=False,
        condition_id=condition_id,
        condition_ids=condition_ids,
    )


def level_4_matrix_error(results: dict[tuple[str, str], dict]) -> float:
    """Return absolute error from the directional L4 target matrix."""
    return compute_matrix_error(results, TARGETS)


def max_drift(
    baseline: dict[tuple[str, str], dict],
    results: dict[tuple[str, str], dict],
) -> float:
    """Return the worst absolute directional swing versus the no-condition baseline."""
    return max(abs(float(results[key]["p1_rate"]) - float(baseline[key]["p1_rate"])) for key in TARGETS)


def print_level_4_baseline(
    title: str,
    results: dict[tuple[str, str], dict],
    *,
    print_rows,
) -> None:
    """Print the shared no-condition L4 baseline header."""
    print(title)
    print(f"Baseline package: {APPROVED_PACKAGE_NAME}")
    print("  Aggro    = 3 Warrior + Berserker + Berserker + Gambler")
    print("  Control  = 3 Warrior + Warden + Warden + Skald")
    print("  Economy  = 3 Warrior + Miser + Miser + Hunter")
    print(f"  Baseline matrix error: {level_4_matrix_error(results):.1f}")
    print_rows(results)
    print()
