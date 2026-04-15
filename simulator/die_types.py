"""
die_types.py
------------
DieType definitions loaded from /data/dice_types.json.

Each die is represented as an expanded face list of length 6 (e.g., Huskarl's Die
→ ["FACE_AXE", "FACE_ARROW", "FACE_HELMET", "FACE_SHIELD", "FACE_HAND", "FACE_HAND_BORDERED"]).
Rolling a die = uniform sample from this list.

All balance numbers come from the JSON file — never hardcoded here.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass

# Maps dice_types.json face keys → canonical face IDs used in game logic.
_FACE_KEY_TO_ID: dict[str, str] = {
    "axe":           "FACE_AXE",
    "arrow":         "FACE_ARROW",
    "helmet":        "FACE_HELMET",
    "shield":        "FACE_SHIELD",
    "hand":          "FACE_HAND",
    "bordered_hand": "FACE_HAND_BORDERED",
    # Skill-tree unlocks (L7+); ignored in the face list until activated.
    "wild":          "FACE_WILD",
    "runic":         "FACE_RUNIC",
}

_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


@dataclass(frozen=True)
class DieType:
    id: str
    display_name: str
    faces: tuple[str, ...]   # expanded list, always len == 6
    power_budget: float


def _build_faces(faces_dict: dict[str, int]) -> tuple[str, ...]:
    result: list[str] = []
    for key, face_id in _FACE_KEY_TO_ID.items():
        count = faces_dict.get(key, 0)
        result.extend([face_id] * count)
    if len(result) != 6:
        raise ValueError(
            f"Die face list has {len(result)} faces (expected 6): {faces_dict}"
        )
    return tuple(result)


def load_die_types(path: pathlib.Path | None = None) -> dict[str, DieType]:
    """Load all die types from JSON. Returns {die_id: DieType}."""
    path = path or _DATA_DIR / "dice_types.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        d["id"]: DieType(
            id=d["id"],
            display_name=d["display_name"],
            faces=_build_faces(d["faces"]),
            power_budget=d["power_budget"],
        )
        for d in raw
    }
