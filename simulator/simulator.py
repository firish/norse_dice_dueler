"""
simulator.py
------------
L0 simulation runner.

Usage:
    python3 simulator/simulator.py                    # 10,000 games, DIE_WARRIOR
    python3 simulator/simulator.py --games 50000
    python3 simulator/simulator.py --die DIE_WARRIOR --games 5000 --seed 0
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from dataclasses import dataclass, field

import numpy as np

# Allow running as `python3 simulator/simulator.py` from the repo root.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from simulator.agents.aggro_agent import AggroAgent
from simulator.agents.combo_agent import ComboAgent
from simulator.agents.control_agent import ControlAgent
from simulator.agents.economy_agent import EconomyAgent
from simulator.agents.greedy_agent import GreedyAgent
from simulator.agents.random_agent import RandomAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine


# ---------------------------------------------------------------------------
# Results container
# ---------------------------------------------------------------------------

@dataclass
class SimulationResults:
    n_games: int
    die_id: str
    p1_wins: int = 0
    p2_wins: int = 0
    draws: int = 0
    rounds_per_game: list[int] = field(default_factory=list)
    winner_hp_per_game: list[int] = field(default_factory=list)
    elapsed_sec: float = 0.0

    # -- Derived properties --

    @property
    def p1_win_rate(self) -> float:
        return self.p1_wins / self.n_games

    @property
    def p2_win_rate(self) -> float:
        return self.p2_wins / self.n_games

    @property
    def draw_rate(self) -> float:
        return self.draws / self.n_games

    @property
    def decisive_games(self) -> int:
        return self.p1_wins + self.p2_wins

    @property
    def p1_decisive_win_rate(self) -> float:
        """P1 wins / (P1 wins + P2 wins). Excludes draws. The L0 balance metric."""
        d = self.decisive_games
        return self.p1_wins / d if d > 0 else 0.5

    @property
    def avg_rounds(self) -> float:
        return float(np.mean(self.rounds_per_game))

    @property
    def median_rounds(self) -> float:
        return float(np.median(self.rounds_per_game))

    @property
    def avg_winner_hp(self) -> float:
        decisive = [hp for hp in self.winner_hp_per_game if hp > 0]
        return float(np.mean(decisive)) if decisive else 0.0

    @property
    def close_match_rate(self) -> float:
        """Fraction of decisive games where winner had ≤4 HP remaining."""
        decisive = [hp for hp in self.winner_hp_per_game if hp > 0]
        if not decisive:
            return 0.0
        return sum(1 for hp in decisive if hp <= 4) / len(decisive)

    @property
    def games_per_sec(self) -> float:
        return self.n_games / self.elapsed_sec if self.elapsed_sec > 0 else 0.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_simulation(
    n_games: int = 10_000,
    seed: int = 5005,
    die_id: str = "DIE_WARRIOR",
) -> SimulationResults:
    rng = np.random.default_rng(seed)
    die_types = load_die_types()

    if die_id not in die_types:
        raise ValueError(f"Unknown die ID '{die_id}'. Available: {list(die_types)}")

    die = die_types[die_id]
    loadout = [die] * 6

    engine   = GameEngine(loadout, loadout, rng)
    p1_agent = RandomAgent(rng)
    p2_agent = RandomAgent(rng)

    results = SimulationResults(n_games=n_games, die_id=die_id)

    t0 = time.perf_counter()
    for _ in range(n_games):
        final_state, _ = engine.run_game(p1_agent, p2_agent)
        winner = final_state.winner
        rounds = final_state.round_num

        if winner == 1:
            results.p1_wins += 1
            results.winner_hp_per_game.append(final_state.p1.hp)
        elif winner == 2:
            results.p2_wins += 1
            results.winner_hp_per_game.append(final_state.p2.hp)
        else:
            results.draws += 1
            results.winner_hp_per_game.append(0)

        results.rounds_per_game.append(rounds)

    results.elapsed_sec = time.perf_counter() - t0
    return results


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def _status(value: float, green_lo: float, green_hi: float,
            yellow_lo: float, yellow_hi: float) -> str:
    if green_lo <= value <= green_hi:
        return "GREEN  ✓"
    if yellow_lo <= value <= yellow_hi:
        return "YELLOW !"
    return "RED    ✗"


def print_results(r: SimulationResults) -> None:
    n = r.n_games
    p_decisive = r.p1_decisive_win_rate
    ci = 1.96 * (p_decisive * (1 - p_decisive) / r.decisive_games) ** 0.5

    sep = "─" * 58

    print(f"\n{'═'*58}")
    print(f"  Fjöld - L0 Simulation Results")
    print(f"{'═'*58}")
    print(f"  Games  : {n:>10,}")
    print(f"  Die    : {r.die_id} × 6 per player")
    print(f"  Seed   : fixed (reproducible)")
    print()

    # --- Outcomes ---
    print(f"  {'Outcome':<26} {'Count':>8}   {'Rate':>7}")
    print(f"  {sep}")
    print(f"  {'P1 Win':<26} {r.p1_wins:>8,}   {r.p1_win_rate:>6.1%}")
    print(f"  {'P2 Win':<26} {r.p2_wins:>8,}   {r.p2_win_rate:>6.1%}")
    print(f"  {'Draw (simultaneous death)':<26} {r.draws:>8,}   {r.draw_rate:>6.1%}")
    print(f"  {'P1 Decisive Win Rate':<26} {'':>8}   {p_decisive:>6.1%}  ← L0 metric")
    print(f"    (draws excluded; 95% CI: [{p_decisive-ci:.1%}, {p_decisive+ci:.1%}])")
    print()

    # --- Match length ---
    rounds = r.rounds_per_game
    print(f"  {'Match Length':<26} {'Value':>10}")
    print(f"  {sep}")
    print(f"  {'Avg Rounds':<26} {r.avg_rounds:>10.1f}")
    print(f"  {'Median Rounds':<26} {r.median_rounds:>10.1f}")
    print(f"  {'Min Rounds':<26} {min(rounds):>10}")
    print(f"  {'Max Rounds':<26} {max(rounds):>10}")
    print(f"  {'≤ 8 Rounds':<26} {sum(1 for x in rounds if x <= 8)/n:>10.1%}")
    print()

    # --- HP at end ---
    print(f"  {'HP at Game End':<26} {'Value':>10}")
    print(f"  {sep}")
    print(f"  {'Avg Winner HP':<26} {r.avg_winner_hp:>10.1f}")
    print(f"  {'Close games (winner ≤4 HP)':<26} {r.close_match_rate:>10.1%}")
    print()

    # --- L0 validation ---
    # L0 metric: decisive P1 win rate 48-52% (first-mover parity check).
    # Match length target (5-8 rds) applies to the FULL game (L2+), not L0.
    # Draws at L0 are expected: symmetric dice + no GP -> parallel HP decay.
    print(f"  {'L0 Validation':<30} {'Value':>8}  {'Target':>10}  Status")
    print(f"  {sep}")

    wr_status = _status(p_decisive, 0.48, 0.52, 0.46, 0.54)
    print(f"  {'Decisive P1 Win Rate':<30} {p_decisive:>7.1%}   {'48–52%':>10}  {wr_status}")

    ml_status = _status(r.avg_rounds, 5, 8, 4, 10)
    print(f"  {'Avg Match Length':<30} {r.avg_rounds:>7.1f}   {'5–8 rds':>10}  {ml_status}")
    print(f"    ^ L0 note: no GP means less damage/round; target applies at L2+")

    cm_status = _status(r.close_match_rate, 0.40, 1.0, 0.30, 1.0)
    print(f"  {'Close Matches (winner ≤4 HP)':<30} {r.close_match_rate:>7.1%}   {'≥ 40%':>10}  {cm_status}")

    draw_sym = abs(r.p1_wins - r.p2_wins) / n
    ds_status = "GREEN  ✓" if draw_sym < 0.02 else "YELLOW !"
    print(f"  {'Draw Symmetry (|P1-P2| wins)':<30} {draw_sym:>7.1%}   {'< 2%':>10}  {ds_status}")
    print(f"    ^ Draws are symmetric: neither player has an inherent advantage")
    print()

    print(f"  Elapsed : {r.elapsed_sec:.1f}s  ({r.games_per_sec:,.0f} games/sec)")
    print(f"{'═'*58}\n")


# ---------------------------------------------------------------------------
# L1 runner
# ---------------------------------------------------------------------------

# Greedy agent's GP loadout for L1 validation.
# 3 offensive GPs; Fenrir deferred to L2.
_L1_GREEDY_GP_LOADOUT = (
    "GP_MJOLNIRS_WRATH",
    "GP_SURTRS_FLAME",
    "GP_LOKIS_GAMBIT",
)


def run_l1_simulation(
    n_games: int = 10_000,
    seed: int = 5005,
    die_id: str = "DIE_WARRIOR",
) -> SimulationResults:
    """
    L1: GreedyAgent (offensive GP loadout) vs RandomAgent (no GPs).
    Validation target: Greedy (P1) wins 60-70% of decisive games.
    """
    rng = np.random.default_rng(seed)
    die_types = load_die_types()

    if die_id not in die_types:
        raise ValueError(f"Unknown die ID '{die_id}'. Available: {list(die_types)}")

    die = die_types[die_id]
    loadout = [die] * 6

    engine = GameEngine(
        loadout, loadout, rng,
        p1_gp_ids=_L1_GREEDY_GP_LOADOUT,
        p2_gp_ids=(),
    )
    p1_agent = GreedyAgent(rng)
    p2_agent = RandomAgent(rng)

    results = SimulationResults(n_games=n_games, die_id=die_id)

    t0 = time.perf_counter()
    for _ in range(n_games):
        final_state, _ = engine.run_game(p1_agent, p2_agent)
        winner = final_state.winner
        rounds = final_state.round_num

        if winner == 1:
            results.p1_wins += 1
            results.winner_hp_per_game.append(final_state.p1.hp)
        elif winner == 2:
            results.p2_wins += 1
            results.winner_hp_per_game.append(final_state.p2.hp)
        else:
            results.draws += 1
            results.winner_hp_per_game.append(0)

        results.rounds_per_game.append(rounds)

    results.elapsed_sec = time.perf_counter() - t0
    return results


def print_l1_results(r: SimulationResults) -> None:
    n = r.n_games
    p_decisive = r.p1_decisive_win_rate
    ci = 1.96 * (p_decisive * (1 - p_decisive) / max(r.decisive_games, 1)) ** 0.5

    sep = "-" * 58

    print(f"\n{'='*58}")
    print(f"  Fjöld - L1 Simulation Results")
    print(f"  P1: GreedyAgent (offensive GPs)  vs  P2: RandomAgent")
    print(f"{'='*58}")
    print(f"  Games  : {n:>10,}")
    print(f"  Die    : {r.die_id} x 6 per player")
    print()

    print(f"  {'Outcome':<26} {'Count':>8}   {'Rate':>7}")
    print(f"  {sep}")
    print(f"  {'P1 Win (Greedy)':<26} {r.p1_wins:>8,}   {r.p1_win_rate:>6.1%}")
    print(f"  {'P2 Win (Random)':<26} {r.p2_wins:>8,}   {r.p2_win_rate:>6.1%}")
    print(f"  {'Draw':<26} {r.draws:>8,}   {r.draw_rate:>6.1%}")
    print(f"  {'Greedy Decisive Win Rate':<26} {'':>8}   {p_decisive:>6.1%}  <- L1 metric")
    print(f"    (draws excluded; 95% CI: [{p_decisive-ci:.1%}, {p_decisive+ci:.1%}])")
    print()

    rounds = r.rounds_per_game
    print(f"  {'Match Length':<26} {'Value':>10}")
    print(f"  {sep}")
    print(f"  {'Avg Rounds':<26} {r.avg_rounds:>10.1f}")
    print(f"  {'Min / Max':<26} {min(rounds):>5} / {max(rounds):<5}")
    print()

    print(f"  {'L1 Validation':<30} {'Value':>8}  {'Target':>10}  Status")
    print(f"  {sep}")

    wr_status = _status(p_decisive, 0.60, 0.70, 0.55, 0.75)
    print(f"  {'Greedy Decisive Win Rate':<30} {p_decisive:>7.1%}   {'60-70%':>10}  {wr_status}")

    ml_status = _status(r.avg_rounds, 5, 8, 4, 10)
    print(f"  {'Avg Match Length':<30} {r.avg_rounds:>7.1f}   {'5-8 rds':>10}  {ml_status}")

    cm_status = _status(r.close_match_rate, 0.40, 1.0, 0.30, 1.0)
    print(f"  {'Close Matches (winner <=4 HP)':<30} {r.close_match_rate:>7.1%}   {'>=40%':>10}  {cm_status}")
    print()

    print(f"  Elapsed : {r.elapsed_sec:.1f}s  ({r.games_per_sec:,.0f} games/sec)")
    print(f"{'='*58}\n")


# ---------------------------------------------------------------------------
# L2 runner - 4x4 archetype matrix
# ---------------------------------------------------------------------------

@dataclass
class ArchetypeConfig:
    name: str
    agent_cls: type
    dice_loadout: list[str]   # die IDs, length 6
    gp_loadout: tuple[str, ...]

_ARCHETYPES: dict[str, ArchetypeConfig] = {}

def _build_archetypes() -> dict[str, ArchetypeConfig]:
    if _ARCHETYPES:
        return _ARCHETYPES
    configs = {
        "AGGRO": ArchetypeConfig(
            name="Aggro",
            agent_cls=AggroAgent,
            dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_GAMBLER"] * 2,
            gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
        ),
        "CONTROL": ArchetypeConfig(
            name="Control",
            agent_cls=ControlAgent,
            dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"] * 1,
            gp_loadout=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
        ),
        "ECONOMY": ArchetypeConfig(
            name="Economy",
            agent_cls=EconomyAgent,
            dice_loadout=["DIE_MISER"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_WARDEN"] * 1,
            gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
        ),
        "COMBO": ArchetypeConfig(
            name="Combo",
            agent_cls=ComboAgent,
            dice_loadout=["DIE_HUNTER"] * 4 + ["DIE_GAMBLER"] * 2,
            gp_loadout=("GP_SKADIS_VOLLEY", "GP_NJORDS_TIDE", "GP_ODINS_INSIGHT"),
        ),
    }
    _ARCHETYPES.update(configs)
    return configs


@dataclass
class L2MatchupResult:
    p1_arch: str
    p2_arch: str
    n_games: int
    p1_wins: int = 0
    p2_wins: int = 0
    draws: int = 0
    rounds_per_game: list[int] = field(default_factory=list)

    @property
    def decisive_games(self) -> int:
        return self.p1_wins + self.p2_wins

    @property
    def p1_decisive_win_rate(self) -> float:
        d = self.decisive_games
        return self.p1_wins / d if d > 0 else 0.5


@dataclass
class L2Results:
    matchups: dict[tuple[str, str], L2MatchupResult] = field(default_factory=dict)
    elapsed_sec: float = 0.0


def run_l2_simulation(
    n_games: int = 5_000,
    seed: int = 5005,
) -> L2Results:
    die_types = load_die_types()
    archetypes = _build_archetypes()
    arch_names = list(archetypes.keys())
    results = L2Results()

    t0 = time.perf_counter()
    for p1_name in arch_names:
        for p2_name in arch_names:
            rng = np.random.default_rng(seed)
            p1_cfg = archetypes[p1_name]
            p2_cfg = archetypes[p2_name]

            p1_dice = [die_types[d] for d in p1_cfg.dice_loadout]
            p2_dice = [die_types[d] for d in p2_cfg.dice_loadout]

            engine = GameEngine(
                p1_dice, p2_dice, rng,
                p1_gp_ids=p1_cfg.gp_loadout,
                p2_gp_ids=p2_cfg.gp_loadout,
            )
            p1_agent = p1_cfg.agent_cls(rng)
            p2_agent = p2_cfg.agent_cls(rng)

            matchup = L2MatchupResult(p1_arch=p1_name, p2_arch=p2_name, n_games=n_games)
            for _ in range(n_games):
                final_state, _ = engine.run_game(p1_agent, p2_agent)
                winner = final_state.winner
                if winner == 1:
                    matchup.p1_wins += 1
                elif winner == 2:
                    matchup.p2_wins += 1
                else:
                    matchup.draws += 1
                matchup.rounds_per_game.append(final_state.round_num)

            results.matchups[(p1_name, p2_name)] = matchup

    results.elapsed_sec = time.perf_counter() - t0
    return results


def print_l2_results(r: L2Results) -> None:
    archetypes = _build_archetypes()
    arch_names = list(archetypes.keys())
    sep = "=" * 70

    print(f"\n{sep}")
    print("  Fjold - L2 Simulation Results")
    print("  4x4 Archetype Win-Rate Matrix (P1 decisive win rate)")
    print(sep)

    # Header row
    col_label = "P1 \\ P2"
    header = f"  {col_label:<12}"
    for name in arch_names:
        header += f" {archetypes[name].name:>10}"
    header += f" {'Avg':>10}"
    print(header)
    print(f"  {'-'*64}")

    # Target matrix from CLAUDE.md
    targets = {
        ("AGGRO", "AGGRO"): 50, ("AGGRO", "CONTROL"): 35, ("AGGRO", "ECONOMY"): 62, ("AGGRO", "COMBO"): 58,
        ("CONTROL", "AGGRO"): 65, ("CONTROL", "CONTROL"): 50, ("CONTROL", "ECONOMY"): 38, ("CONTROL", "COMBO"): 45,
        ("ECONOMY", "AGGRO"): 38, ("ECONOMY", "CONTROL"): 62, ("ECONOMY", "ECONOMY"): 50, ("ECONOMY", "COMBO"): 55,
        ("COMBO", "AGGRO"): 42, ("COMBO", "CONTROL"): 55, ("COMBO", "ECONOMY"): 45, ("COMBO", "COMBO"): 50,
    }

    overall_rates = []

    for p1_name in arch_names:
        row = f"  {archetypes[p1_name].name:<12}"
        row_rates = []
        for p2_name in arch_names:
            m = r.matchups[(p1_name, p2_name)]
            wr = m.p1_decisive_win_rate
            row_rates.append(wr)
            target = targets.get((p1_name, p2_name), 50)
            diff = abs(wr * 100 - target)
            if diff <= 7:
                marker = " "
            elif diff <= 15:
                marker = "!"
            else:
                marker = "X"
            row += f" {wr:>9.1%}{marker}"
        avg_wr = np.mean(row_rates)
        overall_rates.append(avg_wr)
        status = _status(avg_wr, 0.45, 0.55, 0.40, 0.60)
        row += f" {avg_wr:>9.1%}  {status}"
        print(row)

    print()

    # Match length summary
    all_rounds = []
    for m in r.matchups.values():
        all_rounds.extend(m.rounds_per_game)
    avg_rounds = float(np.mean(all_rounds))
    ml_status = _status(avg_rounds, 5, 8, 4, 10)

    # Draw rate
    total_games = sum(m.n_games for m in r.matchups.values())
    total_draws = sum(m.draws for m in r.matchups.values())
    draw_rate = total_draws / total_games if total_games > 0 else 0

    print(f"  {'L2 Validation':<30} {'Value':>8}  {'Target':>10}  Status")
    print(f"  {'-'*64}")

    print(f"  {'Avg Match Length':<30} {avg_rounds:>7.1f}   {'5-8 rds':>10}  {ml_status}")
    print(f"  {'Draw Rate (all matchups)':<30} {draw_rate:>7.1%}   {'< 20%':>10}  {'GREEN  ok' if draw_rate < 0.20 else 'YELLOW !'}")

    # Mirror symmetry check
    mirror_ok = True
    for p1_name in arch_names:
        m = r.matchups[(p1_name, p1_name)]
        wr = m.p1_decisive_win_rate
        if abs(wr - 0.5) > 0.04:
            mirror_ok = False
            print(f"  {'Mirror: ' + archetypes[p1_name].name:<30} {wr:>7.1%}   {'48-52%':>10}  RED    X")
    if mirror_ok:
        print(f"  {'Mirror Matchups':<30} {'':>7}    {'48-52%':>10}  GREEN  ok")

    # R-P-S check: each archetype should beat at least one and lose to at least one
    rps_ok = True
    for name in arch_names:
        beats = sum(1 for opp in arch_names if opp != name and r.matchups[(name, opp)].p1_decisive_win_rate > 0.55)
        loses = sum(1 for opp in arch_names if opp != name and r.matchups[(name, opp)].p1_decisive_win_rate < 0.45)
        if beats == 0 or loses == 0:
            rps_ok = False
            print(f"  {'R-P-S: ' + archetypes[name].name:<30} beats={beats} loses={loses}  {'beat 1+, lose 1+':>10}  RED    X")
    if rps_ok:
        print(f"  {'R-P-S Structure':<30} {'':>7}    {'each B+L':>10}  GREEN  ok")

    print()

    # Target comparison
    print("  Target Matrix Comparison (actual vs target):")
    print(f"  {'-'*64}")
    header2 = f"  {col_label:<12}"
    for name in arch_names:
        header2 += f" {archetypes[name].name:>10}"
    print(header2)
    print(f"  {'-'*64}")
    for p1_name in arch_names:
        row = f"  {archetypes[p1_name].name:<12}"
        for p2_name in arch_names:
            m = r.matchups[(p1_name, p2_name)]
            actual = m.p1_decisive_win_rate * 100
            target = targets.get((p1_name, p2_name), 50)
            delta = actual - target
            sign = "+" if delta >= 0 else ""
            row += f" {sign}{delta:>7.0f}pp"
        print(row)

    print()
    print(f"  Elapsed : {r.elapsed_sec:.1f}s")
    print(f"  Games   : {total_games:,} ({total_games / r.elapsed_sec:,.0f} games/sec)")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Fjöld balance simulations."
    )
    parser.add_argument(
        "--level", type=int, default=0, choices=[0, 1, 2],
        help="Simulation layer: 0=raw dice, 1=Greedy vs Random, 2=4x4 archetype matrix (default: 0).",
    )
    parser.add_argument(
        "--games", type=int, default=10_000,
        help="Number of games to simulate (default: 10,000).",
    )
    parser.add_argument(
        "--die", default="DIE_WARRIOR",
        help="Die ID for both players' loadouts (default: DIE_WARRIOR).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="RNG seed for reproducibility (default: 42).",
    )
    args = parser.parse_args()

    if args.level == 2:
        n_per_matchup = args.games
        print(f"Running L2: {n_per_matchup:,} games x 16 matchups = {n_per_matchup * 16:,} total...")
        results = run_l2_simulation(n_games=n_per_matchup, seed=args.seed)
        print_l2_results(results)
    elif args.level == 1:
        print(f"Running {args.games:,} games (L1)...")
        results = run_l1_simulation(n_games=args.games, seed=args.seed, die_id=args.die)
        print_l1_results(results)
    else:
        print(f"Running {args.games:,} games (L0)...")
        results = run_simulation(n_games=args.games, seed=args.seed, die_id=args.die)
        print_results(results)


if __name__ == "__main__":
    main()
