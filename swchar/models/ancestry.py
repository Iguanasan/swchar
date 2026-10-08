"""Ancestry domain models and registry for Savage Worlds Adventure Edition."""

import copy
from dataclasses import dataclass, field
from swchar.core.dice import DieType
from swchar.models.attributes import AttributeName


@dataclass(frozen=True)
class AncestryTrait:
    """Special racial ability, trait, or liability."""

    name: str
    description: str = ""

    def __str__(self) -> str:
        return self.name


@dataclass
class Ancestry:
    """Ancestry definition encapsulating racial modifiers and special traits."""

    name: str
    pace: int = 6
    running_die: DieType = DieType.D6
    size: int = 0
    flying_pace: int = 0
    toughness_bonus: int = 0
    armor_bonus: int = 0
    bennies_bonus: int = 0
    free_edge_count: int = 0
    attribute_bonuses: dict[AttributeName, int] = field(default_factory=dict)
    traits: list[AncestryTrait] = field(default_factory=list)


ANCESTRIES: dict[str, Ancestry] = {
    "Human": Ancestry(
        name="Human",
        pace=6,
        running_die=DieType.D6,
        size=0,
        free_edge_count=1,
        traits=[
            AncestryTrait("Adaptable", "Humans gain one free Edge of their choice at character creation."),
        ],
    ),
    "Android": Ancestry(
        name="Android",
        pace=6,
        running_die=DieType.D6,
        size=0,
        traits=[
            AncestryTrait("Construct", "+2 to recover from Shaken; ignore 1 point of Wound penalties; do not breathe or eat; immune to poison and disease."),
            AncestryTrait("Outsider (Major)", "Subtract 2 from Persuasion rolls."),
            AncestryTrait("Pacifist (Minor)", "Avoids unnecessary violence."),
        ],
    ),
    "Aquarian": Ancestry(
        name="Aquarian",
        pace=6,
        running_die=DieType.D6,
        size=0,
        toughness_bonus=1,
        traits=[
            AncestryTrait("Aquatic", "Cannot drown in oxygenated water; swimming Pace equals swimming skill."),
            AncestryTrait("Toughness", "Dense flesh grants +1 Toughness."),
            AncestryTrait("Dehydration", "Must immerse in water daily or suffer fatigue."),
        ],
    ),
    "Avion": Ancestry(
        name="Avion",
        pace=5,
        running_die=DieType.D4,
        size=0,
        flying_pace=12,
        traits=[
            AncestryTrait("Flight", "Avions can fly at Pace 12."),
            AncestryTrait("Reduced Pace", "Ground Pace 5, running die d4."),
            AncestryTrait("Keen Senses", "+2 to Notice rolls."),
            AncestryTrait("Fragile", "-1 Toughness."),
        ],
    ),
    "Dwarf": Ancestry(
        name="Dwarf",
        pace=5,
        running_die=DieType.D4,
        size=0,
        attribute_bonuses={AttributeName.VIGOR: 1},
        traits=[
            AncestryTrait("Reduced Pace", "Ground Pace 5, running die d4."),
            AncestryTrait("Tough", "Start with a d6 in Vigor instead of a d4."),
            AncestryTrait("Low Light Vision", "Ignore dim and dark lighting penalties."),
        ],
    ),
    "Elf": Ancestry(
        name="Elf",
        pace=6,
        running_die=DieType.D6,
        size=0,
        attribute_bonuses={AttributeName.AGILITY: 1},
        traits=[
            AncestryTrait("Agile", "Start with a d6 in Agility instead of a d4."),
            AncestryTrait("Low Light Vision", "Ignore dim and dark lighting penalties."),
            AncestryTrait("All Thumbs", "Problems operating mechanical devices."),
        ],
    ),
    "Half-Elf": Ancestry(
        name="Half-Elf",
        pace=6,
        running_die=DieType.D6,
        size=0,
        traits=[
            AncestryTrait("Heritage", "Gain one free Novice Edge or start with a d6 in a chosen attribute."),
            AncestryTrait("Low Light Vision", "Ignore dim and dark lighting penalties."),
            AncestryTrait("Outsider", "Subtract 2 from Persuasion with non-half-elves."),
        ],
    ),
    "Half-Folk": Ancestry(
        name="Half-Folk",
        pace=5,
        running_die=DieType.D4,
        size=-1,
        bennies_bonus=1,
        attribute_bonuses={AttributeName.SPIRIT: 1},
        traits=[
            AncestryTrait("Luck", "Start each session with +1 additional Benny."),
            AncestryTrait("Small", "Size -1, reducing Toughness by 1."),
            AncestryTrait("Spirited", "Start with a d6 in Spirit instead of a d4."),
            AncestryTrait("Reduced Pace", "Ground Pace 5, running die d4."),
        ],
    ),
    "Rakashan": Ancestry(
        name="Rakashan",
        pace=6,
        running_die=DieType.D6,
        size=0,
        attribute_bonuses={AttributeName.AGILITY: 1},
        traits=[
            AncestryTrait("Agile", "Start with a d6 in Agility instead of a d4."),
            AncestryTrait("Bite / Claws", "Natural weapons dealing Str+d4 damage."),
            AncestryTrait("Low Light Vision", "Ignore dim and dark lighting penalties."),
        ],
    ),
    "Saurian": Ancestry(
        name="Saurian",
        pace=6,
        running_die=DieType.D6,
        size=0,
        armor_bonus=2,
        traits=[
            AncestryTrait("Natural Armor (+2)", "Scaly hide provides +2 Armor."),
            AncestryTrait("Bite", "Natural weapon dealing Str+d4 damage."),
            AncestryTrait("Environmental Weakness (Cold)", "-4 to resist cold hazards."),
        ],
    ),
}


def get_ancestry(name: str) -> Ancestry:
    """Retrieve an Ancestry instance by name (case-insensitive).

    Raises:
        KeyError: If the ancestry name is not found in ANCESTRIES.
    """
    for key, ancestry in ANCESTRIES.items():
        if key.lower() == name.strip().lower():
            return copy.deepcopy(ancestry)
    raise KeyError(f"Unknown ancestry: '{name}'. Expected one of {list(ANCESTRIES.keys())}")
