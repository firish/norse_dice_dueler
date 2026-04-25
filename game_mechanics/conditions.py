"""Helpers for reading condition metadata, approved pairs, and tunable params."""

from __future__ import annotations

import json
import pathlib
from functools import lru_cache
from typing import Any

DATA_DIR = pathlib.Path(__file__).resolve().parent.parent / "data"
CONDITIONS_PATH = DATA_DIR / "conditions.json"
CONDITION_PAIRS_PATH = DATA_DIR / "condition_pairs.json"


@lru_cache(maxsize=1)
def load_condition_list() -> list[dict[str, Any]]:
    """Load the full condition catalog in JSON order."""
    return json.loads(CONDITIONS_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_conditions() -> dict[str, dict[str, Any]]:
    """Load the condition catalog keyed by condition id."""
    return {entry["id"]: entry for entry in load_condition_list()}


@lru_cache(maxsize=1)
def load_condition_pair_config() -> dict[str, Any]:
    """Load the approved and reserve condition-pair pools."""
    return json.loads(CONDITION_PAIRS_PATH.read_text(encoding="utf-8"))


def load_approved_condition_pairs() -> list[tuple[str, str]]:
    """Return the approved unordered condition-pair pool."""
    raw = load_condition_pair_config()
    return [tuple(entry["ids"]) for entry in raw["approved_pairs"]]


def load_reserve_condition_pairs() -> list[tuple[str, str]]:
    """Return the reserve unordered condition-pair pool."""
    raw = load_condition_pair_config()
    return [tuple(entry["ids"]) for entry in raw["reserve_pairs"]]


def condition_params(condition_id: str) -> dict[str, Any]:
    """Return the tunable parameter map for one condition id."""
    return dict(load_conditions().get(condition_id, {}).get("params", {}))


def condition_param(condition_id: str, key: str, default: Any) -> Any:
    """Return one condition parameter, falling back to `default` if absent."""
    return condition_params(condition_id).get(key, default)
