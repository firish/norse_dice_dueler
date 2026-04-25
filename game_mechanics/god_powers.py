"""Load structured God Power definitions from ``data/god_powers.json``.

The simulator currently uses a focused nine-power ruleset, but the loader stays
data-driven so future layers can extend the JSON contract without changing the
engine entry points.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"

@dataclass(frozen=True)
class GodPowerTier:
    """One tier of a God Power.

    Example (Mjölnir's Wrath T1):
        GodPowerTier(tier="T1", cost=6, effect="Deal 2 direct damage...",
                     damage=2)
    Example (Vidar's Reflection T3):
        GodPowerTier(tier="T3", cost=12, ..., reflect_pct=1.0, reflect_bonus=1)
    """
    tier: str
    cost: int
    effect: str
    # -- Offense --
    damage: float = 0       # direct damage to opponent
    self_damage: int = 0    # damage to self (Surtr)
    arrow_bonus: int = 0    # bonus per unblocked arrow (Skaði)
    dmg_min: int = 0        # random damage floor (Loki)
    dmg_max: int = 0        # random damage ceiling (Loki)
    # -- Defense --
    block_amount: int = 0   # damage blocked this round (Aegis, Tyr)
    heal: int = 0           # HP restored (Eir, Freyja, Hel's Purge)
    reflect_pct: float = 0  # fraction of GP damage reflected (Vidar)
    reflect_bonus: int = 0  # flat bonus reflected damage (Vidar T3)
    cleanse: bool = False   # remove all bleed/poison (Hel's Purge)
    cancel_gp: bool = False # cancel opponent's GP (Frigg)
    refund_pct: float = 0   # fraction of opponent's tokens refunded on cancel (Frigg)
    steal_tokens: bool = False  # steal opponent's spent GP tokens (Frigg T3)
    # -- Utility --
    token_gain: int = 0     # tokens gained (Freyja, Odin T3, Hel's Purge T3)
    reroll_count: int = 0   # dice to reroll post-combat (Njordr)
    # -- Hybrid --
    unblockable: int = 0    # number of attacks made unblockable (Heimdallr; 99=all)
    damage_reduction: int = 0  # flat damage reduction this round (Heimdallr)


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
    primary_role: str
    tags: tuple[str, ...]
    allowed_archetypes: tuple[str, ...]
    tiers: tuple[GodPowerTier, ...]   # always length 3

    def has_tag(self, tag: str) -> bool:
        """Return whether this GP carries a specific secondary tag."""
        return tag in self.tags

    def matches_role_or_tag(
        self,
        *,
        primary_roles: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> bool:
        """Return whether this GP matches any requested role or secondary tag."""
        return self.primary_role in primary_roles or any(tag in self.tags for tag in tags)

    def is_allowed_for(self, archetype: str) -> bool:
        """Return whether this GP can belong to a named archetype pool."""
        return archetype in self.allowed_archetypes


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
        block_amount=int(raw.get("block_amount") or 0),
        heal=int(raw.get("heal") or 0),
        reflect_pct=float(raw.get("reflect_pct") or 0),
        reflect_bonus=int(raw.get("reflect_bonus") or 0),
        cleanse=bool(raw.get("cleanse", False)),
        cancel_gp=bool(raw.get("cancel_gp", False)),
        refund_pct=float(raw.get("refund_pct") or 0),
        steal_tokens=bool(raw.get("steal_tokens", False)),
        token_gain=int(raw.get("token_gain") or 0),
        reroll_count=int(raw.get("reroll_count") or 0),
        unblockable=int(raw.get("unblockable") or 0),
        damage_reduction=int(raw.get("damage_reduction") or 0),
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
            primary_role=gp.get("primary_role", gp["category"].lower()),
            tags=tuple(gp.get("tags", [])),
            allowed_archetypes=tuple(gp.get("allowed_archetypes", ())),
            tiers=tuple(_parse_tier(t) for t in gp["tiers"]),
        )
        for gp in raw
    }
