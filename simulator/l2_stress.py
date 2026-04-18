"""
l2_stress.py
------------
Constrained optimization stress test for the canonical L2 balance layer.

For each archetype:
  1. Hold the current baseline package fixed for the other archetypes.
  2. Search the strongest candidate shell inside the canonical candidate pool.
  3. Scan the intended predator archetype for at least one representative answer.

This is not a global metagame solver. It is a practical audit:
does the archetype loop still survive when one side pushes toward its strongest
available deck within the current L2 balance search space?
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from simulator.l2_balance import (
    ARCHETYPES,
    CanonicalCandidate,
    MatchupStats,
    RECOMMENDED_BASELINE_IDS,
    RECOMMENDED_PROFILE_ID,
    _build_candidates,
    _build_tuning_profiles,
    _make_package,
    _run_package,
    _tuned_god_powers,
    list_profiles,
)

_DEFAULT_BASELINE = dict(RECOMMENDED_BASELINE_IDS)
_PRIMARY_PREDATOR = {
    "AGGRO": "CONTROL",
    "CONTROL": "ECONOMY",
    "ECONOMY": "AGGRO",
    "COMBO": "AGGRO",
}


@dataclass(frozen=True)
class CandidateStrength:
    archetype: str
    candidate_id: str
    field_score: float
    row_rates: dict[str, float]
    avg_rounds: float
    draw_rate: float


@dataclass(frozen=True)
class PredatorAnswer:
    predator_archetype: str
    candidate_id: str
    target_win_rate: float
    predator_win_rate: float
    avg_rounds: float
    draw_rate: float


@dataclass(frozen=True)
class StressResult:
    archetype: str
    predator_archetype: str
    strongest: CandidateStrength
    answers: list[PredatorAnswer]


def _package_ids_from_arg(value: str | None) -> dict[str, str]:
    if not value:
        return dict(_DEFAULT_BASELINE)
    picked = [s.strip() for s in value.split(",")]
    if len(picked) != 4:
        raise SystemExit("--baseline-package requires 4 comma-separated IDs.")
    return dict(zip(ARCHETYPES, picked))


def _evaluate_package(
    ids: dict[str, str],
    candidates: dict[str, list[CanonicalCandidate]],
    profile,
    n_games: int,
    seed: int,
) -> tuple[dict[tuple[str, str], MatchupStats], float, float]:
    package = _make_package(ids, candidates)
    return _run_package(
        package,
        n_games=n_games,
        seed=seed,
        god_powers=_tuned_god_powers(profile),
        profile=profile,
    )


def _field_score_for(
    archetype: str,
    ids: dict[str, str],
    matchup_stats: dict[tuple[str, str], MatchupStats],
) -> CandidateStrength:
    def symmetric_target_rate(opp: str) -> float:
        forward = matchup_stats[(archetype, opp)].decisive_win_rate
        reverse = matchup_stats[(opp, archetype)].decisive_win_rate
        return (forward + (1.0 - reverse)) / 2.0

    row_rates = {
        opp: symmetric_target_rate(opp)
        for opp in ARCHETYPES
        if opp != archetype
    }
    field_score = sum(row_rates.values()) / len(row_rates)
    avg_rounds = sum(
        (
            matchup_stats[(archetype, opp)].avg_rounds +
            matchup_stats[(opp, archetype)].avg_rounds
        ) / 2.0
        for opp in ARCHETYPES
        if opp != archetype
    ) / 3.0
    draw_rate = sum(
        (
            matchup_stats[(archetype, opp)].draw_rate +
            matchup_stats[(opp, archetype)].draw_rate
        ) / 2.0
        for opp in ARCHETYPES
        if opp != archetype
    ) / 3.0
    return CandidateStrength(
        archetype=archetype,
        candidate_id=ids[archetype],
        field_score=field_score,
        row_rates=row_rates,
        avg_rounds=avg_rounds,
        draw_rate=draw_rate,
    )


def find_strongest_candidate(
    archetype: str,
    base_ids: dict[str, str],
    candidates: dict[str, list[CanonicalCandidate]],
    profile,
    n_games: int,
    seed: int,
) -> list[CandidateStrength]:
    strengths: list[CandidateStrength] = []
    for candidate in candidates[archetype]:
        ids = dict(base_ids)
        ids[archetype] = candidate.id
        matchup_stats, _, _ = _evaluate_package(ids, candidates, profile, n_games, seed)
        strengths.append(_field_score_for(archetype, ids, matchup_stats))
    strengths.sort(key=lambda s: (-s.field_score, s.draw_rate, s.avg_rounds, s.candidate_id))
    return strengths


def find_predator_answers(
    target_archetype: str,
    strongest_id: str,
    base_ids: dict[str, str],
    candidates: dict[str, list[CanonicalCandidate]],
    profile,
    n_games: int,
    seed: int,
    answer_threshold: float,
) -> list[PredatorAnswer]:
    predator = _PRIMARY_PREDATOR[target_archetype]
    answers: list[PredatorAnswer] = []
    for predator_candidate in candidates[predator]:
        ids = dict(base_ids)
        ids[target_archetype] = strongest_id
        ids[predator] = predator_candidate.id
        matchup_stats, _, _ = _evaluate_package(ids, candidates, profile, n_games, seed)
        forward = matchup_stats[(target_archetype, predator)].decisive_win_rate
        reverse = matchup_stats[(predator, target_archetype)].decisive_win_rate
        symmetric_target_wr = (forward + (1.0 - reverse)) / 2.0
        symmetric_predator_wr = 1.0 - symmetric_target_wr
        if symmetric_target_wr <= answer_threshold:
            answers.append(
                PredatorAnswer(
                    predator_archetype=predator,
                    candidate_id=predator_candidate.id,
                    target_win_rate=symmetric_target_wr,
                    predator_win_rate=symmetric_predator_wr,
                    avg_rounds=(
                        matchup_stats[(target_archetype, predator)].avg_rounds +
                        matchup_stats[(predator, target_archetype)].avg_rounds
                    ) / 2.0,
                    draw_rate=(
                        matchup_stats[(target_archetype, predator)].draw_rate +
                        matchup_stats[(predator, target_archetype)].draw_rate
                    ) / 2.0,
                )
            )
    answers.sort(key=lambda a: (a.target_win_rate, -a.predator_win_rate, a.draw_rate, a.candidate_id))
    return answers


def run_stress_audit(
    base_ids: dict[str, str],
    profile_id: str,
    n_games: int,
    seed: int,
    top_candidates: int,
    answer_threshold: float,
) -> tuple[list[StressResult], dict[str, list[CandidateStrength]]]:
    candidates = _build_candidates()
    profile = _build_tuning_profiles()[profile_id]
    results: list[StressResult] = []
    candidate_rankings: dict[str, list[CandidateStrength]] = {}

    for archetype in ARCHETYPES:
        strengths = find_strongest_candidate(archetype, base_ids, candidates, profile, n_games, seed)
        candidate_rankings[archetype] = strengths[:top_candidates]
        strongest = strengths[0]
        answers = find_predator_answers(
            archetype,
            strongest.candidate_id,
            base_ids,
            candidates,
            profile,
            n_games,
            seed,
            answer_threshold,
        )
        results.append(
            StressResult(
                archetype=archetype,
                predator_archetype=_PRIMARY_PREDATOR[archetype],
                strongest=strongest,
                answers=answers,
            )
        )
    return results, candidate_rankings


def _fmt_rate_map(row_rates: dict[str, float]) -> str:
    return "  ".join(f"{opp}={row_rates[opp]:.1%}" for opp in ARCHETYPES if opp in row_rates)


def print_results(
    results: list[StressResult],
    rankings: dict[str, list[CandidateStrength]],
    base_ids: dict[str, str],
    profile_id: str,
    answer_threshold: float,
) -> None:
    print("\nL2 constrained stress audit\n")
    print(f"Profile: {profile_id}")
    print(
        f"Baseline package: {base_ids['AGGRO']}, {base_ids['CONTROL']}, "
        f"{base_ids['ECONOMY']}, {base_ids['COMBO']}"
    )
    print(f"Predator answer threshold: target decisive win rate <= {answer_threshold:.0%}\n")

    print("Strongest constrained candidates")
    for archetype in ARCHETYPES:
        print(f"- {archetype}:")
        for rank, candidate in enumerate(rankings[archetype], 1):
            print(
                f"  {rank}. {candidate.candidate_id}  field={candidate.field_score:.1%}  "
                f"rounds={candidate.avg_rounds:.2f}  draw={candidate.draw_rate:.1%}"
            )
            print(f"     {_fmt_rate_map(candidate.row_rates)}")

    print("\nPredator answers")
    all_answered = True
    for result in results:
        if result.answers:
            best_answer = result.answers[0]
            print(
                f"- {result.archetype}: strongest={result.strongest.candidate_id}  "
                f"predator={result.predator_archetype}  best_answer={best_answer.candidate_id}  "
                f"target_wr={best_answer.target_win_rate:.1%}  predator_wr={best_answer.predator_win_rate:.1%}  "
                f"rounds={best_answer.avg_rounds:.2f}  draw={best_answer.draw_rate:.1%}"
            )
        else:
            all_answered = False
            print(
                f"- {result.archetype}: strongest={result.strongest.candidate_id}  "
                f"predator={result.predator_archetype}  no answer found"
            )

    verdict = "PASS" if all_answered else "FAIL"
    print(f"\nVerdict: {verdict}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Constrained strongest-deck stress audit.")
    parser.add_argument("--games", type=int, default=48, help="Games per matchup during audit.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed.")
    parser.add_argument(
        "--tune-profile",
        type=str,
        default=RECOMMENDED_PROFILE_ID,
        choices=list_profiles(),
        help="Named GP tuning profile to evaluate.",
    )
    parser.add_argument(
        "--baseline-package",
        type=str,
        default=None,
        help="Comma-separated package IDs, e.g. A_CAN4,C_CAN2,E_CAN5,CO_CAN1",
    )
    parser.add_argument(
        "--top-candidates",
        type=int,
        default=3,
        help="How many strongest candidates per archetype to retain for reporting.",
    )
    parser.add_argument(
        "--answer-threshold",
        type=float,
        default=0.45,
        help="A predator counts as an answer if the target decisive win rate is at or below this value.",
    )
    args = parser.parse_args()

    base_ids = _package_ids_from_arg(args.baseline_package)
    results, rankings = run_stress_audit(
        base_ids=base_ids,
        profile_id=args.tune_profile,
        n_games=args.games,
        seed=args.seed,
        top_candidates=args.top_candidates,
        answer_threshold=args.answer_threshold,
    )
    print_results(results, rankings, base_ids, args.tune_profile, args.answer_threshold)


if __name__ == "__main__":
    main()
