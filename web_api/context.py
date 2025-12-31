from __future__ import annotations

def build_context(context: dict | None = None) -> str:
    """
    Builds a context string from a dictionary of context selectors.
    This is a placeholder implementation.
    """
    if not context:
        return "No context provided."

    parts = []
    for key, value in context.items():
        parts.append(f"{key}: {value}")

    return "\n".join(parts)
