"""Small helpers for single-line, machine-readable Task 3 terminal logs."""


def inline_value(value: object, *, limit: int = 300) -> str:
    """Collapse untrusted text so it cannot forge a second terminal event."""
    if limit <= 0:
        raise ValueError("limit must be positive")
    text = " ".join(str(value).split())
    return (text or "unknown")[:limit]


def optional_count(value: int | None) -> str:
    """Render provider metrics consistently when a count is unavailable."""
    return "na" if value is None else str(value)
