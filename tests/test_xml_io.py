"""Unit and integration tests for XML Serialization Engine - Import & Export (Slice 4).

Verifies acceptance criteria defined in docs/feature-slices.md:
- Serializes complete Character instance into well-formatted, schema-compliant XML.
- Captures identity, attributes, skills, hindrances, edges, arcana, derived stats, cash, and inventory.
- Deserializes valid XML back into a fully formed Character object with complete fidelity.
- Round-trip fidelity across diverse ancestries, edges, hindrances, inventory, and arcane backgrounds.
- Emits informative errors for malformed or invalid XML structures.
- Direct conformance with canonical XML specification in docs/architecture.md.
"""

from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

from swchar.core.constants import BASE_BENNIES, STARTING_CASH
from swchar.core.dice import DieType
from swchar.models.ancestry import get_ancestry
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.character import Character
from swchar.models.edges import Rank
from swchar.models.hindrances import (
    Hindrance,
    HindranceEconomy,
    HindranceSeverity,
)
from swchar.models.items import InventoryItem, ItemCategory
from swchar.models.skills import Skill
from swchar.rules.derived_stats import DerivedStatsCalculator
from swchar.rules.encumbrance import EncumbranceCalculator

# Serialization engine under test (Slice 4)
from swchar.io.xml_serializer import CharacterXmlSerializer
from swchar.io.xml_deserializer import (
    CharacterXmlDeserializer,
    XmlSerializationError,
)

# Optional specific exception types that inherit from XmlSerializationError
try:
    from swchar.io.xml_deserializer import XmlSyntaxError
except ImportError:
    XmlSyntaxError = XmlSerializationError  # type: ignore

try:
    from swchar.io.xml_deserializer import XmlValidationError
except ImportError:
    XmlValidationError = XmlSerializationError  # type: ignore

# Arcana domain model for supernatural backgrounds and powers
try:
    from swchar.models.arcana import Arcana, Power
except ImportError:
    try:
        from swchar.models.arcana import ArcaneBackground as Arcana, Power  # type: ignore
    except ImportError:
        from swchar.models.arcana import Arcana, Power  # type: ignore


# ==============================================================================
# Canonical XML Samples from docs/architecture.md
# ==============================================================================

CANONICAL_ARCHITECTURE_XML = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Id>a1b2c3d4-e5f6-7890-abcd-ef1234567890</Id>
    <Name>Valen Thorne</Name>
    <Concept>Bounty Hunter</Concept>
    <Ancestry>Human</Ancestry>
    <Rank>Novice</Rank>
    <Bennies>3</Bennies>
    <Cash currency="USD">350.00</Cash>
  </Identity>

  <Attributes>
    <Attribute name="Agility" die="d8"/>
    <Attribute name="Smarts" die="d6"/>
    <Attribute name="Spirit" die="d6"/>
    <Attribute name="Strength" die="d6"/>
    <Attribute name="Vigor" die="d6"/>
  </Attributes>

  <Skills>
    <Skill name="Athletics" attribute="Agility" die="d6" core="true"/>
    <Skill name="Common Knowledge" attribute="Smarts" die="d4" core="true"/>
    <Skill name="Notice" attribute="Smarts" die="d6" core="true"/>
    <Skill name="Persuasion" attribute="Spirit" die="d4" core="true"/>
    <Skill name="Stealth" attribute="Agility" die="d6" core="true"/>
    <Skill name="Fighting" attribute="Agility" die="d8" core="false"/>
    <Skill name="Shooting" attribute="Agility" die="d8" core="false"/>
  </Skills>

  <Hindrances>
    <Hindrance name="Cautious" type="Minor"/>
    <Hindrance name="Heroic" type="Major"/>
    <HindranceRewards>
      <AttributePointsBonus>1</AttributePointsBonus>
      <SkillPointsBonus>0</SkillPointsBonus>
      <ExtraEdgesBonus>0</ExtraEdgesBonus>
      <CashBonus>0</CashBonus>
    </HindranceRewards>
  </Hindrances>

  <Edges>
    <Edge name="Quick" category="Combat" origin="Creation"/>
    <Edge name="Alertness" category="Background" origin="Human_Adaptable"/>
  </Edges>

  <DerivedStats>
    <Pace>6</Pace>
    <RunningDie>d6</RunningDie>
    <Parry>6</Parry>
    <Toughness total="7" base="5" armor="2"/>
    <LoadLimit unit="lbs">30</LoadLimit>
    <CarriedWeight unit="lbs">22.5</CarriedWeight>
    <EncumbrancePenalty>0</EncumbrancePenalty>
  </DerivedStats>

  <Arcana>
    <Background name="None"/>
  </Arcana>

  <Inventory>
    <Item>
      <Name>Glock 9mm</Name>
      <Category>Ranged Weapon</Category>
      <Weight>3.0</Weight>
      <Cost>200.0</Cost>
      <Quantity>1</Quantity>
      <Equipped>true</Equipped>
      <Damage>2d6</Damage>
      <Range>12/24/48</Range>
      <MinStr>d4</MinStr>
      <Notes>AP 1, Semi-Auto</Notes>
    </Item>
    <Item>
      <Name>Leather Jacket</Name>
      <Category>Armor</Category>
      <Weight>5.0</Weight>
      <Cost>80.0</Cost>
      <Quantity>1</Quantity>
      <Equipped>true</Equipped>
      <ArmorBonus>1</ArmorBonus>
      <Notes>Covers Torso, Arms</Notes>
    </Item>
  </Inventory>
</SavageWorldsCharacter>"""


CANONICAL_ARCANA_XML = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Id>m1a2g3i4-c5a6-7890-abcd-ef1234567890</Id>
    <Name>Eldrin the Mage</Name>
    <Concept>Battle Mage</Concept>
    <Ancestry>Elf</Ancestry>
    <Rank>Novice</Rank>
    <Bennies>3</Bennies>
    <Cash currency="USD">250.00</Cash>
  </Identity>

  <Attributes>
    <Attribute name="Agility" die="d6"/>
    <Attribute name="Smarts" die="d8"/>
    <Attribute name="Spirit" die="d8"/>
    <Attribute name="Strength" die="d4"/>
    <Attribute name="Vigor" die="d6"/>
  </Attributes>

  <Skills>
    <Skill name="Athletics" attribute="Agility" die="d4" core="true"/>
    <Skill name="Common Knowledge" attribute="Smarts" die="d6" core="true"/>
    <Skill name="Notice" attribute="Smarts" die="d6" core="true"/>
    <Skill name="Persuasion" attribute="Spirit" die="d4" core="true"/>
    <Skill name="Stealth" attribute="Agility" die="d4" core="true"/>
    <Skill name="Spellcasting" attribute="Smarts" die="d8" core="false"/>
  </Skills>

  <Hindrances>
    <Hindrance name="Curious" type="Major"/>
    <HindranceRewards>
      <AttributePointsBonus>0</AttributePointsBonus>
      <SkillPointsBonus>0</SkillPointsBonus>
      <ExtraEdgesBonus>1</ExtraEdgesBonus>
      <CashBonus>0</CashBonus>
    </HindranceRewards>
  </Hindrances>

  <Edges>
    <Edge name="Arcane Background" category="Background" origin="Creation"/>
  </Edges>

  <DerivedStats>
    <Pace>6</Pace>
    <RunningDie>d6</RunningDie>
    <Parry>2</Parry>
    <Toughness total="5" base="5" armor="0"/>
    <LoadLimit unit="lbs">20</LoadLimit>
    <CarriedWeight unit="lbs">4.0</CarriedWeight>
    <EncumbrancePenalty>0</EncumbrancePenalty>
  </DerivedStats>

  <Arcana>
    <Background name="Magic"/>
    <PowerPoints>10</PowerPoints>
    <Powers>
      <Power name="Bolt" trappings="Fire / Sparks"/>
      <Power name="Protection" trappings="Mystic barrier"/>
      <Power name="Burst" trappings="Stream of flame"/>
    </Powers>
  </Arcana>

  <Inventory>
    <Item>
      <Name>Staff</Name>
      <Category>Melee Weapon</Category>
      <Weight>4.0</Weight>
      <Cost>10.0</Cost>
      <Quantity>1</Quantity>
      <Equipped>true</Equipped>
      <Damage>Str+d4</Damage>
      <ParryBonus>1</ParryBonus>
      <Notes>Reach 1, Two Hands, Parry +1</Notes>
    </Item>
  </Inventory>
</SavageWorldsCharacter>"""


# ==============================================================================
# Helper Functions & Character Builders
# ==============================================================================

def make_dwarf_warrior() -> Character:
    """Build a heavily-geared Dwarf fighter with armor, shield, weapon, and rewards."""
    char = Character(
        name="Thorgar Ironbreaker",
        concept="Dwarven Tunnel Fighter",
        ancestry=get_ancestry("Dwarf"),
        cash=150.0,
    )
    char.attributes.strength = DieType.D8
    char.attributes.vigor = DieType.D8
    char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
    char.set_skill("Athletics", DieType.D6, AttributeName.AGILITY)
    char.edges.append("Brawler")
    char.hindrances.append(Hindrance(name="Greedy", severity=HindranceSeverity.MINOR))
    char.hindrances.append(Hindrance(name="Cautious", severity=HindranceSeverity.MINOR))
    char.hindrance_rewards = HindranceEconomy(skill_bonuses=2)
    char.inventory.extend([
        InventoryItem(
            name="Battleaxe",
            category="Melee Weapon",
            cost=300.0,
            weight=10.0,
            quantity=1,
            is_equipped=True,
            damage="Str+d8",
            min_str="d8",
        ),
        InventoryItem(
            name="Medium Shield",
            category="Shield",
            cost=100.0,
            weight=8.0,
            quantity=1,
            is_equipped=True,
            armor_bonus=0,
            parry_bonus=2,
            notes="+2 Parry, -2 Cover vs Ranged",
        ),
        InventoryItem(
            name="Chain Hauberk",
            category="Armor",
            cost=500.0,
            weight=25.0,
            quantity=1,
            is_equipped=True,
            armor_bonus=3,
            min_str="d8",
            notes="Covers Torso, Arms, Legs",
        ),
    ])
    return char


def make_half_folk_thief() -> Character:
    """Build a stealthy Half-Folk rogue with small size and Luck (+1 Benny)."""
    char = Character(
        name="Milo Greenbottle",
        concept="Halfling Burglar",
        ancestry=get_ancestry("Half-Folk"),
        cash=450.0,
    )
    char.attributes.agility = DieType.D8
    char.attributes.smarts = DieType.D6
    char.attributes.spirit = DieType.D6
    char.set_skill("Stealth", DieType.D8, AttributeName.AGILITY)
    char.set_skill("Fighting", DieType.D6, AttributeName.AGILITY)
    char.edges.append("Alertness")
    char.hindrances.append(Hindrance(name="Curious", severity=HindranceSeverity.MAJOR))
    char.inventory.append(
        InventoryItem(
            name="Dagger",
            category="Melee Weapon",
            cost=25.0,
            weight=1.0,
            quantity=2,
            is_equipped=True,
            damage="Str+d4",
        )
    )
    return char


def make_avion_scout() -> Character:
    """Build an Avion winged scout with flight and ranged weaponry."""
    char = Character(
        name="Zephyr Skywatcher",
        concept="Winged Scout",
        ancestry=get_ancestry("Avion"),
        cash=100.0,
    )
    char.attributes.agility = DieType.D8
    char.set_skill("Shooting", DieType.D8, AttributeName.AGILITY)
    char.set_skill("Notice", DieType.D8, AttributeName.SMARTS)
    char.edges.append("Quick")
    char.inventory.extend([
        InventoryItem(
            name="Bow",
            category="Ranged Weapon",
            cost=250.0,
            weight=3.0,
            quantity=1,
            is_equipped=True,
            damage="2d6",
            range="12/24/48",
            min_str="d6",
        ),
        InventoryItem(
            name="Arrows",
            category="Ammo",
            cost=10.0,
            weight=0.1,
            quantity=20,
            is_equipped=False,
        ),
    ])
    return char


def make_saurian_fighter() -> Character:
    """Build a Saurian warrior with natural armor +2."""
    char = Character(
        name="Kroshak",
        concept="Lizardfolk Warrior",
        ancestry=get_ancestry("Saurian"),
        cash=75.0,
    )
    char.attributes.strength = DieType.D8
    char.attributes.vigor = DieType.D8
    char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
    char.edges.append("Brawler")
    char.inventory.append(
        InventoryItem(
            name="Spear",
            category="Melee Weapon",
            cost=100.0,
            weight=5.0,
            quantity=1,
            is_equipped=True,
            damage="Str+d6",
            parry_bonus=1,
            notes="Reach 1, Parry +1 with two hands",
        )
    )
    return char


def make_mage_character() -> Character:
    """Build a spellcasting character with Arcane Background Magic and starting powers."""
    char = Character(
        name="Eldrin the Mage",
        concept="Battle Mage",
        ancestry=get_ancestry("Elf"),
        cash=250.0,
    )
    char.attributes.agility = DieType.D6
    char.attributes.smarts = DieType.D8
    char.attributes.spirit = DieType.D8
    char.attributes.strength = DieType.D4
    char.attributes.vigor = DieType.D6
    char.set_skill("Spellcasting", DieType.D8, AttributeName.SMARTS)
    char.edges.append("Arcane Background")
    char.hindrances.append(Hindrance(name="Curious", severity=HindranceSeverity.MAJOR))
    char.hindrance_rewards = HindranceEconomy(edge_bonuses=1)
    char.arcana = Arcana(
        background="Magic",
        power_points=10,
        powers=[
            Power(name="Bolt", trappings="Fire / Sparks"),
            Power(name="Protection", trappings="Mystic barrier"),
            Power(name="Burst", trappings="Stream of flame"),
        ],
    )
    return char


def assert_characters_equal(char1: Character, char2: Character) -> None:
    """Strictly assert full domain model equality between two characters."""
    # Identity
    assert char1.id == char2.id
    assert char1.name == char2.name
    assert char1.concept == char2.concept
    assert char1.ancestry.name == char2.ancestry.name
    assert char1.rank == char2.rank
    assert char1.bennies == char2.bennies
    assert pytest.approx(char1.cash, rel=1e-2) == char2.cash

    # Attributes
    assert char1.attributes.agility == char2.attributes.agility
    assert char1.attributes.smarts == char2.attributes.smarts
    assert char1.attributes.spirit == char2.attributes.spirit
    assert char1.attributes.strength == char2.attributes.strength
    assert char1.attributes.vigor == char2.attributes.vigor

    # Skills
    for skill_name, skill1 in char1.skills.items():
        skill2 = char2.get_skill(skill_name)
        assert skill2 is not None, f"Skill '{skill_name}' missing in deserialized character"
        assert skill1.die == skill2.die
        assert skill1.core == skill2.core
        assert skill1.attribute == skill2.attribute

    # Hindrances
    h1_names = sorted(h.name if hasattr(h, "name") else str(h) for h in char1.hindrances)
    h2_names = sorted(h.name if hasattr(h, "name") else str(h) for h in char2.hindrances)
    assert h1_names == h2_names

    # Hindrance rewards
    hr1 = getattr(char1, "hindrance_rewards", None)
    hr2 = getattr(char2, "hindrance_rewards", None)
    if hr1 is not None and hr2 is not None:
        assert hr1.attribute_bonuses == hr2.attribute_bonuses
        assert hr1.skill_bonuses == hr2.skill_bonuses
        assert hr1.edge_bonuses == hr2.edge_bonuses
        assert hr1.cash_bonuses == hr2.cash_bonuses

    # Edges
    e1_names = sorted(e.name if hasattr(e, "name") else str(e) for e in char1.edges)
    e2_names = sorted(e.name if hasattr(e, "name") else str(e) for e in char2.edges)
    assert e1_names == e2_names

    # Inventory
    assert len(char1.inventory) == len(char2.inventory)
    for item1 in char1.inventory:
        matching = [
            i for i in char2.inventory
            if (i.name if hasattr(i, "name") else str(i)) == (item1.name if hasattr(item1, "name") else str(item1))
        ]
        assert len(matching) > 0, f"Inventory item '{item1.name}' missing in deserialized character"
        item2 = matching[0]
        assert item1.category == item2.category
        assert pytest.approx(item1.weight, rel=1e-2) == item2.weight
        assert pytest.approx(item1.cost, rel=1e-2) == item2.cost
        assert item1.quantity == item2.quantity
        assert item1.is_equipped == item2.is_equipped
        assert (item1.damage or "") == (item2.damage or "")
        assert (item1.min_str or "") == (item2.min_str or "")
        assert (item1.armor_bonus or 0) == (item2.armor_bonus or 0)

    # Arcana
    a1 = getattr(char1, "arcana", None)
    a2 = getattr(char2, "arcana", None)
    if a1 is not None and getattr(a1, "background", "None").lower() != "none":
        assert a2 is not None
        assert a1.background == a2.background
        assert a1.power_points == a2.power_points
        p1 = getattr(a1, "powers", [])
        p2 = getattr(a2, "powers", [])
        assert len(p1) == len(p2)
        for pow1, pow2 in zip(p1, p2):
            assert pow1.name == pow2.name
            t1 = getattr(pow1, "trappings", getattr(pow1, "trapping", ""))
            t2 = getattr(pow2, "trappings", getattr(pow2, "trapping", ""))
            assert t1 == t2
    else:
        assert a2 is None or getattr(a2, "background", "None").lower() == "none"

    # Derived Stats equality
    p1 = DerivedStatsCalculator.calculate_pace(char1)
    p2 = DerivedStatsCalculator.calculate_pace(char2)
    assert p1.pace == p2.pace
    assert p1.running_die == p2.running_die

    parry1 = DerivedStatsCalculator.calculate_parry(char1)
    parry2 = DerivedStatsCalculator.calculate_parry(char2)
    assert parry1 == parry2

    t1 = DerivedStatsCalculator.calculate_toughness(char1)
    t2 = DerivedStatsCalculator.calculate_toughness(char2)
    assert t1.total == t2.total

    ll1 = DerivedStatsCalculator.calculate_load_limit(char1)
    ll2 = DerivedStatsCalculator.calculate_load_limit(char2)
    assert pytest.approx(ll1, rel=1e-2) == ll2

    cw1 = EncumbranceCalculator.calculate_carried_weight(char1.inventory)
    cw2 = EncumbranceCalculator.calculate_carried_weight(char2.inventory)
    assert pytest.approx(cw1, rel=1e-2) == cw2

    enc1 = EncumbranceCalculator.calculate_encumbrance_penalty(ll1, cw1)
    enc2 = EncumbranceCalculator.calculate_encumbrance_penalty(ll2, cw2)
    assert enc1.penalty == enc2.penalty


# ==============================================================================
# Unit Tests: CharacterXmlSerializer
# ==============================================================================

class TestCharacterXmlSerializer:
    """Verifies that CharacterXmlSerializer produces valid, schema-compliant XML."""

    def test_to_xml_string_returns_xml_declaration(self, sample_human_character: Character) -> None:
        """Serialized XML starts with standard xml declaration with utf-8 encoding."""
        xml_str = CharacterXmlSerializer.to_xml_string(sample_human_character)
        assert isinstance(xml_str, str)
        assert xml_str.strip().startswith("<?xml")
        assert "version=\"1.0\"" in xml_str.lower() or "version='1.0'" in xml_str.lower()
        assert "utf-8" in xml_str.lower()

    def test_to_xml_string_root_element_and_attributes(self, sample_human_character: Character) -> None:
        """Root element is SavageWorldsCharacter with version='1.0' and system='SWADE'."""
        xml_str = CharacterXmlSerializer.to_xml_string(sample_human_character)
        root = ET.fromstring(xml_str)
        assert root.tag == "SavageWorldsCharacter"
        assert root.attrib.get("version") == "1.0"
        assert root.attrib.get("system") == "SWADE"

    def test_to_xml_string_contains_all_major_schema_sections(self, sample_human_character: Character) -> None:
        """Verifies presence of all required canonical blocks defined in docs/architecture.md."""
        xml_str = CharacterXmlSerializer.to_xml_string(sample_human_character)
        root = ET.fromstring(xml_str)
        expected_sections = [
            "Identity",
            "Attributes",
            "Skills",
            "Hindrances",
            "Edges",
            "DerivedStats",
            "Arcana",
            "Inventory",
        ]
        for section in expected_sections:
            elem = root.find(section)
            assert elem is not None, f"Missing required XML section: <{section}>"

    def test_serialize_identity_section_values(self, sample_human_character: Character) -> None:
        """Identity section correctly serializes ID, Name, Concept, Ancestry, Rank, Bennies, and Cash."""
        char = sample_human_character
        char.name = "Valen Thorne"
        char.concept = "Bounty Hunter"
        char.cash = 350.0
        char.bennies = 3

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        ident = root.find("Identity")
        assert ident is not None

        assert ident.findtext("Id") == str(char.id)
        assert ident.findtext("Name") == "Valen Thorne"
        assert ident.findtext("Concept") == "Bounty Hunter"
        assert ident.findtext("Ancestry") == "Human"
        assert ident.findtext("Rank") == "Novice"
        assert ident.findtext("Bennies") == "3"

        cash_elem = ident.find("Cash")
        assert cash_elem is not None
        assert cash_elem.attrib.get("currency") == "USD"
        assert float(cash_elem.text or "0") == pytest.approx(350.0, rel=1e-2)

    def test_serialize_attributes_section_all_five_traits(self, sample_human_character: Character) -> None:
        """Attributes block serializes all 5 traits with correct names and die types."""
        char = sample_human_character
        char.attributes.agility = DieType.D8
        char.attributes.smarts = DieType.D6
        char.attributes.spirit = DieType.D6
        char.attributes.strength = DieType.D10
        char.attributes.vigor = DieType.D8

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        attrs = root.find("Attributes")
        assert attrs is not None

        attr_elements = attrs.findall("Attribute")
        assert len(attr_elements) == 5

        attr_map = {elem.attrib.get("name"): elem.attrib.get("die") for elem in attr_elements}
        assert attr_map["Agility"] == "d8"
        assert attr_map["Smarts"] == "d6"
        assert attr_map["Spirit"] == "d6"
        assert attr_map["Strength"] == "d10"
        assert attr_map["Vigor"] == "d8"

    def test_serialize_skills_section_core_and_non_core(self, sample_human_character: Character) -> None:
        """Skills block serializes all skills with attributes: name, attribute, die, and core flag."""
        char = sample_human_character
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        char.set_skill("Shooting", DieType.D6, AttributeName.AGILITY)

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        skills = root.find("Skills")
        assert skills is not None

        skill_elems = skills.findall("Skill")
        skill_dict = {
            s.attrib.get("name"): {
                "attribute": s.attrib.get("attribute"),
                "die": s.attrib.get("die"),
                "core": s.attrib.get("core"),
            }
            for s in skill_elems
        }

        # Check core skill
        assert "Athletics" in skill_dict
        assert skill_dict["Athletics"]["attribute"] == "Agility"
        assert skill_dict["Athletics"]["core"] in ("true", "True")

        # Check non-core skills
        assert "Fighting" in skill_dict
        assert skill_dict["Fighting"]["die"] == "d8"
        assert skill_dict["Fighting"]["attribute"] == "Agility"
        assert skill_dict["Fighting"]["core"] in ("false", "False")

        assert "Shooting" in skill_dict
        assert skill_dict["Shooting"]["die"] == "d6"

    def test_serialize_hindrances_and_rewards(self, sample_human_character: Character) -> None:
        """Hindrances block serializes hindrances with type, and HindranceRewards child element."""
        char = sample_human_character
        char.hindrances = [
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR),
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR),
        ]
        char.hindrance_rewards = HindranceEconomy(
            attribute_bonuses=1,
            skill_bonuses=0,
            edge_bonuses=0,
            cash_bonuses=0,
        )

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        hindrances = root.find("Hindrances")
        assert hindrances is not None

        h_elems = hindrances.findall("Hindrance")
        assert len(h_elems) == 2
        h_map = {elem.attrib.get("name"): elem.attrib.get("type") for elem in h_elems}
        assert h_map["Cautious"] == "Minor"
        assert h_map["Heroic"] == "Major"

        rewards = hindrances.find("HindranceRewards")
        assert rewards is not None
        assert rewards.findtext("AttributePointsBonus") == "1"
        assert rewards.findtext("SkillPointsBonus") == "0"
        assert rewards.findtext("ExtraEdgesBonus") == "0"
        assert rewards.findtext("CashBonus") == "0"

    def test_serialize_edges_section(self, sample_human_character: Character) -> None:
        """Edges block serializes character edges with name and attributes."""
        char = sample_human_character
        char.edges = ["Quick", "Alertness"]

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        edges = root.find("Edges")
        assert edges is not None

        edge_elems = edges.findall("Edge")
        assert len(edge_elems) == 2
        names = [e.attrib.get("name") for e in edge_elems]
        assert "Quick" in names
        assert "Alertness" in names

    def test_serialize_derived_stats_section(self, sample_human_character: Character) -> None:
        """DerivedStats block reflects accurate pace, parry, toughness, load limit, carried weight."""
        char = sample_human_character
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY)
        char.attributes.vigor = DieType.D6
        char.attributes.strength = DieType.D6

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        derived = root.find("DerivedStats")
        assert derived is not None

        assert derived.findtext("Pace") == "6"
        assert derived.findtext("RunningDie") == "d6"
        assert derived.findtext("Parry") == "6"  # 2 + 8//2 = 6

        toughness_elem = derived.find("Toughness")
        assert toughness_elem is not None
        assert toughness_elem.attrib.get("base") == "5"  # 2 + 6//2 = 5
        assert toughness_elem.attrib.get("armor") == "0"
        assert toughness_elem.attrib.get("total") == "5"

        load_elem = derived.find("LoadLimit")
        assert load_elem is not None
        assert float(load_elem.text or "0") == 30.0  # 6 * 5 = 30 lbs

        encumb_elem = derived.find("EncumbrancePenalty")
        assert encumb_elem is not None
        assert encumb_elem.text == "0"

    def test_serialize_inventory_items_full_attributes(self, sample_human_character: Character) -> None:
        """Inventory block serializes weapons and armor with damage, range, min str, armor bonus, notes."""
        char = sample_human_character
        char.inventory = [
            InventoryItem(
                name="Glock 9mm",
                category="Ranged Weapon",
                cost=200.0,
                weight=3.0,
                quantity=1,
                is_equipped=True,
                damage="2d6",
                range="12/24/48",
                min_str="d4",
                notes="AP 1, Semi-Auto",
            ),
            InventoryItem(
                name="Leather Jacket",
                category="Armor",
                cost=80.0,
                weight=5.0,
                quantity=1,
                is_equipped=True,
                armor_bonus=1,
                notes="Covers Torso, Arms",
            ),
        ]

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        inv = root.find("Inventory")
        assert inv is not None

        items = inv.findall("Item")
        assert len(items) == 2

        item_map = {item.findtext("Name"): item for item in items}
        assert "Glock 9mm" in item_map
        glock = item_map["Glock 9mm"]
        assert glock.findtext("Category") == "Ranged Weapon"
        assert float(glock.findtext("Weight") or "0") == 3.0
        assert float(glock.findtext("Cost") or "0") == 200.0
        assert glock.findtext("Quantity") == "1"
        assert glock.findtext("Equipped") in ("true", "True")
        assert glock.findtext("Damage") == "2d6"
        assert glock.findtext("Range") == "12/24/48"
        assert glock.findtext("MinStr") == "d4"
        assert "AP 1" in (glock.findtext("Notes") or "")

        assert "Leather Jacket" in item_map
        jacket = item_map["Leather Jacket"]
        assert jacket.findtext("Category") == "Armor"
        assert jacket.findtext("ArmorBonus") == "1"

    def test_serialize_empty_inventory(self, sample_human_character: Character) -> None:
        """Character with empty inventory produces valid <Inventory> tag with 0 items."""
        sample_human_character.inventory = []
        xml_str = CharacterXmlSerializer.to_xml_string(sample_human_character)
        root = ET.fromstring(xml_str)
        inv = root.find("Inventory")
        assert inv is not None
        assert len(inv.findall("Item")) == 0

    def test_serialize_non_arcane_character_background_none(self, sample_human_character: Character) -> None:
        """Character with no arcane background serializes <Background name='None'/>."""
        sample_human_character.arcana = None
        xml_str = CharacterXmlSerializer.to_xml_string(sample_human_character)
        root = ET.fromstring(xml_str)
        arcana = root.find("Arcana")
        assert arcana is not None
        bg = arcana.find("Background")
        assert bg is not None
        assert bg.attrib.get("name") == "None"

    def test_export_to_file_path_object(self, sample_human_character: Character, tmp_path: Path) -> None:
        """export_to_file successfully writes valid XML to a Path object."""
        out_file = tmp_path / "exported_character.xml"
        CharacterXmlSerializer.export_to_file(sample_human_character, out_file)
        assert out_file.exists()

        content = out_file.read_text(encoding="utf-8")
        assert content.strip().startswith("<?xml")
        root = ET.fromstring(content)
        assert root.tag == "SavageWorldsCharacter"

    def test_export_to_file_string_path(self, sample_human_character: Character, tmp_path: Path) -> None:
        """export_to_file successfully writes valid XML when given a string path."""
        out_file = str(tmp_path / "exported_char_str.xml")
        CharacterXmlSerializer.export_to_file(sample_human_character, out_file)
        assert Path(out_file).exists()

        content = Path(out_file).read_text(encoding="utf-8")
        root = ET.fromstring(content)
        assert root.tag == "SavageWorldsCharacter"

    def test_export_to_file_instance_and_class_method(self, sample_human_character: Character) -> None:
        """Both instance method and class/static method invocations work cleanly."""
        xml_from_class = CharacterXmlSerializer.to_xml_string(sample_human_character)
        serializer_inst = CharacterXmlSerializer()
        xml_from_inst = serializer_inst.to_xml_string(sample_human_character)
        assert ET.fromstring(xml_from_class).tag == ET.fromstring(xml_from_inst).tag


# ==============================================================================
# Unit Tests: Arcane Backgrounds Serialization
# ==============================================================================

class TestArcaneBackgroundsSerialization:
    """Tests for Arcane Backgrounds (Magic, Gifted, Miracles, Psionics, Weird Science) and Powers."""

    @pytest.mark.parametrize(
        "bg_name,pp,powers_data",
        [
            ("Magic", 10, [("Bolt", "Fire / Sparks"), ("Protection", "Mystic barrier"), ("Burst", "Flames")]),
            ("Gifted", 15, [("Telekinesis", "Glowing violet aura")]),
            ("Miracles", 10, [("Healing", "Golden radiant light"), ("Smite", "Holy vengeance"), ("Boost Trait", "Prayer")]),
            ("Psionics", 10, [("Mind Reading", "Subtle headache"), ("Stun", "Mental scream"), ("Confusion", "Whispers")]),
            ("Weird Science", 15, [("Blast", "Mini-grenade launcher"), ("Fly", "Jetpack harness")]),
        ],
    )
    def test_serialize_arcane_background_types(
        self,
        sample_human_character: Character,
        bg_name: str,
        pp: int,
        powers_data: list[tuple[str, str]],
    ) -> None:
        """Serializes background name, starting power points, and starting powers with trappings."""
        char = sample_human_character
        powers = [Power(name=pname, trappings=ptrap) for pname, ptrap in powers_data]
        char.arcana = Arcana(background=bg_name, power_points=pp, powers=powers)

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        root = ET.fromstring(xml_str)
        arcana = root.find("Arcana")
        assert arcana is not None

        bg = arcana.find("Background")
        assert bg is not None
        assert bg.attrib.get("name") == bg_name

        pp_text = arcana.findtext("PowerPoints")
        assert pp_text == str(pp)

        powers_elem = arcana.find("Powers")
        assert powers_elem is not None
        pow_list = powers_elem.findall("Power")
        assert len(pow_list) == len(powers_data)

        for elem, (expected_name, expected_trap) in zip(pow_list, powers_data):
            assert elem.attrib.get("name") == expected_name
            actual_trap = elem.attrib.get("trappings") or elem.attrib.get("trapping") or elem.text
            assert actual_trap == expected_trap

    def test_round_trip_magic_powers_and_trappings(self) -> None:
        """Round-trip character with Magic, 10 PP, and powers with detailed trappings."""
        char = make_mage_character()
        xml_str = CharacterXmlSerializer.to_xml_string(char)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)

        assert deserialized.arcana is not None
        assert deserialized.arcana.background == "Magic"
        assert deserialized.arcana.power_points == 10
        assert len(deserialized.arcana.powers) == 3

        p_map = {
            p.name: getattr(p, "trappings", getattr(p, "trapping", ""))
            for p in deserialized.arcana.powers
        }
        assert p_map["Bolt"] == "Fire / Sparks"
        assert p_map["Protection"] == "Mystic barrier"
        assert p_map["Burst"] == "Stream of flame"

    def test_round_trip_psionics_powers_and_trappings(self, sample_human_character: Character) -> None:
        """Round-trip Psionic character with powers."""
        char = sample_human_character
        char.arcana = Arcana(
            background="Psionics",
            power_points=10,
            powers=[
                Power(name="Mind Reading", trappings="Subtle pulse"),
                Power(name="Telepathy", trappings="Psionic link"),
            ],
        )

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)

        assert deserialized.arcana is not None
        assert deserialized.arcana.background == "Psionics"
        assert deserialized.arcana.power_points == 10
        assert len(deserialized.arcana.powers) == 2
        assert deserialized.arcana.powers[0].name == "Mind Reading"
        assert deserialized.arcana.powers[1].name == "Telepathy"


# ==============================================================================
# Unit Tests: CharacterXmlDeserializer
# ==============================================================================

class TestCharacterXmlDeserializer:
    """Verifies that CharacterXmlDeserializer correctly constructs domain Character instances."""

    def test_deserialize_canonical_architecture_xml(self) -> None:
        """Deserializes canonical XML from docs/architecture.md into exact domain model."""
        char = CharacterXmlDeserializer.from_xml_string(CANONICAL_ARCHITECTURE_XML)
        assert isinstance(char, Character)

        # Identity
        assert char.id == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert char.name == "Valen Thorne"
        assert char.concept == "Bounty Hunter"
        assert char.ancestry.name == "Human"
        assert char.rank == Rank.NOVICE
        assert char.bennies == 3
        assert pytest.approx(char.cash, rel=1e-2) == 350.0

        # Attributes
        assert char.attributes.agility == DieType.D8
        assert char.attributes.smarts == DieType.D6
        assert char.attributes.spirit == DieType.D6
        assert char.attributes.strength == DieType.D6
        assert char.attributes.vigor == DieType.D6

        # Skills
        athletics = char.get_skill("Athletics")
        assert athletics is not None
        assert athletics.die == DieType.D6
        assert athletics.core is True

        fighting = char.get_skill("Fighting")
        assert fighting is not None
        assert fighting.die == DieType.D8
        assert fighting.core is False

        shooting = char.get_skill("Shooting")
        assert shooting is not None
        assert shooting.die == DieType.D8
        assert shooting.core is False

        # Hindrances & Rewards
        h_names = [h.name if hasattr(h, "name") else str(h) for h in char.hindrances]
        assert "Cautious" in h_names
        assert "Heroic" in h_names
        assert char.hindrance_rewards.attribute_bonuses == 1
        assert char.hindrance_rewards.skill_bonuses == 0

        # Edges
        edge_names = [e.name if hasattr(e, "name") else str(e) for e in char.edges]
        assert "Quick" in edge_names
        assert "Alertness" in edge_names

        # Inventory
        assert len(char.inventory) == 2
        inv_map = {item.name: item for item in char.inventory}
        assert "Glock 9mm" in inv_map
        glock = inv_map["Glock 9mm"]
        assert glock.category == ItemCategory.RANGED_WEAPON or glock.category == "Ranged Weapon"
        assert glock.weight == 3.0
        assert glock.cost == 200.0
        assert glock.is_equipped is True
        assert glock.damage == "2d6"
        assert glock.min_str == "d4"

        assert "Leather Jacket" in inv_map
        jacket = inv_map["Leather Jacket"]
        assert jacket.armor_bonus == 1

        # Arcana
        assert char.arcana is None or getattr(char.arcana, "background", "").lower() == "none"

    def test_deserialize_canonical_arcana_xml(self) -> None:
        """Deserializes canonical Arcana XML with Magic, 10 PP, and powers."""
        char = CharacterXmlDeserializer.from_xml_string(CANONICAL_ARCANA_XML)
        assert char.name == "Eldrin the Mage"
        assert char.ancestry.name == "Elf"
        assert char.arcana is not None
        assert char.arcana.background == "Magic"
        assert char.arcana.power_points == 10
        assert len(char.arcana.powers) == 3

        p_names = [p.name for p in char.arcana.powers]
        assert p_names == ["Bolt", "Protection", "Burst"]

    def test_import_from_file_path_object(self, tmp_path: Path) -> None:
        """import_from_file correctly parses a character from a Path object."""
        file_path = tmp_path / "canonical.xml"
        file_path.write_text(CANONICAL_ARCHITECTURE_XML, encoding="utf-8")

        char = CharacterXmlDeserializer.import_from_file(file_path)
        assert char.name == "Valen Thorne"
        assert char.attributes.agility == DieType.D8

    def test_import_from_file_string_path(self, tmp_path: Path) -> None:
        """import_from_file correctly parses a character from a string path."""
        file_path = tmp_path / "canonical_str.xml"
        file_path.write_text(CANONICAL_ARCHITECTURE_XML, encoding="utf-8")

        char = CharacterXmlDeserializer.import_from_file(str(file_path))
        assert char.name == "Valen Thorne"
        assert char.attributes.agility == DieType.D8

    def test_deserialize_non_human_ancestries(self) -> None:
        """Deserializing non-human ancestries correctly instantiates Ancestry model."""
        ancestries = ["Dwarf", "Half-Folk", "Avion", "Saurian", "Rakashan"]
        for anc_name in ancestries:
            xml = f"""<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Id>test-id</Id>
    <Name>Test {anc_name}</Name>
    <Ancestry>{anc_name}</Ancestry>
    <Rank>Novice</Rank>
    <Bennies>3</Bennies>
    <Cash currency="USD">500.00</Cash>
  </Identity>
  <Attributes>
    <Attribute name="Agility" die="d4"/>
    <Attribute name="Smarts" die="d4"/>
    <Attribute name="Spirit" die="d4"/>
    <Attribute name="Strength" die="d4"/>
    <Attribute name="Vigor" die="d4"/>
  </Attributes>
  <Skills/>
  <Hindrances/>
  <Edges/>
  <DerivedStats/>
  <Arcana><Background name="None"/></Arcana>
  <Inventory/>
</SavageWorldsCharacter>"""
            char = CharacterXmlDeserializer.from_xml_string(xml)
            assert char.ancestry.name == anc_name


# ==============================================================================
# Integration Tests: Full Round-Trip Fidelity
# ==============================================================================

class TestRoundTripSerialization:
    """Verifies that Character -> XML -> Character preserves complete data fidelity."""

    def test_round_trip_baseline_human(self, sample_human_character: Character) -> None:
        """Baseline human round-trips without data loss."""
        xml_str = CharacterXmlSerializer.to_xml_string(sample_human_character)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)
        assert_characters_equal(sample_human_character, deserialized)

    def test_round_trip_dwarf_warrior(self) -> None:
        """Dwarf with heavy armor, shield, weapons, and rewards round-trips accurately."""
        dwarf = make_dwarf_warrior()
        xml_str = CharacterXmlSerializer.to_xml_string(dwarf)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)
        assert_characters_equal(dwarf, deserialized)

    def test_round_trip_half_folk_thief(self) -> None:
        """Half-Folk with size -1 and 4 bennies round-trips accurately."""
        halfling = make_half_folk_thief()
        xml_str = CharacterXmlSerializer.to_xml_string(halfling)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)
        assert_characters_equal(halfling, deserialized)

    def test_round_trip_avion_scout(self) -> None:
        """Avion with flight, bow, and ammunition quantities round-trips accurately."""
        avion = make_avion_scout()
        xml_str = CharacterXmlSerializer.to_xml_string(avion)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)
        assert_characters_equal(avion, deserialized)

    def test_round_trip_saurian_fighter(self) -> None:
        """Saurian with natural armor and spear round-trips accurately."""
        saurian = make_saurian_fighter()
        xml_str = CharacterXmlSerializer.to_xml_string(saurian)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)
        assert_characters_equal(saurian, deserialized)

    def test_round_trip_mage_character(self) -> None:
        """Mage with Arcane Background Magic and spells round-trips accurately."""
        mage = make_mage_character()
        xml_str = CharacterXmlSerializer.to_xml_string(mage)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)
        assert_characters_equal(mage, deserialized)

    def test_round_trip_via_file_io(self, tmp_path: Path) -> None:
        """Export to file followed by import from file preserves complete character model."""
        original = make_dwarf_warrior()
        file_path = tmp_path / "round_trip_dwarf.xml"

        CharacterXmlSerializer.export_to_file(original, file_path)
        loaded = CharacterXmlDeserializer.import_from_file(file_path)

        assert_characters_equal(original, loaded)

    def test_round_trip_special_characters_escaping(self, sample_human_character: Character) -> None:
        """Special XML characters (&, <, >, ', \") in names and notes are escaped and preserved."""
        char = sample_human_character
        char.name = "T'Chala & \"The Ghost\""
        char.concept = "Bounty Hunter <Rogue>"
        char.inventory = [
            InventoryItem(
                name="Custom Blade & Shield",
                category="Melee Weapon",
                notes="Dangerous & Sharp > other blades; 'indestructible' property",
                cost=120.0,
                weight=4.0,
            )
        ]

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)

        assert deserialized.name == "T'Chala & \"The Ghost\""
        assert deserialized.concept == "Bounty Hunter <Rogue>"
        assert deserialized.inventory[0].name == "Custom Blade & Shield"
        assert deserialized.inventory[0].notes == "Dangerous & Sharp > other blades; 'indestructible' property"

    def test_round_trip_unicode_text(self, sample_human_character: Character) -> None:
        """Characters with unicode characters (accents, umlauts, runes) round-trip without corruption."""
        char = sample_human_character
        char.name = "Björn Æthelred"
        char.concept = "Viking Berserker — Shield-Maiden"

        xml_str = CharacterXmlSerializer.to_xml_string(char)
        deserialized = CharacterXmlDeserializer.from_xml_string(xml_str)

        assert deserialized.name == "Björn Æthelred"
        assert deserialized.concept == "Viking Berserker — Shield-Maiden"


# ==============================================================================
# Error Handling & Validation Tests
# ==============================================================================

class TestXmlErrorHandling:
    """Verifies that invalid or malformed XML inputs raise descriptive exceptions."""

    def test_malformed_xml_unclosed_tag(self) -> None:
        """Malformed XML syntax with unclosed tags raises XmlSerializationError or XmlSyntaxError."""
        bad_xml = "<SavageWorldsCharacter><Identity><Name>Broken"
        with pytest.raises((XmlSerializationError, XmlSyntaxError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_malformed_xml_mismatched_tags(self) -> None:
        """Malformed XML syntax with mismatched tags raises XmlSerializationError or XmlSyntaxError."""
        bad_xml = "<SavageWorldsCharacter><Identity><Name>Broken</Concept></Identity></SavageWorldsCharacter>"
        with pytest.raises((XmlSerializationError, XmlSyntaxError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_malformed_xml_empty_string(self) -> None:
        """Empty XML string raises XmlSerializationError or XmlSyntaxError."""
        with pytest.raises((XmlSerializationError, XmlSyntaxError)):
            CharacterXmlDeserializer.from_xml_string("")

    def test_malformed_xml_whitespace_only(self) -> None:
        """Whitespace-only XML string raises XmlSerializationError or XmlSyntaxError."""
        with pytest.raises((XmlSerializationError, XmlSyntaxError)):
            CharacterXmlDeserializer.from_xml_string("   \n\t  ")

    def test_invalid_root_element(self) -> None:
        """XML with incorrect root element raises descriptive XmlSerializationError or XmlValidationError."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<NotACharacter version="1.0" system="SWADE">
  <Identity><Name>Hero</Name><Ancestry>Human</Ancestry></Identity>
</NotACharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_missing_identity_element(self) -> None:
        """XML missing <Identity> element raises descriptive error."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Attributes>
    <Attribute name="Agility" die="d4"/>
    <Attribute name="Smarts" die="d4"/>
    <Attribute name="Spirit" die="d4"/>
    <Attribute name="Strength" die="d4"/>
    <Attribute name="Vigor" die="d4"/>
  </Attributes>
</SavageWorldsCharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_missing_ancestry_element(self) -> None:
        """XML missing <Ancestry> inside <Identity> raises descriptive error."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Name>Nameless</Name>
  </Identity>
  <Attributes>
    <Attribute name="Agility" die="d4"/>
    <Attribute name="Smarts" die="d4"/>
    <Attribute name="Spirit" die="d4"/>
    <Attribute name="Strength" die="d4"/>
    <Attribute name="Vigor" die="d4"/>
  </Attributes>
</SavageWorldsCharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_unknown_ancestry_raises_error(self) -> None:
        """Unknown ancestry name raises descriptive error."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Name>Spock</Name>
    <Ancestry>Vulcan</Ancestry>
  </Identity>
  <Attributes>
    <Attribute name="Agility" die="d4"/>
    <Attribute name="Smarts" die="d4"/>
    <Attribute name="Spirit" die="d4"/>
    <Attribute name="Strength" die="d4"/>
    <Attribute name="Vigor" die="d4"/>
  </Attributes>
</SavageWorldsCharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError, KeyError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_invalid_die_type_in_attribute(self) -> None:
        """Invalid die string (e.g. die='d99') raises validation error."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Name>Cheater</Name>
    <Ancestry>Human</Ancestry>
  </Identity>
  <Attributes>
    <Attribute name="Agility" die="d99"/>
    <Attribute name="Smarts" die="d6"/>
    <Attribute name="Spirit" die="d6"/>
    <Attribute name="Strength" die="d6"/>
    <Attribute name="Vigor" die="d6"/>
  </Attributes>
</SavageWorldsCharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError, ValueError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_invalid_die_type_in_skill(self) -> None:
        """Invalid die string in skill (e.g. die='d7') raises validation error."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Name>Cheater</Name>
    <Ancestry>Human</Ancestry>
  </Identity>
  <Attributes>
    <Attribute name="Agility" die="d6"/>
    <Attribute name="Smarts" die="d6"/>
    <Attribute name="Spirit" die="d6"/>
    <Attribute name="Strength" die="d6"/>
    <Attribute name="Vigor" die="d6"/>
  </Attributes>
  <Skills>
    <Skill name="Fighting" attribute="Agility" die="d7" core="false"/>
  </Skills>
</SavageWorldsCharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError, ValueError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_missing_attributes_block(self) -> None:
        """Missing <Attributes> block raises descriptive validation error."""
        bad_xml = """<?xml version="1.0" encoding="utf-8"?>
<SavageWorldsCharacter version="1.0" system="SWADE">
  <Identity>
    <Name>No Attributes</Name>
    <Ancestry>Human</Ancestry>
  </Identity>
</SavageWorldsCharacter>"""
        with pytest.raises((XmlSerializationError, XmlValidationError)):
            CharacterXmlDeserializer.from_xml_string(bad_xml)

    def test_corrupted_numeric_values_raise_error(self) -> None:
        """Non-numeric values in numeric fields (Cash, Bennies, Quantity) raise error."""
        bad_cash_xml = CANONICAL_ARCHITECTURE_XML.replace(
            '<Cash currency="USD">350.00</Cash>',
            '<Cash currency="USD">five hundred</Cash>',
        )
        with pytest.raises((XmlSerializationError, XmlValidationError, ValueError)):
            CharacterXmlDeserializer.from_xml_string(bad_cash_xml)

    def test_import_from_nonexistent_file_raises_not_found(self, tmp_path: Path) -> None:
        """Attempting to import from a non-existent file path raises FileNotFoundError."""
        non_existent = tmp_path / "does_not_exist.xml"
        with pytest.raises(FileNotFoundError):
            CharacterXmlDeserializer.import_from_file(non_existent)
