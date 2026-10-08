"""Arcane Backgrounds and supernatural powers domain models for SWADE."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ArcaneBackgroundType(str, Enum):
    """Core SWADE Arcane Background types."""

    NONE = "None"
    GIFTED = "Gifted"
    MAGIC = "Magic"
    MIRACLES = "Miracles"
    PSIONICS = "Psionics"
    WEIRD_SCIENCE = "Weird Science"


@dataclass
class ArcaneBackgroundDefaults:
    """Starting Power Points and number of starting powers for an Arcane Background."""

    power_points: int
    starting_powers: int


ARCANE_BACKGROUND_DEFAULTS: dict[str, ArcaneBackgroundDefaults] = {
    ArcaneBackgroundType.NONE.value: ArcaneBackgroundDefaults(power_points=0, starting_powers=0),
    ArcaneBackgroundType.GIFTED.value: ArcaneBackgroundDefaults(power_points=15, starting_powers=1),
    ArcaneBackgroundType.MAGIC.value: ArcaneBackgroundDefaults(power_points=10, starting_powers=3),
    ArcaneBackgroundType.MIRACLES.value: ArcaneBackgroundDefaults(power_points=10, starting_powers=3),
    ArcaneBackgroundType.PSIONICS.value: ArcaneBackgroundDefaults(power_points=10, starting_powers=3),
    ArcaneBackgroundType.WEIRD_SCIENCE.value: ArcaneBackgroundDefaults(power_points=15, starting_powers=2),
}


def get_arcane_background_defaults(
    background: str | ArcaneBackgroundType,
) -> ArcaneBackgroundDefaults:
    """Get standard starting stats (Power Points and starting powers count) for an Arcane Background."""
    bg_str = background.value if isinstance(background, ArcaneBackgroundType) else str(background)
    for name, defaults in ARCANE_BACKGROUND_DEFAULTS.items():
        if name.lower() == bg_str.strip().lower():
            return defaults
    return ArcaneBackgroundDefaults(power_points=0, starting_powers=0)


@dataclass
class Power:
    """Represents a supernatural power/spell/miracle available to an arcane character."""

    name: str
    power_points: int = 1
    trappings: str = ""
    range: str = ""
    duration: str = ""
    damage: str = ""
    notes: str = ""

    def __init__(
        self,
        name: str,
        power_points: int = 1,
        trappings: str = "",
        range: str = "",
        duration: str = "",
        damage: str = "",
        notes: str = "",
        **kwargs: Any,
    ) -> None:
        self.name = name
        self.power_points = power_points
        self.trappings = trappings or kwargs.get("trapping", "")
        self.range = range
        self.duration = duration
        self.damage = damage
        self.notes = notes

    @property
    def trapping(self) -> str:
        """Alias for trappings."""
        return self.trappings

    @trapping.setter
    def trapping(self, val: str) -> None:
        self.trappings = val


@dataclass
class ArcaneConfiguration:
    """Character arcane background configuration including power points and known powers."""

    background: str | ArcaneBackgroundType = ArcaneBackgroundType.NONE.value
    power_points: int = 0
    powers: list[Power] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Normalize background name string."""
        if isinstance(self.background, ArcaneBackgroundType):
            self.background = self.background.value
        elif isinstance(self.background, str):
            for bg_type in ArcaneBackgroundType:
                if self.background.lower() == bg_type.value.lower():
                    self.background = bg_type.value
                    break


Arcana = ArcaneConfiguration
ArcaneBackground = ArcaneConfiguration

__all__ = [
    "ArcaneBackgroundType",
    "ArcaneBackgroundDefaults",
    "ARCANE_BACKGROUND_DEFAULTS",
    "get_arcane_background_defaults",
    "Power",
    "ArcaneConfiguration",
    "Arcana",
    "ArcaneBackground",
]
