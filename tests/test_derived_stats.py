"""Unit tests for Derived Combat Statistics calculations.

Tests cover:
- Pace and Running Die (Human, Dwarf, Half-Folk, Avion)
- Parry (untrained, d4 through d12+2, shield bonuses)
- Toughness (Vigor scaling, torso armor, size modifiers, Saurian armor, Aquarian toughness)
- Bennies (Human 3, Half-Folk 4 Luck, Luck edge)
- Load Limit (Strength * 5 lbs, Brawny * 8 lbs)
"""

import pytest
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName
from swchar.models.skills import Skill
from swchar.models.character import Character
from swchar.rules.derived_stats import DerivedStatsCalculator


def _extract_pace(pace_result):
    """Support either tuple[int, DieType] or object with pace/running_die properties."""
    if isinstance(pace_result, tuple):
        return pace_result[0], pace_result[1]
    return pace_result.pace, pace_result.running_die


def _extract_toughness(toughness_result):
    """Support tuple[int, int] (base, armor) or Toughness dataclass/NamedTuple."""
    if isinstance(toughness_result, tuple):
        base = toughness_result[0]
        armor = toughness_result[1] if len(toughness_result) > 1 else 0
        total = getattr(toughness_result, "total", base + armor)
        return base, armor, total
    return toughness_result.base, toughness_result.armor, toughness_result.total


# ==============================================================================
# Pace & Running Die Tests
# ==============================================================================

def test_pace_and_running_die_human(sample_human_character):
    """Verify Human Pace is 6 with running die d6."""
    pace, run_die = _extract_pace(DerivedStatsCalculator.calculate_pace(sample_human_character))
    assert pace == 6
    assert run_die == DieType.D6


def test_pace_and_running_die_dwarf(sample_dwarf_character):
    """Verify Dwarf Pace is 5 with reduced running die d4."""
    pace, run_die = _extract_pace(DerivedStatsCalculator.calculate_pace(sample_dwarf_character))
    assert pace == 5
    assert run_die == DieType.D4


def test_pace_and_running_die_half_folk(sample_half_folk_character):
    """Verify Half-Folk Pace is 5 with reduced running die d4."""
    pace, run_die = _extract_pace(DerivedStatsCalculator.calculate_pace(sample_half_folk_character))
    assert pace == 5
    assert run_die == DieType.D4


def test_pace_and_running_die_avion_ground_and_flight(sample_avion_character):
    """Verify Avion Ground Pace is 5, running die d4, and Flight Pace is 12."""
    pace_res = DerivedStatsCalculator.calculate_pace(sample_avion_character)
    pace, run_die = _extract_pace(pace_res)
    assert pace == 5
    assert run_die == DieType.D4

    # Avion flying pace is 12
    if hasattr(DerivedStatsCalculator, "calculate_flying_pace"):
        flying_pace = DerivedStatsCalculator.calculate_flying_pace(sample_avion_character)
        assert flying_pace == 12
    elif hasattr(pace_res, "flying_pace"):
        assert pace_res.flying_pace == 12
    else:
        assert sample_avion_character.ancestry.flying_pace == 12


@pytest.mark.parametrize("fixture_name", [
    "sample_elf_character",
    "sample_half_elf_character",
    "sample_android_character",
    "sample_aquarian_character",
    "sample_rakashan_character",
    "sample_saurian_character",
])
def test_pace_and_running_die_standard_ancestries(request, fixture_name):
    """Verify standard ancestries have base Pace 6 and running die d6."""
    character = request.getfixturevalue(fixture_name)
    pace, run_die = _extract_pace(DerivedStatsCalculator.calculate_pace(character))
    assert pace == 6
    assert run_die == DieType.D6


# ==============================================================================
# Parry Tests
# ==============================================================================

def test_parry_untrained(sample_human_character):
    """Verify untrained character (no Fighting skill) has baseline Parry 2."""
    assert DerivedStatsCalculator.calculate_parry(sample_human_character) == 2


@pytest.mark.parametrize("fighting_die, expected_parry", [
    (DieType.D4, 4),   # 2 + 4 // 2 = 4
    (DieType.D6, 5),   # 2 + 6 // 2 = 5
    (DieType.D8, 6),   # 2 + 8 // 2 = 6
    (DieType.D10, 7),  # 2 + 10 // 2 = 7
    (DieType.D12, 8),  # 2 + 12 // 2 = 8
])
def test_parry_fighting_die_scale(sample_human_character, fighting_die, expected_parry):
    """Verify Parry calculation: 2 + half Fighting die."""
    sample_human_character.set_skill("Fighting", fighting_die, AttributeName.AGILITY)
    assert DerivedStatsCalculator.calculate_parry(sample_human_character) == expected_parry


def test_parry_fighting_d12_plus(sample_human_character):
    """Verify Parry calculation for stepped dice above d12 (d12+1 -> 8, d12+2 -> 9)."""
    # d12+1: half of 12 is 6, bonus 1 does not add full point unless +2
    # In SWADE: Parry = 2 + half die type. At d12+1, half is 6 (+0.5 rounded down) -> Parry 8
    # At d12+2 (DieType.D12_PLUS, value 14), half is 7 -> Parry 9
    sample_human_character.set_skill("Fighting", DieType.D12_PLUS, AttributeName.AGILITY)
    assert DerivedStatsCalculator.calculate_parry(sample_human_character) == 9


def test_parry_with_shield_bonus(sample_human_character):
    """Verify Parry calculation accounts for shield parry bonus."""
    sample_human_character.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)  # base Parry 6
    parry_with_shield = DerivedStatsCalculator.calculate_parry(sample_human_character, parry_bonus=1)
    assert parry_with_shield == 7


# ==============================================================================
# Toughness Tests
# ==============================================================================

@pytest.mark.parametrize("vigor_die, expected_base_toughness", [
    (DieType.D4, 4),   # 2 + 4 // 2 = 4
    (DieType.D6, 5),   # 2 + 6 // 2 = 5
    (DieType.D8, 6),   # 2 + 8 // 2 = 6
    (DieType.D10, 7),  # 2 + 10 // 2 = 7
    (DieType.D12, 8),  # 2 + 12 // 2 = 8
    (DieType.D12_PLUS, 9), # 2 + 14 // 2 = 9
])
def test_toughness_vigor_scaling(sample_human_character, vigor_die, expected_base_toughness):
    """Verify unarmored base Toughness = 2 + half Vigor die."""
    sample_human_character.attributes.vigor = vigor_die
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_human_character)
    )
    assert base == expected_base_toughness
    assert armor == 0
    assert total == expected_base_toughness


def test_toughness_with_torso_armor(sample_human_character):
    """Verify Toughness with torso armor increases total toughness."""
    sample_human_character.attributes.vigor = DieType.D6  # base 5
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_human_character, torso_armor=2)
    )
    assert base == 5
    assert armor == 2
    assert total == 7


def test_toughness_half_folk_size_modifier(sample_half_folk_character):
    """Verify Half-Folk Size -1 reduces base Toughness by 1."""
    sample_half_folk_character.attributes.vigor = DieType.D6
    # 2 + 6 // 2 - 1 = 4 base Toughness
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_half_folk_character)
    )
    assert base == 4
    assert armor == 0
    assert total == 4

    # With torso armor 2
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_half_folk_character, torso_armor=2)
    )
    assert base == 4
    assert armor == 2
    assert total == 6


def test_toughness_saurian_natural_armor(sample_saurian_character):
    """Verify Saurian racial natural armor (+2) is included in armor/total toughness."""
    sample_saurian_character.attributes.vigor = DieType.D6  # base 5
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_saurian_character)
    )
    assert base == 5
    assert armor == 2
    assert total == 7

    # Saurian wearing additional leather armor (+2)
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_saurian_character, torso_armor=2)
    )
    assert base == 5
    assert armor == 4  # 2 natural + 2 worn
    assert total == 9


def test_toughness_aquarian_racial_bonus(sample_aquarian_character):
    """Verify Aquarian racial +1 Toughness increases base Toughness."""
    sample_aquarian_character.attributes.vigor = DieType.D6
    # 2 + 6 // 2 + 1 (Aquarian trait) = 6 base Toughness
    base, armor, total = _extract_toughness(
        DerivedStatsCalculator.calculate_toughness(sample_aquarian_character)
    )
    assert base == 6
    assert armor == 0
    assert total == 6


# ==============================================================================
# Bennies Tests
# ==============================================================================

def test_bennies_baseline_human(sample_human_character):
    """Verify standard baseline Bennies is 3."""
    assert DerivedStatsCalculator.calculate_bennies(sample_human_character) == 3


def test_bennies_half_folk_luck(sample_half_folk_character):
    """Verify Half-Folk starts with 4 Bennies due to ancestral Luck trait."""
    assert DerivedStatsCalculator.calculate_bennies(sample_half_folk_character) == 4


@pytest.mark.parametrize("fixture_name", [
    "sample_android_character",
    "sample_aquarian_character",
    "sample_avion_character",
    "sample_dwarf_character",
    "sample_elf_character",
    "sample_half_elf_character",
    "sample_rakashan_character",
    "sample_saurian_character",
])
def test_bennies_other_ancestries(request, fixture_name):
    """Verify all standard ancestries start with 3 Bennies."""
    character = request.getfixturevalue(fixture_name)
    assert DerivedStatsCalculator.calculate_bennies(character) == 3


def test_bennies_with_luck_edge(sample_human_character, sample_half_folk_character):
    """Verify character with Luck edge gains +1 additional Benny."""
    sample_human_character.edges.append("Luck")
    assert DerivedStatsCalculator.calculate_bennies(sample_human_character) == 4

    sample_half_folk_character.edges.append("Luck")
    assert DerivedStatsCalculator.calculate_bennies(sample_half_folk_character) == 5


# ==============================================================================
# Load Limit Tests
# ==============================================================================

@pytest.mark.parametrize("strength_die, expected_load_limit", [
    (DieType.D4, 20.0),   # 4 * 5 = 20
    (DieType.D6, 30.0),   # 6 * 5 = 30
    (DieType.D8, 40.0),   # 8 * 5 = 40
    (DieType.D10, 50.0),  # 10 * 5 = 50
    (DieType.D12, 60.0),  # 12 * 5 = 60
    (DieType.D12_PLUS, 70.0), # 14 * 5 = 70
])
def test_load_limit_standard(sample_human_character, strength_die, expected_load_limit):
    """Verify standard Load Limit = Strength die value * 5 lbs."""
    sample_human_character.attributes.strength = strength_die
    assert DerivedStatsCalculator.calculate_load_limit(sample_human_character) == expected_load_limit


@pytest.mark.parametrize("strength_die, expected_load_limit", [
    (DieType.D4, 32.0),   # 4 * 8 = 32
    (DieType.D6, 48.0),   # 6 * 8 = 48
    (DieType.D8, 64.0),   # 8 * 8 = 64
    (DieType.D10, 80.0),  # 10 * 8 = 80
    (DieType.D12, 96.0),  # 12 * 8 = 96
    (DieType.D12_PLUS, 112.0), # 14 * 8 = 112
])
def test_load_limit_with_brawny_edge(sample_human_character, strength_die, expected_load_limit):
    """Verify character with Brawny edge has Load Limit = Strength die value * 8 lbs."""
    sample_human_character.attributes.strength = strength_die
    sample_human_character.edges.append("Brawny")
    assert DerivedStatsCalculator.calculate_load_limit(sample_human_character) == expected_load_limit
