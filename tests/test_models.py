"""Unit tests for swchar domain models: Attributes, Ancestries, Skills, Character."""

import pytest
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.ancestry import Ancestry, ANCESTRIES, get_ancestry
from swchar.models.skills import Skill, CORE_SKILLS, get_core_skills
from swchar.models.character import Character


# ==============================================================================
# Attribute Model Tests
# ==============================================================================

def test_attribute_name_enum_values():
    """Verify all 5 SWADE attributes exist in AttributeName enum."""
    expected_attributes = {"Agility", "Smarts", "Spirit", "Strength", "Vigor"}
    actual_attributes = {attr.value for attr in AttributeName}
    assert actual_attributes == expected_attributes


def test_attributes_default_initialization(default_attributes):
    """Verify that all 5 attributes default to d4."""
    assert default_attributes.agility == DieType.D4
    assert default_attributes.smarts == DieType.D4
    assert default_attributes.spirit == DieType.D4
    assert default_attributes.strength == DieType.D4
    assert default_attributes.vigor == DieType.D4


def test_attributes_custom_initialization(custom_attributes):
    """Verify customized attributes retain assigned DieType values."""
    assert custom_attributes.agility == DieType.D8
    assert custom_attributes.smarts == DieType.D6
    assert custom_attributes.spirit == DieType.D6
    assert custom_attributes.strength == DieType.D10
    assert custom_attributes.vigor == DieType.D8


def test_attributes_dict_and_enum_access(custom_attributes):
    """Verify attributes can be accessed via enum and string indexing."""
    assert custom_attributes[AttributeName.AGILITY] == DieType.D8
    assert custom_attributes["Agility"] == DieType.D8
    assert custom_attributes.get(AttributeName.STRENGTH) == DieType.D10


def test_attributes_mutation(default_attributes):
    """Verify attributes can be updated by attribute name or indexing."""
    default_attributes.agility = DieType.D6
    assert default_attributes.agility == DieType.D6

    default_attributes[AttributeName.VIGOR] = DieType.D8
    assert default_attributes.vigor == DieType.D8


def test_attributes_validation_rejects_invalid_types(default_attributes):
    """Verify setting non-DieType values raises TypeError or ValueError."""
    with pytest.raises((TypeError, ValueError)):
        default_attributes.agility = "invalid"  # type: ignore
    with pytest.raises((TypeError, ValueError)):
        default_attributes[AttributeName.SMARTS] = 6  # type: ignore


# ==============================================================================
# Ancestry Model Tests
# ==============================================================================

def test_all_ten_ancestries_present_in_registry():
    """Verify all 10 SWADE ancestries exist in ANCESTRIES registry."""
    expected_ancestries = {
        "Human", "Android", "Aquarian", "Avion", "Dwarf",
        "Elf", "Half-Elf", "Half-Folk", "Rakashan", "Saurian"
    }
    assert expected_ancestries.issubset(set(ANCESTRIES.keys()))
    for name in expected_ancestries:
        ancestry = get_ancestry(name)
        assert isinstance(ancestry, Ancestry)
        assert ancestry.name == name


def test_get_ancestry_invalid():
    """Verify requesting an unknown ancestry raises KeyError or ValueError."""
    with pytest.raises((KeyError, ValueError)):
        get_ancestry("NonExistentRace")


def test_human_ancestry_baseline():
    """Verify Human baseline traits: pace 6, running die d6, 1 free edge."""
    human = get_ancestry("Human")
    assert human.pace == 6
    assert human.running_die == DieType.D6
    assert human.size == 0
    assert human.free_edge_count == 1 or "Adaptable" in [t.name if hasattr(t, "name") else str(t) for t in human.traits]
    assert len(human.attribute_bonuses) == 0


def test_android_ancestry_baseline():
    """Verify Android traits: construct, pace 6, running die d6."""
    android = get_ancestry("Android")
    assert android.pace == 6
    assert android.running_die == DieType.D6
    assert android.size == 0
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in android.traits]
    assert any("Construct" in t for t in trait_names)


def test_aquarian_ancestry_baseline():
    """Verify Aquarian traits: aquatic, toughness bonus +1, pace 6."""
    aquarian = get_ancestry("Aquarian")
    assert aquarian.pace == 6
    assert aquarian.running_die == DieType.D6
    assert aquarian.size == 0
    assert aquarian.toughness_bonus == 1
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in aquarian.traits]
    assert any("Aquatic" in t for t in trait_names)


def test_avion_ancestry_baseline():
    """Verify Avion traits: ground pace 5, flight pace 12, running die d4."""
    avion = get_ancestry("Avion")
    assert avion.pace == 5
    assert avion.flying_pace == 12
    assert avion.running_die == DieType.D4
    assert avion.size == 0
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in avion.traits]
    assert any("Flight" in t for t in trait_names)


def test_dwarf_ancestry_baseline():
    """Verify Dwarf traits: pace 5, running die d4, Vigor bonus (starts at d6)."""
    dwarf = get_ancestry("Dwarf")
    assert dwarf.pace == 5
    assert dwarf.running_die == DieType.D4
    assert dwarf.size == 0
    assert AttributeName.VIGOR in dwarf.attribute_bonuses or "Vigor" in dwarf.attribute_bonuses
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in dwarf.traits]
    assert any("Reduced Pace" in t or "Slow" in t for t in trait_names)
    assert any("Tough" in t for t in trait_names)
    assert any("Low Light Vision" in t for t in trait_names)


def test_elf_ancestry_baseline():
    """Verify Elf traits: pace 6, Agility bonus (starts at d6), low light vision."""
    elf = get_ancestry("Elf")
    assert elf.pace == 6
    assert elf.running_die == DieType.D6
    assert elf.size == 0
    assert AttributeName.AGILITY in elf.attribute_bonuses or "Agility" in elf.attribute_bonuses
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in elf.traits]
    assert any("Agile" in t for t in trait_names)
    assert any("Low Light Vision" in t for t in trait_names)


def test_half_elf_ancestry_baseline():
    """Verify Half-Elf traits: pace 6, low light vision, heritage."""
    half_elf = get_ancestry("Half-Elf")
    assert half_elf.pace == 6
    assert half_elf.running_die == DieType.D6
    assert half_elf.size == 0
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in half_elf.traits]
    assert any("Low Light Vision" in t for t in trait_names)
    assert any("Heritage" in t for t in trait_names)


def test_half_folk_ancestry_baseline():
    """Verify Half-Folk traits: pace 5, running die d4, size -1, Spirit bonus, Luck."""
    half_folk = get_ancestry("Half-Folk")
    assert half_folk.pace == 5
    assert half_folk.running_die == DieType.D4
    assert half_folk.size == -1
    assert AttributeName.SPIRIT in half_folk.attribute_bonuses or "Spirit" in half_folk.attribute_bonuses
    assert half_folk.bennies_bonus == 1
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in half_folk.traits]
    assert any("Luck" in t for t in trait_names)
    assert any("Small" in t for t in trait_names)


def test_rakashan_ancestry_baseline():
    """Verify Rakashan traits: pace 6, Agility bonus, bite/claws, low light vision."""
    rakashan = get_ancestry("Rakashan")
    assert rakishan_pace := rakishan.pace == 6
    assert rakishan.running_die == DieType.D6
    assert rakishan.size == 0
    assert AttributeName.AGILITY in rakishan.attribute_bonuses or "Agility" in rakishan.attribute_bonuses
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in rakishan.traits]
    assert any("Agile" in t for t in trait_names)
    assert any("Bite" in t or "Claw" in t for t in trait_names)


def test_saurian_ancestry_baseline():
    """Verify Saurian traits: pace 6, natural armor +2, bite."""
    saurian = get_ancestry("Saurian")
    assert saurian.pace == 6
    assert saurian.running_die == DieType.D6
    assert saurian.size == 0
    assert saurian.armor_bonus == 2
    trait_names = [t.name if hasattr(t, "name") else str(t) for t in saurian.traits]
    assert any("Armor" in t for t in trait_names)
    assert any("Bite" in t for t in trait_names)


# ==============================================================================
# Skill Model Tests
# ==============================================================================

def test_core_skills_definition():
    """Verify the 5 standard SWADE core skills and their linked attributes."""
    expected_core = {
        "Athletics": AttributeName.AGILITY,
        "Common Knowledge": AttributeName.SMARTS,
        "Notice": AttributeName.SMARTS,
        "Persuasion": AttributeName.SPIRIT,
        "Stealth": AttributeName.AGILITY,
    }
    core_skills = get_core_skills()
    assert len(core_skills) == 5

    core_map = {s.name: s for s in core_skills}
    for name, linked_attr in expected_core.items():
        assert name in core_map
        assert core_map[name].attribute == linked_attr
        assert core_map[name].core is True
        assert core_map[name].die == DieType.D4


def test_non_core_skill_creation():
    """Verify creating a non-core skill defaults core flag to False."""
    fighting = Skill(name="Fighting", attribute=AttributeName.AGILITY, die=DieType.D8)
    assert fighting.name == "Fighting"
    assert fighting.attribute == AttributeName.AGILITY
    assert fighting.die == DieType.D8
    assert fighting.core is False


def test_skill_die_advancement():
    """Verify advancing a skill's die rating via next_die()."""
    notice = Skill(name="Notice", attribute=AttributeName.SMARTS, die=DieType.D4, core=True)
    notice.die = notice.die.next_die()
    assert notice.die == DieType.D6
    notice.die = notice.die.next_die()
    assert notice.die == DieType.D8


# ==============================================================================
# Character Aggregate Model Tests
# ==============================================================================

def test_character_initialization_defaults(sample_human_character):
    """Verify new character initializes with default attributes, 5 core skills, 3 bennies."""
    char = sample_human_character
    assert char.name == "Valen Thorne"
    assert char.concept == "Bounty Hunter"
    assert char.ancestry.name == "Human"
    assert char.attributes.agility == DieType.D4
    assert char.attributes.vigor == DieType.D4
    assert char.bennies == 3

    # Check 5 core skills are present at d4
    for core_name in ["Athletics", "Common Knowledge", "Notice", "Persuasion", "Stealth"]:
        skill = char.get_skill(core_name)
        assert skill is not None
        assert skill.core is True
        assert skill.die == DieType.D4


def test_character_add_and_get_custom_skills(sample_human_character):
    """Verify adding custom skills to character and retrieving them."""
    char = sample_human_character
    char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
    char.set_skill("Shooting", DieType.D6, AttributeName.AGILITY)

    fighting = char.get_skill("Fighting")
    assert fighting is not None
    assert fighting.die == DieType.D8
    assert fighting.attribute == AttributeName.AGILITY
    assert fighting.core is False

    shooting = char.get_skill("Shooting")
    assert shooting is not None
    assert shooting.die == DieType.D6


def test_character_half_folk_bennies_initialization(sample_half_folk_character):
    """Verify Half-Folk character initializes with 4 bennies from Luck."""
    assert sample_half_folk_character.bennies == 4
