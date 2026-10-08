"""End-to-end integration tests for Savage Worlds Character Builder (Slice 5).

Verifies acceptance criteria defined in docs/feature-slices.md:
- Complete end-to-end integration test confirming that a character can be created,
  saved to database, exported to XML, and reloaded.
- Full character creation workflow from concept to attributes, skills, hindrances,
  edges, arcana, and inventory.
- Save character and inventory to SQLite database.
- Export character to canonical XML file.
- Import character from XML file.
- Verify imported character matches database character with 100% fidelity across
  all stats, points, gear, and calculations.
- Test application factory / runner create_app() and main(argv).
"""

import os
import sqlite3
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
import pytest

from swchar.core.constants import BASE_BENNIES, STARTING_CASH
from swchar.core.dice import DieType
from swchar.db.catalog_seed import seed_default_catalog
from swchar.db.connection import DatabaseManager, get_db_connection
from swchar.db.repository import InventoryRepository
from swchar.db.schema import init_schema
from swchar.io.xml_deserializer import CharacterXmlDeserializer
from swchar.io.xml_serializer import CharacterXmlSerializer
from swchar.models.ancestry import get_ancestry
from swchar.models.arcana import (
    ArcaneBackgroundType,
    ArcaneConfiguration,
    Power,
    get_arcane_background_defaults,
)
from swchar.models.attributes import AttributeName, Attributes
from swchar.models.character import Character
from swchar.models.edges import Rank
from swchar.models.hindrances import Hindrance, HindranceEconomy, HindranceSeverity
from swchar.models.items import CatalogItem, InventoryItem, ItemCategory
from swchar.models.skills import Skill
from swchar.rules.derived_stats import DerivedStatsCalculator
from swchar.rules.encumbrance import EncumbranceCalculator
from swchar.rules.point_tracker import PointTracker
from swchar.rules.prerequisites import PrerequisiteChecker

# Application factory, controller, and main entrypoint under test (Slice 5)
try:
    from swchar.app import AppController, CharacterState, create_app, main
except ImportError:
    try:
        from swchar.ui.controller import AppController, CharacterState  # type: ignore
        from swchar.app import create_app, main  # type: ignore
    except ImportError:
        # Fallback to swchar.app to trigger RED phase in pytest
        from swchar.app import AppController, CharacterState, create_app, main  # type: ignore


# ==============================================================================
# Fixtures
# ==============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Return path to a new temporary SQLite database file."""
    return tmp_path / "integration_swchar.db"


@pytest.fixture
def seeded_db_conn(temp_db_path: Path) -> sqlite3.Connection:
    """Initialize schema and seed catalog items into a temporary SQLite database."""
    conn = get_db_connection(str(temp_db_path))
    init_schema(conn)
    seed_default_catalog(conn)
    yield conn
    conn.close()


@pytest.fixture
def repo(seeded_db_conn: sqlite3.Connection) -> InventoryRepository:
    """Return an InventoryRepository linked to the seeded database."""
    return InventoryRepository(seeded_db_conn)


# ==============================================================================
# 1. Full Character Creation Workflow (Novice Human Wild Card)
# ==============================================================================


class TestEndToEndCharacterBuilderWorkflow:
    """End-to-end integration tests for character creation, SQLite persistence, and XML round-trip."""

    def test_complete_character_lifecycle_workflow(
        self,
        temp_db_path: Path,
        seeded_db_conn: sqlite3.Connection,
        repo: InventoryRepository,
        tmp_path: Path,
    ) -> None:
        """Execute full character creation workflow from concept to attributes, skills,

        hindrances, edges, arcana, and inventory; save to SQLite, export to XML, import from
        XML, and verify 100% round-trip fidelity across all stats, points, and gear.
        """
        # ----------------------------------------------------------------------
        # Step 1: Initialize Character & Concept
        # ----------------------------------------------------------------------
        char = Character(
            name="Valen Thorne",
            concept="Cyberpunk Bounty Hunter",
            ancestry=get_ancestry("Human"),
            rank=Rank.NOVICE,
            cash=STARTING_CASH,
            bennies=BASE_BENNIES,
        )

        # ----------------------------------------------------------------------
        # Step 2: Configure Attributes (5 base points spent)
        # ----------------------------------------------------------------------
        # Agility: d8 (2 pts), Smarts: d6 (1 pt), Spirit: d6 (1 pt), Strength: d8 (2 pts), Vigor: d6 (1 pt)
        # Total = 7 points (we will reward 2 points from Hindrances below to make budget exact)
        char.attributes.agility = DieType.D8
        char.attributes.smarts = DieType.D6
        char.attributes.spirit = DieType.D6
        char.attributes.strength = DieType.D8
        char.attributes.vigor = DieType.D6

        # ----------------------------------------------------------------------
        # Step 3: Configure Skills (Core + Non-Core)
        # ----------------------------------------------------------------------
        # Core skills:
        char.set_skill("Athletics", DieType.D6, AttributeName.AGILITY, core=True)       # 1 pt
        char.set_skill("Common Knowledge", DieType.D4, AttributeName.SMARTS, core=True) # 0 pt
        char.set_skill("Notice", DieType.D6, AttributeName.SMARTS, core=True)           # 1 pt
        char.set_skill("Persuasion", DieType.D4, AttributeName.SPIRIT, core=True)       # 0 pt
        char.set_skill("Stealth", DieType.D6, AttributeName.AGILITY, core=True)          # 1 pt
        # Non-core skills:
        char.set_skill("Fighting", DieType.D8, AttributeName.AGILITY, core=False)       # 3 pts (d4, d6, d8 <= Agility)
        char.set_skill("Shooting", DieType.D8, AttributeName.AGILITY, core=False)       # 3 pts (d4, d6, d8 <= Agility)
        char.set_skill("Driving", DieType.D6, AttributeName.AGILITY, core=False)        # 2 pts (d4, d6 <= Agility)
        char.set_skill("Survival", DieType.D6, AttributeName.SMARTS, core=False)        # 2 pts (d4, d6 <= Smarts)
        # Total skill points: 1 + 0 + 1 + 0 + 1 + 3 + 3 + 2 + 2 = 13 points spent (12 base + 1 hindrance reward)

        # ----------------------------------------------------------------------
        # Step 4: Add Hindrances (4 points of disadvantage)
        # ----------------------------------------------------------------------
        char.hindrances = [
            Hindrance(name="Heroic", severity=HindranceSeverity.MAJOR, description="Never turns down aid."),
            Hindrance(name="Cautious", severity=HindranceSeverity.MINOR, description="Plans meticulously."),
            Hindrance(name="Loyal", severity=HindranceSeverity.MINOR, description="Never betrays friends."),
        ]

        # ----------------------------------------------------------------------
        # Step 5: Redeem Hindrance Rewards (4 points total)
        # ----------------------------------------------------------------------
        # - 2 points -> +1 Attribute point (raises budget from 5 to 6)
        # - 1 point -> +1 Skill point (raises budget from 12 to 13)
        # - 1 point -> +$500 cash (raises cash from $500 to $1000)
        char.hindrance_rewards = HindranceEconomy(
            total_earned=4,
            usable_points=4,
            attribute_bonuses=1,
            skill_bonuses=1,
            extra_edges=0,
            cash_bonus=500.0,
            spent_points=4,
            remaining_points=0,
        )
        # Adjust starting cash with bonus:
        char.cash = STARTING_CASH + 500.0  # $1000.0

        # Adjust one attribute so total spent is exactly 6 points:
        char.attributes.strength = DieType.D6  # Agility d8 (2) + Smarts d6 (1) + Spirit d6 (1) + Strength d6 (1) + Vigor d6 (1) = 6 pts
        assert PointTracker.get_attribute_points_spent(char) == 6
        assert PointTracker.get_attribute_points_remaining(char) == 0
        assert PointTracker.get_skill_points_spent(char) == 13
        assert PointTracker.get_skill_points_remaining(char) == 0

        # ----------------------------------------------------------------------
        # Step 6: Select Edges (Human Free Edge + Standard Edges)
        # ----------------------------------------------------------------------
        # Prerequisites check:
        # - Alertness (requires Notice d6): satisfied!
        # - Quick (requires Agility d8): satisfied!
        can_take_alertness, _ = PrerequisiteChecker.can_take_edge(char, "Alertness")
        can_take_quick, _ = PrerequisiteChecker.can_take_edge(char, "Quick")
        assert can_take_alertness is True
        assert can_take_quick is True

        char.edges = ["Alertness", "Quick"]

        # ----------------------------------------------------------------------
        # Step 7: Configure Arcana (Mundane character)
        # ----------------------------------------------------------------------
        char.arcana = ArcaneConfiguration(
            background=ArcaneBackgroundType.NONE.value,
            power_points=0,
            powers=[],
        )

        # ----------------------------------------------------------------------
        # Step 8: Purchase & Equip Inventory Items from SQLite Catalog
        # ----------------------------------------------------------------------
        # Query items from catalog
        dagger_catalog = repo.list_catalog_items(query="Dagger")[0]
        glock_catalog = repo.list_catalog_items(query="Glock 9mm")[0]
        armor_catalog = repo.list_catalog_items(category=ItemCategory.ARMOR)[0]  # Leather Jacket / Armor
        gear_catalog = repo.list_catalog_items(query="Backpack")[0]

        # Convert to InventoryItem and calculate purchases
        items_to_buy = [
            InventoryItem.from_catalog_item(dagger_catalog, quantity=1, is_equipped=True),
            InventoryItem.from_catalog_item(glock_catalog, quantity=1, is_equipped=True),
            InventoryItem.from_catalog_item(armor_catalog, quantity=1, is_equipped=True),
            InventoryItem.from_catalog_item(gear_catalog, quantity=1, is_equipped=False),
        ]

        total_purchase_cost = sum(item.cost * item.quantity for item in items_to_buy)
        assert char.cash >= total_purchase_cost
        char.cash -= total_purchase_cost
        char.inventory = items_to_buy

        # ----------------------------------------------------------------------
        # Step 9: Verify Derived Combat Profile Calculations
        # ----------------------------------------------------------------------
        pace_result = DerivedStatsCalculator.calculate_pace(char)
        assert pace_result.pace == 6
        assert pace_result.running_die == DieType.D6

        parry = DerivedStatsCalculator.calculate_parry(char)
        assert parry == 6  # 2 + (Fighting d8 // 2)

        toughness_res = DerivedStatsCalculator.calculate_toughness(
            char, torso_armor=armor_catalog.armor_bonus
        )
        assert toughness_res.base == 5  # 2 + (Vigor d6 // 2)
        assert toughness_res.armor == armor_catalog.armor_bonus
        assert toughness_res.total == 5 + armor_catalog.armor_bonus

        load_limit = DerivedStatsCalculator.calculate_load_limit(char)
        assert load_limit == 30.0  # Strength d6 (6) * 5 lbs

        carried_weight = EncumbranceCalculator.calculate_carried_weight(char.inventory)
        assert carried_weight < load_limit

        encumbrance = EncumbranceCalculator.calculate_encumbrance_penalty(load_limit, carried_weight)
        assert encumbrance.penalty == 0
        assert encumbrance.is_immobilized is False

        # ----------------------------------------------------------------------
        # Step 10: Persist Character & Inventory to SQLite Database
        # ----------------------------------------------------------------------
        repo.save_character(char)
        repo.save_inventory(char.id, char.inventory)

        # Retrieve and verify database records
        db_char = repo.get_character(char.id)
        assert db_char is not None
        assert db_char.id == char.id
        assert db_char.name == "Valen Thorne"
        assert db_char.concept == "Cyberpunk Bounty Hunter"
        assert db_char.ancestry.name == "Human"
        assert db_char.cash == char.cash

        db_inventory = repo.get_inventory(char.id)
        assert len(db_inventory) == 4
        assert {item.name for item in db_inventory} == {item.name for item in char.inventory}
        equipped_db = [item for item in db_inventory if item.is_equipped]
        assert len(equipped_db) == 3

        # ----------------------------------------------------------------------
        # Step 11: Export Complete Character to Canonical XML File
        # ----------------------------------------------------------------------
        xml_file_path = tmp_path / "valen_thorne_export.xml"
        CharacterXmlSerializer.export_to_file(char, xml_file_path)
        assert xml_file_path.exists()
        assert xml_file_path.stat().st_size > 0

        # Read exported XML content and sanity check tags
        xml_text = xml_file_path.read_text(encoding="utf-8")
        assert "<SavageWorldsCharacter" in xml_text
        assert "<Name>Valen Thorne</Name>" in xml_text
        assert '<Attribute name="Agility" die="d8"/>' in xml_text
        assert '<Skill name="Fighting"' in xml_text
        assert "<Pace>6</Pace>" in xml_text

        # ----------------------------------------------------------------------
        # Step 12: Import Character from XML File
        # ----------------------------------------------------------------------
        imported_char = CharacterXmlDeserializer.from_xml_file(xml_file_path)
        assert imported_char is not None

        # ----------------------------------------------------------------------
        # Step 13: 100% Round-Trip Fidelity Verification
        # ----------------------------------------------------------------------
        # Identity
        assert imported_char.id == char.id
        assert imported_char.name == char.name
        assert imported_char.concept == char.concept
        assert imported_char.ancestry.name == char.ancestry.name
        assert imported_char.rank == char.rank
        assert imported_char.bennies == char.bennies
        assert imported_char.cash == pytest.approx(char.cash, 0.01)

        # Attributes
        for attr in [
            AttributeName.AGILITY,
            AttributeName.SMARTS,
            AttributeName.SPIRIT,
            AttributeName.STRENGTH,
            AttributeName.VIGOR,
        ]:
            assert (
                imported_char.attributes[attr] == char.attributes[attr]
            ), f"Attribute {attr.value} mismatch: {imported_char.attributes[attr]} != {char.attributes[attr]}"

        # Skills
        assert len(imported_char.skills) == len(char.skills)
        for skill_name, original_skill in char.skills.items():
            imp_skill = imported_char.get_skill(skill_name)
            assert imp_skill is not None, f"Missing skill {skill_name} in imported character"
            assert imp_skill.die == original_skill.die
            assert imp_skill.attribute == original_skill.attribute
            assert imp_skill.core == original_skill.core

        # Hindrances & Economy
        assert len(imported_char.hindrances) == len(char.hindrances)
        original_hindrance_names = {h.name for h in char.hindrances}
        imported_hindrance_names = {h.name for h in imported_char.hindrances}
        assert original_hindrance_names == imported_hindrance_names

        # Edges
        assert set(imported_char.edges) == set(char.edges)

        # Inventory
        assert len(imported_char.inventory) == len(char.inventory)
        for orig_item in char.inventory:
            matching_imp = next(
                (item for item in imported_char.inventory if item.name == orig_item.name),
                None,
            )
            assert matching_imp is not None, f"Item {orig_item.name} not found in imported character"
            assert matching_imp.quantity == orig_item.quantity
            assert matching_imp.is_equipped == orig_item.is_equipped
            assert matching_imp.cost == pytest.approx(orig_item.cost, 0.01)
            assert matching_imp.weight == pytest.approx(orig_item.weight, 0.01)

        # Derived Combat Statistics on Imported Character
        imp_pace = DerivedStatsCalculator.calculate_pace(imported_char)
        assert imp_pace.pace == pace_result.pace
        assert imp_pace.running_die == pace_result.running_die

        imp_parry = DerivedStatsCalculator.calculate_parry(imported_char)
        assert imp_parry == parry

        imp_toughness = DerivedStatsCalculator.calculate_toughness(
            imported_char, torso_armor=armor_catalog.armor_bonus
        )
        assert imp_toughness.total == toughness_res.total

        imp_load_limit = DerivedStatsCalculator.calculate_load_limit(imported_char)
        assert imp_load_limit == load_limit

        imp_carried_weight = EncumbranceCalculator.calculate_carried_weight(imported_char.inventory)
        assert imp_carried_weight == pytest.approx(carried_weight, 0.01)

        imp_encumbrance = EncumbranceCalculator.calculate_encumbrance_penalty(
            imp_load_limit, imp_carried_weight
        )
        assert imp_encumbrance.penalty == 0

        # Point Budgets on Imported Character
        assert PointTracker.get_attribute_points_spent(imported_char) == 6
        assert PointTracker.get_skill_points_spent(imported_char) == 13


# ==============================================================================
# 2. Arcane Character Creation & Round-Trip Workflow
# ==============================================================================


class TestArcaneCharacterEndToEndWorkflow:
    """Integration test for characters with Arcane Backgrounds and powers."""

    def test_arcane_character_creation_and_xml_roundtrip(
        self,
        seeded_db_conn: sqlite3.Connection,
        repo: InventoryRepository,
        tmp_path: Path,
    ) -> None:
        """Create an Elven Mage character with 3 powers, save to DB, export to XML, and verify fidelity."""
        char = Character(
            name="Aeloria Starweaver",
            concept="Elven Elementalist",
            ancestry=get_ancestry("Elf"),
            rank=Rank.NOVICE,
            cash=STARTING_CASH,
            bennies=BASE_BENNIES,
        )

        # Attributes: Elf starts with Agility d6.
        char.attributes.agility = DieType.D6
        char.attributes.smarts = DieType.D8  # 2 pts
        char.attributes.spirit = DieType.D8  # 2 pts
        char.attributes.strength = DieType.D4 # 0 pts
        char.attributes.vigor = DieType.D6   # 1 pt
        # Total = 5 attribute points spent

        # Core skills + Spellcasting
        char.set_skill("Athletics", DieType.D4, AttributeName.AGILITY, core=True)
        char.set_skill("Common Knowledge", DieType.D4, AttributeName.SMARTS, core=True)
        char.set_skill("Notice", DieType.D6, AttributeName.SMARTS, core=True)
        char.set_skill("Persuasion", DieType.D4, AttributeName.SPIRIT, core=True)
        char.set_skill("Stealth", DieType.D4, AttributeName.AGILITY, core=True)
        # Spellcasting skill (non-core, linked to Smarts)
        char.set_skill("Spellcasting", DieType.D8, AttributeName.SMARTS, core=False)

        # Arcane Background: Magic
        char.arcana = ArcaneConfiguration(
            background=ArcaneBackgroundType.MAGIC.value,
            power_points=10,
            powers=[
                Power(
                    name="Bolt",
                    power_points=1,
                    trappings="Arcane Fire",
                    range="12/24/48",
                    damage="2d6",
                ),
                Power(
                    name="Burst",
                    power_points=2,
                    trappings="Cone of Cold",
                    range="Cone Template",
                    damage="2d6",
                ),
                Power(
                    name="Healing",
                    power_points=3,
                    trappings="Restorative Light",
                    range="Touch",
                ),
            ],
        )

        # Save to SQLite DB
        repo.save_character(char)
        db_char = repo.get_character(char.id)
        assert db_char is not None
        assert db_char.name == "Aeloria Starweaver"
        assert db_char.ancestry.name == "Elf"

        # Export to XML
        xml_path = tmp_path / "aeloria_export.xml"
        CharacterXmlSerializer.export_to_file(char, xml_path)
        assert xml_path.exists()

        # Import from XML
        imported_char = CharacterXmlDeserializer.from_xml_file(xml_path)

        # Verify Arcana Fidelity
        assert imported_char.arcana is not None
        assert imported_char.arcana.background == "Magic"
        assert imported_char.arcana.power_points == 10
        assert len(imported_char.arcana.powers) == 3

        bolt_p = next((p for p in imported_char.arcana.powers if p.name == "Bolt"), None)
        assert bolt_p is not None
        assert bolt_p.power_points == 1
        assert bolt_p.trappings == "Arcane Fire"
        assert bolt_p.damage == "2d6"

        healing_p = next((p for p in imported_char.arcana.powers if p.name == "Healing"), None)
        assert healing_p is not None
        assert healing_p.power_points == 3
        assert healing_p.trappings == "Restorative Light"


# ==============================================================================
# 3. Application Factory & CLI Runner Tests
# ==============================================================================


class TestApplicationFactoryAndRunner:
    """Acceptance tests for application factory create_app() and CLI entrypoint main(argv)."""

    def test_create_app_factory_initializes_controller(
        self, temp_db_path: Path, seeded_db_conn: sqlite3.Connection
    ) -> None:
        """create_app(db_path) factory function initializes AppController and database repository."""
        app = create_app(db_path=str(temp_db_path), headless=True)
        assert app is not None
        # Verify app has access to state and repository
        assert hasattr(app, "state") or hasattr(app, "repo") or hasattr(app, "controller")

    def test_create_app_with_in_memory_db(self) -> None:
        """create_app(':memory:') creates and seeds an in-memory database cleanly."""
        app = create_app(db_path=":memory:", headless=True)
        assert app is not None

    def test_main_cli_help_flag(self) -> None:
        """Running main(['--help']) prints usage instructions and exits with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_main_cli_custom_db_option(self, temp_db_path: Path) -> None:
        """Running main(['--db', path, '--headless']) starts app cleanly with custom database."""
        result = main(["--db", str(temp_db_path), "--headless"])
        # Exit code 0 or returns cleanly
        assert result in (0, None)
