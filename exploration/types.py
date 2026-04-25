"""Common dataclasses used by exploration tools."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    """One legal candidate loadout inside an exploration pool."""

    id: str
    archetype: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type
    summary: str
    identity_score: float = 0.0

    @property
    def name(self) -> str:
        """Expose a stable name for shared matchup helpers."""
        return self.id


@dataclass(frozen=True)
class CandidatePool:
    """A named, legal candidate space grouped by archetype."""

    pool_id: str
    display_name: str
    grammar: str
    targets: dict[tuple[str, str], float]
    candidates_by_archetype: dict[str, dict[str, Candidate]]
    approved_package_ids: dict[str, str]
    identity_requirements: dict[str, dict[str, int]]


@dataclass(frozen=True)
class CandidateStanding:
    """One candidate's standing inside an intra-archetype tournament."""

    candidate_id: str
    archetype: str
    points: float
    series_wins: int
    series_losses: int
    series_ties: int
    decisive_rate: float
    wins: int
    losses: int
    draws: int
    identity_score: float


@dataclass(frozen=True)
class PackageEvaluation:
    """One evaluated three-candidate package."""

    package_ids: dict[str, str]
    matrix_error: float
    rank_sum: int
    identity_sum: float
    results: dict[tuple[str, str], dict[str, float | int]]
