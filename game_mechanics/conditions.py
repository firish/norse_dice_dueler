"""Helpers for reading condition metadata and tunable parameters."""

from __future__ import annotations

from functools import lru_cache
import json
import pathlib
from typing import Any

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=1)
def load_conditions() -> dict[str, dict[str, Any]]:
    """Load the condition catalog keyed by condition id."""
    path = DATA_DIR / "conditions.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in raw}


def condition_params(condition_id: str) -> dict[str, Any]:
    """Return the tunable parameter map for one condition id."""
    return dict(load_conditions().get(condition_id, {}).get("params", {}))


def condition_param(condition_id: str, key: str, default: Any) -> Any:
    """Return one condition parameter, falling back to `default` if absent."""
    return condition_params(condition_id).get(key, default)
