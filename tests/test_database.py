"""Unit and integration tests for SQLite database, item catalog, and inventory persistence (Slice 3)."""

import sqlite3
from pathlib import Path
import pytest

from swchar.core.dice import DieType
from swchar.db.connection import DatabaseManager, get_db_connection
from swchar.db.schema import init_schema
from swchar.db.catalog_seed import seed_default_catalog
from swchar.db.repository import InventoryRepository
from swchar.models.ancestry import get_ancestry
from swchar.models.character import Character
from swchar.models.items import CatalogItem, InventoryItem


class TestDatabaseConnection:
    """Tests for SQLite database connection management and configurations."""

    def test_get_db_connection_in_memory(self) -> None:
        """get_db_connection(':memory:') returns an open SQLite connection with foreign keys enabled."""
        conn = get_db_connection(":memory:")
        assert isinstance(conn, sqlite3.Connection)

        # Foreign keys MUST be explicitly enabled in SQLite
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 1, "Foreign keys should be enabled (PRAGMA foreign_keys = ON)"
        conn.close()

    def test_get_db_connection_file(self, tmp_path: Path) -> None:
        """get_db_connection creates and connects to an on-disk SQLite database file."""
        db_file = tmp_path / "test_swchar.db"
        conn = get_db_connection(str(db_file))
        assert isinstance(conn, sqlite3.Connection)
        assert db_file.exists()

        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        assert cursor.fetchone()[0] == 1
        conn.close()

    def test_database_manager_in_memory(self) -> None:
        """DatabaseManager manages in-memory database connections."""
        db_mgr = DatabaseManager(":memory:")
        conn = db_mgr.get_connection()
        assert isinstance(conn, sqlite3.Connection)

        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys;")
        assert cursor.fetchone()[0] == 1
        db_mgr.close()

    def test_database_manager_file(self, tmp_path: Path) -> None:
        """DatabaseManager manages on-disk database file and path resolution."""
        db_file = tmp_path / "managed.db"
        db_mgr = DatabaseManager(str(db_file))
        conn = db_mgr.get_connection()
        assert isinstance(conn, sqlite3.Connection)
        assert db_file.exists()
        db_mgr.close()

    def test_database_manager_context_manager(self, tmp_path: Path) -> None:
        """DatabaseManager supports context manager protocol for automated cleanup."""
        db_file = tmp_path / "ctx_managed.db"
        with DatabaseManager(str(db_file)) as mgr:
            conn = mgr.get_connection()
            assert isinstance(conn, sqlite3.Connection)
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            assert cursor.fetchone()[0] == 1


class TestDatabaseSchema:
    """Tests for DDL table initialization and structural integrity."""

    @pytest.fixture
    def db_conn(self) -> sqlite3.Connection:
        """Provide a fresh in-memory database connection with foreign keys enabled."""
        conn = get_db_connection(":memory:")
        yield conn
        conn.close()

    def test_init_schema_creates_tables(self, db_conn: sqlite3.Connection) -> None:
        """init_schema creates catalog_items, characters, and character_inventory tables."""
        init_schema(db_conn)

        cursor = db_conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row[0] for row in cursor.fetchall()}

        assert "catalog_items" in tables
        assert "characters" in tables
        assert "character_inventory" in tables

    def test_init_schema_is_idempotent(self, db_conn: sqlite3.Connection) -> None:
        """init_schema can be executed multiple times without error."""
        init_schema(db_conn)
        # Second call should not raise OperationalError (table already exists)
        init_schema(db_conn)

    def test_catalog_items_columns(self, db_conn: sqlite3.Connection) -> None:
        """Verify catalog_items table has all required columns and constraints."""
        init_schema(db_conn)
        cursor = db_conn.cursor()
        cursor.execute("PRAGMA table_info(catalog_items);")
        columns = {row[1]: row[2].upper() for row in cursor.fetchall()}

        expected_columns = [
            "id",
            "name",
            "category",
            "cost",
            "weight",
            "min_str",
            "damage",
            "range",
            "armor_bonus",
            "parry_bonus",
            "notes",
        ]
        for col in expected_columns:
            assert col in columns, f"Expected column '{col}' missing from catalog_items"

    def test_characters_columns(self, db_conn: sqlite3.Connection) -> None:
        """Verify characters table has all required columns."""
        init_schema(db_conn)
        cursor = db_conn.cursor()
        cursor.execute("PRAGMA table_info(characters);")
        columns = {row[1]: row[2].upper() for row in cursor.fetchall()}

        expected_columns = ["id", "name", "concept", "ancestry", "cash", "created_at", "updated_at"]
        for col in expected_columns:
            assert col in columns, f"Expected column '{col}' missing from characters"

    def test_character_inventory_columns(self, db_conn: sqlite3.Connection) -> None:
        """Verify character_inventory table has all required columns."""
        init_schema(db_conn)
        cursor = db_conn.cursor()
        cursor.execute("PRAGMA table_info(character_inventory);")
        columns = {row[1]: row[2].upper() for row in cursor.fetchall()}

        expected_columns = [
            "id",
            "character_id",
            "catalog_item_id",
            "custom_name",
            "category",
            "cost",
            "weight",
            "quantity",
            "is_equipped",
            "min_str",
            "damage",
            "armor_bonus",
            "notes",
        ]
        for col in expected_columns:
            assert col in columns, f"Expected column '{col}' missing from character_inventory"

    def test_foreign_key_violation_raises_integrity_error(self, db_conn: sqlite3.Connection) -> None:
        """Inserting inventory item for nonexistent character raises IntegrityError."""
        init_schema(db_conn)
        cursor = db_conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                """
                INSERT INTO character_inventory (
                    character_id, custom_name, category, cost, weight, quantity, is_equipped
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("non-existent-uuid", "Dagger", "Melee Weapon", 25.0, 1.0, 1, 0),
            )
            db_conn.commit()


class TestCatalogSeed:
    """Tests for seeding canonical SWADE equipment catalog data."""

    @pytest.fixture
    def seeded_db(self) -> sqlite3.Connection:
        """Provide an in-memory database with schema initialized and catalog seeded."""
        conn = get_db_connection(":memory:")
        init_schema(conn)
        seed_default_catalog(conn)
        yield conn
        conn.close()

    def test_seed_default_catalog_populates_items(self, seeded_db: sqlite3.Connection) -> None:
        """seed_default_catalog seeds standard items into catalog_items table."""
        cursor = seeded_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM catalog_items;")
        count = cursor.fetchone()[0]
        assert count >= 15, f"Expected at least 15 default catalog items, got {count}"

    def test_seed_default_catalog_idempotency(self, seeded_db: sqlite3.Connection) -> None:
        """Calling seed_default_catalog multiple times does not duplicate items."""
        cursor = seeded_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM catalog_items;")
        initial_count = cursor.fetchone()[0]

        seed_default_catalog(seeded_db)

        cursor.execute("SELECT COUNT(*) FROM catalog_items;")
        assert cursor.fetchone()[0] == initial_count

    def test_seed_contains_canonical_melee_weapons(self, seeded_db: sqlite3.Connection) -> None:
        """Seed contains canonical Melee Weapons: Dagger, Short Sword, Long Sword, Battle Axe."""
        cursor = seeded_db.cursor()
        melee_names = ["Dagger", "Short Sword", "Long Sword", "Battle Axe"]
        for name in melee_names:
            cursor.execute("SELECT * FROM catalog_items WHERE name = ? AND category = 'Melee Weapon';", (name,))
            item = cursor.fetchone()
            assert item is not None, f"Melee weapon '{name}' not found in catalog"

        # Verify specific stats for Dagger: Str+d4, cost 25, weight 1, min str d4
        cursor.execute("SELECT cost, weight, damage, min_str FROM catalog_items WHERE name = 'Dagger';")
        dagger = cursor.fetchone()
        assert dagger[0] == 25.0
        assert dagger[1] == 1.0
        assert "d4" in dagger[2].lower()
        assert dagger[3].lower() == "d4"

        # Verify Long Sword: Str+d8, cost 300, weight 8, min str d8
        cursor.execute("SELECT cost, weight, damage, min_str FROM catalog_items WHERE name = 'Long Sword';")
        sword = cursor.fetchone()
        assert sword[0] == 300.0
        assert sword[1] == 8.0
        assert "d8" in sword[2].lower()
        assert sword[3].lower() == "d8"

    def test_seed_contains_canonical_ranged_weapons(self, seeded_db: sqlite3.Connection) -> None:
        """Seed contains canonical Ranged Weapons: Bow, Crossbow, Glock 9mm, Colt .45."""
        cursor = seeded_db.cursor()
        ranged_names = ["Bow", "Crossbow", "Glock 9mm", "Colt .45"]
        for name in ranged_names:
            cursor.execute("SELECT * FROM catalog_items WHERE name = ? AND category = 'Ranged Weapon';", (name,))
            item = cursor.fetchone()
            assert item is not None, f"Ranged weapon '{name}' not found in catalog"

        # Verify Glock 9mm stats: 2d6, range 12/24/48, cost 200, weight 3, min str d4
        cursor.execute("SELECT cost, weight, damage, range, min_str FROM catalog_items WHERE name = 'Glock 9mm';")
        glock = cursor.fetchone()
        assert glock[0] == 200.0
        assert glock[1] == 3.0
        assert "2d6" in glock[2].lower()
        assert "12/24/48" in glock[3]
        assert glock[4].lower() == "d4"

    def test_seed_contains_canonical_armor(self, seeded_db: sqlite3.Connection) -> None:
        """Seed contains canonical Armor: Leather Jacket, Chainmail, Plate."""
        cursor = seeded_db.cursor()
        cursor.execute("SELECT armor_bonus, cost, weight FROM catalog_items WHERE name = 'Leather Jacket' AND category = 'Armor';")
        leather = cursor.fetchone()
        assert leather is not None
        assert leather[0] >= 1  # Armor +1
        assert leather[1] == 80.0
        assert leather[2] == 5.0

        cursor.execute("SELECT armor_bonus, cost, weight, min_str FROM catalog_items WHERE name = 'Chainmail' AND category = 'Armor';")
        chain = cursor.fetchone()
        assert chain is not None
        assert chain[0] >= 2  # Armor +3 or +2
        assert chain[3].lower() == "d8"

        cursor.execute("SELECT armor_bonus, cost, weight, min_str FROM catalog_items WHERE name LIKE '%Plate%' AND category = 'Armor';")
        plate = cursor.fetchone()
        assert plate is not None
        assert plate[0] >= 3

    def test_seed_contains_canonical_shields(self, seeded_db: sqlite3.Connection) -> None:
        """Seed contains canonical Shields: Small Shield, Medium Shield."""
        cursor = seeded_db.cursor()
        cursor.execute("SELECT parry_bonus, cost, weight FROM catalog_items WHERE name = 'Small Shield' AND category = 'Shield';")
        small_shield = cursor.fetchone()
        assert small_shield is not None
        assert small_shield[0] == 1  # Parry +1
        assert small_shield[1] == 50.0

        cursor.execute("SELECT parry_bonus, cost, weight FROM catalog_items WHERE name = 'Medium Shield' AND category = 'Shield';")
        med_shield = cursor.fetchone()
        assert med_shield is not None
        assert med_shield[0] == 2  # Parry +2
        assert med_shield[1] == 100.0

    def test_seed_contains_canonical_adventuring_gear(self, seeded_db: sqlite3.Connection) -> None:
        """Seed contains canonical Adventuring Gear: Backpack, Bedroll, Rope, Flashlight."""
        cursor = seeded_db.cursor()
        gear_names = ["Backpack", "Bedroll", "Rope", "Flashlight"]
        for name in gear_names:
            cursor.execute("SELECT cost, weight FROM catalog_items WHERE name = ? AND category = 'Adventuring Gear';", (name,))
            gear = cursor.fetchone()
            assert gear is not None, f"Gear '{name}' not found in catalog"

    def test_seed_contains_ammo(self, seeded_db: sqlite3.Connection) -> None:
        """Seed contains ammunition items in 'Ammo' category."""
        cursor = seeded_db.cursor()
        cursor.execute("SELECT COUNT(*) FROM catalog_items WHERE category = 'Ammo';")
        ammo_count = cursor.fetchone()[0]
        assert ammo_count > 0, "Expected at least one ammo item in catalog"


class TestInventoryRepository:
    """Tests for InventoryRepository data access operations."""

    @pytest.fixture
    def repo(self) -> InventoryRepository:
        """Provide an InventoryRepository with initialized and seeded in-memory database."""
        conn = get_db_connection(":memory:")
        init_schema(conn)
        seed_default_catalog(conn)
        return InventoryRepository(conn)

    def test_list_catalog_items_all(self, repo: InventoryRepository) -> None:
        """list_catalog_items without arguments returns all items as CatalogItem instances."""
        items = repo.list_catalog_items()
        assert len(items) >= 15
        assert all(isinstance(i, CatalogItem) for i in items)
        names = [i.name for i in items]
        assert "Dagger" in names
        assert "Glock 9mm" in names
        assert "Backpack" in names

    def test_list_catalog_items_filter_by_category(self, repo: InventoryRepository) -> None:
        """list_catalog_items filters correctly by category."""
        melee = repo.list_catalog_items(category="Melee Weapon")
        assert len(melee) > 0
        assert all(i.category == "Melee Weapon" for i in melee)
        assert any(i.name == "Dagger" for i in melee)
        assert not any(i.name == "Glock 9mm" for i in melee)

        armor = repo.list_catalog_items(category="Armor")
        assert len(armor) > 0
        assert all(i.category == "Armor" for i in armor)

        gear = repo.list_catalog_items(category="Adventuring Gear")
        assert len(gear) > 0
        assert all(i.category == "Adventuring Gear" for i in gear)

    def test_list_catalog_items_search_query(self, repo: InventoryRepository) -> None:
        """list_catalog_items searches item names and notes case-insensitively."""
        # Query matching multiple items
        swords = repo.list_catalog_items(query="sword")
        sword_names = [s.name for s in swords]
        assert "Short Sword" in sword_names
        assert "Long Sword" in sword_names
        assert "Dagger" not in sword_names

        # Case-insensitivity check
        swords_upper = repo.list_catalog_items(query="SWORD")
        assert len(swords_upper) == len(swords)

        # Empty search query returns all
        all_items = repo.list_catalog_items(query="")
        assert len(all_items) >= 15

        # Query yielding no results
        empty = repo.list_catalog_items(query="nonexistent_fantasy_item_xyz")
        assert len(empty) == 0

    def test_list_catalog_items_category_and_query_combined(self, repo: InventoryRepository) -> None:
        """list_catalog_items filters by both category and query simultaneously."""
        # Melee weapon with 'Axe'
        axes = repo.list_catalog_items(category="Melee Weapon", query="axe")
        assert len(axes) >= 1
        assert all(a.category == "Melee Weapon" for a in axes)
        assert any("axe" in a.name.lower() for a in axes)

        # Ranged weapon query for 'Axe' should yield nothing
        no_axes = repo.list_catalog_items(category="Ranged Weapon", query="axe")
        assert len(no_axes) == 0

    def test_get_catalog_item_existing(self, repo: InventoryRepository) -> None:
        """get_catalog_item retrieves item by integer ID."""
        items = repo.list_catalog_items()
        first_item = items[0]
        assert first_item.id is not None

        retrieved = repo.get_catalog_item(first_item.id)
        assert retrieved is not None
        assert retrieved.id == first_item.id
        assert retrieved.name == first_item.name
        assert retrieved.cost == first_item.cost
        assert retrieved.weight == first_item.weight

    def test_get_catalog_item_nonexistent(self, repo: InventoryRepository) -> None:
        """get_catalog_item returns None for non-existent ID."""
        retrieved = repo.get_catalog_item(999999)
        assert retrieved is None

    def test_save_and_get_character(self, repo: InventoryRepository) -> None:
        """save_character persists a character and get_character retrieves it."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
            cash=450.0,
        )
        repo.save_character(char)

        fetched = repo.get_character(char.id)
        assert fetched is not None
        assert fetched.id == char.id
        assert fetched.name == "Valen Thorne"
        assert fetched.concept == "Bounty Hunter"
        assert fetched.ancestry.name == "Human"
        assert fetched.cash == 450.0

    def test_save_character_update_existing(self, repo: InventoryRepository) -> None:
        """save_character updates an already existing character record."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
            cash=500.0,
        )
        repo.save_character(char)

        # Update cash and concept
        char.cash = 320.0
        char.concept = "Veteran Bounty Hunter"
        repo.save_character(char)

        fetched = repo.get_character(char.id)
        assert fetched is not None
        assert fetched.cash == 320.0
        assert fetched.concept == "Veteran Bounty Hunter"

    def test_get_character_nonexistent(self, repo: InventoryRepository) -> None:
        """get_character returns None when character ID is not in database."""
        fetched = repo.get_character("non-existent-id")
        assert fetched is None

    def test_save_inventory_and_get_inventory(self, repo: InventoryRepository) -> None:
        """save_inventory persists character items and get_inventory retrieves them."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
        )
        repo.save_character(char)

        items = [
            InventoryItem(
                name="Glock 9mm",
                category="Ranged Weapon",
                cost=200.0,
                weight=3.0,
                quantity=1,
                is_equipped=True,
                damage="2d6",
                min_str="d4",
                notes="AP 1",
            ),
            InventoryItem(
                name="Backpack",
                category="Adventuring Gear",
                cost=50.0,
                weight=2.0,
                quantity=1,
                is_equipped=False,
            ),
            InventoryItem(
                name="9mm Ammo",
                category="Ammo",
                cost=0.5,
                weight=0.05,
                quantity=50,
                is_equipped=False,
            ),
        ]

        repo.save_inventory(char.id, items)

        retrieved = repo.get_inventory(char.id)
        assert len(retrieved) == 3

        glock = next(i for i in retrieved if i.name == "Glock 9mm")
        assert glock.is_equipped is True
        assert glock.quantity == 1
        assert glock.damage == "2d6"
        assert glock.weight == 3.0

        ammo = next(i for i in retrieved if i.name == "9mm Ammo")
        assert ammo.quantity == 50
        assert ammo.is_equipped is False

    def test_update_inventory_items(self, repo: InventoryRepository) -> None:
        """Modifying inventory items (quantity, equipped status) persists upon save."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
        )
        repo.save_character(char)

        items = [
            InventoryItem(
                name="Dagger",
                category="Melee Weapon",
                cost=25.0,
                weight=1.0,
                quantity=1,
                is_equipped=False,
            ),
            InventoryItem(
                name="Rations",
                category="Adventuring Gear",
                cost=10.0,
                weight=1.0,
                quantity=3,
                is_equipped=False,
            ),
        ]
        repo.save_inventory(char.id, items)

        # Update: equip dagger and increase rations to 7
        current_inv = repo.get_inventory(char.id)
        for item in current_inv:
            if item.name == "Dagger":
                item.is_equipped = True
            elif item.name == "Rations":
                item.quantity = 7

        repo.save_inventory(char.id, current_inv)

        updated_inv = repo.get_inventory(char.id)
        dagger = next(i for i in updated_inv if i.name == "Dagger")
        assert dagger.is_equipped is True

        rations = next(i for i in updated_inv if i.name == "Rations")
        assert rations.quantity == 7

    def test_remove_inventory_item(self, repo: InventoryRepository) -> None:
        """Removing an item from inventory list and saving removes it from persistence."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
        )
        repo.save_character(char)

        items = [
            InventoryItem(name="Dagger", category="Melee Weapon", cost=25.0, weight=1.0),
            InventoryItem(name="Backpack", category="Adventuring Gear", cost=50.0, weight=2.0),
        ]
        repo.save_inventory(char.id, items)

        # Keep only Dagger
        current_inv = repo.get_inventory(char.id)
        retained = [i for i in current_inv if i.name == "Dagger"]
        repo.save_inventory(char.id, retained)

        new_inv = repo.get_inventory(char.id)
        assert len(new_inv) == 1
        assert new_inv[0].name == "Dagger"
        assert not any(i.name == "Backpack" for i in new_inv)

    def test_cascade_deletion_when_character_is_deleted(self, repo: InventoryRepository) -> None:
        """Deleting a character cascades deletion to character_inventory entries."""
        char = Character(
            name="Valen Thorne",
            concept="Bounty Hunter",
            ancestry=get_ancestry("Human"),
        )
        repo.save_character(char)

        items = [
            InventoryItem(name="Dagger", category="Melee Weapon", cost=25.0, weight=1.0),
            InventoryItem(name="Plate", category="Armor", cost=700.0, weight=30.0),
        ]
        repo.save_inventory(char.id, items)

        assert len(repo.get_inventory(char.id)) == 2

        # Delete character using repository method (or direct delete if repository defines delete_character)
        if hasattr(repo, "delete_character"):
            repo.delete_character(char.id)
        else:
            repo.conn.execute("DELETE FROM characters WHERE id = ?;", (char.id,))
            repo.conn.commit()

        # Verify character is gone
        assert repo.get_character(char.id) is None

        # Verify inventory items were cascade-deleted
        cursor = repo.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM character_inventory WHERE character_id = ?;", (char.id,))
        count = cursor.fetchone()[0]
        assert count == 0, f"Expected 0 cascade-deleted inventory items, found {count}"
        assert repo.get_inventory(char.id) == []
