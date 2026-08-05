"""sources/custom.py — Custom event normalizer.

Converts arbitrary webhook payloads into canonical Signal format
using tenant-defined mapping configuration.
"""

from __future__ import annotations

from typing import Any


def normalize(event_type: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Convert custom event to canonical Signal format.

    For custom events, the tenant defines the mapping via webhook config:
    {
        "payload_path": "data.user_count",    # dot-notation path to value
        "metric_name": "tenant.user.count",   # signal metric name
        "value_type": "int",                   # float, int, bool
        "value_transform": null                # abs, log, normalize, or null
    }

    Returns: {metric_name, value, timestamp, metadata} or None if mapping missing.
    """

    # Get the tenant's custom mapping from the payload
    mapping = payload.get("mapping") or {}
    if not mapping:
        # Fallback: use top-level fields directly
        mapping = {
            "payload_path": "value",
            "metric_name": event_type or "custom.event",
            "value_type": "float",
        }

    # Extract value from payload using dot-notation path
    payload_path = mapping.get("payload_path", "value")
    value = _get_nested_value(payload, payload_path)
    if value is None:
        return None

    # Transform value
    value_type = mapping.get("value_type", "float")
    value_transform = mapping.get("value_transform")

    value = _convert_type(value, value_type)
    value = _apply_transform(value, value_transform)

    if value is None:
        return None

    # Use configured metric name or event_type
    metric_name = mapping.get("metric_name") or f"custom.{event_type}"
    timestamp = payload.get("timestamp") or payload.get("ts")

    return {
        "metric_name": metric_name,
        "value": value,
        "timestamp": timestamp,
        "metadata": {
            "event_type": event_type,
            "source": "custom",
            "original_payload_size": len(str(payload)),
        },
    }


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    """Get a nested value using dot-notation path (e.g., 'data.user.count')."""
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _convert_type(value: Any, value_type: str) -> float | None:
    """Convert value to the specified type."""
    try:
        if value_type == "int":
            return float(int(value))
        elif value_type == "float":
            return float(value)
        elif value_type == "bool":
            return 1.0 if value else 0.0
    except (ValueError, TypeError):
        return None
    return None


def _apply_transform(value: float | None, transform: str | None) -> float | None:
    """Apply value transformation."""
    if value is None:
        return None
    if transform is None:
        return value
    if transform == "abs":
        return abs(value)
    elif transform == "log":
        import math
        return math.log(value) if value > 0 else 0.0
    elif transform == "normalize":
        # Placeholder: actual normalization requires baseline tracking
        return value
    return value
