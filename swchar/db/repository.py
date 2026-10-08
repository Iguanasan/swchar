"""Repository pattern for catalog item queries and character inventory persistence."""

import sqlite3
from typing import Any
from swchar.models.ancestry import get_ancestry
from swchar.models.character import Character
from swchar.models.items import CatalogItem, InventoryItem, ItemCategory


class InventoryRepository:
    """Repository handling catalog item queries and character inventory persistence."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize repository with SQLite connection.

        Args:
            conn: SQLite connection with foreign keys enabled.
        """
        self.conn = conn

    def list_catalog_items(
        self,
        category: str | None = None,
        query: str = "",
    ) -> list[CatalogItem]:
        """Query catalog items, optionally filtering by category and search term.

        Args:
            category: Optional category filter (e.g. 'Melee Weapon').
            query: Optional search string matching name or notes case-insensitively.

        Returns:
            List of CatalogItem matching criteria.
        """
        sql = "SELECT * FROM catalog_items WHERE 1=1"
        params: list[Any] = []

        if category is not None:
            cat_val = category.value if isinstance(category, ItemCategory) else category
            sql += " AND category = ?"
            params.append(cat_val)

        if query.strip():
            clean_query = f"%{query.strip().lower()}%"
            sql += " AND (LOWER(name) LIKE ? OR LOWER(COALESCE(notes, '')) LIKE ?)"
            params.extend([clean_query, clean_query])

        sql += " ORDER BY id"
        cursor = self.conn.execute(sql, params)
        rows = cursor.fetchall()
        return [
            CatalogItem(
                id=row["id"],
                name=row["name"],
                category=row["category"],
                cost=float(row["cost"]),
                weight=float(row["weight"]),
                min_str=row["min_str"],
                damage=row["damage"],
                range=row["range"],
                armor_bonus=int(row["armor_bonus"]),
                parry_bonus=int(row["parry_bonus"]),
                notes=row["notes"] or "",
            )
            for row in rows
        ]

    def get_catalog_item(self, item_id: int) -> CatalogItem | None:
        """Retrieve a catalog item by its integer primary key.

        Args:
            item_id: Integer ID of the item.

        Returns:
            CatalogItem if found, else None.
        """
        cursor = self.conn.execute(
            "SELECT * FROM catalog_items WHERE id = ?",
            (item_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return CatalogItem(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            cost=float(row["cost"]),
            weight=float(row["weight"]),
            min_str=row["min_str"],
            damage=row["damage"],
            range=row["range"],
            armor_bonus=int(row["armor_bonus"]),
            parry_bonus=int(row["parry_bonus"]),
            notes=row["notes"] or "",
        )

    def save_character(self, character: Character) -> None:
        """Persist or update a character in the characters table.

        Args:
            character: Character Wild Card aggregate.
        """
        ancestry_name = (
            character.ancestry.name
            if hasattr(character.ancestry, "name")
            else str(character.ancestry)
        )
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO characters (id, name, concept, ancestry, cash, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    concept = excluded.concept,
                    ancestry = excluded.ancestry,
                    cash = excluded.cash,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    character.id,
                    character.name,
                    character.concept,
                    ancestry_name,
                    float(character.cash),
                ),
            )

    def get_character(self, character_id: str) -> Character | None:
        """Retrieve a character by ID.

        Args:
            character_id: String UUID or ID.

        Returns:
            Character instance if found, else None.
        """
        cursor = self.conn.execute(
            "SELECT id, name, concept, ancestry, cash FROM characters WHERE id = ?",
            (character_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        ancestry_name = row["ancestry"]
        try:
            ancestry = get_ancestry(ancestry_name)
        except (KeyError, ValueError):
            ancestry = get_ancestry("Human")

        return Character(
            id=row["id"],
            name=row["name"],
            concept=row["concept"] or "",
            ancestry=ancestry,
            cash=float(row["cash"]),
        )

    def delete_character(self, character_id: str) -> None:
        """Delete a character record and cascade-delete associated inventory.

        Args:
            character_id: String UUID or ID.
        """
        with self.conn:
            self.conn.execute("DELETE FROM characters WHERE id = ?", (character_id,))

    def save_inventory(self, character_id: str, items: list[InventoryItem]) -> None:
        """Replace all inventory items for a character with the provided items.

        Args:
            character_id: String ID of character.
            items: List of InventoryItem to persist.
        """
        with self.conn:
            self.conn.execute(
                "DELETE FROM character_inventory WHERE character_id = ?",
                (character_id,),
            )
            for item in items:
                cat_val = (
                    item.category.value
                    if isinstance(item.category, ItemCategory)
                    else item.category
                )
                cursor = self.conn.execute(
                    """
                    INSERT INTO character_inventory (
                        character_id, catalog_item_id, custom_name, category,
                        cost, weight, quantity, is_equipped, min_str, damage,
                        armor_bonus, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        character_id,
                        item.catalog_item_id,
                        item.custom_name or item.name,
                        cat_val,
                        float(item.cost),
                        float(item.weight),
                        int(item.quantity),
                        1 if item.is_equipped else 0,
                        item.min_str,
                        item.damage,
                        int(item.armor_bonus),
                        item.notes or "",
                    ),
                )
                item.id = cursor.lastrowid
                item.character_id = character_id

    def get_inventory(self, character_id: str) -> list[InventoryItem]:
        """Fetch all inventory items belonging to a character.

        Args:
            character_id: String ID of character.

        Returns:
            List of InventoryItem instances.
        """
        cursor = self.conn.execute(
            "SELECT * FROM character_inventory WHERE character_id = ? ORDER BY id ASC",
            (character_id,),
        )
        rows = cursor.fetchall()
        items: list[InventoryItem] = []
        for row in rows:
            items.append(
                InventoryItem(
                    id=row["id"],
                    character_id=row["character_id"],
                    catalog_item_id=row["catalog_item_id"],
                    name=row["custom_name"],
                    custom_name=row["custom_name"],
                    category=row["category"],
                    cost=float(row["cost"]),
                    weight=float(row["weight"]),
                    quantity=int(row["quantity"]),
                    is_equipped=bool(row["is_equipped"]),
                    min_str=row["min_str"],
                    damage=row["damage"],
                    armor_bonus=int(row["armor_bonus"]),
                    notes=row["notes"] or "",
                )
            )
        return items

    save_character_inventory = save_inventory
    load_character_inventory = get_inventory
