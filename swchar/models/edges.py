"""Edge domain models, categories, rank progression, and prerequisite definitions for SWADE."""

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName


class Rank(str, Enum):
    """Character rank progression in Savage Worlds Adventure Edition."""

    NOVICE = "Novice"
    SEASONED = "Seasoned"
    VETERAN = "Veteran"
    HEROIC = "Heroic"
    LEGENDARY = "Legendary"

    @property
    def _order(self) -> int:
        ranks = [Rank.NOVICE, Rank.SEASONED, Rank.VETERAN, Rank.HEROIC, Rank.LEGENDARY]
        return ranks.index(self)

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, Rank):
            return self._order < other._order
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, Rank):
            return self._order <= other._order
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, Rank):
            return self._order > other._order
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, Rank):
            return self._order >= other._order
        return NotImplemented


class EdgeCategory(str, Enum):
    """Categorical classification of Savage Worlds Edges."""

    BACKGROUND = "Background"
    COMBAT = "Combat"
    LEADERSHIP = "Leadership"
    POWER = "Power"
    PROFESSIONAL = "Professional"
    SOCIAL = "Social"
    WEIRD = "Weird"


@dataclass
class EdgePrerequisite:
    """Encapsulates trait minimums, edge dependencies, and special requirements for an Edge."""

    attributes: dict[AttributeName, DieType] = field(default_factory=dict)
    skills: dict[str, DieType] = field(default_factory=dict)
    edges: list[str] = field(default_factory=list)
    requires_arcane: bool = False


class Edge:
    """Represents a Savage Worlds Edge granting special talents and combat benefits."""

    def __init__(
        self,
        name: str,
        category: EdgeCategory = EdgeCategory.BACKGROUND,
        rank: Rank = Rank.NOVICE,
        description: str = "",
        prerequisites: EdgePrerequisite | None = None,
    ) -> None:
        if isinstance(description, EdgePrerequisite) and (
            prerequisites is None or isinstance(prerequisites, str)
        ):
            prerequisites, description = description, prerequisites or ""
        self.name = name
        self.category = category
        self.rank = rank
        self.description = description
        self.prerequisites = (
            prerequisites if prerequisites is not None else EdgePrerequisite()
        )

    def __repr__(self) -> str:
        return f"Edge(name={self.name!r}, category={self.category!r}, rank={self.rank!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Edge):
            return self.name.lower() == other.name.lower()
        return False


EDGES: dict[str, Edge] = {
    "Alertness": Edge(
        name="Alertness",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="+2 to Notice rolls.",
        prerequisites=EdgePrerequisite(),
    ),
    "Ambidextrous": Edge(
        name="Ambidextrous",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="Ignore -2 off-hand penalty when using either hand.",
        prerequisites=EdgePrerequisite(
            attributes={AttributeName.AGILITY: DieType.D8}
        ),
    ),
    "Arcane Background": Edge(
        name="Arcane Background",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="Enables power activation and supernatural abilities.",
        prerequisites=EdgePrerequisite(),
    ),
    "Brawny": Edge(
        name="Brawny",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="Size +1 (Toughness +1), Load Limit is Strength x 8 lbs.",
        prerequisites=EdgePrerequisite(
            attributes={
                AttributeName.STRENGTH: DieType.D6,
                AttributeName.VIGOR: DieType.D6,
            }
        ),
    ),
    "Quick": Edge(
        name="Quick",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="Discard Action Cards of 5 or lower and draw again.",
        prerequisites=EdgePrerequisite(),
    ),
    "Fleet-Footed": Edge(
        name="Fleet-Footed",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="Pace +2, running die increases by one die type.",
        prerequisites=EdgePrerequisite(
            attributes={AttributeName.AGILITY: DieType.D6}
        ),
    ),
    "Brawler": Edge(
        name="Brawler",
        category=EdgeCategory.COMBAT,
        rank=Rank.NOVICE,
        description="Toughness +1, unarmed damage increases to Str+d4.",
        prerequisites=EdgePrerequisite(
            attributes={
                AttributeName.STRENGTH: DieType.D8,
                AttributeName.VIGOR: DieType.D8,
            }
        ),
    ),
    "Command": Edge(
        name="Command",
        category=EdgeCategory.LEADERSHIP,
        rank=Rank.NOVICE,
        description="+1 to recover from Shaken for allies in Command Range.",
        prerequisites=EdgePrerequisite(
            attributes={AttributeName.SMARTS: DieType.D6}
        ),
    ),
    "Luck": Edge(
        name="Luck",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="+1 Benny at the start of each session.",
        prerequisites=EdgePrerequisite(),
    ),
    "Great Luck": Edge(
        name="Great Luck",
        category=EdgeCategory.BACKGROUND,
        rank=Rank.NOVICE,
        description="+2 Bennies at the start of each session instead of +1.",
        prerequisites=EdgePrerequisite(edges=["Luck"]),
    ),
    "Frenzy": Edge(
        name="Frenzy",
        category=EdgeCategory.COMBAT,
        rank=Rank.SEASONED,
        description="Roll a second Fighting die with one melee attack per turn.",
        prerequisites=EdgePrerequisite(skills={"Fighting": DieType.D8}),
    ),
    "Improved Frenzy": Edge(
        name="Improved Frenzy",
        category=EdgeCategory.COMBAT,
        rank=Rank.VETERAN,
        description="Make two Fighting attacks at no Multi-Action penalty.",
        prerequisites=EdgePrerequisite(
            skills={"Fighting": DieType.D8}, edges=["Frenzy"]
        ),
    ),
    "Power Points": Edge(
        name="Power Points",
        category=EdgeCategory.POWER,
        rank=Rank.NOVICE,
        description="Gain 5 additional Power Points.",
        prerequisites=EdgePrerequisite(requires_arcane=True),
    ),
    "New Powers": Edge(
        name="New Powers",
        category=EdgeCategory.POWER,
        rank=Rank.NOVICE,
        description="Learn two additional powers.",
        prerequisites=EdgePrerequisite(requires_arcane=True),
    ),
}


def get_edge(name: str) -> Edge:
    """Retrieve an Edge from the catalog by name (case-insensitive).

    Raises:
        KeyError: If edge is not found in registry.
    """
    for key, edge in EDGES.items():
        if key.lower() == name.strip().lower():
            return copy.deepcopy(edge)
    raise KeyError(f"Unknown edge: '{name}'.")
