"""JSON helpers safe for AWS Lambda (no NaN/Infinity)."""

from __future__ import annotations

import json
import math
import numbers
from typing import Any


def sanitize_for_json(value: Any) -> Any:
    """Recursively replace NaN/Inf and numpy/pandas scalars with JSON-safe values."""
    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    # numpy.float64, Decimal, etc.
    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return None
        return f

    # numpy / pandas scalar types
    if hasattr(value, "item") and callable(value.item):
        try:
            return sanitize_for_json(value.item())
        except (TypeError, ValueError):
            pass

    if isinstance(value, dict):
        return {str(k): sanitize_for_json(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [sanitize_for_json(v) for v in value]

    return value


def dumps_json(payload: Any) -> str:
    """Serialize payload for Lambda invoke / API responses."""
    return json.dumps(sanitize_for_json(payload))
