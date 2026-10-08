"""Polyhedral dice engine representing SWADE stepped trait dice."""

from enum import IntEnum
from typing import Self


class DieType(IntEnum):
    """Stepped polyhedral dice ratings used in Savage Worlds Adventure Edition.

    Values correspond directly to the die scale:
    d4 (4), d6 (6), d8 (8), d10 (10), d12 (12), and d12+ (14 representing d12+2 / stepped beyond).
    """

    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D12 = 12
    D12_PLUS = 14

    def __str__(self) -> str:
        """Return canonical lowercase RPG dice notation (e.g. 'd6', 'd12+')."""
        if self == DieType.D12_PLUS:
            return "d12+"
        return f"d{self.value}"

    def next_die(self) -> Self:
        """Return the next die type in the polyhedral progression scale.

        Raises:
            ValueError: If already at maximum stepped die (D12_PLUS).
        """
        members = list(DieType)
        idx = members.index(self)
        if idx + 1 >= len(members):
            raise ValueError(f"Cannot increase beyond maximum die rating {self}.")
        return members[idx + 1]

    def prev_die(self) -> Self:
        """Return the previous die type in the polyhedral progression scale.

        Raises:
            ValueError: If already at minimum die rating (D4).
        """
        members = list(DieType)
        idx = members.index(self)
        if idx - 1 < 0:
            raise ValueError(f"Cannot decrease below minimum die rating {self}.")
        return members[idx - 1]

    @classmethod
    def from_string(cls, notation: str) -> "DieType":
        """Parse dice notation string (case-insensitive) into a DieType enum.

        Supports standard notations such as 'd4', 'D6', 'd8', 'd10', 'd12', 'd12+', 'd12_plus'.

        Raises:
            ValueError: If the notation is not a valid SWADE polyhedral die.
        """
        cleaned = notation.strip().lower()
        mapping = {
            "d4": cls.D4,
            "d6": cls.D6,
            "d8": cls.D8,
            "d10": cls.D10,
            "d12": cls.D12,
            "d12+": cls.D12_PLUS,
            "d12_plus": cls.D12_PLUS,
        }
        if cleaned in mapping:
            return mapping[cleaned]
        raise ValueError(f"Invalid die notation: '{notation}'. Expected one of {list(mapping.keys())}")
