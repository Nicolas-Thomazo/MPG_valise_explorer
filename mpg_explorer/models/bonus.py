"""Bonus domain model and normalization helpers for MPG scraping."""

from enum import Enum
import unicodedata


class BonusName(Enum):
    """
    Enumerate all supported MPG bonus labels.

    Enum values store the canonical display labels as they can appear in MPG.
    """

    zahia: str = "Zahia"
    mcdo: str = "McDo+"
    valise: str = "La Valise à Nanard"
    suarez: str = "Suarez"
    miroir: str = "Miroir"
    cheat_code: str = "Cheat Code 18-26"
    tonton_pat: str = "Tonton Pat'"
    decathlon: str = "Decathlon"
    four_defense: str = "4 défenseurs"
    five_defense: str = "5 défenseurs"
    capitaine: str = "Capitaine"


def get_bonus_name(potential_bonus: str) -> BonusName | None:
    """
    Resolve a raw bonus label to a `BonusName`.

    Matching is accent-insensitive, case-insensitive, and spacing-insensitive,
    so UI variations such as `La valise à Nanard` are accepted.

    Args:
        potential_bonus: Raw bonus label extracted from the UI.

    Returns:
        BonusName | None: Matching enum value, or `None` when unknown.
    """
    normalized_input = _normalize_bonus_label(potential_bonus)

    for bonus in BonusName:
        if normalized_input == _normalize_bonus_label(bonus.value):
            return bonus
    return None


def _normalize_bonus_label(value: str) -> str:
    """
    Normalize a bonus label for robust comparisons.

    Args:
        value: Raw label.

    Returns:
        str: Label normalized to ASCII lowercase with collapsed spaces.
    """
    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return " ".join(normalized.strip().lower().split())
