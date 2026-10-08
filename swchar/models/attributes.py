"""Attribute models and enumeration for SWADE characters."""

from enum import Enum
from typing import Any
from swchar.core.dice import DieType


class AttributeName(str, Enum):
    """The five core character attributes defined in SWADE."""

    AGILITY = "Agility"
    SMARTS = "Smarts"
    SPIRIT = "Spirit"
    STRENGTH = "Strength"
    VIGOR = "Vigor"


class Attributes:
    """Tracks and validates the five core character attributes.

    Attributes can be accessed via property attributes (e.g. `attrs.agility`)
    or indexed by AttributeName enum / string (e.g. `attrs[AttributeName.AGILITY]`).
    Values must strictly be instances of `DieType`.
    """

    __slots__ = ("_agility", "_smarts", "_spirit", "_strength", "_vigor")

    def __init__(
        self,
        agility: DieType = DieType.D4,
        smarts: DieType = DieType.D4,
        spirit: DieType = DieType.D4,
        strength: DieType = DieType.D4,
        vigor: DieType = DieType.D4,
    ) -> None:
        self.agility = agility
        self.smarts = smarts
        self.spirit = spirit
        self.strength = strength
        self.vigor = vigor

    def _validate_die(self, value: Any, attr_name: str) -> DieType:
        if not isinstance(value, DieType):
            raise TypeError(
                f"Attribute '{attr_name}' must be an instance of DieType, got {type(value).__name__}: {value}"
            )
        return value

    @property
    def agility(self) -> DieType:
        return self._agility

    @agility.setter
    def agility(self, val: Any) -> None:
        self._agility = self._validate_die(val, "agility")

    @property
    def smarts(self) -> DieType:
        return self._smarts

    @smarts.setter
    def smarts(self, val: Any) -> None:
        self._smarts = self._validate_die(val, "smarts")

    @property
    def spirit(self) -> DieType:
        return self._spirit

    @spirit.setter
    def spirit(self, val: Any) -> None:
        self._spirit = self._validate_die(val, "spirit")

    @property
    def strength(self) -> DieType:
        return self._strength

    @strength.setter
    def strength(self, val: Any) -> None:
        self._strength = self._validate_die(val, "strength")

    @property
    def vigor(self) -> DieType:
        return self._vigor

    @vigor.setter
    def vigor(self, val: Any) -> None:
        self._vigor = self._validate_die(val, "vigor")

    def _normalize_key(self, key: AttributeName | str) -> str:
        if isinstance(key, AttributeName):
            return key.value.lower()
        if isinstance(key, str):
            for attr in AttributeName:
                if key.lower() == attr.value.lower() or key.lower() == attr.name.lower():
                    return attr.value.lower()
        raise KeyError(f"Invalid attribute: '{key}'")

    def __getitem__(self, key: AttributeName | str) -> DieType:
        norm_key = self._normalize_key(key)
        return getattr(self, norm_key)

    def __setitem__(self, key: AttributeName | str, value: Any) -> None:
        norm_key = self._normalize_key(key)
        setattr(self, norm_key, value)

    def get(self, key: AttributeName | str, default: DieType | None = None) -> DieType | None:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[AttributeName, DieType]:
        return {
            AttributeName.AGILITY: self.agility,
            AttributeName.SMARTS: self.smarts,
            AttributeName.SPIRIT: self.spirit,
            AttributeName.STRENGTH: self.strength,
            AttributeName.VIGOR: self.vigor,
        }

    def __repr__(self) -> str:
        return (
            f"Attributes(agility={self.agility}, smarts={self.smarts}, "
            f"spirit={self.spirit}, strength={self.strength}, vigor={self.vigor})"
        )
