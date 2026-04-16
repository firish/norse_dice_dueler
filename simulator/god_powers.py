"""
god_powers.py
-------------
GodPower definitions loaded from /data/god_powers.json.

Each GodPower has 3 tiers with escalating cost and effect.
Effect-specific fields (damage, self_damage, arrow_bonus, dmg_min/max) are
loaded from the JSON and used by the engine during GOD_RESOLVE.

L1 scope: 4 offensive GPs implemented (Fenrir's Bite deferred to L2).
    GP_MJOLNIRS_WRATH  - direct damage
    GP_SKADIS_VOLLEY   - bonus damage per unblocked arrow
    GP_SURTRS_FLAME    - direct damage + self damage
    GP_LOKIS_GAMBIT    - random damage in a range

All other GPs are loaded from JSON but their effects are no-ops until
the layer that implements them.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"

# GPs active at L1. Engine will resolve these; all others are skipped.
L1_OFFENSIVE_GP_IDS: frozenset[str] = frozenset({
    "GP_MJOLNIRS_WRATH",
    "GP_SKADIS_VOLLEY",
    "GP_SURTRS_FLAME",
    "GP_LOKIS_GAMBIT",
})


@dataclass(frozen=True)
class GodPowerTier:
    """One tier of a God Power.

    Example (Mjölnir's Wrath T1):
        GodPowerTier(
            tier="T1", cost=6, effect="Deal 2 direct damage...",
            damage=2, self_damage=0, arrow_bonus=0, dmg_min=0, dmg_max=0,
        )
    """
    tier: str           # "T1", "T2", "T3"
    cost: int           # token cost to activate
    effect: str         # human-readable description (for UI / tooltips)
    damage: float       # direct damage dealt to opponent (0 if N/A)
    self_damage: int    # damage dealt to self (Surtr's Flame only; 0 otherwise)
    arrow_bonus: int    # bonus damage per unblocked arrow (Skaði only; 0 otherwise)
    dmg_min: int        # minimum random damage (Loki only; 0 otherwise)
    dmg_max: int        # maximum random damage (Loki only; 0 otherwise)


@dataclass(frozen=True)
class GodPower:
    """A single God Power with 3 tiers, loaded from god_powers.json.

    Example (Surtr's Flame):
        GodPower(
            id="GP_SURTRS_FLAME",
            display_name="Surtr's Flame",
            category="Offense",
            tiers=(GodPowerTier(...T1), GodPowerTier(...T2), GodPowerTier(...T3)),
        )

    Access tiers by 0-based index: gp.tiers[0] = T1, gp.tiers[2] = T3.
    """
    id: str
    display_name: str
    category: str       # "Offense", "Defense", "Utility", "Hybrid"
    tiers: tuple[GodPowerTier, ...]   # always length 3


def _parse_tier(raw: dict) -> GodPowerTier:
    """Convert one tier dict from JSON into a GodPowerTier."""
    return GodPowerTier(
        tier=raw["tier"],
        cost=raw["cost"],
        effect=raw["effect"],
        damage=float(raw.get("damage") or 0),
        self_damage=int(raw.get("self_damage") or 0),
        arrow_bonus=int(raw.get("arrow_bonus") or 0),
        dmg_min=int(raw.get("dmg_min") or 0),
        dmg_max=int(raw.get("dmg_max") or 0),
    )


def load_god_powers(path: pathlib.Path | None = None) -> dict[str, GodPower]:
    """Load all God Powers from JSON. Returns {gp_id: GodPower}.

    Input:  path to god_powers.json (defaults to /data/god_powers.json)
    Output: {"GP_MJOLNIRS_WRATH": GodPower(...), "GP_FENRIRS_BITE": GodPower(...), ...}
    """
    path = path or _DATA_DIR / "god_powers.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        gp["id"]: GodPower(
            id=gp["id"],
            display_name=gp["display_name"],
            category=gp["category"],
            tiers=tuple(_parse_tier(t) for t in gp["tiers"]),
        )
        for gp in raw
    }
