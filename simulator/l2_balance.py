"""
l2_balance.py
-------------
Search and validate representative mixed-loadout archetype packages.

This sits between the L2 identity shell and the full simulator:
  - mixed dice loadouts only
  - 3 God Powers per archetype
  - current engine rules
  - smarter GP logic where that meaningfully improves archetype expression

The goal is not "pick the spikiest tournament winner", but find a believable
4-pack that looks like what players would plausibly choose while getting
closer to CLAUDE.md's target matchup matrix.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
from dataclasses import dataclass, replace
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
from simulator.god_powers import GodPower, load_god_powers
from simulator.l2_identity import (
    _aggro_gp_select,
    _combo_gp_select,
    _control_gp_select,
    _economy_gp_select,
)

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


def _co6_odin_burst_gp(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    opp_shields = opponent.dice_faces.count("FACE_SHIELD")
    opp_helmets = opponent.dice_faces.count("FACE_HELMET")
    arrows = player.dice_faces.count("FACE_ARROW")
    axes = player.dice_faces.count("FACE_AXE")
    unblocked_arrows = max(0, arrows - opp_shields)
    if unblocked_arrows >= 2:
        gp = god_powers.get("GP_SKADIS_VOLLEY")
        if gp and "GP_SKADIS_VOLLEY" in player.gp_loadout:
            for t in (2, 1, 0):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_SKADIS_VOLLEY", t)
    if opp_helmets >= 2 and axes >= 2:
        gp = god_powers.get("GP_HEIMDALLRS_WATCH")
        if gp and "GP_HEIMDALLRS_WATCH" in player.gp_loadout:
            for t in (2, 1, 0):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_HEIMDALLRS_WATCH", t)
    gp = god_powers.get("GP_ODINS_INSIGHT")
    if gp and "GP_ODINS_INSIGHT" in player.gp_loadout and player.tokens >= gp.tiers[2].cost:
        return ("GP_ODINS_INSIGHT", 2)
    return None


def _co4_bridge_burst_gp(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    arrows = player.dice_faces.count("FACE_ARROW")
    axes = player.dice_faces.count("FACE_AXE")
    opp_shields = opponent.dice_faces.count("FACE_SHIELD")
    opp_helmets = opponent.dice_faces.count("FACE_HELMET")
    unblocked_arrows = max(0, arrows - opp_shields)
    blocked_hits = min(arrows, opp_shields) + min(axes, opp_helmets)

    if blocked_hits >= 2:
        gp = god_powers.get("GP_HEIMDALLRS_WATCH")
        if gp and "GP_HEIMDALLRS_WATCH" in player.gp_loadout:
            for t in (0, 1, 2):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_HEIMDALLRS_WATCH", t)

    if unblocked_arrows >= 2:
        gp = god_powers.get("GP_SKADIS_VOLLEY")
        if gp and "GP_SKADIS_VOLLEY" in player.gp_loadout:
            for t in (0, 1, 2):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_SKADIS_VOLLEY", t)

    if opponent.hp <= 9:
        gp = god_powers.get("GP_FENRIRS_BITE")
        if gp and "GP_FENRIRS_BITE" in player.gp_loadout:
            for t in (0, 1, 2):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_FENRIRS_BITE", t)
    return None


def _a5_bank_breaker_gp(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    axes = player.dice_faces.count("FACE_AXE")
    arrows = player.dice_faces.count("FACE_ARROW")
    opp_helmets = opponent.dice_faces.count("FACE_HELMET")
    opp_shields = opponent.dice_faces.count("FACE_SHIELD")
    blocked_hits = min(axes, opp_helmets) + min(arrows, opp_shields)
    total_hits = axes + arrows

    if opponent.tokens >= 4:
        gp = god_powers.get("GP_HEIMDALLRS_WATCH")
        if gp and "GP_HEIMDALLRS_WATCH" in player.gp_loadout and total_hits >= 2 and blocked_hits >= 1:
            for t in (2, 1, 0):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_HEIMDALLRS_WATCH", t)

        gp = god_powers.get("GP_FENRIRS_BITE")
        if gp and "GP_FENRIRS_BITE" in player.gp_loadout:
            for t in (2, 1, 0):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_FENRIRS_BITE", t)

    gp = god_powers.get("GP_SURTRS_FLAME")
    if gp and "GP_SURTRS_FLAME" in player.gp_loadout and (total_hits >= 3 or opponent.hp <= 8):
        for t in (2, 1, 0):
            if player.tokens >= gp.tiers[t].cost:
                return ("GP_SURTRS_FLAME", t)

    gp = god_powers.get("GP_HEIMDALLRS_WATCH")
    if gp and "GP_HEIMDALLRS_WATCH" in player.gp_loadout and blocked_hits >= 2:
        for t in (2, 1, 0):
            if player.tokens >= gp.tiers[t].cost:
                return ("GP_HEIMDALLRS_WATCH", t)

    gp = god_powers.get("GP_FENRIRS_BITE")
    if gp and "GP_FENRIRS_BITE" in player.gp_loadout and opponent.hp <= 10:
        for t in (2, 1, 0):
            if player.tokens >= gp.tiers[t].cost:
                return ("GP_FENRIRS_BITE", t)
    return None


def _a6_econ_crack_gp(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    axes = player.dice_faces.count("FACE_AXE")
    arrows = player.dice_faces.count("FACE_ARROW")
    opp_helmets = opponent.dice_faces.count("FACE_HELMET")
    opp_shields = opponent.dice_faces.count("FACE_SHIELD")
    blocked_hits = min(axes, opp_helmets) + min(arrows, opp_shields)
    total_hits = axes + arrows

    if opponent.tokens >= 2 and total_hits >= 2:
        gp = god_powers.get("GP_HEIMDALLRS_WATCH")
        if gp and "GP_HEIMDALLRS_WATCH" in player.gp_loadout and blocked_hits >= 1:
            for t in (2, 1, 0):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_HEIMDALLRS_WATCH", t)

    if opponent.tokens >= 4:
        gp = god_powers.get("GP_FENRIRS_BITE")
        if gp and "GP_FENRIRS_BITE" in player.gp_loadout:
            for t in (2, 1, 0):
                if player.tokens >= gp.tiers[t].cost:
                    return ("GP_FENRIRS_BITE", t)

    gp = god_powers.get("GP_SURTRS_FLAME")
    if gp and "GP_SURTRS_FLAME" in player.gp_loadout and (total_hits >= 2 or opponent.hp <= 8):
        for t in (2, 1, 0):
            if player.tokens >= gp.tiers[t].cost:
                return ("GP_SURTRS_FLAME", t)

    gp = god_powers.get("GP_HEIMDALLRS_WATCH")
    if gp and "GP_HEIMDALLRS_WATCH" in player.gp_loadout and blocked_hits >= 2:
        for t in (2, 1, 0):
            if player.tokens >= gp.tiers[t].cost:
                return ("GP_HEIMDALLRS_WATCH", t)
    return None


def _e8_reactive_frigg_gp(state, player_num: int, god_powers: dict) -> tuple[str, int] | None:
    player = state.p1 if player_num == 1 else state.p2
    opponent = state.p2 if player_num == 1 else state.p1
    opp_axes = opponent.dice_faces.count("FACE_AXE")
    opp_arrows = opponent.dice_faces.count("FACE_ARROW")
    player_helmets = player.dice_faces.count("FACE_HELMET")
    player_shields = player.dice_faces.count("FACE_SHIELD")
    opp_damage = max(0, opp_axes - player_helmets) + max(0, opp_arrows - player_shields)
    player_hands = player.dice_faces.count("FACE_HAND") + player.dice_faces.count("FACE_HAND_BORDERED")

    if "GP_FRIGGS_VEIL" in player.gp_loadout:
        gp = god_powers.get("GP_FRIGGS_VEIL")
        if gp and player.tokens >= gp.tiers[0].cost:
            if (
                "GP_SKADIS_VOLLEY" in opponent.gp_loadout
                or "GP_ODINS_INSIGHT" in opponent.gp_loadout
                or "GP_HEIMDALLRS_WATCH" in opponent.gp_loadout
            ):
                if opponent.tokens >= 5 or opp_damage >= 2:
                    return ("GP_FRIGGS_VEIL", 0)

    if "GP_MJOLNIRS_WRATH" in player.gp_loadout:
        gp = god_powers.get("GP_MJOLNIRS_WRATH")
        if gp and player.tokens >= gp.tiers[0].cost:
            if opponent.hp <= 8 or player.tokens >= 8:
                return ("GP_MJOLNIRS_WRATH", 0)

    if "GP_FREYAS_BLESSING" in player.gp_loadout:
        gp = god_powers.get("GP_FREYAS_BLESSING")
        if gp and player.tokens >= gp.tiers[0].cost and player_hands >= 2:
            return ("GP_FREYAS_BLESSING", 0)

    if "GP_MJOLNIRS_WRATH" in player.gp_loadout:
        gp = god_powers.get("GP_MJOLNIRS_WRATH")
        if gp and player.tokens >= gp.tiers[0].cost:
            return ("GP_MJOLNIRS_WRATH", 0)

    return None

ARCHETYPES = ("AGGRO", "CONTROL", "ECONOMY", "COMBO")
RECOMMENDED_PROFILE_ID = "MIXED_A"
RECOMMENDED_BASELINE_IDS = {
    "AGGRO": "A_CAN4",
    "CONTROL": "C_CAN4",
    "ECONOMY": "E_CAN1",
    "COMBO": "CO_CAN4",
}
_CANDIDATES: dict[str, list["CanonicalCandidate"]] = {}
_PROFILES: dict[str, "TuningProfile"] = {}


@dataclass(frozen=True)
class CanonicalCandidate:
    id: str
    archetype: str
    name: str
    agent_cls: type
    agent_kwargs: dict
    dice_loadout: list[str]
    gp_loadout: tuple[str, ...]


@dataclass
class MatchupStats:
    decisive_win_rate: float
    avg_rounds: float
    draw_rate: float


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


@dataclass(frozen=True)
class TuningProfile:
    id: str
    description: str
    aegis_t1_block: int = 3
    frigg_t1_cost: int = 6
    mjolnir_t1_cost: int = 6
    mjolnir_t1_damage: int = 4
    freyja_token_gains: tuple[int, int, int] = (3, 5, 8)
    heimdallr_t1_cost: int = 4
    skadi_t1_cost: int = 5
    surtr_t1_damage: int = 2
    fenrir_t1_cost: int = 5
    enable_token_shield: bool = True
    steal_hp_penalty_threshold: int | None = None
    steal_hp_penalty: int = 0


def _build_tuning_profiles() -> dict[str, TuningProfile]:
    if _PROFILES:
        return _PROFILES

    profiles = {
        "BASE": TuningProfile(
            id="BASE",
            description="Current GP values.",
        ),
        "CTRL_RELIEF": TuningProfile(
            id="CTRL_RELIEF",
            description="Slightly stronger early Control tools.",
            aegis_t1_block=4,
            frigg_t1_cost=5,
        ),
        "ECON_SOFTEN": TuningProfile(
            id="ECON_SOFTEN",
            description="Slightly slower/fairer early Economy cashout.",
            mjolnir_t1_cost=7,
            freyja_token_gains=(2, 4, 7),
        ),
        "MIXED_A": TuningProfile(
            id="MIXED_A",
            description="Stronger Control answers and softer Economy ramp.",
            aegis_t1_block=4,
            frigg_t1_cost=5,
            mjolnir_t1_cost=7,
            freyja_token_gains=(2, 4, 7),
        ),
        "MIXED_B": TuningProfile(
            id="MIXED_B",
            description="Mixed tuning plus slightly weaker early Mjolnir burst.",
            aegis_t1_block=4,
            frigg_t1_cost=5,
            mjolnir_t1_cost=7,
            mjolnir_t1_damage=3,
            freyja_token_gains=(2, 4, 7),
        ),
        "MIXED_C": TuningProfile(
            id="MIXED_C",
            description="Control relief with damage-softened Mjolnir.",
            aegis_t1_block=4,
            frigg_t1_cost=5,
            mjolnir_t1_damage=3,
            freyja_token_gains=(2, 4, 7),
        ),
        "BALANCED_V1": TuningProfile(
            id="BALANCED_V1",
            description="Best current mixed-loadout balance candidate.",
            aegis_t1_block=4,
            frigg_t1_cost=5,
            mjolnir_t1_cost=8,
            mjolnir_t1_damage=4,
            freyja_token_gains=(2, 4, 7),
            heimdallr_t1_cost=4,
            skadi_t1_cost=7,
            surtr_t1_damage=3,
            fenrir_t1_cost=4,
            enable_token_shield=True,
            steal_hp_penalty_threshold=3,
            steal_hp_penalty=1,
        ),
    }
    _PROFILES.update(profiles)
    return profiles


def _tuned_god_powers(profile: TuningProfile) -> dict[str, GodPower]:
    god_powers = load_god_powers()

    aegis = god_powers["GP_AEGIS_OF_BALDR"]
    aegis_tiers = list(aegis.tiers)
    aegis_tiers[0] = replace(aegis_tiers[0], block_amount=profile.aegis_t1_block)
    god_powers[aegis.id] = replace(aegis, tiers=tuple(aegis_tiers))

    frigg = god_powers["GP_FRIGGS_VEIL"]
    frigg_tiers = list(frigg.tiers)
    frigg_tiers[0] = replace(frigg_tiers[0], cost=profile.frigg_t1_cost)
    god_powers[frigg.id] = replace(frigg, tiers=tuple(frigg_tiers))

    mjolnir = god_powers["GP_MJOLNIRS_WRATH"]
    mjolnir_tiers = list(mjolnir.tiers)
    mjolnir_tiers[0] = replace(
        mjolnir_tiers[0],
        cost=profile.mjolnir_t1_cost,
        damage=profile.mjolnir_t1_damage,
    )
    god_powers[mjolnir.id] = replace(mjolnir, tiers=tuple(mjolnir_tiers))

    freyja = god_powers["GP_FREYAS_BLESSING"]
    freyja_tiers = list(freyja.tiers)
    for idx, gain in enumerate(profile.freyja_token_gains):
        freyja_tiers[idx] = replace(freyja_tiers[idx], token_gain=gain)
    god_powers[freyja.id] = replace(freyja, tiers=tuple(freyja_tiers))

    heimdallr = god_powers["GP_HEIMDALLRS_WATCH"]
    heimdallr_tiers = list(heimdallr.tiers)
    heimdallr_tiers[0] = replace(heimdallr_tiers[0], cost=profile.heimdallr_t1_cost)
    god_powers[heimdallr.id] = replace(heimdallr, tiers=tuple(heimdallr_tiers))

    skadi = god_powers["GP_SKADIS_VOLLEY"]
    skadi_tiers = list(skadi.tiers)
    skadi_tiers[0] = replace(skadi_tiers[0], cost=profile.skadi_t1_cost)
    god_powers[skadi.id] = replace(skadi, tiers=tuple(skadi_tiers))

    surtr = god_powers["GP_SURTRS_FLAME"]
    surtr_tiers = list(surtr.tiers)
    surtr_tiers[0] = replace(surtr_tiers[0], damage=profile.surtr_t1_damage)
    god_powers[surtr.id] = replace(surtr, tiers=tuple(surtr_tiers))

    fenrir = god_powers["GP_FENRIRS_BITE"]
    fenrir_tiers = list(fenrir.tiers)
    fenrir_tiers[0] = replace(fenrir_tiers[0], cost=profile.fenrir_t1_cost)
    god_powers[fenrir.id] = replace(fenrir, tiers=tuple(fenrir_tiers))

    return god_powers


def _build_candidates() -> dict[str, list[CanonicalCandidate]]:
    if _CANDIDATES:
        return _CANDIDATES

    candidates = {
        "AGGRO": [
            CanonicalCandidate(
                id="A_CAN1",
                archetype="AGGRO",
                name="Berserker Blitz Smart",
                agent_cls=AggroAgent,
                agent_kwargs={"gp_select_fn": _aggro_gp_select},
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_GAMBLER"] * 2,
                gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
            ),
            CanonicalCandidate(
                id="A_CAN2",
                archetype="AGGRO",
                name="Tyr Pressure",
                agent_cls=AggroAgent,
                agent_kwargs={
                    "gp_priority": ("GP_TYRS_JUDGMENT", "GP_SURTRS_FLAME", "GP_FENRIRS_BITE"),
                    "tier_order": (0, 1, 2),
                },
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_TYRS_JUDGMENT", "GP_SURTRS_FLAME", "GP_FENRIRS_BITE"),
            ),
            CanonicalCandidate(
                id="A_CAN3",
                archetype="AGGRO",
                name="Warrior Blitz",
                agent_cls=AggroAgent,
                agent_kwargs={"gp_select_fn": _aggro_gp_select},
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
            ),
            CanonicalCandidate(
                id="A_CAN4",
                archetype="AGGRO",
                name="Balanced Blitz",
                agent_cls=AggroAgent,
                agent_kwargs={"gp_select_fn": _aggro_gp_select},
                dice_loadout=["DIE_BERSERKER"] * 3 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
            ),
            CanonicalCandidate(
                id="A_CAN5",
                archetype="AGGRO",
                name="Economy Punish",
                agent_cls=AggroAgent,
                agent_kwargs={
                    "gp_select_fn": _a5_bank_breaker_gp,
                },
                dice_loadout=["DIE_BERSERKER"] * 4 + ["DIE_GAMBLER"] + ["DIE_WARRIOR"],
                gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
            ),
            CanonicalCandidate(
                id="A_CAN6",
                archetype="AGGRO",
                name="Crackdown Blitz",
                agent_cls=AggroAgent,
                agent_kwargs={"gp_select_fn": _a6_econ_crack_gp},
                dice_loadout=["DIE_BERSERKER"] * 3 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_SURTRS_FLAME", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
            ),
        ],
        "CONTROL": [
            CanonicalCandidate(
                id="C_CAN1",
                archetype="CONTROL",
                name="Tyr Wall",
                agent_cls=ControlAgent,
                agent_kwargs={},
                dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"],
                gp_loadout=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_TYRS_JUDGMENT"),
            ),
            CanonicalCandidate(
                id="C_CAN2",
                archetype="CONTROL",
                name="Frigg Guard",
                agent_cls=ControlAgent,
                agent_kwargs={"gp_select_fn": _control_gp_select},
                dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"],
                gp_loadout=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_FRIGGS_VEIL"),
            ),
            CanonicalCandidate(
                id="C_CAN3",
                archetype="CONTROL",
                name="Sustain Guard",
                agent_cls=ControlAgent,
                agent_kwargs={
                    "keep_faces": frozenset({"FACE_HELMET", "FACE_SHIELD", "FACE_HAND_BORDERED"}),
                    "gp_select_fn": _control_gp_select,
                },
                dice_loadout=["DIE_WARDEN"] * 3 + ["DIE_SKALD"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_EIRS_MERCY", "GP_AEGIS_OF_BALDR", "GP_FRIGGS_VEIL"),
            ),
            CanonicalCandidate(
                id="C_CAN4",
                archetype="CONTROL",
                name="Frigg Midwall",
                agent_cls=ControlAgent,
                agent_kwargs={"gp_select_fn": _control_gp_select},
                dice_loadout=["DIE_WARDEN"] * 2 + ["DIE_WARRIOR"] * 2 + ["DIE_SKALD"] * 2,
                gp_loadout=("GP_AEGIS_OF_BALDR", "GP_EIRS_MERCY", "GP_FRIGGS_VEIL"),
            ),
        ],
        "ECONOMY": [
            CanonicalCandidate(
                id="E_CAN1",
                archetype="ECONOMY",
                name="Hoard Smooth",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "gp_priority": ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
                    "tier_order": (0, 1, 2),
                    "token_threshold": 4,
                    "frigg_threshold": 7,
                },
                dice_loadout=["DIE_MISER"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_WARDEN"],
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
            ),
            CanonicalCandidate(
                id="E_CAN2",
                archetype="ECONOMY",
                name="Defensive Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "gp_select_fn": _economy_gp_select,
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_HAND", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                },
                dice_loadout=["DIE_MISER"] * 3 + ["DIE_WARDEN"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_AEGIS_OF_BALDR"),
            ),
            CanonicalCandidate(
                id="E_CAN3",
                archetype="ECONOMY",
                name="Skald Hoard Trimmed",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET"}
                    ),
                    "gp_priority": ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
                    "tier_order": (0, 1, 2),
                    "token_threshold": 4,
                    "frigg_threshold": 8,
                },
                dice_loadout=["DIE_SKALD"] * 3 + ["DIE_MISER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
            ),
            CanonicalCandidate(
                id="E_CAN4",
                archetype="ECONOMY",
                name="Skald Tempo Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "gp_select_fn": _economy_gp_select,
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET"}
                    ),
                    "gp_priority": ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
                    "tier_order": (0, 1, 2),
                    "token_threshold": 4,
                    "frigg_threshold": 8,
                },
                dice_loadout=["DIE_SKALD"] * 3 + ["DIE_MISER"] + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
            ),
            CanonicalCandidate(
                id="E_CAN5",
                archetype="ECONOMY",
                name="Tempered Skald Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET"}
                    ),
                    "gp_priority": ("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
                    "tier_order": (0, 1, 2),
                    "token_threshold": 4,
                    "frigg_threshold": 8,
                },
                dice_loadout=["DIE_SKALD"] * 2 + ["DIE_MISER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
            ),
            CanonicalCandidate(
                id="E_CAN6",
                archetype="ECONOMY",
                name="Tempered Guard Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "gp_select_fn": _economy_gp_select,
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                },
                dice_loadout=["DIE_SKALD"] * 2 + ["DIE_MISER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_AEGIS_OF_BALDR"),
            ),
            CanonicalCandidate(
                id="E_CAN7",
                archetype="ECONOMY",
                name="Active Guard Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "gp_select_fn": _economy_gp_select,
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD"}
                    ),
                },
                dice_loadout=["DIE_SKALD"] * 3 + ["DIE_WARRIOR"] * 2 + ["DIE_MISER"],
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_AEGIS_OF_BALDR"),
            ),
            CanonicalCandidate(
                id="E_CAN8",
                archetype="ECONOMY",
                name="Reactive Frigg Bank",
                agent_cls=EconomyAgent,
                agent_kwargs={
                    "gp_select_fn": _e8_reactive_frigg_gp,
                    "keep_faces": frozenset(
                        {"FACE_HAND_BORDERED", "FACE_AXE", "FACE_ARROW", "FACE_HELMET"}
                    ),
                },
                dice_loadout=["DIE_SKALD"] * 2 + ["DIE_MISER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_MJOLNIRS_WRATH", "GP_FREYAS_BLESSING", "GP_FRIGGS_VEIL"),
            ),
        ],
        "COMBO": [
            CanonicalCandidate(
                id="CO_CAN1",
                archetype="COMBO",
                name="Odin Burst",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "gp_select_fn": _co6_odin_burst_gp,
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"}),
                },
                dice_loadout=["DIE_HUNTER"] * 3 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"],
                gp_loadout=("GP_ODINS_INSIGHT", "GP_SKADIS_VOLLEY", "GP_HEIMDALLRS_WATCH"),
            ),
            CanonicalCandidate(
                id="CO_CAN2",
                archetype="COMBO",
                name="Volley Smart",
                agent_cls=ComboAgent,
                agent_kwargs={"gp_select_fn": _combo_gp_select, "min_arrows_for_skadi": 2},
                dice_loadout=["DIE_HUNTER"] * 4 + ["DIE_GAMBLER"] * 2,
                gp_loadout=("GP_SKADIS_VOLLEY", "GP_NJORDS_TIDE", "GP_ODINS_INSIGHT"),
            ),
            CanonicalCandidate(
                id="CO_CAN3",
                archetype="COMBO",
                name="Arrow Bleed",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_HAND"}),
                    "gp_priority": ("GP_SKADIS_VOLLEY", "GP_FENRIRS_BITE", "GP_NJORDS_TIDE"),
                    "tier_order": (0, 1, 2),
                    "min_arrows_for_skadi": 2,
                },
                dice_loadout=["DIE_HUNTER"] * 4 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_SKADIS_VOLLEY", "GP_FENRIRS_BITE", "GP_NJORDS_TIDE"),
            ),
            CanonicalCandidate(
                id="CO_CAN4",
                archetype="COMBO",
                name="Bridge Burst",
                agent_cls=ComboAgent,
                agent_kwargs={
                    "gp_select_fn": _co4_bridge_burst_gp,
                    "keep_faces": frozenset({"FACE_ARROW", "FACE_HAND_BORDERED", "FACE_AXE"}),
                },
                dice_loadout=["DIE_HUNTER"] * 2 + ["DIE_GAMBLER"] * 2 + ["DIE_WARRIOR"] * 2,
                gp_loadout=("GP_SKADIS_VOLLEY", "GP_FENRIRS_BITE", "GP_HEIMDALLRS_WATCH"),
            ),
        ],
    }
    _CANDIDATES.update(candidates)
    return candidates


def _candidate_by_id(
    candidates: dict[str, list[CanonicalCandidate]],
    archetype: str,
    candidate_id: str,
) -> CanonicalCandidate:
    return next(c for c in candidates[archetype] if c.id == candidate_id)


def _make_package(
    ids: dict[str, str],
    candidates: dict[str, list[CanonicalCandidate]],
) -> dict[str, CanonicalCandidate]:
    return {
        arch: _candidate_by_id(candidates, arch, ids[arch])
        for arch in ARCHETYPES
    }


def _engine_kwargs_for_profile(profile: TuningProfile | None) -> dict:
    if profile is None:
        return {}
    return {
        "enable_token_shield": profile.enable_token_shield,
        "steal_hp_penalty_threshold": profile.steal_hp_penalty_threshold,
        "steal_hp_penalty": profile.steal_hp_penalty,
    }


def _run_package(
    package: dict[str, CanonicalCandidate],
    n_games: int,
    seed: int,
    god_powers: dict[str, GodPower] | None = None,
    profile: TuningProfile | None = None,
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
    candidates: dict[str, list[CanonicalCandidate]],
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
        row = [
            matchup_stats[(arch, opp)].decisive_win_rate
            for opp in ARCHETYPES
            if opp != arch
        ]
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
    profile_ids: tuple[str, ...] = ("BASE",),
) -> list[PackageScore]:
    candidates = _build_candidates()
    profiles = _build_tuning_profiles()
    scores: list[PackageScore] = []
    for profile_id in profile_ids:
        profile = profiles[profile_id]
        for picks in product(*(candidates[arch] for arch in ARCHETYPES)):
            ids = {cand.archetype: cand.id for cand in picks}
            scores.append(
                _score_package(ids, candidates, n_games=n_games, seed=seed, profile=profile)
            )
    scores.sort(key=lambda s: s.objective)
    return scores


def list_profiles() -> list[str]:
    return sorted(_build_tuning_profiles())


def print_search(scores: list[PackageScore], top: int) -> None:
    print("\nBest canonical-loadout packages")
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
    print("\nCanonical package validation\n")
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
        vals = [
            score.matchup_stats[(row, col)].decisive_win_rate
            for col in ARCHETYPES
        ]
        print(
            f"{row:<14} "
            f"{vals[0]:>7.1%} {vals[1]:>8.1%} {vals[2]:>8.1%} {vals[3]:>8.1%}"
        )


def main() -> None:
    profiles = _build_tuning_profiles()
    parser = argparse.ArgumentParser(description="Search mixed-loadout canonical packages.")
    parser.add_argument("--games", type=int, default=40, help="Games per matchup during search/validation.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed.")
    parser.add_argument("--top", type=int, default=8, help="Number of top search results to print.")
    parser.add_argument(
        "--tune-profile",
        type=str,
        default=RECOMMENDED_PROFILE_ID,
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
        help="Comma-separated package IDs, e.g. A_CAN1,C_CAN1,E_CAN3,CO_CAN1",
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
