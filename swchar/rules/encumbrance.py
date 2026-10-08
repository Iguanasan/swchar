"""SWADE encumbrance rules, carried weight, minimum strength, and damage capping."""

import re
from dataclasses import dataclass
from typing import Sequence
from swchar.core.dice import DieType
from swchar.models.items import InventoryItem


@dataclass(frozen=True)
class EncumbranceResult:
    """Result of character load limit vs. carried weight evaluation."""

    penalty: int
    is_immobilized: bool = False


@dataclass(frozen=True)
class MinStrResult:
    """Result of checking character Strength against item Minimum Strength."""

    satisfies: bool
    deficiency: int = 0
    penalty: int = 0


class EncumbranceCalculator:
    """Calculations for carried weight, encumbrance penalties, minimum strength, and weapon damage caps."""

    @staticmethod
    def calculate_carried_weight(items: Sequence[InventoryItem]) -> float:
        """Calculate total carried weight from inventory items (weight * quantity).

        Args:
            items: Sequence of inventory items.

        Returns:
            Total weight in pounds (lbs).
        """
        return sum(float(item.weight) * int(item.quantity) for item in items)

    @staticmethod
    def calculate_encumbrance_penalty(
        load_limit: float, carried_weight: float
    ) -> EncumbranceResult:
        """Calculate encumbrance penalty and immobilization status based on SWADE load limits.

        Rules:
        - Carried weight <= Load Limit: 0 penalty, not immobilized.
        - Carried weight <= 2x Load Limit: -1 penalty, not immobilized.
        - Carried weight <= 3x Load Limit: -2 penalty, not immobilized.
        - Carried weight <= 4x Load Limit: -3 penalty, not immobilized.
        - Carried weight > 4x Load Limit: immobilized.
        - Zero load limit with positive weight causes immobilization.

        Args:
            load_limit: Character load limit in lbs.
            carried_weight: Total carried weight in lbs.

        Returns:
            EncumbranceResult containing penalty and is_immobilized flag.
        """
        if load_limit <= 0.0:
            if carried_weight > 0.0:
                return EncumbranceResult(penalty=-3, is_immobilized=True)
            return EncumbranceResult(penalty=0, is_immobilized=False)

        if carried_weight <= load_limit:
            return EncumbranceResult(penalty=0, is_immobilized=False)
        elif carried_weight <= 2 * load_limit:
            return EncumbranceResult(penalty=-1, is_immobilized=False)
        elif carried_weight <= 3 * load_limit:
            return EncumbranceResult(penalty=-2, is_immobilized=False)
        elif carried_weight <= 4 * load_limit:
            return EncumbranceResult(penalty=-3, is_immobilized=False)
        else:
            return EncumbranceResult(penalty=-3, is_immobilized=True)

    @staticmethod
    def check_min_strength(
        character_strength: DieType,
        min_str: DieType | str | None,
    ) -> MinStrResult:
        """Check character Strength against item Minimum Strength requirement.

        Args:
            character_strength: The character's Strength DieType.
            min_str: The required minimum strength as DieType, string (e.g. 'd6'), or None.

        Returns:
            MinStrResult containing satisfies flag, step deficiency, and negative penalty.
        """
        if min_str is None:
            return MinStrResult(satisfies=True, deficiency=0, penalty=0)

        if isinstance(min_str, str):
            cleaned = min_str.strip()
            if not cleaned or cleaned.lower() in ("none", "-"):
                return MinStrResult(satisfies=True, deficiency=0, penalty=0)
            req_die = DieType.from_string(cleaned)
        else:
            req_die = min_str

        die_order = [
            DieType.D4,
            DieType.D6,
            DieType.D8,
            DieType.D10,
            DieType.D12,
            DieType.D12_PLUS,
        ]

        try:
            char_idx = die_order.index(character_strength)
            req_idx = die_order.index(req_die)
        except ValueError:
            char_idx = character_strength.value
            req_idx = req_die.value

        if char_idx >= req_idx:
            return MinStrResult(satisfies=True, deficiency=0, penalty=0)

        deficiency = req_idx - char_idx
        return MinStrResult(
            satisfies=False,
            deficiency=deficiency,
            penalty=-deficiency,
        )

    @classmethod
    def calculate_effective_weapon_damage(
        cls,
        character_strength: DieType,
        min_str: DieType | str | None = None,
        base_damage: str = "",
    ) -> str:
        """Calculate effective weapon damage considering Minimum Strength capping.

        If Min Str is not satisfied for a Str+d... weapon, the weapon bonus damage die
        is capped at the character's Strength die. Flat bonuses (e.g. +1) are preserved.

        Args:
            character_strength: Wielder's Strength die.
            min_str: Weapon Minimum Strength requirement.
            base_damage: Base weapon damage string (e.g. 'Str+d8', 'Str+d8+1').

        Returns:
            Effective damage notation string.
        """
        if not base_damage:
            return ""

        min_str_res = cls.check_min_strength(character_strength, min_str)
        if min_str_res.satisfies:
            return base_damage

        # Match Str+d<number><optional suffix>
        match = re.match(r"(?i)^(str\s*\+\s*)d(\d+)(.*)$", base_damage.strip())
        if not match:
            return base_damage

        prefix = "Str+"
        die_sides = int(match.group(2))
        suffix = match.group(3)

        try:
            weapon_die = DieType.from_string(f"d{die_sides}")
        except ValueError:
            return base_damage

        if weapon_die > character_strength:
            effective_die_str = str(character_strength)
            return f"{prefix}{effective_die_str}{suffix}"

        return base_damage

    @classmethod
    def calculate_effective_damage(
        cls,
        character_strength: DieType,
        base_damage: str = "",
        min_str: DieType | str | None = None,
    ) -> str:
        """Alias for calculate_effective_weapon_damage supporting alternative parameter order."""
        return cls.calculate_effective_weapon_damage(
            character_strength=character_strength,
            min_str=min_str,
            base_damage=base_damage,
        )
