from __future__ import annotations

def build_context(context: dict | None = None) -> str:
    """
    Builds a deterministic context string from context selectors.
    """
    if not context:
        return "No context provided."

    parts = []
    for key in sorted(context):
        value = context[key]
        parts.append(f"{key}: {value}")

    return "\n".join(parts)
