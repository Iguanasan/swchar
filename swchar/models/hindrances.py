"""Hindrance domain models, severity classifications, and reward economy for SWADE."""

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any
from swchar.core.constants import MAX_HINDRANCE_POINTS


class HindranceSeverity(str, Enum):
    """Severity level of a Savage Worlds Hindrance."""

    MINOR = "Minor"
    MAJOR = "Major"


class HindranceRewardType(str, Enum):
    """Types of mechanical rewards earned by taking Hindrances."""

    ATTRIBUTE = "Attribute"
    EDGE = "Edge"
    SKILL = "Skill"
    CASH = "Cash"


@dataclass
class HindranceRedemption:
    """Represents a specific redemption of hindrance points."""

    reward_type: HindranceRewardType
    count: int = 1

    @property
    def cost_per_unit(self) -> int:
        """Hindrance points required per unit of reward."""
        match self.reward_type:
            case HindranceRewardType.ATTRIBUTE | HindranceRewardType.EDGE:
                return 2
            case HindranceRewardType.SKILL | HindranceRewardType.CASH:
                return 1

    @property
    def total_cost(self) -> int:
        """Total hindrance points spent on this redemption."""
        return self.cost_per_unit * self.count


@dataclass
class Hindrance:
    """Domain model representing a character Hindrance (flaw, liability, or drawback)."""

    name: str
    severity: HindranceSeverity = HindranceSeverity.MINOR
    description: str = ""

    def __post_init__(self) -> None:
        """Ensure severity is an instance of HindranceSeverity."""
        if isinstance(self.severity, str) and not isinstance(self.severity, HindranceSeverity):
            for s in HindranceSeverity:
                if s.value.lower() == self.severity.lower() or s.name.lower() == self.severity.lower():
                    self.severity = s
                    break

    @property
    def points(self) -> int:
        """Mechanical point value yielded by this hindrance (Minor = 1, Major = 2)."""
        return 2 if self.severity == HindranceSeverity.MAJOR else 1

    def __str__(self) -> str:
        return f"{self.name} ({self.severity.value})"


@dataclass
class HindranceEconomy:
    """Tracks hindrance points earned, capped at usable limit, and redemptions made.

    Redemption costs:
    - 2 points -> +1 Attribute point (attribute_bonuses)
    - 2 points -> +1 Edge (edge_bonuses / extra_edges)
    - 1 point  -> +1 Skill point (skill_bonuses)
    - 1 point  -> +$500 starting cash (cash_bonuses)
    """

    attribute_bonuses: int = 0
    edge_bonuses: int = 0
    skill_bonuses: int = 0
    cash_bonuses: int = 0
    total_points: int = 0
    usable_points: int = 0

    def __init__(
        self,
        attribute_bonuses: int = 0,
        edge_bonuses: int = 0,
        skill_bonuses: int = 0,
        cash_bonuses: int = 0,
        total_points: int = 0,
        usable_points: int = 0,
        total_earned: int | None = None,
        spent_points: int | None = None,
        remaining_points: int | None = None,
        **kwargs: Any,
    ) -> None:
        self.attribute_bonuses = attribute_bonuses or kwargs.get("attribute_bonus", 0)
        self.edge_bonuses = (
            edge_bonuses or kwargs.get("edge_bonus", 0) or kwargs.get("extra_edges", 0)
        )
        self.skill_bonuses = skill_bonuses or kwargs.get("skill_bonus", 0)
        raw_cash = cash_bonuses or kwargs.get("cash_bonus", 0)
        if raw_cash >= 500:
            self.cash_bonuses = int(raw_cash // 500)
        else:
            self.cash_bonuses = int(raw_cash)
        if total_earned is not None:
            self.total_points = total_earned
        else:
            self.total_points = total_points or kwargs.get("total_earned", 0)
        self.usable_points = usable_points

    @property
    def total_earned(self) -> int:
        """Alias for total_points."""
        return self.total_points

    @total_earned.setter
    def total_earned(self, val: int) -> None:
        self.total_points = val

    @property
    def remaining_points(self) -> int:
        """Alias for points_remaining."""
        return self.points_remaining

    @property
    def spent_points(self) -> int:
        """Alias for points_spent."""
        return self.points_spent

    @property
    def points_spent(self) -> int:
        """Total points consumed by selected rewards."""
        return (
            self.attribute_bonuses * 2
            + self.edge_bonuses * 2
            + self.skill_bonuses * 1
            + self.cash_bonuses * 1
        )

    @property
    def points_remaining(self) -> int:
        """Points remaining from usable allotment."""
        return self.usable_points - self.points_spent

    @property
    def is_valid(self) -> bool:
        """Check whether redeemed points do not exceed usable points and are non-negative."""
        return (
            self.points_spent <= self.usable_points
            and self.attribute_bonuses >= 0
            and self.edge_bonuses >= 0
            and self.skill_bonuses >= 0
            and self.cash_bonuses >= 0
        )

    @property
    def attribute_bonus(self) -> int:
        """Alias for attribute_bonuses."""
        return self.attribute_bonuses

    @property
    def edge_bonus(self) -> int:
        """Alias for edge_bonuses."""
        return self.edge_bonuses

    @property
    def extra_edges(self) -> int:
        """Alias for edge_bonuses."""
        return self.edge_bonuses

    @property
    def skill_bonus(self) -> int:
        """Alias for skill_bonuses."""
        return self.skill_bonuses

    @property
    def cash_bonus(self) -> float:
        """Cash bonus dollar amount (+$500 per cash bonus point)."""
        return float(self.cash_bonuses * 500)


HINDRANCES: dict[str, Hindrance] = {
    "All Thumbs": Hindrance("All Thumbs", HindranceSeverity.MINOR, "-2 to Repair rolls and operating modern devices."),
    "Anemic": Hindrance("Anemic", HindranceSeverity.MINOR, "-2 to Vigor checks resisting fatigue, poison, disease."),
    "Arrogant": Hindrance("Arrogant", HindranceSeverity.MAJOR, "Must humiliate opponents and seek victory alone."),
    "Bad Eyes (Minor)": Hindrance("Bad Eyes (Minor)", HindranceSeverity.MINOR, "-2 to visual Notice rolls or ranged attacks without glasses."),
    "Bad Eyes (Major)": Hindrance("Bad Eyes (Major)", HindranceSeverity.MAJOR, "-2 to all trait rolls depending on vision."),
    "Bad Luck": Hindrance("Bad Luck", HindranceSeverity.MAJOR, "Start each session with one fewer Benny."),
    "Bloodthirsty": Hindrance("Bloodthirsty", HindranceSeverity.MAJOR, "Never takes prisoners; cruel and savage."),
    "Cautious": Hindrance("Cautious", HindranceSeverity.MINOR, "Overly careful and plans everything meticulously."),
    "Clueless": Hindrance("Clueless", HindranceSeverity.MAJOR, "-2 to Common Knowledge and Notice rolls."),
    "Code of Honor": Hindrance("Code of Honor", HindranceSeverity.MAJOR, "Adheres to a strict moral code."),
    "Curious": Hindrance("Curious", HindranceSeverity.MAJOR, "Must investigate the unknown or mysterious."),
    "Death Wish": Hindrance("Death Wish", HindranceSeverity.MINOR, "Seeks a glorious death or heroic sacrifice."),
    "Greedy": Hindrance("Greedy", HindranceSeverity.MINOR, "Obsessed with wealth and money."),
    "Heroic": Hindrance("Heroic", HindranceSeverity.MAJOR, "Always helps those in need and acts honorably."),
    "Loyal": Hindrance("Loyal", HindranceSeverity.MINOR, "Will never abandon or betray friends."),
    "Mean": Hindrance("Mean", HindranceSeverity.MINOR, "-2 to Persuasion rolls."),
    "Outsider": Hindrance("Outsider", HindranceSeverity.MINOR, "-2 to Persuasion with foreign groups."),
    "Pacifist (Minor)": Hindrance("Pacifist (Minor)", HindranceSeverity.MINOR, "Fights only in self-defense."),
    "Pacifist (Major)": Hindrance("Pacifist (Major)", HindranceSeverity.MAJOR, "Despises all violence."),
    "Stubborn": Hindrance("Stubborn", HindranceSeverity.MINOR, "Rarely admits fault or changes mind."),
    "Vow": Hindrance("Vow", HindranceSeverity.MAJOR, "Bound to a solemn oath."),
}


def get_hindrance(name: str) -> Hindrance:
    """Retrieve a Hindrance from the registry by name (case-insensitive).

    Raises:
        KeyError: If the hindrance is not found.
    """
    for key, hindrance in HINDRANCES.items():
        if key.lower() == name.strip().lower():
            return copy.deepcopy(hindrance)
    raise KeyError(f"Unknown hindrance: '{name}'.")
