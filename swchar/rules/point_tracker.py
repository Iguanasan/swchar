"""Point-buy budget calculations and validation engine for SWADE Wild Cards."""

from swchar.core.constants import (
    BASE_ATTRIBUTE_POINTS,
    BASE_SKILL_POINTS,
    MAX_HINDRANCE_POINTS,
)
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName
from swchar.models.character import Character
from swchar.models.hindrances import Hindrance, HindranceEconomy, HindranceSeverity
from swchar.rules.prerequisites import PrerequisiteChecker


DIE_SCALE: list[DieType] = [
    DieType.D4,
    DieType.D6,
    DieType.D8,
    DieType.D10,
    DieType.D12,
    DieType.D12_PLUS,
]
DIE_INDICES: dict[DieType, int] = {die: idx for idx, die in enumerate(DIE_SCALE)}


class PointTracker:
    """Rules engine for tracking trait point expenditures, budgets, and validations."""

    @classmethod
    def _get_ancestral_bonus(
        cls, character: Character, attr: AttributeName
    ) -> int:
        """Return the ancestral die step bonus for an attribute (0 if none)."""
        ancestry = getattr(character, "ancestry", None)
        if not ancestry:
            return 0
        bonuses = getattr(ancestry, "attribute_bonuses", {})
        if attr in bonuses:
            return bonuses[attr]
        if attr.value in bonuses:
            return bonuses[attr.value]
        if attr.value.lower() in bonuses:
            return bonuses[attr.value.lower()]
        return 0

    # --------------------------------------------------------------------------
    # Attribute Point Tracking
    # --------------------------------------------------------------------------

    @classmethod
    def get_attribute_points_spent(cls, character: Character) -> int:
        """Calculate total attribute points spent above starting racial baselines."""
        total_spent = 0
        for attr in [
            AttributeName.AGILITY,
            AttributeName.SMARTS,
            AttributeName.SPIRIT,
            AttributeName.STRENGTH,
            AttributeName.VIGOR,
        ]:
            current_die = character.attributes[attr]
            current_idx = DIE_INDICES.get(current_die, 0)
            base_idx = cls._get_ancestral_bonus(character, attr)
            if current_idx > base_idx:
                total_spent += current_idx - base_idx
        return total_spent

    @classmethod
    def get_attribute_points_available(cls, character: Character) -> int:
        """Calculate total attribute points available (base 5 + hindrance reward bonuses)."""
        bonus = 0
        rewards = getattr(character, "hindrance_rewards", None)
        if rewards is not None:
            bonus = getattr(rewards, "attribute_bonuses", 0)
        return BASE_ATTRIBUTE_POINTS + bonus

    @classmethod
    def get_attribute_points_budget(cls, character: Character) -> int:
        """Alias for get_attribute_points_available."""
        return cls.get_attribute_points_available(character)

    @classmethod
    def get_attribute_points_remaining(cls, character: Character) -> int:
        """Calculate remaining unspent attribute points."""
        return cls.get_attribute_points_available(character) - cls.get_attribute_points_spent(character)

    @classmethod
    def validate_attributes(cls, character: Character) -> list[str]:
        """Validate attribute allocations against minimums, racial caps, and point budget."""
        errors: list[str] = []

        # 1. Check minimums and caps per attribute
        for attr in [
            AttributeName.AGILITY,
            AttributeName.SMARTS,
            AttributeName.SPIRIT,
            AttributeName.STRENGTH,
            AttributeName.VIGOR,
        ]:
            current_die = character.attributes[attr]
            current_idx = DIE_INDICES.get(current_die, 0)
            base_idx = cls._get_ancestral_bonus(character, attr)

            if current_idx < base_idx:
                errors.append(
                    f"Attribute {attr.value} cannot be below ancestral minimum "
                    f"{DIE_SCALE[base_idx]} (currently {current_die})."
                )

            max_idx = min(len(DIE_SCALE) - 1, 4 + base_idx)
            if current_idx > max_idx:
                errors.append(
                    f"Attribute {attr.value} exceeds maximum cap of "
                    f"{DIE_SCALE[max_idx]} (currently {current_die})."
                )

        # 2. Check budget compliance
        spent = cls.get_attribute_points_spent(character)
        available = cls.get_attribute_points_available(character)
        remaining = available - spent

        if spent > available:
            errors.append(
                f"Attribute points overspent: {spent} points spent of {available} budget "
                f"({spent - available} over budget)."
            )
        elif spent < available:
            errors.append(
                f"Attribute points unspent: {spent} points spent of {available} budget "
                f"({remaining} points remaining)."
            )

        return errors

    # --------------------------------------------------------------------------
    # Skill Point Tracking
    # --------------------------------------------------------------------------

    @classmethod
    def get_skill_points_spent(cls, character: Character) -> int:
        """Calculate total skill points spent.

        Rules:
        - 5 core skills start at d4 at 0 cost.
        - Non-core skills start untrained at 0 cost.
        - Purchasing d4 in non-core skill costs 1 point.
        - Advancing up to linked attribute costs 1 point per die step.
        - Advancing beyond linked attribute costs 2 points per die step.
        """
        total_spent = 0
        for skill in character.skills.values():
            skill_idx = DIE_INDICES.get(skill.die, 0)
            attr_die = character.attributes[skill.attribute]
            attr_idx = DIE_INDICES.get(attr_die, 0)

            if skill.core:
                for step in range(1, skill_idx + 1):
                    if step <= attr_idx:
                        total_spent += 1
                    else:
                        total_spent += 2
            else:
                # Purchasing non-core skill at d4 (step 0)
                if 0 <= attr_idx:
                    total_spent += 1
                else:
                    total_spent += 2

                for step in range(1, skill_idx + 1):
                    if step <= attr_idx:
                        total_spent += 1
                    else:
                        total_spent += 2

        return total_spent

    @classmethod
    def get_skill_points_available(cls, character: Character) -> int:
        """Calculate total skill points available (base 12 + hindrance reward bonuses)."""
        bonus = 0
        rewards = getattr(character, "hindrance_rewards", None)
        if rewards is not None:
            bonus = getattr(rewards, "skill_bonuses", 0)
        return BASE_SKILL_POINTS + bonus

    @classmethod
    def get_skill_points_budget(cls, character: Character) -> int:
        """Alias for get_skill_points_available."""
        return cls.get_skill_points_available(character)

    @classmethod
    def get_skill_points_remaining(cls, character: Character) -> int:
        """Calculate remaining unspent skill points."""
        return cls.get_skill_points_available(character) - cls.get_skill_points_spent(character)

    @classmethod
    def validate_skills(cls, character: Character) -> list[str]:
        """Validate skill allocations against d12 creation cap and point budget."""
        errors: list[str] = []

        # 1. Check skill caps (cannot exceed d12 at creation)
        for skill in character.skills.values():
            if skill.die > DieType.D12:
                errors.append(
                    f"Skill '{skill.name}' exceeds maximum cap of d12 at character creation "
                    f"({skill.die})."
                )

        # 2. Check budget compliance
        spent = cls.get_skill_points_spent(character)
        available = cls.get_skill_points_available(character)
        remaining = available - spent

        if spent > available:
            errors.append(
                f"Skill points overspent: {spent} points spent of {available} budget "
                f"({spent - available} over budget)."
            )
        elif spent < available:
            errors.append(
                f"Skill points unspent: {spent} points spent of {available} budget "
                f"({remaining} points remaining)."
            )

        return errors

    # --------------------------------------------------------------------------
    # Hindrance Economy Tracking
    # --------------------------------------------------------------------------

    @classmethod
    def get_hindrance_points_balance(cls, character: Character) -> HindranceEconomy:
        """Compute hindrance point earnings, 4-point benefit cap, and redemption balance."""
        total_points = 0
        for h in getattr(character, "hindrances", []):
            if isinstance(h, Hindrance):
                total_points += h.points
            elif hasattr(h, "points"):
                total_points += h.points
            elif hasattr(h, "severity"):
                sev_str = str(h.severity).lower()
                total_points += 2 if "major" in sev_str else 1
            elif isinstance(h, dict):
                sev_str = str(h.get("severity", "minor")).lower()
                total_points += 2 if "major" in sev_str else 1
            else:
                total_points += 1

        usable_points = min(total_points, MAX_HINDRANCE_POINTS)
        rewards = getattr(character, "hindrance_rewards", None)
        if rewards is None:
            rewards = HindranceEconomy()

        attr_bonuses = getattr(rewards, "attribute_bonuses", 0)
        edge_bonuses = getattr(rewards, "edge_bonuses", 0)
        skill_bonuses = getattr(rewards, "skill_bonuses", 0)
        cash_bonuses = getattr(rewards, "cash_bonuses", 0)

        return HindranceEconomy(
            attribute_bonuses=attr_bonuses,
            edge_bonuses=edge_bonuses,
            skill_bonuses=skill_bonuses,
            cash_bonuses=cash_bonuses,
            total_points=total_points,
            usable_points=usable_points,
        )

    @classmethod
    def validate_hindrances(cls, character: Character) -> list[str]:
        """Validate hindrance point redemptions against earned usable points."""
        errors: list[str] = []
        balance = cls.get_hindrance_points_balance(character)

        if balance.points_spent > balance.usable_points:
            errors.append(
                f"Hindrance rewards overspent: {balance.points_spent} points redeemed, "
                f"exceeding {balance.usable_points} usable points available."
            )

        if (
            balance.attribute_bonuses < 0
            or balance.edge_bonuses < 0
            or balance.skill_bonuses < 0
            or balance.cash_bonuses < 0
        ):
            errors.append("Hindrance rewards cannot have negative bonuses.")

        return errors

    # --------------------------------------------------------------------------
    # Aggregate Build Validation
    # --------------------------------------------------------------------------

    @classmethod
    def validate_build(cls, character: Character) -> list[str]:
        """Aggregate validation errors across attributes, skills, hindrances, and edges."""
        errors: list[str] = []
        errors.extend(cls.validate_attributes(character))
        skill_errors = cls.validate_skills(character)
        if not skill_errors and cls.get_attribute_points_remaining(character) < 0:
            # If attributes are overspent, evaluate skills against ancestral base attributes
            base_spent = 0
            for skill in character.skills.values():
                skill_idx = DIE_INDICES.get(skill.die, 0)
                base_idx = cls._get_ancestral_bonus(character, skill.attribute)
                if skill.core:
                    for step in range(1, skill_idx + 1):
                        base_spent += 1 if step <= base_idx else 2
                else:
                    base_spent += 1 if 0 <= base_idx else 2
                    for step in range(1, skill_idx + 1):
                        base_spent += 1 if step <= base_idx else 2
            available = cls.get_skill_points_available(character)
            if base_spent > available:
                skill_errors.append(
                    f"Skill points overspent: {base_spent} points spent of {available} budget "
                    f"when evaluated against legal base attributes ({base_spent - available} over budget)."
                )
            else:
                skill_errors.append(
                    "Skill points allocation cannot be verified while attribute points are overspent."
                )
        errors.extend(skill_errors)
        errors.extend(cls.validate_hindrances(character))
        errors.extend(PrerequisiteChecker.validate_character_edges(character))
        return errors
