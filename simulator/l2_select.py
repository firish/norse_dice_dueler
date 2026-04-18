"""
l2_select.py
------------
Select a representative L2 package that satisfies both:
  1. good l2_balance objective
  2. passing l2_stress predator-answer audit

This is intentionally a selector, not a tuner. It keeps the current candidate
pool, GP tuning profile, and agent logic fixed, then searches for packages that
look good under both lenses.
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
    PackageScore,
    RECOMMENDED_PROFILE_ID,
    _build_candidates,
    _build_tuning_profiles,
    _score_package,
    list_profiles,
    print_package,
    search_packages,
)
from simulator.l2_stress import StressResult, run_stress_audit


@dataclass(frozen=True)
class SelectedPackage:
    search_rank: int
    quick_score: PackageScore
    final_score: PackageScore
    stress_results: list[StressResult]


def _stress_passes(results: list[StressResult]) -> bool:
    return all(result.answers for result in results)


def _stress_summary(results: list[StressResult]) -> str:
    parts: list[str] = []
    for result in results:
        if result.answers:
            parts.append(f"{result.archetype}:ok")
        else:
            parts.append(f"{result.archetype}:FAIL")
    return "  ".join(parts)


def select_packages(
    profile_id: str,
    search_games: int,
    stress_games: int,
    final_games: int,
    seed: int,
    top_balance: int,
    top_final: int,
    answer_threshold: float,
) -> tuple[list[SelectedPackage], list[PackageScore]]:
    candidates = _build_candidates()
    profile = _build_tuning_profiles()[profile_id]
    quick_scores = search_packages(
        n_games=search_games,
        seed=seed,
        profile_ids=(profile_id,),
    )

    selected: list[SelectedPackage] = []
    for rank, quick_score in enumerate(quick_scores[:top_balance], 1):
        stress_results, _ = run_stress_audit(
            base_ids=quick_score.ids,
            profile_id=profile_id,
            n_games=stress_games,
            seed=seed,
            top_candidates=1,
            answer_threshold=answer_threshold,
        )
        if not _stress_passes(stress_results):
            continue

        final_score = _score_package(
            quick_score.ids,
            candidates,
            n_games=final_games,
            seed=seed,
            profile=profile,
        )
        selected.append(
            SelectedPackage(
                search_rank=rank,
                quick_score=quick_score,
                final_score=final_score,
                stress_results=stress_results,
            )
        )

    selected.sort(
        key=lambda s: (
            s.final_score.objective,
            s.final_score.matrix_error,
            s.final_score.draw_rate,
            s.search_rank,
        )
    )
    return selected[:top_final], quick_scores[:top_balance]


def print_selection(
    selected: list[SelectedPackage],
    searched: list[PackageScore],
    profile_id: str,
    search_games: int,
    stress_games: int,
    final_games: int,
    top_balance: int,
    answer_threshold: float,
) -> None:
    print("\nL2 package selector\n")
    print(
        f"Profile: {profile_id}\n"
        f"Search games={search_games}  Stress games={stress_games}  Final games={final_games}\n"
        f"Balance shortlist={min(top_balance, len(searched))}  "
        f"Stress threshold={answer_threshold:.0%}\n"
    )

    if not selected:
        print("No stress-safe packages found in the searched shortlist.")
        return

    print("Stress-safe representative packages\n")
    for idx, package in enumerate(selected, 1):
        ids = package.final_score.ids
        print(
            f"{idx}. {ids['AGGRO']}, {ids['CONTROL']}, {ids['ECONOMY']}, {ids['COMBO']}  "
            f"search_rank={package.search_rank}  "
            f"obj={package.final_score.objective:.3f}  "
            f"matrix={package.final_score.matrix_error:.3f}  "
            f"rounds={package.final_score.avg_rounds:.2f}  "
            f"draw={package.final_score.draw_rate:.1%}  "
            f"rps_fail={package.final_score.rps_failures}"
        )
        print(f"   stress: {_stress_summary(package.stress_results)}")


def _parse_package_ids(value: str) -> dict[str, str]:
    picked = [s.strip() for s in value.split(",")]
    if len(picked) != 4:
        raise SystemExit("--validate requires 4 comma-separated IDs.")
    return dict(zip(ARCHETYPES, picked))


def validate_package(
    package_arg: str,
    profile_id: str,
    score_games: int,
    stress_games: int,
    seed: int,
    answer_threshold: float,
) -> None:
    candidates = _build_candidates()
    profile = _build_tuning_profiles()[profile_id]
    ids = _parse_package_ids(package_arg)
    score = _score_package(ids, candidates, n_games=score_games, seed=seed, profile=profile)
    print_package(score)
    print()
    stress_results, _ = run_stress_audit(
        base_ids=ids,
        profile_id=profile_id,
        n_games=stress_games,
        seed=seed,
        top_candidates=3,
        answer_threshold=answer_threshold,
    )
    print("Stress summary")
    for result in stress_results:
        status = "PASS" if result.answers else "FAIL"
        print(
            f"- {result.archetype}: strongest={result.strongest.candidate_id}  "
            f"predator={result.predator_archetype}  {status}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Select stress-safe L2 balance packages.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed.")
    parser.add_argument(
        "--tune-profile",
        type=str,
        default=RECOMMENDED_PROFILE_ID,
        choices=list_profiles(),
        help="Named GP tuning profile to evaluate.",
    )
    parser.add_argument("--search-games", type=int, default=12, help="Games per matchup for initial balance ranking.")
    parser.add_argument("--stress-games", type=int, default=16, help="Games per matchup for stress filtering.")
    parser.add_argument("--final-games", type=int, default=64, help="Games per matchup for final validation of survivors.")
    parser.add_argument("--top-balance", type=int, default=24, help="How many top balance packages to stress-test.")
    parser.add_argument("--top-final", type=int, default=6, help="How many final stress-safe packages to print.")
    parser.add_argument(
        "--answer-threshold",
        type=float,
        default=0.45,
        help="Predator answer threshold passed to l2_stress.",
    )
    parser.add_argument(
        "--validate",
        type=str,
        default=None,
        help="Comma-separated package IDs to score and stress-check directly.",
    )
    args = parser.parse_args()

    if args.validate:
        validate_package(
            package_arg=args.validate,
            profile_id=args.tune_profile,
            score_games=args.final_games,
            stress_games=args.stress_games,
            seed=args.seed,
            answer_threshold=args.answer_threshold,
        )
        return

    selected, searched = select_packages(
        profile_id=args.tune_profile,
        search_games=args.search_games,
        stress_games=args.stress_games,
        final_games=args.final_games,
        seed=args.seed,
        top_balance=args.top_balance,
        top_final=args.top_final,
        answer_threshold=args.answer_threshold,
    )
    print_selection(
        selected=selected,
        searched=searched,
        profile_id=args.tune_profile,
        search_games=args.search_games,
        stress_games=args.stress_games,
        final_games=args.final_games,
        top_balance=args.top_balance,
        answer_threshold=args.answer_threshold,
    )


if __name__ == "__main__":
    main()
