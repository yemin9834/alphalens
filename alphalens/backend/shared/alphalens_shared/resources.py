"""Load bundled JSON data files."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


def _data_dir() -> Path:
    pkg = Path(__file__).resolve().parent
    for candidate in (pkg / "data", pkg.parent / "data"):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("AlphaLens shared data directory not found")


@lru_cache(maxsize=8)
def load_json(filename: str) -> Dict[str, Any]:
    path = _data_dir() / filename
    return json.loads(path.read_text(encoding="utf-8"))
