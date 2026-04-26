"""Intra-archetype tournament harness for realistic exploration pools."""

from __future__ import annotations

import argparse
from itertools import combinations

from exploration.candidate_pools import ARCHETYPE_ORDER, POOL_IDS, get_candidate_pool
from exploration.common import run_symmetric_matchup, sample_candidate_pool
from exploration.types import CandidateStanding, CandidatePool
from simulator.common.cli import add_agent_mode_arg, add_games_arg, add_seed_arg


def run_intra_tournament(
    pool: CandidatePool,
    archetype: str,
    games: int,
    seed: int,
) -> list[CandidateStanding]:
    """Run a full round-robin inside one archetype's legal candidate pool."""
    candidates = list(pool.candidates_by_archetype[archetype].values())
    stats = {
        candidate.id: {
            "points": 0.0,
            "series_wins": 0,
            "series_losses": 0,
            "series_ties": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "identity_score": candidate.identity_score,
        }
        for candidate in candidates
    }

    for pair_index, (candidate_a, candidate_b) in enumerate(combinations(candidates, 2)):
        result = run_symmetric_matchup(candidate_a, candidate_b, games, seed + pair_index * 17)
        stats[candidate_a.id]["wins"] += int(result["a_wins"])
        stats[candidate_a.id]["losses"] += int(result["b_wins"])
        stats[candidate_a.id]["draws"] += int(result["draws"])
        stats[candidate_b.id]["wins"] += int(result["b_wins"])
        stats[candidate_b.id]["losses"] += int(result["a_wins"])
        stats[candidate_b.id]["draws"] += int(result["draws"])

        if float(result["a_rate"]) > float(result["b_rate"]):
            stats[candidate_a.id]["points"] += 2.0
            stats[candidate_a.id]["series_wins"] += 1
            stats[candidate_b.id]["series_losses"] += 1
        elif float(result["b_rate"]) > float(result["a_rate"]):
            stats[candidate_b.id]["points"] += 2.0
            stats[candidate_b.id]["series_wins"] += 1
            stats[candidate_a.id]["series_losses"] += 1
        else:
            stats[candidate_a.id]["points"] += 1.0
            stats[candidate_b.id]["points"] += 1.0
            stats[candidate_a.id]["series_ties"] += 1
            stats[candidate_b.id]["series_ties"] += 1

    standings: list[CandidateStanding] = []
    for candidate in candidates:
        row = stats[candidate.id]
        decisive = row["wins"] + row["losses"]
        rate = (row["wins"] / decisive * 100.0) if decisive else 50.0
        standings.append(
            CandidateStanding(
                candidate_id=candidate.id,
                archetype=archetype,
                points=float(row["points"]),
                series_wins=int(row["series_wins"]),
                series_losses=int(row["series_losses"]),
                series_ties=int(row["series_ties"]),
                decisive_rate=rate,
                wins=int(row["wins"]),
                losses=int(row["losses"]),
                draws=int(row["draws"]),
                identity_score=float(row["identity_score"]),
            )
        )

    standings.sort(
        key=lambda row: (
            row.points,
            row.series_wins,
            row.decisive_rate,
            row.identity_score,
            row.wins - row.losses,
        ),
        reverse=True,
    )
    return standings


def run_all_tournaments(pool: CandidatePool, games: int, seed: int) -> dict[str, list[CandidateStanding]]:
    """Run one intra-archetype tournament for each archetype in the pool."""
    return {
        archetype: run_intra_tournament(pool, archetype, games, seed + index * 10_000)
        for index, archetype in enumerate(ARCHETYPE_ORDER)
    }


def print_tournament(pool: CandidatePool, standings_by_arch: dict[str, list[CandidateStanding]], top: int) -> None:
    """Render a compact tournament table for each archetype."""
    print(pool.display_name)
    print(f"Grammar: {pool.grammar}")
    for archetype in ARCHETYPE_ORDER:
        print()
        print(archetype)
        for row in standings_by_arch[archetype][:top]:
            candidate = pool.candidates_by_archetype[archetype][row.candidate_id]
            print(
                f"  {row.candidate_id:<28} "
                f"pts={row.points:4.1f}  "
                f"series={row.series_wins}-{row.series_losses}-{row.series_ties}  "
                f"rate={row.decisive_rate:5.1f}%  "
                f"identity={row.identity_score:3.1f}"
            )
            print(f"    {candidate.summary}")


def main() -> None:
    """CLI entrypoint for intra-archetype candidate tournaments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", choices=POOL_IDS, required=True)
    add_agent_mode_arg(parser, default="game-aware-tier-loadout")
    add_games_arg(parser, default=40)
    add_seed_arg(parser)
    parser.add_argument("--top", type=int, default=5, help="candidates to print per archetype")
    parser.add_argument(
        "--sample-per-archetype",
        type=int,
        default=0,
        help="sample this many variants per archetype before the round robin (0 = use all)",
    )
    args = parser.parse_args()

    pool = get_candidate_pool(args.pool, args.agent_mode)
    if args.sample_per_archetype > 0:
        pool = sample_candidate_pool(pool, args.sample_per_archetype, args.seed)
    standings_by_arch = run_all_tournaments(pool, args.games, args.seed)
    print_tournament(pool, standings_by_arch, args.top)


if __name__ == "__main__":
    main()
