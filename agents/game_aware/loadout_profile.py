"""Loadout-aware feature extraction for smarter heuristic agents.

These helpers summarize a player's six equipped dice into stable expected-value
signals. The goal is not to solve the loadout, only to let agents react to
whether they are on a burst-heavy, defensive, or token-rich package.
"""

from __future__ import annotations

from dataclasses import dataclass

from game_mechanics.die_types import DieType, load_die_types

_DIE_TYPES = load_die_types()
_FACES_PER_DIE = 6.0


@dataclass(frozen=True)
class LoadoutProfile:
    """Expected per-roll output and specialist counts for one six-die package."""

    die_ids: tuple[str, ...]
    expected_axes: float
    expected_arrows: float
    expected_helmets: float
    expected_shields: float
    expected_hands: float
    expected_bordered_hands: float
    berserker_count: int
    warden_count: int
    miser_count: int
    gambler_count: int
    skald_count: int
    hunter_count: int

    @property
    def expected_attack(self) -> float:
        return self.expected_axes + self.expected_arrows

    @property
    def expected_block(self) -> float:
        return self.expected_helmets + self.expected_shields

    @property
    def expected_tokens(self) -> float:
        return self.expected_hands + self.expected_bordered_hands

    @property
    def gp_fuel(self) -> float:
        return self.expected_bordered_hands + (0.45 * self.expected_hands)

    @property
    def offense_bias(self) -> float:
        return self.expected_attack - self.expected_block

    @property
    def defense_bias(self) -> float:
        return self.expected_block - self.expected_attack

    @property
    def attack_support(self) -> bool:
        return self.expected_attack >= 2.0

    @property
    def fuel_rich(self) -> bool:
        return self.gp_fuel >= 1.25

    @property
    def light_defense(self) -> bool:
        return self.expected_block < 1.9

    @property
    def heavy_defense(self) -> bool:
        return self.expected_block >= 2.3


def _expected_face_count(die_types: tuple[DieType, ...], face_id: str) -> float:
    """Return expected visible copies of one face per roll across the loadout."""
    total = sum(die.faces.count(face_id) for die in die_types)
    return total / _FACES_PER_DIE


def profile_for_loadout(
    die_ids: tuple[str, ...],
    die_types: dict[str, DieType] | None = None,
) -> LoadoutProfile:
    """Summarize the provided die IDs into expected combat/token output."""
    die_types = die_types if die_types is not None else _DIE_TYPES
    equipped = tuple(die_types[die_id] for die_id in die_ids)
    return LoadoutProfile(
        die_ids=die_ids,
        expected_axes=_expected_face_count(equipped, "FACE_AXE"),
        expected_arrows=_expected_face_count(equipped, "FACE_ARROW"),
        expected_helmets=_expected_face_count(equipped, "FACE_HELMET"),
        expected_shields=_expected_face_count(equipped, "FACE_SHIELD"),
        expected_hands=_expected_face_count(equipped, "FACE_HAND"),
        expected_bordered_hands=_expected_face_count(equipped, "FACE_HAND_BORDERED"),
        berserker_count=die_ids.count("DIE_BERSERKER"),
        warden_count=die_ids.count("DIE_WARDEN"),
        miser_count=die_ids.count("DIE_MISER"),
        gambler_count=die_ids.count("DIE_GAMBLER"),
        skald_count=die_ids.count("DIE_SKALD"),
        hunter_count=die_ids.count("DIE_HUNTER"),
    )
