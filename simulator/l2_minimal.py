"""
l2_minimal.py
-------------
L2 simplified experiment: strip L2 to bare essentials to test whether
R-P-S emerges at all before we reintroduce dice variance and tier choice.

Scope:
  - Loadout: 6x of ONE signature die per archetype (one die per archetype,
    no mixed loadouts). AGGRO=Berserker, CONTROL=Warden, ECONOMY=Miser,
    COMBO=Hunter.
  - GPs: 8 total (2 per archetype), T1 only.
  - House rules: thorns ON (every 2 blocks -> 1 dmg back; provably helpful
    in past experiments), token-shield OFF (no passive -1 dmg per 4 tokens).
      AGGRO   -> Surtr's Flame, Fenrir's Bite
      CONTROL -> Aegis of Baldr, Eir's Mercy
      ECONOMY -> Mjolnir's Wrath, Freyja's Blessing
      COMBO   -> Skadi's Volley, Njordr's Tide
  - Agents: reuses the existing archetype agents with tier_order=(0,)
    so the T2/T3 tiers defined in god_powers.json are ignored.

Run:  python3 simulator/l2_minimal.py --games 2000
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from dataclasses import dataclass, field

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from simulator.agents.aggro_agent import AggroAgent
from simulator.agents.combo_agent import ComboAgent
from simulator.agents.control_agent import ControlAgent
from simulator.agents.economy_agent import EconomyAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine


# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------

# T1 only - agents try tier index 0 first and nothing else.
_T1_ONLY = (0,)


@dataclass
class Archetype:
    name: str
    agent_cls: type
    agent_kwargs: dict
    gp_loadout: tuple[str, ...]
    die_id: str   # all 6 loadout dice are this single type


_ARCHETYPES: dict[str, Archetype] = {
    "AGGRO": Archetype(
        name="Aggro",
        agent_cls=AggroAgent,
        agent_kwargs={
            "gp_priority": ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE"),
            "tier_order": _T1_ONLY,
        },
        gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE"),
        die_id="DIE_BERSERKER",
    ),
    "CONTROL": Archetype(
        name="Control",
        agent_cls=ControlAgent,
        agent_kwargs={
            "gp_priority_healthy": ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY"),
            "gp_priority_hurt": ("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR"),
            "tier_order": _T1_ONLY,
        },
        gp_loadout=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY"),
        die_id="DIE_WARDEN",
    ),
    "ECONOMY": Archetype(
        name="Economy",
        agent_cls=EconomyAgent,
        agent_kwargs={
            "gp_priority": ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING"),
            "tier_order": _T1_ONLY,
            "frigg_threshold": 999,
        },
        gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING"),
        die_id="DIE_MISER",
    ),
    "COMBO": Archetype(
        name="Combo",
        agent_cls=ComboAgent,
        agent_kwargs={
            "gp_priority": ("GP_SKADIS_VOLLEY", "GP_NJORDS_TIDE"),
            "tier_order": _T1_ONLY,
        },
        gp_loadout=("GP_SKADIS_VOLLEY", "GP_NJORDS_TIDE"),
        die_id="DIE_HUNTER",
    ),
}

# CLAUDE.md §9 target win-rate matrix. Rows = P1 archetype, cols = P2 archetype.
_TARGETS: dict[tuple[str, str], float] = {
    ("AGGRO",   "AGGRO"):   0.50, ("AGGRO",   "CONTROL"): 0.35,
    ("AGGRO",   "ECONOMY"): 0.62, ("AGGRO",   "COMBO"):   0.58,
    ("CONTROL", "AGGRO"):   0.65, ("CONTROL", "CONTROL"): 0.50,
    ("CONTROL", "ECONOMY"): 0.38, ("CONTROL", "COMBO"):   0.45,
    ("ECONOMY", "AGGRO"):   0.38, ("ECONOMY", "CONTROL"): 0.62,
    ("ECONOMY", "ECONOMY"): 0.50, ("ECONOMY", "COMBO"):   0.55,
    ("COMBO",   "AGGRO"):   0.42, ("COMBO",   "CONTROL"): 0.55,
    ("COMBO",   "ECONOMY"): 0.45, ("COMBO",   "COMBO"):   0.50,
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class MatchupResult:
    p1: str
    p2: str
    n_games: int
    p1_wins: int = 0
    p2_wins: int = 0
    draws: int = 0
    rounds: list[int] = field(default_factory=list)

    @property
    def decisive(self) -> int:
        return self.p1_wins + self.p2_wins

    @property
    def p1_decisive_wr(self) -> float:
        return self.p1_wins / self.decisive if self.decisive else 0.5


@dataclass
class L2MinimalResults:
    matchups: dict[tuple[str, str], MatchupResult] = field(default_factory=dict)
    elapsed_sec: float = 0.0


def run(n_games: int = 2_000, seed: int = 42) -> L2MinimalResults:
    die_types = load_die_types()

    results = L2MinimalResults()
    names = list(_ARCHETYPES.keys())

    t0 = time.perf_counter()
    for p1_name in names:
        for p2_name in names:
            rng = np.random.default_rng(seed)
            p1 = _ARCHETYPES[p1_name]
            p2 = _ARCHETYPES[p2_name]

            p1_dice = [die_types[p1.die_id]] * 6
            p2_dice = [die_types[p2.die_id]] * 6

            engine = GameEngine(
                p1_dice, p2_dice, rng,
                p1_gp_ids=p1.gp_loadout,
                p2_gp_ids=p2.gp_loadout,
                enable_thorns=True,
                enable_token_shield=False,
            )
            p1_agent = p1.agent_cls(rng=rng, **p1.agent_kwargs)
            p2_agent = p2.agent_cls(rng=rng, **p2.agent_kwargs)

            m = MatchupResult(p1=p1_name, p2=p2_name, n_games=n_games)
            for _ in range(n_games):
                final_state, _ = engine.run_game(p1_agent, p2_agent)
                w = final_state.winner
                if w == 1:
                    m.p1_wins += 1
                elif w == 2:
                    m.p2_wins += 1
                else:
                    m.draws += 1
                m.rounds.append(final_state.round_num)

            results.matchups[(p1_name, p2_name)] = m

    results.elapsed_sec = time.perf_counter() - t0
    return results


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _cell_marker(actual_pct: float, target_pct: float) -> str:
    diff = abs(actual_pct - target_pct)
    if diff <= 7:
        return " "
    if diff <= 15:
        return "!"
    return "X"


def _rps_check(results: L2MinimalResults, names: list[str]) -> tuple[bool, list[str]]:
    """Each archetype must beat at least one and lose to at least one (>55% / <45%)."""
    ok = True
    lines: list[str] = []
    for name in names:
        beats = [o for o in names if o != name
                 and results.matchups[(name, o)].p1_decisive_wr > 0.55]
        loses = [o for o in names if o != name
                 and results.matchups[(name, o)].p1_decisive_wr < 0.45]
        status = "GREEN ok" if (beats and loses) else "RED X"
        if not (beats and loses):
            ok = False
        lines.append(
            f"  {name:<10} beats={len(beats)} ({','.join(beats) or '-'})  "
            f"loses={len(loses)} ({','.join(loses) or '-'})  {status}"
        )
    return ok, lines


def print_results(r: L2MinimalResults) -> None:
    names = list(_ARCHETYPES.keys())
    sep = "=" * 72

    print(f"\n{sep}")
    print("  L2 MINIMAL - R-P-S Emergence Experiment")
    print("  Signature die per archetype | 2 GPs | T1 only | thorns ON, token-shield OFF")
    for n in names:
        a = _ARCHETYPES[n]
        print(f"    {a.name:<8} 6x {a.die_id:<14} "
              f"GPs={', '.join(g.replace('GP_','') for g in a.gp_loadout)}")
    print(sep)

    # --- Actual matrix ---
    col_label = "P1 \\ P2"
    header = f"  {col_label:<10}"
    for n in names:
        header += f" {_ARCHETYPES[n].name:>10}"
    header += f" {'RowAvg':>10}"
    print(header)
    print(f"  {'-'*70}")

    row_avgs: list[float] = []
    for p1 in names:
        row = f"  {_ARCHETYPES[p1].name:<10}"
        wrs = []
        for p2 in names:
            m = r.matchups[(p1, p2)]
            wr = m.p1_decisive_wr
            wrs.append(wr)
            marker = _cell_marker(wr * 100, _TARGETS[(p1, p2)] * 100)
            row += f" {wr:>9.1%}{marker}"
        avg = float(np.mean(wrs))
        row_avgs.append(avg)
        row += f" {avg:>9.1%}"
        print(row)

    print()

    # --- Deviation from targets ---
    print("  Deviation from CLAUDE.md target matrix (actual - target, in pp):")
    print(f"  {'-'*70}")
    print(f"  {col_label:<10}" + "".join(f" {_ARCHETYPES[n].name:>10}" for n in names))
    total_dev_sq = 0.0
    for p1 in names:
        row = f"  {_ARCHETYPES[p1].name:<10}"
        for p2 in names:
            actual = r.matchups[(p1, p2)].p1_decisive_wr * 100
            target = _TARGETS[(p1, p2)] * 100
            d = actual - target
            total_dev_sq += d * d
            sign = "+" if d >= 0 else ""
            row += f" {sign}{d:>7.0f}pp"
        print(row)
    print(f"\n  RMS deviation: {(total_dev_sq / 16) ** 0.5:.1f}pp")
    print()

    # --- Mirror matchup symmetry ---
    print("  Mirror matchups (should be 48-52%; >4pp off = suspect):")
    for n in names:
        wr = r.matchups[(n, n)].p1_decisive_wr
        status = "GREEN ok" if abs(wr - 0.5) <= 0.04 else "YELLOW !"
        print(f"  {_ARCHETYPES[n].name:<10} {wr:>6.1%}  {status}")
    print()

    # --- R-P-S structure ---
    print("  R-P-S structure (each archetype must beat 1+ and lose to 1+):")
    ok, lines = _rps_check(r, names)
    for ln in lines:
        print(ln)
    verdict = "GREEN - R-P-S emerged" if ok else "RED - R-P-S did not emerge"
    print(f"\n  Verdict: {verdict}")
    print()

    # --- Length + draw summary ---
    all_rounds: list[int] = []
    total_games = 0
    total_draws = 0
    for m in r.matchups.values():
        all_rounds.extend(m.rounds)
        total_games += m.n_games
        total_draws += m.draws
    avg_rounds = float(np.mean(all_rounds))
    draw_rate = total_draws / total_games if total_games else 0.0
    print(f"  Avg match length : {avg_rounds:.1f} rounds  (target 5-8)")
    print(f"  Draw rate        : {draw_rate:.1%}           (target <20%)")
    print(f"  Elapsed          : {r.elapsed_sec:.1f}s "
          f"({total_games / r.elapsed_sec:,.0f} games/sec)")
    print(f"{sep}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(description="L2 minimal R-P-S experiment.")
    p.add_argument("--games", type=int, default=2_000,
                   help="Games per matchup (default 2,000 -> 32k total).")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    n_total = args.games * 16
    print(f"Running L2 minimal: {args.games:,} games x 16 matchups = {n_total:,} total...")
    results = run(n_games=args.games, seed=args.seed)
    print_results(results)


if __name__ == "__main__":
    main()
