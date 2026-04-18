"""
l2_signature.py
---------------
Search and validate canonical mixed-loadout archetype packages with exactly one
signature God Power per archetype.

This sits between the L2 identity shell and the fuller L2 balance search:
  - mixed stock dice loadouts only
  - 1 God Power per archetype
  - T1-only GP usage
  - lightweight heuristic pilots tuned for the chosen signature GP

The goal is to answer a narrower question than l2_balance.py:
can representative dice packages plus one defining tool already express the
intended archetype loop, before multi-GP interactions take over?
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass
from itertools import product

import numpy as np

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from simulator.agents.aggro_agent import AggroAgent
from simulator.agents.combo_agent import ComboAgent
from simulator.agents.control_agent import ControlAgent
from simulator.agents.economy_agent import EconomyAgent
from simulator.die_types import load_die_types
from simulator.game_engine import GameEngine
from simulator.god_powers import GodPower
from simulator.l2_balance import (
    ARCHETYPES,
    MatchupStats,
    TuningProfile,
    _build_tuning_profiles,
    _engine_kwargs_for_profile,
    _tuned_god_powers,
    list_profiles,
)
from simulator.l2_identity import _predicted_dice_damage

_TARGET_MATRIX: dict[tuple[str, str], float] = {
    ("AGGRO", "AGGRO"): 0.50,
    ("AGGRO", "CONTROL"): 0.35,
    ("AGGRO", "ECONOMY"): 0.62,
    ("AGGRO", "COMBO"): 0.58,
    ("CONTROL", "AGGRO"): 0.65,
    ("CONTROL", "CONTROL"): 0.50,
    ("CONTROL", "ECONOMY"): 0.38,
    ("CONTROL", "COMBO"): 0.45,
    ("ECONOMY", "AGGRO"): 0.38,
    ("ECONOMY", "CONTROL"): 0.62,
    ("ECONOMY", "ECONOMY"): 0.50,
    ("ECONOMY", "COMBO"): 0.55,
    ("COMBO", "AGGRO"): 0.42,
    ("COMBO", "CONTROL"): 0.55,
    ("COMBO", "ECONOMY"): 0.45,
    ("COMBO", "COMBO"): 0.50,
}
_T1_ONLY = (0,)
_CANDIDATES: dict[str, list["SignatureCandidate"]] = {}
_DISRUPTIBLE_GPS = frozenset(
    {
        "GP_FENRIRS_BITE",
        "GP_SURTRS_FLAME",
        "GP_AEGIS_OF_BALDR",
        "GP_TYRS_JUDGMENT",
        "GP_MJOLNIRS_WRATH",
        "GP_FREYAS_BLESSING",
        "GP_SKADIS_VOLLEY",
        "GP_HEIMDALLRS_WATCH",
    }
)


@dataclass(frozen=True)
class SignatureCandidate:
    id: str
    archetype: str
    name: str
    agent_cls: type
    agent_kwargs: dict
    dice_loadout: list[str]
    gp_loadout: tuple[str, ...]


@dataclass
class PackageScore:
    profile_id: str
    ids: dict[str, str]
    objective: float
    matrix_error: float
    avg_rounds: float
    draw_rate: float
    rps_failures: int
    matchup_stats: dict[tuple[str, str], MatchupStats]


def _players(state, player_num: int):
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    return player, opponent


def _try_t1(player, god_powers: dict[str, GodPower], gp_id: str) -> tuple[str, int] | None:
    gp = god_powers.get(gp_id)
    if gp is None or gp_id not in player.gp_loadout:
        return None
    return (gp_id, 0) if player.tokens >= gp.tiers[0].cost else None


def _aggro_fenrir_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_FENRIRS_BITE")
    if choice is None:
        return None
    damage, _ = _predicted_dice_damage(player, opponent)
    if opponent.hp <= 7 or damage >= 2 or opponent.tokens >= 4:
        return choice
    return None


def _aggro_surtr_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_SURTRS_FLAME")
    if choice is None:
        return None
    damage, _ = _predicted_dice_damage(player, opponent)
    if opponent.hp <= 5 or damage >= 3:
        return choice
    return None


def _control_aegis_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_AEGIS_OF_BALDR")
    if choice is None:
        return None
    incoming_damage, _ = _predicted_dice_damage(opponent, player)
    opp_arrows = opponent.dice_faces.count("FACE_ARROW")
    player_shields = player.dice_faces.count("FACE_SHIELD")
    if incoming_damage >= 2 or max(0, opp_arrows - player_shields) >= 2 or player.hp <= 8:
        return choice
    return None


def _control_eir_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, _ = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_EIRS_MERCY")
    if choice is None:
        return None
    return choice if player.hp <= 8 else None


def _control_tyr_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_TYRS_JUDGMENT")
    if choice is None:
        return None
    incoming_damage, _ = _predicted_dice_damage(opponent, player)
    outgoing_damage, _ = _predicted_dice_damage(player, opponent)
    if incoming_damage >= 1 or outgoing_damage >= 1 or player.hp <= 9:
        return choice
    return None


def _control_frigg_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_FRIGGS_VEIL")
    if choice is None or not opponent.gp_loadout:
        return None
    opp_gp_id = opponent.gp_loadout[0]
    opp_gp = god_powers.get(opp_gp_id)
    if opp_gp is None or opp_gp_id not in _DISRUPTIBLE_GPS:
        return None
    if opponent.tokens < opp_gp.tiers[0].cost:
        return None
    incoming_damage, _ = _predicted_dice_damage(opponent, player)
    return choice if incoming_damage >= 1 or opponent.tokens >= opp_gp.tiers[0].cost + 1 else None


def _economy_freyja_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, _ = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_FREYAS_BLESSING")
    if choice is None:
        return None
    hands = player.dice_faces.count("FACE_HAND") + player.dice_faces.count("FACE_HAND_BORDERED")
    return choice if hands >= 2 or player.hp <= 8 else None


def _economy_mjolnir_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_MJOLNIRS_WRATH")
    if choice is None:
        return None
    return choice if opponent.hp <= 8 or player.tokens >= 8 else None


def _combo_skadi_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_SKADIS_VOLLEY")
    if choice is None:
        return None
    arrows = player.dice_faces.count("FACE_ARROW")
    unblocked = max(0, arrows - opponent.dice_faces.count("FACE_SHIELD"))
    if unblocked >= 2:
        return choice
    return choice if unblocked >= 1 and opponent.hp <= 8 else None


def _combo_heimdallr_gp(state, player_num: int, god_powers: dict[str, GodPower]) -> tuple[str, int] | None:
    player, opponent = _players(state, player_num)
    choice = _try_t1(player, god_powers, "GP_HEIMDALLRS_WATCH")
    if choice is None:
        return None
    _, blocked = _predicted_dice_damage(player, opponent)
    attacks = player.dice_faces.count("FACE_AXE") + player.dice_faces.count("FACE_ARROW")
    if attacks >= 2 and blocked >= 1:
        return choice
    return None


def _build_candidates() -> dict[str, list[SignatureCandidate]]:
    if _CANDIDATES:
        return _CANDIDATES

    candidates = {
        "AGGRO": [
            SignatureCandidate(
                id="A_SIG1",
                archetype="AGGRO",
                name="Fenrir Blitz",
                agent_cls=AggroAgent,
                agent_kwargs={
                    "gp_priority": ("GP_FENRIRS_BITE",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _aggro_fenrir_gp,
                },
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_GAMBLER"] * 2,
                gp_loadout=("GP_FENRIRS_BITE",),
            ),
            SignatureCandidate(
                id="A_SIG2",
                archetype="AGGRO",
                name="Balanced Fenrir",
                agent_cls=AggroAgent,
                agent_kwargs={
                    "gp_priority": ("GP_FENRIRS_BITE",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _aggro_fenrir_gp,
                },
                dice_loadout=["DIE_BERSERKER"] * 3 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_FENRIRS_BITE",),
            ),
            SignatureCandidate(
                id="A_SIG3",
                archetype="AGGRO",
                name="Surtr Pressure",
                agent_cls=AggroAgent,
                agent_kwargs={
                    "gp_priority": ("GP_SURTRS_FLAME",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _aggro_surtr_gp,
                },
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_SURTRS_FLAME",),
            ),
            SignatureCandidate(
                id="A_SIG4",
                archetype="AGGRO",
                name="Tempered Fenrir",
                agent_cls=AggroAgent,
                agent_kwargs={
                    "gp_priority": ("GP_FENRIRS_BITE",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _aggro_fenrir_gp,
                },
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_GAMBLER"] + ["DIE_WARRIOR"],
                gp_loadout=("GP_FENRIRS_BITE",),
            ),
        ],
        "CONTROL": [
            SignatureCandidate(
                id="C_SIG1",
                archetype="CONTROL",
                name="Aegis Guard",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "gp_priority_healthy": ("GP_AEGIS_OF_BALDR",),
                    "gp_priority_hurt": ("GP_AEGIS_OF_BALDR",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _control_aegis_gp,
                },
                dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"],
                gp_loadout=("GP_AEGIS_OF_BALDR",),
            ),
            SignatureCandidate(
                id="C_SIG2",
                archetype="CONTROL",
                name="Eir Sustain",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "gp_priority_healthy": ("GP_EIRS_MERCY",),
                    "gp_priority_hurt": ("GP_EIRS_MERCY",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _control_eir_gp,
                },
                dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_SKALD"] * 2 + ["DIE_MISER"],
                gp_loadout=("GP_EIRS_MERCY",),
            ),
            SignatureCandidate(
                id="C_SIG3",
                archetype="CONTROL",
                name="Tyr Counterwall",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "gp_priority_healthy": ("GP_TYRS_JUDGMENT",),
                    "gp_priority_hurt": ("GP_TYRS_JUDGMENT",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _control_tyr_gp,
                },
                dice_loadout=["DIE_WARDEN"] * 2 + ["DIE_WARRIOR"] * 3 + ["DIE_SKALD"],
                gp_loadout=("GP_TYRS_JUDGMENT",),
            ),
            SignatureCandidate(
                id="C_SIG4",
                archetype="CONTROL",
                name="Aegis Midwall",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "gp_priority_healthy": ("GP_AEGIS_OF_BALDR",),
                    "gp_priority_hurt": ("GP_AEGIS_OF_BALDR",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _control_aegis_gp,
                },
                dice_loadout=["DIE_WARDEN"] * 2 + ["DIE_WARRIOR"] * 3 + ["DIE_SKALD"],
                gp_loadout=("GP_AEGIS_OF_BALDR",),
            ),
            SignatureCandidate(
                id="C_SIG5",
                archetype="CONTROL",
                name="Frigg Guard",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "gp_priority_healthy": ("GP_FRIGGS_VEIL",),
                    "gp_priority_hurt": ("GP_FRIGGS_VEIL",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _control_frigg_gp,
                },
                dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"],
                gp_loadout=("GP_FRIGGS_VEIL",),
            ),
            SignatureCandidate(
                id="C_SIG6",
                archetype="CONTROL",
                name="Frigg Midwall",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HELMET", "FACE_SHIELD", "FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW"}
                    ),
                    "gp_priority_healthy": ("GP_FRIGGS_VEIL",),
                    "gp_priority_hurt": ("GP_FRIGGS_VEIL",),
                    "tier_order": _T1_ONLY,
                    "gp_select_fn": _control_frigg_gp,
                },
                dice_loadout=["DIE_WARDEN"] * 2 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"] * 2,
                gp_loadout=("GP_FRIGGS_VEIL",),
            ),
        ],
        "ECONOMY": [
            SignatureCandidate(
                id="E_SIG1",
                archetype="ECONOMY",
                name="Miser Freyja",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_HAND", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                    "gp_priority": ("GP_FREYAS_BLESSING",),
                    "tier_order": _T1_ONLY,
                    "token_threshold": 0,
                    "gp_select_fn": _economy_freyja_gp,
                },
                dice_loadout=["DIE_MISER"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_WARDEN"],
                gp_loadout=("GP_FREYAS_BLESSING",),
            ),
            SignatureCandidate(
                id="E_SIG2",
                archetype="ECONOMY",
                name="Skald Freyja",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                    "gp_priority": ("GP_FREYAS_BLESSING",),
                    "tier_order": _T1_ONLY,
                    "token_threshold": 0,
                    "gp_select_fn": _economy_freyja_gp,
                },
                dice_loadout=["DIE_SKALD"] * 2 + ["DIE_MISER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_FREYAS_BLESSING",),
            ),
            SignatureCandidate(
                id="E_SIG3",
                archetype="ECONOMY",
                name="Cashout Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_HAND", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                    "gp_priority": ("GP_MJOLNIRS_WRATH",),
                    "tier_order": _T1_ONLY,
                    "token_threshold": 0,
                    "gp_select_fn": _economy_mjolnir_gp,
                },
                dice_loadout=["DIE_SKALD"] * 2 + ["DIE_MISER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_MJOLNIRS_WRATH",),
            ),
            SignatureCandidate(
                id="E_SIG4",
                archetype="ECONOMY",
                name="Boarded Freyja",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                    "gp_priority": ("GP_FREYAS_BLESSING",),
                    "tier_order": _T1_ONLY,
                    "token_threshold": 0,
                    "gp_select_fn": _economy_freyja_gp,
                },
                dice_loadout=["DIE_SKALD"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_MISER"],
                gp_loadout=("GP_FREYAS_BLESSING",),
            ),
        ],
        "COMBO": [
            SignatureCandidate(
                id="CO_SIG1",
                archetype="COMBO",
                name="Hunter Volley",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"}),
                    "gp_priority": ("GP_SKADIS_VOLLEY",),
                    "tier_order": _T1_ONLY,
                    "min_arrows_for_skadi": 2,
                    "gp_select_fn": _combo_skadi_gp,
                },
                dice_loadout=["DIE_HUNTER"] * 4 + ["DIE_GAMBLER"] * 2,
                gp_loadout=("GP_SKADIS_VOLLEY",),
            ),
            SignatureCandidate(
                id="CO_SIG2",
                archetype="COMBO",
                name="Tempered Volley",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"}),
                    "gp_priority": ("GP_SKADIS_VOLLEY",),
                    "tier_order": _T1_ONLY,
                    "min_arrows_for_skadi": 2,
                    "gp_select_fn": _combo_skadi_gp,
                },
                dice_loadout=["DIE_HUNTER"] * 3 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_SKADIS_VOLLEY",),
            ),
            SignatureCandidate(
                id="CO_SIG3",
                archetype="COMBO",
                name="Unblockable Hunt",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"}),
                    "gp_priority": ("GP_HEIMDALLRS_WATCH",),
                    "tier_order": _T1_ONLY,
                    "min_arrows_for_skadi": 99,
                    "gp_select_fn": _combo_heimdallr_gp,
                },
                dice_loadout=["DIE_HUNTER"] * 3 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_HEIMDALLRS_WATCH",),
            ),
            SignatureCandidate(
                id="CO_SIG4",
                archetype="COMBO",
                name="Heavy Unblockable Hunt",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"}),
                    "gp_priority": ("GP_HEIMDALLRS_WATCH",),
                    "tier_order": _T1_ONLY,
                    "min_arrows_for_skadi": 99,
                    "gp_select_fn": _combo_heimdallr_gp,
                },
                dice_loadout=["DIE_HUNTER"] * 2 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_HEIMDALLRS_WATCH",),
            ),
        ],
    }
    _CANDIDATES.update(candidates)
    return candidates


def _candidate_by_id(
    candidates: dict[str, list[SignatureCandidate]],
    archetype: str,
    candidate_id: str,
) -> SignatureCandidate:
    return next(c for c in candidates[archetype] if c.id == candidate_id)


def _make_package(
    ids: dict[str, str],
    candidates: dict[str, list[SignatureCandidate]],
) -> dict[str, SignatureCandidate]:
    return {arch: _candidate_by_id(candidates, arch, ids[arch]) for arch in ARCHETYPES}


def _run_package(
    package: dict[str, SignatureCandidate],
    n_games: int,
    seed: int,
    god_powers: dict[str, GodPower],
    profile: TuningProfile,
) -> tuple[dict[tuple[str, str], MatchupStats], float, float]:
    die_types = load_die_types()
    engine_kwargs = _engine_kwargs_for_profile(profile)
    matchup_stats: dict[tuple[str, str], MatchupStats] = {}
    all_rounds: list[int] = []
    total_draws = 0
    total_games = 0

    for p1_name in ARCHETYPES:
        for p2_name in ARCHETYPES:
            rng = np.random.default_rng(seed)
            p1 = package[p1_name]
            p2 = package[p2_name]
            engine = GameEngine(
                [die_types[d] for d in p1.dice_loadout],
                [die_types[d] for d in p2.dice_loadout],
                rng,
                p1_gp_ids=p1.gp_loadout,
                p2_gp_ids=p2.gp_loadout,
                god_powers=god_powers,
                **engine_kwargs,
            )
            p1_agent = p1.agent_cls(rng=rng, **p1.agent_kwargs)
            p2_agent = p2.agent_cls(rng=rng, **p2.agent_kwargs)

            p1_wins = 0
            p2_wins = 0
            draws = 0
            rounds: list[int] = []
            for _ in range(n_games):
                final_state, _ = engine.run_game(p1_agent, p2_agent)
                if final_state.winner == 1:
                    p1_wins += 1
                elif final_state.winner == 2:
                    p2_wins += 1
                else:
                    draws += 1
                rounds.append(final_state.round_num)

            decisive = p1_wins + p2_wins
            matchup_stats[(p1_name, p2_name)] = MatchupStats(
                decisive_win_rate=(p1_wins / decisive) if decisive else 0.5,
                avg_rounds=sum(rounds) / len(rounds),
                draw_rate=draws / n_games,
            )
            all_rounds.extend(rounds)
            total_draws += draws
            total_games += n_games

    return matchup_stats, sum(all_rounds) / len(all_rounds), total_draws / total_games


def _score_package(
    ids: dict[str, str],
    candidates: dict[str, list[SignatureCandidate]],
    n_games: int,
    seed: int,
    profile: TuningProfile,
) -> PackageScore:
    package = _make_package(ids, candidates)
    matchup_stats, avg_rounds, draw_rate = _run_package(
        package,
        n_games=n_games,
        seed=seed,
        god_powers=_tuned_god_powers(profile),
        profile=profile,
    )
    matrix_error = sum(
        (matchup_stats[k].decisive_win_rate - _TARGET_MATRIX[k]) ** 2
        for k in matchup_stats
    )

    rps_failures = 0
    for arch in ARCHETYPES:
        row = [matchup_stats[(arch, opp)].decisive_win_rate for opp in ARCHETYPES if opp != arch]
        if not any(rate > 0.55 for rate in row) or not any(rate < 0.45 for rate in row):
            rps_failures += 1

    objective = matrix_error
    objective += max(0.0, avg_rounds - 8.0) * 0.03
    objective += max(0.0, draw_rate - 0.20) * 0.60
    objective += rps_failures * 0.10

    return PackageScore(
        profile_id=profile.id,
        ids=ids,
        objective=objective,
        matrix_error=matrix_error,
        avg_rounds=avg_rounds,
        draw_rate=draw_rate,
        rps_failures=rps_failures,
        matchup_stats=matchup_stats,
    )


def search_packages(
    n_games: int = 40,
    seed: int = 42,
    profile_ids: tuple[str, ...] = ("BALANCED_V1",),
) -> list[PackageScore]:
    candidates = _build_candidates()
    profiles = _build_tuning_profiles()
    scores: list[PackageScore] = []
    for profile_id in profile_ids:
        profile = profiles[profile_id]
        for picks in product(*(candidates[arch] for arch in ARCHETYPES)):
            ids = {cand.archetype: cand.id for cand in picks}
            scores.append(_score_package(ids, candidates, n_games=n_games, seed=seed, profile=profile))
    scores.sort(key=lambda s: s.objective)
    return scores


def print_search(scores: list[PackageScore], top: int) -> None:
    print("\nBest signature-GP packages")
    print("Objective = matrix error + pacing/draw/RPS penalties. Lower is better.\n")
    for i, score in enumerate(scores[:top], 1):
        print(
            f"{i:>2}. [{score.profile_id}] {score.ids['AGGRO']}, {score.ids['CONTROL']}, "
            f"{score.ids['ECONOMY']}, {score.ids['COMBO']}  "
            f"obj={score.objective:.3f}  matrix={score.matrix_error:.3f}  "
            f"rounds={score.avg_rounds:.2f}  draw={score.draw_rate:.1%}  "
            f"rps_fail={score.rps_failures}"
        )


def print_package(score: PackageScore) -> None:
    print("\nSignature package validation\n")
    print(
        f"Profile: {score.profile_id}\n"
        f"Package: {score.ids['AGGRO']}, {score.ids['CONTROL']}, "
        f"{score.ids['ECONOMY']}, {score.ids['COMBO']}"
    )
    print(
        f"Objective={score.objective:.3f}  MatrixError={score.matrix_error:.3f}  "
        f"AvgRounds={score.avg_rounds:.2f}  DrawRate={score.draw_rate:.1%}  "
        f"RPSFailures={score.rps_failures}"
    )
    print("\nMatrix (P1 decisive win rate)")
    header = "P1 \\\\ P2"
    print(f"{header:<14} {'Aggro':>8} {'Control':>8} {'Economy':>8} {'Combo':>8}")
    for row in ARCHETYPES:
        vals = [score.matchup_stats[(row, col)].decisive_win_rate for col in ARCHETYPES]
        print(
            f"{row:<14} "
            f"{vals[0]:>7.1%} {vals[1]:>8.1%} {vals[2]:>8.1%} {vals[3]:>8.1%}"
        )


def main() -> None:
    profiles = _build_tuning_profiles()
    parser = argparse.ArgumentParser(description="Search canonical one-GP signature packages.")
    parser.add_argument("--games", type=int, default=40, help="Games per matchup during search/validation.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed.")
    parser.add_argument("--top", type=int, default=8, help="Number of top search results to print.")
    parser.add_argument(
        "--tune-profile",
        type=str,
        default="BALANCED_V1",
        choices=list_profiles(),
        help="Named GP tuning profile to evaluate.",
    )
    parser.add_argument(
        "--search-profiles",
        action="store_true",
        help="Search across all named tuning profiles instead of only --tune-profile.",
    )
    parser.add_argument(
        "--validate",
        type=str,
        default=None,
        help="Comma-separated package IDs, e.g. A_SIG2,C_SIG1,E_SIG2,CO_SIG2",
    )
    args = parser.parse_args()

    candidates = _build_candidates()
    if args.validate:
        picked = [s.strip() for s in args.validate.split(",")]
        if len(picked) != 4:
            raise SystemExit("--validate requires 4 comma-separated IDs.")
        ids = dict(zip(ARCHETYPES, picked))
        score = _score_package(
            ids,
            candidates,
            n_games=args.games,
            seed=args.seed,
            profile=profiles[args.tune_profile],
        )
        print_package(score)
        return

    profile_ids = tuple(sorted(profiles)) if args.search_profiles else (args.tune_profile,)
    scores = search_packages(n_games=args.games, seed=args.seed, profile_ids=profile_ids)
    print_search(scores, top=args.top)


if __name__ == "__main__":
    main()
