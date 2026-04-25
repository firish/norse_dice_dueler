"""Helpers for reasoning about equipped God Powers and archetype fit."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from game_mechanics.god_powers import GodPower

ARCHETYPE_ORDER: tuple[str, ...] = ("AGGRO", "CONTROL", "ECONOMY")
ROLE_ARCHETYPE_BIAS: dict[str, dict[str, float]] = {
    "burst": {"AGGRO": 0.25},
    "finisher": {"AGGRO": 0.20, "ECONOMY": 0.15},
    "block": {"CONTROL": 0.25},
    "heal": {"CONTROL": 0.25},
    "ramp": {"ECONOMY": 0.25},
    "anti_race": {"CONTROL": 0.10, "ECONOMY": 0.15},
    "counter": {"AGGRO": 0.05, "CONTROL": 0.10, "ECONOMY": 0.05},
    "hybrid_pressure": {"AGGRO": 0.10, "CONTROL": 0.10, "ECONOMY": 0.05},
}


def equipped_gp_ids(player, god_powers: Mapping[str, GodPower]) -> tuple[str, ...]:
    """Return the equipped GP ids that exist in the current GP ruleset."""
    return tuple(gp_id for gp_id in player.gp_loadout if gp_id in god_powers)


def equipped_gp_ids_matching(
    player,
    god_powers: Mapping[str, GodPower],
    *,
    primary_roles: Iterable[str] = (),
    tags: Iterable[str] = (),
    allowed_archetypes: Iterable[str] = (),
) -> tuple[str, ...]:
    """Return equipped GPs matching any requested role/tag/archetype filter."""
    role_set = tuple(primary_roles)
    tag_set = tuple(tags)
    archetype_set = tuple(allowed_archetypes)
    matches: list[str] = []
    for gp_id in equipped_gp_ids(player, god_powers):
        gp = god_powers[gp_id]
        role_or_tag_match = not role_set and not tag_set
        if not role_or_tag_match:
            role_or_tag_match = gp.matches_role_or_tag(primary_roles=role_set, tags=tag_set)
        archetype_match = not archetype_set or any(gp.is_allowed_for(arch) for arch in archetype_set)
        if role_or_tag_match and archetype_match:
            matches.append(gp_id)
    return tuple(matches)


def merge_gp_priority_groups(*groups: Iterable[str]) -> tuple[str, ...]:
    """Merge GP id lists while preserving order and removing duplicates."""
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for gp_id in group:
            if gp_id not in seen:
                seen.add(gp_id)
                merged.append(gp_id)
    return tuple(merged)


def minimum_tier_cost(
    gp_ids: Iterable[str],
    god_powers: Mapping[str, GodPower],
    *,
    tier_order: Iterable[int] = (0,),
) -> int | None:
    """Return the cheapest listed tier cost across a GP subset."""
    costs: list[int] = []
    tiers = tuple(tier_order)
    for gp_id in gp_ids:
        gp = god_powers.get(gp_id)
        if gp is None:
            continue
        for tier_idx in tiers:
            costs.append(gp.tiers[tier_idx].cost)
    return min(costs) if costs else None


def infer_archetype_from_gp_loadout(
    gp_loadout: Iterable[str],
    god_powers: Mapping[str, GodPower],
) -> str:
    """Infer the most likely archetype from an equipped GP loadout."""
    scores = {arch: 0.0 for arch in ARCHETYPE_ORDER}
    for gp_id in gp_loadout:
        gp = god_powers.get(gp_id)
        if gp is None:
            continue
        allowed = gp.allowed_archetypes or ARCHETYPE_ORDER
        share = 1.0 / len(allowed)
        for arch in allowed:
            scores[arch] += share
        for arch, bias in ROLE_ARCHETYPE_BIAS.get(gp.primary_role, {}).items():
            scores[arch] += bias
    return max(ARCHETYPE_ORDER, key=lambda arch: (scores[arch], -ARCHETYPE_ORDER.index(arch)))
