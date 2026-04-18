"""
l2_identity.py
--------------
L2 identity harness: strip L2 to bare essentials to test whether
R-P-S archetype identity emerges before we reintroduce dice variance and tier choice.

Scope:
  - Loadout: 6x of ONE custom structured die per archetype. Each die uses
    3 core faces for the archetype and 3 support faces (distinct), so no
    archetype gets six overconcentrated copies of a stock die.
  - GPs: 12 total (3 per archetype), T1 only.
  - House rules are configurable from this module for fast experiments:
    thorns, token-shield, anti-steal HP penalties, anti-hoard HP penalties,
    and an optional Njordr reroll cap.
      AGGRO   -> Surtr's Flame, Fenrir's Bite, Heimdallr's Watch
      CONTROL -> Aegis of Baldr, Eir's Mercy, Frigg's Veil
      ECONOMY -> Mjolnir's Wrath, Freyja's Blessing, Aegis of Baldr
      COMBO   -> Skadi's Volley, Heimdallr's Watch, Fenrir's Bite
  - Agents: reuses the existing archetype agents with tier_order=(0,)
    so the T2/T3 tiers defined in god_powers.json are ignored.

Run:  python3 simulator/l2_identity.py --games 2000
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
from simulator.die_types import DieType
from simulator.game_engine import GameEngine


# ---------------------------------------------------------------------------
# Experiment configuration
# ---------------------------------------------------------------------------

# T1 only - agents try tier index 0 first and nothing else.
_T1_ONLY = (0,)
_FACE_POWER = {
    "FACE_AXE": 1.0,
    "FACE_ARROW": 1.0,
    "FACE_HELMET": 1.0,
    "FACE_SHIELD": 1.0,
    "FACE_HAND": 0.8,
    "FACE_HAND_BORDERED": 1.2,
}


def _make_structured_die(die_id: str, display_name: str, faces: tuple[str, ...]) -> DieType:
    return DieType(
        id=die_id,
        display_name=display_name,
        faces=faces,
        power_budget=sum(_FACE_POWER[f] for f in faces),
    )


_STRUCTURED_DICE: dict[str, DieType] = {
    # 3 core faces + 3 support faces.
    "AGGRO": _make_structured_die(
        "EXP_AGGRO",
        "Aggro Structured Die",
        (
            "FACE_AXE", "FACE_ARROW", "FACE_HELMET",
            "FACE_HELMET", "FACE_HAND", "FACE_HAND_BORDERED",
        ),
    ),
    "CONTROL": _make_structured_die(
        "EXP_CONTROL",
        "Control Structured Die",
        (
            "FACE_HELMET", "FACE_HELMET", "FACE_SHIELD",
            "FACE_AXE", "FACE_ARROW", "FACE_HAND_BORDERED",
        ),
    ),
    "ECONOMY": _make_structured_die(
        "EXP_ECONOMY",
        "Economy Structured Die",
        (
            "FACE_HAND_BORDERED", "FACE_HAND", "FACE_HELMET",
            "FACE_SHIELD", "FACE_SHIELD", "FACE_ARROW",
        ),
    ),
    "COMBO": _make_structured_die(
        "EXP_COMBO",
        "Combo Structured Die",
        (
            "FACE_ARROW", "FACE_HAND_BORDERED", "FACE_HAND",
            "FACE_AXE", "FACE_HELMET", "FACE_SHIELD",
        ),
    ),
}

_ENGINE_KWARGS = {
    "enable_thorns": True,
    "enable_token_shield": False,
    "steal_hp_penalty_threshold": 3,
    "steal_hp_penalty": 1,
    "hoard_hp_penalty_threshold": None,
    "hoard_hp_penalty": 0,
    "njordr_reroll_cap": None,
}
_IDENTITY_BEAT_THRESHOLD = 0.50
_IDENTITY_LOSE_THRESHOLD = 0.50

_OFFENSIVE_GPS = frozenset({
    "GP_MJOLNIRS_WRATH",
    "GP_FENRIRS_BITE",
    "GP_SKADIS_VOLLEY",
    "GP_SURTRS_FLAME",
    "GP_LOKIS_GAMBIT",
    "GP_TYRS_JUDGMENT",
    "GP_HEIMDALLRS_WATCH",
})


def _players(state, player_num: int):
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    return player, opponent


def _first_affordable(
    player,
    god_powers: dict,
    gp_ids: tuple[str, ...],
    tier_order: tuple[int, ...] = _T1_ONLY,
) -> tuple[str, int] | None:
    for gp_id in gp_ids:
        if gp_id not in player.gp_loadout:
            continue
        gp = god_powers.get(gp_id)
        if gp is None:
            continue
        for tier_idx in tier_order:
            if player.tokens >= gp.tiers[tier_idx].cost:
                return (gp_id, tier_idx)
    return None


def _can_afford(player, god_powers: dict, gp_id: str, tier_idx: int = 0) -> bool:
    gp = god_powers.get(gp_id)
    return (
        gp_id in player.gp_loadout
        and gp is not None
        and player.tokens >= gp.tiers[tier_idx].cost
    )


def _predicted_dice_damage(attacker, defender) -> tuple[int, int]:
    axes = attacker.dice_faces.count("FACE_AXE")
    arrows = attacker.dice_faces.count("FACE_ARROW")
    opp_helmets = defender.dice_faces.count("FACE_HELMET")
    opp_shields = defender.dice_faces.count("FACE_SHIELD")
    damage = max(0, axes - opp_helmets) + max(0, arrows - opp_shields)
    blocked = min(axes, opp_helmets) + min(arrows, opp_shields)
    return damage, blocked


def _is_control_loadout(opponent) -> bool:
    return (
        "GP_AEGIS_OF_BALDR" in opponent.gp_loadout
        and "GP_EIRS_MERCY" in opponent.gp_loadout
    ) or "GP_FRIGGS_VEIL" in opponent.gp_loadout


def _is_economy_loadout(opponent) -> bool:
    return (
        "GP_MJOLNIRS_WRATH" in opponent.gp_loadout
        and "GP_FREYAS_BLESSING" in opponent.gp_loadout
    )


def _is_combo_loadout(opponent) -> bool:
    return "GP_SKADIS_VOLLEY" in opponent.gp_loadout


def _aggro_gp_select(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    _, incoming_blocked = _predicted_dice_damage(player, opponent)
    total_attacks = player.dice_faces.count("FACE_AXE") + player.dice_faces.count("FACE_ARROW")

    if opponent.hp <= 4 and _can_afford(player, god_powers, "GP_FENRIRS_BITE"):
        return ("GP_FENRIRS_BITE", 0)
    if opponent.hp <= 3 and _can_afford(player, god_powers, "GP_SURTRS_FLAME"):
        return ("GP_SURTRS_FLAME", 0)

    if (
        _is_control_loadout(opponent)
        and _can_afford(player, god_powers, "GP_HEIMDALLRS_WATCH")
        and total_attacks >= 1
        and (incoming_blocked >= 1 or opponent.tokens >= 2)
    ):
        return ("GP_HEIMDALLRS_WATCH", 0)

    if (
        _is_economy_loadout(opponent)
        and _can_afford(player, god_powers, "GP_FENRIRS_BITE")
        and opponent.tokens >= 4
    ):
        return ("GP_FENRIRS_BITE", 0)

    if (
        _can_afford(player, god_powers, "GP_HEIMDALLRS_WATCH")
        and incoming_blocked >= 2
    ):
        return ("GP_HEIMDALLRS_WATCH", 0)

    return _first_affordable(
        player,
        god_powers,
        ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
    )


def _control_gp_select(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    opponent_damage, _ = _predicted_dice_damage(opponent, player)
    opp_unblocked_arrows = max(
        0,
        opponent.dice_faces.count("FACE_ARROW") - player.dice_faces.count("FACE_SHIELD"),
    )
    opp_has_big_power_turn = any(
        _can_afford(opponent, god_powers, gp_id)
        for gp_id in ("GP_MJOLNIRS_WRATH", "GP_FENRIRS_BITE", "GP_SKADIS_VOLLEY")
    )

    if (
        _is_economy_loadout(opponent)
        and _can_afford(player, god_powers, "GP_FRIGGS_VEIL")
        and opponent.tokens >= 6
    ):
        return ("GP_FRIGGS_VEIL", 0)

    if player.hp <= 8 and _can_afford(player, god_powers, "GP_EIRS_MERCY"):
        return ("GP_EIRS_MERCY", 0)

    if (
        _can_afford(player, god_powers, "GP_AEGIS_OF_BALDR")
        and (opponent_damage >= 2 or opp_unblocked_arrows >= 2 or opp_has_big_power_turn)
    ):
        return ("GP_AEGIS_OF_BALDR", 0)

    if (
        _can_afford(player, god_powers, "GP_FRIGGS_VEIL")
        and opponent.tokens >= 5
        and any(gp_id in opponent.gp_loadout for gp_id in _OFFENSIVE_GPS)
    ):
        return ("GP_FRIGGS_VEIL", 0)

    return _first_affordable(
        player,
        god_powers,
        ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_FRIGGS_VEIL"),
    )


def _economy_gp_select(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    opponent_damage, _ = _predicted_dice_damage(opponent, player)
    opp_unblocked_arrows = max(
        0,
        opponent.dice_faces.count("FACE_ARROW") - player.dice_faces.count("FACE_SHIELD"),
    )
    player_hands = player.dice_faces.count("FACE_HAND") + player.dice_faces.count("FACE_HAND_BORDERED")

    if opponent.hp <= 4 and _can_afford(player, god_powers, "GP_MJOLNIRS_WRATH"):
        return ("GP_MJOLNIRS_WRATH", 0)

    if (
        _is_combo_loadout(opponent)
        and _can_afford(player, god_powers, "GP_AEGIS_OF_BALDR")
        and (opp_unblocked_arrows >= 2 or opponent.tokens >= 4 or opponent_damage >= 2)
    ):
        return ("GP_AEGIS_OF_BALDR", 0)

    if (
        _can_afford(player, god_powers, "GP_AEGIS_OF_BALDR")
        and (opponent_damage >= 3 or player.hp <= 8)
    ):
        return ("GP_AEGIS_OF_BALDR", 0)

    if (
        _is_control_loadout(opponent)
        and _can_afford(player, god_powers, "GP_FREYAS_BLESSING")
        and player_hands >= 1
    ):
        return ("GP_FREYAS_BLESSING", 0)

    if _can_afford(player, god_powers, "GP_MJOLNIRS_WRATH"):
        return ("GP_MJOLNIRS_WRATH", 0)

    if (
        _can_afford(player, god_powers, "GP_FREYAS_BLESSING")
        and player_hands >= 2
    ):
        return ("GP_FREYAS_BLESSING", 0)

    return _first_affordable(
        player,
        god_powers,
        ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_AEGIS_OF_BALDR"),
    )


def _combo_gp_select(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    arrows = player.dice_faces.count("FACE_ARROW")
    unblocked = max(0, arrows - opponent.dice_faces.count("FACE_SHIELD"))
    player_hands = player.dice_faces.count("FACE_HAND") + player.dice_faces.count("FACE_HAND_BORDERED")

    if _is_economy_loadout(opponent):
        if unblocked >= 4 and _can_afford(player, god_powers, "GP_SKADIS_VOLLEY"):
            return ("GP_SKADIS_VOLLEY", 0)
        if (
            _can_afford(player, god_powers, "GP_FENRIRS_BITE")
            and (opponent.tokens >= 7 or opponent.hp <= 6)
            and unblocked >= 1
        ):
            return ("GP_FENRIRS_BITE", 0)
        if (
            _can_afford(player, god_powers, "GP_NJORDS_TIDE")
            and arrows == 0
            and player_hands <= 1
        ):
            return ("GP_NJORDS_TIDE", 0)
        return None

    if unblocked >= 2 and _can_afford(player, god_powers, "GP_SKADIS_VOLLEY"):
        return ("GP_SKADIS_VOLLEY", 0)
    if _can_afford(player, god_powers, "GP_FENRIRS_BITE") and opponent.hp <= 9:
        return ("GP_FENRIRS_BITE", 0)
    if _can_afford(player, god_powers, "GP_NJORDS_TIDE") and arrows <= 1:
        return ("GP_NJORDS_TIDE", 0)
    if arrows > 0 and _can_afford(player, god_powers, "GP_SKADIS_VOLLEY"):
        return ("GP_SKADIS_VOLLEY", 0)
    return None


@dataclass
class Archetype:
    name: str
    agent_cls: type
    agent_kwargs: dict
    gp_loadout: tuple[str, ...]
    die_type: DieType


def _make_archetype(
    name: str,
    agent_cls: type,
    die_key: str,
    gp_loadout: tuple[str, ...],
    **agent_kwargs,
) -> Archetype:
    return Archetype(
        name=name,
        agent_cls=agent_cls,
        agent_kwargs=agent_kwargs,
        gp_loadout=gp_loadout,
        die_type=_STRUCTURED_DICE[die_key],
    )


_ARCHETYPES: dict[str, Archetype] = {
    "AGGRO": _make_archetype(
        "Aggro",
        AggroAgent,
        "AGGRO",
        ("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
        gp_priority=("GP_FENRIRS_BITE", "GP_SURTRS_FLAME", "GP_HEIMDALLRS_WATCH"),
        tier_order=_T1_ONLY,
        gp_select_fn=_aggro_gp_select,
    ),
    "CONTROL": _make_archetype(
        "Control",
        ControlAgent,
        "CONTROL",
        ("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_FRIGGS_VEIL"),
        gp_priority_healthy=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_FRIGGS_VEIL"),
        gp_priority_hurt=("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR", "GP_FRIGGS_VEIL"),
        tier_order=_T1_ONLY,
        gp_select_fn=_control_gp_select,
    ),
    "ECONOMY": _make_archetype(
        "Economy",
        EconomyAgent,
        "ECONOMY",
        ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_AEGIS_OF_BALDR"),
        gp_priority=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_AEGIS_OF_BALDR"),
        tier_order=_T1_ONLY,
        frigg_threshold=999,
        gp_select_fn=_economy_gp_select,
    ),
    "COMBO": _make_archetype(
        "Combo",
        ComboAgent,
        "COMBO",
        ("GP_SKADIS_VOLLEY", "GP_HEIMDALLRS_WATCH", "GP_FENRIRS_BITE"),
        gp_priority=("GP_SKADIS_VOLLEY", "GP_HEIMDALLRS_WATCH", "GP_FENRIRS_BITE"),
        tier_order=_T1_ONLY,
        min_arrows_for_skadi=2,
        gp_select_fn=_combo_gp_select,
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


def run(
    n_games: int = 2_000,
    seed: int = 42,
    archetypes: dict[str, Archetype] | None = None,
    engine_kwargs: dict | None = None,
) -> L2MinimalResults:
    archetypes = archetypes or _ARCHETYPES
    engine_kwargs = {**_ENGINE_KWARGS, **(engine_kwargs or {})}
    results = L2MinimalResults()
    names = list(archetypes.keys())

    t0 = time.perf_counter()
    for p1_name in names:
        for p2_name in names:
            rng = np.random.default_rng(seed)
            p1 = archetypes[p1_name]
            p2 = archetypes[p2_name]

            p1_dice = [p1.die_type] * 6
            p2_dice = [p2.die_type] * 6

            engine = GameEngine(
                p1_dice, p2_dice, rng,
                p1_gp_ids=p1.gp_loadout,
                p2_gp_ids=p2.gp_loadout,
                **engine_kwargs,
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
    """Each archetype must have one favorable and one unfavorable non-mirror matchup."""
    ok = True
    lines: list[str] = []
    for name in names:
        beats = [o for o in names if o != name
                 and results.matchups[(name, o)].p1_decisive_wr > _IDENTITY_BEAT_THRESHOLD]
        loses = [o for o in names if o != name
                 and results.matchups[(name, o)].p1_decisive_wr < _IDENTITY_LOSE_THRESHOLD]
        status = "GREEN ok" if (beats and loses) else "RED X"
        if not (beats and loses):
            ok = False
        lines.append(
            f"  {name:<10} beats={len(beats)} ({','.join(beats) or '-'})  "
            f"loses={len(loses)} ({','.join(loses) or '-'})  {status}"
        )
    return ok, lines


def print_results(
    r: L2MinimalResults,
    archetypes: dict[str, Archetype] | None = None,
    engine_kwargs: dict | None = None,
) -> None:
    archetypes = archetypes or _ARCHETYPES
    engine_kwargs = {**_ENGINE_KWARGS, **(engine_kwargs or {})}
    names = list(archetypes.keys())
    sep = "=" * 72

    print(f"\n{sep}")
    print("  L2 MINIMAL - R-P-S Emergence Experiment")
    print("  Structured die per archetype | 3 GPs | T1 only")
    print(f"  Rules: thorns={engine_kwargs['enable_thorns']}  "
          f"token_shield={engine_kwargs['enable_token_shield']}  "
          f"steal_hp={engine_kwargs['steal_hp_penalty_threshold']}/{engine_kwargs['steal_hp_penalty']}  "
          f"hoard_hp={engine_kwargs['hoard_hp_penalty_threshold']}/{engine_kwargs['hoard_hp_penalty']}  "
          f"njordr_cap={engine_kwargs['njordr_reroll_cap']}")
    for n in names:
        a = archetypes[n]
        print(f"    {a.name:<8} 6x {a.die_type.id:<14} "
              f"GPs={', '.join(g.replace('GP_','') for g in a.gp_loadout)}")
        print(f"              faces={', '.join(f.replace('FACE_','') for f in a.die_type.faces)}")
    print(sep)

    # --- Actual matrix ---
    col_label = "P1 \\ P2"
    header = f"  {col_label:<10}"
    for n in names:
        header += f" {archetypes[n].name:>10}"
    header += f" {'RowAvg':>10}"
    print(header)
    print(f"  {'-'*70}")

    row_avgs: list[float] = []
    for p1 in names:
        row = f"  {archetypes[p1].name:<10}"
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
    print(f"  {col_label:<10}" + "".join(f" {archetypes[n].name:>10}" for n in names))
    total_dev_sq = 0.0
    for p1 in names:
        row = f"  {archetypes[p1].name:<10}"
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
        print(f"  {archetypes[n].name:<10} {wr:>6.1%}  {status}")
    print()

    # --- R-P-S structure ---
    print("  R-P-S structure (each archetype must have 1 favorable and 1 unfavorable edge):")
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
