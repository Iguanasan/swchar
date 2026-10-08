"""Rules calculations for SWADE derived combat statistics."""

from typing import NamedTuple
from swchar.core.constants import BASE_BENNIES, BASE_PACE, STANDARD_LOAD_LIMIT_MULTIPLIER, BRAWNY_LOAD_LIMIT_MULTIPLIER
from swchar.core.dice import DieType
from swchar.models.character import Character


class PaceResult(NamedTuple):
    """Encapsulates ground pace, running die, and optional flying pace."""

    pace: int
    running_die: DieType
    flying_pace: int = 0


class ToughnessResult(NamedTuple):
    """Encapsulates base toughness, armor, and total toughness."""

    base: int
    armor: int
    total: int


class DerivedStatsCalculator:
    """Rules engine calculating derived combat traits for Savage Worlds characters."""

    @staticmethod
    def calculate_pace(character: Character) -> PaceResult:
        """Calculate character's ground Pace, Running Die, and Flying Pace.

        Considers ancestry defaults (Human pace 6 / d6, Dwarf/Half-Folk pace 5 / d4,
        Avion ground 5 / d4 / fly 12).
        """
        pace = character.ancestry.pace if character.ancestry else BASE_PACE
        running_die = character.ancestry.running_die if character.ancestry else DieType.D6
        flying_pace = getattr(character.ancestry, "flying_pace", 0) if character.ancestry else 0

        # Check for Fleet-Footed Edge (+2 Pace, die step up for running die)
        if "Fleet-Footed" in getattr(character, "edges", []):
            pace += 2
            try:
                running_die = running_die.next_die()
            except ValueError:
                pass

        return PaceResult(pace=pace, running_die=running_die, flying_pace=flying_pace)

    @staticmethod
    def calculate_flying_pace(character: Character) -> int:
        """Calculate flying Pace (e.g. 12 for Avion)."""
        if character.ancestry:
            return getattr(character.ancestry, "flying_pace", 0)
        return 0

    @staticmethod
    def calculate_parry(character: Character, parry_bonus: int = 0) -> int:
        """Calculate Parry statistic: 2 + half Fighting die + shields + edge bonuses.

        If untrained (no Fighting skill), baseline Parry is 2.
        """
        fighting = character.get_skill("Fighting")
        if fighting is None:
            base_parry = 2
        else:
            base_parry = 2 + (fighting.die.value // 2)

        edge_bonus = 0
        edges = getattr(character, "edges", [])
        if "Improved Block" in edges:
            edge_bonus += 2
        elif "Block" in edges:
            edge_bonus += 1

        return base_parry + parry_bonus + edge_bonus

    @staticmethod
    def calculate_toughness(character: Character, torso_armor: int = 0) -> ToughnessResult:
        """Calculate Toughness: 2 + half Vigor die + Size modifier + racial bonus + Armor.

        Torso armor stacks with ancestral natural armor (e.g. Saurian +2).
        """
        vigor_val = character.attributes.vigor.value
        base_toughness = 2 + (vigor_val // 2)

        # Ancestral size modifier (e.g. Half-Folk -1)
        if character.ancestry:
            base_toughness += character.ancestry.size
            base_toughness += character.ancestry.toughness_bonus

        # Check for Brawny or other toughness-modifying edges
        edges = getattr(character, "edges", [])
        if "Brawny" in edges:
            base_toughness += 1

        # Armor calculations: worn armor + natural armor
        armor = torso_armor
        if character.ancestry:
            armor += character.ancestry.armor_bonus

        total_toughness = base_toughness + armor

        return ToughnessResult(base=base_toughness, armor=armor, total=total_toughness)

    @staticmethod
    def calculate_bennies(character: Character) -> int:
        """Calculate starting Bennies: 3 + ancestral Luck + Edge bonuses."""
        bennies = BASE_BENNIES
        if character.ancestry:
            bennies += getattr(character.ancestry, "bennies_bonus", 0)

        edges = getattr(character, "edges", [])
        if "Luck" in edges:
            bennies += 1
        if "Great Luck" in edges:
            bennies += 1

        return bennies

    @staticmethod
    def calculate_load_limit(character: Character) -> float:
        """Calculate unencumbered Load Limit in pounds (Strength die × 5 lbs, or × 8 with Brawny)."""
        strength_val = character.attributes.strength.value
        edges = getattr(character, "edges", [])
        multiplier = (
            BRAWNY_LOAD_LIMIT_MULTIPLIER
            if "Brawny" in edges
            else STANDARD_LOAD_LIMIT_MULTIPLIER
        )
        return float(strength_val * multiplier)
