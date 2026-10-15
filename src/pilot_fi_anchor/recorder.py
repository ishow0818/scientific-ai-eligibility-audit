"""Per-seed JSON records (schema in EXPERIMENT_DESIGN.md 7)."""

from __future__ import annotations

import json
import os
from typing import Any

import numpy as np

from .config import PilotConfig


def _builtin(o: Any) -> Any:
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, dict):
        return {k: _builtin(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_builtin(v) for v in o]
    return o


def seed_record(seed: int, rec: dict[str, Any], cfg: PilotConfig) -> dict[str, Any]:
    return {"seed": seed, "version": cfg.version, "config": cfg.to_dict(), **rec}


def write_seed(record: dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_builtin(record), f, separators=(",", ":"))


def read_seed(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
