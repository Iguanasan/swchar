"""Skill domain models and core skill definitions for SWADE."""

from dataclasses import dataclass
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName


@dataclass
class Skill:
    """Represents a character skill with a linked attribute and die rating."""

    name: str
    attribute: AttributeName
    die: DieType = DieType.D4
    core: bool = False

    @property
    def linked_attribute(self) -> AttributeName:
        """Alias for attribute."""
        return self.attribute

    @property
    def is_core(self) -> bool:
        """Alias for core."""
        return self.core


CORE_SKILLS: dict[str, AttributeName] = {
    "Athletics": AttributeName.AGILITY,
    "Common Knowledge": AttributeName.SMARTS,
    "Notice": AttributeName.SMARTS,
    "Persuasion": AttributeName.SPIRIT,
    "Stealth": AttributeName.AGILITY,
}


def get_core_skills() -> list[Skill]:
    """Return new instances of the five standard SWADE core skills initialized to d4."""
    return [
        Skill(name=name, attribute=linked_attr, die=DieType.D4, core=True)
        for name, linked_attr in CORE_SKILLS.items()
    ]
