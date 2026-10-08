"""Pytest fixtures for swchar domain models and derived stats."""

import pytest
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.ancestry import get_ancestry
from swchar.models.character import Character


@pytest.fixture
def default_attributes() -> Attributes:
    """Return default attributes with all traits set to d4."""
    return Attributes()


@pytest.fixture
def custom_attributes() -> Attributes:
    """Return attributes customized above baseline."""
    return Attributes(
        agility=DieType.D8,
        smarts=DieType.D6,
        spirit=DieType.D6,
        strength=DieType.D10,
        vigor=DieType.D8,
    )


@pytest.fixture
def sample_human_character() -> Character:
    """Return a standard baseline Novice Human character."""
    return Character(
        name="Valen Thorne",
        concept="Bounty Hunter",
        ancestry=get_ancestry("Human"),
    )


@pytest.fixture
def sample_dwarf_character() -> Character:
    """Return a Novice Dwarf character."""
    char = Character(
        name="Thorgar Stonehelm",
        concept="Dwarven Tunnel Fighter",
        ancestry=get_ancestry("Dwarf"),
    )
    char.attributes.vigor = DieType.D6
    return char


@pytest.fixture
def sample_half_folk_character() -> Character:
    """Return a Novice Half-Folk character."""
    char = Character(
        name="Milo Greenbottle",
        concept="Halfling Burglar",
        ancestry=get_ancestry("Half-Folk"),
    )
    char.attributes.spirit = DieType.D6
    return char


@pytest.fixture
def sample_avion_character() -> Character:
    """Return a Novice Avion character."""
    return Character(
        name="Zephyr Skywatcher",
        concept="Winged Scout",
        ancestry=get_ancestry("Avion"),
    )


@pytest.fixture
def sample_saurian_character() -> Character:
    """Return a Novice Saurian character."""
    return Character(
        name="Kroshak",
        concept="Lizardfolk Warrior",
        ancestry=get_ancestry("Saurian"),
    )


@pytest.fixture
def sample_aquarian_character() -> Character:
    """Return a Novice Aquarian character."""
    return Character(
        name="Marina Deepstrider",
        concept="Aquatic Explorer",
        ancestry=get_ancestry("Aquarian"),
    )


@pytest.fixture
def sample_elf_character() -> Character:
    """Return a Novice Elf character."""
    char = Character(
        name="Aeloria",
        concept="Elven Scout",
        ancestry=get_ancestry("Elf"),
    )
    char.attributes.agility = DieType.D6
    return char


@pytest.fixture
def sample_half_elf_character() -> Character:
    """Return a Novice Half-Elf character."""
    return Character(
        name="Corin Half-Elven",
        concept="Wandering Ranger",
        ancestry=get_ancestry("Half-Elf"),
    )


@pytest.fixture
def sample_android_character() -> Character:
    """Return a Novice Android character."""
    return Character(
        name="Unit 734",
        concept="Synth Enforcer",
        ancestry=get_ancestry("Android"),
    )


@pytest.fixture
def sample_rakashan_character() -> Character:
    """Return a Novice Rakashan character."""
    char = Character(
        name="T’Chala",
        concept="Feline Huntress",
        ancestry=get_ancestry("Rakashan"),
    )
    char.attributes.agility = DieType.D6
    return char
