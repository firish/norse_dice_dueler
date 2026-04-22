"""Head-to-head diagnostics for rule-based vs game-aware agents.

The balance matrix tells us how the meta shifts when we swap agent families.
This harness answers the smaller question we need before retuning values:

    Does a game-aware pilot beat the older rule-based pilot on the same
    archetype/loadout, and are there obvious decision mistakes?

Run:
    python3 -m simulator.agent_diagnostics --layer l3 --games 500
    python3 -m simulator.agent_diagnostics --layer l2 --games 500 --trace-games 1
    python3 -m simulator.agent_diagnostics --layer l3 --p1 CONTROL --p2 ECONOMY --p1-mode game-aware --p2-mode game-aware --games 500 --trace-games 1
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from agents.game_aware.evaluator import affordable_choices
from agents.game_aware.state_features import (
    estimate_opponent_gp_damage,
    player_with_available_tokens,
    view_for,
)
from game_mechanics.die_types import load_die_types
from game_mechanics.game_engine import GameEngine
from game_mechanics.game_state import GameEvent, GamePhase, GameState
from game_mechanics.god_powers import GodPower, load_god_powers


@dataclass(frozen=True)
class AgentSide:
    """One side of an A/B diagnostic duel."""

    family: str
    archetype_name: str
    dice_ids: tuple[str, ...]
    gp_ids: tuple[str, ...]
    agent_cls: type


@dataclass
class DecisionStats:
    """Aggregated decisions and warnings for one agent family."""

    games: int = 0
    wins: int = 0
    losses: int = 0
    draws: int = 0
    rounds: int = 0
    gp_decisions: int = 0
    gp_passes: int = 0
    gp_choices: Counter[str] = field(default_factory=Counter)
    warnings: Counter[str] = field(default_factory=Counter)
    keep_decisions: int = 0
    kept_faces: Counter[str] = field(default_factory=Counter)

    def merge(self, other: "DecisionStats") -> None:
        """Merge one game's stats into this aggregate."""
        self.games += other.games
        self.wins += other.wins
        self.losses += other.losses
        self.draws += other.draws
        self.rounds += other.rounds
        self.gp_decisions += other.gp_decisions
        self.gp_passes += other.gp_passes
        self.gp_choices.update(other.gp_choices)
        self.warnings.update(other.warnings)
        self.keep_decisions += other.keep_decisions
        self.kept_faces.update(other.kept_faces)

    @property
    def decisive_games(self) -> int:
        """Number of non-draw games."""
        return self.wins + self.losses

    @property
    def win_rate(self) -> float:
        """Decisive win rate as a percentage."""
        if self.decisive_games == 0:
            return 0.0
        return self.wins / self.decisive_games * 100

    @property
    def avg_rounds(self) -> float:
        """Average game length."""
        if self.games == 0:
            return 0.0
        return self.rounds / self.games


@dataclass
class TraceLine:
    """Compact human-readable decision log line."""

    round_num: int
    phase: str
    family: str
    player: int
    detail: str


def _load_layer_archetypes(layer: str) -> dict[str, tuple[AgentSide, AgentSide]]:
    """Return archetype pairs for a supported benchmark layer."""
    if layer == "l2":
        from simulator.l2_balance_matrix import build_archetypes
    elif layer == "l3":
        from simulator.l3_advanced_dice_pool import build_archetypes
    else:
        raise ValueError(f"Unknown layer: {layer}")

    rule_based = build_archetypes("rule-based")
    game_aware = build_archetypes("game-aware")
    pairs: dict[str, tuple[AgentSide, AgentSide]] = {}
    for name in rule_based:
        rb = rule_based[name]
        ga = game_aware[name]
        pairs[name] = (
            AgentSide("rule-based", name, rb.dice_ids, rb.gp_ids, rb.agent_cls),
            AgentSide("game-aware", name, ga.dice_ids, ga.gp_ids, ga.agent_cls),
        )
    return pairs


def _side_for(
    pairs: dict[str, tuple[AgentSide, AgentSide]],
    archetype: str,
    family: str,
) -> AgentSide:
    """Return a concrete side from the layer archetype map."""
    rule_based, game_aware = pairs[archetype]
    if family == "rule-based":
        return rule_based
    if family == "game-aware":
        return game_aware
    raise ValueError(f"Unknown agent family: {family}")


def _resolve_dice(dice_ids: tuple[str, ...]):
    """Resolve die ids into concrete die definitions."""
    die_types = load_die_types()
    return [die_types[die_id] for die_id in dice_ids]


def _new_engine(
    p1: AgentSide,
    p2: AgentSide,
    rng: np.random.Generator,
) -> GameEngine:
    """Construct an engine for one diagnostic duel."""
    return GameEngine(
        p1_die_types=_resolve_dice(p1.dice_ids),
        p2_die_types=_resolve_dice(p2.dice_ids),
        rng=rng,
        p1_gp_ids=p1.gp_ids,
        p2_gp_ids=p2.gp_ids,
    )


def _new_side_stats() -> dict[int, DecisionStats]:
    """Create empty per-seat stats for one game."""
    return {1: DecisionStats(games=1), 2: DecisionStats(games=1)}


def _record_keep(
    stats: DecisionStats,
    state: GameState,
    player_num: int,
    action: frozenset[int],
) -> None:
    """Record keep selection shape for one decision."""
    player = state.p1 if player_num == 1 else state.p2
    stats.keep_decisions += 1
    for idx in action:
        if 0 <= idx < len(player.dice_faces):
            stats.kept_faces[player.dice_faces[idx]] += 1


def _warning_keys_for_gp(
    state: GameState,
    player_num: int,
    choice: tuple[str, int] | None,
    god_powers: dict[str, GodPower],
) -> list[str]:
    """Return simple tactical warning keys for a GP decision."""
    view = view_for(state, player_num)
    player = player_with_available_tokens(view)
    choices = affordable_choices(view, god_powers, tier_order=(0,))
    warnings: list[str] = []

    if choice is None:
        if choices:
            warnings.append("passed_with_affordable_gp")
        return warnings

    if choice not in choices:
        warnings.append("chose_unaffordable_or_unloaded_gp")
        return warnings

    gp_id, tier_idx = choice
    tier = god_powers[gp_id].tiers[tier_idx]

    if gp_id == "GP_EIRS_MERCY" and view.missing_hp <= 0:
        warnings.append("eir_at_full_hp")
    if gp_id == "GP_AEGIS_OF_BALDR" and estimate_opponent_gp_damage(view) <= 0:
        warnings.append("aegis_without_gp_threat")
    if gp_id == "GP_BRAGIS_SONG" and view.combat.incoming_total <= 0:
        warnings.append("bragi_without_dice_threat")
    if gp_id == "GP_SURTRS_FLAME" and player.hp <= tier.self_damage:
        warnings.append("surtr_self_lethal")
    if gp_id == "GP_GULLVEIGS_HOARD" and ("GP_MJOLNIRS_WRATH", 0) in choices:
        warnings.append("hoard_while_mjolnir_affordable")
    if gp_id == "GP_MJOLNIRS_WRATH" and view.opponent.hp > tier.damage and view.combat.incoming_total >= view.player.hp:
        warnings.append("nonlethal_mjolnir_while_dying_to_dice")

    return warnings


def _record_gp(
    stats: DecisionStats,
    state: GameState,
    player_num: int,
    choice: tuple[str, int] | None,
    god_powers: dict[str, GodPower],
) -> list[str]:
    """Record one GP decision and return warning keys for trace output."""
    stats.gp_decisions += 1
    if choice is None:
        stats.gp_passes += 1
    else:
        stats.gp_choices[f"{choice[0]}:T{choice[1] + 1}"] += 1

    warnings = _warning_keys_for_gp(state, player_num, choice, god_powers)
    stats.warnings.update(warnings)
    return warnings


def _choice_label(choice: tuple[str, int] | None) -> str:
    """Format a GP choice for compact trace output."""
    if choice is None:
        return "PASS"
    return f"{choice[0]}:T{choice[1] + 1}"


def _gp_context_label(
    state: GameState,
    player_num: int,
    choice: tuple[str, int] | None,
    warnings: list[str],
    god_powers: dict[str, GodPower],
) -> str:
    """Return a compact tactical context string for a GP decision."""
    view = view_for(state, player_num)
    choices = affordable_choices(view, god_powers, tier_order=(0,))
    player = state.p1 if player_num == 1 else state.p2
    available = player_with_available_tokens(view).tokens
    return (
        f"choice={_choice_label(choice)} warnings={warnings or '-'} "
        f"hp={player.hp} tok={player.tokens}->{available} "
        f"in={view.combat.incoming_total} out={view.combat.outgoing_total} "
        f"opp_gp={estimate_opponent_gp_damage(view)} "
        f"affordable={[ _choice_label(c) for c in choices ] or '-'}"
    )


def _append_trace(
    trace: list[TraceLine],
    trace_enabled: bool,
    state: GameState,
    phase: str,
    family: str,
    player_num: int,
    detail: str,
) -> None:
    """Append a trace line when tracing is enabled."""
    if not trace_enabled:
        return
    trace.append(TraceLine(state.round_num, phase, family, player_num, detail))


def _run_traced_game(
    p1_side: AgentSide,
    p2_side: AgentSide,
    rng: np.random.Generator,
    trace_enabled: bool,
    max_rounds: int = 100,
) -> tuple[GameState, dict[int, DecisionStats], list[TraceLine]]:
    """Run one game while collecting per-seat decision diagnostics."""
    god_powers = load_god_powers()
    engine = _new_engine(p1_side, p2_side, rng)
    p1_agent = p1_side.agent_cls(rng=rng)
    p2_agent = p2_side.agent_cls(rng=rng)
    state = engine.new_game()
    stats = _new_side_stats()
    trace: list[TraceLine] = []

    def tick(p1_action=None, p2_action=None) -> list[GameEvent]:
        nonlocal state
        state, events = engine.step(state, p1_action, p2_action)
        return events

    while state.phase != GamePhase.GAME_OVER:
        if state.round_num > max_rounds:
            state = GameState(
                round_num=state.round_num,
                phase=GamePhase.GAME_OVER,
                p1=state.p1,
                p2=state.p2,
                winner=0,
                condition_ids=state.condition_ids,
            )
            break

        tick()  # REVEAL -> ROLL
        tick()  # ROLL -> KEEP_1

        p1_keep = p1_agent.choose_keep(state, 1)
        p2_keep = p2_agent.choose_keep(state, 2)
        _record_keep(stats[1], state, 1, p1_keep)
        _record_keep(stats[2], state, 2, p2_keep)
        _append_trace(trace, trace_enabled, state, "KEEP_1", p1_side.family, 1, f"kept={sorted(p1_keep)}")
        _append_trace(trace, trace_enabled, state, "KEEP_1", p2_side.family, 2, f"kept={sorted(p2_keep)}")
        tick(p1_keep, p2_keep)

        tick()  # REROLL_1 -> KEEP_2
        p1_keep = p1_agent.choose_keep(state, 1)
        p2_keep = p2_agent.choose_keep(state, 2)
        _record_keep(stats[1], state, 1, p1_keep)
        _record_keep(stats[2], state, 2, p2_keep)
        _append_trace(trace, trace_enabled, state, "KEEP_2", p1_side.family, 1, f"kept={sorted(p1_keep)}")
        _append_trace(trace, trace_enabled, state, "KEEP_2", p2_side.family, 2, f"kept={sorted(p2_keep)}")
        tick(p1_keep, p2_keep)

        tick()  # REROLL_2 -> GOD_POWER
        p1_gp = p1_agent.choose_god_power(state, 1)
        p2_gp = p2_agent.choose_god_power(state, 2)
        p1_warnings = _record_gp(stats[1], state, 1, p1_gp, god_powers)
        p2_warnings = _record_gp(stats[2], state, 2, p2_gp, god_powers)
        _append_trace(
            trace,
            trace_enabled,
            state,
            "GOD_POWER",
            p1_side.family,
            1,
            _gp_context_label(state, 1, p1_gp, p1_warnings, god_powers),
        )
        _append_trace(
            trace,
            trace_enabled,
            state,
            "GOD_POWER",
            p2_side.family,
            2,
            _gp_context_label(state, 2, p2_gp, p2_warnings, god_powers),
        )
        tick(p1_gp, p2_gp)

        tick()  # COMBAT -> GOD_RESOLVE
        tick()  # GOD_RESOLVE -> TOKENS
        tick()  # TOKENS -> END_CHECK
        tick()  # END_CHECK -> next REVEAL/GAME_OVER

    for seat in (1, 2):
        stats[seat].rounds += state.round_num

    if state.winner == 1:
        stats[1].wins += 1
        stats[2].losses += 1
    elif state.winner == 2:
        stats[2].wins += 1
        stats[1].losses += 1
    else:
        stats[1].draws += 1
        stats[2].draws += 1

    return state, stats, trace


def _merge_seat_stats(
    aggregate: dict[str, DecisionStats],
    seat_stats: dict[int, DecisionStats],
    p1_side: AgentSide,
    p2_side: AgentSide,
) -> None:
    """Merge per-seat stats into family aggregate stats."""
    aggregate[p1_side.family].merge(seat_stats[1])
    aggregate[p2_side.family].merge(seat_stats[2])


def run_duel(
    rule_based: AgentSide,
    game_aware: AgentSide,
    games: int,
    seed: int,
    trace_games: int,
) -> tuple[dict[str, DecisionStats], list[TraceLine]]:
    """Run both seat orders for a same-archetype rule-vs-aware duel."""
    rng = np.random.default_rng(seed)
    aggregate = {
        "rule-based": DecisionStats(),
        "game-aware": DecisionStats(),
    }
    traces: list[TraceLine] = []

    for game_idx in range(games):
        trace_enabled = game_idx < trace_games
        _, seat_stats, trace = _run_traced_game(game_aware, rule_based, rng, trace_enabled)
        _merge_seat_stats(aggregate, seat_stats, game_aware, rule_based)
        traces.extend(trace)

        _, seat_stats, trace = _run_traced_game(rule_based, game_aware, rng, trace_enabled)
        _merge_seat_stats(aggregate, seat_stats, rule_based, game_aware)
        traces.extend(trace)

    return aggregate, traces


def run_fixed_matchup(
    p1_side: AgentSide,
    p2_side: AgentSide,
    games: int,
    seed: int,
    trace_games: int,
    swap_seats: bool,
) -> tuple[dict[str, DecisionStats], list[TraceLine]]:
    """Run one cross-archetype diagnostic matchup, optionally with seat swap."""
    rng = np.random.default_rng(seed)
    aggregate = {
        f"P1 {p1_side.family} {p1_side.archetype_name}": DecisionStats(),
        f"P2 {p2_side.family} {p2_side.archetype_name}": DecisionStats(),
    }
    traces: list[TraceLine] = []

    for game_idx in range(games):
        trace_enabled = game_idx < trace_games
        _, seat_stats, trace = _run_traced_game(p1_side, p2_side, rng, trace_enabled)
        aggregate[f"P1 {p1_side.family} {p1_side.archetype_name}"].merge(seat_stats[1])
        aggregate[f"P2 {p2_side.family} {p2_side.archetype_name}"].merge(seat_stats[2])
        traces.extend(trace)

    if not swap_seats:
        return aggregate, traces

    swapped = {
        f"P2 {p1_side.family} {p1_side.archetype_name}": DecisionStats(),
        f"P1 {p2_side.family} {p2_side.archetype_name}": DecisionStats(),
    }
    for game_idx in range(games):
        trace_enabled = game_idx < trace_games
        _, seat_stats, trace = _run_traced_game(p2_side, p1_side, rng, trace_enabled)
        swapped[f"P1 {p2_side.family} {p2_side.archetype_name}"].merge(seat_stats[1])
        swapped[f"P2 {p1_side.family} {p1_side.archetype_name}"].merge(seat_stats[2])
        traces.extend(trace)

    aggregate.update(swapped)
    return aggregate, traces


def _format_counter(counter: Counter[str], limit: int = 5) -> str:
    """Format the most common counter entries for CLI output."""
    if not counter:
        return "-"
    return ", ".join(f"{name}={count}" for name, count in counter.most_common(limit))


def _print_duel_report(archetype: str, stats: dict[str, DecisionStats]) -> None:
    """Print one archetype's diagnostic report."""
    print()
    print(f"{archetype}")
    print("-" * len(archetype))
    for family in ("rule-based", "game-aware"):
        s = stats[family]
        pass_rate = (s.gp_passes / s.gp_decisions * 100) if s.gp_decisions else 0.0
        print(
            f"  {family:<10} win={s.win_rate:5.1f}% "
            f"({s.wins}/{s.decisive_games}, draws={s.draws}) "
            f"avg_rounds={s.avg_rounds:4.1f} gp_pass={pass_rate:4.1f}%"
        )
        print(f"    GP usage: {_format_counter(s.gp_choices)}")
        print(f"    Warnings: {_format_counter(s.warnings)}")
        print(f"    Kept faces: {_format_counter(s.kept_faces, limit=6)}")


def _print_stats_block(title: str, stats: dict[str, DecisionStats]) -> None:
    """Print a generic stats block keyed by descriptive side labels."""
    print()
    print(title)
    print("-" * len(title))
    for label, s in stats.items():
        pass_rate = (s.gp_passes / s.gp_decisions * 100) if s.gp_decisions else 0.0
        print(
            f"  {label:<30} win={s.win_rate:5.1f}% "
            f"({s.wins}/{s.decisive_games}, draws={s.draws}) "
            f"avg_rounds={s.avg_rounds:4.1f} gp_pass={pass_rate:4.1f}%"
        )
        print(f"    GP usage: {_format_counter(s.gp_choices)}")
        print(f"    Warnings: {_format_counter(s.warnings)}")
        print(f"    Kept faces: {_format_counter(s.kept_faces, limit=6)}")


def _print_trace(lines: list[TraceLine]) -> None:
    """Print optional trace lines."""
    if not lines:
        return
    print()
    print("TRACE")
    print("-----")
    for line in lines:
        print(
            f"  R{line.round_num:02d} {line.phase:<9} "
            f"P{line.player} {line.family:<10} {line.detail}"
        )


def main() -> None:
    """CLI entrypoint for agent A/B diagnostics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layer", choices=("l2", "l3"), default="l3", help="benchmark layer to test")
    parser.add_argument("--games", type=int, default=300, help="games per seat order")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed")
    parser.add_argument(
        "--archetype",
        choices=("AGGRO", "CONTROL", "ECONOMY", "all"),
        default="all",
        help="archetype to diagnose",
    )
    parser.add_argument("--p1", choices=("AGGRO", "CONTROL", "ECONOMY"), help="optional fixed-matchup P1 archetype")
    parser.add_argument("--p2", choices=("AGGRO", "CONTROL", "ECONOMY"), help="optional fixed-matchup P2 archetype")
    parser.add_argument(
        "--p1-mode",
        choices=("rule-based", "game-aware"),
        default="game-aware",
        help="agent family for --p1",
    )
    parser.add_argument(
        "--p2-mode",
        choices=("rule-based", "game-aware"),
        default="game-aware",
        help="agent family for --p2",
    )
    parser.add_argument(
        "--swap-seats",
        action="store_true",
        help="also run the fixed matchup with P1/P2 seats swapped",
    )
    parser.add_argument("--trace-games", type=int, default=0, help="print compact traces for first N games")
    args = parser.parse_args()

    pairs = _load_layer_archetypes(args.layer)

    if args.p1 or args.p2:
        if not args.p1 or not args.p2:
            raise SystemExit("--p1 and --p2 must be supplied together")
        p1_side = _side_for(pairs, args.p1, args.p1_mode)
        p2_side = _side_for(pairs, args.p2, args.p2_mode)
        print(
            f"Agent diagnostics: layer={args.layer}, "
            f"games={args.games}, seed={args.seed}, fixed matchup"
        )
        print(
            f"P1={args.p1_mode} {args.p1}, "
            f"P2={args.p2_mode} {args.p2}, swap_seats={args.swap_seats}"
        )
        stats, traces = run_fixed_matchup(
            p1_side,
            p2_side,
            games=args.games,
            seed=args.seed,
            trace_games=args.trace_games,
            swap_seats=args.swap_seats,
        )
        _print_stats_block(f"{args.p1} vs {args.p2}", stats)
        _print_trace(traces)
        return

    names = list(pairs.keys()) if args.archetype == "all" else [args.archetype]

    print(
        f"Agent diagnostics: layer={args.layer}, "
        f"games={args.games} per seat order, seed={args.seed}"
    )
    print("Each archetype is tested as game-aware vs rule-based using the same dice and GP loadout.")

    all_traces: list[TraceLine] = []
    for offset, name in enumerate(names):
        rule_based, game_aware = pairs[name]
        stats, traces = run_duel(
            rule_based,
            game_aware,
            games=args.games,
            seed=args.seed + offset * 10_000,
            trace_games=args.trace_games,
        )
        _print_duel_report(name, stats)
        all_traces.extend(traces)

    _print_trace(all_traces)


if __name__ == "__main__":
    main()
