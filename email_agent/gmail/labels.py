"""Gmail label management with normalization.

Provides label normalization using NFKD unicode decomposition to ensure
consistent label naming regardless of how categories are specified in config.

See PLAN.md §8 for label normalization specification.
"""

from __future__ import annotations

import unicodedata

# Characters allowed in Gmail label names (after NFKD normalization)
_ALLOWED_LABEL_CHARS = {" ", "&", "/", "-", "_"}


def normalize_label_name(value: str) -> str:
    """Normalize a label or category name for consistent Gmail matching.

    Applies NFKD unicode normalization, then filters to keep only
    alphanumeric characters and selected punctuation (space, &, /, -, _).
    Result is lowercased and whitespace is collapsed.

    Args:
        value: Raw label name from config or Gmail API.

    Returns:
        Normalized label name safe for Gmail API use.

    Example:
        >>> normalize_label_name("Finance/Tax")
        'finance tax'
        >>> normalize_label_name("Work & Personal")
        'work personal'
        >>> normalize_label_name("IMPORTANT!")
        'important'
    """
    normalized = unicodedata.normalize("NFKD", value)
    cleaned = "".join(c for c in normalized if c.isalnum() or c in _ALLOWED_LABEL_CHARS).lower()
    return " ".join(cleaned.split())


def create_gmail_label_name(category: str) -> str:
    """Convert a config category name to a Gmail-friendly label name.

    Args:
        category: Category name from config.yaml categories list.

    Returns:
        Gmail label name (not normalized - caller decides whether
        to normalize based on use case).
    """
    return category.strip()
