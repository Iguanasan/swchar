"""Character aggregate root model for Savage Worlds Wild Cards."""

import uuid
from dataclasses import dataclass, field
from typing import Any
from swchar.core.constants import STARTING_CASH, BASE_BENNIES
from swchar.core.dice import DieType
from swchar.models.ancestry import Ancestry, get_ancestry
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.edges import Rank
from swchar.models.hindrances import HindranceEconomy
from swchar.models.skills import Skill, CORE_SKILLS, get_core_skills


@dataclass
class Character:
    """Root aggregate representing a Savage Worlds Wild Card character."""

    name: str = ""
    concept: str = ""
    ancestry: Ancestry = field(default_factory=lambda: get_ancestry("Human"))
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rank: Rank = Rank.NOVICE
    attributes: Attributes = field(default_factory=Attributes)
    skills: dict[str, Skill] = field(default_factory=dict)
    edges: list[str] = field(default_factory=list)
    hindrances: list[Any] = field(default_factory=list)
    hindrance_rewards: Any = field(default_factory=HindranceEconomy)
    bennies: int | None = None
    cash: float = STARTING_CASH
    inventory: list[Any] = field(default_factory=list)
    arcana: Any = None

    def __post_init__(self) -> None:
        """Initialize bennies from ancestry and populate core skills at d4 if not present."""
        if self.bennies is None:
            ancestry_bonus = getattr(self.ancestry, "bennies_bonus", 0) if self.ancestry else 0
            self.bennies = BASE_BENNIES + ancestry_bonus

        for core_skill in get_core_skills():
            if not any(k.lower() == core_skill.name.lower() for k in self.skills):
                self.skills[core_skill.name] = core_skill

    def get_skill(self, name: str) -> Skill | None:
        """Retrieve a skill by name (case-insensitive)."""
        for k, v in self.skills.items():
            if k.lower() == name.strip().lower():
                return v
        return None

    def set_skill(
        self,
        name: str,
        die: DieType,
        attribute: AttributeName | None = None,
        core: bool | None = None,
    ) -> Skill:
        """Set or update a skill on the character."""
        existing = self.get_skill(name)
        if existing is not None:
            existing.die = die
            if attribute is not None:
                existing.attribute = attribute
            if core is not None:
                existing.core = core
            return existing

        is_core = core if core is not None else False
        if attribute is None:
            if name in CORE_SKILLS:
                attribute = CORE_SKILLS[name]
                is_core = True
            else:
                attribute = AttributeName.AGILITY

        new_skill = Skill(name=name, attribute=attribute, die=die, core=is_core)
        self.skills[name] = new_skill
        return new_skill
