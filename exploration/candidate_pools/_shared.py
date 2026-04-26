"""Shared helpers for realistic exploration candidate pools."""

from __future__ import annotations

from game_mechanics.god_powers import GodPower, load_god_powers

_GOD_POWERS = load_god_powers()
SPECIALIST_LABELS = {
    "DIE_BERSERKER": "Berserker",
    "DIE_WARDEN": "Warden",
    "DIE_MISER": "Miser",
    "DIE_GAMBLER": "Gambler",
    "DIE_SKALD": "Skald",
    "DIE_HUNTER": "Hunter",
}

GP_CODE = {
    "GP_SURTRS_FLAME": "SU",
    "GP_FENRIRS_BITE": "FE",
    "GP_AEGIS_OF_BALDR": "AE",
    "GP_EIRS_MERCY": "EI",
    "GP_BRAGIS_SONG": "BR",
    "GP_GULLVEIGS_HOARD": "GU",
    "GP_TYRS_JUDGMENT": "TY",
    "GP_FRIGGS_VEIL": "FR",
    "GP_MJOLNIRS_WRATH": "MJ",
}

def gp_combo_suffix(gp_ids: tuple[str, str, str]) -> str:
    """Encode one GP trio as a short stable suffix."""
    return "G" + "".join(GP_CODE[gp_id] for gp_id in gp_ids)


def gp_combo_summary(gp_ids: tuple[str, str, str], god_powers: dict[str, GodPower] | None = None) -> str:
    """Render a readable GP trio summary."""
    god_powers = god_powers if god_powers is not None else _GOD_POWERS
    return " / ".join(god_powers[gp_id].display_name for gp_id in gp_ids)


def specialist_summary(extra_dice: tuple[str, ...]) -> str:
    """Render the specialist dice after the fixed 3-Warrior shell."""
    return "3 Warrior + " + " + ".join(SPECIALIST_LABELS[die_id] for die_id in extra_dice)
